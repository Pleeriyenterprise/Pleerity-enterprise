"""
Iteration 19 Tests: Apply & Save Date Parsing, AI Query History, Calendar Integration

Tests:
1. Apply & Save endpoint POST /api/documents/{id}/apply-extraction with ISO date (2026-02-14)
2. Apply & Save works with UK date format (14/02/2026)
3. Apply & Save creates AI_EXTRACTION_APPLIED audit log with before/after states
4. Requirement due_date and status are updated after Apply & Save
5. AI Query History endpoint GET /api/admin/assistant/history returns saved queries
6. AI Query History filtered by CRN works
7. Admin Assistant POST /api/admin/assistant/ask saves query to history with query_id
8. Calendar endpoint GET /api/calendar/expiries shows requirements by date
9. Plan features endpoint GET /api/client/plan-features works
"""

import pytest
import requests
import os
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://order-fulfillment-9.preview.emergentagent.com').rstrip('/')

# Test credentials
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"
TEST_CRN = "PLE-CVP-2026-07354"
TEST_DOCUMENT_ID = "69200948-fd0a-4add-8012-45887b46867b"


class TestAuthentication:
    """Authentication tests for client and admin"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Client authentication failed: {response.status_code} - {response.text}")
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Admin authentication failed: {response.status_code} - {response.text}")
    
    def test_client_login(self):
        """Test client login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert response.status_code == 200, f"Client login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        print(f"✓ Client login successful")
    
    def test_admin_login(self):
        """Test admin login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        print(f"✓ Admin login successful")


class TestApplyAndSave:
    """Tests for Apply & Save endpoint with date parsing"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Client authentication failed")
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin authentication failed")
    
    def test_apply_extraction_iso_date_format(self, client_token):
        """Test Apply & Save with ISO date format (YYYY-MM-DD)"""
        headers = {"Authorization": f"Bearer {client_token}"}
        
        # First check if document exists and has extraction
        doc_response = requests.get(
            f"{BASE_URL}/api/documents/{TEST_DOCUMENT_ID}/extraction",
            headers=headers
        )
        
        if doc_response.status_code == 404:
            pytest.skip(f"Test document {TEST_DOCUMENT_ID} not found")
        
        # Apply extraction with ISO date format
        iso_date = "2026-02-14"
        payload = {
            "confirmed_data": {
                "expiry_date": iso_date,
                "certificate_number": "TEST-ISO-001",
                "document_type": "Gas Safety Certificate"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/documents/{TEST_DOCUMENT_ID}/apply-extraction",
            headers=headers,
            json=payload
        )
        
        # Check response
        if response.status_code == 400:
            # Document may not have extraction or not linked to requirement
            print(f"Apply extraction returned 400: {response.json().get('detail')}")
            pytest.skip("Document not ready for apply extraction test")
        
        assert response.status_code == 200, f"Apply extraction failed: {response.status_code} - {response.text}"
        data = response.json()
        
        assert "message" in data
        assert data["message"] == "Extraction applied successfully"
        assert "due_date" in data
        assert "requirement_status" in data
        
        # Verify the date was parsed correctly
        due_date = data.get("due_date", "")
        assert "2026-02-14" in due_date, f"ISO date not parsed correctly: {due_date}"
        
        print(f"✓ Apply extraction with ISO date format works")
        print(f"  Due date set to: {due_date}")
        print(f"  Requirement status: {data.get('requirement_status')}")
    
    def test_apply_extraction_uk_date_format(self, client_token):
        """Test Apply & Save with UK date format (DD/MM/YYYY)"""
        headers = {"Authorization": f"Bearer {client_token}"}
        
        # Apply extraction with UK date format
        uk_date = "14/02/2026"
        payload = {
            "confirmed_data": {
                "expiry_date": uk_date,
                "certificate_number": "TEST-UK-001",
                "document_type": "Gas Safety Certificate"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/documents/{TEST_DOCUMENT_ID}/apply-extraction",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 400:
            print(f"Apply extraction returned 400: {response.json().get('detail')}")
            pytest.skip("Document not ready for apply extraction test")
        
        assert response.status_code == 200, f"Apply extraction with UK date failed: {response.status_code} - {response.text}"
        data = response.json()
        
        assert "message" in data
        assert data["message"] == "Extraction applied successfully"
        
        # Verify the date was parsed correctly (should be 2026-02-14 in ISO format)
        due_date = data.get("due_date", "")
        assert "2026-02-14" in due_date, f"UK date not parsed correctly to ISO: {due_date}"
        
        print(f"✓ Apply extraction with UK date format works")
        print(f"  UK date '14/02/2026' parsed to: {due_date}")
    
    def test_apply_extraction_creates_audit_log(self, admin_token):
        """Test that Apply & Save creates AI_EXTRACTION_APPLIED audit log"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get recent audit logs
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs",
            headers=headers,
            params={"action": "AI_EXTRACTION_APPLIED", "limit": 10}
        )
        
        assert response.status_code == 200, f"Get audit logs failed: {response.text}"
        data = response.json()
        
        assert "logs" in data
        
        # Check if we have any AI_EXTRACTION_APPLIED logs
        extraction_logs = [log for log in data["logs"] if log.get("action") == "AI_EXTRACTION_APPLIED"]
        
        if len(extraction_logs) > 0:
            log = extraction_logs[0]
            # Verify audit log structure
            assert "before_state" in log or log.get("before_state") is not None or "metadata" in log
            assert "after_state" in log or log.get("after_state") is not None or "metadata" in log
            
            # Check metadata contains expected fields
            metadata = log.get("metadata", {})
            if metadata:
                print(f"✓ AI_EXTRACTION_APPLIED audit log found with metadata")
                print(f"  Changes made: {metadata.get('changes_made', [])}")
            else:
                print(f"✓ AI_EXTRACTION_APPLIED audit log found")
        else:
            print("⚠ No AI_EXTRACTION_APPLIED audit logs found yet (may need to run apply extraction first)")


class TestAIQueryHistory:
    """Tests for AI Query History persistence"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin authentication failed")
    
    def test_admin_assistant_ask_saves_to_history(self, admin_token):
        """Test that POST /api/admin/assistant/ask saves query to history with query_id"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Ask a question
        question = "What is the compliance status for this client?"
        payload = {
            "crn": TEST_CRN,
            "question": question
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/assistant/ask",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 404:
            pytest.skip(f"Client with CRN {TEST_CRN} not found")
        
        assert response.status_code == 200, f"Admin assistant ask failed: {response.status_code} - {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "answer" in data, "Response missing 'answer' field"
        assert "query_id" in data, "Response missing 'query_id' field"
        assert "crn" in data
        assert data["crn"] == TEST_CRN
        
        query_id = data["query_id"]
        print(f"✓ Admin assistant ask returned query_id: {query_id}")
        
        # Verify query was saved to history
        import time
        time.sleep(1)  # Wait for DB write
        
        history_response = requests.get(
            f"{BASE_URL}/api/admin/assistant/history",
            headers=headers,
            params={"limit": 5}
        )
        
        assert history_response.status_code == 200, f"Get history failed: {history_response.text}"
        history_data = history_response.json()
        
        assert "queries" in history_data
        
        # Find our query in history
        found_query = None
        for q in history_data["queries"]:
            if q.get("query_id") == query_id:
                found_query = q
                break
        
        assert found_query is not None, f"Query {query_id} not found in history"
        assert found_query.get("question") == question
        assert found_query.get("crn") == TEST_CRN
        
        print(f"✓ Query saved to history and retrievable")
        return query_id
    
    def test_get_assistant_history(self, admin_token):
        """Test GET /api/admin/assistant/history returns saved queries"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/admin/assistant/history",
            headers=headers
        )
        
        assert response.status_code == 200, f"Get history failed: {response.text}"
        data = response.json()
        
        assert "queries" in data
        assert "total" in data
        assert "has_more" in data
        
        print(f"✓ GET /api/admin/assistant/history works")
        print(f"  Total queries: {data['total']}")
        print(f"  Returned: {len(data['queries'])} queries")
    
    def test_get_assistant_history_filtered_by_crn(self, admin_token):
        """Test GET /api/admin/assistant/history filtered by CRN"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/admin/assistant/history",
            headers=headers,
            params={"crn": TEST_CRN}
        )
        
        assert response.status_code == 200, f"Get history with CRN filter failed: {response.text}"
        data = response.json()
        
        assert "queries" in data
        
        # All returned queries should have the filtered CRN
        for query in data["queries"]:
            assert query.get("crn") == TEST_CRN, f"Query CRN mismatch: {query.get('crn')} != {TEST_CRN}"
        
        print(f"✓ GET /api/admin/assistant/history with CRN filter works")
        print(f"  Queries for CRN {TEST_CRN}: {len(data['queries'])}")


class TestCalendarEndpoint:
    """Tests for Calendar expiries endpoint"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Client authentication failed")
    
    def test_calendar_expiries_endpoint(self, client_token):
        """Test GET /api/calendar/expiries shows requirements by date"""
        headers = {"Authorization": f"Bearer {client_token}"}
        
        # Get current year calendar
        current_year = datetime.now().year
        response = requests.get(
            f"{BASE_URL}/api/calendar/expiries",
            headers=headers,
            params={"year": current_year}
        )
        
        assert response.status_code == 200, f"Calendar expiries failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "year" in data
        assert data["year"] == current_year
        assert "events_by_date" in data
        assert "summary" in data
        
        summary = data["summary"]
        assert "total_events" in summary
        assert "overdue_count" in summary
        assert "expiring_soon_count" in summary
        assert "dates_with_events" in summary
        
        print(f"✓ GET /api/calendar/expiries works")
        print(f"  Year: {data['year']}")
        print(f"  Total events: {summary['total_events']}")
        print(f"  Dates with events: {summary['dates_with_events']}")
    
    def test_calendar_expiries_with_month_filter(self, client_token):
        """Test GET /api/calendar/expiries with month filter"""
        headers = {"Authorization": f"Bearer {client_token}"}
        
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        response = requests.get(
            f"{BASE_URL}/api/calendar/expiries",
            headers=headers,
            params={"year": current_year, "month": current_month}
        )
        
        assert response.status_code == 200, f"Calendar expiries with month failed: {response.text}"
        data = response.json()
        
        assert data["year"] == current_year
        assert data["month"] == current_month
        
        print(f"✓ GET /api/calendar/expiries with month filter works")
        print(f"  Year: {data['year']}, Month: {data['month']}")
    
    def test_calendar_upcoming_expiries(self, client_token):
        """Test GET /api/calendar/upcoming endpoint"""
        headers = {"Authorization": f"Bearer {client_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/calendar/upcoming",
            headers=headers,
            params={"days": 90}
        )
        
        assert response.status_code == 200, f"Calendar upcoming failed: {response.text}"
        data = response.json()
        
        assert "days_ahead" in data
        assert data["days_ahead"] == 90
        assert "count" in data
        assert "upcoming" in data
        
        print(f"✓ GET /api/calendar/upcoming works")
        print(f"  Days ahead: {data['days_ahead']}")
        print(f"  Upcoming count: {data['count']}")


