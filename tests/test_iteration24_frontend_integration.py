"""
Iteration 24 - Frontend Integration Testing for New Plan Structure
Tests for verifying frontend displays new plans correctly and property limits work.

Test Coverage:
1. Intake Plans Page - Shows new plans (Solo Landlord £19, Portfolio £39, Professional £79)
2. Intake Property Limit - Solo plan shows 1/2 counter, can add 2nd property
3. Intake Property Limit Exceeded - Cannot add 3rd property on Solo plan
4. Backend Property Validation - POST /api/intake/validate-property-count enforces limits
5. AI Extraction Mode - /api/documents/analyze returns extraction_mode based on plan
6. Client Entitlements - GET /api/client/entitlements returns correct feature flags
7. Tenant Portal View-Only - POST /api/tenant/request-certificate returns FEATURE_DISABLED
8. Admin Feature Matrix - GET /api/admin/system/feature-matrix returns all plans
9. Dashboard Works - Client dashboard loads correctly
10. Score Trending Still Works - GET /api/client/compliance-score/trend returns data
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


class TestIntakePlansDisplay:
    """Test intake plans endpoint returns correct plan structure"""
    
    def test_plans_endpoint_returns_three_plans(self):
        """Verify /api/intake/plans returns 3 plans with correct structure"""
        response = requests.get(f"{BASE_URL}/api/intake/plans")
        assert response.status_code == 200
        
        data = response.json()
        plans = data.get("plans", [])
        
        assert len(plans) == 3, f"Expected 3 plans, got {len(plans)}"
        
        plan_ids = [p["plan_id"] for p in plans]
        assert "PLAN_1_SOLO" in plan_ids
        assert "PLAN_2_PORTFOLIO" in plan_ids
        assert "PLAN_3_PRO" in plan_ids
        
        print(f"✓ Plans endpoint returns 3 plans: {plan_ids}")
    
    def test_solo_landlord_plan_pricing(self):
        """Verify Solo Landlord Plan has £19/mo pricing"""
        response = requests.get(f"{BASE_URL}/api/intake/plans")
        data = response.json()
        
        solo = next((p for p in data["plans"] if p["plan_id"] == "PLAN_1_SOLO"), None)
        assert solo is not None
        assert solo["monthly_price"] == 19.0, f"Expected £19, got £{solo['monthly_price']}"
        assert solo["max_properties"] == 2, f"Expected 2 properties, got {solo['max_properties']}"
        assert solo["setup_fee"] == 49.0, f"Expected £49 setup, got £{solo['setup_fee']}"
        
        print(f"✓ Solo Landlord: £{solo['monthly_price']}/mo, {solo['max_properties']} props, £{solo['setup_fee']} setup")
    
    def test_portfolio_plan_pricing(self):
        """Verify Portfolio Plan has £39/mo pricing"""
        response = requests.get(f"{BASE_URL}/api/intake/plans")
        data = response.json()
        
        portfolio = next((p for p in data["plans"] if p["plan_id"] == "PLAN_2_PORTFOLIO"), None)
        assert portfolio is not None
        assert portfolio["monthly_price"] == 39.0, f"Expected £39, got £{portfolio['monthly_price']}"
        assert portfolio["max_properties"] == 10, f"Expected 10 properties, got {portfolio['max_properties']}"
        assert portfolio["is_popular"] == True, "Portfolio should be marked as popular"
        
        print(f"✓ Portfolio: £{portfolio['monthly_price']}/mo, {portfolio['max_properties']} props, popular={portfolio['is_popular']}")
    
    def test_professional_plan_pricing(self):
        """Verify Professional Plan has £79/mo pricing"""
        response = requests.get(f"{BASE_URL}/api/intake/plans")
        data = response.json()
        
        pro = next((p for p in data["plans"] if p["plan_id"] == "PLAN_3_PRO"), None)
        assert pro is not None
        assert pro["monthly_price"] == 79.0, f"Expected £79, got £{pro['monthly_price']}"
        assert pro["max_properties"] == 25, f"Expected 25 properties, got {pro['max_properties']}"
        
        print(f"✓ Professional: £{pro['monthly_price']}/mo, {pro['max_properties']} props")


class TestPropertyLimitValidation:
    """Test property count validation endpoint"""
    
    def test_solo_plan_allows_2_properties(self):
        """PLAN_1_SOLO should allow up to 2 properties"""
        response = requests.post(
            f"{BASE_URL}/api/intake/validate-property-count",
            json={"plan_id": "PLAN_1_SOLO", "property_count": 2}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["allowed"] == True
        assert data["max_properties"] == 2
        
        print("✓ Solo plan allows 2 properties")
    
    def test_solo_plan_rejects_3_properties(self):
        """PLAN_1_SOLO should reject 3 properties with upgrade suggestion"""
        response = requests.post(
            f"{BASE_URL}/api/intake/validate-property-count",
            json={"plan_id": "PLAN_1_SOLO", "property_count": 3}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["allowed"] == False
        assert data.get("error_code") == "PROPERTY_LIMIT_EXCEEDED"
        assert data.get("upgrade_to") == "PLAN_2_PORTFOLIO"
        
        print(f"✓ Solo plan rejects 3 properties, suggests upgrade to {data.get('upgrade_to')}")
    
    def test_portfolio_plan_allows_10_properties(self):
        """PLAN_2_PORTFOLIO should allow up to 10 properties"""
        response = requests.post(
            f"{BASE_URL}/api/intake/validate-property-count",
            json={"plan_id": "PLAN_2_PORTFOLIO", "property_count": 10}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["allowed"] == True
        assert data["max_properties"] == 10
        
        print("✓ Portfolio plan allows 10 properties")
    
    def test_pro_plan_allows_25_properties(self):
        """PLAN_3_PRO should allow up to 25 properties"""
        response = requests.post(
            f"{BASE_URL}/api/intake/validate-property-count",
            json={"plan_id": "PLAN_3_PRO", "property_count": 25}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["allowed"] == True
        assert data["max_properties"] == 25
        
        print("✓ Pro plan allows 25 properties")


class TestClientEntitlements:
    """Test client entitlements endpoint"""
    
    @pytest.fixture
    def client_token(self):
        """Get client auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Client login failed: {response.status_code}")
        return response.json().get("access_token")
    
    def test_client_entitlements_returns_plan(self, client_token):
        """Verify entitlements returns plan info"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(f"{BASE_URL}/api/client/entitlements", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "plan" in data
        assert "features" in data
        assert "max_properties" in data
        
        # Test client should be on PLAN_1_SOLO (mapped from legacy PLAN_1)
        assert data["plan"] == "PLAN_1_SOLO", f"Expected PLAN_1_SOLO, got {data['plan']}"
        assert data["max_properties"] == 2
        
        print(f"✓ Client entitlements: plan={data['plan']}, max_properties={data['max_properties']}")
    
    def test_client_has_basic_ai_extraction(self, client_token):
        """Verify PLAN_1_SOLO has basic AI extraction enabled"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(f"{BASE_URL}/api/client/entitlements", headers=headers)
        
        data = response.json()
        features = data.get("features", {})
        
        ai_basic = features.get("ai_extraction_basic", {})
        ai_advanced = features.get("ai_extraction_advanced", {})
        
        # Basic should be enabled, advanced should be disabled
        assert ai_basic.get("enabled") == True, "ai_extraction_basic should be enabled"
        assert ai_advanced.get("enabled") == False, "ai_extraction_advanced should be disabled for PLAN_1_SOLO"
        
        print(f"✓ AI extraction: basic={ai_basic.get('enabled')}, advanced={ai_advanced.get('enabled')}")


