"""
Phase D Service Expansion Tests
Tests for 9 new services added to the Service Catalogue
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# New services added in Phase D
NEW_SERVICE_CODES = [
    "INVENTORY_PRO",
    "DUE_DILIGENCE",
    "RENT_REVIEW",
    "TENANT_REF",
    "EPC_CONSULT",
    "HMO_LICENCE_SUPPORT",
    "PORTFOLIO_ANALYSIS",
    "LEASE_EXTENSION",
    "AIRBNB_SETUP",
]

# Expected pricing for new services (in pence)
EXPECTED_PRICING = {
    "INVENTORY_PRO": 19900,       # £199
    "DUE_DILIGENCE": 49900,       # £499
    "RENT_REVIEW": 7900,          # £79
    "TENANT_REF": 3500,           # £35
    "EPC_CONSULT": 9900,          # £99
    "HMO_LICENCE_SUPPORT": 29900, # £299
    "PORTFOLIO_ANALYSIS": 39900,  # £399
    "LEASE_EXTENSION": 24900,     # £249
    "AIRBNB_SETUP": 19900,        # £199
}


class TestPublicServicesAPI:
    """Test public services API endpoints"""
    
    def test_public_services_list_returns_active_services(self):
        """Test that public services list returns active services"""
        response = requests.get(f"{BASE_URL}/api/admin/services/public/list")
        assert response.status_code == 200
        
        data = response.json()
        assert "services" in data
        assert "total" in data
        assert data["total"] >= 23, f"Expected at least 23 services, got {data['total']}"
        
        print(f"✓ Public services API returns {data['total']} services")
    
    def test_all_new_services_present_in_public_list(self):
        """Test that all 9 new services are present in public list"""
        response = requests.get(f"{BASE_URL}/api/admin/services/public/list")
        assert response.status_code == 200
        
        data = response.json()
        service_codes = [s["service_code"] for s in data["services"]]
        
        missing_services = []
        for code in NEW_SERVICE_CODES:
            if code not in service_codes:
                missing_services.append(code)
        
        assert len(missing_services) == 0, f"Missing services: {missing_services}"
        print(f"✓ All 9 new services present in public list")
    
    def test_new_services_have_correct_pricing(self):
        """Test that new services have correct pricing"""
        response = requests.get(f"{BASE_URL}/api/admin/services/public/list")
        assert response.status_code == 200
        
        data = response.json()
        services_by_code = {s["service_code"]: s for s in data["services"]}
        
        pricing_errors = []
        for code, expected_price in EXPECTED_PRICING.items():
            if code in services_by_code:
                actual_price = services_by_code[code]["price_amount"]
                if actual_price != expected_price:
                    pricing_errors.append(f"{code}: expected {expected_price}, got {actual_price}")
        
        assert len(pricing_errors) == 0, f"Pricing errors: {pricing_errors}"
        print(f"✓ All new services have correct pricing")


class TestAdminServicesAPI:
    """Test admin services API endpoints"""
    
    @pytest.fixture
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@pleerity.com",
            "password": "Admin123!"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin authentication failed")
    
    def test_admin_services_list_returns_all_services(self, auth_token):
        """Test that admin services list returns all services including inactive"""
        response = requests.get(
            f"{BASE_URL}/api/admin/services/?include_inactive=true",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "services" in data
        assert "total" in data
        assert data["total"] >= 23, f"Expected at least 23 services, got {data['total']}"
        
        print(f"✓ Admin services API returns {data['total']} services")
    
    def test_admin_can_get_individual_new_services(self, auth_token):
        """Test that admin can get details of each new service"""
        for code in NEW_SERVICE_CODES:
            response = requests.get(
                f"{BASE_URL}/api/admin/services/{code}",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            assert response.status_code == 200, f"Failed to get service {code}"
            
            data = response.json()
            assert data["service_code"] == code
            assert "intake_fields" in data
            assert "documents_generated" in data
            
        print(f"✓ Admin can access all 9 new services individually")
    
    def test_new_services_have_intake_fields(self, auth_token):
        """Test that all new services have intake_fields defined"""
        services_without_intake = []
        
        for code in NEW_SERVICE_CODES:
            response = requests.get(
                f"{BASE_URL}/api/admin/services/{code}",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            if response.status_code == 200:
                data = response.json()
                if not data.get("intake_fields") or len(data["intake_fields"]) == 0:
                    services_without_intake.append(code)
        
        assert len(services_without_intake) == 0, f"Services without intake_fields: {services_without_intake}"
        print(f"✓ All new services have intake_fields defined")
    
    def test_new_services_have_documents_generated(self, auth_token):
        """Test that all new services have documents_generated defined"""
        services_without_docs = []
        
        for code in NEW_SERVICE_CODES:
            response = requests.get(
                f"{BASE_URL}/api/admin/services/{code}",
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            if response.status_code == 200:
                data = response.json()
                if not data.get("documents_generated") or len(data["documents_generated"]) == 0:
                    services_without_docs.append(code)
        
        assert len(services_without_docs) == 0, f"Services without documents_generated: {services_without_docs}"
        print(f"✓ All new services have documents_generated defined")
    
    def test_service_categories_endpoint(self, auth_token):
        """Test that categories endpoint returns valid data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/services/categories",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "categories" in data
        assert "pricing_models" in data
        assert "delivery_types" in data
        assert "generation_modes" in data
        
        print(f"✓ Categories endpoint returns valid data")


