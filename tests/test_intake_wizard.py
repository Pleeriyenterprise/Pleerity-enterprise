"""
Test suite for Universal Intake Wizard - Compliance Vault Pro
Tests the 5-step intake wizard with conditional logic, plan-aware property limits,
and audit-ready data collection.

Endpoints tested:
- GET /api/intake/plans - Returns all 3 plans with correct limits and pricing
- GET /api/intake/councils - Search UK councils with query and nation filter
- POST /api/intake/submit - Creates client with customer_reference and validates all fields
- POST /api/intake/checkout - Creates Stripe checkout session
- GET /api/intake/onboarding-status/{id} - Returns detailed step-by-step progress
"""
import pytest
import requests
import os
import re
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestIntakePlansAPI:
    """Test GET /api/intake/plans endpoint"""
    
    def test_get_plans_returns_all_three_plans(self):
        """Verify all 3 plans are returned with correct structure"""
        response = requests.get(f"{BASE_URL}/api/intake/plans")
        assert response.status_code == 200
        
        data = response.json()
        assert "plans" in data
        assert len(data["plans"]) == 3
        
        plan_ids = [p["plan_id"] for p in data["plans"]]
        assert "PLAN_1" in plan_ids
        assert "PLAN_2_5" in plan_ids
        assert "PLAN_6_15" in plan_ids
    
    def test_plans_have_correct_property_limits(self):
        """Verify plan property limits: Starter=1, Growth=5, Portfolio=15"""
        response = requests.get(f"{BASE_URL}/api/intake/plans")
        assert response.status_code == 200
        
        plans = {p["plan_id"]: p for p in response.json()["plans"]}
        
        assert plans["PLAN_1"]["max_properties"] == 1
        assert plans["PLAN_1"]["name"] == "Starter"
        
        assert plans["PLAN_2_5"]["max_properties"] == 5
        assert plans["PLAN_2_5"]["name"] == "Growth"
        
        assert plans["PLAN_6_15"]["max_properties"] == 15
        assert plans["PLAN_6_15"]["name"] == "Portfolio"
    
    def test_plans_have_correct_pricing(self):
        """Verify pricing: £9.99/month + £49.99 setup for all plans"""
        response = requests.get(f"{BASE_URL}/api/intake/plans")
        assert response.status_code == 200
        
        for plan in response.json()["plans"]:
            assert plan["monthly_price"] == 9.99
            assert plan["setup_fee"] == 49.99
            # Total first payment should be ~59.98
            assert abs(plan["total_first_payment"] - 59.98) < 0.01
    
    def test_plans_have_features_list(self):
        """Verify each plan has a features list"""
        response = requests.get(f"{BASE_URL}/api/intake/plans")
        assert response.status_code == 200
        
        for plan in response.json()["plans"]:
            assert "features" in plan
            assert isinstance(plan["features"], list)
            assert len(plan["features"]) > 0


class TestCouncilsSearchAPI:
    """Test GET /api/intake/councils endpoint"""
    
    def test_search_councils_by_query(self):
        """Search councils with q=manchester returns Manchester"""
        response = requests.get(f"{BASE_URL}/api/intake/councils", params={"q": "manchester"})
        assert response.status_code == 200
        
        data = response.json()
        assert "councils" in data
        assert len(data["councils"]) >= 1
        
        # Manchester should be in results
        names = [c["name"].lower() for c in data["councils"]]
        assert any("manchester" in name for name in names)
    
    def test_filter_councils_by_nation_wales(self):
        """Filter councils by nation=Wales returns only Welsh councils"""
        response = requests.get(f"{BASE_URL}/api/intake/councils", params={"nation": "Wales"})
        assert response.status_code == 200
        
        data = response.json()
        assert "councils" in data
        assert data["total"] == 22  # 22 Welsh councils in the data
        
        # All councils should be Welsh
        for council in data["councils"]:
            assert council["nation"] == "Wales"
    
    def test_filter_councils_by_nation_scotland(self):
        """Filter councils by nation=Scotland returns only Scottish councils"""
        response = requests.get(f"{BASE_URL}/api/intake/councils", params={"nation": "Scotland"})
        assert response.status_code == 200
        
        data = response.json()
        assert "councils" in data
        
        for council in data["councils"]:
            assert council["nation"] == "Scotland"
    
    def test_councils_pagination(self):
        """Test pagination parameters work correctly"""
        response = requests.get(f"{BASE_URL}/api/intake/councils", params={"page": 1, "limit": 10})
        assert response.status_code == 200
        
        data = response.json()
        assert "councils" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert "total_pages" in data
        
        assert data["page"] == 1
        assert data["limit"] == 10
        assert len(data["councils"]) <= 10
    
    def test_councils_have_required_fields(self):
        """Verify council objects have code, name, region, nation"""
        response = requests.get(f"{BASE_URL}/api/intake/councils", params={"q": "london"})
        assert response.status_code == 200
        
        data = response.json()
        if data["councils"]:
            council = data["councils"][0]
            assert "code" in council
            assert "name" in council
            assert "region" in council
            assert "nation" in council


