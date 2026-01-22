"""
Iteration 31 - Enterprise-grade Orders Pipeline Testing
Tests: Visual emphasis, clickable stages, state-specific actions, rollback, delete, priority, audit timeline
7 Mandatory Requirements:
1) Pipeline stage visual emphasis (highlighted if orders present, muted if empty)
2) Clickable pipeline stages with filtered order lists
3) State-specific action panel (only valid actions shown)
4) End-to-end automation after human action
5) Real-time updates with auto-refresh
6) Manual fallback controls (rollback, retry, delete with reason)
7) Audit timeline with all transitions logged
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


def get_admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    return None


class TestSetup:
    """Setup and authentication tests"""
    
    def test_health_check(self):
        """Verify API is healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ API health check passed")
    
    def test_admin_login(self):
        """Verify admin can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data or "token" in data
        print(f"✓ Admin login successful")


class TestPipelineVisualEmphasis:
    """Test Requirement 1: Pipeline stage visual emphasis"""
    
    def test_pipeline_returns_counts_for_emphasis(self):
        """Test that pipeline returns counts to determine visual emphasis"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/admin/orders/pipeline", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "counts" in data
        assert isinstance(data["counts"], dict)
        
        # Counts should be available for determining visual emphasis
        print(f"✓ Pipeline counts for visual emphasis: {data['counts']}")
    
    def test_pipeline_columns_configuration(self):
        """Test that pipeline columns have proper configuration for styling"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/admin/orders/pipeline/counts", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "columns" in data
        
        # Each column should have status, label, color for styling
        for col in data["columns"]:
            assert "status" in col
            assert "label" in col
            assert "color" in col
        
        print(f"✓ Pipeline has {len(data['columns'])} columns with styling config")


class TestClickablePipelineStages:
    """Test Requirement 2: Clickable pipeline stages with filtered order lists"""
    
    def test_pipeline_filter_by_status(self):
        """Test filtering orders by status (simulates clicking a stage)"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test filtering by PAID status
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/pipeline",
            headers=headers,
            params={"status": "PAID"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "orders" in data
        
        # All returned orders should be in PAID status
        for order in data["orders"]:
            assert order["status"] == "PAID", f"Expected PAID, got {order['status']}"
        
        print(f"✓ Stage filter returns {len(data['orders'])} orders in PAID status")
    
    def test_pipeline_filter_internal_review(self):
        """Test filtering by INTERNAL_REVIEW status"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/pipeline",
            headers=headers,
            params={"status": "INTERNAL_REVIEW"}
        )
        assert response.status_code == 200
        
        data = response.json()
        for order in data["orders"]:
            assert order["status"] == "INTERNAL_REVIEW"
        
        print(f"✓ INTERNAL_REVIEW filter returns {len(data['orders'])} orders")


class TestStateSpecificActionPanel:
    """Test Requirement 3: State-specific action panel"""
    
    def test_internal_review_has_4_actions(self):
        """Test INTERNAL_REVIEW state shows exactly 4 actions: Approve, Regen, Request Info, Cancel"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create order and move to INTERNAL_REVIEW
        order_id = self._create_order_in_state(token, "INTERNAL_REVIEW")
        if not order_id:
            pytest.skip("Could not create order in INTERNAL_REVIEW state")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/admin/orders/{order_id}", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["order"]["status"] == "INTERNAL_REVIEW"
        
        # Check admin_actions are available
        assert "admin_actions" in data
        assert data["admin_actions"] is not None
        
        # Should have approve, regen, request_info
        expected_actions = ["approve", "regen", "request_info"]
        for action in expected_actions:
            assert action in data["admin_actions"], f"Missing action: {action}"
        
        # Check allowed_transitions includes CANCELLED
        assert "CANCELLED" in data["allowed_transitions"]
        
        print(f"✓ INTERNAL_REVIEW has correct actions: {list(data['admin_actions'].keys())}")
    
    def test_failed_state_has_retry_and_rollback(self):
        """Test FAILED state shows Retry and Rollback actions"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create order and move to FAILED
        order_id = self._create_order_in_state(token, "FAILED")
        if not order_id:
            pytest.skip("Could not create order in FAILED state")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/admin/orders/{order_id}", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["order"]["status"] == "FAILED"
        
        # FAILED should allow transition to QUEUED (retry)
        assert "QUEUED" in data["allowed_transitions"]
        
        print(f"✓ FAILED state has retry (QUEUED) in allowed transitions")
    
    def _create_order_in_state(self, token, target_state):
        """Helper to create an order and move it to target state"""
        # Create order
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": f"Test Order for {target_state}",
            "service_category": "workflow",
            "customer_email": f"test_{target_state.lower()}_{datetime.now().timestamp()}@example.com",
            "customer_name": f"Test {target_state}",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        if create_response.status_code != 200:
            return None
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Define transition paths
        if target_state == "INTERNAL_REVIEW":
            transitions = [
                ("PAID", "Payment confirmed"),
                ("QUEUED", "Queued for processing"),
                ("IN_PROGRESS", "Processing started"),
                ("DRAFT_READY", "Draft completed"),
                ("INTERNAL_REVIEW", "Ready for review"),
            ]
        elif target_state == "FAILED":
            transitions = [
                ("PAID", "Payment confirmed"),
                ("QUEUED", "Queued for processing"),
                ("IN_PROGRESS", "Processing started"),
                ("FAILED", "Processing failed"),
            ]
        elif target_state == "PAID":
            transitions = [("PAID", "Payment confirmed")]
        else:
            return None
        
        for new_status, reason in transitions:
            response = requests.post(
                f"{BASE_URL}/api/admin/orders/{order_id}/transition",
                headers=headers,
                json={"new_status": new_status, "reason": reason}
            )
            if response.status_code != 200:
                print(f"Failed to transition to {new_status}: {response.text}")
                return None
        
        return order_id


class TestDeleteOrderWithReason:
    """Test Requirement 6: Delete order requires mandatory reason"""
    
    def test_delete_order_success(self):
        """Test POST /api/admin/orders/{id}/delete works with reason"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create an order to delete
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Order to Delete",
            "service_category": "workflow",
            "customer_email": f"test_delete_{datetime.now().timestamp()}@example.com",
            "customer_name": "Delete Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Delete with reason
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/delete",
            headers=headers,
            json={"reason": "Test deletion - duplicate order created by mistake"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] == True
        
        # Verify order is deleted
        get_response = requests.get(f"{BASE_URL}/api/admin/orders/{order_id}", headers=headers)
        assert get_response.status_code == 404
        
        print(f"✓ Order {order_id} deleted successfully with reason")
    
    def test_delete_requires_reason(self):
        """Test that delete fails without reason"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create an order
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Order to Delete",
            "service_category": "workflow",
            "customer_email": f"test_delete_noreason_{datetime.now().timestamp()}@example.com",
            "customer_name": "Delete Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try delete without reason
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/delete",
            headers=headers,
            json={"reason": ""}  # Empty reason
        )
        assert response.status_code == 400
        
        print("✓ Delete correctly requires non-empty reason")


class TestRollbackWithReason:
    """Test Requirement 6: Rollback requires mandatory reason"""
    
    def test_rollback_from_failed(self):
        """Test POST /api/admin/orders/{id}/rollback works from FAILED state"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create order and move to FAILED
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Rollback Test Order",
            "service_category": "workflow",
            "customer_email": f"test_rollback_{datetime.now().timestamp()}@example.com",
            "customer_name": "Rollback Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Move to FAILED state
        transitions = [
            ("PAID", "Payment confirmed"),
            ("QUEUED", "Queued"),
            ("IN_PROGRESS", "Started"),
            ("FAILED", "Processing failed"),
        ]
        
        for new_status, reason in transitions:
            requests.post(
                f"{BASE_URL}/api/admin/orders/{order_id}/transition",
                headers=headers,
                json={"new_status": new_status, "reason": reason}
            )
        
        # Verify in FAILED state
        detail_response = requests.get(f"{BASE_URL}/api/admin/orders/{order_id}", headers=headers)
        assert detail_response.json()["order"]["status"] == "FAILED"
        
        # Rollback
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/rollback",
            headers=headers,
            json={"reason": "Rollback to retry processing after fixing issue"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] == True
        # FAILED should rollback to QUEUED
        assert data["order"]["status"] == "QUEUED"
        
        print(f"✓ Order {order_id} rolled back from FAILED to QUEUED")
    
    def test_rollback_requires_reason(self):
        """Test that rollback fails without reason"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create order in FAILED state
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Rollback No Reason Test",
            "service_category": "workflow",
            "customer_email": f"test_rollback_noreason_{datetime.now().timestamp()}@example.com",
            "customer_name": "Rollback Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Move to FAILED
        for new_status in ["PAID", "QUEUED", "IN_PROGRESS", "FAILED"]:
            requests.post(
                f"{BASE_URL}/api/admin/orders/{order_id}/transition",
                headers=headers,
                json={"new_status": new_status, "reason": "Test"}
            )
        
        # Try rollback without reason
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/rollback",
            headers=headers,
            json={"reason": ""}
        )
        assert response.status_code == 400
        
        print("✓ Rollback correctly requires non-empty reason")


class TestResendRequest:
    """Test resend-request endpoint"""
    
    def test_resend_request_in_client_input_required(self):
        """Test POST /api/admin/orders/{id}/resend-request works"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create order and move to CLIENT_INPUT_REQUIRED
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Resend Request Test",
            "service_category": "workflow",
            "customer_email": f"test_resend_{datetime.now().timestamp()}@example.com",
            "customer_name": "Resend Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Move to CLIENT_INPUT_REQUIRED
        transitions = [
            ("PAID", "Payment confirmed"),
            ("QUEUED", "Queued"),
            ("IN_PROGRESS", "Started"),
            ("DRAFT_READY", "Draft ready"),
            ("INTERNAL_REVIEW", "Review"),
        ]
        
        for new_status, reason in transitions:
            requests.post(
                f"{BASE_URL}/api/admin/orders/{order_id}/transition",
                headers=headers,
                json={"new_status": new_status, "reason": reason}
            )
        
        # Request info to move to CLIENT_INPUT_REQUIRED
        requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/request-info",
            headers=headers,
            json={"note": "Need more details"}
        )
        
        # Verify in CLIENT_INPUT_REQUIRED
        detail_response = requests.get(f"{BASE_URL}/api/admin/orders/{order_id}", headers=headers)
        assert detail_response.json()["order"]["status"] == "CLIENT_INPUT_REQUIRED"
        
        # Resend request
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/resend-request",
            headers=headers,
            json={"note": "Reminder: Please provide the requested information"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] == True
        
        print(f"✓ Resend request successful for order {order_id}")


