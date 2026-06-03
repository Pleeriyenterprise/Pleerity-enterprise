"""Governed admin subscription cancellation route tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from middleware import admin_route_guard
from routes import admin_billing as admin_billing_routes
from server import app
from services.admin_action_governance import CONFIRMATION_HEADER
from services.admin_confirmation_token_service import issue_admin_confirmation_token


@pytest.fixture
def client():
    return TestClient(app)


def _admin_user():
    return {"portal_user_id": "admin-portal-1", "role": "ROLE_ADMIN", "email": "admin@test.com"}


async def _issue_token(action_id: str, resource_key: str) -> str:
    stored: dict = {}

    async def insert_one(doc):
        stored.clear()
        stored.update(doc)

    async def find_one(q):
        if q.get("token_hash") == stored.get("token_hash"):
            return dict(stored)
        return None

    async def update_one(q, upd):
        stored.update(upd.get("$set", {}))

    collection = AsyncMock()
    collection.insert_one = insert_one
    collection.find_one = find_one
    collection.update_one = update_one
    collection.delete_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=collection)

    with patch("database.database.get_db", return_value=mock_db):
        return await issue_admin_confirmation_token(
            "admin-portal-1",
            action_id,
            resource_key=resource_key,
            reason="Customer requested cancellation via support ticket",
        )


def _billing_row(**overrides):
    row = {
        "client_id": "client-cancel-1",
        "stripe_subscription_id": "sub_test_1",
        "stripe_customer_id": "cus_test_1",
        "subscription_status": "ACTIVE",
        "cancel_at_period_end": False,
    }
    row.update(overrides)
    return row


@pytest.fixture
def admin_auth():
    async def _guard(_request=None):
        return _admin_user()

    app.dependency_overrides[admin_route_guard] = _guard
    with patch.object(admin_billing_routes, "admin_route_guard", new=AsyncMock(side_effect=_guard)):
        yield
    app.dependency_overrides.pop(admin_route_guard, None)


def test_admin_cancel_requires_reason(client, admin_auth):
    r = client.post(
            "/api/admin/billing/clients/client-cancel-1/cancel",
            json={"cancel_immediately": False, "reason": "short"},
        )
    assert r.status_code == 422


def test_admin_cancel_requires_confirmation_token(client, admin_auth):
    with patch("routes.admin_billing.database.get_db") as mock_get_db:
        db = MagicMock()
        db.clients.find_one = AsyncMock(return_value={"client_id": "client-cancel-1"})
        db.client_billing.find_one = AsyncMock(return_value=_billing_row())
        mock_get_db.return_value = db
        with patch(
            "services.admin_action_governance.enforce_governed_admin_action",
            new=AsyncMock(side_effect=HTTPException(status_code=403, detail="Confirmation required")),
        ):
            r = client.post(
                "/api/admin/billing/clients/client-cancel-1/cancel",
                json={
                    "cancel_immediately": False,
                    "reason": "Customer requested cancellation via phone support",
                },
            )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_cancel_at_period_end(client, admin_auth):
    token = await _issue_token("admin_cancel_subscription", "client-cancel-1")
    cancel_mock = AsyncMock(
        return_value={
            "success": True,
            "cancel_at_period_end": True,
            "current_period_end": "2026-07-01T00:00:00+00:00",
        }
    )
    with patch(
        "routes.admin_billing.database.get_db"
    ) as mock_get_db, patch(
        "services.admin_action_governance.enforce_governed_admin_action",
        new=AsyncMock(return_value="Customer requested cancellation via phone support"),
    ), patch(
        "routes.admin_billing.resolve_stripe_context",
        new=AsyncMock(),
    ), patch(
        "routes.admin_billing.stripe_service.cancel_subscription",
        cancel_mock,
    ), patch(
        "routes.admin_billing.create_audit_log",
        new=AsyncMock(),
    ), patch(
        "middleware.step_up_auth.require_recent_step_up",
        new=AsyncMock(),
    ):
        db = MagicMock()
        db.clients.find_one = AsyncMock(return_value={"client_id": "client-cancel-1"})
        db.client_billing.find_one = AsyncMock(return_value=_billing_row())
        mock_get_db.return_value = db
        r = client.post(
            "/api/admin/billing/clients/client-cancel-1/cancel",
            json={
                "cancel_immediately": False,
                "reason": "Customer requested cancellation via phone support",
            },
            headers={CONFIRMATION_HEADER: token},
        )
    assert r.status_code == 200
    assert r.json().get("success") is True
    cancel_mock.assert_awaited_once()
    assert cancel_mock.await_args.kwargs.get("cancel_immediately") is False
    assert cancel_mock.await_args.kwargs.get("cancellation_source") == "admin_billing_cancel"


@pytest.mark.asyncio
async def test_admin_cancel_immediate(client, admin_auth):
    token = await _issue_token("admin_cancel_subscription", "client-cancel-1")
    cancel_mock = AsyncMock(
        return_value={
            "success": True,
            "cancel_at_period_end": False,
            "current_period_end": "2026-07-01T00:00:00+00:00",
        }
    )
    with patch(
        "routes.admin_billing.database.get_db"
    ) as mock_get_db, patch(
        "services.admin_action_governance.enforce_governed_admin_action",
        new=AsyncMock(return_value="Customer requested cancellation via phone support"),
    ), patch(
        "routes.admin_billing.resolve_stripe_context",
        new=AsyncMock(),
    ), patch(
        "routes.admin_billing.stripe_service.cancel_subscription",
        cancel_mock,
    ), patch(
        "routes.admin_billing.create_audit_log",
        new=AsyncMock(),
    ), patch(
        "middleware.step_up_auth.require_recent_step_up",
        new=AsyncMock(),
    ):
        db = MagicMock()
        db.clients.find_one = AsyncMock(return_value={"client_id": "client-cancel-1"})
        db.client_billing.find_one = AsyncMock(return_value=_billing_row())
        mock_get_db.return_value = db
        r = client.post(
            "/api/admin/billing/clients/client-cancel-1/cancel",
            json={
                "cancel_immediately": True,
                "reason": "Customer requested immediate cancellation via support",
            },
            headers={CONFIRMATION_HEADER: token},
        )
    assert r.status_code == 200
    assert cancel_mock.await_args.kwargs.get("cancel_immediately") is True


@pytest.mark.asyncio
async def test_admin_cancel_rejects_already_cancelled(client, admin_auth):
    token = await _issue_token("admin_cancel_subscription", "client-cancel-1")
    with patch(
        "routes.admin_billing.database.get_db"
    ) as mock_get_db, patch(
        "services.admin_action_governance.enforce_governed_admin_action",
        new=AsyncMock(return_value="Customer requested cancellation via phone support"),
    ), patch(
        "middleware.step_up_auth.require_recent_step_up",
        new=AsyncMock(),
    ):
        db = MagicMock()
        db.clients.find_one = AsyncMock(return_value={"client_id": "client-cancel-1"})
        db.client_billing.find_one = AsyncMock(
            return_value=_billing_row(subscription_status="CANCELED")
        )
        mock_get_db.return_value = db
        r = client.post(
            "/api/admin/billing/clients/client-cancel-1/cancel",
            json={
                "cancel_immediately": False,
                "reason": "Customer requested cancellation via phone support",
            },
            headers={CONFIRMATION_HEADER: token},
        )
    assert r.status_code == 400
    assert "already cancelled" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_admin_cancel_rejects_already_scheduled(client, admin_auth):
    token = await _issue_token("admin_cancel_subscription", "client-cancel-1")
    with patch(
        "routes.admin_billing.database.get_db"
    ) as mock_get_db, patch(
        "services.admin_action_governance.enforce_governed_admin_action",
        new=AsyncMock(return_value="Customer requested cancellation via phone support"),
    ), patch(
        "middleware.step_up_auth.require_recent_step_up",
        new=AsyncMock(),
    ):
        db = MagicMock()
        db.clients.find_one = AsyncMock(return_value={"client_id": "client-cancel-1"})
        db.client_billing.find_one = AsyncMock(
            return_value=_billing_row(cancel_at_period_end=True)
        )
        mock_get_db.return_value = db
        r = client.post(
            "/api/admin/billing/clients/client-cancel-1/cancel",
            json={
                "cancel_immediately": False,
                "reason": "Customer requested cancellation via phone support",
            },
            headers={CONFIRMATION_HEADER: token},
        )
    assert r.status_code == 400
    assert "already scheduled" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_payment_failed_ops_bridge_lifecycle_sync_flag():
    from services.stripe_webhook_service import StripeWebhookService

    svc = StripeWebhookService()
    db = MagicMock()
    db.client_billing.find_one = AsyncMock(
        side_effect=[
            {
                "client_id": "c1",
                "stripe_customer_id": "cus_1",
                "stripe_subscription_id": "sub_1",
                "subscription_status": "ACTIVE",
            },
            {"entitlement_status": "LIMITED"},
            {"entitlement_status": "LIMITED"},
        ]
    )
    db.client_billing.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db.clients.update_one = AsyncMock()
    db.clients.find_one = AsyncMock(return_value={"contact_name": "Test"})
    svc._insert_payment = AsyncMock()
    bridge_mock = AsyncMock()

    with patch("services.stripe_webhook_service.database.get_db", return_value=db), patch(
        "services.stripe_webhook_service.stripe.Subscription.retrieve",
        return_value={"id": "sub_1", "status": "past_due", "customer": "cus_1"},
    ), patch(
        "services.stripe_webhook_service.sync_subscription_lifecycle",
        new=AsyncMock(side_effect=RuntimeError("sync failed")),
    ), patch(
        "services.stripe_webhook_service.mark_billing_reconciliation_needed",
        new=AsyncMock(),
    ), patch(
        "services.stripe_webhook_service.create_audit_log",
        new=AsyncMock(),
    ), patch(
        "services.subscription_operational_bridge.on_payment_failed",
        bridge_mock,
    ), patch(
        "services.notification_orchestrator.notification_orchestrator.send",
        new=AsyncMock(return_value=MagicMock(outcome="duplicate_ignored")),
    ):
        result = await svc._handle_payment_failed(
            {
                "id": "in_1",
                "customer": "cus_1",
                "subscription": "sub_1",
                "amount_due": 1900,
                "currency": "gbp",
                "status": "open",
            },
            {"id": "evt_1", "type": "invoice.payment_failed"},
        )

    assert result.get("handled") is True
    bridge_mock.assert_awaited_once()
    assert bridge_mock.await_args.kwargs.get("lifecycle_sync_failed") is True
