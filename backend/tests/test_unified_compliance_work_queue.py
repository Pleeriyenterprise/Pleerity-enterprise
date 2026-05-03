"""
PVG-001: Unified Compliance Work Queue v1 — projection + API contract tests.
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request

from middleware import client_route_guard as middleware_client_route_guard
from server import app
from services.unified_compliance_work_queue_service import (
    UCWQ_V1_ITEM_TOP_LEVEL_KEYS,
    UCWQ_V1_PRIMARY_ACTION_KEYS,
    UCWQ_V1_RELATED_IDS_KEYS,
    _closure_summary_user,
    urgency_band_from_unified_urgency_level,
)


@pytest.mark.parametrize(
    "urgency_level, expected_band",
    [
        ("critical", "Urgent"),
        ("high", "Urgent"),
        ("medium", "Soon"),
        ("low", "Watch"),
        ("", "Watch"),
        (None, "Watch"),
    ],
)
def test_urgency_band_mapping(urgency_level, expected_band):
    assert urgency_band_from_unified_urgency_level(urgency_level) == expected_band


def _base_unified_bundle_with_tasks(urgent=None, upcoming=None, in_progress=None):
    urgent = urgent or []
    upcoming = upcoming or []
    in_progress = in_progress or []
    return {
        "tasks": {
            "urgent": urgent,
            "upcoming": upcoming,
            "in_progress": in_progress,
            "recently_completed": [],
            "snoozed": [],
            "hidden": [],
        },
        "summary": {},
        "freshness": {},
        "spend_this_month": None,
        "activity_feed": [],
    }


def _task(
    tid,
    *,
    source_type="requirement",
    urgency_level="medium",
    primary_url="/requirements?x=1",
    metadata=None,
    requirement_id=None,
    gap_key=None,
    title="T",
):
    meta = dict(metadata or {})
    if gap_key:
        meta["gap_key"] = gap_key
    if requirement_id:
        meta["requirement_id"] = requirement_id
    out = {
        "id": tid,
        "source_type": source_type,
        "title": title,
        "description": "Sub",
        "property_id": "p1",
        "property_label": "Prop",
        "urgency_level": urgency_level,
        "primary_action_type": "review_requirement",
        "primary_action_label": "Open",
        "primary_action_url": primary_url,
        "inline_action_supported": False,
        "impact_score": 10,
        "metadata": meta,
        "recommended_action": None,
        "created_at": "2024-06-01T00:00:00+00:00",
        "updated_at": "2024-06-01T00:00:00+00:00",
    }
    if requirement_id:
        out["requirement_id"] = requirement_id
    return out


@pytest.fixture
def client_user():
    return {
        "client_id": "ucwq-test-client",
        "portal_user_id": "pu-ucwq-1",
        "role": "ROLE_CLIENT",
    }


@pytest.fixture
def override_client_guard(client_user):
    async def _fake_guard(request: Request):
        return client_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    with patch("routes.client.client_route_guard", new=AsyncMock(return_value=client_user)):
        yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


def _assert_v1_item_shape(item: dict):
    assert set(item.keys()) == UCWQ_V1_ITEM_TOP_LEVEL_KEYS
    pa = item["primary_action"]
    assert set(pa.keys()) <= UCWQ_V1_PRIMARY_ACTION_KEYS
    rel = item["related_ids"]
    assert isinstance(rel, dict)
    for k in rel.keys():
        assert k in UCWQ_V1_RELATED_IDS_KEYS


def test_api_contract_allowed_v1_fields_only(client, override_client_guard):
    t = _task(
        "requirement:req-1",
        urgency_level="high",
        primary_url="/properties/p1",
        requirement_id="req-1",
        gap_key="gk-a",
    )
    bundle = _base_unified_bundle_with_tasks(urgent=[t])
    with patch(
        "services.unified_compliance_work_queue_service.get_unified_tasks_for_client",
        new_callable=AsyncMock,
        return_value=bundle,
    ):
        r = client.get("/api/client/work-queue")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"items", "summary"}
    assert body["summary"] == {"count": 1}
    assert len(body["items"]) == 1
    _assert_v1_item_shape(body["items"][0])


def test_no_collapse_by_requirement_id_only(client, override_client_guard):
    """Two rows sharing requirement_id but different unified task ids must both appear."""
    a = _task(
        "requirement:req-shared",
        requirement_id="req-shared",
        title="Compliance A",
        primary_url="/a",
    )
    b = _task(
        "issue:iss-2",
        source_type="issue",
        requirement_id="req-shared",
        title="Issue B",
        primary_url="/issues/iss-2",
    )
    b["requirement_id"] = "req-shared"
    bundle = _base_unified_bundle_with_tasks(urgent=[a, b])
    with patch(
        "services.unified_compliance_work_queue_service.get_unified_tasks_for_client",
        new_callable=AsyncMock,
        return_value=bundle,
    ):
        r = client.get("/api/client/work-queue")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    ids = {x["queue_item_id"] for x in items}
    assert ids == {"requirement:req-shared", "issue:iss-2"}


def test_primary_action_from_unified_task_not_raw_gap_fields(client, override_client_guard):
    """
    Primary CTA URL/label must mirror unified task primary fields (resolver path), not ad-hoc gap strings.
    """
    resolved_url = "/documents?property_id=p1&requirement_id=r1"
    t = _task(
        "requirement:r1",
        primary_url=resolved_url,
        requirement_id="r1",
        title="Gas safety",
    )
    t["metadata"]["take_action"] = {"primary": {"kind": "review_requirement", "route": resolved_url}}
    bundle = _base_unified_bundle_with_tasks(upcoming=[t])
    with patch(
        "services.unified_compliance_work_queue_service.get_unified_tasks_for_client",
        new_callable=AsyncMock,
        return_value=bundle,
    ):
        r = client.get("/api/client/work-queue")
    item = r.json()["items"][0]
    assert item["primary_action"]["url"] == resolved_url
    assert item["primary_action"]["label"] == "Open"
    assert "recommended_action_label" not in item
    assert "diagnostic" not in str(item).lower()


def test_excludes_tenant_message_and_request(client, override_client_guard):
    tm = _task("tenant_message:m1", source_type="tenant_message", title="Msg")
    tr = _task("tenant_request:r1", source_type="tenant_request", title="Req")
    ok = _task("requirement:ok1", title="Ok")
    bundle = _base_unified_bundle_with_tasks(urgent=[tm, tr, ok])
    with patch(
        "services.unified_compliance_work_queue_service.get_unified_tasks_for_client",
        new_callable=AsyncMock,
        return_value=bundle,
    ):
        r = client.get("/api/client/work-queue")
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["queue_item_id"] == "requirement:ok1"


def test_remediation_key_prefers_gap_key(client, override_client_guard):
    t = _task("requirement:rid", gap_key="stable-gap-key-xyz", requirement_id="rid")
    bundle = _base_unified_bundle_with_tasks(urgent=[t])
    with patch(
        "services.unified_compliance_work_queue_service.get_unified_tasks_for_client",
        new_callable=AsyncMock,
        return_value=bundle,
    ):
        r = client.get("/api/client/work-queue")
    assert r.json()["items"][0]["remediation_key"] == "stable-gap-key-xyz"


def test_closure_summary_user_risk_signal_clarifies_not_compliance_closure():
    msg = _closure_summary_user({"source_type": "risk_signal"})
    assert "risk signal" in msg.lower()
    assert "acknowledg" in msg.lower() or "dismiss" in msg.lower()
    assert "compliance" in msg.lower()
