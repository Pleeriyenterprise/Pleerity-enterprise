"""POST /api/jobs/{id}/verify: compliance only; maintenance must use attach-completion-proof + close."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from routes import api_compliance_workflow as acw
from server import app

CLIENT_ID = "cli-verify-pol"
WO_MAINT = "wo-maint-verify"


async def _fake_mw(request: Request):
    return {"client_id": CLIENT_ID, "portal_user_id": "pu-vp", "role": "ROLE_CLIENT_ADMIN"}


@pytest.fixture
def client_jobs():
    app.dependency_overrides[acw._require_maintenance_workflows] = _fake_mw
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(acw._require_maintenance_workflows, None)


def test_post_verify_rejects_maintenance_job(client_jobs):
    wo = {
        "work_order_id": WO_MAINT,
        "client_id": CLIENT_ID,
        "property_id": "p1",
        "work_order_kind": "MAINTENANCE",
        "status": "COMPLETED",
        "evidence_keys": ["document:x"],
    }
    with patch.object(acw, "load_client_work_order", new_callable=AsyncMock, return_value=wo):
        res = client_jobs.post(f"/api/jobs/{WO_MAINT}/verify", json={})
    assert res.status_code == 400
    assert "compliance" in res.json().get("detail", "").lower()
    assert "maintenance" in res.json().get("detail", "").lower() or "close" in res.json().get("detail", "").lower()


def test_client_job_timeline_includes_schedule_last_updated():
    from services.compliance_workflow_service import client_job_timeline_events

    wo = {
        "work_order_id": "w1",
        "created_at": "2026-01-01T00:00:00+00:00",
        "scheduled_at": "2026-01-15T10:00:00+00:00",
        "last_schedule_update_at": "2026-01-10T12:00:00+00:00",
    }
    ev = client_job_timeline_events(wo)
    labels = [e["label"] for e in ev]
    assert "Visit time recorded" in labels
    assert "Schedule last updated" in labels
