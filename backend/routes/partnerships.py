"""Partnership Enquiry Routes - Public submission and Admin management"""
from fastapi import APIRouter, HTTPException, Depends
from database import database
from models.partnership import PartnershipEnquiry, PartnershipStatus
from models import AuditAction
from utils.audit import create_audit_log
from middleware import admin_route_guard
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/partnerships", tags=["partnerships"])


class PartnershipEnquiryRequest(BaseModel):
    first_name: str
    last_name: str
    role_title: str
    work_email: str
    phone: Optional[str] = None
    partnership_type: str
    partnership_type_other: Optional[str] = None
    company_name: str
    country_region: str
    website_url: str
    organisation_type: str
    org_description: str
    primary_services: str
    typical_client_profile: Optional[str] = None
    collaboration_type: str
    collaboration_other: Optional[str] = None
    problem_solved: str
    works_with_partners: bool
    org_size: str
    gdpr_compliant_status: str
    timeline: str
    additional_notes: Optional[str] = None
    declaration_accepted: bool


class StatusUpdateRequest(BaseModel):
    status: PartnershipStatus
    admin_notes: Optional[str] = None
    tags: Optional[List[str]] = None


@router.post("/submit")
async def submit_partnership_enquiry(data: PartnershipEnquiryRequest):
    """Public endpoint for submitting partnership enquiry."""
    db = database.get_db()
    
    # Check for duplicate
    existing = await db.partnership_enquiries.find_one(
        {"work_email": data.work_email},
        {"_id": 0}
    )
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail="An enquiry with this email already exists"
        )
    
    # Create enquiry
    enquiry = PartnershipEnquiry(**data.dict())
    
    enquiry_doc = enquiry.dict()
    for key in ['created_at', 'updated_at', 'ack_email_sent_at']:
        if enquiry_doc.get(key):
            val = enquiry_doc[key]
            enquiry_doc[key] = val.isoformat() if hasattr(val, 'isoformat') else val
    
    await db.partnership_enquiries.insert_one(enquiry_doc)
    
    # Send acknowledgement email
    email_sent = await send_partnership_ack_email(enquiry)
    
    # Update record with email status
    if email_sent:
        await db.partnership_enquiries.update_one(
            {"enquiry_id": enquiry.enquiry_id},
            {"$set": {
                "ack_email_sent": True,
                "ack_email_sent_at": datetime.now(timezone.utc).isoformat()
            }}
        )
    
    # Audit log
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role="PUBLIC",
        metadata={
            "action_type": "PARTNERSHIP_ENQUIRY_SUBMITTED",
            "enquiry_id": enquiry.enquiry_id,
            "company_name": enquiry.company_name,
            "email": enquiry.work_email,
            "partnership_type": enquiry.partnership_type,
        }
    )
    
    logger.info(f"Partnership enquiry submitted: {enquiry.company_name} ({enquiry.work_email})")
    
    return {
        "success": True,
        "enquiry_id": enquiry.enquiry_id,
        "message": "Thank you. Your partnership enquiry has been received. If suitable, we will contact you."
    }


