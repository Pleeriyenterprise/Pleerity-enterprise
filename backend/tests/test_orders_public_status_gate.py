"""Regression: public order status must not leak without session_id or JWT."""
import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    os.environ.setdefault("PYTEST_RUNNING", "1")
    from server import app

    return TestClient(app)


def test_order_status_denied_without_credentials(client):
    with patch("routes.orders.get_order", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {
            "order_id": "ORD-XYZ",
            "status": "CREATED",
            "service_name": "Test Service",
            "customer": {"email": "a@example.com"},
            "pricing": {"stripe_checkout_session_id": "cs_test_123"},
            "created_at": None,
            "completed_at": None,
        }
        r = client.get("/api/orders/ORD-XYZ/status")
        assert r.status_code == 401


def test_order_status_ok_with_matching_session_id(client):
    with patch("routes.orders.get_order", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {
            "order_id": "ORD-XYZ",
            "status": "PAID",
            "service_name": "Test Service",
            "customer": {"email": "a@example.com"},
            "pricing": {"stripe_checkout_session_id": "cs_test_123"},
            "created_at": None,
            "completed_at": None,
        }
        r = client.get("/api/orders/ORD-XYZ/status?session_id=cs_test_123")
        assert r.status_code == 200
        body = r.json()
        assert body["order_id"] == "ORD-XYZ"
        assert body["status"] == "PAID"


def test_create_test_order_blocked_in_production(client):
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
        r = client.post("/api/orders/create-test-order")
        assert r.status_code == 404
