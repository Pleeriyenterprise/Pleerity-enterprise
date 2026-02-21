"""
Test suite for Analytics Dashboard, Intake Schema Manager, and Service Detail V2 API
Tests the 4 new features implemented in iteration 47:
1. Analytics Dashboard APIs
2. Intake Schema Manager APIs
3. Dynamic Service Detail Page V2 API
4. Toast error fix verification (via API status codes)
"""
import pytest

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"


@pytest.fixture
def admin_token(client):
    """Get admin authentication token"""
    response = client.post("/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Admin authentication failed: {response.status_code}")


@pytest.fixture
def client_token(client):
    """Get client authentication token"""
    response = client.post("/api/auth/login", json={
        "email": CLIENT_EMAIL,
        "password": CLIENT_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Client authentication failed: {response.status_code}")


@pytest.fixture
def admin_headers(admin_token):
    """Headers with admin auth token"""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def client_headers(client_token):
    """Headers with client auth token"""
    return {
        "Authorization": f"Bearer {client_token}",
        "Content-Type": "application/json"
    }


# ============================================================================
# ANALYTICS DASHBOARD API TESTS
# ============================================================================

class TestAnalyticsSummary:
    """Test GET /api/admin/analytics/summary endpoint"""
    
    def test_summary_returns_200(self, client, admin_headers):
        """Summary endpoint returns 200 with valid admin token"""
        response = client.get(
            "/api/admin/analytics/summary?period=30d",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "revenue" in data
        assert "orders" in data
        assert "average_order_value" in data
        assert "completion_rate" in data
        assert "status_breakdown" in data
    
    def test_summary_revenue_structure(self, client, admin_headers):
        """Revenue data has correct structure"""
        response = client.get(
            "/api/admin/analytics/summary?period=30d",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        revenue = data["revenue"]
        assert "total_pence" in revenue
        assert "total_formatted" in revenue
        assert "change_percent" in revenue
        assert "trend" in revenue
        assert revenue["trend"] in ["up", "down", "flat"]
    
    def test_summary_orders_structure(self, client, admin_headers):
        """Orders data has correct structure"""
        response = client.get(
            "/api/admin/analytics/summary?period=30d",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        orders = data["orders"]
        assert "total" in orders
        assert "paid" in orders
        assert "change_percent" in orders
        assert "trend" in orders
    
    def test_summary_aov_structure(self, client, admin_headers):
        """Average order value has correct structure"""
        response = client.get(
            "/api/admin/analytics/summary?period=30d",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        aov = data["average_order_value"]
        assert "pence" in aov
        assert "formatted" in aov
        assert "change_percent" in aov
    
    def test_summary_completion_rate_structure(self, client, admin_headers):
        """Completion rate has correct structure"""
        response = client.get(
            "/api/admin/analytics/summary?period=30d",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        completion = data["completion_rate"]
        assert "percent" in completion
        assert "completed" in completion
        assert "total" in completion
    
    def test_summary_different_periods(self, client, admin_headers):
        """Summary works with different period values"""
        periods = ["today", "7d", "30d", "90d", "ytd", "all"]
        
        for period in periods:
            response = client.get(
                f"/api/admin/analytics/summary?period={period}",
                headers=admin_headers
            )
            assert response.status_code == 200, f"Failed for period: {period}"
            data = response.json()
            assert data["period"] == period
    
    def test_summary_requires_admin(self, client):
        """Summary endpoint requires admin authentication"""
        response = client.get("/api/admin/analytics/summary")
        assert response.status_code in [401, 403]


class TestAnalyticsServices:
    """Test GET /api/admin/analytics/services endpoint"""
    
    def test_services_returns_200(self, client, admin_headers):
        """Services endpoint returns 200"""
        response = client.get(
            "/api/admin/analytics/services?period=30d",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "services" in data
        assert "total_services" in data
        assert isinstance(data["services"], list)
    
    def test_services_structure(self, client, admin_headers):
        """Service items have correct structure"""
        response = client.get(
            "/api/admin/analytics/services?period=30d",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if data["services"]:
            service = data["services"][0]
            assert "service_code" in service
            assert "service_name" in service
            assert "orders" in service
            assert "revenue_pence" in service
            assert "revenue_formatted" in service


class TestAnalyticsConversionFunnel:
    """Test GET /api/admin/analytics/conversion-funnel endpoint"""
    
    def test_funnel_returns_200(self, client, admin_headers):
        """Conversion funnel endpoint returns 200"""
        response = client.get(
            "/api/admin/analytics/conversion-funnel?period=30d",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "funnel" in data
        assert "overall_conversion" in data
        assert isinstance(data["funnel"], list)
    
    def test_funnel_stages(self, client, admin_headers):
        """Funnel has expected stages"""
        response = client.get(
            "/api/admin/analytics/conversion-funnel?period=30d",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        stages = [f["stage"] for f in data["funnel"]]
        assert "Drafts Created" in stages
        assert "Payment Started" in stages
        assert "Payment Completed" in stages
        assert "Order Completed" in stages


class TestAnalyticsSLA:
    """Test GET /api/admin/analytics/sla-performance endpoint"""
    
    def test_sla_returns_200(self, client, admin_headers):
        """SLA performance endpoint returns 200"""
        response = client.get(
            "/api/admin/analytics/sla-performance?period=30d",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "on_time" in data
        assert "warnings_issued" in data
        assert "breached" in data
        assert "health_score" in data
    
    def test_sla_structure(self, client, admin_headers):
        """SLA data has correct structure"""
        response = client.get(
            "/api/admin/analytics/sla-performance?period=30d",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "count" in data["on_time"]
        assert "percent" in data["on_time"]
        assert "count" in data["breached"]
        assert "percent" in data["breached"]


class TestAnalyticsCustomers:
    """Test GET /api/admin/analytics/customers endpoint"""
    
    def test_customers_returns_200(self, client, admin_headers):
        """Customers endpoint returns 200"""
        response = client.get(
            "/api/admin/analytics/customers?period=30d",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "total_customers" in data
        assert "repeat_customers" in data
        assert "repeat_rate" in data
        assert "top_customers" in data


class TestAnalyticsAddons:
    """Test GET /api/admin/analytics/addons endpoint"""
    
    def test_addons_returns_200(self, client, admin_headers):
        """Addons endpoint returns 200"""
        response = client.get(
            "/api/admin/analytics/addons?period=30d",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "fast_track" in data
        assert "printed_copy" in data
        assert "total_addon_revenue" in data
    
    def test_addons_structure(self, client, admin_headers):
        """Addon data has correct structure"""
        response = client.get(
            "/api/admin/analytics/addons?period=30d",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        fast_track = data["fast_track"]
        assert "count" in fast_track
        assert "adoption_rate" in fast_track
        assert "revenue_pence" in fast_track
        assert "revenue_formatted" in fast_track


# ============================================================================
# INTAKE SCHEMA MANAGER API TESTS
# ============================================================================

class TestIntakeSchemaServices:
    """Test GET /api/admin/intake-schema/services endpoint"""
    
    def test_services_list_returns_200(self, client, admin_headers):
        """Services list endpoint returns 200"""
        response = client.get(
            "/api/admin/intake-schema/services",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "services" in data
        assert "total" in data
        assert isinstance(data["services"], list)
    
    def test_services_list_has_11_services(self, client, admin_headers):
        """Services list returns 11 services"""
        response = client.get(
            "/api/admin/intake-schema/services",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should have 11 services based on requirements
        assert data["total"] >= 11, f"Expected at least 11 services, got {data['total']}"
    
    def test_services_have_field_counts(self, client, admin_headers):
        """Each service has field_count"""
        response = client.get(
            "/api/admin/intake-schema/services",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for service in data["services"]:
            assert "service_code" in service
            assert "field_count" in service
            assert isinstance(service["field_count"], int)
            assert service["field_count"] > 0


class TestIntakeSchemaEditor:
    """Test GET /api/admin/intake-schema/{service_code} endpoint"""
    
    def test_schema_editor_returns_200(self, client, admin_headers):
        """Schema editor endpoint returns 200 for valid service"""
        response = client.get(
            "/api/admin/intake-schema/DOC_PACK_ESSENTIAL",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "service_code" in data
        assert "fields" in data
        assert data["service_code"] == "DOC_PACK_ESSENTIAL"
    
    def test_schema_editor_fields_structure(self, client, admin_headers):
        """Schema fields have correct structure"""
        response = client.get(
            "/api/admin/intake-schema/DOC_PACK_ESSENTIAL",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["fields"]) > 0
        
        field = data["fields"][0]
        assert "base" in field
        assert "has_override" in field
        
        base = field["base"]
        assert "field_key" in base
        assert "label" in base
        assert "type" in base
    
    def test_schema_editor_404_for_invalid_service(self, client, admin_headers):
        """Schema editor returns 404 for invalid service"""
        response = client.get(
            "/api/admin/intake-schema/INVALID_SERVICE_CODE",
            headers=admin_headers
        )
        assert response.status_code == 404


# ============================================================================
# SERVICE DETAIL V2 API TESTS (Public)
# ============================================================================

class TestServiceDetailV2:
    """Test GET /api/public/v2/services/{service_code} endpoint"""
    
    def test_service_detail_returns_200(self, client):
        """Service detail V2 endpoint returns 200 for valid service"""
        response = client.get("/api/public/v2/services/AI_WF_BLUEPRINT")
        assert response.status_code == 200
        data = response.json()
        
        assert "service_code" in data
        assert "service_name" in data
        assert "description" in data
    
    def test_service_detail_has_pricing(self, client):
        """Service detail includes pricing information"""
        response = client.get("/api/public/v2/services/AI_WF_BLUEPRINT")
        assert response.status_code == 200
        data = response.json()
        
        # V2 API uses base_price directly
        assert "base_price" in data
        assert "price_currency" in data
    
    def test_service_detail_has_slug(self, client):
        """Service detail includes slug for URL"""
        response = client.get("/api/public/v2/services/AI_WF_BLUEPRINT")
        assert response.status_code == 200
        data = response.json()
        
        # V2 API uses learn_more_slug
        assert "learn_more_slug" in data
    
    def test_service_detail_404_for_invalid(self, client):
        """Service detail returns 404 for invalid service code"""
        response = client.get("/api/public/v2/services/INVALID_CODE")
        assert response.status_code == 404
    
    def test_multiple_services_accessible(self, client):
        """Multiple services are accessible via V2 API"""
        service_codes = [
            "AI_WF_BLUEPRINT",
            "DOC_PACK_ESSENTIAL",
        ]
        
        for code in service_codes:
            response = client.get(f"/api/public/v2/services/{code}")
            assert response.status_code == 200, f"Failed for service: {code}"
    
    def test_service_detail_structure(self, client):
        """Service detail has complete structure"""
        response = client.get("/api/public/v2/services/AI_WF_BLUEPRINT")
        assert response.status_code == 200
        data = response.json()
        
        # Verify key fields
        assert "category" in data
        assert "pricing_model" in data
        assert "delivery_type" in data
        assert "turnaround_hours" in data


# ============================================================================
# AUTH ERROR HANDLING TESTS (Toast fix verification)
# ============================================================================

class TestAuthErrorHandling:
    """Test that auth errors return proper 401 status"""
    
    def test_client_orders_returns_401_without_auth(self, client):
        """Client orders endpoint returns 401 without auth"""
        response = client.get("/api/client/orders/")
        assert response.status_code in [401, 403]
    
    def test_admin_analytics_returns_401_without_auth(self, client):
        """Admin analytics endpoint returns 401 without auth"""
        response = client.get("/api/admin/analytics/summary")
        assert response.status_code in [401, 403]
    
    def test_admin_notifications_returns_401_without_auth(self, client):
        """Admin notifications endpoint returns 401 without auth"""
        response = client.get("/api/admin/notifications/preferences")
        assert response.status_code in [401, 403]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
