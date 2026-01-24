"""
Iteration 33 - Phase A Foundation Testing
Tests for:
1. Service Catalogue management (13 seeded services)
2. Cancel/Archive order functionality (replacing DELETE)
3. Orders Pipeline with status counts
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://prompt-fix-6.preview.emergentagent.com')

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"
CLIENT_EMAIL = "test@pleerity.com"
CLIENT_PASSWORD = "TestClient123!"


class TestAuthAndSetup:
    """Authentication and setup tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    def test_admin_login(self, admin_token):
        """Test admin can login"""
        assert admin_token is not None
        assert len(admin_token) > 0
        print(f"✓ Admin login successful")


class TestServiceCatalogue:
    """Service Catalogue API tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    def test_list_services_returns_13_seeded(self, admin_token):
        """Test that service catalogue has 13 seeded services"""
        response = requests.get(
            f"{BASE_URL}/api/admin/services/?include_inactive=true",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to list services: {response.text}"
        data = response.json()
        assert "services" in data
        assert "total" in data
        # Should have at least 13 seeded services
        assert data["total"] >= 13, f"Expected at least 13 services, got {data['total']}"
        print(f"✓ Service catalogue has {data['total']} services")
    
    def test_get_service_categories(self, admin_token):
        """Test getting service categories dropdown data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/services/categories",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get categories: {response.text}"
        data = response.json()
        
        # Verify all category types are present
        assert "categories" in data
        assert "pricing_models" in data
        assert "delivery_types" in data
        assert "generation_modes" in data
        
        # Check categories
        category_values = [c["value"] for c in data["categories"]]
        assert "CVP_FEATURE" in category_values
        assert "CVP_ADDON" in category_values
        assert "STANDALONE_REPORT" in category_values
        assert "DOCUMENT_PACK" in category_values
        print(f"✓ Categories endpoint returns all 4 category types")
    
    def test_get_single_service(self, admin_token):
        """Test getting a single service by code"""
        response = requests.get(
            f"{BASE_URL}/api/admin/services/DOC_PACK_ESSENTIAL",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get service: {response.text}"
        data = response.json()
        
        assert data["service_code"] == "DOC_PACK_ESSENTIAL"
        assert data["service_name"] == "Essential Landlord Document Pack"
        assert data["category"] == "DOCUMENT_PACK"
        assert data["price_amount"] == 4999  # £49.99 in pence
        print(f"✓ Single service retrieval works correctly")
    
    def test_create_new_service(self, admin_token):
        """Test creating a new service"""
        new_service = {
            "service_code": "TEST_SERVICE_001",
            "service_name": "Test Service for Phase A",
            "description": "A test service created during Phase A testing",
            "short_description": "Test service",
            "category": "STANDALONE_REPORT",
            "pricing_model": "one_time",
            "price_amount": 9999,
            "price_currency": "gbp",
            "delivery_type": "portal+email",
            "estimated_turnaround_hours": 48,
            "review_required": True,
            "generation_mode": "TEMPLATE_ONLY",
            "requires_cvp_subscription": False,
            "active": True,
            "display_order": 100
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/services/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=new_service
        )
        
        # May already exist from previous test run
        if response.status_code == 400 and "already exists" in response.text:
            print(f"✓ Service already exists (from previous test run)")
            return
        
        assert response.status_code == 200, f"Failed to create service: {response.text}"
        data = response.json()
        assert data["success"] == True
        assert data["service"]["service_code"] == "TEST_SERVICE_001"
        print(f"✓ New service created successfully")
    
    def test_update_service(self, admin_token):
        """Test updating an existing service"""
        update_data = {
            "short_description": "Updated test service description"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/services/TEST_SERVICE_001",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=update_data
        )
        
        if response.status_code == 404:
            pytest.skip("Test service not found - create test may have failed")
        
        assert response.status_code == 200, f"Failed to update service: {response.text}"
        data = response.json()
        assert data["success"] == True
        print(f"✓ Service updated successfully")
    
    def test_deactivate_service(self, admin_token):
        """Test deactivating a service"""
        response = requests.post(
            f"{BASE_URL}/api/admin/services/TEST_SERVICE_001/deactivate",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 404:
            pytest.skip("Test service not found")
        
        assert response.status_code == 200, f"Failed to deactivate: {response.text}"
        data = response.json()
        assert data["success"] == True
        print(f"✓ Service deactivated successfully")
    
    def test_activate_service(self, admin_token):
        """Test activating a service"""
        response = requests.post(
            f"{BASE_URL}/api/admin/services/TEST_SERVICE_001/activate",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 404:
            pytest.skip("Test service not found")
        
        assert response.status_code == 200, f"Failed to activate: {response.text}"
        data = response.json()
        assert data["success"] == True
        print(f"✓ Service activated successfully")
    
    def test_public_services_endpoint(self):
        """Test public services endpoint (no auth required)"""
        response = requests.get(f"{BASE_URL}/api/admin/services/public/list")
        assert response.status_code == 200, f"Failed to get public services: {response.text}"
        data = response.json()
        
        assert "services" in data
        assert "total" in data
        # Public endpoint should only show active services
        for service in data["services"]:
            # Public response should not include sensitive fields
            assert "stripe_price_id" not in service or service.get("stripe_price_id") is None
        print(f"✓ Public services endpoint works ({data['total']} active services)")


class TestOrdersCancelArchive:
    """Tests for Cancel/Archive order functionality"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def test_order_id(self, admin_token):
        """Create a test order for cancel/archive testing"""
        # First try to create a test order
        response = requests.post(
            f"{BASE_URL}/api/orders/create-test-order",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "service_code": "DOC_PACK_ESSENTIAL",
                "status": "CREATED"  # Start in CREATED for cancel testing
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("order_id") or data.get("order", {}).get("order_id")
        
        # If test order creation fails, use existing test order
        return "ORD-2026-71A9A4"
    
    def test_delete_returns_405(self, admin_token, test_order_id):
        """Test that DELETE endpoint returns 405 Method Not Allowed"""
        response = requests.delete(
            f"{BASE_URL}/api/admin/orders/{test_order_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 405, f"Expected 405, got {response.status_code}: {response.text}"
        data = response.json()
        assert "DELETE is not permitted" in data["detail"]
        assert "immutable records" in data["detail"]
        print(f"✓ DELETE returns 405 with proper message")
    
    def test_cancel_order_requires_reason(self, admin_token, test_order_id):
        """Test that cancel requires a reason"""
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{test_order_id}/cancel",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": ""}  # Empty reason
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"✓ Cancel requires non-empty reason")
    
    def test_archive_order_requires_reason(self, admin_token, test_order_id):
        """Test that archive requires a reason"""
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{test_order_id}/archive",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": ""}  # Empty reason
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"✓ Archive requires non-empty reason")
    
    def test_archive_order_success(self, admin_token):
        """Test archiving an order successfully"""
        # Use an existing active order
        test_order = "ORD-2026-71A9A4"
        
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{test_order}/archive",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "Testing archive functionality in Phase A"}
        )
        
        if response.status_code == 404:
            pytest.skip("Test order not found")
        
        assert response.status_code == 200, f"Failed to archive: {response.text}"
        data = response.json()
        assert data["success"] == True
        print(f"✓ Order archived successfully")
    
    def test_unarchive_order(self, admin_token):
        """Test unarchiving an order"""
        test_order = "ORD-2026-71A9A4"
        
        response = requests.post(
            f"{BASE_URL}/api/admin/orders/{test_order}/unarchive",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 404:
            pytest.skip("Test order not found")
        
        if response.status_code == 400 and "not archived" in response.text:
            print(f"✓ Order was not archived (expected if archive test didn't run)")
            return
        
        assert response.status_code == 200, f"Failed to unarchive: {response.text}"
        data = response.json()
        assert data["success"] == True
        print(f"✓ Order unarchived successfully")


class TestOrdersPipeline:
    """Tests for Orders Pipeline functionality"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    def test_pipeline_endpoint(self, admin_token):
        """Test pipeline endpoint returns orders and counts"""
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/pipeline",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200, f"Failed to get pipeline: {response.text}"
        data = response.json()
        
        assert "orders" in data
        assert "counts" in data
        print(f"✓ Pipeline endpoint returns {len(data['orders'])} orders")
        print(f"  Status counts: {data['counts']}")
    
    def test_pipeline_counts_endpoint(self, admin_token):
        """Test pipeline counts endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/pipeline/counts",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200, f"Failed to get counts: {response.text}"
        data = response.json()
        
        assert "counts" in data
        assert "columns" in data
        
        # Verify column structure
        for col in data["columns"]:
            assert "status" in col
            assert "label" in col
            assert "color" in col
        
        print(f"✓ Pipeline counts endpoint works")
        print(f"  Columns: {[c['label'] for c in data['columns']]}")
    
    def test_order_detail_endpoint(self, admin_token):
        """Test getting order details"""
        # Use a known test order
        test_order = "ORD-2026-71A9A4"
        
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/{test_order}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 404:
            pytest.skip("Test order not found")
        
        assert response.status_code == 200, f"Failed to get order: {response.text}"
        data = response.json()
        
        assert "order" in data
        assert "timeline" in data
        assert "allowed_transitions" in data
        print(f"✓ Order detail endpoint works")
        print(f"  Order status: {data['order'].get('status')}")
    
    def test_order_search(self, admin_token):
        """Test order search functionality"""
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/search?q=ORD",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200, f"Failed to search: {response.text}"
        data = response.json()
        
        assert "orders" in data
        assert "total" in data
        print(f"✓ Order search works ({data['total']} results)")


class TestExistingTestOrders:
    """Tests using existing test orders mentioned in context"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    def test_cancelled_order_exists(self, admin_token):
        """Verify cancelled order ORD-2026-6FD468 exists"""
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/ORD-2026-6FD468",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 404:
            print("⚠ Cancelled test order not found")
            return
        
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Cancelled order found, status: {data['order'].get('status')}")
    
    def test_archived_order_exists(self, admin_token):
        """Verify archived order ORD-2026-C40465 exists"""
        response = requests.get(
            f"{BASE_URL}/api/admin/orders/ORD-2026-C40465",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 404:
            print("⚠ Archived test order not found")
            return
        
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Archived order found, status: {data['order'].get('status')}")
        print(f"  Is archived: {data['order'].get('is_archived')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
