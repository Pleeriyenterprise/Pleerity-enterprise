"""
Cookie Consent Models

GDPR/UK-compliant consent tracking with:
- Event stream (append-only audit trail)
- Materialized state (fast reads)
- Full audit logging
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class ConsentEventType(str, Enum):
    """Types of consent events."""
    BANNER_SHOWN = "BANNER_SHOWN"
    ACCEPT_ALL = "ACCEPT_ALL"
    REJECT_NON_ESSENTIAL = "REJECT_NON_ESSENTIAL"
    CUSTOM = "CUSTOM"
    WITHDRAW = "WITHDRAW"
    UPDATE = "UPDATE"


class ConsentActionTaken(str, Enum):
    """Consent action categories."""
    ACCEPT_ALL = "ACCEPT_ALL"
    REJECT_NON_ESSENTIAL = "REJECT_NON_ESSENTIAL"
    CUSTOM = "CUSTOM"
    UNKNOWN = "UNKNOWN"


class ConsentPreferences(BaseModel):
    """Cookie consent preferences."""
    necessary: bool = True  # Always true
    analytics: bool = False
    marketing: bool = False
    functional: bool = False


class UTMData(BaseModel):
    """UTM tracking parameters."""
    source: Optional[str] = None
    medium: Optional[str] = None
    campaign: Optional[str] = None
    term: Optional[str] = None
    content: Optional[str] = None


class ConsentCaptureRequest(BaseModel):
    """Request to capture consent from frontend."""
    session_id: str
    event_type: ConsentEventType
    consent_version: str = "v1"
    banner_text_hash: Optional[str] = None
    preferences: ConsentPreferences
    page_path: Optional[str] = None
    referrer: Optional[str] = None
    utm: Optional[UTMData] = None
    country: Optional[str] = None
    user_agent: Optional[str] = None


class ConsentEvent(BaseModel):
    """Append-only consent event record."""
    event_id: str
    created_at: datetime
    event_type: ConsentEventType
    consent_version: str
    banner_text_hash: Optional[str] = None
    session_id: str
    user_id: Optional[str] = None
    portal_user_id: Optional[str] = None
    client_id: Optional[str] = None
    crn: Optional[str] = None
    email_masked: Optional[str] = None
    country: Optional[str] = None
    ip_hash: Optional[str] = None
    user_agent: Optional[str] = None
    page_path: Optional[str] = None
    referrer: Optional[str] = None
    utm: Optional[UTMData] = None
    preferences: ConsentPreferences


class ConsentState(BaseModel):
    """Materialized current consent state per session."""
    state_id: str
    updated_at: datetime
    session_id: str
    user_id: Optional[str] = None
    portal_user_id: Optional[str] = None
    client_id: Optional[str] = None
    crn: Optional[str] = None
    email_masked: Optional[str] = None
    action_taken: ConsentActionTaken
    consent_version: str
    banner_text_hash: Optional[str] = None
    preferences: ConsentPreferences
    page_path: Optional[str] = None
    country: Optional[str] = None
    is_logged_in: bool = False
    outreach_eligible: bool = False  # True only if marketing=True


class ConsentStatsResponse(BaseModel):
    """Admin dashboard statistics response."""
    kpis: Dict[str, int]
    categories: Dict[str, int]
    trend: List[Dict[str, Any]]


class ConsentLogItem(BaseModel):
    """Single consent log item for admin view."""
    event_id: str
    created_at: datetime
    event_type: ConsentEventType
    action_taken: ConsentActionTaken
    preferences: ConsentPreferences
    session_id: str
    user_display: str  # "CRN + masked email" or "Anonymous"
    crn: Optional[str] = None
    country: Optional[str] = None
    page_path: Optional[str] = None
    consent_version: str
    is_logged_in: bool


class ConsentLogDetailResponse(BaseModel):
    """Detailed consent record for admin drawer."""
    # Consent snapshot
    event_id: str
    session_id: str
    crn: Optional[str] = None
    user_id: Optional[str] = None
    portal_user_id: Optional[str] = None
    client_id: Optional[str] = None
    action_taken: ConsentActionTaken
    preferences: ConsentPreferences
    created_at: datetime
    updated_at: Optional[datetime] = None
    consent_version: str
    banner_text_hash: Optional[str] = None
    
    # Context
    page_path: Optional[str] = None
    referrer: Optional[str] = None
    utm: Optional[UTMData] = None
    country: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Derived
    is_logged_in: bool
    outreach_eligible: bool
    
    # Timeline
    timeline: List[Dict[str, Any]]
