"""
ClearForm Admin and Pricing Features Tests - Iteration 61

Tests for:
- ClearForm admin endpoints (stats, users, documents)
- Pricing page data validation
- ClearForm vault and credits pages
"""

import pytest


class TestClearFormAdminEndpoints:
    """Test ClearForm admin API endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self, client):
        """Setup admin authentication"""
        response = client.post(
            "/api/auth/login",
            json={"email": "admin@pleerity.com", "password": "Admin123!"}
        )
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        self.admin_token = response.json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.client = client

    def test_clearform_admin_stats(self):
        """Test GET /api/admin/clearform/stats - returns ClearForm statistics"""
        response = self.client.get(
            "/api/admin/clearform/stats",
            headers=self.admin_headers
        )
        assert response.status_code == 200, f"Stats endpoint failed: {response.text}"

        data = response.json()
        assert "total_users" in data, "Missing total_users in stats"
        assert "active_users" in data, "Missing active_users in stats"
        assert "total_documents" in data, "Missing total_documents in stats"
        assert "total_credits_used" in data, "Missing total_credits_used in stats"
        assert isinstance(data["total_users"], int)
        assert isinstance(data["active_users"], int)
        assert isinstance(data["total_documents"], int)
        assert isinstance(data["total_credits_used"], int)

    def test_clearform_admin_users(self):
        """Test GET /api/admin/clearform/users - returns ClearForm users list"""
        response = self.client.get(
            "/api/admin/clearform/users",
            headers=self.admin_headers
        )
        assert response.status_code == 200, f"Users endpoint failed: {response.text}"

        data = response.json()
        assert "users" in data, "Missing users array"
        assert "total" in data, "Missing total count"
        assert "page" in data, "Missing page number"
        assert "page_size" in data, "Missing page_size"
        if data["users"]:
            user = data["users"][0]
            assert "user_id" in user, "Missing user_id"
            assert "email" in user, "Missing email"
            assert "full_name" in user, "Missing full_name"
            assert "status" in user, "Missing status"
            assert "credit_balance" in user, "Missing credit_balance"
            assert "created_at" in user, "Missing created_at"

    def test_clearform_admin_documents(self):
        """Test GET /api/admin/clearform/documents - returns ClearForm documents list"""
        response = self.client.get(
            "/api/admin/clearform/documents",
            headers=self.admin_headers
        )
        assert response.status_code == 200, f"Documents endpoint failed: {response.text}"

        data = response.json()
        assert "documents" in data, "Missing documents array"
        assert "total" in data, "Missing total count"
        assert "page" in data, "Missing page number"
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

    def test_clearform_admin_requires_auth(self, client):
        """Test that admin endpoints require authentication"""
        response = client.get("/api/admin/clearform/stats")
        assert response.status_code == 401, "Stats should require auth"
        response = client.get("/api/admin/clearform/users")
        assert response.status_code == 401, "Users should require auth"
        response = client.get("/api/admin/clearform/documents")
        assert response.status_code == 401, "Documents should require auth"


class TestClearFormUserEndpoints:
    """Test ClearForm user-facing endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self, client):
        """Setup ClearForm user authentication"""
        response = client.post(
            "/api/clearform/auth/login",
            json={"email": "doctest@clearform.com", "password": "Test123!"}
        )
        assert response.status_code == 200, f"ClearForm login failed: {response.text}"
        self.user_token = response.json()["access_token"]
        self.user_headers = {"Authorization": f"Bearer {self.user_token}"}
        self.user_data = response.json()["user"]
        self.client = client

    def test_clearform_vault_endpoint(self):
        """Test GET /api/clearform/documents/vault - returns user's documents"""
        response = self.client.get(
            "/api/clearform/documents/vault",
            headers=self.user_headers
        )
        assert response.status_code == 200, f"Vault endpoint failed: {response.text}"
        data = response.json()
        assert "items" in data, "Missing items array"
        assert "total" in data, "Missing total count"

    def test_clearform_credits_wallet(self):
        """Test GET /api/clearform/credits/wallet - returns user's credit wallet"""
        response = self.client.get(
            "/api/clearform/credits/wallet",
            headers=self.user_headers
        )
        assert response.status_code == 200, f"Wallet endpoint failed: {response.text}"
        data = response.json()
        assert "total_balance" in data, "Missing total_balance"

    def test_clearform_credit_packages(self):
        """Test GET /api/clearform/credits/packages - returns available credit packages"""
        response = self.client.get(
            "/api/clearform/credits/packages",
            headers=self.user_headers
        )
        assert response.status_code == 200, f"Packages endpoint failed: {response.text}"
        data = response.json()
        packages = data if isinstance(data, list) else data.get("packages", [])
        assert len(packages) >= 3, "Should have at least 3 credit packages"
        credit_amounts = [p.get("credits") for p in packages]
        assert 10 in credit_amounts, "Missing 10 credits package"
        assert 25 in credit_amounts, "Missing 25 credits package"


class TestHealthAndBasicEndpoints:
    """Test basic health and public endpoints"""

    def test_health_endpoint(self, client):
        """Test GET /api/health - returns healthy status"""
        response = client.get("/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy", "Status should be healthy"

    def test_clearform_document_types(self, client):
        """Test GET /api/clearform/documents/types - returns available document types"""
        response = client.get("/api/clearform/documents/types")
        assert response.status_code == 200, f"Document types failed: {response.text}"
        data = response.json()
        types = data if isinstance(data, list) else data.get("types", [])
        assert len(types) > 0, "Should have at least one document type"


class TestPricingDataValidation:
    """Validate pricing data matches expected values"""

    def test_credit_package_prices(self, client):
        """Verify credit packages exist with expected credit amounts"""
        response = client.post(
            "/api/clearform/auth/login",
            json={"email": "doctest@clearform.com", "password": "Test123!"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get(
            "/api/clearform/credits/packages",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        packages = data if isinstance(data, list) else data.get("packages", [])

        for pkg in packages:
            assert "credits" in pkg, "Package missing credits field"
            assert "price_gbp" in pkg, "Package missing price_gbp field"
            assert "package_id" in pkg, "Package missing package_id field"
            assert "price_display" in pkg, "Package missing price_display field"
        credit_amounts = [p.get("credits") for p in packages]
        assert 10 in credit_amounts, "Missing 10 credits package"
        assert 25 in credit_amounts, "Missing 25 credits package"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
