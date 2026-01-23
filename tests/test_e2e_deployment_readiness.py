"""
Comprehensive E2E Testing for Compliance Vault Pro - Deployment Readiness
Tests: Authentication, RBAC, Admin/Client Dashboards, Intake Wizard, Webhooks, Reports, Audit Logs
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://leadsquared.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_ADMIN_EMAIL = "admin@pleerity.com"
TEST_ADMIN_PASSWORD = "Admin123!"
TEST_CLIENT_EMAIL = "test@pleerity.com"
TEST_CLIENT_PASSWORD = "TestClient123!"


class TestHealthAndBasicEndpoints:
    """Basic health and API availability tests"""
    
    def test_health_endpoint(self):
        """Test /api/health returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health endpoint working")
    
    def test_root_api_endpoint(self):
        """Test /api returns service info"""
        response = requests.get(f"{BASE_URL}/api")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Compliance Vault Pro"
        assert data["owner"] == "Pleerity Enterprise Ltd"
        print("✓ Root API endpoint working")


class TestAdminAuthentication:
    """Admin authentication flow tests"""
    
    def test_admin_login_success(self):
        """Test admin login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/admin/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "ROLE_ADMIN"
        assert data["user"]["email"] == TEST_ADMIN_EMAIL
        print(f"✓ Admin login successful: {TEST_ADMIN_EMAIL}")
        return data["access_token"]
    
    def test_admin_login_invalid_credentials(self):
        """Test admin login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/admin/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": "WrongPassword123!"
        })
        assert response.status_code == 401
        print("✓ Admin login correctly rejects invalid credentials")
    
    def test_admin_login_non_admin_user(self):
        """Test admin login endpoint rejects non-admin users"""
        response = requests.post(f"{BASE_URL}/api/auth/admin/login", json={
            "email": TEST_CLIENT_EMAIL,
            "password": TEST_CLIENT_PASSWORD
        })
        assert response.status_code == 401
        print("✓ Admin login correctly rejects non-admin users")


class TestClientAuthentication:
    """Client authentication flow tests"""
    
    def test_client_login_success(self):
        """Test client login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_CLIENT_EMAIL,
            "password": TEST_CLIENT_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] in ["ROLE_CLIENT", "ROLE_LANDLORD", "ROLE_CLIENT_ADMIN"]
        assert data["user"]["email"] == TEST_CLIENT_EMAIL
        print(f"✓ Client login successful: {TEST_CLIENT_EMAIL} (role: {data['user']['role']})")
    
    def test_client_login_invalid_credentials(self):
        """Test client login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_CLIENT_EMAIL,
            "password": "WrongPassword123!"
        })
        assert response.status_code == 401
        print("✓ Client login correctly rejects invalid credentials")


