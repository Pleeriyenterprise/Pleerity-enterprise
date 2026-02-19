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
    """UNPAID -> next_action PAYMENT."""
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
    assert data["payment_state"] == "UNPAID"
    assert data["next_action"] == "PAYMENT"
    assert data["client_name"] == "Test Client"
    assert data["properties_count"] == 0
    assert data["requirements_count"] == 0


def test_setup_status_next_action_wait_provisioning(client):
    """CONFIRMING / not yet provisioned -> next_action WAIT_PROVISIONING."""
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
    assert data["payment_state"] in ("CONFIRMING", "PAID")  # depends on time
    assert data["provisioning_state"] == "RUNNING"
    assert data["next_action"] == "WAIT_PROVISIONING"


def test_setup_status_next_action_set_password(client):
    """Provisioned but password NOT_SET -> next_action SET_PASSWORD."""
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
    assert data["payment_state"] == "PAID"
    assert data["provisioning_state"] == "PROVISIONED"
    assert data["password_state"] == "NOT_SET"
    assert data["next_action"] == "SET_PASSWORD"


def test_setup_status_next_action_dashboard(client):
    """Provisioned and password SET -> next_action DASHBOARD."""
    mock_client = {
        "client_id": "c1",
        "customer_reference": "PLE-CVP-2026-00001",
        "subscription_status": "ACTIVE",
        "onboarding_status": "PROVISIONED",
        "created_at": "2026-01-01T00:00:00Z",
    }
    mock_portal = {"password_status": "SET"}
    mock_db = _make_db(
        client=mock_client,
        portal_user=mock_portal,
        properties_count=2,
        property_items=[{"property_id": "p1"}, {"property_id": "p2"}],
    )
    mock_db.requirements.count_documents = AsyncMock(return_value=5)

    with patch("routes.portal.database.get_db", return_value=mock_db), \
         patch("routes.portal.get_current_user", new_callable=AsyncMock, return_value=None):
        response = client.get("/api/portal/setup-status", params={"client_id": "c1"})

    assert response.status_code == 200
    data = response.json()
    assert data["payment_state"] == "PAID"
    assert data["provisioning_state"] == "PROVISIONED"
    assert data["password_state"] == "SET"
    assert data["next_action"] == "DASHBOARD"
    assert data["properties_count"] == 2
    assert data["requirements_count"] == 5


def test_setup_status_provisioning_failed(client):
    """provisioning_state FAILED -> last_error present when job has last_error."""
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
    assert data["provisioning_state"] == "FAILED"
    assert data["next_action"] == "WAIT_PROVISIONING"  # still wait (retry possible)
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
