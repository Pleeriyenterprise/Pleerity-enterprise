"""
Submission validation, sanitization, dedupe and rate limiting for inbound submissions.
Used by public lead, contact, partnership, talent endpoints.
Enterprise limits: name<=120, org<=160, phone<=30, subject<=180, message<=2000, email<=254.
"""
import os
import re
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


async def notify_admin_new_submission(
    submission_type: str,
    submission_id: str,
    summary: str,
    detail_url_path: Optional[str] = None,
) -> None:
    """
    If ADMIN_NOTIFY_EMAIL is set, send one internal 'new submission' email.
    Logs errors and does not raise; does not block submission success.
    """
    admin_email = (os.environ.get("ADMIN_NOTIFY_EMAIL") or "").strip()
    if not admin_email:
        return
    try:
        from services.notification_orchestrator import notification_orchestrator
        base_url = (os.environ.get("FRONTEND_URL") or os.environ.get("ADMIN_DASHBOARD_URL") or "http://localhost:3000").rstrip("/")
        link = f"{base_url}/admin/submissions/{submission_type}/{submission_id}" if detail_url_path is None else f"{base_url}{detail_url_path}"
        subject = f"New {submission_type.title()} submission: {submission_id}"
        message = f"<p>{summary}</p><p><a href=\"{link}\">View in admin →</a></p>"
        idempotency_key = f"admin_notify_{submission_type}_{submission_id}_{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H')}"
        result = await notification_orchestrator.send(
            template_key="SUPPORT_INTERNAL_NOTIFICATION",
            client_id=None,
            context={"recipient": admin_email, "subject": subject, "message": message},
            idempotency_key=idempotency_key,
            event_type="submission_admin_notify",
        )
        if result.outcome not in ("sent", "duplicate_ignored"):
            logger.warning("Admin notify for %s %s: outcome=%s", submission_type, submission_id, getattr(result, "outcome", None))
    except Exception as e:
        logger.exception("Admin notify email failed for %s %s: %s", submission_type, submission_id, e)

# Enterprise hard limits (enhancement audit)
MAX_NAME_LENGTH = 120
MAX_ORG_LENGTH = 160
MAX_EMAIL_LENGTH = 254
MAX_PHONE_LENGTH = 30
MAX_SUBJECT_LENGTH = 180
MAX_MESSAGE_LENGTH = 2000
MAX_FIELD_LENGTH = 2000
# Legacy / backward compat (longer fields use these where needed)
MAX_MESSAGE_LEGACY = 2000
MAX_NAME_LEGACY = 200
MAX_SUBJECT_LEGACY = 500
MAX_PHONE_LEGACY = 50

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


def _is_field_filled(value: Optional[str]) -> bool:
    if value is None:
        return False
    return isinstance(value, str) and bool(value.strip())


def is_honeypot_filled(honeypot_value: Optional[str]) -> bool:
    """If honeypot field is present and non-empty, treat as bot."""
    return _is_field_filled(honeypot_value)


def is_website_honeypot_filled(website: Optional[str], honeypot: Optional[str]) -> bool:
    """Task: honeypot field name 'website'. Accept both website and legacy honeypot."""
    return _is_field_filled(website) or _is_field_filled(honeypot)


# Spam scoring: +50 honeypot, +20 urls>3, +20 script; threshold 50 => status spam
SPAM_SCORE_HONEYPOT = 50
SPAM_SCORE_URLS = 20
SPAM_SCORE_SCRIPT = 20
SPAM_THRESHOLD = 50
URL_PATTERN = re.compile(r"https?://[^\s]+", re.I)


def compute_spam_score(message: Optional[str], honeypot_filled: bool) -> Tuple[int, bool]:
    """
    Returns (spam_score, has_script). +50 if honeypot, +20 if >3 URLs in message, +20 if script-like.
    """
    score = 0
    has_script = False
    if honeypot_filled:
        score += SPAM_SCORE_HONEYPOT
    if message and isinstance(message, str):
        urls = URL_PATTERN.findall(message)
        if len(urls) > 3:
            score += SPAM_SCORE_URLS
        if SCRIPT_PATTERN.search(message):
            score += SPAM_SCORE_SCRIPT
            has_script = True
    return (score, has_script)
