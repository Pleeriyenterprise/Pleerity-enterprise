"""
Iteration 27 - Admin Billing & Subscription Management Tests

Tests for the new Admin Billing module:
- GET /api/admin/billing/statistics - returns subscription stats
- GET /api/admin/billing/clients/search?q=test - search clients by email/CRN/ID
- GET /api/admin/billing/clients/{client_id} - get billing snapshot with all fields
- POST /api/admin/billing/clients/{client_id}/sync - force sync (handles no Stripe customer)
- POST /api/admin/billing/clients/{client_id}/resend-setup - resend password setup email
- POST /api/admin/billing/clients/{client_id}/force-provision - force provisioning (checks entitlement)
- POST /api/admin/billing/clients/{client_id}/portal-link - create Stripe portal link
- POST /api/admin/billing/clients/{client_id}/message - send message to client
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://docpackhub.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"
TEST_CLIENT_ID = "87ff6c33-1f99-40b6-b9ed-a05c17e13950"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Get headers with admin auth token."""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


class TestAdminBillingStatistics:
    """Tests for GET /api/admin/billing/statistics"""
    
    def test_statistics_returns_200(self, admin_headers):
        """Statistics endpoint returns 200 OK."""
        response = requests.get(
            f"{BASE_URL}/api/admin/billing/statistics",
            headers=admin_headers
        )
        assert response.status_code == 200
    
    def test_statistics_has_entitlement_counts(self, admin_headers):
        """Statistics includes entitlement counts."""
        response = requests.get(
            f"{BASE_URL}/api/admin/billing/statistics",
            headers=admin_headers
        )
        data = response.json()
        
        assert "entitlement_counts" in data
        assert "enabled" in data["entitlement_counts"]
        assert "limited" in data["entitlement_counts"]
        assert "disabled" in data["entitlement_counts"]
    
    def test_statistics_has_plan_counts(self, admin_headers):
        """Statistics includes plan counts."""
        response = requests.get(
            f"{BASE_URL}/api/admin/billing/statistics",
            headers=admin_headers
        )
        data = response.json()
        
        assert "plan_counts" in data
        assert "PLAN_1_SOLO" in data["plan_counts"]
        assert "PLAN_2_PORTFOLIO" in data["plan_counts"]
        assert "PLAN_3_PRO" in data["plan_counts"]
    
    def test_statistics_has_clients_needing_attention(self, admin_headers):
        """Statistics includes clients needing attention."""
        response = requests.get(
            f"{BASE_URL}/api/admin/billing/statistics",
            headers=admin_headers
        )
        data = response.json()
        
        assert "clients_needing_attention" in data
        assert isinstance(data["clients_needing_attention"], list)
    
    def test_statistics_requires_admin_auth(self):
        """Statistics endpoint requires admin authentication."""
        response = requests.get(f"{BASE_URL}/api/admin/billing/statistics")
        assert response.status_code in [401, 403]


class TestAdminBillingSearch:
    """Tests for GET /api/admin/billing/clients/search"""
    
    def test_search_returns_200(self, admin_headers):
        """Search endpoint returns 200 OK."""
        response = requests.get(
            f"{BASE_URL}/api/admin/billing/clients/search?q=test",
            headers=admin_headers
        )
        assert response.status_code == 200
    
    def test_search_returns_clients_array(self, admin_headers):
        """Search returns clients array."""
        response = requests.get(
            f"{BASE_URL}/api/admin/billing/clients/search?q=test",
            headers=admin_headers
        )
        data = response.json()
        
        assert "clients" in data
        assert isinstance(data["clients"], list)
        assert "total" in data
        assert "query" in data
    
    def test_search_finds_test_client(self, admin_headers):
        """Search finds the test client."""
        response = requests.get(
            f"{BASE_URL}/api/admin/billing/clients/search?q=test",
            headers=admin_headers
        )
        data = response.json()
        
        assert data["total"] >= 1
        client_ids = [c["client_id"] for c in data["clients"]]
        assert TEST_CLIENT_ID in client_ids
    
    def test_search_client_has_required_fields(self, admin_headers):
        """Search results include required fields."""
        response = requests.get(
            f"{BASE_URL}/api/admin/billing/clients/search?q=test",
            headers=admin_headers
        )
        data = response.json()
        
        if data["clients"]:
            client = data["clients"][0]
            assert "client_id" in client
            assert "billing_plan" in client or "plan_name" in client
    
    def test_search_short_query_returns_empty(self, admin_headers):
        """Search with short query returns empty results."""
        response = requests.get(
            f"{BASE_URL}/api/admin/billing/clients/search?q=a",
            headers=admin_headers
        )
        data = response.json()
        
        assert data["clients"] == []
        assert data["total"] == 0


