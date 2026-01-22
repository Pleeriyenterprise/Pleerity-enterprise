"""
Public API Routes - NEW FILE
Handles public website submissions (contact forms, service inquiries)
NO CVP COLLECTIONS TOUCHED - Writes only to new collections
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone
from database import database
import logging
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/public", tags=["public"])


# ============================================
# MODELS
# ============================================

class ContactSubmission(BaseModel):
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    company_name: Optional[str] = None
    contact_reason: str
    subject: str
    message: str


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
# RATE LIMITING (Simple in-memory)
# ============================================

# Track submissions per IP (5 per minute)
_rate_limit_cache = {}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 5


def check_rate_limit(ip: str) -> bool:
    """Check if IP is rate limited. Returns True if allowed."""
    now = datetime.now(timezone.utc).timestamp()
    
    if ip not in _rate_limit_cache:
        _rate_limit_cache[ip] = []
    
    # Clean old entries
    _rate_limit_cache[ip] = [
        ts for ts in _rate_limit_cache[ip] 
        if now - ts < RATE_LIMIT_WINDOW
    ]
    
    if len(_rate_limit_cache[ip]) >= RATE_LIMIT_MAX:
        return False
    
    _rate_limit_cache[ip].append(now)
    return True


# ============================================
# ENDPOINTS
# ============================================

@router.post("/contact")
async def submit_contact_form(submission: ContactSubmission, request: Request):
    """
    Submit a contact form from the public website.
    Writes to contact_submissions collection ONLY.
    """
    client_ip = request.client.host if request.client else "unknown"
    
    # Rate limiting
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment and try again."
        )
    
    db = database.get_db()
    
    # Create submission record
    submission_id = generate_submission_id("CONTACT")
    submission_doc = {
        "submission_id": submission_id,
        "full_name": submission.full_name,
        "email": submission.email,
        "phone": submission.phone,
        "company_name": submission.company_name,
        "contact_reason": submission.contact_reason,
        "subject": submission.subject,
        "message": submission.message,
        "status": "new",
        "admin_notes": None,
        "responded_by": None,
        "responded_at": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "source_ip": client_ip,
    }
    
    try:
        await db.contact_submissions.insert_one(submission_doc)
        logger.info(f"Contact submission created: {submission_id}")
        
        return {
            "success": True,
            "submission_id": submission_id,
            "message": "Thank you for your message. We'll be in touch within 1-2 business days."
        }
    except Exception as e:
        logger.error(f"Failed to save contact submission: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit form")


@router.post("/service-inquiry")
async def submit_service_inquiry(inquiry: ServiceInquiry, request: Request):
    """
    Submit a service inquiry from the public website.
    Writes to service_inquiries collection ONLY.
    """
    client_ip = request.client.host if request.client else "unknown"
    
    # Rate limiting
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment and try again."
        )
    
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
    
    service = service_details.get(service_code.upper())
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    return service
