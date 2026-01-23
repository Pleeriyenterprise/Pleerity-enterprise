"""
Admin Endpoints Test Suite - Compliance Vault Pro
Tests admin authentication, dashboard, clients, audit logs, jobs, and invitations.
"""
import pytest
import requests
import os

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://reportico.preview.emergentagent.com').rstrip('/')

# Admin credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


class TestHealthCheck:
    """Health check endpoint tests - run first to verify API is up"""
    
    def test_health_endpoint(self):
        """Test /api/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print(f"✅ Health check passed: {data}")


class TestAdminAuthentication:
    """Admin authentication tests"""
    
    def test_admin_login_success(self):
        """Test admin login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "ROLE_ADMIN"
        print(f"✅ Admin login successful: {data['user']['email']}")
        return data["access_token"]
    
    def test_admin_login_invalid_password(self):
        """Test admin login with invalid password"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": "WrongPassword123!"}
        )
        assert response.status_code == 401
        print("✅ Invalid password correctly rejected")
    
    def test_admin_login_invalid_email(self):
        """Test admin login with non-existent email"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "nonexistent@pleerity.com", "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 401
        print("✅ Non-existent email correctly rejected")


class TestAdminDashboard:
    """Admin dashboard endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Admin authentication failed")
    
    def test_dashboard_with_auth(self):
        """Test /api/admin/dashboard with valid auth"""
        response = requests.get(
            f"{BASE_URL}/api/admin/dashboard",
            headers=self.headers
        )
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "stats" in data
        assert "compliance_overview" in data
        
        # Verify stats fields
        stats = data["stats"]
        assert "total_clients" in stats
        assert "active_clients" in stats
        assert "pending_clients" in stats
        assert "provisioned_clients" in stats
        assert "total_properties" in stats
        
        print(f"✅ Dashboard data retrieved: {stats['total_clients']} total clients")
    
    def test_dashboard_without_auth(self):
        """Test /api/admin/dashboard without auth token"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard")
        assert response.status_code in [401, 403]
        print("✅ Dashboard correctly requires authentication")


