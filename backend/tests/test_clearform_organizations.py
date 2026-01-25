"""
ClearForm Organizations API Tests
=================================
Tests for team management, organization CRUD, member invitations, and related features.
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ORG_OWNER_EMAIL = "orgtest@clearform.com"
ORG_OWNER_PASSWORD = "Test123!"
CLEARFORM_USER_EMAIL = "doctest@clearform.com"
CLEARFORM_USER_PASSWORD = "Test123!"
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


class TestClearFormOrganizationsAPI:
    """Test ClearForm Organizations API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
    def get_clearform_token(self, email, password):
        """Get ClearForm auth token"""
        response = self.session.post(
            f"{BASE_URL}/api/clearform/auth/login",
            json={"email": email, "password": password}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    
    def get_admin_token(self):
        """Get admin auth token"""
        response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    
    # =========================================================================
    # Organizations API Tests
    # =========================================================================
    
    def test_get_user_organizations(self):
        """Test GET /api/clearform/organizations - Get user's organizations"""
        token = self.get_clearform_token(ORG_OWNER_EMAIL, ORG_OWNER_PASSWORD)
        assert token, "Failed to get auth token"
        
        response = self.session.get(
            f"{BASE_URL}/api/clearform/organizations",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "organizations" in data
        assert isinstance(data["organizations"], list)
        
        # Verify org owner has at least one organization
        if len(data["organizations"]) > 0:
            org = data["organizations"][0]
            assert "org_id" in org
            assert "name" in org
            assert "user_role" in org
            print(f"✓ Found {len(data['organizations'])} organization(s) for user")
    
    def test_get_organization_details(self):
        """Test GET /api/clearform/organizations/{org_id} - Get org details"""
        token = self.get_clearform_token(ORG_OWNER_EMAIL, ORG_OWNER_PASSWORD)
        assert token, "Failed to get auth token"
        
        # First get user's organizations
        orgs_response = self.session.get(
            f"{BASE_URL}/api/clearform/organizations",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert orgs_response.status_code == 200
        orgs = orgs_response.json().get("organizations", [])
        
        if len(orgs) == 0:
            pytest.skip("No organizations found for user")
        
        org_id = orgs[0]["org_id"]
        
        response = self.session.get(
            f"{BASE_URL}/api/clearform/organizations/{org_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "organization" in data
        assert data["organization"]["org_id"] == org_id
        print(f"✓ Got organization details for {org_id}")
    
    def test_get_organization_members(self):
        """Test GET /api/clearform/organizations/{org_id}/members - Get members"""
        token = self.get_clearform_token(ORG_OWNER_EMAIL, ORG_OWNER_PASSWORD)
        assert token, "Failed to get auth token"
        
        # Get user's organizations
        orgs_response = self.session.get(
            f"{BASE_URL}/api/clearform/organizations",
            headers={"Authorization": f"Bearer {token}"}
        )
        orgs = orgs_response.json().get("organizations", [])
        
        if len(orgs) == 0:
            pytest.skip("No organizations found for user")
        
        org_id = orgs[0]["org_id"]
        
        response = self.session.get(
            f"{BASE_URL}/api/clearform/organizations/{org_id}/members",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "members" in data
        assert isinstance(data["members"], list)
        
        # Verify at least the owner is a member
        assert len(data["members"]) >= 1, "Organization should have at least one member (owner)"
        
        # Check member structure
        member = data["members"][0]
        assert "member_id" in member
        assert "user_id" in member
        assert "role" in member
        assert "email" in member
        print(f"✓ Found {len(data['members'])} member(s) in organization")
    
    def test_invite_member(self):
        """Test POST /api/clearform/organizations/{org_id}/invitations - Invite member"""
        token = self.get_clearform_token(ORG_OWNER_EMAIL, ORG_OWNER_PASSWORD)
        assert token, "Failed to get auth token"
        
        # Get user's organizations
        orgs_response = self.session.get(
            f"{BASE_URL}/api/clearform/organizations",
            headers={"Authorization": f"Bearer {token}"}
        )
        orgs = orgs_response.json().get("organizations", [])
        
        if len(orgs) == 0:
            pytest.skip("No organizations found for user")
        
        org_id = orgs[0]["org_id"]
        
        # Generate unique test email
        test_email = f"test_invite_{uuid.uuid4().hex[:8]}@example.com"
        
        response = self.session.post(
            f"{BASE_URL}/api/clearform/organizations/{org_id}/invitations",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": test_email,
                "role": "MEMBER",
                "message": "Test invitation"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "invitation" in data
        assert data["invitation"]["email"] == test_email
        print(f"✓ Successfully invited {test_email}")
    
    def test_get_pending_invitations(self):
        """Test GET /api/clearform/organizations/{org_id}/invitations - Get pending invitations"""
        token = self.get_clearform_token(ORG_OWNER_EMAIL, ORG_OWNER_PASSWORD)
        assert token, "Failed to get auth token"
        
        # Get user's organizations
        orgs_response = self.session.get(
            f"{BASE_URL}/api/clearform/organizations",
            headers={"Authorization": f"Bearer {token}"}
        )
        orgs = orgs_response.json().get("organizations", [])
        
        if len(orgs) == 0:
            pytest.skip("No organizations found for user")
        
        org_id = orgs[0]["org_id"]
        
        response = self.session.get(
            f"{BASE_URL}/api/clearform/organizations/{org_id}/invitations",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "invitations" in data
        assert isinstance(data["invitations"], list)
        print(f"✓ Found {len(data['invitations'])} pending invitation(s)")
    
    def test_get_organization_credits(self):
        """Test GET /api/clearform/organizations/{org_id}/credits - Get org credits"""
        token = self.get_clearform_token(ORG_OWNER_EMAIL, ORG_OWNER_PASSWORD)
        assert token, "Failed to get auth token"
        
        # Get user's organizations
        orgs_response = self.session.get(
            f"{BASE_URL}/api/clearform/organizations",
            headers={"Authorization": f"Bearer {token}"}
        )
        orgs = orgs_response.json().get("organizations", [])
        
        if len(orgs) == 0:
            pytest.skip("No organizations found for user")
        
        org_id = orgs[0]["org_id"]
        
        response = self.session.get(
            f"{BASE_URL}/api/clearform/organizations/{org_id}/credits",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert "credit_balance" in data
        assert "lifetime_credits_purchased" in data
        assert "lifetime_credits_used" in data
        print(f"✓ Organization credit balance: {data['credit_balance']}")
    
    def test_unauthorized_access_to_org(self):
        """Test that non-members cannot access organization"""
        # Login as different user
        token = self.get_clearform_token(CLEARFORM_USER_EMAIL, CLEARFORM_USER_PASSWORD)
        assert token, "Failed to get auth token"
        
        # Try to access org that belongs to another user
        response = self.session.get(
            f"{BASE_URL}/api/clearform/organizations/ORG-DADB67A3",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Should be 403 Forbidden if not a member
        assert response.status_code in [403, 404], f"Expected 403/404, got {response.status_code}"
        print("✓ Non-member access correctly denied")
    
    def test_create_organization_duplicate_owner(self):
        """Test that user cannot create multiple organizations as owner"""
        token = self.get_clearform_token(ORG_OWNER_EMAIL, ORG_OWNER_PASSWORD)
        assert token, "Failed to get auth token"
        
        response = self.session.post(
            f"{BASE_URL}/api/clearform/organizations",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Second Organization",
                "description": "Should fail",
                "org_type": "SMALL_BUSINESS"
            }
        )
        
        # Should fail because user already owns an org
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("✓ Duplicate organization creation correctly prevented")
    
    def test_invite_with_invalid_role(self):
        """Test invitation with invalid role"""
        token = self.get_clearform_token(ORG_OWNER_EMAIL, ORG_OWNER_PASSWORD)
        assert token, "Failed to get auth token"
        
        # Get user's organizations
        orgs_response = self.session.get(
            f"{BASE_URL}/api/clearform/organizations",
            headers={"Authorization": f"Bearer {token}"}
        )
        orgs = orgs_response.json().get("organizations", [])
        
        if len(orgs) == 0:
            pytest.skip("No organizations found for user")
        
        org_id = orgs[0]["org_id"]
        
        response = self.session.post(
            f"{BASE_URL}/api/clearform/organizations/{org_id}/invitations",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "test@example.com",
                "role": "INVALID_ROLE"
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid role correctly rejected")


class TestPricingPageContent:
    """Test that pricing page shows correct content"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_clearform_credit_packages_api(self):
        """Test GET /api/clearform/credits/packages - Get credit packages"""
        response = self.session.get(f"{BASE_URL}/api/clearform/credits/packages")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "packages" in data
        assert isinstance(data["packages"], list)
        assert len(data["packages"]) > 0
        print(f"✓ Found {len(data['packages'])} credit packages")
    
    def test_clearform_subscription_plans_api(self):
        """Test GET /api/clearform/subscriptions/plans - Get subscription plans"""
        response = self.session.get(f"{BASE_URL}/api/clearform/subscriptions/plans")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "plans" in data
        assert isinstance(data["plans"], list)
        print(f"✓ Found {len(data['plans'])} subscription plans")


class TestClearFormDashboardTeamCard:
    """Test ClearForm Dashboard Team Management card"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_clearform_token(self, email, password):
        """Get ClearForm auth token"""
        response = self.session.post(
            f"{BASE_URL}/api/clearform/auth/login",
            json={"email": email, "password": password}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    
    def test_dashboard_data_loads(self):
        """Test that dashboard data loads correctly"""
        token = self.get_clearform_token(ORG_OWNER_EMAIL, ORG_OWNER_PASSWORD)
        assert token, "Failed to get auth token"
        
        # Test wallet endpoint
        wallet_response = self.session.get(
            f"{BASE_URL}/api/clearform/credits/wallet",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert wallet_response.status_code == 200, f"Wallet API failed: {wallet_response.text}"
        
        # Test vault endpoint
        vault_response = self.session.get(
            f"{BASE_URL}/api/clearform/documents/vault",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert vault_response.status_code == 200, f"Vault API failed: {vault_response.text}"
        
        print("✓ Dashboard data endpoints working")


class TestAdminClearFormOrganizations:
    """Test Admin ClearForm Organizations endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_admin_token(self):
        """Get admin auth token"""
        response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    
    def test_admin_clearform_stats(self):
        """Test GET /api/admin/clearform/stats - Admin stats endpoint"""
        token = self.get_admin_token()
        assert token, "Failed to get admin token"
        
        response = self.session.get(
            f"{BASE_URL}/api/admin/clearform/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "total_users" in data
        assert "total_documents" in data
        print(f"✓ Admin stats: {data['total_users']} users, {data['total_documents']} documents")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
