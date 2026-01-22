"""
Test Frontend Order Intake - Public Service Ordering Flow
Tests the public services API and order creation endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://workmaster-app.preview.emergentagent.com')


class TestPublicServicesAPI:
    """Tests for GET /api/public/services endpoint"""
    
    def test_get_all_services_returns_23_services(self):
        """Verify all 23 services are returned"""
        response = requests.get(f"{BASE_URL}/api/public/services")
        assert response.status_code == 200
        
        data = response.json()
        assert "services" in data
        assert "total" in data
        assert data["total"] == 23
        assert len(data["services"]) == 23
    
    def test_services_have_required_fields(self):
        """Verify each service has required fields"""
        response = requests.get(f"{BASE_URL}/api/public/services")
        assert response.status_code == 200
        
        data = response.json()
        required_fields = [
            "service_code", "service_name", "description", "category",
            "pricing_model", "price_amount", "price_currency", "vat_rate",
            "delivery_type", "turnaround_hours", "display_order"
        ]
        
        for service in data["services"]:
            for field in required_fields:
                assert field in service, f"Missing field {field} in service {service.get('service_code')}"
    
    def test_tenant_ref_service_price_is_35_pounds(self):
        """Verify TENANT_REF service price is £35 (3500 pence)"""
        response = requests.get(f"{BASE_URL}/api/public/services/TENANT_REF")
        assert response.status_code == 200
        
        data = response.json()
        assert data["service_code"] == "TENANT_REF"
        assert data["price_amount"] == 3500  # £35.00 in pence
        assert data["price_currency"] == "gbp"
    
    def test_rent_review_service_price_is_79_pounds(self):
        """Verify RENT_REVIEW service price is £79 (7900 pence)"""
        response = requests.get(f"{BASE_URL}/api/public/services/RENT_REVIEW")
        assert response.status_code == 200
        
        data = response.json()
        assert data["service_code"] == "RENT_REVIEW"
        assert data["price_amount"] == 7900  # £79.00 in pence
    
    def test_epc_consult_service_price_is_99_pounds(self):
        """Verify EPC_CONSULT service price is £99 (9900 pence)"""
        response = requests.get(f"{BASE_URL}/api/public/services/EPC_CONSULT")
        assert response.status_code == 200
        
        data = response.json()
        assert data["service_code"] == "EPC_CONSULT"
        assert data["price_amount"] == 9900  # £99.00 in pence


class TestServiceDetailAPI:
    """Tests for GET /api/public/services/{service_code} endpoint"""
    
    def test_get_tenant_ref_service_detail(self):
        """Verify TENANT_REF service detail includes intake_fields"""
        response = requests.get(f"{BASE_URL}/api/public/services/TENANT_REF")
        assert response.status_code == 200
        
        data = response.json()
        assert "intake_fields" in data
        assert len(data["intake_fields"]) > 0
        
        # Check for expected intake fields
        field_ids = [f["field_id"] for f in data["intake_fields"]]
        assert "tenant_name" in field_ids
        assert "tenant_email" in field_ids
        assert "tenant_phone" in field_ids
        assert "current_address" in field_ids
        assert "proposed_rent" in field_ids
        assert "employment_status" in field_ids
    
    def test_get_rent_review_service_detail(self):
        """Verify RENT_REVIEW service detail includes intake_fields"""
        response = requests.get(f"{BASE_URL}/api/public/services/RENT_REVIEW")
        assert response.status_code == 200
        
        data = response.json()
        assert "intake_fields" in data
        assert len(data["intake_fields"]) > 0
        
        # Check for expected intake fields
        field_ids = [f["field_id"] for f in data["intake_fields"]]
        assert "property_address" in field_ids
        assert "current_rent" in field_ids
        assert "property_type" in field_ids
        assert "bedrooms" in field_ids
    
    def test_service_detail_includes_documents_generated(self):
        """Verify service detail includes documents_generated"""
        response = requests.get(f"{BASE_URL}/api/public/services/TENANT_REF")
        assert response.status_code == 200
        
        data = response.json()
        assert "documents_generated" in data
        assert len(data["documents_generated"]) > 0
        
        doc = data["documents_generated"][0]
        assert "document_code" in doc
        assert "document_name" in doc
        assert "format" in doc
    
    def test_nonexistent_service_returns_404(self):
        """Verify 404 for non-existent service"""
        response = requests.get(f"{BASE_URL}/api/public/services/NONEXISTENT_SERVICE")
        assert response.status_code == 404


class TestOrderCreationAPI:
    """Tests for POST /api/orders/create endpoint"""
    
    def test_create_order_success(self):
        """Verify order creation returns success with order_id"""
        order_data = {
            "order_type": "service_order",
            "service_code": "TENANT_REF",
            "service_name": "Tenant Referencing Report",
            "service_category": "STANDALONE_REPORT",
            "customer_email": "test_order_intake@example.com",
            "customer_name": "Test Order Intake User",
            "customer_phone": "+44 7123 456789",
            "customer_company": None,
            "parameters": {
                "tenant_name": "John Doe",
                "tenant_email": "john@example.com",
                "tenant_phone": "07123456789",
                "current_address": "123 Test Street, London",
                "proposed_rent": "1500",
                "employment_status": "Employed"
            },
            "base_price": 3500,
            "vat_amount": 700,
            "sla_hours": 24
        }
        
        response = requests.post(
            f"{BASE_URL}/api/orders/create",
            json=order_data
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "order_id" in data
        assert data["order_id"].startswith("ORD-")
        assert data["status"] == "CREATED"
        assert data["total_amount"] == 4200  # 3500 + 700 VAT
    
    def test_create_order_with_rent_review_service(self):
        """Verify order creation for RENT_REVIEW service"""
        order_data = {
            "order_type": "service_order",
            "service_code": "RENT_REVIEW",
            "service_name": "Rent Review Analysis",
            "service_category": "STANDALONE_REPORT",
            "customer_email": "test_rent_review@example.com",
            "customer_name": "Test Rent Review User",
            "customer_phone": None,
            "customer_company": "Test Company Ltd",
            "parameters": {
                "property_address": "456 Test Avenue, London",
                "current_rent": "1200",
                "property_type": "Flat",
                "bedrooms": "2"
            },
            "base_price": 7900,
            "vat_amount": 1580,
            "sla_hours": 24
        }
        
        response = requests.post(
            f"{BASE_URL}/api/orders/create",
            json=order_data
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "order_id" in data
        assert data["total_amount"] == 9480  # 7900 + 1580 VAT
    
    def test_create_order_missing_required_field_fails(self):
        """Verify order creation fails without required fields"""
        order_data = {
            "order_type": "service_order",
            "service_code": "TENANT_REF",
            # Missing customer_email and customer_name
        }
        
        response = requests.post(
            f"{BASE_URL}/api/orders/create",
            json=order_data
        )
        
        # Should return 422 for validation error
        assert response.status_code == 422


class TestOrderStatusAPI:
    """Tests for GET /api/orders/{order_id}/status endpoint"""
    
    def test_get_order_status(self):
        """Verify order status can be retrieved"""
        # First create an order
        order_data = {
            "order_type": "service_order",
            "service_code": "TENANT_REF",
            "service_name": "Tenant Referencing Report",
            "service_category": "STANDALONE_REPORT",
            "customer_email": "test_status@example.com",
            "customer_name": "Test Status User",
            "parameters": {},
            "base_price": 3500,
            "vat_amount": 700,
            "sla_hours": 24
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/orders/create",
            json=order_data
        )
        assert create_response.status_code == 200
        order_id = create_response.json()["order_id"]
        
        # Get order status
        status_response = requests.get(f"{BASE_URL}/api/orders/{order_id}/status")
        assert status_response.status_code == 200
        
        data = status_response.json()
        assert data["order_id"] == order_id
        assert data["status"] == "CREATED"
        assert data["service_name"] == "Tenant Referencing Report"
    
    def test_get_nonexistent_order_returns_404(self):
        """Verify 404 for non-existent order"""
        response = requests.get(f"{BASE_URL}/api/orders/ORD-NONEXISTENT/status")
        assert response.status_code == 404


class TestServiceCategories:
    """Tests for service category filtering"""
    
    def test_services_have_valid_categories(self):
        """Verify all services have valid categories"""
        response = requests.get(f"{BASE_URL}/api/public/services")
        assert response.status_code == 200
        
        data = response.json()
        valid_categories = ["CVP_FEATURE", "CVP_ADDON", "STANDALONE_REPORT", "DOCUMENT_PACK"]
        
        for service in data["services"]:
            assert service["category"] in valid_categories, \
                f"Invalid category {service['category']} for service {service['service_code']}"
    
    def test_standalone_reports_count(self):
        """Verify STANDALONE_REPORT category has expected services"""
        response = requests.get(f"{BASE_URL}/api/public/services")
        assert response.status_code == 200
        
        data = response.json()
        standalone_reports = [s for s in data["services"] if s["category"] == "STANDALONE_REPORT"]
        
        # Should have multiple standalone reports including TENANT_REF, RENT_REVIEW, EPC_CONSULT
        assert len(standalone_reports) >= 3
        
        service_codes = [s["service_code"] for s in standalone_reports]
        assert "TENANT_REF" in service_codes
        assert "RENT_REVIEW" in service_codes
        assert "EPC_CONSULT" in service_codes
