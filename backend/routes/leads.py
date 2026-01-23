"""
Lead Management API Routes

Public endpoints for lead capture.
Admin endpoints for lead management.

All actions are audit-logged.
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from middleware import admin_route_guard, client_route_guard
from database import database
from services.lead_service import LeadService, AbandonedIntakeService
from services.lead_followup_service import LeadFollowUpService
from services.lead_ai_service import LeadAISummaryService
from services.lead_models import (
    LeadSourcePlatform,
    LeadServiceInterest,
    LeadIntentScore,
    LeadStage,
    LeadStatus,
    LeadCreateRequest,
    LeadUpdateRequest,
)
import logging

logger = logging.getLogger(__name__)

# Routers
public_router = APIRouter(prefix="/api/leads", tags=["leads-public"])
admin_router = APIRouter(prefix="/api/admin/leads", tags=["admin-leads"])


# ============================================================================
# PUBLIC ENDPOINTS - Lead Capture
# ============================================================================

class ChatbotLeadCaptureRequest(BaseModel):
    """Request from chatbot to capture a lead."""
    name: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    company_name: Optional[str] = None
    service_interest: Optional[str] = None
    message: Optional[str] = None
    conversation_id: Optional[str] = None
    marketing_consent: bool = False
    # UTM tracking (from frontend)
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    referrer_url: Optional[str] = None


class ContactFormLeadRequest(BaseModel):
    """Request from website contact form."""
    name: str = Field(..., min_length=2)
    email: EmailStr
    phone: Optional[str] = None
    company_name: Optional[str] = None
    service_interest: Optional[str] = None
    message: str = Field(..., min_length=10)
    marketing_consent: bool = False
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None


class DocumentServiceLeadRequest(BaseModel):
    """Request from document service enquiry."""
    name: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    service_code: str  # e.g., TENANCY_PACK, EPC_CERT
    property_address: Optional[str] = None
    message: Optional[str] = None
    marketing_consent: bool = False


@public_router.post("/capture/chatbot")
async def capture_chatbot_lead(
    request: ChatbotLeadCaptureRequest,
    req: Request,
):
    """
    Capture a lead from the website chatbot.
    Creates lead and optionally starts follow-up sequence.
    """
    # Map service interest
    service_map = {
        "cvp": LeadServiceInterest.CVP,
        "compliance vault pro": LeadServiceInterest.CVP,
        "document packs": LeadServiceInterest.DOCUMENT_PACKS,
        "documents": LeadServiceInterest.DOCUMENT_PACKS,
        "automation": LeadServiceInterest.AUTOMATION,
        "market research": LeadServiceInterest.MARKET_RESEARCH,
    }
    
    service_interest = LeadServiceInterest.UNKNOWN
    if request.service_interest:
        service_interest = service_map.get(
            request.service_interest.lower(),
            LeadServiceInterest.UNKNOWN
        )
    
    # Create lead
    lead_request = LeadCreateRequest(
        source_platform=LeadSourcePlatform.WEB_CHAT,
        service_interest=service_interest,
        name=request.name,
        email=request.email,
        phone=request.phone,
        company_name=request.company_name,
        message_summary=request.message,
        conversation_id=request.conversation_id,
        marketing_consent=request.marketing_consent,
        utm_source=request.utm_source,
        utm_medium=request.utm_medium,
        utm_campaign=request.utm_campaign,
        utm_content=request.utm_content,
        utm_term=request.utm_term,
        referrer_url=request.referrer_url,
    )
    
    lead = await LeadService.create_lead(
        request=lead_request,
        actor_id="chatbot",
        actor_type="system",
        ip_address=req.client.host if req.client else None,
    )
    
    # Send acknowledgement email (transactional, not marketing)
    if lead.get("email") and not lead.get("is_duplicate"):
        await LeadFollowUpService.send_acknowledgement(lead)
    
    # Start follow-up sequence if consent given
    if request.marketing_consent and not lead.get("is_duplicate"):
        await LeadFollowUpService.start_followup_sequence(lead["lead_id"])
    
    return {
        "success": True,
        "lead_id": lead["lead_id"],
        "is_duplicate": lead.get("is_duplicate", False),
        "message": "Thank you! We've received your enquiry.",
    }


@public_router.post("/capture/contact-form")
async def capture_contact_form_lead(
    request: ContactFormLeadRequest,
    req: Request,
):
    """Capture a lead from the website contact form."""
    lead_request = LeadCreateRequest(
        source_platform=LeadSourcePlatform.CONTACT_FORM,
        service_interest=LeadServiceInterest.UNKNOWN,
        name=request.name,
        email=request.email,
        phone=request.phone,
        company_name=request.company_name,
        message_summary=request.message,
        marketing_consent=request.marketing_consent,
        utm_source=request.utm_source,
        utm_medium=request.utm_medium,
        utm_campaign=request.utm_campaign,
    )
    
    lead = await LeadService.create_lead(
        request=lead_request,
        actor_id="contact_form",
        actor_type="system",
        ip_address=req.client.host if req.client else None,
    )
    
    # Send acknowledgement
    if lead.get("email") and not lead.get("is_duplicate"):
        await LeadFollowUpService.send_acknowledgement(lead)
    
    # Start follow-up if consent
    if request.marketing_consent and not lead.get("is_duplicate"):
        await LeadFollowUpService.start_followup_sequence(lead["lead_id"])
    
    return {
        "success": True,
        "lead_id": lead["lead_id"],
        "message": "Thank you! We'll be in touch shortly.",
    }


@public_router.post("/capture/document-service")
async def capture_document_service_lead(
    request: DocumentServiceLeadRequest,
    req: Request,
):
    """Capture a lead from document service enquiry."""
    lead_request = LeadCreateRequest(
        source_platform=LeadSourcePlatform.DOCUMENT_SERVICES,
        service_interest=LeadServiceInterest.DOCUMENT_PACKS,
        name=request.name,
        email=request.email,
        phone=request.phone,
        message_summary=f"Service: {request.service_code}. Property: {request.property_address or 'Not specified'}. {request.message or ''}",
        marketing_consent=request.marketing_consent,
        source_metadata={
            "service_code": request.service_code,
            "property_address": request.property_address,
        },
    )
    
    lead = await LeadService.create_lead(
        request=lead_request,
        actor_id="document_service",
        actor_type="system",
        ip_address=req.client.host if req.client else None,
    )
    
    # Send acknowledgement
    if lead.get("email") and not lead.get("is_duplicate"):
        await LeadFollowUpService.send_acknowledgement(lead)
    
    return {
        "success": True,
        "lead_id": lead["lead_id"],
        "message": "Thank you! We'll process your document request shortly.",
    }


@public_router.post("/capture/whatsapp")
async def capture_whatsapp_lead(
    request: Request,
    conversation_id: Optional[str] = None,
    email: Optional[str] = None,
    name: Optional[str] = None,
    message_summary: Optional[str] = None,
):
    """
    Capture a lead when user clicks WhatsApp handoff.
    Called by the support chat widget.
    """
    # Only create lead if we have email
    if not email:
        return {"success": False, "message": "Email required for lead capture"}
    
    lead_request = LeadCreateRequest(
        source_platform=LeadSourcePlatform.WHATSAPP,
        service_interest=LeadServiceInterest.UNKNOWN,
        name=name,
        email=email,
        conversation_id=conversation_id,
        message_summary=message_summary or "WhatsApp handoff request",
        marketing_consent=False,  # Don't auto-consent for WhatsApp leads
    )
    
    lead = await LeadService.create_lead(
        request=lead_request,
        actor_id="whatsapp_handoff",
        actor_type="system",
        ip_address=request.client.host if request.client else None,
    )
    
    return {
        "success": True,
        "lead_id": lead["lead_id"],
        "is_duplicate": lead.get("is_duplicate", False),
    }


@public_router.post("/unsubscribe/{lead_id}")
async def unsubscribe_lead(lead_id: str):
    """
    Unsubscribe a lead from marketing emails.
    Public endpoint (uses lead_id as token).
    """
    db = database.get_db()
    
    result = await db["leads"].update_one(
        {"lead_id": lead_id},
        {
            "$set": {
                "marketing_consent": False,
                "followup_status": "OPTED_OUT",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    await LeadService.log_audit(
        event="MARKETING_CONSENT_UPDATED",
        lead_id=lead_id,
        actor_id="self",
        actor_type="lead",
        details={"marketing_consent": False, "source": "unsubscribe_link"},
    )
    
    return {
        "success": True,
        "message": "You have been unsubscribed from marketing emails.",
    }


# ============================================================================
# ADMIN ENDPOINTS - Lead Management
# ============================================================================

@admin_router.get("")
async def list_leads(
    source_platform: Optional[str] = None,
    service_interest: Optional[str] = None,
    stage: Optional[str] = None,
    intent_score: Optional[str] = None,
    status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    search: Optional[str] = None,
    sla_breach_only: bool = False,
    page: int = Query(1, ge=1),
    limit: int = Query(50, le=200),
    current_user: dict = Depends(admin_route_guard),
):
    """List all leads with filters and pagination."""
    leads, total = await LeadService.list_leads(
        source_platform=source_platform,
        service_interest=service_interest,
        stage=stage,
        intent_score=intent_score,
        status=status,
        assigned_to=assigned_to,
        search=search,
        sla_breach_only=sla_breach_only,
        page=page,
        limit=limit,
    )
    
    # Get stats
    stats = await LeadService.get_stats()
    
    return {
        "leads": leads,
        "total": total,
        "page": page,
        "limit": limit,
        "stats": stats,
    }


@admin_router.get("/stats")
async def get_lead_stats(
    current_user: dict = Depends(admin_route_guard),
):
    """Get lead statistics and metrics."""
    return await LeadService.get_stats()


@admin_router.get("/sources")
async def get_lead_sources(
    current_user: dict = Depends(admin_route_guard),
):
    """Get available lead sources and service interests."""
    return {
        "source_platforms": [s.value for s in LeadSourcePlatform],
        "service_interests": [s.value for s in LeadServiceInterest],
        "intent_scores": [s.value for s in LeadIntentScore],
        "stages": [s.value for s in LeadStage],
        "statuses": [s.value for s in LeadStatus],
    }


@admin_router.get("/{lead_id}")
async def get_lead(
    lead_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Get a single lead with full details."""
    lead = await LeadService.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Get audit log
    audit_log = await LeadService.get_audit_log(lead_id, limit=20)
    
    # Get contacts
    db = database.get_db()
    contacts = await db["lead_contacts"].find(
        {"lead_id": lead_id},
        {"_id": 0}
    ).sort("contacted_at", -1).to_list(length=20)
    
    # Get conversation transcript if available
    transcript = None
    if lead.get("conversation_id"):
        conversation = await db["support_conversations"].find_one(
            {"conversation_id": lead["conversation_id"]},
            {"_id": 0}
        )
        if conversation:
            messages = await db["conversation_messages"].find(
                {"conversation_id": lead["conversation_id"]},
                {"_id": 0}
            ).sort("timestamp", 1).to_list(length=100)
            transcript = messages
    
    return {
        **lead,
        "audit_log": audit_log,
        "contacts": contacts,
        "transcript": transcript,
    }


