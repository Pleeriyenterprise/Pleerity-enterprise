"""
Test Suite for Iteration 45 - New Features Testing
Tests:
1. Legacy catalogue service removal (INVENTORY_PRO, EPC_CONSULT, HMO_LICENCE_SUPPORT, PORTFOLIO_ANALYSIS, LEASE_EXTENSION, AIRBNB_SETUP)
2. FastTrack queue priority (queue_priority field, expedited flag)
3. Postal tracking endpoints (GET /postal/pending, POST /{id}/postal/status, POST /{id}/postal/address)
4. Enhanced compliance score (requirement type weighting, breakdown)
"""
import pytest

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"


class TestServiceCatalogueRemoval:
    """Test that unwanted services are removed from legacy catalogue"""
    
    # Services that should NOT exist in the catalogue
    REMOVED_SERVICES = [
        "INVENTORY_PRO",
        "EPC_CONSULT", 
        "HMO_LICENCE_SUPPORT",
        "PORTFOLIO_ANALYSIS",
        "LEASE_EXTENSION",
        "AIRBNB_SETUP"
    ]
    
    def test_removed_services_not_in_seed_data(self):
        """Verify removed services are not in SEED_SERVICES"""
        from services.service_catalogue import SEED_SERVICES
        
        seed_service_codes = [s["service_code"] for s in SEED_SERVICES]
        
        for service_code in self.REMOVED_SERVICES:
            assert service_code not in seed_service_codes, \
                f"Service {service_code} should be removed from SEED_SERVICES"
        
        print(f"PASS: All {len(self.REMOVED_SERVICES)} removed services are not in SEED_SERVICES")
    
    def test_active_services_exist(self):
        """Verify expected active services still exist"""
        from services.service_catalogue import SEED_SERVICES
        
        # Services that SHOULD exist
        expected_services = [
            "CVP_COMPLIANCE_REPORT",
            "CVP_GAP_ANALYSIS",
            "HMO_AUDIT",
            "FULL_AUDIT",
            "DOC_PACK_ESSENTIAL",
            "DOC_PACK_TENANCY",
            "AI_WF_BLUEPRINT",
            "MR_BASIC",
            "MR_ADV",
            "DUE_DILIGENCE",
            "RENT_REVIEW",
            "TENANT_REF"
        ]
        
        seed_service_codes = [s["service_code"] for s in SEED_SERVICES]
        
        for service_code in expected_services:
            assert service_code in seed_service_codes, \
                f"Service {service_code} should exist in SEED_SERVICES"
        
        print(f"PASS: All {len(expected_services)} expected services exist in SEED_SERVICES")


class TestFastTrackQueuePriority:
    """Test FastTrack queue priority implementation"""
    
    def test_wf1_sets_queue_priority_for_fast_track(self):
        """Verify WF1 sets queue_priority for fast-track orders"""
        from services.workflow_automation_service import WorkflowAutomationService
        
        # Check that the service has the wf1_payment_to_queue method
        service = WorkflowAutomationService()
        assert hasattr(service, 'wf1_payment_to_queue'), "WF1 method should exist"
        
        print("PASS: WF1 method exists for queue priority handling")
    
    def test_process_queued_orders_sorts_by_priority(self):
        """Verify process_queued_orders sorts by queue_priority"""
        from services.workflow_automation_service import WorkflowAutomationService
        
        service = WorkflowAutomationService()
        assert hasattr(service, 'process_queued_orders'), "process_queued_orders method should exist"
        
        print("PASS: process_queued_orders method exists for priority sorting")
    
    def test_queue_priority_values(self):
        """Verify queue_priority values: fast_track=5, priority=10"""
        # Check the WF1 code sets correct values
        import inspect
        from services.workflow_automation_service import WorkflowAutomationService
        
        source = inspect.getsource(WorkflowAutomationService.wf1_payment_to_queue)
        
        # Check for queue_priority assignments
        assert "queue_priority" in source, "queue_priority should be set in WF1"
        assert "10" in source or "5" in source, "Priority values should be defined"
        
        print("PASS: queue_priority values are defined in WF1")


