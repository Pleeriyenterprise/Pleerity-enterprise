"""GET /api/jobs/{id}/assignable-contractors and POST /api/contractors (workflow surface)."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from routes import api_compliance_workflow as acw
from server import app
from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import build_runtime_contract

CLIENT_ID = "cli-wc"
JOB_ID = "wo-wc-1"


async def _fake_mw(request: Request):
    return {"client_id": CLIENT_ID, "portal_user_id": "pu-wc", "role": "ROLE_CLIENT_ADMIN"}


def _mock_evaluate_contract(fixed_contract):
    svc = CapabilityEnforcementService(db=None)

    async def _evaluate(client_id, capability_id, action, *, contract=None):
        return svc.evaluate_from_contract(fixed_contract, capability_id, action)

    return _evaluate


@pytest.fixture
def client_wf():
    app.dependency_overrides[acw._require_maintenance_jobs_read] = _fake_mw
    app.dependency_overrides[acw._require_maintenance_workflows] = _fake_mw
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(acw._require_maintenance_jobs_read, None)
    app.dependency_overrides.pop(acw._require_maintenance_workflows, None)


def test_get_assignable_contractors_requires_contractors_capability(client_wf):
    deny_contract = build_runtime_contract(
        client={"client_id": CLIENT_ID, "billing_plan": "PLAN_1_SOLO", "subscription_status": "ACTIVE"},
        billing={
            "client_id": CLIENT_ID,
            "subscription_status": "ACTIVE",
            "billing_lifecycle_state": "active",
            "canonical_entitlement_state": "ENABLED",
        },
    )
    with patch(
        "routes.api_compliance_workflow.CapabilityEnforcementService.evaluate",
        new=AsyncMock(side_effect=_mock_evaluate_contract(deny_contract)),
    ):
        res = client_wf.get(f"/api/jobs/{JOB_ID}/assignable-contractors")
    assert res.status_code == 403
    assert res.json()["detail"]["capability_id"] == "CAP_OPS_CONTRACTORS"


def test_get_assignable_contractors_delegates(client_wf):
    with patch.object(acw, "_enforce_capability", new=AsyncMock()):
        with patch.object(
            acw.contractor_service,
            "list_assignable_contractors_for_work_order",
            new_callable=AsyncMock,
            return_value={"contractors": [], "total": 0, "skip": 0, "limit": 100},
        ) as lst:
            res = client_wf.get(f"/api/jobs/{JOB_ID}/assignable-contractors")
    assert res.status_code == 200
    assert lst.await_args.kwargs["work_order_id"] == JOB_ID
    assert lst.await_args.kwargs["client_id"] == CLIENT_ID


def test_post_contractors_requires_phone_or_email(client_wf):
    with patch.object(acw, "_enforce_capability", new=AsyncMock()):
        res = client_wf.post(
            "/api/contractors",
            json={"company_name": "Acme", "trade_types": ["general"]},
        )
    assert res.status_code == 400


def test_post_assign_contractor_requires_contractors_capability(client_wf):
    wo = {"work_order_id": JOB_ID, "client_id": CLIENT_ID}
    deny_contract = build_runtime_contract(
        client={"client_id": CLIENT_ID, "billing_plan": "PLAN_1_SOLO", "subscription_status": "ACTIVE"},
        billing={
            "client_id": CLIENT_ID,
            "subscription_status": "ACTIVE",
            "billing_lifecycle_state": "active",
            "canonical_entitlement_state": "ENABLED",
        },
    )
    with patch(
        "routes.api_compliance_workflow.CapabilityEnforcementService.evaluate",
        new=AsyncMock(side_effect=_mock_evaluate_contract(deny_contract)),
    ):
        with patch.object(acw, "load_client_work_order", new_callable=AsyncMock, return_value=wo):
            res = client_wf.post(
                f"/api/jobs/{JOB_ID}/assign-contractor",
                json={"contractor_id": "ctr-blocked-1"},
            )
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "capability_denied"
    assert res.json()["detail"]["capability_id"] == "CAP_OPS_CONTRACTORS"


def test_post_assign_contractor_allowed_with_contractors_capability(client_wf):
    wo = {"work_order_id": JOB_ID, "client_id": CLIENT_ID}
    updated = {**wo, "contractor_id": "ctr-ok-1"}
    with patch.object(acw, "_enforce_capability", new=AsyncMock()):
        with patch.object(acw, "load_client_work_order", new_callable=AsyncMock, return_value=wo):
            with patch.object(acw, "_resolve_portal_job_assignment_profile", new_callable=AsyncMock, return_value={}):
                with patch.object(
                    acw.maintenance_service,
                    "update_work_order",
                    new_callable=AsyncMock,
                    return_value=updated,
                ):
                    res = client_wf.post(
                        f"/api/jobs/{JOB_ID}/assign-contractor",
                        json={"contractor_id": "ctr-ok-1"},
                    )
    assert res.status_code == 200


def test_post_contractors_creates_landlord_row(client_wf):
    created = {"contractor_id": "ctr-new-1", "company_name": "Acme Ltd", "source_type": "landlord_added"}
    create_mock = AsyncMock(return_value=created)

    with patch.object(acw, "_enforce_capability", new=AsyncMock()):
        with patch.object(acw.contractor_service, "create_contractor_for_client_job_portal", create_mock):
            with patch.object(acw, "create_audit_log", new_callable=AsyncMock):
                res = client_wf.post(
                    "/api/contractors",
                    json={
                        "company_name": "Acme Ltd",
                        "trade_types": ["plumbing"],
                        "email": "a@example.com",
                    },
                )
    assert res.status_code == 200
    assert res.json().get("contractor_id") == "ctr-new-1"
    assert create_mock.await_args.kwargs["client_id"] == CLIENT_ID
    assert create_mock.await_args.kwargs["company_name"] == "Acme Ltd"
