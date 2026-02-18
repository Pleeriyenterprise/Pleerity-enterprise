"""
Intake checkout error responses: structured detail (error_code, message, request_id).
Tests use mocked stripe_service and database so no live Stripe or DB required.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from server import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value={
        "client_id": "test-client-checkout",
        "billing_plan": "PLAN_1_SOLO",
        "email": "test@example.com",
        "contact_email": None,
    })
    db.client_billing.find_one = AsyncMock(return_value=None)
    return db


def test_checkout_returns_structured_error_with_request_id_when_stripe_fails(client, mock_db):
    """When create_checkout_session raises ValueError, response has 400, error_code, message, request_id."""
    with patch("routes.intake.database.get_db", return_value=mock_db):
        with patch("routes.intake.create_audit_log", new_callable=AsyncMock):
            with patch("routes.intake.stripe_service") as mock_stripe:
                mock_stripe.create_checkout_session = AsyncMock(
                    side_effect=ValueError("No subscription price configured for plan X")
                )
                response = client.post(
                    "/api/intake/checkout",
                    params={"client_id": "test-client-checkout"},
                    headers={"origin": "https://example.com"},
                )
    assert response.status_code == 400
    data = response.json()
    detail = data.get("detail")
    assert isinstance(detail, dict)
    assert detail.get("error_code") == "CHECKOUT_FAILED"
    assert detail.get("message")
    request_id = detail.get("request_id")
    assert request_id, "request_id required for correlation"
    assert len(request_id) == 36 and request_id.count("-") == 4


def test_checkout_returns_404_with_request_id_for_missing_client(client):
    """Checkout with invalid client_id returns 404 with error_code, message, request_id."""
    mock_db = MagicMock()
    mock_db.clients.find_one = AsyncMock(return_value=None)
    with patch("routes.intake.database.get_db", return_value=mock_db):
        response = client.post(
            "/api/intake/checkout",
            params={"client_id": "non-existent-client-id"},
            headers={"origin": "https://example.com"},
        )
    assert response.status_code == 404
    data = response.json()
    detail = data.get("detail")
    assert isinstance(detail, dict)
    assert detail.get("error_code") == "CLIENT_NOT_FOUND"
    assert detail.get("message")
    assert detail.get("request_id")
    assert len(detail["request_id"]) == 36
