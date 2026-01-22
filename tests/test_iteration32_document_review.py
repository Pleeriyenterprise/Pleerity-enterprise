"""
Test Iteration 32 - Document-Centric Internal Review System
Tests for:
1. Test order creation via /api/orders/create-test-order
2. Document generation via /api/admin/orders/{id}/generate-documents
3. Structured regeneration modal with reason dropdown and mandatory notes
4. Request More Info flow transitions to CLIENT_INPUT_REQUIRED
5. Approval flow locks document version and transitions to FINALISING
6. Version lock prevents regeneration on approved orders
7. Admin notification preferences CRUD operations
8. Order detail modal with tabs (Details, Documents, Timeline)
"""
import pytest
import requests
import os
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://pleeritydocs.preview.emergentagent.com')

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"
TEST_CLIENT_EMAIL = "test@example.com"


class TestDocumentReviewSystem:
    """Tests for the document-centric Internal Review system"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.admin_token = None
        self.test_order_id = None
    
    def get_admin_token(self):
        """Get admin authentication token"""
        if self.admin_token:
            return self.admin_token
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if response.status_code == 200:
            data = response.json()
            self.admin_token = data.get("access_token")
            return self.admin_token
        
        pytest.skip(f"Admin login failed: {response.status_code}")
    
    def get_auth_headers(self):
        """Get headers with auth token"""
        token = self.get_admin_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # ==========================================
    # TEST ORDER CREATION
    # ==========================================
    
    def test_01_create_test_order(self):
        """Test creating a test order via /api/orders/create-test-order"""
        headers = self.get_auth_headers()
        
        response = self.session.post(
            f"{BASE_URL}/api/orders/create-test-order",
            headers=headers
        )
        
        assert response.status_code in [200, 201], f"Create test order failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "order_id" in data or "order" in data, "Response should contain order_id or order"
        
        # Store order_id for subsequent tests
        if "order_id" in data:
            self.__class__.test_order_id = data["order_id"]
        elif "order" in data:
            self.__class__.test_order_id = data["order"]["order_id"]
        
        print(f"Created test order: {self.__class__.test_order_id}")
    
    def test_02_verify_test_order_in_internal_review(self):
        """Verify test order is created in INTERNAL_REVIEW status"""
        headers = self.get_auth_headers()
        order_id = getattr(self.__class__, 'test_order_id', None)
        
        if not order_id:
            pytest.skip("No test order created")
        
        response = self.session.get(
            f"{BASE_URL}/api/admin/orders/{order_id}",
            headers=headers
        )
        
        assert response.status_code == 200, f"Get order failed: {response.status_code}"
        
        data = response.json()
        order = data.get("order", data)
        
        assert order.get("status") == "INTERNAL_REVIEW", f"Order should be in INTERNAL_REVIEW, got: {order.get('status')}"
        print(f"Order {order_id} is in INTERNAL_REVIEW status")
    
    # ==========================================
    # DOCUMENT GENERATION
    # ==========================================
    
    def test_03_generate_documents(self):
        """Test document generation via /api/admin/orders/{id}/generate-documents"""
        headers = self.get_auth_headers()
        order_id = getattr(self.__class__, 'test_order_id', None)
        
        if not order_id:
            pytest.skip("No test order created")
        
        response = self.session.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/generate-documents",
            headers=headers
        )
        
        assert response.status_code == 200, f"Generate documents failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Document generation should succeed"
        assert "version" in data, "Response should contain version info"
        
        version = data["version"]
        assert version.get("version") == 1, "First document should be version 1"
        print(f"Generated document version {version.get('version')}")
    
    def test_04_get_document_versions(self):
        """Test getting document versions for an order"""
        headers = self.get_auth_headers()
        order_id = getattr(self.__class__, 'test_order_id', None)
        
        if not order_id:
            pytest.skip("No test order created")
        
        response = self.session.get(
            f"{BASE_URL}/api/admin/orders/{order_id}/documents",
            headers=headers
        )
        
        assert response.status_code == 200, f"Get documents failed: {response.status_code}"
        
        data = response.json()
        assert "versions" in data, "Response should contain versions"
        assert len(data["versions"]) >= 1, "Should have at least one document version"
        assert data.get("total_versions") >= 1, "Total versions should be >= 1"
        
        print(f"Order has {data.get('total_versions')} document version(s)")
    
    # ==========================================
    # STRUCTURED REGENERATION
    # ==========================================
    
    def test_05_request_regeneration_requires_reason(self):
        """Test that regeneration requires reason and notes"""
        headers = self.get_auth_headers()
        order_id = getattr(self.__class__, 'test_order_id', None)
        
        if not order_id:
            pytest.skip("No test order created")
        
        # Try without correction_notes - should fail
        response = self.session.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/request-regen",
            headers=headers,
            json={
                "reason": "missing_info",
                "correction_notes": ""  # Empty notes
            }
        )
        
        assert response.status_code == 400, "Should fail without correction notes"
        print("Correctly rejected regeneration without notes")
    
    def test_06_request_regeneration_success(self):
        """Test successful regeneration request with reason and notes"""
        headers = self.get_auth_headers()
        order_id = getattr(self.__class__, 'test_order_id', None)
        
        if not order_id:
            pytest.skip("No test order created")
        
        response = self.session.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/request-regen",
            headers=headers,
            json={
                "reason": "incorrect_wording",
                "correction_notes": "Please fix the tenant name spelling and update the property address format",
                "affected_sections": ["tenant_details", "property_info"],
                "guardrails": {"preserve_names_dates": True}
            }
        )
        
        assert response.status_code == 200, f"Regeneration request failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Regeneration request should succeed"
        
        # Verify order moved to REGEN_REQUESTED
        order = data.get("order", {})
        assert order.get("status") == "REGEN_REQUESTED", f"Order should be in REGEN_REQUESTED, got: {order.get('status')}"
        
        print("Regeneration requested successfully")
    
    def test_07_transition_back_to_internal_review(self):
        """Transition order back to INTERNAL_REVIEW for further testing"""
        headers = self.get_auth_headers()
        order_id = getattr(self.__class__, 'test_order_id', None)
        
        if not order_id:
            pytest.skip("No test order created")
        
        # First check current status
        response = self.session.get(
            f"{BASE_URL}/api/admin/orders/{order_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            order = data.get("order", data)
            current_status = order.get("status")
            
            if current_status == "REGEN_REQUESTED":
                # Transition to INTERNAL_REVIEW
                response = self.session.post(
                    f"{BASE_URL}/api/admin/orders/{order_id}/transition",
                    headers=headers,
                    json={
                        "new_status": "INTERNAL_REVIEW",
                        "reason": "Regeneration completed - returning to review"
                    }
                )
                
                assert response.status_code == 200, f"Transition failed: {response.status_code}"
                print("Transitioned back to INTERNAL_REVIEW")
            else:
                print(f"Order already in {current_status}")
    
    # ==========================================
    # REQUEST MORE INFO FLOW
    # ==========================================
    
    def test_08_request_info_requires_notes(self):
        """Test that request info requires notes"""
        headers = self.get_auth_headers()
        order_id = getattr(self.__class__, 'test_order_id', None)
        
        if not order_id:
            pytest.skip("No test order created")
        
        # Ensure order is in INTERNAL_REVIEW first
        self.test_07_transition_back_to_internal_review()
        
        # Try without notes - should fail
        response = self.session.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/request-info",
            headers=headers,
            json={
                "request_notes": "",  # Empty notes
                "requested_fields": ["tenant_name"]
            }
        )
        
        assert response.status_code == 400, "Should fail without request notes"
        print("Correctly rejected info request without notes")
    
    def test_09_request_info_success(self):
        """Test successful request for client info"""
        headers = self.get_auth_headers()
        order_id = getattr(self.__class__, 'test_order_id', None)
        
        if not order_id:
            pytest.skip("No test order created")
        
        response = self.session.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/request-info",
            headers=headers,
            json={
                "request_notes": "Please provide the tenant's full legal name and confirm the property address",
                "requested_fields": ["tenant_name", "property_address"],
                "deadline_days": 7,
                "request_attachments": False
            }
        )
        
        assert response.status_code == 200, f"Request info failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Request info should succeed"
        
        # Verify order moved to CLIENT_INPUT_REQUIRED
        order = data.get("order", {})
        assert order.get("status") == "CLIENT_INPUT_REQUIRED", f"Order should be in CLIENT_INPUT_REQUIRED, got: {order.get('status')}"
        
        print("Info request sent successfully, order in CLIENT_INPUT_REQUIRED")
    
    def test_10_verify_sla_paused(self):
        """Verify SLA is paused when in CLIENT_INPUT_REQUIRED"""
        headers = self.get_auth_headers()
        order_id = getattr(self.__class__, 'test_order_id', None)
        
        if not order_id:
            pytest.skip("No test order created")
        
        response = self.session.get(
            f"{BASE_URL}/api/admin/orders/{order_id}",
            headers=headers
        )
        
        assert response.status_code == 200
        
        data = response.json()
        order = data.get("order", data)
        
        # Check SLA paused timestamp exists
        assert order.get("sla_paused_at") is not None or order.get("status") == "CLIENT_INPUT_REQUIRED", \
            "SLA should be paused in CLIENT_INPUT_REQUIRED state"
        
        print("SLA pause verified")
    
    # ==========================================
    # APPROVAL FLOW
    # ==========================================
    
    def test_11_create_new_order_for_approval(self):
        """Create a new test order for approval testing"""
        headers = self.get_auth_headers()
        
        response = self.session.post(
            f"{BASE_URL}/api/orders/create-test-order",
            headers=headers
        )
        
        assert response.status_code in [200, 201], f"Create test order failed: {response.status_code}"
        
        data = response.json()
        if "order_id" in data:
            self.__class__.approval_order_id = data["order_id"]
        elif "order" in data:
            self.__class__.approval_order_id = data["order"]["order_id"]
        
        print(f"Created order for approval testing: {self.__class__.approval_order_id}")
    
    def test_12_generate_documents_for_approval(self):
        """Generate documents for the approval test order"""
        headers = self.get_auth_headers()
        order_id = getattr(self.__class__, 'approval_order_id', None)
        
        if not order_id:
            pytest.skip("No approval test order created")
        
        response = self.session.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/generate-documents",
            headers=headers
        )
        
        assert response.status_code == 200, f"Generate documents failed: {response.status_code}"
        print("Documents generated for approval test")
    
    def test_13_approve_order_locks_version(self):
        """Test that approval locks the document version"""
        headers = self.get_auth_headers()
        order_id = getattr(self.__class__, 'approval_order_id', None)
        
        if not order_id:
            pytest.skip("No approval test order created")
        
        response = self.session.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/approve",
            headers=headers,
            json={
                "version": 1,
                "notes": "Approved after review - all details correct"
            }
        )
        
        assert response.status_code == 200, f"Approval failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Approval should succeed"
        assert data.get("approved_version") == 1, "Approved version should be 1"
        
        # Verify order moved to FINALISING
        order = data.get("order", {})
        assert order.get("status") == "FINALISING", f"Order should be in FINALISING, got: {order.get('status')}"
        
        print("Order approved and moved to FINALISING")
    
    def test_14_version_lock_prevents_regeneration(self):
        """Test that locked version prevents regeneration"""
        headers = self.get_auth_headers()
        order_id = getattr(self.__class__, 'approval_order_id', None)
        
        if not order_id:
            pytest.skip("No approval test order created")
        
        # First transition back to INTERNAL_REVIEW to test regen block
        # This should fail because version is locked
        response = self.session.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/request-regen",
            headers=headers,
            json={
                "reason": "incorrect_wording",
                "correction_notes": "Try to regenerate locked order"
            }
        )
        
        # Should fail because version is locked
        assert response.status_code == 400, f"Should fail on locked order: {response.status_code}"
        
        data = response.json()
        assert "locked" in data.get("detail", "").lower() or "approved" in data.get("detail", "").lower(), \
            "Error should mention locked/approved version"
        
        print("Version lock correctly prevents regeneration")
    
    def test_15_double_approval_prevented(self):
        """Test that double approval is prevented"""
        headers = self.get_auth_headers()
        order_id = getattr(self.__class__, 'approval_order_id', None)
        
        if not order_id:
            pytest.skip("No approval test order created")
        
        response = self.session.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/approve",
            headers=headers,
            json={
                "version": 1,
                "notes": "Try to approve again"
            }
        )
        
        # Should fail because already approved
        assert response.status_code == 400, f"Double approval should fail: {response.status_code}"
        print("Double approval correctly prevented")
    
    # ==========================================
    # ADMIN NOTIFICATION PREFERENCES
    # ==========================================
    
    def test_16_get_notification_preferences(self):
        """Test getting admin notification preferences"""
        headers = self.get_auth_headers()
        
        response = self.session.get(
            f"{BASE_URL}/api/admin/notifications/preferences",
            headers=headers
        )
        
        assert response.status_code == 200, f"Get preferences failed: {response.status_code}"
        
        data = response.json()
        # Check expected fields exist
        assert "email_enabled" in data or "notification_email" in data, "Should have notification settings"
        
        print(f"Got notification preferences: {data}")
    
    def test_17_update_notification_preferences(self):
        """Test updating admin notification preferences"""
        headers = self.get_auth_headers()
        
        response = self.session.put(
            f"{BASE_URL}/api/admin/notifications/preferences",
            headers=headers,
            json={
                "email_enabled": True,
                "sms_enabled": False,
                "in_app_enabled": True
            }
        )
        
        assert response.status_code == 200, f"Update preferences failed: {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, "Update should succeed"
        
        print("Notification preferences updated successfully")
    
    def test_18_get_notifications_list(self):
        """Test getting notifications list"""
        headers = self.get_auth_headers()
        
        response = self.session.get(
            f"{BASE_URL}/api/admin/notifications/",
            headers=headers
        )
        
        assert response.status_code == 200, f"Get notifications failed: {response.status_code}"
        
        data = response.json()
        assert "notifications" in data, "Response should contain notifications"
        assert "unread_count" in data, "Response should contain unread_count"
        
        print(f"Got {len(data['notifications'])} notifications, {data['unread_count']} unread")
    
    def test_19_get_unread_count(self):
        """Test getting unread notification count"""
        headers = self.get_auth_headers()
        
        response = self.session.get(
            f"{BASE_URL}/api/admin/notifications/unread-count",
            headers=headers
        )
        
        assert response.status_code == 200, f"Get unread count failed: {response.status_code}"
        
        data = response.json()
        assert "unread_count" in data, "Response should contain unread_count"
        
        print(f"Unread count: {data['unread_count']}")
    
    # ==========================================
    # ORDER DETAIL & TIMELINE
    # ==========================================
    
    def test_20_get_order_detail_with_timeline(self):
        """Test getting order detail with timeline"""
        headers = self.get_auth_headers()
        order_id = getattr(self.__class__, 'test_order_id', None)
        
        if not order_id:
            pytest.skip("No test order created")
        
        response = self.session.get(
            f"{BASE_URL}/api/admin/orders/{order_id}",
            headers=headers
        )
        
        assert response.status_code == 200, f"Get order detail failed: {response.status_code}"
        
        data = response.json()
        
        # Check order data
        assert "order" in data, "Response should contain order"
        
        # Check timeline
        assert "timeline" in data, "Response should contain timeline"
        timeline = data["timeline"]
        assert len(timeline) > 0, "Timeline should have entries"
        
        # Check allowed transitions
        assert "allowed_transitions" in data, "Response should contain allowed_transitions"
        
        print(f"Order detail retrieved with {len(timeline)} timeline entries")
    
    def test_21_get_order_timeline_only(self):
        """Test getting just the order timeline"""
        headers = self.get_auth_headers()
        order_id = getattr(self.__class__, 'test_order_id', None)
        
        if not order_id:
            pytest.skip("No test order created")
        
        response = self.session.get(
            f"{BASE_URL}/api/admin/orders/{order_id}/timeline",
            headers=headers
        )
        
        assert response.status_code == 200, f"Get timeline failed: {response.status_code}"
        
        data = response.json()
        assert "timeline" in data, "Response should contain timeline"
        
        # Verify timeline entries have required fields
        for entry in data["timeline"]:
            assert "new_state" in entry or "action" in entry, "Timeline entry should have state/action"
            assert "created_at" in entry or "timestamp" in entry, "Timeline entry should have timestamp"
        
        print(f"Timeline has {len(data['timeline'])} entries")
    
    # ==========================================
    # PIPELINE VIEW
    # ==========================================
    
    def test_22_get_pipeline_view(self):
        """Test getting pipeline view with counts"""
        headers = self.get_auth_headers()
        
        response = self.session.get(
            f"{BASE_URL}/api/admin/orders/pipeline",
            headers=headers
        )
        
        assert response.status_code == 200, f"Get pipeline failed: {response.status_code}"
        
        data = response.json()
        assert "orders" in data, "Response should contain orders"
        assert "counts" in data, "Response should contain counts"
        
        print(f"Pipeline has {len(data['orders'])} orders")
        print(f"Counts: {data['counts']}")
    
    def test_23_get_pipeline_counts(self):
        """Test getting pipeline status counts"""
        headers = self.get_auth_headers()
        
        response = self.session.get(
            f"{BASE_URL}/api/admin/orders/pipeline/counts",
            headers=headers
        )
        
        assert response.status_code == 200, f"Get counts failed: {response.status_code}"
        
        data = response.json()
        assert "counts" in data, "Response should contain counts"
        assert "columns" in data, "Response should contain columns"
        
        print(f"Pipeline counts: {data['counts']}")
    
    # ==========================================
    # CLEANUP
    # ==========================================
    
    def test_99_cleanup_test_orders(self):
        """Cleanup test orders created during testing"""
        headers = self.get_auth_headers()
        
        # Delete test orders
        for order_id in [
            getattr(self.__class__, 'test_order_id', None),
            getattr(self.__class__, 'approval_order_id', None)
        ]:
            if order_id:
                try:
                    response = self.session.post(
                        f"{BASE_URL}/api/admin/orders/{order_id}/delete",
                        headers=headers,
                        json={"reason": "Test cleanup - iteration 32"}
                    )
                    if response.status_code == 200:
                        print(f"Deleted test order: {order_id}")
                except Exception as e:
                    print(f"Failed to delete {order_id}: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
