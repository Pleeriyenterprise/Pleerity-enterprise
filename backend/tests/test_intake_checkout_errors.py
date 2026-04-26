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
            with patch(
                "routes.intake.validate_acceptance_for_checkout",
                new_callable=AsyncMock,
                return_value=({"template_id": "t1", "template_version_id": "v1"}, None),
            ):
                with patch("routes.intake.stripe_service") as mock_stripe:
                    mock_stripe.create_checkout_session = AsyncMock(
                        side_effect=ValueError("No subscription price configured for plan X")
                    )
                    response = client.post(
                        "/api/intake/checkout",
                        params={"client_id": "test-client-checkout"},
                        headers={"origin": "https://example.com"},
                        json={"acceptance_id": "acc-test-1"},
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
            json={"acceptance_id": "acc-test-1"},
        )
    assert response.status_code == 404
    data = response.json()
    detail = data.get("detail")
    assert isinstance(detail, dict)
    assert detail.get("error_code") == "CLIENT_NOT_FOUND"
    assert detail.get("message")
    assert detail.get("request_id")
    assert len(detail["request_id"]) == 36


def test_checkout_returns_400_with_request_id_for_invalid_origin(client, mock_db):
    """Checkout with invalid origin returns 400 CHECKOUT_FAILED with request_id (no Stripe call)."""
    with patch("routes.intake.database.get_db", return_value=mock_db):
        response = client.post(
            "/api/intake/checkout",
            params={"client_id": "test-client-checkout"},
            headers={"origin": "not-a-valid-origin"},
            json={"acceptance_id": "acc-test-1"},
        )
    assert response.status_code == 400
    data = response.json()
    detail = data.get("detail")
    assert isinstance(detail, dict)
    assert detail.get("error_code") == "CHECKOUT_FAILED"
    assert "redirect" in (detail.get("message") or "").lower() or "origin" in (detail.get("message") or "").lower()
    assert detail.get("request_id")
    assert len(detail["request_id"]) == 36


def test_checkout_returns_502_with_request_id_when_stripe_returns_no_url(client, mock_db):
    """When create_checkout_session returns session without checkout_url, response has 502, CHECKOUT_URL_MISSING, request_id."""
    with patch("routes.intake.database.get_db", return_value=mock_db):
        with patch("routes.intake.create_audit_log", new_callable=AsyncMock):
            with patch(
                "routes.intake.validate_acceptance_for_checkout",
                new_callable=AsyncMock,
                return_value=({"template_id": "t1", "template_version_id": "v1"}, None),
            ):
                with patch("routes.intake.stripe_service") as mock_stripe:
                    mock_stripe.create_checkout_session = AsyncMock(
                        return_value={"session_id": "cs_xxx", "checkout_url": None}
                    )
                    mock_stripe.expire_checkout_session = AsyncMock()
                    response = client.post(
                        "/api/intake/checkout",
                        params={"client_id": "test-client-checkout"},
                        headers={"origin": "https://example.com"},
                        json={"acceptance_id": "acc-test-1"},
                    )
    assert response.status_code == 502
    data = response.json()
    detail = data.get("detail")
    assert isinstance(detail, dict)
    assert detail.get("error_code") == "CHECKOUT_URL_MISSING"
    assert detail.get("message")
    request_id = detail.get("request_id")
    assert request_id, "request_id required for correlation"
    assert len(request_id) == 36 and request_id.count("-") == 4


def test_checkout_returns_409_when_acceptance_commercial_mismatch(client, mock_db):
    """Checkout blocked when acceptance no longer matches commercial snapshot."""
    with patch("routes.intake.database.get_db", return_value=mock_db):
        with patch(
            "routes.intake.validate_acceptance_for_checkout",
            new_callable=AsyncMock,
            return_value=(None, "ACCEPTANCE_COMMERCIAL_MISMATCH"),
        ):
            response = client.post(
                "/api/intake/checkout",
                params={"client_id": "test-client-checkout"},
                headers={"origin": "https://example.com"},
                json={"acceptance_id": "acc-test-1"},
            )
    assert response.status_code == 409
    detail = response.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("error_code") == "ACCEPTANCE_COMMERCIAL_MISMATCH"
    assert detail.get("request_id")


def test_checkout_returns_422_when_acceptance_render_invalid(client, mock_db):
    """Checkout blocked when server-side acceptance render validation is invalid."""
    with patch("routes.intake.database.get_db", return_value=mock_db):
        with patch(
            "routes.intake.validate_acceptance_for_checkout",
            new_callable=AsyncMock,
            return_value=(None, "ACCEPTANCE_RENDER_INVALID"),
        ):
            response = client.post(
                "/api/intake/checkout",
                params={"client_id": "test-client-checkout"},
                headers={"origin": "https://example.com"},
                json={"acceptance_id": "acc-test-1"},
            )
    assert response.status_code == 422
    detail = response.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("error_code") == "ACCEPTANCE_RENDER_INVALID"
    assert detail.get("request_id")


def test_checkout_returns_503_when_acceptance_checkout_link_fails(client, mock_db):
    """If Stripe session is created but acceptance row cannot be linked, client gets 503 and session is expired."""
    with patch("routes.intake.database.get_db", return_value=mock_db):
        with patch("routes.intake.create_audit_log", new_callable=AsyncMock):
            with patch(
                "routes.intake.validate_acceptance_for_checkout",
                new_callable=AsyncMock,
                return_value=({"template_id": "t1", "template_version_id": "v1"}, None),
            ):
                with patch("routes.intake.stripe_service") as mock_stripe:
                    mock_stripe.create_checkout_session = AsyncMock(
                        return_value={"session_id": "cs_test_linkfail", "checkout_url": "https://pay.example/cs"}
                    )
                    mock_stripe.expire_checkout_session = AsyncMock()
                    with patch(
                        "routes.intake.mark_acceptance_checkout_started",
                        new_callable=AsyncMock,
                        side_effect=ValueError("acceptance_not_found:bad-id"),
                    ):
                        response = client.post(
                            "/api/intake/checkout",
                            params={"client_id": "test-client-checkout"},
                            headers={"origin": "https://example.com"},
                            json={"acceptance_id": "bad-id"},
                        )
    assert response.status_code == 503
    detail = response.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("error_code") == "ACCEPTANCE_CHECKOUT_LINK_FAILED"
    mock_stripe.expire_checkout_session.assert_awaited_once_with("cs_test_linkfail")
