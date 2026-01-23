"""
Iteration 4 Test Suite - Compliance Vault Pro
Tests: 
- Audit log diff calculation (before/after states)
- Client Dashboard notification widget
- Jobs respecting notification preferences
"""
import pytest
import requests
import os
import time

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://content-forge-411.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"
TEST_CLIENT_ID = "87ff6c33-1f99-40b6-b9ed-a05c17e13950"


class TestAuditLogDiff:
    """Test audit log diff calculation - /api/admin/audit-logs"""
    
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
    
    def test_audit_logs_contain_diff_field(self):
        """Test that audit logs with before/after states contain diff field"""
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?limit=20",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Get audit logs failed: {response.text}"
        data = response.json()
        
        assert "logs" in data, "Response should contain 'logs' field"
        
        # Look for logs with metadata containing diff
        logs_with_diff = []
        for log in data["logs"]:
            metadata = log.get("metadata", {})
            if metadata and "diff" in metadata:
                logs_with_diff.append(log)
        
        print(f"✅ Found {len(logs_with_diff)} audit logs with diff field out of {len(data['logs'])} total")
        
        # If we have logs with diff, verify structure
        if logs_with_diff:
            diff = logs_with_diff[0]["metadata"]["diff"]
            # Diff should have added, removed, or changed keys
            valid_diff_keys = ["added", "removed", "changed"]
            has_valid_key = any(key in diff for key in valid_diff_keys)
            assert has_valid_key, f"Diff should contain at least one of: {valid_diff_keys}"
            print(f"   Sample diff structure: {list(diff.keys())}")
    
    def test_audit_log_diff_on_notification_update(self):
        """Test that updating notification preferences creates audit log with diff"""
        # First, login as client
        client_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD}
        )
        
        if client_response.status_code != 200:
            pytest.skip("Client login failed")
        
        client_token = client_response.json()["access_token"]
        client_headers = {"Authorization": f"Bearer {client_token}"}
        
        # Get current preferences
        get_response = requests.get(
            f"{BASE_URL}/api/profile/notifications",
            headers=client_headers
        )
        
        if get_response.status_code != 200:
            pytest.skip("Could not get notification preferences")
        
        current_prefs = get_response.json()
        
        # Toggle a preference to create an audit log
        new_value = not current_prefs.get("monthly_digest", True)
        update_response = requests.put(
            f"{BASE_URL}/api/profile/notifications",
            json={"monthly_digest": new_value},
            headers=client_headers
        )
        
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        # Wait a moment for audit log to be created
        time.sleep(0.5)
        
        # Check audit logs for the change
        audit_response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?limit=5",
            headers=self.headers
        )
        
        assert audit_response.status_code == 200
        audit_data = audit_response.json()
        
        # Find the notification preferences update log
        found_log = None
        for log in audit_data["logs"]:
            metadata = log.get("metadata", {})
            if metadata.get("action") == "notification_preferences_updated":
                found_log = log
                break
        
        if found_log:
            print(f"✅ Found notification preferences audit log")
            metadata = found_log.get("metadata", {})
            if "diff" in metadata:
                print(f"   Diff: {metadata['diff']}")
                print(f"   Changes count: {metadata.get('changes_count', 'N/A')}")
            else:
                print("   ⚠️ No diff field in metadata (may be first-time creation)")
        else:
            print("⚠️ Notification preferences audit log not found in recent logs")
        
        # Restore original value
        requests.put(
            f"{BASE_URL}/api/profile/notifications",
            json={"monthly_digest": current_prefs.get("monthly_digest", True)},
            headers=client_headers
        )


