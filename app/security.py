import hmac
import hashlib

def verify_hmac_signature(raw_body: bytes, signature_header: str | None, secret: str) -> bool:
    """
    Verifies HMAC-SHA256 signature using constant-time comparison.
    Supports raw hex or 'sha256=<hex>' formats.
    """
    if not signature_header or not secret:
        return False

    signature = signature_header.strip()
    if signature.startswith("sha256="):
        signature = signature[7:]

    computed = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    # compare_digest prevents timing attacks
    return hmac.compare_digest(computed.lower(), signature.lower())