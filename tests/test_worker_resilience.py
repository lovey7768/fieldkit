import pytest
import json
from unittest.mock import patch
import httpx
from sqlalchemy import select
from app.database import AsyncSessionLocal, init_db
from app.models import EventRecord, PIIVault, DeadLetterQueue
from app.worker import process_single_event

@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()

@pytest.mark.asyncio
async def test_worker_healthy_flow():
    """Verifies that an event is masked, saved in DB, and marked synced when ERP responds 200."""
    event_id = "evt_worker_success_101"
    raw_payload = json.dumps({
        "id": event_id,
        "type": "equipment_repair",
        "customer_email": "ops@client.com",
        "customer_phone": "+1 415-555-0199",
        "summary": "Pump valve replaced"
    })

    # Mock successful ERP response
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = httpx.Response(200, json={"status": "ok"})
        await process_single_event(event_id, raw_payload)

    async with AsyncSessionLocal() as session:
        # Check event record
        evt = await session.get(EventRecord, event_id)
        assert evt is not None
        assert evt.synced_to_erp is True
        assert "[PII_EMAIL_" in evt.payload_masked["customer_email"]
        assert "[PII_PHONE_" in evt.payload_masked["customer_phone"]

        # Check PII vault
        vault_res = await session.execute(select(PIIVault).where(PIIVault.event_id == event_id))
        vault_rows = vault_res.scalars().all()
        assert len(vault_rows) == 2

@pytest.mark.asyncio
async def test_worker_erp_down_routes_to_dlq():
    """Verifies that when ERP is unreachable, retries execute and payload lands in DeadLetterQueue."""
    event_id = "evt_worker_dlq_999"
    raw_payload = json.dumps({
        "id": event_id,
        "type": "urgent_leak",
        "summary": "Main pipe burst"
    })

    # Mock ERP throwing connection failure on every attempt
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        await process_single_event(event_id, raw_payload)

    async with AsyncSessionLocal() as session:
        # Event is saved but NOT marked synced
        evt = await session.get(EventRecord, event_id)
        assert evt is not None
        assert evt.synced_to_erp is False

        # Must exist in Dead Letter Queue
        dlq_res = await session.execute(select(DeadLetterQueue).where(DeadLetterQueue.event_id == event_id))
        dlq_entry = dlq_res.scalar_one_or_none()
        assert dlq_entry is not None
        assert dlq_entry.destination == "ERP_SYNC"
        assert dlq_entry.attempts == 3
        assert "Connection failed" in dlq_entry.error_reason