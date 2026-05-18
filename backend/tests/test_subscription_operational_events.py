"""Tests for subscription operational renewal notifications and digest."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.subscription_operational_constants import (
    OPERATIONAL_EVENT_LABELS,
    SUBSCRIPTION_RENEWAL_FAILED,
    SUBSCRIPTION_RENEWED,
    PAYMENT_RECONCILIATION_MISMATCH,
)
from services.subscription_operational_events import (
    operational_label,
    record_subscription_renewal_failed,
    record_subscription_renewed,
    list_recent_operational_events,
    COLLECTION,
)
from services.subscription_ops_digest import build_digest_summary, format_digest_text
from services.subscription_renewal_metadata import (
    record_successful_renewal_metadata,
    record_failed_payment_metadata,
)


@pytest.fixture
def mock_db():
    db = MagicMock()
    col = MagicMock()
    billing_col = MagicMock()
    clients_col = MagicMock()

    async def find_one_billing(*args, **kwargs):
        return {
            "client_id": "client-1",
            "current_plan_code": "PLAN_2_PORTFOLIO",
            "entitlement_status": "ENABLED",
            "stripe_customer_id": "cus_1",
            "stripe_subscription_id": "sub_1",
            "billing_reconciliation_needed": False,
            "subscription_ops_renewal_number": 0,
        }

    async def find_one_client(*args, **kwargs):
        return {
            "client_id": "client-1",
            "contact_name": "Test User",
            "email": "test@example.com",
        }

    billing_col.find_one = AsyncMock(side_effect=find_one_billing)
    billing_col.update_one = AsyncMock()
    clients_col.find_one = AsyncMock(side_effect=find_one_client)
    col.find_one = AsyncMock(return_value=None)
    col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="evt-1"))
    col.find = MagicMock()

    db.client_billing = billing_col
    db.clients = clients_col
    db.subscription_operational_events = col
    return db


@pytest.mark.asyncio
async def test_operational_presentation_labels():
    assert operational_label(SUBSCRIPTION_RENEWED) == "Subscription renewed successfully"
    assert "renewal payment failed" in operational_label(SUBSCRIPTION_RENEWAL_FAILED).lower()
    assert OPERATIONAL_EVENT_LABELS[PAYMENT_RECONCILIATION_MISMATCH]


@pytest.mark.asyncio
@patch("services.subscription_operational_events.database.get_db")
@patch("services.subscription_operational_notifications.send_subscription_ops_admin_alert", new_callable=AsyncMock)
async def test_first_renewal_triggers_immediate_notify(mock_alert, mock_get_db, mock_db):
    mock_get_db.return_value = mock_db

    result = await record_subscription_renewed(
        client_id="client-1",
        invoice={
            "id": "in_1",
            "amount_paid": 2900,
            "currency": "gbp",
            "billing_reason": "subscription_cycle",
            "customer": "cus_1",
            "subscription": "sub_1",
        },
        event={"id": "evt_stripe_1"},
        recovered=False,
        old_status="active",
    )
    assert result["created"] is True
    assert result["immediate_admin_notify"] is True
    mock_alert.assert_called_once()


@pytest.mark.asyncio
@patch("services.subscription_operational_events.database.get_db")
@patch("services.subscription_operational_notifications.send_subscription_ops_admin_alert", new_callable=AsyncMock)
async def test_repeated_renewal_suppressed_notify(mock_alert, mock_get_db, mock_db):
    mock_get_db.return_value = mock_db

    async def find_one_billing(*args, **kwargs):
        return {
            "client_id": "client-1",
            "current_plan_code": "PLAN_2_PORTFOLIO",
            "entitlement_status": "ENABLED",
            "subscription_ops_renewal_number": 5,
            "subscription_ops_consecutive_successful_renewals": 5,
        }

    mock_db.client_billing.find_one = AsyncMock(side_effect=find_one_billing)

    result = await record_subscription_renewed(
        client_id="client-1",
        invoice={
            "id": "in_2",
            "amount_paid": 2900,
            "currency": "gbp",
            "billing_reason": "subscription_cycle",
        },
        event={"id": "evt_stripe_2"},
        recovered=False,
        old_status="active",
    )
    assert result["created"] is True
    assert result["immediate_admin_notify"] is False
    mock_alert.assert_not_called()


@pytest.mark.asyncio
@patch("services.subscription_operational_events.database.get_db")
@patch("services.subscription_operational_notifications.send_subscription_ops_admin_alert", new_callable=AsyncMock)
async def test_duplicate_stripe_event_deduped(mock_alert, mock_get_db, mock_db):
    mock_get_db.return_value = mock_db

    async def find_one_events(query, *args, **kwargs):
        if isinstance(query, dict) and query.get("dedupe_key"):
            return {"_id": "existing"}
        return None

    mock_db.subscription_operational_events.find_one = AsyncMock(side_effect=find_one_events)

    result = await record_subscription_renewed(
        client_id="client-1",
        invoice={"id": "in_dup", "amount_paid": 2900, "billing_reason": "subscription_cycle"},
        event={"id": "evt_dup"},
    )
    assert result["created"] is False
    mock_db.subscription_operational_events.insert_one.assert_not_called()
    mock_alert.assert_not_called()


@pytest.mark.asyncio
@patch("services.subscription_operational_events.database.get_db")
@patch("services.subscription_operational_notifications.send_subscription_ops_admin_alert", new_callable=AsyncMock)
async def test_failed_renewal_aggregates_repeat(mock_alert, mock_get_db, mock_db):
    mock_get_db.return_value = mock_db

    r1 = await record_subscription_renewal_failed(
        client_id="client-1",
        invoice={"id": "in_fail_1", "amount_due": 2900, "currency": "gbp"},
        event={"id": "evt_f1"},
    )
    assert r1["created"] is True
    assert r1["immediate_admin_notify"] is True
    assert mock_alert.call_count == 1

    mock_db.subscription_operational_events.find_one = AsyncMock(return_value={"_id": "incident"})
    r2 = await record_subscription_renewal_failed(
        client_id="client-1",
        invoice={"id": "in_fail_2", "amount_due": 2900, "currency": "gbp"},
        event={"id": "evt_f2"},
    )
    assert r2["suppressed"] is True
    assert r2["immediate_admin_notify"] is False
    assert mock_alert.call_count == 1


@pytest.mark.asyncio
@patch("services.subscription_operational_events.database.get_db")
@patch("services.subscription_operational_notifications.send_subscription_ops_admin_alert", new_callable=AsyncMock)
async def test_recovery_after_failure_notifies(mock_alert, mock_get_db, mock_db):
    mock_get_db.return_value = mock_db

    async def find_one_billing(*args, **kwargs):
        return {
            "client_id": "client-1",
            "current_plan_code": "PLAN_2_PORTFOLIO",
            "entitlement_status": "ENABLED",
            "subscription_ops_open_failure_incident_key": "renewal_fail:client-1",
        }

    mock_db.client_billing.find_one = AsyncMock(side_effect=find_one_billing)

    result = await record_subscription_renewed(
        client_id="client-1",
        invoice={
            "id": "in_rec",
            "amount_paid": 2900,
            "currency": "gbp",
            "billing_reason": "subscription_cycle",
        },
        event={"id": "evt_rec"},
        recovered=True,
        old_status="PAST_DUE",
    )
    assert result["immediate_admin_notify"] is True
    mock_alert.assert_called_once()


@pytest.mark.asyncio
@patch("services.subscription_operational_events.database.get_db")
@patch("services.subscription_operational_notifications.send_subscription_ops_admin_alert", new_callable=AsyncMock)
async def test_reconciliation_mismatch_warning(mock_alert, mock_get_db, mock_db):
    mock_get_db.return_value = mock_db

    async def find_one_billing(*args, **kwargs):
        return {
            "client_id": "client-1",
            "current_plan_code": "PLAN_2_PORTFOLIO",
            "entitlement_status": "ENABLED",
            "billing_reconciliation_needed": True,
            "subscription_ops_renewal_number": 2,
        }

    mock_db.client_billing.find_one = AsyncMock(side_effect=find_one_billing)

    result = await record_subscription_renewed(
        client_id="client-1",
        invoice={
            "id": "in_recon",
            "amount_paid": 2900,
            "currency": "gbp",
            "billing_reason": "subscription_cycle",
        },
        event={"id": "evt_recon"},
        lifecycle_sync_failed=True,
        old_status="active",
    )
    assert result["immediate_admin_notify"] is True
    assert mock_alert.call_count >= 1


@pytest.mark.asyncio
async def test_metadata_increment(mock_db):
    now = datetime.now(timezone.utc)
    meta = await record_successful_renewal_metadata(
        mock_db, client_id="client-1", amount_pence=2900, paid_at=now
    )
    assert meta["renewal_number"] == 1
    mock_db.client_billing.update_one.assert_called()

    await record_failed_payment_metadata(mock_db, client_id="client-1", failed_at=now)
    assert mock_db.client_billing.update_one.call_count >= 2


@pytest.mark.asyncio
@patch("services.subscription_ops_digest.database.get_db")
async def test_digest_generation(mock_get_db, mock_db):
    mock_get_db.return_value = mock_db
    day = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    async def to_list(*args, **kwargs):
        return [
            {
                "operational_event_type": SUBSCRIPTION_RENEWED,
                "amount": 2900,
                "digest_date": day,
                "recovered_after_failure": False,
            },
            {
                "operational_event_type": SUBSCRIPTION_RENEWAL_FAILED,
                "client_id": "c2",
                "digest_date": day,
            },
        ]

    cursor = MagicMock()
    cursor.to_list = AsyncMock(side_effect=to_list)
    mock_db.subscription_operational_events.find = MagicMock(return_value=cursor)

    summary = await build_digest_summary(digest_date=day)
    assert summary["subscriptions_renewed"] == 1
    assert summary["failed_renewals"] == 1
    text = format_digest_text(summary)
    assert "Subscriptions renewed: 1" in text
    assert "Failed renewals: 1" in text


@pytest.mark.asyncio
@patch("services.subscription_operational_events.database.get_db")
async def test_list_recent_events_humanised(mock_get_db, mock_db):
    mock_get_db.return_value = mock_db
    occurred = datetime.now(timezone.utc)

    async def to_list(*args, **kwargs):
        return [
            {
                "operational_event_label": "Subscription renewed successfully",
                "payment_status": "successful",
                "provisioning_status": "completed",
                "reconciliation_status": "verified",
                "occurred_at": occurred,
            }
        ]

    limit_mock = MagicMock()
    limit_mock.to_list = AsyncMock(side_effect=to_list)
    sort_mock = MagicMock()
    sort_mock.limit.return_value = limit_mock
    find_mock = MagicMock()
    find_mock.sort.return_value = sort_mock
    mock_db.subscription_operational_events.find.return_value = find_mock

    rows = await list_recent_operational_events(limit=10)
    assert rows[0]["payment_status_label"] == "Payment successful"
    assert "Entitlement provisioning: completed" in rows[0]["provisioning_status_label"]
