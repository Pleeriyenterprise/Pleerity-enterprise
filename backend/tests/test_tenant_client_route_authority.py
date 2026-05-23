"""Tenant must not access landlord /api/client/* operational authority."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from middleware import client_route_guard as middleware_client_route_guard
from middleware import tenant_route_guard as middleware_tenant_route_guard
from models import OnboardingStatus, PasswordStatus, UserRole
from server import app


def _make_request(path: str = "/api/client/maintenance/issues") -> Request:
    scope = {"type": "http", "method": "GET", "path": path, "headers": []}
    return Request(scope)


TENANT_PORTAL_USER = {
    "portal_user_id": "pu-tenant-1",
    "client_id": "cli-1",
    "auth_email": "tenant@example.com",
    "role": UserRole.ROLE_TENANT.value,
    "status": "ACTIVE",
    "password_status": PasswordStatus.SET.value,
}

CLIENT_PORTAL_USER = {
    **TENANT_PORTAL_USER,
    "portal_user_id": "pu-client-1",
    "role": UserRole.ROLE_CLIENT.value,
}

CLIENT_DOC = {
    "client_id": "cli-1",
    "onboarding_status": OnboardingStatus.PROVISIONED.value,
}


@pytest.mark.asyncio
async def test_client_route_guard_blocks_role_tenant():
    request = _make_request("/api/client/operations/rent/summary")
    with patch("middleware.require_auth", new_callable=AsyncMock) as mock_auth, patch(
        "middleware.database.get_db"
    ) as mock_get_db, patch("middleware.log_route_guard_redirect", new_callable=AsyncMock):
        mock_auth.return_value = {
            "portal_user_id": "pu-tenant-1",
            "client_id": "cli-1",
            "role": UserRole.ROLE_TENANT.value,
            "email": "tenant@example.com",
        }
        db = MagicMock()
        db.portal_users.find_one = AsyncMock(return_value=TENANT_PORTAL_USER)
        mock_get_db.return_value = db

        with pytest.raises(HTTPException) as exc:
            await middleware_client_route_guard(request)
        assert exc.value.status_code == 403
        detail = exc.value.detail
        assert detail.get("error_code") == "TENANT_LANDLORD_API_FORBIDDEN"


@pytest.mark.asyncio
async def test_tenant_route_guard_allows_role_tenant_on_tenant_domain():
    request = _make_request("/api/tenant/dashboard")
    with patch("middleware.require_auth", new_callable=AsyncMock) as mock_auth, patch(
        "middleware.database.get_db"
    ) as mock_get_db, patch("middleware.log_route_guard_redirect", new_callable=AsyncMock):
        mock_auth.return_value = {
            "portal_user_id": "pu-tenant-1",
            "client_id": "cli-1",
            "role": UserRole.ROLE_TENANT.value,
            "email": "tenant@example.com",
        }
        db = MagicMock()
        db.portal_users.find_one = AsyncMock(return_value=TENANT_PORTAL_USER)
        db.clients.find_one = AsyncMock(return_value=CLIENT_DOC)
        db.client_billing.find_one = AsyncMock(return_value=None)
        mock_get_db.return_value = db

        user = await middleware_tenant_route_guard(request)
        assert user["role"] == UserRole.ROLE_TENANT.value
        assert user["client_id"] == "cli-1"


@pytest.mark.asyncio
async def test_tenant_route_guard_rejects_unknown_role():
    request = _make_request("/api/tenant/dashboard")
    with patch("middleware.require_auth", new_callable=AsyncMock) as mock_auth, patch(
        "middleware.database.get_db"
    ) as mock_get_db, patch("middleware.log_route_guard_redirect", new_callable=AsyncMock):
        mock_auth.return_value = {
            "portal_user_id": "pu-contractor-1",
            "client_id": "cli-1",
            "role": UserRole.ROLE_CONTRACTOR.value,
        }
        portal_user = {**TENANT_PORTAL_USER, "role": UserRole.ROLE_CONTRACTOR.value}
        db = MagicMock()
        db.portal_users.find_one = AsyncMock(return_value=portal_user)
        mock_get_db.return_value = db

        with pytest.raises(HTTPException) as exc:
            await middleware_tenant_route_guard(request)
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_client_route_guard_allows_role_client():
    request = _make_request("/api/client/dashboard")
    with patch("middleware.require_auth", new_callable=AsyncMock) as mock_auth, patch(
        "middleware.database.get_db"
    ) as mock_get_db, patch("middleware.log_route_guard_redirect", new_callable=AsyncMock):
        mock_auth.return_value = {
            "portal_user_id": "pu-client-1",
            "client_id": "cli-1",
            "role": UserRole.ROLE_CLIENT.value,
        }
        db = MagicMock()
        db.portal_users.find_one = AsyncMock(return_value=CLIENT_PORTAL_USER)
        db.clients.find_one = AsyncMock(return_value=CLIENT_DOC)
        db.client_billing.find_one = AsyncMock(return_value=None)
        mock_get_db.return_value = db

        user = await middleware_client_route_guard(request)
        assert user["client_id"] == "cli-1"



@pytest.mark.asyncio
async def test_tenant_reported_issues_lifecycle_projection():
    from routes.tenant import _tenant_issue_lifecycle_phase

    assert _tenant_issue_lifecycle_phase("triaged") == "reported"
    assert _tenant_issue_lifecycle_phase("monitoring") == "acknowledged"
    assert _tenant_issue_lifecycle_phase("in_progress") == "in_progress"
    assert _tenant_issue_lifecycle_phase("triaged", "IN_PROGRESS") == "in_progress"
    assert _tenant_issue_lifecycle_phase("closed") == "completed"
    assert _tenant_issue_lifecycle_phase("triaged", "COMPLETED") == "completed"
