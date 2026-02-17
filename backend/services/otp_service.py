"""
Enterprise OTP flow: send and verify using Twilio Messaging Service.
- OTP stored as SHA256 hash with OTP_PEPPER; never store raw OTP.
- One active OTP per (phone_e164 + purpose). TTL and attempt limits enforced.
- Generic responses only; do not reveal whether a phone exists.
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

OTP_LENGTH = 6
GENERIC_SEND_SUCCESS = "If this number is registered, you will receive a verification code shortly."
GENERIC_VERIFY_FAIL = "Invalid or expired code. Please try again or request a new code."
GENERIC_VERIFY_SUCCESS = "Verification successful."


def _normalize_phone(phone: str) -> str:
    p = (phone or "").strip()
    if p and not p.startswith("+"):
        p = f"+{p}"
    return p


def _phone_hash_for_log(phone_e164: str) -> str:
    """Hash for logging only; never log raw phone."""
    if not OTP_PEPPER:
        return "no_pepper"
    h = hashlib.sha256((OTP_PEPPER + phone_e164).encode()).hexdigest()
    return h[:16]


def _otp_hash(raw_otp: str) -> str:
    """Store only hash of OTP (with pepper)."""
    if not OTP_PEPPER:
        raise ValueError("OTP_PEPPER must be set")
    return hashlib.sha256((OTP_PEPPER + raw_otp).encode()).hexdigest()


def _generate_otp() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))


async def send_otp(
    phone_number: str,
    purpose: str,
    correlation_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Create or replace OTP for (phone, purpose), enforce resend cooldown, send SMS via Messaging Service.
    Always returns (True, generic_message) for API response; logs real outcome.
    """
    correlation_id = correlation_id or ""
    phone_e164 = _normalize_phone(phone_number)
    if len(phone_e164) < 10:
        logger.warning(f"[{correlation_id}] otp_send invalid_phone phone_hash={_phone_hash_for_log(phone_e164)}")
        return True, GENERIC_SEND_SUCCESS

    if not OTP_PEPPER:
        logger.error(f"[{correlation_id}] otp_send misconfiguration OTP_PEPPER not set")
        return True, GENERIC_SEND_SUCCESS

    db = database.get_db()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=OTP_TTL_SECONDS)
    cooldown_until = now - timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS)

    existing = await db.otp_codes.find_one(
        {"phone_e164": phone_e164, "purpose": purpose},
        {"_id": 1, "last_sent_at": 1},
    )
    if existing and existing.get("last_sent_at"):
        last = existing["last_sent_at"]
        if isinstance(last, str):
            try:
                last = datetime.fromisoformat(last.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                last = now
        if hasattr(last, "tzinfo") and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last > cooldown_until:
            logger.info(
                f"[{correlation_id}] otp_send cooldown phone_hash={_phone_hash_for_log(phone_e164)} "
                f"purpose={purpose} success=skipped"
            )
            return True, GENERIC_SEND_SUCCESS

    raw_code = _generate_otp()
    otp_hash_val = _otp_hash(raw_code)
    doc = {
        "phone_e164": phone_e164,
        "purpose": purpose,
        "otp_hash": otp_hash_val,
        "attempts": 0,
        "created_at": now,
        "expires_at": expires_at,
        "last_sent_at": now,
    }
    await db.otp_codes.update_one(
        {"phone_e164": phone_e164, "purpose": purpose},
        {"$set": doc},
        upsert=True,
    )

    if not sms_service.is_messaging_service_configured():
        logger.warning(f"[{correlation_id}] otp_send not_configured phone_hash={_phone_hash_for_log(phone_e164)}")
        return True, GENERIC_SEND_SUCCESS

    body = f"Your verification code is {raw_code}. It expires in {OTP_TTL_SECONDS // 60} minutes."
    result = await sms_service.send_sms_via_messaging_service(phone_e164, body)
    if result.get("success"):
        logger.info(
            f"[{correlation_id}] otp_send success phone_hash={_phone_hash_for_log(phone_e164)} "
            f"purpose={purpose}"
        )
    else:
        logger.warning(
            f"[{correlation_id}] otp_send send_failed phone_hash={_phone_hash_for_log(phone_e164)} "
            f"purpose={purpose}"
        )
    return True, GENERIC_SEND_SUCCESS


async def verify_otp(
    phone_number: str,
    code: str,
    purpose: str,
    correlation_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Verify code against stored hash. On success: if purpose==verify_phone, set phone_verified.
    Returns (success, generic_message). Never reveal phone existence or attempt count to caller.
    """
    correlation_id = correlation_id or ""
    phone_e164 = _normalize_phone(phone_number)
    code = (code or "").strip()

    if len(phone_e164) < 10 or len(code) != OTP_LENGTH or not code.isdigit():
        return False, GENERIC_VERIFY_FAIL

    if not OTP_PEPPER:
        logger.error(f"[{correlation_id}] otp_verify misconfiguration OTP_PEPPER not set")
        return False, GENERIC_VERIFY_FAIL

    db = database.get_db()
    now = datetime.now(timezone.utc)
    doc = await db.otp_codes.find_one(
        {"phone_e164": phone_e164, "purpose": purpose},
        {"_id": 1, "otp_hash": 1, "attempts": 1, "expires_at": 1},
    )
    if not doc:
        logger.info(f"[{correlation_id}] otp_verify no_record phone_hash={_phone_hash_for_log(phone_e164)}")
        return False, GENERIC_VERIFY_FAIL

    expires_at = doc.get("expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                expires_at = now
        if hasattr(expires_at, "tzinfo") and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now:
            logger.info(
                f"[{correlation_id}] otp_verify expired phone_hash={_phone_hash_for_log(phone_e164)} "
                f"attempts={doc.get('attempts', 0)}"
            )
            await db.otp_codes.delete_one({"phone_e164": phone_e164, "purpose": purpose})
            return False, GENERIC_VERIFY_FAIL

    attempts = doc.get("attempts", 0)
    if attempts >= OTP_MAX_ATTEMPTS:
        logger.warning(
            f"[{correlation_id}] otp_verify max_attempts phone_hash={_phone_hash_for_log(phone_e164)} "
            f"attempts={attempts}"
        )
        await db.otp_codes.delete_one({"phone_e164": phone_e164, "purpose": purpose})
        return False, GENERIC_VERIFY_FAIL

    try:
        expected_hash = _otp_hash(code)
    except ValueError:
        return False, GENERIC_VERIFY_FAIL

    if doc.get("otp_hash") != expected_hash:
        await db.otp_codes.update_one(
            {"phone_e164": phone_e164, "purpose": purpose},
            {"$inc": {"attempts": 1}},
        )
        new_attempts = attempts + 1
        logger.info(
            f"[{correlation_id}] otp_verify failed phone_hash={_phone_hash_for_log(phone_e164)} "
            f"attempt_count={new_attempts}"
        )
        return False, GENERIC_VERIFY_FAIL

    await db.otp_codes.delete_one({"phone_e164": phone_e164, "purpose": purpose})

    if purpose == "verify_phone":
        r = await db.notification_preferences.update_many(
            {"sms_phone_number": phone_e164},
            {"$set": {"sms_phone_verified": True, "sms_verified_at": now}},
        )
        logger.info(
            f"[{correlation_id}] otp_verify success purpose=verify_phone phone_hash={_phone_hash_for_log(phone_e164)} "
            f"matched_prefs={r.modified_count}"
        )
    else:
        logger.info(
            f"[{correlation_id}] otp_verify success purpose={purpose} phone_hash={_phone_hash_for_log(phone_e164)}"
        )

    return True, GENERIC_VERIFY_SUCCESS
