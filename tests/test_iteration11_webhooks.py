"""
Test Suite for Iteration 11 - Webhook Notifications and Email Digest Customization

Features tested:
1. Webhook CRUD operations (Create, Read, Update, Delete)
2. Webhook test functionality
3. Webhook enable/disable toggle
4. Webhook secret regeneration
5. Webhook events listing
6. Webhook statistics
7. Notification preferences with digest customization fields
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


class TestWebhookEndpoints:
    """Test webhook CRUD and management endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures - authenticate and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as client
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json().get("access_token")
        assert token, "No access token returned"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Store created webhook IDs for cleanup
        self.created_webhook_ids = []
        
        yield
        
        # Cleanup: Delete created webhooks
        for webhook_id in self.created_webhook_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/webhooks/{webhook_id}")
            except:
                pass
    
    # ==================== GET /api/webhooks/events ====================
    def test_get_available_events(self):
        """Test GET /api/webhooks/events returns available event types"""
        response = self.session.get(f"{BASE_URL}/api/webhooks/events")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "events" in data, "Response should contain 'events'"
        assert "rate_limit" in data, "Response should contain 'rate_limit'"
        assert "signature_info" in data, "Response should contain 'signature_info'"
        
        # Verify event types
        events = data["events"]
        assert len(events) >= 5, "Should have at least 5 event types"
        
        event_types = [e["type"] for e in events]
        assert "compliance.status_changed" in event_types
        assert "requirement.status_changed" in event_types
        assert "document.verification_changed" in event_types
        assert "digest.sent" in event_types
        assert "reminder.sent" in event_types
        
        # Verify rate limit info
        rate_limit = data["rate_limit"]
        assert "max_requests_per_minute" in rate_limit
        assert "max_retries" in rate_limit
        assert "auto_disable_after_failures" in rate_limit
        
        print("✓ GET /api/webhooks/events - All event types returned correctly")
    
    # ==================== POST /api/webhooks ====================
    def test_create_webhook_success(self):
        """Test creating a webhook with valid data"""
        webhook_data = {
            "name": f"TEST_Webhook_{uuid.uuid4().hex[:8]}",
            "url": "https://webhook.site/test-endpoint",
            "event_types": ["compliance.status_changed", "requirement.status_changed"]
        }
        
        response = self.session.post(f"{BASE_URL}/api/webhooks", json=webhook_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "webhook_id" in data, "Response should contain webhook_id"
        assert "secret" in data, "Response should contain secret (only on creation)"
        assert data["message"] == "Webhook created successfully"
        
        # Store for cleanup
        self.created_webhook_ids.append(data["webhook_id"])
        
        # Verify secret format (64 hex chars)
        assert len(data["secret"]) == 64, "Secret should be 64 hex characters"
        
        print(f"✓ POST /api/webhooks - Webhook created: {data['webhook_id']}")
    
    def test_create_webhook_with_custom_secret(self):
        """Test creating a webhook with a custom secret"""
        custom_secret = "my-custom-secret-key-12345678901234567890123456789012"
        webhook_data = {
            "name": f"TEST_CustomSecret_{uuid.uuid4().hex[:8]}",
            "url": "https://webhook.site/custom-secret-test",
            "event_types": ["digest.sent"],
            "secret": custom_secret
        }
        
        response = self.session.post(f"{BASE_URL}/api/webhooks", json=webhook_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["secret"] == custom_secret, "Custom secret should be returned"
        
        self.created_webhook_ids.append(data["webhook_id"])
        print("✓ POST /api/webhooks - Custom secret accepted")
    
    def test_create_webhook_invalid_url(self):
        """Test creating webhook with invalid URL fails"""
        webhook_data = {
            "name": "Invalid URL Webhook",
            "url": "not-a-valid-url",
            "event_types": ["compliance.status_changed"]
        }
        
        response = self.session.post(f"{BASE_URL}/api/webhooks", json=webhook_data)
        assert response.status_code == 400, f"Should fail with 400: {response.text}"
        assert "URL must start with http" in response.json().get("detail", "")
        
        print("✓ POST /api/webhooks - Invalid URL rejected")
    
    def test_create_webhook_invalid_event_type(self):
        """Test creating webhook with invalid event type fails"""
        webhook_data = {
            "name": "Invalid Event Webhook",
            "url": "https://webhook.site/test",
            "event_types": ["invalid.event.type"]
        }
        
        response = self.session.post(f"{BASE_URL}/api/webhooks", json=webhook_data)
        assert response.status_code == 400, f"Should fail with 400: {response.text}"
        assert "Invalid event type" in response.json().get("detail", "")
        
        print("✓ POST /api/webhooks - Invalid event type rejected")
    
    def test_create_duplicate_webhook_url(self):
        """Test creating webhook with duplicate URL fails"""
        webhook_data = {
            "name": f"TEST_Duplicate_{uuid.uuid4().hex[:8]}",
            "url": "https://webhook.site/duplicate-test-url",
            "event_types": ["compliance.status_changed"]
        }
        
        # Create first webhook
        response1 = self.session.post(f"{BASE_URL}/api/webhooks", json=webhook_data)
        assert response1.status_code == 200
        self.created_webhook_ids.append(response1.json()["webhook_id"])
        
        # Try to create duplicate
        webhook_data["name"] = f"TEST_Duplicate2_{uuid.uuid4().hex[:8]}"
        response2 = self.session.post(f"{BASE_URL}/api/webhooks", json=webhook_data)
        assert response2.status_code == 400, f"Should fail with 400: {response2.text}"
        assert "already exists" in response2.json().get("detail", "")
        
        print("✓ POST /api/webhooks - Duplicate URL rejected")
    
    # ==================== GET /api/webhooks ====================
    def test_list_webhooks(self):
        """Test listing webhooks returns correct structure"""
        # Create a webhook first
        webhook_data = {
            "name": f"TEST_List_{uuid.uuid4().hex[:8]}",
            "url": f"https://webhook.site/list-test-{uuid.uuid4().hex[:8]}",
            "event_types": ["compliance.status_changed"]
        }
        create_response = self.session.post(f"{BASE_URL}/api/webhooks", json=webhook_data)
        assert create_response.status_code == 200
        self.created_webhook_ids.append(create_response.json()["webhook_id"])
        
        # List webhooks
        response = self.session.get(f"{BASE_URL}/api/webhooks")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "webhooks" in data, "Response should contain 'webhooks'"
        assert "rate_limit" in data, "Response should contain 'rate_limit'"
        
        # Verify webhook structure (secret should NOT be in list)
        webhooks = data["webhooks"]
        assert len(webhooks) >= 1, "Should have at least 1 webhook"
        
        webhook = webhooks[0]
        assert "webhook_id" in webhook
        assert "name" in webhook
        assert "url" in webhook
        assert "event_types" in webhook
        assert "is_active" in webhook
        assert "secret" not in webhook, "Secret should NOT be in list response"
        
        print(f"✓ GET /api/webhooks - Listed {len(webhooks)} webhooks")
    
    # ==================== GET /api/webhooks/{id} ====================
    def test_get_webhook_details(self):
        """Test getting single webhook details with masked secret"""
        # Create a webhook
        webhook_data = {
            "name": f"TEST_Details_{uuid.uuid4().hex[:8]}",
            "url": f"https://webhook.site/details-test-{uuid.uuid4().hex[:8]}",
            "event_types": ["compliance.status_changed", "digest.sent"]
        }
        create_response = self.session.post(f"{BASE_URL}/api/webhooks", json=webhook_data)
        assert create_response.status_code == 200
        webhook_id = create_response.json()["webhook_id"]
        self.created_webhook_ids.append(webhook_id)
        
        # Get details
        response = self.session.get(f"{BASE_URL}/api/webhooks/{webhook_id}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["webhook_id"] == webhook_id
        assert data["name"] == webhook_data["name"]
        assert "secret_masked" in data, "Should have masked secret"
        assert "secret" not in data, "Full secret should NOT be returned"
        
        # Verify masked format (first 8 chars + ... + last 4 chars)
        masked = data["secret_masked"]
        assert "..." in masked, "Masked secret should contain '...'"
        
        print(f"✓ GET /api/webhooks/{webhook_id} - Details with masked secret")
    
    def test_get_webhook_not_found(self):
        """Test getting non-existent webhook returns 404"""
        response = self.session.get(f"{BASE_URL}/api/webhooks/non-existent-id")
        assert response.status_code == 404, f"Should return 404: {response.text}"
        
        print("✓ GET /api/webhooks/{id} - 404 for non-existent webhook")
    
    # ==================== PATCH /api/webhooks/{id} ====================
    def test_update_webhook(self):
        """Test updating webhook name and URL"""
        # Create a webhook
        webhook_data = {
            "name": f"TEST_Update_{uuid.uuid4().hex[:8]}",
            "url": f"https://webhook.site/update-test-{uuid.uuid4().hex[:8]}",
            "event_types": ["compliance.status_changed"]
        }
        create_response = self.session.post(f"{BASE_URL}/api/webhooks", json=webhook_data)
        assert create_response.status_code == 200
        webhook_id = create_response.json()["webhook_id"]
        self.created_webhook_ids.append(webhook_id)
        
        # Update webhook
        update_data = {
            "name": "Updated Webhook Name",
            "event_types": ["compliance.status_changed", "reminder.sent"]
        }
        response = self.session.patch(f"{BASE_URL}/api/webhooks/{webhook_id}", json=update_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        # Verify update
        get_response = self.session.get(f"{BASE_URL}/api/webhooks/{webhook_id}")
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["name"] == "Updated Webhook Name"
        assert "reminder.sent" in data["event_types"]
        
        print(f"✓ PATCH /api/webhooks/{webhook_id} - Webhook updated")
    
    # ==================== DELETE /api/webhooks/{id} ====================
    def test_delete_webhook(self):
        """Test soft deleting a webhook"""
        # Create a webhook
        webhook_data = {
            "name": f"TEST_Delete_{uuid.uuid4().hex[:8]}",
            "url": f"https://webhook.site/delete-test-{uuid.uuid4().hex[:8]}",
            "event_types": ["compliance.status_changed"]
        }
        create_response = self.session.post(f"{BASE_URL}/api/webhooks", json=webhook_data)
        assert create_response.status_code == 200
        webhook_id = create_response.json()["webhook_id"]
        
        # Delete webhook
        response = self.session.delete(f"{BASE_URL}/api/webhooks/{webhook_id}")
        assert response.status_code == 200, f"Failed: {response.text}"
        assert response.json()["message"] == "Webhook deleted"
        
        # Verify it's no longer accessible
        get_response = self.session.get(f"{BASE_URL}/api/webhooks/{webhook_id}")
        assert get_response.status_code == 404, "Deleted webhook should return 404"
        
        print(f"✓ DELETE /api/webhooks/{webhook_id} - Webhook soft deleted")
    
    # ==================== POST /api/webhooks/{id}/test ====================
    def test_webhook_test_endpoint(self):
        """Test sending a test webhook (will fail since URL is fake, but API should work)"""
        # Create a webhook
        webhook_data = {
            "name": f"TEST_TestEndpoint_{uuid.uuid4().hex[:8]}",
            "url": "https://webhook.site/test-endpoint-fake",
            "event_types": ["compliance.status_changed"]
        }
        create_response = self.session.post(f"{BASE_URL}/api/webhooks", json=webhook_data)
        assert create_response.status_code == 200
        webhook_id = create_response.json()["webhook_id"]
        self.created_webhook_ids.append(webhook_id)
        
        # Test webhook (will fail because URL is fake, but API should return proper response)
        response = self.session.post(f"{BASE_URL}/api/webhooks/{webhook_id}/test")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "success" in data, "Response should contain 'success'"
        assert "triggered_at" in data, "Response should contain 'triggered_at'"
        # Note: success will be False because the URL is fake
        
        print(f"✓ POST /api/webhooks/{webhook_id}/test - Test endpoint works")
    
    # ==================== POST /api/webhooks/{id}/enable ====================
    def test_enable_webhook(self):
        """Test enabling a webhook"""
        # Create and disable a webhook
        webhook_data = {
            "name": f"TEST_Enable_{uuid.uuid4().hex[:8]}",
            "url": f"https://webhook.site/enable-test-{uuid.uuid4().hex[:8]}",
            "event_types": ["compliance.status_changed"]
        }
        create_response = self.session.post(f"{BASE_URL}/api/webhooks", json=webhook_data)
        assert create_response.status_code == 200
        webhook_id = create_response.json()["webhook_id"]
        self.created_webhook_ids.append(webhook_id)
        
        # Disable first
        self.session.post(f"{BASE_URL}/api/webhooks/{webhook_id}/disable")
        
        # Enable
        response = self.session.post(f"{BASE_URL}/api/webhooks/{webhook_id}/enable")
        assert response.status_code == 200, f"Failed: {response.text}"
        assert response.json()["is_active"] == True
        
        print(f"✓ POST /api/webhooks/{webhook_id}/enable - Webhook enabled")
    
    # ==================== POST /api/webhooks/{id}/disable ====================
    def test_disable_webhook(self):
        """Test disabling a webhook"""
        # Create a webhook
        webhook_data = {
            "name": f"TEST_Disable_{uuid.uuid4().hex[:8]}",
            "url": f"https://webhook.site/disable-test-{uuid.uuid4().hex[:8]}",
            "event_types": ["compliance.status_changed"]
        }
        create_response = self.session.post(f"{BASE_URL}/api/webhooks", json=webhook_data)
        assert create_response.status_code == 200
        webhook_id = create_response.json()["webhook_id"]
        self.created_webhook_ids.append(webhook_id)
        
        # Disable
        response = self.session.post(f"{BASE_URL}/api/webhooks/{webhook_id}/disable")
        assert response.status_code == 200, f"Failed: {response.text}"
        assert response.json()["is_active"] == False
        
        print(f"✓ POST /api/webhooks/{webhook_id}/disable - Webhook disabled")
    
    # ==================== POST /api/webhooks/{id}/regenerate-secret ====================
    def test_regenerate_secret(self):
        """Test regenerating webhook secret"""
        # Create a webhook
        webhook_data = {
            "name": f"TEST_Regenerate_{uuid.uuid4().hex[:8]}",
            "url": f"https://webhook.site/regenerate-test-{uuid.uuid4().hex[:8]}",
            "event_types": ["compliance.status_changed"]
        }
        create_response = self.session.post(f"{BASE_URL}/api/webhooks", json=webhook_data)
        assert create_response.status_code == 200
        webhook_id = create_response.json()["webhook_id"]
        original_secret = create_response.json()["secret"]
        self.created_webhook_ids.append(webhook_id)
        
        # Regenerate secret
        response = self.session.post(f"{BASE_URL}/api/webhooks/{webhook_id}/regenerate-secret")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "secret" in data, "Response should contain new secret"
        assert data["secret"] != original_secret, "New secret should be different"
        assert len(data["secret"]) == 64, "New secret should be 64 hex chars"
        
        print(f"✓ POST /api/webhooks/{webhook_id}/regenerate-secret - Secret regenerated")
    
    # ==================== GET /api/webhooks/stats ====================
    def test_get_webhook_stats(self):
        """Test getting webhook delivery statistics"""
        response = self.session.get(f"{BASE_URL}/api/webhooks/stats")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "total_webhooks" in data
        assert "active_webhooks" in data
        assert "total_deliveries" in data
        assert "successful_deliveries" in data
        assert "success_rate" in data
        
        print(f"✓ GET /api/webhooks/stats - Stats: {data['total_webhooks']} webhooks, {data['success_rate']}% success rate")


class TestNotificationPreferences:
    """Test notification preferences with digest customization"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures - authenticate and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as client
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json().get("access_token")
        assert token, "No access token returned"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    # ==================== GET /api/profile/notifications ====================
    def test_get_notification_preferences(self):
        """Test getting notification preferences includes digest customization fields"""
        response = self.session.get(f"{BASE_URL}/api/profile/notifications")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        
        # Verify standard notification fields
        assert "status_change_alerts" in data
        assert "expiry_reminders" in data
        assert "monthly_digest" in data
        assert "document_updates" in data
        assert "system_announcements" in data
        assert "reminder_days_before" in data
        
        # Verify digest customization fields
        assert "digest_compliance_summary" in data, "Missing digest_compliance_summary"
        assert "digest_action_items" in data, "Missing digest_action_items"
        assert "digest_upcoming_expiries" in data, "Missing digest_upcoming_expiries"
        assert "digest_property_breakdown" in data, "Missing digest_property_breakdown"
        assert "digest_recent_documents" in data, "Missing digest_recent_documents"
        assert "digest_recommendations" in data, "Missing digest_recommendations"
        assert "digest_audit_summary" in data, "Missing digest_audit_summary"
        assert "daily_reminder_enabled" in data, "Missing daily_reminder_enabled"
        
        # Verify SMS fields
        assert "sms_enabled" in data
        assert "sms_phone_number" in data
        assert "sms_urgent_alerts_only" in data
        
        print("✓ GET /api/profile/notifications - All digest customization fields present")
    
    # ==================== PUT /api/profile/notifications ====================
    def test_update_digest_customization(self):
        """Test updating digest customization toggles"""
        # Get current preferences
        get_response = self.session.get(f"{BASE_URL}/api/profile/notifications")
        assert get_response.status_code == 200
        original = get_response.json()
        
        # Update digest customization
        update_data = {
            "digest_compliance_summary": True,
            "digest_action_items": True,
            "digest_upcoming_expiries": False,  # Toggle off
            "digest_property_breakdown": True,
            "digest_recent_documents": False,  # Toggle off
            "digest_recommendations": True,
            "digest_audit_summary": True,  # Toggle on (default is off)
            "daily_reminder_enabled": False  # Toggle off
        }
        
        response = self.session.put(f"{BASE_URL}/api/profile/notifications", json=update_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        # Verify update
        verify_response = self.session.get(f"{BASE_URL}/api/profile/notifications")
        assert verify_response.status_code == 200
        updated = verify_response.json()
        
        assert updated["digest_upcoming_expiries"] == False
        assert updated["digest_recent_documents"] == False
        assert updated["digest_audit_summary"] == True
        assert updated["daily_reminder_enabled"] == False
        
        # Restore original values
        restore_data = {
            "digest_upcoming_expiries": original.get("digest_upcoming_expiries", True),
            "digest_recent_documents": original.get("digest_recent_documents", True),
            "digest_audit_summary": original.get("digest_audit_summary", False),
            "daily_reminder_enabled": original.get("daily_reminder_enabled", True)
        }
        self.session.put(f"{BASE_URL}/api/profile/notifications", json=restore_data)
        
        print("✓ PUT /api/profile/notifications - Digest customization updated")
    
    def test_update_reminder_days(self):
        """Test updating reminder_days_before with valid values"""
        valid_values = [7, 14, 30, 60, 90]
        
        for days in valid_values:
            response = self.session.put(f"{BASE_URL}/api/profile/notifications", json={
                "reminder_days_before": days
            })
            assert response.status_code == 200, f"Failed for {days} days: {response.text}"
        
        # Restore to default
        self.session.put(f"{BASE_URL}/api/profile/notifications", json={
            "reminder_days_before": 30
        })
        
        print("✓ PUT /api/profile/notifications - Valid reminder days accepted")
    
    def test_update_reminder_days_invalid(self):
        """Test updating reminder_days_before with invalid value fails"""
        response = self.session.put(f"{BASE_URL}/api/profile/notifications", json={
            "reminder_days_before": 45  # Invalid - not in [7, 14, 30, 60, 90]
        })
        assert response.status_code == 400, f"Should fail with 400: {response.text}"
        
        print("✓ PUT /api/profile/notifications - Invalid reminder days rejected")


class TestWebhookAuthentication:
    """Test webhook endpoints require authentication"""
    
    def test_webhooks_require_auth(self):
        """Test that webhook endpoints require authentication"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Test without auth
        endpoints = [
            ("GET", "/api/webhooks"),
            ("GET", "/api/webhooks/events"),
            ("GET", "/api/webhooks/stats"),
            ("POST", "/api/webhooks"),
        ]
        
        for method, endpoint in endpoints:
            if method == "GET":
                response = session.get(f"{BASE_URL}{endpoint}")
            else:
                response = session.post(f"{BASE_URL}{endpoint}", json={})
            
            assert response.status_code == 401, f"{method} {endpoint} should require auth: {response.status_code}"
        
        print("✓ All webhook endpoints require authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
