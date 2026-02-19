"""Canonical Plan Registry - Single Source of Truth for all plan definitions.

This is the AUTHORITATIVE source for:
- Plan codes and internal identifiers
- Property limits
- Pricing (monthly + onboarding)
- Feature entitlements
- Stripe price ID mappings (loaded from env; never hardcoded)

NON-NEGOTIABLE RULES:
1. Backend is authoritative - all entitlement checks happen server-side
2. Stripe is a billing system, not a permission system
3. No feature leakage - blocked features must fail clearly
4. Admin access is never plan-gated
5. Plan code is derived from subscription line item price_id ONLY

Plan Structure (January 2026):
- PLAN_1_SOLO: Solo Landlord (2 properties, £19/mo, £49 onboarding)
- PLAN_2_PORTFOLIO: Portfolio Landlord / Small Agent (10 properties, £39/mo, £79 onboarding)
- PLAN_3_PRO: Professional / Agent / HMO (25 properties, £79/mo, £149 onboarding)

Stripe price IDs are loaded from environment variables (no hardcoding):
  STRIPE_PRICE_PLAN_1_SOLO_MONTHLY, STRIPE_PRICE_PLAN_1_SOLO_ONBOARDING,
  STRIPE_PRICE_PLAN_2_PORTFOLIO_MONTHLY, STRIPE_PRICE_PLAN_2_PORTFOLIO_ONBOARDING,
  STRIPE_PRICE_PLAN_3_PRO_MONTHLY, STRIPE_PRICE_PLAN_3_PRO_ONBOARDING.
"""
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import os
from database import database
import logging

logger = logging.getLogger(__name__)


class PriceConfigMissingError(Exception):
    """Raised when a required Stripe price env var is missing. Use error_code PRICE_CONFIG_MISSING in HTTP 500."""
    def __init__(self, message: str, missing_var: Optional[str] = None):
        super().__init__(message)
        self.missing_var = missing_var


# ============================================================================
# PLAN ENUM - Canonical Plan Codes
# ============================================================================
class PlanCode(str, Enum):
    """Canonical plan codes - single source of truth."""
    PLAN_1_SOLO = "PLAN_1_SOLO"
    PLAN_2_PORTFOLIO = "PLAN_2_PORTFOLIO"
    PLAN_3_PRO = "PLAN_3_PRO"


# ============================================================================
# ENTITLEMENT STATUS - Subscription-based access level
# ============================================================================
class EntitlementStatus(str, Enum):
    """Entitlement status derived from subscription status."""
    ENABLED = "ENABLED"       # Full access (ACTIVE, TRIALING)
    LIMITED = "LIMITED"       # Read-only mode (PAST_DUE)
    DISABLED = "DISABLED"     # Locked (UNPAID, CANCELED, INCOMPLETE_EXPIRED)


# ============================================================================
# SUBSCRIPTION ALLOW-LIST - Shared helper for feature gating
# ============================================================================
SUBSCRIPTION_STATUSES_ALLOWING_FEATURE_ACCESS = frozenset({"ACTIVE", "TRIALING"})


def subscription_allows_feature_access(subscription_status: Optional[str]) -> bool:
    """
    Return True if subscription status is in the allow-list for feature access.
    Use this consistently for plan-gated endpoints (middleware, enforce_feature, etc.).
    """
    if not subscription_status:
        return False
    return subscription_status.upper() in SUBSCRIPTION_STATUSES_ALLOWING_FEATURE_ACCESS


# ============================================================================
# STRIPE PRICE ID MAPPINGS - Loaded from environment (never hardcoded)
# ============================================================================
# Env var names: STRIPE_PRICE_<PLAN_CODE>_MONTHLY, STRIPE_PRICE_<PLAN_CODE>_ONBOARDING
# e.g. STRIPE_PRICE_PLAN_1_SOLO_MONTHLY, STRIPE_PRICE_PLAN_1_SOLO_ONBOARDING
_STRIPE_PRICE_CACHE: Optional[Dict[str, Any]] = None


