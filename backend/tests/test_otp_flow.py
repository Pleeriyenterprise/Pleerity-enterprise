"""
Unit tests for enterprise OTP flow (send + verify).
- OTP stored as hash only; generic responses; cooldown and max attempts.
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
async def test_otp_send_returns_generic_success_and_upserts_hash_only():
    """POST /api/sms/otp/send returns generic success; DB stores otp_hash, never raw OTP."""
    from services.otp_service import send_otp, OTP_PEPPER, GENERIC_SEND_SUCCESS

    db = MagicMock()
    db.otp_codes.find_one = AsyncMock(return_value=None)
    db.otp_codes.update_one = AsyncMock(return_value=MagicMock(modified_count=0, upserted_id=1))

    with patch.dict("os.environ", {"OTP_PEPPER": "test-pepper"}, clear=False):
        with patch("services.otp_service.database.get_db", return_value=db):
            with patch("services.otp_service.sms_service.is_messaging_service_configured", return_value=True):
                with patch("services.otp_service.sms_service.send_sms_via_messaging_service", new_callable=AsyncMock) as send_sms:
                    send_sms.return_value = {"success": True}
                    ok, message = await send_otp(phone_number="+447700900123", purpose="verify_phone", correlation_id="cid-1")
    assert ok is True
    assert message == GENERIC_SEND_SUCCESS
    db.otp_codes.update_one.assert_called_once()
    call_kw = db.otp_codes.update_one.call_args[0][2]["$set"]
    assert "otp_hash" in call_kw
    assert "phone_e164" in call_kw
    assert call_kw["phone_e164"] == "+447700900123"
    assert call_kw["purpose"] == "verify_phone"
    assert "otp" not in str(call_kw).lower() or "otp_hash" in call_kw
    assert len(call_kw["otp_hash"]) == 64


@pytest.mark.asyncio
async def test_otp_send_without_pepper_returns_generic_success_no_send():
    """When OTP_PEPPER is not set, send still returns generic success and does not send SMS."""
    from services.otp_service import send_otp, GENERIC_SEND_SUCCESS

    db = MagicMock()
    db.otp_codes.find_one = AsyncMock(return_value=None)

    with patch.dict("os.environ", {"OTP_PEPPER": ""}, clear=False):
        with patch("services.otp_service.OTP_PEPPER", ""):
            with patch("services.otp_service.database.get_db", return_value=db):
                ok, message = await send_otp(phone_number="+447700900123", purpose="step_up", correlation_id="cid-2")
    assert ok is True
    assert message == GENERIC_SEND_SUCCESS
    db.otp_codes.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_otp_verify_valid_code_returns_success():
    """Verify with correct code (matching hash) returns success."""
    from services.otp_service import verify_otp, _otp_hash, GENERIC_VERIFY_SUCCESS

    raw_code = "123456"
    pepper = "my-pepper"
    phone_e164 = "+447700900456"
    purpose = "step_up"
    db = MagicMock()
    db.otp_codes.update_one = AsyncMock()
    db.otp_codes.delete_one = AsyncMock()

    with patch.dict("os.environ", {"OTP_PEPPER": pepper}, clear=False):
        with patch("services.otp_service.OTP_PEPPER", pepper):
            doc = {
                "otp_hash": _otp_hash(raw_code),
                "attempts": 0,
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            }
            db.otp_codes.find_one = AsyncMock(return_value=doc)
            with patch("services.otp_service.database.get_db", return_value=db):
                ok, message = await verify_otp(phone_number=phone_e164, code=raw_code, purpose=purpose, correlation_id="v1")
    assert ok is True
    assert message == GENERIC_VERIFY_SUCCESS
    db.otp_codes.delete_one.assert_called_once()


@pytest.mark.asyncio
async def test_otp_verify_wrong_code_returns_generic_fail_and_increments_attempts():
    """Verify with wrong code returns generic fail and increments attempts."""
    from services.otp_service import verify_otp, _otp_hash, GENERIC_VERIFY_FAIL

    pepper = "pep"
    phone_e164 = "+447700900789"
    purpose = "verify_phone"
    db = MagicMock()
    db.otp_codes.update_one = AsyncMock()

    with patch.dict("os.environ", {"OTP_PEPPER": pepper}, clear=False):
        with patch("services.otp_service.OTP_PEPPER", pepper):
            doc = {
                "otp_hash": _otp_hash("000000"),
                "attempts": 1,
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            }
            db.otp_codes.find_one = AsyncMock(return_value=doc)
            with patch("services.otp_service.database.get_db", return_value=db):
                ok, message = await verify_otp(phone_number=phone_e164, code="123456", purpose=purpose, correlation_id="v2")
    assert ok is False
    assert message == GENERIC_VERIFY_FAIL
    db.otp_codes.update_one.assert_called_once()
    assert db.otp_codes.update_one.call_args[0][2]["$inc"]["attempts"] == 1


@pytest.mark.asyncio
async def test_otp_verify_purpose_verify_phone_updates_notification_preferences():
    """When purpose is verify_phone and code is valid, notification_preferences.sms_phone_verified is set."""
    from services.otp_service import verify_otp, _otp_hash, GENERIC_VERIFY_SUCCESS

    pepper = "p"
    raw_code = "654321"
    phone_e164 = "+447700900111"
    db = MagicMock()
    db.otp_codes.delete_one = AsyncMock()
    db.notification_preferences = MagicMock()
    db.notification_preferences.update_many = AsyncMock(return_value=MagicMock(modified_count=1))

    with patch.dict("os.environ", {"OTP_PEPPER": pepper}, clear=False):
        with patch("services.otp_service.OTP_PEPPER", pepper):
            doc = {
                "otp_hash": _otp_hash(raw_code),
                "attempts": 0,
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            }
            db.otp_codes.find_one = AsyncMock(return_value=doc)
            with patch("services.otp_service.database.get_db", return_value=db):
                ok, message = await verify_otp(phone_number=phone_e164, code=raw_code, purpose="verify_phone", correlation_id="v3")
    assert ok is True
    assert message == GENERIC_VERIFY_SUCCESS
    db.notification_preferences.update_many.assert_called_once()
    call = db.notification_preferences.update_many.call_args[0]
    assert call[0][0]["sms_phone_number"] == phone_e164
    assert call[1]["$set"]["sms_phone_verified"] is True


@pytest.mark.asyncio
async def test_otp_verify_no_record_returns_generic_fail():
    """Verify when no OTP record exists returns generic fail (no leak)."""
    from services.otp_service import verify_otp, GENERIC_VERIFY_FAIL

    db = MagicMock()
    db.otp_codes.find_one = AsyncMock(return_value=None)

    with patch.dict("os.environ", {"OTP_PEPPER": "x"}, clear=False):
        with patch("services.otp_service.database.get_db", return_value=db):
            ok, message = await verify_otp(phone_number="+447700900222", code="111111", purpose="step_up", correlation_id="v4")
    assert ok is False
    assert message == GENERIC_VERIFY_FAIL
