from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from services.billing_stripe_sync_service import persist_subscription_billing_from_stripe
from services.jobs import JobScheduler
from services.stripe_webhook_service import stripe_webhook_service
from services.subscription_lifecycle_service import (
    BillingLifecycleState,
    compute_billing_lifecycle_state,
    compute_entitlement_for_lifecycle,
)
from services.plan_registry import EntitlementStatus


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, _):
        return list(self._rows)


class _FakeFindResult:
    def __init__(self, rows):
        self._rows = rows

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    async def to_list(self, _):
        return list(self._rows)


class _FakeClientBilling:
    def __init__(self):
        self.docs = {}
        self.find_queries = []

    async def update_one(self, query, update, upsert=False):
        cid = query.get("client_id")
        if not cid:
            return SimpleNamespace(modified_count=0)
        row = self.docs.setdefault(cid, {"client_id": cid})
        for k, v in (update.get("$set") or {}).items():
            row[k] = v
        for k in (update.get("$unset") or {}).keys():
            row.pop(k, None)
        return SimpleNamespace(modified_count=1)

    async def find_one(self, query, projection=None):
        if "stripe_customer_id" in query:
            for d in self.docs.values():
                if d.get("stripe_customer_id") == query["stripe_customer_id"]:
                    return dict(d)
            return None
        if "stripe_subscription_id" in query:
            for d in self.docs.values():
                if d.get("stripe_subscription_id") == query["stripe_subscription_id"]:
                    return dict(d)
            return None
        cid = query.get("client_id")
        d = self.docs.get(cid)
        return dict(d) if d else None

    def find(self, query, projection=None):
        self.find_queries.append(query)
        return _FakeCursor([])


class _FakeClients:
    def __init__(self, fail=False):
        self.fail = fail
        self.docs = {}

    async def update_one(self, query, update):
        if self.fail:
            raise RuntimeError("clients write failed")
        cid = query.get("client_id")
        if not cid:
            return SimpleNamespace(modified_count=0)
        row = self.docs.setdefault(cid, {"client_id": cid})
        for k, v in (update.get("$set") or {}).items():
            row[k] = v
        return SimpleNamespace(modified_count=1)

    async def find_one(self, query, projection=None):
        cid = query.get("client_id")
        d = self.docs.get(cid)
        return dict(d) if d else None


class _FakeDb:
    def __init__(self, fail_clients=False):
        self.client_billing = _FakeClientBilling()
        self.clients = _FakeClients(fail=fail_clients)
        self.notification_preferences = SimpleNamespace(find_one=AsyncMock(return_value=None))


def _sub() -> dict:
    return {
        "id": "sub_phaseb_1",
        "customer": "cus_phaseb_1",
        "status": "active",
        "cancel_at_period_end": False,
        "latest_invoice": "in_phaseb_latest",
        "current_period_start": int(datetime.now(timezone.utc).timestamp()),
        "current_period_end": int(datetime.now(timezone.utc).timestamp()) + 86400 * 30,
        "items": {"data": [{"price": {"id": "price_test_plan2_portfolio_monthly", "unit_amount": 3900, "recurring": {"interval": "month"}}}]},
    }


def test_lifecycle_cancel_at_period_end_projection_enabled_access():
    now = datetime.now(timezone.utc)
    lifecycle = compute_billing_lifecycle_state(
        subscription_status_upper="ACTIVE",
        cancel_at_period_end=True,
        grace_period_ends_at=None,
        current_period_end=now,
        now=now,
    )
    assert lifecycle == BillingLifecycleState.CANCEL_AT_PERIOD_END.value
    ent = compute_entitlement_for_lifecycle(lifecycle, "ACTIVE")
    assert ent == EntitlementStatus.ENABLED


@pytest.mark.asyncio
async def test_webhook_invoice_paid_ignored_for_cancelled_subscription():
    db = _FakeDb()
    db.client_billing.docs["c1"] = {
        "client_id": "c1",
        "stripe_customer_id": "cus_1",
        "stripe_subscription_id": "sub_1",
        "subscription_status": "CANCELED",
    }
    with patch("services.stripe_webhook_service.database.get_db", return_value=db):
        result = await stripe_webhook_service._handle_invoice_paid(
            {"id": "", "customer": "cus_1", "subscription": "sub_1", "amount_paid": 0, "currency": "gbp"},
            {"id": "evt_paid", "type": "invoice.paid", "created": int(datetime.now(timezone.utc).timestamp())},
        )
    assert result.get("ignored_cancelled") is True


@pytest.mark.asyncio
async def test_webhook_payment_failed_ignored_for_cancelled_subscription():
    db = _FakeDb()
    db.client_billing.docs["c1"] = {
        "client_id": "c1",
        "stripe_customer_id": "cus_1",
        "stripe_subscription_id": "sub_1",
        "subscription_status": "CANCELED",
    }
    with patch("services.stripe_webhook_service.database.get_db", return_value=db):
        result = await stripe_webhook_service._handle_payment_failed(
            {"id": "in_1", "customer": "cus_1", "subscription": "sub_1", "amount_due": 0, "currency": "gbp"},
            {"id": "evt_fail", "type": "invoice.payment_failed", "created": int(datetime.now(timezone.utc).timestamp())},
        )
    assert result.get("ignored_cancelled") is True


@pytest.mark.asyncio
async def test_split_write_marker_set_when_clients_write_fails():
    db = _FakeDb(fail_clients=True)
    db.client_billing.docs["c_split"] = {"client_id": "c_split"}
    with (
        patch("services.billing_stripe_sync_service.database.get_db", return_value=db),
        patch("services.billing_reconciliation_service.database.get_db", return_value=db),
        patch("services.billing_reconciliation_service.create_audit_log", new=AsyncMock(return_value=None)),
    ):
        with pytest.raises(RuntimeError):
            await persist_subscription_billing_from_stripe(
                "c_split",
                _sub(),
                event_source="test",
                update_plan=True,
                increment_entitlements_version=0,
            )
    row = db.client_billing.docs["c_split"]
    assert row.get("billing_reconciliation_needed") is True
    assert row.get("billing_sync_state") == "needs_reconciliation"


@pytest.mark.asyncio
async def test_scheduled_job_grace_query_skips_cancelled_statuses():
    db = _FakeDb()
    scheduler = JobScheduler()
    scheduler.db = db
    with (
        patch("services.subscription_lifecycle_service.apply_post_grace_transitions", new=AsyncMock(return_value=0)),
        patch("utils.app_urls.get_app_base_url", return_value="https://app.example.com"),
    ):
        result = await scheduler.process_subscription_lifecycle_and_reminders()
    assert result.get("count") == 0
    assert db.client_billing.find_queries
    grace_query = db.client_billing.find_queries[0]
    assert grace_query.get("subscription_status", {}).get("$nin") == ["CANCELED", "CANCELLED", "UNPAID", "INCOMPLETE_EXPIRED"]