def _load_stripe_prices_from_env() -> Dict[str, Any]:
    """
    Load Stripe price IDs from environment. Raises PriceConfigMissingError if any required var is missing.
    Returns dict with keys: mappings, subscription_price_to_plan, onboarding_price_to_plan.
    """
    global _STRIPE_PRICE_CACHE
    mappings = {}
    for plan in PlanCode:
        monthly_key = f"STRIPE_PRICE_{plan.value}_MONTHLY"
        onb_key = f"STRIPE_PRICE_{plan.value}_ONBOARDING"
        monthly = (os.environ.get(monthly_key) or "").strip()
        onb = (os.environ.get(onb_key) or "").strip() or None
        if not monthly:
            raise PriceConfigMissingError(
                f"Missing required Stripe price env: {monthly_key}. Set test/live price ID for this plan.",
                missing_var=monthly_key,
            )
        mappings[plan.value] = {
            "subscription_price_id": monthly,
            "onboarding_price_id": onb,
        }
    subscription_price_to_plan = {
        mappings[k]["subscription_price_id"]: k for k in mappings
    }
    onboarding_price_to_plan = {
        mappings[k]["onboarding_price_id"]: k
        for k in mappings
        if mappings[k].get("onboarding_price_id")
    }
    _STRIPE_PRICE_CACHE = {
        "mappings": mappings,
        "subscription_price_to_plan": subscription_price_to_plan,
        "onboarding_price_to_plan": onboarding_price_to_plan,
    }
    return _STRIPE_PRICE_CACHE


def get_stripe_price_mappings() -> Dict[str, Any]:
    """Return cached Stripe price config (mappings + reverse lookups). Raises PriceConfigMissingError if env incomplete."""
    global _STRIPE_PRICE_CACHE
    if _STRIPE_PRICE_CACHE is None:
        _load_stripe_prices_from_env()
    return _STRIPE_PRICE_CACHE


# ============================================================================
# PLAN DEFINITIONS - Complete plan configuration
# ============================================================================
PLAN_DEFINITIONS = {
    PlanCode.PLAN_1_SOLO: {
        "code": "PLAN_1_SOLO",
        "name": "Solo Landlord",
        "display_name": "Solo Landlord Plan",
        "description": "Perfect for DIY landlords managing 1-2 properties",
        "target_audience": "DIY landlords",
        
        # Pricing
        "monthly_price": 19.00,
        "onboarding_fee": 49.00,
        "currency": "GBP",
        
        # Limits
        "max_properties": 2,
        
        # Stripe IDs - loaded from env (STRIPE_PRICE_PLAN_1_SOLO_MONTHLY / ONBOARDING)
        
        # UI
        "color": "#6B7280",  # Gray
        "badge": None,
        "is_popular": False,
    },
    PlanCode.PLAN_2_PORTFOLIO: {
        "code": "PLAN_2_PORTFOLIO",
        "name": "Portfolio Landlord",
        "display_name": "Portfolio / Small Agent Plan",
        "description": "For portfolio landlords and small letting agents",
        "target_audience": "Portfolio landlords, small agents",
        
        # Pricing
        "monthly_price": 39.00,
        "onboarding_fee": 79.00,
        "currency": "GBP",
        
        # Limits
        "max_properties": 10,
        
        # Stripe IDs - loaded from env (STRIPE_PRICE_PLAN_2_PORTFOLIO_MONTHLY / ONBOARDING)
        
        # UI
        "color": "#00B8A9",  # Electric Teal
        "badge": "Most Popular",
        "is_popular": True,
    },
    PlanCode.PLAN_3_PRO: {
        "code": "PLAN_3_PRO",
        "name": "Professional",
        "display_name": "Professional / Agent / HMO Plan",
        "description": "For letting agents, HMOs, and serious operators",
        "target_audience": "Letting agents, HMOs, serious operators",
        
        # Pricing
        "monthly_price": 79.00,
        "onboarding_fee": 149.00,
        "currency": "GBP",
        "annual_discount_price": 69.00,  # Optional annual pricing
        
        # Limits
        "max_properties": 25,
        
        # Stripe IDs - loaded from env (STRIPE_PRICE_PLAN_3_PRO_MONTHLY / ONBOARDING)
        
        # UI
        "color": "#0B1D3A",  # Midnight Blue
        "badge": "Full Features",
        "is_popular": False,
    },
}


