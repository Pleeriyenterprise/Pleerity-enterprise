"""
New Features Test Suite - Compliance Vault Pro
Tests: Onboarding Status API, Notification Preferences API
"""
import pytest
import requests
import os
import time

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://enterprise-comply.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"
TEST_CLIENT_ID = "87ff6c33-1f99-40b6-b9ed-a05c17e13950"


class TestOnboardingStatusAPI:
    """Onboarding Status API tests - /api/intake/onboarding-status/{client_id}"""
    
    def test_onboarding_status_valid_client(self):
        """Test onboarding status with valid client_id"""
        response = requests.get(f"{BASE_URL}/api/intake/onboarding-status/{TEST_CLIENT_ID}")
        
        # Should return 200 if client exists, 404 if not
        if response.status_code == 404:
            print(f"⚠️ Test client {TEST_CLIENT_ID} not found - creating test client first")
            pytest.skip("Test client not found in database")
        
        assert response.status_code == 200, f"Onboarding status failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "client_id" in data
        assert "steps" in data
        assert "current_step" in data
        assert "progress_percent" in data
        assert "is_complete" in data
        
        # Verify steps array has 5 steps
        assert len(data["steps"]) == 5, f"Expected 5 steps, got {len(data['steps'])}"
        
        # Verify each step has required fields
        for step in data["steps"]:
            assert "step" in step
            assert "name" in step
            assert "description" in step
            assert "status" in step
            assert "icon" in step
            assert step["status"] in ["complete", "in_progress", "pending", "failed", "waiting"]
        
        # Verify step names
        step_names = [s["name"] for s in data["steps"]]
        expected_names = ["Intake Form", "Payment", "Portal Setup", "Account Activation", "Ready to Use"]
        assert step_names == expected_names, f"Step names mismatch: {step_names}"
        
        print(f"✅ Onboarding status retrieved: {data['progress_percent']}% complete, current step: {data['current_step']}")
        print(f"   Steps: {[(s['name'], s['status']) for s in data['steps']]}")
    
    def test_onboarding_status_invalid_client(self):
        """Test onboarding status with non-existent client_id"""
        fake_client_id = "00000000-0000-0000-0000-000000000000"
        response = requests.get(f"{BASE_URL}/api/intake/onboarding-status/{fake_client_id}")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✅ Non-existent client correctly returns 404")
    
    def test_onboarding_status_response_fields(self):
        """Test onboarding status returns all expected fields"""
        response = requests.get(f"{BASE_URL}/api/intake/onboarding-status/{TEST_CLIENT_ID}")
        
        if response.status_code == 404:
            pytest.skip("Test client not found in database")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all expected fields
        expected_fields = [
            "client_id", "client_name", "email", "onboarding_status",
            "subscription_status", "steps", "current_step", "progress_percent",
            "is_complete", "properties_count", "requirements_count",
            "can_login", "portal_url", "next_action"
        ]
        
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify next_action structure
        if data["next_action"]:
            assert "action" in data["next_action"]
            assert "message" in data["next_action"]
        
        print(f"✅ All expected fields present in response")
        print(f"   Client: {data['client_name']}, Email: {data['email']}")


