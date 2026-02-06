"""
Talent Pool Routes - Public submission and Admin management
Handles career applications and talent pool management
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from database import database
from models.talent_pool import TalentPoolSubmission, TalentPoolStatus
from models import AuditAction
from utils.audit import create_audit_log
from middleware import admin_route_guard
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/talent-pool", tags=["talent-pool"])


class TalentPoolSubmissionRequest(BaseModel):
    full_name: str
    email: str
    country: str
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    interest_areas: List[str]
    other_interest_text: Optional[str] = None
    professional_summary: str
    years_experience: str
    skills_tools: List[str]
    other_skills_text: Optional[str] = None
    availability: str
    work_style: List[str]
    cv_filename: Optional[str] = None
    consent_accepted: bool


class StatusUpdateRequest(BaseModel):
    status: TalentPoolStatus
    admin_notes: Optional[str] = None
    tags: Optional[List[str]] = None


@router.post("/submit")
async def submit_talent_pool(data: TalentPoolSubmissionRequest):
    """Public endpoint for submitting talent pool application."""
    db = database.get_db()
    
    # Check for duplicate email
    existing = await db.talent_pool.find_one({"email": data.email}, {"_id": 0})
    if existing:
        raise HTTPException(
            status_code=400,
            detail="An application with this email already exists"
        )
    
    # Create submission
    submission = TalentPoolSubmission(**data.dict())
    
    submission_doc = submission.dict()
    # Convert datetime fields
    for key in ['created_at', 'updated_at']:
        if submission_doc.get(key):
            submission_doc[key] = submission_doc[key].isoformat() if hasattr(submission_doc[key], 'isoformat') else submission_doc[key]
    
    await db.talent_pool.insert_one(submission_doc)
    
    # Audit log
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role="PUBLIC",
        metadata={
            "action_type": "TALENT_POOL_SUBMITTED",
            "submission_id": submission.submission_id,
            "email": submission.email,
            "interest_areas": submission.interest_areas,
        }
    )
    
    logger.info(f"New talent pool submission: {submission.email}")
    
    return {
        "success": True,
        "submission_id": submission.submission_id,
        "message": "Thank you. Your details have been added to our Talent Pool."
    }


# ============================================================================
# ADMIN ENDPOINTS (ROLE_ADMIN only)
# ============================================================================

@router.get("/admin/list", dependencies=[Depends(admin_route_guard)])
async def list_talent_pool(
    status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(admin_route_guard)
):
    """List all talent pool submissions with filters."""
    db = database.get_db()
    
    query = {}
    
    if status:
        query["status"] = status
    
    if search:
        query["$or"] = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
        ]
    
    submissions = await db.talent_pool.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).to_list(1000)
    
    return submissions


@router.get("/admin/{submission_id}", dependencies=[Depends(admin_route_guard)])
async def get_talent_pool_submission(
    submission_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Get detailed talent pool submission."""
    db = database.get_db()
    
    submission = await db.talent_pool.find_one(
        {"submission_id": submission_id},
        {"_id": 0}
    )
    
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    return submission


@router.put("/admin/{submission_id}", dependencies=[Depends(admin_route_guard)])
async def update_talent_pool_status(
    submission_id: str,
    data: StatusUpdateRequest,
    current_user: dict = Depends(admin_route_guard)
):
    """Update talent pool submission status and notes."""
    db = database.get_db()
    
    # Get current submission for audit
    current = await db.talent_pool.find_one(
        {"submission_id": submission_id},
        {"_id": 0}
    )
    
    if not current:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Update fields
    update_fields = {
        "status": data.status.value,
        "updated_at": datetime.now(timezone.utc),
        "updated_by": current_user.get("email")
    }
    
    if data.admin_notes is not None:
        update_fields["admin_notes"] = data.admin_notes
    
    if data.tags is not None:
        update_fields["tags"] = data.tags
    
    await db.talent_pool.update_one(
        {"submission_id": submission_id},
        {"$set": update_fields}
    )
    
    # Audit log
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role="ROLE_ADMIN",
        actor_id=current_user.get("user_id"),
        metadata={
            "action_type": "TALENT_POOL_UPDATED",
            "submission_id": submission_id,
            "previous_status": current.get("status"),
            "new_status": data.status.value,
            "admin_email": current_user.get("email"),
        }
    )
    
    logger.info(f"Talent pool {submission_id} updated by {current_user.get('email')}")
    
    return {
        "success": True,
        "message": "Submission updated successfully"
    }


@router.get("/admin/stats", dependencies=[Depends(admin_route_guard)])
async def get_talent_pool_stats(current_user: dict = Depends(admin_route_guard)):
    """Get talent pool statistics for admin dashboard."""
    db = database.get_db()
    
    total = await db.talent_pool.count_documents({})
    new_count = await db.talent_pool.count_documents({"status": "NEW"})
    reviewed = await db.talent_pool.count_documents({"status": "REVIEWED"})
    shortlisted = await db.talent_pool.count_documents({"status": "SHORTLISTED"})
    
    return {
        "total": total,
        "new": new_count,
        "reviewed": reviewed,
        "shortlisted": shortlisted,
        "archived": await db.talent_pool.count_documents({"status": "ARCHIVED"})
    }
