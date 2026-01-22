"""
Service Catalogue V2 API Tests - Phase 1

Tests for the new V2 Service Catalogue APIs:
- Public V2 APIs: /api/public/v2/*
- Admin V2 APIs: /api/admin/services/v2/*

Features tested:
- 11 active non-CVP services listing
- Services grouped by category
- Document pack hierarchy (Essential → Plus → Pro)
- Add-on pricing (Fast Track +£20, Printed Copy +£25)
- CVP subscription plans
- Admin authentication requirements
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@pleerity.com"
ADMIN_PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
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
# PUBLIC V2 API TESTS
# ============================================================================

class TestPublicServicesV2:
    """Tests for public V2 service endpoints."""
    
    def test_list_all_services_returns_11_non_cvp(self):
        """GET /api/public/v2/services lists all 11 active non-CVP services."""
        response = requests.get(f"{BASE_URL}/api/public/v2/services")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "services" in data
        assert "total" in data
        assert data["total"] == 11, f"Expected 11 services, got {data['total']}"
        
        # Verify no CVP services in public list
        service_codes = [s["service_code"] for s in data["services"]]
        assert "CVP_SUBSCRIPTION" not in service_codes
        
        # Verify expected service codes present
        expected_codes = [
            "AI_WF_BLUEPRINT", "AI_PROC_MAP", "AI_TOOLS",
            "MR_BASIC", "MR_ADV",
            "COMP_HMO", "COMP_FULL_AUDIT", "COMP_MOVEOUT",
            "DOC_PACK_ESSENTIAL", "DOC_PACK_PLUS", "DOC_PACK_PRO"
        ]
        for code in expected_codes:
            assert code in service_codes, f"Missing service: {code}"
    
    def test_services_by_category_groups_correctly(self):
        """GET /api/public/v2/services/by-category groups services correctly."""
        response = requests.get(f"{BASE_URL}/api/public/v2/services/by-category")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all categories present
        expected_categories = ["ai_automation", "market_research", "compliance", "document_pack"]
        for cat in expected_categories:
            assert cat in data, f"Missing category: {cat}"
        
        # Verify counts
        assert data["ai_automation"]["count"] == 3
        assert data["market_research"]["count"] == 2
        assert data["compliance"]["count"] == 3
        assert data["document_pack"]["count"] == 3
        
        # Verify category info structure
        for cat in expected_categories:
            assert "info" in data[cat]
            assert "services" in data[cat]
            assert "label" in data[cat]["info"]
    
    def test_document_packs_returns_tier_order(self):
        """GET /api/public/v2/services/document-packs returns packs in tier order."""
        response = requests.get(f"{BASE_URL}/api/public/v2/services/document-packs")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 3
        packs = data["packs"]
        
        # Verify tier order: ESSENTIAL → PLUS → PRO
        assert packs[0]["pack_tier"] == "ESSENTIAL"
        assert packs[1]["pack_tier"] == "PLUS"
        assert packs[2]["pack_tier"] == "PRO"
        
        # Verify service codes
        assert packs[0]["service_code"] == "DOC_PACK_ESSENTIAL"
        assert packs[1]["service_code"] == "DOC_PACK_PLUS"
        assert packs[2]["service_code"] == "DOC_PACK_PRO"
    
    def test_document_pack_essential_has_5_documents(self):
        """DOC_PACK_ESSENTIAL has 5 documents."""
        response = requests.get(f"{BASE_URL}/api/public/v2/services/document-packs")
        
        assert response.status_code == 200
        packs = response.json()["packs"]
        
        essential = next(p for p in packs if p["service_code"] == "DOC_PACK_ESSENTIAL")
        assert essential["document_count"] == 5, f"Expected 5 docs, got {essential['document_count']}"
    
    def test_document_pack_plus_inherits_11_documents(self):
        """DOC_PACK_PLUS inherits Essential (5) + own (6) = 11 documents."""
        response = requests.get(f"{BASE_URL}/api/public/v2/services/document-packs")
        
        assert response.status_code == 200
        packs = response.json()["packs"]
        
        plus = next(p for p in packs if p["service_code"] == "DOC_PACK_PLUS")
        assert plus["document_count"] == 11, f"Expected 11 docs, got {plus['document_count']}"
        assert plus["includes_lower_tiers"] == True
    
    def test_document_pack_pro_inherits_15_documents(self):
        """DOC_PACK_PRO inherits Plus (11) + own (4) = 15 documents."""
        response = requests.get(f"{BASE_URL}/api/public/v2/services/document-packs")
        
        assert response.status_code == 200
        packs = response.json()["packs"]
        
        pro = next(p for p in packs if p["service_code"] == "DOC_PACK_PRO")
        assert pro["document_count"] == 15, f"Expected 15 docs, got {pro['document_count']}"
        assert pro["includes_lower_tiers"] == True
    
    def test_get_service_details(self):
        """GET /api/public/v2/services/{service_code} returns service details."""
        response = requests.get(f"{BASE_URL}/api/public/v2/services/AI_WF_BLUEPRINT")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service_code"] == "AI_WF_BLUEPRINT"
        assert data["service_name"] == "Workflow Automation Blueprint"
        assert data["category"] == "ai_automation"
        assert data["base_price"] == 7900  # £79 in pence
        assert data["fast_track_available"] == True
        assert data["fast_track_price"] == 2000  # £20 in pence
    
    def test_get_service_not_found(self):
        """GET /api/public/v2/services/{invalid} returns 404."""
        response = requests.get(f"{BASE_URL}/api/public/v2/services/INVALID_SERVICE")
        
        assert response.status_code == 404
    
    def test_get_service_intake_fields(self):
        """GET /api/public/v2/services/{service_code}/intake returns CRM field dictionary intake fields."""
        response = requests.get(f"{BASE_URL}/api/public/v2/services/DOC_PACK_ESSENTIAL/intake")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service_code"] == "DOC_PACK_ESSENTIAL"
        assert data["total_fields"] > 0
        assert "intake_fields" in data
        
        # Verify field structure
        field = data["intake_fields"][0]
        assert "field_id" in field
        assert "label" in field
        assert "field_type" in field
        assert "required" in field
    
    def test_price_calculation_base(self):
        """GET /api/public/v2/services/{service_code}/price calculates base price correctly."""
        response = requests.get(f"{BASE_URL}/api/public/v2/services/DOC_PACK_ESSENTIAL/price")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["base_price"] == 2900  # £29 in pence
        assert data["subtotal"] == 2900
        assert data["vat_rate"] == 0.2
        assert data["vat_amount"] == 580  # 20% of £29
        assert data["total"] == 3480  # £29 + VAT
        assert data["addons"] == []
    
    def test_price_calculation_with_fast_track(self):
        """Price calculation with fast_track=true adds £20."""
        response = requests.get(
            f"{BASE_URL}/api/public/v2/services/DOC_PACK_ESSENTIAL/price?fast_track=true"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["base_price"] == 2900
        assert len(data["addons"]) == 1
        assert data["addons"][0]["code"] == "fast_track"
        assert data["addons"][0]["price"] == 2000  # £20 in pence
        assert data["subtotal"] == 4900  # £29 + £20
        assert data["vat_amount"] == 980  # 20% of £49
        assert data["total"] == 5880  # £49 + VAT
    
    def test_price_calculation_with_printed_copy(self):
        """Price calculation with printed_copy=true adds £25 (only for document packs)."""
        response = requests.get(
            f"{BASE_URL}/api/public/v2/services/DOC_PACK_ESSENTIAL/price?printed_copy=true"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["base_price"] == 2900
        assert len(data["addons"]) == 1
        assert data["addons"][0]["code"] == "printed_copy"
        assert data["addons"][0]["price"] == 2500  # £25 in pence
        assert data["subtotal"] == 5400  # £29 + £25
        assert data["total"] == 6480  # £54 + VAT
    
    def test_price_calculation_with_both_addons(self):
        """Price calculation with both fast_track and printed_copy."""
        response = requests.get(
            f"{BASE_URL}/api/public/v2/services/DOC_PACK_ESSENTIAL/price?fast_track=true&printed_copy=true"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["base_price"] == 2900
        assert len(data["addons"]) == 2
        assert data["subtotal"] == 7400  # £29 + £20 + £25
        assert data["total"] == 8880  # £74 + VAT
    
    def test_printed_copy_not_available_for_non_document_packs(self):
        """Printed copy addon should not apply to non-document pack services."""
        response = requests.get(
            f"{BASE_URL}/api/public/v2/services/AI_WF_BLUEPRINT/price?printed_copy=true"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # AI_WF_BLUEPRINT doesn't have printed_copy_available
        # So the addon should not be added
        assert data["base_price"] == 7900
        assert len(data["addons"]) == 0
        assert data["subtotal"] == 7900
    
    def test_cvp_plans_returns_3_tiers(self):
        """GET /api/public/v2/cvp/plans returns 3 CVP subscription tiers."""
        response = requests.get(f"{BASE_URL}/api/public/v2/cvp/plans")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["available"] == True
        assert len(data["plans"]) == 3
        
        # Verify tier names
        tiers = [p["tier"] for p in data["plans"]]
        assert "solo" in tiers
        assert "portfolio" in tiers
        assert "professional" in tiers
        
        # Verify pricing structure
        solo = next(p for p in data["plans"] if p["tier"] == "solo")
        assert solo["monthly_price"] == 1900  # £19/month
        assert solo["setup_fee"] == 4900  # £49 setup


# ============================================================================
# ADMIN V2 API TESTS
# ============================================================================

class TestAdminServicesV2:
    """Tests for admin V2 service endpoints."""
    
    def test_admin_list_requires_auth(self):
        """GET /api/admin/services/v2/ requires admin auth."""
        response = requests.get(f"{BASE_URL}/api/admin/services/v2/")
        
        assert response.status_code == 401 or response.status_code == 403
    
    def test_admin_list_services(self, admin_headers):
        """GET /api/admin/services/v2/ returns all services including CVP."""
        response = requests.get(
            f"{BASE_URL}/api/admin/services/v2/",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 12  # 11 + CVP
        
        # Verify CVP is included in admin list
        service_codes = [s["service_code"] for s in data["services"]]
        assert "CVP_SUBSCRIPTION" in service_codes
    
    def test_admin_stats_returns_correct_counts(self, admin_headers):
        """GET /api/admin/services/v2/stats returns correct counts by category."""
        response = requests.get(
            f"{BASE_URL}/api/admin/services/v2/stats",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_active"] == 12
        assert data["by_category"]["ai_automation"] == 3
        assert data["by_category"]["market_research"] == 2
        assert data["by_category"]["compliance"] == 3
        assert data["by_category"]["document_pack"] == 3
        assert data["by_category"]["subscription"] == 1
    
    def test_admin_categories_returns_all_enums(self, admin_headers):
        """GET /api/admin/services/v2/categories returns all enum options."""
        response = requests.get(
            f"{BASE_URL}/api/admin/services/v2/categories",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all enum types present
        assert "categories" in data
        assert "pricing_models" in data
        assert "delivery_types" in data
        assert "generation_modes" in data
        assert "pack_tiers" in data
        assert "product_types" in data
        assert "intake_field_types" in data
        
        # Verify category values
        category_values = [c["value"] for c in data["categories"]]
        assert "ai_automation" in category_values
        assert "market_research" in category_values
        assert "compliance" in category_values
        assert "document_pack" in category_values
        assert "subscription" in category_values
    
    def test_admin_get_single_service(self, admin_headers):
        """GET /api/admin/services/v2/{service_code} returns service details."""
        response = requests.get(
            f"{BASE_URL}/api/admin/services/v2/DOC_PACK_PRO",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service_code"] == "DOC_PACK_PRO"
        assert data["pack_tier"] == "PRO"
        assert data["includes_lower_tiers"] == True
        assert data["parent_pack_code"] == "DOC_PACK_PLUS"
    
    def test_admin_get_service_documents_with_inheritance(self, admin_headers):
        """GET /api/admin/services/v2/{service_code}/documents includes inherited docs."""
        response = requests.get(
            f"{BASE_URL}/api/admin/services/v2/DOC_PACK_PRO/documents?include_inherited=true",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 15  # All inherited + own
        assert data["includes_inherited"] == True
    
    def test_admin_get_service_documents_without_inheritance(self, admin_headers):
        """GET /api/admin/services/v2/{service_code}/documents without inheritance."""
        response = requests.get(
            f"{BASE_URL}/api/admin/services/v2/DOC_PACK_PRO/documents?include_inherited=false",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 4  # Only own documents
        assert data["includes_inherited"] == False
    
    def test_admin_calculate_price(self, admin_headers):
        """GET /api/admin/services/v2/{service_code}/price calculates price."""
        response = requests.get(
            f"{BASE_URL}/api/admin/services/v2/DOC_PACK_PLUS/price?fast_track=true",
            headers=admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["base_price"] == 4900  # £49
        assert data["subtotal"] == 6900  # £49 + £20 fast track


# ============================================================================
# SERVICE CODE VERIFICATION TESTS
# ============================================================================

class TestServiceCodes:
    """Verify all expected service codes exist with correct properties."""
    
    @pytest.mark.parametrize("service_code,expected_category,expected_price", [
        ("AI_WF_BLUEPRINT", "ai_automation", 7900),
        ("AI_PROC_MAP", "ai_automation", 12900),
        ("AI_TOOLS", "ai_automation", 5900),
        ("MR_BASIC", "market_research", 6900),
        ("MR_ADV", "market_research", 14900),
        ("COMP_HMO", "compliance", 7900),
        ("COMP_FULL_AUDIT", "compliance", 9900),
        ("COMP_MOVEOUT", "compliance", 3500),
        ("DOC_PACK_ESSENTIAL", "document_pack", 2900),
        ("DOC_PACK_PLUS", "document_pack", 4900),
        ("DOC_PACK_PRO", "document_pack", 7900),
    ])
    def test_service_exists_with_correct_properties(self, service_code, expected_category, expected_price):
        """Verify each service exists with correct category and price."""
        response = requests.get(f"{BASE_URL}/api/public/v2/services/{service_code}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service_code"] == service_code
        assert data["category"] == expected_category
        assert data["base_price"] == expected_price
