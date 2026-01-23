"""
Iteration 25 - Feature Gating Tests
Tests for feature gating on Reports, Integrations, and Branding pages
Verifies API entitlements endpoint returns correct feature availability
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://content-forge-411.preview.emergentagent.com')

# Test credentials
TEST_CLIENT_EMAIL = "test@pleerity.com"
TEST_CLIENT_PASSWORD = "TestClient123!"
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


class TestAuthentication:
    """Test authentication endpoints"""
    
    def test_client_login_success(self):
        """Test client login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_CLIENT_EMAIL, "password": TEST_CLIENT_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == TEST_CLIENT_EMAIL
        assert data["user"]["role"] == "ROLE_CLIENT_ADMIN"
        print(f"✓ Client login successful: {data['user']['email']}")
    
    def test_admin_login_success(self):
        """Test admin login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "ROLE_ADMIN"
        print(f"✓ Admin login successful: {data['user']['email']}")


class TestEntitlementsAPI:
    """Test /api/client/entitlements endpoint for feature gating"""
    
    @pytest.fixture
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_CLIENT_EMAIL, "password": TEST_CLIENT_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Client authentication failed")
    
    def test_entitlements_endpoint_returns_200(self, client_token):
        """Test entitlements endpoint returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/client/entitlements",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        print("✓ Entitlements endpoint returns 200")
    
    def test_entitlements_returns_plan_info(self, client_token):
        """Test entitlements returns plan information"""
        response = requests.get(
            f"{BASE_URL}/api/client/entitlements",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify plan info
        assert "plan" in data
        assert "plan_name" in data
        assert "max_properties" in data
        assert "features" in data
        
        print(f"✓ Plan: {data['plan']}")
        print(f"✓ Plan Name: {data['plan_name']}")
        print(f"✓ Max Properties: {data['max_properties']}")
    
    def test_entitlements_plan_is_solo(self, client_token):
        """Test that test client is on PLAN_1_SOLO"""
        response = requests.get(
            f"{BASE_URL}/api/client/entitlements",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Test client should be on PLAN_1_SOLO
        assert data["plan"] == "PLAN_1_SOLO", f"Expected PLAN_1_SOLO, got {data['plan']}"
        assert data["max_properties"] == 2, f"Expected max_properties=2, got {data['max_properties']}"
        print(f"✓ Test client is on PLAN_1_SOLO with max_properties=2")
    
    def test_reports_features_disabled_for_solo(self, client_token):
        """Test that reports features are disabled for PLAN_1_SOLO"""
        response = requests.get(
            f"{BASE_URL}/api/client/entitlements",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        features = data["features"]
        
        # Reports features should be disabled for PLAN_1_SOLO
        assert features["reports_pdf"]["enabled"] == False, "reports_pdf should be disabled"
        assert features["reports_csv"]["enabled"] == False, "reports_csv should be disabled"
        assert features["scheduled_reports"]["enabled"] == False, "scheduled_reports should be disabled"
        
        # Verify minimum plan requirement
        assert features["reports_pdf"]["minimum_plan"] == "PLAN_2_PORTFOLIO"
        assert features["reports_csv"]["minimum_plan"] == "PLAN_2_PORTFOLIO"
        assert features["scheduled_reports"]["minimum_plan"] == "PLAN_2_PORTFOLIO"
        
        print("✓ Reports features correctly disabled for PLAN_1_SOLO")
        print(f"  - reports_pdf: enabled={features['reports_pdf']['enabled']}, requires={features['reports_pdf']['minimum_plan']}")
        print(f"  - reports_csv: enabled={features['reports_csv']['enabled']}, requires={features['reports_csv']['minimum_plan']}")
        print(f"  - scheduled_reports: enabled={features['scheduled_reports']['enabled']}, requires={features['scheduled_reports']['minimum_plan']}")
    
    def test_webhooks_disabled_for_solo(self, client_token):
        """Test that webhooks feature is disabled for PLAN_1_SOLO"""
        response = requests.get(
            f"{BASE_URL}/api/client/entitlements",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        features = data["features"]
        
        # Webhooks should be disabled for PLAN_1_SOLO (requires PLAN_3_PRO)
        assert features["webhooks"]["enabled"] == False, "webhooks should be disabled"
        assert features["webhooks"]["minimum_plan"] == "PLAN_3_PRO"
        
        print("✓ Webhooks feature correctly disabled for PLAN_1_SOLO")
        print(f"  - webhooks: enabled={features['webhooks']['enabled']}, requires={features['webhooks']['minimum_plan']}")
    
    def test_white_label_disabled_for_solo(self, client_token):
        """Test that white-label features are disabled for PLAN_1_SOLO"""
        response = requests.get(
            f"{BASE_URL}/api/client/entitlements",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        features = data["features"]
        
        # White-label reports should be disabled for PLAN_1_SOLO (requires PLAN_3_PRO)
        assert features["white_label_reports"]["enabled"] == False, "white_label_reports should be disabled"
        assert features["white_label_reports"]["minimum_plan"] == "PLAN_3_PRO"
        
        print("✓ White-label features correctly disabled for PLAN_1_SOLO")
        print(f"  - white_label_reports: enabled={features['white_label_reports']['enabled']}, requires={features['white_label_reports']['minimum_plan']}")
    
    def test_core_features_enabled_for_solo(self, client_token):
        """Test that core features are enabled for PLAN_1_SOLO"""
        response = requests.get(
            f"{BASE_URL}/api/client/entitlements",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        features = data["features"]
        
        # Core features should be enabled for all plans
        assert features["compliance_dashboard"]["enabled"] == True
        assert features["compliance_score"]["enabled"] == True
        assert features["compliance_calendar"]["enabled"] == True
        assert features["email_notifications"]["enabled"] == True
        assert features["multi_file_upload"]["enabled"] == True
        assert features["score_trending"]["enabled"] == True
        assert features["ai_extraction_basic"]["enabled"] == True
        
        print("✓ Core features correctly enabled for PLAN_1_SOLO")
    
    def test_feature_summary_counts(self, client_token):
        """Test that feature summary counts are correct"""
        response = requests.get(
            f"{BASE_URL}/api/client/entitlements",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "feature_summary" in data
        summary = data["feature_summary"]
        
        assert "total" in summary
        assert "enabled" in summary
        assert "disabled" in summary
        
        # Verify counts add up
        assert summary["enabled"] + summary["disabled"] == summary["total"]
        
        print(f"✓ Feature summary: {summary['enabled']}/{summary['total']} enabled, {summary['disabled']} disabled")


class TestBrandingAPI:
    """Test /api/client/branding endpoint for feature gating"""
    
    @pytest.fixture
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_CLIENT_EMAIL, "password": TEST_CLIENT_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Client authentication failed")
    
    def test_branding_get_returns_200(self, client_token):
        """Test GET /api/client/branding returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/client/branding",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        print("✓ GET /api/client/branding returns 200")
    
    def test_branding_returns_feature_enabled_flag(self, client_token):
        """Test branding endpoint returns feature_enabled flag"""
        response = requests.get(
            f"{BASE_URL}/api/client/branding",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "feature_enabled" in data
        # For PLAN_1_SOLO, white_label should be disabled
        assert data["feature_enabled"] == False, "feature_enabled should be False for PLAN_1_SOLO"
        
        print(f"✓ Branding feature_enabled={data['feature_enabled']} (correctly disabled for PLAN_1_SOLO)")
    
    def test_branding_returns_upgrade_message(self, client_token):
        """Test branding endpoint returns upgrade message when locked"""
        response = requests.get(
            f"{BASE_URL}/api/client/branding",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should have upgrade info when feature is disabled
        if not data.get("feature_enabled"):
            assert "upgrade_message" in data or "upgrade_required" in data
            print(f"✓ Branding returns upgrade info when locked")
    
    def test_branding_put_returns_403_for_solo(self, client_token):
        """Test PUT /api/client/branding returns 403 for PLAN_1_SOLO"""
        response = requests.put(
            f"{BASE_URL}/api/client/branding",
            headers={"Authorization": f"Bearer {client_token}"},
            json={"company_name": "Test Company"}
        )
        # Should return 403 Forbidden for PLAN_1_SOLO
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        
        data = response.json()
        assert "detail" in data
        
        print(f"✓ PUT /api/client/branding correctly returns 403 for PLAN_1_SOLO")


class TestDashboardAPI:
    """Test dashboard and navigation APIs"""
    
    @pytest.fixture
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_CLIENT_EMAIL, "password": TEST_CLIENT_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Client authentication failed")
    
    def test_dashboard_returns_200(self, client_token):
        """Test GET /api/client/dashboard returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/client/dashboard",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "client" in data
        assert "properties" in data
        assert "compliance_summary" in data
        
        print(f"✓ Dashboard API returns 200 with client data")
    
    def test_properties_returns_200(self, client_token):
        """Test GET /api/client/properties returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/client/properties",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "properties" in data
        print(f"✓ Properties API returns 200 with {len(data['properties'])} properties")
    
    def test_compliance_score_returns_200(self, client_token):
        """Test GET /api/client/compliance-score returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/client/compliance-score",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "score" in data or "overall_score" in data
        print(f"✓ Compliance score API returns 200")


class TestReportsAPI:
    """Test reports API endpoints"""
    
    @pytest.fixture
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_CLIENT_EMAIL, "password": TEST_CLIENT_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Client authentication failed")
    
    def test_available_reports_returns_200(self, client_token):
        """Test GET /api/reports/available returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/reports/available",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "reports" in data
        print(f"✓ Available reports API returns 200 with {len(data['reports'])} reports")
    
    def test_report_schedules_returns_200(self, client_token):
        """Test GET /api/reports/schedules returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/reports/schedules",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "schedules" in data
        print(f"✓ Report schedules API returns 200")


class TestWebhooksAPI:
    """Test webhooks API endpoints"""
    
    @pytest.fixture
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_CLIENT_EMAIL, "password": TEST_CLIENT_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Client authentication failed")
    
    def test_webhooks_list_returns_200(self, client_token):
        """Test GET /api/webhooks returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/webhooks",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        # May return 200 with empty list or 403 if feature gated at API level
        assert response.status_code in [200, 403]
        print(f"✓ Webhooks list API returns {response.status_code}")
    
    def test_webhooks_events_returns_200(self, client_token):
        """Test GET /api/webhooks/events returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/webhooks/events",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code in [200, 403]
        print(f"✓ Webhooks events API returns {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
