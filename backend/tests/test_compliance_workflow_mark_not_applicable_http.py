"""HTTP tests: POST /api/requirements/{id}/mark-not-applicable with active compliance job (409 + confirm)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from database import database as db_singleton
from routes import api_compliance_workflow as acw
from server import app

CLIENT_ID = "cli-na-test"
REQ_ID = "req-na-test"
PROP_ID = "prop-na-test"

PROP_DOC = {
    "property_id": PROP_ID,
    "client_id": CLIENT_ID,
    "jurisdiction": "England",
    "property_type": "residential",
    "tenancy_active": True,
    "has_gas_supply": True,
    "deposit_taken": True,
    "furnished": False,
    "is_hmo": False,
}


async def _fake_client_guard(request: Request):
    return {
        "client_id": CLIENT_ID,
        "portal_user_id": "pu-na-test",
        "role": "ROLE_CLIENT_ADMIN",
        "email": "na-test@test.com",
    }


def _mock_db_for_requirement():
    requirements = {
        "req": {
            "requirement_id": REQ_ID,
            "client_id": CLIENT_ID,
            "property_id": PROP_ID,
            "requirement_code": "gas_safety",
            "requirement_type": "gas_safety",
            "jurisdiction": "England",
            "applicability": "REQUIRED",
            "status": "PENDING",
            "client_surface_visible": True,
            "requirement_generation_source": "catalog_registry",
        }
    }

    async def find_one(filt, *args, **kwargs):
        if filt.get("requirement_id") == REQ_ID and filt.get("client_id") == CLIENT_ID:
            return dict(requirements["req"])
        return None

    async def update_one(*_a, **_kw):
        return {"modified_count": 1}

    mock_db = MagicMock()
    mock_db.requirements.find_one = AsyncMock(side_effect=find_one)
    mock_db.requirements.update_one = AsyncMock(side_effect=update_one)
    mock_db.properties = MagicMock()
    mock_db.properties.find_one = AsyncMock(return_value=dict(PROP_DOC))
    mock_db.clients = MagicMock()
    mock_db.clients.find_one = AsyncMock(
        return_value={"client_id": CLIENT_ID, "default_jurisdiction": "England"}
    )
    return mock_db


@pytest.fixture
def client_http():
    app.dependency_overrides[acw._require_client] = _fake_client_guard
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(acw._require_client, None)


def test_mark_not_applicable_409_when_active_job_and_no_confirm(client_http):
    mock_db = _mock_db_for_requirement()
    active = {"work_order_id": "wo-active-1", "status": "OPEN"}

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch(
            "routes.api_compliance_workflow.find_active_compliance_job_for_requirement",
            new_callable=AsyncMock,
            return_value=active,
        ),
    ):
        res = client_http.post(
            f"/api/requirements/{REQ_ID}/mark-not-applicable",
            json={"reason": "aaaaaaaaaa", "reason_code": "not_applicable", "confirm_close_active_job": False},
        )
    assert res.status_code == 409
    body = res.json()
    assert body["detail"]["code"] == "ACTIVE_COMPLIANCE_JOB_EXISTS"
    assert body["detail"]["work_order_id"] == "wo-active-1"


def test_mark_not_applicable_cancels_job_when_confirmed(client_http):
    mock_db = _mock_db_for_requirement()
    active = {"work_order_id": "wo-active-2", "status": "OPEN"}
    updates = []

    async def track_update(wid, **kwargs):
        updates.append((wid, kwargs))
        return {"work_order_id": wid, "status": kwargs.get("status")}

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch(
            "routes.api_compliance_workflow.find_active_compliance_job_for_requirement",
            new_callable=AsyncMock,
            return_value=active,
        ),
        patch("routes.api_compliance_workflow.maintenance_service.update_work_order", new_callable=AsyncMock, side_effect=track_update),
        patch("routes.api_compliance_workflow.create_audit_log", new_callable=AsyncMock),
        patch("services.compliance_recalc_queue.enqueue_compliance_recalc", new_callable=AsyncMock),
        patch(
            "routes.api_compliance_workflow.sync_requirement_evidence_authority",
            new_callable=AsyncMock,
        ) as sync_auth,
    ):
        res = client_http.post(
            f"/api/requirements/{REQ_ID}/mark-not-applicable",
            json={"reason": "bbbbbbbbbb", "reason_code": "exempt", "confirm_close_active_job": True},
        )
    assert res.status_code == 200
    assert res.json().get("ok") is True
    assert any(x[0] == "wo-active-2" and x[1].get("status") == "CANCELLED" for x in updates)
    sync_auth.assert_awaited_once()
    assert sync_auth.await_args[0][1] == REQ_ID
    assert sync_auth.await_args[1].get("property_id_hint") == PROP_ID


def test_reopen_requirement_calls_sync_evidence_authority(client_http):
    mock_db = _mock_db_for_requirement()

    async def req_find_one_na(filt, *args, **kwargs):
        if filt.get("requirement_id") == REQ_ID and filt.get("client_id") == CLIENT_ID:
            return {
                "requirement_id": REQ_ID,
                "client_id": CLIENT_ID,
                "property_id": PROP_ID,
                "requirement_code": "gas_safety",
                "requirement_type": "gas_safety",
                "jurisdiction": "England",
                "applicability": "NOT_REQUIRED",
                "status": "NOT_REQUIRED",
                "client_surface_visible": True,
                "requirement_generation_source": "catalog_registry",
            }
        return None

    mock_db.requirements.find_one = AsyncMock(side_effect=req_find_one_na)
    mock_db.requirements.update_one = AsyncMock(return_value={"modified_count": 1})

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("routes.api_compliance_workflow.create_audit_log", new_callable=AsyncMock),
        patch("services.compliance_recalc_queue.enqueue_compliance_recalc", new_callable=AsyncMock),
        patch(
            "routes.api_compliance_workflow.sync_requirement_evidence_authority",
            new_callable=AsyncMock,
        ) as sync_auth,
        patch(
            "routes.api_compliance_workflow._client_requirement_row_eligible",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        res = client_http.post(f"/api/requirements/{REQ_ID}/reopen")
    assert res.status_code == 200
    assert res.json().get("ok") is True
    sync_auth.assert_awaited_once()
    assert sync_auth.await_args[0][1] == REQ_ID
    assert sync_auth.await_args[1].get("property_id_hint") == PROP_ID
