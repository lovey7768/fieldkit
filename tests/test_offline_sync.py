import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_root_serves_field_pwa():
    """Verify that root GET / serves the mobile web application."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/")
        assert resp.status_code == 200
        assert "FieldKit — Mobile Operations" in resp.text
        assert "html5-qrcode" in resp.text

@pytest.mark.asyncio
async def test_field_scan_valid_submission():
    """Verify valid field scan ingestion and response."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "client_uuid": "c-uuid-field-101",
            "barcode": "EQUIP-HVAC-9082",
            "photo_payload": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "source": "mobile_field_pwa"
        }
        resp = await ac.post("/api/field/scan", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["client_uuid"] == "c-uuid-field-101"

@pytest.mark.asyncio
async def test_field_scan_idempotency_duplicate_ignored():
    """Verify scanning/submitting the same client_uuid twice is harmless."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "client_uuid": "c-uuid-dedup-test-999",
            "barcode": "EQUIP-VALVE-223",
            "source": "mobile_field_pwa"
        }

        # 1st call -> processed
        res1 = await ac.post("/api/field/scan", json=payload)
        assert res1.status_code == 200
        assert res1.json()["message"] == "Scan record queued for background processing"

        # 2nd duplicate call -> recognized and safely ignored
        res2 = await ac.post("/api/field/scan", json=payload)
        assert res2.status_code == 200
        assert res2.json()["message"] == "Duplicate scan safely ignored"