"""
Contract: GET /api/client/priorities matches GET /api/client/tasks (same handler semantics).

- OpenAPI documents /api/client/priorities with stable extension x-equivalent-path.
- JSON bodies are identical for the same auth and query params when the underlying service returns the same value.
"""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request

from middleware import client_route_guard as middleware_client_route_guard
from server import app

_UNIFIED_STUB = {
    "tasks": {
        "urgent": [],
        "upcoming": [],
        "in_progress": [],
        "recently_completed": [],
        "snoozed": [],
        "hidden": [],
    },
    "summary": {
        "urgent_count": 0,
        "upcoming_count": 0,
        "in_progress_count": 0,
        "recently_completed_count": 0,
        "snoozed_count": 0,
        "hidden_count": 0,
        "habit": {
            "urgent_open_total": 0,
            "items_due_or_expiring_in_7_days": 0,
            "tasks_acknowledged_last_7_days": 0,
        },
    },
    "freshness": {"tasks_refreshed_at": "2025-01-01T00:00:00+00:00"},
    "spend_this_month": None,
    "activity_feed": [],
}


@pytest.fixture
def client_user():
    return {
        "client_id": "contract-test-client",
        "portal_user_id": "pu-contract-1",
        "role": "ROLE_CLIENT",
    }


@pytest.fixture
def override_client_guard(client_user):
    """
    Client router uses Depends(client_route_guard) and most handlers also await client_route_guard(request).
    Override the dependency for the original callable and patch the name in routes.client for inline calls.
    """
    async def _fake_guard(request: Request):
        return client_user

    app.dependency_overrides[middleware_client_route_guard] = _fake_guard
    with patch("routes.client.client_route_guard", new=AsyncMock(return_value=client_user)):
        yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


def test_openapi_documents_priorities_and_tasks(client):
    schema = client.app.openapi()
    paths = schema.get("paths") or {}
    assert "/api/client/priorities" in paths
    assert "/api/client/tasks" in paths
    prio_get = paths["/api/client/priorities"].get("get") or {}
    assert prio_get.get("summary")
    assert "GET /api/client/tasks" in (prio_get.get("description") or "")
    assert prio_get.get("x-equivalent-path") == "/api/client/tasks"


def test_priorities_and_tasks_json_identical(client, override_client_guard):
    with patch(
        "services.unified_tasks_service.get_unified_tasks_for_client",
        new_callable=AsyncMock,
        return_value=_UNIFIED_STUB,
    ):
        r_tasks = client.get("/api/client/tasks")
        r_prio = client.get("/api/client/priorities")
    assert r_tasks.status_code == 200
    assert r_prio.status_code == 200
    assert r_tasks.json() == r_prio.json() == _UNIFIED_STUB


def test_priorities_passes_same_service_kwargs_as_tasks(client, override_client_guard):
    with patch(
        "services.unified_tasks_service.get_unified_tasks_for_client",
        new_callable=AsyncMock,
        return_value=_UNIFIED_STUB,
    ) as m:
        client.get("/api/client/tasks", params={"property_id": "prop-contract-1"})
        client.get("/api/client/priorities", params={"property_id": "prop-contract-1"})
    assert m.call_count == 2
    for call in m.call_args_list:
        assert call.kwargs == {
            "client_id": "contract-test-client",
            "property_id_filter": "prop-contract-1",
            "raw_limit": 120,
        }
