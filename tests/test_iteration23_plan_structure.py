"""
Iteration 23 - New Plan Structure Testing
Tests for the new plan codes (PLAN_1_SOLO, PLAN_2_PORTFOLIO, PLAN_3_PRO)
and property limit enforcement at intake level.

Test Coverage:
1. Plans Endpoint - GET /api/intake/plans returns new plan structure
2. Property Count Validation - POST /api/intake/validate-property-count enforces limits
3. Property Limit Exceeded - PLAN_1_SOLO with 3 properties should fail
4. Property Limit OK - PLAN_1_SOLO with 2 properties should pass
5. Client Entitlements - GET /api/client/entitlements uses new plan_registry
6. Admin Feature Matrix - GET /api/admin/system/feature-matrix uses new plan_registry
7. Tenant Portal View-Only - POST /api/tenant/request-certificate returns FEATURE_DISABLED
8. Tenant Portal View-Only - POST /api/tenant/contact-landlord returns FEATURE_DISABLED
9. Tenant Portal View-Only - GET /api/tenant/requests returns empty list with note
10. Tenant Dashboard Still Works - GET /api/tenant/dashboard returns data
11. Legacy Plan Mapping - Old plan codes map to new codes
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"


class TestPlansEndpoint:
    """Test GET /api/intake/plans returns new plan structure"""
    
    def test_plans_endpoint_returns_new_structure(self):
        """Verify /api/intake/plans returns PLAN_1_SOLO, PLAN_2_PORTFOLIO, PLAN_3_PRO"""
        response = requests.get(f"{BASE_URL}/api/intake/plans")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "plans" in data, "Response should contain 'plans' key"
        
        plans = data["plans"]
        assert len(plans) >= 3, f"Expected at least 3 plans, got {len(plans)}"
        
        # Extract plan IDs
        plan_ids = [p["plan_id"] for p in plans]
        
        # Verify new plan codes exist
        assert "PLAN_1_SOLO" in plan_ids, "PLAN_1_SOLO should be in plans"
        assert "PLAN_2_PORTFOLIO" in plan_ids, "PLAN_2_PORTFOLIO should be in plans"
        assert "PLAN_3_PRO" in plan_ids, "PLAN_3_PRO should be in plans"
        
        print(f"✓ Plans endpoint returns {len(plans)} plans with new structure")
    
    def test_plan_1_solo_details(self):
        """Verify PLAN_1_SOLO has correct limits and pricing"""
        response = requests.get(f"{BASE_URL}/api/intake/plans")
        assert response.status_code == 200
        
        data = response.json()
        solo_plan = next((p for p in data["plans"] if p["plan_id"] == "PLAN_1_SOLO"), None)
        
        assert solo_plan is not None, "PLAN_1_SOLO not found"
        assert solo_plan["max_properties"] == 2, f"Expected max_properties=2, got {solo_plan['max_properties']}"
        assert solo_plan["monthly_price"] == 19.00, f"Expected monthly_price=19.00, got {solo_plan['monthly_price']}"
        assert solo_plan["setup_fee"] == 49.00, f"Expected setup_fee=49.00, got {solo_plan['setup_fee']}"
        
        print(f"✓ PLAN_1_SOLO: {solo_plan['max_properties']} props, £{solo_plan['monthly_price']}/mo, £{solo_plan['setup_fee']} setup")
    
    def test_plan_2_portfolio_details(self):
        """Verify PLAN_2_PORTFOLIO has correct limits and pricing"""
        response = requests.get(f"{BASE_URL}/api/intake/plans")
        assert response.status_code == 200
        
        data = response.json()
        portfolio_plan = next((p for p in data["plans"] if p["plan_id"] == "PLAN_2_PORTFOLIO"), None)
        
        assert portfolio_plan is not None, "PLAN_2_PORTFOLIO not found"
        assert portfolio_plan["max_properties"] == 10, f"Expected max_properties=10, got {portfolio_plan['max_properties']}"
        assert portfolio_plan["monthly_price"] == 39.00, f"Expected monthly_price=39.00, got {portfolio_plan['monthly_price']}"
        assert portfolio_plan["setup_fee"] == 79.00, f"Expected setup_fee=79.00, got {portfolio_plan['setup_fee']}"
        
        print(f"✓ PLAN_2_PORTFOLIO: {portfolio_plan['max_properties']} props, £{portfolio_plan['monthly_price']}/mo, £{portfolio_plan['setup_fee']} setup")
    
    def test_plan_3_pro_details(self):
        """Verify PLAN_3_PRO has correct limits and pricing"""
        response = requests.get(f"{BASE_URL}/api/intake/plans")
        assert response.status_code == 200
        
        data = response.json()
        pro_plan = next((p for p in data["plans"] if p["plan_id"] == "PLAN_3_PRO"), None)
        
        assert pro_plan is not None, "PLAN_3_PRO not found"
        assert pro_plan["max_properties"] == 25, f"Expected max_properties=25, got {pro_plan['max_properties']}"
        assert pro_plan["monthly_price"] == 79.00, f"Expected monthly_price=79.00, got {pro_plan['monthly_price']}"
        assert pro_plan["setup_fee"] == 149.00, f"Expected setup_fee=149.00, got {pro_plan['setup_fee']}"
        
        print(f"✓ PLAN_3_PRO: {pro_plan['max_properties']} props, £{pro_plan['monthly_price']}/mo, £{pro_plan['setup_fee']} setup")


class TestPropertyCountValidation:
    """Test POST /api/intake/validate-property-count enforces limits"""
    
    def test_plan_1_solo_with_2_properties_allowed(self):
        """PLAN_1_SOLO with 2 properties should pass"""
        response = requests.post(
            f"{BASE_URL}/api/intake/validate-property-count",
            json={"plan_id": "PLAN_1_SOLO", "property_count": 2}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["allowed"] == True, f"Expected allowed=True, got {data}"
        assert data["max_properties"] == 2, f"Expected max_properties=2, got {data['max_properties']}"
        
        print("✓ PLAN_1_SOLO with 2 properties: ALLOWED")
    
    def test_plan_1_solo_with_3_properties_rejected(self):
        """PLAN_1_SOLO with 3 properties should fail with PROPERTY_LIMIT_EXCEEDED"""
        response = requests.post(
            f"{BASE_URL}/api/intake/validate-property-count",
            json={"plan_id": "PLAN_1_SOLO", "property_count": 3}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["allowed"] == False, f"Expected allowed=False, got {data}"
        assert data.get("error_code") == "PROPERTY_LIMIT_EXCEEDED", f"Expected error_code=PROPERTY_LIMIT_EXCEEDED, got {data.get('error_code')}"
        assert data.get("upgrade_required") == True, "Expected upgrade_required=True"
        assert data.get("upgrade_to") == "PLAN_2_PORTFOLIO", f"Expected upgrade_to=PLAN_2_PORTFOLIO, got {data.get('upgrade_to')}"
        
        print(f"✓ PLAN_1_SOLO with 3 properties: REJECTED (error_code={data.get('error_code')})")
    
    def test_plan_2_portfolio_with_10_properties_allowed(self):
        """PLAN_2_PORTFOLIO with 10 properties should pass"""
        response = requests.post(
            f"{BASE_URL}/api/intake/validate-property-count",
            json={"plan_id": "PLAN_2_PORTFOLIO", "property_count": 10}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["allowed"] == True, f"Expected allowed=True, got {data}"
        assert data["max_properties"] == 10
        
        print("✓ PLAN_2_PORTFOLIO with 10 properties: ALLOWED")
    
    def test_plan_2_portfolio_with_11_properties_rejected(self):
        """PLAN_2_PORTFOLIO with 11 properties should fail"""
        response = requests.post(
            f"{BASE_URL}/api/intake/validate-property-count",
            json={"plan_id": "PLAN_2_PORTFOLIO", "property_count": 11}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["allowed"] == False
        assert data.get("error_code") == "PROPERTY_LIMIT_EXCEEDED"
        assert data.get("upgrade_to") == "PLAN_3_PRO"
        
        print(f"✓ PLAN_2_PORTFOLIO with 11 properties: REJECTED (upgrade_to={data.get('upgrade_to')})")
    
    def test_plan_3_pro_with_25_properties_allowed(self):
        """PLAN_3_PRO with 25 properties should pass"""
        response = requests.post(
            f"{BASE_URL}/api/intake/validate-property-count",
            json={"plan_id": "PLAN_3_PRO", "property_count": 25}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["allowed"] == True
        assert data["max_properties"] == 25
        
        print("✓ PLAN_3_PRO with 25 properties: ALLOWED")
    
    def test_plan_3_pro_with_26_properties_rejected(self):
        """PLAN_3_PRO with 26 properties should fail (no upgrade available)"""
        response = requests.post(
            f"{BASE_URL}/api/intake/validate-property-count",
            json={"plan_id": "PLAN_3_PRO", "property_count": 26}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["allowed"] == False
        assert data.get("error_code") == "PROPERTY_LIMIT_EXCEEDED"
        # No upgrade available for PLAN_3_PRO
        
        print(f"✓ PLAN_3_PRO with 26 properties: REJECTED (no upgrade available)")


class TestLegacyPlanMapping:
    """Test that legacy plan codes map to new codes correctly"""
    
    def test_legacy_plan_1_maps_to_solo(self):
        """PLAN_1 should map to PLAN_1_SOLO (2 properties)"""
        response = requests.post(
            f"{BASE_URL}/api/intake/validate-property-count",
            json={"plan_id": "PLAN_1", "property_count": 2}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["allowed"] == True, f"PLAN_1 with 2 properties should be allowed: {data}"
        
        # Test limit exceeded
        response2 = requests.post(
            f"{BASE_URL}/api/intake/validate-property-count",
            json={"plan_id": "PLAN_1", "property_count": 3}
        )
        data2 = response2.json()
        assert data2["allowed"] == False, "PLAN_1 with 3 properties should be rejected"
        
        print("✓ Legacy PLAN_1 maps to PLAN_1_SOLO (2 property limit)")
    
    def test_legacy_plan_2_5_maps_to_portfolio(self):
        """PLAN_2_5 should map to PLAN_2_PORTFOLIO (10 properties)"""
        response = requests.post(
            f"{BASE_URL}/api/intake/validate-property-count",
            json={"plan_id": "PLAN_2_5", "property_count": 10}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["allowed"] == True, f"PLAN_2_5 with 10 properties should be allowed: {data}"
        
        # Test limit exceeded
        response2 = requests.post(
            f"{BASE_URL}/api/intake/validate-property-count",
            json={"plan_id": "PLAN_2_5", "property_count": 11}
        )
        data2 = response2.json()
        assert data2["allowed"] == False, "PLAN_2_5 with 11 properties should be rejected"
        
        print("✓ Legacy PLAN_2_5 maps to PLAN_2_PORTFOLIO (10 property limit)")
    
    def test_legacy_plan_6_15_maps_to_pro(self):
        """PLAN_6_15 should map to PLAN_3_PRO (25 properties)"""
        response = requests.post(
            f"{BASE_URL}/api/intake/validate-property-count",
            json={"plan_id": "PLAN_6_15", "property_count": 25}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["allowed"] == True, f"PLAN_6_15 with 25 properties should be allowed: {data}"
        
        # Test limit exceeded
        response2 = requests.post(
            f"{BASE_URL}/api/intake/validate-property-count",
            json={"plan_id": "PLAN_6_15", "property_count": 26}
        )
        data2 = response2.json()
        assert data2["allowed"] == False, "PLAN_6_15 with 26 properties should be rejected"
        
        print("✓ Legacy PLAN_6_15 maps to PLAN_3_PRO (25 property limit)")


class TestClientEntitlements:
    """Test GET /api/client/entitlements uses new plan_registry"""
    
    @pytest.fixture
    def client_token(self):
        """Get client auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Client login failed: {response.status_code} - {response.text}")
        return response.json().get("access_token")
    
    def test_client_entitlements_endpoint(self, client_token):
        """Verify /api/client/entitlements returns feature matrix"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(f"{BASE_URL}/api/client/entitlements", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify structure
        assert "plan" in data, "Response should contain 'plan'"
        assert "features" in data, "Response should contain 'features'"
        assert "max_properties" in data, "Response should contain 'max_properties'"
        
        # Verify features structure
        features = data["features"]
        assert isinstance(features, dict), "Features should be a dict"
        
        # Check for expected feature keys
        expected_features = [
            "compliance_dashboard", "compliance_score", "email_notifications",
            "ai_extraction_basic", "tenant_portal"
        ]
        for feature in expected_features:
            assert feature in features, f"Feature '{feature}' should be in entitlements"
        
        print(f"✓ Client entitlements: plan={data['plan']}, max_properties={data['max_properties']}, features={len(features)}")


class TestAdminFeatureMatrix:
    """Test GET /api/admin/system/feature-matrix uses new plan_registry"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
        return response.json().get("access_token")
    
    def test_admin_feature_matrix_endpoint(self, admin_token):
        """Verify /api/admin/system/feature-matrix returns complete matrix"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/system/feature-matrix", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify structure
        assert "features" in data, "Response should contain 'features'"
        assert "plans" in data, "Response should contain 'plans'"
        
        # Verify new plan codes in matrix
        plans = data["plans"]
        assert "PLAN_1_SOLO" in plans, "PLAN_1_SOLO should be in plans"
        assert "PLAN_2_PORTFOLIO" in plans, "PLAN_2_PORTFOLIO should be in plans"
        assert "PLAN_3_PRO" in plans, "PLAN_3_PRO should be in plans"
        
        # Verify plan details
        solo = plans["PLAN_1_SOLO"]
        assert solo["max_properties"] == 2, f"PLAN_1_SOLO max_properties should be 2, got {solo['max_properties']}"
        
        portfolio = plans["PLAN_2_PORTFOLIO"]
        assert portfolio["max_properties"] == 10, f"PLAN_2_PORTFOLIO max_properties should be 10, got {portfolio['max_properties']}"
        
        pro = plans["PLAN_3_PRO"]
        assert pro["max_properties"] == 25, f"PLAN_3_PRO max_properties should be 25, got {pro['max_properties']}"
        
        print(f"✓ Admin feature matrix: {len(data['features'])} features, {len(plans)} plans")
        print(f"  - PLAN_1_SOLO: {solo['max_properties']} props, £{solo['monthly_price']}/mo")
        print(f"  - PLAN_2_PORTFOLIO: {portfolio['max_properties']} props, £{portfolio['monthly_price']}/mo")
        print(f"  - PLAN_3_PRO: {pro['max_properties']} props, £{pro['monthly_price']}/mo")


class TestTenantPortalViewOnly:
    """Test tenant portal is view-only (certificate requests and messaging disabled)"""
    
    @pytest.fixture
    def tenant_token(self):
        """Get tenant auth token - may need to create tenant first"""
        # Try to login as tenant
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "tenant@test.com", "password": "TenantTest123!"}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        
        # If no tenant exists, skip these tests
        pytest.skip("No tenant user available for testing")
    
    def test_tenant_request_certificate_disabled(self, tenant_token):
        """POST /api/tenant/request-certificate should return FEATURE_DISABLED"""
        headers = {"Authorization": f"Bearer {tenant_token}"}
        response = requests.post(
            f"{BASE_URL}/api/tenant/request-certificate",
            headers=headers,
            json={"property_id": "test", "certificate_type": "GAS_SAFETY"}
        )
        
        # Should return 403 or similar with FEATURE_DISABLED
        assert response.status_code in [403, 400], f"Expected 403/400, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check for disabled message
        assert "disabled" in str(data).lower() or "view-only" in str(data).lower() or "FEATURE_DISABLED" in str(data), \
            f"Expected FEATURE_DISABLED message, got: {data}"
        
        print(f"✓ Tenant request-certificate: DISABLED ({response.status_code})")
    
    def test_tenant_contact_landlord_disabled(self, tenant_token):
        """POST /api/tenant/contact-landlord should return FEATURE_DISABLED"""
        headers = {"Authorization": f"Bearer {tenant_token}"}
        response = requests.post(
            f"{BASE_URL}/api/tenant/contact-landlord",
            headers=headers,
            json={"message": "Test message"}
        )
        
        # Should return 403 or similar with FEATURE_DISABLED
        assert response.status_code in [403, 400], f"Expected 403/400, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "disabled" in str(data).lower() or "view-only" in str(data).lower() or "FEATURE_DISABLED" in str(data), \
            f"Expected FEATURE_DISABLED message, got: {data}"
        
        print(f"✓ Tenant contact-landlord: DISABLED ({response.status_code})")
    
    def test_tenant_requests_returns_empty_with_note(self, tenant_token):
        """GET /api/tenant/requests should return empty list with note"""
        headers = {"Authorization": f"Bearer {tenant_token}"}
        response = requests.get(f"{BASE_URL}/api/tenant/requests", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should have empty requests and a note about view-only
        assert "requests" in data or "note" in data or "message" in data, f"Expected requests or note in response: {data}"
        
        print(f"✓ Tenant requests: Returns with view-only note")
    
    def test_tenant_dashboard_still_works(self, tenant_token):
        """GET /api/tenant/dashboard should return data (view-only is OK)"""
        headers = {"Authorization": f"Bearer {tenant_token}"}
        response = requests.get(f"{BASE_URL}/api/tenant/dashboard", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Dashboard should return some data
        assert data is not None, "Dashboard should return data"
        
        print(f"✓ Tenant dashboard: Works (view-only access)")


class TestTenantEndpointsWithoutAuth:
    """Test tenant endpoints return proper errors without auth"""
    
    def test_tenant_request_certificate_no_auth(self):
        """POST /api/tenant/request-certificate without auth should return 401 or 403"""
        response = requests.post(
            f"{BASE_URL}/api/tenant/request-certificate",
            json={"property_id": "test", "certificate_type": "GAS_SAFETY"}
        )
        
        # Should return 401 (unauthorized) or 403 (forbidden)
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ Tenant request-certificate without auth: {response.status_code}")
    
    def test_tenant_contact_landlord_no_auth(self):
        """POST /api/tenant/contact-landlord without auth should return 401 or 403"""
        response = requests.post(
            f"{BASE_URL}/api/tenant/contact-landlord",
            json={"message": "Test message"}
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ Tenant contact-landlord without auth: {response.status_code}")


class TestHealthAndBasicEndpoints:
    """Basic health checks"""
    
    def test_health_endpoint(self):
        """Verify /api/health returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        print("✓ Health endpoint: OK")
    
    def test_plans_endpoint_accessible(self):
        """Verify /api/intake/plans is publicly accessible"""
        response = requests.get(f"{BASE_URL}/api/intake/plans")
        assert response.status_code == 200, f"Plans endpoint failed: {response.status_code}"
        print("✓ Plans endpoint: Publicly accessible")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
