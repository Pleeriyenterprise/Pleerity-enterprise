"""
Test suite for Unified Intake Wizard API endpoints.
Tests: GET /api/intake/services, GET /api/intake/packs, GET /api/intake/schema/{service_code},
       POST /api/intake/draft, PUT /api/intake/draft/{draft_id}/client-identity
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestIntakeServices:
    """Test GET /api/intake/services endpoint"""
    
    def test_get_services_returns_200(self):
        """Services endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/intake/services")
        assert response.status_code == 200
    
    def test_get_services_returns_11_services(self):
        """Services endpoint returns all 11 services"""
        response = requests.get(f"{BASE_URL}/api/intake/services")
        data = response.json()
        assert "services" in data
        assert len(data["services"]) == 11
    
    def test_get_services_has_4_categories(self):
        """Services endpoint returns 4 categories"""
        response = requests.get(f"{BASE_URL}/api/intake/services")
        data = response.json()
        assert "categories" in data
        assert len(data["categories"]) == 4
        category_codes = [c["code"] for c in data["categories"]]
        assert "ai_automation" in category_codes
        assert "market_research" in category_codes
        assert "compliance" in category_codes
        assert "document_pack" in category_codes
    
    def test_services_have_required_fields(self):
        """Each service has required fields"""
        response = requests.get(f"{BASE_URL}/api/intake/services")
        data = response.json()
        for service in data["services"]:
            assert "service_code" in service
            assert "name" in service
            assert "category" in service
            assert "price_pence" in service
            assert "price_display" in service
            assert "description" in service
    
    def test_ai_automation_services(self):
        """AI & Automation category has 3 services"""
        response = requests.get(f"{BASE_URL}/api/intake/services")
        data = response.json()
        ai_services = [s for s in data["services"] if s["category"] == "ai_automation"]
        assert len(ai_services) == 3
        service_codes = [s["service_code"] for s in ai_services]
        assert "AI_WF_BLUEPRINT" in service_codes
        assert "AI_PROC_MAP" in service_codes
        assert "AI_TOOL_REPORT" in service_codes
    
    def test_market_research_services(self):
        """Market Research category has 2 services"""
        response = requests.get(f"{BASE_URL}/api/intake/services")
        data = response.json()
        mr_services = [s for s in data["services"] if s["category"] == "market_research"]
        assert len(mr_services) == 2
        service_codes = [s["service_code"] for s in mr_services]
        assert "MR_BASIC" in service_codes
        assert "MR_ADV" in service_codes
    
    def test_compliance_services(self):
        """Compliance Services category has 3 services"""
        response = requests.get(f"{BASE_URL}/api/intake/services")
        data = response.json()
        compliance_services = [s for s in data["services"] if s["category"] == "compliance"]
        assert len(compliance_services) == 3
        service_codes = [s["service_code"] for s in compliance_services]
        assert "HMO_AUDIT" in service_codes
        assert "FULL_AUDIT" in service_codes
        assert "MOVE_CHECKLIST" in service_codes
    
    def test_document_pack_services(self):
        """Document Packs category has 3 services"""
        response = requests.get(f"{BASE_URL}/api/intake/services")
        data = response.json()
        doc_services = [s for s in data["services"] if s["category"] == "document_pack"]
        assert len(doc_services) == 3
        service_codes = [s["service_code"] for s in doc_services]
        assert "DOC_PACK_ESSENTIAL" in service_codes
        assert "DOC_PACK_TENANCY" in service_codes
        assert "DOC_PACK_ULTIMATE" in service_codes


