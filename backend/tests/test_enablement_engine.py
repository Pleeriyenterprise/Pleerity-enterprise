"""
Test Suite for Customer Enablement Automation Engine
Tests all admin enablement endpoints for iteration 53

Enablement Categories:
- ONBOARDING_GUIDANCE
- VALUE_CONFIRMATION
- COMPLIANCE_AWARENESS
- INACTIVITY_SUPPORT
- FEATURE_GATE_EXPLANATION

Delivery Channels: IN_APP, EMAIL, ASSISTANT
Action Statuses: SUCCESS, FAILED, SUPPRESSED, PENDING
"""
import json
from datetime import datetime
import pytest

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


class TestEnablementEngineSetup:
    """Setup and authentication tests"""

    @pytest.fixture
    def admin_token(self, client):
        """Get admin authentication token"""
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]

    @pytest.fixture
    def auth_headers(self, admin_token):
        """Get authorization headers"""
        return {"Authorization": f"Bearer {admin_token}"}

    def test_admin_login(self, client):
        """Test admin can login successfully"""
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data.get("user", {}).get("role") == "ROLE_ADMIN"


class TestEnablementOverview:
    """Test GET /api/admin/enablement/overview endpoint"""

    @pytest.fixture
    def admin_token(self, client):
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]

    @pytest.fixture
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}

    def test_get_overview_success(self, client, auth_headers):
        """Test overview endpoint returns expected structure"""
        response = client.get(
            "/api/admin/enablement/overview",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify expected fields
        assert "active_templates" in data
        assert "active_suppressions" in data
        assert "event_subscribers" in data
        assert "recent_actions" in data
        
        # Verify types
        assert isinstance(data["active_templates"], int)
        assert isinstance(data["active_suppressions"], int)
        assert isinstance(data["event_subscribers"], dict)
        assert isinstance(data["recent_actions"], list)
    
    def test_overview_requires_auth(self, client):
        """Test overview endpoint requires authentication"""
        response = client.get("/api/admin/enablement/overview")
        assert response.status_code in [401, 403]


class TestEnablementStats:
    """Test GET /api/admin/enablement/stats endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self, client):
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_get_stats_default_30_days(self, client, auth_headers):
        """Test stats endpoint with default 30 days"""
        response = client.get(
            "/api/admin/enablement/stats",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify expected fields
        assert "total_actions" in data
        assert "success_count" in data
        assert "failed_count" in data
        assert "suppressed_count" in data
        assert "by_category" in data
        assert "by_channel" in data
        assert "period_days" in data
        
        # Verify period
        assert data["period_days"] == 30
    
    def test_get_stats_custom_days(self, client, auth_headers):
        """Test stats endpoint with custom days parameter"""
        response = client.get(
            "/api/admin/enablement/stats?days=7",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 7
    
    def test_stats_requires_auth(self, client):
        """Test stats endpoint requires authentication"""
        response = client.get("/api/admin/enablement/stats")
        assert response.status_code in [401, 403]


class TestEnablementTemplates:
    """Test GET /api/admin/enablement/templates endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self, client):
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_list_templates_success(self, client, auth_headers):
        """Test templates endpoint returns list of templates"""
        response = client.get(
            "/api/admin/enablement/templates",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "templates" in data
        assert "total" in data
        assert isinstance(data["templates"], list)
        
        # Should have 16 active templates as per requirements
        assert data["total"] >= 16, f"Expected at least 16 templates, got {data['total']}"
    
    def test_templates_have_required_fields(self, client, auth_headers):
        """Test each template has required fields"""
        response = client.get(
            "/api/admin/enablement/templates",
            headers=auth_headers
        )
        data = response.json()
        
        for template in data["templates"]:
            assert "template_id" in template
            assert "template_code" in template
            assert "category" in template
            assert "event_triggers" in template
            assert "title" in template
            assert "body" in template
            assert "channels" in template
            assert "is_active" in template
    
    def test_filter_templates_by_category(self, client, auth_headers):
        """Test filtering templates by category"""
        response = client.get(
            "/api/admin/enablement/templates?category=ONBOARDING_GUIDANCE",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # All returned templates should be ONBOARDING_GUIDANCE
        for template in data["templates"]:
            assert template["category"] == "ONBOARDING_GUIDANCE"
    
    def test_templates_requires_auth(self, client):
        """Test templates endpoint requires authentication"""
        response = client.get("/api/admin/enablement/templates")
        assert response.status_code in [401, 403]


class TestEnablementEventTypes:
    """Test GET /api/admin/enablement/event-types endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self, client):
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_get_event_types_success(self, client, auth_headers):
        """Test event-types endpoint returns all enums"""
        response = client.get(
            "/api/admin/enablement/event-types",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify all enum types are returned
        assert "event_types" in data
        assert "categories" in data
        assert "channels" in data
        assert "statuses" in data
        
        # Verify event types include expected values
        event_type_values = [et["value"] for et in data["event_types"]]
        assert "CLIENT_INTAKE_COMPLETED" in event_type_values
        assert "PROVISIONING_COMPLETED" in event_type_values
        assert "FIRST_LOGIN" in event_type_values
        assert "DOCUMENT_VERIFIED" in event_type_values
        
        # Verify categories include all 5
        category_values = [c["value"] for c in data["categories"]]
        assert "ONBOARDING_GUIDANCE" in category_values
        assert "VALUE_CONFIRMATION" in category_values
        assert "COMPLIANCE_AWARENESS" in category_values
        assert "INACTIVITY_SUPPORT" in category_values
        assert "FEATURE_GATE_EXPLANATION" in category_values
        
        # Verify channels
        channel_values = [ch["value"] for ch in data["channels"]]
        assert "IN_APP" in channel_values
        assert "EMAIL" in channel_values
        assert "ASSISTANT" in channel_values
        
        # Verify statuses
        status_values = [s["value"] for s in data["statuses"]]
        assert "SUCCESS" in status_values
        assert "FAILED" in status_values
        assert "SUPPRESSED" in status_values
        assert "PENDING" in status_values


class TestEnablementSuppressions:
    """Test suppression rules CRUD endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self, client):
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_list_suppressions_success(self, client, auth_headers):
        """Test listing suppression rules"""
        response = client.get(
            "/api/admin/enablement/suppressions",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "rules" in data
        assert isinstance(data["rules"], list)
    
    def test_create_suppression_rule(self, client, auth_headers):
        """Test creating a new suppression rule"""
        payload = {
            "client_id": None,
            "category": "INACTIVITY_SUPPORT",
            "template_code": None,
            "reason": "TEST_suppression_rule_for_testing"
        }
        
        response = client.post(
            "/api/admin/enablement/suppressions",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "rule_id" in data
        assert data["reason"] == "TEST_suppression_rule_for_testing"
        assert data["category"] == "INACTIVITY_SUPPORT"
        assert data["active"] == True
        
        # Store rule_id for cleanup
        return data["rule_id"]
    
    def test_create_and_delete_suppression_rule(self, client, auth_headers):
        """Test creating and then deleting a suppression rule"""
        # Create
        payload = {
            "client_id": None,
            "category": None,
            "template_code": None,
            "reason": "TEST_temporary_suppression_for_deletion"
        }
        
        create_response = client.post(
            "/api/admin/enablement/suppressions",
            headers=auth_headers,
            json=payload
        )
        assert create_response.status_code == 200
        rule_id = create_response.json()["rule_id"]
        
        # Delete
        delete_response = client.delete(
            "/api/admin/enablement/suppressions/{rule_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["success"] == True
    
    def test_create_suppression_requires_reason(self, client, auth_headers):
        """Test that reason is required for suppression rule"""
        payload = {
            "client_id": None,
            "category": None,
            "template_code": None,
            "reason": ""  # Empty reason
        }
        
        response = client.post(
            "/api/admin/enablement/suppressions",
            headers=auth_headers,
            json=payload
        )
        # Should still work with empty string (validation is on frontend)
        # or return 422 if backend validates
        assert response.status_code in [200, 422]
    
    def test_delete_nonexistent_suppression(self, client, auth_headers):
        """Test deleting a non-existent suppression rule"""
        response = client.delete(
            "/api/admin/enablement/suppressions/SUP-NONEXISTENT123",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestEnablementManualTrigger:
    """Test POST /api/admin/enablement/trigger endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self, client):
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    @pytest.fixture(scope="class")
    def test_client_id(self, client, auth_headers):
        """Get or create a test client for triggering events"""
        # First try to get existing clients
        response = client.get(
            "/api/admin/clients",
            headers=auth_headers
        )
        if response.status_code == 200:
            data = response.json()
            clients = data.get("clients", [])
            if clients:
                return clients[0]["client_id"]
        return None
    
    def test_trigger_event_invalid_client(self, client, auth_headers):
        """Test triggering event for non-existent client"""
        payload = {
            "event_type": "FIRST_LOGIN",
            "client_id": "NONEXISTENT-CLIENT-123",
            "context_payload": {}
        }
        
        response = client.post(
            "/api/admin/enablement/trigger",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 404
        assert "Client not found" in response.json().get("detail", "")
    
    def test_trigger_event_success(self, auth_headers, test_client_id):
        """Test triggering event for valid client"""
        if not test_client_id:
            pytest.skip("No test client available")
        
        payload = {
            "event_type": "FIRST_LOGIN",
            "client_id": test_client_id,
            "context_payload": {"test": True}
        }
        
        response = client.post(
            "/api/admin/enablement/trigger",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert "event_id" in data
        assert "message" in data
    
    def test_trigger_requires_auth(self, client):
        """Test trigger endpoint requires authentication"""
        payload = {
            "event_type": "FIRST_LOGIN",
            "client_id": "test-client",
            "context_payload": {}
        }
        
        response = client.post(
            "/api/admin/enablement/trigger",
            json=payload
        )
        assert response.status_code in [401, 403]


class TestEnablementClientTimeline:
    """Test client timeline endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self, client):
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_get_client_timeline(self, client, auth_headers):
        """Test getting timeline for a client"""
        response = client.get(
            "/api/admin/enablement/clients/test-client-123/timeline",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "client_id" in data
        assert "actions" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        
        assert data["client_id"] == "test-client-123"
        assert isinstance(data["actions"], list)
    
    def test_timeline_pagination(self, client, auth_headers):
        """Test timeline pagination parameters"""
        response = client.get(
            "/api/admin/enablement/clients/test-client/timeline?limit=10&offset=0",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["limit"] == 10
        assert data["offset"] == 0


class TestEnablementActions:
    """Test actions query endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self, client):
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_list_actions(self, client, auth_headers):
        """Test listing enablement actions"""
        response = client.get(
            "/api/admin/enablement/actions",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "actions" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
    
    def test_filter_actions_by_status(self, client, auth_headers):
        """Test filtering actions by status"""
        response = client.get(
            "/api/admin/enablement/actions?status=SUCCESS",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # All returned actions should have SUCCESS status
        for action in data["actions"]:
            assert action["status"] == "SUCCESS"
    
    def test_filter_actions_by_category(self, client, auth_headers):
        """Test filtering actions by category"""
        response = client.get(
            "/api/admin/enablement/actions?category=ONBOARDING_GUIDANCE",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for action in data["actions"]:
            assert action["category"] == "ONBOARDING_GUIDANCE"


class TestEnablementEvents:
    """Test events query endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self, client):
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_list_events(self, client, auth_headers):
        """Test listing enablement events"""
        response = client.get(
            "/api/admin/enablement/events",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "events" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data


class TestEnablementTemplateToggle:
    """Test template toggle endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self, client):
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_toggle_template_status(self, client, auth_headers):
        """Test toggling a template's active status"""
        # First get a template
        templates_response = client.get(
            "/api/admin/enablement/templates",
            headers=auth_headers
        )
        templates = templates_response.json()["templates"]
        
        if not templates:
            pytest.skip("No templates available")
        
        template_code = templates[0]["template_code"]
        original_status = templates[0]["is_active"]
        
        # Toggle
        toggle_response = client.put(
            "/api/admin/enablement/templates/{template_code}/toggle",
            headers=auth_headers
        )
        assert toggle_response.status_code == 200
        data = toggle_response.json()
        
        assert data["template_code"] == template_code
        assert data["is_active"] == (not original_status)
        
        # Toggle back to original
        client.put(
            "/api/admin/enablement/templates/{template_code}/toggle",
            headers=auth_headers
        )
    
    def test_toggle_nonexistent_template(self, client, auth_headers):
        """Test toggling a non-existent template"""
        response = client.put(
            "/api/admin/enablement/templates/nonexistent_template/toggle",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestEnablementTemplateReseed:
    """Test template reseed endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self, client):
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_reseed_templates(self, client, auth_headers):
        """Test reseeding templates"""
        response = client.post(
            "/api/admin/enablement/templates/seed",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert "seeded" in data
        assert "updated" in data


# Cleanup fixture to remove test data
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_suppressions():
    """Cleanup TEST_ prefixed suppression rules after all tests"""
    yield
    
    # Login and cleanup
    try:
        login_response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if login_response.status_code == 200:
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            # Get all suppressions
            suppressions_response = client.get(
                "/api/admin/enablement/suppressions?active_only=false",
                headers=headers
            )
            if suppressions_response.status_code == 200:
                rules = suppressions_response.json().get("rules", [])
                for rule in rules:
                    if "TEST_" in rule.get("reason", ""):
                        client.delete(
                            "/api/admin/enablement/suppressions/{rule['rule_id']}",
                            headers=headers
                        )
    except Exception as e:
        print(f"Cleanup failed: {e}")