@admin_router.post("")
async def create_lead_manual(
    source_platform: str = "ADMIN",
    service_interest: str = "UNKNOWN",
    name: Optional[str] = None,
    email: Optional[EmailStr] = None,
    phone: Optional[str] = None,
    company_name: Optional[str] = None,
    message_summary: Optional[str] = None,
    intent_score: Optional[str] = None,
    admin_notes: Optional[str] = None,
    current_user: dict = Depends(admin_route_guard),
):
    """Create a lead manually (admin action)."""
    lead_request = LeadCreateRequest(
        source_platform=LeadSourcePlatform(source_platform),
        service_interest=LeadServiceInterest(service_interest),
        name=name,
        email=email,
        phone=phone,
        company_name=company_name,
        message_summary=message_summary,
        intent_score=LeadIntentScore(intent_score) if intent_score else None,
        admin_notes=admin_notes,
        marketing_consent=False,  # Manual leads don't auto-consent
    )
    
    lead = await LeadService.create_lead(
        request=lead_request,
        actor_id=current_user.get("email"),
        actor_type="admin",
    )
    
    return {
        "success": True,
        "lead_id": lead["lead_id"],
        "lead": lead,
    }


@admin_router.put("/{lead_id}")
async def update_lead(
    lead_id: str,
    name: Optional[str] = None,
    email: Optional[EmailStr] = None,
    phone: Optional[str] = None,
    company_name: Optional[str] = None,
    service_interest: Optional[str] = None,
    message_summary: Optional[str] = None,
    intent_score: Optional[str] = None,
    stage: Optional[str] = None,
    admin_notes: Optional[str] = None,
    current_user: dict = Depends(admin_route_guard),
):
    """Update a lead."""
    request = LeadUpdateRequest(
        name=name,
        email=email,
        phone=phone,
        company_name=company_name,
        service_interest=LeadServiceInterest(service_interest) if service_interest else None,
        message_summary=message_summary,
        intent_score=LeadIntentScore(intent_score) if intent_score else None,
        stage=LeadStage(stage) if stage else None,
        admin_notes=admin_notes,
    )
    
    lead = await LeadService.update_lead(
        lead_id=lead_id,
        request=request,
        actor_id=current_user.get("email"),
        actor_type="admin",
    )
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return {"success": True, "lead": lead}


