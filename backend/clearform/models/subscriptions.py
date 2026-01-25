"""ClearForm Subscription Models

Phase 1 Subscription Scope:
- Simple subscription → monthly credit grant
- Manual top-ups via Stripe

Uses same Stripe account as Pleerity but separate products.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum
import uuid


class ClearFormPlan(str, Enum):
    """ClearForm subscription plans"""
    FREE = "free"           # No subscription, pay-as-you-go only
    STARTER = "starter"     # 10 credits/month
    PROFESSIONAL = "professional"  # 30 credits/month
    UNLIMITED = "unlimited"  # 100 credits/month


class ClearFormSubscriptionStatus(str, Enum):
    """Subscription status"""
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class ClearFormSubscription(BaseModel):
    """User subscription record"""
    subscription_id: str = Field(default_factory=lambda: f"CFS-{uuid.uuid4().hex[:12].upper()}")
    user_id: str
    
    # Plan details
    plan: ClearFormPlan
    status: ClearFormSubscriptionStatus = ClearFormSubscriptionStatus.ACTIVE
    
    # Credit grants
    monthly_credits: int  # Credits granted each month
    credits_granted_this_period: bool = False
    
    # Stripe references
    stripe_subscription_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    
    # Billing cycle
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cancelled_at: Optional[datetime] = None
    
    model_config = {"extra": "ignore"}


class ClearFormPlanDetails(BaseModel):
    """Plan details for display"""
    plan: ClearFormPlan
    name: str
    description: str
    monthly_price_gbp: int  # Price in pence, 0 for free
    monthly_price_display: str
    monthly_credits: int
    features: List[str]
    popular: bool = False
    stripe_price_id: Optional[str] = None


# ============================================================================
# Plan Configuration
# ============================================================================

CLEARFORM_PLANS = {
    ClearFormPlan.FREE: ClearFormPlanDetails(
        plan=ClearFormPlan.FREE,
        name="Pay As You Go",
        description="Purchase credits when you need them",
        monthly_price_gbp=0,
        monthly_price_display="Free",
        monthly_credits=0,
        features=[
            "Pay-as-you-go credits",
            "All document types",
            "PDF & DOCX exports",
            "Document vault storage",
        ],
        popular=False,
    ),
    ClearFormPlan.STARTER: ClearFormPlanDetails(
        plan=ClearFormPlan.STARTER,
        name="Starter",
        description="Perfect for occasional document needs",
        monthly_price_gbp=499,  # £4.99
        monthly_price_display="£4.99/month",
        monthly_credits=10,
        features=[
            "10 credits/month",
            "All document types",
            "PDF & DOCX exports",
            "Document vault storage",
            "Unused credits roll over (up to 20)",
        ],
        popular=False,
    ),
    ClearFormPlan.PROFESSIONAL: ClearFormPlanDetails(
        plan=ClearFormPlan.PROFESSIONAL,
        name="Professional",
        description="For regular document generation",
        monthly_price_gbp=999,  # £9.99
        monthly_price_display="£9.99/month",
        monthly_credits=30,
        features=[
            "30 credits/month",
            "All document types",
            "PDF & DOCX exports",
            "Document vault storage",
            "Unused credits roll over (up to 60)",
            "Priority support",
        ],
        popular=True,
    ),
    ClearFormPlan.UNLIMITED: ClearFormPlanDetails(
        plan=ClearFormPlan.UNLIMITED,
        name="Unlimited",
        description="For power users and small businesses",
        monthly_price_gbp=2499,  # £24.99
        monthly_price_display="£24.99/month",
        monthly_credits=100,
        features=[
            "100 credits/month",
            "All document types",
            "PDF & DOCX exports",
            "Document vault storage",
            "Unlimited rollover",
            "Priority support",
            "API access (coming soon)",
        ],
        popular=False,
    ),
}

# Credit rollover limits by plan
CREDIT_ROLLOVER_LIMITS = {
    ClearFormPlan.FREE: 0,        # No rollover for free tier
    ClearFormPlan.STARTER: 20,    # Max 20 credits can roll over
    ClearFormPlan.PROFESSIONAL: 60,  # Max 60 credits
    ClearFormPlan.UNLIMITED: -1,  # Unlimited (-1 = no limit)
}