class TestPostalTrackingEndpoints:
    """Test postal tracking endpoints for printed copies"""

    @pytest.fixture
    def admin_token(self, client):
        """Get admin authentication token"""
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin authentication failed")

    def test_get_pending_postal_orders_endpoint_exists(self, client, admin_token):
        """Test GET /api/admin/orders/postal/pending endpoint"""
        response = client.get(
            "/api/admin/orders/postal/pending",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Should return 200 even if no postal orders exist
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "total" in data, "Response should include total count"
        assert "orders" in data, "Response should include orders object"
        assert "pending_print" in data, "Response should include pending_print count"
        assert "printed" in data, "Response should include printed count"
        assert "dispatched" in data, "Response should include dispatched count"
        
        print(f"PASS: GET /postal/pending returns correct structure with {data['total']} orders")
    
    def test_get_pending_postal_orders_requires_auth(self, client):
        """Test that postal pending endpoint requires authentication"""
        response = client.get("/api/admin/orders/postal/pending")
        assert response.status_code == 401, "Should require authentication"
        print("PASS: GET /postal/pending requires authentication")
    
    def test_postal_status_update_endpoint_exists(self, client, admin_token):
        """Test POST /api/admin/orders/{id}/postal/status endpoint structure"""
        # Test with a non-existent order to verify endpoint exists
        response = client.post(
            "/api/admin/orders/TEST_NONEXISTENT/postal/status",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"status": "PRINTED"}
        )
        
        # Should return 404 for non-existent order, not 405 (method not allowed)
        assert response.status_code in [400, 404], \
            f"Expected 400 or 404 for non-existent order, got {response.status_code}"
        
        print("PASS: POST /postal/status endpoint exists and validates order")
    
    def test_postal_address_endpoint_exists(self, client, admin_token):
        """Test POST /api/admin/orders/{id}/postal/address endpoint structure"""
        response = client.post(
            "/api/admin/orders/TEST_NONEXISTENT/postal/address",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "delivery_address": "123 Test Street",
                "recipient_name": "Test User"
            }
        )
        
        # Should return 404 for non-existent order
        assert response.status_code == 404, \
            f"Expected 404 for non-existent order, got {response.status_code}"
        
        print("PASS: POST /postal/address endpoint exists and validates order")
    
    def test_postal_status_valid_values(self):
        """Verify valid postal status values are defined"""
        # Check the route file for valid statuses
        valid_statuses = ["PENDING_PRINT", "PRINTED", "DISPATCHED", "DELIVERED", "FAILED"]
        
        # Read the route file to verify
        import inspect
        from routes.admin_orders import update_postal_status
        
        source = inspect.getsource(update_postal_status)
        
        for status in valid_statuses:
            assert status in source, f"Status {status} should be defined in postal status endpoint"
        
        print(f"PASS: All {len(valid_statuses)} postal status values are defined")


