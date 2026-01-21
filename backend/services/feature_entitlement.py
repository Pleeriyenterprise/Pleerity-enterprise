"""Central Feature Entitlement System - Comprehensive feature gating.

This module provides the complete feature entitlement registry and enforcement.
All features must be explicitly defined here with plan mappings.

NON-NEGOTIABLE RULES:
1. Plans only toggle access to completed capability modules
2. No plan-specific logic branches in application code
3. UI must hide or disable unavailable features
4. API must reject unauthorized access with PLAN_NOT_ELIGIBLE
5. Upgrade prompts appear only when user attempts access

Feature Categories:
- AI Features (ai_basic, ai_advanced)
- Document Features (bulk_upload, zip_upload)
- Communication Features (sms, email_digest)
- Reporting Features (reports_pdf, reports_csv, scheduled_reports)
- Integration Features (webhooks, api_access)
- Portal Features (tenant_portal, calendar_sync)
- Advanced Features (compliance_packs, audit_exports, white_label)
"""
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from models import BillingPlan
from database import database
import logging

logger = logging.getLogger(__name__)


class FeatureCategory(str, Enum):
    """Feature categories for organization and display."""
    AI = "ai"
    DOCUMENTS = "documents"
    COMMUNICATION = "communication"
    REPORTING = "reporting"
    INTEGRATION = "integration"
    PORTAL = "portal"
    ADVANCED = "advanced"


# ============================================================================
# CENTRAL FEATURE REGISTRY
# ============================================================================
# All features in the system with their metadata
FEATURE_REGISTRY = {
    # AI Features
    "ai_basic": {
        "name": "AI Assistant (Basic)",
        "description": "AI-powered compliance assistant for basic queries",
        "category": FeatureCategory.AI,
        "is_core": True,  # Available on all plans
    },
    "ai_advanced": {
        "name": "AI Assistant (Advanced)",
        "description": "Advanced AI analysis including document extraction and scoring explanation",
        "category": FeatureCategory.AI,
        "is_core": False,
    },
    
    # Document Features
    "bulk_upload": {
        "name": "Bulk Document Upload",
        "description": "Upload multiple documents at once (individual files)",
        "category": FeatureCategory.DOCUMENTS,
        "is_core": True,
    },
    "zip_upload": {
        "name": "ZIP Archive Upload",
        "description": "Upload documents as a single ZIP archive",
        "category": FeatureCategory.DOCUMENTS,
        "is_core": False,
    },
    
    # Communication Features
    "sms": {
        "name": "SMS Notifications",
        "description": "Receive compliance reminders via SMS",
        "category": FeatureCategory.COMMUNICATION,
        "is_core": False,
        "requires_opt_in": True,
        "requires_verification": True,
    },
    "email_digest": {
        "name": "Email Digest",
        "description": "Customizable email digest delivery",
        "category": FeatureCategory.COMMUNICATION,
        "is_core": True,
    },
    
    # Reporting Features
    "reports_pdf": {
        "name": "PDF Reports",
        "description": "Download compliance reports as PDF documents",
        "category": FeatureCategory.REPORTING,
        "is_core": False,
    },
    "reports_csv": {
        "name": "CSV Reports",
        "description": "Download compliance data as CSV spreadsheets",
        "category": FeatureCategory.REPORTING,
        "is_core": False,
    },
    "scheduled_reports": {
        "name": "Scheduled Report Delivery",
        "description": "Automatically receive reports on a schedule",
        "category": FeatureCategory.REPORTING,
        "is_core": False,
    },
    
    # Integration Features
    "webhooks": {
        "name": "Webhook Integrations",
        "description": "Send compliance events to external systems",
        "category": FeatureCategory.INTEGRATION,
        "is_core": False,
    },
    "api_access": {
        "name": "API Access",
        "description": "Programmatic access to compliance data",
        "category": FeatureCategory.INTEGRATION,
        "is_core": False,
    },
    
    # Portal Features
    "tenant_portal": {
        "name": "Tenant Portal",
        "description": "Allow tenants to view property compliance",
        "category": FeatureCategory.PORTAL,
        "is_core": True,
    },
    "calendar_sync": {
        "name": "Calendar Sync",
        "description": "Export expiry dates to external calendars (iCal)",
        "category": FeatureCategory.PORTAL,
        "is_core": False,
    },
    
    # Advanced Features
    "compliance_packs": {
        "name": "Compliance Packs",
        "description": "Generate and download compliance pack PDFs",
        "category": FeatureCategory.ADVANCED,
        "is_core": False,
    },
    "audit_exports": {
        "name": "Audit Log Exports",
        "description": "Export audit logs for compliance review",
        "category": FeatureCategory.ADVANCED,
        "is_core": False,
    },
    "white_label": {
        "name": "White Label Branding",
        "description": "Custom branding for reports and emails",
        "category": FeatureCategory.ADVANCED,
        "is_core": False,
    },
    "score_trending": {
        "name": "Compliance Score Trending",
        "description": "View compliance score history and trends",
        "category": FeatureCategory.ADVANCED,
        "is_core": True,  # Available on all plans as it adds value
    },
}


