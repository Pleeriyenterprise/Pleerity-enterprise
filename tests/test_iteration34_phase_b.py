"""
Phase B Document Quality Testing - Iteration 34
Tests real PDF/DOCX generation using reportlab and python-docx.

Features tested:
- Document generation creates real PDF files (should start with %PDF header)
- Document generation creates real DOCX files (should be valid ZIP/PK format)
- Input data snapshot is stored with each document version
- Document versions show DOCX/PDF format badges in UI
- Document status labels (DRAFT, FINAL, SUPERSEDED, REGENERATED) display correctly
- Generate documents endpoint creates versioned documents
- Download PDF endpoint returns valid PDF file
- Download DOCX endpoint returns valid DOCX file
"""
import pytest
import requests
import os
import zipfile
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_ORDER_ID = "ORD-2026-DBF85E"

# Admin credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin authentication token."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}"}


class TestHealthCheck:
    """Basic health check tests."""
    
    def test_api_health(self):
        """Test API is healthy."""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ API health check passed")


class TestDocumentVersionsAPI:
    """Test document versions API endpoints."""
    
    def test_get_order_documents(self, auth_headers):
        """Test getting document versions for an order."""
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/documents",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "order_id" in data
        assert "versions" in data
        assert "current_version" in data
        assert "total_versions" in data
        
        # Verify we have versions
        assert data["total_versions"] >= 1, "Should have at least 1 document version"
        print(f"✓ Order has {data['total_versions']} document versions")
        
        return data
    
    def test_document_version_has_required_fields(self, auth_headers):
        """Test that document versions have all required fields."""
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/documents",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for version in data["versions"]:
            # Required fields
            assert "version" in version
            assert "document_type" in version
            assert "status" in version
            assert "file_id_docx" in version
            assert "file_id_pdf" in version
            assert "filename_docx" in version
            assert "filename_pdf" in version
            assert "generated_at" in version
            
            # Verify status is valid
            valid_statuses = ["DRAFT", "REGENERATED", "FINAL", "SUPERSEDED", "VOID"]
            assert version["status"] in valid_statuses, f"Invalid status: {version['status']}"
            
            print(f"✓ Version {version['version']} has status: {version['status']}")
    
    def test_document_version_has_input_data_hash(self, auth_headers):
        """Test that document versions have input data hash for traceability."""
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/documents",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for version in data["versions"]:
            assert "input_data_hash" in version, "Version should have input_data_hash"
            assert version["input_data_hash"] is not None, "input_data_hash should not be None"
            assert len(version["input_data_hash"]) == 64, "input_data_hash should be SHA256 (64 chars)"
            print(f"✓ Version {version['version']} has input_data_hash: {version['input_data_hash'][:16]}...")


class TestInputDataSnapshot:
    """Test input data snapshotting feature."""
    
    def test_order_has_input_snapshot(self, auth_headers):
        """Test that order document versions have input snapshots."""
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        order = data.get("order", data)
        doc_versions = order.get("document_versions", [])
        
        assert len(doc_versions) >= 1, "Should have at least 1 document version"
        
        for version in doc_versions:
            # Check for input_snapshot
            if "input_snapshot" in version:
                snapshot = version["input_snapshot"]
                assert "snapshot_created_at" in snapshot, "Snapshot should have creation timestamp"
                assert "order_id" in snapshot, "Snapshot should have order_id"
                assert "service_code" in snapshot, "Snapshot should have service_code"
                assert "customer" in snapshot, "Snapshot should have customer data"
                assert "parameters" in snapshot, "Snapshot should have parameters"
                print(f"✓ Version {version['version']} has complete input snapshot")
            else:
                print(f"⚠ Version {version['version']} missing input_snapshot (may be older version)")