@admin_router.post("/{lead_id}/assign")
async def assign_lead(
    lead_id: str,
    admin_id: str,
    notify_admin: bool = True,
    current_user: dict = Depends(admin_route_guard),
):
    """Assign a lead to an admin."""
    lead = await LeadService.assign_lead(
        lead_id=lead_id,
        admin_id=admin_id,
        assigned_by=current_user.get("email"),
        notify_admin=notify_admin,
    )
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return {"success": True, "lead": lead}


@admin_router.post("/{lead_id}/contact")
async def log_lead_contact(
    lead_id: str,
    contact_method: str,  # email, phone, whatsapp, in_person
    notes: Optional[str] = None,
    outcome: Optional[str] = None,
    current_user: dict = Depends(admin_route_guard),
):
    """Log a contact attempt with a lead."""
    success = await LeadService.log_contact(
        lead_id=lead_id,
        contact_method=contact_method,
        actor_id=current_user.get("email"),
        notes=notes,
        outcome=outcome,
    )
    
    return {"success": success}


@admin_router.post("/{lead_id}/convert")
async def convert_lead(
    lead_id: str,
    client_id: str,
    conversion_notes: Optional[str] = None,
    current_user: dict = Depends(admin_route_guard),
):
    """Convert a lead to a client."""
    lead = await LeadService.convert_lead(
        lead_id=lead_id,
        client_id=client_id,
        actor_id=current_user.get("email"),
        conversion_notes=conversion_notes,
    )
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return {"success": True, "lead": lead}


