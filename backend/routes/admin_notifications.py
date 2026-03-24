"""
Admin Notifications Routes - Manage admin notification preferences and in-app notifications.
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from database import database
from middleware import admin_route_guard
from services.order_service import (
    get_admin_notification_preferences,
    update_admin_notification_preferences,
    get_unread_notifications,
    get_all_notifications,
    mark_notification_read,
    mark_all_notifications_read,
    get_unread_count,
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/notifications", tags=["admin-notifications"])


# ============================================
# NOTIFICATION PREFERENCES
# ============================================

class NotificationPreferencesRequest(BaseModel):
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
    notification_email: Optional[EmailStr] = None
    notification_phone: Optional[str] = None


@router.get("/preferences")
async def get_notification_preferences(
    current_user: dict = Depends(admin_route_guard),
):
    """Get admin's notification preferences."""
    admin_id = current_user.get("portal_user_id") or current_user.get("user_id")
    prefs = await get_admin_notification_preferences(admin_id)
    return prefs


@router.put("/preferences")
async def update_notification_preferences(
    request: NotificationPreferencesRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """Update admin's notification preferences."""
    admin_id = current_user.get("portal_user_id") or current_user.get("user_id")
    try:
        updated = await update_admin_notification_preferences(
            admin_id=admin_id,
            email_enabled=request.email_enabled,
            sms_enabled=request.sms_enabled,
            in_app_enabled=request.in_app_enabled,
            notification_email=request.notification_email,
            notification_phone=request.notification_phone,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    
    return {
        "success": True,
        "preferences": updated,
    }


# ============================================
# IN-APP NOTIFICATIONS
# ============================================

def _admin_id(current_user: dict):
    """Resolve admin id for notification lookups (portal_user_id or user_id)."""
    return current_user.get("portal_user_id") or current_user.get("user_id")


def _serialize_notification(n: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure datetime fields are ISO strings for JSON (bell expects date strings)."""
    out = dict(n)
    for key in ("created_at", "read_at"):
        if key in out and out[key] is not None and hasattr(out[key], "isoformat"):
            out[key] = out[key].isoformat()
    return out


@router.get("/")
async def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    current_user: dict = Depends(admin_route_guard),
):
    """List notifications for the admin. recipient_id in DB must match JWT portal_user_id for bell to show them."""
    admin_id = _admin_id(current_user)
    if unread_only:
        notifications = await get_unread_notifications(admin_id, limit=limit)
    else:
        notifications = await get_all_notifications(admin_id, limit=limit)
    unread_count = await get_unread_count(admin_id)
    return {
        "notifications": [_serialize_notification(n) for n in notifications],
        "total": len(notifications),
        "unread_count": unread_count,
    }


@router.get("/unread-count")
async def get_notification_count(
    current_user: dict = Depends(admin_route_guard),
):
    """Get count of unread notifications."""
    count = await get_unread_count(_admin_id(current_user))
    return {"unread_count": count}


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Mark a single notification as read."""
    success = await mark_notification_read(notification_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"success": True}


@router.post("/read-all")
async def mark_all_as_read(
    current_user: dict = Depends(admin_route_guard),
):
    """Mark all notifications as read."""
    count = await mark_all_notifications_read(_admin_id(current_user))
    
    return {
        "success": True,
        "marked_read": count,
    }


# ============================================
# ADMIN PROFILE UPDATE (Notification Settings)
# ============================================

class AdminProfileUpdate(BaseModel):
    name: Optional[str] = None
    notification_email: Optional[EmailStr] = None
    notification_phone: Optional[str] = None


@router.put("/profile")
async def update_admin_profile(
    request: AdminProfileUpdate,
    current_user: dict = Depends(admin_route_guard),
):
    """Update admin's profile (name, notification contact details)."""
    db = database.get_db()
    aid = _admin_id(current_user)
    update_fields = {"updated_at": datetime.now(timezone.utc)}
    if request.name:
        update_fields["name"] = request.name
    if request.notification_email:
        update_fields["notification_preferences.notification_email"] = request.notification_email
    if request.notification_phone:
        update_fields["notification_preferences.notification_phone"] = request.notification_phone
    await db.portal_users.update_one(
        {"$or": [{"portal_user_id": aid}, {"user_id": aid}], "role": {"$in": ["admin", "ROLE_ADMIN", "ROLE_OWNER"]}},
        {"$set": update_fields}
    )
    admin = await db.portal_users.find_one(
        {"$or": [{"portal_user_id": aid}, {"user_id": aid}]},
        {"_id": 0, "password_hash": 0}
    )
    return {"success": True, "profile": admin or {}}


@router.get("/profile")
async def get_admin_profile(
    current_user: dict = Depends(admin_route_guard),
):
    """Get admin's profile with notification settings."""
    db = database.get_db()
    aid = _admin_id(current_user)
    admin = await db.portal_users.find_one(
        {"$or": [{"portal_user_id": aid}, {"user_id": aid}]},
        {"_id": 0, "password_hash": 0}
    )
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    return admin


@router.post("/test-sms")
async def send_test_sms(
    body: Optional[Dict[str, Any]] = Body(None),
    current_user: dict = Depends(admin_route_guard),
):
    """Send a test SMS to the current admin's notification phone. Use to verify SMS config without OTP.
    Optional body: { \"phone\": \"+44...\" }. If provided, uses that number so you can test before saving preferences."""
    phone = None
    if body and isinstance(body.get("phone"), str) and body["phone"].strip():
        phone = body["phone"].strip()
    if not phone:
        prefs = await get_admin_notification_preferences(_admin_id(current_user))
        phone = prefs.get("notification_phone") or (current_user.get("phone") if isinstance(current_user.get("phone"), str) else None)
    if not phone or not str(phone).strip():
        raise HTTPException(status_code=400, detail="No notification phone set. Set a phone number in Notification Preferences first.")
    from services.notification_orchestrator import notification_orchestrator
    import time
    result = await notification_orchestrator.send(
        template_key="ADMIN_MANUAL_SMS",
        client_id=None,
        context={
            "recipient": str(phone).strip(),
            "body": "Pleerity: This is a test SMS. Your admin SMS notifications are working.",
        },
        idempotency_key=f"admin_test_sms_{_admin_id(current_user)}_{int(time.time())}",
        event_type="admin_test_sms",
    )
    if result.outcome in ("sent", "duplicate_ignored"):
        return {"success": True, "message": f"Test SMS sent to {str(phone)[:7]}***"}
    raise HTTPException(
        status_code=503 if result.block_reason else 500,
        detail=result.error_message or result.block_reason or "Failed to send test SMS",
    )
