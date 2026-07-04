"""ILP-4 — rent operations and approvals capability enforcement."""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request

from middleware import client_route_guard as middleware_client_route_guard
from routes import client_approvals as approvals_routes
from routes import client_rent_operations as rent_routes
from server import app
from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import build_runtime_contract

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)

CLIENT_ID = "c-ilp4-rent-1"


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
        "portal_user_id": "pu-ilp4-rent-1",
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
    "READ_ONLY": (
        _client(),
        _billing(
            subscription_status="UNPAID",
            billing_lifecycle_state="expired",
            read_only_retention=True,
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
    "SUSPENDED": (
        _client(client_lifecycle_status="SUSPENDED"),
        _billing(),
    ),
    "ARCHIVED": (
        _client(is_deleted=True, client_lifecycle_status="ARCHIVED"),
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


def _svc():
    return CapabilityEnforcementService(db=None)


def _expected_allowed(contract, cap_id: str, action: str) -> bool:
    return _svc().evaluate_from_contract(contract, cap_id, action).allowed


def _assert_capability_denied(res, cap_id: str):
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["error"] == "capability_denied"
    assert detail["capability_id"] == cap_id


@pytest.fixture
def rent_user():
    return _portal_user()


@pytest.fixture
def override_guard(rent_user):
    async def _fake_guard(request: Request):
        return rent_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    with patch.object(rent_routes, "client_route_guard", new=AsyncMock(return_value=rent_user)):
        with patch.object(approvals_routes, "client_route_guard", new=AsyncMock(return_value=rent_user)):
            yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


class TestRentApprovalsSourceGovernance:
    def test_rent_module_uses_capability_enforcement(self):
        source = open(rent_routes.__file__, encoding="utf-8").read()
        assert "get_effective_flags" not in source
        assert "RENT_OPERATIONS" not in source
        assert "CAP_OPS_RENT" in source
        assert "_enforce_capability" in source

    def test_approvals_module_uses_capability_enforcement(self):
        source = open(approvals_routes.__file__, encoding="utf-8").read()
        assert "get_effective_flags" not in source
        assert "INVOICING" not in source
        assert "CAP_OPS_APPROVALS" in source
        assert "_enforce_capability" in source


class TestRentApprovalsRuntimeMatrix:
    def test_ops_capabilities_in_contract(self):
        contract = _contract()
        for cap in ("CAP_OPS_RENT", "CAP_OPS_APPROVALS"):
            assert cap in contract["capabilities"]


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
class TestRentApprovalsLifecycle:
    def test_rent_ledgers_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_OPS_RENT"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "routes.client_rent_operations.rent_ledger_service.list_ledgers",
                        new=AsyncMock(return_value={"ledgers": []}),
                    )
                )
            res = client.get("/api/client/operations/rent/ledgers")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_rent_payment_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_OPS_RENT"
        allowed = _expected_allowed(contract, cap, "write")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "routes.client_rent_operations.rent_payment_service.record_payment",
                        new=AsyncMock(return_value={"payment_id": "p-1"}),
                    )
                )
            res = client.post(
                "/api/client/operations/rent/payments",
                json={
                    "amount_minor": 10000,
                    "payment_date": "2026-06-15",
                    "ledger_id": "rl-1",
                },
            )

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_approvals_list_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_OPS_APPROVALS"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "routes.client_approvals.approval_service.list_approvals",
                        new=AsyncMock(return_value={"approvals": []}),
                    )
                )
            res = client.get("/api/client/approvals")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_approvals_update_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_OPS_APPROVALS"
        allowed = _expected_allowed(contract, cap, "write")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                stack.enter_context(
                    patch(
                        "routes.client_approvals.require_recent_step_up",
                        new=AsyncMock(),
                    )
                )
                stack.enter_context(
                    patch(
                        "routes.client_approvals.approval_service.update_approval",
                        new=AsyncMock(return_value={"invoice_id": "inv-1"}),
                    )
                )
            res = client.patch(
                "/api/client/approvals/inv-1",
                json={"action": "approved"},
            )

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)


class TestRentApprovalsWriteBlockedOnReadGrant:
    def test_read_only_lifecycle_denies_rent_mutations(self, client, override_guard):
        client_doc, billing = LIFECYCLE_PRESETS["READ_ONLY"]
        contract = _contract(client_doc, billing)
        cap = "CAP_OPS_RENT"
        assert not _expected_allowed(contract, cap, "write")

        with patch(
            "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
            new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
        ):
            res = client.post(
                "/api/client/operations/rent/payments",
                json={
                    "amount_minor": 5000,
                    "payment_date": "2026-06-15",
                    "ledger_id": "rl-1",
                },
            )
        _assert_capability_denied(res, cap)

    def test_read_grant_semantics_block_write(self):
        contract = _contract(
            _client(),
            _billing(
                subscription_status="UNPAID",
                billing_lifecycle_state="expired",
                read_only_retention=True,
            ),
        )
        svc = _svc()
        read_decision = svc.evaluate_from_contract(contract, "CAP_LEDGER_VIEW", "read")
        write_decision = svc.evaluate_from_contract(contract, "CAP_LEDGER_VIEW", "write")
        assert read_decision.allowed is True
        assert write_decision.allowed is False
        assert write_decision.reason_code == "read_only_blocked"
