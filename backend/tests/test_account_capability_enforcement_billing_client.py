"""ILP-4 — customer billing route capability enforcement."""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from middleware import client_route_guard as middleware_client_route_guard
from routes import billing as billing_routes
from routes import client_billing as client_billing_routes
from server import app
from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import build_runtime_contract

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
CLIENT_ID = "c-ilp4-bill-1"

RECOVERY_LIFECYCLES = (
    "ACTIVE",
    "TRIAL",
    "GRACE_PERIOD",
    "CANCELLATION_SCHEDULED",
    "CANCELLED_IMMEDIATE",
    "SUBSCRIPTION_EXPIRED",
    "READ_ONLY",
    "SUSPENDED",
)

BILLING_RECOVERY_CAPS = (
    ("CAP_BILLING_VIEW", "read"),
    ("CAP_BILLING_CHECKOUT", "write"),
    ("CAP_BILLING_INVOICES", "read"),
    ("CAP_BILLING_PAYMENT_METHODS", "read"),
    ("CAP_SUB_MANAGE", "write"),
    ("CAP_SUB_CANCEL", "write"),
)


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
        "subscription_status": "ACTIVE",
        "billing_lifecycle_state": "active",
        "canonical_entitlement_state": "ENABLED",
    }
    base.update(overrides)
    return base


def _portal_user():
    return {
        "client_id": CLIENT_ID,
        "portal_user_id": "pu-ilp4-bill-1",
        "role": "ROLE_CLIENT",
    }


def _contract(client=None, billing=None, **kwargs):
    return build_runtime_contract(
        client=client or _client(),
        billing=billing or _billing(),
        now=NOW,
        **kwargs,
    )


LIFECYCLE_PRESETS = {
    "ACTIVE": (_client(), _billing()),
    "TRIAL": (_client(), _billing(subscription_status="TRIALING")),
    "GRACE_PERIOD": (
        _client(),
        _billing(
            subscription_status="PAST_DUE",
            billing_lifecycle_state="grace_period",
        ),
    ),
    "CANCELLATION_SCHEDULED": (
        _client(),
        _billing(
            subscription_status="ACTIVE",
            billing_lifecycle_state="cancel_at_period_end",
            cancel_at_period_end=True,
            current_period_end=PERIOD_END.isoformat(),
        ),
    ),
    "CANCELLED_IMMEDIATE": (
        _client(),
        _billing(subscription_status="CANCELED", billing_lifecycle_state="cancelled"),
    ),
    "SUBSCRIPTION_EXPIRED": (
        _client(),
        _billing(
            subscription_status="UNPAID",
            billing_lifecycle_state="expired",
        ),
    ),
    "READ_ONLY": (
        _client(),
        _billing(
            subscription_status="UNPAID",
            billing_lifecycle_state="expired",
            read_only_retention=True,
        ),
    ),
    "SUSPENDED": (
        _client(client_lifecycle_status="SUSPENDED"),
        _billing(),
    ),
    "ARCHIVED": (
        _client(is_deleted=True, client_lifecycle_status="ARCHIVED"),
        _billing(),
    ),
    "ACCOUNT_DELETED": (
        _client(is_deleted=True, client_lifecycle_status="ACCOUNT_DELETED"),
        _billing(),
    ),
    "UNKNOWN": (
        _client(),
        _billing(subscription_status="WEIRD", billing_lifecycle_state="active"),
    ),
}


def _mock_evaluate_contract(fixed_contract):
    svc = CapabilityEnforcementService(db=None)

    async def _evaluate(client_id, capability_id, action, *, contract=None):
        return svc.evaluate_from_contract(fixed_contract, capability_id, action)

    return _evaluate


def _expected_allowed(contract, cap_id: str, action: str) -> bool:
    return CapabilityEnforcementService(db=None).evaluate_from_contract(
        contract, cap_id, action
    ).allowed


def _assert_capability_denied(res, cap_id: str):
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["error"] == "capability_denied"
    assert detail["capability_id"] == cap_id


@pytest.fixture
def bill_user():
    return _portal_user()


@pytest.fixture
def override_guard(bill_user):
    async def _fake_guard(request: Request):
        return bill_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    with patch.object(
        billing_routes, "client_route_guard", new=AsyncMock(return_value=bill_user)
    ):
        with patch.object(
            client_billing_routes,
            "client_route_guard",
            new=AsyncMock(return_value=bill_user),
        ):
            yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