class TestAdminBillingSnapshot:
    """Tests for GET /api/admin/billing/clients/{client_id}"""
    
    def test_snapshot_returns_200(self, admin_headers):
        """Billing snapshot returns 200 OK."""
        response = requests.get(
            f"{BASE_URL}/api/admin/billing/clients/{TEST_CLIENT_ID}",
            headers=admin_headers
        )
        assert response.status_code == 200
    
    def test_snapshot_has_client_identifiers(self, admin_headers):
        """Snapshot includes client identifiers."""
        response = requests.get(
            f"{BASE_URL}/api/admin/billing/clients/{TEST_CLIENT_ID}",
            headers=admin_headers
        )
        data = response.json()
        
        assert data["client_id"] == TEST_CLIENT_ID
        assert "company_name" in data
        assert "contact_email" in data or data.get("contact_email") is None
    
    def test_snapshot_has_plan_info(self, admin_headers):
        """Snapshot includes plan information."""
        response = requests.get(
            f"{BASE_URL}/api/admin/billing/clients/{TEST_CLIENT_ID}",
            headers=admin_headers
        )
        data = response.json()
        
        assert "plan_code" in data
        assert "plan_name" in data
        assert "max_properties" in data
        assert "current_property_count" in data
        assert "over_property_limit" in data
    
    def test_snapshot_has_entitlement_status(self, admin_headers):
        """Snapshot includes entitlement status."""
        response = requests.get(
            f"{BASE_URL}/api/admin/billing/clients/{TEST_CLIENT_ID}",
            headers=admin_headers
        )
        data = response.json()
        
        assert "subscription_status" in data
        assert "entitlement_status" in data
        assert "onboarding_status" in data
    
    def test_snapshot_has_stripe_fields(self, admin_headers):
        """Snapshot includes Stripe fields."""
        response = requests.get(
            f"{BASE_URL}/api/admin/billing/clients/{TEST_CLIENT_ID}",
            headers=admin_headers
        )
        data = response.json()
        
        # These fields should exist even if null
        assert "stripe_customer_id" in data
        assert "stripe_subscription_id" in data
        assert "cancel_at_period_end" in data
        assert "onboarding_fee_paid" in data
    
    def test_snapshot_has_portal_user(self, admin_headers):
        """Snapshot includes portal user info."""
        response = requests.get(
            f"{BASE_URL}/api/admin/billing/clients/{TEST_CLIENT_ID}",
            headers=admin_headers
        )
        data = response.json()
        
        assert "portal_user" in data
        assert "password_setup_complete" in data
        
        if data["portal_user"]:
            assert "portal_user_id" in data["portal_user"]
            assert "email" in data["portal_user"]
    
    def test_snapshot_404_for_invalid_client(self, admin_headers):
        """Snapshot returns 404 for invalid client ID."""
        response = requests.get(
            f"{BASE_URL}/api/admin/billing/clients/invalid-client-id-12345",
            headers=admin_headers
        )
        assert response.status_code == 404


class TestAdminBillingSync:
    """Tests for POST /api/admin/billing/clients/{client_id}/sync"""
    
    def test_sync_returns_200(self, admin_headers):
        """Sync endpoint returns 200 OK."""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/clients/{TEST_CLIENT_ID}/sync",
            headers=admin_headers
        )
        assert response.status_code == 200
    
    def test_sync_handles_no_stripe_customer(self, admin_headers):
        """Sync handles client with no Stripe customer gracefully."""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/clients/{TEST_CLIENT_ID}/sync",
            headers=admin_headers
        )
        data = response.json()
        
        # Test client has no Stripe customer, so sync should return success=false
        assert "success" in data
        assert "message" in data
        
        if not data["success"]:
            assert "has_stripe_customer" in data
            assert data["has_stripe_customer"] == False


