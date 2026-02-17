"""SMS Routes - Phone verification and SMS settings
Provides endpoints for OTP verification and SMS notification management.
"""
from fastapi import APIRouter, HTTPException, Request, status
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


@router.post("/send-otp")
async def send_otp(request: Request, data: SendOTPRequest):
    """Send OTP to a phone number for verification.
    
    Phone number must be in E.164 format (e.g., +447123456789).
    """
    user = await client_route_guard(request)
    
    # Validate phone number format
    phone = data.phone_number.strip()
    if not phone.startswith("+"):
        phone = f"+{phone}"
    
    if len(phone) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format. Use E.164 format (e.g., +447123456789)"
        )
    
    # Check if SMS is enabled
    if not sms_service.is_enabled():
        # Return mock success for development
        logger.info(f"SMS not enabled - mock OTP sent to {phone[:7]}***")
        
        # Store pending verification
        db = database.get_db()
        await db.phone_verifications.update_one(
            {"client_id": user["client_id"]},
            {"$set": {
                "phone_number": phone,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "mock_mode": True
            }},
            upsert=True
        )
        
        return {
            "success": True,
            "status": "pending",
            "message": "OTP sent (development mode - use code 123456)"
        }
    
    # Send real OTP via Twilio
    result = await sms_service.send_otp(phone)
    
    if result["success"]:
        # Store pending verification
        db = database.get_db()
        await db.phone_verifications.update_one(
            {"client_id": user["client_id"]},
            {"$set": {
                "phone_number": phone,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "mock_mode": False
            }},
            upsert=True
        )
        
        return {"success": True, "status": result["status"]}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to send OTP")
        )


@router.post("/verify-otp")
async def verify_otp(request: Request, data: VerifyOTPRequest):
    """Verify OTP code and mark phone as verified.
    
    In development mode, use code '123456' for testing.
    """
    user = await client_route_guard(request)
    db = database.get_db()
    
    # Validate phone number format
    phone = data.phone_number.strip()
    if not phone.startswith("+"):
        phone = f"+{phone}"
    
    # Check pending verification
    pending = await db.phone_verifications.find_one(
        {"client_id": user["client_id"], "phone_number": phone},
        {"_id": 0}
    )
    
    if not pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending verification found. Please request a new OTP."
        )
    
    # Check if in mock mode or real mode
    is_mock = pending.get("mock_mode", True) or not sms_service.is_enabled()
    
    if is_mock:
        # Development mode - accept code 123456
        is_valid = data.code == "123456"
    else:
        # Real verification via Twilio
        result = await sms_service.verify_otp(phone, data.code)
        is_valid = result.get("valid", False)
    
    if is_valid:
        # Update notification preferences with verified phone
        await db.notification_preferences.update_one(
            {"client_id": user["client_id"]},
            {"$set": {
                "sms_phone_number": phone,
                "sms_phone_verified": True,
                "sms_verified_at": datetime.now(timezone.utc).isoformat()
            }},
            upsert=True
        )
        
        # Clean up pending verification
        await db.phone_verifications.delete_one({"client_id": user["client_id"]})
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole(user["role"]),
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="phone_verification",
            metadata={
                "action": "phone_verified",
                "phone_number_masked": f"{phone[:7]}***"
            }
        )
        
        return {"success": True, "valid": True, "message": "Phone number verified successfully"}
    else:
        return {"success": True, "valid": False, "message": "Invalid code. Please try again."}


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
