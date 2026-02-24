"""
Submission validation, sanitization, dedupe and rate limiting for inbound submissions.
Used by public lead, contact, partnership, talent endpoints.
"""
import re
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Max lengths (task: message <= 2000)
MAX_MESSAGE_LENGTH = 2000
MAX_NAME_LENGTH = 200
MAX_EMAIL_LENGTH = 254
MAX_PHONE_LENGTH = 50
MAX_SUBJECT_LENGTH = 500
MAX_FIELD_LENGTH = 2000

# Dangerous patterns (stored XSS / script injection)
SCRIPT_PATTERN = re.compile(r"<script\b[^>]*>|</script>|javascript:", re.I)
TAG_PATTERN = re.compile(r"<[^>]+>")


def sanitize_html(text: Optional[str], max_len: int = MAX_MESSAGE_LENGTH) -> str:
    """
    Strip HTML tags and reject script-like content. Returns safe string for storage.
    If text is None or not str, returns empty string.
    """
    if text is None or not isinstance(text, str):
        return ""
    s = text.strip()
    if SCRIPT_PATTERN.search(s):
        logger.warning("Submission contained script-like content, stripped")
        s = SCRIPT_PATTERN.sub("", s)
    s = TAG_PATTERN.sub("", s)
    s = s.replace("&lt;", "<").replace("&gt;", ">")  # decode entities then strip again
    s = TAG_PATTERN.sub("", s)
    if len(s) > max_len:
        s = s[:max_len]
    return s


def normalize_email(email: Optional[str]) -> str:
    """Lowercase and strip for dedupe."""
    if not email or not isinstance(email, str):
        return ""
    return email.lower().strip()


def normalize_phone(phone: Optional[str]) -> str:
    """Digits only for dedupe."""
    if not phone or not isinstance(phone, str):
        return ""
    return "".join(c for c in phone if c.isdigit()) or ""


def compute_dedupe_key(
    submission_type: str,
    email: str,
    phone: Optional[str],
    message_snippet: Optional[str],
    day_bucket: Optional[datetime] = None,
) -> str:
    """
    dedupe_key = sha256(type + normalized_email + normalized_phone + message_80 + day_bucket).
    day_bucket is date only (YYYY-MM-DD) so same payload same day collides.
    """
    now = day_bucket or datetime.now(timezone.utc)
    day_str = now.strftime("%Y-%m-%d")
    msg = (message_snippet or "")[:80]
    raw = f"{submission_type}|{normalize_email(email)}|{normalize_phone(phone)}|{msg}|{day_str}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# Rate limiting (in-memory, per endpoint key)
_rate_limit_cache: dict = {}
RATE_LIMIT_WINDOW_SEC = 60
RATE_LIMIT_MAX_PER_WINDOW = 5


def check_rate_limit(ip: str, key: str = "default") -> bool:
    """
    Returns True if request is allowed. Uses key to separate e.g. contact vs talent.
    """
    now = datetime.now(timezone.utc).timestamp()
    cache_key = f"{key}:{ip}"
    if cache_key not in _rate_limit_cache:
        _rate_limit_cache[cache_key] = []
    _rate_limit_cache[cache_key] = [
        ts for ts in _rate_limit_cache[cache_key]
        if now - ts < RATE_LIMIT_WINDOW_SEC
    ]
    if len(_rate_limit_cache[cache_key]) >= RATE_LIMIT_MAX_PER_WINDOW:
        return False
    _rate_limit_cache[cache_key].append(now)
    return True


def is_honeypot_filled(honeypot_value: Optional[str]) -> bool:
    """If honeypot field is present and non-empty, treat as bot."""
    if honeypot_value is None:
        return False
    if isinstance(honeypot_value, str) and honeypot_value.strip():
        return True
    return False
