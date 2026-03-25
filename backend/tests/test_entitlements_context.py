"""GET /api/client/entitlements/context"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from middleware import client_route_guard as middleware_client_route_guard
from server import app


@pytest.fixture
def client_user():
    return {
        "client_id": "ctx-test-client",
        "portal_user_id": "pu-ctx-1",
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


def test_entitlements_context_shape(client, override_client_guard):
    class _Props:
        async def count_documents(self, q):
            return 2

    db = MagicMock()
    db.properties = _Props()

    def _get_db():
        return db

    fake_ent = AsyncMock(
        return_value={
            "plan": "PLAN_1_SOLO",
            "plan_name": "Solo",
            "is_active": True,
            "max_properties": 2,
        }
    )

    with patch("routes.client.database.get_db", _get_db), patch(
        "services.plan_registry.plan_registry.get_client_entitlements",
        fake_ent,
    ):
        r = client.get("/api/client/entitlements/context")

    assert r.status_code == 200
    data = r.json()
    assert data["property_count"] == 2
    assert data["max_properties"] == 2
    assert data["at_property_limit"] is True
    assert data["read_api_base_path"] == "/api/client-data/v1"
