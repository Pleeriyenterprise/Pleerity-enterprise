"""
Test Suite for Tenant Management Features (Iteration 9):
1. GET /api/client/tenants - List tenants with assigned properties
2. POST /api/client/tenants/invite - Invite new tenant with email
3. POST /api/client/tenants/{id}/assign-property - Assign property to tenant
4. DELETE /api/client/tenants/{id}/unassign-property/{prop_id} - Unassign property
5. DELETE /api/client/tenants/{id} - Revoke tenant access
6. POST /api/client/tenants/{id}/resend-invite - Resend invitation email
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://tenant-hub-77.preview.emergentagent.com').rstrip('/')

# Test credentials
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def client_auth():
    """Get client auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": CLIENT_EMAIL,
        "password": CLIENT_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return {
            "token": data["access_token"],
            "headers": {"Authorization": f"Bearer {data['access_token']}"},
            "user": data["user"]
        }
    pytest.skip("Client authentication failed")


@pytest.fixture(scope="module")
def admin_auth():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return {
            "token": data["access_token"],
            "headers": {"Authorization": f"Bearer {data['access_token']}"},
            "user": data["user"]
        }
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def properties(client_auth):
    """Get client properties for testing"""
    response = requests.get(f"{BASE_URL}/api/client/properties", headers=client_auth["headers"])
    if response.status_code == 200:
        return response.json().get("properties", [])
    return []


class TestHealthAndAuth:
    """Basic health and authentication tests"""
    
    def test_health_endpoint(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print(f"✓ Health check passed: {data}")
    
    def test_client_login(self):
        """Test client login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == CLIENT_EMAIL
        print(f"✓ Client login successful: {data['user']['email']}")


class TestListTenants:
    """Test GET /api/client/tenants - List tenants with assigned properties"""
    
    def test_list_tenants_success(self, client_auth):
        """Test listing tenants returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/client/tenants", headers=client_auth["headers"])
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "tenants" in data
        assert isinstance(data["tenants"], list)
        
        print(f"✓ List tenants: {len(data['tenants'])} tenants found")
        
        # If tenants exist, verify structure
        if data["tenants"]:
            tenant = data["tenants"][0]
            assert "portal_user_id" in tenant
            assert "email" in tenant
            assert "role" in tenant
            assert tenant["role"] == "ROLE_TENANT"
            assert "status" in tenant
            assert "assigned_properties" in tenant
            print(f"✓ Tenant structure verified: {tenant['email']}, status: {tenant['status']}, properties: {len(tenant['assigned_properties'])}")
    
    def test_list_tenants_unauthorized(self):
        """Test listing tenants without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/client/tenants")
        assert response.status_code == 401
        print("✓ Unauthorized access correctly rejected")


class TestInviteTenant:
    """Test POST /api/client/tenants/invite - Invite new tenant with email"""
    
    def test_invite_tenant_success(self, client_auth, properties):
        """Test inviting a new tenant with property assignment"""
        test_email = f"test_tenant_{uuid.uuid4().hex[:8]}@example.com"
        
        # Get property IDs for assignment
        property_ids = [p["property_id"] for p in properties[:2]] if properties else []
        
        response = requests.post(
            f"{BASE_URL}/api/client/tenants/invite",
            headers=client_auth["headers"],
            json={
                "email": test_email,
                "full_name": "Test Tenant User",
                "property_ids": property_ids,
                "base_url": BASE_URL
            }
        )
        
        # May be 403 if user is not CLIENT_ADMIN
        if response.status_code == 403:
            print(f"⚠ Tenant invite requires CLIENT_ADMIN role (got 403)")
            pytest.skip("User does not have CLIENT_ADMIN role")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "tenant_id" in data
        assert "email" in data
        assert data["email"] == test_email.lower()
        assert "message" in data
        assert "invite_sent" in data
        
        print(f"✓ Tenant invited: {test_email}, ID: {data['tenant_id']}, invite_sent: {data['invite_sent']}")
        
        # Store tenant_id for cleanup
        return data["tenant_id"]
    
    def test_invite_tenant_missing_email(self, client_auth):
        """Test inviting tenant without email returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/client/tenants/invite",
            headers=client_auth["headers"],
            json={
                "full_name": "Test Tenant"
            }
        )
        
        if response.status_code == 403:
            pytest.skip("User does not have CLIENT_ADMIN role")
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        print(f"✓ Missing email correctly rejected: {data['detail']}")
    
    def test_invite_duplicate_email(self, client_auth):
        """Test inviting tenant with existing email returns 400"""
        # First invite
        test_email = f"test_dup_{uuid.uuid4().hex[:8]}@example.com"
        
        response1 = requests.post(
            f"{BASE_URL}/api/client/tenants/invite",
            headers=client_auth["headers"],
            json={
                "email": test_email,
                "full_name": "First Tenant",
                "base_url": BASE_URL
            }
        )
        
        if response1.status_code == 403:
            pytest.skip("User does not have CLIENT_ADMIN role")
        
        # Second invite with same email
        response2 = requests.post(
            f"{BASE_URL}/api/client/tenants/invite",
            headers=client_auth["headers"],
            json={
                "email": test_email,
                "full_name": "Duplicate Tenant",
                "base_url": BASE_URL
            }
        )
        
        assert response2.status_code == 400
        data = response2.json()
        assert "already exists" in data["detail"].lower()
        print(f"✓ Duplicate email correctly rejected: {data['detail']}")


