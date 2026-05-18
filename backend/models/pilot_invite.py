"""Founding pilot invite codes — live Stripe checkout with authorised Stripe-native discounts."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class PilotInviteStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    EXPIRED = "expired"


class PilotInviteDiscountMode(str, Enum):
    COUPON = "coupon"
    PROMOTION_CODE = "promotion_code"
    MANUAL_SESSION_DISCOUNT = "manual_session_discount"


class PilotInviteDiscountType(str, Enum):
    PERCENT = "percent"


class PilotInviteDiscountDuration(str, Enum):
    """Mirrors Stripe coupon duration; configured in Stripe Dashboard, stored here for tagging/UX."""
    FOREVER = "forever"
    ONCE = "once"
    REPEATING = "repeating"


class PilotOnboardingFeePolicy(str, Enum):
    """How onboarding/setup fee is handled at checkout and thereafter."""
    WAIVED = "waived"
    DEFERRED = "deferred"
    CHARGE_NOW = "charge_now"
    DISCOUNT = "discount"


class PilotInviteCodeCreate(BaseModel):
    code: str = Field(..., min_length=4, max_length=64)
    program_type: str = Field(default="FOUNDING_PILOT", max_length=64)
    applies_to_plan_codes: List[str] = Field(
        default_factory=lambda: ["PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO"]
    )
    max_uses: int = Field(default=1, ge=1, le=100_000)
    expires_at: Optional[datetime] = None
    email_restriction: Optional[str] = Field(default=None, max_length=320)
    stripe_coupon_id: Optional[str] = Field(default=None, max_length=128)
    stripe_promotion_code_id: Optional[str] = Field(default=None, max_length=128)
    discount_mode: PilotInviteDiscountMode = PilotInviteDiscountMode.COUPON
    discount_type: PilotInviteDiscountType = PilotInviteDiscountType.PERCENT
    discount_percent: int = Field(default=100, ge=1, le=100)
    discount_duration: PilotInviteDiscountDuration = PilotInviteDiscountDuration.REPEATING
    discount_duration_in_months: Optional[int] = Field(default=2, ge=1, le=36)
    waive_onboarding_fee: bool = Field(default=True)
    onboarding_fee_policy: PilotOnboardingFeePolicy = Field(default=PilotOnboardingFeePolicy.WAIVED)
    onboarding_fee_discount_percent: Optional[int] = Field(default=None, ge=1, le=100)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_by: Optional[str] = Field(default=None, max_length=128)

    @field_validator("code")
    @classmethod
    def _strip_code(cls, v: str) -> str:
        return (v or "").strip()

    @model_validator(mode="after")
    def _validate_discount_shape(self) -> "PilotInviteCodeCreate":
        if self.discount_duration == PilotInviteDiscountDuration.REPEATING:
            if not self.discount_duration_in_months or self.discount_duration_in_months < 1:
                raise ValueError("discount_duration_in_months is required (>= 1) when discount_duration is repeating")
        elif self.discount_duration == PilotInviteDiscountDuration.FOREVER:
            if self.discount_duration_in_months not in (None, 0):
                raise ValueError("discount_duration_in_months must not be set when discount_duration is forever")
        elif self.discount_duration == PilotInviteDiscountDuration.ONCE:
            if self.discount_duration_in_months not in (None, 0):
                raise ValueError("discount_duration_in_months must not be set when discount_duration is once")
        return self


class PilotInviteCodeUpdate(BaseModel):
    status: Optional[PilotInviteStatus] = None
    max_uses: Optional[int] = Field(default=None, ge=1, le=100_000)
    expires_at: Optional[datetime] = None
    email_restriction: Optional[str] = Field(default=None, max_length=320)
    stripe_coupon_id: Optional[str] = None
    stripe_promotion_code_id: Optional[str] = None
    discount_mode: Optional[PilotInviteDiscountMode] = None
    discount_type: Optional[PilotInviteDiscountType] = None
    discount_percent: Optional[int] = Field(default=None, ge=1, le=100)
    discount_duration: Optional[PilotInviteDiscountDuration] = None
    discount_duration_in_months: Optional[int] = Field(default=None, ge=1, le=36)
    waive_onboarding_fee: Optional[bool] = None
    onboarding_fee_policy: Optional[PilotOnboardingFeePolicy] = None
    onboarding_fee_discount_percent: Optional[int] = Field(default=None, ge=1, le=100)
    metadata: Optional[Dict[str, Any]] = None


class PilotInviteValidateBody(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    plan_code: str = Field(..., min_length=1, max_length=64)
    email: Optional[str] = Field(default=None, max_length=320)


class PilotInviteValidateResponse(BaseModel):
    valid: bool
    message: str
    program_type: Optional[str] = None
    plan_code: Optional[str] = None
    discount_applied: bool = False
    discount_percent: Optional[int] = None
    discount_duration: Optional[str] = None
    discount_duration_in_months: Optional[int] = None
    expected_transition_to_paid: bool = False
    headline: Optional[str] = None
    detail: Optional[str] = None
    onboarding_fee_policy: Optional[str] = None
    onboarding_fee_waived: bool = False


class PilotInvitePublicError(Exception):
    """Raised when invite validation fails; carries safe client error_code."""

    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(message)
