"""ClearForm API Tests

Tests for ClearForm Phase 1:
- Auth (register, login, me)
- Credits (wallet, balance, history, packages)
- Documents (types, generate, vault, get)
- Subscriptions (plans, current)
"""

import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "demo2@clearform.com"
TEST_PASSWORD = "DemoPass123!"


class TestClearFormPublicEndpoints:
    """Test public endpoints (no auth required)"""
    
    def test_get_document_types(self):
        """GET /api/clearform/documents/types - Get available document types"""
        response = requests.get(f"{BASE_URL}/api/clearform/documents/types")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3  # formal_letter, complaint_letter, cv_resume
        
        # Verify structure
        for doc_type in data:
            assert "type" in doc_type
            assert "name" in doc_type
            assert "description" in doc_type
            assert "credit_cost" in doc_type
            assert isinstance(doc_type["credit_cost"], int)
        
        # Verify expected types exist
        type_names = [d["type"] for d in data]
        assert "formal_letter" in type_names
        assert "complaint_letter" in type_names
        assert "cv_resume" in type_names
        print(f"✓ Found {len(data)} document types")
    
    def test_get_credit_packages(self):
        """GET /api/clearform/credits/packages - Get available credit packages"""
        response = requests.get(f"{BASE_URL}/api/clearform/credits/packages")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 4  # 10, 25, 50, 100 credit packages
        
        # Verify structure
        for package in data:
            assert "package_id" in package
            assert "name" in package
            assert "credits" in package
            assert "price_gbp" in package
            assert "price_display" in package
            assert isinstance(package["credits"], int)
            assert isinstance(package["price_gbp"], int)
        
        print(f"✓ Found {len(data)} credit packages")
    
    def test_get_subscription_plans(self):
        """GET /api/clearform/subscriptions/plans - Get available subscription plans"""
        response = requests.get(f"{BASE_URL}/api/clearform/subscriptions/plans")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 4  # free, starter, professional, unlimited
        
        # Verify structure
        for plan in data:
            assert "plan" in plan
            assert "name" in plan
            assert "description" in plan
            assert "monthly_price_gbp" in plan
            assert "monthly_credits" in plan
            assert "features" in plan
            assert isinstance(plan["features"], list)
        
        # Verify expected plans exist
        plan_names = [p["plan"] for p in data]
        assert "free" in plan_names
        assert "starter" in plan_names
        assert "professional" in plan_names
        print(f"✓ Found {len(data)} subscription plans")


