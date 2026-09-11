from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Header, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import redis.asyncio as aioredis
import json
import hashlib
import os

from app.config import settings
from app.security import verify_hmac_signature
from app.database import init_db, AsyncSessionLocal
from sqlalchemy import select
import app.models  # noqa: F401 — registers ORM models on Base.metadata before init_db()
from app.models import AIReviewQueue

redis_client: aioredis.Redis | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    await init_db()
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
    yield
    if redis_client:
        await redis_client.close()

app = FastAPI(title="FieldKit Core API", version="1.0.0", lifespan=lifespan)

# Mount static asset directory
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def serve_pwa():
    """Serves the mobile-friendly field operations web page."""
    index_path = os.path.join("app", "static", "index.html")
    return FileResponse(index_path)

@app.get("/healthz")
async def health_check():
    return {"status": "healthy", "service": "fieldkit"}

@app.post("/webhooks/events", status_code=status.HTTP_202_ACCEPTED)
async def webhook_intake(
    request: Request,
    x_signature_256: str | None = Header(default=None, alias="X-Signature-256")
):
    raw_body = await request.body()

    if not verify_hmac_signature(raw_body, x_signature_256, settings.WEBHOOK_SECRET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing HMAC-SHA256 signature."
        )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON payload."
        )

    event_id = payload.get("id") or payload.get("event_id")
    if not event_id:
        event_id = hashlib.sha256(raw_body).hexdigest()
        payload["id"] = event_id

    dedup_key = f"dedup:{event_id}"
    is_new = await redis_client.set(dedup_key, "1", ex=86400, nx=True)
    if not is_new:
        return {"status": "ignored", "reason": "duplicate_event", "event_id": event_id}

    await redis_client.xadd("events:stream", {"event_id": event_id, "data": json.dumps(payload)})
    return {"status": "accepted", "event_id": event_id}

@app.post("/api/field/scan", status_code=status.HTTP_200_OK)
async def field_scan_intake(request: Request):
    """
    Receives scan submissions from mobile field devices.
    Enforces idempotency using the client-generated UUID.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed JSON payload.")

    client_uuid = payload.get("client_uuid")
    if not client_uuid:
        raise HTTPException(status_code=400, detail="Missing required 'client_uuid'.")

    # Idempotent deduplication in Redis (24-hour window)
    dedup_key = f"field_dedup:{client_uuid}"
    is_new = await redis_client.set(dedup_key, "1", ex=86400, nx=True)

    if not is_new:
        return {
            "status": "success",
            "message": "Duplicate scan safely ignored",
            "client_uuid": client_uuid
        }

    # Forward to event stream for background masking and worker processing
    await redis_client.xadd(
        "events:stream",
        {"event_id": client_uuid, "data": json.dumps(payload)}
    )

    return {
        "status": "success",
        "message": "Scan record queued for background processing",
        "client_uuid": client_uuid
    }

@app.get("/api/reviews/pending", status_code=status.HTTP_200_OK)
async def list_pending_ai_reviews():
    """Returns AI-drafted responses awaiting human dispatcher review."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AIReviewQueue)
            .where(AIReviewQueue.status == "PENDING_HUMAN_REVIEW")
            .order_by(AIReviewQueue.created_at.desc())
        )
        reviews = result.scalars().all()
        return [
            {
                "id": r.id,
                "event_id": r.event_id,
                "intent": r.intent,
                "suggested_reply": r.suggested_reply,
                "model_name": r.model_name,
                "latency_ms": r.latency_ms,
                "tokens_used": r.tokens_used,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in reviews
        ]