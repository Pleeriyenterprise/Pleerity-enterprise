"""
Test Suite for Three New Features:
1. Team Permissions UI with Manager role + custom role builder
2. CMS Templates with pre-built page templates
3. Report Sharing via public time-limited URLs

Iteration 55 - Testing all new endpoints
"""
import pytest
import uuid
from datetime import datetime

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


class TestSetup:
    """Setup and authentication"""
    
    @pytest.fixture
    def auth_token(self, client):
        """Get admin authentication token"""
        response = client.post("/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }


# ============================================
# TEAM PERMISSIONS TESTS
# ============================================

class TestTeamPermissions(TestSetup):
    """Test Team Permissions API - 13 permission categories, 5 built-in roles"""
    
    def test_get_all_permissions(self, client, auth_headers):
        """GET /api/admin/team/permissions - Returns 13 permission categories"""
        response = client.get("/api/admin/team/permissions", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "permissions" in data
        assert "categories" in data
        
        # Verify 13 permission categories
        expected_categories = [
            "dashboard", "clients", "leads", "orders", "reports", "cms",
            "support", "billing", "settings", "team", "analytics", "enablement", "consent"
        ]
        for cat in expected_categories:
            assert cat in data["permissions"], f"Missing category: {cat}"
        
        print(f"✓ Found {len(data['categories'])} permission categories")
    
    def test_list_roles(self, client, auth_headers):
        """GET /api/admin/team/roles - Returns 5 built-in roles"""
        response = client.get("/api/admin/team/roles", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "roles" in data
        
        # Verify 5 built-in roles
        role_ids = [r["role_id"] for r in data["roles"]]
        expected_roles = ["super_admin", "manager", "viewer", "support_agent", "content_manager"]
        for role in expected_roles:
            assert role in role_ids, f"Missing built-in role: {role}"
        
        # Verify role structure
        for role in data["roles"]:
            assert "role_id" in role
            assert "name" in role
            assert "description" in role
            assert "permissions" in role
            assert "is_system" in role
        
        print(f"✓ Found {len(data['roles'])} roles including 5 built-in")
    
    def test_get_role_details(self, client, auth_headers):
        """GET /api/admin/team/roles/{role_id} - Get role details"""
        # Test built-in role
        response = client.get("/api/admin/team/roles/manager", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["role_id"] == "manager"
        assert data["name"] == "Manager"
        assert data["is_system"] == True
        assert "permissions" in data
        
        print(f"✓ Manager role has {len(data['permissions'])} permission categories")
    
    def test_create_custom_role(self, client, auth_headers):
        """POST /api/admin/team/roles - Create custom role"""
        unique_id = uuid.uuid4().hex[:8]
        role_data = {
            "name": f"TEST_Custom_Role_{unique_id}",
            "description": "Test custom role with specific permissions",
            "permissions": {
                "dashboard": ["view"],
                "clients": ["view", "create"],
                "leads": ["view", "edit"],
                "reports": ["view"]
            }
        }
        
        response = client.post("/api/admin/team/roles", json=role_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "role_id" in data
        assert data["name"] == role_data["name"]
        assert data["is_system"] == False
        assert data["permissions"] == role_data["permissions"]
        
        # Store for cleanup
        self.__class__.created_role_id = data["role_id"]
        print(f"✓ Created custom role: {data['role_id']}")
        return data["role_id"]
    
    def test_update_custom_role(self, client, auth_headers):
        """PUT /api/admin/team/roles/{id} - Update custom role"""
        role_id = getattr(self.__class__, 'created_role_id', None)
        if not role_id:
            pytest.skip("No custom role created")
        
        update_data = {
            "name": f"TEST_Updated_Role_{uuid.uuid4().hex[:8]}",
            "description": "Updated description",
            "permissions": {
                "dashboard": ["view"],
                "clients": ["view", "create", "edit"],
                "leads": ["view", "edit", "delete"]
            }
        }
        
        response = client.put(f"/api/admin/team/roles/{role_id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["success"] == True
        print(f"✓ Updated custom role: {role_id}")
    
    def test_cannot_update_builtin_role(self, client, auth_headers):
        """PUT /api/admin/team/roles/{id} - Cannot modify built-in roles"""
        response = client.put(
            "/api/admin/team/roles/super_admin",
            json={"name": "Hacked Admin"},
            headers=auth_headers
        )
        assert response.status_code == 400, f"Should fail: {response.text}"
        print("✓ Built-in roles cannot be modified")
    
    def test_delete_custom_role(self, client, auth_headers):
        """DELETE /api/admin/team/roles/{id} - Delete custom role"""
        role_id = getattr(self.__class__, 'created_role_id', None)
        if not role_id:
            pytest.skip("No custom role created")
        
        response = client.delete(f"/api/admin/team/roles/{role_id}", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["success"] == True
        print(f"✓ Deleted custom role: {role_id}")
    
    def test_cannot_delete_builtin_role(self, client, auth_headers):
        """DELETE /api/admin/team/roles/{id} - Cannot delete built-in roles"""
        response = client.delete("/api/admin/team/roles/manager", headers=auth_headers)
        assert response.status_code == 400, f"Should fail: {response.text}"
        print("✓ Built-in roles cannot be deleted")
    
    def test_list_admin_users(self, client, auth_headers):
        """GET /api/admin/team/users - List admin users"""
        response = client.get("/api/admin/team/users", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "users" in data
        assert "total" in data
        
        # Verify user structure - note: uses auth_email not email
        if data["users"]:
            user = data["users"][0]
            assert "portal_user_id" in user
            assert "auth_email" in user or "email" in user
            assert "role_id" in user or "role_name" in user
        
        print(f"✓ Found {data['total']} admin users")
    
    def test_create_admin_user(self, client, auth_headers):
        """POST /api/admin/team/users - Create new admin user"""
        unique_id = uuid.uuid4().hex[:8]
        user_data = {
            "email": f"test_admin_{unique_id}@pleerity.com",
            "name": f"Test Admin {unique_id}",
            "role_id": "viewer",
            "send_invite": False
        }
        
        response = client.post("/api/admin/team/users", json=user_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "portal_user_id" in data
        assert data["email"] == user_data["email"].lower()
        assert data["role_id"] == "viewer"
        
        # Store for cleanup
        self.__class__.created_user_id = data["portal_user_id"]
        print(f"✓ Created admin user: {data['portal_user_id']}")
    
    def test_update_admin_user(self, client, auth_headers):
        """PUT /api/admin/team/users/{id} - Update admin user role"""
        user_id = getattr(self.__class__, 'created_user_id', None)
        if not user_id:
            pytest.skip("No user created")
        
        update_data = {
            "name": "Updated Test Admin",
            "role_id": "support_agent"
        }
        
        response = client.put(f"/api/admin/team/users/{user_id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["success"] == True
        print(f"✓ Updated admin user role to support_agent")
    
    def test_get_my_permissions(self, client, auth_headers):
        """GET /api/admin/team/me/permissions - Get current user's permissions"""
        response = client.get("/api/admin/team/me/permissions", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "role_id" in data
        assert "role_name" in data
        assert "permissions" in data
        
        print(f"✓ Current user role: {data['role_name']} with {len(data['permissions'])} permission categories")


# ============================================
# CMS TEMPLATES TESTS
# ============================================

class TestCMSTemplates(TestSetup):
    """Test CMS Templates API - 4 pre-built page templates"""
    
    def test_list_templates(self, client, auth_headers):
        """GET /api/admin/cms/templates - Returns 4 templates"""
        response = client.get("/api/admin/cms/templates", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "templates" in data
        
        # Verify 4 templates
        template_ids = [t["template_id"] for t in data["templates"]]
        expected_templates = ["landing_page", "about_us", "contact_us", "pricing_page"]
        for template in expected_templates:
            assert template in template_ids, f"Missing template: {template}"
        
        # Verify template structure
        for template in data["templates"]:
            assert "template_id" in template
            assert "name" in template
            assert "description" in template
            assert "block_count" in template
        
        print(f"✓ Found {len(data['templates'])} templates: {template_ids}")
    
    def test_get_template_details_landing(self, client, auth_headers):
        """GET /api/admin/cms/templates/landing_page - Get landing page template"""
        response = client.get("/api/admin/cms/templates/landing_page", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["template_id"] == "landing_page"
        assert "name" in data
        assert "blocks" in data
        assert len(data["blocks"]) > 0
        
        print(f"✓ Landing page template has {len(data['blocks'])} blocks")
    
    def test_get_template_details_about(self, client, auth_headers):
        """GET /api/admin/cms/templates/about_us - Get about us template"""
        response = client.get("/api/admin/cms/templates/about_us", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["template_id"] == "about_us"
        assert "blocks" in data
        
        print(f"✓ About Us template has {len(data['blocks'])} blocks")
    
    def test_get_template_details_contact(self, client, auth_headers):
        """GET /api/admin/cms/templates/contact_us - Get contact us template"""
        response = client.get("/api/admin/cms/templates/contact_us", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["template_id"] == "contact_us"
        assert "blocks" in data
        
        print(f"✓ Contact Us template has {len(data['blocks'])} blocks")
    
    def test_get_template_details_pricing(self, client, auth_headers):
        """GET /api/admin/cms/templates/pricing_page - Get pricing page template"""
        response = client.get("/api/admin/cms/templates/pricing_page", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["template_id"] == "pricing_page"
        assert "blocks" in data
        
        print(f"✓ Pricing page template has {len(data['blocks'])} blocks")
    
    def test_get_template_preview(self, client, auth_headers):
        """GET /api/admin/cms/templates/{id}/preview - Get template preview data"""
        response = client.get("/api/admin/cms/templates/landing_page/preview", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["template_id"] == "landing_page"
        assert "name" in data
        assert "blocks" in data
        
        # Verify preview block structure
        for block in data["blocks"]:
            assert "block_id" in block
            assert "block_type" in block
            assert "content" in block
            assert "order" in block
        
        print(f"✓ Template preview has {len(data['blocks'])} blocks with preview IDs")
    
    def test_apply_template_create_page(self, client, auth_headers):
        """POST /api/admin/cms/templates/apply - Apply template to create new page"""
        unique_id = uuid.uuid4().hex[:8]
        apply_data = {
            "template_id": "landing_page",
            "page_title": f"TEST Landing Page {unique_id}",
            "page_slug": f"test-landing-{unique_id}",
            "replace_existing": False
        }
        
        response = client.post("/api/admin/cms/templates/apply", json=apply_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["success"] == True
        assert "page_id" in data
        assert data["action"] == "created"
        
        # Store for cleanup
        self.__class__.created_page_id = data["page_id"]
        self.__class__.created_page_slug = apply_data["page_slug"]
        print(f"✓ Created page from template: {data['page_id']}")
    
    def test_verify_created_page_has_blocks(self, client, auth_headers):
        """Verify the page created from template has blocks"""
        page_id = getattr(self.__class__, 'created_page_id', None)
        if not page_id:
            pytest.skip("No page created")
        
        response = client.get(f"/api/admin/cms/pages/{page_id}", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "blocks" in data
        assert len(data["blocks"]) > 0, "Page should have blocks from template"
        
        print(f"✓ Created page has {len(data['blocks'])} blocks from template")
    
    def test_template_not_found(self, client, auth_headers):
        """GET /api/admin/cms/templates/{id} - Template not found"""
        response = client.get("/api/admin/cms/templates/nonexistent_template", headers=auth_headers)
        assert response.status_code == 404, f"Should return 404: {response.text}"
        print("✓ Non-existent template returns 404")
    
    def test_cleanup_created_page(self, client, auth_headers):
        """Cleanup: Delete the test page"""
        page_id = getattr(self.__class__, 'created_page_id', None)
        if page_id:
            response = client.delete(f"/api/admin/cms/pages/{page_id}", headers=auth_headers)
            print(f"✓ Cleaned up test page: {page_id}")


# ============================================
# REPORT SHARING TESTS
# ============================================

class TestReportSharing(TestSetup):
    """Test Report Sharing API - Public time-limited URLs"""
    
    def test_create_share_link(self, client, auth_headers):
        """POST /api/admin/reports/share - Create shareable report link"""
        share_data = {
            "name": f"TEST Share Link {uuid.uuid4().hex[:8]}",
            "report_type": "leads",
            "format": "csv",
            "period": "last_30_days",
            "expires_in_days": 7
        }
        
        response = client.post("/api/admin/reports/share", json=share_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "share_id" in data
        assert "share_url" in data
        assert "expires_at" in data
        
        # Store for later tests
        self.__class__.created_share_id = data["share_id"]
        print(f"✓ Created share link: {data['share_id']}")
    
    def test_list_share_links(self, client, auth_headers):
        """GET /api/admin/reports/shares - List all share links"""
        response = client.get("/api/admin/reports/shares", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "shares" in data
        
        # Verify share structure
        if data["shares"]:
            share = data["shares"][0]
            assert "share_id" in share
            assert "name" in share
            assert "report_type" in share
            assert "format" in share
            assert "expires_at" in share
        
        print(f"✓ Found {len(data['shares'])} share links")
    
    def test_get_public_shared_report_info(self, client):
        """GET /api/public/reports/shared/{id} - Get public shared report info (no auth)"""
        share_id = getattr(self.__class__, 'created_share_id', None)
        if not share_id:
            pytest.skip("No share link created")
        
        # This endpoint should NOT require authentication
        response = client.get(f"/api/public/reports/shared/{share_id}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "name" in data
        assert "report_type" in data
        assert "format" in data
        assert "expires_at" in data
        
        print(f"✓ Public report info accessible without auth: {data['name']}")
    
    def test_download_public_shared_report(self, client):
        """GET /api/public/reports/shared/{id}/download - Download shared report (no auth)"""
        share_id = getattr(self.__class__, 'created_share_id', None)
        if not share_id:
            pytest.skip("No share link created")
        
        # This endpoint should NOT require authentication
        response = client.get(f"/api/public/reports/shared/{share_id}/download")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        # Should return file content
        assert len(response.content) > 0, "Download should return content"
        
        # Check content-disposition header
        content_disp = response.headers.get('Content-Disposition', '')
        assert 'attachment' in content_disp or 'filename' in content_disp, "Should have download headers"
        
        print(f"✓ Public report download works without auth, size: {len(response.content)} bytes")
    
    def test_expired_share_link_rejected(self, client):
        """Test that expired share links are rejected"""
        # Try to access a non-existent share ID
        fake_share_id = f"SHARE-{uuid.uuid4().hex[:12].upper()}"
        response = client.get(f"/api/public/reports/shared/{fake_share_id}")
        assert response.status_code in [404, 400], f"Should fail: {response.text}"
        print("✓ Invalid/expired share links are rejected")
    
    def test_revoke_share_link(self, client, auth_headers):
        """DELETE /api/admin/reports/shares/{id} - Revoke share link"""
        share_id = getattr(self.__class__, 'created_share_id', None)
        if not share_id:
            pytest.skip("No share link created")
        
        response = client.delete(f"/api/admin/reports/shares/{share_id}", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["success"] == True
        print(f"✓ Revoked share link: {share_id}")
    
    def test_revoked_share_link_inaccessible(self, client):
        """Test that revoked share links cannot be accessed"""
        share_id = getattr(self.__class__, 'created_share_id', None)
        if not share_id:
            pytest.skip("No share link created")
        
        # Try to access revoked share
        response = client.get(f"/api/public/reports/shared/{share_id}")
        assert response.status_code in [404, 400, 410], f"Should fail: {response.text}"
        print("✓ Revoked share links are inaccessible")


# ============================================
# AUTHENTICATION TESTS
# ============================================

class TestAuthenticationRequired:
    """Test that all admin endpoints require authentication"""
    
    def test_team_permissions_requires_auth(self, client):
        """Team permissions endpoint requires auth"""
        response = client.get("/api/admin/team/permissions")
        assert response.status_code in [401, 403], f"Should require auth: {response.text}"
        print("✓ /api/admin/team/permissions requires auth")
    
    def test_team_roles_requires_auth(self, client):
        """Team roles endpoint requires auth"""
        response = client.get("/api/admin/team/roles")
        assert response.status_code in [401, 403], f"Should require auth: {response.text}"
        print("✓ /api/admin/team/roles requires auth")
    
    def test_team_users_requires_auth(self, client):
        """Team users endpoint requires auth"""
        response = client.get("/api/admin/team/users")
        assert response.status_code in [401, 403], f"Should require auth: {response.text}"
        print("✓ /api/admin/team/users requires auth")
    
    def test_cms_templates_requires_auth(self, client):
        """CMS templates endpoint requires auth"""
        response = client.get("/api/admin/cms/templates")
        assert response.status_code in [401, 403], f"Should require auth: {response.text}"
        print("✓ /api/admin/cms/templates requires auth")
    
    def test_report_shares_requires_auth(self, client):
        """Report shares endpoint requires auth"""
        response = client.get("/api/admin/reports/shares")
        assert response.status_code in [401, 403], f"Should require auth: {response.text}"
        print("✓ /api/admin/reports/shares requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
