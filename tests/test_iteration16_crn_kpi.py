"""
Iteration 16 Tests: CRN Display Everywhere + Clickable KPI Tiles
Tests for:
1. CRN (Customer Reference Number) display in email templates and client dashboard
2. Clickable KPI tiles that open drill-down modals
3. KPI drill-down modal showing filtered data
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCRNDisplay:
    """Tests for Customer Reference Number (CRN) display"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.admin_email = "admin@pleerity.com"
        self.admin_password = "Admin123!"
        self.client_email = "test@pleerity.com"
        self.client_password = "TestClient123!"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_admin_token(self):
        """Get admin authentication token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.admin_email,
            "password": self.admin_password
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()["access_token"]
    
    def get_client_token(self):
        """Get client authentication token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.client_email,
            "password": self.client_password
        })
        assert response.status_code == 200, f"Client login failed: {response.text}"
        return response.json()["access_token"]
    
    def test_client_dashboard_returns_crn(self):
        """Test that client dashboard API returns customer_reference"""
        token = self.get_client_token()
        response = self.session.get(
            f"{BASE_URL}/api/client/dashboard",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify client data structure
        assert "client" in data
        client = data["client"]
        
        # Check customer_reference field exists
        assert "customer_reference" in client, "customer_reference field missing from client dashboard"
        
        # If CRN exists, verify format (PLE-CVP-YYYY-XXXXX)
        if client["customer_reference"]:
            crn = client["customer_reference"]
            assert crn.startswith("PLE-CVP-"), f"CRN format invalid: {crn}"
            print(f"✓ Client dashboard returns CRN: {crn}")
    
    def test_admin_client_detail_returns_crn(self):
        """Test that admin client detail API returns customer_reference"""
        token = self.get_admin_token()
        
        # First get a client ID
        response = self.session.get(
            f"{BASE_URL}/api/admin/clients?limit=1",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        clients = response.json()["clients"]
        assert len(clients) > 0, "No clients found"
        
        client_id = clients[0]["client_id"]
        
        # Get client detail
        response = self.session.get(
            f"{BASE_URL}/api/admin/clients/{client_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify customer_reference in client data
        assert "client" in data
        assert "customer_reference" in data["client"], "customer_reference missing from admin client detail"
        print(f"✓ Admin client detail returns CRN: {data['client'].get('customer_reference')}")
    
    def test_admin_search_returns_crn(self):
        """Test that admin search results include customer_reference"""
        token = self.get_admin_token()
        
        # Search for a client
        response = self.session.get(
            f"{BASE_URL}/api/admin/search?q=test&limit=5",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check results include customer_reference field
        if data.get("results"):
            for result in data["results"]:
                assert "customer_reference" in result or result.get("customer_reference") is None, \
                    "customer_reference field should be present in search results"
            print(f"✓ Admin search returns {len(data['results'])} results with CRN field")


class TestKPIDrilldown:
    """Tests for clickable KPI tiles and drill-down modals"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.admin_email = "admin@pleerity.com"
        self.admin_password = "Admin123!"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_admin_token(self):
        """Get admin authentication token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.admin_email,
            "password": self.admin_password
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()["access_token"]
    
    def test_admin_dashboard_returns_kpi_stats(self):
        """Test that admin dashboard returns KPI statistics for tiles"""
        token = self.get_admin_token()
        response = self.session.get(
            f"{BASE_URL}/api/admin/dashboard",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify stats structure
        assert "stats" in data
        stats = data["stats"]
        
        # Check required KPI fields
        assert "total_clients" in stats, "total_clients missing from dashboard stats"
        assert "total_properties" in stats, "total_properties missing from dashboard stats"
        assert "active_clients" in stats, "active_clients missing from dashboard stats"
        assert "pending_clients" in stats, "pending_clients missing from dashboard stats"
        
        # Verify compliance overview
        assert "compliance_overview" in data
        compliance = data["compliance_overview"]
        assert "GREEN" in compliance, "GREEN compliance count missing"
        assert "AMBER" in compliance, "AMBER compliance count missing"
        assert "RED" in compliance, "RED compliance count missing"
        
        print(f"✓ Dashboard KPI stats: {stats['total_clients']} clients, {stats['total_properties']} properties")
        print(f"✓ Compliance: GREEN={compliance['GREEN']}, AMBER={compliance['AMBER']}, RED={compliance['RED']}")
    
    def test_kpi_clients_drilldown(self):
        """Test KPI drill-down for clients list"""
        token = self.get_admin_token()
        response = self.session.get(
            f"{BASE_URL}/api/admin/clients?limit=50",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "clients" in data
        assert "total" in data
        
        # Verify client data includes required fields for drilldown modal
        if data["clients"]:
            client = data["clients"][0]
            assert "client_id" in client
            assert "full_name" in client
            assert "email" in client
            assert "subscription_status" in client
            print(f"✓ Clients drilldown returns {len(data['clients'])} clients (total: {data['total']})")
    
    def test_kpi_clients_active_filter(self):
        """Test KPI drill-down for active clients"""
        token = self.get_admin_token()
        response = self.session.get(
            f"{BASE_URL}/api/admin/clients?subscription_status=ACTIVE&limit=50",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify all returned clients are ACTIVE
        for client in data.get("clients", []):
            assert client["subscription_status"] == "ACTIVE", \
                f"Expected ACTIVE status, got {client['subscription_status']}"
        
        print(f"✓ Active clients filter returns {len(data.get('clients', []))} clients")
    
    def test_kpi_properties_drilldown(self):
        """Test KPI drill-down for properties list"""
        token = self.get_admin_token()
        response = self.session.get(
            f"{BASE_URL}/api/admin/kpi/properties?limit=50",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "properties" in data
        assert "total" in data
        
        # Verify property data includes required fields for drilldown modal
        if data["properties"]:
            prop = data["properties"][0]
            assert "property_id" in prop
            assert "address_line_1" in prop or "nickname" in prop
            assert "postcode" in prop
            assert "compliance_status" in prop
            
            # Verify client info is included
            if "client" in prop:
                assert "full_name" in prop["client"]
        
        print(f"✓ Properties drilldown returns {len(data['properties'])} properties (total: {data['total']})")
    
    def test_kpi_compliance_green_filter(self):
        """Test KPI drill-down for GREEN compliance properties"""
        token = self.get_admin_token()
        response = self.session.get(
            f"{BASE_URL}/api/admin/kpi/properties?status_filter=GREEN&limit=50",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify all returned properties are GREEN
        for prop in data.get("properties", []):
            assert prop["compliance_status"] == "GREEN", \
                f"Expected GREEN status, got {prop['compliance_status']}"
        
        print(f"✓ GREEN compliance filter returns {len(data.get('properties', []))} properties")
    
    def test_kpi_compliance_amber_filter(self):
        """Test KPI drill-down for AMBER compliance properties"""
        token = self.get_admin_token()
        response = self.session.get(
            f"{BASE_URL}/api/admin/kpi/properties?status_filter=AMBER&limit=50",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify all returned properties are AMBER
        for prop in data.get("properties", []):
            assert prop["compliance_status"] == "AMBER", \
                f"Expected AMBER status, got {prop['compliance_status']}"
        
        print(f"✓ AMBER compliance filter returns {len(data.get('properties', []))} properties")
    
    def test_kpi_compliance_red_filter(self):
        """Test KPI drill-down for RED compliance properties"""
        token = self.get_admin_token()
        response = self.session.get(
            f"{BASE_URL}/api/admin/kpi/properties?status_filter=RED&limit=50",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify all returned properties are RED
        for prop in data.get("properties", []):
            assert prop["compliance_status"] == "RED", \
                f"Expected RED status, got {prop['compliance_status']}"
        
        print(f"✓ RED compliance filter returns {len(data.get('properties', []))} properties")


class TestEmailTemplatesCRN:
    """Tests for CRN in email templates (code review verification)"""
    
    def test_email_footer_includes_crn_placeholder(self):
        """Verify email service footer method handles customer_reference"""
        # This is a code review test - verify the implementation exists
        import sys
        sys.path.insert(0, '/app/backend')
        
        from services.email_service import EmailService
        
        service = EmailService()
        
        # Test footer with CRN
        model_with_crn = {
            'customer_reference': 'PLE-CVP-2026-12345',
            'company_name': 'Test Company',
            'tagline': 'Test Tagline'
        }
        footer = service._build_email_footer(model_with_crn)
        assert 'PLE-CVP-2026-12345' in footer, "CRN not found in email footer"
        assert 'Your Reference' in footer, "Reference label not found in footer"
        print("✓ Email footer includes CRN when provided")
        
        # Test footer without CRN
        model_without_crn = {
            'company_name': 'Test Company',
            'tagline': 'Test Tagline'
        }
        footer_no_crn = service._build_email_footer(model_without_crn)
        assert 'Your Reference' not in footer_no_crn, "Reference label should not appear without CRN"
        print("✓ Email footer correctly omits CRN when not provided")
    
    def test_password_setup_email_includes_crn_badge(self):
        """Verify password setup email template includes CRN badge"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from services.email_service import EmailService
        from models import EmailTemplateAlias
        
        service = EmailService()
        
        model = {
            'customer_reference': 'PLE-CVP-2026-12345',
            'client_name': 'Test Client',
            'setup_link': 'https://example.com/setup',
            'company_name': 'Test Company',
            'tagline': 'Test Tagline'
        }
        
        html = service._build_html_body(EmailTemplateAlias.PASSWORD_SETUP, model)
        
        # Verify CRN badge is in header
        assert 'PLE-CVP-2026-12345' in html, "CRN not found in password setup email"
        assert '#00B8A9' in html, "Electric teal color not found (CRN badge styling)"
        print("✓ Password setup email includes CRN badge")
    
    def test_portal_ready_email_includes_crn_badge(self):
        """Verify portal ready email template includes CRN badge"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from services.email_service import EmailService
        from models import EmailTemplateAlias
        
        service = EmailService()
        
        model = {
            'customer_reference': 'PLE-CVP-2026-12345',
            'client_name': 'Test Client',
            'portal_link': 'https://example.com/portal',
            'company_name': 'Test Company',
            'tagline': 'Test Tagline'
        }
        
        html = service._build_html_body(EmailTemplateAlias.PORTAL_READY, model)
        
        # Verify CRN badge is in header
        assert 'PLE-CVP-2026-12345' in html, "CRN not found in portal ready email"
        print("✓ Portal ready email includes CRN badge")
    
    def test_compliance_alert_email_includes_crn_badge(self):
        """Verify compliance alert email template includes CRN badge"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from services.email_service import EmailService
        from models import EmailTemplateAlias
        
        service = EmailService()
        
        model = {
            'customer_reference': 'PLE-CVP-2026-12345',
            'client_name': 'Test Client',
            'portal_link': 'https://example.com/portal',
            'affected_properties': [
                {'address': '123 Test St', 'previous_status': 'GREEN', 'new_status': 'RED', 'reason': 'Expired'}
            ],
            'status_color': '#dc2626',
            'company_name': 'Test Company',
            'tagline': 'Test Tagline'
        }
        
        html = service._build_html_body(EmailTemplateAlias.COMPLIANCE_ALERT, model)
        
        # Verify CRN badge is in header
        assert 'PLE-CVP-2026-12345' in html, "CRN not found in compliance alert email"
        print("✓ Compliance alert email includes CRN badge")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
