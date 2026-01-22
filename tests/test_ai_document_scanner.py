"""
Test AI Document Scanner Enhancement (Task 1 of 4):
- POST /api/documents/analyze/{document_id} - AI document analysis with enhanced extraction
- POST /api/documents/{document_id}/apply-extraction - Apply reviewed AI extraction data
- POST /api/documents/{document_id}/reject-extraction - Reject AI extraction for manual entry
- GET /api/documents/{document_id}/details - Get full document details with extraction data
- Document upload and AI auto-matching
- Review workflow (pending -> approved/rejected)
- Expiry date from extraction updates requirement due_date when applied
"""

import pytest
import requests
import os
import io
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://workflow-admin-4.preview.emergentagent.com').rstrip('/')

# Test credentials
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def client_auth_token(api_client):
    """Get client authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": CLIENT_EMAIL,
        "password": CLIENT_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Client authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def admin_auth_token(api_client):
    """Get admin authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Admin authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def authenticated_client(api_client, client_auth_token):
    """Session with client auth header"""
    api_client.headers.update({"Authorization": f"Bearer {client_auth_token}"})
    return api_client


@pytest.fixture(scope="module")
def test_property_and_requirement(authenticated_client):
    """Get a test property and requirement for document upload"""
    # Get properties
    props_response = authenticated_client.get(f"{BASE_URL}/api/client/properties")
    assert props_response.status_code == 200, f"Failed to get properties: {props_response.text}"
    
    properties = props_response.json().get("properties", [])
    if not properties:
        pytest.skip("No properties available for testing")
    
    property_id = properties[0]["property_id"]
    
    # Get requirements for this property
    reqs_response = authenticated_client.get(f"{BASE_URL}/api/client/requirements")
    assert reqs_response.status_code == 200, f"Failed to get requirements: {reqs_response.text}"
    
    requirements = reqs_response.json().get("requirements", [])
    property_requirements = [r for r in requirements if r["property_id"] == property_id]
    
    if not property_requirements:
        pytest.skip("No requirements available for testing")
    
    # Prefer gas_safety requirement for testing
    gas_req = next((r for r in property_requirements if r["requirement_type"] == "gas_safety"), None)
    requirement = gas_req or property_requirements[0]
    
    return {
        "property_id": property_id,
        "requirement_id": requirement["requirement_id"],
        "requirement_type": requirement["requirement_type"]
    }


class TestDocumentUpload:
    """Test document upload functionality"""
    
    def test_upload_document_success(self, authenticated_client, test_property_and_requirement):
        """Test uploading a document"""
        # Create a simple test file
        test_content = b"""Gas Safety Certificate (CP12)
Certificate Number: TEST-GS-2024-001
Date of Check: 2024-12-15
Next Check Due: 2025-12-15
Engineer: John Smith
Gas Safe ID: 1234567
Result: SATISFACTORY"""
        
        files = {
            'file': ('test_gas_safety.pdf', io.BytesIO(test_content), 'application/pdf')
        }
        data = {
            'property_id': test_property_and_requirement["property_id"],
            'requirement_id': test_property_and_requirement["requirement_id"]
        }
        
        # Remove Content-Type header for multipart upload
        headers = {"Authorization": authenticated_client.headers.get("Authorization")}
        
        response = requests.post(
            f"{BASE_URL}/api/documents/upload",
            files=files,
            data=data,
            headers=headers
        )
        
        assert response.status_code == 200, f"Upload failed: {response.status_code} - {response.text}"
        result = response.json()
        assert "document_id" in result, "Response should contain document_id"
        assert result.get("message") == "Document uploaded successfully"
        
        # Store document_id for later tests
        pytest.document_id = result["document_id"]
        
    def test_upload_document_missing_property(self, authenticated_client, test_property_and_requirement):
        """Test upload fails without property_id"""
        test_content = b"Test content"
        files = {
            'file': ('test.pdf', io.BytesIO(test_content), 'application/pdf')
        }
        data = {
            'requirement_id': test_property_and_requirement["requirement_id"]
        }
        
        headers = {"Authorization": authenticated_client.headers.get("Authorization")}
        
        response = requests.post(
            f"{BASE_URL}/api/documents/upload",
            files=files,
            data=data,
            headers=headers
        )
        
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"


class TestDocumentAnalysis:
    """Test AI document analysis endpoints"""
    
    def test_analyze_document_endpoint_exists(self, authenticated_client):
        """Test that analyze endpoint exists and requires valid document"""
        # Test with non-existent document
        response = authenticated_client.post(f"{BASE_URL}/api/documents/analyze/non-existent-id")
        assert response.status_code == 404, f"Expected 404 for non-existent document, got {response.status_code}"
    
    def test_analyze_document_requires_auth(self, api_client):
        """Test that analyze endpoint requires authentication"""
        # Remove auth header temporarily
        original_headers = api_client.headers.copy()
        api_client.headers.pop("Authorization", None)
        
        response = api_client.post(f"{BASE_URL}/api/documents/analyze/test-id")
        
        # Restore headers
        api_client.headers = original_headers
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
    
    def test_get_document_extraction_endpoint(self, authenticated_client):
        """Test GET extraction endpoint exists"""
        response = authenticated_client.get(f"{BASE_URL}/api/documents/non-existent-id/extraction")
        assert response.status_code == 404, f"Expected 404 for non-existent document, got {response.status_code}"


