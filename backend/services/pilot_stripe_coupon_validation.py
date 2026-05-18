"""
Stripe coupon/promotion validation for pilot invites — block misconfigured discounts before go-live.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import stripe

from models.pilot_invite import PilotInviteDiscountDuration, PilotInviteDiscountMode
from services.pilot_invite_service import discount_config_from_doc
from services.stripe_mode_authority import (
    assert_stripe_object_mode,
    configure_stripe_sdk,
    enhance_stripe_not_found_error,
    get_stripe_mode,
)

logger = logging.getLogger(__name__)


class PilotStripeCouponValidationError(ValueError):
    """Admin-safe validation failure for pilot Stripe discount configuration."""

    def __init__(self, message: str, *, details: Optional[List[str]] = None):
        self.details = details or []
        super().__init__(message)


def _duration_matches(coupon: Dict[str, Any], expected: str, months: int) -> bool:
    dur = str(coupon.get("duration") or "").lower()
    if expected == PilotInviteDiscountDuration.REPEATING.value:
        return dur == "repeating" and int(coupon.get("duration_in_months") or 0) == months
    if expected == PilotInviteDiscountDuration.FOREVER.value:
        return dur == "forever"
    if expected == PilotInviteDiscountDuration.ONCE.value:
        return dur == "once"
    return False


async def validate_pilot_stripe_discount_config(
    *,
    stripe_coupon_id: Optional[str],
    stripe_promotion_code_id: Optional[str],
    discount_mode: str,
    invite_fields: Dict[str, Any],
) -> None:
    """
    Retrieve Stripe coupon (via coupon id or promotion code) and verify it matches invite record.

    Raises PilotStripeCouponValidationError with operator-safe messages.
    """
    configure_stripe_sdk()
    platform_stripe_mode = get_stripe_mode()

    cfg = discount_config_from_doc(invite_fields)
    expected_percent = cfg["discount_percent"]
    expected_duration = cfg["discount_duration"]
    expected_months = cfg["discount_duration_in_months"]
    discount_mode_key = str(discount_mode or "").lower()

    coupon_id = (stripe_coupon_id or "").strip()
    promo_id = (stripe_promotion_code_id or "").strip()

    if discount_mode_key == PilotInviteDiscountMode.PROMOTION_CODE.value:
        if not promo_id:
            raise PilotStripeCouponValidationError(
                "Promotion code mode requires stripe_promotion_code_id."
            )
        try:
            promo = stripe.PromotionCode.retrieve(promo_id, expand=["coupon"])
        except stripe.error.StripeError as e:
            raise PilotStripeCouponValidationError(
                enhance_stripe_not_found_error(e, mode=mode, object_type="promotion code")
            ) from e
        if not promo.get("active", True):
            raise PilotStripeCouponValidationError("Stripe promotion code is not active.")
        coupon = promo.get("coupon")
        if isinstance(coupon, str):
            coupon = stripe.Coupon.retrieve(coupon)
        elif hasattr(coupon, "to_dict"):
            coupon = coupon.to_dict()
    else:
        if not coupon_id:
            raise PilotStripeCouponValidationError(
                "Coupon mode requires stripe_coupon_id."
            )
        try:
            coupon = stripe.Coupon.retrieve(coupon_id)
        except stripe.error.StripeError as e:
            raise PilotStripeCouponValidationError(
                f"Stripe coupon could not be loaded: {e.user_message or str(e)}"
            ) from e
        if hasattr(coupon, "to_dict"):
            coupon = coupon.to_dict()

    if not coupon:
        raise PilotStripeCouponValidationError("Stripe coupon not found for this invite configuration.")

    if not coupon.get("valid", True):
        raise PilotStripeCouponValidationError("Stripe coupon is not valid (expired or disabled).")

    try:
        assert_stripe_object_mode(
            coupon, expected_mode=platform_stripe_mode, object_type="coupon"
        )
    except Exception as e:
        raise PilotStripeCouponValidationError(str(e)) from e

    errors: List[str] = []
    percent_off = coupon.get("percent_off")
    if percent_off is None:
        errors.append("Coupon must be percentage-based (percent_off).")
    elif int(percent_off) != int(expected_percent):
        errors.append(
            f"Coupon percent_off is {percent_off}% but invite expects {expected_percent}%."
        )

    if not _duration_matches(coupon, expected_duration, expected_months):
        if expected_duration == PilotInviteDiscountDuration.REPEATING.value:
            errors.append(
                f"Coupon duration must be repeating for {expected_months} month(s); "
                f"Stripe has duration={coupon.get('duration')} "
                f"duration_in_months={coupon.get('duration_in_months')}."
            )
        else:
            errors.append(
                f"Coupon duration must be {expected_duration}; Stripe has duration={coupon.get('duration')}."
            )

    applies_to = coupon.get("applies_to") or {}
    products = applies_to.get("products") or []
    if products:
        logger.info(
            "Pilot coupon %s restricted to products %s — verify CVP subscription prices are included",
            coupon.get("id"),
            products,
        )

    if errors:
        raise PilotStripeCouponValidationError(
            "Stripe coupon does not match invite discount configuration.",
            details=errors,
        )
