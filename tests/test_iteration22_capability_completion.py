"""
Iteration 22 Tests - Capability Completion & Gating Build

Tests for:
1. Compliance Score Trending - GET /api/client/compliance-score/trend
2. Compliance Score Snapshot - POST /api/client/compliance-score/snapshot
3. Client Entitlements - GET /api/client/entitlements
4. Admin Feature Matrix - GET /api/admin/system/feature-matrix
5. iCal Calendar Export - GET /api/calendar/export.ics (plan-gated to PLAN_2_5+)
6. Branding Settings GET - GET /api/client/branding
7. Branding Settings PUT - PUT /api/client/branding (plan-gated to PLAN_6_15)
8. Professional PDF Report - GET /api/reports/professional/compliance-summary (plan-gated to PLAN_2_5+)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


class TestAuthentication:
    """Authentication tests for client and admin"""
    
    def test_client_login(self):
        """Test client login returns token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert response.status_code == 200, f"Client login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert "user" in data, "No user in response"
        print(f"✓ Client login successful - Plan: {data['user'].get('billing_plan', 'N/A')}")
    
    def test_admin_login(self):
        """Test admin login returns token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        print("✓ Admin login successful")


@pytest.fixture
def client_token():
    """Get client authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": CLIENT_EMAIL,
        "password": CLIENT_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Client authentication failed")


@pytest.fixture
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin authentication failed")


class TestComplianceScoreTrending:
    """Tests for Compliance Score Trending feature"""
    
    def test_get_score_trend_returns_sparkline_data(self, client_token):
        """GET /api/client/compliance-score/trend returns sparkline data"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(
            f"{BASE_URL}/api/client/compliance-score/trend?days=30",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "has_history" in data, "Missing has_history field"
        assert "sparkline" in data, "Missing sparkline field"
        assert "data_points" in data, "Missing data_points field"
        assert "trend_direction" in data, "Missing trend_direction field"
        
        # Sparkline should be a list
        assert isinstance(data["sparkline"], list), "sparkline should be a list"
        
        print(f"✓ Score trend returned - has_history: {data['has_history']}, points: {len(data['sparkline'])}")
    
    def test_score_trend_with_breakdown(self, client_token):
        """GET /api/client/compliance-score/trend with include_breakdown=true"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(
            f"{BASE_URL}/api/client/compliance-score/trend?days=30&include_breakdown=true",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify data_points structure
        if data.get("has_history") and data.get("data_points"):
            point = data["data_points"][0]
            assert "date" in point, "Missing date in data point"
            assert "score" in point, "Missing score in data point"
        
        print(f"✓ Score trend with breakdown returned - {len(data.get('data_points', []))} data points")
    
    def test_score_trend_unauthorized(self):
        """GET /api/client/compliance-score/trend without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/client/compliance-score/trend")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthorized access correctly rejected")


class TestComplianceScoreSnapshot:
    """Tests for Compliance Score Snapshot feature"""
    
    def test_create_snapshot(self, client_token):
        """POST /api/client/compliance-score/snapshot creates a snapshot"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.post(
            f"{BASE_URL}/api/client/compliance-score/snapshot",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "snapshot_id" in data, "Missing snapshot_id"
        assert "action" in data, "Missing action field"
        assert "score" in data, "Missing score field"
        assert data["action"] in ["created", "updated"], f"Unexpected action: {data['action']}"
        
        print(f"✓ Snapshot {data['action']} - ID: {data['snapshot_id']}, Score: {data['score']}")
    
    def test_snapshot_unauthorized(self):
        """POST /api/client/compliance-score/snapshot without auth returns 401"""
        response = requests.post(f"{BASE_URL}/api/client/compliance-score/snapshot")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthorized snapshot correctly rejected")