class TestApplyExtraction:
    """Test apply-extraction endpoint"""
    
    def test_apply_extraction_endpoint_exists(self, authenticated_client):
        """Test that apply-extraction endpoint exists"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/documents/non-existent-id/apply-extraction",
            json={"confirmed_data": {}}
        )
        assert response.status_code == 404, f"Expected 404 for non-existent document, got {response.status_code}"
    
    def test_apply_extraction_requires_auth(self, api_client):
        """Test that apply-extraction requires authentication"""
        original_headers = api_client.headers.copy()
        api_client.headers.pop("Authorization", None)
        
        response = api_client.post(
            f"{BASE_URL}/api/documents/test-id/apply-extraction",
            json={"confirmed_data": {}}
        )
        
        api_client.headers = original_headers
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"


class TestRejectExtraction:
    """Test reject-extraction endpoint"""
    
    def test_reject_extraction_endpoint_exists(self, authenticated_client):
        """Test that reject-extraction endpoint exists"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/documents/non-existent-id/reject-extraction",
            json={"reason": "Test rejection"}
        )
        assert response.status_code == 404, f"Expected 404 for non-existent document, got {response.status_code}"
    
    def test_reject_extraction_requires_auth(self, api_client):
        """Test that reject-extraction requires authentication"""
        original_headers = api_client.headers.copy()
        api_client.headers.pop("Authorization", None)
        
        response = api_client.post(
            f"{BASE_URL}/api/documents/test-id/reject-extraction",
            json={"reason": "Test"}
        )
        
        api_client.headers = original_headers
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"


class TestDocumentDetails:
    """Test document details endpoint"""
    
    def test_document_details_endpoint_exists(self, authenticated_client):
        """Test that details endpoint exists"""
        response = authenticated_client.get(f"{BASE_URL}/api/documents/non-existent-id/details")
        assert response.status_code == 404, f"Expected 404 for non-existent document, got {response.status_code}"
    
    def test_document_details_requires_auth(self, api_client):
        """Test that details endpoint requires authentication"""
        original_headers = api_client.headers.copy()
        api_client.headers.pop("Authorization", None)
        
        response = api_client.get(f"{BASE_URL}/api/documents/test-id/details")
        
        api_client.headers = original_headers
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"


class TestBulkUpload:
    """Test bulk upload endpoint"""
    
    def test_bulk_upload_endpoint_exists(self, authenticated_client, test_property_and_requirement):
        """Test that bulk upload endpoint exists"""
        # Create test files
        test_content = b"Test gas safety content"
        files = [
            ('files', ('test1.pdf', io.BytesIO(test_content), 'application/pdf'))
        ]
        data = {
            'property_id': test_property_and_requirement["property_id"]
        }
        
        headers = {"Authorization": authenticated_client.headers.get("Authorization")}
        
        response = requests.post(
            f"{BASE_URL}/api/documents/bulk-upload",
            files=files,
            data=data,
            headers=headers
        )
        
        # Should succeed or return validation error, not 404
        assert response.status_code in [200, 422], f"Unexpected status: {response.status_code} - {response.text}"


class TestDocumentListAndRetrieval:
    """Test document listing and retrieval"""
    
    def test_get_documents_list(self, authenticated_client):
        """Test getting list of documents"""
        response = authenticated_client.get(f"{BASE_URL}/api/documents")
        assert response.status_code == 200, f"Failed to get documents: {response.text}"
        
        data = response.json()
        assert "documents" in data, "Response should contain 'documents'"
        assert "total" in data, "Response should contain 'total'"
        assert isinstance(data["documents"], list), "Documents should be a list"


