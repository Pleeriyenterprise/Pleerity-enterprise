"""
Enterprise OTP flow: send and verify using Twilio Messaging Service.
- OTP stored as SHA-256 hash: sha256(code + ":" + OTP_PEPPER). Never store raw OTP.
- DB stores phone_hash only (unique index phone_hash + purpose). Never store raw phone.
- TTL, cooldown, OTP_MAX_SENDS_PER_HOUR, OTP_MAX_ATTEMPTS; lockout until expires_at.
- Generic responses only. Step-up: issue short-lived token (not JWT) on verify success.
"""
import hashlib
import logging
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from database import database
from services.sms_service import sms_service

logger = logging.getLogger(__name__)

OTP_PEPPER = (os.getenv("OTP_PEPPER") or "").strip()
OTP_TTL_SECONDS = int(os.getenv("OTP_TTL_SECONDS", "300"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "60"))
OTP_MAX_SENDS_PER_HOUR = int(os.getenv("OTP_MAX_SENDS_PER_HOUR", "5"))
STEP_UP_TOKEN_TTL_SECONDS = int(os.getenv("STEP_UP_TOKEN_TTL_SECONDS", "300"))  # 5 min

OTP_LENGTH = 6
SMS_VERIFY_PHONE = "Your Pleerity verification code is {CODE}. It expires in {MINUTES} minutes."
SMS_STEP_UP = "Your Pleerity security code is {CODE}. It expires in {MINUTES} minutes."


def _normalize_phone(phone: str) -> str:
    p = (phone or "").strip()
    if p and not p.startswith("+"):
        p = f"+{p}"
    return p


def _phone_hash(phone_e164: str) -> str:
    """Deterministic hash for DB storage and lookup; never store raw phone."""
    if not OTP_PEPPER:
        raise ValueError("OTP_PEPPER must be set")
    return hashlib.sha256((phone_e164 + ":" + OTP_PEPPER).encode()).hexdigest()


def _phone_hash_for_log(phone_e164: str) -> str:
    """Hash for logging only."""
    try:
        return _phone_hash(phone_e164)[:16]
    except ValueError:
        return "no_pepper"


def _code_hash(raw_otp: str) -> str:
    """Task: sha256(code + ":" + OTP_PEPPER)."""
    if not OTP_PEPPER:
        raise ValueError("OTP_PEPPER must be set")
    return hashlib.sha256((raw_otp + ":" + OTP_PEPPER).encode()).hexdigest()


def _generate_otp() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))


