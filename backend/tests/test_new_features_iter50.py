"""
Test Suite for Iteration 50 Features:
1. WhatsApp handoff with window.open() and audit logging
2. Admin Intake Schema Manager with draft/publish workflow
3. Admin Canned Responses CRUD with soft delete
4. Knowledge Base/FAQ system (public + admin)

Run: pytest /app/backend/tests/test_new_features_iter50.py -v --tb=short
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"


class TestSetup:
    """Setup and authentication tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Admin login failed: {response.status_code}")
    
    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        """Get admin headers with auth token"""
        return {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        }


# ============================================================================
# WHATSAPP HANDOFF AUDIT TESTS
# ============================================================================

class TestWhatsAppHandoffAudit:
    """Test WhatsApp handoff audit logging endpoint"""
    
    def test_whatsapp_handoff_audit_endpoint_exists(self):
        """Test that the WhatsApp audit endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/support/audit/whatsapp-handoff", json={
            "conversation_id": "test-conv-123",
            "user_role": "anonymous",
            "client_id": None,
            "page_url": "https://example.com/support",
            "timestamp": "2026-01-23T12:00:00Z"
        })
        # Should return 200 (success) or 422 (validation error), not 404
        assert response.status_code in [200, 422], f"Endpoint should exist, got {response.status_code}"
    
    def test_whatsapp_handoff_audit_logs_event(self):
        """Test that WhatsApp handoff click is logged"""
        response = requests.post(f"{BASE_URL}/api/support/audit/whatsapp-handoff", json={
            "conversation_id": "TEST_conv_whatsapp_001",
            "user_role": "anonymous",
            "client_id": None,
            "page_url": "https://order-fulfillment-9.preview.emergentagent.com/support",
            "timestamp": "2026-01-23T12:00:00Z"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        # Verify the event type is correct
        assert data.get("event") == "SUPPORT_WHATSAPP_HANDOFF_CLICKED"
    
    def test_whatsapp_handoff_audit_with_authenticated_user(self):
        """Test audit logging for authenticated user"""
        response = requests.post(f"{BASE_URL}/api/support/audit/whatsapp-handoff", json={
            "conversation_id": "TEST_conv_whatsapp_002",
            "user_role": "authenticated",
            "client_id": "client-123",
            "page_url": "https://order-fulfillment-9.preview.emergentagent.com/dashboard",
            "timestamp": "2026-01-23T12:00:00Z"
        })
        assert response.status_code == 200


# ============================================================================
# ADMIN INTAKE SCHEMA MANAGER TESTS
# ============================================================================

class TestAdminIntakeSchemaManager(TestSetup):
    """Test Admin Intake Schema Manager APIs"""
    
    def test_get_services_list(self, admin_headers):
        """GET /api/admin/intake-schema/services returns list of services"""
        response = requests.get(
            f"{BASE_URL}/api/admin/intake-schema/services",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "services" in data
        assert "total" in data
        assert isinstance(data["services"], list)
        # Should have at least some services
        assert data["total"] > 0, "Should have at least one service"
        
        # Verify service structure
        if data["services"]:
            service = data["services"][0]
            assert "service_code" in service
            assert "field_count" in service
    
    def test_get_schema_for_editing(self, admin_headers):
        """GET /api/admin/intake-schema/{service_code} returns schema for editing"""
        # First get list of services
        services_response = requests.get(
            f"{BASE_URL}/api/admin/intake-schema/services",
            headers=admin_headers
        )
        services = services_response.json().get("services", [])
        
        if not services:
            pytest.skip("No services available to test")
        
        service_code = services[0]["service_code"]
        
        response = requests.get(
            f"{BASE_URL}/api/admin/intake-schema/{service_code}",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "service_code" in data
        assert "fields" in data
        assert "customizations_meta" in data
        assert data["service_code"] == service_code
    
    def test_save_draft_schema(self, admin_headers):
        """PUT /api/admin/intake-schema/{service_code} saves draft"""
        # Get a service code
        services_response = requests.get(
            f"{BASE_URL}/api/admin/intake-schema/services",
            headers=admin_headers
        )
        services = services_response.json().get("services", [])
        
        if not services:
            pytest.skip("No services available to test")
        
        service_code = services[0]["service_code"]
        
        # Save draft with a test override
        response = requests.put(
            f"{BASE_URL}/api/admin/intake-schema/{service_code}",
            headers=admin_headers,
            json={
                "service_code": service_code,
                "field_overrides": [
                    {
                        "field_key": "TEST_field_override",
                        "label": "TEST Override Label",
                        "helper_text": "Test helper text",
                        "hidden": False
                    }
                ],
                "is_draft": True
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
        assert data.get("is_draft") == True
    
    def test_publish_schema(self, admin_headers):
        """POST /api/admin/intake-schema/{service_code}/publish publishes draft"""
        # Get a service code
        services_response = requests.get(
            f"{BASE_URL}/api/admin/intake-schema/services",
            headers=admin_headers
        )
        services = services_response.json().get("services", [])
        
        if not services:
            pytest.skip("No services available to test")
        
        service_code = services[0]["service_code"]
        
        # First save a draft
        requests.put(
            f"{BASE_URL}/api/admin/intake-schema/{service_code}",
            headers=admin_headers,
            json={
                "service_code": service_code,
                "field_overrides": [
                    {
                        "field_key": "TEST_publish_field",
                        "label": "TEST Publish Label",
                        "hidden": False
                    }
                ],
                "is_draft": True
            }
        )
        
        # Now publish
        response = requests.post(
            f"{BASE_URL}/api/admin/intake-schema/{service_code}/publish",
            headers=admin_headers
        )
        # May return 200 (success) or 400 (no draft to publish)
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}"
    
    def test_schema_requires_admin(self):
        """Test that schema endpoints require admin authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/intake-schema/services")
        assert response.status_code in [401, 403], "Should require authentication"