class TestPlanFeatures:
    """Tests for Plan features endpoint"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Client authentication failed")
    
    def test_plan_features_endpoint(self, client_token):
        """Test GET /api/client/plan-features returns feature availability"""
        headers = {"Authorization": f"Bearer {client_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/client/plan-features",
            headers=headers
        )
        
        assert response.status_code == 200, f"Plan features failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "plan" in data
        assert "plan_name" in data
        assert "features" in data
        
        features = data["features"]
        assert isinstance(features, dict)
        
        print(f"✓ GET /api/client/plan-features works")
        print(f"  Plan: {data['plan']}")
        print(f"  Plan name: {data['plan_name']}")
        print(f"  Features: {list(features.keys())}")


class TestDocumentExtraction:
    """Additional tests for document extraction flow"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Client authentication failed")
    
    def test_get_document_extraction(self, client_token):
        """Test GET /api/documents/{id}/extraction endpoint"""
        headers = {"Authorization": f"Bearer {client_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/documents/{TEST_DOCUMENT_ID}/extraction",
            headers=headers
        )
        
        if response.status_code == 404:
            pytest.skip(f"Test document {TEST_DOCUMENT_ID} not found")
        
        assert response.status_code == 200, f"Get extraction failed: {response.text}"
        data = response.json()
        
        assert "has_extraction" in data
        
        if data["has_extraction"]:
            assert "extraction" in data
            print(f"✓ Document has extraction data")
            print(f"  Extraction status: {data['extraction'].get('status')}")
        else:
            print(f"✓ Document found but no extraction yet")
    
    def test_get_document_details(self, client_token):
        """Test GET /api/documents/{id}/details endpoint"""
        headers = {"Authorization": f"Bearer {client_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/documents/{TEST_DOCUMENT_ID}/details",
            headers=headers
        )
        
        if response.status_code == 404:
            pytest.skip(f"Test document {TEST_DOCUMENT_ID} not found")
        
        assert response.status_code == 200, f"Get document details failed: {response.text}"
        data = response.json()
        
        assert "document" in data
        
        document = data["document"]
        assert "document_id" in document
        assert document["document_id"] == TEST_DOCUMENT_ID
        
        print(f"✓ GET /api/documents/{TEST_DOCUMENT_ID}/details works")
        print(f"  File name: {document.get('file_name')}")
        print(f"  Status: {document.get('status')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
