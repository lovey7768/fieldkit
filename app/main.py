from fastapi import FastAPI, Request, Header, HTTPException, status
from contextlib import asynccontextmanager
import redis.asyncio as aioredis
import json
import hashlib
from app.config import settings
from app.security import verify_hmac_signature
from app.database import init_db
import app.models  # noqa: F401 — registers models on Base.metadata before init_db()

# Redis connection pool
redis_client: aioredis.Redis | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    # Initialize Postgres tables
    await init_db()
    # Initialize Redis connection
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
    yield
    if redis_client:
        await redis_client.close()

app = FastAPI(title="FieldKit Core API", version="1.0.0", lifespan=lifespan)

@app.get("/healthz")
async def health_check():
    return {"status": "healthy", "service": "fieldkit"}

@app.post("/webhooks/events", status_code=status.HTTP_202_ACCEPTED)
async def webhook_intake(
    request: Request,
    x_signature_256: str | None = Header(default=None, alias="X-Signature-256")
):
    raw_body = await request.body()

    # 1. Cryptographic HMAC validation over raw bytes
    if not verify_hmac_signature(raw_body, x_signature_256, settings.WEBHOOK_SECRET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing HMAC-SHA256 signature."
        )

    # 2. JSON Deserialization validation
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON payload."
        )

    # 3. Deterministic Event Identification
    event_id = payload.get("id") or payload.get("event_id")
    if not event_id:
        # Fallback: Canonical hash of raw payload bytes
        event_id = hashlib.sha256(raw_body).hexdigest()
        payload["id"] = event_id

    # 4. Atomic Deduplication via Redis SETNX (24-hour sliding window)
    dedup_key = f"dedup:{event_id}"
    is_new = await redis_client.set(dedup_key, "1", ex=86400, nx=True)
    if not is_new:
        return {
            "status": "ignored",
            "reason": "duplicate_event",
            "event_id": event_id
        }

    # 5. Append to Redis Stream for fault-tolerant worker consumption
    await redis_client.xadd(
        "events:stream",
        {"event_id": event_id, "data": json.dumps(payload)}
    )

    return {
        "status": "accepted",
        "event_id": event_id
    }