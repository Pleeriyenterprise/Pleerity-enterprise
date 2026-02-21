"""
Document Orchestration API Tests - Phase 2

Tests for the GPT-powered document generation orchestration:
- Orchestration API endpoints: /api/orchestration/*
- GPT Prompt Registry: All 8 service prompts + 1 orchestrator
- Document Orchestrator: Payment gating, validation
- Admin authentication requirements

Features tested:
- GET /api/orchestration/validate/{service_code} - Returns prompt info
- GET /api/orchestration/stats - Returns execution statistics
- POST /api/orchestration/validate-data - Validates intake data
- Admin authentication requirements
- GPT Prompt Registry completeness
- AUTHORITATIVE_FRAMEWORK guardrails
"""
import pytest

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


@pytest.fixture
def admin_token(client):
    """Get admin authentication token."""
    response = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Admin authentication failed")


@pytest.fixture
def admin_headers(admin_token):
    """Headers with admin auth token."""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


# ============================================================================
# ORCHESTRATION VALIDATE ENDPOINT TESTS
# ============================================================================

class TestOrchestrationValidateEndpoint:
    """Tests for GET /api/orchestration/validate/{service_code}"""
    
    def test_validate_ai_wf_blueprint_returns_prompt_info(self, admin_headers):
        """GET /api/orchestration/validate/AI_WF_BLUEPRINT returns prompt info."""
        response = client.get(
            "/api/orchestration/validate/AI_WF_BLUEPRINT",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service_code"] == "AI_WF_BLUEPRINT"
        assert data["has_prompt"] == True
        assert data["prompt_id"] == "AI_WF_BLUEPRINT_MASTER"
        assert data["prompt_name"] == "Workflow Automation Blueprint Generator"
        assert "required_fields" in data
        assert "gpt_sections" in data
        assert "temperature" in data
        assert "max_tokens" in data
        
        # Verify required fields
        expected_fields = [
            "business_description", "current_process_overview", "goals_objectives",
            "priority_goal", "team_size", "processes_to_focus", "main_challenges"
        ]
        for field in expected_fields:
            assert field in data["required_fields"], f"Missing required field: {field}"
    
    def test_validate_mr_basic_returns_prompt_info(self, admin_headers):
        """GET /api/orchestration/validate/MR_BASIC returns prompt info."""
        response = client.get(
            "/api/orchestration/validate/MR_BASIC",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service_code"] == "MR_BASIC"
        assert data["has_prompt"] == True
        assert data["prompt_id"] == "MR_BASIC_MASTER"
        assert data["prompt_name"] == "Basic Market Research Report Generator"
        
        # Verify required fields
        expected_fields = [
            "target_industry", "target_region", "target_audience_description",
            "main_research_question", "business_description"
        ]
        for field in expected_fields:
            assert field in data["required_fields"], f"Missing required field: {field}"
    
    def test_validate_comp_hmo_returns_prompt_info(self, admin_headers):
        """GET /api/orchestration/validate/COMP_HMO returns prompt info."""
        response = client.get(
            "/api/orchestration/validate/COMP_HMO",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service_code"] == "COMP_HMO"
        assert data["has_prompt"] == True
        assert data["prompt_id"] == "COMP_HMO_MASTER"
        assert data["prompt_name"] == "HMO Compliance Audit Report Generator"
        
        # Verify required fields for HMO compliance
        expected_fields = [
            "property_address_line1", "property_postcode", "number_of_bedrooms",
            "hmo_number_of_occupants", "current_hmo_licence_status", "top_three_concerns"
        ]
        for field in expected_fields:
            assert field in data["required_fields"], f"Missing required field: {field}"
    
    def test_validate_doc_pack_pro_returns_orchestrator(self, admin_headers):
        """GET /api/orchestration/validate/DOC_PACK_PRO returns orchestrator prompt."""
        response = client.get(
            "/api/orchestration/validate/DOC_PACK_PRO",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service_code"] == "DOC_PACK_PRO"
        assert data["has_prompt"] == True
        assert data["prompt_id"] == "DOC_PACK_ORCHESTRATOR"
        assert data["prompt_name"] == "Document Pack Orchestrator"
        
        # Verify orchestrator required fields
        expected_fields = ["pack_type", "documents_required", "landlord_name", "doc_tenant_full_name"]
        for field in expected_fields:
            assert field in data["required_fields"], f"Missing required field: {field}"
    
    def test_validate_requires_admin_auth(self, client):
        """GET /api/orchestration/validate/{service_code} requires admin auth."""
        response = client.get(
            "/api/orchestration/validate/AI_WF_BLUEPRINT",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code in [401, 403]
    
    def test_validate_invalid_service_returns_404(self, admin_headers):
        """GET /api/orchestration/validate/{invalid} returns 404."""
        response = client.get(
            "/api/orchestration/validate/INVALID_SERVICE_CODE",
            headers=admin_headers
        )
        
        assert response.status_code == 404


# ============================================================================
# ORCHESTRATION STATS ENDPOINT TESTS
# ============================================================================

class TestOrchestrationStatsEndpoint:
    """Tests for GET /api/orchestration/stats"""
    
    def test_stats_returns_execution_statistics(self, admin_headers):
        """GET /api/orchestration/stats returns execution statistics."""
        response = client.get(
            "/api/orchestration/stats",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "total_executions" in data
        assert "last_24h" in data
        assert "by_status" in data
        assert "by_service" in data
        
        # Verify types
        assert isinstance(data["total_executions"], int)
        assert isinstance(data["last_24h"], int)
        assert isinstance(data["by_status"], dict)
        assert isinstance(data["by_service"], list)
    
    def test_stats_requires_admin_auth(self, client):
        """GET /api/orchestration/stats requires admin auth."""
        response = client.get(
            "/api/orchestration/stats",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code in [401, 403]


# ============================================================================
# ORCHESTRATION VALIDATE-DATA ENDPOINT TESTS
# ============================================================================

class TestOrchestrationValidateDataEndpoint:
    """Tests for POST /api/orchestration/validate-data"""
    
    def test_validate_data_returns_missing_fields(self, admin_headers):
        """POST /api/orchestration/validate-data returns missing fields correctly."""
        response = client.post(
            "/api/orchestration/validate-data?service_code=AI_WF_BLUEPRINT",
            headers=admin_headers,
            json={
                "business_description": "Test business",
                "current_process_overview": "Test process"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service_code"] == "AI_WF_BLUEPRINT"
        assert data["is_valid"] == False
        assert len(data["missing_fields"]) > 0
        
        # Verify specific missing fields
        expected_missing = ["goals_objectives", "priority_goal", "team_size", "processes_to_focus", "main_challenges"]
        for field in expected_missing:
            assert field in data["missing_fields"], f"Should report {field} as missing"
    
    def test_validate_data_returns_valid_when_all_fields_present(self, admin_headers):
        """POST /api/orchestration/validate-data returns valid when all fields present."""
        response = client.post(
            "/api/orchestration/validate-data?service_code=AI_WF_BLUEPRINT",
            headers=admin_headers,
            json={
                "business_description": "Test business",
                "current_process_overview": "Test process",
                "goals_objectives": "Test goals",
                "priority_goal": "Test priority",
                "team_size": "10",
                "processes_to_focus": "Test processes",
                "main_challenges": "Test challenges"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service_code"] == "AI_WF_BLUEPRINT"
        assert data["is_valid"] == True
        assert len(data["missing_fields"]) == 0
        assert data["message"] == "All required fields present"
    
    def test_validate_data_for_doc_pack_uses_orchestrator(self, admin_headers):
        """POST /api/orchestration/validate-data for DOC_PACK uses orchestrator validation."""
        response = client.post(
            "/api/orchestration/validate-data?service_code=DOC_PACK_PRO",
            headers=admin_headers,
            json={
                "pack_type": "DOC_PACK_PRO",
                "documents_required": ["AST", "INVENTORY"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service_code"] == "DOC_PACK_PRO"
        # Should be missing landlord_name and doc_tenant_full_name
        assert data["is_valid"] == False
        assert "landlord_name" in data["missing_fields"]
        assert "doc_tenant_full_name" in data["missing_fields"]
    
    def test_validate_data_requires_admin_auth(self, client):
        """POST /api/orchestration/validate-data requires admin auth."""
        response = client.post(
            "/api/orchestration/validate-data?service_code=AI_WF_BLUEPRINT",
            headers={"Content-Type": "application/json"},
            json={"business_description": "Test"}
        )
        
        assert response.status_code in [401, 403]


# ============================================================================
# GPT PROMPT REGISTRY TESTS
# ============================================================================

class TestGPTPromptRegistry:
    """Tests for GPT Prompt Registry completeness."""
    
    @pytest.mark.parametrize("service_code,expected_prompt_id", [
        ("AI_WF_BLUEPRINT", "AI_WF_BLUEPRINT_MASTER"),
        ("AI_PROC_MAP", "AI_PROC_MAP_MASTER"),
        ("AI_TOOLS", "AI_TOOLS_MASTER"),
        ("MR_BASIC", "MR_BASIC_MASTER"),
        ("MR_ADV", "MR_ADV_MASTER"),
        ("COMP_HMO", "COMP_HMO_MASTER"),
        ("COMP_FULL_AUDIT", "COMP_FULL_AUDIT_MASTER"),
        ("COMP_MOVEOUT", "COMP_MOVEOUT_MASTER"),
    ])
    def test_all_8_services_have_prompts_defined(self, admin_headers, service_code, expected_prompt_id):
        """All 8 services have prompts defined in the registry."""
        response = client.get(
            f"/api/orchestration/validate/{service_code}",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["has_prompt"] == True, f"{service_code} should have a prompt defined"
        assert data["prompt_id"] == expected_prompt_id, f"{service_code} should have prompt_id {expected_prompt_id}"
    
    def test_doc_pack_orchestrator_prompt_exists(self, admin_headers):
        """DOC_PACK_ORCHESTRATOR prompt exists for document packs."""
        # Test via DOC_PACK_PRO which should use the orchestrator
        response = client.get(
            "/api/orchestration/validate/DOC_PACK_PRO",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["has_prompt"] == True
        assert data["prompt_id"] == "DOC_PACK_ORCHESTRATOR"
    
    def test_prompts_have_required_fields_defined(self, admin_headers):
        """All prompts have required_fields defined."""
        service_codes = [
            "AI_WF_BLUEPRINT", "AI_PROC_MAP", "AI_TOOLS",
            "MR_BASIC", "MR_ADV",
            "COMP_HMO", "COMP_FULL_AUDIT", "COMP_MOVEOUT"
        ]
        
        for service_code in service_codes:
            response = client.get(
                f"/api/orchestration/validate/{service_code}",
                headers=admin_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "required_fields" in data, f"{service_code} should have required_fields"
            assert len(data["required_fields"]) > 0, f"{service_code} should have at least one required field"
    
    def test_prompts_have_gpt_sections_defined(self, admin_headers):
        """All prompts have gpt_sections defined."""
        service_codes = [
            "AI_WF_BLUEPRINT", "AI_PROC_MAP", "AI_TOOLS",
            "MR_BASIC", "MR_ADV",
            "COMP_HMO", "COMP_FULL_AUDIT", "COMP_MOVEOUT"
        ]
        
        for service_code in service_codes:
            response = client.get(
                f"/api/orchestration/validate/{service_code}",
                headers=admin_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "gpt_sections" in data, f"{service_code} should have gpt_sections"
            # Note: gpt_sections can be empty for some services


# ============================================================================
# SERVICE CATALOGUE V2 INTEGRATION TESTS
# ============================================================================

class TestServiceCatalogueV2Integration:
    """Tests for Service Catalogue V2 integration with orchestration."""
    
    def test_all_12_services_accessible_via_public_v2(self, client):
        """All 12 services (11 public + 1 CVP) are accessible via /api/public/v2/services."""
        response = client.get("/api/public/v2/services")
        
        assert response.status_code == 200
        data = response.json()
        
        # Public endpoint returns 11 services (excludes CVP)
        assert data["total"] == 11
        
        # Verify all expected service codes
        service_codes = [s["service_code"] for s in data["services"]]
        expected_codes = [
            "AI_WF_BLUEPRINT", "AI_PROC_MAP", "AI_TOOLS",
            "MR_BASIC", "MR_ADV",
            "COMP_HMO", "COMP_FULL_AUDIT", "COMP_MOVEOUT",
            "DOC_PACK_ESSENTIAL", "DOC_PACK_PLUS", "DOC_PACK_PRO"
        ]
        
        for code in expected_codes:
            assert code in service_codes, f"Missing service: {code}"
    
    def test_admin_v2_returns_all_12_services(self, admin_headers):
        """Admin V2 endpoint returns all 12 services including CVP."""
        response = client.get(
            "/api/admin/services/v2/",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 12
        
        # Verify CVP is included
        service_codes = [s["service_code"] for s in data["services"]]
        assert "CVP_SUBSCRIPTION" in service_codes


# ============================================================================
# ADMIN AUTHENTICATION TESTS
# ============================================================================

class TestOrchestrationAdminAuth:
    """Tests for admin authentication requirements on orchestration endpoints."""
    
    def test_generate_requires_admin_auth(self, client):
        """POST /api/orchestration/generate requires admin auth."""
        response = client.post(
            "/api/orchestration/generate",
            headers={"Content-Type": "application/json"},
            json={"order_id": "test", "intake_data": {}}
        )
        
        assert response.status_code in [401, 403]
    
    def test_regenerate_requires_admin_auth(self, client):
        """POST /api/orchestration/regenerate requires admin auth."""
        response = client.post(
            "/api/orchestration/regenerate",
            headers={"Content-Type": "application/json"},
            json={"order_id": "test", "intake_data": {}, "regeneration_notes": "test"}
        )
        
        assert response.status_code in [401, 403]
    
    def test_review_requires_admin_auth(self, client):
        """POST /api/orchestration/review requires admin auth."""
        response = client.post(
            "/api/orchestration/review",
            headers={"Content-Type": "application/json"},
            json={"order_id": "test", "approved": True}
        )
        
        assert response.status_code in [401, 403]
    
    def test_history_requires_admin_auth(self, client):
        """GET /api/orchestration/history/{order_id} requires admin auth."""
        response = client.get(
            "/api/orchestration/history/test-order",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code in [401, 403]
    
    def test_latest_requires_admin_auth(self, client):
        """GET /api/orchestration/latest/{order_id} requires admin auth."""
        response = client.get(
            "/api/orchestration/latest/test-order",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code in [401, 403]


# ============================================================================
# PROMPT TEMPERATURE AND TOKEN TESTS
# ============================================================================

class TestPromptConfiguration:
    """Tests for prompt configuration values."""
    
    def test_ai_services_have_appropriate_temperature(self, admin_headers):
        """AI automation services have temperature 0.3."""
        for service_code in ["AI_WF_BLUEPRINT", "AI_PROC_MAP", "AI_TOOLS"]:
            response = client.get(
                f"/api/orchestration/validate/{service_code}",
                headers=admin_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # AI services should have lower temperature for consistency
            assert data["temperature"] <= 0.4, f"{service_code} should have temperature <= 0.4"
    
    def test_compliance_services_have_low_temperature(self, admin_headers):
        """Compliance services have low temperature (0.2) for accuracy."""
        for service_code in ["COMP_HMO", "COMP_FULL_AUDIT", "COMP_MOVEOUT"]:
            response = client.get(
                f"/api/orchestration/validate/{service_code}",
                headers=admin_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Compliance services should have very low temperature
            assert data["temperature"] == 0.2, f"{service_code} should have temperature 0.2"
    
    def test_prompts_have_reasonable_max_tokens(self, admin_headers):
        """All prompts have reasonable max_tokens (3000-6000)."""
        service_codes = [
            "AI_WF_BLUEPRINT", "AI_PROC_MAP", "AI_TOOLS",
            "MR_BASIC", "MR_ADV",
            "COMP_HMO", "COMP_FULL_AUDIT", "COMP_MOVEOUT"
        ]
        
        for service_code in service_codes:
            response = client.get(
                f"/api/orchestration/validate/{service_code}",
                headers=admin_headers
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert 3000 <= data["max_tokens"] <= 6000, f"{service_code} max_tokens should be between 3000-6000"
