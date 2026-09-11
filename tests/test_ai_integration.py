import pytest
import json
from unittest.mock import patch
import httpx
from sqlalchemy import select
from app.database import AsyncSessionLocal, init_db
from app.models import AIReviewQueue
from app.worker import process_single_event
from app.ai import classify_and_draft_reply

@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()

@pytest.mark.asyncio
async def test_ai_classification_on_masked_data_zero_pii_leakage():
    """Verify AI prompt contains strictly masked tokens, never raw email/phone."""
    raw_payload = {
        "id": "evt_ai_test_01",
        "type": "customer_message",
        "notes": "Please schedule emergency repair. Contact John at john@example.com or +1 415-555-0199."
    }

    # Pass through PII masking first
    from app.pii import mask_payload_recursively
    masked, vault = mask_payload_recursively(raw_payload)

    # Verify masked state before passing to AI
    assert "john@example.com" not in str(masked)
    assert "+1 415-555-0199" not in str(masked)
    assert "[PII_EMAIL_" in str(masked)
    assert "[PII_PHONE_" in str(masked)

    # Classify
    res = await classify_and_draft_reply(masked)
    assert res["intent"] in ["booking_request", "complaint", "status_query", "other"]
    assert res["model"] != ""
    assert res["latency_ms"] >= 0.0
    assert isinstance(res["tokens_used"], int)

@pytest.mark.asyncio
async def test_worker_persists_ai_review_queue():
    """Verify worker writes classification and suggested reply as PENDING_HUMAN_REVIEW."""
    event_id = "evt_ai_worker_review_100"
    raw_payload = json.dumps({
        "id": event_id,
        "type": "inbound_complaint",
        "summary": "Water pump is completely broken and leaking everywhere"
    })

    with patch("httpx.AsyncClient.post") as mock_erp:
        mock_erp.return_value = httpx.Response(200, json={"status": "ok"})
        await process_single_event(event_id, raw_payload)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AIReviewQueue).where(AIReviewQueue.event_id == event_id)
        )
        review = result.scalar_one_or_none()
        assert review is not None
        assert review.intent == "complaint"
        assert "apologize" in review.suggested_reply.lower() or "notified" in review.suggested_reply.lower()
        assert review.status == "PENDING_HUMAN_REVIEW"
        assert review.model_name == "mock-local-rule-engine"