# ============================================================================
# FEATURE ENTITLEMENT MATRIX - What each plan gets (Pricing Page truth)
# SOLO: Core + Basic AI. PORTFOLIO: SOLO + ZIP bulk, PDF reports, Scheduled reports.
# PROFESSIONAL: PORTFOLIO + Advanced AI, Review UI, CSV, SMS, Tenant portal,
# Webhooks, White label, Audit log export. API Access removed (not implemented).
# Legacy keys (zip_upload, compliance_calendar, extraction_review_ui, tenant_portal)
# kept for backward compatibility with existing enforce_feature/require_feature.
# ============================================================================
FEATURE_MATRIX = {
    PlanCode.PLAN_1_SOLO: {
        # Core (all plans)
        "compliance_dashboard": True,
        "compliance_score": True,
        "compliance_calendar": True,
        "expiry_calendar": True,
        "email_notifications": True,
        "document_upload_single": True,
        "multi_file_upload": True,
        "score_trending": True,
        "ai_extraction_basic": True,
        # Portfolio additions -> False for Solo
        "document_upload_bulk_zip": False,
        "zip_upload": False,
        "reports_pdf": False,
        "scheduled_reports": False,
        # Professional additions -> False for Solo
        "ai_extraction_advanced": False,
        "extraction_review_ui": False,
        "ai_review_interface": False,
        "reports_csv": False,
        "sms_reminders": False,
        "tenant_portal": False,
        "tenant_portal_access": False,
        "webhooks": False,
        "white_label_reports": False,
        "audit_log_export": False,
    },
    PlanCode.PLAN_2_PORTFOLIO: {
        # Core
        "compliance_dashboard": True,
        "compliance_score": True,
        "compliance_calendar": True,
        "expiry_calendar": True,
        "email_notifications": True,
        "document_upload_single": True,
        "multi_file_upload": True,
        "score_trending": True,
        "ai_extraction_basic": True,
        # Portfolio additions
        "document_upload_bulk_zip": True,
        "zip_upload": True,
        "reports_pdf": True,
        "scheduled_reports": True,
        # Professional only -> False for Portfolio
        "ai_extraction_advanced": False,
        "extraction_review_ui": False,
        "ai_review_interface": False,
        "reports_csv": False,
        "sms_reminders": False,
        "tenant_portal": False,
        "tenant_portal_access": False,
        "webhooks": False,
        "white_label_reports": False,
        "audit_log_export": False,
    },
    PlanCode.PLAN_3_PRO: {
        # Core
        "compliance_dashboard": True,
        "compliance_score": True,
        "compliance_calendar": True,
        "expiry_calendar": True,
        "email_notifications": True,
        "document_upload_single": True,
        "multi_file_upload": True,
        "score_trending": True,
        "ai_extraction_basic": True,
        # Portfolio
        "document_upload_bulk_zip": True,
        "zip_upload": True,
        "reports_pdf": True,
        "scheduled_reports": True,
        # Professional
        "ai_extraction_advanced": True,
        "extraction_review_ui": True,
        "ai_review_interface": True,
        "reports_csv": True,
        "sms_reminders": True,
        "tenant_portal": True,
        "tenant_portal_access": True,
        "webhooks": True,
        "white_label_reports": True,
        "audit_log_export": True,
    },
}


