"""GET /api/webhooks/deliveries — recent outbound webhook rows from message_logs."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from server import app
from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import build_runtime_contract

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
CLIENT_ID = "wh-deliveries-client"


def _contract(*, plan="PLAN_3_PRO"):
    return build_runtime_contract(
        client={"client_id": CLIENT_ID, "billing_plan": plan, "subscription_status": "ACTIVE"},
        billing={
            "client_id": CLIENT_ID,
            "subscription_status": "ACTIVE",
            "billing_lifecycle_state": "active",
            "canonical_entitlement_state": "ENABLED",
        },
        now=NOW,
    )


def _mock_evaluate(fixed_contract):
    svc = CapabilityEnforcementService(db=None)

    async def _evaluate(client_id, capability_id, action, *, contract=None):
        return svc.evaluate_from_contract(fixed_contract, capability_id, action)

    return _evaluate


@pytest.fixture
def override_client_guard():
    from middleware import client_route_guard as middleware_client_route_guard

    async def _fake(request):
        return {
            "client_id": CLIENT_ID,
            "portal_user_id": "pu-1",
            "role": "ROLE_CLIENT",
        }

    app.dependency_overrides[middleware_client_route_guard] = _fake
    with patch(
        "routes.webhooks_config.client_route_guard",
        new=AsyncMock(
            return_value={
                "client_id": CLIENT_ID,
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
        "middleware.capability_gating.CapabilityEnforcementService.evaluate",
        new=AsyncMock(side_effect=_mock_evaluate(_contract())),
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
        "middleware.capability_gating.CapabilityEnforcementService.evaluate",
        new=AsyncMock(side_effect=_mock_evaluate(_contract(plan="PLAN_1_SOLO"))),
    ):
        r = client.get("/api/webhooks/deliveries")
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "capability_denied"
