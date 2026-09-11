import asyncio
import json
import logging
import redis.asyncio as aioredis
from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.models import EventRecord, PIIVault, DeadLetterQueue
from app.pii import mask_payload_recursively
from app.erp import send_to_erp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FieldKitWorker")

STREAM_NAME = "events:stream"
GROUP_NAME = "fieldkit_workers"
CONSUMER_NAME = "worker_core_1"

async def process_single_event(event_id: str, raw_data_str: str) -> None:
    try:
        data = json.loads(raw_data_str)
    except Exception as exc:
        logger.error(f"Malformed JSON for event {event_id}: {exc}")
        return

    # 1. PII Masking
    masked_payload, vault_entries = mask_payload_recursively(data)

    async with AsyncSessionLocal() as session:
        # Check DB-level idempotency
        existing = await session.get(EventRecord, event_id)
        if existing:
            logger.info(f"Event {event_id} already exists in DB. Skipping.")
            return

        # 2. Persist sanitized event record
        event_record = EventRecord(
            id=event_id,
            source=masked_payload.get("source", "webhook"),
            event_type=masked_payload.get("type", "generic"),
            payload_masked=masked_payload,
            synced_to_erp=False,
            erp_sync_attempts=0
        )
        session.add(event_record)

        # 3. Store reversible PII entries in isolated vault table
        for entry in vault_entries:
            pv = PIIVault(
                event_id=event_id,
                pii_token=entry["token"],
                pii_type=entry["type"],
                encrypted_value=entry["encrypted"]
            )
            session.add(pv)

        await session.commit()
        logger.info(f"Event {event_id} masked and persisted to DB.")

        # 4. Outbound ERP Sync with retries & backoff
        summary_payload = {
            "ref_id": event_id,
            "type": masked_payload.get("type", "field_event"),
            "timestamp": masked_payload.get("timestamp"),
            "summary": masked_payload.get("summary", "FieldKit edge event")
        }

        success, note = await send_to_erp(summary_payload, max_retries=3, initial_delay=0.3)

        if success:
            event_record.synced_to_erp = True
            event_record.erp_sync_attempts = 1
            await session.commit()
            logger.info(f"Event {event_id} successfully synced to ERP.")
        else:
            # 5. Route to Dead Letter Queue (DLQ)
            logger.warning(f"ERP sync failed for {event_id}. Routing to DLQ: {note}")
            event_record.erp_sync_attempts = 3
            dlq_entry = DeadLetterQueue(
                event_id=event_id,
                destination="ERP_SYNC",
                error_reason=note,
                attempts=3,
                payload=summary_payload
            )
            session.add(dlq_entry)
            await session.commit()

async def start_worker():
    await init_db()
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    # Initialize consumer group
    try:
        await redis_client.xgroup_create(STREAM_NAME, GROUP_NAME, id="0", mkstream=True)
        logger.info(f"Created consumer group '{GROUP_NAME}' on stream '{STREAM_NAME}'.")
    except Exception:
        logger.info(f"Consumer group '{GROUP_NAME}' already registered.")

    logger.info(f"Worker '{CONSUMER_NAME}' listening for incoming stream events...")

    while True:
        try:
            # Read new messages for this group
            entries = await redis_client.xreadgroup(
                GROUP_NAME, CONSUMER_NAME, {STREAM_NAME: ">"}, count=5, block=2000
            )
            if not entries:
                continue

            for stream_name, messages in entries:
                for message_id, fields in messages:
                    event_id = fields.get("event_id")
                    raw_data = fields.get("data")
                    if event_id and raw_data:
                        await process_single_event(event_id, raw_data)
                    # Acknowledge processed message in the stream
                    await redis_client.xack(STREAM_NAME, GROUP_NAME, message_id)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            err_str = str(exc)
            if "NOGROUP" in err_str:
                # Consumer group was lost (e.g. Redis flush or restart) — recreate it
                try:
                    await redis_client.xgroup_create(STREAM_NAME, GROUP_NAME, id="0", mkstream=True)
                    logger.warning(f"Recreated consumer group '{GROUP_NAME}' after NOGROUP error.")
                except Exception:
                    pass  # BUSYGROUP means it already exists — race condition, safe to ignore
            else:
                logger.error(f"Worker loop error: {exc}")
            await asyncio.sleep(1)

    await redis_client.close()

if __name__ == "__main__":
    asyncio.run(start_worker())