"""GET /api/webhooks/deliveries — recent outbound webhook rows from message_logs."""
from unittest.mock import AsyncMock, patch

import pytest

from server import app


@pytest.fixture
def override_client_guard():
    from middleware import client_route_guard as middleware_client_route_guard

    async def _fake(request):
        return {
            "client_id": "wh-deliveries-client",
            "portal_user_id": "pu-1",
            "role": "ROLE_CLIENT",
        }

    app.dependency_overrides[middleware_client_route_guard] = _fake
    with patch(
        "routes.webhooks_config.client_route_guard",
        new=AsyncMock(
            return_value={
                "client_id": "wh-deliveries-client",
                "portal_user_id": "pu-1",
                "role": "ROLE_CLIENT",
            }
        ),
    ):
        yield
    app.dependency_overrides.pop(middleware_client_route_guard, None)


def test_deliveries_returns_list(client, override_client_guard):
    sample = [
        {
            "created_at": "2025-01-01T00:00:00+00:00",
            "status": "sent",
            "target_url": "https://example.com/hook",
            "event_alias": "compliance.status_changed",
            "error_message": None,
            "webhook_id": "w1",
            "response_code": 200,
            "attempts": 1,
        }
    ]
    with patch(
        "services.plan_registry.plan_registry.enforce_feature",
        new_callable=AsyncMock,
        return_value=(True, None, None),
    ), patch(
        "routes.webhooks_config.webhook_service.list_recent_deliveries",
        new_callable=AsyncMock,
        return_value=sample,
    ):
        r = client.get("/api/webhooks/deliveries")
    assert r.status_code == 200
    assert r.json() == {"deliveries": sample}


def test_deliveries_403_without_entitlement(client, override_client_guard):
    with patch(
        "services.plan_registry.plan_registry.enforce_feature",
        new_callable=AsyncMock,
        return_value=(False, "no", {"upgrade_required": True, "feature": "webhooks"}),
    ):
        r = client.get("/api/webhooks/deliveries")
    assert r.status_code == 403