# ============================================================================
# FEATURE METADATA - Human-readable feature info
# ============================================================================
FEATURE_METADATA = {
    "compliance_dashboard": {
        "name": "Compliance Dashboard",
        "description": "View property compliance status at a glance",
        "category": "core",
    },
    "compliance_score": {
        "name": "Compliance Score",
        "description": "Track your compliance score with explanations",
        "category": "core",
    },
    "compliance_calendar": {
        "name": "Compliance Calendar",
        "description": "View expiry dates in calendar format",
        "category": "core",
    },
    "expiry_calendar": {
        "name": "Expiry Calendar",
        "description": "View certificate expirations in calendar format",
        "category": "core",
    },
    "email_notifications": {
        "name": "Email Notifications",
        "description": "Receive compliance reminders via email",
        "category": "communication",
    },
    "document_upload_single": {
        "name": "Document Upload",
        "description": "Upload compliance documents (single file)",
        "category": "documents",
    },
    "multi_file_upload": {
        "name": "Multi-File Upload",
        "description": "Upload multiple documents at once",
        "category": "documents",
    },
    "score_trending": {
        "name": "Score Trending",
        "description": "View compliance score history and trends",
        "category": "core",
    },
    "ai_extraction_basic": {
        "name": "AI Document Extraction (Basic)",
        "description": "Automatically extract document type, issue and expiry dates",
        "category": "ai",
    },
    "ai_extraction_advanced": {
        "name": "AI Document Extraction (Advanced)",
        "description": "Confidence scoring and field validation for extracted data",
        "category": "ai",
    },
    "extraction_review_ui": {
        "name": "Extraction Review UI",
        "description": "Review and approve AI-extracted data before applying",
        "category": "ai",
    },
    "ai_review_interface": {
        "name": "AI Review Interface",
        "description": "Review and approve AI-extracted data before applying (Professional)",
        "category": "ai",
    },
    "document_upload_bulk_zip": {
        "name": "ZIP Bulk Upload",
        "description": "Upload documents as a single ZIP archive (Portfolio+)",
        "category": "documents",
    },
    "zip_upload": {
        "name": "ZIP Archive Upload",
        "description": "Upload documents as a single ZIP archive",
        "category": "documents",
    },
    "reports_pdf": {
        "name": "PDF Reports",
        "description": "Download compliance reports as PDF documents",
        "category": "reporting",
    },
    "reports_csv": {
        "name": "CSV Reports",
        "description": "Download compliance data as CSV spreadsheets",
        "category": "reporting",
    },
    "scheduled_reports": {
        "name": "Scheduled Reports",
        "description": "Automatically receive reports on a schedule",
        "category": "reporting",
    },
    "sms_reminders": {
        "name": "SMS Reminders",
        "description": "Receive compliance reminders via SMS",
        "category": "communication",
    },
    "tenant_portal": {
        "name": "Tenant Portal",
        "description": "Allow tenants to view property compliance (read-only)",
        "category": "portal",
    },
    "tenant_portal_access": {
        "name": "Tenant View Access",
        "description": "Allow tenants to view property compliance (Professional)",
        "category": "portal",
    },
    "webhooks": {
        "name": "Webhooks",
        "description": "Send compliance events to external systems",
        "category": "integration",
    },
    "white_label_reports": {
        "name": "White-Label Reports",
        "description": "Custom branding for reports and compliance packs",
        "category": "advanced",
    },
    "audit_log_export": {
        "name": "Audit Log Export",
        "description": "Export audit logs for compliance review",
        "category": "advanced",
    },
}


# ============================================================================
# MINIMUM PLAN FOR FEATURE - Which plan unlocks each feature (Pricing Page)
# ============================================================================
MINIMUM_PLAN_FOR_FEATURE = {
    # PLAN_2_PORTFOLIO: ZIP bulk, PDF reports, Scheduled reports only
    "document_upload_bulk_zip": PlanCode.PLAN_2_PORTFOLIO,
    "zip_upload": PlanCode.PLAN_2_PORTFOLIO,
    "reports_pdf": PlanCode.PLAN_2_PORTFOLIO,
    "scheduled_reports": PlanCode.PLAN_2_PORTFOLIO,
    # PLAN_3_PRO only
    "ai_extraction_advanced": PlanCode.PLAN_3_PRO,
    "extraction_review_ui": PlanCode.PLAN_3_PRO,
    "ai_review_interface": PlanCode.PLAN_3_PRO,
    "reports_csv": PlanCode.PLAN_3_PRO,
    "sms_reminders": PlanCode.PLAN_3_PRO,
    "tenant_portal": PlanCode.PLAN_3_PRO,
    "tenant_portal_access": PlanCode.PLAN_3_PRO,
    "webhooks": PlanCode.PLAN_3_PRO,
    "white_label_reports": PlanCode.PLAN_3_PRO,
    "audit_log_export": PlanCode.PLAN_3_PRO,
}