class TestRealPDFGeneration:
    """Test that PDF files are real PDFs (not mock text files)."""
    
    def test_download_pdf_returns_valid_pdf(self, auth_headers):
        """Test that downloaded PDF starts with %PDF header."""
        # Get document versions first
        versions_response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/documents",
            headers=auth_headers
        )
        assert versions_response.status_code == 200
        versions_data = versions_response.json()
        
        # Get the latest version
        current_version = versions_data.get("current_version")
        if not current_version:
            pytest.skip("No current document version available")
        
        version_num = current_version["version"]
        
        # Download PDF
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/documents/{version_num}/preview?format=pdf",
            headers=auth_headers
        )
        assert response.status_code == 200, f"PDF download failed: {response.status_code}"
        
        # Check content type
        content_type = response.headers.get("Content-Type", "")
        assert "application/pdf" in content_type, f"Expected PDF content type, got: {content_type}"
        
        # Check PDF header - real PDFs start with %PDF
        content = response.content
        assert len(content) > 100, f"PDF too small: {len(content)} bytes"
        
        pdf_header = content[:4]
        assert pdf_header == b'%PDF', f"PDF should start with %PDF, got: {pdf_header}"
        
        print(f"✓ PDF v{version_num} is a real PDF file ({len(content)} bytes)")
        print(f"  Header: {content[:20]}")
    
    def test_pdf_has_reasonable_size(self, auth_headers):
        """Test that PDF has reasonable file size (not just text)."""
        versions_response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/documents",
            headers=auth_headers
        )
        current_version = versions_response.json().get("current_version")
        if not current_version:
            pytest.skip("No current document version available")
        
        version_num = current_version["version"]
        
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/documents/{version_num}/preview?format=pdf",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Real PDFs generated by reportlab should be at least 1KB
        content_length = len(response.content)
        assert content_length > 1000, f"PDF too small for real PDF: {content_length} bytes"
        
        print(f"✓ PDF has reasonable size: {content_length} bytes")


class TestRealDOCXGeneration:
    """Test that DOCX files are real DOCX (ZIP format with proper structure)."""
    
    def test_download_docx_returns_valid_docx(self, auth_headers):
        """Test that downloaded DOCX is a valid ZIP file (DOCX format)."""
        versions_response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/documents",
            headers=auth_headers
        )
        assert versions_response.status_code == 200
        current_version = versions_response.json().get("current_version")
        if not current_version:
            pytest.skip("No current document version available")
        
        version_num = current_version["version"]
        
        # Download DOCX
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/documents/{version_num}/preview?format=docx",
            headers=auth_headers
        )
        assert response.status_code == 200, f"DOCX download failed: {response.status_code}"
        
        # Check content type
        content_type = response.headers.get("Content-Type", "")
        expected_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert expected_type in content_type, f"Expected DOCX content type, got: {content_type}"
        
        # Check DOCX header - DOCX files are ZIP files, start with PK
        content = response.content
        assert len(content) > 100, f"DOCX too small: {len(content)} bytes"
        
        docx_header = content[:2]
        assert docx_header == b'PK', f"DOCX should start with PK (ZIP format), got: {docx_header}"
        
        print(f"✓ DOCX v{version_num} is a real DOCX file ({len(content)} bytes)")
        print(f"  Header: {content[:10]}")
    
    def test_docx_is_valid_zip_with_word_content(self, auth_headers):
        """Test that DOCX is a valid ZIP containing Word document structure."""
        versions_response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/documents",
            headers=auth_headers
        )
        current_version = versions_response.json().get("current_version")
        if not current_version:
            pytest.skip("No current document version available")
        
        version_num = current_version["version"]
        
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/documents/{version_num}/preview?format=docx",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Try to open as ZIP
        try:
            docx_file = io.BytesIO(response.content)
            with zipfile.ZipFile(docx_file, 'r') as zf:
                file_list = zf.namelist()
                
                # Real DOCX files should contain these
                expected_files = ['[Content_Types].xml', 'word/document.xml']
                for expected in expected_files:
                    assert expected in file_list, f"DOCX missing required file: {expected}"
                
                print(f"✓ DOCX is valid ZIP with Word structure")
                print(f"  Contains: {len(file_list)} files")
                
        except zipfile.BadZipFile:
            pytest.fail("DOCX is not a valid ZIP file")
    
    def test_docx_has_reasonable_size(self, auth_headers):
        """Test that DOCX has reasonable file size."""
        versions_response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/documents",
            headers=auth_headers
        )
        current_version = versions_response.json().get("current_version")
        if not current_version:
            pytest.skip("No current document version available")
        
        version_num = current_version["version"]
        
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/documents/{version_num}/preview?format=docx",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Real DOCX files generated by python-docx should be at least 5KB
        content_length = len(response.content)
        assert content_length > 5000, f"DOCX too small for real DOCX: {content_length} bytes"
        
        print(f"✓ DOCX has reasonable size: {content_length} bytes")