class TestAdminClients:
    """Admin clients endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Admin authentication failed")
    
    def test_get_clients_list(self):
        """Test /api/admin/clients returns client list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/clients",
            headers=self.headers
        )
        assert response.status_code == 200, f"Get clients failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "clients" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        assert isinstance(data["clients"], list)
        
        print(f"✅ Clients list retrieved: {data['total']} total clients")
    
    def test_get_clients_with_pagination(self):
        """Test /api/admin/clients with pagination params"""
        response = requests.get(
            f"{BASE_URL}/api/admin/clients?skip=0&limit=10",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["skip"] == 0
        assert data["limit"] == 10
        print("✅ Clients pagination working correctly")
    
    def test_get_clients_without_auth(self):
        """Test /api/admin/clients without auth"""
        response = requests.get(f"{BASE_URL}/api/admin/clients")
        assert response.status_code in [401, 403]
        print("✅ Clients endpoint correctly requires authentication")


class TestAdminAuditLogs:
    """Admin audit logs endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Admin authentication failed")
    
    def test_get_audit_logs(self):
        """Test /api/admin/audit-logs returns logs"""
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs",
            headers=self.headers
        )
        assert response.status_code == 200, f"Get audit logs failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "logs" in data
        assert "total" in data
        assert "filters" in data
        assert isinstance(data["logs"], list)
        
        print(f"✅ Audit logs retrieved: {data['total']} total logs")
    
    def test_get_audit_logs_with_filters(self):
        """Test /api/admin/audit-logs with action filter"""
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?action=USER_LOGIN_SUCCESS",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # All returned logs should have the filtered action
        for log in data["logs"]:
            assert log["action"] == "USER_LOGIN_SUCCESS"
        
        print(f"✅ Audit logs filtering working: {len(data['logs'])} login success logs")
    
    def test_get_audit_logs_without_auth(self):
        """Test /api/admin/audit-logs without auth"""
        response = requests.get(f"{BASE_URL}/api/admin/audit-logs")
        assert response.status_code in [401, 403]
        print("✅ Audit logs endpoint correctly requires authentication")


class TestAdminJobsStatus:
    """Admin jobs status endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Admin authentication failed")
    
    def test_get_jobs_status(self):
        """Test /api/admin/jobs/status returns job info"""
        response = requests.get(
            f"{BASE_URL}/api/admin/jobs/status",
            headers=self.headers
        )
        assert response.status_code == 200, f"Get jobs status failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "daily_reminders" in data
        assert "monthly_digest" in data
        assert "scheduled_jobs" in data
        assert "system_status" in data
        
        # Verify daily_reminders structure
        assert "last_run" in data["daily_reminders"]
        assert "pending_count" in data["daily_reminders"]
        
        # Verify monthly_digest structure
        assert "last_run" in data["monthly_digest"]
        assert "total_sent" in data["monthly_digest"]
        
        # Verify scheduled_jobs is a list
        assert isinstance(data["scheduled_jobs"], list)
        
        print(f"✅ Jobs status retrieved: {len(data['scheduled_jobs'])} scheduled jobs")
        print(f"   System status: {data['system_status']}")
    
    def test_get_jobs_status_without_auth(self):
        """Test /api/admin/jobs/status without auth"""
        response = requests.get(f"{BASE_URL}/api/admin/jobs/status")
        assert response.status_code in [401, 403]
        print("✅ Jobs status endpoint correctly requires authentication")


class TestAdminJobTrigger:
    """Admin job trigger endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Admin authentication failed")
    
    def test_trigger_daily_job(self):
        """Test /api/admin/jobs/trigger/daily triggers daily reminders"""
        response = requests.post(
            f"{BASE_URL}/api/admin/jobs/trigger/daily",
            headers=self.headers
        )
        assert response.status_code == 200, f"Trigger daily job failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        assert "count" in data
        assert "daily" in data["message"].lower() or "reminders" in data["message"].lower()
        
        print(f"✅ Daily job triggered: {data['message']}, count: {data['count']}")
    
    def test_trigger_monthly_job(self):
        """Test /api/admin/jobs/trigger/monthly triggers monthly digests"""
        response = requests.post(
            f"{BASE_URL}/api/admin/jobs/trigger/monthly",
            headers=self.headers
        )
        assert response.status_code == 200, f"Trigger monthly job failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        assert "count" in data
        
        print(f"✅ Monthly job triggered: {data['message']}, count: {data['count']}")
    
    def test_trigger_invalid_job_type(self):
        """Test /api/admin/jobs/trigger with invalid job type"""
        response = requests.post(
            f"{BASE_URL}/api/admin/jobs/trigger/invalid",
            headers=self.headers
        )
        assert response.status_code == 400
        print("✅ Invalid job type correctly rejected")
    
    def test_trigger_job_without_auth(self):
        """Test /api/admin/jobs/trigger without auth"""
        response = requests.post(f"{BASE_URL}/api/admin/jobs/trigger/daily")
        assert response.status_code in [401, 403]
        print("✅ Job trigger endpoint correctly requires authentication")


class TestAdminClientInvite:
    """Admin client invite endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Admin authentication failed")
    
    def test_invite_client_success(self):
        """Test /api/admin/clients/invite creates new client"""
        import time
        test_email = f"TEST_invite_{int(time.time())}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/admin/clients/invite",
            params={
                "full_name": "Test Invited Client",
                "email": test_email,
                "billing_plan": "PLAN_1"
            },
            headers=self.headers
        )
        assert response.status_code == 200, f"Invite client failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        assert "client_id" in data
        assert "next_steps" in data
        assert isinstance(data["next_steps"], list)
        
        print(f"✅ Client invited: {data['client_id']}")
        
        # Store client_id for cleanup
        self.invited_client_id = data["client_id"]
    
    def test_invite_duplicate_email(self):
        """Test /api/admin/clients/invite rejects duplicate email"""
        import time
        test_email = f"TEST_dup_{int(time.time())}@example.com"
        
        # First invite
        response1 = requests.post(
            f"{BASE_URL}/api/admin/clients/invite",
            params={
                "full_name": "Test Client 1",
                "email": test_email,
                "billing_plan": "PLAN_1"
            },
            headers=self.headers
        )
        assert response1.status_code == 200
        
        # Second invite with same email
        response2 = requests.post(
            f"{BASE_URL}/api/admin/clients/invite",
            params={
                "full_name": "Test Client 2",
                "email": test_email,
                "billing_plan": "PLAN_1"
            },
            headers=self.headers
        )
        assert response2.status_code == 400
        print("✅ Duplicate email correctly rejected")
    
    def test_invite_client_without_auth(self):
        """Test /api/admin/clients/invite without auth"""
        response = requests.post(
            f"{BASE_URL}/api/admin/clients/invite",
            params={
                "full_name": "Test Client",
                "email": "test@example.com",
                "billing_plan": "PLAN_1"
            }
        )
        assert response.status_code in [401, 403]
        print("✅ Client invite endpoint correctly requires authentication")


class TestRootEndpoint:
    """Root API endpoint test"""
    
    def test_root_endpoint(self):
        """Test /api returns service info"""
        response = requests.get(f"{BASE_URL}/api")
        assert response.status_code == 200
        data = response.json()
        
        assert "service" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "operational"
        
        print(f"✅ Root endpoint: {data['service']} v{data['version']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
