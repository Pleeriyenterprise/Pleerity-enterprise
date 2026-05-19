"""Campaign governance hardening for pilot invite / promo codes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.pilot_invite import (
    PilotInviteCodeCreate,
    PilotInviteCodeType,
    PilotInviteCodeUpdate,
    PilotInviteDiscountDuration,
)
from services import pilot_lifecycle_service as pls
from services.pilot_invite_service import (
    COL_CODES,
    COL_REDEMPTIONS,
    build_invite_distribution,
    build_redeemed_campaign_snapshot,
    create_invite_code,
    update_invite_code,
)


def _collection_mock() -> MagicMock:
    return MagicMock()


@pytest.mark.asyncio
async def test_internal_test_defaults_are_backend_enforced():
    db = {COL_CODES: _collection_mock()}
    db[COL_CODES].find_one = AsyncMock(return_value=None)
    db[COL_CODES].insert_one = AsyncMock()

    body = PilotInviteCodeCreate(
        code="PILOTINT-LIVE",
        code_type=PilotInviteCodeType.INTERNAL_TEST,
        stripe_coupon_id="coupon_internal",
        discount_duration=PilotInviteDiscountDuration.REPEATING,
        discount_duration_in_months=1,
    )

    with patch("services.pilot_invite_service.database.get_db", return_value=db):
        with patch(
            "services.pilot_stripe_coupon_validation.validate_pilot_stripe_discount_config",
            new_callable=AsyncMock,
        ):
            doc = await create_invite_code(body)

    assert doc["max_uses"] == 5
    assert doc["public_entry_enabled"] is False
    assert doc["is_publicly_enterable"] is False
    assert doc["onboarding_fee_policy"] == "waived"
    assert doc["launch_visibility"] == "internal"
    assert doc["analytics_family"] == "internal_test"


@pytest.mark.asyncio
async def test_update_validates_before_persistence_for_internal_cap():
    current = {
        "invite_code_id": "inv-internal",
        "code": "PILOTINT-LIVE",
        "status": "active",
        "code_type": "internal_test",
        "max_uses": 5,
        "used_count": 0,
        "discount_duration": "repeating",
        "discount_duration_in_months": 1,
        "discount_percent": 100,
        "discount_type": "percent",
        "discount_mode": "coupon",
        "onboarding_fee_policy": "waived",
        "waive_onboarding_fee": True,
        "public_entry_enabled": False,
        "is_publicly_enterable": False,
        "analytics_family": "internal_test",
        "launch_visibility": "internal",
    }
    db = {COL_CODES: _collection_mock(), COL_REDEMPTIONS: _collection_mock()}
    db[COL_CODES].find_one = AsyncMock(return_value=current)
    db[COL_CODES].find_one_and_update = AsyncMock()
    db[COL_REDEMPTIONS].count_documents = AsyncMock(return_value=0)

    with patch("services.pilot_invite_service.database.get_db", return_value=db):
        with pytest.raises(ValueError, match="max_uses=10"):
            await update_invite_code("PILOTINT-LIVE", PilotInviteCodeUpdate(max_uses=11))

    db[COL_CODES].find_one_and_update.assert_not_awaited()


def test_redeemed_campaign_snapshot_is_immutable_copy():
    invite_doc = {
        "invite_code_id": "inv-launch",
        "code": "LAUNCH2026",
        "code_type": "public_promo",
        "campaign_name": "Launch",
        "campaign_config_version": 1,
        "discount_duration": "repeating",
        "discount_duration_in_months": 2,
        "discount_percent": 100,
        "discount_type": "percent",
        "onboarding_fee_policy": "waived",
        "stripe_coupon_id": "coupon_v1",
        "analytics_family": "public_promo",
        "launch_visibility": "public",
    }

    snap = build_redeemed_campaign_snapshot(
        invite_doc,
        client_id="client-1",
        checkout_session_id="cs_1",
        plan_code="PLAN_1_SOLO",
    )
    invite_doc["campaign_config_version"] = 2
    invite_doc["discount_duration_in_months"] = 6
    invite_doc["stripe_coupon_id"] = "coupon_v2"

    assert snap["campaign_config_version"] == 1
    assert snap["discount_duration_in_months"] == 2
    assert snap["stripe_coupon_id"] == "coupon_v1"


def test_distribution_uses_canonical_intake_start_route():
    dist = build_invite_distribution(
        {"code": "FOUNDING-ABCD", "discount_duration": "repeating", "discount_duration_in_months": 2},
        base_url="https://app.example.com/",
        plan_code="PLAN_1_SOLO",
    )

    assert "/intake/start?" in dist["invite_url"]
    assert dist["canonical_intake_path"] == "/intake/start"


@pytest.mark.asyncio
async def test_extend_pilot_records_account_override_and_recalculates_projection():
    now = datetime.now(timezone.utc)
    client = {
        "client_id": "client-override",
        "pilot_status": "active",
        "pilot_expires_at": now + timedelta(days=30),
        "pilot_expected_first_paid_invoice_at": now + timedelta(days=30),
        "pilot_redeemed_campaign_snapshot_id": "snap-1",
        "pilot_analytics_family": "public_promo",
        "pilot_campaign_config_version": 1,
    }

    async def _fake_persist(**kwargs):
        return {**kwargs["before"], **kwargs["patch"]}

    with patch.object(pls, "_load_client", new_callable=AsyncMock, return_value=client):
        with patch.object(pls, "_persist_transition", new_callable=AsyncMock, side_effect=_fake_persist):
            with patch.object(pls, "_record_account_override", new_callable=AsyncMock) as record_override:
                result = await pls.extend_pilot(
                    client_id="client-override",
                    actor_id="admin-1",
                    actor_email="admin@example.com",
                    reason="Strategic account extension",
                    months=1,
                )

    assert result["pilot_status"] == "extended"
    assert result["pilot_expected_first_paid_invoice_at"] == result["pilot_extended_until"]
    assert result["pilot_original_expected_first_paid_invoice_at"] == client["pilot_expected_first_paid_invoice_at"]
    assert record_override.await_args.kwargs["override_type"] == "extension"