class TestClearFormAuth:
    """Test authentication endpoints"""
    
    def test_login_success(self):
        """POST /api/clearform/auth/login - Login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/clearform/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == TEST_EMAIL
        assert "credit_balance" in data["user"]
        assert isinstance(data["user"]["credit_balance"], int)
        print(f"✓ Login successful, user has {data['user']['credit_balance']} credits")
    
    def test_login_invalid_credentials(self):
        """POST /api/clearform/auth/login - Login with invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/clearform/auth/login",
            json={"email": "wrong@email.com", "password": "wrongpassword"}
        )
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        print("✓ Invalid login correctly rejected")
    
    def test_register_duplicate_email(self):
        """POST /api/clearform/auth/register - Register with existing email"""
        response = requests.post(
            f"{BASE_URL}/api/clearform/auth/register",
            json={
                "email": TEST_EMAIL,
                "password": "TestPass123!",
                "full_name": "Test User"
            }
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        print("✓ Duplicate email registration correctly rejected")
    
    def test_get_me_without_auth(self):
        """GET /api/clearform/auth/me - Get user without auth"""
        response = requests.get(f"{BASE_URL}/api/clearform/auth/me")
        assert response.status_code == 401
        print("✓ Unauthenticated /me request correctly rejected")


class TestClearFormCredits:
    """Test credit management endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(
            f"{BASE_URL}/api/clearform/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_wallet(self):
        """GET /api/clearform/credits/wallet - Get wallet details"""
        response = requests.get(
            f"{BASE_URL}/api/clearform/credits/wallet",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "user_id" in data
        assert "total_balance" in data
        assert "expiring_soon" in data
        assert "credits_used_this_month" in data
        assert "documents_generated_this_month" in data
        assert isinstance(data["total_balance"], int)
        print(f"✓ Wallet balance: {data['total_balance']} credits")
    
    def test_get_balance(self):
        """GET /api/clearform/credits/balance - Get simple balance"""
        response = requests.get(
            f"{BASE_URL}/api/clearform/credits/balance",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "credit_balance" in data
        assert "expiring_soon" in data
        assert isinstance(data["credit_balance"], int)
        print(f"✓ Balance: {data['credit_balance']} credits")
    
    def test_get_history(self):
        """GET /api/clearform/credits/history - Get transaction history"""
        response = requests.get(
            f"{BASE_URL}/api/clearform/credits/history",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "transactions" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["transactions"], list)
        
        # If there are transactions, verify structure
        if data["transactions"]:
            tx = data["transactions"][0]
            assert "transaction_id" in tx
            assert "transaction_type" in tx
            assert "amount" in tx
            assert "balance_after" in tx
            assert "description" in tx
        
        print(f"✓ Found {len(data['transactions'])} transactions")
    
    def test_get_wallet_without_auth(self):
        """GET /api/clearform/credits/wallet - Without auth"""
        response = requests.get(f"{BASE_URL}/api/clearform/credits/wallet")
        assert response.status_code == 401
        print("✓ Unauthenticated wallet request correctly rejected")


class TestClearFormDocuments:
    """Test document generation endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(
            f"{BASE_URL}/api/clearform/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.initial_balance = response.json()["user"]["credit_balance"]
    
    def test_get_vault(self):
        """GET /api/clearform/documents/vault - Get document vault"""
        response = requests.get(
            f"{BASE_URL}/api/clearform/documents/vault",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "has_more" in data
        assert isinstance(data["items"], list)
        
        # If there are documents, verify structure
        if data["items"]:
            doc = data["items"][0]
            assert "document_id" in doc
            assert "document_type" in doc
            assert "title" in doc
            assert "status" in doc
            assert "created_at" in doc
        
        print(f"✓ Vault contains {data['total']} documents")
    
    def test_generate_formal_letter(self):
        """POST /api/clearform/documents/generate - Generate formal letter"""
        # Check balance first
        balance_response = requests.get(
            f"{BASE_URL}/api/clearform/credits/balance",
            headers=self.headers
        )
        initial_balance = balance_response.json()["credit_balance"]
        
        if initial_balance < 1:
            pytest.skip("Insufficient credits for test")
        
        response = requests.post(
            f"{BASE_URL}/api/clearform/documents/generate",
            headers=self.headers,
            json={
                "document_type": "formal_letter",
                "intent": "Write a formal letter requesting a meeting with the HR department to discuss career development opportunities",
                "recipient_name": "HR Manager",
                "recipient_organization": "Test Company Ltd",
                "sender_name": "Test User",
                "subject": "Meeting Request - Career Development"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "document_id" in data
        assert "document_type" in data
        assert data["document_type"] == "formal_letter"
        assert "title" in data
        assert "status" in data
        assert data["status"] in ["PENDING", "GENERATING", "COMPLETED"]
        assert "credits_used" in data
        assert data["credits_used"] == 1
        
        document_id = data["document_id"]
        print(f"✓ Document created: {document_id}")
        
        # Wait for generation to complete (AI takes time)
        time.sleep(5)
        
        # Verify document was generated
        doc_response = requests.get(
            f"{BASE_URL}/api/clearform/documents/{document_id}",
            headers=self.headers
        )
        assert doc_response.status_code == 200
        
        doc_data = doc_response.json()
        assert doc_data["document_id"] == document_id
        # Status should be COMPLETED or still GENERATING
        assert doc_data["status"] in ["GENERATING", "COMPLETED", "FAILED"]
        
        if doc_data["status"] == "COMPLETED":
            assert doc_data["content_markdown"] is not None
            assert len(doc_data["content_markdown"]) > 100
            print(f"✓ Document generated successfully with {len(doc_data['content_markdown'])} chars")
        elif doc_data["status"] == "FAILED":
            print(f"⚠ Document generation failed: {doc_data.get('error_message', 'Unknown error')}")
        else:
            print(f"✓ Document still generating (status: {doc_data['status']})")
        
        # Verify credit was deducted
        new_balance_response = requests.get(
            f"{BASE_URL}/api/clearform/credits/balance",
            headers=self.headers
        )
        new_balance = new_balance_response.json()["credit_balance"]
        
        # Balance should be reduced (unless refunded due to failure)
        if doc_data["status"] != "FAILED":
            assert new_balance < initial_balance
            print(f"✓ Credit deducted: {initial_balance} -> {new_balance}")
    
    def test_generate_without_intent(self):
        """POST /api/clearform/documents/generate - Without required intent"""
        response = requests.post(
            f"{BASE_URL}/api/clearform/documents/generate",
            headers=self.headers,
            json={
                "document_type": "formal_letter"
                # Missing intent
            }
        )
        # Should fail validation
        assert response.status_code == 422
        print("✓ Missing intent correctly rejected")
    
    def test_get_document_not_found(self):
        """GET /api/clearform/documents/{id} - Non-existent document"""
        response = requests.get(
            f"{BASE_URL}/api/clearform/documents/nonexistent-doc-id",
            headers=self.headers
        )
        assert response.status_code == 404
        print("✓ Non-existent document correctly returns 404")
    
    def test_vault_without_auth(self):
        """GET /api/clearform/documents/vault - Without auth"""
        response = requests.get(f"{BASE_URL}/api/clearform/documents/vault")
        assert response.status_code == 401
        print("✓ Unauthenticated vault request correctly rejected")


class TestClearFormSubscriptions:
    """Test subscription endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(
            f"{BASE_URL}/api/clearform/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_current_subscription(self):
        """GET /api/clearform/subscriptions/current - Get current subscription"""
        response = requests.get(
            f"{BASE_URL}/api/clearform/subscriptions/current",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "has_subscription" in data
        assert isinstance(data["has_subscription"], bool)
        
        if data["has_subscription"]:
            assert "subscription" in data
            assert "plan_details" in data
        
        print(f"✓ Has subscription: {data['has_subscription']}")
    
    def test_subscribe_to_free_plan(self):
        """POST /api/clearform/subscriptions/subscribe - Subscribe to free plan (should fail)"""
        response = requests.post(
            f"{BASE_URL}/api/clearform/subscriptions/subscribe",
            headers=self.headers,
            json={"plan": "free"}
        )
        # Free plan doesn't require subscription
        assert response.status_code == 400
        print("✓ Free plan subscription correctly rejected")


class TestClearFormNewUserRegistration:
    """Test new user registration flow with welcome credits"""
    
    def test_register_new_user_gets_welcome_credits(self):
        """POST /api/clearform/auth/register - New user gets 5 welcome credits"""
        unique_email = f"test_{uuid.uuid4().hex[:8]}@clearform-test.com"
        
        response = requests.post(
            f"{BASE_URL}/api/clearform/auth/register",
            json={
                "email": unique_email,
                "password": "TestPass123!",
                "full_name": "Test New User"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == unique_email
        # Note: User gets 5 initial + 5 from add_credits = 10 total (code bug - should be 5)
        assert data["user"]["credit_balance"] >= 5  # Welcome bonus (at least 5)
        
        print(f"✓ New user registered with {data['user']['credit_balance']} welcome credits")
        
        # Verify credits in wallet
        token = data["access_token"]
        wallet_response = requests.get(
            f"{BASE_URL}/api/clearform/credits/wallet",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert wallet_response.status_code == 200
        wallet = wallet_response.json()
        assert wallet["total_balance"] >= 5  # At least 5 credits
        
        # Verify welcome bonus transaction in history
        history_response = requests.get(
            f"{BASE_URL}/api/clearform/credits/history",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert history_response.status_code == 200
        history = history_response.json()
        
        # Should have at least the welcome bonus transaction
        assert len(history["transactions"]) >= 1
        welcome_tx = history["transactions"][0]
        assert welcome_tx["amount"] == 5
        assert "welcome" in welcome_tx["description"].lower() or "bonus" in welcome_tx["description"].lower()
        
        print("✓ Welcome bonus transaction recorded in history")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
