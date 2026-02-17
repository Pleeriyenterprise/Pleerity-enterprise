"""SMS Routes - Phone verification and SMS settings
Provides endpoints for OTP verification and SMS notification management.
Legacy Twilio Verify endpoints (/send-otp, /verify-otp) return 410 Gone; use /api/otp/send and /api/otp/verify.
"""
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from database import database
from middleware import client_route_guard
from services.sms_service import sms_service
from services.otp_service import send_otp as otp_send, verify_otp as otp_verify
from utils.audit import create_audit_log
from models import AuditAction, UserRole
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sms", tags=["sms"])


class SendOTPRequest(BaseModel):
    phone_number: str  # E.164 format (+44...)


class OtpSendRequest(BaseModel):
    """Enterprise OTP send. Request uses phone_e164; response always { status: sent }."""
    phone_e164: str = Field(..., min_length=10, description="E.164 phone number")
    purpose: str = Field(..., pattern="^(verify_phone|step_up)$")


class OtpVerifyRequest(BaseModel):
    """Enterprise OTP verify. Response 200 { status: verified [, step_up_token ] } or 400 generic."""
    phone_e164: str = Field(..., min_length=10)
    code: str = Field(..., pattern="^[0-9]{6}$")
    purpose: str = Field(..., pattern="^(verify_phone|step_up)$")


class VerifyOTPRequest(BaseModel):
    phone_number: str
    code: str  # 6-digit code


@router.get("/status")
async def get_sms_status():
    """Get SMS service status and configuration."""
    return {
        "enabled": sms_service.is_enabled(),
        "configured": sms_service.is_configured(),
        "feature_flag": sms_service.is_enabled()
    }


def _correlation_id(request: Request) -> str:
    return (request.headers.get("X-Correlation-ID") or "").strip() or None


@router.post("/otp/send")
async def enterprise_otp_send(request: Request, data: OtpSendRequest):
    """
    Send OTP to phone via Twilio Messaging Service.
    Always 200 { "status": "sent" } (do not leak existence).
    """
    try:
        await otp_send(
            phone_e164=data.phone_e164,
            purpose=data.purpose,
            correlation_id=_correlation_id(request),
        )
        return {"status": "sent"}
    except Exception as e:
        logger.exception(f"OTP send error: {e}")
        return {"status": "sent"}


@router.post("/otp/verify")
async def enterprise_otp_verify(request: Request, data: OtpVerifyRequest):
    """
    Verify OTP. Success: 200 { "status": "verified" } or { "status": "verified", "step_up_token": "..." }.
    Failure: 400 { "detail": "Invalid or expired code" }. step_up requires auth (user_id for token).
    """
    cid = _correlation_id(request)
    user_id = None
    if data.purpose == "step_up":
        try:
            user = await client_route_guard(request)
            user_id = user.get("portal_user_id") or user.get("client_id")
        except HTTPException:
            raise
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    try:
        ok, step_up_token = await otp_verify(
            phone_e164=data.phone_e164,
            code=data.code,
            purpose=data.purpose,
            correlation_id=cid,
            user_id=user_id,
        )
        if ok:
            out = {"status": "verified"}
            if step_up_token is not None:
                out["step_up_token"] = step_up_token
            return out
    except Exception as e:
        logger.exception(f"OTP verify error: {e}")
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")


# --- Legacy Twilio Verify endpoints: deprecated, return 410 Gone. Use /api/otp/send and /api/otp/verify. ---
LEGACY_OTP_410_BODY = {
    "error": "LEGACY_OTP_ENDPOINT_DEPRECATED",
    "use": "/api/otp/send and /api/otp/verify",
}


@router.post("/send-otp")
async def send_otp_legacy(request: Request, data: SendOTPRequest):
    """DEPRECATED: Legacy Twilio Verify send. Use POST /api/otp/send."""
    return JSONResponse(
        status_code=status.HTTP_410_GONE,
        content=LEGACY_OTP_410_BODY,
    )


@router.post("/verify-otp")
async def verify_otp_legacy(request: Request, data: VerifyOTPRequest):
    """DEPRECATED: Legacy Twilio Verify verify. Use POST /api/otp/verify."""
    return JSONResponse(
        status_code=status.HTTP_410_GONE,
        content=LEGACY_OTP_410_BODY,
    )


@router.post("/test-send")
async def test_send_sms(request: Request):
    """Send a test SMS to the verified phone number (for testing only)."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    # Get notification preferences
    prefs = await db.notification_preferences.find_one(
        {"client_id": user["client_id"]},
        {"_id": 0}
    )
    
    if not prefs or not prefs.get("sms_phone_verified"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number not verified. Please verify your phone first."
        )
    
    phone = prefs.get("sms_phone_number")
    
    if not sms_service.is_enabled():
        return {
            "success": True,
            "message": f"Test SMS would be sent to {phone[:7]}*** (SMS not enabled)"
        }
    
    from services.notification_orchestrator import notification_orchestrator
    result = await notification_orchestrator.send(
        template_key="ADMIN_MANUAL_SMS",
        client_id=user["client_id"],
        context={"body": "🔔 Compliance Vault Pro: This is a test message. Your SMS notifications are working!"},
        idempotency_key=f"{user['client_id']}_test_sms_{__import__('time').time()}",
        event_type="test_sms",
    )
    if result.outcome in ("sent", "duplicate_ignored"):
        return {"success": True, "message": f"Test SMS sent to {phone[:7]}***"}
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=result.error_message or result.block_reason or "Failed to send test SMS"
    )
