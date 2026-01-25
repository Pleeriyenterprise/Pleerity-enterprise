"""
ClearForm Admin and Pricing Features Tests - Iteration 61

Tests for:
- ClearForm admin endpoints (stats, users, documents)
- Pricing page data validation
- ClearForm vault and credits pages
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestClearFormAdminEndpoints:
    """Test ClearForm admin API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup admin authentication"""
        # Login as admin
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@pleerity.com", "password": "Admin123!"}
        )
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        self.admin_token = response.json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
    
    def test_clearform_admin_stats(self):
        """Test GET /api/admin/clearform/stats - returns ClearForm statistics"""
        response = requests.get(
            f"{BASE_URL}/api/admin/clearform/stats",
            headers=self.admin_headers
        )
        assert response.status_code == 200, f"Stats endpoint failed: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "total_users" in data, "Missing total_users in stats"
        assert "active_users" in data, "Missing active_users in stats"
        assert "total_documents" in data, "Missing total_documents in stats"
        assert "total_credits_used" in data, "Missing total_credits_used in stats"
        
        # Verify data types
        assert isinstance(data["total_users"], int)
        assert isinstance(data["active_users"], int)
        assert isinstance(data["total_documents"], int)
        assert isinstance(data["total_credits_used"], int)
        
        print(f"✅ ClearForm stats: {data}")
    
    def test_clearform_admin_users(self):
        """Test GET /api/admin/clearform/users - returns ClearForm users list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/clearform/users",
            headers=self.admin_headers
        )
        assert response.status_code == 200, f"Users endpoint failed: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "users" in data, "Missing users array"
        assert "total" in data, "Missing total count"
        assert "page" in data, "Missing page number"
        assert "page_size" in data, "Missing page_size"
        
        # Verify users have required fields
        if data["users"]:
            user = data["users"][0]
            assert "user_id" in user, "Missing user_id"
            assert "email" in user, "Missing email"
            assert "full_name" in user, "Missing full_name"
            assert "status" in user, "Missing status"
            assert "credit_balance" in user, "Missing credit_balance"
            assert "created_at" in user, "Missing created_at"
        
        print(f"✅ ClearForm users: {data['total']} total users")
    
    def test_clearform_admin_documents(self):
        """Test GET /api/admin/clearform/documents - returns ClearForm documents list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/clearform/documents",
            headers=self.admin_headers
        )
        assert response.status_code == 200, f"Documents endpoint failed: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "documents" in data, "Missing documents array"
        assert "total" in data, "Missing total count"
        assert "page" in data, "Missing page number"
        
        # Verify documents have required fields
        if data["documents"]:
            doc = data["documents"][0]
            assert "document_id" in doc, "Missing document_id"
            assert "user_id" in doc, "Missing user_id"
            assert "document_type" in doc, "Missing document_type"
            assert "title" in doc, "Missing title"
            assert "status" in doc, "Missing status"
            assert "credits_used" in doc, "Missing credits_used"
            assert "created_at" in doc, "Missing created_at"
            assert "user_email" in doc, "Missing user_email"
        
        print(f"✅ ClearForm documents: {data['total']} total documents")
    
    def test_clearform_admin_requires_auth(self):
        """Test that admin endpoints require authentication"""
        # Test without auth header
        response = requests.get(f"{BASE_URL}/api/admin/clearform/stats")
        assert response.status_code == 401, "Stats should require auth"
        
        response = requests.get(f"{BASE_URL}/api/admin/clearform/users")
        assert response.status_code == 401, "Users should require auth"
        
        response = requests.get(f"{BASE_URL}/api/admin/clearform/documents")
        assert response.status_code == 401, "Documents should require auth"
        
        print("✅ Admin endpoints properly require authentication")


class TestClearFormUserEndpoints:
    """Test ClearForm user-facing endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup ClearForm user authentication"""
        # Login as ClearForm user
        response = requests.post(
            f"{BASE_URL}/api/clearform/auth/login",
            json={"email": "doctest@clearform.com", "password": "Test123!"}
        )
        assert response.status_code == 200, f"ClearForm login failed: {response.text}"
        self.user_token = response.json()["access_token"]
        self.user_headers = {"Authorization": f"Bearer {self.user_token}"}
        self.user_data = response.json()["user"]
    
    def test_clearform_vault_endpoint(self):
        """Test GET /api/clearform/documents/vault - returns user's documents"""
        response = requests.get(
            f"{BASE_URL}/api/clearform/documents/vault",
            headers=self.user_headers
        )
        assert response.status_code == 200, f"Vault endpoint failed: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "items" in data, "Missing items array"
        assert "total" in data, "Missing total count"
        
        print(f"✅ Vault endpoint: {data['total']} documents")
    
    def test_clearform_credits_wallet(self):
        """Test GET /api/clearform/credits/wallet - returns user's credit wallet"""
        response = requests.get(
            f"{BASE_URL}/api/clearform/credits/wallet",
            headers=self.user_headers
        )
        assert response.status_code == 200, f"Wallet endpoint failed: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "total_balance" in data, "Missing total_balance"
        
        print(f"✅ Wallet endpoint: {data['total_balance']} credits")
    
    def test_clearform_credit_packages(self):
        """Test GET /api/clearform/credits/packages - returns available credit packages"""
        response = requests.get(
            f"{BASE_URL}/api/clearform/credits/packages",
            headers=self.user_headers
        )
        assert response.status_code == 200, f"Packages endpoint failed: {response.text}"
        
        data = response.json()
        # API returns array directly
        packages = data if isinstance(data, list) else data.get("packages", [])
        assert len(packages) >= 3, "Should have at least 3 credit packages"
        
        # Check for expected credit amounts
        credit_amounts = [p.get("credits") for p in packages]
        assert 10 in credit_amounts, "Missing 10 credits package"
        assert 25 in credit_amounts, "Missing 25 credits package"
        
        print(f"✅ Credit packages: {len(packages)} packages available")