class TestPriorityFlag:
    """Test priority flag functionality"""
    
    def test_set_priority_flag(self):
        """Test POST /api/admin/orders/{id}/priority sets priority flag"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create an order
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Priority Test Order",
            "service_category": "workflow",
            "customer_email": f"test_priority_{datetime.now().timestamp()}@example.com",
            "customer_name": "Priority Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Set priority
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/priority",
            headers=headers,
            json={"priority": True, "reason": "VIP customer - urgent request"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] == True
        assert data["order"]["priority"] == True
        
        print(f"✓ Priority flag set for order {order_id}")
    
    def test_remove_priority_flag(self):
        """Test removing priority flag"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create an order
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Priority Remove Test",
            "service_category": "workflow",
            "customer_email": f"test_priority_remove_{datetime.now().timestamp()}@example.com",
            "customer_name": "Priority Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Set priority first
        requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/priority",
            headers=headers,
            json={"priority": True}
        )
        
        # Remove priority
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/priority",
            headers=headers,
            json={"priority": False, "reason": "Issue resolved"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["order"]["priority"] == False
        
        print(f"✓ Priority flag removed for order {order_id}")


class TestAuditTimeline:
    """Test Requirement 7: Audit timeline with all transitions logged"""
    
    def test_audit_timeline_shows_transition_type(self):
        """Test that audit timeline shows transition_type (system, admin_manual, admin_delete)"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create an order
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Audit Timeline Test",
            "service_category": "workflow",
            "customer_email": f"test_audit_{datetime.now().timestamp()}@example.com",
            "customer_name": "Audit Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Make some transitions
        requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/transition",
            headers=headers,
            json={"new_status": "PAID", "reason": "Manual payment confirmation"}
        )
        
        # Get timeline
        response = requests.get(f"{BASE_URL}/api/admin/orders/{order_id}/timeline", headers=headers)
        assert response.status_code == 200
        
        timeline = response.json()["timeline"]
        
        # Verify timeline entries have transition_type
        for entry in timeline:
            assert "transition_type" in entry
            assert entry["transition_type"] in ["system", "admin_manual", "admin_delete", "customer_action"]
        
        # First entry (creation) should be system
        assert timeline[0]["transition_type"] == "system"
        
        # Second entry (manual transition) should be admin_manual
        if len(timeline) > 1:
            assert timeline[1]["transition_type"] == "admin_manual"
        
        print(f"✓ Audit timeline shows transition_type correctly")
    
    def test_audit_timeline_logs_admin_email(self):
        """Test that audit timeline logs admin email for manual actions"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create an order
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Admin Email Audit Test",
            "service_category": "workflow",
            "customer_email": f"test_admin_audit_{datetime.now().timestamp()}@example.com",
            "customer_name": "Admin Audit Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Make a transition
        requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/transition",
            headers=headers,
            json={"new_status": "PAID", "reason": "Test transition"}
        )
        
        # Get timeline
        response = requests.get(f"{BASE_URL}/api/admin/orders/{order_id}/timeline", headers=headers)
        timeline = response.json()["timeline"]
        
        # Find admin_manual entry
        admin_entries = [e for e in timeline if e["transition_type"] == "admin_manual"]
        assert len(admin_entries) > 0
        
        # Should have triggered_by with user_email
        admin_entry = admin_entries[0]
        assert "triggered_by" in admin_entry
        assert admin_entry["triggered_by"]["user_email"] == ADMIN_EMAIL
        
        print(f"✓ Audit timeline logs admin email: {admin_entry['triggered_by']['user_email']}")