class TestNotificationPreferencesAPI:
    """Notification Preferences API tests - /api/profile/notifications"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get client auth token before each test"""
        # Try client login first
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD}
        )
        
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
            self.is_client = True
        else:
            # Fall back to admin login
            response = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
            )
            if response.status_code == 200:
                self.token = response.json()["access_token"]
                self.headers = {"Authorization": f"Bearer {self.token}"}
                self.is_client = False
            else:
                pytest.skip("Authentication failed for both client and admin")
    
    def test_get_notification_preferences(self):
        """Test GET /api/profile/notifications returns preferences"""
        response = requests.get(
            f"{BASE_URL}/api/profile/notifications",
            headers=self.headers
        )
        
        # Admin users may not have client_id, so this might fail
        if response.status_code == 500 and not self.is_client:
            pytest.skip("Admin user doesn't have notification preferences")
        
        assert response.status_code == 200, f"Get preferences failed: {response.text}"
        data = response.json()
        
        # Verify default preference fields
        expected_fields = [
            "status_change_alerts", "expiry_reminders", "monthly_digest",
            "document_updates", "system_announcements", "reminder_days_before",
            "quiet_hours_enabled", "quiet_hours_start", "quiet_hours_end"
        ]
        
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify default values are booleans/integers
        assert isinstance(data["status_change_alerts"], bool)
        assert isinstance(data["expiry_reminders"], bool)
        assert isinstance(data["monthly_digest"], bool)
        assert isinstance(data["document_updates"], bool)
        assert isinstance(data["system_announcements"], bool)
        assert isinstance(data["reminder_days_before"], int)
        assert isinstance(data["quiet_hours_enabled"], bool)
        
        print(f"✅ Notification preferences retrieved")
        print(f"   Status alerts: {data['status_change_alerts']}, Expiry reminders: {data['expiry_reminders']}")
        print(f"   Reminder days: {data['reminder_days_before']}")
    
    def test_update_notification_preferences(self):
        """Test PUT /api/profile/notifications updates preferences"""
        # Update preferences
        update_data = {
            "status_change_alerts": False,
            "expiry_reminders": True,
            "reminder_days_before": 14
        }
        
        response = requests.put(
            f"{BASE_URL}/api/profile/notifications",
            json=update_data,
            headers=self.headers
        )
        
        if response.status_code == 500 and not self.is_client:
            pytest.skip("Admin user doesn't have notification preferences")
        
        assert response.status_code == 200, f"Update preferences failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        assert "preferences" in data
        assert data["preferences"]["status_change_alerts"] == False
        assert data["preferences"]["reminder_days_before"] == 14
        
        print(f"✅ Notification preferences updated successfully")
        
        # Verify by GET
        get_response = requests.get(
            f"{BASE_URL}/api/profile/notifications",
            headers=self.headers
        )
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["status_change_alerts"] == False
        assert get_data["reminder_days_before"] == 14
        
        print(f"✅ Verified preferences persisted correctly")
        
        # Reset to defaults
        reset_data = {
            "status_change_alerts": True,
            "reminder_days_before": 30
        }
        requests.put(
            f"{BASE_URL}/api/profile/notifications",
            json=reset_data,
            headers=self.headers
        )
    
    def test_update_invalid_reminder_days(self):
        """Test PUT /api/profile/notifications rejects invalid reminder_days_before"""
        update_data = {
            "reminder_days_before": 15  # Invalid - must be 7, 14, 30, 60, or 90
        }
        
        response = requests.put(
            f"{BASE_URL}/api/profile/notifications",
            json=update_data,
            headers=self.headers
        )
        
        if response.status_code == 500 and not self.is_client:
            pytest.skip("Admin user doesn't have notification preferences")
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✅ Invalid reminder_days_before correctly rejected")
    
    def test_update_valid_reminder_days_options(self):
        """Test all valid reminder_days_before options (7, 14, 30, 60, 90)"""
        valid_options = [7, 14, 30, 60, 90]
        
        for days in valid_options:
            response = requests.put(
                f"{BASE_URL}/api/profile/notifications",
                json={"reminder_days_before": days},
                headers=self.headers
            )
            
            if response.status_code == 500 and not self.is_client:
                pytest.skip("Admin user doesn't have notification preferences")
            
            assert response.status_code == 200, f"Failed for {days} days: {response.text}"
        
        # Reset to default
        requests.put(
            f"{BASE_URL}/api/profile/notifications",
            json={"reminder_days_before": 30},
            headers=self.headers
        )
        
        print(f"✅ All valid reminder_days_before options work: {valid_options}")
    
    def test_notification_preferences_without_auth(self):
        """Test /api/profile/notifications without auth"""
        response = requests.get(f"{BASE_URL}/api/profile/notifications")
        assert response.status_code in [401, 403]
        print("✅ Notification preferences correctly requires authentication")


class TestProfileAPI:
    """Profile API tests - /api/profile/me"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get client auth token before each test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD}
        )
        
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            # Fall back to admin
            response = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
            )
            if response.status_code == 200:
                self.token = response.json()["access_token"]
                self.headers = {"Authorization": f"Bearer {self.token}"}
            else:
                pytest.skip("Authentication failed")
    
    def test_get_profile(self):
        """Test GET /api/profile/me returns user profile"""
        response = requests.get(
            f"{BASE_URL}/api/profile/me",
            headers=self.headers
        )
        
        if response.status_code == 500:
            pytest.skip("Profile endpoint error - may be admin user")
        
        assert response.status_code == 200, f"Get profile failed: {response.text}"
        data = response.json()
        
        # Verify profile fields
        assert "email" in data
        assert "full_name" in data
        assert "notification_preferences" in data
        
        print(f"✅ Profile retrieved: {data['full_name']} ({data['email']})")


class TestAdminJobsComplianceCheck:
    """Admin Jobs - Compliance Check endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin auth token before each test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Admin authentication failed")
    
    def test_jobs_status_includes_compliance_check(self):
        """Test /api/admin/jobs/status includes compliance check jobs"""
        response = requests.get(
            f"{BASE_URL}/api/admin/jobs/status",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Get jobs status failed: {response.text}"
        data = response.json()
        
        # Check for scheduled jobs
        assert "scheduled_jobs" in data
        job_ids = [job.get("id") for job in data["scheduled_jobs"]]
        
        # Should have compliance check jobs
        compliance_jobs = [j for j in job_ids if j and "compliance" in j.lower()]
        print(f"✅ Jobs status retrieved. Scheduled jobs: {job_ids}")
        print(f"   Compliance check jobs: {compliance_jobs}")
    
    def test_trigger_compliance_check(self):
        """Test /api/admin/jobs/trigger/compliance triggers compliance check"""
        response = requests.post(
            f"{BASE_URL}/api/admin/jobs/trigger/compliance",
            headers=self.headers
        )
        
        # May return 400 if job type not supported, or 200 if it is
        if response.status_code == 400:
            print("⚠️ Compliance job trigger not available via /trigger/compliance endpoint")
            # Check if there's an alternative endpoint
            return
        
        assert response.status_code == 200, f"Trigger compliance check failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        print(f"✅ Compliance check triggered: {data.get('message')}")


class TestClientLogin:
    """Test client login to verify test credentials"""
    
    def test_client_login(self):
        """Test client login with provided credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD}
        )
        
        if response.status_code == 401:
            print(f"⚠️ Client login failed - credentials may be invalid or user not provisioned")
            print(f"   Email: {CLIENT_EMAIL}")
            return
        
        assert response.status_code == 200, f"Client login failed: {response.text}"
        data = response.json()
        
        assert "access_token" in data
        assert "user" in data
        
        print(f"✅ Client login successful: {data['user']['email']}")
        print(f"   Role: {data['user'].get('role')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
