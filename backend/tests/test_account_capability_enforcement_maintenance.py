"""ILP-4 — maintenance and contractors capability enforcement."""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from middleware import client_route_guard as middleware_client_route_guard
from routes import client as client_routes
from routes import client_maintenance as maintenance_routes
from server import app
from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import build_runtime_contract

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
GRACE_END = datetime(2026, 6, 20, 0, 0, 0, tzinfo=timezone.utc)

CLIENT_ID = "c-ilp4-maint-1"


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
        "portal_user_id": "pu-ilp4-maint-1",
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
def maint_user():
    return _portal_user()


@pytest.fixture
def override_guard(maint_user):
    async def _fake_guard(request: Request):
        return maint_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    with patch.object(client_routes, "client_route_guard", new=AsyncMock(return_value=maint_user)):
        with patch.object(maintenance_routes, "client_route_guard", new=AsyncMock(return_value=maint_user)):
            yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


class TestMaintenanceSourceGovernance:
    def test_maintenance_routes_use_capability_enforcement(self):
        source = open(maintenance_routes.__file__, encoding="utf-8").read()
        route_start = source.index('@router.get("/maintenance/work-orders")')
        block = source[route_start:]
        assert "enforce_feature" not in block
        assert "_require_maintenance_enabled" in block
        assert "_enforce_capability" in block
        assert "CAP_OPS_MAINTENANCE" in block
        assert "CAP_OPS_PREDICTIVE" in block
        assert "CAP_OPS_CONTRACTORS" in block
        assert block.count("get_effective_flags(") == 0
        assert "COMPLIANCE_ENGINE" in block

    def test_client_contractor_routes_use_capabilities(self):
        source = open(client_routes.__file__, encoding="utf-8").read()
        start = source.index('@router.get("/contractors")')
        end = source.index('@router.get("/documents")')
        block = source[start:end]
        assert "get_effective_flags" not in block
        assert 'client_require_capability("CAP_OPS_CONTRACTORS"' in block


class TestMaintenanceRuntimeMatrix:
    def test_ops_capabilities_in_contract(self):
        contract = _contract()
        for cap in ("CAP_OPS_MAINTENANCE", "CAP_OPS_CONTRACTORS", "CAP_OPS_PREDICTIVE"):
            assert cap in contract["capabilities"]


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
class TestMaintenanceContractorsLifecycle:
    def test_maintenance_work_orders_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_OPS_MAINTENANCE"
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
                        "routes.client_maintenance.maintenance_service.list_work_orders",
                        new=AsyncMock(return_value={"work_orders": []}),
                    )
                )
            res = client.get("/api/client/maintenance/work-orders")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_maintenance_issue_create_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_OPS_MAINTENANCE"
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
                        "routes.client_maintenance.maintenance_issues_service.create_issue",
                        new=AsyncMock(return_value={"issue_id": "i-1"}),
                    )
                )
                stack.enter_context(
                    patch(
                        "routes.client_maintenance.issue_create_begin",
                        new=AsyncMock(return_value=("new", None)),
                    )
                )
                stack.enter_context(
                    patch(
                        "routes.client_maintenance.issue_create_complete",
                        new=AsyncMock(),
                    )
                )
                stack.enter_context(
                    patch("routes.client_maintenance.create_audit_log", new=AsyncMock())
                )
                stack.enter_context(
                    patch(
                        "services.operational_surface_cache.invalidate_client_operational_surfaces",
                        new=MagicMock(),
                    )
                )
            res = client.post(
                "/api/client/maintenance/issues",
                json={"property_id": "p-1", "description": "Leak"},
            )

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_contractors_list_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_OPS_CONTRACTORS"
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
                        "routes.client.contractor_service.list_contractors_for_client",
                        new=AsyncMock(return_value={"contractors": []}),
                    )
                )
            res = client.get("/api/client/contractors")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_contractors_create_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_OPS_CONTRACTORS"
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
                        "routes.client.contractor_service.create_contractor_landlord",
                        new=AsyncMock(return_value={"contractor_id": "c-1"}),
                    )
                )
                stack.enter_context(
                    patch("utils.audit.create_audit_log", new=AsyncMock())
                )
            res = client.post(
                "/api/client/contractors",
                json={
                    "company_name": "Acme Repairs",
                    "trade_types": ["plumbing"],
                    "email": "a@example.com",
                },
            )

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)


class TestMaintenanceWriteBlockedOnReadGrant:
    def test_read_only_lifecycle_denies_maintenance_mutations(self, client, override_guard):
        """READ_ONLY lifecycle matrix denies CAP_OPS_MAINTENANCE (not read-retention)."""
        client_doc, billing = LIFECYCLE_PRESETS["READ_ONLY"]
        contract = _contract(client_doc, billing)
        cap = "CAP_OPS_MAINTENANCE"
        assert not _expected_allowed(contract, cap, "read")
        assert not _expected_allowed(contract, cap, "write")

        with patch(
            "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
            new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
        ):
            res = client.post(
                "/api/client/maintenance/work-orders",
                json={"property_id": "p-1", "description": "Fix tap"},
            )
        _assert_capability_denied(res, cap)

    def test_read_grant_semantics_block_write(self):
        """READ grant allows read actions; write actions return READ_ONLY_BLOCKED."""
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
