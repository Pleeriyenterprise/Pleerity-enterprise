"""P0 billing recovery portal authorization — portal drift fallback and capability matrix."""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from middleware import client_route_guard as middleware_client_route_guard
from routes import billing as billing_routes
from server import app
from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import build_runtime_contract
from services.billing_recovery_authorization import billing_recovery_write_allowed
from services.stripe_mode_containment_service import StripeModeDriftError, STRIPE_CUSTOMER_MODE_DRIFT
from services.stripe_service import StripeService

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
CLIENT_ID = "c-p0-bill-recovery-1"


def _client(**overrides):
    base = {
        "client_id": CLIENT_ID,
        "billing_plan": "PLAN_3_PRO",
        "subscription_status": "ACTIVE",
    }
    base.update(overrides)
    return base


def _billing(**overrides):
    base = {
        "client_id": CLIENT_ID,
        "subscription_status": "CANCELED",
        "billing_lifecycle_state": "cancelled",
        "current_plan_code": "PLAN_3_PRO",
        "stripe_customer_id": "cus_test_1",
        "stripe_mode_verification_status": "MODE_UNVERIFIED",
    }
    base.update(overrides)
    return base


def _portal_user(contract):
    return {
        "client_id": CLIENT_ID,
        "portal_user_id": "pu-p0-bill-recovery-1",
        "role": "ROLE_CLIENT",
        "runtime_contract": contract,
    }


def _contract(client=None, billing=None, **kwargs):
    return build_runtime_contract(
        client=client or _client(client_lifecycle_status="SUSPENDED"),
        billing=billing or _billing(),
        now=NOW,
        **kwargs,
    )


def _mock_evaluate_contract(fixed_contract):
    svc = CapabilityEnforcementService(db=None)

    async def _evaluate(client_id, capability_id, action, *, contract=None):
        return svc.evaluate_from_contract(fixed_contract, capability_id, action)

    return _evaluate


@pytest.fixture
def suspended_contract():
    return _contract()


@pytest.fixture
def override_guard(suspended_contract):
    user = _portal_user(suspended_contract)

    async def _fake_guard(request: Request):
        return user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    with patch.object(
        billing_routes, "client_route_guard", new=AsyncMock(return_value=user)
    ):
        yield user
    app.dependency_overrides.pop(middleware_client_route_guard, None)


class TestBillingRecoveryAuthorizationHelpers:
    def test_suspended_allows_recovery_write(self, suspended_contract):
        assert billing_recovery_write_allowed(suspended_contract)

    def test_archived_denies_recovery_write(self):
        contract = _contract(
            _client(is_deleted=True, client_lifecycle_status="ARCHIVED"),
            _billing(),
        )
        assert not billing_recovery_write_allowed(contract)

    def test_account_deleted_denies_recovery_write(self):
        contract = _contract(
            _client(is_deleted=True, client_lifecycle_status="ACCOUNT_DELETED"),
            _billing(),
        )
        assert not billing_recovery_write_allowed(contract)


class TestBillingPortalRecoveryFallback:
    def test_portal_mode_unverified_falls_back_to_checkout(
        self, client, override_guard, suspended_contract
    ):
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "middleware.capability_gating.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(suspended_contract)),
                )
            )
            stack.enter_context(
                patch("routes.billing.require_recent_step_up", new=AsyncMock())
            )
            stack.enter_context(
                patch(
                    "routes.billing.stripe_service.create_billing_portal_session",
                    new=AsyncMock(
                        return_value={
                            "checkout_url": "https://checkout.stripe.test/recovery",
                            "recovery_path": "deployment_checkout",
                            "recovery_guidance": "Complete payment in Stripe to restore your subscription.",
                        }
                    ),
                )
            )
            res = client.post("/api/billing/portal", json={})

        assert res.status_code == 200
        body = res.json()
        assert body["checkout_url"].startswith("https://checkout.stripe")
        assert body["recovery_path"] == "deployment_checkout"

    def test_archived_portal_denied(self, client, suspended_contract):
        archived_contract = _contract(
            _client(is_deleted=True, client_lifecycle_status="ARCHIVED"),
            _billing(),
        )
        user = _portal_user(archived_contract)

        async def _fake_guard(request: Request):
            return user

        app.dependency_overrides[middleware_client_route_guard] = _fake_guard
        try:
            with patch.object(
                billing_routes, "client_route_guard", new=AsyncMock(return_value=user)
            ):
                with patch(
                    "middleware.capability_gating.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(archived_contract)),
                ):
                    res = client.post("/api/billing/portal", json={})
        finally:
            app.dependency_overrides.pop(middleware_client_route_guard, None)

        assert res.status_code == 403
        assert res.json()["detail"]["error"] == "capability_denied"


@pytest.mark.asyncio
async def test_create_billing_portal_session_drift_fallback():
    svc = StripeService()
    contract = _contract()
    billing = _billing()

    mock_db = MagicMock()
    mock_db.client_billing.find_one = AsyncMock(return_value=billing)

    drift = StripeModeDriftError(
        STRIPE_CUSTOMER_MODE_DRIFT,
        client_id=CLIENT_ID,
        operation="billing_portal",
        recovery_action="MODE_UNVERIFIED",
    )

    svc.create_upgrade_session = AsyncMock(
        return_value={
            "checkout_url": "https://checkout.stripe.test/cs_recovery",
            "plan_change_path": "deployment_checkout",
            "session_id": "cs_test",
        }
    )

    with patch("services.stripe_service.database.get_db", return_value=mock_db):
        with patch("services.stripe_service.get_stripe_mode", return_value="test"):
            with patch("services.stripe_service.configure_stripe_sdk"):
                with patch(
                    "services.stripe_service.resolve_stripe_context",
                    new=AsyncMock(side_effect=drift),
                ):
                    result = await svc.create_billing_portal_session(
                        CLIENT_ID,
                        "https://app.example",
                        runtime_contract=contract,
                    )

    svc.create_upgrade_session.assert_awaited_once()
    assert result["checkout_url"].startswith("https://checkout.stripe")
    assert result["recovery_path"] == "deployment_checkout"
