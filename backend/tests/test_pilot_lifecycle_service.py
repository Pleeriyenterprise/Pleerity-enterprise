"""Pilot lifecycle governance service tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.pilot_lifecycle import PilotStatus
from services.pilot_lifecycle_service import (
    cancel_pilot,
    comp_account,
    convert_to_paid,
    create_from_invite_checkout,
    extend_pilot,
    evaluate_pilot_governance_access,
    is_pilot_comped_entitled,
    record_stripe_paid_transition,
    set_pilot_expiry,
)


def _invite_doc():
    return {
        "code": "PILOT-X",
        "program_type": "FOUNDING_PILOT",
        "discount_type": "percent",
        "discount_percent": 100,
        "discount_duration": "repeating",
        "discount_duration_in_months": 2,
        "discount_mode": "coupon",
        "stripe_coupon_id": "c_test",
    }


@pytest.fixture
def mock_db_client():
    store = {"client": None, "audits": []}

    async def find_one(q, projection=None):
        if q.get("client_id") == "c1":
            return store["client"]
        return None

    async def update_one(q, u, **kw):
        if store["client"] is None:
            store["client"] = {"client_id": "c1"}
        if "$set" in u:
            store["client"].update(u["$set"])

    db = MagicMock()
    clients = MagicMock()
    clients.find_one = AsyncMock(side_effect=find_one)
    clients.update_one = AsyncMock(side_effect=update_one)
    db.clients = clients

    async def insert_audit(doc):
        store["audits"].append(doc)

    db.pilot_lifecycle_audit = MagicMock()
    db.pilot_lifecycle_audit.insert_one = AsyncMock(side_effect=insert_audit)
    db.pilot_lifecycle_audit.find_one = AsyncMock(return_value=None)

    def getitem(key):
        if key == "pilot_lifecycle_audit":
            return db.pilot_lifecycle_audit
        return MagicMock()

    db.__getitem__ = MagicMock(side_effect=getitem)
    return db, store


@pytest.mark.asyncio
async def test_create_from_invite_sets_active_status(mock_db_client):
    db, store = mock_db_client
    store["client"] = {"client_id": "c1"}
    with patch("services.pilot_lifecycle_service.database.get_db", return_value=db):
        with patch("services.pilot_lifecycle_audit.database.get_db", return_value=db):
            with patch("services.pilot_lifecycle_service.create_audit_log", new_callable=AsyncMock):
                await create_from_invite_checkout(
                    client_id="c1",
                    invite_doc=_invite_doc(),
                    checkout_session_id="cs_1",
                )
    assert store["client"]["pilot_status"] == PilotStatus.ACTIVE.value
    assert store["client"]["pilot_duration_months"] == 2
    assert len(store["audits"]) == 1


@pytest.mark.asyncio
async def test_extend_pilot_updates_extended_until(mock_db_client):
    db, store = mock_db_client
    now = datetime.now(timezone.utc)
    store["client"] = {
        "client_id": "c1",
        "pilot_status": PilotStatus.ACTIVE.value,
        "pilot_started_at": now,
        "pilot_expires_at": now + timedelta(days=30),
    }
    with patch("services.pilot_lifecycle_service.database.get_db", return_value=db):
        with patch("services.pilot_lifecycle_audit.database.get_db", return_value=db):
            with patch("services.pilot_lifecycle_service.create_audit_log", new_callable=AsyncMock):
                await extend_pilot(
                    client_id="c1",
                    actor_id="admin1",
                    actor_email="a@b.com",
                    reason="Founder extension approved",
                    days=14,
                )
    assert store["client"]["pilot_status"] == PilotStatus.EXTENDED.value
    assert store["client"].get("pilot_extended_until") is not None


@pytest.mark.asyncio
async def test_convert_to_paid_no_stripe_call(mock_db_client):
    db, store = mock_db_client
    store["client"] = {"client_id": "c1", "pilot_status": PilotStatus.ACTIVE.value}
    with patch("services.pilot_lifecycle_service.database.get_db", return_value=db):
        with patch("services.pilot_lifecycle_audit.database.get_db", return_value=db):
            with patch("services.pilot_lifecycle_service.create_audit_log", new_callable=AsyncMock):
                with patch("services.stripe_service.stripe_service") as stripe_mock:
                    await convert_to_paid(
                        client_id="c1",
                        actor_id="admin1",
                        actor_email=None,
                        reason="Manual conversion",
                    )
                    stripe_mock.cancel_subscription.assert_not_called()
    assert store["client"]["pilot_status"] == PilotStatus.CONVERTED_TO_PAID.value


@pytest.mark.asyncio
async def test_comp_entitled():
    assert is_pilot_comped_entitled({"pilot_status": "comped"}) is True
    denial = evaluate_pilot_governance_access(
        {"pilot_status": "cancelled", "pilot_governance_revoke_access": True}
    )
    assert denial is not None
    assert denial[1]["error_code"] == "PILOT_ACCESS_REVOKED"


@pytest.mark.asyncio
async def test_stripe_paid_transition_idempotent(mock_db_client):
    db, store = mock_db_client
    store["client"] = {
        "client_id": "c1",
        "pilot_program_type": "FOUNDING_PILOT",
        "pilot_status": PilotStatus.ACTIVE.value,
    }
    with patch("services.pilot_lifecycle_service.database.get_db", return_value=db):
        with patch("services.pilot_lifecycle_audit.database.get_db", return_value=db):
            with patch("services.pilot_lifecycle_service.create_audit_log", new_callable=AsyncMock):
                ok1 = await record_stripe_paid_transition(
                    client_id="c1",
                    invoice={"id": "in_1", "amount_paid": 1900},
                )
                ok2 = await record_stripe_paid_transition(
                    client_id="c1",
                    invoice={"id": "in_2", "amount_paid": 1900},
                )
    assert ok1 is True
    assert ok2 is False


@pytest.mark.asyncio
async def test_cannot_extend_cancelled(mock_db_client):
    db, store = mock_db_client
    store["client"] = {"client_id": "c1", "pilot_status": PilotStatus.CANCELLED.value}
    with patch("services.pilot_lifecycle_service.database.get_db", return_value=db):
        with pytest.raises(ValueError, match="Cannot extend"):
            await extend_pilot(
                client_id="c1",
                actor_id="a",
                actor_email=None,
                reason="Should fail",
                days=1,
            )


@pytest.mark.asyncio
async def test_set_expiry_shortens(mock_db_client):
    db, store = mock_db_client
    now = datetime.now(timezone.utc)
    store["client"] = {
        "client_id": "c1",
        "pilot_status": PilotStatus.ACTIVE.value,
        "pilot_started_at": now,
        "pilot_expires_at": now + timedelta(days=60),
    }
    new_exp = now + timedelta(days=7)
    with patch("services.pilot_lifecycle_service.database.get_db", return_value=db):
        with patch("services.pilot_lifecycle_audit.database.get_db", return_value=db):
            with patch("services.pilot_lifecycle_service.create_audit_log", new_callable=AsyncMock):
                await set_pilot_expiry(
                    client_id="c1",
                    actor_id="admin",
                    actor_email=None,
                    reason="Shorten pilot",
                    expires_at=new_exp,
                )
    assert store["client"]["pilot_expires_at"] == new_exp
