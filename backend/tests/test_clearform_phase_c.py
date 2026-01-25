"""
ClearForm Phase C - Organizations and Audit Logs API Tests
Tests for institutional accounts, team management, and audit logging.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from review request
TEST_USER_1 = {"email": "orgtest@clearform.com", "password": "Test123!"}
TEST_USER_2 = {"email": "doctest@clearform.com", "password": "Test123!"}
EXISTING_ORG_ID = "ORG-DADB67A3"
EXISTING_DOC_ID = "CFD-4BBD9DBB0482"


class TestClearFormAuth:
    """Authentication tests for ClearForm users"""
    
    def test_login_orgtest_user(self):
        """Test login for orgtest@clearform.com (org owner)"""
        response = requests.post(f"{BASE_URL}/api/clearform/auth/login", json=TEST_USER_1)
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == TEST_USER_1["email"]
    
    def test_login_doctest_user(self):
        """Test login for doctest@clearform.com (document owner)"""
        response = requests.post(f"{BASE_URL}/api/clearform/auth/login", json=TEST_USER_2)
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == TEST_USER_2["email"]


class TestOrganizationAPIs:
    """Organization CRUD and member management tests"""
    
    @pytest.fixture
    def auth_token_orgtest(self):
        """Get auth token for orgtest user (org owner)"""
        response = requests.post(f"{BASE_URL}/api/clearform/auth/login", json=TEST_USER_1)
        if response.status_code != 200:
            pytest.skip(f"Auth failed for orgtest user: {response.text}")
        return response.json()["access_token"]
    
    @pytest.fixture
    def auth_token_doctest(self):
        """Get auth token for doctest user"""
        response = requests.post(f"{BASE_URL}/api/clearform/auth/login", json=TEST_USER_2)
        if response.status_code != 200:
            pytest.skip(f"Auth failed for doctest user: {response.text}")
        return response.json()["access_token"]
    
    def test_get_user_organizations(self, auth_token_orgtest):
        """GET /api/clearform/organizations - Get user's organizations"""
        headers = {"Authorization": f"Bearer {auth_token_orgtest}"}
        response = requests.get(f"{BASE_URL}/api/clearform/organizations", headers=headers)
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "organizations" in data
        assert isinstance(data["organizations"], list)
        
        # User should have at least one org (ORG-DADB67A3)
        if len(data["organizations"]) > 0:
            org = data["organizations"][0]
            assert "org_id" in org
            assert "name" in org
            assert "user_role" in org
    
    def test_get_organization_details(self, auth_token_orgtest):
        """GET /api/clearform/organizations/{org_id} - Get org details"""
        headers = {"Authorization": f"Bearer {auth_token_orgtest}"}
        response = requests.get(
            f"{BASE_URL}/api/clearform/organizations/{EXISTING_ORG_ID}", 
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "organization" in data
        assert data["organization"]["org_id"] == EXISTING_ORG_ID
        assert "user_role" in data
    
    def test_get_organization_members(self, auth_token_orgtest):
        """GET /api/clearform/organizations/{org_id}/members - Get org members"""
        headers = {"Authorization": f"Bearer {auth_token_orgtest}"}
        response = requests.get(
            f"{BASE_URL}/api/clearform/organizations/{EXISTING_ORG_ID}/members", 
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "members" in data
        assert isinstance(data["members"], list)
        
        # Should have at least the owner
        assert len(data["members"]) >= 1
        
        # Check member structure
        member = data["members"][0]
        assert "member_id" in member
        assert "user_id" in member
        assert "role" in member
    
    def test_get_pending_invitations(self, auth_token_orgtest):
        """GET /api/clearform/organizations/{org_id}/invitations - Get pending invitations"""
        headers = {"Authorization": f"Bearer {auth_token_orgtest}"}
        response = requests.get(
            f"{BASE_URL}/api/clearform/organizations/{EXISTING_ORG_ID}/invitations", 
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "invitations" in data
        assert isinstance(data["invitations"], list)
    
    def test_send_invitation(self, auth_token_orgtest):
        """POST /api/clearform/organizations/{org_id}/invitations - Send invitation"""
        headers = {"Authorization": f"Bearer {auth_token_orgtest}"}
        
        # Use a unique email to avoid duplicate invitation errors
        import time
        unique_email = f"testinvite_{int(time.time())}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/clearform/organizations/{EXISTING_ORG_ID}/invitations",
            headers=headers,
            json={
                "email": unique_email,
                "role": "MEMBER",
                "message": "Join our team!"
            }
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "invitation" in data
        assert data["invitation"]["email"] == unique_email
        assert data["invitation"]["role"] == "MEMBER"
        assert data["invitation"]["status"] == "PENDING"
    
    def test_get_org_credits(self, auth_token_orgtest):
        """GET /api/clearform/organizations/{org_id}/credits - Get org credit balance"""
        headers = {"Authorization": f"Bearer {auth_token_orgtest}"}
        response = requests.get(
            f"{BASE_URL}/api/clearform/organizations/{EXISTING_ORG_ID}/credits", 
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "credit_balance" in data
        assert "lifetime_credits_purchased" in data
        assert "lifetime_credits_used" in data
    
    def test_create_organization_already_owner(self, auth_token_orgtest):
        """POST /api/clearform/organizations - Should fail if user already owns an org"""
        headers = {"Authorization": f"Bearer {auth_token_orgtest}"}
        response = requests.post(
            f"{BASE_URL}/api/clearform/organizations",
            headers=headers,
            json={
                "name": "Another Org",
                "description": "Test org"
            }
        )
        
        # Should fail because user already owns an org
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "already own" in data.get("detail", "").lower()
    
    def test_non_member_cannot_access_org(self, auth_token_doctest):
        """Non-member should not be able to access organization details"""
        headers = {"Authorization": f"Bearer {auth_token_doctest}"}
        response = requests.get(
            f"{BASE_URL}/api/clearform/organizations/{EXISTING_ORG_ID}", 
            headers=headers
        )
        
        # Should be 403 Forbidden
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
    
    def test_list_compliance_packs(self, auth_token_orgtest):
        """GET /api/clearform/organizations/compliance-packs/list - List compliance packs"""
        headers = {"Authorization": f"Bearer {auth_token_orgtest}"}
        response = requests.get(
            f"{BASE_URL}/api/clearform/organizations/compliance-packs/list", 
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "packs" in data
        assert isinstance(data["packs"], list)


class TestAuditLogAPIs:
    """Audit log API tests"""
    
    @pytest.fixture
    def auth_token_orgtest(self):
        """Get auth token for orgtest user"""
        response = requests.post(f"{BASE_URL}/api/clearform/auth/login", json=TEST_USER_1)
        if response.status_code != 200:
            pytest.skip(f"Auth failed: {response.text}")
        return response.json()["access_token"]
    
    @pytest.fixture
    def auth_token_doctest(self):
        """Get auth token for doctest user"""
        response = requests.post(f"{BASE_URL}/api/clearform/auth/login", json=TEST_USER_2)
        if response.status_code != 200:
            pytest.skip(f"Auth failed: {response.text}")
        return response.json()["access_token"]
    
    def test_get_my_audit_logs(self, auth_token_orgtest):
        """GET /api/clearform/audit/me - Get user's audit logs"""
        headers = {"Authorization": f"Bearer {auth_token_orgtest}"}
        response = requests.get(f"{BASE_URL}/api/clearform/audit/me", headers=headers)
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "logs" in data
        assert isinstance(data["logs"], list)
        assert "count" in data
    
    def test_get_my_activity(self, auth_token_orgtest):
        """GET /api/clearform/audit/me/activity - Get recent activity"""
        headers = {"Authorization": f"Bearer {auth_token_orgtest}"}
        response = requests.get(f"{BASE_URL}/api/clearform/audit/me/activity", headers=headers)
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "activity" in data
        assert isinstance(data["activity"], list)
    
    def test_get_my_audit_stats(self, auth_token_orgtest):
        """GET /api/clearform/audit/me/stats - Get audit statistics"""
        headers = {"Authorization": f"Bearer {auth_token_orgtest}"}
        response = requests.get(f"{BASE_URL}/api/clearform/audit/me/stats", headers=headers)
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "stats" in data
    
    def test_get_org_audit_logs(self, auth_token_orgtest):
        """GET /api/clearform/audit/org/{org_id} - Get org audit logs (admin only)"""
        headers = {"Authorization": f"Bearer {auth_token_orgtest}"}
        response = requests.get(
            f"{BASE_URL}/api/clearform/audit/org/{EXISTING_ORG_ID}", 
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "logs" in data
        assert isinstance(data["logs"], list)
    
    def test_get_org_activity(self, auth_token_orgtest):
        """GET /api/clearform/audit/org/{org_id}/activity - Get org recent activity"""
        headers = {"Authorization": f"Bearer {auth_token_orgtest}"}
        response = requests.get(
            f"{BASE_URL}/api/clearform/audit/org/{EXISTING_ORG_ID}/activity", 
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "activity" in data
    
    def test_get_org_audit_stats(self, auth_token_orgtest):
        """GET /api/clearform/audit/org/{org_id}/stats - Get org audit stats"""
        headers = {"Authorization": f"Bearer {auth_token_orgtest}"}
        response = requests.get(
            f"{BASE_URL}/api/clearform/audit/org/{EXISTING_ORG_ID}/stats", 
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "stats" in data
    
    def test_get_document_audit_trail(self, auth_token_doctest):
        """GET /api/clearform/audit/document/{document_id} - Get document audit trail"""
        headers = {"Authorization": f"Bearer {auth_token_doctest}"}
        response = requests.get(
            f"{BASE_URL}/api/clearform/audit/document/{EXISTING_DOC_ID}", 
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "trail" in data
        assert isinstance(data["trail"], list)
    
    def test_list_audit_actions(self, auth_token_orgtest):
        """GET /api/clearform/audit/actions - List all audit action types"""
        headers = {"Authorization": f"Bearer {auth_token_orgtest}"}
        response = requests.get(f"{BASE_URL}/api/clearform/audit/actions", headers=headers)
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "actions" in data
        assert isinstance(data["actions"], list)
        assert len(data["actions"]) > 0
    
    def test_list_audit_severities(self, auth_token_orgtest):
        """GET /api/clearform/audit/severities - List audit severity levels"""
        headers = {"Authorization": f"Bearer {auth_token_orgtest}"}
        response = requests.get(f"{BASE_URL}/api/clearform/audit/severities", headers=headers)
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "severities" in data
        assert isinstance(data["severities"], list)
        assert "INFO" in data["severities"]
    
    def test_non_admin_cannot_access_org_audit(self, auth_token_doctest):
        """Non-admin should not be able to access org audit logs"""
        headers = {"Authorization": f"Bearer {auth_token_doctest}"}
        response = requests.get(
            f"{BASE_URL}/api/clearform/audit/org/{EXISTING_ORG_ID}", 
            headers=headers
        )
        
        # Should be 403 Forbidden (not a member or not admin)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"


class TestDocumentGeneration:
    """Test document generation still works"""
    
    @pytest.fixture
    def auth_token_doctest(self):
        """Get auth token for doctest user"""
        response = requests.post(f"{BASE_URL}/api/clearform/auth/login", json=TEST_USER_2)
        if response.status_code != 200:
            pytest.skip(f"Auth failed: {response.text}")
        return response.json()["access_token"]
    
    def test_get_existing_document(self, auth_token_doctest):
        """GET /api/clearform/documents/{document_id} - Get existing document"""
        headers = {"Authorization": f"Bearer {auth_token_doctest}"}
        response = requests.get(
            f"{BASE_URL}/api/clearform/documents/{EXISTING_DOC_ID}", 
            headers=headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["document_id"] == EXISTING_DOC_ID
        assert "status" in data
        assert "content_markdown" in data or data["status"] != "COMPLETED"
    
    def test_get_document_types(self, auth_token_doctest):
        """GET /api/clearform/documents/types - Get available document types"""
        headers = {"Authorization": f"Bearer {auth_token_doctest}"}
        response = requests.get(f"{BASE_URL}/api/clearform/documents/types", headers=headers)
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "document_types" in data
        assert isinstance(data["document_types"], list)
        assert len(data["document_types"]) > 0
    
    def test_get_user_vault(self, auth_token_doctest):
        """GET /api/clearform/documents/vault - Get user's document vault"""
        headers = {"Authorization": f"Bearer {auth_token_doctest}"}
        response = requests.get(f"{BASE_URL}/api/clearform/documents/vault", headers=headers)
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "documents" in data
        assert isinstance(data["documents"], list)


class TestCreditSystem:
    """Test credit system still works"""
    
    @pytest.fixture
    def auth_token_doctest(self):
        """Get auth token for doctest user"""
        response = requests.post(f"{BASE_URL}/api/clearform/auth/login", json=TEST_USER_2)
        if response.status_code != 200:
            pytest.skip(f"Auth failed: {response.text}")
        return response.json()["access_token"]
    
    def test_get_credit_wallet(self, auth_token_doctest):
        """GET /api/clearform/credits/wallet - Get credit wallet"""
        headers = {"Authorization": f"Bearer {auth_token_doctest}"}
        response = requests.get(f"{BASE_URL}/api/clearform/credits/wallet", headers=headers)
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "balance" in data
        assert "lifetime_purchased" in data
    
    def test_get_credit_packages(self, auth_token_doctest):
        """GET /api/clearform/credits/packages - Get available credit packages"""
        headers = {"Authorization": f"Bearer {auth_token_doctest}"}
        response = requests.get(f"{BASE_URL}/api/clearform/credits/packages", headers=headers)
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "packages" in data
        assert isinstance(data["packages"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
