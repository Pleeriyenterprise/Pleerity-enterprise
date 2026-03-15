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
    COMPLIANCE_CHECKLIST = "COMPLIANCE_CHECKLIST"  # Lead magnet: UK Landlord Compliance Master Checklist
    # Unified lead engine sources
    COMPLIANCE_RISK_CHECK = "COMPLIANCE_RISK_CHECK"  # Full risk check report (risk_leads sync)
    PRICING_PAGE = "PRICING_PAGE"
    AUTOMATION_ENQUIRY = "AUTOMATION_ENQUIRY"
    MARKET_RESEARCH_ENQUIRY = "MARKET_RESEARCH_ENQUIRY"
    SUPPORT_FORM = "SUPPORT_FORM"


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
    NURTURING = "NURTURING"   # In nurture sequence
    SALES_READY = "SALES_READY"
    PROPOSAL_SENT = "PROPOSAL_SENT"
    NEGOTIATING = "NEGOTIATING"
    WON = "WON"  # Converted to Client
    LOST = "LOST"
    INACTIVE = "INACTIVE"


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
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    
    # Qualification (unified lead engine)
    user_type: Optional[str] = None  # e.g. landlord, agent
    portfolio_size: Optional[int] = None
    primary_interest: Optional[str] = None
    secondary_interest: Optional[str] = None
    risk_score: Optional[int] = None
    risk_level: Optional[str] = None  # HIGH, MODERATE, LOW
    
    # Context
    message_summary: Optional[str] = None
    conversation_id: Optional[str] = None  # Link to support conversation
    intake_draft_id: Optional[str] = None  # Link to abandoned intake
    
    # Source metadata (for social integrations and risk_check)
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
    lead_score: Optional[int] = None  # 0-100 numeric score
    
    # Admin notes
    admin_notes: Optional[str] = None


class LeadUpdateRequest(BaseModel):
    """Request to update a lead."""
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    user_type: Optional[str] = None
    portfolio_size: Optional[int] = None
    primary_interest: Optional[str] = None
    secondary_interest: Optional[str] = None
    risk_score: Optional[int] = None
    risk_level: Optional[str] = None
    service_interest: Optional[LeadServiceInterest] = None
    message_summary: Optional[str] = None
    intent_score: Optional[LeadIntentScore] = None
    lead_score: Optional[int] = None
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

# Default day-based nurture (task example: day0 welcome → day15 conversion CTA). Used for leads without type-specific sequence.
DEFAULT_DAY_NURTURE_SEQUENCE = [
    {"step": 1, "delay_days": 0, "template_id": "nurture_day0_welcome", "subject": "Welcome to Pleerity"},
    {"step": 2, "delay_days": 2, "template_id": "nurture_day2_compliance_education", "subject": "Quick guide to landlord compliance"},
    {"step": 3, "delay_days": 4, "template_id": "nurture_day4_compliance_mistakes", "subject": "The most commonly missed landlord deadline"},
    {"step": 4, "delay_days": 6, "template_id": "nurture_day6_automation_benefits", "subject": "How portfolio landlords reduce compliance stress"},
    {"step": 5, "delay_days": 8, "template_id": "nurture_day8_document_pack", "subject": "Introducing our document packs"},
    {"step": 6, "delay_days": 12, "template_id": "nurture_day12_case_example", "subject": "How other landlords stay on top of compliance"},
    {"step": 7, "delay_days": 15, "template_id": "nurture_day15_conversion_cta", "subject": "Ready to centralise your compliance?"},
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
    """Lead-related audit event types (also used as activity_type for timeline)."""
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
    # Unified lead engine activity types
    RISK_CHECK_COMPLETED = "RISK_CHECK_COMPLETED"
    CHATBOT_CAPTURE = "CHATBOT_CAPTURE"
    PRICING_REQUESTED = "PRICING_REQUESTED"
    NURTURE_STARTED = "NURTURE_STARTED"
    CTA_CLICKED = "CTA_CLICKED"
    LEAD_SCORE_UPDATED = "LEAD_SCORE_UPDATED"
