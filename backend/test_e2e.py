"""
End-to-End Production Testing Script
Compliance Vault Pro - Complete Flow Verification

Tests the entire user journey from intake to dashboard access.
"""
import asyncio
import requests
import json
from datetime import datetime
import sys

API_URL = "https://paperwork-assist-1.preview.emergentagent.com/api"

class E2ETestSuite:
    def __init__(self):
        self.test_email = f"test_{int(datetime.now().timestamp())}@pleerity.com"
        self.client_id = None
        self.auth_token = None
        self.passed = 0
        self.failed = 0
    
    def log_test(self, name, passed, detail=""):
        if passed:
            self.passed += 1
            print(f"✅ {name}")
            if detail:
                print(f"   {detail}")
        else:
            self.failed += 1
            print(f"❌ {name}")
            if detail:
                print(f"   {detail}")
    
    def test_1_health_check(self):
        """Test 1: API Health Check"""
        print("\n📋 Test 1: API Health Check\n")
        
        try:
            response = requests.get(f"{API_URL}/health", timeout=5)
            self.log_test(
                "API is accessible",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            data = response.json()
            self.log_test(
                "Health endpoint returns correct data",
                "status" in data and data["status"] == "healthy"
            )
        except Exception as e:
            self.log_test("API health check", False, str(e))
    
    def test_2_intake_submission(self):
        """Test 2: Intake Form Submission"""
        print("\n📋 Test 2: Intake Form Submission\n")
        
        intake_data = {
            "full_name": "Test User E2E",
            "email": self.test_email,
            "phone": "+44 7700 900000",
            "client_type": "INDIVIDUAL",
            "preferred_contact": "EMAIL",
            "billing_plan": "PLAN_1",
            "properties": [
                {
                    "address_line_1": "123 Test Street",
                    "city": "London",
                    "postcode": "SW1A 1AA",
                    "property_type": "residential",
                    "number_of_units": 1
                }
            ],
            "consent_data_processing": True,
            "consent_communications": True
        }
        
        try:
            response = requests.post(
                f"{API_URL}/intake/submit",
                json=intake_data,
                timeout=10
            )
            
            self.log_test(
                "Intake form accepts valid data",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            if response.status_code == 200:
                data = response.json()
                self.client_id = data.get("client_id")
                self.log_test(
                    "Client ID returned",
                    self.client_id is not None,
                    f"Client ID: {self.client_id}"
                )
            else:
                print(f"   Error: {response.text}")
        except Exception as e:
            self.log_test("Intake submission", False, str(e))
    
    def test_3_onboarding_status(self):
        """Test 3: Onboarding Status Check"""
        print("\n📋 Test 3: Onboarding Status Check\n")
        
        if not self.client_id:
            print("⚠️  Skipped: No client_id from previous test\n")
            return
        
        try:
            response = requests.get(
                f"{API_URL}/intake/onboarding-status/{self.client_id}",
                timeout=5
            )
            
            self.log_test(
                "Onboarding status endpoint accessible",
                response.status_code == 200
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "Onboarding status is INTAKE_PENDING",
                    data.get("onboarding_status") == "INTAKE_PENDING"
                )
                self.log_test(
                    "Subscription status is PENDING",
                    data.get("subscription_status") == "PENDING"
                )
        except Exception as e:
            self.log_test("Onboarding status check", False, str(e))
    
    def test_4_admin_login(self):
        """Test 4: Admin Login"""
        print("\n📋 Test 4: Admin Authentication\n")
        
        admin_credentials = {
            "email": "admin@pleerity.com",
            "password": "Admin123!"
        }
        
        try:
            response = requests.post(
                f"{API_URL}/auth/admin/login",
                json=admin_credentials,
                timeout=5
            )
            
            self.log_test(
                "Admin can authenticate",
                response.status_code == 200,
                f"Status: {response.status_code}"
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log_test(
                    "Admin receives JWT token",
                    "access_token" in data and len(data["access_token"]) > 0
                )
                self.log_test(
                    "Admin role verified",
                    data.get("user", {}).get("role") == "ROLE_ADMIN"
                )
        except Exception as e:
            self.log_test("Admin authentication", False, str(e))
    
    def test_5_route_guards(self):
        """Test 5: Route Guard Enforcement"""
        print("\n📋 Test 5: Route Guard Enforcement\n")
        
        # Test unauthenticated access
        try:
            response = requests.get(
                f"{API_URL}/client/dashboard",
                timeout=5
            )
            
            self.log_test(
                "Unauthenticated requests blocked",
                response.status_code == 401,
                f"Status: {response.status_code}"
            )
        except Exception as e:
            self.log_test("Route guard test", False, str(e))
        
        # Test admin-only endpoint without admin token
        try:
            response = requests.get(
                f"{API_URL}/admin/clients",
                headers={"Authorization": "Bearer invalid_token"},
                timeout=5
            )
            
            self.log_test(
                "Invalid tokens rejected",
                response.status_code in [401, 403],
                f"Status: {response.status_code}"
            )
        except Exception as e:
            self.log_test("Admin route guard test", False, str(e))
    
    def test_6_document_routes(self):
        """Test 6: Document Routes Exist"""
        print("\n📋 Test 6: Document Management\n")
        
        # Test that document routes are registered (will fail auth but route exists)
        try:
            response = requests.post(
                f"{API_URL}/documents/upload",
                files={"file": ("test.pdf", b"test", "application/pdf")},
                data={"property_id": "test", "requirement_id": "test"},
                timeout=5
            )
            
            # Should get 401 (unauthorized) not 404 (not found)
            self.log_test(
                "Document upload route registered",
                response.status_code != 404,
                f"Status: {response.status_code} (expected 401)"
            )
        except Exception as e:
            self.log_test("Document routes test", False, str(e))
    
    def test_7_audit_logging(self):
        """Test 7: Audit Log Verification"""
        print("\n📋 Test 7: Audit Logging\n")
        
        # This would require admin access to check logs
        # For now, verify the intake submission was logged
        print("⚠️  Audit log verification requires database access")
        print("   Manual verification: Check audit_logs collection for INTAKE_SUBMITTED event\n")
    
    def test_8_password_setup_route(self):
        """Test 8: Password Setup Route"""
        print("\n📋 Test 8: Password Setup Flow\n")
        
        try:
            # Test with invalid token
            response = requests.post(
                f"{API_URL}/auth/set-password",
                json={"token": "invalid_token", "password": "Test123!"},
                timeout=5
            )
            
            self.log_test(
                "Password setup route exists",
                response.status_code != 404
            )
            
            self.log_test(
                "Invalid tokens rejected",
                response.status_code == 400,
                f"Status: {response.status_code}"
            )
        except Exception as e:
            self.log_test("Password setup test", False, str(e))
    
    def run_all_tests(self):
        """Run complete E2E test suite"""
        print("=" * 60)
        print("END-TO-END PRODUCTION TESTING")
        print("Compliance Vault Pro - Complete Flow Verification")
        print("=" * 60)
        
        self.test_1_health_check()
        self.test_2_intake_submission()
        self.test_3_onboarding_status()
        self.test_4_admin_login()
        self.test_5_route_guards()
        self.test_6_document_routes()
        self.test_7_audit_logging()
        self.test_8_password_setup_route()
        
        print("\n" + "=" * 60)
        print(f"RESULTS: {self.passed} passed, {self.failed} failed")
        print("=" * 60)
        
        if self.failed == 0:
            print("\n✅ ALL E2E TESTS PASSED - Core flows operational")
            print("\nNext steps:")
            print("1. Configure Postmark to test email flow")
            print("2. Test Stripe payment flow")
            print("3. Test complete provisioning with real payment")
            print("4. Verify password setup email delivery")
            return 0
        else:
            print(f"\n❌ {self.failed} TESTS FAILED - Review errors above")
            return 1

def main():
    suite = E2ETestSuite()
    exit_code = suite.run_all_tests()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
