"""
Test suite for Full Reporting System - Export & Scheduling
Tests all report types, export formats (CSV, XLSX, PDF, JSON), and scheduled report delivery
"""
import json
import pytest

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


class TestReportingAuth:
    """Authentication tests for reporting endpoints"""

    @pytest.fixture
    def admin_token(self, client):
        """Get admin authentication token"""
        response = client.post(
            "/api/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]

    @pytest.fixture
    def auth_headers(self, admin_token):
        """Get authenticated headers"""
        return {"Authorization": f"Bearer {admin_token}"}

    def test_unauthenticated_access_rejected(self, client):
        """Test that unauthenticated requests are rejected"""
        response = client.get("/api/admin/reports/types")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"


class TestReportTypes:
    """Tests for GET /api/admin/reports/types endpoint"""

    @pytest.fixture
    def admin_token(self, client):
        """Get admin authentication token"""
        response = client.post(
            "/api/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]

    @pytest.fixture
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}

    def test_get_report_types_returns_7_types(self, client, auth_headers):
        """Test that 7 report types are returned"""
        response = client.get(
            "/api/admin/reports/types",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "types" in data
        assert len(data["types"]) == 7, f"Expected 7 report types, got {len(data['types'])}"
        
        # Verify all expected report types
        type_values = [t["value"] for t in data["types"]]
        expected_types = ["revenue", "orders", "clients", "leads", "compliance", "enablement", "consent"]
        for expected in expected_types:
            assert expected in type_values, f"Missing report type: {expected}"
    
    def test_get_report_types_returns_4_formats(self, client, auth_headers):
        """Test that 4 export formats are returned"""
        response = client.get(
            "/api/admin/reports/types",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "formats" in data
        assert len(data["formats"]) == 4, f"Expected 4 formats, got {len(data['formats'])}"
        
        # Verify all expected formats
        format_values = [f["value"] for f in data["formats"]]
        expected_formats = ["csv", "xlsx", "pdf", "json"]
        for expected in expected_formats:
            assert expected in format_values, f"Missing format: {expected}"
    
    def test_get_report_types_returns_periods(self, client, auth_headers):
        """Test that time periods are returned"""
        response = client.get(
            "/api/admin/reports/types",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "periods" in data
        assert len(data["periods"]) >= 5, "Expected at least 5 period options"


class TestReportPreview:
    """Tests for GET /api/admin/reports/preview/{report_type} endpoint"""

    @pytest.fixture
    def admin_token(self, client):
        response = client.post(
            "/api/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}

    def test_preview_leads_report(self, client, auth_headers):
        """Test preview of leads report"""
        response = client.get(
            "/api/admin/reports/preview/leads?period=30d&limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "report_type" in data
        assert data["report_type"] == "leads"
        assert "period" in data
        assert "total_rows" in data
        assert "preview" in data
        assert "columns" in data
    
    def test_preview_revenue_report(self, client, auth_headers):
        """Test preview of revenue report"""
        response = client.get(
            "/api/admin/reports/preview/revenue?period=30d&limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["report_type"] == "revenue"
        assert "preview" in data
    
    def test_preview_orders_report(self, client, auth_headers):
        """Test preview of orders report"""
        response = client.get(
            "/api/admin/reports/preview/orders?period=30d&limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["report_type"] == "orders"
    
    def test_preview_clients_report(self, client, auth_headers):
        """Test preview of clients report"""
        response = client.get(
            "/api/admin/reports/preview/clients?period=30d&limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["report_type"] == "clients"
    
    def test_preview_compliance_report(self, client, auth_headers):
        """Test preview of compliance report"""
        response = client.get(
            "/api/admin/reports/preview/compliance?period=30d&limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["report_type"] == "compliance"
    
    def test_preview_enablement_report(self, client, auth_headers):
        """Test preview of enablement report"""
        response = client.get(
            "/api/admin/reports/preview/enablement?period=30d&limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["report_type"] == "enablement"
    
    def test_preview_consent_report(self, client, auth_headers):
        """Test preview of consent report"""
        response = client.get(
            "/api/admin/reports/preview/consent?period=30d&limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["report_type"] == "consent"
    
    def test_preview_invalid_report_type(self, client, auth_headers):
        """Test preview with invalid report type returns 400"""
        response = client.get(
            "/api/admin/reports/preview/invalid_type?period=30d",
            headers=auth_headers
        )
        assert response.status_code == 400


class TestReportGenerate:
    """Tests for POST /api/admin/reports/generate endpoint - Export formats"""

    @pytest.fixture
    def admin_token(self, client):
        response = client.post(
            "/api/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_generate_csv_report(self, client, auth_headers):
        """Test generating CSV report"""
        response = client.post(
            "/api/admin/reports/generate",
            headers=auth_headers,
            json={
                "report_type": "leads",
                "period": "30d",
                "format": "csv"
            }
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        assert "attachment" in response.headers.get("content-disposition", "")
        assert ".csv" in response.headers.get("content-disposition", "")
    
    def test_generate_xlsx_report(self, client, auth_headers):
        """Test generating Excel XLSX report"""
        response = client.post(
            "/api/admin/reports/generate",
            headers=auth_headers,
            json={
                "report_type": "orders",
                "period": "30d",
                "format": "xlsx"
            }
        )
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "spreadsheetml" in content_type or "application/vnd" in content_type
        assert ".xlsx" in response.headers.get("content-disposition", "")
    
    def test_generate_pdf_report(self, client, auth_headers):
        """Test generating PDF report"""
        response = client.post(
            "/api/admin/reports/generate",
            headers=auth_headers,
            json={
                "report_type": "clients",
                "period": "30d",
                "format": "pdf"
            }
        )
        assert response.status_code == 200
        assert "application/pdf" in response.headers.get("content-type", "")
        assert ".pdf" in response.headers.get("content-disposition", "")
    
    def test_generate_json_report(self, client, auth_headers):
        """Test generating JSON report"""
        response = client.post(
            "/api/admin/reports/generate",
            headers=auth_headers,
            json={
                "report_type": "revenue",
                "period": "30d",
                "format": "json"
            }
        )
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")
        # Verify JSON is valid
        data = response.json()
        assert "data" in data
        assert "count" in data
        assert "generated_at" in data
    
    def test_generate_report_invalid_type(self, client, auth_headers):
        """Test generating report with invalid type returns 400"""
        response = client.post(
            "/api/admin/reports/generate",
            headers=auth_headers,
            json={
                "report_type": "invalid_type",
                "period": "30d",
                "format": "csv"
            }
        )
        assert response.status_code == 400


class TestScheduledReports:
    """Tests for scheduled reports CRUD operations"""

    @pytest.fixture
    def admin_token(self, client):
        response = client.post(
            "/api/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_list_scheduled_reports(self, client, auth_headers):
        """Test listing scheduled reports"""
        response = client.get(
            "/api/admin/reports/schedules",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "schedules" in data
        assert "total" in data
        assert isinstance(data["schedules"], list)
    
    def test_create_scheduled_report(self, client, auth_headers):
        """Test creating a new scheduled report"""
        response = client.post(
            "/api/admin/reports/schedules",
            headers=auth_headers,
            json={
                "name": "TEST_Weekly Leads Report",
                "report_type": "leads",
                "frequency": "weekly",
                "recipients": ["test@example.com"],
                "format": "csv",
                "enabled": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "schedule_id" in data
        assert data["name"] == "TEST_Weekly Leads Report"
        assert data["report_type"] == "leads"
        assert data["frequency"] == "weekly"
        assert data["format"] == "csv"
        assert data["enabled"] == True
        assert "next_run" in data
        
        # Store schedule_id for cleanup
        TestScheduledReports.created_schedule_id = data["schedule_id"]
    
    def test_toggle_scheduled_report(self, client, auth_headers):
        """Test toggling a scheduled report on/off"""
        # First get the schedule we created
        schedule_id = getattr(TestScheduledReports, 'created_schedule_id', None)
        if not schedule_id:
            pytest.skip("No schedule created to toggle")
        
        response = client.put(
            f"/api/admin/reports/schedules/{schedule_id}/toggle",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "schedule_id" in data
        assert "enabled" in data
        # Should be toggled to False (was True)
        assert data["enabled"] == False
    
    def test_run_scheduled_report_now(self, client, auth_headers):
        """Test manually running a scheduled report"""
        schedule_id = getattr(TestScheduledReports, 'created_schedule_id', None)
        if not schedule_id:
            pytest.skip("No schedule created to run")
        
        response = client.post(
            f"/api/admin/reports/schedules/{schedule_id}/run",
            headers=auth_headers
        )
        # Should succeed even if email delivery fails (logged but not sent without POSTMARK)
        assert response.status_code == 200
        data = response.json()
        
        # Response includes success, schedule_id, report_type, recipients, row_count, email_results
        assert data.get("success") == True
        assert "schedule_id" in data
        assert "report_type" in data
        assert "email_results" in data
    
    def test_delete_scheduled_report(self, client, auth_headers):
        """Test deleting a scheduled report"""
        schedule_id = getattr(TestScheduledReports, 'created_schedule_id', None)
        if not schedule_id:
            pytest.skip("No schedule created to delete")
        
        response = client.delete(
            f"/api/admin/reports/schedules/{schedule_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("success") == True
        
        # Verify deletion
        response = client.get(
            "/api/admin/reports/schedules",
            headers=auth_headers
        )
        schedules = response.json().get("schedules", [])
        schedule_ids = [s["schedule_id"] for s in schedules]
        assert schedule_id not in schedule_ids, "Schedule was not deleted"
    
    def test_delete_nonexistent_schedule(self, client, auth_headers):
        """Test deleting a non-existent schedule returns 404"""
        response = client.delete(
            "/api/admin/reports/schedules/SCHED-NONEXISTENT",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestReportHistory:
    """Tests for report history and execution endpoints"""

    @pytest.fixture
    def admin_token(self, client):
        response = client.post(
            "/api/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_get_report_history(self, client, auth_headers):
        """Test getting report download history"""
        response = client.get(
            "/api/admin/reports/history",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "history" in data
        assert "total" in data
        assert isinstance(data["history"], list)
    
    def test_get_report_executions(self, client, auth_headers):
        """Test getting scheduled report execution history"""
        response = client.get(
            "/api/admin/reports/executions",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "executions" in data
        assert "total" in data
        assert isinstance(data["executions"], list)


class TestReportGenerateAllTypes:
    """Test generating reports for all 7 report types"""

    @pytest.fixture
    def admin_token(self, client):
        response = client.post(
            "/api/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    @pytest.mark.parametrize("report_type", [
        "revenue", "orders", "clients", "leads", "compliance", "enablement", "consent"
    ])
    def test_generate_all_report_types_csv(self, auth_headers, report_type):
        """Test generating CSV for all report types"""
        response = client.post(
            "/api/admin/reports/generate",
            headers=auth_headers,
            json={
                "report_type": report_type,
                "period": "30d",
                "format": "csv"
            }
        )
        assert response.status_code == 200, f"Failed to generate {report_type} CSV report"
        assert "text/csv" in response.headers.get("content-type", "")
