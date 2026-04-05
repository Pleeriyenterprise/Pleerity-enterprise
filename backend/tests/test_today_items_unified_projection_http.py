"""
Today inbox: GET /api/today/items runs build_today_payload_from_unified(get_unified_tasks_for_client(...)).

These tests prove that when unified task feed changes (e.g. open compliance job disappears after
finalize, or a requirement satisfaction row appears), the Today HTTP payload reflects it — without
requiring a live MongoDB or full priority-action engine.
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from routes import api_compliance_workflow as acw
from server import app

CLIENT_ID = "cli-today-proj"


async def _fake_client(request: Request):
    return {"client_id": CLIENT_ID, "portal_user_id": "pu-today", "role": "ROLE_CLIENT_ADMIN"}


def _work_order_task(wid: str, section: str = "in_progress") -> dict:
    """Minimal unified task row shaped like work_order source (see unified_tasks_service)."""
    return {
        "id": f"open_wo:{wid}",
        "source_type": "work_order",
        "source_id": wid,
        "source_entity_type": "work_order",
        "source_entity_id": wid,
        "title": f"Job {wid}",
        "description": "Needs attention",
        "property_id": "prop-t1",
        "section": section,
        "urgency_level": "medium",
        "metadata": {"action_type": "open_work_order", "related_work_order_id": wid},
    }


def _empty_tasks_payload(**sections):
    base = {
        "tasks": {
            "urgent": [],
            "upcoming": [],
            "in_progress": [],
            "recently_completed": [],
            "snoozed": [],
            "hidden": [],
        },
        "summary": {},
        "freshness": {},
        "activity_feed": [],
    }
    for k, v in sections.items():
        base["tasks"][k] = v
    return base


@pytest.fixture
def client_today():
    app.dependency_overrides[acw._require_client] = _fake_client
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(acw._require_client, None)


def test_today_items_includes_open_compliance_job_task_when_unified_feed_has_work_order(client_today):
    wid = "wo-compliance-open"
    payload = _empty_tasks_payload(in_progress=[_work_order_task(wid)])
    with patch.object(acw, "get_unified_tasks_for_client", new_callable=AsyncMock, return_value=payload):
        res = client_today.get("/api/today/items")
    assert res.status_code == 200
    data = res.json()
    flat = data.get("items") or []
    assert any(wid in str(it.get("task") or it) for it in flat), flat
    # business_actions from today_projection include View job → /operations/jobs/{wid}
    ba = next((it.get("business_actions") or [] for it in flat if wid in str(it)), [])
    assert any(a.get("id") == "view_job" and wid in (a.get("navigate") or "") for a in ba)


def test_today_items_omits_work_order_when_unified_feed_no_longer_surfaces_it(client_today):
    """Simulates post-finalize / post-verify: priority stream no longer emits ACTION_OPEN_WORK_ORDER for that id."""
    wid = "wo-finalized"
    before = _empty_tasks_payload(in_progress=[_work_order_task(wid)])
    after = _empty_tasks_payload(in_progress=[])
    with patch.object(acw, "get_unified_tasks_for_client", new_callable=AsyncMock, return_value=before):
        r1 = client_today.get("/api/today/items")
    assert r1.status_code == 200
    assert any(wid in str(i) for i in (r1.json().get("items") or []))
    with patch.object(acw, "get_unified_tasks_for_client", new_callable=AsyncMock, return_value=after):
        r2 = client_today.get("/api/today/items")
    assert r2.status_code == 200
    assert not any(wid in str(i) for i in (r2.json().get("items") or [])), r2.json().get("items")


def test_today_recently_completed_surfaces_requirement_satisfied_when_unified_includes_it(client_today):
    """Requirement COMPLIANT / satisfied rows in unified feed appear under enriched recently_completed (verify outcome path)."""
    req_task = {
        "id": "requirement_completed:req-xyz",
        "source_type": "requirement",
        "source_entity_id": "req-xyz",
        "source_id": "req-xyz",
        "title": "Requirement satisfied: Gas safety",
        "description": "Status is now Compliant.",
        "property_id": "prop-t1",
        "section": "recently_completed",
        "urgency_level": "low",
        "metadata": {"action_type": "requirement_satisfied"},
    }
    payload = _empty_tasks_payload(recently_completed=[req_task])
    with patch.object(acw, "get_unified_tasks_for_client", new_callable=AsyncMock, return_value=payload):
        res = client_today.get("/api/today/items")
    assert res.status_code == 200
    tasks = (res.json().get("tasks") or {}).get("recently_completed") or []
    assert any("req-xyz" in str(t) or "Gas safety" in str(t.get("title")) for t in tasks)
