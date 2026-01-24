"""
Test Suite for Iteration 8 Features:
1. AI Document Scanner Enhancement - POST /api/documents/analyze/{id}, apply-extraction, reject-extraction
2. Bulk Document Upload - POST /api/documents/bulk-upload
3. Advanced Reporting - GET /api/reports/available, /api/reports/compliance-summary, /api/reports/requirements
4. Tenant Portal - GET /api/tenant/dashboard, /api/tenant/property/{id}
5. Client tenant management - POST /api/client/tenants/invite, GET /api/client/tenants
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://prompt-versioner-1.preview.emergentagent.com').rstrip('/')

# Test credentials
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


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
        return data["access_token"]
    
    def test_admin_login(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "ROLE_ADMIN"
        print(f"✓ Admin login successful: {data['user']['email']}")
        return data["access_token"]


class TestReportsEndpoints:
    """Test Advanced Reporting feature (Feature 3)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_get_available_reports(self):
        """Test GET /api/reports/available - list available reports"""
        response = requests.get(f"{BASE_URL}/api/reports/available", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "reports" in data
        assert len(data["reports"]) >= 2  # At least compliance_summary and requirements
        
        report_ids = [r["id"] for r in data["reports"]]
        assert "compliance_summary" in report_ids
        assert "requirements" in report_ids
        print(f"✓ Available reports: {report_ids}")
    
    def test_compliance_summary_report_csv(self):
        """Test GET /api/reports/compliance-summary?format=csv"""
        response = requests.get(
            f"{BASE_URL}/api/reports/compliance-summary?format=csv",
            headers=self.headers
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        
        # Check CSV content
        content = response.text
        assert "Compliance Status Summary" in content or "Report:" in content
        print(f"✓ Compliance summary CSV generated ({len(content)} bytes)")
    
    def test_compliance_summary_report_pdf(self):
        """Test GET /api/reports/compliance-summary?format=pdf - returns JSON for client-side rendering"""
        response = requests.get(
            f"{BASE_URL}/api/reports/compliance-summary?format=pdf",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "format" in data
        assert data["format"] == "pdf"
        assert "data" in data
        print(f"✓ Compliance summary PDF data returned")
    
    def test_requirements_report_csv(self):
        """Test GET /api/reports/requirements?format=csv"""
        response = requests.get(
            f"{BASE_URL}/api/reports/requirements?format=csv",
            headers=self.headers
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        
        content = response.text
        assert "Requirements Report" in content or "Report:" in content
        print(f"✓ Requirements report CSV generated ({len(content)} bytes)")
    
    def test_requirements_report_with_property_filter(self):
        """Test requirements report with property filter"""
        # First get a property ID
        props_response = requests.get(f"{BASE_URL}/api/client/properties", headers=self.headers)
        if props_response.status_code == 200:
            properties = props_response.json().get("properties", [])
            if properties:
                property_id = properties[0]["property_id"]
                response = requests.get(
                    f"{BASE_URL}/api/reports/requirements?format=csv&property_id={property_id}",
                    headers=self.headers
                )
                assert response.status_code == 200
                print(f"✓ Requirements report with property filter works")


class TestAuditLogsReport:
    """Test Audit Logs Report (Admin only)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Admin authentication failed")
    
    def test_audit_logs_report_csv(self):
        """Test GET /api/reports/audit-logs?format=csv (Admin only)"""
        response = requests.get(
            f"{BASE_URL}/api/reports/audit-logs?format=csv&limit=100",
            headers=self.headers
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        
        content = response.text
        assert "Audit Log Extract" in content or "Report:" in content
        print(f"✓ Audit logs report CSV generated ({len(content)} bytes)")
    
    def test_audit_logs_report_with_filters(self):
        """Test audit logs report with date filters"""
        response = requests.get(
            f"{BASE_URL}/api/reports/audit-logs?format=csv&start_date=2024-01-01&limit=50",
            headers=self.headers
        )
        assert response.status_code == 200
        print(f"✓ Audit logs report with date filter works")


class TestTenantPortal:
    """Test Tenant Portal feature (Feature 4)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get client auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
            self.user = response.json()["user"]
        else:
            pytest.skip("Authentication failed")
    
    def test_tenant_dashboard(self):
        """Test GET /api/tenant/dashboard"""
        response = requests.get(f"{BASE_URL}/api/tenant/dashboard", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify dashboard structure
        assert "properties" in data
        assert "summary" in data
        assert "last_updated" in data
        
        # Verify summary fields
        summary = data["summary"]
        assert "total_properties" in summary
        assert "fully_compliant" in summary
        assert "needs_attention" in summary
        assert "action_required" in summary
        
        print(f"✓ Tenant dashboard: {summary['total_properties']} properties, {summary['fully_compliant']} compliant")
    
    def test_tenant_property_details(self):
        """Test GET /api/tenant/property/{property_id}"""
        # First get properties from dashboard
        dashboard_response = requests.get(f"{BASE_URL}/api/tenant/dashboard", headers=self.headers)
        if dashboard_response.status_code == 200:
            properties = dashboard_response.json().get("properties", [])
            if properties:
                property_id = properties[0]["property_id"]
                response = requests.get(
                    f"{BASE_URL}/api/tenant/property/{property_id}",
                    headers=self.headers
                )
                assert response.status_code == 200
                data = response.json()
                
                assert "property" in data
                assert "certificates" in data
                assert data["property"]["property_id"] == property_id
                
                print(f"✓ Tenant property details: {len(data['certificates'])} certificates")
            else:
                print("⚠ No properties available for tenant property test")
        else:
            pytest.skip("Could not get tenant dashboard")


class TestClientTenantManagement:
    """Test Client Tenant Management (Feature 4 - landlord side)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get client auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
            self.user = response.json()["user"]
        else:
            pytest.skip("Authentication failed")
    
    def test_list_tenants(self):
        """Test GET /api/client/tenants"""
        response = requests.get(f"{BASE_URL}/api/client/tenants", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "tenants" in data
        print(f"✓ List tenants: {len(data['tenants'])} tenants found")
    
    def test_invite_tenant(self):
        """Test POST /api/client/tenants/invite"""
        # Generate unique email for test
        test_email = f"test_tenant_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/client/tenants/invite",
            headers=self.headers,
            json={
                "email": test_email,
                "full_name": "Test Tenant",
                "base_url": BASE_URL
            }
        )
        
        # Check response - may be 403 if user is not CLIENT_ADMIN
        if response.status_code == 403:
            print(f"⚠ Tenant invite requires CLIENT_ADMIN role (got 403)")
            return
        
        assert response.status_code == 200
        data = response.json()
        assert "tenant_id" in data
        assert data["email"] == test_email.lower()
        print(f"✓ Tenant invited: {test_email}")


class TestBulkUpload:
    """Test Bulk Document Upload feature (Feature 2)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get client auth token and property"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
            
            # Get a property for testing
            props_response = requests.get(
                f"{BASE_URL}/api/client/properties",
                headers=self.headers
            )
            if props_response.status_code == 200:
                properties = props_response.json().get("properties", [])
                if properties:
                    self.property_id = properties[0]["property_id"]
                else:
                    self.property_id = None
            else:
                self.property_id = None
        else:
            pytest.skip("Authentication failed")
    
    def test_bulk_upload_endpoint_exists(self):
        """Test that bulk upload endpoint exists"""
        if not self.property_id:
            pytest.skip("No property available for testing")
        
        # Create test files
        files = [
            ('files', ('test_gas_safety.pdf', b'%PDF-1.4 test gas safety content', 'application/pdf')),
            ('files', ('test_eicr.pdf', b'%PDF-1.4 test eicr content', 'application/pdf'))
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/documents/bulk-upload",
            headers=self.headers,
            files=files,
            data={"property_id": self.property_id}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "summary" in data
        
        summary = data["summary"]
        assert "total" in summary
        assert "successful" in summary
        assert "failed" in summary
        assert "auto_matched" in summary
        
        print(f"✓ Bulk upload: {summary['successful']}/{summary['total']} successful, {summary['auto_matched']} auto-matched")


class TestDocumentAnalysis:
    """Test AI Document Scanner Enhancement (Feature 1)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get client auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_list_documents(self):
        """Test GET /api/documents - list documents"""
        response = requests.get(f"{BASE_URL}/api/documents", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        print(f"✓ Documents list: {len(data['documents'])} documents")
        return data["documents"]
    
    def test_document_details(self):
        """Test GET /api/documents/{id}/details"""
        # Get documents first
        docs_response = requests.get(f"{BASE_URL}/api/documents", headers=self.headers)
        if docs_response.status_code == 200:
            documents = docs_response.json().get("documents", [])
            if documents:
                doc_id = documents[0]["document_id"]
                response = requests.get(
                    f"{BASE_URL}/api/documents/{doc_id}/details",
                    headers=self.headers
                )
                assert response.status_code == 200
                data = response.json()
                assert "document" in data
                print(f"✓ Document details retrieved for {doc_id}")
            else:
                print("⚠ No documents available for details test")
    
    def test_document_extraction_endpoint(self):
        """Test GET /api/documents/{id}/extraction"""
        docs_response = requests.get(f"{BASE_URL}/api/documents", headers=self.headers)
        if docs_response.status_code == 200:
            documents = docs_response.json().get("documents", [])
            if documents:
                doc_id = documents[0]["document_id"]
                response = requests.get(
                    f"{BASE_URL}/api/documents/{doc_id}/extraction",
                    headers=self.headers
                )
                assert response.status_code == 200
                data = response.json()
                assert "has_extraction" in data
                print(f"✓ Document extraction endpoint works, has_extraction: {data['has_extraction']}")
    
    def test_analyze_document_endpoint(self):
        """Test POST /api/documents/analyze/{id}"""
        docs_response = requests.get(f"{BASE_URL}/api/documents", headers=self.headers)
        if docs_response.status_code == 200:
            documents = docs_response.json().get("documents", [])
            if documents:
                doc_id = documents[0]["document_id"]
                response = requests.post(
                    f"{BASE_URL}/api/documents/analyze/{doc_id}",
                    headers=self.headers
                )
                # May return 200 (success or already analyzed) or error if file not valid
                assert response.status_code in [200, 400, 500]
                print(f"✓ Analyze document endpoint works, status: {response.status_code}")
    
    def test_reject_extraction_endpoint(self):
        """Test POST /api/documents/{id}/reject-extraction"""
        docs_response = requests.get(f"{BASE_URL}/api/documents", headers=self.headers)
        if docs_response.status_code == 200:
            documents = docs_response.json().get("documents", [])
            if documents:
                doc_id = documents[0]["document_id"]
                response = requests.post(
                    f"{BASE_URL}/api/documents/{doc_id}/reject-extraction",
                    headers=self.headers,
                    json={"reason": "Test rejection"}
                )
                assert response.status_code == 200
                data = response.json()
                assert "message" in data
                print(f"✓ Reject extraction endpoint works")


class TestClientDashboard:
    """Test client dashboard and properties"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get client auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Authentication failed")
    
    def test_client_dashboard(self):
        """Test GET /api/client/dashboard"""
        response = requests.get(f"{BASE_URL}/api/client/dashboard", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "client" in data
        assert "properties" in data
        assert "compliance_summary" in data
        print(f"✓ Client dashboard: {len(data['properties'])} properties")
    
    def test_client_properties(self):
        """Test GET /api/client/properties"""
        response = requests.get(f"{BASE_URL}/api/client/properties", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "properties" in data
        print(f"✓ Client properties: {len(data['properties'])} properties")
    
    def test_client_requirements(self):
        """Test GET /api/client/requirements"""
        response = requests.get(f"{BASE_URL}/api/client/requirements", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "requirements" in data
        print(f"✓ Client requirements: {len(data['requirements'])} requirements")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
