"""ClearForm Institutional/Organization Models

Phase 3: Enterprise features for team/institutional use.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum
import uuid


class OrganizationType(str, Enum):
    """Organization types"""
    SMALL_BUSINESS = "SMALL_BUSINESS"
    ENTERPRISE = "ENTERPRISE"
    NONPROFIT = "NONPROFIT"
    EDUCATIONAL = "EDUCATIONAL"
    GOVERNMENT = "GOVERNMENT"


class OrgMemberRole(str, Enum):
    """Organization member roles"""
    OWNER = "OWNER"          # Full control, billing
    ADMIN = "ADMIN"          # Manage users, settings
    MANAGER = "MANAGER"      # Manage team, view reports
    MEMBER = "MEMBER"        # Use credits, create docs
    VIEWER = "VIEWER"        # View only


class InvitationStatus(str, Enum):
    """Invitation status"""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"


class Organization(BaseModel):
    """Institutional/Team organization"""
    org_id: str = Field(default_factory=lambda: f"ORG-{uuid.uuid4().hex[:8].upper()}")
    
    # Basic info
    name: str
    slug: str  # URL-friendly name
    description: Optional[str] = None
    org_type: OrganizationType = OrganizationType.SMALL_BUSINESS
    
    # Branding
    logo_url: Optional[str] = None
    primary_color: str = "#10b981"
    
    # Credit pool
    credit_balance: int = 0
    lifetime_credits_purchased: int = 0
    lifetime_credits_used: int = 0
    monthly_credit_budget: Optional[int] = None  # Optional spending limit
    
    # Subscription (org-level)
    subscription_id: Optional[str] = None
    subscription_plan: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    
    # Settings
    settings: Dict[str, Any] = Field(default_factory=lambda: {
        "allow_member_purchases": False,  # Can members buy credits?
        "require_approval": False,        # Require approval for documents
        "default_workspace_id": None,
        "allowed_document_types": [],     # Empty = all allowed
        "compliance_pack_ids": [],
    })
    
    # Owner
    owner_id: str
    
    # Stats
    member_count: int = 1
    document_count: int = 0
    
    # Status
    is_active: bool = True
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = {"extra": "ignore"}


class OrgMember(BaseModel):
    """Organization membership"""
    member_id: str = Field(default_factory=lambda: f"OM-{uuid.uuid4().hex[:8].upper()}")
    org_id: str
    user_id: str
    
    # Role
    role: OrgMemberRole = OrgMemberRole.MEMBER
    
    # Permissions override (optional per-user limits)
    credit_limit: Optional[int] = None  # Monthly credit limit for this user
    allowed_document_types: Optional[List[str]] = None  # Override org settings
    
    # Invitation
    invited_by: Optional[str] = None
    invitation_email: Optional[str] = None
    
    # Status
    is_active: bool = True
    
    # Timestamps
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: Optional[datetime] = None
    
    model_config = {"extra": "ignore"}


class OrgInvitation(BaseModel):
    """Organization invitation"""
    invitation_id: str = Field(default_factory=lambda: f"INV-{uuid.uuid4().hex[:8].upper()}")
    org_id: str
    
    # Invitation details
    email: str
    role: OrgMemberRole = OrgMemberRole.MEMBER
    message: Optional[str] = None
    
    # Status
    status: InvitationStatus = InvitationStatus.PENDING
    
    # Tracking
    invited_by: str
    accepted_by_user_id: Optional[str] = None
    
    # Expiry
    expires_at: datetime
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    responded_at: Optional[datetime] = None
    
    model_config = {"extra": "ignore"}


class CompliancePack(BaseModel):
    """Pre-built document set for specific use cases"""
    pack_id: str = Field(default_factory=lambda: f"CP-{uuid.uuid4().hex[:8].upper()}")
    
    # Pack info
    code: str  # e.g., "TENANT_ESSENTIALS"
    name: str
    description: str
    
    # Document types in this pack
    document_types: List[str]  # List of document type codes
    
    # Pricing
    credit_cost: int  # Total cost to generate all docs in pack
    
    # Target audience
    target_audience: str  # e.g., "Landlords", "HR Departments"
    use_cases: List[str] = Field(default_factory=list)
    
    # Status
    is_active: bool = True
    is_featured: bool = False
    display_order: int = 0
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = {"extra": "ignore"}


# ============================================================================
# Default Compliance Packs
# ============================================================================

DEFAULT_COMPLIANCE_PACKS = [
    CompliancePack(
        code="TENANT_ESSENTIALS",
        name="Tenant Essentials Pack",
        description="Essential documents for tenants dealing with landlord issues",
        document_types=["NOTICE_TO_LANDLORD", "COMPLAINT_APPEAL_LETTER", "STATEMENT_OF_CIRCUMSTANCES"],
        credit_cost=2,  # Discount from individual prices
        target_audience="Tenants",
        use_cases=["Repair requests", "Deposit disputes", "Notice to quit"],
    ),
    CompliancePack(
        code="JOB_SEEKER",
        name="Job Seeker Pack",
        description="Complete job application document set",
        document_types=["cv_resume", "APPLICATION_COVER_LETTER", "formal_letter"],
        credit_cost=3,  # Discount from individual prices
        target_audience="Job Seekers",
        use_cases=["Job applications", "Career change", "Graduate applications"],
    ),
    CompliancePack(
        code="SMALL_BUSINESS",
        name="Small Business Starter",
        description="Essential business correspondence templates",
        document_types=["formal_letter", "REFERENCE_LETTER", "COMPLAINT_APPEAL_LETTER"],
        credit_cost=3,
        target_audience="Small Businesses",
        use_cases=["Client communication", "Employee references", "Supplier disputes"],
    ),
]
