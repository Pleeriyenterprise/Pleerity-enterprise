"""
Test Iteration 6 Features:
- Compliance Score API /api/client/compliance-score - returns score 0-100 with grade and breakdown
- SMS Status API /api/sms/status - returns configured status
- OTP API POST /api/otp/send, POST /api/otp/verify (single enterprise OTP surface; legacy /api/sms/send-otp, verify-otp removed)
- NotificationPreferencesPage SMS section with Beta badge
- After phone verification, SMS section shows Verified badge
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://order-fulfillment-9.preview.emergentagent.com').rstrip('/')

# Test credentials
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"
TEST_PHONE = "+447999888777"  # Different phone for testing


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def client_auth_token(api_client):
    """Get client authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": CLIENT_EMAIL,
        "password": CLIENT_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Client authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def authenticated_client(api_client, client_auth_token):
    """Session with client auth header"""
    api_client.headers.update({"Authorization": f"Bearer {client_auth_token}"})
    return api_client


class TestComplianceScoreAPI:
    """Test /api/client/compliance-score endpoint"""
    
    def test_compliance_score_returns_200(self, authenticated_client):
        """Test that compliance score endpoint returns 200"""
        response = authenticated_client.get(f"{BASE_URL}/api/client/compliance-score")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
    def test_compliance_score_has_score_0_to_100(self, authenticated_client):
        """Test that score is between 0 and 100"""
        response = authenticated_client.get(f"{BASE_URL}/api/client/compliance-score")
        assert response.status_code == 200
        
        data = response.json()
        assert "score" in data, "Response should contain 'score'"
        assert isinstance(data["score"], (int, float)), "Score should be a number"
        assert 0 <= data["score"] <= 100, f"Score should be 0-100, got {data['score']}"
        
    def test_compliance_score_has_grade(self, authenticated_client):
        """Test that response includes grade (A-F)"""
        response = authenticated_client.get(f"{BASE_URL}/api/client/compliance-score")
        assert response.status_code == 200
        
        data = response.json()
        assert "grade" in data, "Response should contain 'grade'"
        assert data["grade"] in ["A", "B", "C", "D", "F", "?"], f"Invalid grade: {data['grade']}"
        
    def test_compliance_score_has_color(self, authenticated_client):
        """Test that response includes color indicator"""
        response = authenticated_client.get(f"{BASE_URL}/api/client/compliance-score")
        assert response.status_code == 200
        
        data = response.json()
        assert "color" in data, "Response should contain 'color'"
        assert data["color"] in ["green", "amber", "red", "gray"], f"Invalid color: {data['color']}"
        
    def test_compliance_score_has_breakdown(self, authenticated_client):
        """Test that response includes score breakdown"""
        response = authenticated_client.get(f"{BASE_URL}/api/client/compliance-score")
        assert response.status_code == 200
        
        data = response.json()
        assert "breakdown" in data, "Response should contain 'breakdown'"
        
        breakdown = data["breakdown"]
        if breakdown:  # May be empty if no properties
            expected_keys = ["status_score", "expiry_score", "document_score", "overdue_penalty_score"]
            for key in expected_keys:
                assert key in breakdown, f"Breakdown should contain '{key}'"
                
    def test_compliance_score_has_recommendations(self, authenticated_client):
        """Test that response includes recommendations"""
        response = authenticated_client.get(f"{BASE_URL}/api/client/compliance-score")
        assert response.status_code == 200
        
        data = response.json()
        assert "recommendations" in data, "Response should contain 'recommendations'"
        assert isinstance(data["recommendations"], list), "Recommendations should be a list"
        
        # Check recommendation structure if any exist
        for rec in data["recommendations"]:
            assert "priority" in rec, "Recommendation should have 'priority'"
            assert "action" in rec, "Recommendation should have 'action'"
            assert "impact" in rec, "Recommendation should have 'impact'"
            assert rec["priority"] in ["high", "medium", "low"], f"Invalid priority: {rec['priority']}"
            
    def test_compliance_score_has_stats(self, authenticated_client):
        """Test that response includes stats"""
        response = authenticated_client.get(f"{BASE_URL}/api/client/compliance-score")
        assert response.status_code == 200
        
        data = response.json()
        assert "stats" in data, "Response should contain 'stats'"
        
        stats = data.get("stats", {})
        if stats:
            expected_keys = ["total_requirements", "compliant", "pending", "expiring_soon", "overdue"]
            for key in expected_keys:
                assert key in stats, f"Stats should contain '{key}'"


class TestSMSStatusAPI:
    """Test /api/sms/status endpoint"""
    
    def test_sms_status_returns_200(self, api_client):
        """Test that SMS status endpoint returns 200 (no auth required)"""
        response = api_client.get(f"{BASE_URL}/api/sms/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
    def test_sms_status_structure(self, api_client):
        """Test SMS status response structure"""
        response = api_client.get(f"{BASE_URL}/api/sms/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "enabled" in data, "Response should contain 'enabled'"
        assert "configured" in data, "Response should contain 'configured'"
        assert "feature_flag" in data, "Response should contain 'feature_flag'"
        
        # All should be boolean
        assert isinstance(data["enabled"], bool), "'enabled' should be boolean"
        assert isinstance(data["configured"], bool), "'configured' should be boolean"
        assert isinstance(data["feature_flag"], bool), "'feature_flag' should be boolean"


class TestSendOTPAPI:
    """Test POST /api/otp/send (canonical OTP API)"""
    
    def test_send_otp_returns_200_with_ok(self, api_client):
        """Send OTP returns 200 with ok=true and generic message (no auth required for send)."""
        response = api_client.post(f"{BASE_URL}/api/otp/send", json={
            "phone_number": TEST_PHONE,
            "action": "verify_phone",
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("ok") is True, "Should return ok=true"
        assert "message" in data, "Should return generic message"

    def test_send_otp_validates_phone_format(self, api_client):
        """Send OTP with invalid phone format returns 422."""
        response = api_client.post(f"{BASE_URL}/api/otp/send", json={
            "phone_number": "123",
            "action": "verify_phone",
        })
        assert response.status_code == 422, f"Expected 422 for invalid phone, got {response.status_code}"


class TestVerifyOTPAPI:
    """Test POST /api/otp/verify (canonical OTP API)"""
    
    def test_verify_otp_wrong_code_returns_400(self, api_client):
        """Verify with wrong or expired code returns 400."""
        response = api_client.post(f"{BASE_URL}/api/otp/verify", json={
            "phone_number": TEST_PHONE,
            "action": "verify_phone",
            "code": "000000",
        })
        assert response.status_code == 400, f"Expected 400 for wrong code, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data

    def test_verify_otp_invalid_code_format_returns_422(self, api_client):
        """Verify with non-6-digit code returns 422."""
        response = api_client.post(f"{BASE_URL}/api/otp/verify", json={
            "phone_number": TEST_PHONE,
            "action": "verify_phone",
            "code": "12",
        })
        assert response.status_code == 422, f"Expected 422 for invalid code format, got {response.status_code}"


class TestHealthAndAuth:
    """Basic health and authentication tests"""
    
    def test_health_endpoint(self, api_client):
        """Test health endpoint"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        
    def test_client_login(self, api_client):
        """Test client login works"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
