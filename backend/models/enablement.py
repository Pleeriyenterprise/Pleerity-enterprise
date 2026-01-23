"""
Customer Enablement Automation Engine - Models
Educational automation system (NOT sales/marketing)

Core principles:
- Enablement only, no selling
- Event-driven only
- Backend-authoritative
- Full auditability
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


# ============================================
# Enablement Event Types
# ============================================

class EnablementEventType(str, Enum):
    """Core enablement events - subscribe to internal event system"""
    # Onboarding events
    CLIENT_INTAKE_COMPLETED = "CLIENT_INTAKE_COMPLETED"
    PROVISIONING_COMPLETED = "PROVISIONING_COMPLETED"
    PASSWORD_SET = "PASSWORD_SET"
    FIRST_LOGIN = "FIRST_LOGIN"
    
    # Property & Document events
    PROPERTY_ADDED = "PROPERTY_ADDED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_VERIFIED = "DOCUMENT_VERIFIED"
    
    # Compliance events
    COMPLIANCE_SCORE_CALCULATED = "COMPLIANCE_SCORE_CALCULATED"
    COMPLIANCE_STATUS_CHANGED = "COMPLIANCE_STATUS_CHANGED"
    REQUIREMENT_EXPIRING_SOON = "REQUIREMENT_EXPIRING_SOON"
    REQUIREMENT_OVERDUE = "REQUIREMENT_OVERDUE"
    
    # Value events
    REPORT_GENERATED = "REPORT_GENERATED"
    ORDER_DELIVERED = "ORDER_DELIVERED"
    
    # Feature gate events
    FEATURE_BLOCKED_BY_PLAN = "FEATURE_BLOCKED_BY_PLAN"
    
    # Inactivity events (system-detected)
    INACTIVITY_DETECTED = "INACTIVITY_DETECTED"
    NO_ACTION_AFTER_REMINDER = "NO_ACTION_AFTER_REMINDER"


# ============================================
# Enablement Automation Categories
# ============================================

class EnablementCategory(str, Enum):
    """Automation categories - each has specific rules"""
    ONBOARDING_GUIDANCE = "ONBOARDING_GUIDANCE"      # Help users understand onboarding
    VALUE_CONFIRMATION = "VALUE_CONFIRMATION"        # Explain why something mattered
    COMPLIANCE_AWARENESS = "COMPLIANCE_AWARENESS"    # Risk awareness without advice
    INACTIVITY_SUPPORT = "INACTIVITY_SUPPORT"       # Gentle educational nudges
    FEATURE_GATE_EXPLANATION = "FEATURE_GATE_EXPLANATION"  # Explain gated features


# ============================================
# Delivery Channels
# ============================================

class DeliveryChannel(str, Enum):
    """Allowed delivery channels"""
    IN_APP = "IN_APP"           # In-app notifications
    EMAIL = "EMAIL"             # Email via Postmark
    ASSISTANT = "ASSISTANT"     # AI Assistant context


# ============================================
# Action Status
# ============================================

class EnablementActionStatus(str, Enum):
    """Every action must end in one of these states"""
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SUPPRESSED = "SUPPRESSED"


# ============================================
# Event Payload
# ============================================

class EnablementEventPayload(BaseModel):
    """Standard event payload structure"""
    event_id: str
    event_type: EnablementEventType
    client_id: str
    plan_code: Optional[str] = None
    timestamp: datetime
    context_payload: Dict[str, Any] = {}
    
    # Optional identifiers
    property_id: Optional[str] = None
    document_id: Optional[str] = None
    requirement_id: Optional[str] = None
    order_id: Optional[str] = None


# ============================================
# Enablement Template
# ============================================

class EnablementTemplate(BaseModel):
    """Message template for enablement communications"""
    template_id: str
    template_code: str  # Unique code for referencing
    category: EnablementCategory
    event_triggers: List[EnablementEventType]
    
    # Template content
    title: str
    body: str  # Supports {{variable}} placeholders
    
    # Channel-specific content
    email_subject: Optional[str] = None
    email_body_html: Optional[str] = None
    assistant_context: Optional[str] = None
    
    # Delivery configuration
    channels: List[DeliveryChannel]
    delay_minutes: int = 0  # Delay after event
    
    # Conditions
    plan_codes: Optional[List[str]] = None  # Only for these plans
    
    # Metadata
    version: int = 1
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


# ============================================
# Enablement Action (Audit Log)
# ============================================

class EnablementAction(BaseModel):
    """Audit record for every enablement action"""
    action_id: str
    
    # Event that triggered this
    event_id: str
    event_type: EnablementEventType
    
    # Who received it
    client_id: str
    portal_user_id: Optional[str] = None
    
    # What was sent
    template_id: str
    template_code: str
    category: EnablementCategory
    
    # How it was delivered
    channel: DeliveryChannel
    
    # Result
    status: EnablementActionStatus
    status_reason: Optional[str] = None  # Reason for FAILED/SUPPRESSED
    
    # Content snapshot (for auditability)
    rendered_title: str
    rendered_body: str
    
    # Timestamps
    created_at: datetime
    delivered_at: Optional[datetime] = None
    
    # Retry info
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None


# ============================================
# User Enablement Preferences
# ============================================

class EnablementPreferences(BaseModel):
    """User preferences for enablement communications"""
    client_id: str
    portal_user_id: Optional[str] = None
    
    # Channel preferences
    in_app_enabled: bool = True
    email_enabled: bool = True
    assistant_enabled: bool = True
    
    # Category preferences (user can opt out of categories)
    categories_enabled: Dict[str, bool] = {
        "ONBOARDING_GUIDANCE": True,
        "VALUE_CONFIRMATION": True,
        "COMPLIANCE_AWARENESS": True,
        "INACTIVITY_SUPPORT": True,
        "FEATURE_GATE_EXPLANATION": True,
    }
    
    # Global suppression
    all_suppressed: bool = False
    suppressed_until: Optional[datetime] = None
    
    # Metadata
    updated_at: datetime


# ============================================
# Admin Suppression Rule
# ============================================

class SuppressionRule(BaseModel):
    """Admin-created suppression rules"""
    rule_id: str
    
    # Scope
    client_id: Optional[str] = None  # None = global
    category: Optional[EnablementCategory] = None  # None = all categories
    template_code: Optional[str] = None  # None = all templates
    
    # Duration
    active: bool = True
    expires_at: Optional[datetime] = None
    
    # Audit
    reason: str
    created_by: str  # Admin ID
    created_at: datetime


# ============================================
# Request/Response Models
# ============================================

class EnablementTimelineResponse(BaseModel):
    """Response for client enablement timeline"""
    client_id: str
    actions: List[EnablementAction]
    total: int
    
    
class EnablementStatsResponse(BaseModel):
    """Dashboard statistics"""
    total_actions: int
    success_count: int
    failed_count: int
    suppressed_count: int
    by_category: Dict[str, int]
    by_channel: Dict[str, int]


class TriggerEnablementRequest(BaseModel):
    """Manually trigger an enablement event (for testing/admin)"""
    event_type: EnablementEventType
    client_id: str
    context_payload: Dict[str, Any] = {}


class UpdatePreferencesRequest(BaseModel):
    """Update enablement preferences"""
    in_app_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    assistant_enabled: Optional[bool] = None
    categories_enabled: Optional[Dict[str, bool]] = None


class CreateSuppressionRequest(BaseModel):
    """Create a suppression rule"""
    client_id: Optional[str] = None
    category: Optional[EnablementCategory] = None
    template_code: Optional[str] = None
    reason: str
    expires_at: Optional[datetime] = None