class TestBillingClientSourceGovernance:
    def test_billing_routes_use_capability_enforcement(self):
        source = open(billing_routes.__file__, encoding="utf-8").read()
        assert "enforce_feature" not in source
        assert "require_feature" not in source
        assert "canonical_entitlement_state" not in source
        assert "assert_client_capability" in source
        assert "CAP_BILLING_VIEW" in source
        assert "CAP_BILLING_CHECKOUT" in source
        assert "CAP_SUB_CANCEL" in source

    def test_client_billing_routes_use_capability_enforcement(self):
        source = open(client_billing_routes.__file__, encoding="utf-8").read()
        assert "enforce_feature" not in source
        assert "require_feature" not in source
        assert "assert_client_capability" in source
        assert "CAP_BILLING_INVOICES" in source


class TestBillingClientRuntimeMatrix:
    def test_billing_capabilities_in_contract(self):
        contract = _contract()
        for cap in (
            "CAP_BILLING_INVOICES",
            "CAP_BILLING_PAYMENT_METHODS",
            "CAP_SUB_CANCEL",
            "CAP_BILLING_VIEW",
            "CAP_BILLING_CHECKOUT",
            "CAP_SUB_MANAGE",
        ):
            assert cap in contract["capabilities"]

    def test_runtime_resolver_count_includes_billing_caps(self):
        from services.account_lifecycle_runtime_contract import _BASE_CAPABILITY_MATRIX

        assert len(_BASE_CAPABILITY_MATRIX) == 67


class TestBillingRecoveryNotBlocked:
    @pytest.mark.parametrize("lifecycle", RECOVERY_LIFECYCLES)
    @pytest.mark.parametrize("cap_id,action", BILLING_RECOVERY_CAPS)
    def test_recovery_lifecycle_allows_billing_caps(self, lifecycle, cap_id, action):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        assert _expected_allowed(contract, cap_id, action), (lifecycle, cap_id, action)


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
class TestBillingClientLifecycle:
    def test_billing_status(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_BILLING_VIEW"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "middleware.capability_gating.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "routes.billing.stripe_service.get_subscription_status",
                        new=AsyncMock(return_value={"has_subscription": False}),
                    )
                )
                stack.enter_context(
                    patch(
                        "routes.billing.database.get_db",
                        return_value=MagicMock(
                            properties=MagicMock(
                                count_documents=AsyncMock(return_value=0)
                            )
                        ),
                    )
                )
            res = client.get("/api/billing/status")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_billing_invoices(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_BILLING_INVOICES"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "middleware.capability_gating.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "routes.billing.stripe_service.list_invoices",
                        new=AsyncMock(return_value={"invoices": []}),
                    )
                )
            res = client.get("/api/billing/invoices")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_payment_method_summary(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_BILLING_PAYMENT_METHODS"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "middleware.capability_gating.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "routes.billing.stripe_service.get_payment_method_summary",
                        new=AsyncMock(return_value=None),
                    )
                )
            res = client.get("/api/billing/payment-method-summary")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_client_receipts(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_BILLING_INVOICES"
        allowed = _expected_allowed(contract, cap, "read")

        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=[])

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "middleware.capability_gating.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                mock_col = MagicMock()
                mock_col.find = MagicMock(return_value=mock_cursor)
                mock_db = MagicMock()
                mock_db.__getitem__ = MagicMock(return_value=mock_col)
                stack.enter_context(
                    patch(
                        "routes.client_billing.database.get_db",
                        return_value=mock_db,
                    )
                )
            res = client.get("/api/client/billing/receipts")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_billing_checkout_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_BILLING_CHECKOUT"
        allowed = _expected_allowed(contract, cap, "write")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "middleware.capability_gating.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "routes.billing.require_recent_step_up",
                        new=AsyncMock(),
                    )
                )
                stack.enter_context(
                    patch(
                        "routes.billing.create_audit_log",
                        new=AsyncMock(),
                    )
                )
                stack.enter_context(
                    patch(
                        "routes.billing.stripe_service.create_upgrade_session",
                        new=AsyncMock(return_value={"checkout_url": "https://stripe.test"}),
                    )
                )
            res = client.post(
                "/api/billing/checkout",
                json={"plan_code": "PLAN_2_PORTFOLIO"},
            )

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_billing_cancel_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_SUB_CANCEL"
        allowed = _expected_allowed(contract, cap, "write")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "middleware.capability_gating.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "routes.billing.require_recent_step_up",
                        new=AsyncMock(),
                    )
                )
                stack.enter_context(
                    patch(
                        "routes.billing.stripe_service.cancel_subscription",
                        new=AsyncMock(return_value={"status": "cancelled"}),
                    )
                )
            res = client.post(
                "/api/billing/cancel",
                json={"cancel_immediately": False},
            )

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)
