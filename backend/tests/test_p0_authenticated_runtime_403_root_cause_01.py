"""P0-AUTHENTICATED-RUNTIME-403-ROOT-CAUSE-01 — authenticated path regression tests."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from middleware import client_route_guard
from models import OnboardingStatus, PasswordStatus, UserRole
from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import build_runtime_contract


def _make_request(path: str = "/api/profile/me") -> Request:
    scope = {"type": "http", "method": "GET", "path": path, "headers": []}
    return Request(scope)


def _billing_row(**overrides):
    base = {
        "client_id": "cli-p0",
        "subscription_status": "active",
        "billing_lifecycle_state": "active",
        "canonical_entitlement_state": "ENABLED",
        "entitlement_status": "ACTIVE",
    }
    base.update(overrides)
    return base


def _client_doc(**overrides):
    base = {
        "client_id": "cli-p0",
        "onboarding_status": OnboardingStatus.PROVISIONED.value,
        "billing_plan": "PLAN_1_SOLO",
        "subscription_status": "active",
    }
    base.update(overrides)
    return base


PORTAL_USER = {
    "portal_user_id": "pu-p0",
    "client_id": "cli-p0",
    "auth_email": "client-p0@example.com",
    "role": UserRole.ROLE_CLIENT.value,
    "status": "ACTIVE",
    "password_status": PasswordStatus.SET.value,
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lifecycle_state,billing_overrides",
    [
        ("ACTIVE", {}),
        ("GRACE_PERIOD", {"billing_lifecycle_state": "grace_period", "grace_period_ends_at": "2099-01-01T00:00:00+00:00"}),
        ("CANCELLED_IMMEDIATE", {"subscription_status": "canceled", "billing_lifecycle_state": "cancelled"}),
        ("READ_ONLY", {"read_only_retention": True, "account_lifecycle_read_only": True}),
    ],
)
async def test_client_context_guard_allows_non_terminal_lifecycle_reads(lifecycle_state, billing_overrides):
    """Coarse guard must not deny before CAP_* for non-terminal lifecycle bands."""
    request = _make_request("/api/profile/me")
    client = _client_doc(**{k: v for k, v in billing_overrides.items() if k in ("read_only_retention", "account_lifecycle_read_only")})
    billing = _billing_row(**{k: v for k, v in billing_overrides.items() if k not in ("read_only_retention", "account_lifecycle_read_only")})
    contract = build_runtime_contract(
        client=client,
        billing=billing,
        now=datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc),
    )
    # Guard behaviour is keyed on resolved contract lifecycle, not fixture label drift.
    resolved_state = contract["lifecycle_state"]
    assert resolved_state not in ("ARCHIVED", "ACCOUNT_DELETED")

    with patch("middleware.require_auth", new_callable=AsyncMock) as mock_auth, patch(
        "middleware.database.get_db"
    ) as mock_get_db, patch("middleware.log_route_guard_redirect", new_callable=AsyncMock), patch(
        "middleware.session_runtime.apply_session_runtime_validation", new_callable=AsyncMock
    ), patch(
        "services.account_lifecycle_runtime_contract.resolve_runtime_contract_for_client",
        new_callable=AsyncMock,
        return_value=contract,
    ):
        mock_auth.return_value = {
            "portal_user_id": "pu-p0",
            "client_id": "cli-p0",
            "role": UserRole.ROLE_CLIENT.value,
            "session_id": "sess-p0",
        }
        db = MagicMock()
        db.portal_users.find_one = AsyncMock(return_value=PORTAL_USER)
        db.clients.find_one = AsyncMock(return_value=client)
        db.client_billing.find_one = AsyncMock(return_value=billing)
        mock_get_db.return_value = db

        user = await client_route_guard(request)
        assert user["client_id"] == "cli-p0"


@pytest.mark.asyncio
async def test_client_context_guard_blocks_only_archived_terminal_band():
    request = _make_request("/api/client/dashboard")
    client = _client_doc(client_lifecycle_status="ARCHIVED")
    billing = _billing_row(subscription_status="canceled", billing_lifecycle_state="expired")
    contract = build_runtime_contract(
        client=client,
        billing=billing,
        now=datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc),
    )
    assert contract["lifecycle_state"] == "ARCHIVED"

    with patch("middleware.require_auth", new_callable=AsyncMock) as mock_auth, patch(
        "middleware.database.get_db"
    ) as mock_get_db, patch("middleware.log_route_guard_redirect", new_callable=AsyncMock), patch(
        "services.account_lifecycle_runtime_contract.resolve_runtime_contract_for_client",
        new_callable=AsyncMock,
        return_value=contract,
    ), patch(
        "services.account_lifecycle_response_authority.lifecycle_denial_for_client",
        new_callable=AsyncMock,
        return_value={"error_code": "lifecycle_access_denied", "message": "archived"},
    ):
        mock_auth.return_value = {
            "portal_user_id": "pu-p0",
            "client_id": "cli-p0",
            "role": UserRole.ROLE_CLIENT.value,
        }
        db = MagicMock()
        db.portal_users.find_one = AsyncMock(return_value=PORTAL_USER)
        db.clients.find_one = AsyncMock(return_value=client)
        db.client_billing.find_one = AsyncMock(return_value=billing)
        mock_get_db.return_value = db

        with pytest.raises(HTTPException) as exc:
            await client_route_guard(request)
        assert exc.value.status_code == 403


def test_active_runtime_contract_grants_core_read_capabilities():
    contract = build_runtime_contract(
        client=_client_doc(),
        billing=_billing_row(),
        now=datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc),
    )
    caps = contract["capabilities"]
    for cap in (
        "CAP_PROFILE_VIEW",
        "CAP_DASHBOARD_VIEW",
        "CAP_TODAY_VIEW",
        "CAP_PROP_VIEW",
        "CAP_DOC_VIEW",
        "CAP_REPORT_VIEW",
    ):
        assert caps.get(cap) in ("ALLOW", "READ", "LIMITED"), cap
    assert len(caps) >= 40


@pytest.mark.asyncio
async def test_capability_enforcement_skips_event_emission_on_load():
    service = CapabilityEnforcementService(MagicMock())
    with patch(
        "services.account_capability_enforcement.resolve_runtime_contract_for_client",
        new_callable=AsyncMock,
    ) as resolve_mock:
        resolve_mock.return_value = build_runtime_contract(
            client=_client_doc(),
            billing=_billing_row(),
        )
        await service.load_contract("cli-p0")
    assert resolve_mock.await_args.kwargs.get("emit_events") is False


def test_plan_context_includes_max_properties():
    contract = build_runtime_contract(client=_client_doc(), billing=_billing_row())
    assert contract["plan"].get("max_properties") is not None
