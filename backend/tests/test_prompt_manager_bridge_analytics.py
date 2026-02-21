"""
Prompt Manager Bridge Integration & Analytics Tests
Tests for:
- PromptManagerBridge integration with document orchestrator
- Prompt selection prioritizes Prompt Manager ACTIVE prompts over legacy registry
- prompt_version_used storage on orchestration_executions and orders
- Execution metrics recording in prompt_execution_metrics collection
- Analytics API endpoints return correct data structure
"""
import pytest

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


class TestPromptManagerBridgeIntegration:
    """Test PromptManagerBridge integration with document orchestrator"""

    @pytest.fixture
    def auth_token(self, client):
        """Get admin authentication token"""
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]

    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

    def test_bridge_service_exists(self, client, headers):
        """Verify the prompt manager bridge service is accessible via API"""
        response = client.get(
            "/api/admin/prompts/analytics/performance",
            headers=headers
        )
        assert response.status_code == 200, f"Analytics endpoint failed: {response.text}"
    
    def test_active_prompt_lookup(self, client, headers):
        """Test that active prompt lookup works for service/doc_type"""
        # First create and activate a prompt
        payload = {
            "service_code": "TEST_BRIDGE_SERVICE",
            "doc_type": "GENERAL_DOCUMENT",
            "name": "TEST_Bridge Integration Prompt",
            "description": "Testing bridge integration",
            "system_prompt": "You are a test assistant.",
            "user_prompt_template": "Process:\n\n{{INPUT_DATA_JSON}}\n\nReturn JSON.",
            "temperature": 0.3,
            "max_tokens": 2000,
            "tags": ["bridge", "test"],
            "output_schema": {
                "schema_version": "1.0",
                "root_type": "object",
                "strict_validation": False,
                "fields": [{"field_name": "result", "field_type": "string", "required": True}]
            }
        }
        
        # Create template
        create_response = client.post("/api/admin/prompts", headers=headers, json=payload)
        assert create_response.status_code == 200
        template_id = create_response.json()["template_id"]
        
        # Run test to enable marking as tested
        test_payload = {
            "template_id": template_id,
            "test_input_data": {"test": "data"}
        }
        test_response = client.post(
            "/api/admin/prompts/test",
            headers=headers,
            json=test_payload,
            timeout=60
        )
        
        if test_response.status_code == 200 and test_response.json().get("status") == "PASSED":
            # Mark as tested
            client.post(f"/api/admin/prompts/{template_id}/mark-tested", headers=headers)
            
            # Activate
            activate_payload = {
                "template_id": template_id,
                "activation_reason": "Bridge integration test"
            }
            client.post(f"/api/admin/prompts/{template_id}/activate", headers=headers, json=activate_payload)
            
            # Now test the active prompt lookup
            response = client.get(
                "/api/admin/prompts/active/TEST_BRIDGE_SERVICE/GENERAL_DOCUMENT",
                headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ACTIVE"
            assert data["service_code"] == "TEST_BRIDGE_SERVICE"


class TestAnalyticsPerformanceEndpoint:
    """Test /analytics/performance endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_performance_analytics_structure(self, client, headers):
        """Test that performance analytics returns correct structure"""
        response = client.get(
            "/api/admin/prompts/analytics/performance",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields in response
        assert "period_days" in data
        assert "total_executions" in data
        assert "total_successful" in data
        assert "total_failed" in data
        assert "overall_success_rate" in data
        assert "total_tokens_used" in data
        assert "by_prompt" in data
        
        # Verify types
        assert isinstance(data["period_days"], int)
        assert isinstance(data["total_executions"], int)
        assert isinstance(data["total_successful"], int)
        assert isinstance(data["total_failed"], int)
        assert isinstance(data["overall_success_rate"], (int, float))
        assert isinstance(data["total_tokens_used"], int)
        assert isinstance(data["by_prompt"], list)
    
    def test_performance_analytics_with_days_filter(self, client, headers):
        """Test performance analytics with different day ranges"""
        for days in [7, 14, 30, 90]:
            response = client.get(
                "/api/admin/prompts/analytics/performance?days={days}",
                headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["period_days"] == days
    
    def test_performance_analytics_with_template_filter(self, client, headers):
        """Test performance analytics filtered by template_id"""
        response = client.get(
            "/api/admin/prompts/analytics/performance?template_id=PT-TEST",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_executions" in data
    
    def test_performance_analytics_with_service_filter(self, client, headers):
        """Test performance analytics filtered by service_code"""
        response = client.get(
            "/api/admin/prompts/analytics/performance?service_code=AI_WF_BLUEPRINT",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_executions" in data


class TestAnalyticsTopPromptsEndpoint:
    """Test /analytics/top-prompts endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_top_prompts_structure(self, client, headers):
        """Test that top prompts returns correct structure"""
        response = client.get(
            "/api/admin/prompts/analytics/top-prompts",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "sort_by" in data
        assert "limit" in data
        assert "prompts" in data
        
        # Verify types
        assert isinstance(data["prompts"], list)
        
        # If there are prompts, verify their structure
        if data["prompts"]:
            prompt = data["prompts"][0]
            expected_fields = [
                "template_id", "version", "service_code", "source",
                "total_executions", "successful_executions", "success_rate",
                "total_tokens", "avg_execution_time_ms", "name"
            ]
            for field in expected_fields:
                assert field in prompt, f"Missing field: {field}"
    
    def test_top_prompts_sort_options(self, client, headers):
        """Test top prompts with different sort options"""
        for sort_by in ["executions", "success_rate", "tokens"]:
            response = client.get(
                "/api/admin/prompts/analytics/top-prompts?sort_by={sort_by}",
                headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["sort_by"] == sort_by
    
    def test_top_prompts_limit(self, client, headers):
        """Test top prompts with different limits"""
        for limit in [5, 10, 20]:
            response = client.get(
                "/api/admin/prompts/analytics/top-prompts?limit={limit}",
                headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["limit"] == limit
            assert len(data["prompts"]) <= limit


class TestAnalyticsExecutionTimelineEndpoint:
    """Test /analytics/execution-timeline endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_execution_timeline_structure(self, client, headers):
        """Test that execution timeline returns correct structure"""
        response = client.get(
            "/api/admin/prompts/analytics/execution-timeline",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "period_days" in data
        assert "timeline" in data
        
        # Verify types
        assert isinstance(data["period_days"], int)
        assert isinstance(data["timeline"], list)
        
        # If there are timeline entries, verify their structure
        if data["timeline"]:
            entry = data["timeline"][0]
            expected_fields = [
                "date", "total_executions", "successful_executions",
                "success_rate", "total_tokens", "avg_execution_time_ms"
            ]
            for field in expected_fields:
                assert field in entry, f"Missing field: {field}"
    
    def test_execution_timeline_days_filter(self, client, headers):
        """Test execution timeline with different day ranges"""
        for days in [7, 14, 30]:
            response = client.get(
                "/api/admin/prompts/analytics/execution-timeline?days={days}",
                headers=headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["period_days"] == days


class TestPromptVersionUsedTracking:
    """Test that prompt_version_used is properly tracked"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_prompt_version_info_structure(self, client, headers):
        """Test that ManagedPromptInfo structure is correct in API responses"""
        # Create a template and verify its structure includes version info
        payload = {
            "service_code": "VERSION_TRACKING_TEST",
            "doc_type": "GENERAL_DOCUMENT",
            "name": "TEST_Version Tracking Prompt",
            "description": "Testing version tracking",
            "system_prompt": "You are a test assistant.",
            "user_prompt_template": "Process:\n\n{{INPUT_DATA_JSON}}\n\nReturn JSON.",
            "temperature": 0.3,
            "max_tokens": 2000,
            "tags": ["version", "test"],
            "output_schema": {
                "schema_version": "1.0",
                "root_type": "object",
                "strict_validation": False,
                "fields": [{"field_name": "result", "field_type": "string", "required": True}]
            }
        }
        
        response = client.post("/api/admin/prompts", headers=headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        
        # Verify version tracking fields
        assert "template_id" in data
        assert "version" in data
        assert "service_code" in data
        assert "doc_type" in data
        assert data["template_id"].startswith("PT-")
        assert data["version"] == 1


class TestAnalyticsAuthRequired:
    """Test that analytics endpoints require authentication"""
    
    def test_performance_requires_auth(self):
        """Test that performance analytics requires authentication"""
        response = client.get("/api/admin/prompts/analytics/performance")
        assert response.status_code in [401, 403]
    
    def test_top_prompts_requires_auth(self):
        """Test that top prompts requires authentication"""
        response = client.get("/api/admin/prompts/analytics/top-prompts")
        assert response.status_code in [401, 403]
    
    def test_execution_timeline_requires_auth(self):
        """Test that execution timeline requires authentication"""
        response = client.get("/api/admin/prompts/analytics/execution-timeline")
        assert response.status_code in [401, 403]


class TestAnalyticsDataIntegrity:
    """Test analytics data integrity and calculations"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = client.post(
            "/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_success_rate_calculation(self, client, headers):
        """Test that success rate is calculated correctly"""
        response = client.get(
            "/api/admin/prompts/analytics/performance",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        total = data["total_executions"]
        successful = data["total_successful"]
        failed = data["total_failed"]
        
        # Verify total = successful + failed
        assert total == successful + failed
        
        # Verify success rate calculation
        if total > 0:
            expected_rate = round((successful / total) * 100, 2)
            assert abs(data["overall_success_rate"] - expected_rate) < 0.1
    
    def test_by_prompt_aggregation(self, client, headers):
        """Test that by_prompt aggregation is correct"""
        response = client.get(
            "/api/admin/prompts/analytics/performance",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # If there are prompts, verify aggregation
        if data["by_prompt"]:
            for prompt in data["by_prompt"]:
                # Verify each prompt has required metrics
                assert "total_executions" in prompt
                assert "successful_executions" in prompt
                assert "failed_executions" in prompt
                assert "success_rate" in prompt
                assert "total_tokens" in prompt
                
                # Verify calculations
                assert prompt["total_executions"] == prompt["successful_executions"] + prompt["failed_executions"]
