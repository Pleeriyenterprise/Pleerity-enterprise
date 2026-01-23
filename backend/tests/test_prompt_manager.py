"""
Enterprise Prompt Manager API Tests
Tests for prompt template CRUD, testing, lifecycle, and audit log.

Features tested:
- Create/Read/Update/Delete prompt templates
- Prompt Playground (LLM test execution)
- Draft -> Tested -> Active lifecycle
- Schema validation
- Audit log
- Archive functionality
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


class TestPromptManagerAuth:
    """Test authentication for Prompt Manager endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]
    
    def test_endpoints_require_auth(self):
        """Verify all prompt manager endpoints require authentication"""
        endpoints = [
            ("GET", "/api/admin/prompts"),
            ("GET", "/api/admin/prompts/stats/overview"),
            ("GET", "/api/admin/prompts/audit/log"),
            ("GET", "/api/admin/prompts/reference/service-codes"),
            ("GET", "/api/admin/prompts/reference/doc-types"),
        ]
        
        for method, endpoint in endpoints:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}")
            assert response.status_code in [401, 403], f"{endpoint} should require auth"
    
    def test_admin_can_access(self, auth_token):
        """Verify admin can access prompt manager"""
        response = requests.get(
            f"{BASE_URL}/api/admin/prompts",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200


class TestPromptTemplatesCRUD:
    """Test CRUD operations for prompt templates"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_list_templates(self, headers):
        """Test listing prompt templates"""
        response = requests.get(f"{BASE_URL}/api/admin/prompts", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "prompts" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
    
    def test_get_stats_overview(self, headers):
        """Test getting stats overview"""
        response = requests.get(f"{BASE_URL}/api/admin/prompts/stats/overview", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_templates" in data
        assert "by_status" in data
        assert "tests_last_24h" in data
    
    def test_get_service_codes(self, headers):
        """Test getting service codes reference"""
        response = requests.get(f"{BASE_URL}/api/admin/prompts/reference/service-codes", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "service_codes" in data
        assert len(data["service_codes"]) > 0
    
    def test_get_doc_types(self, headers):
        """Test getting document types reference"""
        response = requests.get(f"{BASE_URL}/api/admin/prompts/reference/doc-types", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "doc_types" in data
        assert len(data["doc_types"]) > 0
    
    def test_create_template(self, headers):
        """Test creating a new prompt template"""
        payload = {
            "service_code": "RISK_ASSESSMENT",
            "doc_type": "GENERAL_DOCUMENT",
            "name": "TEST_Risk Assessment Prompt",
            "description": "Test prompt for risk assessment",
            "system_prompt": "You are a risk assessment expert. Analyze data and provide risk scores.",
            "user_prompt_template": "Analyze the following data for risks:\n\n{{INPUT_DATA_JSON}}\n\nProvide risk assessment as JSON.",
            "temperature": 0.3,
            "max_tokens": 4000,
            "tags": ["risk", "test"],
            "output_schema": {
                "schema_version": "1.0",
                "root_type": "object",
                "strict_validation": False,
                "fields": [
                    {"field_name": "risk_score", "field_type": "number", "required": True},
                    {"field_name": "findings", "field_type": "array", "required": True, "array_item_type": "string"}
                ]
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/admin/prompts", headers=headers, json=payload)
        assert response.status_code == 200, f"Create failed: {response.text}"
        
        data = response.json()
        assert data["template_id"].startswith("PT-")
        assert data["status"] == "DRAFT"
        assert data["version"] == 1
        assert data["name"] == payload["name"]
        assert "{{INPUT_DATA_JSON}}" in data["user_prompt_template"]
        
        return data["template_id"]
    
    def test_create_template_requires_injection_pattern(self, headers):
        """Test that template creation requires {{INPUT_DATA_JSON}} pattern"""
        payload = {
            "service_code": "RISK_ASSESSMENT",
            "doc_type": "GENERAL_DOCUMENT",
            "name": "TEST_Invalid Prompt",
            "description": "This should fail",
            "system_prompt": "You are an assistant.",
            "user_prompt_template": "Process this data: {data}",  # Missing {{INPUT_DATA_JSON}}
            "temperature": 0.3,
            "max_tokens": 4000,
            "tags": [],
            "output_schema": {
                "schema_version": "1.0",
                "root_type": "object",
                "strict_validation": False,
                "fields": []
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/admin/prompts", headers=headers, json=payload)
        assert response.status_code == 422, "Should reject template without {{INPUT_DATA_JSON}}"
    
    def test_get_template_by_id(self, headers):
        """Test getting a specific template by ID"""
        # First create a template
        payload = {
            "service_code": "DOCUMENT_ANALYSIS",
            "doc_type": "GENERAL_DOCUMENT",
            "name": "TEST_Get By ID Prompt",
            "description": "Test for get by ID",
            "system_prompt": "You are a document analyzer.",
            "user_prompt_template": "Analyze:\n\n{{INPUT_DATA_JSON}}\n\nReturn JSON.",
            "temperature": 0.3,
            "max_tokens": 4000,
            "tags": ["test"],
            "output_schema": {
                "schema_version": "1.0",
                "root_type": "object",
                "strict_validation": False,
                "fields": [{"field_name": "analysis", "field_type": "string", "required": True}]
            }
        }
        
        create_response = requests.post(f"{BASE_URL}/api/admin/prompts", headers=headers, json=payload)
        template_id = create_response.json()["template_id"]
        
        # Get by ID
        response = requests.get(f"{BASE_URL}/api/admin/prompts/{template_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["template_id"] == template_id
        assert data["name"] == payload["name"]
    
    def test_update_draft_template(self, headers):
        """Test updating a DRAFT template"""
        # Create template
        payload = {
            "service_code": "REPORT_GENERATION",
            "doc_type": "GENERAL_DOCUMENT",
            "name": "TEST_Update Draft Prompt",
            "description": "Original description",
            "system_prompt": "You are a report generator.",
            "user_prompt_template": "Generate report:\n\n{{INPUT_DATA_JSON}}\n\nReturn JSON.",
            "temperature": 0.3,
            "max_tokens": 4000,
            "tags": ["test"],
            "output_schema": {
                "schema_version": "1.0",
                "root_type": "object",
                "strict_validation": False,
                "fields": [{"field_name": "report", "field_type": "string", "required": True}]
            }
        }
        
        create_response = requests.post(f"{BASE_URL}/api/admin/prompts", headers=headers, json=payload)
        template_id = create_response.json()["template_id"]
        
        # Update
        update_payload = {
            "name": "TEST_Updated Draft Prompt",
            "description": "Updated description"
        }
        
        response = requests.put(f"{BASE_URL}/api/admin/prompts/{template_id}", headers=headers, json=update_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_payload["name"]
        assert data["description"] == update_payload["description"]
        assert data["version"] == 1  # DRAFT updates in place
    
    def test_list_with_filters(self, headers):
        """Test listing templates with filters"""
        # Filter by status
        response = requests.get(f"{BASE_URL}/api/admin/prompts?status=DRAFT", headers=headers)
        assert response.status_code == 200
        
        # Filter by service_code
        response = requests.get(f"{BASE_URL}/api/admin/prompts?service_code=COMPLIANCE_AUDIT", headers=headers)
        assert response.status_code == 200
        
        # Search
        response = requests.get(f"{BASE_URL}/api/admin/prompts?search=TEST_", headers=headers)
        assert response.status_code == 200


class TestPromptPlayground:
    """Test Prompt Playground (LLM test execution)"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def test_template(self, headers):
        """Create a template for testing"""
        payload = {
            "service_code": "DATA_EXTRACTION",
            "doc_type": "GENERAL_DOCUMENT",
            "name": "TEST_Playground Test Prompt",
            "description": "Template for playground testing",
            "system_prompt": "You are a data extraction assistant. Always return valid JSON.",
            "user_prompt_template": "Extract key information from:\n\n{{INPUT_DATA_JSON}}\n\nReturn JSON with 'extracted_data' field.",
            "temperature": 0.1,
            "max_tokens": 2000,
            "tags": ["test", "playground"],
            "output_schema": {
                "schema_version": "1.0",
                "root_type": "object",
                "strict_validation": False,
                "fields": [{"field_name": "extracted_data", "field_type": "string", "required": True}]
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/admin/prompts", headers=headers, json=payload)
        return response.json()
    
    def test_execute_test(self, headers, test_template):
        """Test executing a prompt test (calls LLM)"""
        payload = {
            "template_id": test_template["template_id"],
            "test_input_data": {
                "document_type": "invoice",
                "content": "Invoice #12345 from Acme Corp for $500"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/prompts/test",
            headers=headers,
            json=payload,
            timeout=60  # LLM calls can take time
        )
        assert response.status_code == 200, f"Test execution failed: {response.text}"
        
        data = response.json()
        assert data["test_id"].startswith("TEST-")
        assert data["template_id"] == test_template["template_id"]
        assert data["status"] in ["PASSED", "FAILED"]
        assert "rendered_user_prompt" in data
        assert "{{INPUT_DATA_JSON}}" not in data["rendered_user_prompt"]  # Should be replaced
        assert "execution_time_ms" in data
    
    def test_get_test_results(self, headers, test_template):
        """Test getting test results for a template"""
        response = requests.get(
            f"{BASE_URL}/api/admin/prompts/test/{test_template['template_id']}/results",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data


class TestPromptLifecycle:
    """Test Draft -> Tested -> Active lifecycle"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_full_lifecycle(self, headers):
        """Test complete lifecycle: Create -> Test -> Mark Tested -> Activate"""
        # 1. Create template
        payload = {
            "service_code": "AI_WF_BLUEPRINT",
            "doc_type": "GENERAL_DOCUMENT",
            "name": "TEST_Lifecycle Test Prompt",
            "description": "Testing full lifecycle",
            "system_prompt": "You are a workflow assistant. Return JSON.",
            "user_prompt_template": "Process:\n\n{{INPUT_DATA_JSON}}\n\nReturn JSON with 'result' field.",
            "temperature": 0.1,
            "max_tokens": 2000,
            "tags": ["lifecycle", "test"],
            "output_schema": {
                "schema_version": "1.0",
                "root_type": "object",
                "strict_validation": False,
                "fields": [{"field_name": "result", "field_type": "string", "required": True}]
            }
        }
        
        create_response = requests.post(f"{BASE_URL}/api/admin/prompts", headers=headers, json=payload)
        assert create_response.status_code == 200
        template = create_response.json()
        template_id = template["template_id"]
        assert template["status"] == "DRAFT"
        
        # 2. Run test (calls LLM)
        test_payload = {
            "template_id": template_id,
            "test_input_data": {"task": "test workflow"}
        }
        
        test_response = requests.post(
            f"{BASE_URL}/api/admin/prompts/test",
            headers=headers,
            json=test_payload,
            timeout=60
        )
        assert test_response.status_code == 200
        test_result = test_response.json()
        
        # 3. Mark as tested (only if test passed)
        if test_result["status"] == "PASSED":
            mark_response = requests.post(
                f"{BASE_URL}/api/admin/prompts/{template_id}/mark-tested",
                headers=headers
            )
            assert mark_response.status_code == 200
            
            # Verify status changed
            get_response = requests.get(f"{BASE_URL}/api/admin/prompts/{template_id}", headers=headers)
            assert get_response.json()["status"] == "TESTED"
            
            # 4. Activate
            activate_payload = {
                "template_id": template_id,
                "activation_reason": "Lifecycle test - validated and ready for production"
            }
            
            activate_response = requests.post(
                f"{BASE_URL}/api/admin/prompts/{template_id}/activate",
                headers=headers,
                json=activate_payload
            )
            assert activate_response.status_code == 200
            activate_data = activate_response.json()
            assert activate_data["success"] == True
            assert activate_data["status"] == "ACTIVE"
            
            # Verify final status
            final_response = requests.get(f"{BASE_URL}/api/admin/prompts/{template_id}", headers=headers)
            assert final_response.json()["status"] == "ACTIVE"
    
    def test_cannot_activate_without_test(self, headers):
        """Test that activation requires passing test"""
        # Create template
        payload = {
            "service_code": "REPORT_GENERATION",
            "doc_type": "GENERAL_DOCUMENT",
            "name": "TEST_No Test Activation",
            "description": "Should not activate without test",
            "system_prompt": "You are an assistant.",
            "user_prompt_template": "Process:\n\n{{INPUT_DATA_JSON}}\n\nReturn JSON.",
            "temperature": 0.3,
            "max_tokens": 2000,
            "tags": ["test"],
            "output_schema": {
                "schema_version": "1.0",
                "root_type": "object",
                "strict_validation": False,
                "fields": []
            }
        }
        
        create_response = requests.post(f"{BASE_URL}/api/admin/prompts", headers=headers, json=payload)
        template_id = create_response.json()["template_id"]
        
        # Try to mark as tested without running test
        mark_response = requests.post(
            f"{BASE_URL}/api/admin/prompts/{template_id}/mark-tested",
            headers=headers
        )
        assert mark_response.status_code == 400, "Should not mark as tested without passing test"


class TestAuditLog:
    """Test audit log functionality"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_get_audit_log(self, headers):
        """Test getting audit log entries"""
        response = requests.get(f"{BASE_URL}/api/admin/prompts/audit/log", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "total" in data
    
    def test_audit_log_has_required_fields(self, headers):
        """Test that audit log entries have required fields"""
        response = requests.get(f"{BASE_URL}/api/admin/prompts/audit/log?limit=5", headers=headers)
        data = response.json()
        
        if data["entries"]:
            entry = data["entries"][0]
            assert "audit_id" in entry
            assert "template_id" in entry
            assert "action" in entry
            assert "performed_by" in entry
            assert "performed_at" in entry
    
    def test_filter_audit_by_template(self, headers):
        """Test filtering audit log by template ID"""
        # First get a template ID
        list_response = requests.get(f"{BASE_URL}/api/admin/prompts", headers=headers)
        templates = list_response.json()["prompts"]
        
        if templates:
            template_id = templates[0]["template_id"]
            response = requests.get(
                f"{BASE_URL}/api/admin/prompts/audit/log?template_id={template_id}",
                headers=headers
            )
            assert response.status_code == 200


class TestArchiveTemplate:
    """Test archive functionality"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_archive_draft_template(self, headers):
        """Test archiving a DRAFT template"""
        # Create template
        payload = {
            "service_code": "DATA_EXTRACTION",
            "doc_type": "GENERAL_DOCUMENT",
            "name": "TEST_Archive Me",
            "description": "This will be archived",
            "system_prompt": "You are an assistant.",
            "user_prompt_template": "Process:\n\n{{INPUT_DATA_JSON}}\n\nReturn JSON.",
            "temperature": 0.3,
            "max_tokens": 2000,
            "tags": ["archive", "test"],
            "output_schema": {
                "schema_version": "1.0",
                "root_type": "object",
                "strict_validation": False,
                "fields": []
            }
        }
        
        create_response = requests.post(f"{BASE_URL}/api/admin/prompts", headers=headers, json=payload)
        template_id = create_response.json()["template_id"]
        
        # Archive
        response = requests.delete(f"{BASE_URL}/api/admin/prompts/{template_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True


# Cleanup fixture to remove TEST_ prefixed templates
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    """Cleanup TEST_ prefixed templates after all tests"""
    yield
    # Cleanup would go here if needed
    # For now, we leave test data for audit trail purposes
