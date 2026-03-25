"""Billing and client approvals require X-Step-Up-Token (403 STEP_UP_REQUIRED when missing)."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request

from auth import create_step_up_token
from middleware import client_route_guard
from server import app


@pytest.fixture
def client_user():
    return {
        "client_id": "client-test-1",
        "portal_user_id": "portal-user-test-1",
        "role": "ROLE_CLIENT",
    }


@pytest.fixture
def override_client_guard(client_user):
    """client_approvals router uses Depends(client_route_guard); override on the app."""

    async def _fake_guard(request: Request):
        return client_user

    app.dependency_overrides[client_route_guard] = _fake_guard
    yield
    app.dependency_overrides.pop(client_route_guard, None)


def test_billing_cancel_returns_step_up_required_without_token(client, client_user):
    with patch("routes.billing.client_route_guard", AsyncMock(return_value=client_user)):
        with patch(
            "routes.billing.stripe_service.cancel_subscription",
            AsyncMock(return_value={"status": "ok"}),
        ):
            r = client.post("/api/billing/cancel", json={"cancel_immediately": False})
    assert r.status_code == 403
    body = r.json()
    assert body["detail"]["error_code"] == "STEP_UP_REQUIRED"


def test_billing_cancel_succeeds_with_valid_step_up_token(client, client_user):
    step = create_step_up_token(client_user["portal_user_id"])
    with patch("routes.billing.client_route_guard", AsyncMock(return_value=client_user)):
        with patch(
            "routes.billing.stripe_service.cancel_subscription",
            AsyncMock(return_value={"status": "cancelled"}),
        ):
            r = client.post(
                "/api/billing/cancel",
                json={"cancel_immediately": False},
                headers={"X-Step-Up-Token": step},
            )
    assert r.status_code == 200
    assert r.json().get("status") == "cancelled"


def test_billing_checkout_requires_step_up(client, client_user):
    with patch("routes.billing.client_route_guard", AsyncMock(return_value=client_user)):
        with patch(
            "routes.billing.stripe_service.create_upgrade_session",
            AsyncMock(return_value={"checkout_url": "https://stripe.test/checkout"}),
        ):
            r = client.post("/api/billing/checkout", json={"plan_code": "PLAN_2_PORTFOLIO"})
    assert r.status_code == 403
    assert r.json()["detail"]["error_code"] == "STEP_UP_REQUIRED"


def test_client_approval_patch_requires_step_up(client, client_user, override_client_guard):
    # Router Depends(client_route_guard) uses dependency_overrides; _require_invoicing_enabled
    # calls client_route_guard by name — patch that name too.
    with patch("routes.client_approvals.client_route_guard", AsyncMock(return_value=client_user)):
        with patch(
            "routes.client_approvals.get_effective_flags",
            AsyncMock(return_value={"INVOICING": True}),
        ):
            with patch(
                "routes.client_approvals.approval_service.update_approval",
                AsyncMock(return_value={"invoice_id": "inv-1", "status": "approved"}),
            ):
                r = client.patch(
                    "/api/client/approvals/inv-1",
                    json={"action": "approved"},
                )
    assert r.status_code == 403
    assert r.json()["detail"]["error_code"] == "STEP_UP_REQUIRED"


def test_client_approval_patch_with_step_up_token(client, client_user, override_client_guard):
    step = create_step_up_token(client_user["portal_user_id"])
    with patch("routes.client_approvals.client_route_guard", AsyncMock(return_value=client_user)):
        with patch(
            "routes.client_approvals.get_effective_flags",
            AsyncMock(return_value={"INVOICING": True}),
        ):
            with patch(
                "routes.client_approvals.approval_service.update_approval",
                AsyncMock(return_value={"invoice_id": "inv-1", "status": "approved"}),
            ):
                r = client.patch(
                    "/api/client/approvals/inv-1",
                    json={"action": "approved"},
                    headers={"X-Step-Up-Token": step},
                )
    assert r.status_code == 200
    assert r.json().get("status") == "approved"
