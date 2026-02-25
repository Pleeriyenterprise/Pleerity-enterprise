"""
Signed lead token for Activate Monitoring links.
Encodes lead_id + expiry (e.g. 7 days). Verify without DB lookup.
"""
import os
import hmac
import hashlib
import base64
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Default expiry for activation link (days)
DEFAULT_EXPIRY_DAYS = 7


def _secret() -> str:
    s = (os.environ.get("RISK_LEAD_TOKEN_SECRET") or os.environ.get("SECRET_KEY") or "").strip()
    if not s:
        logger.warning("RISK_LEAD_TOKEN_SECRET (or SECRET_KEY) not set; lead tokens are insecure in production.")
    return s or "dev-lead-token-secret-change-in-production"


def create_lead_token(lead_id: str, expiry_days: int = DEFAULT_EXPIRY_DAYS) -> str:
    """
    Produce a signed token containing lead_id and exp (ISO timestamp).
    Format: base64(payload_json).base64(signature).
    """
    if not (lead_id or "").strip():
        raise ValueError("lead_id required")
    exp = (datetime.now(timezone.utc) + timedelta(days=expiry_days)).isoformat()
    payload = {"lead_id": (lead_id or "").strip(), "exp": exp}
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode()).decode().rstrip("=")
    sig = hmac.new(
        _secret().encode(),
        payload_b64.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_lead_token(token: str) -> Optional[str]:
    """
    Verify signature and expiry; return lead_id if valid, else None.
    Caller should return 401/400 when None.
    """
    if not (token or "").strip():
        return None
    token = (token or "").strip()
    parts = token.split(".")
    if len(parts) != 2:
        return None
    payload_b64, sig = parts[0], parts[1]
    # Restore padding if needed
    payload_b64_pad = payload_b64 + "=" * (4 - len(payload_b64) % 4) if len(payload_b64) % 4 else payload_b64
    try:
        payload_json = base64.urlsafe_b64decode(payload_b64_pad.encode()).decode()
    except Exception:
        return None
    expected_sig = hmac.new(
        _secret().encode(),
        payload_b64.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_sig, sig):
        return None
    try:
        data = json.loads(payload_json)
    except Exception:
        return None
    lead_id = data.get("lead_id")
    exp_str = data.get("exp")
    if not lead_id or not exp_str:
        return None
    try:
        exp_dt = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
    except Exception:
        return None
    if exp_dt.tzinfo is None:
        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) >= exp_dt:
        return None  # Expired
    return (lead_id or "").strip()
