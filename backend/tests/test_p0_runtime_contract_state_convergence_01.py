"""P0 runtime contract state convergence — request-scoped contract authority."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from middleware.session_runtime import apply_session_runtime_validation
from models import OnboardingStatus
from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import build_runtime_contract
from services.account_lifecycle_state_resolver import resolve_account_lifecycle_state


def _request() -> Request:
    scope = {"type": "http", "method": "GET", "path": "/api/client/lifecycle-runtime", "headers": []}
    return Request(scope)


def test_stale_pending_payment_does_not_override_provisioned_active():
    client = {
        "client_id": "cli-convergence",
        "onboarding_status": OnboardingStatus.PROVISIONED.value,
        "subscription_status": "ACTIVE",
        "lifecycle_status": "pending_payment",
        "client_lifecycle_status": "ACTIVE",
        "billing_plan": "PLAN_1_SOLO",
    }
    resolution = resolve_account_lifecycle_state(client=client, billing=None)
    assert resolution.account_lifecycle_state == "ACTIVE"


@pytest.mark.asyncio
async def test_session_validation_attaches_runtime_contract_to_request_and_user():
    request = _request()
    contract = build_runtime_contract(
        client={
            "client_id": "cli-convergence",
            "onboarding_status": OnboardingStatus.PROVISIONED.value,
            "subscription_status": "ACTIVE",
            "billing_plan": "PLAN_1_SOLO",
        },
        billing=None,
        now=datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc),
    )
    user = {
        "portal_user_id": "pu-1",
        "client_id": "cli-convergence",
        "role": "ROLE_CLIENT",
        "session_id": "sess-1",
        "runtime_version": contract["runtime_version"],
        "entitlements_version": 1,
    }

    with patch(
        "services.account_lifecycle_runtime_contract.resolve_runtime_contract_for_client",
        new_callable=AsyncMock,
        return_value=contract,
    ), patch(
        "services.account_session_runtime_service.SessionRuntimeService.get_session",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "services.account_session_runtime_service.SessionRuntimeService.touch_validation",
        new_callable=AsyncMock,
    ):
        await apply_session_runtime_validation(request, user)

    assert request.state.runtime_contract is contract
    assert user["runtime_contract"] is contract


@pytest.mark.asyncio
async def test_capability_evaluate_uses_attached_contract_without_reload():
    contract = build_runtime_contract(
        client={
            "client_id": "cli-convergence",
            "onboarding_status": OnboardingStatus.PROVISIONED.value,
            "subscription_status": "ACTIVE",
            "billing_plan": "PLAN_1_SOLO",
        },
        billing=None,
    )
    service = CapabilityEnforcementService(MagicMock())
    with patch.object(service, "load_contract", new_callable=AsyncMock) as load_mock:
        decision = await service.evaluate(
            "cli-convergence",
            "CAP_PROFILE_VIEW",
            "read",
            contract=contract,
        )
    load_mock.assert_not_called()
    assert decision.allowed is True
    assert decision.lifecycle_state == contract["lifecycle_state"]
