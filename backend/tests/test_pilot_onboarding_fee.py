"""Pilot onboarding/setup fee policy — checkout, webhook, and admin overrides."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.pilot_invite import PilotInviteCodeCreate, PilotOnboardingFeePolicy
from services.pilot_invite_service import _build_validate_response, build_checkout_pilot_metadata
from services.pilot_onboarding_fee import (
    resolve_checkout_onboarding,
    resolve_webhook_onboarding_fee,
)


def _active_invite_doc(**overrides):
    doc = {
        "invite_code_id": "inv-onb-001",
        "code": "PILOTONB",
        "status": "active",
        "program_type": "FOUNDING_PILOT",
        "applies_to_plan_codes": ["PLAN_1_SOLO"],
        "max_uses": 5,
        "used_count": 0,
        "stripe_coupon_id": "coupon_test_100",
        "discount_duration": "repeating",
        "discount_duration_in_months": 2,
        "discount_percent": 100,
        "waive_onboarding_fee": True,
        "onboarding_fee_policy": "waived",
    }
    doc.update(overrides)
    return doc


def test_normal_checkout_includes_onboarding_line_item():
    include, policy, meta = resolve_checkout_onboarding(
        pilot_invite_doc=None,
        plan_code="PLAN_1_SOLO",
        already_paid=False,
        onboarding_price_id="price_onboard",
    )
    assert include is True
    assert policy == PilotOnboardingFeePolicy.CHARGE_NOW
    assert meta["onboarding_fee_policy"] == "charge_now"
    assert meta["onboarding_fee_waived"] == "false"


def test_pilot_waived_excludes_onboarding_line_item():
    include, policy, meta = resolve_checkout_onboarding(
        pilot_invite_doc=_active_invite_doc(),
        plan_code="PLAN_1_SOLO",
        already_paid=False,
        onboarding_price_id="price_onboard",
    )
    assert include is False
    assert policy == PilotOnboardingFeePolicy.WAIVED
    assert meta["onboarding_fee_policy"] == "waived"
    assert meta["onboarding_fee_waived"] == "true"


def test_pilot_deferred_excludes_onboarding_line_item():
    include, policy, _meta = resolve_checkout_onboarding(
        pilot_invite_doc=_active_invite_doc(onboarding_fee_policy="deferred", waive_onboarding_fee=False),
        plan_code="PLAN_1_SOLO",
        already_paid=False,
        onboarding_price_id="price_onboard",
    )
    assert include is False
    assert policy == PilotOnboardingFeePolicy.DEFERRED


def test_already_paid_skips_onboarding():
    include, _, _ = resolve_checkout_onboarding(
        pilot_invite_doc=None,
        plan_code="PLAN_1_SOLO",
        already_paid=True,
        onboarding_price_id="price_onboard",
    )
    assert include is False


def test_webhook_waived_pilot_marks_onboarding_paid_without_line_items():
    paid, amount, inv = resolve_webhook_onboarding_fee(
        session_metadata={
            "onboarding_fee_policy": "waived",
            "onboarding_fee_waived": "true",
            "program_type": "FOUNDING_PILOT",
        },
        client=None,
        session_line_items=None,
        expected_onboarding_price_id="price_onboard",
    )
    assert paid is True
    assert amount == 0
    assert inv is None


def test_webhook_missing_line_items_does_not_assume_paid_for_normal():
    paid, amount, _ = resolve_webhook_onboarding_fee(
        session_metadata={"onboarding_fee_policy": "charge_now", "onboarding_fee_waived": "false"},
        client=None,
        session_line_items=None,
        expected_onboarding_price_id="price_onboard",
    )
    assert paid is False
    assert amount is None


def test_webhook_detects_onboarding_from_line_items():
    paid, amount, _ = resolve_webhook_onboarding_fee(
        session_metadata={},
        client=None,
        session_line_items={
            "data": [
                {"price": {"id": "price_sub"}, "amount": 1900},
                {"price": {"id": "price_onboard"}, "amount": 4900},
            ]
        },
        expected_onboarding_price_id="price_onboard",
    )
    assert paid is True
    assert amount == 4900


def test_validate_response_includes_onboarding_waiver():
    resp = _build_validate_response(_active_invite_doc(), "PLAN_1_SOLO")
    assert resp.onboarding_fee_waived is True
    assert resp.onboarding_fee_policy == "waived"
    assert "onboarding fee is waived" in (resp.detail or "").lower()


def test_checkout_metadata_merges_pilot_duration():
    meta = build_checkout_pilot_metadata(_active_invite_doc(), plan_code="PLAN_1_SOLO")
    assert meta["pilot_duration_months"] == "2"
    assert meta["pilot_discount_months"] == "2"


@pytest.mark.asyncio
async def test_admin_set_onboarding_fee_policy_waive():
    from services import pilot_lifecycle_service as pls

    before = {
        "client_id": "c-pilot",
        "pilot_status": "active",
        "pilot_program_type": "FOUNDING_PILOT",
        "billing_plan": "PLAN_1_SOLO",
    }
    with patch.object(pls, "_load_client", AsyncMock(return_value=before)):
        with patch.object(pls, "_persist_transition", AsyncMock(return_value={**before, "onboarding_fee_waived": True})):
            with patch("services.pilot_lifecycle_service.database.get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_db.client_billing.update_one = AsyncMock()
                mock_get_db.return_value = mock_db
                doc = await pls.admin_set_onboarding_fee_policy(
                    client_id="c-pilot",
                    actor_id="admin-1",
                    actor_email="admin@example.com",
                    policy="waived",
                    reason="Founding pilot waiver",
                    waiver_reason="Executive approval",
                )
    assert doc.get("onboarding_fee_waived") is True
    mock_db.client_billing.update_one.assert_awaited()
    billing_set = mock_db.client_billing.update_one.call_args[0][1]["$set"]
    assert billing_set.get("onboarding_fee_paid") is True


def test_pilot_invite_create_defaults_onboarding_waived():
    body = PilotInviteCodeCreate(code="NEW1", stripe_coupon_id="c1")
    assert body.waive_onboarding_fee is True
    assert body.onboarding_fee_policy == PilotOnboardingFeePolicy.WAIVED
