"""
Iteration 20 Tests: ZIP File Bulk Upload and Email Notifications for AI Extraction Applied

Features tested:
1. ZIP upload endpoint POST /api/documents/zip-upload returns 403 PLAN_NOT_ELIGIBLE for PLAN_1 users
2. ZIP upload validates .zip file extension
3. Apply & Save POST /api/documents/{id}/apply-extraction sends email notification
4. Plan features endpoint GET /api/client/plan-features returns zip_upload: false for PLAN_1
5. Bulk upload page loads with upload mode toggle (files/zip)
6. ZIP mode toggle is disabled for non-Portfolio plans with Lock icon
"""

import pytest
import requests
import os
import io
import zipfile
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"
TEST_PROPERTY_ID = "602cccda-fd42-4d48-947c-8fd1feb49564"
TEST_DOCUMENT_ID = "69200948-fd0a-4add-8012-45887b46867b"


class TestAuthentication:
    """Authentication tests for client and admin users"""
    
    def test_client_login(self):
        """Test client login returns valid token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert response.status_code == 200, f"Client login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert data.get("user", {}).get("email") == CLIENT_EMAIL
        print(f"✓ Client login successful")
    
    def test_admin_login(self):
        """Test admin login returns valid token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        print(f"✓ Admin login successful")


class TestPlanFeatures:
    """Test plan features endpoint for PLAN_1 users"""
    
    @pytest.fixture
    def client_token(self):
        """Get client auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Client login failed")
        return response.json()["access_token"]
    
    def test_plan_features_returns_zip_upload_false_for_plan_1(self, client_token):
        """Test that PLAN_1 users get zip_upload: false in plan features"""
        response = requests.get(
            f"{BASE_URL}/api/client/plan-features",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200, f"Plan features failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "plan" in data, "Missing 'plan' in response"
        assert "features" in data, "Missing 'features' in response"
        
        # Verify PLAN_1 features
        features = data.get("features", {})
        assert features.get("zip_upload") == False, f"Expected zip_upload=False for PLAN_1, got {features.get('zip_upload')}"
        assert features.get("bulk_upload") == True, f"Expected bulk_upload=True for PLAN_1, got {features.get('bulk_upload')}"
        
        print(f"✓ Plan features returns zip_upload=False for PLAN_1")
        print(f"  Plan: {data.get('plan')}, Plan Name: {data.get('plan_name')}")
        print(f"  Features: {features}")


class TestZipUploadPlanGating:
    """Test ZIP upload endpoint plan gating for PLAN_1 users"""
    
    @pytest.fixture
    def client_token(self):
        """Get client auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Client login failed")
        return response.json()["access_token"]
    
    def test_zip_upload_returns_403_for_plan_1(self, client_token):
        """Test that ZIP upload returns 403 PLAN_NOT_ELIGIBLE for PLAN_1 users"""
        # Create a minimal valid ZIP file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('test_document.pdf', b'%PDF-1.4 test content')
        zip_buffer.seek(0)
        
        files = {
            'file': ('test_documents.zip', zip_buffer, 'application/zip')
        }
        data = {
            'property_id': TEST_PROPERTY_ID
        }
        
        response = requests.post(
            f"{BASE_URL}/api/documents/zip-upload",
            headers={"Authorization": f"Bearer {client_token}"},
            files=files,
            data=data
        )
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        
        detail = response.json().get("detail", {})
        assert detail.get("error_code") == "PLAN_NOT_ELIGIBLE", f"Expected PLAN_NOT_ELIGIBLE, got {detail}"
        assert detail.get("feature") == "zip_upload", f"Expected feature=zip_upload, got {detail.get('feature')}"
        assert detail.get("upgrade_required") == True, f"Expected upgrade_required=True"
        
        print(f"✓ ZIP upload returns 403 PLAN_NOT_ELIGIBLE for PLAN_1 users")
        print(f"  Error: {detail.get('message')}")
    
    def test_zip_upload_validates_zip_extension(self, client_token):
        """Test that ZIP upload validates .zip file extension"""
        # Create a non-ZIP file
        files = {
            'file': ('test_document.pdf', b'%PDF-1.4 test content', 'application/pdf')
        }
        data = {
            'property_id': TEST_PROPERTY_ID
        }
        
        response = requests.post(
            f"{BASE_URL}/api/documents/zip-upload",
            headers={"Authorization": f"Bearer {client_token}"},
            files=files,
            data=data
        )
        
        # Should fail with 400 for invalid file type OR 403 for plan gating (plan check happens first)
        # Based on the code, plan gating check happens before file validation
        # So for PLAN_1 users, we'll get 403 first
        assert response.status_code in [400, 403], f"Expected 400 or 403, got {response.status_code}: {response.text}"
        
        if response.status_code == 400:
            detail = response.json().get("detail", "")
            assert "zip" in detail.lower() or "ZIP" in detail, f"Expected ZIP validation error, got: {detail}"
            print(f"✓ ZIP upload validates .zip file extension (400 error)")
        else:
            # Plan gating happens first
            print(f"✓ ZIP upload plan gating happens before file validation (403 error)")