class TestClientEntitlements:
    """Tests for Client Entitlements feature"""
    
    def test_get_entitlements_returns_feature_matrix(self, client_token):
        """GET /api/client/entitlements returns full feature matrix"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(
            f"{BASE_URL}/api/client/entitlements",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "client_id" in data, "Missing client_id"
        assert "plan" in data, "Missing plan"
        assert "plan_name" in data, "Missing plan_name"
        assert "features" in data, "Missing features"
        assert "feature_summary" in data, "Missing feature_summary"
        assert "max_properties" in data, "Missing max_properties"
        
        # Verify features structure
        features = data["features"]
        assert isinstance(features, dict), "features should be a dict"
        
        # Check for expected feature keys
        expected_features = ["ai_basic", "bulk_upload", "reports_pdf", "calendar_sync", "white_label"]
        for feature in expected_features:
            assert feature in features, f"Missing feature: {feature}"
            assert "enabled" in features[feature], f"Missing enabled for {feature}"
            assert "name" in features[feature], f"Missing name for {feature}"
        
        # For PLAN_1, certain features should be disabled
        if data["plan"] == "PLAN_1":
            assert features["reports_pdf"]["enabled"] == False, "reports_pdf should be disabled for PLAN_1"
            assert features["calendar_sync"]["enabled"] == False, "calendar_sync should be disabled for PLAN_1"
            assert features["white_label"]["enabled"] == False, "white_label should be disabled for PLAN_1"
            print(f"✓ PLAN_1 entitlements verified - disabled features confirmed")
        
        print(f"✓ Entitlements returned - Plan: {data['plan_name']}, Features: {data['feature_summary']}")
    
    def test_entitlements_unauthorized(self):
        """GET /api/client/entitlements without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/client/entitlements")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthorized entitlements correctly rejected")


class TestAdminFeatureMatrix:
    """Tests for Admin Feature Matrix endpoint"""
    
    def test_get_feature_matrix(self, admin_token):
        """GET /api/admin/system/feature-matrix returns feature entitlements"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/system/feature-matrix",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "feature_matrix" in data, "Missing feature_matrix"
        assert "plans" in data, "Missing plans"
        assert "total_features" in data, "Missing total_features"
        assert "generated_at" in data, "Missing generated_at"
        
        # Verify plans structure
        plans = data["plans"]
        assert "PLAN_1" in plans, "Missing PLAN_1"
        assert "PLAN_2_5" in plans, "Missing PLAN_2_5"
        assert "PLAN_6_15" in plans, "Missing PLAN_6_15"
        
        # Verify feature matrix structure
        matrix = data["feature_matrix"]
        assert isinstance(matrix, dict), "feature_matrix should be a dict"
        
        # Check a specific feature
        if "calendar_sync" in matrix:
            feature = matrix["calendar_sync"]
            assert "name" in feature, "Missing name in feature"
            assert "plans" in feature, "Missing plans in feature"
            assert feature["plans"]["PLAN_1"] == False, "calendar_sync should be False for PLAN_1"
            assert feature["plans"]["PLAN_2_5"] == True, "calendar_sync should be True for PLAN_2_5"
        
        print(f"✓ Feature matrix returned - {data['total_features']} features across 3 plans")
    
    def test_feature_matrix_requires_admin(self, client_token):
        """GET /api/admin/system/feature-matrix requires admin role"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/system/feature-matrix",
            headers=headers
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("✓ Non-admin access correctly rejected")


class TestCalendarExport:
    """Tests for iCal Calendar Export (plan-gated to PLAN_2_5+)"""
    
    def test_ical_export_plan_gated_for_plan_1(self, client_token):
        """GET /api/calendar/export.ics returns 403 PLAN_NOT_ELIGIBLE for PLAN_1"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(
            f"{BASE_URL}/api/calendar/export.ics",
            headers=headers
        )
        
        # For PLAN_1, should return 403
        assert response.status_code == 403, f"Expected 403 for PLAN_1, got {response.status_code}"
        data = response.json()
        
        # Verify error structure
        detail = data.get("detail", {})
        assert detail.get("error_code") == "PLAN_NOT_ELIGIBLE", f"Expected PLAN_NOT_ELIGIBLE, got {detail.get('error_code')}"
        assert detail.get("feature") == "calendar_sync", f"Expected feature calendar_sync, got {detail.get('feature')}"
        assert detail.get("upgrade_required") == True, "upgrade_required should be True"
        
        print(f"✓ iCal export correctly gated for PLAN_1 - error_code: {detail.get('error_code')}")
    
    def test_ical_export_unauthorized(self):
        """GET /api/calendar/export.ics without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/calendar/export.ics")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthorized iCal export correctly rejected")


