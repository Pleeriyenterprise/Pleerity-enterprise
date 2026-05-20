"""Recovery-aware pilot redemption eligibility and lifecycle."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.pilot_invite import PilotInvitePublicError
from services.pilot_invite_code_governance import assert_abuse_rules
from services.pilot_invite_service import (
    COL_CODES,
    COL_REDEMPTIONS,
    admin_allow_redemption_retry,
    complete_redemption_after_provisioning,
    validate_invite_for_checkout,
)


def _active_invite_doc(**overrides):
    now = datetime.now(timezone.utc)
    doc = {
        "invite_code_id": "inv-test-001",
        "code": "PILOTTEST",
        "status": "active",
        "program_type": "FOUNDING_PILOT",
        "applies_to_plan_codes": ["PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO"],
        "max_uses": 5,
        "used_count": 0,
        "expires_at": now + timedelta(days=30),
        "email_restriction": None,
        "stripe_coupon_id": "coupon_test_100",
        "discount_mode": "coupon",
        "discount_percent": 100,
        "discount_duration": "repeating",
        "discount_duration_in_months": 2,
        "waive_onboarding_fee": True,
        "onboarding_fee_policy": "waived",
        "code_type": "private_invite",
    }
    doc.update(overrides)
    return doc


from services.pilot_redemption_lifecycle import PilotRedemptionStatus


def _async_empty_cursor():
    class _Cursor:
        def sort(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        async def to_list(self, length=None):
            return []

        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    return _Cursor()


def _fake_db_for_recovery(
    doc,
    *,
    redemptions=None,
    client_row=None,
    redemption_count=0,
):
    fdb = {}
    fdb[COL_CODES] = MagicMock()
    fdb[COL_CODES].find_one = AsyncMock(return_value=doc)
    fdb[COL_REDEMPTIONS] = MagicMock()
    fdb[COL_REDEMPTIONS].count_documents = AsyncMock(return_value=redemption_count)
    fdb[COL_REDEMPTIONS].find = MagicMock(return_value=_async_empty_cursor())
    fdb[COL_REDEMPTIONS].find_one = AsyncMock(return_value=redemptions[0] if redemptions else None)
    fdb[COL_REDEMPTIONS].update_many = AsyncMock(return_value=MagicMock(modified_count=0))
    fdb["pilot_redemption_eligibility_overrides"] = MagicMock()
    fdb["pilot_redemption_eligibility_overrides"].find = MagicMock(return_value=_async_empty_cursor())
    fdb["pilot_invite_validation_attempts"] = MagicMock()
    fdb["pilot_invite_validation_attempts"].insert_one = AsyncMock()
    fdb["clients"] = MagicMock()
    fdb["clients"].find_one = AsyncMock(return_value=client_row)
    fdb["clients"].find = MagicMock(return_value=_async_empty_cursor())
    return fdb


@pytest.mark.asyncio
async def test_first_time_blocks_only_after_redeemed_not_intake_client():
    doc = _active_invite_doc(first_time_customer_only=True, code_type="public_promo", public_entry_enabled=True, is_publicly_enterable=True, campaign_state="active")
    # Client exists from intake but no redeemed redemption / snapshot on record
    fdb = _fake_db_for_recovery(doc, redemption_count=0)

    async def _find_one_client(filter_doc, projection=None):
        if filter_doc.get("pilot_redeemed_campaign_snapshot_id"):
            return None
        if "$or" in filter_doc:
            return {"_id": "x", "email": "new@example.com"}
        return None

    fdb["clients"].find_one = AsyncMock(side_effect=_find_one_client)
    with patch("services.pilot_invite_service.database.get_db", return_value=fdb):
        with patch("services.pilot_redemption_eligibility_service.database.get_db", return_value=fdb):
            with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
                _, resp = await validate_invite_for_checkout(
                    code="PILOTTEST",
                    plan_code="PLAN_1_SOLO",
                    email="new@example.com",
                    entry_channel="manual",
                )
    assert resp.valid is True


@pytest.mark.asyncio
async def test_first_time_blocks_when_redeemed_redemption_exists():
    doc = _active_invite_doc(first_time_customer_only=True)
    fdb = _fake_db_for_recovery(doc, redemption_count=0)
    fdb["clients"].find_one = AsyncMock(
        side_effect=[
            None,
            {"_id": 1, "pilot_redeemed_campaign_snapshot_id": "snap-1"},
        ]
    )
    fdb[COL_REDEMPTIONS].find_one = AsyncMock(
        return_value={"status": PilotRedemptionStatus.REDEEMED.value, "redemption_email": "used@example.com"}
    )
    with patch("services.pilot_invite_service.database.get_db", return_value=fdb):
        with patch("services.pilot_redemption_eligibility_service.database.get_db", return_value=fdb):
            with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
                with pytest.raises(PilotInvitePublicError) as exc:
                    await validate_invite_for_checkout(
                        code="PILOTTEST",
                        plan_code="PLAN_1_SOLO",
                        email="used@example.com",
                    )
    assert exc.value.error_code == "PILOT_INVITE_NOT_FIRST_TIME_CUSTOMER"


@pytest.mark.asyncio
async def test_stale_pending_does_not_block_retry():
    doc = _active_invite_doc(one_redemption_per_email=True, code_type="public_promo", public_entry_enabled=True, is_publicly_enterable=True, campaign_state="active")
    fdb = _fake_db_for_recovery(doc, redemption_count=0)
    old_pending = {
        "status": "pending",
        "created_at": datetime.now(timezone.utc) - timedelta(days=5),
    }
    with patch(
        "services.pilot_redemption_eligibility_service.database.get_db",
        return_value=fdb,
    ):
        with patch(
            "services.pilot_invite_code_governance._expire_stale_pending_for_identity",
            new_callable=AsyncMock,
            return_value=1,
        ):
            await assert_abuse_rules(fdb, doc, email="retry@example.com", client_id="c1")


@pytest.mark.asyncio
async def test_complete_redemption_sets_redeemed_status():
    now = datetime.now(timezone.utc)
    redemption = {
        "redemption_id": "r1",
        "invite_code_id": "inv-test-001",
        "code": "PILOTTEST",
        "client_id": "c1",
        "checkout_session_id": "cs_1",
        "status": "pending",
    }
    invite = _active_invite_doc(used_count=0)

    class _Codes:
        find_one_and_update = AsyncMock(return_value=invite)

    class _Redemptions:
        find_one_and_update = AsyncMock(return_value=redemption)
        find_one = AsyncMock(return_value=None)

    fdb = {
        COL_CODES: _Codes(),
        COL_REDEMPTIONS: _Redemptions(),
        "pilot_redeemed_campaign_snapshots": MagicMock(),
        "clients": MagicMock(),
    }
    fdb["pilot_redeemed_campaign_snapshots"].update_one = AsyncMock()
    fdb["clients"].update_one = AsyncMock()
    with patch("services.pilot_invite_service.database.get_db", return_value=fdb):
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            ok = await complete_redemption_after_provisioning(checkout_session_id="cs_1")
    assert ok is True
    set_call = fdb[COL_REDEMPTIONS].find_one_and_update.call_args[0][1]["$set"]
    assert set_call["status"] == PilotRedemptionStatus.REDEEMED.value


@pytest.mark.asyncio
async def test_admin_allow_retry_revokes_incomplete():
    row = {
        "redemption_id": "r-retry",
        "invite_code_id": "inv-test-001",
        "code": "PILOTTEST",
        "client_id": "c1",
        "status": "provisioning_failed",
        "redemption_email": "u@example.com",
    }
    updated_row = {**row, "status": PilotRedemptionStatus.REVOKED.value}

    with patch(
        "services.pilot_invite_service.update_redemption_status",
        new_callable=AsyncMock,
        return_value=updated_row,
    ):
        with patch(
            "services.pilot_redemption_eligibility_service.create_eligibility_override",
            new_callable=AsyncMock,
            return_value={"override_id": "ov1"},
        ):
            with patch("services.pilot_invite_service.database.get_db") as mock_db:
                mock_db.return_value = MagicMock()
                mock_db.return_value[COL_REDEMPTIONS].find_one = AsyncMock(return_value=row)
                result = await admin_allow_redemption_retry(
                    redemption_id="r-retry",
                    actor={"type": "admin", "id": "a1", "email": "admin@test.com"},
                    reason="Support recovery",
                )
    assert result["redemption"]["status"] == PilotRedemptionStatus.REVOKED.value
    assert result["override"]["override_id"] == "ov1"
