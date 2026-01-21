"""
Iteration 18 Tests - Dashboard Drilldowns, Compliance Score, AI Assistant, Plan Gating

Tests for:
1. Dashboard clickable tiles navigation
2. Compliance Score page with explanation
3. AI Assistant structured responses
4. Plan gating enforcement (webhooks blocked for PLAN_1)
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


class TestAuthAndSetup:
    """Authentication tests to get tokens for subsequent tests"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert response.status_code == 200, f"Client login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    def test_client_login(self, client_token):
        """Verify client can login"""
        assert client_token is not None
        assert len(client_token) > 0
        print(f"✓ Client login successful, token length: {len(client_token)}")
    
    def test_admin_login(self, admin_token):
        """Verify admin can login"""
        assert admin_token is not None
        assert len(admin_token) > 0
        print(f"✓ Admin login successful, token length: {len(admin_token)}")


class TestClientDashboard:
    """Test client dashboard endpoints that support drilldowns"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Client login failed")
        return response.json()["access_token"]
    
    def test_dashboard_endpoint(self, client_token):
        """Test GET /api/client/dashboard returns data for tiles"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(f"{BASE_URL}/api/client/dashboard", headers=headers)
        
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        data = response.json()
        
        # Verify compliance_summary exists for tiles
        assert "compliance_summary" in data, "Missing compliance_summary"
        summary = data["compliance_summary"]
        
        # Verify all tile data fields exist
        assert "total_requirements" in summary, "Missing total_requirements"
        assert "compliant" in summary, "Missing compliant count"
        assert "expiring_soon" in summary, "Missing expiring_soon count"
        assert "overdue" in summary, "Missing overdue count"
        
        print(f"✓ Dashboard data: total={summary['total_requirements']}, compliant={summary['compliant']}, expiring={summary['expiring_soon']}, overdue={summary['overdue']}")
    
    def test_compliance_score_endpoint(self, client_token):
        """Test GET /api/client/compliance-score returns score data"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(f"{BASE_URL}/api/client/compliance-score", headers=headers)
        
        assert response.status_code == 200, f"Compliance score failed: {response.text}"
        data = response.json()
        
        # Verify score fields
        assert "score" in data, "Missing score"
        assert "grade" in data, "Missing grade"
        assert "color" in data, "Missing color"
        assert "breakdown" in data, "Missing breakdown"
        
        # Verify breakdown has components for explanation
        breakdown = data["breakdown"]
        assert "status_score" in breakdown, "Missing status_score in breakdown"
        assert "expiry_score" in breakdown, "Missing expiry_score in breakdown"
        assert "document_score" in breakdown, "Missing document_score in breakdown"
        
        print(f"✓ Compliance score: {data['score']}/100, grade={data['grade']}, color={data['color']}")
    
    def test_requirements_endpoint(self, client_token):
        """Test GET /api/client/requirements returns requirements list"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(f"{BASE_URL}/api/client/requirements", headers=headers)
        
        assert response.status_code == 200, f"Requirements failed: {response.text}"
        data = response.json()
        
        assert "requirements" in data, "Missing requirements array"
        requirements = data["requirements"]
        
        if len(requirements) > 0:
            req = requirements[0]
            assert "requirement_id" in req, "Missing requirement_id"
            assert "status" in req, "Missing status"
            print(f"✓ Requirements endpoint: {len(requirements)} requirements found")
        else:
            print("✓ Requirements endpoint works (0 requirements)")


class TestPlanFeatures:
    """Test plan features endpoint for plan gating"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Client login failed")
        return response.json()["access_token"]
    
    def test_plan_features_endpoint(self, client_token):
        """Test GET /api/client/plan-features returns feature availability"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(f"{BASE_URL}/api/client/plan-features", headers=headers)
        
        assert response.status_code == 200, f"Plan features failed: {response.text}"
        data = response.json()
        
        # Verify plan info
        assert "plan" in data, "Missing plan"
        assert "plan_name" in data, "Missing plan_name"
        assert "features" in data, "Missing features"
        
        features = data["features"]
        # Verify key features are present
        assert "webhooks" in features, "Missing webhooks feature"
        assert "sms_reminders" in features, "Missing sms_reminders feature"
        assert "ai_assistant" in features, "Missing ai_assistant feature"
        
        print(f"✓ Plan features: plan={data['plan']}, name={data['plan_name']}")
        print(f"  Features: webhooks={features.get('webhooks')}, sms={features.get('sms_reminders')}, ai={features.get('ai_assistant')}")