class TestBrandingSettings:
    """Tests for Branding Settings (white-label feature)"""
    
    def test_get_branding_returns_settings_with_upgrade_message(self, client_token):
        """GET /api/client/branding returns branding with upgrade message for PLAN_1"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(
            f"{BASE_URL}/api/client/branding",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "feature_enabled" in data, "Missing feature_enabled"
        assert "primary_color" in data, "Missing primary_color"
        assert "secondary_color" in data, "Missing secondary_color"
        
        # For PLAN_1, feature should be disabled with upgrade message
        if data.get("feature_enabled") == False:
            assert "upgrade_message" in data, "Missing upgrade_message for disabled feature"
            assert "upgrade_required" in data, "Missing upgrade_required"
            print(f"✓ Branding GET returned with upgrade message: {data.get('upgrade_message')}")
        else:
            print(f"✓ Branding GET returned - feature_enabled: {data['feature_enabled']}")
    
    def test_put_branding_rejected_for_plan_1(self, client_token):
        """PUT /api/client/branding rejected with PLAN_NOT_ELIGIBLE for PLAN_1"""
        headers = {
            "Authorization": f"Bearer {client_token}",
            "Content-Type": "application/json"
        }
        response = requests.put(
            f"{BASE_URL}/api/client/branding",
            headers=headers,
            json={
                "company_name": "Test Company",
                "primary_color": "#FF0000"
            }
        )
        
        # For PLAN_1, should return 403
        assert response.status_code == 403, f"Expected 403 for PLAN_1, got {response.status_code}"
        data = response.json()
        
        # Verify error structure
        detail = data.get("detail", {})
        assert detail.get("error_code") == "PLAN_NOT_ELIGIBLE", f"Expected PLAN_NOT_ELIGIBLE, got {detail.get('error_code')}"
        assert detail.get("feature") == "white_label", f"Expected feature white_label, got {detail.get('feature')}"
        assert detail.get("upgrade_required") == True, "upgrade_required should be True"
        
        print(f"✓ Branding PUT correctly rejected for PLAN_1 - error_code: {detail.get('error_code')}")
    
    def test_branding_unauthorized(self):
        """GET /api/client/branding without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/client/branding")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthorized branding access correctly rejected")


class TestProfessionalPDFReport:
    """Tests for Professional PDF Report (plan-gated to PLAN_2_5+)"""
    
    def test_professional_pdf_plan_gated_for_plan_1(self, client_token):
        """GET /api/reports/professional/compliance-summary returns 403 for PLAN_1"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(
            f"{BASE_URL}/api/reports/professional/compliance-summary",
            headers=headers
        )
        
        # For PLAN_1, should return 403
        assert response.status_code == 403, f"Expected 403 for PLAN_1, got {response.status_code}"
        data = response.json()
        
        # Verify error structure
        detail = data.get("detail", {})
        assert detail.get("error_code") == "PLAN_NOT_ELIGIBLE", f"Expected PLAN_NOT_ELIGIBLE, got {detail.get('error_code')}"
        assert detail.get("feature") == "reports_pdf", f"Expected feature reports_pdf, got {detail.get('feature')}"
        assert detail.get("upgrade_required") == True, "upgrade_required should be True"
        
        print(f"✓ Professional PDF correctly gated for PLAN_1 - error_code: {detail.get('error_code')}")
    
    def test_professional_pdf_unauthorized(self):
        """GET /api/reports/professional/compliance-summary without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/reports/professional/compliance-summary")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthorized professional PDF access correctly rejected")


class TestScoreExplanation:
    """Tests for Compliance Score Explanation endpoint"""
    
    def test_get_score_explanation(self, client_token):
        """GET /api/client/compliance-score/explanation returns explanation"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(
            f"{BASE_URL}/api/client/compliance-score/explanation?compare_days=7",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "has_comparison" in data, "Missing has_comparison"
        assert "explanation" in data, "Missing explanation"
        assert "changes" in data, "Missing changes"
        
        print(f"✓ Score explanation returned - has_comparison: {data['has_comparison']}")


class TestCalendarExpiries:
    """Tests for Calendar Expiries endpoint (not plan-gated)"""
    
    def test_get_calendar_expiries(self, client_token):
        """GET /api/calendar/expiries returns calendar data"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(
            f"{BASE_URL}/api/calendar/expiries?year=2026",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "year" in data, "Missing year"
        assert "events_by_date" in data, "Missing events_by_date"
        assert "summary" in data, "Missing summary"
        
        print(f"✓ Calendar expiries returned - {data['summary'].get('total_events', 0)} events")
    
    def test_get_upcoming_expiries(self, client_token):
        """GET /api/calendar/upcoming returns upcoming expiries"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(
            f"{BASE_URL}/api/calendar/upcoming?days=90",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "days_ahead" in data, "Missing days_ahead"
        assert "count" in data, "Missing count"
        assert "upcoming" in data, "Missing upcoming"
        
        print(f"✓ Upcoming expiries returned - {data['count']} items in next {data['days_ahead']} days")


class TestPlanFeatures:
    """Tests for Plan Features endpoint"""
    
    def test_get_plan_features(self, client_token):
        """GET /api/client/plan-features returns plan info"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(
            f"{BASE_URL}/api/client/plan-features",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "plan" in data, "Missing plan"
        assert "plan_name" in data, "Missing plan_name"
        
        print(f"✓ Plan features returned - Plan: {data.get('plan_name', 'N/A')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
