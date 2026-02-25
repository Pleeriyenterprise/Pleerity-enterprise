"""
Tests for admin Analytics Revenue and Executive Overview endpoints.

- RBAC: /revenue and /executive-overview return 401 without auth.
- With admin: revenue returns 200 and expected shape (kpis, subscriber_breakdown, time_series, payment_health).
- With admin: executive-overview returns 200 and expected shape (row1_core, row2_saas, subscription_performance, etc.).
"""

import pytest

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

class TestRevenueExecutiveRBAC:
    """Revenue and Executive Overview require owner or admin."""

    def test_revenue_requires_auth(self, client):
        response = client.get("/api/admin/analytics/revenue?period=30d")
        assert response.status_code == 401

    def test_executive_overview_requires_auth(self, client):
        response = client.get("/api/admin/analytics/executive-overview")
        assert response.status_code == 401


# =============================================================================
# Revenue endpoint shape
# =============================================================================

def test_revenue_returns_200_and_shape(client, admin_headers):
    """Revenue returns KPIs, subscriber_breakdown, time_series, payment_health."""
    response = client.get("/api/admin/analytics/revenue?period=30d", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "kpis" in data
    assert "subscriber_breakdown" in data
    assert "time_series" in data
    assert "payment_health" in data
    kpis = data["kpis"]
    assert "total_revenue_lifetime_pence" in kpis
    assert "revenue_period_pence" in kpis
    assert "recurring_revenue_pence" in kpis
    assert "active_subscribers" in kpis
    assert isinstance(data["subscriber_breakdown"], list)
    assert isinstance(data["time_series"], list)
    ph = data["payment_health"]
    assert "failed_payments_last_30d" in ph
    assert "refunds_last_30d" in ph


# =============================================================================
# Executive Overview endpoint shape
# =============================================================================

def test_executive_overview_returns_200_and_shape(client, admin_headers):
    """Executive Overview returns row1_core, row2_saas, subscription_performance, risk, valuation, growth_efficiency."""
    response = client.get("/api/admin/analytics/executive-overview", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "row1_core" in data
    assert "row2_saas" in data
    assert "subscription_performance" in data
    assert "revenue_composition" in data
    assert "monthly_trend_12" in data
    assert "financial_stability" in data
    assert "risk_indicators" in data
    assert "valuation_snapshot" in data
    assert "growth_efficiency" in data
    row1 = data["row1_core"]
    assert "mrr_pence" in row1
    assert "arr_pence" in row1
    assert "revenue_ytd_pence" in row1
    assert "gross_profit_ytd_pence" in row1
    row2 = data["row2_saas"]
    assert "active_subscribers" in row2
    assert "nrr" in row2
    assert "arpu_pence" in row2
    assert "ltv_pence" in row2
    assert isinstance(data["subscription_performance"], list)
    assert "revenue_top5_pct" in data["risk_indicators"]
    val = data["valuation_snapshot"]
    assert "arr_pence" in val
    assert "multiple_low" in val
    assert "multiple_high" in val
    assert "implied_valuation_low_gbp" in val
    assert "implied_valuation_high_gbp" in val
    ge = data["growth_efficiency"]
    assert "leads_30d" in ge
    assert "trials_30d" in ge
    assert "conversion_pct" in ge
