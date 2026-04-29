"""Canonical admin client support search (shared by /admin/search and billing search)."""

import re
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

import services.admin_client_support_search as admin_client_support_search
from services.admin_client_support_search import (
    run_admin_client_support_search,
    assert_support_row_has_no_sensitive_payment_blob,
)


def _regex_val(spec):
    if isinstance(spec, dict) and "$regex" in spec:
        return str(spec["$regex"]), spec.get("$options", "")
    return None, ""


def _row_matches_client_query(q, row):
    """Very small matcher for tests: supports $and with visibility + $or regex, or plain $or."""
    if not isinstance(q, dict):
        return True
    if "$and" in q:
        parts = q["$and"]
        return all(_row_matches_client_query(p, row) for p in parts)
    if "$or" in q:
        blob = " ".join(str(row.get(k) or "") for k in row).lower()
        for branch in q["$or"]:
            for _k, spec in branch.items():
                pat, opts = _regex_val(spec)
                if pat and re.search(pat, blob, flags=re.I if opts == "i" else 0):
                    return True
        return False
    return True


def _row_matches_simple(q, row):
    if not isinstance(q, dict):
        return True
    if len(q) == 1:
        k, v = next(iter(q.items()))
        if k != "$or" and not isinstance(v, dict):
            return row.get(k) == v
    if "$or" in q:
        blob = " ".join(str(row.get(k) or "") for k in row).lower()
        for branch in q["$or"]:
            for _k, spec in branch.items():
                pat, opts = _regex_val(spec)
                if pat and re.search(pat, blob, flags=re.I if opts == "i" else 0):
                    return True
        return False
    for k, v in q.items():
        if k == "$or":
            continue
        if isinstance(v, dict) and "$regex" in v:
            pat, opts = _regex_val(v)
            if pat and not re.search(pat, str(row.get(k) or ""), flags=re.I if opts == "i" else 0):
                return False
    return True


def _fake_db(
    *,
    clients_rows,
    orders_rows=None,
    props_rows=None,
    billing_rows=None,
    billing_by_stripe=None,
):
    """Minimal async Mongo-like fake for the search service."""
    orders_rows = orders_rows or []
    props_rows = props_rows or []
    billing_rows = billing_rows or []
    billing_by_stripe = billing_by_stripe or []

    class _Cur:
        def __init__(self, rows):
            self._rows = list(rows)

        def limit(self, n):
            self._limit = n
            return self

        async def to_list(self, n=None):
            lim = getattr(self, "_limit", n) or n or len(self._rows)
            return self._rows[:lim]

    class _Agg:
        def __init__(self, pipeline):
            self.pipeline = pipeline

        async def to_list(self, _n=None):
            if self.pipeline and "$group" in str(self.pipeline):
                return [{"_id": "c1", "n": 2}]
            return []

    class _Coll:
        def __init__(self, name, rows):
            self.name = name
            self._rows = rows

        def find(self, q, _proj=None):
            if self.name == "clients":
                matched = [r for r in self._rows if _row_matches_client_query(q, r)]
                return _Cur(matched)
            matched = [r for r in self._rows if _row_matches_simple(q, r)]
            return _Cur(matched)

        def aggregate(self, pipeline):
            return _Agg(pipeline)

    billing_all = list(billing_rows) + list(billing_by_stripe)

    db = MagicMock()
    db.clients = _Coll("clients", clients_rows)
    db.orders = _Coll("orders", orders_rows)
    db.properties = _Coll("properties", props_rows)
    db.client_billing = _Coll("client_billing", billing_all)
    return db


@pytest.mark.asyncio
async def test_support_search_by_email_finds_client(monkeypatch):
    clients = [
        {
            "client_id": "c1",
            "email": "pat@example.com",
            "full_name": "Pat Example",
            "company_name": "Ex Co",
            "customer_reference": "PLE-CVP-2026-00001",
            "billing_plan": "PLAN_1_SOLO",
            "subscription_status": "ACTIVE",
            "onboarding_status": "PROVISIONED",
        }
    ]
    billing = [
        {
            "client_id": "c1",
            "stripe_customer_id": "cus_test1",
            "stripe_subscription_id": "sub_test1",
            "last_payment_at": datetime(2026, 1, 15, tzinfo=timezone.utc),
            "current_period_end": datetime(2026, 2, 15, tzinfo=timezone.utc),
            "billing_sync_state": "ok",
            "billing_lifecycle_state": "active",
            "billing_reconciliation_needed": False,
        }
    ]
    db = _fake_db(clients_rows=clients, billing_rows=billing)
    monkeypatch.setattr(
        "services.admin_client_support_search.default_active_client_match",
        lambda: {},
    )
    rows = await run_admin_client_support_search(db, search_term="pat@ex", limit=10, include_archived=True)
    assert len(rows) == 1
    r = rows[0]
    assert r["client_id"] == "c1"
    assert r["email"] == "pat@example.com"
    assert r["primary_support_url"] == "/admin/clients/c1"
    assert r["stripe_customer_id"] == "cus_test1"
    assert r["stripe_subscription_id"] == "sub_test1"
    assert r["property_count"] == 2
    assert_support_row_has_no_sensitive_payment_blob(r)


@pytest.mark.asyncio
async def test_support_search_by_stripe_customer_id(monkeypatch):
    clients = [
        {
            "client_id": "c9",
            "email": "x@y.com",
            "full_name": "Stripe Match",
            "customer_reference": "PLE-CVP-2026-00009",
            "billing_plan": "PLAN_2_PORTFOLIO",
            "subscription_status": "ACTIVE",
            "onboarding_status": "PROVISIONED",
        }
    ]
    billing = [{"client_id": "c9", "stripe_customer_id": "cus_ABC123", "stripe_subscription_id": None}]
    db = _fake_db(clients_rows=clients, billing_rows=billing)
    monkeypatch.setattr(admin_client_support_search, "default_active_client_match", lambda: {})
    rows = await run_admin_client_support_search(db, search_term="cus_ABC123", limit=5, include_archived=True)
    assert len(rows) == 1
    assert rows[0]["client_id"] == "c9"
    assert rows[0].get("matched_via") == "stripe_id"
    assert rows[0]["stripe_customer_id"] == "cus_ABC123"


@pytest.mark.asyncio
async def test_support_search_property_match(monkeypatch):
    clients = [
        {
            "client_id": "c2",
            "email": "a@b.com",
            "full_name": "Addr Client",
            "customer_reference": "PLE-CVP-2026-00002",
            "billing_plan": "PLAN_1_SOLO",
            "subscription_status": "ACTIVE",
            "onboarding_status": "PROVISIONED",
        }
    ]
    props = [{"client_id": "c2", "postcode": "SW1A 1AA"}]
    db = _fake_db(clients_rows=clients, props_rows=props)
    monkeypatch.setattr(admin_client_support_search, "default_active_client_match", lambda: {})
    rows = await run_admin_client_support_search(db, search_term="SW1A", limit=5, include_archived=True)
    assert len(rows) == 1
    assert rows[0]["client_id"] == "c2"
    assert rows[0].get("matched_via") == "property"
    assert rows[0].get("matched_postcode") == "SW1A 1AA"
