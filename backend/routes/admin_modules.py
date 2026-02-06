"""Admin Module Routes - Contact, FAQ, Newsletter, Insights Feedback"""
from fastapi import APIRouter, HTTPException, Depends
from database import database
from models.admin_modules import ContactEnquiry, ContactEnquiryStatus, FAQItem, NewsletterSubscriber, InsightFeedback
from models import AuditAction
from utils.audit import create_audit_log
from middleware import admin_route_guard
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin-modules"])

# Contact Enquiries
class ContactEnquiryRequest(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    subject: str
    message: str

@router.post("/contact/submit")
async def submit_contact_enquiry(data: ContactEnquiryRequest):
    db = database.get_db()
    enquiry = ContactEnquiry(**data.dict())
    doc = enquiry.dict()
    for k in ['created_at','updated_at','replied_at']:
        if doc.get(k): doc[k] = doc[k].isoformat() if hasattr(doc[k],'isoformat') else doc[k]
    await db.contact_enquiries.insert_one(doc)
    return {"success": True, "enquiry_id": enquiry.enquiry_id}

@router.get("/contact/enquiries", dependencies=[Depends(admin_route_guard)])
async def list_contact_enquiries(status: Optional[str] = None, current_user: dict = Depends(admin_route_guard)):
    db = database.get_db()
    query = {"status": status} if status else {}
    return await db.contact_enquiries.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)

@router.get("/contact/enquiries/{id}", dependencies=[Depends(admin_route_guard)])
async def get_contact_enquiry(id: str, current_user: dict = Depends(admin_route_guard)):
    db = database.get_db()
    e = await db.contact_enquiries.find_one({"enquiry_id": id}, {"_id": 0})
    if not e: raise HTTPException(404, "Not found")
    return e

class ContactReplyRequest(BaseModel):
    reply_message: str
    status: str

@router.post("/contact/enquiries/{id}/reply", dependencies=[Depends(admin_route_guard)])
async def reply_contact_enquiry(id: str, data: ContactReplyRequest, current_user: dict = Depends(admin_route_guard)):
    db = database.get_db()
    await db.contact_enquiries.update_one({"enquiry_id": id}, {"$set": {
        "admin_reply": data.reply_message, "replied_at": datetime.now(timezone.utc).isoformat(),
        "replied_by": current_user.get("email"), "status": data.status, "updated_at": datetime.now(timezone.utc).isoformat()
    }})
    return {"success": True}

# FAQ Management
@router.get("/faqs")
async def list_faqs():
    db = database.get_db()
    return await db.faq_items.find({"is_active": True}, {"_id": 0}).sort("display_order", 1).to_list(1000)

@router.get("/faqs/admin", dependencies=[Depends(admin_route_guard)])
async def list_all_faqs(current_user: dict = Depends(admin_route_guard)):
    db = database.get_db()
    return await db.faq_items.find({}, {"_id": 0}).sort("display_order", 1).to_list(1000)

class FAQRequest(BaseModel):
    category: str
    question: str
    answer: str
    is_active: bool = True
    display_order: int = 0

@router.post("/faqs", dependencies=[Depends(admin_route_guard)])
async def create_faq(data: FAQRequest, current_user: dict = Depends(admin_route_guard)):
    db = database.get_db()
    faq = FAQItem(**data.dict(), updated_by=current_user.get("email"))
    doc = faq.dict()
    for k in ['created_at','updated_at']: 
        if doc.get(k): doc[k] = doc[k].isoformat() if hasattr(doc[k],'isoformat') else doc[k]
    await db.faq_items.insert_one(doc)
    return {"success": True, "faq_id": faq.faq_id}

@router.put("/faqs/{id}", dependencies=[Depends(admin_route_guard)])
async def update_faq(id: str, data: FAQRequest, current_user: dict = Depends(admin_route_guard)):
    db = database.get_db()
    await db.faq_items.update_one({"faq_id": id}, {"$set": {**data.dict(), "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": current_user.get("email")}})
    return {"success": True}

@router.delete("/faqs/{id}", dependencies=[Depends(admin_route_guard)])
async def delete_faq(id: str, current_user: dict = Depends(admin_route_guard)):
    db = database.get_db()
    await db.faq_items.delete_one({"faq_id": id})
    return {"success": True}

# Newsletter
@router.post("/newsletter/subscribe")
async def subscribe_newsletter(email: str, source: str = "website"):
    """Subscribe to newsletter and sync to Kit."""
    db = database.get_db()
    
    # Check if already exists
    existing = await db.newsletter_subscribers.find_one({"email": email}, {"_id": 0})
    if existing:
        return {"success": True, "message": "Already subscribed"}
    
    # Create subscriber
    sub = NewsletterSubscriber(email=email, source=source)
    
    # Sync to Kit
    from services.kit_integration import kit_integration
    kit_success, kit_error = await kit_integration.add_subscriber(email, source)
    
    # Update sync status
    if kit_success:
        sub.kit_sync_status = "SYNCED"
        sub.kit_synced_at = datetime.now(timezone.utc)
    else:
        sub.kit_sync_status = "FAILED"
        sub.kit_sync_error = kit_error
    
    # Save to database regardless of Kit status
    doc = sub.dict()
    for k in ['subscribed_at', 'unsubscribed_at', 'kit_synced_at']:
        if doc.get(k):
            doc[k] = doc[k].isoformat() if hasattr(doc[k], 'isoformat') else doc[k]
    
    await db.newsletter_subscribers.insert_one(doc)
    
    # Audit log
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role="PUBLIC",
        metadata={
            "action_type": "NEWSLETTER_SUBSCRIBED",
            "email": email,
            "source": source,
            "kit_sync_status": sub.kit_sync_status,
        }
    )
    
    logger.info(f"Newsletter subscription: {email} (source: {source}, Kit: {sub.kit_sync_status})")
    
    return {"success": True, "message": "Subscribed successfully"}

@router.get("/newsletter/subscribers", dependencies=[Depends(admin_route_guard)])
async def list_newsletter_subscribers(current_user: dict = Depends(admin_route_guard)):
    db = database.get_db()
    return await db.newsletter_subscribers.find({}, {"_id": 0}).sort("subscribed_at", -1).to_list(10000)

# Insights Feedback
@router.post("/feedback/submit")
async def submit_feedback(article_slug: str, article_title: str, was_helpful: bool, comment: Optional[str] = None):
    db = database.get_db()
    fb = InsightFeedback(article_slug=article_slug, article_title=article_title, was_helpful=was_helpful, comment=comment)
    doc = fb.dict()
    for k in ['created_at','updated_at']: 
        if doc.get(k): doc[k] = doc[k].isoformat() if hasattr(doc[k],'isoformat') else doc[k]
    await db.insights_feedback.insert_one(doc)
    return {"success": True}

@router.get("/feedback/list", dependencies=[Depends(admin_route_guard)])
async def list_feedback(current_user: dict = Depends(admin_route_guard)):
    db = database.get_db()
    return await db.insights_feedback.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)

class FeedbackUpdateRequest(BaseModel):
    status: str
    admin_notes: Optional[str] = None

@router.put("/feedback/{id}", dependencies=[Depends(admin_route_guard)])
async def update_feedback(id: str, data: FeedbackUpdateRequest, current_user: dict = Depends(admin_route_guard)):
    db = database.get_db()
    await db.insights_feedback.update_one({"feedback_id": id}, {"$set": {**data.dict(), "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": current_user.get("email")}})
    return {"success": True}
