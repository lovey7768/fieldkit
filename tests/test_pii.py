import pytest
from app.pii import mask_text, mask_payload_recursively, decrypt_pii

def test_mask_email_simple():
    raw = "Contact support at dispatch-team@fieldkit.co.uk for urgent dispatch."
    masked, entries = mask_text(raw)
    assert "dispatch-team@fieldkit.co.uk" not in masked
    assert "[PII_EMAIL_" in masked
    assert len(entries) == 1
    assert entries[0]["type"] == "EMAIL"
    assert decrypt_pii(entries[0]["encrypted"]) == "dispatch-team@fieldkit.co.uk"

def test_multi_country_phone_formats():
    test_cases = [
        ("+1 415-555-2671", "North America NANP"),
        ("+91 98765 43210", "India E.164 with spaces"),
        ("020 7946 0919", "UK National"),
        ("+852 9123 4567", "Hong Kong"),
        ("+49 30 123456", "Germany")
    ]
    for phone, label in test_cases:
        masked, entries = mask_text(f"Call crew on {phone} now.")
        assert phone not in masked, f"Failed to mask {label}: {phone}"
        assert "[PII_PHONE_" in masked
        assert len(entries) == 1
        assert decrypt_pii(entries[0]["encrypted"]) == phone

def test_recursive_payload_masking():
    payload = {
        "event_id": "evt_nested_001",
        "customer": {
            "name": "Jane Doe",
            "email": "jane.doe@enterprise.ca",
            "contact": {
                "mobile": "+1-514-555-0199",
                "notes": "Emergency backup: +91-9123456789"
            }
        },
        "tags": ["urgent", "crew_dispatch"]
    }

    masked, vault = mask_payload_recursively(payload)

    # Validate structural preservation
    assert masked["event_id"] == "evt_nested_001"
    assert masked["tags"] == ["urgent", "crew_dispatch"]
    assert masked["customer"]["name"] == "Jane Doe"

    # Validate sensitive field replacement
    assert "[PII_EMAIL_" in masked["customer"]["email"]
    assert "[PII_PHONE_" in masked["customer"]["contact"]["mobile"]
    assert "[PII_PHONE_" in masked["customer"]["contact"]["notes"]

    # 3 sensitive elements extracted
    assert len(vault) == 3