"""Admin change-login-email action: duplicate rejection, success, session invalidation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from starlette.requests import Request

from middleware import admin_route_guard
from models import UserRole, UserStatus, PasswordStatus
from server import app


async def _override_admin_route_guard(request: Request):
    return {"portal_user_id": "admin_1", "role": "ROLE_ADMIN", "auth_email": "admin@example.com"}


@pytest.fixture
def client():
    return TestClient(app)


def _post_change_login_email(client, **json_body):
    return client.post(
        "/api/admin/clients/c1/actions/change-login-email",
        json=json_body,
    )


def _portal_user(**overrides):
    base = {
        "portal_user_id": "pu_1",
        "client_id": "c1",
        "auth_email": "client@example.com",
        "role": UserRole.ROLE_CLIENT_ADMIN.value,
        "status": UserStatus.ACTIVE.value,
        "password_status": PasswordStatus.SET.value,
        "session_version": 2,
    }
    base.update(overrides)
    return base


def _build_mock_db(*, client_doc, portal_user, duplicate_portal_user=None):
    mock_db = MagicMock()

    async def clients_find_one(query, projection=None):
        if query.get("client_id") == "c1":
            return client_doc
        if isinstance(query.get("client_id"), dict) and query["client_id"].get("$ne") == "c1":
            return None
        if "$expr" in query and query.get("client_id", {}).get("$ne") == "c1":
            return None
        return client_doc

    async def portal_find_one(query, projection=None):
        if "auth_email" in query and isinstance(query.get("portal_user_id"), dict):
            return duplicate_portal_user
        if query.get("client_id") == "c1":
            return portal_user
        return None

    mock_db.clients.find_one = AsyncMock(side_effect=clients_find_one)
    mock_db.portal_users.find_one = AsyncMock(side_effect=portal_find_one)
    mock_db.portal_users.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.clients.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.password_tokens.update_many = AsyncMock()
    mock_db.password_tokens.insert_one = AsyncMock()
    return mock_db


def test_change_login_email_rejects_short_reason(client):
    app.dependency_overrides[admin_route_guard] = _override_admin_route_guard
    try:
        r = _post_change_login_email(
            client,
            new_email="new@example.com",
            reason="short",
        )
    finally:
        app.dependency_overrides.pop(admin_route_guard, None)
    assert r.status_code == 422


def test_change_login_email_rejects_duplicate_portal_email(client):
    mock_db = _build_mock_db(
        client_doc={"client_id": "c1", "email": "client@example.com", "full_name": "Client One"},
        portal_user=_portal_user(),
        duplicate_portal_user={"portal_user_id": "pu_other", "auth_email": "taken@example.com"},
    )

    app.dependency_overrides[admin_route_guard] = _override_admin_route_guard
    try:
        with patch("routes.admin.admin_route_guard", new=AsyncMock(return_value={"portal_user_id": "admin_1", "role": "ROLE_ADMIN"})):
            with patch("routes.admin.database.get_db", return_value=mock_db):
                with patch("routes.admin.require_recent_step_up", new_callable=AsyncMock):
                    r = _post_change_login_email(
                        client,
                        new_email="taken@example.com",
                        reason="Ticket 9001 verified customer requested email change",
                        send_activation_email=False,
                    )
    finally:
        app.dependency_overrides.pop(admin_route_guard, None)

    assert r.status_code == 400
    detail = r.json().get("detail")
    assert detail.get("error_code") == "EMAIL_ALREADY_EXISTS"


def test_change_login_email_success_invalidates_session_and_audits(client):
    audit_calls = []

    async def capture_audit(**kwargs):
        audit_calls.append(kwargs)

    mock_db = _build_mock_db(
        client_doc={"client_id": "c1", "email": "client@example.com", "full_name": "Client One"},
        portal_user=_portal_user(session_version=2),
    )

    app.dependency_overrides[admin_route_guard] = _override_admin_route_guard
    try:
        with patch("routes.admin.admin_route_guard", new=AsyncMock(return_value={"portal_user_id": "admin_1", "role": "ROLE_ADMIN"})):
            with patch("routes.admin.database.get_db", return_value=mock_db):
                with patch("routes.admin.require_recent_step_up", new_callable=AsyncMock):
                    with patch("routes.admin.create_audit_log", new_callable=AsyncMock, side_effect=capture_audit):
                        r = _post_change_login_email(
                            client,
                            new_email="newclient@example.com",
                            reason="Ticket 9002 customer verified new inbox for portal login",
                            send_activation_email=False,
                        )
    finally:
        app.dependency_overrides.pop(admin_route_guard, None)

    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["login_email"] == "newclient@example.com"
    assert body["session_invalidated"] is True

    update_call = mock_db.portal_users.update_one.await_args
    assert update_call is not None
    update_doc = update_call.args[1]
    assert update_doc["$set"]["auth_email"] == "newclient@example.com"
    assert update_doc["$inc"]["session_version"] == 1

    assert audit_calls
    meta = audit_calls[0].get("metadata") or {}
    assert meta.get("action_type") == "change_login_email"
    assert meta.get("action_id") == "change_login_email"
    assert meta.get("session_invalidated") is True
    assert meta.get("support_reason") == "Ticket 9002 customer verified new inbox for portal login"
    assert audit_calls[0].get("before_state", {}).get("login_email")
    assert audit_calls[0].get("after_state", {}).get("login_email")
