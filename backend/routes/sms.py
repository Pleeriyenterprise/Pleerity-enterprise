"""SMS Routes - SMS notification management and test-send.
OTP is only via POST /api/otp/send and POST /api/otp/verify (see routes/otp.py).
"""
from fastapi import APIRouter, HTTPException, Request, status
from database import database
from middleware import client_route_guard
from services.sms_service import sms_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sms", tags=["sms"])


@router.get("/status")
async def get_sms_status():
    """Get SMS service status and configuration."""
    return {
        "enabled": sms_service.is_enabled(),
        "configured": sms_service.is_configured(),
        "feature_flag": sms_service.is_enabled()
    }


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
