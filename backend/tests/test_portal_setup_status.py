"""Tests for GET /api/portal/setup-status and next_action mapping."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from server import app


class _AsyncIter:
    def __init__(self, items):
        self.items = list(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.items:
            raise StopAsyncIteration
        return self.items.pop(0)


def _make_db(client=None, job=None, portal_user=None, properties_count=0, property_items=None):
    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value=client)
    db.provisioning_jobs.find_one = AsyncMock(return_value=job)
    db.portal_users.find_one = AsyncMock(return_value=portal_user)
    db.properties.count_documents = AsyncMock(return_value=properties_count)
    db.properties.find = MagicMock(return_value=_AsyncIter(property_items or []))
    db.requirements.count_documents = AsyncMock(return_value=5 if property_items else 0)
    return db


@pytest.fixture
def client():
    return TestClient(app)


def test_setup_status_next_action_payment(client):
    """unpaid -> next_action pay."""
    mock_client = {
        "client_id": "c1",
        "customer_reference": "PLE-CVP-2026-00001",
        "full_name": "Test Client",
        "billing_plan": "PLAN_3_PRO",
        "subscription_status": "PENDING",
        "onboarding_status": "INTAKE_PENDING",
        "created_at": "2026-01-01T00:00:00Z",
    }
    mock_db = _make_db(client=mock_client)

    with patch("routes.portal.database.get_db", return_value=mock_db), \
         patch("routes.portal.get_current_user", new_callable=AsyncMock, return_value=None):
        response = client.get("/api/portal/setup-status", params={"client_id": "c1"})

    assert response.status_code == 200
    data = response.json()
    assert data["payment_state"] == "unpaid"
    assert data["next_action"] == "pay"
    assert data["client_name"] == "Test Client"
    assert data["properties_count"] == 0
    assert data["requirements_count"] == 0


def test_setup_status_next_action_wait_provisioning(client):
    """confirming / not yet provisioned -> next_action wait_provisioning; job PAYMENT_CONFIRMED -> queued."""
    mock_client = {
        "client_id": "c1",
        "customer_reference": "PLE-CVP-2026-00001",
        "subscription_status": "PENDING",
        "onboarding_status": "PROVISIONING",
        "created_at": "2026-02-18T10:00:00Z",  # recent
    }
    mock_job = {"status": "PAYMENT_CONFIRMED"}
    mock_db = _make_db(client=mock_client, job=mock_job)
    mock_db.provisioning_jobs.find_one = AsyncMock(return_value=mock_job)

    with patch("routes.portal.database.get_db", return_value=mock_db), \
         patch("routes.portal.get_current_user", new_callable=AsyncMock, return_value=None):
        response = client.get("/api/portal/setup-status", params={"client_id": "c1"})

    assert response.status_code == 200
    data = response.json()
    assert data["payment_state"] in ("confirming", "paid")  # depends on time
    assert data["provisioning_state"] == "queued"  # PAYMENT_CONFIRMED -> queued
    assert data["next_action"] == "wait_provisioning"


def test_setup_status_next_action_set_password(client):
    """Provisioned but password not set -> next_action set_password."""
    mock_client = {
        "client_id": "c1",
        "customer_reference": "PLE-CVP-2026-00001",
        "subscription_status": "ACTIVE",
        "onboarding_status": "PROVISIONED",
        "created_at": "2026-01-01T00:00:00Z",
    }
    mock_portal = {"password_status": "NOT_SET"}
    mock_db = _make_db(client=mock_client, portal_user=mock_portal)

    with patch("routes.portal.database.get_db", return_value=mock_db), \
         patch("routes.portal.get_current_user", new_callable=AsyncMock, return_value=None):
        response = client.get("/api/portal/setup-status", params={"client_id": "c1"})

    assert response.status_code == 200
    data = response.json()
    assert data["payment_state"] == "paid"
    assert data["provisioning_state"] == "completed"
    assert data["password_state"] == "not_sent"
    assert data["next_action"] == "set_password"


def test_setup_status_next_action_dashboard(client):
    """Provisioned and password set -> next_action go_to_dashboard."""
    mock_client = {
        "client_id": "c1",
        "customer_reference": "PLE-CVP-2026-00001",
        "subscription_status": "ACTIVE",
        "onboarding_status": "PROVISIONED",
        "provisioning_status": "COMPLETED",
        "created_at": "2026-01-01T00:00:00Z",
    }
    mock_portal = {"password_status": "SET"}
    mock_job = {"status": "WELCOME_EMAIL_SENT"}
    mock_db = _make_db(
        client=mock_client,
        portal_user=mock_portal,
        job=mock_job,
        properties_count=2,
        property_items=[{"property_id": "p1"}, {"property_id": "p2"}],
    )
    mock_db.requirements.count_documents = AsyncMock(return_value=5)
    mock_db.provisioning_jobs.find_one = AsyncMock(return_value=mock_job)

    with patch("routes.portal.database.get_db", return_value=mock_db), \
         patch("routes.portal.get_current_user", new_callable=AsyncMock, return_value=None):
        response = client.get("/api/portal/setup-status", params={"client_id": "c1"})

    assert response.status_code == 200
    data = response.json()
    assert data["payment_state"] == "paid"
    assert data["subscription_status"] == "ACTIVE"
    assert data["provisioning_state"] == "completed"
    assert data["provisioning_status"] == "COMPLETED"
    assert data["portal_user_created"] is True
    assert data["password_reset_sent"] is True
    assert data["password_state"] == "set"
    assert data["next_action"] == "go_to_dashboard"
    assert data["properties_count"] == 2
    assert data["requirements_count"] == 5


def test_setup_status_provisioning_failed(client):
    """provisioning_state failed -> last_error present when job has last_error."""
    mock_client = {
        "client_id": "c1",
        "subscription_status": "ACTIVE",
        "onboarding_status": "FAILED",
        "created_at": "2026-01-01T00:00:00Z",
    }
    mock_job = {"status": "FAILED", "last_error": "Provisioning failed: XYZ"}
    mock_db = _make_db(client=mock_client, job=mock_job)
    mock_db.provisioning_jobs.find_one = AsyncMock(return_value=mock_job)

    with patch("routes.portal.database.get_db", return_value=mock_db), \
         patch("routes.portal.get_current_user", new_callable=AsyncMock, return_value=None):
        response = client.get("/api/portal/setup-status", params={"client_id": "c1"})

    assert response.status_code == 200
    data = response.json()
    assert data["provisioning_state"] == "failed"
    assert data["next_action"] == "wait_provisioning"  # still wait (retry possible)
    assert data.get("last_error") is not None
    assert "PROVISIONING_FAILED" in str(data.get("last_error", {}))


def test_setup_status_404(client):
    """404 when client not found."""
    mock_db = _make_db(client=None)

    with patch("routes.portal.database.get_db", return_value=mock_db), \
         patch("routes.portal.get_current_user", new_callable=AsyncMock, return_value=None):
        response = client.get("/api/portal/setup-status", params={"client_id": "nonexistent"})

    assert response.status_code == 404


def test_setup_status_400_no_client_id(client):
    """400 when client_id missing and not authenticated."""
    with patch("routes.portal.get_current_user", new_callable=AsyncMock, return_value=None):
        response = client.get("/api/portal/setup-status")

    assert response.status_code == 400


def test_setup_status_returns_activation_fields(client):
    """setup-status returns activation_email_status, activation_email_sent_at, support_email."""
    mock_client = {
        "client_id": "c1",
        "customer_reference": "PLE-001",
        "subscription_status": "ACTIVE",
        "onboarding_status": "PROVISIONED",
        "provisioning_status": "COMPLETED",
        "activation_email_status": "SENT",
        "activation_email_sent_at": "2026-02-20T12:00:00+00:00",
        "portal_user_created_at": "2026-02-20T11:59:00+00:00",
        "created_at": "2026-01-01T00:00:00Z",
    }
    mock_portal = {"password_status": "SET"}
    mock_job = {"status": "WELCOME_EMAIL_SENT"}
    mock_db = _make_db(client=mock_client, portal_user=mock_portal, job=mock_job)
    mock_db.provisioning_jobs.find_one = AsyncMock(return_value=mock_job)

    with patch("routes.portal.database.get_db", return_value=mock_db), \
         patch("routes.portal.get_current_user", new_callable=AsyncMock, return_value=None):
        response = client.get("/api/portal/setup-status", params={"client_id": "c1"})

    assert response.status_code == 200
    data = response.json()
    assert data.get("activation_email_status") == "SENT"
    assert data.get("activation_email_sent_at") is not None
    assert data.get("support_email") is not None
    assert data.get("portal_user_created_at") is not None


def test_resend_activation_403_when_not_provisioned(client):
    """resend-activation returns 403 when onboarding_status != PROVISIONED."""
    mock_client = {"client_id": "c1", "onboarding_status": "PROVISIONING", "email": "c@ex.com", "full_name": "Test"}
    mock_portal = {"portal_user_id": "pu1", "auth_email": "c@ex.com"}
    mock_db = _make_db(client=mock_client, portal_user=mock_portal)
    mock_db.portal_users.find_one = AsyncMock(return_value=mock_portal)

    with patch("routes.portal.database.get_db", return_value=mock_db), \
         patch("routes.portal.get_current_user", new_callable=AsyncMock, return_value=None):
        response = client.post("/api/portal/resend-activation", params={"client_id": "c1"})

    assert response.status_code == 403
    assert "provisioning" in (response.json().get("detail") or "").lower() or "complete" in (response.json().get("detail") or "").lower()


def test_resend_activation_200_does_not_alter_subscription(client):
    """resend-activation sends email and does not change subscription or provisioning fields."""
    mock_client = {
        "client_id": "c1",
        "onboarding_status": "PROVISIONED",
        "email": "c@ex.com",
        "full_name": "Test",
        "subscription_status": "ACTIVE",
        "provisioning_status": "COMPLETED",
    }
    mock_portal = {"portal_user_id": "pu1", "auth_email": "c@ex.com"}
    mock_db = _make_db(client=mock_client, portal_user=mock_portal)
    mock_db.portal_users.find_one = AsyncMock(return_value=mock_portal)
    mock_db.clients.update_one = AsyncMock()

    with patch("routes.portal.database.get_db", return_value=mock_db), \
         patch("routes.portal.get_current_user", new_callable=AsyncMock, return_value=None), \
         patch("services.provisioning.provisioning_service._send_password_setup_link", new_callable=AsyncMock, return_value=(True, "SENT", None)):
        response = client.post("/api/portal/resend-activation", params={"client_id": "c1"})

    assert response.status_code == 200
    assert response.json().get("message") == "Activation email sent"
    # update_one should have been called with client_id c1; payload is second positional arg
    calls = [c for c in mock_db.clients.update_one.call_args_list if len(c[0]) >= 2 and (c[0][0] or {}).get("client_id") == "c1"]
    assert len(calls) >= 1
    payload = calls[0][0][1] if len(calls[0][0]) > 1 else (calls[0][1] or {})
    set_payload = payload.get("$set", {})
    assert "subscription_status" not in set_payload
    assert "onboarding_status" not in set_payload
    assert "provisioning_status" not in set_payload
    assert set_payload.get("activation_email_status") == "SENT"


def test_send_password_setup_link_returns_not_configured_when_blocked():
    """When notification orchestrator returns blocked (Postmark not configured), _send_password_setup_link returns (False, NOT_CONFIGURED, ...) and does not raise."""
    import asyncio
    from services.provisioning import provisioning_service
    from unittest.mock import AsyncMock, MagicMock, patch

    db = MagicMock()
    db.password_tokens = MagicMock()
    db.password_tokens.insert_one = AsyncMock()
    db.clients = MagicMock()

    class BlockedResult:
        outcome = "blocked"
        block_reason = "BLOCKED_PROVIDER_NOT_CONFIGURED"
        error_message = "POSTMARK_SERVER_TOKEN not set"

    async def run():
        with patch("services.provisioning.database.get_db", return_value=db), \
             patch("services.provisioning.generate_secure_token", return_value="tok"), \
             patch("services.provisioning.hash_token", return_value="hash"), \
             patch("services.provisioning.create_audit_log", new_callable=AsyncMock), \
             patch("services.notification_orchestrator.notification_orchestrator.send", new_callable=AsyncMock, return_value=BlockedResult()):
            return await provisioning_service._send_password_setup_link("c1", "pu1", "c@ex.com", "Test", idempotency_key="k")

    ok, status, err = asyncio.run(run())
    assert ok is False
    assert status == "NOT_CONFIGURED"
    assert err is not None