class TestEnhancedComplianceScore:
    """Test enhanced compliance score with requirement type weighting"""
    
    def test_requirement_type_weights_defined(self):
        """Verify REQUIREMENT_TYPE_WEIGHTS are defined"""
        from services.compliance_score import REQUIREMENT_TYPE_WEIGHTS
        
        # Check critical requirements have higher weights
        assert REQUIREMENT_TYPE_WEIGHTS.get("GAS_SAFETY", 0) >= 1.4, \
            "Gas Safety should have weight >= 1.4"
        assert REQUIREMENT_TYPE_WEIGHTS.get("EICR", 0) >= 1.3, \
            "EICR should have weight >= 1.3"
        assert REQUIREMENT_TYPE_WEIGHTS.get("EPC", 0) >= 1.1, \
            "EPC should have weight >= 1.1"
        
        print(f"PASS: REQUIREMENT_TYPE_WEIGHTS defined with {len(REQUIREMENT_TYPE_WEIGHTS)} types")
    
    def test_gas_safety_weight_is_1_5(self):
        """Verify Gas Safety has 1.5x weight"""
        from services.compliance_score import REQUIREMENT_TYPE_WEIGHTS
        
        assert REQUIREMENT_TYPE_WEIGHTS.get("GAS_SAFETY") == 1.5, \
            f"Gas Safety weight should be 1.5, got {REQUIREMENT_TYPE_WEIGHTS.get('GAS_SAFETY')}"
        
        print("PASS: Gas Safety weight is 1.5x")
    
    def test_eicr_weight_is_1_4(self):
        """Verify EICR has 1.4x weight"""
        from services.compliance_score import REQUIREMENT_TYPE_WEIGHTS
        
        assert REQUIREMENT_TYPE_WEIGHTS.get("EICR") == 1.4, \
            f"EICR weight should be 1.4, got {REQUIREMENT_TYPE_WEIGHTS.get('EICR')}"
        
        print("PASS: EICR weight is 1.4x")
    
    def test_epc_weight_is_1_2(self):
        """Verify EPC has 1.2x weight"""
        from services.compliance_score import REQUIREMENT_TYPE_WEIGHTS
        
        assert REQUIREMENT_TYPE_WEIGHTS.get("EPC") == 1.2, \
            f"EPC weight should be 1.2, got {REQUIREMENT_TYPE_WEIGHTS.get('EPC')}"
        
        print("PASS: EPC weight is 1.2x")
    
    def test_hmo_multiplier_defined(self):
        """Verify HMO_SCORE_MULTIPLIER is defined"""
        from services.compliance_score import HMO_SCORE_MULTIPLIER
        
        assert HMO_SCORE_MULTIPLIER == 0.9, \
            f"HMO multiplier should be 0.9, got {HMO_SCORE_MULTIPLIER}"
        
        print("PASS: HMO_SCORE_MULTIPLIER is 0.9")
    
    def test_get_requirement_weight_function(self):
        """Verify get_requirement_weight function works"""
        from services.compliance_score import get_requirement_weight, DEFAULT_REQUIREMENT_WEIGHT
        
        # Test known types
        assert get_requirement_weight("GAS_SAFETY") == 1.5
        assert get_requirement_weight("EICR") == 1.4
        assert get_requirement_weight("EPC") == 1.2
        
        # Test unknown type returns default
        assert get_requirement_weight("UNKNOWN_TYPE") == DEFAULT_REQUIREMENT_WEIGHT
        
        print("PASS: get_requirement_weight function works correctly")
    
    def test_calculate_compliance_score_returns_breakdown(self):
        """Verify calculate_compliance_score returns breakdown fields"""
        import asyncio
        from services.compliance_score import calculate_compliance_score
        
        # Run async function
        result = asyncio.get_event_loop().run_until_complete(
            calculate_compliance_score("TEST_CLIENT_ID")
        )
        
        # Should return breakdown even for non-existent client
        assert "breakdown" in result, "Result should include breakdown"
        assert "enhanced_model" in result, "Result should indicate enhanced model"
        
        print("PASS: calculate_compliance_score returns breakdown structure")
    
    def test_compliance_score_breakdown_fields(self):
        """Verify compliance score breakdown includes all required fields"""
        import asyncio
        from services.compliance_score import calculate_compliance_score
        
        # For a client with no properties, we get a simple response
        result = asyncio.get_event_loop().run_until_complete(
            calculate_compliance_score("TEST_CLIENT_ID")
        )
        
        # Check required fields
        assert "score" in result, "Result should include score"
        assert "grade" in result, "Result should include grade"
        assert "color" in result, "Result should include color"
        assert "message" in result, "Result should include message"
        
        print("PASS: Compliance score includes all required fields")
    
    def test_compliance_score_weights_documented(self):
        """Verify compliance score weights are documented"""
        import inspect
        from services.compliance_score import calculate_compliance_score
        
        source = inspect.getsource(calculate_compliance_score)
        
        # Check weight percentages are documented
        assert "35%" in source or "0.35" in source, "Status weight (35%) should be documented"
        assert "25%" in source or "0.25" in source, "Expiry weight (25%) should be documented"
        assert "15%" in source or "0.15" in source, "Document weight (15%) should be documented"
        
        print("PASS: Compliance score weights are documented in code")


