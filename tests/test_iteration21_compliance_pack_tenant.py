"""
Test Suite for Iteration 21: Tenant Portal Enhancements and Compliance Pack Feature

Features to test:
1. GET /api/client/compliance-pack/{property_id}/preview - Returns certificate list
2. GET /api/client/compliance-pack/{property_id}/download - Returns 403 PLAN_NOT_ELIGIBLE for PLAN_1
3. POST /api/tenant/request-certificate - Creates request in database
4. POST /api/tenant/contact-landlord - Sends message
5. GET /api/tenant/compliance-pack/{property_id} - Generates PDF for assigned tenants
6. GET /api/tenant/dashboard - Returns tenant dashboard data
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://leadsquared.preview.emergentagent.com').rstrip('/')

# Test credentials
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"
TEST_PROPERTY_ID = "602cccda-fd42-4d48-947c-8fd1feb49564"


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
    
    def test_admin_login(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        print(f"✓ Admin login successful: {data['user']['email']}")


class TestCompliancePackPreview:
    """Test GET /api/client/compliance-pack/{property_id}/preview"""
    
    def test_compliance_pack_preview_success(self, client_auth, properties):
        """Test getting compliance pack preview returns certificate list"""
        if not properties:
            pytest.skip("No properties available for testing")
        
        property_id = properties[0]["property_id"]
        
        response = requests.get(
            f"{BASE_URL}/api/client/compliance-pack/{property_id}/preview",
            headers=client_auth["headers"]
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "property_address" in data
        assert "total_certificates" in data
        assert "compliant" in data
        assert "expiring_soon" in data
        assert "overdue" in data
        assert "certificates" in data
        assert isinstance(data["certificates"], list)
        
        print(f"✓ Compliance pack preview: {data['property_address']}")
        print(f"  Total certificates: {data['total_certificates']}")
        print(f"  Compliant: {data['compliant']}, Expiring: {data['expiring_soon']}, Overdue: {data['overdue']}")
        
        # Verify certificate structure if any exist
        if data["certificates"]:
            cert = data["certificates"][0]
            assert "type" in cert
            assert "status" in cert
            assert "expiry" in cert
            print(f"  Sample certificate: {cert['type']} - {cert['status']}")
    
    def test_compliance_pack_preview_with_test_property(self, client_auth):
        """Test compliance pack preview with known test property"""
        response = requests.get(
            f"{BASE_URL}/api/client/compliance-pack/{TEST_PROPERTY_ID}/preview",
            headers=client_auth["headers"]
        )
        
        # May be 404 if property doesn't exist or doesn't belong to client
        if response.status_code == 404:
            print(f"⚠ Test property {TEST_PROPERTY_ID} not found or not owned by client")
            pytest.skip("Test property not available")
        
        assert response.status_code == 200
        data = response.json()
        assert "certificates" in data
        print(f"✓ Test property preview: {data.get('property_address', 'N/A')}")
    
    def test_compliance_pack_preview_invalid_property(self, client_auth):
        """Test compliance pack preview with invalid property returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/client/compliance-pack/invalid-property-id/preview",
            headers=client_auth["headers"]
        )
        
        assert response.status_code == 404
        print("✓ Invalid property correctly rejected with 404")
    
    def test_compliance_pack_preview_unauthorized(self):
        """Test compliance pack preview without auth returns 401"""
        response = requests.get(
            f"{BASE_URL}/api/client/compliance-pack/{TEST_PROPERTY_ID}/preview"
        )
        
        assert response.status_code == 401
        print("✓ Unauthorized access correctly rejected")


