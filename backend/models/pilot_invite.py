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


class PilotInviteCodeType(str, Enum):
    PRIVATE_INVITE = "private_invite"
    PUBLIC_PROMO = "public_promo"
    REFERRAL = "referral"
    PARTNER = "partner"
    INTERNAL_TEST = "internal_test"


class PilotCampaignStatus(str, Enum):
    """Lifecycle for publicly governed campaigns (private_invite uses not_applicable)."""
    NOT_APPLICABLE = "not_applicable"
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


class PilotCampaignState(str, Enum):
    """Campaign governance state. Existing campaign_status is kept for compatibility."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class PilotLaunchVisibility(str, Enum):
    PRIVATE = "private"
    RESTRICTED = "restricted"
    PUBLIC = "public"
    INTERNAL = "internal"


class PilotInviteCodeCreate(BaseModel):
    code: str = Field(default="", max_length=64)
    code_type: PilotInviteCodeType = Field(
        default=PilotInviteCodeType.PRIVATE_INVITE,
        description="private_invite = distribution link + manual entry; public_promo/referral/partner = campaign-governed",
    )
    is_publicly_enterable: bool = Field(
        default=False,
        description="When True, code may be typed during intake/checkout (public promo family only).",
    )
    public_entry_enabled: bool = Field(
        default=False,
        description="Master switch for public/campaign codes (off by default).",
    )
    campaign_name: Optional[str] = Field(default=None, max_length=200)
    public_description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional shopper-facing description for public promo entry UI.",
    )
    campaign_status: PilotCampaignStatus = Field(
        default=PilotCampaignStatus.NOT_APPLICABLE,
        description="Active public/referral/partner codes must be ACTIVE with public_entry_enabled.",
    )
    campaign_state: PilotCampaignState = Field(default=PilotCampaignState.DRAFT)
    launch_visibility: PilotLaunchVisibility = Field(default=PilotLaunchVisibility.PRIVATE)
    campaign_config_version: int = Field(default=1, ge=1, le=10_000)
    campaign_locked_at: Optional[datetime] = None
    campaign_launched_at: Optional[datetime] = None
    analytics_family: Optional[str] = Field(default=None, max_length=64)
    max_uses_per_account: Optional[int] = Field(default=None, ge=1, le=1_000_000)
    internal_live_test: bool = Field(default=False)
    auto_generate: bool = Field(
        default=False,
        description="When True, backend allocates a unique code (code field may be empty).",
    )
    first_time_customer_only: bool = Field(default=False)
    one_redemption_per_email: bool = Field(default=False)
    one_redemption_per_customer: bool = Field(default=False)
    one_redemption_per_payment_method: bool = Field(default=False)
    allowed_email_domains: List[str] = Field(default_factory=list)
    blocked_email_domains: List[str] = Field(default_factory=list)
    max_uses_per_day: Optional[int] = Field(default=None, ge=1, le=1_000_000)
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

    @field_validator("allowed_email_domains", "blocked_email_domains", mode="before")
    @classmethod
    def _coerce_domain_lists(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip().lower().lstrip("@") for x in v if str(x).strip()]
        s = str(v).strip()
        if not s:
            return []
        import re

        return [p.strip().lower().lstrip("@") for p in re.split(r"[\s,;]+", s) if p.strip()]

    @model_validator(mode="after")
    def _code_or_auto_generate(self) -> "PilotInviteCodeCreate":
        c = (self.code or "").strip()
        if not self.auto_generate and len(c) < 4:
            raise ValueError("code is required (min 4 chars) unless auto_generate is True")
        return self

    @model_validator(mode="after")
    def _sync_campaign_defaults_for_private(self) -> "PilotInviteCodeCreate":
        if self.code_type == PilotInviteCodeType.INTERNAL_TEST:
            if self.max_uses > 10:
                raise ValueError("internal_test campaigns are capped at max_uses=10")
            if self.max_uses == 1:
                self.max_uses = 5
            self.is_publicly_enterable = False
            self.public_entry_enabled = False
            self.launch_visibility = PilotLaunchVisibility.INTERNAL
            self.analytics_family = "internal_test"
            self.internal_live_test = True
            self.onboarding_fee_policy = PilotOnboardingFeePolicy.WAIVED
            self.waive_onboarding_fee = True
        elif self.code_type == PilotInviteCodeType.PRIVATE_INVITE:
            # Private founding invites ignore public-governance fields at runtime
            self.analytics_family = self.analytics_family or PilotInviteCodeType.PRIVATE_INVITE.value
        elif self.code_type in (
            PilotInviteCodeType.PUBLIC_PROMO,
            PilotInviteCodeType.REFERRAL,
            PilotInviteCodeType.PARTNER,
        ):
            if self.campaign_status == PilotCampaignStatus.NOT_APPLICABLE:
                raise ValueError("campaign_status must be set for public_promo, referral, or partner codes")
            self.analytics_family = self.analytics_family or self.code_type.value
            if self.public_entry_enabled and self.launch_visibility == PilotLaunchVisibility.PRIVATE:
                self.launch_visibility = PilotLaunchVisibility.PUBLIC
        return self

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
    code_type: Optional[PilotInviteCodeType] = None
    is_publicly_enterable: Optional[bool] = None
    public_entry_enabled: Optional[bool] = None
    campaign_name: Optional[str] = Field(default=None, max_length=200)
    public_description: Optional[str] = Field(default=None, max_length=500)
    campaign_status: Optional[PilotCampaignStatus] = None
    campaign_state: Optional[PilotCampaignState] = None
    launch_visibility: Optional[PilotLaunchVisibility] = None
    campaign_config_version: Optional[int] = Field(default=None, ge=1, le=10_000)
    campaign_locked_at: Optional[datetime] = None
    campaign_launched_at: Optional[datetime] = None
    analytics_family: Optional[str] = Field(default=None, max_length=64)
    max_uses_per_account: Optional[int] = Field(default=None, ge=1, le=1_000_000)
    internal_live_test: Optional[bool] = None
    expires_at: Optional[datetime] = None
    deactivated_by: Optional[str] = Field(default=None, max_length=320)
    deactivated_reason: Optional[str] = Field(default=None, max_length=500)
    archived: Optional[bool] = None
    first_time_customer_only: Optional[bool] = None
    one_redemption_per_email: Optional[bool] = None
    one_redemption_per_customer: Optional[bool] = None
    one_redemption_per_payment_method: Optional[bool] = None
    allowed_email_domains: Optional[List[str]] = None
    blocked_email_domains: Optional[List[str]] = None
    max_uses_per_day: Optional[int] = Field(default=None, ge=1, le=1_000_000)
    max_uses: Optional[int] = Field(default=None, ge=1, le=100_000)
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

    @field_validator("allowed_email_domains", "blocked_email_domains", mode="before")
    @classmethod
    def _coerce_domain_lists_update(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, list):
            return [str(x).strip().lower().lstrip("@") for x in v if str(x).strip()]
        s = str(v).strip()
        if not s:
            return []
        import re

        return [p.strip().lower().lstrip("@") for p in re.split(r"[\s,;]+", s) if p.strip()]


class PilotInviteValidateBody(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    plan_code: str = Field(..., min_length=1, max_length=64)
    email: Optional[str] = Field(default=None, max_length=320)
    entry_channel: str = Field(
        default="manual",
        max_length=16,
        description="manual = typed code; link = from invite URL (distribution link).",
    )

    @field_validator("entry_channel")
    @classmethod
    def _entry_channel_norm(cls, v: Any) -> str:
        e = str(v or "manual").strip().lower()
        return e if e in ("manual", "link") else "manual"


class PilotInviteValidateResponse(BaseModel):
    valid: bool
    message: str
    code_type: Optional[str] = None
    campaign_name: Optional[str] = None
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
    setup_fee_effective: Optional[float] = None
    monthly_price_after_pilot: Optional[float] = None
    first_payment_estimate: Optional[float] = None
    commercial_summary: Optional[str] = None


class PilotInvitePublicError(Exception):
    """Raised when invite validation fails; carries safe client error_code."""

    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(message)