class TestAssignProperty:
    """Test POST /api/client/tenants/{id}/assign-property - Assign property to tenant"""
    
    @pytest.fixture
    def test_tenant(self, client_auth, properties):
        """Create a test tenant for property assignment tests"""
        test_email = f"test_assign_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/client/tenants/invite",
            headers=client_auth["headers"],
            json={
                "email": test_email,
                "full_name": "Assign Test Tenant",
                "base_url": BASE_URL
            }
        )
        
        if response.status_code == 403:
            pytest.skip("User does not have CLIENT_ADMIN role")
        
        if response.status_code == 200:
            return response.json()["tenant_id"]
        pytest.skip("Could not create test tenant")
    
    def test_assign_property_success(self, client_auth, properties, test_tenant):
        """Test assigning a property to a tenant"""
        if not properties:
            pytest.skip("No properties available for testing")
        
        property_id = properties[0]["property_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/client/tenants/{test_tenant}/assign-property",
            headers=client_auth["headers"],
            json={"property_id": property_id}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "tenant_id" in data or "assigned" in data["message"].lower()
        
        print(f"✓ Property {property_id} assigned to tenant {test_tenant}")
    
    def test_assign_property_missing_property_id(self, client_auth, test_tenant):
        """Test assigning without property_id returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/client/tenants/{test_tenant}/assign-property",
            headers=client_auth["headers"],
            json={}
        )
        
        assert response.status_code == 400
        print("✓ Missing property_id correctly rejected")
    
    def test_assign_property_invalid_tenant(self, client_auth, properties):
        """Test assigning to non-existent tenant returns 404"""
        if not properties:
            pytest.skip("No properties available for testing")
        
        response = requests.post(
            f"{BASE_URL}/api/client/tenants/invalid-tenant-id/assign-property",
            headers=client_auth["headers"],
            json={"property_id": properties[0]["property_id"]}
        )
        
        assert response.status_code == 404
        print("✓ Invalid tenant correctly rejected with 404")
    
    def test_assign_property_invalid_property(self, client_auth, test_tenant):
        """Test assigning non-existent property returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/client/tenants/{test_tenant}/assign-property",
            headers=client_auth["headers"],
            json={"property_id": "invalid-property-id"}
        )
        
        assert response.status_code == 404
        print("✓ Invalid property correctly rejected with 404")