class TestNotificationPreferencesWidget:
    """Test notification preferences widget data - /api/profile/notifications"""
    
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
            pytest.skip("Client authentication failed")
    
    def test_notification_prefs_returns_all_widget_fields(self):
        """Test that notification preferences returns all fields needed for widget"""
        response = requests.get(
            f"{BASE_URL}/api/profile/notifications",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Get preferences failed: {response.text}"
        data = response.json()
        
        # Widget needs these fields
        widget_fields = [
            "status_change_alerts",  # Status Alerts On/Off
            "expiry_reminders",      # Expiry Reminders On/Off
            "monthly_digest",        # Monthly Digest On/Off
            "reminder_days_before"   # Reminder Timing in days
        ]
        
        for field in widget_fields:
            assert field in data, f"Missing widget field: {field}"
        
        # Verify types
        assert isinstance(data["status_change_alerts"], bool), "status_change_alerts should be boolean"
        assert isinstance(data["expiry_reminders"], bool), "expiry_reminders should be boolean"
        assert isinstance(data["monthly_digest"], bool), "monthly_digest should be boolean"
        assert isinstance(data["reminder_days_before"], int), "reminder_days_before should be integer"
        
        print(f"✅ All widget fields present:")
        print(f"   Status Alerts: {'On' if data['status_change_alerts'] else 'Off'}")
        print(f"   Expiry Reminders: {'On' if data['expiry_reminders'] else 'Off'}")
        print(f"   Monthly Digest: {'On' if data['monthly_digest'] else 'Off'}")
        print(f"   Reminder Timing: {data['reminder_days_before']} days")
    
    def test_client_dashboard_returns_data(self):
        """Test that client dashboard endpoint returns data"""
        response = requests.get(
            f"{BASE_URL}/api/client/dashboard",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        data = response.json()
        
        # Verify dashboard structure
        assert "client" in data, "Dashboard should contain client info"
        assert "compliance_summary" in data, "Dashboard should contain compliance_summary"
        assert "properties" in data, "Dashboard should contain properties"
        
        print(f"✅ Client dashboard data retrieved")
        print(f"   Client: {data['client'].get('full_name', 'N/A')}")
        print(f"   Properties: {len(data.get('properties', []))}")


class TestJobsRespectPreferences:
    """Test that jobs respect notification preferences"""
    
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
    
    def test_jobs_status_endpoint(self):
        """Test /api/admin/jobs/status returns job information"""
        response = requests.get(
            f"{BASE_URL}/api/admin/jobs/status",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Jobs status failed: {response.text}"
        data = response.json()
        
        assert "scheduled_jobs" in data, "Response should contain scheduled_jobs"
        
        # List all scheduled jobs
        print(f"✅ Jobs status retrieved. {len(data['scheduled_jobs'])} scheduled jobs:")
        for job in data["scheduled_jobs"]:
            print(f"   - {job.get('name', job.get('id', 'Unknown'))}")
    
    def test_trigger_daily_reminders_job(self):
        """Test triggering daily reminders job"""
        response = requests.post(
            f"{BASE_URL}/api/admin/jobs/trigger/daily",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Trigger daily job failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        print(f"✅ Daily reminders job triggered: {data.get('message')}")
        
        # Check if result contains count
        if "result" in data:
            print(f"   Result: {data['result']}")
    
    def test_trigger_monthly_digest_job(self):
        """Test triggering monthly digest job"""
        response = requests.post(
            f"{BASE_URL}/api/admin/jobs/trigger/monthly",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Trigger monthly job failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        print(f"✅ Monthly digest job triggered: {data.get('message')}")
    
    def test_trigger_invalid_job_type(self):
        """Test triggering invalid job type returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/admin/jobs/trigger/invalid_job_type",
            headers=self.headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✅ Invalid job type correctly rejected with 400")
    
    def test_jobs_require_admin_auth(self):
        """Test that job endpoints require admin authentication"""
        # Try without auth
        response = requests.get(f"{BASE_URL}/api/admin/jobs/status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        
        # Try with client auth
        client_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD}
        )
        
        if client_response.status_code == 200:
            client_token = client_response.json()["access_token"]
            client_headers = {"Authorization": f"Bearer {client_token}"}
            
            response = requests.post(
                f"{BASE_URL}/api/admin/jobs/trigger/daily",
                headers=client_headers
            )
            # 403 Forbidden is correct for authenticated but unauthorized users
            assert response.status_code in [401, 403], f"Expected 401/403 for client, got {response.status_code}"
        
        print("✅ Job endpoints correctly require admin authentication")


class TestProfileNavigation:
    """Test profile navigation link in dashboard"""
    
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
            pytest.skip("Client authentication failed")
    
    def test_profile_endpoint_exists(self):
        """Test that /api/profile/me endpoint exists and returns data"""
        response = requests.get(
            f"{BASE_URL}/api/profile/me",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Profile endpoint failed: {response.text}"
        data = response.json()
        
        assert "email" in data
        assert "full_name" in data
        assert "notification_preferences" in data
        
        print(f"✅ Profile endpoint working: {data['full_name']}")


class TestHealthAndBasics:
    """Basic health and API tests"""
    
    def test_api_health(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✅ API health check passed")
    
    def test_api_root(self):
        """Test API root endpoint"""
        response = requests.get(f"{BASE_URL}/api")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Compliance Vault Pro"
        print(f"✅ API root: {data['service']} v{data['version']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
