"""Pilot Stripe coupon validation — platform live/test mode vs coupon livemode."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from models.pilot_invite import PilotInviteDiscountDuration
from services.pilot_stripe_coupon_validation import (
    PilotStripeCouponValidationError,
    validate_pilot_stripe_discount_config,
)
from services.stripe_mode_authority import (
    StripeModeConfigurationError,
    assert_stripe_object_mode,
    normalize_stripe_mode,
)


def _invite_fields(**overrides):
    base = {
        "discount_percent": 100,
        "discount_duration": PilotInviteDiscountDuration.REPEATING.value,
        "discount_duration_in_months": 2,
        "discount_type": "percent",
    }
    base.update(overrides)
    return base


def _coupon(**overrides):
    base = {
        "id": "85x6smtg",
        "valid": True,
        "percent_off": 100,
        "duration": "repeating",
        "duration_in_months": 2,
        "livemode": True,
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def _stripe_env(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "live")
    monkeypatch.setenv("STRIPE_SECRET_KEY_LIVE", "sk_live_testkey")


@pytest.mark.asyncio
async def test_live_coupon_live_platform_mode_succeeds():
    with patch(
        "services.pilot_stripe_coupon_validation.stripe.Coupon.retrieve",
        return_value=_coupon(livemode=True),
    ):
        await validate_pilot_stripe_discount_config(
            stripe_coupon_id="85x6smtg",
            stripe_promotion_code_id=None,
            discount_mode="coupon",
            invite_fields=_invite_fields(),
        )


@pytest.mark.asyncio
async def test_live_coupon_test_platform_mode_rejected(monkeypatch):
    monkeypatch.setenv("STRIPE_MODE", "test")
    monkeypatch.setenv("STRIPE_SECRET_KEY_TEST", "sk_test_abc")
    monkeypatch.delenv("STRIPE_SECRET_KEY_LIVE", raising=False)

    with patch(
        "services.pilot_stripe_coupon_validation.stripe.Coupon.retrieve",
        return_value=_coupon(livemode=True),
    ):
        with pytest.raises(PilotStripeCouponValidationError) as exc:
            await validate_pilot_stripe_discount_config(
                stripe_coupon_id="85x6smtg",
                stripe_promotion_code_id=None,
                discount_mode="coupon",
                invite_fields=_invite_fields(),
            )
    assert "Stripe coupon is live mode but platform STRIPE_MODE is test" in str(exc.value)


@pytest.mark.asyncio
async def test_test_coupon_live_platform_mode_rejected():
    with patch(
        "services.pilot_stripe_coupon_validation.stripe.Coupon.retrieve",
        return_value=_coupon(livemode=False),
    ):
        with pytest.raises(PilotStripeCouponValidationError) as exc:
            await validate_pilot_stripe_discount_config(
                stripe_coupon_id="test_coupon",
                stripe_promotion_code_id=None,
                discount_mode="coupon",
                invite_fields=_invite_fields(),
            )
    msg = str(exc.value)
    assert "test" in msg.lower()
    assert "live" in msg.lower()
    assert "platform STRIPE_MODE is coupon" not in msg


def test_normalize_stripe_mode_rejects_discount_mode_string():
    with pytest.raises(StripeModeConfigurationError, match="Invalid Stripe mode 'coupon'"):
        normalize_stripe_mode("coupon", source="caller")


def test_assert_stripe_object_mode_rejects_invalid_expected_mode():
    with pytest.raises(StripeModeConfigurationError, match="Invalid Stripe mode"):
        assert_stripe_object_mode(
            {"livemode": True},
            expected_mode="coupon",
            object_type="coupon",
        )


def test_error_message_reports_coupon_and_platform_modes():
    with pytest.raises(Exception) as exc:
        assert_stripe_object_mode(
            {"livemode": True},
            expected_mode="test",
            object_type="coupon",
        )
    assert "Stripe coupon is live mode but platform STRIPE_MODE is test" in str(exc.value)
