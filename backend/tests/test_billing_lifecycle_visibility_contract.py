from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest
from starlette.requests import Request

from routes import admin as admin_routes
from routes import admin_billing as admin_billing_routes
from services.stripe_service import stripe_service


class _FakeCursor:
    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    async def to_list(self, _n: int):
        return list(self._rows)


class _FakeCollection:
    def __init__(self, one: Dict[str, Any] | None = None, rows: List[Dict[str, Any]] | None = None):
        self._one = one
        self._rows = rows or []

    async def find_one(self, *_args, **_kwargs):
        return dict(self._one) if isinstance(self._one, dict) else None

    async def count_documents(self, *_args, **_kwargs):
        return 0

    def find(self, *_args, **_kwargs):
        return _FakeCursor(self._rows)


class _FakeDb:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.clients = _FakeCollection(
            one={
                "client_id": "client_x",
                "full_name": "Client X",
                "email": "client@example.com",
                "billing_plan": "PLAN_1_SOLO",
                "subscription_status": "ACTIVE",
                "entitlement_status": "ENABLED",
                "canonical_entitlement_state": "ENABLED",
                "created_at": now,
            }
        )
        self.client_billing = _FakeCollection(
            one={
                "client_id": "client_x",
                "stripe_customer_id": "cus_x",
                "stripe_subscription_id": "sub_x",
                "billing_lifecycle_state": "active",
                "billing_reconciliation_needed": True,
                "billing_reconciliation_reason": "test_marker",
                "billing_reconciliation_marked_at": now,
                "current_period_end": now,
            }
        )
        self.portal_users = _FakeCollection(one={"portal_user_id": "pu_1", "auth_email": "client@example.com"})
        self.stripe_events = _FakeCollection(rows=[])
        self.stripe_checkout_invoices = _FakeCollection()
        self.cvp_subscription_renewal_receipts = _FakeCollection()
        self.properties = _FakeCollection()
        self.requirements = _FakeCollection()
        self.payments = _FakeCollection(rows=[])
        self.audit_logs = _FakeCollection(rows=[])
        self.maintenance_issues = _FakeCollection()
        self.work_orders = _FakeCollection()
        self.contractors = _FakeCollection()
        self.digest_logs = _FakeCollection(rows=[])
        self.communication_deliveries = _FakeCollection(rows=[])
        self.documents = _FakeCollection()


def _request() -> Request:
    return Request({"type": "http", "headers": []})


@pytest.mark.asyncio
async def test_admin_billing_snapshot_contract_fields_present():
    fake_db = _FakeDb()
    async def _admin_guard(_request=None):
        return {"portal_user_id": "admin_1", "role": "ROLE_ADMIN"}

    with (
        patch.object(admin_billing_routes, "admin_route_guard", new=AsyncMock(side_effect=_admin_guard)),
        patch.object(admin_billing_routes.database, "get_db", return_value=fake_db),
        patch.object(
            admin_billing_routes.StripeService,
            "get_subscription_status",
            new=AsyncMock(
                return_value={
                    "has_subscription": True,
                    "billing_lifecycle_state": "active",
                    "lifecycle_status_label": "Active",
                    "billing_sync_state": "ok",
                    "billing_last_synced_at": datetime.now(timezone.utc).isoformat(),
                    "current_period_end": datetime.now(timezone.utc).isoformat(),
                }
            ),
        ),
    ):
        payload = await admin_billing_routes.get_client_billing_snapshot(_request(), "client_x")

    assert "subscription_lifecycle" in payload
    sl = payload["subscription_lifecycle"] or {}
    assert "billing_lifecycle_state" in sl
    assert "lifecycle_status_label" in sl
    assert "billing_reconciliation_needed" in payload
    assert "billing_reconciliation_reason" in payload
    assert "billing_reconciliation_marked_at" in payload


@pytest.mark.asyncio
async def test_admin_control_panel_contract_fields_present():
    fake_db = _FakeDb()
    now = datetime.now(timezone.utc)
    async def _admin_guard(_request=None):
        return {"portal_user_id": "admin_1", "role": "ROLE_ADMIN"}

    with (
        patch.object(admin_routes, "admin_route_guard", new=AsyncMock(side_effect=_admin_guard)),
        patch.object(admin_routes.database, "get_db", return_value=fake_db),
        patch("services.admin_billing_receipts.list_receipts_for_client", new=AsyncMock(return_value=([], {"total": 0}))),
        patch("services.onboarding_checklist_service.get_checklist_for_client", new=AsyncMock(return_value={"error": True})),
        patch(
            "services.stripe_service.StripeService.get_subscription_status",
            new=AsyncMock(
                return_value={
                    "has_subscription": True,
                    "stripe_customer_id": "cus_x",
                    "stripe_subscription_id": "sub_x",
                    "stripe_webhook_last_received_at": now.isoformat(),
                    "stripe_webhook_last_event_type": "invoice.paid",
                    "billing_last_synced_at": now.isoformat(),
                    "billing_sync_state": "ok",
                    "lifecycle_status_label": "Active",
                }
            ),
        ),
    ):
        payload = await admin_routes.get_client_control_panel(_request(), "client_x")

    billing = payload.get("subscription_billing") or {}
    assert "billing_lifecycle_state" in billing
    assert "lifecycle_status_label" in billing
    assert "billing_reconciliation_needed" in billing
    assert "billing_reconciliation_reason" in billing
    assert "billing_reconciliation_marked_at" in billing
    assert billing.get("stripe_customer_id") == "cus_x"
    assert billing.get("stripe_subscription_id") == "sub_x"
    assert billing.get("stripe_webhook_last_event_type") == "invoice.paid"
    assert billing.get("billing_sync_state") == "ok"
    assert billing.get("billing_last_synced_at")
    co = payload.get("compliance_overview") or {}
    assert "unresolved_evidence_document_count" in co


@pytest.mark.asyncio
async def test_client_billing_status_contract_includes_lifecycle_status_label():
    fake_db = _FakeDb()
    with patch("services.stripe_service.database.get_db", return_value=fake_db):
        payload = await stripe_service.get_subscription_status("client_x", client_facing=True)
    assert "lifecycle_status_label" in payload