class TestIntakePacks:
    """Test GET /api/intake/packs endpoint"""
    
    def test_get_packs_returns_200(self):
        """Packs endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/intake/packs")
        assert response.status_code == 200
    
    def test_get_packs_returns_3_packs(self):
        """Packs endpoint returns 3 document packs"""
        response = requests.get(f"{BASE_URL}/api/intake/packs")
        data = response.json()
        assert "packs" in data
        assert len(data["packs"]) == 3
    
    def test_get_packs_returns_2_addons(self):
        """Packs endpoint returns 2 add-ons"""
        response = requests.get(f"{BASE_URL}/api/intake/packs")
        data = response.json()
        assert "addons" in data
        assert len(data["addons"]) == 2
    
    def test_fast_track_addon(self):
        """Fast Track add-on has correct properties"""
        response = requests.get(f"{BASE_URL}/api/intake/packs")
        data = response.json()
        fast_track = next((a for a in data["addons"] if a["addon_code"] == "FAST_TRACK"), None)
        assert fast_track is not None
        assert fast_track["price_pence"] == 2000
        assert fast_track["price_display"] == "£20.00"
        assert "effects" in fast_track
        assert fast_track["effects"]["priority"] == True
    
    def test_printed_copy_addon(self):
        """Printed Copy add-on has correct properties"""
        response = requests.get(f"{BASE_URL}/api/intake/packs")
        data = response.json()
        printed_copy = next((a for a in data["addons"] if a["addon_code"] == "PRINTED_COPY"), None)
        assert printed_copy is not None
        assert printed_copy["price_pence"] == 2500
        assert printed_copy["price_display"] == "£25.00"
        assert printed_copy["requires_postal_address"] == True


class TestIntakeSchema:
    """Test GET /api/intake/schema/{service_code} endpoint"""
    
    def test_get_schema_doc_pack_essential(self):
        """Schema endpoint returns schema for DOC_PACK_ESSENTIAL"""
        response = requests.get(f"{BASE_URL}/api/intake/schema/DOC_PACK_ESSENTIAL")
        assert response.status_code == 200
        data = response.json()
        assert data["service_code"] == "DOC_PACK_ESSENTIAL"
        assert data["supports_uploads"] == True
        assert data["supports_fast_track"] == True
        assert data["supports_printed_copy"] == True
        assert "fields" in data
        assert len(data["fields"]) > 0
    
    def test_get_schema_hmo_audit(self):
        """Schema endpoint returns schema for HMO_AUDIT"""
        response = requests.get(f"{BASE_URL}/api/intake/schema/HMO_AUDIT")
        assert response.status_code == 200
        data = response.json()
        assert data["service_code"] == "HMO_AUDIT"
        assert "fields" in data
    
    def test_get_schema_ai_wf_blueprint(self):
        """Schema endpoint returns schema for AI_WF_BLUEPRINT"""
        response = requests.get(f"{BASE_URL}/api/intake/schema/AI_WF_BLUEPRINT")
        assert response.status_code == 200
        data = response.json()
        assert data["service_code"] == "AI_WF_BLUEPRINT"
        assert "fields" in data
    
    def test_schema_has_client_identity_fields(self):
        """Schema includes client identity fields"""
        response = requests.get(f"{BASE_URL}/api/intake/schema/DOC_PACK_ESSENTIAL")
        data = response.json()
        field_keys = [f["field_key"] for f in data["fields"]]
        assert "full_name" in field_keys
        assert "email" in field_keys
        assert "phone" in field_keys
        assert "role" in field_keys
    
    def test_schema_invalid_service_code(self):
        """Schema endpoint returns 404 for invalid service code"""
        response = requests.get(f"{BASE_URL}/api/intake/schema/INVALID_SERVICE")
        assert response.status_code == 404


class TestIntakeDraft:
    """Test POST /api/intake/draft endpoint"""
    
    def test_create_draft_returns_200(self):
        """Create draft returns 200 OK"""
        response = requests.post(
            f"{BASE_URL}/api/intake/draft",
            json={"service_code": "DOC_PACK_ESSENTIAL", "category": "document_pack"}
        )
        assert response.status_code == 200
    
    def test_create_draft_returns_draft_id(self):
        """Create draft returns draft_id"""
        response = requests.post(
            f"{BASE_URL}/api/intake/draft",
            json={"service_code": "DOC_PACK_ESSENTIAL", "category": "document_pack"}
        )
        data = response.json()
        assert "draft_id" in data
        assert len(data["draft_id"]) > 0
    
    def test_create_draft_returns_draft_ref(self):
        """Create draft returns draft_ref in format INT-YYYYMMDD-####"""
        response = requests.post(
            f"{BASE_URL}/api/intake/draft",
            json={"service_code": "DOC_PACK_ESSENTIAL", "category": "document_pack"}
        )
        data = response.json()
        assert "draft_ref" in data
        assert data["draft_ref"].startswith("INT-")
        # Format: INT-YYYYMMDD-####
        parts = data["draft_ref"].split("-")
        assert len(parts) == 3
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 4  # ####
    
    def test_create_draft_has_pricing_snapshot(self):
        """Create draft includes pricing snapshot"""
        response = requests.post(
            f"{BASE_URL}/api/intake/draft",
            json={"service_code": "DOC_PACK_ESSENTIAL", "category": "document_pack"}
        )
        data = response.json()
        assert "pricing_snapshot" in data
        assert data["pricing_snapshot"]["base_price_pence"] == 2900
        assert data["pricing_snapshot"]["total_price_pence"] == 2900
    
    def test_create_draft_status_is_draft(self):
        """Create draft has status DRAFT"""
        response = requests.post(
            f"{BASE_URL}/api/intake/draft",
            json={"service_code": "DOC_PACK_ESSENTIAL", "category": "document_pack"}
        )
        data = response.json()
        assert data["status"] == "DRAFT"
    
    def test_create_draft_has_audit_log(self):
        """Create draft has audit log with DRAFT_CREATED action"""
        response = requests.post(
            f"{BASE_URL}/api/intake/draft",
            json={"service_code": "DOC_PACK_ESSENTIAL", "category": "document_pack"}
        )
        data = response.json()
        assert "audit_log" in data
        assert len(data["audit_log"]) > 0
        assert data["audit_log"][0]["action"] == "DRAFT_CREATED"


