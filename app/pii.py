import re
import hashlib
import base64
from typing import Any, Tuple, List, Dict
from cryptography.fernet import Fernet
from app.config import settings

# Derive valid URL-safe Base64 32-byte Fernet key
_derived_key = base64.urlsafe_b64encode(settings.PII_ENCRYPTION_KEY.encode()[:32])
_cipher = Fernet(_derived_key)

# Robust Multi-Country Regex
EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
)

# Handles:
# - E.164: +14155552671, +919876543210, +442079460919
# - Delimited: +1-415-555-2671, 020 7946 0919, (555) 234-5678
# - International regional variations: +852 9123 4567, +91 98765 43210
PHONE_REGEX = re.compile(
    r'(?:\+?\d{1,4}[-.\s]?)?(?:\(?\d{2,5}\)?[-.\s]?)?\d{3,5}[-.\s]?\d{3,5}\b'
)

def encrypt_pii(raw_value: str) -> str:
    return _cipher.encrypt(raw_value.encode("utf-8")).decode("utf-8")

def decrypt_pii(encrypted_value: str) -> str:
    return _cipher.decrypt(encrypted_value.encode("utf-8")).decode("utf-8")

def mask_text(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """
    Masks emails and phones in a string, replacing them with deterministic tokens
    and generating reversible vault entries.
    """
    vault_entries: List[Dict[str, str]] = []

    def _replace_email(match: re.Match) -> str:
        raw_email = match.group(0)
        token_hash = hashlib.sha256(raw_email.lower().encode()).hexdigest()[:8]
        token = f"[PII_EMAIL_{token_hash}]"
        vault_entries.append({
            "token": token,
            "type": "EMAIL",
            "encrypted": encrypt_pii(raw_email)
        })
        return token

    def _replace_phone(match: re.Match) -> str:
        raw_phone = match.group(0).strip()
        # Heuristic: reject numbers with fewer than 7 digits (avoids matching short IDs or dates)
        digits = re.sub(r'\D', '', raw_phone)
        if len(digits) < 7 or len(digits) > 15:
            return raw_phone
        
        token_hash = hashlib.sha256(digits.encode()).hexdigest()[:8]
        token = f"[PII_PHONE_{token_hash}]"
        vault_entries.append({
            "token": token,
            "type": "PHONE",
            "encrypted": encrypt_pii(raw_phone)
        })
        return token

    # Order matters: replace emails first so localparts don't trigger phone regex
    masked = EMAIL_REGEX.sub(_replace_email, text)
    masked = PHONE_REGEX.sub(_replace_phone, masked)
    return masked, vault_entries

def mask_payload_recursively(data: Any) -> Tuple[Any, List[Dict[str, str]]]:
    """
    Traverses arbitrary JSON structures (dicts, lists, primitives)
    and applies masking to all string values.
    """
    collected_entries: List[Dict[str, str]] = []

    def _traverse(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: _traverse(v) for k, v in node.items()}
        elif isinstance(node, list):
            return [_traverse(elem) for elem in node]
        elif isinstance(node, str):
            masked_str, entries = mask_text(node)
            collected_entries.extend(entries)
            return masked_str
        return node

    sanitized_data = _traverse(data)
    return sanitized_data, collected_entries