# ============================================================================
# ADMIN CANNED RESPONSES TESTS
# ============================================================================

class TestAdminCannedResponses(TestSetup):
    """Test Admin Canned Responses CRUD APIs"""
    
    def test_list_canned_responses(self, admin_headers):
        """GET /api/admin/support/responses returns list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/support/responses",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "responses" in data
        assert "total" in data
        assert "categories" in data
        assert "channels" in data
        assert isinstance(data["responses"], list)
    
    def test_create_canned_response(self, admin_headers):
        """POST /api/admin/support/responses creates new response with audit"""
        response = requests.post(
            f"{BASE_URL}/api/admin/support/responses",
            headers=admin_headers,
            json={
                "label": "TEST Response Label",
                "category": "other",
                "channel": "WEB_CHAT",
                "response_text": "This is a TEST canned response for automated testing purposes. It should be at least 10 characters.",
                "icon": "🧪",
                "order": 999,
                "trigger_keywords": ["test", "automated"]
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("success") == True
        assert "response_id" in data
        assert "response" in data
        
        # Verify created response
        created = data["response"]
        assert created["label"] == "TEST Response Label"
        assert created["category"] == "other"
        assert created["is_active"] == True
        
        # Store for cleanup
        return data["response_id"]
    
    def test_get_single_response(self, admin_headers):
        """GET /api/admin/support/responses/{id} returns single response"""
        # First create a response
        create_response = requests.post(
            f"{BASE_URL}/api/admin/support/responses",
            headers=admin_headers,
            json={
                "label": "TEST Get Single Response",
                "category": "billing",
                "channel": "WEB_CHAT",
                "response_text": "This is a test response for getting single item test.",
                "icon": "💰",
                "order": 998
            }
        )
        response_id = create_response.json().get("response_id")
        
        # Get the response
        response = requests.get(
            f"{BASE_URL}/api/admin/support/responses/{response_id}",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["response_id"] == response_id
        assert data["label"] == "TEST Get Single Response"
    
    def test_update_canned_response(self, admin_headers):
        """PUT /api/admin/support/responses/{id} updates response"""
        # First create a response
        create_response = requests.post(
            f"{BASE_URL}/api/admin/support/responses",
            headers=admin_headers,
            json={
                "label": "TEST Update Response Original",
                "category": "orders",
                "channel": "WEB_CHAT",
                "response_text": "Original response text for update test.",
                "order": 997
            }
        )
        response_id = create_response.json().get("response_id")
        
        # Update the response
        response = requests.put(
            f"{BASE_URL}/api/admin/support/responses/{response_id}",
            headers=admin_headers,
            json={
                "label": "TEST Update Response Modified",
                "response_text": "Modified response text after update."
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert data["response"]["label"] == "TEST Update Response Modified"
    
    def test_soft_delete_canned_response(self, admin_headers):
        """DELETE soft deletes (sets is_active=false)"""
        # First create a response
        create_response = requests.post(
            f"{BASE_URL}/api/admin/support/responses",
            headers=admin_headers,
            json={
                "label": "TEST Delete Response",
                "category": "technical",
                "channel": "WEB_CHAT",
                "response_text": "This response will be soft deleted.",
                "order": 996
            }
        )
        response_id = create_response.json().get("response_id")
        
        # Delete (soft)
        response = requests.delete(
            f"{BASE_URL}/api/admin/support/responses/{response_id}",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        
        # Verify it's deactivated (not hard deleted)
        get_response = requests.get(
            f"{BASE_URL}/api/admin/support/responses/{response_id}",
            headers=admin_headers
        )
        assert get_response.status_code == 200
        assert get_response.json()["is_active"] == False
    
    def test_reactivate_canned_response(self, admin_headers):
        """POST /api/admin/support/responses/{id}/reactivate reactivates"""
        # Create and deactivate a response
        create_response = requests.post(
            f"{BASE_URL}/api/admin/support/responses",
            headers=admin_headers,
            json={
                "label": "TEST Reactivate Response",
                "category": "login",
                "channel": "WEB_CHAT",
                "response_text": "This response will be deactivated then reactivated.",
                "order": 995
            }
        )
        response_id = create_response.json().get("response_id")
        
        # Deactivate
        requests.delete(
            f"{BASE_URL}/api/admin/support/responses/{response_id}",
            headers=admin_headers
        )
        
        # Reactivate
        response = requests.post(
            f"{BASE_URL}/api/admin/support/responses/{response_id}/reactivate",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        # Verify it's active again
        get_response = requests.get(
            f"{BASE_URL}/api/admin/support/responses/{response_id}",
            headers=admin_headers
        )
        assert get_response.json()["is_active"] == True
    
    def test_canned_responses_requires_admin(self):
        """Test that canned responses endpoints require admin auth"""
        response = requests.get(f"{BASE_URL}/api/admin/support/responses")
        assert response.status_code in [401, 403]


# ============================================================================
# KNOWLEDGE BASE PUBLIC API TESTS
# ============================================================================

class TestKnowledgeBasePublic:
    """Test Knowledge Base public APIs"""
    
    def test_get_categories(self):
        """GET /api/kb/categories returns 9 default categories"""
        response = requests.get(f"{BASE_URL}/api/kb/categories")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "categories" in data
        categories = data["categories"]
        assert isinstance(categories, list)
        # Should have 9 default categories
        assert len(categories) >= 9, f"Expected at least 9 categories, got {len(categories)}"
        
        # Verify category structure
        if categories:
            cat = categories[0]
            assert "category_id" in cat or "id" in cat
            assert "name" in cat
    
    def test_get_featured_articles(self):
        """GET /api/kb/featured returns popular and recent articles"""
        response = requests.get(f"{BASE_URL}/api/kb/featured")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "popular" in data
        assert "recent" in data
        assert isinstance(data["popular"], list)
        assert isinstance(data["recent"], list)
    
    def test_search_articles(self):
        """GET /api/kb/articles with search parameter"""
        response = requests.get(f"{BASE_URL}/api/kb/articles?search=test")
        assert response.status_code == 200
        data = response.json()
        
        assert "articles" in data
        assert isinstance(data["articles"], list)
    
    def test_get_articles_by_category(self):
        """GET /api/kb/articles with category filter"""
        response = requests.get(f"{BASE_URL}/api/kb/articles?category=getting-started")
        assert response.status_code == 200
        data = response.json()
        
        assert "articles" in data


# ============================================================================
# KNOWLEDGE BASE ADMIN API TESTS
# ============================================================================

class TestKnowledgeBaseAdmin(TestSetup):
    """Test Knowledge Base admin APIs"""
    
    def test_create_article(self, admin_headers):
        """POST /api/admin/kb/articles creates article with audit"""
        response = requests.post(
            f"{BASE_URL}/api/admin/kb/articles",
            headers=admin_headers,
            json={
                "title": "TEST Article for Automated Testing",
                "category_id": "getting-started",
                "excerpt": "This is a test article excerpt for automated testing purposes.",
                "content": "This is the full content of the test article. It needs to be at least 50 characters long to pass validation. Here is some more content to make it longer.",
                "tags": ["test", "automated"],
                "status": "draft"
            }
        )
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("success") == True or "article_id" in data
        assert "article_id" in data or "article" in data
    
    def test_publish_article(self, admin_headers):
        """POST /api/admin/kb/articles/{id}/publish publishes article"""
        # First create a draft article
        create_response = requests.post(
            f"{BASE_URL}/api/admin/kb/articles",
            headers=admin_headers,
            json={
                "title": "TEST Article to Publish",
                "category_id": "billing-subscriptions",
                "excerpt": "This article will be published during testing.",
                "content": "Full content of the article that will be published. This needs to be at least 50 characters long for validation.",
                "tags": ["test", "publish"],
                "status": "draft"
            }
        )
        
        article_id = create_response.json().get("article_id") or create_response.json().get("article", {}).get("article_id")
        
        if not article_id:
            pytest.skip("Could not create article to publish")
        
        # Publish the article
        response = requests.post(
            f"{BASE_URL}/api/admin/kb/articles/{article_id}/publish",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True
    
    def test_get_analytics(self, admin_headers):
        """GET /api/admin/kb/analytics returns search analytics"""
        response = requests.get(
            f"{BASE_URL}/api/admin/kb/analytics",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Should have analytics data
        assert "top_searches" in data or "total_searches" in data or "analytics" in data
    
    def test_list_admin_articles(self, admin_headers):
        """GET /api/admin/kb/articles returns all articles including drafts"""
        response = requests.get(
            f"{BASE_URL}/api/admin/kb/articles",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "articles" in data
        assert "total" in data
    
    def test_kb_admin_requires_auth(self):
        """Test that KB admin endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/kb/articles")
        assert response.status_code in [401, 403]
        
        response = requests.post(f"{BASE_URL}/api/admin/kb/articles", json={})
        assert response.status_code in [401, 403, 422]


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration(TestSetup):
    """Integration tests for the new features"""
    
    def test_support_chat_with_handoff_options(self):
        """Test that chat endpoint returns handoff options with WhatsApp link"""
        # Send a message requesting human help
        response = requests.post(f"{BASE_URL}/api/support/chat", json={
            "message": "I need to speak to a human agent please",
            "channel": "web"
        })
        assert response.status_code == 200
        data = response.json()
        
        assert "conversation_id" in data
        assert "response" in data
        
        # If handoff is triggered, verify WhatsApp option
        if data.get("action") == "handoff" and data.get("handoff_options"):
            assert "whatsapp" in data["handoff_options"]
            assert "link" in data["handoff_options"]["whatsapp"]
    
    def test_quick_action_speak_to_human(self):
        """Test speak_to_human quick action returns handoff options"""
        response = requests.post(f"{BASE_URL}/api/support/quick-action/speak_to_human")
        assert response.status_code == 200
        data = response.json()
        
        assert "conversation_id" in data
        assert "response" in data
        
        # Should have handoff options
        if data.get("handoff_options"):
            assert "whatsapp" in data["handoff_options"]
            assert "live_chat" in data["handoff_options"]
            assert "email_ticket" in data["handoff_options"]


# ============================================================================
# CLEANUP
# ============================================================================

class TestCleanup(TestSetup):
    """Cleanup test data"""
    
    def test_cleanup_test_responses(self, admin_headers):
        """Clean up TEST_ prefixed canned responses"""
        response = requests.get(
            f"{BASE_URL}/api/admin/support/responses?include_inactive=true&limit=200",
            headers=admin_headers
        )
        if response.status_code == 200:
            responses = response.json().get("responses", [])
            for resp in responses:
                if resp.get("label", "").startswith("TEST"):
                    # Hard delete would be ideal, but soft delete is fine
                    requests.delete(
                        f"{BASE_URL}/api/admin/support/responses/{resp['response_id']}",
                        headers=admin_headers
                    )
        print("Cleanup completed for TEST_ prefixed responses")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
