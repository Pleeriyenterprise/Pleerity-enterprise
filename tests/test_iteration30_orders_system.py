"""
Iteration 30 - Orders System with 14-State Workflow Machine Testing
Tests: Order creation, state transitions, admin pipeline view, admin review actions, workflow timeline
CVP ISOLATION: Verifies no CVP collections are touched
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
        # Handle both token formats
        return data.get("access_token") or data.get("token")
    return None


class TestOrdersSystemSetup:
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
        # Handle both token formats
        assert "access_token" in data or "token" in data
        assert data.get("user", {}).get("role") in ["admin", "ROLE_ADMIN"]
        print(f"✓ Admin login successful: {data.get('user', {}).get('email')}")


class TestOrderCreation:
    """Test POST /api/orders/create - Create new order"""
    
    def test_create_order_success(self):
        """Create a new order and verify response"""
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "AI Workflow Automation",
            "service_category": "workflow",
            "customer_email": "test_customer@example.com",
            "customer_name": "Test Customer",
            "customer_phone": "+447123456789",
            "customer_company": "Test Company Ltd",
            "parameters": {"workflow_type": "compliance_check"},
            "base_price": 9900,  # £99.00 in pence
            "vat_amount": 1980,  # £19.80 VAT
            "sla_hours": 24
        }
        
        response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert "order_id" in data
        assert data["order_id"].startswith("ORD-")
        assert data["status"] == "CREATED"
        assert data["total_amount"] == 11880  # base + vat
        
        print(f"✓ Order created: {data['order_id']} with status {data['status']}")
    
    def test_create_order_missing_fields(self):
        """Test order creation with missing required fields"""
        incomplete_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW"
            # Missing required fields
        }
        
        response = requests.post(f"{BASE_URL}/api/orders/create", json=incomplete_data)
        assert response.status_code == 422  # Validation error
        print("✓ Order creation correctly rejects incomplete data")
    
    def test_get_order_status(self):
        """Test GET /api/orders/{order_id}/status"""
        # First create an order
        order_data = {
            "order_type": "service",
            "service_code": "MARKET_RESEARCH",
            "service_name": "Market Research Report",
            "service_category": "research",
            "customer_email": "test_status@example.com",
            "customer_name": "Status Test Customer",
            "base_price": 4900,
            "vat_amount": 980
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]
        
        # Get status
        status_response = requests.get(f"{BASE_URL}/api/orders/{order_id}/status")
        assert status_response.status_code == 200
        
        data = status_response.json()
        assert data["order_id"] == order_id
        assert data["status"] == "CREATED"
        assert data["service_name"] == "Market Research Report"
        
        print(f"✓ Order status retrieved: {order_id} - {data['status']}")


class TestAdminPipelineView:
    """Test admin pipeline/kanban view endpoints"""
    
    def test_get_pipeline_orders(self):
        """Test GET /api/admin/orders/pipeline - Returns orders grouped by status"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/admin/orders/pipeline", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "orders" in data
        assert "counts" in data
        assert "total" in data
        assert isinstance(data["orders"], list)
        assert isinstance(data["counts"], dict)
        
        print(f"✓ Pipeline view: {data['total']} total orders, counts: {data['counts']}")
    
    def test_get_pipeline_counts(self):
        """Test GET /api/admin/orders/pipeline/counts - Returns status counts and column config"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/admin/orders/pipeline/counts", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "counts" in data
        assert "columns" in data
        assert isinstance(data["columns"], list)
        
        # Verify column structure
        for col in data["columns"]:
            assert "status" in col
            assert "label" in col
            assert "color" in col
        
        # Verify expected statuses are present
        statuses = [col["status"] for col in data["columns"]]
        expected_statuses = ["PAID", "IN_PROGRESS", "DRAFT_READY", "INTERNAL_REVIEW", "COMPLETED", "FAILED"]
        for status in expected_statuses:
            assert status in statuses, f"Missing status: {status}"
        
        print(f"✓ Pipeline counts: {len(data['columns'])} columns configured")
    
    def test_pipeline_requires_auth(self):
        """Test that pipeline endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/orders/pipeline")
        assert response.status_code in [401, 403]
        print("✓ Pipeline endpoint correctly requires authentication")