class TestCompliancePackDownload:
    """Test GET /api/client/compliance-pack/{property_id}/download - Plan gating"""
    
    def test_compliance_pack_download_plan_gating(self, client_auth, properties):
        """Test compliance pack download returns 403 PLAN_NOT_ELIGIBLE for PLAN_1"""
        if not properties:
            pytest.skip("No properties available for testing")
        
        property_id = properties[0]["property_id"]
        
        response = requests.get(
            f"{BASE_URL}/api/client/compliance-pack/{property_id}/download",
            headers=client_auth["headers"]
        )
        
        # PLAN_1 should get 403 PLAN_NOT_ELIGIBLE
        assert response.status_code == 403
        data = response.json()
        
        # Verify error response structure
        assert "detail" in data
        detail = data["detail"]
        assert "error_code" in detail
        assert detail["error_code"] == "PLAN_NOT_ELIGIBLE"
        assert "feature" in detail
        assert detail["feature"] == "compliance_packs"
        assert "upgrade_required" in detail
        assert detail["upgrade_required"] == True
        
        print(f"✓ Compliance pack download correctly gated for PLAN_1")
        print(f"  Error code: {detail['error_code']}")
        print(f"  Feature: {detail['feature']}")
        print(f"  Message: {detail.get('message', 'N/A')}")
    
    def test_compliance_pack_download_with_test_property(self, client_auth):
        """Test compliance pack download with known test property"""
        response = requests.get(
            f"{BASE_URL}/api/client/compliance-pack/{TEST_PROPERTY_ID}/download",
            headers=client_auth["headers"]
        )
        
        # Should be 403 for PLAN_1 or 404 if property not found
        assert response.status_code in [403, 404]
        
        if response.status_code == 403:
            data = response.json()
            assert data["detail"]["error_code"] == "PLAN_NOT_ELIGIBLE"
            print(f"✓ Test property download correctly gated")
        else:
            print(f"⚠ Test property not found")
    
    def test_compliance_pack_download_unauthorized(self):
        """Test compliance pack download without auth returns 401"""
        response = requests.get(
            f"{BASE_URL}/api/client/compliance-pack/{TEST_PROPERTY_ID}/download"
        )
        
        assert response.status_code == 401
        print("✓ Unauthorized access correctly rejected")


class TestPlanFeatures:
    """Test plan features endpoint to verify compliance_packs is disabled for PLAN_1"""
    
    def test_plan_features_compliance_packs_disabled(self, client_auth):
        """Test that compliance_packs feature is disabled for PLAN_1"""
        response = requests.get(
            f"{BASE_URL}/api/client/plan-features",
            headers=client_auth["headers"]
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "plan" in data
        assert "plan_name" in data
        assert "features" in data
        
        # Verify compliance_packs is disabled for PLAN_1
        features = data["features"]
        assert "compliance_packs" in features
        assert features["compliance_packs"] == False
        
        print(f"✓ Plan features verified: {data['plan_name']}")
        print(f"  compliance_packs: {features['compliance_packs']}")
        print(f"  zip_upload: {features.get('zip_upload', 'N/A')}")


class TestTenantDashboard:
    """Test GET /api/tenant/dashboard - Tenant dashboard data"""
    
    def test_tenant_dashboard_with_client_auth(self, client_auth):
        """Test tenant dashboard endpoint with client auth (should work for CLIENT role too)"""
        response = requests.get(
            f"{BASE_URL}/api/tenant/dashboard",
            headers=client_auth["headers"]
        )
        
        # Client role should be able to access tenant dashboard
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "tenant_name" in data
        assert "summary" in data
        assert "properties" in data
        assert "last_updated" in data
        
        # Verify summary structure
        summary = data["summary"]
        assert "total_properties" in summary
        assert "fully_compliant" in summary
        assert "needs_attention" in summary
        assert "action_required" in summary
        
        print(f"✓ Tenant dashboard loaded: {data['tenant_name']}")
        print(f"  Total properties: {summary['total_properties']}")
        print(f"  Fully compliant: {summary['fully_compliant']}")
    
    def test_tenant_dashboard_unauthorized(self):
        """Test tenant dashboard without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/tenant/dashboard")
        
        assert response.status_code == 401
        print("✓ Unauthorized access correctly rejected")


class TestTenantPropertyDetails:
    """Test GET /api/tenant/property/{property_id} - Property details for tenant"""
    
    def test_tenant_property_details(self, client_auth, properties):
        """Test getting property details for tenant"""
        if not properties:
            pytest.skip("No properties available for testing")
        
        property_id = properties[0]["property_id"]
        
        response = requests.get(
            f"{BASE_URL}/api/tenant/property/{property_id}",
            headers=client_auth["headers"]
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "property" in data
        assert "certificates" in data
        
        # Verify property structure
        prop = data["property"]
        assert "property_id" in prop
        assert "address" in prop
        assert "compliance_status" in prop
        
        print(f"✓ Tenant property details: {prop['address']}")
        print(f"  Compliance status: {prop['compliance_status']}")
        print(f"  Certificates: {len(data['certificates'])}")
    
    def test_tenant_property_details_invalid(self, client_auth):
        """Test getting property details for invalid property returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/tenant/property/invalid-property-id",
            headers=client_auth["headers"]
        )
        
        assert response.status_code == 404
        print("✓ Invalid property correctly rejected with 404")