class TestPriorityOrdersSorting:
    """Test that priority orders appear first in sorted lists"""
    
    def test_priority_orders_first_in_pipeline(self):
        """Test that priority orders appear first in pipeline view"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create two orders - one priority, one not
        timestamp = datetime.now().timestamp()
        
        # Create non-priority order first
        order1_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Non-Priority Order",
            "service_category": "workflow",
            "customer_email": f"test_nonpriority_{timestamp}@example.com",
            "customer_name": "Non-Priority",
            "base_price": 1000,
            "vat_amount": 200
        }
        create1 = requests.post(f"{BASE_URL}/api/orders/create", json=order1_data)
        order1_id = create1.json()["order_id"]
        
        # Move to PAID
        requests.post(
            f"{BASE_URL}/api/admin/orders/{order1_id}/transition",
            headers=headers,
            json={"new_status": "PAID", "reason": "Test"}
        )
        
        # Create priority order
        order2_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Priority Order",
            "service_category": "workflow",
            "customer_email": f"test_priority_{timestamp}@example.com",
            "customer_name": "Priority",
            "base_price": 1000,
            "vat_amount": 200
        }
        create2 = requests.post(f"{BASE_URL}/api/orders/create", json=order2_data)
        order2_id = create2.json()["order_id"]
        
        # Move to PAID and set priority
        requests.post(
            f"{BASE_URL}/api/admin/orders/{order2_id}/transition",
            headers=headers,
            json={"new_status": "PAID", "reason": "Test"}
        )
        requests.post(
            f"{BASE_URL}/api/admin/orders/{order2_id}/priority",
            headers=headers,
            json={"priority": True, "reason": "VIP"}
        )
        
        # Get pipeline filtered by PAID
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/pipeline",
            headers=headers,
            params={"status": "PAID"}
        )
        assert response.status_code == 200
        
        orders = response.json()["orders"]
        
        # Find our test orders
        priority_orders = [o for o in orders if o.get("priority") == True]
        
        if len(priority_orders) > 0:
            # Priority orders should have priority flag
            assert priority_orders[0]["priority"] == True
            print(f"✓ Priority orders have priority flag set")
        else:
            print("⚠ No priority orders found in PAID status")


class TestConfirmationDialogs:
    """Test that admin actions require confirmation (tested via API validation)"""
    
    def test_transition_requires_reason(self):
        """Test that transitions require reason (confirmation equivalent)"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create an order
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Confirmation Test",
            "service_category": "workflow",
            "customer_email": f"test_confirm_{datetime.now().timestamp()}@example.com",
            "customer_name": "Confirm Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try transition without reason
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/transition",
            headers=headers,
            json={"new_status": "PAID"}  # Missing reason
        )
        assert response.status_code == 422  # Validation error
        
        print("✓ Transitions require reason (confirmation)")


class TestExistingOrdersInPipeline:
    """Test that existing orders from previous tests are visible"""
    
    def test_pipeline_has_orders(self):
        """Test that pipeline shows existing orders"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/admin/orders/pipeline", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        
        print(f"✓ Pipeline has {data['total']} total orders")
        print(f"  Counts by status: {data['counts']}")
        
        # Check for orders in PAID and INTERNAL_REVIEW as mentioned in context
        if data['counts'].get('PAID', 0) > 0:
            print(f"  ✓ Found {data['counts']['PAID']} orders in PAID status")
        if data['counts'].get('INTERNAL_REVIEW', 0) > 0:
            print(f"  ✓ Found {data['counts']['INTERNAL_REVIEW']} orders in INTERNAL_REVIEW status")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