class TestClientIdentityUpdate:
    """Test PUT /api/intake/draft/{draft_id}/client-identity endpoint"""
    
    @pytest.fixture
    def draft_id(self):
        """Create a draft and return its ID"""
        response = requests.post(
            f"{BASE_URL}/api/intake/draft",
            json={"service_code": "DOC_PACK_ESSENTIAL", "category": "document_pack"}
        )
        return response.json()["draft_id"]
    
    def test_update_client_identity_returns_200(self, draft_id):
        """Update client identity returns 200 OK"""
        response = requests.put(
            f"{BASE_URL}/api/intake/draft/{draft_id}/client-identity",
            json={
                "full_name": "Test User",
                "email": "test@example.com",
                "phone": "+44 7123456789",
                "role": "Landlord"
            }
        )
        assert response.status_code == 200
    
    def test_update_client_identity_persists_data(self, draft_id):
        """Update client identity persists data correctly"""
        client_data = {
            "full_name": "John Smith",
            "email": "john@example.com",
            "phone": "+44 7987654321",
            "role": "Business Owner"
        }
        response = requests.put(
            f"{BASE_URL}/api/intake/draft/{draft_id}/client-identity",
            json=client_data
        )
        data = response.json()
        assert data["client_identity"]["full_name"] == "John Smith"
        assert data["client_identity"]["email"] == "john@example.com"
        assert data["client_identity"]["phone"] == "+44 7987654321"
        assert data["client_identity"]["role"] == "Business Owner"
    
    def test_update_client_identity_adds_audit_log(self, draft_id):
        """Update client identity adds audit log entry"""
        response = requests.put(
            f"{BASE_URL}/api/intake/draft/{draft_id}/client-identity",
            json={
                "full_name": "Test User",
                "email": "test@example.com",
                "phone": "+44 7123456789",
                "role": "Landlord"
            }
        )
        data = response.json()
        # Should have at least 2 audit entries (DRAFT_CREATED + DRAFT_UPDATED)
        assert len(data["audit_log"]) >= 2
        last_entry = data["audit_log"][-1]
        assert last_entry["action"] == "DRAFT_UPDATED"
        assert last_entry["details"]["step"] == "client_identity"
    
    def test_update_client_identity_invalid_draft_id(self):
        """Update client identity returns 404 for invalid draft ID"""
        response = requests.put(
            f"{BASE_URL}/api/intake/draft/invalid-draft-id/client-identity",
            json={
                "full_name": "Test User",
                "email": "test@example.com",
                "phone": "+44 7123456789",
                "role": "Landlord"
            }
        )
        assert response.status_code == 404


class TestCalculatePrice:
    """Test POST /api/intake/calculate-price endpoint"""
    
    def test_calculate_price_base_only(self):
        """Calculate price returns base price without add-ons"""
        response = requests.post(
            f"{BASE_URL}/api/intake/calculate-price",
            json={"service_code": "DOC_PACK_ESSENTIAL", "addons": []}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["base_price_pence"] == 2900
        assert data["total_price_pence"] == 2900
    
    def test_calculate_price_with_fast_track(self):
        """Calculate price includes Fast Track add-on"""
        response = requests.post(
            f"{BASE_URL}/api/intake/calculate-price",
            json={"service_code": "DOC_PACK_ESSENTIAL", "addons": ["FAST_TRACK"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["base_price_pence"] == 2900
        assert data["addon_total_pence"] == 2000
        assert data["total_price_pence"] == 4900
    
    def test_calculate_price_with_printed_copy(self):
        """Calculate price includes Printed Copy add-on"""
        response = requests.post(
            f"{BASE_URL}/api/intake/calculate-price",
            json={"service_code": "DOC_PACK_ESSENTIAL", "addons": ["PRINTED_COPY"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["base_price_pence"] == 2900
        assert data["addon_total_pence"] == 2500
        assert data["total_price_pence"] == 5400
    
    def test_calculate_price_with_both_addons(self):
        """Calculate price includes both add-ons"""
        response = requests.post(
            f"{BASE_URL}/api/intake/calculate-price",
            json={"service_code": "DOC_PACK_ESSENTIAL", "addons": ["FAST_TRACK", "PRINTED_COPY"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["base_price_pence"] == 2900
        assert data["addon_total_pence"] == 4500  # 2000 + 2500
        assert data["total_price_pence"] == 7400  # 2900 + 4500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
