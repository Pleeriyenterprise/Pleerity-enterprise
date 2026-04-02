from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request

from middleware import client_route_guard as middleware_client_route_guard
from server import app
from services.command_center_service import _slim_task, get_command_center_bundle
from services import unified_tasks_service as uts


@pytest.fixture
def client_user():
    return {
        "client_id": "phase21-client",
        "portal_user_id": "phase21-user",
        "role": "ROLE_CLIENT",
        "plan_tier": "professional",
    }


@pytest.fixture
def override_client_guard(client_user):
    async def _fake_guard(request: Request):
        return client_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    with patch("routes.client.client_route_guard", new=AsyncMock(return_value=client_user)):
        yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


@pytest.mark.asyncio
async def test_command_center_urgent_matches_unified_tasks_order():
    full = {
        "tasks": {
            "urgent": [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}],
            "in_progress": [{"id": "c", "title": "C"}],
        }
    }
    with patch("services.command_center_service.get_unified_tasks_for_client", new=AsyncMock(return_value=full)), patch(
        "services.command_center_service.get_unified_tasks_digest",
        new=AsyncMock(return_value={"summary": {}, "freshness": {}, "activity_feed": []}),
    ), patch("services.command_center_service.risk_signal_service.get_risk_signals_for_client", new=AsyncMock(return_value={"signals": []})), patch(
        "services.compliance_score.calculate_compliance_score",
        new=AsyncMock(return_value={"score": 80, "grade": "B", "message": "ok", "stats": {}}),
    ):
        bundle = await get_command_center_bundle("phase21-client", predictive_enabled=True)
    assert [x.get("id") for x in bundle["urgent_actions"]] == ["a", "b", "c"]


def test_slim_task_contains_cta_model_fields():
    t = _slim_task(
        {
            "id": "requirement:req1",
            "title": "Upload EPC",
            "source_type": "requirement",
            "source_id": "req1",
            "property_id": "p1",
            "requirement_id": "req1",
            "primary_action_type": "upload_evidence",
            "primary_action_label": "Upload document",
            "primary_action_url": "/documents?property_id=p1&requirement_id=req1",
        }
    )
    assert t["source_type"] == "requirement"
    assert t["source_id"] == "req1"
    assert t["primary_cta"]["action_type"] == "upload_evidence"
    assert t["primary_cta"]["route"] == "/documents?property_id=p1&requirement_id=req1"


@pytest.mark.asyncio
async def test_tenant_request_tasks_enter_unified_priority_stream():
    tr = {
        "id": "tenant_request:tr1",
        "source_type": "tenant_request",
        "source_id": "tr1",
        "section": "upcoming",
        "title": "Tenant certificate request",
        "impact_score": 34,
        "urgency_level": "low",
        "property_id": "p1",
        "primary_action_type": "upload_evidence",
        "primary_action_label": "Upload document",
        "primary_action_url": "/documents?property_id=p1&requirement_id=r1",
    }
    with patch("services.unified_tasks_service.fetch_client_priority_actions", new=AsyncMock(return_value=[])), patch(
        "services.unified_tasks_service._tenant_message_tasks", new=AsyncMock(return_value=[])
    ), patch("services.unified_tasks_service._tenant_request_tasks", new=AsyncMock(return_value=[tr])), patch(
        "services.unified_tasks_service._recently_completed_tasks", new=AsyncMock(return_value=[])
    ), patch("services.unified_tasks_service._load_property_labels", new=AsyncMock(return_value={})), patch(
        "services.unified_tasks_service._freshness_block", new=AsyncMock(return_value={})
    ), patch(
        "services.client_task_state_service.load_active_overrides", new=AsyncMock(return_value={})
    ), patch(
        "services.client_task_state_service.list_recent_activity", new=AsyncMock(return_value=[])
    ), patch(
        "services.client_task_state_service.count_activity_since", new=AsyncMock(return_value=0)
    ), patch(
        "services.client_task_state_service.list_hidden_inbox_items", new=AsyncMock(return_value=[])
    ):
        out = await uts.get_unified_tasks_for_client("phase21-client")
    all_ids = [x["id"] for x in out["tasks"]["upcoming"] + out["tasks"]["in_progress"] + out["tasks"]["urgent"]]
    assert "tenant_request:tr1" in all_ids


def test_priority_actions_endpoint_matches_command_center_urgent(client, override_client_guard):
    urgent = [{"id": "u1", "title": "t1"}, {"id": "u2", "title": "t2"}]
    payload = {
        "urgent_actions": urgent,
        "upcoming_risks": [],
        "recent_activity": [],
        "compliance_status_summary": {},
        "tasks_digest_summary": {},
        "freshness": {},
    }
    with patch(
        "services.ops_compliance_feature_flags.get_effective_flags", new=AsyncMock(return_value={"predictive_maintenance": True})
    ), patch("services.command_center_service.get_command_center_bundle", new=AsyncMock(return_value=payload)):
        r1 = client.get("/api/client/command-center")
        r2 = client.get("/api/client/priority-actions", params={"limit": 2})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json()["source"] == "command_center"
    assert r2.json()["actions"] == r1.json()["urgent_actions"][:2]

