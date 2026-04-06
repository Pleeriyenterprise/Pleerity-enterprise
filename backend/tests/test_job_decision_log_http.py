"""POST /api/jobs/{id}/decision-log appends decision_log and returns serialized job."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from routes import api_compliance_workflow as acw
from server import app

CLIENT_ID = "cli-decision-log"
WO_ID = "wo-decision-1"


async def _fake_mw(request: Request):
    return {"client_id": CLIENT_ID, "portal_user_id": "pu-dl", "role": "ROLE_CLIENT"}


@pytest.fixture
def client_jobs():
    app.dependency_overrides[acw._require_maintenance_workflows] = _fake_mw
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(acw._require_maintenance_workflows, None)


def test_post_decision_log_appends_and_returns_job(client_jobs):
    wo_before = {
        "work_order_id": WO_ID,
        "client_id": CLIENT_ID,
        "property_id": "p1",
        "work_order_kind": "MAINTENANCE",
        "status": "OPEN",
        "decision_log": [],
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    wo_after = {**wo_before, "decision_log": [{"message": "Approved visit window", "actor": "client", "timestamp": "2026-02-01T12:00:00+00:00"}]}

    async def load_side_effect(*, work_order_id, client_id):
        if work_order_id == WO_ID and client_id == CLIENT_ID:
            return wo_after
        return None

    mock_update = AsyncMock(return_value=MagicMock(matched_count=1))

    with patch.object(acw, "load_client_work_order", new_callable=AsyncMock, side_effect=load_side_effect):
        with patch.object(acw.database, "get_db") as gdb:
            db = MagicMock()
            db.work_orders.update_one = mock_update
            gdb.return_value = db
            res = client_jobs.post(
                f"/api/jobs/{WO_ID}/decision-log",
                json={"message": "Approved visit window"},
            )
    assert res.status_code == 200
    body = res.json()
    assert body.get("work_order_id") == WO_ID
    assert len(body.get("decision_log") or []) == 1
    assert body["decision_log"][0]["message"] == "Approved visit window"
    assert body["decision_log"][0]["actor"] == "client"
    mock_update.assert_called_once()


def test_post_decision_log_whitespace_only_message(client_jobs):
    wo = {"work_order_id": WO_ID, "client_id": CLIENT_ID, "work_order_kind": "MAINTENANCE", "status": "OPEN"}
    with patch.object(acw, "load_client_work_order", new_callable=AsyncMock, return_value=wo):
        res = client_jobs.post(f"/api/jobs/{WO_ID}/decision-log", json={"message": "   "})
    assert res.status_code == 400
