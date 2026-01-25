"""ClearForm Audit Log Models

Comprehensive audit logging for compliance and tracking.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum
import uuid


class AuditAction(str, Enum):
    """Audit action types"""
    # Auth
    USER_REGISTERED = "USER_REGISTERED"
    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    
    # Documents
    DOCUMENT_CREATED = "DOCUMENT_CREATED"
    DOCUMENT_GENERATED = "DOCUMENT_GENERATED"
    DOCUMENT_DOWNLOADED = "DOCUMENT_DOWNLOADED"
    DOCUMENT_ARCHIVED = "DOCUMENT_ARCHIVED"
    DOCUMENT_SHARED = "DOCUMENT_SHARED"
    
    # Credits
    CREDITS_PURCHASED = "CREDITS_PURCHASED"
    CREDITS_DEDUCTED = "CREDITS_DEDUCTED"
    CREDITS_REFUNDED = "CREDITS_REFUNDED"
    CREDITS_EXPIRED = "CREDITS_EXPIRED"
    CREDITS_GRANTED = "CREDITS_GRANTED"
    
    # Subscriptions
    SUBSCRIPTION_CREATED = "SUBSCRIPTION_CREATED"
    SUBSCRIPTION_RENEWED = "SUBSCRIPTION_RENEWED"
    SUBSCRIPTION_CANCELLED = "SUBSCRIPTION_CANCELLED"
    
    # Organization
    ORG_CREATED = "ORG_CREATED"
    ORG_UPDATED = "ORG_UPDATED"
    ORG_MEMBER_ADDED = "ORG_MEMBER_ADDED"
    ORG_MEMBER_REMOVED = "ORG_MEMBER_REMOVED"
    ORG_MEMBER_ROLE_CHANGED = "ORG_MEMBER_ROLE_CHANGED"
    
    # Templates
    TEMPLATE_CREATED = "TEMPLATE_CREATED"
    TEMPLATE_USED = "TEMPLATE_USED"
    TEMPLATE_DELETED = "TEMPLATE_DELETED"
    
    # Profiles
    PROFILE_CREATED = "PROFILE_CREATED"
    PROFILE_UPDATED = "PROFILE_UPDATED"
    PROFILE_DELETED = "PROFILE_DELETED"
    
    # Workspaces
    WORKSPACE_CREATED = "WORKSPACE_CREATED"
    WORKSPACE_ARCHIVED = "WORKSPACE_ARCHIVED"
    
    # Admin
    ADMIN_DOC_TYPE_CREATED = "ADMIN_DOC_TYPE_CREATED"
    ADMIN_DOC_TYPE_UPDATED = "ADMIN_DOC_TYPE_UPDATED"
    ADMIN_DOC_TYPE_DISABLED = "ADMIN_DOC_TYPE_DISABLED"
    
    # System
    SYSTEM_ERROR = "SYSTEM_ERROR"


class AuditSeverity(str, Enum):
    """Audit entry severity"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AuditLog(BaseModel):
    """Audit log entry"""
    log_id: str = Field(default_factory=lambda: f"AL-{uuid.uuid4().hex[:12].upper()}")
    
    # Actor
    user_id: Optional[str] = None
    org_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Action
    action: AuditAction
    severity: AuditSeverity = AuditSeverity.INFO
    
    # Context
    resource_type: Optional[str] = None  # e.g., "document", "organization"
    resource_id: Optional[str] = None
    
    # Details
    description: str
    details: Dict[str, Any] = Field(default_factory=dict)
    
    # Request info
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Timestamp
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = {"extra": "ignore"}


class AuditLogQuery(BaseModel):
    """Query parameters for audit logs"""
    user_id: Optional[str] = None
    org_id: Optional[str] = None
    action: Optional[AuditAction] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    severity: Optional[AuditSeverity] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 100
    offset: int = 0
