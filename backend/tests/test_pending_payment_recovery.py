"""
Non-regression tests for Pending Payment Recovery.

- Recovery endpoint does NOT change subscription_status/onboarding_status
- STRIPE_MODE_MISMATCH returns 400
- Lifecycle job only updates lifecycle_status; no delete
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from fastapi.testclient import TestClient
from server import app


def _make_db():
    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value=None)
    db.clients.find = MagicMock(return_value=MagicMock(
        sort=MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    ))
    db.clients.update_one = AsyncMock()
    db.clients.update_many = AsyncMock()
    db.checkout_sessions = MagicMock()
    db.checkout_sessions.insert_one = AsyncMock()
    db.client_billing = MagicMock()
    db.client_billing.find_one = AsyncMock(return_value=None)
    return db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_headers():
    """Mock admin auth - tests may need to patch auth."""
    return {"Authorization": "Bearer mock-admin-token"}


def test_recovery_endpoint_does_not_change_subscription_status(client):
    """send-payment-link must NOT modify subscription_status or onboarding_status."""
    mock_client = {
        "client_id": "c1",
        "email": "test@example.com",
        "customer_reference": "PLE-CVP-2026-000001",
        "billing_plan": "PLAN_1_SOLO",
        "lifecycle_status": "pending_payment",
        "subscription_status": "PENDING",
        "onboarding_status": "INTAKE_PENDING",
        "latest_checkout_session_id": None,
        "latest_checkout_url": None,
        "checkout_link_sent_at": None,
    }
    mock_db = _make_db()
    mock_db.clients.find_one = AsyncMock(return_value=mock_client)
    update_calls = []

    async def capture_update(*args, **kwargs):
        update_calls.append(args[1] if len(args) > 1 else kwargs)

    mock_db.clients.update_one = AsyncMock(side_effect=capture_update)

    with patch("routes.admin_pending_payments.database.get_db", return_value=mock_db):
        with patch("routes.admin_pending_payments.admin_route_guard", new_callable=AsyncMock, return_value={"role": "ROLE_ADMIN"}):
            with patch("routes.admin_pending_payments.stripe_service.create_checkout_session", new_callable=AsyncMock) as mock_checkout:
                mock_checkout.return_value = {"checkout_url": "https://checkout.stripe.com/xxx", "session_id": "cs_xxx"}
                with patch("routes.admin_pending_payments.require_owner_or_admin", return_value=None):
                    response = client.post(
                        "/api/admin/intake/c1/send-payment-link",
                        headers={"Authorization": "Bearer mock-admin-token", "Origin": "https://example.com"},
                    )

    assert response.status_code == 200
    for call_update in update_calls:
        if isinstance(call_update, dict) and "$set" in call_update:
            s = call_update["$set"]
            assert "subscription_status" not in s, "Recovery must not update subscription_status"
            assert "onboarding_status" not in s, "Recovery must not update onboarding_status"


def test_get_pending_payments_returns_new_fields(client):
    """GET pending-payments returns full_name, subscription_status, onboarding_status, checkout_link_sent_at, last_checkout_error."""
    mock_item = {
        "client_id": "c1",
        "customer_reference": "PLE-CVP-2026-000099",
        "email": "pending@example.com",
        "full_name": "Jane Doe",
        "billing_plan": "PLAN_1_SOLO",
        "created_at": "2026-01-15T10:00:00Z",
        "lifecycle_status": "pending_payment",
        "subscription_status": "PENDING",
        "onboarding_status": "INTAKE_PENDING",
        "checkout_link_sent_at": "2026-01-16T09:00:00Z",
        "last_checkout_error_code": "STRIPE_MODE_MISMATCH",
        "last_checkout_error_message": "Test message",
        "last_checkout_attempt_at": "2026-01-16T09:05:00Z",
    }
    mock_db = _make_db()
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[mock_item])
    mock_db.clients.find = MagicMock(return_value=MagicMock(sort=MagicMock(return_value=mock_cursor)))

    with patch("routes.admin_pending_payments.database.get_db", return_value=mock_db):
        with patch("routes.admin_pending_payments.admin_route_guard", new_callable=AsyncMock, return_value={"role": "ROLE_ADMIN"}):
            with patch("routes.admin_pending_payments.require_owner_or_admin", return_value=None):
                response = client.get(
                    "/api/admin/intake/pending-payments",
                    headers={"Authorization": "Bearer mock-admin-token"},
                )

    assert response.status_code == 200
    data = response.json()
    items = data.get("items", [])
    assert len(items) == 1
    item = items[0]
    assert item.get("full_name") == "Jane Doe"
    assert item.get("subscription_status") == "PENDING"
    assert item.get("onboarding_status") == "INTAKE_PENDING"
    assert item.get("checkout_link_sent_at") == "2026-01-16T09:00:00Z"
    assert item.get("last_checkout_error") is not None
    assert item["last_checkout_error"].get("code") == "STRIPE_MODE_MISMATCH"
    assert item["last_checkout_error"].get("message") == "Test message"


def test_stripe_mode_mismatch_returns_400_from_intake_checkout():
    """When stripe_service raises StripeModeMismatchError, intake checkout returns 400."""
    from services.plan_registry import StripeModeMismatchError

    test_client = TestClient(app)
    mock_db = _make_db()
    mock_db.clients.find_one = AsyncMock(return_value={
        "client_id": "c1",
        "email": "t@ex.com",
        "billing_plan": "PLAN_1_SOLO",
    })

    with patch("routes.intake.database.get_db", return_value=mock_db):
        with patch("routes.intake.create_audit_log", new_callable=AsyncMock):
            with patch("routes.intake.stripe_service.create_checkout_session", new_callable=AsyncMock) as mock_create:
                mock_create.side_effect = StripeModeMismatchError("Stripe key is test mode but STRIPE_TEST_PRICE_PLAN_1_SOLO_MONTHLY is not set")
                response = test_client.post(
                    "/api/intake/checkout?client_id=c1",
                    headers={"Origin": "https://example.com"},
                )

    assert response.status_code == 400
    data = response.json()
    detail = data.get("detail") or {}
    if isinstance(detail, dict):
        assert detail.get("error_code") == "STRIPE_MODE_MISMATCH"
    else:
        assert "STRIPE_MODE_MISMATCH" in str(data)


@pytest.mark.asyncio
async def test_lifecycle_job_only_updates_lifecycle_status():
    """Lifecycle job only updates lifecycle_status; no delete."""
    from job_runner import run_pending_payment_lifecycle

    mock_db = MagicMock()
    r1 = MagicMock()
    r1.modified_count = 1
    r2 = MagicMock()
    r2.modified_count = 0
    mock_db.clients.update_many = AsyncMock(side_effect=[r1, r2])

    with patch("job_runner.database.get_db", return_value=mock_db):
        result = await run_pending_payment_lifecycle()

    assert "abandoned" in (result.get("message") or "")
    calls = mock_db.clients.update_many.call_args_list
    for call in calls:
        args = call[0]
        update = args[1] if len(args) > 1 else {}
        assert "$set" in update
        assert "lifecycle_status" in update["$set"]
        assert "deleted" not in str(update).lower()
