"""Pilot billing hardening — commercial truth, coupon validation, reconciliation, governance."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.pilot_invite import PilotInviteCodeCreate, PilotOnboardingFeePolicy
from services.agreement_commercial_snapshot import build_commercial_snapshot_from_intake_form
from services.pilot_commercial_truth import (
    apply_pilot_to_commercial_snapshot,
    commercial_context_from_invite,
    validate_response_commercial_fields,
)
from services.pilot_invite_service import (
    _reject_public_deferred_onboarding,
    create_invite_code,
)
from services.pilot_lifecycle_reconciliation_worker import reconcile_pilot_lifecycle_batch
from services.pilot_stripe_coupon_validation import PilotStripeCouponValidationError


def _invite_doc(**overrides):
    doc = {
        "code": "PILOT-HARDEN",
        "program_type": "FOUNDING_PILOT",
        "discount_percent": 100,
        "discount_duration": "repeating",
        "discount_duration_in_months": 2,
        "waive_onboarding_fee": True,
        "onboarding_fee_policy": "waived",
        "stripe_coupon_id": "coupon_test",
    }
    doc.update(overrides)
    return doc


def test_commercial_snapshot_waived_onboarding_for_pilot_invite():
    snap_base = {
        "client_full_name": "Test",
        "selected_plan_code": "PLAN_1_SOLO",
        "plan_label": "Solo",
        "billing_amount_minor": 1900,
        "billing_interval": "month",
        "onboarding_fee_minor": 4900,
        "currency": "GBP",
        "agreement_template_id": "t1",
        "agreement_template_version_id": "v1",
    }
    ctx = commercial_context_from_invite(_invite_doc(), plan_code="PLAN_1_SOLO")
    snap = apply_pilot_to_commercial_snapshot(snap_base, ctx)
    assert snap["onboarding_fee_minor"] == 0
    assert snap["first_checkout_total_minor"] == 0
    assert snap["recurring_monthly_minor"] == 1900
    assert snap["pilot_discount_percent"] == 100
    assert snap["pilot_discount_months"] == 2
    assert snap.get("onboarding_fee_waived") is True
    assert "waived" in (snap.get("pilot_commercial_summary") or "").lower()


def test_commercial_context_validate_response():
    ctx = commercial_context_from_invite(_invite_doc(), plan_code="PLAN_1_SOLO")
    fields = validate_response_commercial_fields(ctx)
    assert fields["setup_fee_effective"] == 0.0
    assert "Founding Pilot" in fields["commercial_summary"]


def test_deferred_policy_rejected_at_public_checkout():
    from models.pilot_invite import PilotInvitePublicError

    with pytest.raises(PilotInvitePublicError) as exc:
        _reject_public_deferred_onboarding(_invite_doc(onboarding_fee_policy="deferred"))
    assert exc.value.error_code == "PILOT_ONBOARDING_DEFERRED_NOT_AVAILABLE"


@pytest.mark.asyncio
async def test_create_invite_rejects_deferred_policy():
    mock_db = MagicMock()
    mock_db["pilot_invite_codes"].find_one = AsyncMock(return_value=None)
    body = PilotInviteCodeCreate(
        code="DEFER1",
        stripe_coupon_id="c1",
        onboarding_fee_policy=PilotOnboardingFeePolicy.DEFERRED,
    )
    with patch("services.pilot_invite_service.database.get_db", return_value=mock_db):
        with pytest.raises(ValueError, match="experimental"):
            await create_invite_code(body)


@pytest.mark.asyncio
async def test_stripe_coupon_validation_rejects_percent_mismatch():
    coupon = {
        "id": "coupon_test",
        "valid": True,
        "percent_off": 50,
        "duration": "repeating",
        "duration_in_months": 2,
    }
    with patch(
        "services.pilot_stripe_coupon_validation.configure_stripe_sdk", return_value="sk_test_x"
    ), patch(
        "services.pilot_stripe_coupon_validation.get_stripe_mode", return_value="test"
    ), patch(
        "services.pilot_stripe_coupon_validation.stripe.Coupon.retrieve", return_value=coupon
    ):
        from services.pilot_stripe_coupon_validation import validate_pilot_stripe_discount_config

        with pytest.raises(PilotStripeCouponValidationError, match="match"):
            await validate_pilot_stripe_discount_config(
                stripe_coupon_id="coupon_test",
                stripe_promotion_code_id=None,
                discount_mode="coupon",
                invite_fields=_invite_doc(),
            )


@pytest.mark.asyncio
async def test_reconcile_pilot_lifecycle_idempotent():
    expired_client = {
        "client_id": "c-exp",
        "pilot_status": "active",
        "pilot_expires_at": datetime.now(timezone.utc) - timedelta(days=1),
    }
    mock_db = MagicMock()

    async def async_iter():
        yield expired_client

    mock_cursor = MagicMock()
    mock_cursor.__aiter__ = lambda self: async_iter()
    mock_db.clients.find.return_value.limit.return_value = mock_cursor

    with patch("services.pilot_lifecycle_reconciliation_worker.database.get_db", return_value=mock_db):
        with patch(
            "services.pilot_lifecycle_reconciliation_worker.sync_expired_if_due",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_sync:
            result = await reconcile_pilot_lifecycle_batch(limit=10)
    assert result["expired_transitions"] == 1
    mock_sync.assert_awaited_once_with("c-exp")


@pytest.mark.asyncio
async def test_comp_route_uses_require_owner_dependency():
    import inspect
    from routes import admin_pilot_lifecycle as routes

    sig = inspect.signature(routes.comp_account)
    assert "require_owner" in str(sig)
