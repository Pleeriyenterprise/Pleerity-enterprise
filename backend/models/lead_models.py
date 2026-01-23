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


class LeadAssignRequest(BaseModel):
    """Request to assign a lead to an admin."""
    admin_id: str
    notify_admin: bool = True


class LeadConvertRequest(BaseModel):
    """Request to convert a lead to a client."""
    client_id: str  # The created client's ID
    conversion_notes: Optional[str] = None


class LeadMarkLostRequest(BaseModel):
    """Request to mark a lead as lost."""
    reason: str  # Why the lead was lost
    competitor: Optional[str] = None  # If lost to competitor


class LeadContactRequest(BaseModel):
    """Request to log a contact attempt."""
    contact_method: str  # email, phone, whatsapp, in_person
    notes: Optional[str] = None
    outcome: Optional[str] = None  # answered, voicemail, no_response


class LeadBulkImportRequest(BaseModel):
    """Request for CSV import (placeholder)."""
    leads: List[LeadCreateRequest]
    source: str = "IMPORT"
    campaign_name: Optional[str] = None


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class LeadResponse(BaseModel):
    """Full lead response."""
    lead_id: str
    source_platform: str
    service_interest: str
    
    # Contact info
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    
    # Qualification
    intent_score: str
    stage: str
    status: str
    
    # Assignment
    assigned_to: Optional[str] = None
    assigned_at: Optional[str] = None
    
    # Context
    message_summary: Optional[str] = None
    ai_summary: Optional[str] = None
    conversation_id: Optional[str] = None
    intake_draft_id: Optional[str] = None
    
    # Source metadata
    source_metadata: Optional[Dict[str, Any]] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    referrer_url: Optional[str] = None
    
    # Consent & follow-up
    marketing_consent: bool
    followup_status: str
    followup_step: int
    last_followup_at: Optional[str] = None
    
    # Timestamps
    created_at: str
    updated_at: str
    last_contacted_at: Optional[str] = None
    converted_at: Optional[str] = None
    
    # Conversion link
    client_id: Optional[str] = None
    
    # Merge tracking
    merged_into_lead_id: Optional[str] = None
    
    # Admin
    admin_notes: Optional[str] = None
    
    # SLA
    sla_breach: bool = False
    sla_breach_at: Optional[str] = None


class LeadListResponse(BaseModel):
    """Paginated lead list response."""
    leads: List[LeadResponse]
    total: int
    page: int
    limit: int
    stats: Dict[str, Any]


class LeadStatsResponse(BaseModel):
    """Lead statistics response."""
    total_leads: int
    new_leads: int
    contacted_leads: int
    qualified_leads: int
    converted_leads: int
    lost_leads: int
    conversion_rate: float
    avg_time_to_contact_hours: Optional[float]
    leads_by_source: Dict[str, int]
    leads_by_service: Dict[str, int]
    leads_by_intent: Dict[str, int]
    sla_breaches_today: int


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
# INTENT SCORING RULES
# ============================================================================

INTENT_SCORING_RULES = [
    # HIGH intent indicators
    {
        "condition": "service_interest == 'CVP' and property_count >= 3",
        "score": LeadIntentScore.HIGH,
        "reason": "CVP interest with 3+ properties",
    },
    {
        "condition": "asked_about_pricing",
        "score": LeadIntentScore.HIGH,
        "reason": "Asked about pricing",
    },
    {
        "condition": "requested_demo",
        "score": LeadIntentScore.HIGH,
        "reason": "Requested demo/consultation",
    },
    {
        "condition": "source_platform == 'INTAKE_ABANDONED' and reached_payment",
        "score": LeadIntentScore.HIGH,
        "reason": "Reached payment step in intake",
    },
    
    # MEDIUM intent indicators
    {
        "condition": "asked_about_pricing",
        "score": LeadIntentScore.MEDIUM,
        "reason": "Asked about pricing",
    },
    {
        "condition": "service_interest in ['CVP', 'DOCUMENT_PACKS']",
        "score": LeadIntentScore.MEDIUM,
        "reason": "Specific service interest",
    },
    {
        "condition": "provided_phone",
        "score": LeadIntentScore.MEDIUM,
        "reason": "Provided phone number",
    },
    
    # LOW intent indicators (default)
    {
        "condition": "general_question_only",
        "score": LeadIntentScore.LOW,
        "reason": "General enquiry only",
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
