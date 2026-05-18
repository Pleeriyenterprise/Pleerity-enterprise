"""Pilot lifecycle governance — platform state (Stripe remains billing authority)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from models.pilot_invite import PilotOnboardingFeePolicy


class PilotStatus(str, Enum):
    ACTIVE = "active"
    EXTENDED = "extended"
    EXPIRED = "expired"
    CONVERTED_TO_PAID = "converted_to_paid"
    CANCELLED = "cancelled"
    COMPED = "comped"
    PAUSED = "paused"


class PilotDiscountSource(str, Enum):
    INVITE_CODE = "invite_code"
    ADMIN_OVERRIDE = "admin_override"
    COMP = "comp"
    STRIPE_WEBHOOK = "stripe_webhook"


class PilotLifecycleAction(str, Enum):
    CREATED = "created"
    EXTENDED = "extended"
    SHORTENED = "shortened"
    EXPIRY_SET = "expiry_set"
    CANCELLED = "cancelled"
    CONVERTED_TO_PAID = "converted_to_paid"
    COMPED = "comped"
    PAUSED = "paused"
    RESUMED = "resumed"
    EXPIRED = "expired"
    STRIPE_PAID_TRANSITION = "stripe_paid_transition"
    STRIPE_CANCELLED_BEFORE_PAID = "stripe_cancelled_before_paid"
    NOTES_UPDATED = "notes_updated"


class PilotExtendBody(BaseModel):
    reason: str = Field(..., min_length=3, max_length=2000)
    days: Optional[int] = Field(default=None, ge=1, le=3650)
    weeks: Optional[int] = Field(default=None, ge=1, le=520)
    months: Optional[int] = Field(default=None, ge=1, le=120)
    until: Optional[datetime] = None

    @model_validator(mode="after")
    def _one_extension_mode(self) -> "PilotExtendBody":
        modes = sum(
            1
            for x in (self.days, self.weeks, self.months, self.until)
            if x is not None and x != 0
        )
        if modes != 1:
            raise ValueError("Specify exactly one of: days, weeks, months, or until")
        return self


class PilotSetExpiryBody(BaseModel):
    reason: str = Field(..., min_length=3, max_length=2000)
    expires_at: datetime


class PilotCancelBody(BaseModel):
    reason: str = Field(..., min_length=3, max_length=2000)
    cancel_stripe_subscription: bool = False
    revoke_access_immediately: bool = False


class PilotConvertBody(BaseModel):
    reason: str = Field(..., min_length=3, max_length=2000)


class PilotCompBody(BaseModel):
    reason: str = Field(..., min_length=10, max_length=2000)
    notes: Optional[str] = Field(default=None, max_length=4000)
    review_expires_at: Optional[datetime] = Field(
        default=None,
        description="Optional governance review date for comped access.",
    )


class PilotNotesBody(BaseModel):
    notes: str = Field(..., max_length=4000)


class PilotSetOnboardingFeeBody(BaseModel):
    """Admin override for pilot onboarding/setup fee policy."""
    reason: str = Field(..., min_length=3, max_length=2000)
    onboarding_fee_policy: PilotOnboardingFeePolicy
    waiver_reason: Optional[str] = Field(default=None, max_length=2000)
    deferred_until: Optional[datetime] = None
    mark_charged: bool = Field(
        default=False,
        description="When true, records onboarding as charged now (admin manual capture).",
    )


class PilotCreateOverrideBody(BaseModel):
    """Admin-initiated pilot state on an existing client (no new checkout)."""
    reason: str = Field(..., min_length=3, max_length=2000)
    program_type: str = Field(default="FOUNDING_PILOT", max_length=64)
    duration_months: int = Field(default=2, ge=1, le=120)
    expires_at: Optional[datetime] = None
    discount_percent: int = Field(default=100, ge=1, le=100)
    invite_code: Optional[str] = Field(default=None, max_length=64)
    notes: Optional[str] = Field(default=None, max_length=4000)