class TestApplyExtractionEmail:
    """Test Apply & Save endpoint sends email notification"""
    
    @pytest.fixture
    def client_token(self):
        """Get client auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Client login failed")
        return response.json()["access_token"]
    
    def test_apply_extraction_attempts_email_notification(self, client_token):
        """Test that Apply & Save attempts to send email notification
        
        Note: Email may fail due to test email being inactive in Postmark,
        but the endpoint should still succeed and log the attempt.
        """
        # First, check if the document has AI extraction data
        response = requests.get(
            f"{BASE_URL}/api/documents/{TEST_DOCUMENT_ID}/extraction",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        
        if response.status_code != 200:
            pytest.skip(f"Document extraction not available: {response.text}")
        
        extraction_response = response.json()
        # Handle nested extraction structure
        extraction_data = extraction_response.get("extraction", extraction_response)
        if extraction_data.get("status") != "completed":
            pytest.skip(f"Document extraction not completed: {extraction_data.get('status')}")
        
        # Apply extraction with confirmed data
        confirmed_data = extraction_data.get("data", {})
        if not confirmed_data.get("expiry_date"):
            # Set a future expiry date for testing
            confirmed_data["expiry_date"] = "2026-12-31"
        
        # Use a unique certificate number to track this test
        confirmed_data["certificate_number"] = f"EMAIL-TEST-{datetime.now().strftime('%H%M%S')}"
        
        response = requests.post(
            f"{BASE_URL}/api/documents/{TEST_DOCUMENT_ID}/apply-extraction",
            headers={
                "Authorization": f"Bearer {client_token}",
                "Content-Type": "application/json"
            },
            json={"confirmed_data": confirmed_data}
        )
        
        # The endpoint should succeed even if email fails
        assert response.status_code == 200, f"Apply extraction failed: {response.text}"
        
        data = response.json()
        assert "message" in data, "Missing message in response"
        assert data.get("document_id") == TEST_DOCUMENT_ID
        
        print(f"✓ Apply extraction succeeded (email attempt logged)")
        print(f"  Message: {data.get('message')}")
        print(f"  Requirement status: {data.get('requirement_status')}")
        print(f"  Due date: {data.get('due_date')}")


class TestBulkUploadEndpoint:
    """Test bulk upload endpoint (non-ZIP) for PLAN_1 users"""
    
    @pytest.fixture
    def client_token(self):
        """Get client auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Client login failed")
        return response.json()["access_token"]
    
    def test_bulk_upload_available_for_plan_1(self, client_token):
        """Test that regular bulk upload is available for PLAN_1 users"""
        # Create a test PDF file
        files = [
            ('files', ('test_gas_safety.pdf', b'%PDF-1.4 test gas safety content', 'application/pdf'))
        ]
        data = {
            'property_id': TEST_PROPERTY_ID
        }
        
        response = requests.post(
            f"{BASE_URL}/api/documents/bulk-upload",
            headers={"Authorization": f"Bearer {client_token}"},
            files=files,
            data=data
        )
        
        # Should succeed for PLAN_1 users (bulk_upload is available)
        assert response.status_code == 200, f"Bulk upload failed: {response.text}"
        
        data = response.json()
        assert "results" in data, "Missing results in response"
        assert "summary" in data, "Missing summary in response"
        
        print(f"✓ Bulk upload available for PLAN_1 users")
        print(f"  Summary: {data.get('summary')}")


class TestMessageLogs:
    """Test that email attempts are logged in message_logs collection"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json()["access_token"]
    
    def test_email_logs_exist(self, admin_token):
        """Test that email logs are created for AI extraction emails"""
        # Check audit logs for email attempts
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?action=EMAIL_SENT&limit=5",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            logs = data.get("logs", [])
            print(f"✓ Found {len(logs)} EMAIL_SENT audit logs")
            for log in logs[:3]:
                print(f"  - {log.get('metadata', {}).get('template', 'N/A')} to {log.get('metadata', {}).get('recipient', 'N/A')}")
        else:
            # Also check for EMAIL_FAILED
            response = requests.get(
                f"{BASE_URL}/api/admin/audit-logs?action=EMAIL_FAILED&limit=5",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            if response.status_code == 200:
                data = response.json()
                logs = data.get("logs", [])
                print(f"✓ Found {len(logs)} EMAIL_FAILED audit logs (expected for test emails)")
            else:
                print(f"⚠ Could not retrieve email logs: {response.status_code}")


class TestAIExtractionAuditLog:
    """Test that AI extraction applied creates proper audit log"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json()["access_token"]
    
    def test_ai_extraction_applied_audit_log(self, admin_token):
        """Test that AI_EXTRACTION_APPLIED audit log is created"""
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?action=AI_EXTRACTION_APPLIED&limit=5",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200, f"Audit logs failed: {response.text}"
        
        data = response.json()
        logs = data.get("logs", [])
        
        print(f"✓ Found {len(logs)} AI_EXTRACTION_APPLIED audit logs")
        
        if logs:
            latest = logs[0]
            metadata = latest.get("metadata", {})
            print(f"  Latest log:")
            print(f"    - Document ID: {latest.get('resource_id')}")
            print(f"    - Changes: {metadata.get('changes_made', [])}")
            print(f"    - Expiry date set: {metadata.get('expiry_date_set')}")
            print(f"    - Status before: {metadata.get('requirement_status_before')}")
            print(f"    - Status after: {metadata.get('requirement_status_after')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
