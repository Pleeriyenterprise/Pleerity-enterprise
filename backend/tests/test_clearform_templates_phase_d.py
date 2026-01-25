"""
ClearForm Phase D Templates API Tests
Tests for system templates, rule packs, and Smart Profile pre-fill functionality.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://paperwork-assist-1.preview.emergentagent.com')

# Test credentials
TEST_USER_EMAIL = "demo2@clearform.com"
TEST_USER_PASSWORD = "DemoPass123!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for ClearForm user."""
    response = requests.post(
        f"{BASE_URL}/api/clearform/auth/login",
        json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestSystemTemplatesAPI:
    """Tests for GET /api/clearform/templates/system endpoint."""
    
    def test_get_all_system_templates(self, auth_headers):
        """Test fetching all system templates."""
        response = requests.get(
            f"{BASE_URL}/api/clearform/templates/system",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "templates" in data
        assert "total" in data
        assert isinstance(data["templates"], list)
        assert data["total"] >= 1
        
        # Verify template structure
        if data["templates"]:
            template = data["templates"][0]
            assert "template_id" in template
            assert "name" in template
            assert "description" in template
            assert "document_type" in template
            assert "generation_mode" in template
            assert "credit_cost" in template
            assert "has_rule_pack" in template
    
    def test_get_templates_filtered_by_document_type(self, auth_headers):
        """Test filtering templates by document type."""
        response = requests.get(
            f"{BASE_URL}/api/clearform/templates/system?document_type=complaint_letter",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # All returned templates should be for complaint_letter
        for template in data["templates"]:
            assert template["document_type"] == "complaint_letter"
    
    def test_get_templates_for_formal_letter(self, auth_headers):
        """Test getting templates for formal letter type."""
        response = requests.get(
            f"{BASE_URL}/api/clearform/templates/system?document_type=formal_letter",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should have at least one formal letter template
        assert data["total"] >= 1
        for template in data["templates"]:
            assert template["document_type"] == "formal_letter"


class TestTemplatePreFillAPI:
    """Tests for POST /api/clearform/templates/system/prefill endpoint."""
    
    def test_prefill_complaint_template(self, auth_headers):
        """Test getting prefilled template data."""
        response = requests.post(
            f"{BASE_URL}/api/clearform/templates/system/prefill",
            headers=auth_headers,
            json={"template_id": "TPL-COMPLAINT-01"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["template_id"] == "TPL-COMPLAINT-01"
        assert "template_name" in data
        assert "description" in data
        assert "document_type" in data
        assert "generation_mode" in data
        assert "credit_cost" in data
        assert "sections" in data
        
        # Verify sections structure
        assert isinstance(data["sections"], list)
        assert len(data["sections"]) > 0
        
        for section in data["sections"]:
            assert "section_id" in section
            assert "section_type" in section
            assert "name" in section
            assert "order" in section
            assert "placeholders" in section
            
            # Verify placeholders structure
            for placeholder in section["placeholders"]:
                assert "key" in placeholder
                assert "label" in placeholder
                assert "field_type" in placeholder
                assert "required" in placeholder
    
    def test_prefill_formal_letter_template(self, auth_headers):
        """Test getting prefilled formal letter template."""
        response = requests.post(
            f"{BASE_URL}/api/clearform/templates/system/prefill",
            headers=auth_headers,
            json={"template_id": "TPL-FORMAL-01"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["template_id"] == "TPL-FORMAL-01"
        assert data["document_type"] == "formal_letter"
    
    def test_prefill_invalid_template(self, auth_headers):
        """Test prefill with invalid template ID."""
        response = requests.post(
            f"{BASE_URL}/api/clearform/templates/system/prefill",
            headers=auth_headers,
            json={"template_id": "INVALID-TEMPLATE"}
        )
        assert response.status_code == 404


class TestSmartProfilesAPI:
    """Tests for GET /api/clearform/templates/profiles endpoint."""
    
    def test_get_profiles(self, auth_headers):
        """Test fetching user's smart profiles."""
        response = requests.get(
            f"{BASE_URL}/api/clearform/templates/profiles",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "profiles" in data
        assert "total" in data
        assert isinstance(data["profiles"], list)


class TestRulePacksAPI:
    """Tests for rule packs endpoints."""
    
    def test_get_all_rule_packs(self, auth_headers):
        """Test fetching all rule packs."""
        response = requests.get(
            f"{BASE_URL}/api/clearform/templates/rule-packs",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "rule_packs" in data
        assert "total" in data
        assert data["total"] >= 1
        
        # Verify rule pack structure
        if data["rule_packs"]:
            pack = data["rule_packs"][0]
            assert "pack_id" in pack
            assert "name" in pack
            assert "description" in pack
            assert "category" in pack
            assert "document_types" in pack
            assert "compliance_standard" in pack
            assert "section_count" in pack
            assert "rule_count" in pack
    
    def test_get_rule_packs_filtered(self, auth_headers):
        """Test filtering rule packs by document type."""
        response = requests.get(
            f"{BASE_URL}/api/clearform/templates/rule-packs?document_type=complaint_letter",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # All returned packs should support complaint_letter
        for pack in data["rule_packs"]:
            assert "complaint_letter" in pack["document_types"]
    
    def test_get_rule_pack_details(self, auth_headers):
        """Test getting specific rule pack details."""
        response = requests.get(
            f"{BASE_URL}/api/clearform/templates/rule-packs/RP-COMPLAINT-01",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify detailed structure
        assert data["pack_id"] == "RP-COMPLAINT-01"
        assert "required_sections" in data
        assert "validation_rules" in data
        assert isinstance(data["required_sections"], list)
        assert isinstance(data["validation_rules"], list)


class TestDocumentTypesAPI:
    """Tests for document types endpoint."""
    
    def test_get_document_types(self, auth_headers):
        """Test fetching document types."""
        response = requests.get(
            f"{BASE_URL}/api/clearform/documents/types",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return list of document types
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Verify document type structure
        for doc_type in data:
            assert "type" in doc_type
            assert "name" in doc_type
            assert "description" in doc_type
            assert "credit_cost" in doc_type


class TestMarketingPages:
    """Tests for marketing website pages."""
    
    def test_homepage_loads(self):
        """Test homepage returns 200."""
        response = requests.get(f"{BASE_URL}/")
        assert response.status_code == 200
    
    def test_about_page_loads(self):
        """Test about page returns 200."""
        response = requests.get(f"{BASE_URL}/about")
        assert response.status_code == 200
    
    def test_services_page_loads(self):
        """Test services page returns 200."""
        response = requests.get(f"{BASE_URL}/services")
        assert response.status_code == 200
    
    def test_pricing_page_loads(self):
        """Test pricing page returns 200."""
        response = requests.get(f"{BASE_URL}/pricing")
        assert response.status_code == 200
    
    def test_contact_page_loads(self):
        """Test contact page returns 200."""
        response = requests.get(f"{BASE_URL}/contact")
        assert response.status_code == 200


class TestDocumentPackServices:
    """Tests for Document Pack services."""
    
    def test_get_document_pack_services(self):
        """Test fetching document pack services."""
        response = requests.get(f"{BASE_URL}/api/public/v2/services?category=document_pack")
        assert response.status_code == 200
        data = response.json()
        
        assert "services" in data
        assert len(data["services"]) >= 1
        
        # Verify document pack structure
        for service in data["services"]:
            assert service["category"] == "document_pack"
            assert "service_code" in service
            assert "service_name" in service
            assert "base_price" in service
    
    def test_get_essential_pack_details(self):
        """Test getting Essential pack details."""
        response = requests.get(f"{BASE_URL}/api/public/v2/services/DOC_PACK_ESSENTIAL")
        assert response.status_code == 200
        data = response.json()
        
        assert data["service_code"] == "DOC_PACK_ESSENTIAL"
        assert data["category"] == "document_pack"


class TestIntakeWizardServices:
    """Tests for intake wizard service endpoints."""
    
    def test_get_all_services(self):
        """Test fetching all services for intake wizard."""
        response = requests.get(f"{BASE_URL}/api/public/v2/services")
        assert response.status_code == 200
        data = response.json()
        
        assert "services" in data
        assert len(data["services"]) >= 1
    
    def test_get_intake_schema(self):
        """Test getting intake schema for a service."""
        response = requests.get(f"{BASE_URL}/api/public/v2/services/DOC_PACK_ESSENTIAL/intake-schema")
        # May return 200 or 404 depending on schema availability
        assert response.status_code in [200, 404]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
