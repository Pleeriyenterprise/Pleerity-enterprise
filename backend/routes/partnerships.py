"""Partnership Enquiry Routes - Public submission and Admin management"""
from fastapi import APIRouter, HTTPException, Depends, Request
from database import database
from models.partnership import PartnershipEnquiry, PartnershipStatus
from models import AuditAction
from utils.audit import create_audit_log
from utils.submission_utils import (
    check_rate_limit,
    sanitize_html,
    is_website_honeypot_filled,
    compute_spam_score,
    normalize_email,
    MAX_FIELD_LENGTH,
    MAX_NAME_LENGTH,
    MAX_PHONE_LENGTH,
    MAX_ORG_LENGTH,
    SPAM_THRESHOLD,
)
from middleware import admin_route_guard
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from pydantic import BaseModel
import logging
import os

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
    privacy_accepted: bool = False
    website: Optional[str] = None
    honeypot: Optional[str] = None


class StatusUpdateRequest(BaseModel):
    status: PartnershipStatus
    admin_notes: Optional[str] = None
    tags: Optional[List[str]] = None


@router.post("/submit")
async def submit_partnership_enquiry(data: PartnershipEnquiryRequest, request: Request):
    """Partnership submit. Requires privacy_accepted. Dedupes by (type+email) 24h with duplicate_ping. Spam score => status SPAM when >=50."""
    if not data.privacy_accepted:
        raise HTTPException(status_code=422, detail="You must accept the privacy policy to submit.")

    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip, "partnership"):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment and try again.")

    honeypot_filled = is_website_honeypot_filled(data.website, data.honeypot)
    safe_notes = sanitize_html(data.additional_notes, max_len=MAX_FIELD_LENGTH) if data.additional_notes else None
    msg_for_spam = safe_notes or data.problem_solved or ""
    spam_score, _ = compute_spam_score(msg_for_spam, honeypot_filled)
    status = "SPAM" if spam_score >= SPAM_THRESHOLD else "NEW"

    db = database.get_db()
    now = datetime.now(timezone.utc)
    email_norm = normalize_email(data.work_email)
    since_24h = now - timedelta(hours=24)
    since_24h_str = since_24h.isoformat()
    existing = await db.partnership_enquiries.find_one(
        {"email_normalized": email_norm, "created_at": {"$gte": since_24h_str}},
        {"enquiry_id": 1},
    )
    if existing:
        await db.partnership_enquiries.update_one(
            {"enquiry_id": existing["enquiry_id"]},
            {
                "$set": {"last_activity_at": now, "updated_at": now},
                "$push": {"audit": {"at": now.isoformat(), "by": "system", "action": "duplicate_ping"}},
            },
        )
        logger.info("Partnership duplicate within 24h, updated duplicate_ping: %s", existing["enquiry_id"])
        return {
            "ok": True,
            "submission_id": existing["enquiry_id"],
            "message": "Thank you. Your partnership enquiry has been received. If suitable, we will contact you.",
        }

    payload = {k: v for k, v in data.dict().items() if k not in ("website", "honeypot", "privacy_accepted")}
    if safe_notes is not None:
        payload["additional_notes"] = safe_notes
    payload["first_name"] = (payload.get("first_name") or "")[:MAX_NAME_LENGTH]
    payload["last_name"] = (payload.get("last_name") or "")[:MAX_NAME_LENGTH]
    if payload.get("phone"):
        payload["phone"] = (payload["phone"] or "")[:MAX_PHONE_LENGTH]
    payload["company_name"] = (payload.get("company_name") or "")[:MAX_ORG_LENGTH]

    enquiry = PartnershipEnquiry(**payload)
    enquiry_doc = enquiry.dict()
    for key in ["created_at", "updated_at", "ack_email_sent_at"]:
        if enquiry_doc.get(key):
            val = enquiry_doc[key]
            enquiry_doc[key] = val.isoformat() if hasattr(val, "isoformat") else val
    enquiry_doc["email_normalized"] = email_norm
    enquiry_doc["status"] = status
    enquiry_doc["spam_score"] = spam_score
    enquiry_doc["last_activity_at"] = now
    enquiry_doc["source_ip"] = client_ip
    enquiry_doc["user_agent"] = (request.headers.get("user-agent") or "")[:500]
    if "audit" not in enquiry_doc or not enquiry_doc.get("audit"):
        enquiry_doc["audit"] = [{"at": now.isoformat(), "by": "system", "action": "created"}]

    await db.partnership_enquiries.insert_one(enquiry_doc)

    if status == "NEW":
        try:
            from utils.submission_utils import notify_admin_new_submission
            summary = f"{enquiry.company_name} – {enquiry.first_name} {enquiry.last_name} &lt;{enquiry.work_email}&gt;"
            await notify_admin_new_submission("partnership", enquiry.enquiry_id, summary)
        except Exception:
            pass

    # Send acknowledgement email only if explicitly enabled (default off)
    send_ack = os.getenv("PARTNERSHIP_SEND_ACK_EMAIL", "false").strip().lower() == "true"
    email_sent = False
    if send_ack:
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
    
    logger.info("Partnership enquiry submitted: %s (%s)", enquiry.company_name, enquiry.work_email)

    return {
        "ok": True,
        "submission_id": enquiry.enquiry_id,
        "message": "Thank you. Your partnership enquiry has been received. If suitable, we will contact you.",
    }


async def send_partnership_ack_email(enquiry: PartnershipEnquiry) -> bool:
    """Send partnership acknowledgement email via NotificationOrchestrator."""
    try:
        from services.notification_orchestrator import notification_orchestrator
        subject = "Partnership Enquiry Received – Pleerity Enterprise Ltd"
        message = (
            f"<p>Hello {enquiry.first_name},</p>"
            "<p>Thank you for submitting a partnership enquiry to Pleerity Enterprise Ltd.</p>"
            "<p>We have received your information and your proposal is now under initial review. "
            "All partnership enquiries are assessed based on strategic alignment, operational capability, and regulatory considerations.</p>"
            "<p>If your proposal is suitable for further discussion, a member of our team will contact you. "
            "Please note that submitting an enquiry does not guarantee acceptance into a partnership.</p>"
            "<p>No further action is required from you at this stage.</p>"
            "<p>Kind regards,<br><strong>Pleerity Enterprise Ltd</strong><br>AI-Driven Solutions & Compliance</p>"
        )
        result = await notification_orchestrator.send(
            template_key="PARTNERSHIP_ACK",
            client_id=None,
            context={"recipient": enquiry.work_email, "subject": subject, "message": message},
            idempotency_key=f"{enquiry.enquiry_id}_PARTNERSHIP_ACK",
            event_type="partnership_enquiry_ack",
        )
        if result.outcome in ("sent", "duplicate_ignored"):
            # Log in audit
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role="SYSTEM",
                metadata={
                    "action_type": "PARTNERSHIP_ENQUIRY_ACK_SENT",
                    "enquiry_id": enquiry.enquiry_id,
                    "recipient_email": enquiry.work_email,
                    "message_id": result.message_id,
                }
            )
            logger.info(f"Partnership ack email sent to {enquiry.work_email}")
            return True
        logger.warning("Partnership ack email not sent: %s", result.outcome)
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
