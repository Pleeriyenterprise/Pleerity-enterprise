"""Tests for GET /api/onboarding/status response shape."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from server import app


def _make_db():
    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value=None)
    db.portal_users.find_one = AsyncMock(return_value=None)
    return db


@pytest.fixture
def client():
    return TestClient(app)


def test_onboarding_status_response_shape(client):
    """GET /api/onboarding/status returns expected fields."""
    mock_client = {
        "client_id": "c1",
        "customer_reference": "PLE-CVP-2026-000001",
        "subscription_status": "ACTIVE",
        "onboarding_status": "PROVISIONED",
        "created_at": "2026-02-01T10:00:00Z",
        "updated_at": "2026-02-01T10:05:00Z",
    }
    mock_portal = {"password_status": "SET"}

    mock_db = _make_db()
    mock_db.clients.find_one = AsyncMock(return_value=mock_client)
    mock_db.portal_users.find_one = AsyncMock(return_value=mock_portal)

    with patch("routes.onboarding.database.get_db", return_value=mock_db):
        response = client.get("/api/onboarding/status", params={"client_id": "c1"})

    assert response.status_code == 200
    data = response.json()
    assert "customer_reference" in data
    assert "payment_status" in data
    assert "subscription_status" in data
    assert "provisioning_status" in data
    assert "portal_user_exists" in data
    assert "password_set" in data
    assert "created_at" in data
    assert "updated_at" in data

    assert data["customer_reference"] == "PLE-CVP-2026-000001"
    assert data["payment_status"] == "paid"
    assert data["subscription_status"] == "ACTIVE"
    assert data["provisioning_status"] == "PROVISIONED"
    assert data["portal_user_exists"] is True
    assert data["password_set"] is True


def test_onboarding_status_404_for_missing_client(client):
    """GET /api/onboarding/status returns 404 when client not found."""
    mock_db = _make_db()
    mock_db.clients.find_one = AsyncMock(return_value=None)

    with patch("routes.onboarding.database.get_db", return_value=mock_db):
        response = client.get("/api/onboarding/status", params={"client_id": "nonexistent"})

    assert response.status_code == 404
