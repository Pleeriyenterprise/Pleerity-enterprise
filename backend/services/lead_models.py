"""
Lead Management Data Models

Enterprise-grade lead entity separate from Client.
Designed for scalability with social lead sources and future integrations.

Lead ≠ Client
- Lead: someone who showed intent but has not paid
- Client: someone who has completed checkout and provisioning
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class LeadSourcePlatform(str, Enum):
    """Platform where the lead originated - extensible for social integrations."""
    WEB_CHAT = "WEB_CHAT"
    WHATSAPP = "WHATSAPP"
    INTAKE_ABANDONED = "INTAKE_ABANDONED"
    DOCUMENT_SERVICES = "DOCUMENT_SERVICES"
    ADMIN = "ADMIN"
    CONTACT_FORM = "CONTACT_FORM"
    # Future social integrations (provisioned now)
    FACEBOOK = "FACEBOOK"
    INSTAGRAM = "INSTAGRAM"
    LINKEDIN = "LINKEDIN"
    EMAIL = "EMAIL"
    IMPORT = "IMPORT"
    REFERRAL = "REFERRAL"


class LeadServiceInterest(str, Enum):
    """Service the lead is interested in."""
    CVP = "CVP"  # Compliance Vault Pro
    DOCUMENT_PACKS = "DOCUMENT_PACKS"
    AUTOMATION = "AUTOMATION"  # AI Workflow Automation
    MARKET_RESEARCH = "MARKET_RESEARCH"
    COMPLIANCE_AUDITS = "COMPLIANCE_AUDITS"
    MULTIPLE = "MULTIPLE"
    UNKNOWN = "UNKNOWN"


class LeadIntentScore(str, Enum):
    """Qualification score based on engagement signals."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class LeadStage(str, Enum):
    """Sales pipeline stage."""
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    PROPOSAL_SENT = "PROPOSAL_SENT"
    NEGOTIATING = "NEGOTIATING"
    WON = "WON"  # Converted to Client
    LOST = "LOST"


class LeadStatus(str, Enum):
    """Lead status for filtering."""
    ACTIVE = "ACTIVE"
    CONVERTED = "CONVERTED"
    LOST = "LOST"
    MERGED = "MERGED"
    UNSUBSCRIBED = "UNSUBSCRIBED"


class FollowUpStatus(str, Enum):
    """Status of automated follow-up sequence."""
    PENDING = "PENDING"  # Not started
    IN_PROGRESS = "IN_PROGRESS"  # Sequence running
    COMPLETED = "COMPLETED"  # All emails sent
    STOPPED = "STOPPED"  # Manually stopped or condition met
    OPTED_OUT = "OPTED_OUT"  # Marketing consent withdrawn


# ============================================================================
# REQUEST MODELS
# ============================================================================

class LeadCreateRequest(BaseModel):
    """Request to create a lead."""
    source_platform: LeadSourcePlatform
    service_interest: LeadServiceInterest = LeadServiceInterest.UNKNOWN
    
    # Contact info
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    
    # Context
    message_summary: Optional[str] = None
    conversation_id: Optional[str] = None  # Link to support conversation
    intake_draft_id: Optional[str] = None  # Link to abandoned intake
    
    # Source metadata (for social integrations)
    source_metadata: Optional[Dict[str, Any]] = None
    
    # UTM tracking
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    referrer_url: Optional[str] = None
    
    # Consent
    marketing_consent: bool = False
    
    # Manual scoring override
    intent_score: Optional[LeadIntentScore] = None
    
    # Admin notes
    admin_notes: Optional[str] = None


class LeadUpdateRequest(BaseModel):
    """Request to update a lead."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    service_interest: Optional[LeadServiceInterest] = None
    message_summary: Optional[str] = None
    intent_score: Optional[LeadIntentScore] = None
    stage: Optional[LeadStage] = None
    assigned_to: Optional[str] = None
    admin_notes: Optional[str] = None
    marketing_consent: Optional[bool] = None


# ============================================================================
# FOLLOW-UP SEQUENCE DEFINITION
# ============================================================================

FOLLOWUP_SEQUENCE = [
    {
        "step": 1,
        "delay_hours": 1,
        "template_id": "lead_followup_1h",
        "subject": "Following up on your enquiry",
    },
    {
        "step": 2,
        "delay_hours": 24,
        "template_id": "lead_followup_24h",
        "subject": "Still deciding? Here's what you need to know",
    },
    {
        "step": 3,
        "delay_hours": 72,
        "template_id": "lead_followup_72h",
        "subject": "Final reminder: We're here to help",
    },
]

# Specific sequence for abandoned intake
ABANDONED_INTAKE_SEQUENCE = [
    {
        "step": 1,
        "delay_hours": 1,
        "template_id": "abandoned_intake_1h",
        "subject": "You started setting up Compliance Vault Pro — need help?",
    },
    {
        "step": 2,
        "delay_hours": 24,
        "template_id": "abandoned_intake_24h",
        "subject": "Most landlords finish setup in under 5 minutes",
    },
    {
        "step": 3,
        "delay_hours": 72,
        "template_id": "abandoned_intake_72h",
        "subject": "Still deciding? Here's what you get with your plan",
    },
]


# ============================================================================
# AUDIT EVENT TYPES
# ============================================================================

class LeadAuditEvent(str, Enum):
    """Lead-related audit event types."""
    LEAD_CREATED = "LEAD_CREATED"
    LEAD_UPDATED = "LEAD_UPDATED"
    LEAD_ASSIGNED = "LEAD_ASSIGNED"
    LEAD_CONTACTED = "LEAD_CONTACTED"
    LEAD_STAGE_CHANGED = "LEAD_STAGE_CHANGED"
    LEAD_CONVERTED = "LEAD_CONVERTED"
    LEAD_MARKED_LOST = "LEAD_MARKED_LOST"
    LEAD_MERGED = "LEAD_MERGED"
    LEAD_AI_SUMMARY_CREATED = "LEAD_AI_SUMMARY_CREATED"
    FOLLOWUP_EMAIL_SENT = "FOLLOWUP_EMAIL_SENT"
    FOLLOWUP_EMAIL_FAILED = "FOLLOWUP_EMAIL_FAILED"
    FOLLOWUP_STOPPED = "FOLLOWUP_STOPPED"
    MARKETING_CONSENT_UPDATED = "MARKETING_CONSENT_UPDATED"
    SLA_BREACH = "SLA_BREACH"
