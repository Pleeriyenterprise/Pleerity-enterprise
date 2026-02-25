"""
Public API Routes - NEW FILE
Handles public website submissions (contact forms, service inquiries)
NO CVP COLLECTIONS TOUCHED - Writes only to new collections
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime, timezone, timedelta
from database import database
from utils.submission_utils import (
    sanitize_html,
    check_rate_limit,
    is_website_honeypot_filled,
    is_honeypot_filled,
    compute_spam_score,
    normalize_email,
    MAX_MESSAGE_LENGTH,
    MAX_NAME_LENGTH,
    MAX_SUBJECT_LENGTH,
    MAX_PHONE_LENGTH,
    MAX_ORG_LENGTH,
    SPAM_THRESHOLD,
)
import logging
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/public", tags=["public"])


# ============================================
# MODELS
# ============================================

class ContactSubmission(BaseModel):
    full_name: str = Field(..., max_length=MAX_NAME_LENGTH)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=MAX_PHONE_LENGTH)
    company_name: Optional[str] = Field(None, max_length=MAX_ORG_LENGTH)
    contact_reason: str = Field(..., max_length=200)
    subject: str = Field(..., max_length=MAX_SUBJECT_LENGTH)
    message: str = Field(..., max_length=MAX_MESSAGE_LENGTH)
    marketing_opt_in: bool = False
    privacy_accepted: bool = False
    website: Optional[str] = None  # honeypot (hidden); if filled, mark spam
    honeypot: Optional[str] = None  # legacy honeypot field
    source_page: Optional[str] = None
    referrer: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None


class ServiceInquiry(BaseModel):
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    company_name: Optional[str] = None
    service_interest: str
    message: str
    source_page: Optional[str] = None


# ============================================
# HELPER FUNCTIONS
# ============================================

def generate_submission_id(prefix: str) -> str:
    """Generate unique submission ID"""
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"{prefix}-{short_uuid}"


# ============================================
# RATE LIMITING (delegate to submission_utils for consistency)
# ============================================

def _rate_limit_contact(ip: str) -> bool:
    return check_rate_limit(ip, "contact")


# ============================================
# ENDPOINTS
# ============================================

@router.post("/contact")
async def submit_contact_form(submission: ContactSubmission, request: Request):
    """
    Submit a contact form. Requires privacy_accepted. Dedupes by (type+email) in 24h with duplicate_ping update.
    Spam scoring: honeypot/URLs/script => status=SPAM when score>=50.
    """
    if not submission.privacy_accepted:
        raise HTTPException(status_code=422, detail="You must accept the privacy policy to submit.")

    client_ip = request.client.host if request.client else "unknown"
    if not _rate_limit_contact(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment and try again.")

    honeypot_filled = is_website_honeypot_filled(submission.website, submission.honeypot)
    message_safe = sanitize_html(submission.message)
    subject_safe = sanitize_html(submission.subject, max_len=MAX_SUBJECT_LENGTH)
    spam_score, _ = compute_spam_score(message_safe, honeypot_filled)
    status = "SPAM" if spam_score >= SPAM_THRESHOLD else "NEW"

    db = database.get_db()
    now = datetime.now(timezone.utc)
    email_norm = normalize_email(submission.email)
    since_24h = now - timedelta(hours=24)
    existing = await db.contact_submissions.find_one(
        {"email_normalized": email_norm, "created_at": {"$gte": since_24h}},
        {"submission_id": 1},
    )
    if existing:
        await db.contact_submissions.update_one(
            {"submission_id": existing["submission_id"]},
            {
                "$set": {"last_activity_at": now, "updated_at": now},
                "$push": {"audit": {"at": now.isoformat(), "by": "system", "action": "duplicate_ping"}},
            },
        )
        logger.info("Contact duplicate within 24h, updated duplicate_ping: %s", existing["submission_id"])
        return {
            "ok": True,
            "submission_id": existing["submission_id"],
            "message": "Thank you for your message. We'll be in touch within 1-2 business days.",
        }

    submission_id = generate_submission_id("CONTACT")
    source = {"page": submission.source_page, "referrer": submission.referrer, "utm": None}
    utm = {}
    for k, v in [
        ("utm_source", submission.utm_source),
        ("utm_medium", submission.utm_medium),
        ("utm_campaign", submission.utm_campaign),
        ("utm_content", submission.utm_content),
        ("utm_term", submission.utm_term),
    ]:
        if v:
            utm[k] = (v[:200] if isinstance(v, str) else v)
    if utm:
        source["utm"] = utm

    submission_doc = {
        "submission_id": submission_id,
        "email_normalized": email_norm,
        "full_name": submission.full_name[:MAX_NAME_LENGTH],
        "email": submission.email,
        "phone": (submission.phone or "")[:MAX_PHONE_LENGTH] if submission.phone else None,
        "company_name": (submission.company_name or "")[:MAX_ORG_LENGTH] if submission.company_name else None,
        "contact_reason": submission.contact_reason[:200],
        "subject": subject_safe,
        "message": message_safe,
        "status": status,
        "spam_score": spam_score,
        "last_activity_at": now,
        "admin_notes": None,
        "admin_reply": None,
        "replied_by": None,
        "replied_at": None,
        "created_at": now,
        "updated_at": now,
        "source_ip": client_ip,
        "user_agent": (request.headers.get("user-agent") or "")[:500],
        "consent": {
            "marketing_opt_in": submission.marketing_opt_in,
            "privacy_accepted": True,
        },
        "source": source,
        "notes": [],
        "audit": [{"at": now.isoformat(), "by": "system", "action": "created"}],
    }
    try:
        await db.contact_submissions.insert_one(submission_doc)
        logger.info("Contact submission created: %s (spam_score=%s)", submission_id, spam_score)
        if status == "NEW":
            from utils.submission_utils import notify_admin_new_submission
            summary = f"{submission.full_name} &lt;{submission.email}&gt; – {submission.subject}"
            await notify_admin_new_submission("contact", submission_id, summary)
        return {
            "ok": True,
            "submission_id": submission_id,
            "message": "Thank you for your message. We'll be in touch within 1-2 business days.",
        }
    except Exception as e:
        logger.error("Failed to save contact submission: %s", e)
        raise HTTPException(status_code=500, detail="Failed to submit form")


# ============================================
# PUBLIC LEAD (marketing / checklist → leads collection)
# ============================================

class LeadSubmission(BaseModel):
    name: Optional[str] = Field(None, max_length=MAX_NAME_LENGTH)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=MAX_PHONE_LENGTH)
    company_name: Optional[str] = Field(None, max_length=MAX_ORG_LENGTH)
    message_summary: Optional[str] = Field(None, max_length=MAX_MESSAGE_LENGTH)
    marketing_consent: bool = False
    privacy_accepted: bool = False
    website: Optional[str] = None
    honeypot: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    referrer_url: Optional[str] = None


@router.post("/lead")
async def submit_lead(data: LeadSubmission, request: Request):
    """Create a lead from public form. Requires privacy_accepted. Honeypot (website/honeypot) => no store."""
    if not data.privacy_accepted:
        raise HTTPException(status_code=422, detail="You must accept the privacy policy to submit.")
    if is_website_honeypot_filled(data.website, data.honeypot):
        return {"ok": True, "submission_id": "", "message": "Thank you. We'll be in touch soon."}
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip, "lead"):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment and try again.")
    from services.lead_service import LeadService
    from services.lead_models import LeadCreateRequest, LeadSourcePlatform, LeadServiceInterest
    message_safe = sanitize_html(data.message_summary or "", max_len=MAX_MESSAGE_LENGTH)
    req = LeadCreateRequest(
        source_platform=LeadSourcePlatform.CONTACT_FORM,
        service_interest=LeadServiceInterest.UNKNOWN,
        name=data.name,
        email=data.email,
        phone=data.phone,
        company_name=data.company_name,
        message_summary=message_safe or None,
        marketing_consent=data.marketing_consent,
        utm_source=data.utm_source,
        utm_medium=data.utm_medium,
        utm_campaign=data.utm_campaign,
        referrer_url=data.referrer_url,
    )
    lead = await LeadService.create_lead(req, ip_address=client_ip)
    lead_id = lead.get("lead_id") or lead.get("original_lead_id") or ""
    return {"ok": True, "submission_id": lead_id, "message": "Thank you. We'll be in touch soon."}


# ============================================
# PUBLIC TALENT (delegate to talent-pool submit)
# ============================================

@router.post("/talent")
async def submit_talent_public(request: Request):
    """Thin wrapper: forward body to talent-pool submit; returns { ok, submission_id, message }."""
    from routes.talent_pool import submit_talent_pool, TalentPoolSubmissionRequest
    body = await request.json()
    data = TalentPoolSubmissionRequest(**body)
    return await submit_talent_pool(data, request)


# ============================================
# PUBLIC PARTNERSHIP (delegate to partnerships submit)
# ============================================

@router.post("/partnership")
async def submit_partnership_public(request: Request):
    """Thin wrapper: forward body to partnerships submit; returns { ok, submission_id, message }."""
    from routes.partnerships import submit_partnership_enquiry, PartnershipEnquiryRequest
    body = await request.json()
    data = PartnershipEnquiryRequest(**body)
    return await submit_partnership_enquiry(data, request)


# ============================================
# PUBLIC TRACK (analytics_events for client-side)
# ============================================

class TrackEventBody(BaseModel):
    """Client-side analytics event (page views, CTA clicks)."""
    event_name: str = Field(..., min_length=1, max_length=64)
    page: Optional[str] = Field(None, max_length=500)
    session_id: Optional[str] = Field(None, max_length=128)
    props: Optional[dict] = None  # Flat key-value; sanitized server-side


@router.post("/track")
async def track_event(body: TrackEventBody, request: Request):
    """
    Record a client-side analytics event (page view, CTA click, etc.).
    Rate-limited; writes to analytics_events. Marketing site can call on load or interaction.
    """
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip, "track"):
        raise HTTPException(status_code=429, detail="Too many requests.")
    from services.analytics_service import log_public_track
    ok = await log_public_track(
        event_name=body.event_name,
        page=body.page,
        session_id=body.session_id,
        props=body.props,
    )
    return {"ok": ok}


@router.post("/service-inquiry")
async def submit_service_inquiry(inquiry: ServiceInquiry, request: Request):
    """
    Submit a service inquiry from the public website.
    Writes to service_inquiries collection ONLY.
    """
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip, "service-inquiry"):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment and try again.")
    
    db = database.get_db()
    
    # Create inquiry record
    inquiry_id = generate_submission_id("INQ")
    inquiry_doc = {
        "inquiry_id": inquiry_id,
        "full_name": inquiry.full_name,
        "email": inquiry.email,
        "phone": inquiry.phone,
        "company_name": inquiry.company_name,
        "service_interest": inquiry.service_interest,
        "message": inquiry.message,
        "source_page": inquiry.source_page,
        "status": "new",
        "admin_notes": None,
        "responded_by": None,
        "responded_at": None,
        "converted_to_order_id": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "source_ip": client_ip,
    }
    
    try:
        await db.service_inquiries.insert_one(inquiry_doc)
        logger.info(f"Service inquiry created: {inquiry_id}")
        
        return {
            "success": True,
            "inquiry_id": inquiry_id,
            "message": "Thank you for your inquiry. We'll be in touch soon."
        }
    except Exception as e:
        logger.error(f"Failed to save service inquiry: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit inquiry")


# ============================================
# PUBLIC INTAKE SCHEMA (published only, for marketing intake form)
# ============================================

@router.get("/intake-schema/{schema_key}")
async def get_published_intake_schema(schema_key: str):
    """
    Return the latest published intake schema for a service (schema_key = service_code).
    Marketing intake form should use this so only published changes go live.
    """
    from services.intake_schema_registry import get_service_schema, SERVICE_INTAKE_SCHEMAS
    from routes.admin_intake_schema import get_live_customizations, merge_schema_with_overrides

    if schema_key not in SERVICE_INTAKE_SCHEMAS:
        raise HTTPException(status_code=404, detail="Schema not found")
    base_schema = get_service_schema(schema_key)
    customizations = await get_live_customizations(schema_key)
    merged = merge_schema_with_overrides(base_schema, customizations)
    return merged


@router.get("/services")
async def get_services():
    """
    Get list of available services with pricing from database.
    Public endpoint - no auth required.
    Redirects to database-driven service catalogue.
    """
    from services.service_catalogue import service_catalogue
    
    services = await service_catalogue.list_services(active_only=True)
    
    # Return public-safe fields
    public_services = []
    for s in services:
        public_services.append({
            "service_code": s.service_code,
            "service_name": s.service_name,
            "description": s.description,
            "short_description": s.short_description,
            "category": s.category.value,
            "pricing_model": s.pricing_model.value,
            "price_amount": s.price_amount,
            "price_currency": s.price_currency,
            "vat_rate": s.vat_rate,
            "delivery_type": s.delivery_type.value,
            "turnaround_hours": s.estimated_turnaround_hours,
            "requires_cvp_subscription": s.requires_cvp_subscription,
            "display_order": s.display_order,
            "review_required": s.review_required,
            "documents_generated": [
                {
                    "document_code": d.document_code,
                    "document_name": d.document_name,
                    "format": d.format,
                    "is_primary": d.is_primary,
                }
                for d in s.documents_generated
            ] if s.documents_generated else [],
        })
    
    return {
        "services": public_services,
        "total": len(public_services),
    }


@router.get("/services/{service_code}")
async def get_service_detail(service_code: str):
    """
    Get detailed information about a specific service from database.
    """
    from services.service_catalogue import service_catalogue
    
    service = await service_catalogue.get_active_service(service_code)
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    return {
        "service_code": service.service_code,
        "service_name": service.service_name,
        "description": service.description,
        "short_description": service.short_description,
        "category": service.category.value,
        "pricing_model": service.pricing_model.value,
        "price_amount": service.price_amount,
        "price_currency": service.price_currency,
        "vat_rate": service.vat_rate,
        "delivery_type": service.delivery_type.value,
        "turnaround_hours": service.estimated_turnaround_hours,
        "intake_fields": [f.model_dump() for f in service.intake_fields] if service.intake_fields else [],
        "documents_generated": [
            {
                "document_code": d.document_code,
                "document_name": d.document_name,
                "format": d.format,
                "is_primary": d.is_primary,
            }
            for d in service.documents_generated
        ] if service.documents_generated else [],
        "review_required": service.review_required,
        "requires_cvp_subscription": service.requires_cvp_subscription,
    }