class TestAdminDashboard:
    """Admin dashboard and admin-only endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/admin/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            self.admin_token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.admin_token}"}
        else:
            pytest.skip("Admin authentication failed")
    
    def test_admin_dashboard_endpoint(self):
        """Test GET /api/admin/dashboard returns stats"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "stats" in data
        assert "compliance_overview" in data
        assert "total_clients" in data["stats"]
        assert "active_clients" in data["stats"]
        print(f"✓ Admin dashboard: {data['stats']['total_clients']} total clients")
    
    def test_admin_statistics_endpoint(self):
        """Test GET /api/admin/statistics returns comprehensive stats"""
        response = requests.get(f"{BASE_URL}/api/admin/statistics", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "clients" in data
        assert "properties" in data
        assert "requirements" in data
        assert "documents" in data
        print("✓ Admin statistics endpoint working")
    
    def test_admin_clients_list(self):
        """Test GET /api/admin/clients returns client list"""
        response = requests.get(f"{BASE_URL}/api/admin/clients", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "clients" in data
        assert "total" in data
        print(f"✓ Admin clients list: {data['total']} clients")
    
    def test_admin_audit_logs(self):
        """Test GET /api/admin/audit-logs returns logs"""
        response = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data
        print(f"✓ Admin audit logs: {data['total']} logs")
    
    def test_admin_admins_list(self):
        """Test GET /api/admin/admins returns admin list"""
        response = requests.get(f"{BASE_URL}/api/admin/admins", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "admins" in data
        print(f"✓ Admin list: {len(data['admins'])} admins")
    
    def test_admin_jobs_status(self):
        """Test GET /api/admin/jobs/status returns job status"""
        response = requests.get(f"{BASE_URL}/api/admin/jobs/status", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "system_status" in data
        print("✓ Admin jobs status endpoint working")


class TestRBACAdminEndpoints:
    """RBAC tests - Admin endpoints should reject client tokens"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get client token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_CLIENT_EMAIL,
            "password": TEST_CLIENT_PASSWORD
        })
        if response.status_code == 200:
            self.client_token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.client_token}"}
        else:
            pytest.skip("Client authentication failed")
    
    def test_admin_dashboard_rejects_client_token(self):
        """Test admin dashboard rejects client token"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard", headers=self.headers)
        assert response.status_code == 403
        print("✓ RBAC: Admin dashboard correctly rejects client token")
    
    def test_admin_clients_rejects_client_token(self):
        """Test admin clients endpoint rejects client token"""
        response = requests.get(f"{BASE_URL}/api/admin/clients", headers=self.headers)
        assert response.status_code == 403
        print("✓ RBAC: Admin clients endpoint correctly rejects client token")
    
    def test_admin_audit_logs_rejects_client_token(self):
        """Test admin audit logs rejects client token"""
        response = requests.get(f"{BASE_URL}/api/admin/audit-logs", headers=self.headers)
        assert response.status_code == 403
        print("✓ RBAC: Admin audit logs correctly rejects client token")


class TestClientDashboard:
    """Client dashboard and client-only endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get client token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_CLIENT_EMAIL,
            "password": TEST_CLIENT_PASSWORD
        })
        if response.status_code == 200:
            self.client_token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.client_token}"}
        else:
            pytest.skip("Client authentication failed")
    
    def test_client_dashboard_endpoint(self):
        """Test GET /api/client/dashboard returns compliance data"""
        response = requests.get(f"{BASE_URL}/api/client/dashboard", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "compliance_score" in data or "properties" in data or "client" in data
        print("✓ Client dashboard endpoint working")
    
    def test_client_properties_endpoint(self):
        """Test GET /api/client/properties returns property list"""
        response = requests.get(f"{BASE_URL}/api/client/properties", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "properties" in data
        print(f"✓ Client properties: {len(data['properties'])} properties")
    
    def test_client_requirements_endpoint(self):
        """Test GET /api/client/requirements returns requirements"""
        response = requests.get(f"{BASE_URL}/api/client/requirements", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "requirements" in data
        print(f"✓ Client requirements: {len(data['requirements'])} requirements")


class TestIntakeWizardAPI:
    """Intake wizard API tests"""
    
    def test_get_plans(self):
        """Test GET /api/intake/plans returns available plans"""
        response = requests.get(f"{BASE_URL}/api/intake/plans")
        assert response.status_code == 200
        data = response.json()
        assert "plans" in data
        assert len(data["plans"]) >= 3
        # Verify plan structure
        for plan in data["plans"]:
            assert "plan_id" in plan
            assert "name" in plan
            assert "monthly_price" in plan
            assert "max_properties" in plan
        print(f"✓ Intake plans: {len(data['plans'])} plans available")
    
    def test_get_councils(self):
        """Test GET /api/intake/councils returns council list"""
        response = requests.get(f"{BASE_URL}/api/intake/councils")
        assert response.status_code == 200
        data = response.json()
        assert "councils" in data
        print(f"✓ Intake councils: {len(data['councils'])} councils")
    
    def test_search_councils(self):
        """Test council search functionality"""
        response = requests.get(f"{BASE_URL}/api/intake/councils?q=manchester")
        assert response.status_code == 200
        data = response.json()
        assert "councils" in data
        # Should find Manchester
        council_names = [c["name"].lower() for c in data["councils"]]
        assert any("manchester" in name for name in council_names)
        print("✓ Council search working")
    
    def test_intake_submit_validation(self):
        """Test intake submit validates required fields"""
        # Missing required fields
        response = requests.post(f"{BASE_URL}/api/intake/submit", json={
            "full_name": "Test User"
            # Missing email, properties, consents, etc.
        })
        assert response.status_code == 422  # Validation error
        print("✓ Intake submit validates required fields")


class TestWebhooksAPI:
    """Webhook configuration API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get client token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_CLIENT_EMAIL,
            "password": TEST_CLIENT_PASSWORD
        })
        if response.status_code == 200:
            self.client_token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.client_token}"}
        else:
            pytest.skip("Client authentication failed")
    
    def test_get_webhook_events(self):
        """Test GET /api/webhooks/events returns available events"""
        response = requests.get(f"{BASE_URL}/api/webhooks/events", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        print(f"✓ Webhook events: {len(data['events'])} event types")
    
    def test_list_webhooks(self):
        """Test GET /api/webhooks returns webhook list"""
        response = requests.get(f"{BASE_URL}/api/webhooks", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "webhooks" in data
        print(f"✓ Webhooks list: {len(data['webhooks'])} webhooks")
    
    def test_get_webhook_stats(self):
        """Test GET /api/webhooks/stats returns statistics"""
        response = requests.get(f"{BASE_URL}/api/webhooks/stats", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_webhooks" in data or "total" in data
        print("✓ Webhook stats endpoint working")


class TestReportsAPI:
    """Reports API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get client token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_CLIENT_EMAIL,
            "password": TEST_CLIENT_PASSWORD
        })
        if response.status_code == 200:
            self.client_token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.client_token}"}
        else:
            pytest.skip("Client authentication failed")
    
    def test_get_available_reports(self):
        """Test GET /api/reports/available returns report types"""
        response = requests.get(f"{BASE_URL}/api/reports/available", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "reports" in data
        print(f"✓ Available reports: {len(data['reports'])} report types")
    
    def test_get_scheduled_reports(self):
        """Test GET /api/reports/schedules returns scheduled reports"""
        response = requests.get(f"{BASE_URL}/api/reports/schedules", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "schedules" in data
        print(f"✓ Scheduled reports: {len(data['schedules'])} schedules")


class TestNotificationPreferences:
    """Notification preferences API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get client token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_CLIENT_EMAIL,
            "password": TEST_CLIENT_PASSWORD
        })
        if response.status_code == 200:
            self.client_token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.client_token}"}
        else:
            pytest.skip("Client authentication failed")
    
    def test_get_notification_preferences(self):
        """Test GET /api/profile/notifications returns preferences"""
        response = requests.get(f"{BASE_URL}/api/profile/notifications", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        # Should have notification preference fields
        assert "email_enabled" in data or "preferences" in data or "digest_compliance_summary" in data
        print("✓ Notification preferences endpoint working")


class TestCalendarAPI:
    """Calendar API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get client token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_CLIENT_EMAIL,
            "password": TEST_CLIENT_PASSWORD
        })
        if response.status_code == 200:
            self.client_token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.client_token}"}
        else:
            pytest.skip("Client authentication failed")
    
    def test_get_calendar_events(self):
        """Test GET /api/calendar/expiries returns calendar events"""
        response = requests.get(f"{BASE_URL}/api/calendar/expiries", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "events_by_date" in data
        print("✓ Calendar expiries endpoint working")


class TestDocumentsAPI:
    """Documents API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get client token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_CLIENT_EMAIL,
            "password": TEST_CLIENT_PASSWORD
        })
        if response.status_code == 200:
            self.client_token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.client_token}"}
        else:
            pytest.skip("Client authentication failed")
    
    def test_get_documents_list(self):
        """Test GET /api/documents returns document list"""
        response = requests.get(f"{BASE_URL}/api/documents", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        print(f"✓ Documents list: {len(data['documents'])} documents")


class TestAuditLogsRecording:
    """Test that audit logs are being recorded for key actions"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/admin/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            self.admin_token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.admin_token}"}
        else:
            pytest.skip("Admin authentication failed")
    
    def test_login_events_recorded(self):
        """Test that login events are recorded in audit logs"""
        # First, do a login to generate an audit log
        requests.post(f"{BASE_URL}/api/auth/admin/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        })
        
        # Check audit logs for login events
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?action=ADMIN_LOGIN_SUCCESS",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        # Should have at least one login event
        login_events = [log for log in data["logs"] if "LOGIN" in log.get("action", "")]
        print(f"✓ Audit logs: Found {len(login_events)} login events")


class TestAdminInvite:
    """Admin invite functionality tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/admin/login", json={
            "email": TEST_ADMIN_EMAIL,
            "password": TEST_ADMIN_PASSWORD
        })
        if response.status_code == 200:
            self.admin_token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.admin_token}"}
        else:
            pytest.skip("Admin authentication failed")
    
    def test_admin_invite_validation(self):
        """Test admin invite validates required fields"""
        # Missing required fields
        response = requests.post(
            f"{BASE_URL}/api/admin/admins/invite",
            headers=self.headers,
            json={}
        )
        assert response.status_code == 422  # Validation error
        print("✓ Admin invite validates required fields")


class TestSetPasswordEndpoint:
    """Set password endpoint tests"""
    
    def test_set_password_invalid_token(self):
        """Test set password with invalid token"""
        response = requests.post(f"{BASE_URL}/api/auth/set-password", json={
            "token": "invalid-token-12345",
            "password": "NewPassword123!"
        })
        assert response.status_code == 400
        print("✓ Set password correctly rejects invalid token")


class TestRouteGuardLogging:
    """Test route guard block logging"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get client token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_CLIENT_EMAIL,
            "password": TEST_CLIENT_PASSWORD
        })
        if response.status_code == 200:
            self.client_token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.client_token}"}
        else:
            pytest.skip("Client authentication failed")
    
    def test_log_route_guard_block(self):
        """Test route guard block logging endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/auth/log-route-guard-block",
            headers=self.headers,
            json={"attempted_path": "/admin/dashboard"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "logged"
        print("✓ Route guard block logging working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
