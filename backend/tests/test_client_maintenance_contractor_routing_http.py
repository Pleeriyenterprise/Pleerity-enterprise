"""
HTTP-level tests: POST .../contractor-routing/request and /confirm via TestClient.

dependency_overrides + patch client_maintenance.client_route_guard; override callable must use
`request: Request` or FastAPI adds spurious query params. DB is mocked (in-memory WO).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from database import database as db_singleton
from middleware import client_route_guard as middleware_client_route_guard
from server import app
from services.account_capability_enforcement import CapabilityDecision, GRANT_ALLOW
from services.work_order_assignment_constants import (
    ASSIGNMENT_ROUTING_ASSIGNED,
    ASSIGNMENT_ROUTING_PENDING_CLIENT_CONFIRMATION,
    ASSIGNMENT_ROUTING_UNASSIGNED,
)


CLIENT_ID = "cli-http-routing"
PORTAL_USER = "pu-http-routing"
WOID = "wo-http-routing"


async def _allow_capability_evaluate(client_id, capability_id, action, *, contract=None):
    return CapabilityDecision(
        capability_id=capability_id,
        action=action,
        grant=GRANT_ALLOW,
        effective_semantic=GRANT_ALLOW,
        allowed=True,
        source="test",
        reason_code="allowed",
        reason="test allow",
    )
async def _fake_client_guard(request: Request):
    return {
        "client_id": CLIENT_ID,
        "portal_user_id": PORTAL_USER,
        "role": "ROLE_CLIENT",
        "email": "client-http@test.com",
    }


def _build_mock_db_with_mutable_wo():
    wo_live = {
        "work_order_id": WOID,
        "client_id": CLIENT_ID,
        "property_id": "prop-http-1",
        "status": "OPEN",
        "description": "HTTP routing test job",
        "contractor_id": None,
        "requires_client_assignment_confirmation": True,
        "work_order_kind": "MAINTENANCE",
        "assignment_routing_state": ASSIGNMENT_ROUTING_UNASSIGNED,
        "evidence_keys": [],
        "sla_breached_at": None,
        "sla_breach_risk_at": None,
        "severity": "medium",
    }

    async def find_one(*args, **kwargs):
        filt = args[0] if args else {}
        if filt.get("work_order_id") != WOID:
            return None
        proj = args[1] if len(args) > 1 else None
        if proj and isinstance(proj, dict):
            return {k: wo_live.get(k) for k, v in proj.items() if k != "_id" and v}
        return dict(wo_live)

    async def update_one(filt, update, *_a, **_kw):
        if filt.get("work_order_id") != WOID:
            return None
        if "$set" in update:
            wo_live.update(update["$set"])
        return {"modified_count": 1}

    async def find_one_and_update(filt, update, **_kwargs):
        if filt.get("work_order_id") != WOID:
            return None
        if "$set" in update:
            wo_live.update(update["$set"])
        if "$addToSet" in update:
            keys = (update["$addToSet"] or {}).get("evidence_keys", {})
            if isinstance(keys, dict) and "$each" in keys:
                for k in keys["$each"]:
                    if k and k not in wo_live.setdefault("evidence_keys", []):
                        wo_live["evidence_keys"].append(k)
        out = dict(wo_live)
        out.pop("_id", None)
        return out

    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(side_effect=find_one)
    mock_db.work_orders.update_one = AsyncMock(side_effect=update_one)
    mock_db.work_orders.find_one_and_update = AsyncMock(side_effect=find_one_and_update)
    mock_db.contractor_assignments.insert_one = AsyncMock()
    mock_db.contractor_job_tokens.insert_one = AsyncMock()
    mock_db.contractors.find_one = AsyncMock(return_value={"email": "ctr-http@test.com"})
    mock_db.properties.find_one = AsyncMock(
        return_value={"address_line_1": "9 HTTP St", "city": "Bristol", "postcode": "BS1 1AA"}
    )
    cur = MagicMock()
    cur.to_list = AsyncMock(return_value=[{"auth_email": "client-http@test.com", "portal_user_id": PORTAL_USER}])
    mock_db.portal_users.find = MagicMock(return_value=cur)

    return mock_db, wo_live


@pytest.fixture
def http_client_guard_override():
    """Override Depends(client_route_guard) for client routers."""
    app.dependency_overrides[middleware_client_route_guard] = _fake_client_guard
    yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


def test_http_post_contractor_routing_request_then_confirm(client, http_client_guard_override):
    mock_db, wo_live = _build_mock_db_with_mutable_wo()
    ranked = {
        "contractors": [
            {
                "contractor_id": "ctr-http-1",
                "name": "HTTP Test Trades Ltd",
                "company_name": "HTTP Test Trades Ltd",
                "reasons": ["bookable"],
            }
        ],
        "routing": {"assignment_urgency": "normal", "routing_messages": []},
    }
    send_mock = AsyncMock(return_value={"ok": True})

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch(
            "routes.client_maintenance.client_route_guard",
            new=_fake_client_guard,
        ),
        patch(
            "routes.client_maintenance.CapabilityEnforcementService.evaluate",
            new_callable=AsyncMock,
            side_effect=_allow_capability_evaluate,
        ),
        patch(
            "services.work_order_contractor_routing_service.contractor_service.recommend_contractors_for_work_order",
            new_callable=AsyncMock,
            return_value=ranked,
        ),
        patch(
            "services.contractor_service.validate_contractor_for_work_order_assignment",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("services.notification_orchestrator.notification_orchestrator.send", send_mock),
        patch("utils.audit.create_audit_log", new_callable=AsyncMock, return_value=None),
        patch(
            "services.work_order_contractor_routing_service.create_audit_log",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("services.order_service.create_in_app_notification", new_callable=AsyncMock, return_value=None),
        patch("services.webhook_service.fire_work_order_status_changed", new_callable=AsyncMock),
        patch("auth.generate_secure_token", return_value="http-test-token-32chars-min________"),
        patch("utils.public_app_url.get_frontend_base_url", return_value="https://app.example.com"),
    ):
        r1 = client.post(f"/api/client/maintenance/work-orders/{WOID}/contractor-routing/request")
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1.get("ok") is True
    assert body1.get("recommended_contractor_id") == "ctr-http-1"
    assert wo_live.get("assignment_routing_state") == ASSIGNMENT_ROUTING_PENDING_CLIENT_CONFIRMATION

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch(
            "routes.client_maintenance.client_route_guard",
            new=_fake_client_guard,
        ),
        patch(
            "routes.client_maintenance.CapabilityEnforcementService.evaluate",
            new_callable=AsyncMock,
            side_effect=_allow_capability_evaluate,
        ),
        patch(
            "services.contractor_service.validate_contractor_for_work_order_assignment",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("services.notification_orchestrator.notification_orchestrator.send", send_mock),
        patch("utils.audit.create_audit_log", new_callable=AsyncMock, return_value=None),
        patch(
            "services.work_order_contractor_routing_service.create_audit_log",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch("services.webhook_service.fire_work_order_status_changed", new_callable=AsyncMock),
        patch("auth.generate_secure_token", return_value="http-test-token-32chars-min________"),
        patch("utils.public_app_url.get_frontend_base_url", return_value="https://app.example.com"),
    ):
        r2 = client.post(f"/api/client/maintenance/work-orders/{WOID}/contractor-routing/confirm")

    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2.get("ok") is True
    assert body2.get("work_order", {}).get("contractor_id") == "ctr-http-1"
    assert wo_live.get("contractor_id") == "ctr-http-1"
    assert wo_live.get("assignment_routing_state") == ASSIGNMENT_ROUTING_ASSIGNED

    assign_sends = [
        c
        for c in send_mock.await_args_list
        if c.kwargs.get("template_key") == "CONTRACTOR_ASSIGNED"
    ]
    assert len(assign_sends) == 1
