"""
Test Iteration 10 Features:
1. Scheduled Reports API (POST/GET/DELETE/PATCH schedules)
2. Bulk Property Import API (POST /api/properties/bulk-import)
3. PDF Report Generation (client-side jsPDF)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def client_token():
    """Get client authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": CLIENT_EMAIL,
        "password": CLIENT_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Client login failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")


@pytest.fixture
def client_headers(client_token):
    """Headers with client auth token"""
    return {
        "Authorization": f"Bearer {client_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def admin_headers(admin_token):
    """Headers with admin auth token"""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


# ============================================================================
# SCHEDULED REPORTS API TESTS
# ============================================================================

class TestScheduledReportsAPI:
    """Test scheduled reports CRUD operations"""
    
    created_schedule_ids = []
    
    def test_create_schedule_compliance_summary_daily(self, client_headers):
        """Test creating a daily compliance summary schedule"""
        response = requests.post(
            f"{BASE_URL}/api/reports/schedules",
            headers=client_headers,
            json={
                "report_type": "compliance_summary",
                "frequency": "daily",
                "recipients": ["test@example.com"]
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "schedule_id" in data
        assert "next_scheduled" in data
        assert data.get("message") == "Report schedule created"
        self.created_schedule_ids.append(data["schedule_id"])
        print(f"✓ Created daily schedule: {data['schedule_id']}")
    
    def test_create_schedule_requirements_weekly(self, client_headers):
        """Test creating a weekly requirements schedule"""
        response = requests.post(
            f"{BASE_URL}/api/reports/schedules",
            headers=client_headers,
            json={
                "report_type": "requirements",
                "frequency": "weekly",
                "recipients": None  # Should default to client email
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "schedule_id" in data
        self.created_schedule_ids.append(data["schedule_id"])
        print(f"✓ Created weekly schedule: {data['schedule_id']}")
    
    def test_create_schedule_monthly(self, client_headers):
        """Test creating a monthly schedule"""
        response = requests.post(
            f"{BASE_URL}/api/reports/schedules",
            headers=client_headers,
            json={
                "report_type": "compliance_summary",
                "frequency": "monthly",
                "recipients": ["monthly@example.com", "team@example.com"]
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "schedule_id" in data
        self.created_schedule_ids.append(data["schedule_id"])
        print(f"✓ Created monthly schedule: {data['schedule_id']}")
    
    def test_create_schedule_invalid_report_type(self, client_headers):
        """Test creating schedule with invalid report type returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/reports/schedules",
            headers=client_headers,
            json={
                "report_type": "invalid_type",
                "frequency": "daily"
            }
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid report type returns 400")
    
    def test_create_schedule_invalid_frequency(self, client_headers):
        """Test creating schedule with invalid frequency returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/reports/schedules",
            headers=client_headers,
            json={
                "report_type": "compliance_summary",
                "frequency": "hourly"  # Invalid
            }
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid frequency returns 400")
    
    def test_list_schedules(self, client_headers):
        """Test listing all schedules for client"""
        response = requests.get(
            f"{BASE_URL}/api/reports/schedules",
            headers=client_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "schedules" in data
        assert isinstance(data["schedules"], list)
        print(f"✓ Listed {len(data['schedules'])} schedules")
        
        # Verify schedule structure
        if len(data["schedules"]) > 0:
            schedule = data["schedules"][0]
            assert "schedule_id" in schedule
            assert "report_type" in schedule
            assert "frequency" in schedule
            assert "is_active" in schedule
            assert "recipients" in schedule
            print("✓ Schedule structure is correct")
    
    def test_toggle_schedule(self, client_headers):
        """Test toggling schedule on/off"""
        # First create a schedule to toggle
        create_response = requests.post(
            f"{BASE_URL}/api/reports/schedules",
            headers=client_headers,
            json={
                "report_type": "compliance_summary",
                "frequency": "weekly"
            }
        )
        assert create_response.status_code == 200
        schedule_id = create_response.json()["schedule_id"]
        self.created_schedule_ids.append(schedule_id)
        
        # Toggle off
        toggle_response = requests.patch(
            f"{BASE_URL}/api/reports/schedules/{schedule_id}/toggle",
            headers=client_headers
        )
        assert toggle_response.status_code == 200, f"Expected 200, got {toggle_response.status_code}"
        data = toggle_response.json()
        assert "is_active" in data
        assert data["is_active"] == False  # Should be toggled off
        print(f"✓ Toggled schedule off: {schedule_id}")
        
        # Toggle back on
        toggle_response2 = requests.patch(
            f"{BASE_URL}/api/reports/schedules/{schedule_id}/toggle",
            headers=client_headers
        )
        assert toggle_response2.status_code == 200
        assert toggle_response2.json()["is_active"] == True
        print(f"✓ Toggled schedule on: {schedule_id}")
    
    def test_toggle_nonexistent_schedule(self, client_headers):
        """Test toggling non-existent schedule returns 404"""
        response = requests.patch(
            f"{BASE_URL}/api/reports/schedules/nonexistent-id/toggle",
            headers=client_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Toggle non-existent schedule returns 404")
    
    def test_delete_schedule(self, client_headers):
        """Test deleting a schedule"""
        # Create a schedule to delete
        create_response = requests.post(
            f"{BASE_URL}/api/reports/schedules",
            headers=client_headers,
            json={
                "report_type": "requirements",
                "frequency": "daily"
            }
        )
        assert create_response.status_code == 200
        schedule_id = create_response.json()["schedule_id"]
        
        # Delete it
        delete_response = requests.delete(
            f"{BASE_URL}/api/reports/schedules/{schedule_id}",
            headers=client_headers
        )
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}"
        assert delete_response.json().get("message") == "Schedule deleted"
        print(f"✓ Deleted schedule: {schedule_id}")
        
        # Verify it's gone
        list_response = requests.get(
            f"{BASE_URL}/api/reports/schedules",
            headers=client_headers
        )
        schedules = list_response.json().get("schedules", [])
        assert not any(s["schedule_id"] == schedule_id for s in schedules)
        print("✓ Verified schedule is deleted")
    
    def test_delete_nonexistent_schedule(self, client_headers):
        """Test deleting non-existent schedule returns 404"""
        response = requests.delete(
            f"{BASE_URL}/api/reports/schedules/nonexistent-id",
            headers=client_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Delete non-existent schedule returns 404")
    
    def test_schedule_unauthorized(self):
        """Test schedule endpoints without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/reports/schedules")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthorized access returns 401")


# ============================================================================
# BULK PROPERTY IMPORT API TESTS
# ============================================================================

class TestBulkPropertyImportAPI:
    """Test bulk property import functionality"""
    
    def test_bulk_import_single_property(self, client_headers):
        """Test importing a single property"""
        unique_id = str(uuid.uuid4())[:8]
        response = requests.post(
            f"{BASE_URL}/api/properties/bulk-import",
            headers=client_headers,
            json={
                "properties": [
                    {
                        "address_line_1": f"TEST_{unique_id} Single Import Street",
                        "city": "London",
                        "postcode": "SW1A 1AA",
                        "property_type": "residential",
                        "number_of_units": 1
                    }
                ]
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "summary" in data
        assert data["summary"]["total"] == 1
        assert data["summary"]["successful"] == 1
        assert data["summary"]["failed"] == 0
        print(f"✓ Single property import successful")
        
        # Verify requirements were created
        if data["summary"]["created_properties"]:
            prop = data["summary"]["created_properties"][0]
            assert "requirements_created" in prop
            assert prop["requirements_created"] > 0
            print(f"✓ Created {prop['requirements_created']} requirements for property")
    
    def test_bulk_import_multiple_properties(self, client_headers):
        """Test importing multiple properties at once"""
        unique_id = str(uuid.uuid4())[:8]
        response = requests.post(
            f"{BASE_URL}/api/properties/bulk-import",
            headers=client_headers,
            json={
                "properties": [
                    {
                        "address_line_1": f"TEST_{unique_id} First Street",
                        "city": "Manchester",
                        "postcode": "M1 1AA",
                        "property_type": "residential",
                        "number_of_units": 1
                    },
                    {
                        "address_line_1": f"TEST_{unique_id} Second Avenue",
                        "address_line_2": "Unit 2B",
                        "city": "Birmingham",
                        "postcode": "B1 1AA",
                        "property_type": "hmo",
                        "number_of_units": 4
                    },
                    {
                        "address_line_1": f"TEST_{unique_id} Third Road",
                        "city": "Leeds",
                        "postcode": "LS1 1AA",
                        "property_type": "commercial",
                        "number_of_units": 2
                    }
                ]
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["summary"]["total"] == 3
        assert data["summary"]["successful"] == 3
        assert data["summary"]["failed"] == 0
        print(f"✓ Bulk import of 3 properties successful")
    
    def test_bulk_import_with_missing_required_fields(self, client_headers):
        """Test import with missing required fields reports errors"""
        unique_id = str(uuid.uuid4())[:8]
        response = requests.post(
            f"{BASE_URL}/api/properties/bulk-import",
            headers=client_headers,
            json={
                "properties": [
                    {
                        "address_line_1": f"TEST_{unique_id} Valid Street",
                        "city": "London",
                        "postcode": "SW1A 1AA"
                    },
                    {
                        "address_line_1": "",  # Missing address
                        "city": "Manchester",
                        "postcode": "M1 1AA"
                    },
                    {
                        "address_line_1": f"TEST_{unique_id} No City",
                        "city": "",  # Missing city
                        "postcode": "B1 1AA"
                    }
                ]
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["summary"]["total"] == 3
        assert data["summary"]["successful"] == 1  # Only first one should succeed
        assert data["summary"]["failed"] == 2
        assert len(data["summary"]["errors"]) == 2
        print(f"✓ Missing fields correctly reported as errors")
    
    def test_bulk_import_duplicate_detection(self, client_headers):
        """Test that duplicate properties are detected"""
        unique_id = str(uuid.uuid4())[:8]
        address = f"TEST_{unique_id} Duplicate Street"
        postcode = "DU1 1AA"
        
        # First import
        response1 = requests.post(
            f"{BASE_URL}/api/properties/bulk-import",
            headers=client_headers,
            json={
                "properties": [
                    {
                        "address_line_1": address,
                        "city": "London",
                        "postcode": postcode
                    }
                ]
            }
        )
        assert response1.status_code == 200
        assert response1.json()["summary"]["successful"] == 1
        
        # Second import with same address
        response2 = requests.post(
            f"{BASE_URL}/api/properties/bulk-import",
            headers=client_headers,
            json={
                "properties": [
                    {
                        "address_line_1": address,
                        "city": "London",
                        "postcode": postcode
                    }
                ]
            }
        )
        assert response2.status_code == 200
        data = response2.json()
        assert data["summary"]["failed"] == 1
        assert any("already exists" in str(e.get("error", "")).lower() for e in data["summary"]["errors"])
        print("✓ Duplicate property detection working")
    
    def test_bulk_import_empty_list(self, client_headers):
        """Test importing empty list"""
        response = requests.post(
            f"{BASE_URL}/api/properties/bulk-import",
            headers=client_headers,
            json={"properties": []}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["summary"]["total"] == 0
        assert data["summary"]["successful"] == 0
        print("✓ Empty list import handled correctly")
    
    def test_bulk_import_unauthorized(self):
        """Test bulk import without auth returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/properties/bulk-import",
            json={"properties": []}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthorized bulk import returns 401")


# ============================================================================
# REPORTS API TESTS (CSV and PDF format)
# ============================================================================

class TestReportsAPI:
    """Test report generation endpoints"""
    
    def test_get_available_reports(self, client_headers):
        """Test getting list of available reports"""
        response = requests.get(
            f"{BASE_URL}/api/reports/available",
            headers=client_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "reports" in data
        assert len(data["reports"]) >= 2  # At least compliance_summary and requirements
        
        report_ids = [r["id"] for r in data["reports"]]
        assert "compliance_summary" in report_ids
        assert "requirements" in report_ids
        print(f"✓ Available reports: {report_ids}")
    
    def test_compliance_summary_csv(self, client_headers):
        """Test downloading compliance summary as CSV"""
        response = requests.get(
            f"{BASE_URL}/api/reports/compliance-summary?format=csv",
            headers=client_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert "text/csv" in response.headers.get("content-type", "")
        assert len(response.content) > 0
        print("✓ Compliance summary CSV download working")
    
    def test_compliance_summary_pdf_data(self, client_headers):
        """Test getting compliance summary data for PDF generation"""
        response = requests.get(
            f"{BASE_URL}/api/reports/compliance-summary?format=pdf",
            headers=client_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Should return JSON data for client-side PDF generation
        assert "data" in data or "summary" in data or "properties" in data
        print("✓ Compliance summary PDF data returned")
    
    def test_requirements_report_csv(self, client_headers):
        """Test downloading requirements report as CSV"""
        response = requests.get(
            f"{BASE_URL}/api/reports/requirements?format=csv",
            headers=client_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert "text/csv" in response.headers.get("content-type", "")
        print("✓ Requirements report CSV download working")
    
    def test_requirements_report_pdf_data(self, client_headers):
        """Test getting requirements report data for PDF generation"""
        response = requests.get(
            f"{BASE_URL}/api/reports/requirements?format=pdf",
            headers=client_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "data" in data or "requirements" in data
        print("✓ Requirements report PDF data returned")
    
    def test_audit_logs_report_admin(self, admin_headers):
        """Test audit logs report (admin only)"""
        response = requests.get(
            f"{BASE_URL}/api/reports/audit-logs?format=csv",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Audit logs report accessible by admin")
    
    def test_audit_logs_report_client_forbidden(self, client_headers):
        """Test that client cannot access audit logs report"""
        response = requests.get(
            f"{BASE_URL}/api/reports/audit-logs?format=csv",
            headers=client_headers
        )
        # Should be 403 Forbidden for non-admin
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Audit logs report forbidden for client")


# ============================================================================
# CLEANUP
# ============================================================================

class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_schedules(self, client_headers):
        """Clean up test schedules"""
        # List all schedules
        response = requests.get(
            f"{BASE_URL}/api/reports/schedules",
            headers=client_headers
        )
        if response.status_code == 200:
            schedules = response.json().get("schedules", [])
            deleted = 0
            for schedule in schedules:
                # Delete schedules created during testing
                del_response = requests.delete(
                    f"{BASE_URL}/api/reports/schedules/{schedule['schedule_id']}",
                    headers=client_headers
                )
                if del_response.status_code == 200:
                    deleted += 1
            print(f"✓ Cleaned up {deleted} test schedules")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
