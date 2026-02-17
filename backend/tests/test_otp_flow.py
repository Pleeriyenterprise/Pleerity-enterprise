"""
Unit tests for enterprise OTP flow (send + verify).
- OTP stored as code_hash only (sha256(code + ":" + OTP_PEPPER)); DB uses phone_hash (no raw phone).
- Generic responses; cooldown; max attempts lockout; step_up token issuance.
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


@pytest.mark.asyncio
async def test_otp_send_returns_sent_and_stores_phone_hash_code_hash_only():
    """Send returns True (status sent); DB stores phone_hash and code_hash, never raw OTP or phone."""
    from services.otp_service import send_otp, _phone_hash, _code_hash

    db = MagicMock()
    db.otp_codes.find_one = AsyncMock(return_value=None)
    db.otp_codes.update_one = AsyncMock(return_value=MagicMock(modified_count=0, upserted_id=1))

    with patch.dict("os.environ", {"OTP_PEPPER": "test-pepper"}, clear=False):
        with patch("services.otp_service.OTP_PEPPER", "test-pepper"):
            with patch("services.otp_service.database.get_db", return_value=db):
                with patch("services.otp_service.sms_service.is_messaging_service_configured", return_value=True):
                    with patch("services.otp_service.sms_service.send_sms_via_messaging_service", new_callable=AsyncMock) as send_sms:
                        send_sms.return_value = {"success": True}
                        result = await send_otp(phone_e164="+447700900123", purpose="verify_phone", correlation_id="cid-1")
    assert result is True
    db.otp_codes.update_one.assert_called_once()
    call_kw = db.otp_codes.update_one.call_args[0][2]["$set"]
    assert "phone_hash" in call_kw
    assert "code_hash" in call_kw
    assert call_kw["purpose"] == "verify_phone"
    assert "phone_e164" not in call_kw
    assert len(call_kw["phone_hash"]) == 64
    assert len(call_kw["code_hash"]) == 64
    assert call_kw["send_count"] == 1


@pytest.mark.asyncio
async def test_otp_send_without_pepper_returns_true_no_send():
    """When OTP_PEPPER is not set, send still returns True and does not write to DB."""
    from services.otp_service import send_otp

    db = MagicMock()
    db.otp_codes.find_one = AsyncMock(return_value=None)

    with patch.dict("os.environ", {"OTP_PEPPER": ""}, clear=False):
        with patch("services.otp_service.OTP_PEPPER", ""):
            with patch("services.otp_service.database.get_db", return_value=db):
                result = await send_otp(phone_e164="+447700900123", purpose="step_up", correlation_id="cid-2")
    assert result is True
    db.otp_codes.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_otp_send_cooldown_returns_true_without_sending():
    """When last_sent_at is within cooldown window, send returns True and does not update/send."""
    from services.otp_service import send_otp, _phone_hash

    now = datetime.now(timezone.utc)
    recent = now - __import__("datetime").timedelta(seconds=30)
    db = MagicMock()
    db.otp_codes.find_one = AsyncMock(return_value={"last_sent_at": recent, "send_count": 1, "send_window_start": recent})

    with patch.dict("os.environ", {"OTP_PEPPER": "p", "OTP_RESEND_COOLDOWN_SECONDS": "60"}, clear=False):
        with patch("services.otp_service.OTP_PEPPER", "p"):
            with patch("services.otp_service.database.get_db", return_value=db):
                result = await send_otp(phone_e164="+447700900456", purpose="verify_phone", correlation_id="c")
    assert result is True
    db.otp_codes.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_otp_verify_valid_code_returns_success():
    """Verify with correct code (matching code_hash) returns (True, None) for step_up without user_id."""
    from services.otp_service import verify_otp, _phone_hash, _code_hash

    raw_code = "123456"
    pepper = "my-pepper"
    phone_e164 = "+447700900456"
    purpose = "step_up"
    ph = _phone_hash(phone_e164)
    doc = {
        "phone_hash": ph,
        "code_hash": _code_hash(raw_code),
        "attempts": 0,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    db = MagicMock()
    db.otp_codes.find_one = AsyncMock(return_value=doc)
    db.otp_codes.delete_one = AsyncMock()

    with patch.dict("os.environ", {"OTP_PEPPER": pepper}, clear=False):
        with patch("services.otp_service.OTP_PEPPER", pepper):
            with patch("services.otp_service.database.get_db", return_value=db):
                ok, step_token = await verify_otp(phone_e164=phone_e164, code=raw_code, purpose=purpose, correlation_id="v1")
    assert ok is True
    assert step_token is None
    db.otp_codes.delete_one.assert_called_once()


@pytest.mark.asyncio
async def test_otp_verify_wrong_code_returns_fail_and_increments_attempts():
    """Verify with wrong code returns (False, None) and increments attempts."""
    from services.otp_service import verify_otp, _phone_hash, _code_hash

    pepper = "pep"
    phone_e164 = "+447700900789"
    purpose = "verify_phone"
    ph = _phone_hash(phone_e164)
    doc = {
        "code_hash": _code_hash("000000"),
        "attempts": 1,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    db = MagicMock()
    db.otp_codes.find_one = AsyncMock(return_value=doc)
    db.otp_codes.update_one = AsyncMock()

    with patch.dict("os.environ", {"OTP_PEPPER": pepper}, clear=False):
        with patch("services.otp_service.OTP_PEPPER", pepper):
            with patch("services.otp_service.database.get_db", return_value=db):
                ok, _ = await verify_otp(phone_e164=phone_e164, code="123456", purpose=purpose, correlation_id="v2")
    assert ok is False
    db.otp_codes.update_one.assert_called_once()
    assert db.otp_codes.update_one.call_args[0][2]["$inc"]["attempts"] == 1


@pytest.mark.asyncio
async def test_otp_verify_max_attempts_lockout_returns_fail():
    """When attempts >= OTP_MAX_ATTEMPTS, verify returns (False, None) and does not delete (lockout)."""
    from services.otp_service import verify_otp, _phone_hash, _code_hash

    pepper = "p"
    phone_e164 = "+447700900999"
    doc = {
        "code_hash": _code_hash("123456"),
        "attempts": 5,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    db = MagicMock()
    db.otp_codes.find_one = AsyncMock(return_value=doc)

    with patch.dict("os.environ", {"OTP_PEPPER": pepper, "OTP_MAX_ATTEMPTS": "5"}, clear=False):
        with patch("services.otp_service.OTP_PEPPER", pepper):
            with patch("services.otp_service.OTP_MAX_ATTEMPTS", 5):
                with patch("services.otp_service.database.get_db", return_value=db):
                    ok, _ = await verify_otp(phone_e164=phone_e164, code="123456", purpose="step_up", correlation_id="v5")
    assert ok is False
    db.otp_codes.update_one.assert_not_called()
    db.otp_codes.delete_one.assert_not_called()


@pytest.mark.asyncio
async def test_otp_verify_purpose_verify_phone_updates_notification_preferences():
    """When purpose is verify_phone and code is valid, notification_preferences.sms_phone_verified is set."""
    from services.otp_service import verify_otp, _phone_hash, _code_hash

    pepper = "p"
    raw_code = "654321"
    phone_e164 = "+447700900111"
    ph = _phone_hash(phone_e164)
    doc = {
        "code_hash": _code_hash(raw_code),
        "attempts": 0,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    db = MagicMock()
    db.otp_codes.find_one = AsyncMock(return_value=doc)
    db.otp_codes.delete_one = AsyncMock()
    db.notification_preferences = MagicMock()
    db.notification_preferences.update_many = AsyncMock(return_value=MagicMock(modified_count=1))

    with patch.dict("os.environ", {"OTP_PEPPER": pepper}, clear=False):
        with patch("services.otp_service.OTP_PEPPER", pepper):
            with patch("services.otp_service.database.get_db", return_value=db):
                ok, _ = await verify_otp(phone_e164=phone_e164, code=raw_code, purpose="verify_phone", correlation_id="v3")
    assert ok is True
    db.notification_preferences.update_many.assert_called_once()
    call = db.notification_preferences.update_many.call_args[0]
    assert call[0][0]["sms_phone_number"] == phone_e164
    assert call[1]["$set"]["sms_phone_verified"] is True


@pytest.mark.asyncio
async def test_otp_verify_step_up_with_user_id_issues_token():
    """When purpose=step_up and user_id provided, success returns (True, step_up_token) and inserts step_up_tokens."""
    from services.otp_service import verify_otp, _phone_hash, _code_hash

    pepper = "pp"
    raw_code = "111222"
    phone_e164 = "+447700900333"
    user_id = "portal-user-123"
    ph = _phone_hash(phone_e164)
    doc = {
        "code_hash": _code_hash(raw_code),
        "attempts": 0,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    db = MagicMock()
    db.otp_codes.find_one = AsyncMock(return_value=doc)
    db.otp_codes.delete_one = AsyncMock()
    db.step_up_tokens = MagicMock()
    db.step_up_tokens.insert_one = AsyncMock()

    with patch.dict("os.environ", {"OTP_PEPPER": pepper}, clear=False):
        with patch("services.otp_service.OTP_PEPPER", pepper):
            with patch("services.otp_service.database.get_db", return_value=db):
                ok, step_token = await verify_otp(
                    phone_e164=phone_e164, code=raw_code, purpose="step_up",
                    correlation_id="v6", user_id=user_id,
                )
    assert ok is True
    assert step_token is not None
    assert len(step_token) > 0
    db.step_up_tokens.insert_one.assert_called_once()
    insert_doc = db.step_up_tokens.insert_one.call_args[0][0]
    assert insert_doc["user_id"] == user_id
    assert "token_hash" in insert_doc
    assert insert_doc["purpose_scope"] == "step_up"


@pytest.mark.asyncio
async def test_otp_verify_no_record_returns_fail():
    """Verify when no OTP record exists returns (False, None) (no enumeration)."""
    from services.otp_service import verify_otp

    db = MagicMock()
    db.otp_codes.find_one = AsyncMock(return_value=None)

    with patch.dict("os.environ", {"OTP_PEPPER": "x"}, clear=False):
        with patch("services.otp_service.database.get_db", return_value=db):
            ok, _ = await verify_otp(phone_e164="+447700900222", code="111111", purpose="step_up", correlation_id="v4")
    assert ok is False


@pytest.mark.asyncio
async def test_consume_step_up_token_valid_one_time_use():
    """Valid step-up token is consumed (deleted) and returns True; second use returns False."""
    from services.otp_service import consume_step_up_token
    import hashlib

    user_id = "user-1"
    token_plain = "test-token-secret"
    token_hash = hashlib.sha256(token_plain.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=5)
    doc = {"user_id": user_id, "token_hash": token_hash, "expires_at": expires_at}
    db = MagicMock()
    db.step_up_tokens.find_one = AsyncMock(side_effect=[doc, None])
    db.step_up_tokens.delete_one = AsyncMock()

    with patch("services.otp_service.database.get_db", return_value=db):
        ok1 = await consume_step_up_token(token_plain, user_id)
        ok2 = await consume_step_up_token(token_plain, user_id)
    assert ok1 is True
    assert ok2 is False
    assert db.step_up_tokens.delete_one.call_count == 2