class TestDocumentStatusLabels:
    """Test document status labels (DRAFT, FINAL, SUPERSEDED, REGENERATED)."""
    
    def test_version_status_labels(self, auth_headers):
        """Test that document versions have proper status labels."""
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/documents",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        versions = data["versions"]
        assert len(versions) >= 1
        
        # Check status distribution
        statuses = [v["status"] for v in versions]
        print(f"✓ Document statuses: {statuses}")
        
        # If there are multiple versions, older ones should be SUPERSEDED
        if len(versions) > 1:
            # Sort by version number
            sorted_versions = sorted(versions, key=lambda x: x["version"])
            
            # All but the latest should be SUPERSEDED (unless FINAL or VOID)
            for v in sorted_versions[:-1]:
                if v["status"] not in ["FINAL", "VOID"]:
                    assert v["status"] == "SUPERSEDED", f"Old version {v['version']} should be SUPERSEDED, got {v['status']}"
            
            print("✓ Older versions correctly marked as SUPERSEDED")
    
    def test_regenerated_status_on_regeneration(self, auth_headers):
        """Test that regenerated documents have REGENERATED status."""
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/documents",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for version in data["versions"]:
            if version.get("is_regeneration"):
                # Regenerated versions should have REGENERATED status (unless superseded)
                if version["status"] != "SUPERSEDED":
                    assert version["status"] == "REGENERATED", \
                        f"Regenerated version should have REGENERATED status, got {version['status']}"
                    print(f"✓ Version {version['version']} correctly marked as REGENERATED")


class TestGenerateDocumentsEndpoint:
    """Test the generate documents endpoint."""
    
    def test_generate_documents_creates_new_version(self, auth_headers):
        """Test that generate-documents endpoint creates a new version."""
        # Get current version count
        before_response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/documents",
            headers=auth_headers
        )
        assert before_response.status_code == 200
        before_count = before_response.json()["total_versions"]
        
        # Generate new documents
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/generate-documents",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Generate documents failed: {response.text}"
        
        data = response.json()
        assert data["success"] is True
        assert "version" in data
        
        new_version = data["version"]
        assert new_version["version"] == before_count + 1
        
        print(f"✓ Generated new document version {new_version['version']}")
        
        # Verify both PDF and DOCX were created
        assert new_version["file_id_pdf"] is not None, "PDF file should be created"
        assert new_version["file_id_docx"] is not None, "DOCX file should be created"
        assert new_version["filename_pdf"] is not None
        assert new_version["filename_docx"] is not None
        
        print(f"  PDF: {new_version['filename_pdf']}")
        print(f"  DOCX: {new_version['filename_docx']}")
    
    def test_generated_document_has_input_snapshot(self, auth_headers):
        """Test that newly generated documents have input snapshot."""
        # Generate new documents
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/generate-documents",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # Get order to check input snapshot
        order_response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}",
            headers=auth_headers
        )
        assert order_response.status_code == 200
        
        order = order_response.json().get("order", order_response.json())
        doc_versions = order.get("document_versions", [])
        
        # Get the latest version
        latest = max(doc_versions, key=lambda x: x["version"])
        
        # Check for input_snapshot
        assert "input_snapshot" in latest, "Latest version should have input_snapshot"
        snapshot = latest["input_snapshot"]
        
        assert "snapshot_created_at" in snapshot
        assert "customer" in snapshot
        assert "parameters" in snapshot
        
        print(f"✓ Version {latest['version']} has input snapshot with customer and parameters")


class TestDocumentFilenames:
    """Test document filename conventions."""
    
    def test_filename_follows_convention(self, auth_headers):
        """Test that filenames follow the naming convention."""
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/documents",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for version in data["versions"]:
            pdf_filename = version.get("filename_pdf", "")
            docx_filename = version.get("filename_docx", "")
            
            # Check PDF filename format: {order_id}_{service_code}_v{version}_{status}_{timestamp}.pdf
            assert TEST_ORDER_ID in pdf_filename, f"PDF filename should contain order ID"
            assert f"_v{version['version']}_" in pdf_filename, f"PDF filename should contain version"
            assert pdf_filename.endswith(".pdf"), f"PDF filename should end with .pdf"
            
            # Check DOCX filename format
            assert TEST_ORDER_ID in docx_filename, f"DOCX filename should contain order ID"
            assert f"_v{version['version']}_" in docx_filename, f"DOCX filename should contain version"
            assert docx_filename.endswith(".docx"), f"DOCX filename should end with .docx"
            
            print(f"✓ Version {version['version']} filenames follow convention")
            print(f"  PDF: {pdf_filename}")
            print(f"  DOCX: {docx_filename}")


class TestOrderDetailWithDocuments:
    """Test order detail endpoint includes document information."""
    
    def test_order_detail_includes_document_versions(self, auth_headers):
        """Test that order detail includes document versions."""
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        order = data.get("order", data)
        
        # Check document-related fields
        assert "document_versions" in order, "Order should have document_versions"
        assert "current_document_version" in order, "Order should have current_document_version"
        
        doc_versions = order["document_versions"]
        assert len(doc_versions) >= 1, "Should have at least 1 document version"
        
        current_version = order["current_document_version"]
        assert current_version >= 1, "Current version should be at least 1"
        
        print(f"✓ Order has {len(doc_versions)} document versions, current: v{current_version}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
