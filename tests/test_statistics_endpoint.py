"""
Statistics Endpoint Test Suite - Compliance Vault Pro
Tests the /api/admin/statistics endpoint for the Statistics Dashboard.
"""
import pytest
import requests
import os

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://paperwork-assist-1.preview.emergentagent.com').rstrip('/')

# Admin credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


class TestStatisticsEndpoint:
    """Statistics endpoint tests for Admin Dashboard"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Admin authentication failed")
    
    def test_statistics_endpoint_returns_200(self):
        """Test /api/admin/statistics returns 200 OK"""
        response = requests.get(
            f"{BASE_URL}/api/admin/statistics",
            headers=self.headers
        )
        assert response.status_code == 200, f"Statistics endpoint failed: {response.text}"
        print("✅ Statistics endpoint returns 200 OK")
    
    def test_statistics_response_structure(self):
        """Test /api/admin/statistics returns correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/admin/statistics",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify top-level keys
        assert "generated_at" in data
        assert "clients" in data
        assert "properties" in data
        assert "requirements" in data
        assert "documents" in data
        assert "emails" in data
        assert "rules" in data
        
        print("✅ Statistics response has correct top-level structure")
    
    def test_statistics_clients_data(self):
        """Test clients section of statistics"""
        response = requests.get(
            f"{BASE_URL}/api/admin/statistics",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        clients = data["clients"]
        assert "total" in clients
        assert "by_subscription_status" in clients
        assert "by_onboarding_status" in clients
        assert "new_last_7_days" in clients
        assert "new_last_30_days" in clients
        assert "new_last_90_days" in clients
        
        # Verify subscription status breakdown
        sub_status = clients["by_subscription_status"]
        assert "ACTIVE" in sub_status
        assert "PENDING" in sub_status
        assert "CANCELLED" in sub_status
        assert "SUSPENDED" in sub_status
        
        # Verify onboarding status breakdown
        onb_status = clients["by_onboarding_status"]
        assert "PROVISIONED" in onb_status
        assert "PENDING_PAYMENT" in onb_status
        assert "INTAKE_COMPLETE" in onb_status
        assert "FAILED" in onb_status
        
        print(f"✅ Clients data: {clients['total']} total clients")
    
    def test_statistics_properties_data(self):
        """Test properties section of statistics"""
        response = requests.get(
            f"{BASE_URL}/api/admin/statistics",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        properties = data["properties"]
        assert "total" in properties
        assert "by_type" in properties
        assert "by_compliance_status" in properties
        
        # Verify compliance status breakdown exists
        compliance = properties["by_compliance_status"]
        # These may or may not exist depending on data
        assert isinstance(compliance, dict)
        
        print(f"✅ Properties data: {properties['total']} total properties")
    
    def test_statistics_requirements_data(self):
        """Test requirements section of statistics"""
        response = requests.get(
            f"{BASE_URL}/api/admin/statistics",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        requirements = data["requirements"]
        assert "total" in requirements
        assert "by_status" in requirements
        assert "by_type" in requirements
        assert "expiring_next_30_days" in requirements
        assert "expiring_next_60_days" in requirements
        assert "expiring_next_90_days" in requirements
        assert "overdue" in requirements
        assert "compliance_rate_percent" in requirements
        
        # Verify compliance rate is a number between 0 and 100
        rate = requirements["compliance_rate_percent"]
        assert isinstance(rate, (int, float))
        assert 0 <= rate <= 100
        
        print(f"✅ Requirements data: {requirements['total']} total, {rate}% compliance rate")
    
    def test_statistics_documents_data(self):
        """Test documents section of statistics"""
        response = requests.get(
            f"{BASE_URL}/api/admin/statistics",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        documents = data["documents"]
        assert "total" in documents
        assert "by_status" in documents
        assert "ai_analyzed" in documents
        
        print(f"✅ Documents data: {documents['total']} total, {documents['ai_analyzed']} AI analyzed")
    
    def test_statistics_emails_data(self):
        """Test emails section of statistics"""
        response = requests.get(
            f"{BASE_URL}/api/admin/statistics",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        emails = data["emails"]
        assert "total" in emails
        assert "sent" in emails
        assert "failed" in emails
        assert "delivery_rate" in emails
        
        # Verify delivery rate is a number
        rate = emails["delivery_rate"]
        assert isinstance(rate, (int, float))
        
        print(f"✅ Emails data: {emails['total']} total, {rate}% delivery rate")
    
    def test_statistics_rules_data(self):
        """Test rules section of statistics"""
        response = requests.get(
            f"{BASE_URL}/api/admin/statistics",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        rules = data["rules"]
        assert "total" in rules
        assert "active" in rules
        
        print(f"✅ Rules data: {rules['total']} total, {rules['active']} active")
    
    def test_statistics_without_auth(self):
        """Test /api/admin/statistics without auth returns 401/403"""
        response = requests.get(f"{BASE_URL}/api/admin/statistics")
        assert response.status_code in [401, 403]
        print("✅ Statistics endpoint correctly requires authentication")
    
    def test_statistics_with_invalid_token(self):
        """Test /api/admin/statistics with invalid token returns 401/403"""
        response = requests.get(
            f"{BASE_URL}/api/admin/statistics",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        assert response.status_code in [401, 403]
        print("✅ Statistics endpoint correctly rejects invalid token")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