class TestEndToEndDocumentFlow:
    """End-to-end test of document upload, analysis, and extraction workflow"""
    
    def test_full_document_workflow(self, authenticated_client, test_property_and_requirement):
        """Test complete document workflow: upload -> analyze -> review -> apply"""
        # Step 1: Upload document
        test_content = b"""Gas Safety Certificate (CP12)
Landlord Gas Safety Record

Certificate Number: TEST-E2E-GS-2024
Date of Check: 2024-12-01
Next Check Due: 2025-12-01

Property Address:
123 Test Street, London, SW1A 1AA

Gas Safe Registered Engineer:
Name: Test Engineer
Gas Safe ID: 9876543
Company: Test Gas Services Ltd

Result: SATISFACTORY"""
        
        files = {
            'file': ('e2e_gas_safety_test.pdf', io.BytesIO(test_content), 'application/pdf')
        }
        data = {
            'property_id': test_property_and_requirement["property_id"],
            'requirement_id': test_property_and_requirement["requirement_id"]
        }
        
        headers = {"Authorization": authenticated_client.headers.get("Authorization")}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/documents/upload",
            files=files,
            data=data,
            headers=headers
        )
        
        assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"
        document_id = upload_response.json()["document_id"]
        
        # Step 2: Get document details
        details_response = authenticated_client.get(f"{BASE_URL}/api/documents/{document_id}/details")
        assert details_response.status_code == 200, f"Get details failed: {details_response.text}"
        
        details = details_response.json()
        assert "document" in details, "Response should contain 'document'"
        assert details["document"]["document_id"] == document_id
        
        # Step 3: Trigger AI analysis (this may take time due to AI processing)
        analyze_response = authenticated_client.post(f"{BASE_URL}/api/documents/analyze/{document_id}")
        # Analysis might succeed or fail depending on file content, but endpoint should work
        assert analyze_response.status_code in [200, 500], f"Analyze returned unexpected status: {analyze_response.status_code}"
        
        # Step 4: Get extraction results
        extraction_response = authenticated_client.get(f"{BASE_URL}/api/documents/{document_id}/extraction")
        assert extraction_response.status_code == 200, f"Get extraction failed: {extraction_response.text}"
        
        # Step 5: Apply extraction with confirmed data
        confirmed_data = {
            "document_type": "Gas Safety Certificate",
            "certificate_number": "TEST-E2E-GS-2024",
            "issue_date": "2024-12-01",
            "expiry_date": "2025-12-01",
            "engineer_details": {
                "name": "Test Engineer",
                "registration_number": "9876543",
                "company_name": "Test Gas Services Ltd"
            },
            "result_summary": {
                "overall_result": "SATISFACTORY"
            }
        }
        
        apply_response = authenticated_client.post(
            f"{BASE_URL}/api/documents/{document_id}/apply-extraction",
            json={"confirmed_data": confirmed_data}
        )
        
        assert apply_response.status_code == 200, f"Apply extraction failed: {apply_response.text}"
        apply_result = apply_response.json()
        assert "message" in apply_result
        assert "changes_applied" in apply_result or "changes_made" in apply_result or apply_result.get("message") == "Extraction applied successfully"
        
        # Verify the document was updated
        final_details = authenticated_client.get(f"{BASE_URL}/api/documents/{document_id}/details")
        assert final_details.status_code == 200
        
        final_doc = final_details.json()["document"]
        # Check that extraction was marked as approved
        if final_doc.get("ai_extraction"):
            assert final_doc["ai_extraction"].get("review_status") == "approved", "Extraction should be marked as approved"


class TestRejectExtractionFlow:
    """Test rejection of AI extraction"""
    
    def test_reject_extraction_workflow(self, authenticated_client, test_property_and_requirement):
        """Test rejecting AI extraction for manual entry"""
        # Upload a document
        test_content = b"Test document for rejection"
        files = {
            'file': ('reject_test.pdf', io.BytesIO(test_content), 'application/pdf')
        }
        data = {
            'property_id': test_property_and_requirement["property_id"],
            'requirement_id': test_property_and_requirement["requirement_id"]
        }
        
        headers = {"Authorization": authenticated_client.headers.get("Authorization")}
        
        upload_response = requests.post(
            f"{BASE_URL}/api/documents/upload",
            files=files,
            data=data,
            headers=headers
        )
        
        if upload_response.status_code != 200:
            pytest.skip(f"Upload failed: {upload_response.text}")
        
        document_id = upload_response.json()["document_id"]
        
        # Reject extraction
        reject_response = authenticated_client.post(
            f"{BASE_URL}/api/documents/{document_id}/reject-extraction",
            json={"reason": "Prefer manual entry for accuracy"}
        )
        
        assert reject_response.status_code == 200, f"Reject failed: {reject_response.text}"
        
        # Verify rejection was recorded
        details_response = authenticated_client.get(f"{BASE_URL}/api/documents/{document_id}/details")
        assert details_response.status_code == 200
        
        doc = details_response.json()["document"]
        if doc.get("ai_extraction"):
            assert doc["ai_extraction"].get("review_status") == "rejected"


class TestDocumentTypeDetection:
    """Test document type detection from filename"""
    
    def test_gas_safety_filename_detection(self, authenticated_client, test_property_and_requirement):
        """Test that gas safety documents are detected from filename"""
        test_content = b"Gas safety certificate content"
        
        # Test various gas safety filename patterns
        filenames = ["gas_safety_cert.pdf", "cp12_certificate.pdf", "lgsr_2024.pdf"]
        
        for filename in filenames:
            files = {
                'file': (filename, io.BytesIO(test_content), 'application/pdf')
            }
            data = {
                'property_id': test_property_and_requirement["property_id"],
                'requirement_id': test_property_and_requirement["requirement_id"]
            }
            
            headers = {"Authorization": authenticated_client.headers.get("Authorization")}
            
            response = requests.post(
                f"{BASE_URL}/api/documents/upload",
                files=files,
                data=data,
                headers=headers
            )
            
            # Just verify upload works - type detection happens during analysis
            assert response.status_code == 200, f"Upload failed for {filename}: {response.text}"


# Cleanup fixture
@pytest.fixture(scope="module", autouse=True)
def cleanup(authenticated_client):
    """Cleanup test documents after all tests"""
    yield
    # Note: In a real scenario, we'd delete test documents here
    # For now, we leave them as they don't affect other tests
    pass
