"""User Profile Routes - Additive Enhancement
Allows clients to view and update their profile and notification preferences.
"""
from fastapi import APIRouter, HTTPException, Request, status, File, UploadFile
from fastapi.responses import FileResponse
from database import database
from middleware import client_route_guard, require_auth
from services import admin_communications_service as acs
from models import AuditAction, UserRole
from utils.audit import create_audit_log
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timezone
from pathlib import Path
import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/profile", tags=["profile"])

DATA_DIR = os.getenv("DATA_DIR", "/tmp")
PROFILE_AVATARS_PATH = Path(DATA_DIR) / "data" / "profile_avatars"
PROFILE_AVATARS_PATH.mkdir(parents=True, exist_ok=True)
AVATAR_MAX_BYTES = 5 * 1024 * 1024  # 5MB
AVATAR_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None

class NotificationPreferencesRequest(BaseModel):
    # Email notification types
    status_change_alerts: Optional[bool] = None  # GREEN→AMBER→RED changes
    expiry_reminders: Optional[bool] = None  # Daily expiry reminders
    monthly_digest: Optional[bool] = None  # Monthly compliance summary
    document_updates: Optional[bool] = None  # Document notifications
    system_announcements: Optional[bool] = None  # Platform updates

    # Category-based email preferences (unified template system)
    compliance_notifications_enabled: Optional[bool] = None  # Certificate expiry, compliance alerts
    reporting_notifications_enabled: Optional[bool] = None  # Scheduled reports, digests, renewal reminders
    marketing_notifications_enabled: Optional[bool] = None  # Product announcements, promotions
    
    # Timing preferences
    reminder_days_before: Optional[int] = None  # Days before expiry (7, 14, 30, 60)
    
    # Quiet hours (optional)
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = None  # HH:MM format
    quiet_hours_end: Optional[str] = None
    
    # SMS preferences (feature flagged)
    sms_enabled: Optional[bool] = None
    sms_phone_number: Optional[str] = None
    sms_urgent_alerts_only: Optional[bool] = None
    
    # Email Digest Customization
    digest_compliance_summary: Optional[bool] = None
    digest_action_items: Optional[bool] = None
    digest_upcoming_expiries: Optional[bool] = None
    digest_property_breakdown: Optional[bool] = None
    digest_recent_documents: Optional[bool] = None
    digest_recommendations: Optional[bool] = None
    digest_audit_summary: Optional[bool] = None
    daily_reminder_enabled: Optional[bool] = None

@router.get("/me")
async def get_profile(request: Request):
    """Get current user profile and preferences."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Get portal user
        portal_user = await db.portal_users.find_one(
            {"portal_user_id": user["portal_user_id"]},
            {"_id": 0}
        )
        
        if not portal_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get client data
        client = await db.clients.find_one(
            {"client_id": user["client_id"]},
            {"_id": 0}
        )
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Get notification preferences
        preferences = await db.notification_preferences.find_one(
            {"client_id": user["client_id"]},
            {"_id": 0}
        )
        
        # Default preferences if not set
        if not preferences:
            preferences = {
                "status_change_alerts": True,
                "expiry_reminders": True,
                "monthly_digest": True,
                "document_updates": True,
                "system_announcements": True,
                "compliance_notifications_enabled": True,
                "reporting_notifications_enabled": True,
                "marketing_notifications_enabled": True,
                "reminder_days_before": 30,
                "quiet_hours_enabled": False,
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "08:00"
            }
        
        profile = {
            "portal_user_id": portal_user["portal_user_id"],
            "email": portal_user.get("auth_email") or "",
            "full_name": client.get("full_name") or "",
            "phone": client.get("phone"),
            "company_name": client.get("company_name"),
            "client_type": client.get("client_type") or "INDIVIDUAL",
            "has_avatar": bool(client.get("avatar_updated_at")),
            "notification_preferences": preferences
        }
        
        return profile
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get profile error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load profile"
        )

@router.get("/notifications")
async def get_notification_preferences(request: Request):
    """Get notification preferences only."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        stored_preferences = await db.notification_preferences.find_one(
            {"client_id": user["client_id"]},
            {"_id": 0}
        )
        
        # Default preferences (including SMS fields and digest customization)
        default_preferences = {
            "client_id": user["client_id"],
            "status_change_alerts": True,
            "expiry_reminders": True,
            "monthly_digest": True,
            "document_updates": True,
            "system_announcements": True,
            "compliance_notifications_enabled": True,
            "reporting_notifications_enabled": True,
            "marketing_notifications_enabled": True,
            "reminder_days_before": 30,
            "quiet_hours_enabled": False,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
            # SMS preferences (feature flagged)
            "sms_enabled": False,
            "sms_phone_number": "",
            "sms_phone_verified": False,
            "sms_urgent_alerts_only": True,
            # Email Digest Customization
            "digest_compliance_summary": True,
            "digest_action_items": True,
            "digest_upcoming_expiries": True,
            "digest_property_breakdown": True,
            "digest_recent_documents": True,
            "digest_recommendations": True,
            "digest_audit_summary": False,
            "daily_reminder_enabled": True
        }
        
        # Merge stored preferences with defaults (stored values override defaults)
        if stored_preferences:
            preferences = {**default_preferences, **stored_preferences}
        else:
            preferences = default_preferences
        
        return preferences
    
    except Exception as e:
        logger.error(f"Get notification preferences error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load notification preferences"
        )

