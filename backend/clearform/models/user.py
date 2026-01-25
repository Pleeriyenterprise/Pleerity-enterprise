"""ClearForm User Model

Single user entity with integrated credit wallet.
Reuses existing auth provider but maintains separate user data.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum
import uuid


class ClearFormUserStatus(str, Enum):
    """User account status"""
    PENDING = "PENDING"      # Email verification pending
    ACTIVE = "ACTIVE"        # Fully active account
    SUSPENDED = "SUSPENDED"  # Account suspended
    DELETED = "DELETED"      # Soft deleted


class ClearFormUser(BaseModel):
    """ClearForm user with integrated credit wallet.
    
    Note: Single user entity - no roles in Phase 1.
    ClearForm user ≠ Pleerity client conceptually.
    """
    user_id: str = Field(default_factory=lambda: f"CFU-{uuid.uuid4().hex[:12].upper()}")
    email: EmailStr
    full_name: str
    password_hash: str
    
    # Account status
    status: ClearFormUserStatus = ClearFormUserStatus.PENDING
    email_verified: bool = False
    email_verified_at: Optional[datetime] = None
    
    # Credit wallet (embedded for simplicity in Phase 1)
    credit_balance: int = 0  # Current available credits
    lifetime_credits_purchased: int = 0
    lifetime_credits_used: int = 0
    lifetime_credits_expired: int = 0
    
    # Subscription info (if active)
    subscription_id: Optional[str] = None
    subscription_plan: Optional[str] = None
    next_credit_grant_at: Optional[datetime] = None
    
    # Stripe customer (separate from Pleerity)
    stripe_customer_id: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: Optional[datetime] = None
    
    # Settings
    preferences: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = {"extra": "ignore"}


class ClearFormUserCreate(BaseModel):
    """Request model for user registration"""
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8)
    
    model_config = {"extra": "ignore"}


class ClearFormUserResponse(BaseModel):
    """Safe user response (no password hash)"""
    user_id: str
    email: str
    full_name: str
    status: ClearFormUserStatus
    email_verified: bool
    
    # Credit info
    credit_balance: int
    lifetime_credits_purchased: int
    lifetime_credits_used: int
    
    # Subscription info
    subscription_id: Optional[str] = None
    subscription_plan: Optional[str] = None
    next_credit_grant_at: Optional[datetime] = None
    
    created_at: datetime
    last_login_at: Optional[datetime] = None
    
    model_config = {"extra": "ignore"}


class ClearFormUserLogin(BaseModel):
    """Login request"""
    email: EmailStr
    password: str


class ClearFormTokenResponse(BaseModel):
    """Auth token response"""
    access_token: str
    token_type: str = "bearer"
    user: ClearFormUserResponse