def _parse_dt(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


async def send_otp(
    phone_e164: str,
    purpose: str,
    correlation_id: Optional[str] = None,
) -> bool:
    """
    Create or replace OTP for (phone_hash, purpose). Enforce cooldown and OTP_MAX_SENDS_PER_HOUR.
    Always return True (generic success). Log hashed phone only.
    """
    correlation_id = correlation_id or ""
    phone_e164 = _normalize_phone(phone_e164)
    if len(phone_e164) < 10:
        logger.warning(f"[{correlation_id}] otp_send invalid_phone phone_hash={_phone_hash_for_log(phone_e164)}")
        return True

    if not OTP_PEPPER:
        logger.error(f"[{correlation_id}] otp_send misconfiguration OTP_PEPPER not set")
        return True

    try:
        ph = _phone_hash(phone_e164)
    except ValueError:
        return True

    db = database.get_db()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=OTP_TTL_SECONDS)
    cooldown_until = now - timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS)
    hour_ago = now - timedelta(hours=1)

    existing = await db.otp_codes.find_one(
        {"phone_hash": ph, "purpose": purpose},
        {"_id": 1, "last_sent_at": 1, "send_count": 1, "send_window_start": 1},
    )
    if existing:
        last_sent = _parse_dt(existing.get("last_sent_at"))
        if last_sent and last_sent > cooldown_until:
            logger.info(
                f"[{correlation_id}] otp_send cooldown phone_hash={_phone_hash_for_log(phone_e164)} purpose={purpose}"
            )
            return True
        send_count = existing.get("send_count", 0)
        window_start = _parse_dt(existing.get("send_window_start")) or now
        if window_start > hour_ago and send_count >= OTP_MAX_SENDS_PER_HOUR:
            logger.info(
                f"[{correlation_id}] otp_send max_sends_per_hour phone_hash={_phone_hash_for_log(phone_e164)} purpose={purpose}"
            )
            return True
        if window_start <= hour_ago:
            send_count = 0
            window_start = now
        else:
            send_count = send_count + 1
    else:
        send_count = 1
        window_start = now

    raw_code = _generate_otp()
    code_hash_val = _code_hash(raw_code)
    doc = {
        "phone_hash": ph,
        "purpose": purpose,
        "code_hash": code_hash_val,
        "created_at": now,
        "expires_at": expires_at,
        "send_count": send_count,
        "send_window_start": window_start,
        "attempts": 0,
        "last_sent_at": now,
        "verified_at": None,
    }
    await db.otp_codes.update_one(
        {"phone_hash": ph, "purpose": purpose},
        {"$set": doc},
        upsert=True,
    )

    if not sms_service.is_messaging_service_configured():
        logger.warning(f"[{correlation_id}] otp_send not_configured phone_hash={_phone_hash_for_log(phone_e164)}")
        return True

    minutes = max(1, OTP_TTL_SECONDS // 60)
    if purpose == "step_up":
        body = SMS_STEP_UP.format(CODE=raw_code, MINUTES=minutes)
    else:
        body = SMS_VERIFY_PHONE.format(CODE=raw_code, MINUTES=minutes)
    result = await sms_service.send_sms_via_messaging_service(phone_e164, body)
    if result.get("success"):
        logger.info(f"[{correlation_id}] otp_send success phone_hash={_phone_hash_for_log(phone_e164)} purpose={purpose}")
    else:
        logger.warning(f"[{correlation_id}] otp_send send_failed phone_hash={_phone_hash_for_log(phone_e164)} purpose={purpose}")
    return True


async def verify_otp(
    phone_e164: str,
    code: str,
    purpose: str,
    correlation_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Verify code. Returns (True, step_up_token_or_none) on success, (False, None) on failure.
    Lockout: after max attempts, reject until expires_at (do not delete).
    On success purpose=verify_phone: update notification_preferences (sms_phone_verified).
    On success purpose=step_up and user_id: create step_up_tokens entry and return token.
    """
    correlation_id = correlation_id or ""
    phone_e164 = _normalize_phone(phone_e164)
    code = (code or "").strip()

    if len(phone_e164) < 10 or len(code) != OTP_LENGTH or not code.isdigit():
        return False, None

    if not OTP_PEPPER:
        logger.error(f"[{correlation_id}] otp_verify misconfiguration OTP_PEPPER not set")
        return False, None

    try:
        ph = _phone_hash(phone_e164)
        expected_hash = _code_hash(code)
    except ValueError:
        return False, None

    db = database.get_db()
    now = datetime.now(timezone.utc)
    doc = await db.otp_codes.find_one(
        {"phone_hash": ph, "purpose": purpose},
        {"_id": 1, "code_hash": 1, "attempts": 1, "expires_at": 1},
    )
    if not doc:
        logger.info(f"[{correlation_id}] otp_verify no_record phone_hash={_phone_hash_for_log(phone_e164)}")
        return False, None

    expires_at = _parse_dt(doc.get("expires_at"))
    if expires_at and expires_at < now:
        logger.info(f"[{correlation_id}] otp_verify expired phone_hash={_phone_hash_for_log(phone_e164)} attempts={doc.get('attempts', 0)}")
        await db.otp_codes.delete_one({"phone_hash": ph, "purpose": purpose})
        return False, None

    attempts = doc.get("attempts", 0)
    if attempts >= OTP_MAX_ATTEMPTS:
        logger.warning(f"[{correlation_id}] otp_verify lockout phone_hash={_phone_hash_for_log(phone_e164)} attempts={attempts}")
        return False, None

    if doc.get("code_hash") != expected_hash:
        await db.otp_codes.update_one(
            {"phone_hash": ph, "purpose": purpose},
            {"$inc": {"attempts": 1}},
        )
        logger.info(f"[{correlation_id}] otp_verify failed phone_hash={_phone_hash_for_log(phone_e164)} attempt_count={attempts + 1}")
        return False, None

    await db.otp_codes.delete_one({"phone_hash": ph, "purpose": purpose})

    if purpose == "verify_phone":
        await db.notification_preferences.update_many(
            {"sms_phone_number": phone_e164},
            {"$set": {"sms_phone_number": phone_e164, "sms_phone_verified": True, "sms_verified_at": now}},
        )
        logger.info(f"[{correlation_id}] otp_verify success purpose=verify_phone phone_hash={_phone_hash_for_log(phone_e164)}")
        return True, None

    if purpose == "step_up" and user_id:
        token_plain = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token_plain.encode()).hexdigest()
        token_expires = now + timedelta(seconds=STEP_UP_TOKEN_TTL_SECONDS)
        await db.step_up_tokens.insert_one({
            "user_id": user_id,
            "token_hash": token_hash,
            "created_at": now,
            "expires_at": token_expires,
            "purpose_scope": "step_up",
        })
        logger.info(f"[{correlation_id}] otp_verify success purpose=step_up phone_hash={_phone_hash_for_log(phone_e164)} user_id={user_id[:8]}...")
        return True, token_plain

    logger.info(f"[{correlation_id}] otp_verify success purpose={purpose} phone_hash={_phone_hash_for_log(phone_e164)}")
    return True, None


async def consume_step_up_token(token: str, user_id: str) -> bool:
    """
    Validate X-Step-Up-Token: match user_id, not expired, one-time use (delete on success).
    Returns True if valid and consumed, False otherwise.
    """
    if not token or not user_id:
        return False
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    db = database.get_db()
    now = datetime.now(timezone.utc)
    doc = await db.step_up_tokens.find_one({"token_hash": token_hash, "user_id": user_id})
    if not doc:
        return False
    expires_at = _parse_dt(doc.get("expires_at"))
    if not expires_at or expires_at < now:
        await db.step_up_tokens.delete_one({"token_hash": token_hash})
        return False
    await db.step_up_tokens.delete_one({"token_hash": token_hash})
    return True