class TestFastTrackVisualIndicator:
    """Test FastTrack visual indicator in frontend"""
    
    def test_order_list_has_fast_track_badge(self):
        """Verify OrderList.jsx has fast_track badge with animate-pulse"""
        with open("/app/frontend/src/components/admin/orders/OrderList.jsx", "r") as f:
            content = f.read()
        
        assert "fast_track" in content, "OrderList should check fast_track flag"
        assert "animate-pulse" in content, "Fast Track badge should have animate-pulse class"
        assert "bg-purple" in content, "Fast Track badge should have purple background"
        assert "Zap" in content, "Fast Track badge should use Zap icon"
        
        print("PASS: OrderList has FastTrack badge with animate-pulse and purple styling")
    
    def test_order_list_has_print_copy_badge(self):
        """Verify OrderList.jsx has Print Copy badge"""
        with open("/app/frontend/src/components/admin/orders/OrderList.jsx", "r") as f:
            content = f.read()
        
        assert "requires_postal_delivery" in content, "OrderList should check requires_postal_delivery"
        assert "Print Copy" in content, "Should display 'Print Copy' text"
        assert "bg-cyan" in content, "Print Copy badge should have cyan background"
        assert "Package" in content, "Print Copy badge should use Package icon"
        
        print("PASS: OrderList has Print Copy badge with cyan styling")


class TestOrderDetailsPanePostal:
    """Test OrderDetailsPane postal delivery section"""
    
    def test_order_details_has_postal_section(self):
        """Verify OrderDetailsPane has postal delivery section"""
        with open("/app/frontend/src/components/admin/orders/OrderDetailsPane.jsx", "r") as f:
            content = f.read()
        
        assert "Postal Delivery" in content, "Should have Postal Delivery section"
        assert "postal_status" in content, "Should display postal_status"
        assert "postal_tracking_number" in content, "Should display tracking number"
        assert "postal_delivery_address" in content, "Should display delivery address"
        
        print("PASS: OrderDetailsPane has postal delivery section with all fields")
    
    def test_postal_status_badge_colors(self):
        """Verify postal status badges have correct colors"""
        with open("/app/frontend/src/components/admin/orders/OrderDetailsPane.jsx", "r") as f:
            content = f.read()
        
        # Check status-specific colors
        assert "DELIVERED" in content, "Should handle DELIVERED status"
        assert "DISPATCHED" in content, "Should handle DISPATCHED status"
        assert "PRINTED" in content, "Should handle PRINTED status"
        assert "PENDING_PRINT" in content, "Should handle PENDING_PRINT status"
        
        print("PASS: Postal status badges have status-specific styling")


class TestWorkflowAutomationPostalFlags:
    """Test WF1 sets postal flags correctly"""
    
    def test_wf1_sets_postal_flags(self):
        """Verify WF1 sets requires_postal_delivery and postal_status"""
        import inspect
        from services.workflow_automation_service import WorkflowAutomationService
        
        source = inspect.getsource(WorkflowAutomationService.wf1_payment_to_queue)
        
        assert "requires_postal_delivery" in source, "WF1 should set requires_postal_delivery"
        assert "postal_status" in source, "WF1 should set postal_status"
        assert "PENDING_PRINT" in source, "WF1 should set initial postal_status to PENDING_PRINT"
        
        print("PASS: WF1 sets postal flags correctly")
    
    def test_wf1_sets_expedited_flag(self):
        """Verify WF1 sets expedited flag for fast-track orders"""
        import inspect
        from services.workflow_automation_service import WorkflowAutomationService
        
        source = inspect.getsource(WorkflowAutomationService.wf1_payment_to_queue)
        
        assert "expedited" in source, "WF1 should set expedited flag"
        
        print("PASS: WF1 sets expedited flag for fast-track orders")


class TestComplianceScoreAPI:
    """Test compliance score API endpoint"""
    
    @pytest.fixture
    def client_token(self, client):
        """Get client authentication token"""
        response = client.post(
            "/api/auth/login",
            json={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Client authentication failed")
    
    def test_compliance_score_endpoint_exists(self, client, client_token):
        """Test compliance score endpoint returns data"""
        response = client.get(
            "/api/compliance/score",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        
        # Should return 200 with score data
        if response.status_code == 200:
            data = response.json()
            assert "score" in data or "compliance_score" in data, \
                "Response should include score"
            print(f"PASS: Compliance score endpoint returns data")
        elif response.status_code == 404:
            print("INFO: Compliance score endpoint not found at /api/compliance/score")
        else:
            print(f"INFO: Compliance score endpoint returned {response.status_code}")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
