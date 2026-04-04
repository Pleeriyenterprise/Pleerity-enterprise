"""Client lifecycle API and pending-payments bucket behaviour."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request
from fastapi.testclient import TestClient

from middleware import require_owner_or_admin
from server import app


@pytest.fixture
def client():
    return TestClient(app)


async def _override_owner_admin(_request: Request):
    return {"role": "ROLE_ADMIN", "portal_user_id": "admin1"}


def _mock_db_for_pending(items):
    db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=items)
    db.clients.find = MagicMock(return_value=MagicMock(sort=MagicMock(return_value=mock_cursor)))
    return db


def test_pending_payments_invalid_bucket_returns_400(client):
    app.dependency_overrides[require_owner_or_admin] = _override_owner_admin
    try:
        with patch("routes.admin_pending_payments.database.get_db", return_value=_mock_db_for_pending([])):
            with patch("routes.admin_pending_payments.admin_route_guard", new_callable=AsyncMock, return_value={"role": "ROLE_ADMIN"}):
                with patch(
                    "routes.admin_pending_payments.latest_provisioning_jobs_for_clients",
                    new_callable=AsyncMock,
                    return_value={},
                ):
                    r = client.get(
                        "/api/admin/intake/pending-payments?bucket=not_a_bucket",
                        headers={"Authorization": "Bearer mock"},
                    )
    finally:
        app.dependency_overrides.pop(require_owner_or_admin, None)
    assert r.status_code == 400


def test_pending_payments_includes_bucket_in_response(client):
    row = {
        "client_id": "c1",
        "customer_reference": "PLE-X",
        "email": "a@b.com",
        "full_name": "A",
        "billing_plan": "PLAN_1_SOLO",
        "created_at": "2026-01-01T00:00:00Z",
        "lifecycle_status": "pending_payment",
        "subscription_status": "PENDING",
        "onboarding_status": "INTAKE_PENDING",
    }
    app.dependency_overrides[require_owner_or_admin] = _override_owner_admin
    try:
        with patch("routes.admin_pending_payments.database.get_db", return_value=_mock_db_for_pending([row])):
            with patch("routes.admin_pending_payments.admin_route_guard", new_callable=AsyncMock, return_value={"role": "ROLE_ADMIN"}):
                with patch(
                    "routes.admin_pending_payments.latest_provisioning_jobs_for_clients",
                    new_callable=AsyncMock,
                    return_value={"c1": {"job_id": "j1", "status": "FAILED"}},
                ):
                    r = client.get(
                        "/api/admin/intake/pending-payments?bucket=pending",
                        headers={"Authorization": "Bearer mock"},
                    )
    finally:
        app.dependency_overrides.pop(require_owner_or_admin, None)
    assert r.status_code == 200
    data = r.json()
    assert data.get("bucket") == "pending"
    assert data["items"][0]["provisioning_state"]["job_id"] == "j1"
    assert data["items"][0]["provisioning_state"]["job_status"] == "FAILED"


@pytest.mark.asyncio
async def test_permanent_delete_preflight_blocks_stripe_subscription():
    from services.client_lifecycle_service import permanent_delete_preflight

    db = MagicMock()
    db.clients.find_one = AsyncMock(
        return_value={
            "client_id": "x",
            "stripe_customer_id": "",
            "stripe_subscription_id": "sub_123",
            "subscription_status": "canceled",
        }
    )

    with patch("services.client_lifecycle_service._count", new_callable=AsyncMock, return_value=0):
        allowed, blockers = await permanent_delete_preflight(db, "x")
    assert allowed is False
    assert "stripe_subscription_id_present" in blockers


@pytest.mark.asyncio
async def test_persist_operational_skips_archived():
    from services.client_lifecycle_service import persist_operational_client_lifecycle_if_needed

    db = MagicMock()
    db.clients.find_one = AsyncMock(
        return_value={
            "client_id": "c",
            "client_lifecycle_status": "ARCHIVED",
            "is_deleted": True,
            "onboarding_status": "PROVISIONED",
            "subscription_status": "ACTIVE",
        }
    )
    db.clients.update_one = AsyncMock()
    await persist_operational_client_lifecycle_if_needed(db, "c")
    db.clients.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_persist_operational_updates_when_mismatched():
    from services.client_lifecycle_service import persist_operational_client_lifecycle_if_needed

    db = MagicMock()
    db.clients.find_one = AsyncMock(
        return_value={
            "client_id": "c",
            "client_lifecycle_status": "LEAD",
            "onboarding_status": "PROVISIONED",
            "subscription_status": "ACTIVE",
        }
    )
    db.clients.update_one = AsyncMock()
    await persist_operational_client_lifecycle_if_needed(db, "c")
    db.clients.update_one.assert_called_once()
    call = db.clients.update_one.call_args
    assert call[0][1]["$set"]["client_lifecycle_status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_permanent_delete_preflight_blocks_active_subscription():
    from services.client_lifecycle_service import permanent_delete_preflight

    db = MagicMock()
    db.clients.find_one = AsyncMock(
        return_value={
            "client_id": "x",
            "stripe_customer_id": "",
            "stripe_subscription_id": "",
            "subscription_status": "active",
        }
    )

    with patch("services.client_lifecycle_service._count", new_callable=AsyncMock, return_value=0):
        allowed, blockers = await permanent_delete_preflight(db, "x")
    assert allowed is False
    assert "subscription_active_or_trialing" in blockers
