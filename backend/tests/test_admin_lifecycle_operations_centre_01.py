"""ADMIN-LIFECYCLE-OPERATIONS-CENTRE-01 — admin API and governance tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from routes import admin_lifecycle_operations as routes


CLIENT_ID = "test-client-lifecycle-ops"


def _mock_request():
    req = MagicMock(spec=Request)
    req.headers = {}
    return req


@pytest.mark.asyncio
async def test_get_lifecycle_operations_snapshot():
    with patch.object(routes, "admin_route_guard", new=AsyncMock(return_value={"role": "ROLE_ADMIN"})):
        with patch.object(
            routes,
            "build_lifecycle_operations_snapshot",
            new=AsyncMock(return_value={"client_id": CLIENT_ID, "lifecycle": {"lifecycle_state": "ACTIVE"}}),
        ):
            result = await routes.get_lifecycle_operations_snapshot(_mock_request(), CLIENT_ID)
    assert result["lifecycle"]["lifecycle_state"] == "ACTIVE"


@pytest.mark.asyncio
async def test_refresh_runtime_contract_audited():
    user = {"portal_user_id": "admin-1", "role": "ROLE_ADMIN"}
    with patch.object(routes, "admin_route_guard", new=AsyncMock(return_value=user)):
        with patch.object(routes, "enforce_governed_admin_action", new=AsyncMock()):
            with patch.object(
                routes,
                "admin_refresh_runtime_contract",
                new=AsyncMock(return_value={"success": True, "runtime_version_after": 99}),
            ):
                with patch.object(routes, "create_audit_log", new=AsyncMock()) as audit:
                    body = routes.LifecycleOpsReasonBody(reason="Support requested runtime refresh for billing drift")
                    result = await routes.post_refresh_runtime_contract(_mock_request(), CLIENT_ID, body)
    assert result["success"] is True
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_resume_subscription_blocked_as_value_error():
    user = {"portal_user_id": "admin-1", "role": "ROLE_ADMIN"}
    with patch.object(routes, "admin_route_guard", new=AsyncMock(return_value=user)):
        with patch.object(routes, "enforce_governed_admin_action", new=AsyncMock()):
            with patch.object(
                routes,
                "admin_resume_scheduled_cancellation",
                new=AsyncMock(side_effect=ValueError("Failed to resume subscription: canceled")),
            ):
                body = routes.LifecycleOpsReasonBody(reason="Attempt resume for support case review")
                with pytest.raises(Exception) as exc:
                    await routes.post_resume_subscription(_mock_request(), CLIENT_ID, body)
    assert "canceled" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_action_eligibility_resume_blocked_when_not_scheduled():
    from services.admin_lifecycle_operations_service import _derive_action_eligibility

    actions = _derive_action_eligibility(
        contract={"lifecycle_state": "ACTIVE"},
        billing={"stripe_subscription_id": "sub_x", "cancel_at_period_end": False, "subscription_status": "ACTIVE"},
        client={},
    )
    assert actions["resume_scheduled_cancellation"]["available"] is False
    assert "not scheduled" in actions["resume_scheduled_cancellation"]["blocked_reason"].lower()
