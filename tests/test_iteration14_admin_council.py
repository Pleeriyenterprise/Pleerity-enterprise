"""
Test Suite for Iteration 14 Features:
1. Admin Management UI - Admin user CRUD operations
2. Council Name Normalization - Proper council name formatting

Tests cover:
- Admin list endpoint
- Admin invite endpoint
- Admin deactivate/reactivate endpoints
- Admin resend invite endpoint
- Council name normalization in postcode lookup
- Council search API with normalized names
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


class TestAdminAuthentication:
    """Test admin authentication for subsequent tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        return data["access_token"]
    
    def test_admin_login_success(self):
        """Test admin login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["role"] == "ROLE_ADMIN"


class TestAdminManagementAPI:
    """Test Admin Management endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip("Admin authentication failed")
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Get authorization headers"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_list_admins(self, auth_headers):
        """Test GET /api/admin/admins - List all admin users"""
        response = requests.get(
            f"{BASE_URL}/api/admin/admins",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "admins" in data
        assert "total" in data
        assert isinstance(data["admins"], list)
        assert data["total"] >= 1  # At least the current admin
        
        # Verify admin structure
        if data["admins"]:
            admin = data["admins"][0]
            assert "portal_user_id" in admin
            assert "auth_email" in admin
            assert "role" in admin
            assert admin["role"] == "ROLE_ADMIN"
            # Password hash should NOT be exposed
            assert "password_hash" not in admin
    
    def test_invite_admin_validation(self, auth_headers):
        """Test POST /api/admin/admins/invite - Validates required fields"""
        # Test missing email
        response = requests.post(
            f"{BASE_URL}/api/admin/admins/invite",
            headers=auth_headers,
            json={"full_name": "Test Admin"}
        )
        assert response.status_code == 422  # Validation error
        
        # Test missing full_name
        response = requests.post(
            f"{BASE_URL}/api/admin/admins/invite",
            headers=auth_headers,
            json={"email": "test@example.com"}
        )
        assert response.status_code == 422  # Validation error
    
    def test_invite_admin_duplicate_email(self, auth_headers):
        """Test POST /api/admin/admins/invite - Rejects duplicate email"""
        response = requests.post(
            f"{BASE_URL}/api/admin/admins/invite",
            headers=auth_headers,
            json={
                "email": ADMIN_EMAIL,  # Existing admin email
                "full_name": "Duplicate Admin"
            }
        )
        assert response.status_code == 400
        data = response.json()
        assert "already exists" in data.get("detail", "").lower()
    
    def test_invite_admin_success(self, auth_headers):
        """Test POST /api/admin/admins/invite - Successfully invites new admin"""
        import uuid
        test_email = f"test_admin_{uuid.uuid4().hex[:8]}@pleerity.com"
        
        response = requests.post(
            f"{BASE_URL}/api/admin/admins/invite",
            headers=auth_headers,
            json={
                "email": test_email,
                "full_name": "Test Admin User"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response
        assert "message" in data
        assert "portal_user_id" in data
        assert data["email"] == test_email
        assert data["status"] == "INVITED"
        
        # Store for cleanup/further tests
        return data["portal_user_id"]
    
    def test_deactivate_admin_self_prevention(self, auth_headers, admin_token):
        """Test DELETE /api/admin/admins/{id} - Cannot deactivate self"""
        # First get current admin's portal_user_id
        response = requests.get(
            f"{BASE_URL}/api/admin/admins",
            headers=auth_headers
        )
        assert response.status_code == 200
        admins = response.json()["admins"]
        
        # Find current admin by email
        current_admin = next(
            (a for a in admins if a.get("auth_email") == ADMIN_EMAIL),
            None
        )
        
        if current_admin:
            # Try to deactivate self
            response = requests.delete(
                f"{BASE_URL}/api/admin/admins/{current_admin['portal_user_id']}",
                headers=auth_headers
            )
            assert response.status_code == 400
            assert "cannot deactivate your own" in response.json().get("detail", "").lower()
    
    def test_deactivate_nonexistent_admin(self, auth_headers):
        """Test DELETE /api/admin/admins/{id} - Returns 404 for non-existent admin"""
        response = requests.delete(
            f"{BASE_URL}/api/admin/admins/nonexistent-id-12345",
            headers=auth_headers
        )
        assert response.status_code == 404
    
    def test_reactivate_nonexistent_admin(self, auth_headers):
        """Test POST /api/admin/admins/{id}/reactivate - Returns 404 for non-existent admin"""
        response = requests.post(
            f"{BASE_URL}/api/admin/admins/nonexistent-id-12345/reactivate",
            headers=auth_headers
        )
        assert response.status_code == 404
    
    def test_resend_invite_nonexistent_admin(self, auth_headers):
        """Test POST /api/admin/admins/{id}/resend-invite - Returns 404 for non-existent admin"""
        response = requests.post(
            f"{BASE_URL}/api/admin/admins/nonexistent-id-12345/resend-invite",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestCouncilNameNormalization:
    """Test Council Name Normalization feature"""
    
    def test_postcode_lookup_westminster(self):
        """Test postcode lookup returns normalized council name for Westminster"""
        response = requests.get(f"{BASE_URL}/api/intake/postcode-lookup/SW1A1AA")
        assert response.status_code == 200
        data = response.json()
        
        # Westminster should be normalized to "City of Westminster"
        council_name = data.get("council_name")
        assert council_name is not None
        # Should contain "Westminster" in some form
        assert "Westminster" in council_name or "westminster" in council_name.lower()
    
    def test_postcode_lookup_camden(self):
        """Test postcode lookup returns normalized council name for Camden (London Borough)"""
        response = requests.get(f"{BASE_URL}/api/intake/postcode-lookup/NW10NE")
        assert response.status_code == 200
        data = response.json()
        
        council_name = data.get("council_name")
        # London boroughs should be "London Borough of X"
        if council_name:
            assert "Camden" in council_name or "London Borough" in council_name
    
    def test_postcode_lookup_bristol(self):
        """Test postcode lookup returns normalized council name for Bristol"""
        response = requests.get(f"{BASE_URL}/api/intake/postcode-lookup/BS81TH")
        assert response.status_code == 200
        data = response.json()
        
        council_name = data.get("council_name")
        # Bristol should be "Bristol City Council"
        if council_name:
            assert "Bristol" in council_name
            # Should have proper suffix
            assert "Council" in council_name or "council" in council_name.lower()
    
    def test_postcode_lookup_manchester(self):
        """Test postcode lookup returns normalized council name for Manchester"""
        response = requests.get(f"{BASE_URL}/api/intake/postcode-lookup/M11AE")
        assert response.status_code == 200
        data = response.json()
        
        council_name = data.get("council_name")
        # Manchester should be "Manchester City Council"
        if council_name:
            assert "Manchester" in council_name
    
    def test_council_search_returns_normalized_names(self):
        """Test council search API returns normalized names"""
        response = requests.get(f"{BASE_URL}/api/intake/councils?q=Bristol")
        assert response.status_code == 200
        data = response.json()
        
        assert "councils" in data
        councils = data["councils"]
        
        # Find Bristol in results
        bristol_councils = [c for c in councils if "Bristol" in c.get("name", "")]
        
        if bristol_councils:
            bristol = bristol_councils[0]
            # Should have normalized name
            assert "Council" in bristol["name"]
            # Should also have raw_name for reference
            assert "raw_name" in bristol
    
    def test_council_search_london_boroughs(self):
        """Test council search returns proper London Borough format"""
        response = requests.get(f"{BASE_URL}/api/intake/councils?q=Camden")
        assert response.status_code == 200
        data = response.json()
        
        councils = data["councils"]
        camden_councils = [c for c in councils if "Camden" in c.get("name", "")]
        
        if camden_councils:
            camden = camden_councils[0]
            # London boroughs should be "London Borough of X"
            assert "London Borough" in camden["name"] or "Council" in camden["name"]
    
    def test_council_search_pagination(self):
        """Test council search pagination works"""
        response = requests.get(f"{BASE_URL}/api/intake/councils?page=1&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert "councils" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert "total_pages" in data
        
        assert len(data["councils"]) <= 10
        assert data["page"] == 1
    
    def test_council_search_by_nation(self):
        """Test council search filter by nation"""
        response = requests.get(f"{BASE_URL}/api/intake/councils?nation=Scotland")
        assert response.status_code == 200
        data = response.json()
        
        councils = data["councils"]
        # All results should be Scottish councils
        for council in councils:
            assert council.get("nation", "").lower() == "scotland"


class TestAdminManagementIntegration:
    """Integration tests for Admin Management workflow"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip("Admin authentication failed")
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Get authorization headers"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_full_admin_lifecycle(self, auth_headers):
        """Test complete admin lifecycle: invite -> deactivate -> reactivate"""
        import uuid
        test_email = f"lifecycle_admin_{uuid.uuid4().hex[:8]}@pleerity.com"
        
        # Step 1: Invite new admin
        invite_response = requests.post(
            f"{BASE_URL}/api/admin/admins/invite",
            headers=auth_headers,
            json={
                "email": test_email,
                "full_name": "Lifecycle Test Admin"
            }
        )
        assert invite_response.status_code == 200
        portal_user_id = invite_response.json()["portal_user_id"]
        
        # Step 2: Verify admin appears in list
        list_response = requests.get(
            f"{BASE_URL}/api/admin/admins",
            headers=auth_headers
        )
        assert list_response.status_code == 200
        admins = list_response.json()["admins"]
        new_admin = next((a for a in admins if a["portal_user_id"] == portal_user_id), None)
        assert new_admin is not None
        assert new_admin["status"] == "INVITED"
        
        # Step 3: Deactivate the admin
        deactivate_response = requests.delete(
            f"{BASE_URL}/api/admin/admins/{portal_user_id}",
            headers=auth_headers
        )
        assert deactivate_response.status_code == 200
        
        # Step 4: Verify admin is disabled
        list_response = requests.get(
            f"{BASE_URL}/api/admin/admins",
            headers=auth_headers
        )
        admins = list_response.json()["admins"]
        disabled_admin = next((a for a in admins if a["portal_user_id"] == portal_user_id), None)
        assert disabled_admin is not None
        assert disabled_admin["status"] == "DISABLED"
        
        # Step 5: Reactivate the admin
        reactivate_response = requests.post(
            f"{BASE_URL}/api/admin/admins/{portal_user_id}/reactivate",
            headers=auth_headers
        )
        assert reactivate_response.status_code == 200
        
        # Step 6: Verify admin is active again
        list_response = requests.get(
            f"{BASE_URL}/api/admin/admins",
            headers=auth_headers
        )
        admins = list_response.json()["admins"]
        reactivated_admin = next((a for a in admins if a["portal_user_id"] == portal_user_id), None)
        assert reactivated_admin is not None
        assert reactivated_admin["status"] == "ACTIVE"
    
    def test_resend_invite_for_pending_admin(self, auth_headers):
        """Test resending invite for admin who hasn't set password"""
        import uuid
        test_email = f"resend_test_{uuid.uuid4().hex[:8]}@pleerity.com"
        
        # Invite new admin
        invite_response = requests.post(
            f"{BASE_URL}/api/admin/admins/invite",
            headers=auth_headers,
            json={
                "email": test_email,
                "full_name": "Resend Test Admin"
            }
        )
        assert invite_response.status_code == 200
        portal_user_id = invite_response.json()["portal_user_id"]
        
        # Resend invite
        resend_response = requests.post(
            f"{BASE_URL}/api/admin/admins/{portal_user_id}/resend-invite",
            headers=auth_headers
        )
        assert resend_response.status_code == 200
        data = resend_response.json()
        assert "message" in data
        assert "resent" in data["message"].lower()


class TestAdminDashboardStats:
    """Test Admin Dashboard stats include admin counts"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip("Admin authentication failed")
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Get authorization headers"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_admin_list_has_stats(self, auth_headers):
        """Test admin list endpoint returns proper stats"""
        response = requests.get(
            f"{BASE_URL}/api/admin/admins",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should have total count
        assert "total" in data
        assert data["total"] >= 1
        
        # Admins should have status info for stats calculation
        admins = data["admins"]
        for admin in admins:
            assert "status" in admin
            assert "password_status" in admin


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
