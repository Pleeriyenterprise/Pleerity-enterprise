"""ClearForm Audit Log Routes

API endpoints for viewing audit logs and activity history.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from datetime import datetime

from clearform.routes.auth import get_current_clearform_user
from clearform.services.audit_service import audit_service
from clearform.services.organization_service import organization_service
from clearform.models.audit import AuditAction, AuditSeverity

router = APIRouter(prefix="/api/clearform/audit", tags=["ClearForm Audit"])


# ============================================================================
# User Audit Logs
# ============================================================================

@router.get("/me")
async def get_my_audit_logs(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    action: Optional[str] = None,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get audit logs for the current user."""
    action_filter = None
    if action:
        try:
            action_filter = AuditAction(action)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action: {action}"
            )
    
    logs = await audit_service.get_user_audit_logs(
        user_id=current_user["user_id"],
        limit=limit,
        offset=offset,
        action=action_filter,
    )
    
    return {
        "success": True,
        "logs": logs,
        "count": len(logs),
    }


@router.get("/me/activity")
async def get_my_recent_activity(
    limit: int = Query(20, le=50),
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get recent activity for dashboard."""
    activity = await audit_service.get_recent_activity(
        user_id=current_user["user_id"],
        limit=limit,
    )
    
    return {
        "success": True,
        "activity": activity,
    }


@router.get("/me/stats")
async def get_my_audit_stats(
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get audit statistics for the current user."""
    counts = await audit_service.count_by_action(
        user_id=current_user["user_id"],
    )
    
    return {
        "success": True,
        "stats": counts,
    }


# ============================================================================
# Organization Audit Logs
# ============================================================================

@router.get("/org/{org_id}")
async def get_org_audit_logs(
    org_id: str,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    action: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get audit logs for an organization. Requires admin/owner access."""
    # Verify admin/owner access
    member = await organization_service.get_member(org_id, current_user["user_id"])
    if not member or member.get("role") not in ["OWNER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to view organization audit logs"
        )
    
    action_filter = None
    if action:
        try:
            action_filter = AuditAction(action)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action: {action}"
            )
    
    logs = await audit_service.get_org_audit_logs(
        org_id=org_id,
        limit=limit,
        offset=offset,
        action=action_filter,
        start_date=start_date,
        end_date=end_date,
    )
    
    return {
        "success": True,
        "logs": logs,
        "count": len(logs),
    }


@router.get("/org/{org_id}/activity")
async def get_org_recent_activity(
    org_id: str,
    limit: int = Query(50, le=100),
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get recent activity for organization dashboard."""
    # Verify membership
    member = await organization_service.get_member(org_id, current_user["user_id"])
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization"
        )
    
    activity = await audit_service.get_recent_activity(
        org_id=org_id,
        limit=limit,
    )
    
    return {
        "success": True,
        "activity": activity,
    }


@router.get("/org/{org_id}/stats")
async def get_org_audit_stats(
    org_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get audit statistics for an organization."""
    # Verify admin/owner access
    member = await organization_service.get_member(org_id, current_user["user_id"])
    if not member or member.get("role") not in ["OWNER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    counts = await audit_service.count_by_action(
        org_id=org_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    return {
        "success": True,
        "stats": counts,
    }


# ============================================================================
# Document Audit Trail
# ============================================================================

@router.get("/document/{document_id}")
async def get_document_audit_trail(
    document_id: str,
    limit: int = Query(50, le=100),
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get audit trail for a specific document."""
    # TODO: Verify document ownership/access
    
    trail = await audit_service.get_document_audit_trail(
        document_id=document_id,
        limit=limit,
    )
    
    return {
        "success": True,
        "trail": trail,
    }


# ============================================================================
# Audit Action Reference
# ============================================================================

@router.get("/actions")
async def list_audit_actions(
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get list of all audit action types."""
    actions = [
        {
            "value": action.value,
            "category": action.value.split("_")[0] if "_" in action.value else "OTHER",
        }
        for action in AuditAction
    ]
    
    return {
        "success": True,
        "actions": actions,
    }


@router.get("/severities")
async def list_audit_severities(
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get list of all audit severity levels."""
    severities = [severity.value for severity in AuditSeverity]
    
    return {
        "success": True,
        "severities": severities,
    }
