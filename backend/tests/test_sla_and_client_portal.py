"""
Test Suite for SLA Configuration, Client Portal, and Admin Notification Preferences
Tests features implemented in iteration 44:
1. Backend SLA Configuration - Service-specific SLA hours
2. SLA Initialization on Order Payment
3. SLA Pause/Resume functionality
4. Client Orders API
5. Client Documents API
6. Admin Notification Preferences API
"""
import pytest
import requests
import os
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"


class TestSLAConfiguration:
    """Test SLA configuration by category and service code"""
    
    def test_sla_config_document_pack_standard(self):
        """Document Packs should have 48h standard SLA"""
        # This tests the SLA_CONFIG_BY_CATEGORY constant
        # We verify by checking the workflow automation service logic
        from services.workflow_automation_service import SLA_CONFIG_BY_CATEGORY
        
        config = SLA_CONFIG_BY_CATEGORY.get("document_pack", {})
        assert config.get("standard_hours") == 48, "Document Pack standard SLA should be 48 hours"
        assert config.get("fast_track_hours") == 24, "Document Pack fast-track SLA should be 24 hours"
        assert config.get("warning_threshold") == 0.75, "Warning threshold should be 75%"
    
    def test_sla_config_compliance_standard(self):
        """Compliance services should have 72h standard SLA"""
        from services.workflow_automation_service import SLA_CONFIG_BY_CATEGORY
        
        config = SLA_CONFIG_BY_CATEGORY.get("compliance", {})
        assert config.get("standard_hours") == 72, "Compliance standard SLA should be 72 hours"
        assert config.get("fast_track_hours") == 24, "Compliance fast-track SLA should be 24 hours"
    
    def test_sla_config_automation_standard(self):
        """AI Automation services should have 120h (5 business days) standard SLA"""
        from services.workflow_automation_service import SLA_CONFIG_BY_CATEGORY
        
        config = SLA_CONFIG_BY_CATEGORY.get("ai_automation", {})
        assert config.get("standard_hours") == 120, "AI Automation standard SLA should be 120 hours"
        assert config.get("fast_track_hours") == 72, "AI Automation fast-track SLA should be 72 hours"
    
    def test_sla_config_market_research(self):
        """Market Research should have 72-120h SLA based on complexity"""
        from services.workflow_automation_service import SLA_CONFIG_BY_CATEGORY
        
        config = SLA_CONFIG_BY_CATEGORY.get("market_research", {})
        assert config.get("standard_hours") == 72, "Market Research basic SLA should be 72 hours"
        assert config.get("advanced_hours") == 120, "Market Research advanced SLA should be 120 hours"
    
    def test_sla_service_overrides_exist(self):
        """Service-specific SLA overrides should be defined"""
        from services.workflow_automation_service import SLA_SERVICE_OVERRIDES
        
        # Check key service codes have overrides
        assert "COMP_HMO" in SLA_SERVICE_OVERRIDES, "COMP_HMO should have SLA override"
        assert "AI_WF_BLUEPRINT" in SLA_SERVICE_OVERRIDES, "AI_WF_BLUEPRINT should have SLA override"
        assert "MR_BASIC" in SLA_SERVICE_OVERRIDES, "MR_BASIC should have SLA override"
        assert "DOC_PACK_ESSENTIAL" in SLA_SERVICE_OVERRIDES, "DOC_PACK_ESSENTIAL should have SLA override"
    
    def test_get_sla_hours_for_order_function(self):
        """get_sla_hours_for_order should return correct SLA config"""
        from services.workflow_automation_service import get_sla_hours_for_order
        
        # Test with service code override
        order_with_override = {
            "service_code": "COMP_HMO",
            "category": "compliance",
            "fast_track": False,
        }
        sla = get_sla_hours_for_order(order_with_override)
        assert sla["target_hours"] == 72, "COMP_HMO standard should be 72 hours"
        
        # Test fast-track
        order_fast_track = {
            "service_code": "COMP_HMO",
            "category": "compliance",
            "fast_track": True,
        }
        sla_fast = get_sla_hours_for_order(order_fast_track)
        assert sla_fast["target_hours"] == 24, "COMP_HMO fast-track should be 24 hours"
        
        # Test fallback to category
        order_no_override = {
            "service_code": "UNKNOWN_CODE",
            "category": "document_pack",
            "fast_track": False,
        }
        sla_fallback = get_sla_hours_for_order(order_no_override)
        assert sla_fallback["target_hours"] == 48, "Should fallback to category SLA"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def client_token():
    """Get client authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Client login failed: {response.status_code} - {response.text}")


class TestAdminNotificationPreferences:
    """Test admin notification preferences API"""
    
    def test_get_notification_preferences_requires_auth(self):
        """GET /api/admin/notifications/preferences should require authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/notifications/preferences")
        assert response.status_code == 401, "Should return 401 without auth"
    
    def test_get_notification_preferences_success(self, admin_token):
        """GET /api/admin/notifications/preferences should return preferences"""
        response = requests.get(
            f"{BASE_URL}/api/admin/notifications/preferences",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Should return 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check expected fields exist
        assert "email_enabled" in data or data.get("email_enabled") is not None or "email_enabled" in str(data), \
            f"Response should contain email_enabled field: {data}"
    
    def test_update_notification_preferences_requires_auth(self):
        """PUT /api/admin/notifications/preferences should require authentication"""
        response = requests.put(
            f"{BASE_URL}/api/admin/notifications/preferences",
            json={"email_enabled": True}
        )
        assert response.status_code == 401, "Should return 401 without auth"
    
    def test_update_notification_preferences_success(self, admin_token):
        """PUT /api/admin/notifications/preferences should update preferences"""
        # Update preferences
        update_payload = {
            "email_enabled": True,
            "sms_enabled": False,
            "in_app_enabled": True,
        }
        response = requests.put(
            f"{BASE_URL}/api/admin/notifications/preferences",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=update_payload
        )
        assert response.status_code == 200, f"Should return 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Should return success: true"
    
    def test_get_admin_profile(self, admin_token):
        """GET /api/admin/notifications/profile should return admin profile"""
        response = requests.get(
            f"{BASE_URL}/api/admin/notifications/profile",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Should return 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should have email field
        assert "email" in data or "auth_email" in data, f"Profile should contain email: {data}"
    
    def test_list_notifications(self, admin_token):
        """GET /api/admin/notifications/ should return notifications list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/notifications/",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Should return 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "notifications" in data, "Should return notifications array"
        assert "unread_count" in data, "Should return unread_count"
    
    def test_get_unread_count(self, admin_token):
        """GET /api/admin/notifications/unread-count should return count"""
        response = requests.get(
            f"{BASE_URL}/api/admin/notifications/unread-count",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Should return 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "unread_count" in data, "Should return unread_count"
        assert isinstance(data["unread_count"], int), "unread_count should be integer"


class TestClientOrdersAPI:
    """Test client orders API endpoints"""
    
    def test_list_client_orders_requires_auth(self):
        """GET /api/client/orders/ should require authentication"""
        response = requests.get(f"{BASE_URL}/api/client/orders/")
        assert response.status_code == 401, "Should return 401 without auth"
    
    def test_list_client_orders_success(self, client_token):
        """GET /api/client/orders/ should return client's orders"""
        response = requests.get(
            f"{BASE_URL}/api/client/orders/",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200, f"Should return 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "orders" in data, "Should return orders array"
        assert "total" in data, "Should return total count"
        assert "action_required" in data, "Should return action_required count"
        assert isinstance(data["orders"], list), "orders should be a list"
    
    def test_list_client_orders_with_status_filter(self, client_token):
        """GET /api/client/orders/?status=COMPLETED should filter by status"""
        response = requests.get(
            f"{BASE_URL}/api/client/orders/?status=COMPLETED",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200, f"Should return 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # All returned orders should have COMPLETED status
        for order in data.get("orders", []):
            assert order.get("status") == "COMPLETED", f"Order should be COMPLETED: {order.get('status')}"
    
    def test_get_client_order_not_found(self, client_token):
        """GET /api/client/orders/{order_id} should return 404 for non-existent order"""
        response = requests.get(
            f"{BASE_URL}/api/client/orders/NONEXISTENT_ORDER_123",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 404, f"Should return 404, got {response.status_code}"


class TestClientDocumentsAPI:
    """Test client document download API endpoints"""
    
    def test_get_documents_requires_auth(self):
        """GET /api/client/orders/{order_id}/documents should require authentication"""
        response = requests.get(f"{BASE_URL}/api/client/orders/TEST_ORDER/documents")
        assert response.status_code == 401, "Should return 401 without auth"
    
    def test_get_documents_order_not_found(self, client_token):
        """GET /api/client/orders/{order_id}/documents should return 404 for non-existent order"""
        response = requests.get(
            f"{BASE_URL}/api/client/orders/NONEXISTENT_ORDER_123/documents",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 404, f"Should return 404, got {response.status_code}"
    
    def test_download_document_requires_auth(self):
        """GET /api/client/orders/{order_id}/documents/{version}/download should require auth"""
        response = requests.get(
            f"{BASE_URL}/api/client/orders/TEST_ORDER/documents/1/download?format=pdf"
        )
        assert response.status_code == 401, "Should return 401 without auth"


class TestSLAFunctions:
    """Test SLA initialization and tracking functions"""
    
    def test_initialize_order_sla_function_exists(self):
        """initialize_order_sla function should exist and be importable"""
        from services.workflow_automation_service import initialize_order_sla
        assert callable(initialize_order_sla), "initialize_order_sla should be callable"
    
    def test_log_sla_event_function_exists(self):
        """log_sla_event function should exist and be importable"""
        from services.workflow_automation_service import log_sla_event
        assert callable(log_sla_event), "log_sla_event should be callable"
    
    def test_sla_paused_states_defined(self):
        """SLA_PAUSED_STATES should be defined in order_workflow"""
        from services.order_workflow import SLA_PAUSED_STATES
        assert SLA_PAUSED_STATES is not None, "SLA_PAUSED_STATES should be defined"
        # CLIENT_INPUT_REQUIRED should pause SLA
        from services.order_workflow import OrderStatus
        assert OrderStatus.CLIENT_INPUT_REQUIRED in SLA_PAUSED_STATES, \
            "CLIENT_INPUT_REQUIRED should be in SLA_PAUSED_STATES"


class TestWorkflowAutomationService:
    """Test workflow automation service methods"""
    
    def test_wf1_payment_to_queue_exists(self):
        """WF1 method should exist"""
        from services.workflow_automation_service import workflow_automation_service
        assert hasattr(workflow_automation_service, 'wf1_payment_to_queue'), \
            "wf1_payment_to_queue method should exist"
    
    def test_wf5_client_response_exists(self):
        """WF5 method should exist for SLA resume"""
        from services.workflow_automation_service import workflow_automation_service
        assert hasattr(workflow_automation_service, 'wf5_client_response'), \
            "wf5_client_response method should exist"
    
    def test_wf9_sla_check_exists(self):
        """WF9 method should exist for SLA monitoring"""
        from services.workflow_automation_service import workflow_automation_service
        assert hasattr(workflow_automation_service, 'wf9_sla_check'), \
            "wf9_sla_check method should exist"


class TestFastTrackGuardrails:
    """Test that fast-track doesn't bypass critical controls"""
    
    def test_fast_track_guardrails_defined(self):
        """Fast-track guardrails should be defined"""
        from services.workflow_automation_service import FAST_TRACK_GUARDRAILS
        
        assert "human_review" in FAST_TRACK_GUARDRAILS, "human_review should be a guardrail"
        assert "audit_logs" in FAST_TRACK_GUARDRAILS, "audit_logs should be a guardrail"
        assert "versioning" in FAST_TRACK_GUARDRAILS, "versioning should be a guardrail"
        assert "sla_tracking" in FAST_TRACK_GUARDRAILS, "sla_tracking should be a guardrail"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