@admin_router.post("/{lead_id}/mark-lost")
async def mark_lead_lost(
    lead_id: str,
    reason: str,
    competitor: Optional[str] = None,
    current_user: dict = Depends(admin_route_guard),
):
    """Mark a lead as lost."""
    lead = await LeadService.mark_lost(
        lead_id=lead_id,
        reason=reason,
        actor_id=current_user.get("email"),
        competitor=competitor,
    )
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    return {"success": True, "lead": lead}


@admin_router.post("/{lead_id}/merge/{secondary_lead_id}")
async def merge_leads(
    lead_id: str,
    secondary_lead_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Merge secondary lead into primary lead."""
    lead = await LeadService.merge_leads(
        primary_lead_id=lead_id,
        secondary_lead_id=secondary_lead_id,
        actor_id=current_user.get("email"),
    )
    
    if not lead:
        raise HTTPException(status_code=404, detail="One or both leads not found")
    
    return {"success": True, "lead": lead}


@admin_router.post("/{lead_id}/generate-summary")
async def generate_lead_summary(
    lead_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Generate or regenerate AI summary for a lead."""
    summary = await LeadAISummaryService.regenerate_summary(
        lead_id=lead_id,
        actor_id=current_user.get("email"),
    )
    
    if not summary:
        raise HTTPException(status_code=500, detail="Failed to generate summary")
    
    return {"success": True, "summary": summary}


@admin_router.post("/{lead_id}/send-message")
async def send_lead_message(
    lead_id: str,
    subject: str,
    message: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Send a manual message to a lead (via Postmark)."""
    lead = await LeadService.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    if not lead.get("email"):
        raise HTTPException(status_code=400, detail="Lead has no email address")
    
    # Send email via Postmark
    import os
    from postmarker.core import PostmarkClient
    
    POSTMARK_SERVER_TOKEN = os.environ.get("POSTMARK_SERVER_TOKEN")
    SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "info@pleerityenterprise.co.uk")
    
    if not POSTMARK_SERVER_TOKEN:
        raise HTTPException(status_code=500, detail="Email service not configured")
    
    try:
        client = PostmarkClient(server_token=POSTMARK_SERVER_TOKEN)
        client.emails.send(
            From=SUPPORT_EMAIL,
            To=lead["email"],
            Subject=subject,
            TextBody=message,
            Tag="admin_manual_message",
            Metadata={
                "lead_id": lead_id,
                "sent_by": current_user.get("email"),
            },
        )
        
        # Log contact
        await LeadService.log_contact(
            lead_id=lead_id,
            contact_method="email",
            actor_id=current_user.get("email"),
            notes=f"Subject: {subject}",
            outcome="sent",
        )
        
        return {"success": True, "message": "Email sent"}
        
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


@admin_router.get("/{lead_id}/audit-log")
async def get_lead_audit_log(
    lead_id: str,
    limit: int = Query(50, le=200),
    current_user: dict = Depends(admin_route_guard),
):
    """Get audit log for a lead."""
    return await LeadService.get_audit_log(lead_id, limit=limit)


# ============================================================================
# ADMIN - IMPORT PLACEHOLDER
# ============================================================================

@admin_router.post("/import/csv")
async def import_leads_csv(
    current_user: dict = Depends(admin_route_guard),
):
    """
    Import leads from CSV (placeholder).
    Feature flagged for later implementation.
    """
    return {
        "success": False,
        "message": "CSV import feature coming soon",
        "feature_flag": "LEAD_IMPORT_CSV",
    }
