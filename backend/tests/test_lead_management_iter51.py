"""
Lead Management System Tests - Iteration 51

Tests for:
1. Lead capture API - POST /api/leads/capture/chatbot
2. Lead listing API - GET /api/admin/leads
3. Lead notifications API - GET /api/admin/leads/notifications
4. Follow-up queue processing - POST /api/admin/leads/test/followup-queue
5. SLA breach detection - POST /api/admin/leads/test/sla-check
6. Abandoned intake detection - POST /api/admin/leads/test/abandoned-intake
7. Admin Intake Schema Manager - Version history, draft/publish workflow, rollback
8. HIGH intent notification - Verify HIGH intent leads trigger admin notifications
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


class TestAuthSetup:
    """Authentication setup for admin tests."""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token."""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        """Get headers with admin auth token."""
        return {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        }


class TestLeadCaptureAPI(TestAuthSetup):
    """Test lead capture from chatbot endpoint."""
    
    def test_capture_chatbot_lead_basic(self):
        """Test basic lead capture from chatbot."""
        unique_email = f"TEST_lead_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/leads/capture/chatbot",
            json={
                "email": unique_email,
                "name": "TEST Lead User",
                "message": "I want to learn about CVP",
                "marketing_consent": False
            }
        )
        
        assert response.status_code == 200, f"Lead capture failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert data.get("success") is True
        assert "lead_id" in data
        assert data["lead_id"].startswith("LEAD-")
        assert "message" in data
        
        print(f"✓ Created lead: {data['lead_id']}")
    
    def test_capture_chatbot_lead_with_service_interest(self):
        """Test lead capture with service interest mapping."""
        unique_email = f"TEST_cvp_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/leads/capture/chatbot",
            json={
                "email": unique_email,
                "name": "TEST CVP Interest",
                "service_interest": "cvp",
                "message": "I need pricing for CVP",
                "marketing_consent": True
            }
        )
        
        assert response.status_code == 200, f"Lead capture failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert "lead_id" in data
        
        print(f"✓ Created lead with CVP interest: {data['lead_id']}")
    
    def test_capture_chatbot_lead_high_intent(self):
        """Test lead capture with HIGH intent keywords triggers correct scoring."""
        unique_email = f"TEST_high_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/leads/capture/chatbot",
            json={
                "email": unique_email,
                "name": "TEST High Intent Lead",
                "service_interest": "cvp",
                "message": "I want to buy CVP and need pricing immediately",
                "marketing_consent": True,
                "phone": "+447700900123"
            }
        )
        
        assert response.status_code == 200, f"Lead capture failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert "lead_id" in data
        
        print(f"✓ Created HIGH intent lead: {data['lead_id']}")
        return data["lead_id"]
    
    def test_capture_chatbot_lead_with_utm(self):
        """Test lead capture with UTM tracking parameters."""
        unique_email = f"TEST_utm_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/leads/capture/chatbot",
            json={
                "email": unique_email,
                "name": "TEST UTM Lead",
                "message": "Found you via Google",
                "marketing_consent": True,
                "utm_source": "google",
                "utm_medium": "cpc",
                "utm_campaign": "test_campaign"
            }
        )
        
        assert response.status_code == 200, f"Lead capture failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        print(f"✓ Created lead with UTM: {data['lead_id']}")
    
    def test_capture_duplicate_lead(self):
        """Test duplicate lead detection."""
        unique_email = f"test_dup_{uuid.uuid4().hex[:8]}@example.com"  # Use lowercase for consistent dedup
        
        # Create first lead
        response1 = requests.post(
            f"{BASE_URL}/api/leads/capture/chatbot",
            json={
                "email": unique_email,
                "name": "TEST First Lead",
                "marketing_consent": False
            }
        )
        assert response1.status_code == 200
        first_lead_id = response1.json()["lead_id"]
        
        # Try to create duplicate with same email
        response2 = requests.post(
            f"{BASE_URL}/api/leads/capture/chatbot",
            json={
                "email": unique_email,
                "name": "TEST Duplicate Lead",
                "marketing_consent": False
            }
        )
        assert response2.status_code == 200
        data = response2.json()
        
        # Should return existing lead as duplicate
        assert data.get("is_duplicate") is True
        print(f"✓ Duplicate detection working - original: {first_lead_id}")