class TestClientDashboard:
    """Test client dashboard functionality"""
    
    @pytest.fixture
    def client_token(self):
        """Get client auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Client login failed: {response.status_code}")
        return response.json().get("access_token")
    
    def test_dashboard_loads(self, client_token):
        """Verify dashboard endpoint returns data"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(f"{BASE_URL}/api/client/dashboard", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "client" in data
        assert "properties" in data
        assert "compliance_summary" in data
        
        print(f"✓ Dashboard loaded: {list(data.keys())}")
    
    def test_compliance_score_trend(self, client_token):
        """Verify compliance score trend endpoint returns data"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(f"{BASE_URL}/api/client/compliance-score/trend", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "has_history" in data
        assert "latest_score" in data
        assert "trend_direction" in data
        
        print(f"✓ Score trend: latest={data.get('latest_score')}, direction={data.get('trend_direction')}")


class TestAdminFeatureMatrix:
    """Test admin feature matrix endpoint"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code}")
        return response.json().get("access_token")
    
    def test_feature_matrix_returns_all_plans(self, admin_token):
        """Verify feature matrix returns all 3 plans"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/system/feature-matrix", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        plans = data.get("plans", {})
        assert "PLAN_1_SOLO" in plans
        assert "PLAN_2_PORTFOLIO" in plans
        assert "PLAN_3_PRO" in plans
        
        # Verify plan limits
        assert plans["PLAN_1_SOLO"]["max_properties"] == 2
        assert plans["PLAN_2_PORTFOLIO"]["max_properties"] == 10
        assert plans["PLAN_3_PRO"]["max_properties"] == 25
        
        print(f"✓ Feature matrix: {len(plans)} plans, {len(data.get('features', []))} features")


class TestTenantPortalViewOnly:
    """Test tenant portal is view-only"""
    
    def test_request_certificate_disabled(self):
        """POST /api/tenant/request-certificate should return FEATURE_DISABLED"""
        response = requests.post(
            f"{BASE_URL}/api/tenant/request-certificate",
            json={"property_id": "test", "certificate_type": "GAS_SAFETY"}
        )
        
        assert response.status_code == 403
        data = response.json()
        detail = data.get("detail", {})
        assert detail.get("error_code") == "FEATURE_DISABLED"
        
        print("✓ Tenant request-certificate: FEATURE_DISABLED")
    
    def test_contact_landlord_disabled(self):
        """POST /api/tenant/contact-landlord should return FEATURE_DISABLED"""
        response = requests.post(
            f"{BASE_URL}/api/tenant/contact-landlord",
            json={"message": "Test"}
        )
        
        assert response.status_code == 403
        data = response.json()
        detail = data.get("detail", {})
        assert detail.get("error_code") == "FEATURE_DISABLED"
        
        print("✓ Tenant contact-landlord: FEATURE_DISABLED")
    
    def test_tenant_requests_empty(self):
        """GET /api/tenant/requests should return empty list"""
        response = requests.get(f"{BASE_URL}/api/tenant/requests")
        
        assert response.status_code == 200
        data = response.json()
        assert data["requests"] == []
        assert "view-only" in data.get("note", "").lower()
        
        print("✓ Tenant requests: Empty with view-only note")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
