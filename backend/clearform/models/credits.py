"""ClearForm Credit System Models

Phase 1 Credit Scope:
- Credit wallet
- Credit deduction on generation
- Manual top-ups via Stripe
- Simple subscription → monthly credit grant
- Expiry logic

Explicitly excluded for Phase 1:
- Workspaces
- Credit sharing
- Institutional billing
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum
import uuid


class CreditTransactionType(str, Enum):
    """Types of credit transactions"""
    # Additions
    PURCHASE = "PURCHASE"              # Manual top-up via Stripe
    SUBSCRIPTION_GRANT = "SUBSCRIPTION_GRANT"  # Monthly subscription grant
    BONUS = "BONUS"                    # Promotional credits
    REFUND = "REFUND"                  # Credits returned (e.g., failed generation)
    
    # Deductions
    DOCUMENT_GENERATION = "DOCUMENT_GENERATION"  # Used for document creation
    EXPIRY = "EXPIRY"                  # Credits expired


class CreditTransaction(BaseModel):
    """Individual credit transaction record.
    
    Every credit movement is recorded for audit.
    """
    transaction_id: str = Field(default_factory=lambda: f"CTX-{uuid.uuid4().hex[:12].upper()}")
    user_id: str
    
    # Transaction details
    transaction_type: CreditTransactionType
    amount: int  # Positive for additions, negative for deductions
    balance_after: int  # Balance after this transaction
    
    # Reference data
    reference_id: Optional[str] = None  # e.g., document_id, stripe_payment_id
    reference_type: Optional[str] = None  # e.g., "document", "stripe_payment"
    description: str
    
    # Expiry tracking (for PURCHASE and SUBSCRIPTION_GRANT)
    expires_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = {"extra": "ignore"}


class CreditWallet(BaseModel):
    """User's credit wallet summary.
    
    Note: The actual balance is stored on ClearFormUser.
    This model provides detailed wallet information.
    """
    user_id: str
    
    # Balances
    total_balance: int
    expiring_soon: int = 0  # Credits expiring in next 30 days
    
    # Breakdown by source
    subscription_credits: int = 0  # Credits from subscription
    purchased_credits: int = 0     # Credits from manual top-ups
    bonus_credits: int = 0         # Promotional credits
    
    # Usage stats
    credits_used_this_month: int = 0
    documents_generated_this_month: int = 0
    
    # Next events
    next_expiry_date: Optional[datetime] = None
    next_expiry_amount: int = 0
    next_grant_date: Optional[datetime] = None
    next_grant_amount: int = 0
    
    model_config = {"extra": "ignore"}


class CreditTopUp(BaseModel):
    """Credit top-up purchase record.
    
    Linked to Stripe one-time payment.
    """
    topup_id: str = Field(default_factory=lambda: f"CTU-{uuid.uuid4().hex[:12].upper()}")
    user_id: str
    
    # Purchase details
    credits: int
    price_gbp: int  # Price in pence
    
    # Stripe references
    stripe_payment_intent_id: Optional[str] = None
    stripe_checkout_session_id: Optional[str] = None
    
    # Status
    status: str = "pending"  # pending, completed, failed, refunded
    
    # Expiry (credits from purchases expire)
    expires_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    
    model_config = {"extra": "ignore"}


class CreditExpiry(BaseModel):
    """Tracks credit expiry batches.
    
    Credits are tracked in batches with expiry dates.
    FIFO: Oldest credits used first.
    """
    expiry_id: str = Field(default_factory=lambda: f"CEX-{uuid.uuid4().hex[:12].upper()}")
    user_id: str
    
    # Credits in this batch
    original_amount: int
    remaining_amount: int
    
    # Source
    source_type: CreditTransactionType  # PURCHASE or SUBSCRIPTION_GRANT
    source_id: str  # topup_id or subscription_id
    
    # Expiry date
    expires_at: datetime
    expired: bool = False
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = {"extra": "ignore"}


# ============================================================================
# Credit Pricing Configuration
# ============================================================================

class CreditPackage(BaseModel):
    """Credit package available for purchase"""
    package_id: str
    name: str
    credits: int
    price_gbp: int  # Price in pence
    price_display: str  # e.g., "£9.99"
    per_credit_price: float  # For display
    popular: bool = False
    stripe_price_id: Optional[str] = None  # To be configured


# Default credit packages for Phase 1
CREDIT_PACKAGES = [
    CreditPackage(
        package_id="credits_10",
        name="10 Credits",
        credits=10,
        price_gbp=999,  # £9.99
        price_display="£9.99",
        per_credit_price=0.999,
        popular=False,
    ),
    CreditPackage(
        package_id="credits_25",
        name="25 Credits",
        credits=25,
        price_gbp=1999,  # £19.99
        price_display="£19.99",
        per_credit_price=0.80,
        popular=True,
    ),
    CreditPackage(
        package_id="credits_50",
        name="50 Credits",
        credits=50,
        price_gbp=3499,  # £34.99
        price_display="£34.99",
        per_credit_price=0.70,
        popular=False,
    ),
    CreditPackage(
        package_id="credits_100",
        name="100 Credits",
        credits=100,
        price_gbp=5999,  # £59.99
        price_display="£59.99",
        per_credit_price=0.60,
        popular=False,
    ),
]

# Credit expiry period (days from purchase/grant)
CREDIT_EXPIRY_DAYS = 365  # Credits expire after 1 year

# Document costs (credits per generation)
DOCUMENT_CREDIT_COSTS = {
    "formal_letter": 1,
    "complaint_letter": 1,
    "cv_resume": 2,  # More complex
    # Phase 2+ document types will be added here
}