class TestPlanGating:
    """Test plan gating enforcement - webhooks blocked for PLAN_1"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Client login failed")
        return response.json()["access_token"]
    
    def test_webhook_creation_blocked_for_plan_1(self, client_token):
        """Test POST /api/webhooks returns 403 PLAN_NOT_ELIGIBLE for PLAN_1 users"""
        headers = {"Authorization": f"Bearer {client_token}"}
        
        # Try to create a webhook
        webhook_data = {
            "name": "Test Webhook",
            "url": "https://example.com/webhook",
            "event_types": ["compliance.status_changed"]
        }
        
        response = requests.post(f"{BASE_URL}/api/webhooks", headers=headers, json=webhook_data)
        
        # Should be blocked with 403
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check for plan gating error
        detail = data.get("detail", "")
        assert "PLAN_NOT_ELIGIBLE" in detail or "plan" in detail.lower() or "upgrade" in detail.lower(), \
            f"Expected plan gating error, got: {detail}"
        
        print(f"✓ Webhook creation correctly blocked for PLAN_1: {detail}")


class TestAIAssistant:
    """Test AI Assistant endpoint with structured responses"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Client login failed")
        return response.json()["access_token"]
    
    def test_assistant_ask_endpoint(self, client_token):
        """Test POST /api/assistant/ask returns structured response"""
        headers = {"Authorization": f"Bearer {client_token}"}
        
        question_data = {
            "question": "What is my current compliance status?"
        }
        
        response = requests.post(f"{BASE_URL}/api/assistant/ask", headers=headers, json=question_data, timeout=60)
        
        assert response.status_code == 200, f"Assistant ask failed: {response.text}"
        data = response.json()
        
        # Verify structured response fields
        assert "answer" in data, "Missing answer field"
        assert "what_this_is_based_on" in data, "Missing what_this_is_based_on field"
        assert "next_actions" in data, "Missing next_actions field"
        
        # Verify types
        assert isinstance(data["answer"], str), "answer should be string"
        assert isinstance(data["what_this_is_based_on"], list), "what_this_is_based_on should be list"
        assert isinstance(data["next_actions"], list), "next_actions should be list"
        
        print(f"✓ AI Assistant response received:")
        print(f"  Answer length: {len(data['answer'])} chars")
        print(f"  Based on: {len(data['what_this_is_based_on'])} items")
        print(f"  Next actions: {len(data['next_actions'])} items")
    
    def test_assistant_refuses_action_requests(self, client_token):
        """Test that assistant refuses requests to modify data"""
        headers = {"Authorization": f"Bearer {client_token}"}
        
        question_data = {
            "question": "Please create a new property for me"
        }
        
        response = requests.post(f"{BASE_URL}/api/assistant/ask", headers=headers, json=question_data, timeout=60)
        
        assert response.status_code == 200, f"Assistant ask failed: {response.text}"
        data = response.json()
        
        # Should be refused
        assert data.get("refused") == True, "Expected refused=True for action request"
        print(f"✓ AI Assistant correctly refused action request: {data.get('refusal_reason', 'N/A')}")
    
    def test_assistant_empty_question_rejected(self, client_token):
        """Test that empty questions are rejected"""
        headers = {"Authorization": f"Bearer {client_token}"}
        
        question_data = {
            "question": ""
        }
        
        response = requests.post(f"{BASE_URL}/api/assistant/ask", headers=headers, json=question_data, timeout=30)
        
        # Should be 400 or 422 for validation error
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}: {response.text}"
        print(f"✓ Empty question correctly rejected with status {response.status_code}")


class TestPropertiesEndpoint:
    """Test properties endpoint for drilldown navigation"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Client login failed")
        return response.json()["access_token"]
    
    def test_properties_list_endpoint(self, client_token):
        """Test GET /api/properties returns properties list"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(f"{BASE_URL}/api/properties", headers=headers)
        
        assert response.status_code == 200, f"Properties failed: {response.text}"
        data = response.json()
        
        # Should have properties array
        assert "properties" in data, "Missing properties array"
        properties = data["properties"]
        
        if len(properties) > 0:
            prop = properties[0]
            assert "property_id" in prop, "Missing property_id"
            assert "compliance_status" in prop or "status" in prop, "Missing compliance status"
            print(f"✓ Properties endpoint: {len(properties)} properties found")
        else:
            print("✓ Properties endpoint works (0 properties)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