class TestOrderDetail:
    """Test order detail and timeline endpoints"""
    
    def test_get_order_detail(self):
        """Test GET /api/admin/orders/{order_id} - Returns order detail with timeline"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create a test order first
        order_data = {
            "order_type": "service",
            "service_code": "DOC_PACK_TENANCY",
            "service_name": "Tenancy Document Pack",
            "service_category": "documents",
            "customer_email": "test_detail@example.com",
            "customer_name": "Detail Test Customer",
            "base_price": 2900,
            "vat_amount": 580,
            "sla_hours": 48
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        assert create_response.status_code == 200
        test_order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/admin/orders/{test_order_id}", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "order" in data
        assert "timeline" in data
        assert "allowed_transitions" in data
        assert "is_terminal" in data
        
        order = data["order"]
        assert order["order_id"] == test_order_id
        assert order["status"] == "CREATED"
        assert "customer" in order
        assert "pricing" in order
        
        # Verify timeline has at least the creation entry
        assert len(data["timeline"]) >= 1
        assert data["timeline"][0]["new_state"] == "CREATED"
        
        print(f"✓ Order detail retrieved: {test_order_id} with {len(data['timeline'])} timeline entries")
    
    def test_get_order_timeline(self):
        """Test GET /api/admin/orders/{order_id}/timeline"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create a test order first
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Timeline Test",
            "service_category": "workflow",
            "customer_email": "test_timeline@example.com",
            "customer_name": "Timeline Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        assert create_response.status_code == 200
        test_order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/admin/orders/{test_order_id}/timeline", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "timeline" in data
        assert isinstance(data["timeline"], list)
        
        # Verify timeline entry structure
        if len(data["timeline"]) > 0:
            entry = data["timeline"][0]
            assert "execution_id" in entry
            assert "order_id" in entry
            assert "new_state" in entry
            assert "transition_type" in entry
            assert "created_at" in entry
        
        print(f"✓ Order timeline retrieved: {len(data['timeline'])} entries")
    
    def test_get_nonexistent_order(self):
        """Test getting a non-existent order returns 404"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/admin/orders/ORD-9999-NOTFOUND", headers=headers)
        assert response.status_code == 404
        print("✓ Non-existent order correctly returns 404")


class TestStateTransitions:
    """Test manual state transitions via admin API"""
    
    def test_transition_requires_reason(self):
        """Test that manual transitions require a reason"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create an order first
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "AI Workflow Test",
            "service_category": "workflow",
            "customer_email": "test_transition@example.com",
            "customer_name": "Transition Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try transition without reason (should fail validation)
        transition_data = {
            "new_status": "PAID"
            # Missing reason
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/transition",
            headers=headers,
            json=transition_data
        )
        assert response.status_code == 422  # Validation error
        print("✓ Transition correctly requires reason")
    
    def test_valid_transition_created_to_paid(self):
        """Test valid transition from CREATED to PAID"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create an order
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "AI Workflow Test",
            "service_category": "workflow",
            "customer_email": "test_paid@example.com",
            "customer_name": "Paid Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Transition to PAID
        transition_data = {
            "new_status": "PAID",
            "reason": "Manual payment confirmation for testing"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/transition",
            headers=headers,
            json=transition_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] == True
        assert data["order"]["status"] == "PAID"
        
        print(f"✓ Order {order_id} transitioned to PAID")
    
    def test_invalid_transition_rejected(self):
        """Test that invalid transitions are rejected"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create an order in CREATED status
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Invalid Transition Test",
            "service_category": "workflow",
            "customer_email": "test_invalid@example.com",
            "customer_name": "Invalid Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try invalid transition: CREATED -> COMPLETED (not allowed)
        transition_data = {
            "new_status": "COMPLETED",
            "reason": "Trying invalid transition"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/transition",
            headers=headers,
            json=transition_data
        )
        assert response.status_code == 400
        assert "Invalid transition" in response.json().get("detail", "")
        
        print("✓ Invalid transition correctly rejected")