class TestServiceDetails:
    """Test detailed service information"""
    
    @pytest.fixture
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@pleerity.com",
            "password": "Admin123!"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin authentication failed")
    
    def test_inventory_pro_service_details(self, auth_token):
        """Test INVENTORY_PRO service has correct details"""
        response = requests.get(
            f"{BASE_URL}/api/admin/services/INVENTORY_PRO",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["service_name"] == "Professional Property Inventory"
        assert data["price_amount"] == 19900
        assert len(data["intake_fields"]) >= 5
        assert len(data["documents_generated"]) >= 2
        
        print(f"✓ INVENTORY_PRO service has correct details")
    
    def test_due_diligence_service_details(self, auth_token):
        """Test DUE_DILIGENCE service has correct details"""
        response = requests.get(
            f"{BASE_URL}/api/admin/services/DUE_DILIGENCE",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["service_name"] == "Investment Due Diligence Report"
        assert data["price_amount"] == 49900
        assert len(data["intake_fields"]) >= 5
        assert len(data["documents_generated"]) >= 3
        
        print(f"✓ DUE_DILIGENCE service has correct details")
    
    def test_tenant_ref_service_details(self, auth_token):
        """Test TENANT_REF service has correct details"""
        response = requests.get(
            f"{BASE_URL}/api/admin/services/TENANT_REF",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["service_name"] == "Tenant Referencing Report"
        assert data["price_amount"] == 3500  # £35
        assert len(data["intake_fields"]) >= 6
        
        print(f"✓ TENANT_REF service has correct details")
    
    def test_portfolio_analysis_service_details(self, auth_token):
        """Test PORTFOLIO_ANALYSIS service has correct details"""
        response = requests.get(
            f"{BASE_URL}/api/admin/services/PORTFOLIO_ANALYSIS",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["service_name"] == "Portfolio Performance Analysis"
        assert data["price_amount"] == 39900  # £399
        assert len(data["documents_generated"]) >= 3
        
        print(f"✓ PORTFOLIO_ANALYSIS service has correct details")


class TestServiceSearch:
    """Test service search functionality"""
    
    @pytest.fixture
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@pleerity.com",
            "password": "Admin123!"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin authentication failed")
    
    def test_filter_by_standalone_report_category(self, auth_token):
        """Test filtering services by STANDALONE_REPORT category"""
        response = requests.get(
            f"{BASE_URL}/api/admin/services/?category=STANDALONE_REPORT",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        # All new services except none are STANDALONE_REPORT
        standalone_new_services = [
            "INVENTORY_PRO", "DUE_DILIGENCE", "RENT_REVIEW", "TENANT_REF",
            "EPC_CONSULT", "HMO_LICENCE_SUPPORT", "PORTFOLIO_ANALYSIS",
            "LEASE_EXTENSION", "AIRBNB_SETUP"
        ]
        
        service_codes = [s["service_code"] for s in data["services"]]
        found_count = sum(1 for code in standalone_new_services if code in service_codes)
        
        assert found_count == 9, f"Expected 9 new standalone services, found {found_count}"
        print(f"✓ Category filter returns correct services")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
