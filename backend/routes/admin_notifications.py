"""
Admin Notifications Routes - Manage admin notification preferences and in-app notifications.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional, List
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
    prefs = await get_admin_notification_preferences(current_user.get("user_id"))
    return prefs


@router.put("/preferences")
async def update_notification_preferences(
    request: NotificationPreferencesRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """Update admin's notification preferences."""
    updated = await update_admin_notification_preferences(
        admin_id=current_user.get("user_id"),
        email_enabled=request.email_enabled,
        sms_enabled=request.sms_enabled,
        in_app_enabled=request.in_app_enabled,
        notification_email=request.notification_email,
        notification_phone=request.notification_phone,
    )
    
    return {
        "success": True,
        "preferences": updated,
    }


# ============================================
# IN-APP NOTIFICATIONS
# ============================================

@router.get("/")
async def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    current_user: dict = Depends(admin_route_guard),
):
    """List notifications for the admin."""
    if unread_only:
        notifications = await get_unread_notifications(
            current_user.get("user_id"), 
            limit=limit
        )
    else:
        notifications = await get_all_notifications(
            current_user.get("user_id"), 
            limit=limit
        )
    
    unread_count = await get_unread_count(current_user.get("user_id"))
    
    return {
        "notifications": notifications,
        "total": len(notifications),
        "unread_count": unread_count,
    }


@router.get("/unread-count")
async def get_notification_count(
    current_user: dict = Depends(admin_route_guard),
):
    """Get count of unread notifications."""
    count = await get_unread_count(current_user.get("user_id"))
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
    count = await mark_all_notifications_read(current_user.get("user_id"))
    
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
    
    update_fields = {"updated_at": datetime.now(timezone.utc)}
    
    if request.name:
        update_fields["name"] = request.name
    if request.notification_email:
        update_fields["notification_preferences.notification_email"] = request.notification_email
    if request.notification_phone:
        update_fields["notification_preferences.notification_phone"] = request.notification_phone
    
    await db.portal_users.update_one(
        {"user_id": current_user.get("user_id")},
        {"$set": update_fields}
    )
    
    # Fetch updated profile
    admin = await db.portal_users.find_one(
        {"user_id": current_user.get("user_id")},
        {"_id": 0, "password_hash": 0}
    )
    
    return {
        "success": True,
        "profile": admin,
    }


@router.get("/profile")
async def get_admin_profile(
    current_user: dict = Depends(admin_route_guard),
):
    """Get admin's profile with notification settings."""
    db = database.get_db()
    
    admin = await db.portal_users.find_one(
        {"user_id": current_user.get("user_id")},
        {"_id": 0, "password_hash": 0}
    )
    
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    return admin