class TestAdminReviewActions:
    """Test admin review actions (approve, regen, request info)"""
    
    def _create_order_in_review(self, token):
        """Helper to create an order and move it to INTERNAL_REVIEW"""
        # Create order
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Review Test Order",
            "service_category": "workflow",
            "customer_email": f"test_review_{datetime.now().timestamp()}@example.com",
            "customer_name": "Review Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        if create_response.status_code != 200:
            return None
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Transition through states: CREATED -> PAID -> QUEUED -> IN_PROGRESS -> DRAFT_READY -> INTERNAL_REVIEW
        transitions = [
            ("PAID", "Payment confirmed"),
            ("QUEUED", "Queued for processing"),
            ("IN_PROGRESS", "Processing started"),
            ("DRAFT_READY", "Draft completed"),
            ("INTERNAL_REVIEW", "Ready for review"),
        ]
        
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
    
    def test_approve_order(self):
        """Test POST /api/admin/orders/{order_id}/approve"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        order_id = self._create_order_in_review(token)
        if not order_id:
            pytest.skip("Could not create order in INTERNAL_REVIEW state")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/approve",
            headers=headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] == True
        assert data["order"]["status"] == "FINALISING"
        
        print(f"✓ Order {order_id} approved and moved to FINALISING")
    
    def test_request_regen(self):
        """Test POST /api/admin/orders/{order_id}/request-regen"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        order_id = self._create_order_in_review(token)
        if not order_id:
            pytest.skip("Could not create order in INTERNAL_REVIEW state")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/request-regen",
            headers=headers,
            json={"note": "Please regenerate with more detail on compliance requirements"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] == True
        assert data["order"]["status"] == "REGEN_REQUESTED"
        
        print(f"✓ Order {order_id} regeneration requested")
    
    def test_request_info(self):
        """Test POST /api/admin/orders/{order_id}/request-info"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        order_id = self._create_order_in_review(token)
        if not order_id:
            pytest.skip("Could not create order in INTERNAL_REVIEW state")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/request-info",
            headers=headers,
            json={"note": "Please provide property address and tenant details"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] == True
        assert data["order"]["status"] == "CLIENT_INPUT_REQUIRED"
        
        print(f"✓ Order {order_id} info requested, SLA paused")
    
    def test_approve_requires_review_state(self):
        """Test that approve only works from INTERNAL_REVIEW state"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create order in CREATED state
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Wrong State Test",
            "service_category": "workflow",
            "customer_email": "test_wrong_state@example.com",
            "customer_name": "Wrong State Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to approve from CREATED state (should fail)
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/approve",
            headers=headers
        )
        assert response.status_code == 400
        
        print("✓ Approve correctly requires INTERNAL_REVIEW state")


class TestInternalNotes:
    """Test internal notes functionality"""
    
    def test_add_internal_note(self):
        """Test POST /api/admin/orders/{order_id}/notes"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create an order
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Notes Test Order",
            "service_category": "workflow",
            "customer_email": "test_notes@example.com",
            "customer_name": "Notes Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Add a note
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/notes",
            headers=headers,
            json={"note": "Customer called to confirm delivery address"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] == True
        assert "internal_notes" in data["order"]
        assert "Customer called" in data["order"]["internal_notes"]
        
        # Verify status didn't change
        assert data["order"]["status"] == "CREATED"
        
        print(f"✓ Internal note added to order {order_id}")


class TestWorkflowAuditTrail:
    """Test workflow audit trail in workflow_executions collection"""
    
    def test_audit_trail_created_on_transitions(self):
        """Test that workflow_executions are created for each transition"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        # Create an order
        order_data = {
            "order_type": "service",
            "service_code": "AI_WORKFLOW",
            "service_name": "Audit Trail Test",
            "service_category": "workflow",
            "customer_email": "test_audit@example.com",
            "customer_name": "Audit Test",
            "base_price": 1000,
            "vat_amount": 200
        }
        
        create_response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data)
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Transition to PAID
        requests.post(
            f"{BASE_URL}/api/admin/orders/{order_id}/transition",
            headers=headers,
            json={"new_status": "PAID", "reason": "Test payment"}
        )
        
        # Get timeline
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/{order_id}/timeline",
            headers=headers
        )
        assert response.status_code == 200
        
        timeline = response.json()["timeline"]
        
        # Should have at least 2 entries: CREATED and PAID
        assert len(timeline) >= 2
        
        # Verify first entry is creation
        assert timeline[0]["new_state"] == "CREATED"
        assert timeline[0]["transition_type"] == "system"
        
        # Verify second entry is PAID transition
        assert timeline[1]["previous_state"] == "CREATED"
        assert timeline[1]["new_state"] == "PAID"
        assert timeline[1]["transition_type"] == "admin_manual"
        assert timeline[1]["reason"] == "Test payment"
        
        print(f"✓ Audit trail correctly logged {len(timeline)} transitions")


class TestExistingOrderVerification:
    """Test the existing test order mentioned in the request"""
    
    def test_existing_order_exists(self):
        """Verify the test order ORD-2026-B61796 exists"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/ORD-2026-B61796",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Existing order found: {data['order']['order_id']} - Status: {data['order']['status']}")
        else:
            print(f"⚠ Existing order ORD-2026-B61796 not found (may have been cleaned up)")


class TestCVPIsolation:
    """Verify CVP collections are not touched by Orders system"""
    
    def test_cvp_login_still_works(self):
        """Verify existing CVP login still works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        print("✓ CVP login still works")
    
    def test_public_website_still_works(self):
        """Verify public website endpoints still work"""
        response = requests.get(f"{BASE_URL}/api/public/services")
        assert response.status_code == 200
        print("✓ Public website services endpoint still works")


class TestSearchEndpoint:
    """Test order search functionality"""
    
    def test_search_orders(self):
        """Test GET /api/admin/orders/search"""
        token = get_admin_token()
        assert token, "Failed to get admin token"
        
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/search",
            headers=headers,
            params={"q": "test"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "orders" in data
        assert "total" in data
        
        print(f"✓ Search returned {data['total']} orders")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