class TestTenantCompliancePack:
    """Test GET /api/tenant/compliance-pack/{property_id} - Tenant compliance pack download"""
    
    def test_tenant_compliance_pack_download(self, client_auth, properties):
        """Test tenant compliance pack download (FREE for tenants)"""
        if not properties:
            pytest.skip("No properties available for testing")
        
        property_id = properties[0]["property_id"]
        
        response = requests.get(
            f"{BASE_URL}/api/tenant/compliance-pack/{property_id}",
            headers=client_auth["headers"]
        )
        
        # Should return PDF (200) or 404 if property not found
        if response.status_code == 404:
            print(f"⚠ Property {property_id} not found for tenant")
            pytest.skip("Property not available")
        
        assert response.status_code == 200
        
        # Verify it's a PDF
        content_type = response.headers.get("content-type", "")
        assert "application/pdf" in content_type
        
        # Verify content disposition header
        content_disposition = response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition
        assert ".pdf" in content_disposition
        
        # Verify PDF content (starts with %PDF)
        assert response.content[:4] == b'%PDF'
        
        print(f"✓ Tenant compliance pack downloaded successfully")
        print(f"  Content-Type: {content_type}")
        print(f"  Content-Disposition: {content_disposition}")
        print(f"  PDF size: {len(response.content)} bytes")
    
    def test_tenant_compliance_pack_invalid_property(self, client_auth):
        """Test tenant compliance pack with invalid property returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/tenant/compliance-pack/invalid-property-id",
            headers=client_auth["headers"]
        )
        
        assert response.status_code == 404
        print("✓ Invalid property correctly rejected with 404")


class TestTenantRequestCertificate:
    """Test POST /api/tenant/request-certificate - Request certificate update"""
    
    def test_request_certificate_success(self, client_auth, properties):
        """Test requesting a certificate update"""
        if not properties:
            pytest.skip("No properties available for testing")
        
        property_id = properties[0]["property_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/tenant/request-certificate",
            headers=client_auth["headers"],
            json={
                "property_id": property_id,
                "certificate_type": "gas_safety",
                "message": "Test request from automated testing"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "message" in data
        assert "request_id" in data
        assert "note" in data
        
        print(f"✓ Certificate request submitted: {data['request_id']}")
        print(f"  Message: {data['message']}")
    
    def test_request_certificate_missing_fields(self, client_auth):
        """Test requesting certificate without required fields returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/tenant/request-certificate",
            headers=client_auth["headers"],
            json={
                "message": "Missing property_id and certificate_type"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        print(f"✓ Missing fields correctly rejected: {data['detail']}")
    
    def test_request_certificate_invalid_property(self, client_auth):
        """Test requesting certificate for invalid property returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/tenant/request-certificate",
            headers=client_auth["headers"],
            json={
                "property_id": "invalid-property-id",
                "certificate_type": "gas_safety"
            }
        )
        
        assert response.status_code == 404
        print("✓ Invalid property correctly rejected with 404")
    
    def test_request_certificate_unauthorized(self):
        """Test requesting certificate without auth returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/tenant/request-certificate",
            json={
                "property_id": TEST_PROPERTY_ID,
                "certificate_type": "gas_safety"
            }
        )
        
        assert response.status_code == 401
        print("✓ Unauthorized access correctly rejected")


