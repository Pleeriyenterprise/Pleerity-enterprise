"""
ClearForm P0 Features Test Suite
Tests for:
1. CLEARFORM service in service catalogue V2
2. Document page with PDF viewer
3. Stripe checkout for credits
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_EMAIL = "demo2@clearform.com"
TEST_USER_PASSWORD = "DemoPass123!"


class TestClearFormServiceCatalogue:
    """Test CLEARFORM service exists in service catalogue V2"""
    
    def test_clearform_service_exists_in_catalogue(self):
        """Verify CLEARFORM service is in the service catalogue"""
        response = requests.get(f"{BASE_URL}/api/public/v2/services?category=clearform")
        assert response.status_code == 200
        
        data = response.json()
        assert "services" in data
        assert data["total"] >= 1
        
        # Find CLEARFORM service
        clearform_service = None
        for service in data["services"]:
            if service["service_code"] == "CLEARFORM":
                clearform_service = service
                break
        
        assert clearform_service is not None, "CLEARFORM service not found in catalogue"
        assert clearform_service["service_name"] == "ClearForm"
        assert clearform_service["category"] == "clearform"
        print(f"CLEARFORM service found: {clearform_service['service_name']}")
    
    def test_clearform_service_details(self):
        """Verify CLEARFORM service has correct details"""
        response = requests.get(f"{BASE_URL}/api/public/v2/services/CLEARFORM")
        assert response.status_code == 200
        
        service = response.json()
        assert service["service_code"] == "CLEARFORM"
        assert service["service_name"] == "ClearForm"
        assert service["category"] == "clearform"
        assert service["pricing_model"] == "one_time"
        assert service["delivery_type"] == "digital"
        
        # Check pricing variants
        assert "pricing_variants" in service
        assert len(service["pricing_variants"]) >= 3
        
        variant_codes = [v["variant_code"] for v in service["pricing_variants"]]
        assert "credits_10" in variant_codes
        assert "credits_25" in variant_codes
        assert "credits_75" in variant_codes
        print(f"CLEARFORM service has {len(service['pricing_variants'])} pricing variants")


class TestClearFormAuth:
    """Test ClearForm authentication"""
    
    def test_login_success(self):
        """Test successful login"""
        response = requests.post(
            f"{BASE_URL}/api/clearform/auth/login",
            json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == TEST_USER_EMAIL
        print(f"Login successful for {TEST_USER_EMAIL}")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/clearform/auth/login",
            json={"email": "invalid@test.com", "password": "wrongpassword"}
        )
        assert response.status_code in [401, 404]


class TestClearFormCredits:
    """Test ClearForm credits and Stripe checkout"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/clearform/auth/login",
            json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_get_wallet(self, auth_token):
        """Test getting user wallet"""
        response = requests.get(
            f"{BASE_URL}/api/clearform/credits/wallet",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        wallet = response.json()
        assert "total_balance" in wallet
        assert "subscription_credits" in wallet
        assert "purchased_credits" in wallet
        print(f"Wallet balance: {wallet['total_balance']} credits")
    
    def test_purchase_credits_creates_stripe_checkout(self, auth_token):
        """Test that purchasing credits creates a Stripe checkout session"""
        response = requests.post(
            f"{BASE_URL}/api/clearform/credits/purchase",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"package_id": "credits_10"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "checkout_url" in data
        assert "session_id" in data
        assert "stripe.com" in data["checkout_url"] or "checkout.stripe.com" in data["checkout_url"]
        print(f"Stripe checkout URL created: {data['checkout_url'][:50]}...")
    
    def test_purchase_credits_25(self, auth_token):
        """Test purchasing 25 credits package"""
        response = requests.post(
            f"{BASE_URL}/api/clearform/credits/purchase",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"package_id": "credits_25"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "checkout_url" in data
        assert "session_id" in data
        print("25 credits package checkout created successfully")
    
    def test_purchase_credits_75(self, auth_token):
        """Test purchasing 75 credits package"""
        response = requests.post(
            f"{BASE_URL}/api/clearform/credits/purchase",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"package_id": "credits_75"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "checkout_url" in data
        assert "session_id" in data
        print("75 credits package checkout created successfully")


class TestClearFormSubscriptions:
    """Test ClearForm subscription plans"""
    
    def test_get_subscription_plans(self):
        """Test getting subscription plans"""
        response = requests.get(f"{BASE_URL}/api/clearform/subscriptions/plans")
        assert response.status_code == 200
        
        plans = response.json()
        assert isinstance(plans, list)
        assert len(plans) >= 3
        
        plan_names = [p["plan"] for p in plans]
        assert "free" in plan_names
        print(f"Found {len(plans)} subscription plans: {plan_names}")
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/clearform/auth/login",
            json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_get_current_subscription(self, auth_token):
        """Test getting current subscription"""
        response = requests.get(
            f"{BASE_URL}/api/clearform/subscriptions/current",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "has_subscription" in data
        print(f"User has subscription: {data['has_subscription']}")


class TestClearFormDocuments:
    """Test ClearForm document functionality"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/clearform/auth/login",
            json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_get_document_types(self):
        """Test getting document types"""
        response = requests.get(f"{BASE_URL}/api/clearform/documents/types")
        assert response.status_code == 200
        
        types = response.json()
        assert isinstance(types, list) or isinstance(types, dict)
        print(f"Document types available: {len(types) if isinstance(types, list) else 'dict format'}")
    
    def test_get_document_vault(self, auth_token):
        """Test getting document vault"""
        response = requests.get(
            f"{BASE_URL}/api/clearform/documents/vault",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        vault = response.json()
        assert "items" in vault
        assert "total" in vault
        print(f"Document vault has {vault['total']} documents")
    
    def test_get_specific_document(self, auth_token):
        """Test getting a specific document"""
        # First get vault to find a document
        vault_response = requests.get(
            f"{BASE_URL}/api/clearform/documents/vault",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert vault_response.status_code == 200
        
        vault = vault_response.json()
        if vault["total"] == 0:
            pytest.skip("No documents in vault to test")
        
        document_id = vault["items"][0]["document_id"]
        
        # Get specific document
        response = requests.get(
            f"{BASE_URL}/api/clearform/documents/{document_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        doc = response.json()
        assert doc["document_id"] == document_id
        assert "content_markdown" in doc
        assert "status" in doc
        print(f"Document {document_id} retrieved successfully, status: {doc['status']}")
    
    def test_download_document_pdf(self, auth_token):
        """Test downloading document as PDF"""
        # First get vault to find a completed document
        vault_response = requests.get(
            f"{BASE_URL}/api/clearform/documents/vault",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert vault_response.status_code == 200
        
        vault = vault_response.json()
        completed_doc = None
        for item in vault["items"]:
            if item["status"] == "COMPLETED":
                completed_doc = item
                break
        
        if not completed_doc:
            pytest.skip("No completed documents to test PDF download")
        
        document_id = completed_doc["document_id"]
        
        # Download as PDF
        response = requests.get(
            f"{BASE_URL}/api/clearform/documents/{document_id}/download?format=pdf",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/pdf"
        print(f"PDF download successful for document {document_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
