import pytest
import hmac
import hashlib
import json
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings

SECRET = settings.WEBHOOK_SECRET

@pytest.mark.asyncio
async def test_missing_signature_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/webhooks/events",
            content=b'{"event":"test"}',
            headers={"Content-Type": "application/json"}
        )
        assert resp.status_code == 401
        assert "Invalid or missing HMAC" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_tampered_payload_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        body = b'{"amount": 100}'
        sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

        # Attacker modifies payload to 1000
        tampered_body = b'{"amount": 1000}'
        resp = await client.post(
            "/webhooks/events",
            content=tampered_body,
            headers={"X-Signature-256": sig, "Content-Type": "application/json"}
        )
        assert resp.status_code == 401

@pytest.mark.asyncio
async def test_valid_signature_accepted():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"id": "evt_test_001", "type": "dispatch_request"}
        body = json.dumps(payload).encode()
        sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

        resp = await client.post(
            "/webhooks/events",
            content=body,
            headers={"X-Signature-256": sig, "Content-Type": "application/json"}
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "accepted"
        assert resp.json()["event_id"] == "evt_test_001"

@pytest.mark.asyncio
async def test_duplicate_webhook_ignored():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"id": "evt_test_dedup_99", "type": "status_ping"}
        body = json.dumps(payload).encode()
        sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

        # 1st post -> Accepted
        resp1 = await client.post(
            "/webhooks/events",
            content=body,
            headers={"X-Signature-256": sig, "Content-Type": "application/json"}
        )
        assert resp1.status_code == 202
        assert resp1.json()["status"] == "accepted"

        # 2nd post with same ID -> Ignored
        resp2 = await client.post(
            "/webhooks/events",
            content=body,
            headers={"X-Signature-256": sig, "Content-Type": "application/json"}
        )
        assert resp2.status_code == 202
        assert resp2.json()["status"] == "ignored"