# ============================================================================
# PLAN FEATURE MATRIX
# ============================================================================
# Explicit mapping of which features are available on which plans
PLAN_FEATURE_MATRIX = {
    BillingPlan.PLAN_1: {  # Starter Plan
        "max_properties": 1,
        
        # AI
        "ai_basic": True,
        "ai_advanced": False,
        
        # Documents
        "bulk_upload": True,
        "zip_upload": False,
        
        # Communication
        "sms": False,
        "email_digest": True,
        
        # Reporting
        "reports_pdf": False,
        "reports_csv": False,
        "scheduled_reports": False,
        
        # Integrations
        "webhooks": False,
        "api_access": False,
        
        # Portal
        "tenant_portal": True,
        "calendar_sync": False,
        
        # Advanced
        "compliance_packs": False,
        "audit_exports": False,
        "white_label": False,
        "score_trending": True,
    },
    BillingPlan.PLAN_2_5: {  # Growth Plan
        "max_properties": 5,
        
        # AI
        "ai_basic": True,
        "ai_advanced": True,
        
        # Documents
        "bulk_upload": True,
        "zip_upload": False,
        
        # Communication
        "sms": True,
        "email_digest": True,
        
        # Reporting
        "reports_pdf": True,
        "reports_csv": True,
        "scheduled_reports": True,
        
        # Integrations
        "webhooks": False,
        "api_access": False,
        
        # Portal
        "tenant_portal": True,
        "calendar_sync": True,
        
        # Advanced
        "compliance_packs": False,
        "audit_exports": False,
        "white_label": False,
        "score_trending": True,
    },
    BillingPlan.PLAN_6_15: {  # Portfolio Plan
        "max_properties": 15,
        
        # AI
        "ai_basic": True,
        "ai_advanced": True,
        
        # Documents
        "bulk_upload": True,
        "zip_upload": True,
        
        # Communication
        "sms": True,
        "email_digest": True,
        
        # Reporting
        "reports_pdf": True,
        "reports_csv": True,
        "scheduled_reports": True,
        
        # Integrations
        "webhooks": True,
        "api_access": True,
        
        # Portal
        "tenant_portal": True,
        "calendar_sync": True,
        
        # Advanced
        "compliance_packs": True,
        "audit_exports": True,
        "white_label": True,
        "score_trending": True,
    },
}


# ============================================================================
# MINIMUM PLAN REQUIREMENTS
# ============================================================================
# For features not available on all plans, specify the minimum required plan
MINIMUM_PLAN_FOR_FEATURE = {
    "ai_advanced": BillingPlan.PLAN_2_5,
    "zip_upload": BillingPlan.PLAN_6_15,
    "sms": BillingPlan.PLAN_2_5,
    "reports_pdf": BillingPlan.PLAN_2_5,
    "reports_csv": BillingPlan.PLAN_2_5,
    "scheduled_reports": BillingPlan.PLAN_2_5,
    "webhooks": BillingPlan.PLAN_6_15,
    "api_access": BillingPlan.PLAN_6_15,
    "calendar_sync": BillingPlan.PLAN_2_5,
    "compliance_packs": BillingPlan.PLAN_6_15,
    "audit_exports": BillingPlan.PLAN_6_15,
    "white_label": BillingPlan.PLAN_6_15,
}


