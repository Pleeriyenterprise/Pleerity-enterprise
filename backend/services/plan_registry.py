"""Canonical Plan Registry - Single Source of Truth for all plan definitions.

This is the AUTHORITATIVE source for:
- Plan codes and internal identifiers
- Property limits
- Pricing (monthly + onboarding)
- Feature entitlements
- Stripe price ID mappings

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
"""
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from database import database
import logging

logger = logging.getLogger(__name__)


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
# STRIPE PRICE ID MAPPINGS - Production Price IDs (from owner)
# ============================================================================
STRIPE_PRICE_MAPPINGS = {
    "PLAN_1_SOLO": {
        "subscription_price_id": "price_1Ss7qNCF0O5oqdUzHUdjy27g",
        "onboarding_price_id": "price_1Ss7xICF0O5oqdUzGikCKHjQ",
    },
    "PLAN_2_PORTFOLIO": {
        "subscription_price_id": "price_1Ss6JPCF0O5oqdUzaBhJv239",
        "onboarding_price_id": "price_1Ss80uCF0O5oqdUzbluYNTD9",
    },
    "PLAN_3_PRO": {
        "subscription_price_id": "price_1Ss6uoCF0O5oqdUzGwmumLiD",
        "onboarding_price_id": "price_1Ss844CF0O5oqdUzM0AWrBG5",
    },
}

# Reverse lookup: price_id -> plan_code
SUBSCRIPTION_PRICE_TO_PLAN = {
    v["subscription_price_id"]: k for k, v in STRIPE_PRICE_MAPPINGS.items()
}

ONBOARDING_PRICE_TO_PLAN = {
    v["onboarding_price_id"]: k for k, v in STRIPE_PRICE_MAPPINGS.items()
}


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
        
        # Stripe IDs - Production
        "stripe_subscription_price_id": "price_1Ss7qNCF0O5oqdUzHUdjy27g",
        "stripe_onboarding_price_id": "price_1Ss7xICF0O5oqdUzGikCKHjQ",
        
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
        
        # Stripe IDs - Production
        "stripe_subscription_price_id": "price_1Ss6JPCF0O5oqdUzaBhJv239",
        "stripe_onboarding_price_id": "price_1Ss80uCF0O5oqdUzbluYNTD9",
        
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
        
        # Stripe IDs - Production
        "stripe_subscription_price_id": "price_1Ss6uoCF0O5oqdUzGwmumLiD",
        "stripe_onboarding_price_id": "price_1Ss844CF0O5oqdUzM0AWrBG5",
        
        # UI
        "color": "#0B1D3A",  # Midnight Blue
        "badge": "Full Features",
        "is_popular": False,
    },
}


