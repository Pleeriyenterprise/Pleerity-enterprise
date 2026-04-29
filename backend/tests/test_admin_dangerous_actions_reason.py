"""Dangerous admin actions require a support reason in the request body (audit metadata)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from starlette.requests import Request

from middleware import admin_route_guard, require_owner_or_admin
from server import app


async def _override_admin_route_guard(_request: Request):
    return {"portal_user_id": "a1", "role": "ROLE_ADMIN"}


async def _override_owner_or_admin(_request: Request):
    return {"portal_user_id": "a1", "role": "ROLE_ADMIN"}


@pytest.fixture
def client():
    return TestClient(app)


def test_retry_provisioning_job_rejects_short_reason(client):
    app.dependency_overrides[admin_route_guard] = _override_admin_route_guard
    try:
        with patch("routes.admin._enforce_admin_job_run_rate", new_callable=AsyncMock):
            r = client.post(
                "/api/admin/provisioning-jobs/job_x/retry",
                json={"reason": "too_short"},
            )
    finally:
        app.dependency_overrides.pop(admin_route_guard, None)
    assert r.status_code == 422


def test_retry_provisioning_job_audit_includes_reason(client):
    audit_calls = []

    async def capture_audit(**kwargs):
        audit_calls.append(kwargs)

    mock_db = MagicMock()
    mock_db.provisioning_jobs.find_one = AsyncMock(
        return_value={"job_id": "job_x", "client_id": "c1", "status": "FAILED"}
    )

    app.dependency_overrides[admin_route_guard] = _override_admin_route_guard
    try:
        with patch("routes.admin.admin_route_guard", new=AsyncMock(return_value={"portal_user_id": "a1", "role": "ROLE_ADMIN"})):
            with patch("routes.admin._enforce_admin_job_run_rate", new_callable=AsyncMock):
                with patch("routes.admin.database.get_db", return_value=mock_db):
                    with patch("services.provisioning_runner.run_provisioning_job", new_callable=AsyncMock, return_value=True):
                        with patch("routes.admin.create_audit_log", new_callable=AsyncMock, side_effect=capture_audit):
                            r = client.post(
                                "/api/admin/provisioning-jobs/job_x/retry",
                                json={"reason": "Incident 12345 — retry after Stripe webhook delay"},
                            )
    finally:
        app.dependency_overrides.pop(admin_route_guard, None)
    assert r.status_code == 200
    assert audit_calls, "create_audit_log should be called"
    meta = audit_calls[0].get("metadata") or {}
    assert meta.get("support_reason") == "Incident 12345 — retry after Stripe webhook delay"
    assert meta.get("action") == "provisioning_job_retry"


def test_impersonation_start_rejects_short_reason(client):
    app.dependency_overrides[admin_route_guard] = _override_admin_route_guard
    app.dependency_overrides[require_owner_or_admin] = _override_owner_or_admin
    try:
        r = client.post(
            "/api/admin/clients/c1/impersonation/start?ttl_minutes=30",
            json={"reason": "nope"},
        )
    finally:
        app.dependency_overrides.pop(require_owner_or_admin, None)
        app.dependency_overrides.pop(admin_route_guard, None)
    assert r.status_code == 422


def test_impersonation_start_audit_includes_context(client):
    audit_calls = []

    async def capture_audit(**kwargs):
        audit_calls.append(kwargs)

    mock_db = MagicMock()
    mock_db.clients.find_one = AsyncMock(
        return_value={
            "client_id": "c1",
            "full_name": "Client One",
            "company_name": "Acme Ltd",
            "onboarding_status": "PROVISIONED",
        }
    )
    mock_db.portal_users.find_one = AsyncMock(
        return_value={
            "portal_user_id": "pu_1",
            "client_id": "c1",
            "auth_email": "client@example.com",
            "role": "ROLE_CLIENT_ADMIN",
            "status": "ACTIVE",
            "password_status": "SET",
            "session_version": 1,
        }
    )

    app.dependency_overrides[admin_route_guard] = _override_admin_route_guard
    app.dependency_overrides[require_owner_or_admin] = _override_owner_or_admin
    try:
        with patch("routes.admin.admin_route_guard", new=AsyncMock(return_value={"portal_user_id": "a1", "role": "ROLE_ADMIN"})):
            with patch("routes.admin.database.get_db", return_value=mock_db):
                with patch("routes.admin.create_access_token", return_value="imp_token"):
                    with patch("routes.admin.require_recent_step_up", new_callable=AsyncMock) as step_up_mock:
                        with patch("routes.admin.create_audit_log", new_callable=AsyncMock, side_effect=capture_audit):
                            r = client.post(
                                "/api/admin/clients/c1/impersonation/start?ttl_minutes=30",
                                json={"reason": "Incident 555 support investigation session"},
                            )
    finally:
        app.dependency_overrides.pop(require_owner_or_admin, None)
        app.dependency_overrides.pop(admin_route_guard, None)

    assert r.status_code == 200
    assert audit_calls
    meta = audit_calls[0].get("metadata") or {}
    assert step_up_mock.await_count == 1
    assert meta.get("action_id") == "start_impersonation"
    assert meta.get("risk_class")
    assert meta.get("operator_level")
    assert meta.get("target_client_id") == "c1"
    assert "affects_multiple_customers" in meta
    assert meta.get("target_email_masked")
    assert meta.get("support_reason") == "Incident 555 support investigation session"
