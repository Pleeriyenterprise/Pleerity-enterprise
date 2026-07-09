"""ILP-4 — compliance workflow, execution, and compliance pack capability enforcement."""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from middleware import client_route_guard as middleware_client_route_guard
from routes import api_compliance_workflow as workflow_routes
from routes import client as client_routes
from routes import client_compliance_execution as execution_routes
from routes import compliance_delivery_audit as delivery_routes
from server import app
from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import build_runtime_contract

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)

CLIENT_ID = "c-ilp4-cwf-1"
REQ_ID = "req-cwf-1"
JOB_ID = "wo-cwf-1"
PROP_ID = "prop-cwf-1"


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
        "portal_user_id": "pu-ilp4-cwf-1",
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
def cwf_user():
    return _portal_user()


@pytest.fixture
def override_guard(cwf_user):
    async def _fake_guard(request: Request):
        return cwf_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    with patch.object(workflow_routes, "client_route_guard", new=AsyncMock(return_value=cwf_user)):
        with patch.object(execution_routes, "client_route_guard", new=AsyncMock(return_value=cwf_user)):
            with patch.object(delivery_routes, "client_route_guard", new=AsyncMock(return_value=cwf_user)):
                with patch.object(client_routes, "client_route_guard", new=AsyncMock(return_value=cwf_user)):
                    yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


class TestComplianceWorkflowSourceGovernance:
    def test_workflow_module_uses_capability_enforcement(self):
        source = open(workflow_routes.__file__, encoding="utf-8").read()
        assert "get_effective_flags" not in source
        assert "COMPLIANCE_ENGINE" not in source
        assert "MAINTENANCE_WORKFLOWS" not in source
        assert "CONTRACTOR_NETWORK" not in source
        assert "plan_registry" not in source
        assert "_enforce_capability" in source
        assert "CAP_OPS_COMPLIANCE_REVIEW" in source
        assert "CAP_OPS_MAINTENANCE" in source
        assert "CAP_OPS_CONTRACTORS" in source
        assert "CAP_TODAY_VIEW" in source
        assert "CAP_TODAY_ACT" in source

    def test_execution_module_uses_capability_enforcement(self):
        source = open(execution_routes.__file__, encoding="utf-8").read()
        assert "get_effective_flags" not in source
        assert "COMPLIANCE_ENGINE" not in source
        assert "CAP_REQ_RESOLVE" in source
        assert "CAP_OPS_MAINTENANCE" in source

    def test_delivery_audit_client_routes_use_capabilities(self):
        source = open(delivery_routes.__file__, encoding="utf-8").read()
        admin_start = source.index("admin_router = APIRouter")
        client_block = source[:admin_start]
        assert "plan_registry" not in client_block
        assert "assert_client_capability" in source
        assert "CAP_TENANT_MANAGE" in source
        assert "CAP_REPORT_AUDIT_PACK" in source
        assert "CAP_REPORT_GENERATE_PDF" in source


class TestComplianceWorkflowRuntimeMatrix:
    def test_compliance_review_capability_in_contract(self):
        contract = _contract()
        assert "CAP_OPS_COMPLIANCE_REVIEW" in contract["capabilities"]


@pytest.mark.parametrize("lifecycle", list(LIFECYCLE_PRESETS.keys()))
class TestComplianceWorkflowLifecycle:
    def test_requirement_view_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_REQ_VIEW"
        allowed = _expected_allowed(contract, cap, "read")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                mock_db = MagicMock()
                mock_db.requirements.find_one = AsyncMock(return_value=None)
                stack.enter_context(
                    patch(
                        "routes.api_compliance_workflow.database.get_db",
                        return_value=mock_db,
                    )
                )
            res = client.get(f"/api/requirements/{REQ_ID}")

        if allowed:
            assert res.status_code == 404
        else:
            _assert_capability_denied(res, cap)

    def test_today_view_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_TODAY_VIEW"
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
                        "routes.api_compliance_workflow.get_unified_tasks_for_client",
                        new=AsyncMock(return_value={"tasks": {}}),
                    )
                )
                stack.enter_context(
                    patch(
                        "services.rent_attention_projection.list_rent_attention_tasks",
                        new=AsyncMock(return_value=[]),
                    )
                )
            res = client.get("/api/today/items")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_today_act_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_TODAY_ACT"
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
                        "routes.api_compliance_workflow.apply_task_action",
                        new=AsyncMock(return_value={"ok": True}),
                    )
                )
            res = client.post(f"/api/today/items/item-1/snooze", json={"days": 1})

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_compliance_job_create_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_OPS_COMPLIANCE_REVIEW"
        allowed = _expected_allowed(contract, cap, "write") and _expected_allowed(
            contract, "CAP_OPS_MAINTENANCE", "write"
        )

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "services.account_capability_enforcement.CapabilityEnforcementService.evaluate",
                    new=AsyncMock(side_effect=_mock_evaluate_contract(contract)),
                )
            )
            if allowed:
                mock_db = MagicMock()
                mock_db.requirements.find_one = AsyncMock(return_value=None)
                stack.enter_context(
                    patch(
                        "routes.api_compliance_workflow.database.get_db",
                        return_value=mock_db,
                    )
                )
            res = client.post(
                f"/api/requirements/{REQ_ID}/jobs",
                json={"compliance_purpose": "inspection"},
            )

        if allowed:
            assert res.status_code == 404
        else:
            _assert_capability_denied(res, cap)

    def test_audit_pack_generate_write(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_REPORT_AUDIT_PACK"
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
                        "routes.compliance_delivery_audit.audit_pack.build_compliance_audit_pack",
                        new=AsyncMock(return_value={"pack_id": "p1"}),
                    )
                )
            res = client.post(
                "/api/client/compliance/audit-pack/generate",
                json={"property_id": PROP_ID},
            )

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_compliance_pack_preview_read(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        cap = "CAP_REPORT_DOWNLOAD"
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
                        "services.compliance_pack.compliance_pack_service.get_pack_preview",
                        new=AsyncMock(return_value={"items": []}),
                    )
                )
            res = client.get(f"/api/client/compliance-pack/{PROP_ID}/preview")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, cap)

    def test_contractors_read_on_assignable_list(self, client, override_guard, lifecycle):
        client_doc, billing = LIFECYCLE_PRESETS[lifecycle]
        contract = _contract(client_doc, billing)
        maint_allowed = _expected_allowed(contract, "CAP_OPS_MAINTENANCE", "read")
        contractors_allowed = _expected_allowed(contract, "CAP_OPS_CONTRACTORS", "read")
        allowed = maint_allowed and contractors_allowed
        if not maint_allowed:
            deny_cap = "CAP_OPS_MAINTENANCE"
        elif not contractors_allowed:
            deny_cap = "CAP_OPS_CONTRACTORS"
        else:
            deny_cap = "CAP_OPS_CONTRACTORS"

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
                        "routes.api_compliance_workflow.contractor_service.list_assignable_contractors_for_work_order",
                        new=AsyncMock(return_value={"contractors": [], "total": 0}),
                    )
                )
            res = client.get(f"/api/jobs/{JOB_ID}/assignable-contractors")

        if allowed:
            assert res.status_code == 200
        else:
            _assert_capability_denied(res, deny_cap)
