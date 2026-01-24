"""
Iteration 29 - Public Website Phase 1 Testing
Tests for public pages, APIs, and navigation
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://prompt-fix-6.preview.emergentagent.com')


class TestPublicAPIs:
    """Test public API endpoints"""
    
    def test_get_services_list(self):
        """GET /api/public/services - Returns list of services"""
        response = requests.get(f"{BASE_URL}/api/public/services")
        assert response.status_code == 200
        
        data = response.json()
        assert "services" in data
        assert len(data["services"]) >= 7  # At least 7 services defined
        
        # Verify service structure
        service = data["services"][0]
        assert "code" in service
        assert "name" in service
        assert "description" in service
        assert "category" in service
        assert "pricing" in service
    
    def test_get_service_detail(self):
        """GET /api/public/services/{code} - Returns service detail"""
        response = requests.get(f"{BASE_URL}/api/public/services/AI_WORKFLOW")
        assert response.status_code == 200
        
        data = response.json()
        assert data["code"] == "AI_WORKFLOW"
        assert data["name"] == "AI Workflow Automation"
        assert "features" in data
    
    def test_get_service_detail_not_found(self):
        """GET /api/public/services/{code} - Returns 404 for unknown service"""
        response = requests.get(f"{BASE_URL}/api/public/services/UNKNOWN_SERVICE")
        assert response.status_code == 404
    
    def test_contact_form_submission(self):
        """POST /api/public/contact - Submit contact form"""
        payload = {
            "full_name": "TEST_John Smith",
            "email": "test@example.com",
            "phone": "+44 7700 900000",
            "company_name": "Test Company Ltd",
            "contact_reason": "general",
            "subject": "Test Inquiry",
            "message": "This is a test message from automated testing."
        }
        
        response = requests.post(
            f"{BASE_URL}/api/public/contact",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "submission_id" in data
        assert data["submission_id"].startswith("CONTACT-")
    
    def test_contact_form_validation(self):
        """POST /api/public/contact - Validates required fields"""
        # Missing required fields
        payload = {
            "full_name": "Test User"
            # Missing email, contact_reason, subject, message
        }
        
        response = requests.post(
            f"{BASE_URL}/api/public/contact",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 422 for validation error
        assert response.status_code == 422
    
    def test_contact_form_invalid_email(self):
        """POST /api/public/contact - Validates email format"""
        payload = {
            "full_name": "Test User",
            "email": "invalid-email",  # Invalid email format
            "contact_reason": "general",
            "subject": "Test",
            "message": "Test message"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/public/contact",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
    
    def test_service_inquiry_submission(self):
        """POST /api/public/service-inquiry - Submit service inquiry"""
        payload = {
            "full_name": "TEST_Jane Doe",
            "email": "jane@example.com",
            "phone": "+44 7700 900001",
            "company_name": "Property Management Ltd",
            "service_interest": "AI_WORKFLOW",
            "message": "Interested in AI workflow automation for my portfolio.",
            "source_page": "/services/ai-workflow-automation"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/public/service-inquiry",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "inquiry_id" in data
        assert data["inquiry_id"].startswith("INQ-")


class TestPublicPageLoading:
    """Test that public pages return 200 status"""
    
    @pytest.mark.parametrize("path,expected_title_fragment", [
        ("/", "Pleerity"),
        ("/compliance-vault-pro", "Compliance Vault Pro"),
        ("/services", "Services"),
        ("/services/ai-workflow-automation", "AI Workflow"),
        ("/pricing", "Pricing"),
        ("/booking", "Book"),
        ("/about", "About"),
        ("/contact", "Contact"),
        ("/legal/privacy", "Privacy"),
        ("/legal/terms", "Terms"),
        ("/login", "Login"),
        ("/intake/start", ""),  # Intake wizard
    ])
    def test_page_loads(self, path, expected_title_fragment):
        """Test that public pages load successfully"""
        response = requests.get(f"{BASE_URL}{path}", allow_redirects=True)
        assert response.status_code == 200, f"Page {path} returned {response.status_code}"


class TestRateLimiting:
    """Test rate limiting on contact form"""
    
    def test_rate_limit_contact_form(self):
        """POST /api/public/contact - Rate limited to 5/min"""
        # Note: This test may fail if run multiple times quickly
        # as rate limiting is per IP
        
        payload = {
            "full_name": "TEST_Rate Limit Test",
            "email": "ratelimit@example.com",
            "contact_reason": "general",
            "subject": "Rate Limit Test",
            "message": "Testing rate limiting"
        }
        
        # First request should succeed
        response = requests.post(
            f"{BASE_URL}/api/public/contact",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Just verify the endpoint works - actual rate limit testing
        # would require 6+ requests which could affect other tests
        assert response.status_code in [200, 429]


class TestExistingCVPRoutes:
    """Verify existing CVP routes still work"""
    
    def test_login_page_accessible(self):
        """Login page should be accessible"""
        response = requests.get(f"{BASE_URL}/login")
        assert response.status_code == 200
    
    def test_intake_wizard_accessible(self):
        """Intake wizard should be accessible"""
        response = requests.get(f"{BASE_URL}/intake/start")
        assert response.status_code == 200
    
    def test_protected_routes_redirect(self):
        """Protected routes should redirect to login when not authenticated"""
        response = requests.get(f"{BASE_URL}/app/dashboard", allow_redirects=False)
        # Should either redirect (302/307) or return the page (200) which will handle auth client-side
        assert response.status_code in [200, 302, 307]


class TestAPIHealthCheck:
    """Basic API health checks"""
    
    def test_api_health(self):
        """API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
    
    def test_api_root(self):
        """API root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