class TestHealthAndBasicEndpoints:
    """Test basic health and public endpoints"""
    
    def test_health_endpoint(self):
        """Test GET /api/health - returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        
        data = response.json()
        assert data.get("status") == "healthy", "Status should be healthy"
        
        print("✅ Health endpoint working")
    
    def test_clearform_document_types(self):
        """Test GET /api/clearform/documents/types - returns available document types"""
        response = requests.get(f"{BASE_URL}/api/clearform/documents/types")
        assert response.status_code == 200, f"Document types failed: {response.text}"
        
        data = response.json()
        # API returns array directly
        types = data if isinstance(data, list) else data.get("types", [])
        assert len(types) > 0, "Should have at least one document type"
        
        print(f"✅ Document types: {len(types)} types available")


class TestPricingDataValidation:
    """Validate pricing data matches expected values"""
    
    def test_credit_package_prices(self):
        """Verify credit packages exist with expected credit amounts"""
        # Login to get packages
        response = requests.post(
            f"{BASE_URL}/api/clearform/auth/login",
            json={"email": "doctest@clearform.com", "password": "Test123!"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/clearform/credits/packages",
            headers=headers
        )
        assert response.status_code == 200
        
        data = response.json()
        # API returns array directly
        packages = data if isinstance(data, list) else data.get("packages", [])
        
        # Verify packages have required fields
        for pkg in packages:
            assert "credits" in pkg, "Package missing credits field"
            assert "price" in pkg, "Package missing price field"
            assert "package_id" in pkg, "Package missing package_id field"
        
        # Verify expected credit amounts exist
        credit_amounts = [p.get("credits") for p in packages]
        assert 10 in credit_amounts, "Missing 10 credits package"
        assert 25 in credit_amounts, "Missing 25 credits package"
        
        print(f"✅ Credit packages validated: {len(packages)} packages")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
