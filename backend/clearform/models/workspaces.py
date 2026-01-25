"""ClearForm Workspace Models

Workspaces allow users to organize documents by project.
Phase 2 feature.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum
import uuid


class WorkspaceRole(str, Enum):
    """Workspace member roles (Phase 3 - Institutional)"""
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


class Workspace(BaseModel):
    """User workspace for organizing documents."""
    workspace_id: str = Field(default_factory=lambda: f"WS-{uuid.uuid4().hex[:8].upper()}")
    owner_id: str
    
    # Workspace info
    name: str
    description: Optional[str] = None
    color: str = "#10b981"  # Default emerald
    icon: str = "folder"
    
    # Stats (cached)
    document_count: int = 0
    template_count: int = 0
    
    # Settings
    is_default: bool = False
    is_archived: bool = False
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = {"extra": "ignore"}


class WorkspaceMember(BaseModel):
    """Workspace member (Phase 3 - Institutional)"""
    member_id: str = Field(default_factory=lambda: f"WM-{uuid.uuid4().hex[:8].upper()}")
    workspace_id: str
    user_id: str
    role: WorkspaceRole = WorkspaceRole.EDITOR
    
    # Invitation
    invited_by: Optional[str] = None
    invited_at: Optional[datetime] = None
    joined_at: Optional[datetime] = None
    
    # Status
    is_active: bool = True
    
    model_config = {"extra": "ignore"}


class SmartProfile(BaseModel):
    """User's saved profile data for auto-fill.
    
    Smart profiles store commonly-used personal and business details
    that can be automatically filled into document forms.
    """
    profile_id: str = Field(default_factory=lambda: f"SP-{uuid.uuid4().hex[:8].upper()}")
    user_id: str
    workspace_id: Optional[str] = None  # Can be workspace-specific
    
    # Profile type
    profile_type: str = "personal"  # personal, business, property, etc.
    name: str  # "My Personal Details", "Business Info", etc.
    is_default: bool = False
    
    # Personal details
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    
    # Address
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    county: Optional[str] = None
    postcode: Optional[str] = None
    country: str = "United Kingdom"
    
    # Professional details
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    company_address: Optional[str] = None
    company_registration: Optional[str] = None
    
    # Additional fields (flexible)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)
    
    # Usage tracking
    use_count: int = 0
    last_used_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = {"extra": "ignore"}