# ============================================================================
# FEATURE ENTITLEMENT MATRIX - What each plan gets
# Canonical feature keys for APIs: /client/entitlements and /client/plan-features
# use these keys only. 403 responses may preserve legacy 'feature' strings
# (e.g. compliance_packs, white_label, audit_exports) for backward compatibility.
# ============================================================================
FEATURE_MATRIX = {
    PlanCode.PLAN_1_SOLO: {
        # Core features (always available)
        "compliance_dashboard": True,
        "compliance_score": True,
        "compliance_calendar": True,
        "email_notifications": True,
        "multi_file_upload": True,
        "score_trending": True,
        
        # AI Features
        "ai_extraction_basic": True,  # Extract type, issue date, expiry date
        "ai_extraction_advanced": False,  # Confidence scoring, review UI
        "extraction_review_ui": False,
        
        # Document Features
        "zip_upload": False,
        
        # Reporting Features
        "reports_pdf": False,
        "reports_csv": False,
        "scheduled_reports": False,
        
        # Communication Features
        "sms_reminders": False,
        
        # Portal Features
        "tenant_portal": False,
        
        # Integration Features
        "webhooks": False,
        "api_access": False,
        
        # Advanced Features
        "white_label_reports": False,
        "audit_log_export": False,
    },
    PlanCode.PLAN_2_PORTFOLIO: {
        # Core features
        "compliance_dashboard": True,
        "compliance_score": True,
        "compliance_calendar": True,
        "email_notifications": True,
        "multi_file_upload": True,
        "score_trending": True,
        
        # AI Features
        "ai_extraction_basic": True,
        "ai_extraction_advanced": True,  # Full confidence scoring
        "extraction_review_ui": True,
        
        # Document Features
        "zip_upload": True,
        
        # Reporting Features
        "reports_pdf": True,
        "reports_csv": True,
        "scheduled_reports": True,
        
        # Communication Features
        "sms_reminders": True,
        
        # Portal Features
        "tenant_portal": True,  # View-only
        
        # Integration Features
        "webhooks": False,
        "api_access": False,
        
        # Advanced Features
        "white_label_reports": False,
        "audit_log_export": False,
    },
    PlanCode.PLAN_3_PRO: {
        # Core features
        "compliance_dashboard": True,
        "compliance_score": True,
        "compliance_calendar": True,
        "email_notifications": True,
        "multi_file_upload": True,
        "score_trending": True,
        
        # AI Features
        "ai_extraction_basic": True,
        "ai_extraction_advanced": True,
        "extraction_review_ui": True,
        
        # Document Features
        "zip_upload": True,
        
        # Reporting Features
        "reports_pdf": True,
        "reports_csv": True,
        "scheduled_reports": True,
        
        # Communication Features
        "sms_reminders": True,
        
        # Portal Features
        "tenant_portal": True,  # View-only
        
        # Integration Features
        "webhooks": True,
        "api_access": True,
        
        # Advanced Features
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
    "email_notifications": {
        "name": "Email Notifications",
        "description": "Receive compliance reminders via email",
        "category": "communication",
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
    "webhooks": {
        "name": "Webhooks",
        "description": "Send compliance events to external systems",
        "category": "integration",
    },
    "api_access": {
        "name": "API Access",
        "description": "Programmatic access to compliance data",
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
# MINIMUM PLAN FOR FEATURE - Which plan unlocks each feature
# ============================================================================
MINIMUM_PLAN_FOR_FEATURE = {
    # PLAN_2_PORTFOLIO unlocks
    "ai_extraction_advanced": PlanCode.PLAN_2_PORTFOLIO,
    "extraction_review_ui": PlanCode.PLAN_2_PORTFOLIO,
    "zip_upload": PlanCode.PLAN_2_PORTFOLIO,
    "reports_pdf": PlanCode.PLAN_2_PORTFOLIO,
    "reports_csv": PlanCode.PLAN_2_PORTFOLIO,
    "scheduled_reports": PlanCode.PLAN_2_PORTFOLIO,
    "sms_reminders": PlanCode.PLAN_2_PORTFOLIO,
    "tenant_portal": PlanCode.PLAN_2_PORTFOLIO,
    
    # PLAN_3_PRO only
    "webhooks": PlanCode.PLAN_3_PRO,
    "api_access": PlanCode.PLAN_3_PRO,
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
        """Get complete plan definition."""
        return PLAN_DEFINITIONS.get(plan_code, PLAN_DEFINITIONS[PlanCode.PLAN_1_SOLO]).copy()
    
    def get_all_plans(self) -> List[Dict[str, Any]]:
        """Get all plans for display."""
        return [
            {**plan, "code": code.value}
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
        plan_str = SUBSCRIPTION_PRICE_TO_PLAN.get(price_id)
        if plan_str:
            return self.resolve_plan_code(plan_str)
        return None

    def get_plan_from_onboarding_price_id(self, price_id: str) -> Optional[PlanCode]:
        """Check if a price_id is a valid onboarding fee."""
        plan_str = ONBOARDING_PRICE_TO_PLAN.get(price_id)
        if plan_str:
            return self.resolve_plan_code(plan_str)
        return None
    
    def is_valid_subscription_price(self, price_id: str) -> bool:
        """Check if a price_id is a recognized subscription price."""
        return price_id in SUBSCRIPTION_PRICE_TO_PLAN
    
    def is_valid_onboarding_price(self, price_id: str) -> bool:
        """Check if a price_id is a recognized onboarding price."""
        return price_id in ONBOARDING_PRICE_TO_PLAN
    
    def get_stripe_price_ids(self, plan_code: PlanCode) -> Dict[str, str]:
        """Get Stripe price IDs for a plan."""
        plan_def = self.get_plan(plan_code)
        return {
            "subscription_price_id": plan_def.get("stripe_subscription_price_id"),
            "onboarding_price_id": plan_def.get("stripe_onboarding_price_id"),
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