@router.put("/notifications")
async def update_notification_preferences(request: Request, data: NotificationPreferencesRequest):
    """Update notification preferences."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Get current preferences
        current = await db.notification_preferences.find_one(
            {"client_id": user["client_id"]},
            {"_id": 0}
        )
        
        before_state = current.copy() if current else {}
        
        # Build update
        update_fields = {"client_id": user["client_id"]}
        
        if data.status_change_alerts is not None:
            update_fields["status_change_alerts"] = data.status_change_alerts
        if data.expiry_reminders is not None:
            update_fields["expiry_reminders"] = data.expiry_reminders
        if data.monthly_digest is not None:
            update_fields["monthly_digest"] = data.monthly_digest
        if data.document_updates is not None:
            update_fields["document_updates"] = data.document_updates
        if data.system_announcements is not None:
            update_fields["system_announcements"] = data.system_announcements
        if data.reminder_days_before is not None:
            # Validate reminder days
            if data.reminder_days_before not in [1, 7, 14, 30, 60, 90]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="reminder_days_before must be 1, 7, 14, 30, 60, or 90"
                )
            update_fields["reminder_days_before"] = data.reminder_days_before
        if data.quiet_hours_enabled is not None:
            update_fields["quiet_hours_enabled"] = data.quiet_hours_enabled
        if data.quiet_hours_start is not None:
            update_fields["quiet_hours_start"] = data.quiet_hours_start
        if data.quiet_hours_end is not None:
            update_fields["quiet_hours_end"] = data.quiet_hours_end
        
        # SMS preferences (feature flagged)
        if data.sms_enabled is not None:
            update_fields["sms_enabled"] = data.sms_enabled
        if data.sms_phone_number is not None:
            incoming_phone = (data.sms_phone_number or "").strip()
            current_phone = ((current or {}).get("sms_phone_number") or "").strip()
            update_fields["sms_phone_number"] = incoming_phone
            # Only reset verification when the phone number actually changes.
            if incoming_phone != current_phone:
                update_fields["sms_phone_verified"] = False
        if data.sms_urgent_alerts_only is not None:
            update_fields["sms_urgent_alerts_only"] = data.sms_urgent_alerts_only
        
        # Email Digest Customization
        if data.digest_compliance_summary is not None:
            update_fields["digest_compliance_summary"] = data.digest_compliance_summary
        if data.digest_action_items is not None:
            update_fields["digest_action_items"] = data.digest_action_items
        if data.digest_upcoming_expiries is not None:
            update_fields["digest_upcoming_expiries"] = data.digest_upcoming_expiries
        if data.digest_property_breakdown is not None:
            update_fields["digest_property_breakdown"] = data.digest_property_breakdown
        if data.digest_recent_documents is not None:
            update_fields["digest_recent_documents"] = data.digest_recent_documents
        if data.digest_recommendations is not None:
            update_fields["digest_recommendations"] = data.digest_recommendations
        if data.digest_audit_summary is not None:
            update_fields["digest_audit_summary"] = data.digest_audit_summary
        if data.daily_reminder_enabled is not None:
            update_fields["daily_reminder_enabled"] = data.daily_reminder_enabled

        # Category-based email preferences
        if data.compliance_notifications_enabled is not None:
            update_fields["compliance_notifications_enabled"] = data.compliance_notifications_enabled
        if data.reporting_notifications_enabled is not None:
            update_fields["reporting_notifications_enabled"] = data.reporting_notifications_enabled
        if data.marketing_notifications_enabled is not None:
            update_fields["marketing_notifications_enabled"] = data.marketing_notifications_enabled
        
        update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Upsert preferences
        await db.notification_preferences.update_one(
            {"client_id": user["client_id"]},
            {"$set": update_fields},
            upsert=True
        )
        
        # Audit log with before/after
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole(user["role"]),
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="notification_preferences",
            before_state=before_state,
            after_state=update_fields,
            metadata={"action": "notification_preferences_updated"}
        )
        
        logger.info(f"Notification preferences updated for client {user['client_id']}")

        # When user enables compliance monitoring, stop any remaining onboarding sequence emails
        if data.compliance_notifications_enabled is True:
            try:
                from services.onboarding_sequence_service import cancel_remaining_onboarding_emails
                await cancel_remaining_onboarding_emails(user["client_id"])
            except Exception as cancel_err:
                logger.warning("Cancel onboarding emails on preference update: %s", cancel_err)
        
        return {"message": "Notification preferences updated successfully", "preferences": update_fields}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update notification preferences error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification preferences"
        )

@router.patch("/me")
async def update_profile(request: Request, data: UpdateProfileRequest):
    """Update user profile (name, phone only)."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Get current client data for audit log
        client = await db.clients.find_one(
            {"client_id": user["client_id"]},
            {"_id": 0}
        )
        
        before_state = {
            "full_name": client.get("full_name"),
            "phone": client.get("phone")
        }
        
        # Build update
        update_fields = {}
        if data.full_name is not None:
            update_fields["full_name"] = data.full_name
        if data.phone is not None:
            update_fields["phone"] = data.phone
        
        if not update_fields:
            return {"message": "No changes to apply"}
        
        # Update client record
        await db.clients.update_one(
            {"client_id": user["client_id"]},
            {"$set": update_fields}
        )
        
        after_state = {
            "full_name": data.full_name if data.full_name else before_state["full_name"],
            "phone": data.phone if data.phone else before_state["phone"]
        }
        
        # Audit log
        await create_audit_log(
            action=AuditAction.PROFILE_UPDATED_BY_CLIENT,
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="client_profile",
            before_state=before_state,
            after_state=after_state,
            metadata={"action": "profile_updated"}
        )
        
        logger.info(f"Profile updated for user {user['portal_user_id']}")
        
        return {"message": "Profile updated successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update profile error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )


@router.get("/me/avatar")
async def get_my_avatar(request: Request):
    """Return the current user's profile picture. 404 if none."""
    user = await client_route_guard(request)
    db = database.get_db()
    client = await db.clients.find_one(
        {"client_id": user["client_id"]},
        {"_id": 0, "avatar_ext": 1}
    )
    if not client or not client.get("avatar_ext"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No profile picture")
    ext = client.get("avatar_ext", ".jpg")
    file_path = PROFILE_AVATARS_PATH / f"{user['client_id']}{ext}"
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No profile picture")
    media = "image/jpeg" if ext == ".jpg" else ("image/png" if ext == ".png" else "image/webp")
    return FileResponse(path=str(file_path), media_type=media)


@router.post("/me/avatar")
async def upload_my_avatar(request: Request, file: UploadFile = File(...)):
    """Upload profile picture. Replaces existing. Logged for admin monitoring."""
    user = await client_route_guard(request)
    db = database.get_db()
    if not file.content_type or file.content_type.lower() not in AVATAR_ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Allowed types: JPEG, PNG, WebP"
        )
    content = await file.read()
    if len(content) > AVATAR_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large (max 5MB)"
        )
    ext = ".jpg" if "jpeg" in (file.content_type or "").lower() else (".png" if "png" in (file.content_type or "").lower() else ".webp")
    file_path = PROFILE_AVATARS_PATH / f"{user['client_id']}{ext}"
    file_path.write_bytes(content)
    now = datetime.now(timezone.utc).isoformat()
    await db.clients.update_one(
        {"client_id": user["client_id"]},
        {"$set": {"avatar_ext": ext, "avatar_updated_at": now}}
    )
    await create_audit_log(
        action=AuditAction.PROFILE_AVATAR_UPLOADED,
        actor_id=user["portal_user_id"],
        client_id=user["client_id"],
        resource_type="client_profile",
        metadata={"action": "avatar_uploaded"},
    )
    logger.info(f"Profile avatar uploaded for client {user['client_id']}")
    return {"message": "Profile picture updated", "has_avatar": True}