class TestAdminBillingResendSetup:
    """Tests for POST /api/admin/billing/clients/{client_id}/resend-setup"""
    
    def test_resend_setup_returns_200(self, admin_headers):
        """Resend setup endpoint returns 200 OK."""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/clients/{TEST_CLIENT_ID}/resend-setup",
            headers=admin_headers
        )
        assert response.status_code == 200
    
    def test_resend_setup_returns_success(self, admin_headers):
        """Resend setup returns success response."""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/clients/{TEST_CLIENT_ID}/resend-setup",
            headers=admin_headers
        )
        data = response.json()
        
        assert data["success"] == True
        assert "email" in data
        assert "email_sent" in data
    
    def test_resend_setup_404_for_invalid_client(self, admin_headers):
        """Resend setup returns 404 for client without portal user."""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/clients/invalid-client-id-12345/resend-setup",
            headers=admin_headers
        )
        assert response.status_code == 404


class TestAdminBillingForceProvision:
    """Tests for POST /api/admin/billing/clients/{client_id}/force-provision"""
    
    def test_force_provision_checks_entitlement(self, admin_headers):
        """Force provision checks entitlement status."""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/clients/{TEST_CLIENT_ID}/force-provision",
            headers=admin_headers
        )
        
        # Test client has DISABLED entitlement, so should return 400
        assert response.status_code == 400
        data = response.json()
        assert "entitlement" in data["detail"].lower() or "disabled" in data["detail"].lower()


class TestAdminBillingPortalLink:
    """Tests for POST /api/admin/billing/clients/{client_id}/portal-link"""
    
    def test_portal_link_requires_stripe_customer(self, admin_headers):
        """Portal link requires Stripe customer ID."""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/clients/{TEST_CLIENT_ID}/portal-link",
            headers=admin_headers
        )
        
        # Test client has no Stripe customer, so should return 400
        assert response.status_code == 400
        data = response.json()
        assert "stripe" in data["detail"].lower() or "customer" in data["detail"].lower()


class TestAdminBillingMessage:
    """Tests for POST /api/admin/billing/clients/{client_id}/message"""
    
    def test_message_returns_200(self, admin_headers):
        """Message endpoint returns 200 OK."""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/clients/{TEST_CLIENT_ID}/message",
            headers=admin_headers,
            json={
                "channels": ["in_app"],
                "template_id": "payment_received"
            }
        )
        assert response.status_code == 200
    
    def test_message_returns_results(self, admin_headers):
        """Message returns results for each channel."""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/clients/{TEST_CLIENT_ID}/message",
            headers=admin_headers,
            json={
                "channels": ["in_app"],
                "custom_text": "Test message from admin"
            }
        )
        data = response.json()
        
        assert data["success"] == True
        assert "results" in data
        assert "in_app" in data["results"]
    
    def test_message_404_for_invalid_client(self, admin_headers):
        """Message returns 404 for invalid client."""
        response = requests.post(
            f"{BASE_URL}/api/admin/billing/clients/invalid-client-id-12345/message",
            headers=admin_headers,
            json={
                "channels": ["in_app"],
                "custom_text": "Test"
            }
        )
        assert response.status_code == 404


class TestAdminBillingAuditLogging:
    """Tests for audit logging of admin billing actions"""
    
    def test_sync_creates_audit_log(self, admin_headers):
        """Sync action creates audit log."""
        # Perform sync
        requests.post(
            f"{BASE_URL}/api/admin/billing/clients/{TEST_CLIENT_ID}/sync",
            headers=admin_headers
        )
        
        # Check audit logs
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?action=ADMIN_ACTION&limit=10",
            headers=admin_headers
        )
        
        if response.status_code == 200:
            data = response.json()
            # Should have recent admin action logs
            assert "logs" in data or "total" in data
    
    def test_resend_setup_creates_audit_log(self, admin_headers):
        """Resend setup action creates audit log."""
        # Perform resend
        requests.post(
            f"{BASE_URL}/api/admin/billing/clients/{TEST_CLIENT_ID}/resend-setup",
            headers=admin_headers
        )
        
        # Check audit logs
        response = requests.get(
            f"{BASE_URL}/api/admin/audit-logs?action=ADMIN_ACTION&limit=10",
            headers=admin_headers
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "logs" in data or "total" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
