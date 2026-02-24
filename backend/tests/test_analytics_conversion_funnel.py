"""
Tests for admin Analytics conversion funnel (event-based): overview, funnel, failures.
- RBAC: overview/funnel/failures require owner or admin (401 without auth).
- payment_succeeded dedupe: repeated log_event with same idempotency_key does not double-insert.
- Overview aggregation: response structure and conversion_rates present.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


@pytest.fixture
def admin_token(client):
    """Get admin authentication token."""
    response = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Admin auth failed: {response.status_code}")


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# =============================================================================
# RBAC
# =============================================================================

class TestAnalyticsConversionFunnelRBAC:
    """Admin-only endpoints return 401 without auth."""

    def test_overview_requires_auth(self, client):
        response = client.get("/api/admin/analytics/overview?period=30d")
        assert response.status_code == 401

    def test_funnel_requires_auth(self, client):
        response = client.get("/api/admin/analytics/funnel?period=30d")
        assert response.status_code == 401

    def test_failures_requires_auth(self, client):
        response = client.get("/api/admin/analytics/failures?period=30d")
        assert response.status_code == 401

    def test_overview_returns_200_with_admin(self, client, admin_headers):
        response = client.get("/api/admin/analytics/overview?period=30d", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "kpis" in data
        assert "conversion_rates" in data
        assert "median_seconds" in data
        assert "leads_by_source" in data
        assert "failures_by_error" in data
        assert "leads" in data["kpis"]
        assert "payment_succeeded" in data["kpis"]
        assert "first_doc_uploaded" in data["kpis"]

    def test_funnel_returns_200_with_admin(self, client, admin_headers):
        response = client.get("/api/admin/analytics/funnel?period=30d", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "funnel" in data
        assert isinstance(data["funnel"], list)

    def test_failures_returns_200_with_admin(self, client, admin_headers):
        response = client.get("/api/admin/analytics/failures?period=30d", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "events" in data


# =============================================================================
# payment_succeeded dedupe
# =============================================================================

def test_payment_succeeded_dedupe_by_idempotency_key():
    """Calling log_event('payment_succeeded', ..., idempotency_key=X) twice inserts only one document."""
    import asyncio
    from services.analytics_service import log_event, COLLECTION

    insert_one_calls = []
    mock_coll = MagicMock()
    mock_coll.find_one = AsyncMock(side_effect=[None, {"_id": 1}])
    mock_coll.insert_one = AsyncMock(side_effect=lambda doc: insert_one_calls.append(doc))

    mock_db = MagicMock()
    mock_db.__getitem__ = lambda self, name: mock_coll if name == COLLECTION else MagicMock()

    with patch("services.analytics_service.database") as mock_db_module:
        mock_db_module.get_db.return_value = mock_db

        async def run():
            r1 = await log_event(
                "payment_succeeded",
                {"client_id": "c1", "stripe_subscription_id": "sub_1"},
                idempotency_key="evt_123",
            )
            r2 = await log_event(
                "payment_succeeded",
                {"client_id": "c1", "stripe_subscription_id": "sub_1"},
                idempotency_key="evt_123",
            )
            return r1, r2

        r1, r2 = asyncio.run(run())

    assert r1 is True
    assert r2 is False
    assert len(insert_one_calls) == 1
    assert insert_one_calls[0].get("event") == "payment_succeeded"
    assert insert_one_calls[0].get("idempotency_key") == "evt_123"


# =============================================================================
# Overview aggregation structure
# =============================================================================

def test_overview_aggregation_structure_and_conversion_rates(client, admin_headers):
    """Overview returns kpis and conversion_rates with expected keys; conversion % is numeric."""
    response = client.get("/api/admin/analytics/overview?period=30d", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    kpis = data["kpis"]
    assert kpis["leads"] >= 0
    assert kpis["intake_submitted"] >= 0
    assert kpis["payment_succeeded"] >= 0
    assert kpis["first_doc_uploaded"] >= 0
    rates = data["conversion_rates"]
    assert "lead_to_intake" in rates
    assert "checkout_to_paid" in rates
    assert "password_set_to_first_value" in rates
    assert isinstance(rates["lead_to_intake"], (int, float))