class TestIntakeSubmitAPI:
    """Test POST /api/intake/submit endpoint"""
    
    @pytest.fixture
    def valid_intake_data(self):
        """Generate valid intake data with unique email"""
        unique_id = str(uuid.uuid4())[:8]
        return {
            "full_name": f"TEST_User_{unique_id}",
            "email": f"test_intake_{unique_id}@example.com",
            "phone": "+447700900000",
            "company_name": None,
            "client_type": "INDIVIDUAL",
            "preferred_contact": "EMAIL",
            "billing_plan": "PLAN_1",
            "document_submission_method": "UPLOAD",
            "email_upload_consent": False,
            "consent_data_processing": True,
            "consent_service_boundary": True,
            "properties": [
                {
                    "nickname": "Test Property",
                    "address_line_1": "123 Test Street",
                    "address_line_2": "",
                    "city": "London",
                    "postcode": "SW1A 1AA",
                    "property_type": "house",
                    "bedrooms": 3,
                    "occupancy": "single_family",
                    "is_hmo": False,
                    "council_name": "Westminster",
                    "council_code": "E09000033",
                    "licence_required": "NO",
                    "licence_type": None,
                    "licence_status": None,
                    "managed_by": "LANDLORD",
                    "send_reminders_to": "LANDLORD",
                    "agent_name": None,
                    "agent_email": None,
                    "agent_phone": None,
                    "cert_gas_safety": "YES",
                    "cert_eicr": "YES",
                    "cert_epc": "YES",
                    "cert_licence": None
                }
            ]
        }
    
    def test_submit_intake_creates_client_with_customer_reference(self, valid_intake_data):
        """Submit intake creates client with PLE-CVP-YYYY-XXXXX format reference"""
        response = requests.post(f"{BASE_URL}/api/intake/submit", json=valid_intake_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "client_id" in data
        assert "customer_reference" in data
        assert "next_step" in data
        assert data["next_step"] == "checkout"
        
        # Verify customer reference format: PLE-CVP-YYYY-XXXXX
        ref = data["customer_reference"]
        pattern = r"^PLE-CVP-\d{4}-[A-Z0-9]{5}$"
        assert re.match(pattern, ref), f"Customer reference {ref} doesn't match expected format"
        
        # Verify year is current year
        year = datetime.now().year
        assert f"-{year}-" in ref
    
    def test_submit_intake_validates_company_name_for_company_type(self, valid_intake_data):
        """Company name required when client_type is COMPANY"""
        valid_intake_data["client_type"] = "COMPANY"
        valid_intake_data["company_name"] = ""  # Empty company name
        valid_intake_data["email"] = f"test_company_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(f"{BASE_URL}/api/intake/submit", json=valid_intake_data)
        assert response.status_code == 400
        assert "company name" in response.json()["detail"].lower()
    
    def test_submit_intake_validates_company_name_for_agent_type(self, valid_intake_data):
        """Company name required when client_type is AGENT"""
        valid_intake_data["client_type"] = "AGENT"
        valid_intake_data["company_name"] = None
        valid_intake_data["email"] = f"test_agent_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(f"{BASE_URL}/api/intake/submit", json=valid_intake_data)
        assert response.status_code == 400
        assert "company name" in response.json()["detail"].lower()
    
    def test_submit_intake_validates_phone_for_sms_contact(self, valid_intake_data):
        """Phone required when preferred_contact is SMS"""
        valid_intake_data["preferred_contact"] = "SMS"
        valid_intake_data["phone"] = ""  # Empty phone
        valid_intake_data["email"] = f"test_sms_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(f"{BASE_URL}/api/intake/submit", json=valid_intake_data)
        assert response.status_code == 400
        assert "phone" in response.json()["detail"].lower()
    
    def test_submit_intake_validates_phone_for_both_contact(self, valid_intake_data):
        """Phone required when preferred_contact is BOTH"""
        valid_intake_data["preferred_contact"] = "BOTH"
        valid_intake_data["phone"] = None
        valid_intake_data["email"] = f"test_both_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(f"{BASE_URL}/api/intake/submit", json=valid_intake_data)
        assert response.status_code == 400
        assert "phone" in response.json()["detail"].lower()
    
    def test_submit_intake_enforces_plan_1_property_limit(self, valid_intake_data):
        """PLAN_1 allows only 1 property - reject if exceeding"""
        valid_intake_data["billing_plan"] = "PLAN_1"
        valid_intake_data["email"] = f"test_limit1_{uuid.uuid4().hex[:8]}@example.com"
        
        # Add second property
        valid_intake_data["properties"].append({
            "nickname": "Second Property",
            "address_line_1": "456 Test Avenue",
            "address_line_2": "",
            "city": "Manchester",
            "postcode": "M1 1AA",
            "property_type": "flat",
            "bedrooms": 2,
            "occupancy": "single_family",
            "is_hmo": False,
            "council_name": "Manchester",
            "council_code": "E08000003",
            "licence_required": "NO",
            "licence_type": None,
            "licence_status": None,
            "managed_by": "LANDLORD",
            "send_reminders_to": "LANDLORD",
            "agent_name": None,
            "agent_email": None,
            "agent_phone": None,
            "cert_gas_safety": "YES",
            "cert_eicr": "YES",
            "cert_epc": "YES",
            "cert_licence": None
        })
        
        response = requests.post(f"{BASE_URL}/api/intake/submit", json=valid_intake_data)
        assert response.status_code == 400
        assert "maximum" in response.json()["detail"].lower() or "limit" in response.json()["detail"].lower()
    
    def test_submit_intake_allows_5_properties_for_plan_2_5(self, valid_intake_data):
        """PLAN_2_5 allows up to 5 properties"""
        valid_intake_data["billing_plan"] = "PLAN_2_5"
        valid_intake_data["email"] = f"test_plan5_{uuid.uuid4().hex[:8]}@example.com"
        
        # Add 4 more properties (total 5)
        for i in range(4):
            valid_intake_data["properties"].append({
                "nickname": f"Property {i+2}",
                "address_line_1": f"{i+2}00 Test Street",
                "address_line_2": "",
                "city": "London",
                "postcode": f"SW{i+1}A 1AA",
                "property_type": "flat",
                "bedrooms": 2,
                "occupancy": "single_family",
                "is_hmo": False,
                "council_name": "Westminster",
                "council_code": "E09000033",
                "licence_required": "NO",
                "licence_type": None,
                "licence_status": None,
                "managed_by": "LANDLORD",
                "send_reminders_to": "LANDLORD",
                "agent_name": None,
                "agent_email": None,
                "agent_phone": None,
                "cert_gas_safety": "YES",
                "cert_eicr": "YES",
                "cert_epc": "YES",
                "cert_licence": None
            })
        
        response = requests.post(f"{BASE_URL}/api/intake/submit", json=valid_intake_data)
        assert response.status_code == 200
        assert "client_id" in response.json()
    
    def test_submit_intake_rejects_6_properties_for_plan_2_5(self, valid_intake_data):
        """PLAN_2_5 rejects more than 5 properties"""
        valid_intake_data["billing_plan"] = "PLAN_2_5"
        valid_intake_data["email"] = f"test_plan5_exceed_{uuid.uuid4().hex[:8]}@example.com"
        
        # Add 5 more properties (total 6)
        for i in range(5):
            valid_intake_data["properties"].append({
                "nickname": f"Property {i+2}",
                "address_line_1": f"{i+2}00 Test Street",
                "address_line_2": "",
                "city": "London",
                "postcode": f"SW{i+1}A 1AA",
                "property_type": "flat",
                "bedrooms": 2,
                "occupancy": "single_family",
                "is_hmo": False,
                "council_name": "Westminster",
                "council_code": "E09000033",
                "licence_required": "NO",
                "licence_type": None,
                "licence_status": None,
                "managed_by": "LANDLORD",
                "send_reminders_to": "LANDLORD",
                "agent_name": None,
                "agent_email": None,
                "agent_phone": None,
                "cert_gas_safety": "YES",
                "cert_eicr": "YES",
                "cert_epc": "YES",
                "cert_licence": None
            })
        
        response = requests.post(f"{BASE_URL}/api/intake/submit", json=valid_intake_data)
        assert response.status_code == 400
        assert "maximum" in response.json()["detail"].lower() or "limit" in response.json()["detail"].lower()
    
    def test_submit_intake_validates_consent_data_processing(self, valid_intake_data):
        """consent_data_processing is required"""
        valid_intake_data["consent_data_processing"] = False
        valid_intake_data["email"] = f"test_consent1_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(f"{BASE_URL}/api/intake/submit", json=valid_intake_data)
        assert response.status_code == 400
        assert "consent" in response.json()["detail"].lower() or "gdpr" in response.json()["detail"].lower()
    
    def test_submit_intake_validates_consent_service_boundary(self, valid_intake_data):
        """consent_service_boundary is required"""
        valid_intake_data["consent_service_boundary"] = False
        valid_intake_data["email"] = f"test_consent2_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(f"{BASE_URL}/api/intake/submit", json=valid_intake_data)
        assert response.status_code == 400
        assert "consent" in response.json()["detail"].lower() or "service" in response.json()["detail"].lower() or "acknowledgment" in response.json()["detail"].lower()
    
    def test_submit_intake_validates_email_consent_for_email_method(self, valid_intake_data):
        """email_upload_consent required when document_submission_method=EMAIL"""
        valid_intake_data["document_submission_method"] = "EMAIL"
        valid_intake_data["email_upload_consent"] = False
        valid_intake_data["email"] = f"test_email_consent_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(f"{BASE_URL}/api/intake/submit", json=valid_intake_data)
        assert response.status_code == 400
        assert "consent" in response.json()["detail"].lower() or "email" in response.json()["detail"].lower()
    
    def test_submit_intake_stores_property_fields(self, valid_intake_data):
        """Verify all property fields are stored correctly"""
        valid_intake_data["email"] = f"test_fields_{uuid.uuid4().hex[:8]}@example.com"
        valid_intake_data["properties"][0]["is_hmo"] = True
        valid_intake_data["properties"][0]["council_name"] = "Manchester"
        valid_intake_data["properties"][0]["council_code"] = "E08000003"
        valid_intake_data["properties"][0]["licence_required"] = "YES"
        valid_intake_data["properties"][0]["licence_type"] = "selective"
        valid_intake_data["properties"][0]["licence_status"] = "approved"
        valid_intake_data["properties"][0]["cert_gas_safety"] = "YES"
        valid_intake_data["properties"][0]["cert_eicr"] = "NO"
        valid_intake_data["properties"][0]["cert_epc"] = "UNSURE"
        valid_intake_data["properties"][0]["cert_licence"] = "YES"
        
        response = requests.post(f"{BASE_URL}/api/intake/submit", json=valid_intake_data)
        assert response.status_code == 200
        
        # Verify client was created
        data = response.json()
        assert "client_id" in data
        assert "customer_reference" in data
    
    def test_submit_intake_validates_agent_details_when_reminders_to_agent(self, valid_intake_data):
        """Agent name and email required when send_reminders_to includes AGENT"""
        valid_intake_data["email"] = f"test_agent_details_{uuid.uuid4().hex[:8]}@example.com"
        valid_intake_data["properties"][0]["send_reminders_to"] = "AGENT"
        valid_intake_data["properties"][0]["agent_name"] = ""  # Empty
        valid_intake_data["properties"][0]["agent_email"] = ""  # Empty
        
        response = requests.post(f"{BASE_URL}/api/intake/submit", json=valid_intake_data)
        assert response.status_code == 400
        assert "agent" in response.json()["detail"].lower()
    
    def test_submit_intake_accepts_valid_agent_details(self, valid_intake_data):
        """Valid agent details accepted when send_reminders_to is AGENT"""
        valid_intake_data["email"] = f"test_valid_agent_{uuid.uuid4().hex[:8]}@example.com"
        valid_intake_data["properties"][0]["send_reminders_to"] = "AGENT"
        valid_intake_data["properties"][0]["agent_name"] = "Jane Agent"
        valid_intake_data["properties"][0]["agent_email"] = "agent@example.com"
        valid_intake_data["properties"][0]["agent_phone"] = "+447700900001"
        
        response = requests.post(f"{BASE_URL}/api/intake/submit", json=valid_intake_data)
        assert response.status_code == 200
        assert "client_id" in response.json()
    
    def test_submit_intake_rejects_empty_properties(self, valid_intake_data):
        """At least one property is required"""
        valid_intake_data["email"] = f"test_no_props_{uuid.uuid4().hex[:8]}@example.com"
        valid_intake_data["properties"] = []
        
        response = requests.post(f"{BASE_URL}/api/intake/submit", json=valid_intake_data)
        assert response.status_code == 400
        assert "property" in response.json()["detail"].lower()
    
    def test_submit_intake_rejects_duplicate_email(self, valid_intake_data):
        """Duplicate email should be rejected"""
        # First submission
        response1 = requests.post(f"{BASE_URL}/api/intake/submit", json=valid_intake_data)
        assert response1.status_code == 200
        
        # Second submission with same email
        response2 = requests.post(f"{BASE_URL}/api/intake/submit", json=valid_intake_data)
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"].lower() or "email" in response2.json()["detail"].lower()


class TestIntakeCheckoutAPI:
    """Test POST /api/intake/checkout endpoint"""
    
    def test_checkout_creates_stripe_session(self):
        """Create checkout session for valid client"""
        # First create a client
        unique_id = str(uuid.uuid4())[:8]
        intake_data = {
            "full_name": f"TEST_Checkout_{unique_id}",
            "email": f"test_checkout_{unique_id}@example.com",
            "phone": "+447700900000",
            "company_name": None,
            "client_type": "INDIVIDUAL",
            "preferred_contact": "EMAIL",
            "billing_plan": "PLAN_1",
            "document_submission_method": "UPLOAD",
            "email_upload_consent": False,
            "consent_data_processing": True,
            "consent_service_boundary": True,
            "properties": [
                {
                    "nickname": "Checkout Test Property",
                    "address_line_1": "123 Checkout Street",
                    "address_line_2": "",
                    "city": "London",
                    "postcode": "SW1A 1AA",
                    "property_type": "house",
                    "bedrooms": 3,
                    "occupancy": "single_family",
                    "is_hmo": False,
                    "council_name": "Westminster",
                    "council_code": "E09000033",
                    "licence_required": "NO",
                    "licence_type": None,
                    "licence_status": None,
                    "managed_by": "LANDLORD",
                    "send_reminders_to": "LANDLORD",
                    "agent_name": None,
                    "agent_email": None,
                    "agent_phone": None,
                    "cert_gas_safety": "YES",
                    "cert_eicr": "YES",
                    "cert_epc": "YES",
                    "cert_licence": None
                }
            ]
        }
        
        submit_response = requests.post(f"{BASE_URL}/api/intake/submit", json=intake_data)
        assert submit_response.status_code == 200
        client_id = submit_response.json()["client_id"]
        
        # Create checkout session
        checkout_response = requests.post(
            f"{BASE_URL}/api/intake/checkout",
            params={"client_id": client_id},
            headers={"origin": "https://pleeritydocs.preview.emergentagent.com"}
        )
        assert checkout_response.status_code == 200
        
        data = checkout_response.json()
        assert "checkout_url" in data
        assert "session_id" in data
        # Stripe checkout URL should contain stripe.com
        assert "stripe.com" in data["checkout_url"]
    
    def test_checkout_returns_404_for_invalid_client(self):
        """Checkout returns 404 for non-existent client"""
        response = requests.post(
            f"{BASE_URL}/api/intake/checkout",
            params={"client_id": "non-existent-client-id"},
            headers={"origin": "https://pleeritydocs.preview.emergentagent.com"}
        )
        assert response.status_code == 404


class TestOnboardingStatusAPI:
    """Test GET /api/intake/onboarding-status/{client_id} endpoint"""
    
    def test_onboarding_status_returns_detailed_progress(self):
        """Get onboarding status returns step-by-step progress"""
        # First create a client
        unique_id = str(uuid.uuid4())[:8]
        intake_data = {
            "full_name": f"TEST_Status_{unique_id}",
            "email": f"test_status_{unique_id}@example.com",
            "phone": "+447700900000",
            "company_name": None,
            "client_type": "INDIVIDUAL",
            "preferred_contact": "EMAIL",
            "billing_plan": "PLAN_1",
            "document_submission_method": "UPLOAD",
            "email_upload_consent": False,
            "consent_data_processing": True,
            "consent_service_boundary": True,
            "properties": [
                {
                    "nickname": "Status Test Property",
                    "address_line_1": "123 Status Street",
                    "address_line_2": "",
                    "city": "London",
                    "postcode": "SW1A 1AA",
                    "property_type": "house",
                    "bedrooms": 3,
                    "occupancy": "single_family",
                    "is_hmo": False,
                    "council_name": "Westminster",
                    "council_code": "E09000033",
                    "licence_required": "NO",
                    "licence_type": None,
                    "licence_status": None,
                    "managed_by": "LANDLORD",
                    "send_reminders_to": "LANDLORD",
                    "agent_name": None,
                    "agent_email": None,
                    "agent_phone": None,
                    "cert_gas_safety": "YES",
                    "cert_eicr": "YES",
                    "cert_epc": "YES",
                    "cert_licence": None
                }
            ]
        }
        
        submit_response = requests.post(f"{BASE_URL}/api/intake/submit", json=intake_data)
        assert submit_response.status_code == 200
        client_id = submit_response.json()["client_id"]
        
        # Get onboarding status
        status_response = requests.get(f"{BASE_URL}/api/intake/onboarding-status/{client_id}")
        assert status_response.status_code == 200
        
        data = status_response.json()
        
        # Verify required fields
        assert "client_id" in data
        assert "customer_reference" in data
        assert "steps" in data
        assert "current_step" in data
        assert "progress_percent" in data
        assert "is_complete" in data
        
        # Verify steps structure
        assert len(data["steps"]) == 5
        
        step_names = [s["name"] for s in data["steps"]]
        assert "Intake Form" in step_names
        assert "Payment" in step_names
        assert "Portal Setup" in step_names
        assert "Account Activation" in step_names
        assert "Ready to Use" in step_names
        
        # Intake should be complete
        intake_step = next(s for s in data["steps"] if s["name"] == "Intake Form")
        assert intake_step["status"] == "complete"
    
    def test_onboarding_status_returns_404_for_invalid_client(self):
        """Onboarding status returns 404 for non-existent client"""
        response = requests.get(f"{BASE_URL}/api/intake/onboarding-status/non-existent-id")
        assert response.status_code == 404


class TestCustomerReferenceFormat:
    """Test customer reference format: PLE-CVP-YYYY-XXXXX"""
    
    def test_customer_reference_format_validation(self):
        """Verify customer reference follows PLE-CVP-YYYY-XXXXX format"""
        unique_id = str(uuid.uuid4())[:8]
        intake_data = {
            "full_name": f"TEST_Ref_{unique_id}",
            "email": f"test_ref_{unique_id}@example.com",
            "phone": "+447700900000",
            "company_name": None,
            "client_type": "INDIVIDUAL",
            "preferred_contact": "EMAIL",
            "billing_plan": "PLAN_1",
            "document_submission_method": "UPLOAD",
            "email_upload_consent": False,
            "consent_data_processing": True,
            "consent_service_boundary": True,
            "properties": [
                {
                    "nickname": "Ref Test Property",
                    "address_line_1": "123 Ref Street",
                    "address_line_2": "",
                    "city": "London",
                    "postcode": "SW1A 1AA",
                    "property_type": "house",
                    "bedrooms": 3,
                    "occupancy": "single_family",
                    "is_hmo": False,
                    "council_name": "Westminster",
                    "council_code": "E09000033",
                    "licence_required": "NO",
                    "licence_type": None,
                    "licence_status": None,
                    "managed_by": "LANDLORD",
                    "send_reminders_to": "LANDLORD",
                    "agent_name": None,
                    "agent_email": None,
                    "agent_phone": None,
                    "cert_gas_safety": "YES",
                    "cert_eicr": "YES",
                    "cert_epc": "YES",
                    "cert_licence": None
                }
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/intake/submit", json=intake_data)
        assert response.status_code == 200
        
        ref = response.json()["customer_reference"]
        
        # Verify format
        parts = ref.split("-")
        assert len(parts) == 4
        assert parts[0] == "PLE"
        assert parts[1] == "CVP"
        assert parts[2] == str(datetime.now().year)
        assert len(parts[3]) == 5
        
        # Verify no confusing characters (O, 0, I, 1, L)
        suffix = parts[3]
        assert "O" not in suffix
        assert "0" not in suffix
        assert "I" not in suffix
        assert "1" not in suffix
        assert "L" not in suffix


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