# --- In-app notifications & system banners (client communications) ---


@router.get("/in-app-notifications")
async def list_my_in_app_notifications(request: Request, limit: int = 50):
    """List in-app notifications for the authenticated portal user."""
    user = await client_route_guard(request)
    from services.order_service import get_all_notifications

    items = await get_all_notifications(user["portal_user_id"], limit=min(limit, 100))
    return {"items": items}


@router.get("/in-app-notifications/unread-count")
async def in_app_notifications_unread_count(request: Request):
    """Unread count for notification bell (admin broadcasts + system notices)."""
    user = await client_route_guard(request)
    from services.order_service import get_unread_count

    n = await get_unread_count(user["portal_user_id"])
    return {"unread_count": n}


@router.patch("/in-app-notifications/{notification_id}/read")
async def mark_in_app_notification_read(request: Request, notification_id: str):
    user = await client_route_guard(request)
    from services.order_service import mark_notification_read

    ok = await mark_notification_read(notification_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return {"ok": True}


@router.get("/system-banners/active")
async def list_active_system_banners(request: Request):
    """
    Active operational banners for the current user's client.
    Uses authentication only (not full client_route_guard) so invited users can see incident banners.
    """
    user = await require_auth(request)
    db = database.get_db()
    pu = await db.portal_users.find_one(
        {"portal_user_id": user["portal_user_id"]},
        {"_id": 0, "client_id": 1},
    )
    if not pu or not pu.get("client_id"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No client context")
    client_id = pu["client_id"]
    now = datetime.now(timezone.utc)
    q = {
        "active": True,
        "$and": [
            {"$or": [{"start_at": {"$lte": now}}, {"start_at": None}]},
            {"$or": [{"end_at": None}, {"end_at": {"$gte": now}}]},
        ],
    }
    banners = await db.system_banners.find(q, {"_id": 0}).sort("start_at", -1).to_list(length=100)
    dismissed = await db.system_banner_dismissals.find(
        {"portal_user_id": user["portal_user_id"]},
        {"_id": 0, "banner_id": 1},
    ).to_list(length=200)
    dismissed_set = {d["banner_id"] for d in dismissed if d.get("banner_id")}
    out: List[dict] = []
    for b in banners:
        if not await acs.banner_is_active_now(b, now):
            continue
        if not await acs.client_matches_banner_target(client_id, b):
            continue
        bid = b.get("banner_id")
        if b.get("persistent_display"):
            out.append(b)
            continue
        if bid and bid in dismissed_set:
            continue
        out.append(b)
    return {"items": out}


@router.post("/system-banners/{banner_id}/dismiss")
async def dismiss_system_banner(request: Request, banner_id: str):
    user = await require_auth(request)
    db = database.get_db()
    b = await db.system_banners.find_one({"banner_id": banner_id}, {"_id": 0, "persistent_display": 1})
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")
    if b.get("persistent_display"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This banner cannot be dismissed")
    now = datetime.now(timezone.utc)
    await db.system_banner_dismissals.update_one(
        {"portal_user_id": user["portal_user_id"], "banner_id": banner_id},
        {"$set": {"dismissed_at": now}},
        upsert=True,
    )
    return {"ok": True}