async def send_partnership_ack_email(enquiry: PartnershipEnquiry) -> bool:
    """Send partnership acknowledgement email."""
    try:
        from services.email_service import email_service
        
        subject = "Partnership Enquiry Received – Pleerity Enterprise Ltd"
        
        html_body = f"""<html><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<p>Hello {enquiry.first_name},</p>

<p>Thank you for submitting a partnership enquiry to Pleerity Enterprise Ltd.</p>

<p>We have received your information and your proposal is now under initial review. All partnership enquiries are assessed based on strategic alignment, operational capability, and regulatory considerations.</p>

<p>If your proposal is suitable for further discussion, a member of our team will contact you to explore the collaboration in more detail. Please note that submitting an enquiry does not guarantee acceptance into a partnership.</p>

<p>No further action is required from you at this stage.</p>

<p style="margin-top: 30px;">
Kind regards,<br>
<strong>Pleerity Enterprise Ltd</strong><br>
AI-Driven Solutions & Compliance
</p>

<p style="color: #666; font-size: 14px;">
📧 info@pleerityenterprise.co.uk<br>
🌐 <a href="https://pleerityenterprise.co.uk" style="color: #00B8A9;">https://pleerityenterprise.co.uk</a>
</p>
</body></html>"""
        
        text_body = f"""Hello {enquiry.first_name},

Thank you for submitting a partnership enquiry to Pleerity Enterprise Ltd.

We have received your information and your proposal is now under initial review. All partnership enquiries are assessed based on strategic alignment, operational capability, and regulatory considerations.

If your proposal is suitable for further discussion, a member of our team will contact you to explore the collaboration in more detail. Please note that submitting an enquiry does not guarantee acceptance into a partnership.

No further action is required from you at this stage.

Kind regards,
Pleerity Enterprise Ltd
AI-Driven Solutions & Compliance

info@pleerityenterprise.co.uk
https://pleerityenterprise.co.uk
"""
        
        # Send via email service
        if email_service.client:
            response = email_service.client.emails.send(
                From="info@pleerityenterprise.co.uk",
                To=enquiry.work_email,
                Subject=subject,
                HtmlBody=html_body,
                TextBody=text_body,
                Tag="partnership_ack"
            )
            
            # Log in audit
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role="SYSTEM",
                metadata={
                    "action_type": "PARTNERSHIP_ENQUIRY_ACK_SENT",
                    "enquiry_id": enquiry.enquiry_id,
                    "recipient_email": enquiry.work_email,
                    "postmark_message_id": response.get("MessageID"),
                }
            )
            
            logger.info(f"Partnership ack email sent to {enquiry.work_email}")
            return True
        else:
            logger.warning("Email service not configured - ack email not sent")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send partnership ack email: {e}")
        return False


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@router.get("/admin/list", dependencies=[Depends(admin_route_guard)])
async def list_partnership_enquiries(
    status: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(admin_route_guard)
):
    """List all partnership enquiries with filters."""
    db = database.get_db()
    
    query = {}
    if status:
        query["status"] = status
    if search:
        query["$or"] = [
            {"first_name": {"$regex": search, "$options": "i"}},
            {"last_name": {"$regex": search, "$options": "i"}},
            {"company_name": {"$regex": search, "$options": "i"}},
            {"work_email": {"$regex": search, "$options": "i"}},
        ]
    
    enquiries = await db.partnership_enquiries.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).to_list(1000)
    
    return enquiries


@router.get("/admin/{enquiry_id}", dependencies=[Depends(admin_route_guard)])
async def get_partnership_enquiry(
    enquiry_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Get detailed partnership enquiry."""
    db = database.get_db()
    
    enquiry = await db.partnership_enquiries.find_one(
        {"enquiry_id": enquiry_id},
        {"_id": 0}
    )
    
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")
    
    return enquiry


@router.put("/admin/{enquiry_id}", dependencies=[Depends(admin_route_guard)])
async def update_partnership_enquiry(
    enquiry_id: str,
    data: StatusUpdateRequest,
    current_user: dict = Depends(admin_route_guard)
):
    """Update partnership enquiry status and notes."""
    db = database.get_db()
    
    current = await db.partnership_enquiries.find_one(
        {"enquiry_id": enquiry_id},
        {"_id": 0}
    )
    
    if not current:
        raise HTTPException(status_code=404, detail="Enquiry not found")
    
    update_fields = {
        "status": data.status.value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": current_user.get("email")
    }
    
    if data.admin_notes is not None:
        update_fields["admin_notes"] = data.admin_notes
    if data.tags is not None:
        update_fields["tags"] = data.tags
    
    await db.partnership_enquiries.update_one(
        {"enquiry_id": enquiry_id},
        {"$set": update_fields}
    )
    
    # Audit log
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role="ROLE_ADMIN",
        actor_id=current_user.get("user_id"),
        metadata={
            "action_type": "PARTNERSHIP_ENQUIRY_UPDATED",
            "enquiry_id": enquiry_id,
            "previous_status": current.get("status"),
            "new_status": data.status.value,
            "admin_email": current_user.get("email"),
        }
    )
    
    logger.info(f"Partnership enquiry {enquiry_id} updated by {current_user.get('email')}")
    
    return {"success": True, "message": "Enquiry updated"}


@router.get("/admin/stats", dependencies=[Depends(admin_route_guard)])
async def get_partnership_stats(current_user: dict = Depends(admin_route_guard)):
    """Get partnership enquiry statistics."""
    db = database.get_db()
    
    total = await db.partnership_enquiries.count_documents({})
    new_count = await db.partnership_enquiries.count_documents({"status": "NEW"})
    reviewed = await db.partnership_enquiries.count_documents({"status": "REVIEWED"})
    approved = await db.partnership_enquiries.count_documents({"status": "APPROVED"})
    
    return {
        "total": total,
        "new": new_count,
        "reviewed": reviewed,
        "approved": approved,
        "rejected": await db.partnership_enquiries.count_documents({"status": "REJECTED"}),
        "archived": await db.partnership_enquiries.count_documents({"status": "ARCHIVED"})
    }