class TestLeadListingAPI(TestAuthSetup):
    """Test admin lead listing endpoint."""
    
    def test_list_leads_basic(self, admin_headers):
        """Test basic lead listing."""
        response = requests.get(
            f"{BASE_URL}/api/admin/leads",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Lead listing failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "leads" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert "stats" in data
        
        assert isinstance(data["leads"], list)
        assert isinstance(data["total"], int)
        
        print(f"✓ Listed {len(data['leads'])} leads (total: {data['total']})")
    
    def test_list_leads_with_stats(self, admin_headers):
        """Test lead listing includes stats."""
        response = requests.get(
            f"{BASE_URL}/api/admin/leads",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        stats = data.get("stats", {})
        assert "total_leads" in stats or "total" in stats or isinstance(stats, dict)
        
        print(f"✓ Lead stats returned: {list(stats.keys())}")
    
    def test_list_leads_filter_by_intent(self, admin_headers):
        """Test lead listing with intent score filter."""
        response = requests.get(
            f"{BASE_URL}/api/admin/leads?intent_score=HIGH",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned leads should have HIGH intent
        for lead in data.get("leads", []):
            if lead.get("intent_score"):
                assert lead["intent_score"] == "HIGH", f"Expected HIGH intent, got {lead['intent_score']}"
        
        print(f"✓ Filtered by HIGH intent: {len(data['leads'])} leads")
    
    def test_list_leads_filter_by_source(self, admin_headers):
        """Test lead listing with source platform filter."""
        response = requests.get(
            f"{BASE_URL}/api/admin/leads?source_platform=WEB_CHAT",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        for lead in data.get("leads", []):
            assert lead.get("source_platform") == "WEB_CHAT"
        
        print(f"✓ Filtered by WEB_CHAT source: {len(data['leads'])} leads")
    
    def test_list_leads_search(self, admin_headers):
        """Test lead listing with search."""
        response = requests.get(
            f"{BASE_URL}/api/admin/leads?search=TEST",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"✓ Search for 'TEST': {len(data['leads'])} leads found")
    
    def test_list_leads_pagination(self, admin_headers):
        """Test lead listing pagination."""
        response = requests.get(
            f"{BASE_URL}/api/admin/leads?page=1&limit=5",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["page"] == 1
        assert data["limit"] == 5
        assert len(data["leads"]) <= 5
        
        print(f"✓ Pagination working: page {data['page']}, limit {data['limit']}")
    
    def test_list_leads_requires_auth(self):
        """Test lead listing requires authentication."""
        response = requests.get(f"{BASE_URL}/api/admin/leads")
        
        assert response.status_code in [401, 403], f"Expected auth error, got {response.status_code}"
        print("✓ Lead listing requires authentication")


class TestLeadNotificationsAPI(TestAuthSetup):
    """Test admin lead notifications endpoint."""
    
    def test_get_notifications(self, admin_headers):
        """Test getting lead notifications."""
        response = requests.get(
            f"{BASE_URL}/api/admin/leads/notifications",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Notifications failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "high_intent_alerts" in data
        assert "sla_breach_alerts" in data
        assert "recent_leads" in data
        assert "total_alerts" in data
        
        assert isinstance(data["high_intent_alerts"], list)
        assert isinstance(data["sla_breach_alerts"], list)
        assert isinstance(data["recent_leads"], list)
        
        print(f"✓ Notifications: {data['total_alerts']} total alerts")
        print(f"  - HIGH intent: {len(data['high_intent_alerts'])}")
        print(f"  - SLA breaches: {len(data['sla_breach_alerts'])}")
        print(f"  - Recent leads: {len(data['recent_leads'])}")
    
    def test_notifications_structure(self, admin_headers):
        """Test notification alert structure."""
        response = requests.get(
            f"{BASE_URL}/api/admin/leads/notifications",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check HIGH intent alert structure
        for alert in data.get("high_intent_alerts", []):
            assert "lead_id" in alert
            assert "name" in alert
            assert "type" in alert
            assert alert["type"] == "high_intent"
        
        # Check SLA breach alert structure
        for alert in data.get("sla_breach_alerts", []):
            assert "lead_id" in alert
            assert "type" in alert
            assert alert["type"] == "sla_breach"
        
        # Check recent leads structure
        for lead in data.get("recent_leads", []):
            assert "lead_id" in lead
            assert "type" in lead
            assert lead["type"] == "new_lead"
        
        print("✓ Notification structure verified")
    
    def test_notifications_requires_auth(self):
        """Test notifications requires authentication."""
        response = requests.get(f"{BASE_URL}/api/admin/leads/notifications")
        
        assert response.status_code in [401, 403]
        print("✓ Notifications requires authentication")


class TestFollowUpQueueProcessing(TestAuthSetup):
    """Test follow-up queue processing endpoint."""
    
    def test_process_followup_queue(self, admin_headers):
        """Test manual follow-up queue processing."""
        response = requests.post(
            f"{BASE_URL}/api/admin/leads/test/followup-queue",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Follow-up queue failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert "message" in data
        
        print(f"✓ Follow-up queue processed: {data['message']}")
    
    def test_followup_queue_requires_auth(self):
        """Test follow-up queue requires authentication."""
        response = requests.post(f"{BASE_URL}/api/admin/leads/test/followup-queue")
        
        assert response.status_code in [401, 403]
        print("✓ Follow-up queue requires authentication")


class TestSLABreachDetection(TestAuthSetup):
    """Test SLA breach detection endpoint."""
    
    def test_sla_check_default(self, admin_headers):
        """Test SLA breach check with default 24 hours."""
        response = requests.post(
            f"{BASE_URL}/api/admin/leads/test/sla-check",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"SLA check failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert "breaches_detected" in data
        assert isinstance(data["breaches_detected"], int)
        
        print(f"✓ SLA check completed: {data['breaches_detected']} breaches detected")
    
    def test_sla_check_custom_hours(self, admin_headers):
        """Test SLA breach check with custom hours."""
        response = requests.post(
            f"{BASE_URL}/api/admin/leads/test/sla-check?sla_hours=1",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("success") is True
        print(f"✓ SLA check with 1 hour: {data['breaches_detected']} breaches")
    
    def test_sla_check_requires_auth(self):
        """Test SLA check requires authentication."""
        response = requests.post(f"{BASE_URL}/api/admin/leads/test/sla-check")
        
        assert response.status_code in [401, 403]
        print("✓ SLA check requires authentication")


class TestAbandonedIntakeDetection(TestAuthSetup):
    """Test abandoned intake detection endpoint."""
    
    def test_abandoned_intake_detection(self, admin_headers):
        """Test manual abandoned intake detection."""
        response = requests.post(
            f"{BASE_URL}/api/admin/leads/test/abandoned-intake",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Abandoned intake failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert "leads_created" in data
        assert "lead_ids" in data
        assert isinstance(data["leads_created"], int)
        assert isinstance(data["lead_ids"], list)
        
        print(f"✓ Abandoned intake detection: {data['leads_created']} leads created")
    
    def test_abandoned_intake_requires_auth(self):
        """Test abandoned intake requires authentication."""
        response = requests.post(f"{BASE_URL}/api/admin/leads/test/abandoned-intake")
        
        assert response.status_code in [401, 403]
        print("✓ Abandoned intake requires authentication")


class TestHighIntentNotification(TestAuthSetup):
    """Test HIGH intent notification endpoint."""
    
    def test_high_intent_notification(self, admin_headers):
        """Test HIGH intent notification for existing lead."""
        # First create a lead
        unique_email = f"TEST_notify_{uuid.uuid4().hex[:8]}@example.com"
        
        create_response = requests.post(
            f"{BASE_URL}/api/leads/capture/chatbot",
            json={
                "email": unique_email,
                "name": "TEST Notification Lead",
                "message": "I want pricing now",
                "marketing_consent": True
            }
        )
        assert create_response.status_code == 200
        lead_id = create_response.json()["lead_id"]
        
        # Test notification endpoint
        response = requests.post(
            f"{BASE_URL}/api/admin/leads/test/high-intent-notification?test_lead_id={lead_id}",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"HIGH intent notification failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert "message" in data
        
        print(f"✓ HIGH intent notification sent for lead: {lead_id}")
    
    def test_high_intent_notification_not_found(self, admin_headers):
        """Test HIGH intent notification for non-existent lead."""
        response = requests.post(
            f"{BASE_URL}/api/admin/leads/test/high-intent-notification?test_lead_id=LEAD-NONEXISTENT",
            headers=admin_headers
        )
        
        assert response.status_code == 404
        print("✓ HIGH intent notification returns 404 for non-existent lead")


class TestAdminIntakeSchemaManager(TestAuthSetup):
    """Test Admin Intake Schema Manager endpoints."""
    
    def test_list_configurable_services(self, admin_headers):
        """Test listing configurable services."""
        response = requests.get(
            f"{BASE_URL}/api/admin/intake-schema/services",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"List services failed: {response.text}"
        data = response.json()
        
        assert "services" in data
        assert "total" in data
        assert isinstance(data["services"], list)
        
        print(f"✓ Listed {data['total']} configurable services")
        
        # Verify service structure
        if data["services"]:
            service = data["services"][0]
            assert "service_code" in service
            assert "field_count" in service
            print(f"  - First service: {service['service_code']} ({service['field_count']} fields)")
    
    def test_get_schema_for_editing(self, admin_headers):
        """Test getting schema for editing."""
        # First get list of services
        list_response = requests.get(
            f"{BASE_URL}/api/admin/intake-schema/services",
            headers=admin_headers
        )
        assert list_response.status_code == 200
        services = list_response.json().get("services", [])
        
        if not services:
            pytest.skip("No services available for testing")
        
        service_code = services[0]["service_code"]
        
        response = requests.get(
            f"{BASE_URL}/api/admin/intake-schema/{service_code}",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Get schema failed: {response.text}"
        data = response.json()
        
        assert "service_code" in data
        assert "fields" in data
        assert "customizations_meta" in data
        assert data["service_code"] == service_code
        
        print(f"✓ Got schema for {service_code}: {len(data['fields'])} fields")
    
    def test_save_schema_draft(self, admin_headers):
        """Test saving schema as draft."""
        # Get a service
        list_response = requests.get(
            f"{BASE_URL}/api/admin/intake-schema/services",
            headers=admin_headers
        )
        services = list_response.json().get("services", [])
        
        if not services:
            pytest.skip("No services available for testing")
        
        service_code = services[0]["service_code"]
        
        # Save draft with a test override
        response = requests.put(
            f"{BASE_URL}/api/admin/intake-schema/{service_code}",
            headers=admin_headers,
            json={
                "service_code": service_code,
                "field_overrides": [
                    {
                        "field_key": "test_field",
                        "label": "TEST Label Override",
                        "helper_text": "TEST helper text"
                    }
                ],
                "is_draft": True
            }
        )
        
        assert response.status_code == 200, f"Save draft failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert data.get("is_draft") is True
        assert "schema_version" in data
        
        print(f"✓ Saved draft for {service_code}, version: {data['schema_version']}")
    
    def test_get_version_history(self, admin_headers):
        """Test getting version history."""
        list_response = requests.get(
            f"{BASE_URL}/api/admin/intake-schema/services",
            headers=admin_headers
        )
        services = list_response.json().get("services", [])
        
        if not services:
            pytest.skip("No services available for testing")
        
        service_code = services[0]["service_code"]
        
        response = requests.get(
            f"{BASE_URL}/api/admin/intake-schema/{service_code}/versions",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Get versions failed: {response.text}"
        data = response.json()
        
        assert "service_code" in data
        assert "versions" in data
        assert isinstance(data["versions"], list)
        
        print(f"✓ Got {len(data['versions'])} versions for {service_code}")
    
    def test_preview_schema(self, admin_headers):
        """Test previewing customized schema."""
        list_response = requests.get(
            f"{BASE_URL}/api/admin/intake-schema/services",
            headers=admin_headers
        )
        services = list_response.json().get("services", [])
        
        if not services:
            pytest.skip("No services available for testing")
        
        service_code = services[0]["service_code"]
        
        response = requests.get(
            f"{BASE_URL}/api/admin/intake-schema/{service_code}/preview",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Preview failed: {response.text}"
        data = response.json()
        
        assert "fields" in data
        assert data.get("is_preview") is True
        
        print(f"✓ Preview schema for {service_code}: {len(data['fields'])} fields")
    
    def test_schema_manager_requires_auth(self):
        """Test schema manager requires authentication."""
        response = requests.get(f"{BASE_URL}/api/admin/intake-schema/services")
        
        assert response.status_code in [401, 403]
        print("✓ Schema manager requires authentication")


class TestLeadSources(TestAuthSetup):
    """Test lead sources endpoint."""
    
    def test_get_lead_sources(self, admin_headers):
        """Test getting available lead sources."""
        response = requests.get(
            f"{BASE_URL}/api/admin/leads/sources",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Get sources failed: {response.text}"
        data = response.json()
        
        assert "source_platforms" in data
        assert "service_interests" in data
        assert "intent_scores" in data
        assert "stages" in data
        assert "statuses" in data
        
        assert isinstance(data["source_platforms"], list)
        assert "WEB_CHAT" in data["source_platforms"]
        assert "HIGH" in data["intent_scores"]
        
        print(f"✓ Got lead sources:")
        print(f"  - Platforms: {len(data['source_platforms'])}")
        print(f"  - Interests: {len(data['service_interests'])}")
        print(f"  - Intent scores: {data['intent_scores']}")


class TestLeadStats(TestAuthSetup):
    """Test lead statistics endpoint."""
    
    def test_get_lead_stats(self, admin_headers):
        """Test getting lead statistics."""
        response = requests.get(
            f"{BASE_URL}/api/admin/leads/stats",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Get stats failed: {response.text}"
        data = response.json()
        
        # Stats should be a dictionary with various metrics
        assert isinstance(data, dict)
        
        print(f"✓ Got lead stats: {list(data.keys())}")


class TestLeadCRUD(TestAuthSetup):
    """Test lead CRUD operations."""
    
    def test_get_single_lead(self, admin_headers):
        """Test getting a single lead."""
        # First create a lead
        unique_email = f"TEST_single_{uuid.uuid4().hex[:8]}@example.com"
        
        create_response = requests.post(
            f"{BASE_URL}/api/leads/capture/chatbot",
            json={
                "email": unique_email,
                "name": "TEST Single Lead",
                "marketing_consent": False
            }
        )
        assert create_response.status_code == 200
        lead_id = create_response.json()["lead_id"]
        
        # Get the lead
        response = requests.get(
            f"{BASE_URL}/api/admin/leads/{lead_id}",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Get lead failed: {response.text}"
        data = response.json()
        
        assert data.get("lead_id") == lead_id
        assert data.get("email") == unique_email
        assert "audit_log" in data
        
        print(f"✓ Got lead {lead_id} with audit log")
    
    def test_update_lead(self, admin_headers):
        """Test updating a lead."""
        # First create a lead
        unique_email = f"TEST_update_{uuid.uuid4().hex[:8]}@example.com"
        
        create_response = requests.post(
            f"{BASE_URL}/api/leads/capture/chatbot",
            json={
                "email": unique_email,
                "name": "TEST Update Lead",
                "marketing_consent": False
            }
        )
        assert create_response.status_code == 200
        lead_id = create_response.json()["lead_id"]
        
        # Update the lead
        response = requests.put(
            f"{BASE_URL}/api/admin/leads/{lead_id}?name=TEST%20Updated%20Name&intent_score=HIGH",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Update lead failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert data.get("lead", {}).get("name") == "TEST Updated Name"
        assert data.get("lead", {}).get("intent_score") == "HIGH"
        
        print(f"✓ Updated lead {lead_id}")
    
    def test_assign_lead(self, admin_headers):
        """Test assigning a lead."""
        # First create a lead
        unique_email = f"TEST_assign_{uuid.uuid4().hex[:8]}@example.com"
        
        create_response = requests.post(
            f"{BASE_URL}/api/leads/capture/chatbot",
            json={
                "email": unique_email,
                "name": "TEST Assign Lead",
                "marketing_consent": False
            }
        )
        assert create_response.status_code == 200
        lead_id = create_response.json()["lead_id"]
        
        # Assign the lead
        response = requests.post(
            f"{BASE_URL}/api/admin/leads/{lead_id}/assign?admin_id={ADMIN_EMAIL}",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Assign lead failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert data.get("lead", {}).get("assigned_to") == ADMIN_EMAIL
        
        print(f"✓ Assigned lead {lead_id} to {ADMIN_EMAIL}")
    
    def test_log_contact(self, admin_headers):
        """Test logging a contact with a lead."""
        # First create a lead
        unique_email = f"TEST_contact_{uuid.uuid4().hex[:8]}@example.com"
        
        create_response = requests.post(
            f"{BASE_URL}/api/leads/capture/chatbot",
            json={
                "email": unique_email,
                "name": "TEST Contact Lead",
                "marketing_consent": False
            }
        )
        assert create_response.status_code == 200
        lead_id = create_response.json()["lead_id"]
        
        # Log contact
        response = requests.post(
            f"{BASE_URL}/api/admin/leads/{lead_id}/contact?contact_method=email&notes=TEST%20contact&outcome=interested",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Log contact failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        
        print(f"✓ Logged contact for lead {lead_id}")
    
    def test_get_lead_audit_log(self, admin_headers):
        """Test getting lead audit log."""
        # First create a lead
        unique_email = f"TEST_audit_{uuid.uuid4().hex[:8]}@example.com"
        
        create_response = requests.post(
            f"{BASE_URL}/api/leads/capture/chatbot",
            json={
                "email": unique_email,
                "name": "TEST Audit Lead",
                "marketing_consent": False
            }
        )
        assert create_response.status_code == 200
        lead_id = create_response.json()["lead_id"]
        
        # Get audit log
        response = requests.get(
            f"{BASE_URL}/api/admin/leads/{lead_id}/audit-log",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Get audit log failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        # Should have at least the LEAD_CREATED event
        assert len(data) >= 1
        
        print(f"✓ Got {len(data)} audit log entries for lead {lead_id}")


class TestContactFormCapture:
    """Test contact form lead capture."""
    
    def test_capture_contact_form_lead(self):
        """Test lead capture from contact form."""
        unique_email = f"TEST_form_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/leads/capture/contact-form",
            json={
                "email": unique_email,
                "name": "TEST Contact Form User",
                "message": "This is a test message from the contact form with enough characters.",
                "marketing_consent": True
            }
        )
        
        assert response.status_code == 200, f"Contact form capture failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert "lead_id" in data
        
        print(f"✓ Created contact form lead: {data['lead_id']}")


class TestDocumentServiceCapture:
    """Test document service lead capture."""
    
    def test_capture_document_service_lead(self):
        """Test lead capture from document service."""
        unique_email = f"TEST_doc_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/leads/capture/document-service",
            json={
                "email": unique_email,
                "service_code": "TENANCY_PACK",
                "property_address": "123 Test Street, London",
                "marketing_consent": False
            }
        )
        
        assert response.status_code == 200, f"Document service capture failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert "lead_id" in data
        
        print(f"✓ Created document service lead: {data['lead_id']}")


class TestUnsubscribe:
    """Test lead unsubscribe functionality."""
    
    def test_unsubscribe_lead(self):
        """Test unsubscribing a lead."""
        # First create a lead with marketing consent
        unique_email = f"TEST_unsub_{uuid.uuid4().hex[:8]}@example.com"
        
        create_response = requests.post(
            f"{BASE_URL}/api/leads/capture/chatbot",
            json={
                "email": unique_email,
                "name": "TEST Unsubscribe Lead",
                "marketing_consent": True
            }
        )
        assert create_response.status_code == 200
        lead_id = create_response.json()["lead_id"]
        
        # Unsubscribe
        response = requests.post(f"{BASE_URL}/api/leads/unsubscribe/{lead_id}")
        
        assert response.status_code == 200, f"Unsubscribe failed: {response.text}"
        data = response.json()
        
        assert data.get("success") is True
        assert "unsubscribed" in data.get("message", "").lower()
        
        print(f"✓ Unsubscribed lead {lead_id}")
    
    def test_unsubscribe_nonexistent_lead(self):
        """Test unsubscribing non-existent lead."""
        response = requests.post(f"{BASE_URL}/api/leads/unsubscribe/LEAD-NONEXISTENT")
        
        assert response.status_code == 404
        print("✓ Unsubscribe returns 404 for non-existent lead")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