# ============================================================================
# PLAN REGISTRY SERVICE
# ============================================================================
class PlanRegistryService:
    """Central service for all plan and entitlement operations."""
    
    # -------------------------------------------------------------------------
    # Plan Information
    # -------------------------------------------------------------------------
    
    def get_plan(self, plan_code: PlanCode) -> Dict[str, Any]:
        """Get complete plan definition. Stripe price IDs are merged from env (get_stripe_price_mappings)."""
        base = PLAN_DEFINITIONS.get(plan_code, PLAN_DEFINITIONS[PlanCode.PLAN_1_SOLO]).copy()
        config = get_stripe_price_mappings()
        prices = config["mappings"].get(plan_code.value, {})
        base["stripe_subscription_price_id"] = prices.get("subscription_price_id")
        base["stripe_onboarding_price_id"] = prices.get("onboarding_price_id")
        return base
    
    def get_all_plans(self) -> List[Dict[str, Any]]:
        """Get all plans for display (includes Stripe price IDs from env)."""
        config = get_stripe_price_mappings()
        return [
            {
                **plan,
                "code": code.value,
                "stripe_subscription_price_id": config["mappings"].get(code.value, {}).get("subscription_price_id"),
                "stripe_onboarding_price_id": config["mappings"].get(code.value, {}).get("onboarding_price_id"),
            }
            for code, plan in PLAN_DEFINITIONS.items()
        ]
    
    def get_plan_by_code_string(self, code_str: str) -> Optional[Dict[str, Any]]:
        """Get plan by string code (handles legacy codes)."""
        # Handle legacy plan codes
        legacy_mapping = {
            "PLAN_1": PlanCode.PLAN_1_SOLO,
            "PLAN_2_5": PlanCode.PLAN_2_PORTFOLIO,
            "PLAN_6_15": PlanCode.PLAN_3_PRO,
        }
        
        try:
            plan_code = PlanCode(code_str)
        except ValueError:
            plan_code = legacy_mapping.get(code_str, PlanCode.PLAN_1_SOLO)
        
        return self.get_plan(plan_code)
    
    def get_property_limit(self, plan_code: PlanCode) -> int:
        """Get max properties for a plan."""
        plan = self.get_plan(plan_code)
        return plan.get("max_properties", 2)
    
    def get_property_limit_by_string(self, code_str: str) -> int:
        """Get property limit by string code."""
        plan = self.get_plan_by_code_string(code_str)
        return plan.get("max_properties", 2) if plan else 2
    
    # -------------------------------------------------------------------------
    # Feature Entitlements
    # -------------------------------------------------------------------------
    
    def get_features(self, plan_code: PlanCode) -> Dict[str, bool]:
        """Get all feature availability for a plan."""
        return FEATURE_MATRIX.get(plan_code, FEATURE_MATRIX[PlanCode.PLAN_1_SOLO]).copy()
    
    def get_features_by_string(self, code_str: str) -> Dict[str, bool]:
        """Get features by string code."""
        legacy_mapping = {
            "PLAN_1": PlanCode.PLAN_1_SOLO,
            "PLAN_2_5": PlanCode.PLAN_2_PORTFOLIO,
            "PLAN_6_15": PlanCode.PLAN_3_PRO,
        }
        
        try:
            plan_code = PlanCode(code_str)
        except ValueError:
            plan_code = legacy_mapping.get(code_str, PlanCode.PLAN_1_SOLO)
        
        return self.get_features(plan_code)
    
    def is_feature_available(self, plan_code: PlanCode, feature: str) -> bool:
        """Check if a feature is available on a plan."""
        features = self.get_features(plan_code)
        return features.get(feature, False)
    
    def get_minimum_plan_for_feature(self, feature: str) -> Optional[PlanCode]:
        """Get the minimum plan required for a feature."""
        return MINIMUM_PLAN_FOR_FEATURE.get(feature)
    
    def get_feature_metadata(self, feature: str) -> Optional[Dict]:
        """Get human-readable info about a feature."""
        return FEATURE_METADATA.get(feature)
    
    # -------------------------------------------------------------------------
    # Entitlement Checks
    # -------------------------------------------------------------------------
    
    def check_feature_access(
        self,
        plan_code: PlanCode,
        feature: str
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Check if feature is accessible and return detailed info.
        
        Returns:
            (is_allowed, upgrade_message, upgrade_info)
        """
        if self.is_feature_available(plan_code, feature):
            return True, None, None
        
        feature_info = self.get_feature_metadata(feature)
        feature_name = feature_info.get("name", feature) if feature_info else feature
        
        min_plan = self.get_minimum_plan_for_feature(feature)
        
        if min_plan:
            min_plan_def = self.get_plan(min_plan)
            upgrade_info = {
                "required_plan": min_plan.value,
                "required_plan_name": min_plan_def["name"],
                "feature_key": feature,
                "feature_name": feature_name,
                "upgrade_path": f"/app/billing?upgrade_to={min_plan.value}",
            }
            return False, f"{feature_name} requires {min_plan_def['name']} plan or higher", upgrade_info
        
        return False, f"{feature_name} is not available on your current plan", None
    
    async def enforce_feature(
        self,
        client_id: str,
        feature: str
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Server-side enforcement of feature access.
        
        Returns:
            (is_allowed, error_message, error_details)
        """
        db = database.get_db()
        
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "billing_plan": 1, "subscription_status": 1}
        )
        
        if not client:
            return False, "Client not found", {"error_code": "CLIENT_NOT_FOUND"}
        
        # Check subscription allows feature access (allow-list: ACTIVE, TRIALING)
        subscription_status = client.get("subscription_status", "PENDING")
        if not subscription_allows_feature_access(subscription_status):
            return False, f"Subscription is {subscription_status}. Active or trialing subscription required.", {
                "error_code": "SUBSCRIPTION_INACTIVE",
                "subscription_status": subscription_status
            }

        # Get plan (handle legacy codes)
        plan_str = client.get("billing_plan", "PLAN_1_SOLO")
        plan_code = self.resolve_plan_code(plan_str)
        
        # Check feature access
        is_allowed, message, upgrade_info = self.check_feature_access(plan_code, feature)
        
        if not is_allowed:
            return False, message, {
                "error_code": "PLAN_NOT_ELIGIBLE",
                "feature": feature,
                "upgrade_required": True,
                "current_plan": plan_str,
                **(upgrade_info or {})
            }
        
        return True, None, None
    
    async def enforce_property_limit(
        self,
        client_id: str,
        requested_count: int
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Enforce property limit during intake.
        
        Returns:
            (is_allowed, error_message, error_details)
        """
        db = database.get_db()
        
        # For new intakes, check requested count against plan
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "billing_plan": 1}
        )
        
        if not client:
            # New intake - use the plan from the request
            return True, None, None
        
        plan_str = client.get("billing_plan", "PLAN_1_SOLO")
        plan_code = self.resolve_plan_code(plan_str)
        max_properties = self.get_property_limit(plan_code)
        
        if requested_count > max_properties:
            plan_def = self.get_plan(plan_code)
            
            # Find the next plan that supports this count
            upgrade_plan = None
            for check_code in [PlanCode.PLAN_2_PORTFOLIO, PlanCode.PLAN_3_PRO]:
                if self.get_property_limit(check_code) >= requested_count:
                    upgrade_plan = check_code
                    break
            
            return False, f"You've reached the maximum of {max_properties} properties for the {plan_def['name']} plan", {
                "error_code": "PROPERTY_LIMIT_EXCEEDED",
                "current_limit": max_properties,
                "requested_count": requested_count,
                "current_plan": plan_str,
                "upgrade_required": True,
                "upgrade_to": upgrade_plan.value if upgrade_plan else None,
            }
        
        return True, None, None
    
    def check_property_limit(
        self,
        plan_code: PlanCode,
        requested_count: int
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Check property limit without DB call.
        
        Returns:
            (is_allowed, error_message, error_details)
        """
        max_properties = self.get_property_limit(plan_code)
        
        if requested_count > max_properties:
            plan_def = self.get_plan(plan_code)
            
            # Find upgrade plan
            upgrade_plan = None
            for check_code in [PlanCode.PLAN_2_PORTFOLIO, PlanCode.PLAN_3_PRO]:
                if self.get_property_limit(check_code) >= requested_count:
                    upgrade_plan = check_code
                    break
            
            upgrade_plan_def = self.get_plan(upgrade_plan) if upgrade_plan else None
            
            return False, f"You've reached the maximum of {max_properties} properties for the {plan_def['name']} plan. Upgrade to {upgrade_plan_def['name'] if upgrade_plan_def else 'a higher plan'} to add more.", {
                "error_code": "PROPERTY_LIMIT_EXCEEDED",
                "current_limit": max_properties,
                "requested_count": requested_count,
                "current_plan": plan_code.value,
                "upgrade_required": True,
                "upgrade_to": upgrade_plan.value if upgrade_plan else None,
                "upgrade_to_name": upgrade_plan_def["name"] if upgrade_plan_def else None,
                "upgrade_to_limit": upgrade_plan_def["max_properties"] if upgrade_plan_def else None,
            }
        
        return True, None, None
    
    # -------------------------------------------------------------------------
    # Client Entitlements
    # -------------------------------------------------------------------------
    
    async def get_client_entitlements(self, client_id: str) -> Dict[str, Any]:
        """Get complete entitlement info for a client."""
        db = database.get_db()
        
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "billing_plan": 1, "subscription_status": 1}
        )
        
        if not client:
            plan_code = PlanCode.PLAN_1_SOLO
            is_active = False
            subscription_status = "UNKNOWN"
        else:
            plan_str = client.get("billing_plan", "PLAN_1_SOLO")
            plan_code = self.resolve_plan_code(plan_str)
            subscription_status = client.get("subscription_status", "PENDING")
            is_active = subscription_allows_feature_access(subscription_status)
        
        plan_def = self.get_plan(plan_code)
        features = self.get_features(plan_code)
        
        # Build detailed feature list
        detailed_features = {}
        for feature_key, is_enabled in features.items():
            feature_info = self.get_feature_metadata(feature_key)
            if feature_info:
                min_plan = self.get_minimum_plan_for_feature(feature_key)
                detailed_features[feature_key] = {
                    "enabled": is_enabled and is_active,
                    "name": feature_info.get("name"),
                    "description": feature_info.get("description"),
                    "category": feature_info.get("category"),
                    "minimum_plan": min_plan.value if min_plan else None,
                }
        
        return {
            "client_id": client_id,
            "plan": plan_code.value,
            "plan_name": plan_def["name"],
            "plan_display_name": plan_def["display_name"],
            "subscription_status": subscription_status,
            "is_active": is_active,
            "max_properties": plan_def["max_properties"],
            "features": detailed_features,
            "feature_summary": {
                "total": len(detailed_features),
                "enabled": sum(1 for f in detailed_features.values() if f["enabled"]),
                "disabled": sum(1 for f in detailed_features.values() if not f["enabled"]),
            }
        }
    
    # -------------------------------------------------------------------------
    # Entitlement Matrix (for admin/docs)
    # -------------------------------------------------------------------------
    
    def get_entitlement_matrix(self) -> Dict[str, Any]:
        """Generate complete feature/plan matrix for documentation."""
        matrix = {}
        
        for feature_key, feature_info in FEATURE_METADATA.items():
            matrix[feature_key] = {
                "name": feature_info.get("name"),
                "description": feature_info.get("description"),
                "category": feature_info.get("category"),
                "plans": {
                    PlanCode.PLAN_1_SOLO.value: FEATURE_MATRIX[PlanCode.PLAN_1_SOLO].get(feature_key, False),
                    PlanCode.PLAN_2_PORTFOLIO.value: FEATURE_MATRIX[PlanCode.PLAN_2_PORTFOLIO].get(feature_key, False),
                    PlanCode.PLAN_3_PRO.value: FEATURE_MATRIX[PlanCode.PLAN_3_PRO].get(feature_key, False),
                }
            }
        
        return {
            "features": matrix,
            "plans": {
                code.value: {
                    "name": plan["name"],
                    "display_name": plan["display_name"],
                    "max_properties": plan["max_properties"],
                    "monthly_price": plan["monthly_price"],
                    "onboarding_fee": plan["onboarding_fee"],
                }
                for code, plan in PLAN_DEFINITIONS.items()
            }
        }
    
    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def resolve_plan_code(self, code_str: str) -> PlanCode:
        """
        Resolve string to PlanCode, handling legacy codes.
        Public API: use this (not _resolve_plan_code) from middleware and other callers.
        """
        return self._resolve_plan_code(code_str)

    def _resolve_plan_code(self, code_str: str) -> PlanCode:
        """Resolve string to PlanCode, handling legacy codes."""
        legacy_mapping = {
            "PLAN_1": PlanCode.PLAN_1_SOLO,
            "PLAN_2_5": PlanCode.PLAN_2_PORTFOLIO,
            "PLAN_6_15": PlanCode.PLAN_3_PRO,
        }

        try:
            return PlanCode(code_str)
        except ValueError:
            return legacy_mapping.get(code_str, PlanCode.PLAN_1_SOLO)
    
    # -------------------------------------------------------------------------
    # Stripe Price ID Mappings
    # -------------------------------------------------------------------------
    
    def get_plan_from_subscription_price_id(self, price_id: str) -> Optional[PlanCode]:
        """
        Derive plan code from Stripe subscription price_id.
        This is the ONLY valid way to determine plan from Stripe.
        """
        config = get_stripe_price_mappings()
        plan_str = config["subscription_price_to_plan"].get(price_id)
        if plan_str:
            return self.resolve_plan_code(plan_str)
        return None

    def get_plan_from_onboarding_price_id(self, price_id: str) -> Optional[PlanCode]:
        """Check if a price_id is a valid onboarding fee."""
        config = get_stripe_price_mappings()
        plan_str = config["onboarding_price_to_plan"].get(price_id)
        if plan_str:
            return self.resolve_plan_code(plan_str)
        return None

    def is_valid_subscription_price(self, price_id: str) -> bool:
        """Check if a price_id is a recognized subscription price."""
        config = get_stripe_price_mappings()
        return price_id in config["subscription_price_to_plan"]

    def is_valid_onboarding_price(self, price_id: str) -> bool:
        """Check if a price_id is a recognized onboarding price."""
        config = get_stripe_price_mappings()
        return price_id in config["onboarding_price_to_plan"]

    def get_stripe_price_ids(self, plan_code: PlanCode) -> Dict[str, str]:
        """Get Stripe price IDs for a plan (from env). Raises PriceConfigMissingError if config missing."""
        config = get_stripe_price_mappings()
        prices = config["mappings"].get(plan_code.value, {})
        return {
            "subscription_price_id": prices.get("subscription_price_id"),
            "onboarding_price_id": prices.get("onboarding_price_id"),
        }
    
    # -------------------------------------------------------------------------
    # Entitlement Status Mapping
    # -------------------------------------------------------------------------
    
    def get_entitlement_status_from_subscription(self, subscription_status: str) -> EntitlementStatus:
        """
        Map Stripe subscription status to entitlement status.
        
        ACTIVE, TRIALING -> ENABLED (full access)
        PAST_DUE -> LIMITED (read-only, no side effects)
        UNPAID, CANCELED, INCOMPLETE, INCOMPLETE_EXPIRED -> DISABLED (locked)
        """
        status_upper = subscription_status.upper() if subscription_status else "UNKNOWN"
        
        if status_upper in ("ACTIVE", "TRIALING"):
            return EntitlementStatus.ENABLED
        elif status_upper == "PAST_DUE":
            return EntitlementStatus.LIMITED
        else:
            # UNPAID, CANCELED, INCOMPLETE, INCOMPLETE_EXPIRED, UNKNOWN, etc.
            return EntitlementStatus.DISABLED
    
    def is_side_effect_allowed(self, entitlement_status: EntitlementStatus) -> bool:
        """
        Check if side-effect actions are allowed.
        Side effects: emails, SMS, webhooks, scheduled reports, AI extraction apply
        """
        return entitlement_status == EntitlementStatus.ENABLED


# Singleton instance
plan_registry = PlanRegistryService()