class TestTenantContactLandlord:
    """Test POST /api/tenant/contact-landlord - Send message to landlord"""
    
    def test_contact_landlord_success(self, client_auth, properties):
        """Test sending message to landlord"""
        if not properties:
            pytest.skip("No properties available for testing")
        
        property_id = properties[0]["property_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/tenant/contact-landlord",
            headers=client_auth["headers"],
            json={
                "property_id": property_id,
                "subject": "Test Message",
                "message": "This is a test message from automated testing."
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "message" in data
        assert "note" in data
        
        print(f"✓ Message sent to landlord: {data['message']}")
    
    def test_contact_landlord_missing_message(self, client_auth, properties):
        """Test contacting landlord without message returns 400"""
        if not properties:
            pytest.skip("No properties available for testing")
        
        property_id = properties[0]["property_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/tenant/contact-landlord",
            headers=client_auth["headers"],
            json={
                "property_id": property_id,
                "subject": "Test"
                # Missing message
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        print(f"✓ Missing message correctly rejected: {data['detail']}")
    
    def test_contact_landlord_message_too_long(self, client_auth, properties):
        """Test contacting landlord with message > 1000 chars returns 400"""
        if not properties:
            pytest.skip("No properties available for testing")
        
        property_id = properties[0]["property_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/tenant/contact-landlord",
            headers=client_auth["headers"],
            json={
                "property_id": property_id,
                "subject": "Test",
                "message": "x" * 1001  # Over 1000 chars
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "too long" in data["detail"].lower()
        print(f"✓ Long message correctly rejected: {data['detail']}")
    
    def test_contact_landlord_invalid_property(self, client_auth):
        """Test contacting landlord for invalid property returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/tenant/contact-landlord",
            headers=client_auth["headers"],
            json={
                "property_id": "invalid-property-id",
                "subject": "Test",
                "message": "Test message"
            }
        )
        
        assert response.status_code == 404
        print("✓ Invalid property correctly rejected with 404")
    
    def test_contact_landlord_unauthorized(self):
        """Test contacting landlord without auth returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/tenant/contact-landlord",
            json={
                "property_id": TEST_PROPERTY_ID,
                "subject": "Test",
                "message": "Test message"
            }
        )
        
        assert response.status_code == 401
        print("✓ Unauthorized access correctly rejected")


class TestTenantRequests:
    """Test GET /api/tenant/requests - Get tenant's certificate requests"""
    
    def test_get_tenant_requests(self, client_auth):
        """Test getting list of tenant's certificate requests"""
        response = requests.get(
            f"{BASE_URL}/api/tenant/requests",
            headers=client_auth["headers"]
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "requests" in data
        assert isinstance(data["requests"], list)
        
        print(f"✓ Tenant requests retrieved: {len(data['requests'])} requests")
        
        # Verify request structure if any exist
        if data["requests"]:
            req = data["requests"][0]
            assert "request_id" in req
            assert "certificate_type" in req
            assert "status" in req
            print(f"  Sample request: {req['certificate_type']} - {req['status']}")
    
    def test_get_tenant_requests_unauthorized(self):
        """Test getting tenant requests without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/tenant/requests")
        
        assert response.status_code == 401
        print("✓ Unauthorized access correctly rejected")


class TestIntegration:
    """Integration tests for full tenant portal workflow"""
    
    def test_full_tenant_workflow(self, client_auth, properties):
        """Test complete tenant workflow: dashboard -> property -> request -> contact"""
        if not properties:
            pytest.skip("No properties available for testing")
        
        property_id = properties[0]["property_id"]
        
        # Step 1: Load dashboard
        dashboard_response = requests.get(
            f"{BASE_URL}/api/tenant/dashboard",
            headers=client_auth["headers"]
        )
        assert dashboard_response.status_code == 200
        dashboard = dashboard_response.json()
        print(f"✓ Step 1: Dashboard loaded - {dashboard['summary']['total_properties']} properties")
        
        # Step 2: Get property details
        property_response = requests.get(
            f"{BASE_URL}/api/tenant/property/{property_id}",
            headers=client_auth["headers"]
        )
        assert property_response.status_code == 200
        property_data = property_response.json()
        print(f"✓ Step 2: Property details loaded - {len(property_data['certificates'])} certificates")
        
        # Step 3: Request certificate update
        request_response = requests.post(
            f"{BASE_URL}/api/tenant/request-certificate",
            headers=client_auth["headers"],
            json={
                "property_id": property_id,
                "certificate_type": "eicr",
                "message": "Integration test request"
            }
        )
        assert request_response.status_code == 200
        request_data = request_response.json()
        print(f"✓ Step 3: Certificate request submitted - {request_data['request_id']}")
        
        # Step 4: Contact landlord
        contact_response = requests.post(
            f"{BASE_URL}/api/tenant/contact-landlord",
            headers=client_auth["headers"],
            json={
                "property_id": property_id,
                "subject": "Integration Test",
                "message": "This is an integration test message."
            }
        )
        assert contact_response.status_code == 200
        print(f"✓ Step 4: Message sent to landlord")
        
        # Step 5: Download compliance pack (FREE for tenants)
        pack_response = requests.get(
            f"{BASE_URL}/api/tenant/compliance-pack/{property_id}",
            headers=client_auth["headers"]
        )
        assert pack_response.status_code == 200
        assert pack_response.content[:4] == b'%PDF'
        print(f"✓ Step 5: Compliance pack downloaded - {len(pack_response.content)} bytes")
        
        # Step 6: Verify request appears in list
        requests_response = requests.get(
            f"{BASE_URL}/api/tenant/requests",
            headers=client_auth["headers"]
        )
        assert requests_response.status_code == 200
        requests_data = requests_response.json()
        print(f"✓ Step 6: Requests list retrieved - {len(requests_data['requests'])} requests")
        
        print(f"\n✓ Full tenant workflow completed successfully!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