class TestUnassignProperty:
    """Test DELETE /api/client/tenants/{id}/unassign-property/{prop_id} - Unassign property"""
    
    @pytest.fixture
    def tenant_with_property(self, client_auth, properties):
        """Create a tenant with an assigned property"""
        if not properties:
            pytest.skip("No properties available for testing")
        
        test_email = f"test_unassign_{uuid.uuid4().hex[:8]}@example.com"
        property_id = properties[0]["property_id"]
        
        # Create tenant with property
        response = requests.post(
            f"{BASE_URL}/api/client/tenants/invite",
            headers=client_auth["headers"],
            json={
                "email": test_email,
                "full_name": "Unassign Test Tenant",
                "property_ids": [property_id],
                "base_url": BASE_URL
            }
        )
        
        if response.status_code == 403:
            pytest.skip("User does not have CLIENT_ADMIN role")
        
        if response.status_code == 200:
            return {
                "tenant_id": response.json()["tenant_id"],
                "property_id": property_id
            }
        pytest.skip("Could not create test tenant")
    
    def test_unassign_property_success(self, client_auth, tenant_with_property):
        """Test unassigning a property from a tenant"""
        tenant_id = tenant_with_property["tenant_id"]
        property_id = tenant_with_property["property_id"]
        
        response = requests.delete(
            f"{BASE_URL}/api/client/tenants/{tenant_id}/unassign-property/{property_id}",
            headers=client_auth["headers"]
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        
        print(f"✓ Property {property_id} unassigned from tenant {tenant_id}")
    
    def test_unassign_property_not_assigned(self, client_auth, properties):
        """Test unassigning a property that was never assigned returns 404"""
        if not properties:
            pytest.skip("No properties available for testing")
        
        # Create tenant without property
        test_email = f"test_no_prop_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/client/tenants/invite",
            headers=client_auth["headers"],
            json={
                "email": test_email,
                "full_name": "No Property Tenant",
                "base_url": BASE_URL
            }
        )
        
        if response.status_code == 403:
            pytest.skip("User does not have CLIENT_ADMIN role")
        
        if response.status_code == 200:
            tenant_id = response.json()["tenant_id"]
            
            # Try to unassign a property that was never assigned
            response = requests.delete(
                f"{BASE_URL}/api/client/tenants/{tenant_id}/unassign-property/{properties[0]['property_id']}",
                headers=client_auth["headers"]
            )
            
            assert response.status_code == 404
            print("✓ Unassigning non-assigned property correctly rejected with 404")