# ============================================================================
# PLAN METADATA
# ============================================================================
PLAN_METADATA = {
    BillingPlan.PLAN_1: {
        "name": "Starter",
        "display_name": "Starter Plan",
        "description": "Perfect for individual landlords with a single property",
        "monthly_price": 9.99,
        "setup_fee": 49.99,
        "color": "#6B7280",  # Gray
    },
    BillingPlan.PLAN_2_5: {
        "name": "Growth",
        "display_name": "Growth Plan",
        "description": "For landlords building their property portfolio",
        "monthly_price": 9.99,
        "setup_fee": 49.99,
        "color": "#00B8A9",  # Electric Teal
    },
    BillingPlan.PLAN_6_15: {
        "name": "Portfolio",
        "display_name": "Portfolio Plan",
        "description": "For professional landlords and letting agents",
        "monthly_price": 9.99,
        "setup_fee": 49.99,
        "color": "#0B1D3A",  # Midnight Blue
    },
}


# ============================================================================
# FEATURE ENTITLEMENT SERVICE
# ============================================================================
class FeatureEntitlementService:
    """Central service for all feature entitlement checks."""
    
    def get_feature_info(self, feature_key: str) -> Optional[Dict]:
        """Get metadata about a specific feature."""
        return FEATURE_REGISTRY.get(feature_key)
    
    def get_all_features(self) -> Dict[str, Dict]:
        """Get all registered features with their metadata."""
        return FEATURE_REGISTRY.copy()
    
    def get_features_by_category(self, category: FeatureCategory) -> Dict[str, Dict]:
        """Get all features in a specific category."""
        return {
            key: info for key, info in FEATURE_REGISTRY.items()
            if info.get("category") == category
        }
    
    def get_plan_features(self, plan: BillingPlan) -> Dict[str, bool]:
        """Get all feature availability for a specific plan."""
        return PLAN_FEATURE_MATRIX.get(plan, PLAN_FEATURE_MATRIX[BillingPlan.PLAN_1]).copy()
    
    def get_plan_metadata(self, plan: BillingPlan) -> Dict:
        """Get plan metadata (name, description, pricing)."""
        return PLAN_METADATA.get(plan, PLAN_METADATA[BillingPlan.PLAN_1]).copy()
    
    def is_feature_available(self, plan: BillingPlan, feature: str) -> bool:
        """Check if a specific feature is available for the given plan."""
        features = self.get_plan_features(plan)
        return features.get(feature, False)
    
    def get_minimum_plan_for_feature(self, feature: str) -> Optional[BillingPlan]:
        """Get the minimum plan required for a feature."""
        return MINIMUM_PLAN_FOR_FEATURE.get(feature)
    
    def check_feature_access(
        self, 
        plan: BillingPlan, 
        feature: str
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Check if feature is accessible and return detailed info.
        
        Returns:
            (is_allowed, upgrade_message, upgrade_info)
        """
        if self.is_feature_available(plan, feature):
            return True, None, None
        
        feature_info = self.get_feature_info(feature)
        feature_name = feature_info.get("name", feature) if feature_info else feature
        
        min_plan = self.get_minimum_plan_for_feature(feature)
        
        if min_plan:
            min_plan_meta = self.get_plan_metadata(min_plan)
            upgrade_info = {
                "required_plan": min_plan.value,
                "required_plan_name": min_plan_meta["name"],
                "feature_key": feature,
                "feature_name": feature_name,
            }
            return False, f"{feature_name} requires {min_plan_meta['name']} plan or higher", upgrade_info
        
        return False, f"{feature_name} is not available on your current plan", None
    
    async def get_client_entitlements(self, client_id: str) -> Dict[str, Any]:
        """Get complete entitlement information for a client.
        
        Returns comprehensive feature availability, plan info, and limits.
        """
        db = database.get_db()
        
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "billing_plan": 1, "subscription_status": 1}
        )
        
        if not client:
            # Return default starter plan features for unknown clients
            plan = BillingPlan.PLAN_1
            is_active = False
            subscription_status = "UNKNOWN"
        else:
            plan_str = client.get("billing_plan", "PLAN_1")
            try:
                plan = BillingPlan(plan_str)
            except ValueError:
                plan = BillingPlan.PLAN_1
            
            subscription_status = client.get("subscription_status", "PENDING")
            is_active = subscription_status == "ACTIVE"
        
        plan_metadata = self.get_plan_metadata(plan)
        features = self.get_plan_features(plan)
        
        # Build detailed feature list with metadata
        detailed_features = {}
        for feature_key, is_enabled in features.items():
            if feature_key == "max_properties":
                continue  # Skip limit, handle separately
            
            feature_info = self.get_feature_info(feature_key)
            if feature_info:
                min_plan = self.get_minimum_plan_for_feature(feature_key)
                detailed_features[feature_key] = {
                    "enabled": is_enabled and is_active,
                    "name": feature_info.get("name"),
                    "description": feature_info.get("description"),
                    "category": feature_info.get("category", "").value if feature_info.get("category") else None,
                    "is_core": feature_info.get("is_core", False),
                    "minimum_plan": min_plan.value if min_plan else None,
                    "requires_opt_in": feature_info.get("requires_opt_in", False),
                }
        
        return {
            "client_id": client_id,
            "plan": plan.value,
            "plan_name": plan_metadata["name"],
            "plan_display_name": plan_metadata["display_name"],
            "subscription_status": subscription_status,
            "is_active": is_active,
            "max_properties": features.get("max_properties", 1),
            "features": detailed_features,
            "feature_summary": {
                "total": len(detailed_features),
                "enabled": sum(1 for f in detailed_features.values() if f["enabled"]),
                "disabled": sum(1 for f in detailed_features.values() if not f["enabled"]),
            }
        }
    
    async def enforce_feature(
        self, 
        client_id: str, 
        feature: str,
        check_opt_in: bool = False
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Server-side enforcement of feature access.
        
        Returns:
            (is_allowed, error_message, error_details)
            
        If not allowed, returns error code PLAN_NOT_ELIGIBLE with details.
        """
        db = database.get_db()
        
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "billing_plan": 1, "subscription_status": 1}
        )
        
        if not client:
            return False, "Client not found", {"error_code": "CLIENT_NOT_FOUND"}
        
        # Check subscription is active
        subscription_status = client.get("subscription_status", "PENDING")
        if subscription_status != "ACTIVE":
            return False, f"Subscription is {subscription_status}. Active subscription required.", {
                "error_code": "SUBSCRIPTION_INACTIVE",
                "subscription_status": subscription_status
            }
        
        # Get plan
        plan_str = client.get("billing_plan", "PLAN_1")
        try:
            plan = BillingPlan(plan_str)
        except ValueError:
            plan = BillingPlan.PLAN_1
        
        # Check feature access
        is_allowed, message, upgrade_info = self.check_feature_access(plan, feature)
        
        if not is_allowed:
            return False, message, {
                "error_code": "PLAN_NOT_ELIGIBLE",
                "feature": feature,
                "upgrade_required": True,
                **(upgrade_info or {})
            }
        
        # Optional: Check opt-in requirements
        if check_opt_in:
            feature_info = self.get_feature_info(feature)
            if feature_info and feature_info.get("requires_opt_in"):
                # Check notification preferences for opt-in
                prefs = await db.notification_preferences.find_one(
                    {"client_id": client_id},
                    {"_id": 0}
                )
                
                if feature == "sms":
                    if not prefs or not prefs.get("sms_enabled"):
                        return False, "SMS not enabled in preferences", {
                            "error_code": "OPT_IN_REQUIRED",
                            "feature": feature
                        }
                    if feature_info.get("requires_verification") and not prefs.get("sms_phone_verified"):
                        return False, "SMS phone number not verified", {
                            "error_code": "VERIFICATION_REQUIRED",
                            "feature": feature
                        }
        
        return True, None, None
    
    def get_entitlement_matrix(self) -> Dict[str, Dict]:
        """Generate the complete feature entitlement matrix for documentation.
        
        Returns a dictionary suitable for display showing all features
        and their availability across all plans.
        """
        matrix = {}
        
        for feature_key, feature_info in FEATURE_REGISTRY.items():
            matrix[feature_key] = {
                "name": feature_info.get("name"),
                "description": feature_info.get("description"),
                "category": feature_info.get("category", "").value if feature_info.get("category") else None,
                "is_core": feature_info.get("is_core", False),
                "plans": {
                    "PLAN_1": PLAN_FEATURE_MATRIX[BillingPlan.PLAN_1].get(feature_key, False),
                    "PLAN_2_5": PLAN_FEATURE_MATRIX[BillingPlan.PLAN_2_5].get(feature_key, False),
                    "PLAN_6_15": PLAN_FEATURE_MATRIX[BillingPlan.PLAN_6_15].get(feature_key, False),
                }
            }
        
        return matrix


# Singleton instance
feature_entitlement_service = FeatureEntitlementService()
