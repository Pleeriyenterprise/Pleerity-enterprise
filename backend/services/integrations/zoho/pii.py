"""PII minimisation for Zoho exports."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Keys never sent to Zoho Analytics aggregates
PII_KEYS: Set[str] = {
    "email",
    "phone",
    "first_name",
    "last_name",
    "full_name",
    "name",
    "address",
    "postcode",
    "ip_address",
    "message_summary",
    "admin_notes",
    "password",
    "token",
}


def strip_pii_from_dict(data: Dict[str, Any], allowed_keys: List[str] | None = None) -> Dict[str, Any]:
    """Return copy with PII keys removed unless explicitly allowed."""
    allowed = set(allowed_keys or [])
    out: Dict[str, Any] = {}
    for key, val in data.items():
        if key in PII_KEYS and key not in allowed:
            continue
        if isinstance(val, dict):
            out[key] = strip_pii_from_dict(val, allowed_keys)
        else:
            out[key] = val
    return out


def is_aggregate_export_safe(payload: Dict[str, Any]) -> bool:
    """Analytics exports must not contain row-level email/phone."""
    for key in payload:
        if key.lower() in PII_KEYS:
            return False
        if EMAIL_RE.match(str(payload.get(key) or "")):
            return False
    return True


def hash_email_for_campaigns(email: str) -> str:
    """Optional pseudonymisation — campaigns may need email; document in DPIA."""
    import hashlib

    normalised = (email or "").strip().lower()
    return hashlib.sha256(normalised.encode()).hexdigest()[:16]
