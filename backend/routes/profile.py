"""User Profile Routes - Additive Enhancement
Allows clients to view and update their profile and notification preferences.
"""
from fastapi import APIRouter, HTTPException, Request, status
from database import database
from middleware import client_route_guard
from models import AuditAction, UserRole
from utils.audit import create_audit_log
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/profile", tags=["profile"])

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
                "reminder_days_before": 30,
                "quiet_hours_enabled": False,
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "08:00"
            }
        
        profile = {
            "portal_user_id": portal_user["portal_user_id"],
            "email": portal_user["auth_email"],
            "full_name": client["full_name"],
            "phone": client.get("phone"),
            "company_name": client.get("company_name"),
            "client_type": client["client_type"],
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
            if data.reminder_days_before not in [7, 14, 30, 60, 90]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="reminder_days_before must be 7, 14, 30, 60, or 90"
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
            update_fields["sms_phone_number"] = data.sms_phone_number
            update_fields["sms_phone_verified"] = False  # Reset verification on phone change
        if data.sms_urgent_alerts_only is not None:
            update_fields["sms_urgent_alerts_only"] = data.sms_urgent_alerts_only
        
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
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole(user["role"]),
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
