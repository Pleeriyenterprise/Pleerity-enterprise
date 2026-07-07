"""
P0 — Platform Service Convergence Audit regression tests.

Ensures route-local CAP_* evaluation uses the request-scoped Runtime Contract
(never duplicate resolution) and documents authority convergence for portal services.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from middleware.capability_gating import enforce_route_capability
from services.account_lifecycle_runtime_contract import build_runtime_contract

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROUTES_DIR = BACKEND_ROOT / "routes"

ROUTE_MODULES_USING_ENFORCE_ROUTE = (
    "calendar.py",
    "assistant.py",
    "api_compliance_workflow.py",
    "client_compliance_execution.py",
    "client_approvals.py",
    "client_rent_operations.py",
    "client_maintenance.py",
    "profile.py",
)

FORBIDDEN_DUPLICATE_RESOLVE = '.evaluate(\n        client_id, capability_id, action\n    )'


def _make_request(path: str = "/api/calendar/events") -> Request:
    scope = {"type": "http", "method": "GET", "path": path, "headers": []}
    return Request(scope)


def _active_contract():
    return build_runtime_contract(
        client={"client_id": "svc-audit", "billing_plan": "PLAN_3_PRO", "onboarding_status": "PROVISIONED"},
        billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
        now=datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc),
    )


@pytest.mark.parametrize("module", ROUTE_MODULES_USING_ENFORCE_ROUTE)
def test_route_modules_delegate_to_enforce_route_capability(module):
    text = (ROUTES_DIR / module).read_text(encoding="utf-8")
    assert "enforce_route_capability" in text, f"{module} must use shared enforce_route_capability"
    assert FORBIDDEN_DUPLICATE_RESOLVE not in text, f"{module} must not re-resolve contract without attachment"


def test_client_routes_pass_attached_contract_for_inline_evaluate():
    text = (ROUTES_DIR / "client.py").read_text(encoding="utf-8")
    assert 'contract=user.get("runtime_contract")' in text


@pytest.mark.asyncio
async def test_enforce_route_capability_uses_attached_contract_not_reload():
    contract = _active_contract()
    user = {"client_id": "svc-audit", "role": "ROLE_CLIENT", "runtime_contract": contract}
    request = _make_request()
    request.state.runtime_contract = contract

    with patch(
        "middleware.capability_gating.CapabilityEnforcementService.load_contract",
        new=AsyncMock(side_effect=AssertionError("must not reload contract")),
    ):
        decision = await enforce_route_capability(
            user, "CAP_CALENDAR_VIEW", "read", request=request
        )
    assert decision.allowed


@pytest.mark.asyncio
async def test_enforce_route_capability_denial_includes_contract_context():
    contract = build_runtime_contract(
        client={"client_id": "svc-audit", "billing_plan": "PLAN_1_SOLO"},
        billing={"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"},
        now=datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc),
    )
    user = {"client_id": "svc-audit", "role": "ROLE_CLIENT", "runtime_contract": contract}

    with pytest.raises(HTTPException) as exc:
        await enforce_route_capability(user, "CAP_PROP_CREATE", "write")
    detail = exc.value.detail
    assert detail.get("reason_code") in ("denied", "plan_denied", "read_only_blocked")
    assert detail.get("lifecycle_state") == "CANCELLED_IMMEDIATE"


PORTAL_SERVICES = (
    "Today",
    "Dashboard",
    "Command Center",
    "Properties",
    "Requirements",
    "Documents",
    "Jobs",
    "Issues",
    "Calendar",
    "Notifications",
    "Analytics",
    "Reports",
    "Billing",
    "Profile",
    "Automation",
    "Discovery",
)


@pytest.mark.parametrize("service", PORTAL_SERVICES)
def test_service_documented_in_convergence_matrix(service):
    matrix = (BACKEND_ROOT / "docs" / "audit" / "p0_platform_service_convergence_audit_01" / "SERVICE_CONVERGENCE_MATRIX.json").read_text(
        encoding="utf-8"
    )
    assert service in matrix


def test_client_portal_routes_avoid_get_effective_flags():
    offenders = []
    for name in ("client.py", "client_maintenance.py", "api_compliance_workflow.py"):
        text = (ROUTES_DIR / name).read_text(encoding="utf-8")
        if "get_effective_flags" in text:
            offenders.append(name)
    assert not offenders, offenders


def test_contract_feature_enabled_uses_mapped_capabilities():
    from services.capability_compatibility import contract_feature_enabled

    contract = {
        "capabilities": {
            "CAP_OPS_MAINTENANCE": "ALLOW",
            "CAP_OPS_ISSUES_VIEW": "ALLOW",
            "CAP_OPS_RENT": "ALLOW",
        },
        "lifecycle_state": "ACTIVE",
        "portal_mode": "FULL_ACCESS",
    }
    assert contract_feature_enabled(contract, "maintenance_workflows", "read")
    assert contract_feature_enabled(contract, "rent_operations", "read")
    assert not contract_feature_enabled(contract, "predictive_maintenance", "read")