class TestRevokeTenantAccess:
    """Test DELETE /api/client/tenants/{id} - Revoke tenant access"""
    
    @pytest.fixture
    def revoke_test_tenant(self, client_auth):
        """Create a tenant for revoke testing"""
        test_email = f"test_revoke_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/client/tenants/invite",
            headers=client_auth["headers"],
            json={
                "email": test_email,
                "full_name": "Revoke Test Tenant",
                "base_url": BASE_URL
            }
        )
        
        if response.status_code == 403:
            pytest.skip("User does not have CLIENT_ADMIN role")
        
        if response.status_code == 200:
            return response.json()["tenant_id"]
        pytest.skip("Could not create test tenant")
    
    def test_revoke_tenant_success(self, client_auth, revoke_test_tenant):
        """Test revoking tenant access"""
        response = requests.delete(
            f"{BASE_URL}/api/client/tenants/{revoke_test_tenant}",
            headers=client_auth["headers"]
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        
        print(f"✓ Tenant {revoke_test_tenant} access revoked")
        
        # Verify tenant is now disabled
        tenants_response = requests.get(f"{BASE_URL}/api/client/tenants", headers=client_auth["headers"])
        if tenants_response.status_code == 200:
            tenants = tenants_response.json()["tenants"]
            revoked_tenant = next((t for t in tenants if t["portal_user_id"] == revoke_test_tenant), None)
            if revoked_tenant:
                assert revoked_tenant["status"] == "DISABLED"
                print(f"✓ Tenant status verified as DISABLED")
    
    def test_revoke_invalid_tenant(self, client_auth):
        """Test revoking non-existent tenant returns 404"""
        response = requests.delete(
            f"{BASE_URL}/api/client/tenants/invalid-tenant-id",
            headers=client_auth["headers"]
        )
        
        assert response.status_code == 404
        print("✓ Invalid tenant correctly rejected with 404")


class TestResendInvite:
    """Test POST /api/client/tenants/{id}/resend-invite - Resend invitation email"""
    
    @pytest.fixture
    def invited_tenant(self, client_auth):
        """Create a tenant in INVITED status"""
        test_email = f"test_resend_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/client/tenants/invite",
            headers=client_auth["headers"],
            json={
                "email": test_email,
                "full_name": "Resend Test Tenant",
                "base_url": BASE_URL
            }
        )
        
        if response.status_code == 403:
            pytest.skip("User does not have CLIENT_ADMIN role")
        
        if response.status_code == 200:
            return response.json()["tenant_id"]
        pytest.skip("Could not create test tenant")
    
    def test_resend_invite_success(self, client_auth, invited_tenant):
        """Test resending invitation to a pending tenant"""
        response = requests.post(
            f"{BASE_URL}/api/client/tenants/{invited_tenant}/resend-invite",
            headers=client_auth["headers"],
            json={"base_url": BASE_URL}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        
        print(f"✓ Invitation resent to tenant {invited_tenant}")
    
    def test_resend_invite_invalid_tenant(self, client_auth):
        """Test resending to non-existent tenant returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/client/tenants/invalid-tenant-id/resend-invite",
            headers=client_auth["headers"],
            json={"base_url": BASE_URL}
        )
        
        assert response.status_code == 404
        print("✓ Invalid tenant correctly rejected with 404")


class TestTenantManagementIntegration:
    """Integration tests for full tenant management workflow"""
    
    def test_full_tenant_lifecycle(self, client_auth, properties):
        """Test complete tenant lifecycle: invite -> assign -> unassign -> revoke"""
        if not properties:
            pytest.skip("No properties available for testing")
        
        test_email = f"test_lifecycle_{uuid.uuid4().hex[:8]}@example.com"
        property_id = properties[0]["property_id"]
        
        # Step 1: Invite tenant
        invite_response = requests.post(
            f"{BASE_URL}/api/client/tenants/invite",
            headers=client_auth["headers"],
            json={
                "email": test_email,
                "full_name": "Lifecycle Test Tenant",
                "base_url": BASE_URL
            }
        )
        
        if invite_response.status_code == 403:
            pytest.skip("User does not have CLIENT_ADMIN role")
        
        assert invite_response.status_code == 200
        tenant_id = invite_response.json()["tenant_id"]
        print(f"✓ Step 1: Tenant invited - {tenant_id}")
        
        # Step 2: Assign property
        assign_response = requests.post(
            f"{BASE_URL}/api/client/tenants/{tenant_id}/assign-property",
            headers=client_auth["headers"],
            json={"property_id": property_id}
        )
        assert assign_response.status_code == 200
        print(f"✓ Step 2: Property assigned - {property_id}")
        
        # Step 3: Verify assignment in tenant list
        list_response = requests.get(f"{BASE_URL}/api/client/tenants", headers=client_auth["headers"])
        assert list_response.status_code == 200
        tenants = list_response.json()["tenants"]
        tenant = next((t for t in tenants if t["portal_user_id"] == tenant_id), None)
        assert tenant is not None
        assert property_id in tenant["assigned_properties"]
        print(f"✓ Step 3: Assignment verified in tenant list")
        
        # Step 4: Unassign property
        unassign_response = requests.delete(
            f"{BASE_URL}/api/client/tenants/{tenant_id}/unassign-property/{property_id}",
            headers=client_auth["headers"]
        )
        assert unassign_response.status_code == 200
        print(f"✓ Step 4: Property unassigned")
        
        # Step 5: Resend invite
        resend_response = requests.post(
            f"{BASE_URL}/api/client/tenants/{tenant_id}/resend-invite",
            headers=client_auth["headers"],
            json={"base_url": BASE_URL}
        )
        assert resend_response.status_code == 200
        print(f"✓ Step 5: Invitation resent")
        
        # Step 6: Revoke access
        revoke_response = requests.delete(
            f"{BASE_URL}/api/client/tenants/{tenant_id}",
            headers=client_auth["headers"]
        )
        assert revoke_response.status_code == 200
        print(f"✓ Step 6: Tenant access revoked")
        
        # Step 7: Verify tenant is disabled
        list_response2 = requests.get(f"{BASE_URL}/api/client/tenants", headers=client_auth["headers"])
        tenants2 = list_response2.json()["tenants"]
        tenant2 = next((t for t in tenants2 if t["portal_user_id"] == tenant_id), None)
        assert tenant2 is not None
        assert tenant2["status"] == "DISABLED"
        print(f"✓ Step 7: Tenant status verified as DISABLED")
        
        print(f"\n✓ Full tenant lifecycle test completed successfully!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
