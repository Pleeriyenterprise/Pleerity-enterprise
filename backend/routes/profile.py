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

class UpdatePreferencesRequest(BaseModel):
    compliance_reminders: Optional[bool] = None
    monthly_digest: Optional[bool] = None
    product_announcements: Optional[bool] = None
    sms_reminders_enabled: Optional[bool] = None

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
        
        # Get preferences (NEW collection)
        preferences = await db.notification_preferences.find_one(
            {"portal_user_id": user["portal_user_id"]},
            {"_id": 0}
        )
        
        # Default preferences if not set
        if not preferences:
            preferences = {
                "compliance_reminders": True,
                "monthly_digest": True,
                "product_announcements": True,
                "sms_reminders_enabled": False,
                "sms_phone_verified": False
            }
        
        profile = {
            "portal_user_id": portal_user["portal_user_id"],
            "email": portal_user["auth_email"],
            "full_name": client["full_name"],
            "phone": client.get("phone"),
            "company_name": client.get("company_name"),
            "client_type": client["client_type"],
            "preferences": preferences
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

@router.patch("/preferences")
async def update_preferences(request: Request, data: UpdatePreferencesRequest):
    """Update notification preferences."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Get current preferences
        current = await db.notification_preferences.find_one(
            {"portal_user_id": user["portal_user_id"]},
            {"_id": 0}
        )
        
        # Build update
        update_fields = {}
        if data.compliance_reminders is not None:
            update_fields["compliance_reminders"] = data.compliance_reminders
        if data.monthly_digest is not None:
            update_fields["monthly_digest"] = data.monthly_digest
        if data.product_announcements is not None:
            update_fields["product_announcements"] = data.product_announcements
        if data.sms_reminders_enabled is not None:
            update_fields["sms_reminders_enabled"] = data.sms_reminders_enabled
        
        if not update_fields:
            return {"message": "No changes to apply"}
        
        update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Upsert preferences
        await db.notification_preferences.update_one(
            {"portal_user_id": user["portal_user_id"]},
            {"$set": update_fields},
            upsert=True
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole(user["role"]),
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            metadata={
                "action": "preferences_updated",
                "changes": update_fields
            }
        )
        
        logger.info(f"Preferences updated for user {user['portal_user_id']}")
        
        return {"message": "Preferences updated successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update preferences error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )
