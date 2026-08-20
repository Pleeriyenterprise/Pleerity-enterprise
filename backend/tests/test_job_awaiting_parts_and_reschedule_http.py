"""POST /api/jobs/{id}/awaiting-parts and mark-reschedule-required."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from routes import api_compliance_workflow as acw
from server import app

CLIENT_ID = "cli-apr"
WO_M = "wo-maint-ap"
WO_C = "wo-comp-ap"


async def _fake_mw(request: Request):
    return {"client_id": CLIENT_ID, "portal_user_id": "pu-apr", "role": "ROLE_CLIENT_ADMIN"}


@pytest.fixture
def client_jobs():
    app.dependency_overrides[acw._require_maintenance_workflows] = _fake_mw
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(acw._require_maintenance_workflows, None)


def test_awaiting_parts_rejects_non_maintenance(client_jobs):
    wo = {
        "work_order_id": WO_C,
        "client_id": CLIENT_ID,
        "work_order_kind": "COMPLIANCE",
        "status": "IN_PROGRESS",
        "contractor_id": "c1",
    }
    with patch.object(acw, "load_client_work_order", new_callable=AsyncMock, return_value=wo):
        res = client_jobs.post(f"/api/jobs/{WO_C}/awaiting-parts", json={})
    assert res.status_code == 400
    assert "maintenance" in res.json().get("detail", "").lower()


def test_awaiting_parts_rejects_not_in_progress(client_jobs):
    wo = {
        "work_order_id": WO_M,
        "client_id": CLIENT_ID,
        "work_order_kind": "MAINTENANCE",
        "status": "ASSIGNED",
        "contractor_id": "c1",
    }
    with patch.object(acw, "load_client_work_order", new_callable=AsyncMock, return_value=wo):
        res = client_jobs.post(f"/api/jobs/{WO_M}/awaiting-parts", json={})
    assert res.status_code == 400


def test_awaiting_parts_ok_patches_update(client_jobs):
    wo = {
        "work_order_id": WO_M,
        "client_id": CLIENT_ID,
        "work_order_kind": "MAINTENANCE",
        "status": "IN_PROGRESS",
        "contractor_id": "c1",
    }

    async def load_wo(*_a, **_k):
        return wo

    upd = AsyncMock()

    with patch.object(acw, "load_client_work_order", side_effect=load_wo), patch.object(
        acw.maintenance_service, "update_work_order", upd
    ), patch.object(acw, "serialize_landlord_job", new=AsyncMock(return_value={"work_order_id": WO_M})):
        res = client_jobs.post(f"/api/jobs/{WO_M}/awaiting-parts", json={})
    assert res.status_code == 200
    assert upd.await_count == 1


def test_mark_reschedule_required_calls_update(client_jobs):
    wo = {
        "work_order_id": WO_C,
        "client_id": CLIENT_ID,
        "work_order_kind": "COMPLIANCE",
        "status": "IN_PROGRESS",
        "contractor_id": "c1",
    }
    upd = AsyncMock()

    async def load_wo(*_a, **_k):
        return wo

    with patch.object(acw, "load_client_work_order", side_effect=load_wo), patch.object(
        acw.maintenance_service, "update_work_order", upd
    ), patch.object(acw, "serialize_landlord_job", new=AsyncMock(return_value={"work_order_id": WO_C})):
        res = client_jobs.post(f"/api/jobs/{WO_C}/mark-reschedule-required", json={})
    assert res.status_code == 200
    assert upd.await_count == 1
    call_kw = upd.await_args.kwargs
    assert call_kw.get("operational_exception") == "RESCHEDULE_REQUIRED"
