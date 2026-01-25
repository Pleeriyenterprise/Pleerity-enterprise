"""
Iteration 17 Tests: Admin Assistant Feature with CRN Lookup
Tests for:
1. GET /api/admin/client-lookup?crn=... - CRN lookup endpoint
2. POST /api/admin/assistant/ask - AI assistant endpoint
3. Audit logging for ADMIN_CRN_LOOKUP and ADMIN_ASSISTANT_QUERY
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://paperwork-assist-1.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"
TEST_CRN = "PLE-CVP-2026-07354"


class TestAdminAssistantFeature:
    """Tests for Admin Assistant CRN Lookup and AI Chat"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get admin auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.admin_token = token
        else:
            pytest.skip(f"Admin login failed: {login_response.status_code} - {login_response.text}")
    
    # ============================================================================
    # CRN Lookup Endpoint Tests
    # ============================================================================
    
    def test_crn_lookup_success(self):
        """Test GET /api/admin/client-lookup with valid CRN returns client snapshot"""
        response = self.session.get(f"{BASE_URL}/api/admin/client-lookup?crn={TEST_CRN}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify client data is returned
        assert "client" in data, "Response should contain 'client' field"
        assert data["client"] is not None, "Client should not be null"
        assert data["client"].get("customer_reference") == TEST_CRN, f"CRN should match: {data['client'].get('customer_reference')}"
        
        # Verify properties are returned
        assert "properties" in data, "Response should contain 'properties' field"
        assert isinstance(data["properties"], list), "Properties should be a list"
        
        # Verify requirements are returned
        assert "requirements" in data, "Response should contain 'requirements' field"
        assert isinstance(data["requirements"], list), "Requirements should be a list"
        
        # Verify compliance_summary is returned
        assert "compliance_summary" in data, "Response should contain 'compliance_summary' field"
        summary = data["compliance_summary"]
        assert "total_requirements" in summary, "Compliance summary should have total_requirements"
        assert "compliant" in summary, "Compliance summary should have compliant count"
        assert "overdue" in summary, "Compliance summary should have overdue count"
        assert "expiring_soon" in summary, "Compliance summary should have expiring_soon count"
        assert "compliance_percentage" in summary, "Compliance summary should have compliance_percentage"
        
        # Verify property_count and document_count
        assert "property_count" in data, "Response should contain 'property_count'"
        assert "document_count" in data, "Response should contain 'document_count'"
        
        print(f"✓ CRN Lookup Success: Found client {data['client'].get('full_name')} with {data['property_count']} properties")
    
    def test_crn_lookup_not_found(self):
        """Test GET /api/admin/client-lookup with invalid CRN returns 404"""
        invalid_crn = "PLE-CVP-9999-99999"
        response = self.session.get(f"{BASE_URL}/api/admin/client-lookup?crn={invalid_crn}")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data, "Error response should have 'detail' field"
        assert invalid_crn in data["detail"], "Error message should mention the CRN"
        
        print(f"✓ CRN Lookup 404: Correctly returned not found for invalid CRN")
    
    def test_crn_lookup_missing_crn(self):
        """Test GET /api/admin/client-lookup without CRN returns 400"""
        response = self.session.get(f"{BASE_URL}/api/admin/client-lookup")
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        print(f"✓ CRN Lookup 400: Correctly returned bad request for missing CRN")
    
    def test_crn_lookup_short_crn(self):
        """Test GET /api/admin/client-lookup with too short CRN returns 400"""
        response = self.session.get(f"{BASE_URL}/api/admin/client-lookup?crn=ABC")
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        print(f"✓ CRN Lookup 400: Correctly returned bad request for short CRN")
    
    def test_crn_lookup_requires_admin(self):
        """Test GET /api/admin/client-lookup requires admin authentication"""
        # Create new session without auth
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        response = no_auth_session.get(f"{BASE_URL}/api/admin/client-lookup?crn={TEST_CRN}")
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}: {response.text}"
        
        print(f"✓ CRN Lookup Auth: Correctly requires admin authentication")
    
    # ============================================================================
    # Admin Assistant Ask Endpoint Tests
    # ============================================================================
    
    def test_assistant_ask_success(self):
        """Test POST /api/admin/assistant/ask with valid CRN and question"""
        response = self.session.post(f"{BASE_URL}/api/admin/assistant/ask", json={
            "crn": TEST_CRN,
            "question": "What is the overall compliance status?"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "crn" in data, "Response should contain 'crn'"
        assert data["crn"] == TEST_CRN, f"CRN should match: {data['crn']}"
        
        assert "client_name" in data, "Response should contain 'client_name'"
        assert data["client_name"] is not None, "Client name should not be null"
        
        assert "question" in data, "Response should contain 'question'"
        assert "answer" in data, "Response should contain 'answer'"
        assert len(data["answer"]) > 0, "Answer should not be empty"
        
        assert "compliance_summary" in data, "Response should contain 'compliance_summary'"
        assert "properties_count" in data, "Response should contain 'properties_count'"
        
        print(f"✓ Assistant Ask Success: Got AI response for client {data['client_name']}")
        print(f"  Answer preview: {data['answer'][:200]}...")
    
    def test_assistant_ask_invalid_crn(self):
        """Test POST /api/admin/assistant/ask with invalid CRN returns 404"""
        response = self.session.post(f"{BASE_URL}/api/admin/assistant/ask", json={
            "crn": "PLE-CVP-9999-99999",
            "question": "What is the compliance status?"
        })
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        
        print(f"✓ Assistant Ask 404: Correctly returned not found for invalid CRN")
    
    def test_assistant_ask_missing_crn(self):
        """Test POST /api/admin/assistant/ask without CRN returns 400"""
        response = self.session.post(f"{BASE_URL}/api/admin/assistant/ask", json={
            "question": "What is the compliance status?"
        })
        
        # Should return 400 or 422 for validation error
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}: {response.text}"
        
        print(f"✓ Assistant Ask 400: Correctly returned bad request for missing CRN")
    
    def test_assistant_ask_empty_question(self):
        """Test POST /api/admin/assistant/ask with empty question returns 400"""
        response = self.session.post(f"{BASE_URL}/api/admin/assistant/ask", json={
            "crn": TEST_CRN,
            "question": ""
        })
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        print(f"✓ Assistant Ask 400: Correctly returned bad request for empty question")
    
    def test_assistant_ask_long_question(self):
        """Test POST /api/admin/assistant/ask with too long question returns 400"""
        long_question = "A" * 1001  # Over 1000 char limit
        response = self.session.post(f"{BASE_URL}/api/admin/assistant/ask", json={
            "crn": TEST_CRN,
            "question": long_question
        })
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        
        print(f"✓ Assistant Ask 400: Correctly returned bad request for too long question")
    
    def test_assistant_ask_requires_admin(self):
        """Test POST /api/admin/assistant/ask requires admin authentication"""
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        response = no_auth_session.post(f"{BASE_URL}/api/admin/assistant/ask", json={
            "crn": TEST_CRN,
            "question": "What is the compliance status?"
        })
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}: {response.text}"
        
        print(f"✓ Assistant Ask Auth: Correctly requires admin authentication")
    
    # ============================================================================
    # Audit Logging Tests
    # ============================================================================
    
    def test_audit_log_crn_lookup(self):
        """Test that CRN lookup creates ADMIN_CRN_LOOKUP audit log"""
        # First do a CRN lookup
        self.session.get(f"{BASE_URL}/api/admin/client-lookup?crn={TEST_CRN}")
        
        # Wait a moment for audit log to be written
        time.sleep(0.5)
        
        # Check audit logs for ADMIN_CRN_LOOKUP
        response = self.session.get(f"{BASE_URL}/api/admin/audit-logs?action=ADMIN_CRN_LOOKUP&limit=5")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "logs" in data, "Response should contain 'logs'"
        
        # Find a log entry for our CRN
        found_log = False
        for log in data["logs"]:
            if log.get("action") == "ADMIN_CRN_LOOKUP":
                metadata = log.get("metadata", {})
                if metadata.get("crn") == TEST_CRN:
                    found_log = True
                    assert metadata.get("found") == True, "Log should indicate client was found"
                    break
        
        assert found_log, f"Should find ADMIN_CRN_LOOKUP audit log for CRN {TEST_CRN}"
        
        print(f"✓ Audit Log: ADMIN_CRN_LOOKUP correctly logged")
    
    def test_audit_log_assistant_query(self):
        """Test that assistant query creates ADMIN_ASSISTANT_QUERY audit log"""
        test_question = "Test audit log question"
        
        # First do an assistant query
        self.session.post(f"{BASE_URL}/api/admin/assistant/ask", json={
            "crn": TEST_CRN,
            "question": test_question
        })
        
        # Wait a moment for audit log to be written
        time.sleep(0.5)
        
        # Check audit logs for ADMIN_ASSISTANT_QUERY
        response = self.session.get(f"{BASE_URL}/api/admin/audit-logs?action=ADMIN_ASSISTANT_QUERY&limit=5")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "logs" in data, "Response should contain 'logs'"
        
        # Find a log entry for our query
        found_log = False
        for log in data["logs"]:
            if log.get("action") == "ADMIN_ASSISTANT_QUERY":
                metadata = log.get("metadata", {})
                if metadata.get("crn") == TEST_CRN and test_question in metadata.get("question", ""):
                    found_log = True
                    assert "answer_preview" in metadata, "Log should contain answer preview"
                    assert metadata.get("model") == "gemini-2.5-flash", "Log should indicate model used"
                    break
        
        assert found_log, f"Should find ADMIN_ASSISTANT_QUERY audit log for CRN {TEST_CRN}"
        
        print(f"✓ Audit Log: ADMIN_ASSISTANT_QUERY correctly logged")
    
    # ============================================================================
    # Integration Tests
    # ============================================================================
    
    def test_assistant_different_questions(self):
        """Test assistant with different types of questions"""
        questions = [
            "Which properties have overdue requirements?",
            "What documents are expiring soon?",
            "Summarize this client's portfolio"
        ]
        
        for question in questions:
            response = self.session.post(f"{BASE_URL}/api/admin/assistant/ask", json={
                "crn": TEST_CRN,
                "question": question
            })
            
            assert response.status_code == 200, f"Expected 200 for question '{question}', got {response.status_code}"
            
            data = response.json()
            assert len(data.get("answer", "")) > 0, f"Should get non-empty answer for '{question}'"
            
            print(f"✓ Question '{question[:40]}...' answered successfully")
            
            # Small delay to avoid rate limiting
            time.sleep(1)


class TestAdminAssistantPageNavigation:
    """Tests for Admin Assistant page navigation from Admin Dashboard"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get admin auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Admin login failed: {login_response.status_code}")
    
    def test_admin_dashboard_accessible(self):
        """Test that admin dashboard endpoint is accessible"""
        response = self.session.get(f"{BASE_URL}/api/admin/dashboard")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "stats" in data, "Dashboard should return stats"
        
        print(f"✓ Admin Dashboard accessible")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
