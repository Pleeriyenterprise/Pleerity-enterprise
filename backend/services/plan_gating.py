"""Plan Gating Service - Enforce feature access based on subscription plan.

This service provides server-side enforcement of plan-based feature gating.
All gated features must check plan eligibility before execution.
"""
from typing import Dict, List, Optional, Tuple
from models import BillingPlan
from database import database
import logging

logger = logging.getLogger(__name__)

# Define which features are available per plan
PLAN_FEATURES = {
    BillingPlan.PLAN_1: {
        "max_properties": 1,
        "sms_reminders": False,
        "webhooks": False,
        "advanced_reports": False,  # PDF/CSV downloads
        "bulk_upload": True,  # Basic bulk upload
        "zip_upload": False,
        "compliance_packs": False,
        "integrations": False,
        "api_access": False,
        "priority_support": False,
        "ai_assistant": True,  # All plans get basic assistant
        "scheduled_reports": False
    },
    BillingPlan.PLAN_2_5: {
        "max_properties": 5,
        "sms_reminders": True,
        "webhooks": False,
        "advanced_reports": True,
        "bulk_upload": True,
        "zip_upload": False,
        "compliance_packs": False,
        "integrations": False,
        "api_access": False,
        "priority_support": True,
        "ai_assistant": True,
        "scheduled_reports": True
    },
    BillingPlan.PLAN_6_15: {
        "max_properties": 15,
        "sms_reminders": True,
        "webhooks": True,
        "advanced_reports": True,
        "bulk_upload": True,
        "zip_upload": True,
        "compliance_packs": True,
        "integrations": True,
        "api_access": True,
        "priority_support": True,
        "ai_assistant": True,
        "scheduled_reports": True
    }
}

# Human-readable feature names for error messages
FEATURE_NAMES = {
    "sms_reminders": "SMS Reminders",
    "webhooks": "Webhook Integrations",
    "advanced_reports": "Advanced Reports (PDF/CSV)",
    "bulk_upload": "Bulk Document Upload",
    "zip_upload": "ZIP File Upload",
    "compliance_packs": "Compliance Packs",
    "integrations": "Third-party Integrations",
    "api_access": "API Access",
    "priority_support": "Priority Support",
    "scheduled_reports": "Scheduled Report Delivery"
}

# Minimum plan required for each feature
MINIMUM_PLAN_FOR_FEATURE = {
    "sms_reminders": BillingPlan.PLAN_2_5,
    "webhooks": BillingPlan.PLAN_6_15,
    "advanced_reports": BillingPlan.PLAN_2_5,
    "zip_upload": BillingPlan.PLAN_6_15,
    "compliance_packs": BillingPlan.PLAN_6_15,
    "integrations": BillingPlan.PLAN_6_15,
    "api_access": BillingPlan.PLAN_6_15,
    "scheduled_reports": BillingPlan.PLAN_2_5
}


class PlanGatingError(Exception):
    """Custom exception for plan gating violations."""
    def __init__(self, feature: str, current_plan: str, required_plan: str):
        self.feature = feature
        self.current_plan = current_plan
        self.required_plan = required_plan
        self.message = f"Feature '{FEATURE_NAMES.get(feature, feature)}' requires {required_plan} plan or higher. Current plan: {current_plan}"
        super().__init__(self.message)


class PlanGatingService:
    """Service to check and enforce plan-based feature access."""
    
    def get_plan_features(self, plan: BillingPlan) -> Dict:
        """Get all features available for a plan."""
        return PLAN_FEATURES.get(plan, PLAN_FEATURES[BillingPlan.PLAN_1])
    
    def is_feature_available(self, plan: BillingPlan, feature: str) -> bool:
        """Check if a specific feature is available for the given plan."""
        features = self.get_plan_features(plan)
        return features.get(feature, False)
    
    def check_feature_access(self, plan: BillingPlan, feature: str) -> Tuple[bool, Optional[str]]:
        """
        Check if feature is accessible and return upgrade message if not.
        
        Returns:
            (is_allowed, upgrade_message)
        """
        if self.is_feature_available(plan, feature):
            return True, None
        
        min_plan = MINIMUM_PLAN_FOR_FEATURE.get(feature)
        feature_name = FEATURE_NAMES.get(feature, feature)
        
        if min_plan:
            plan_name = self._get_plan_name(min_plan)
            return False, f"{feature_name} requires {plan_name} plan or higher"
        
        return False, f"{feature_name} is not available on your current plan"
    
    def _get_plan_name(self, plan: BillingPlan) -> str:
        """Get human-readable plan name."""
        names = {
            BillingPlan.PLAN_1: "Starter",
            BillingPlan.PLAN_2_5: "Growth",
            BillingPlan.PLAN_6_15: "Portfolio"
        }
        return names.get(plan, str(plan))
    
    async def get_client_plan_info(self, client_id: str) -> Dict:
        """Get full plan information for a client including features and limits."""
        db = database.get_db()
        
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "billing_plan": 1, "subscription_status": 1}
        )
        
        if not client:
            return {
                "plan": BillingPlan.PLAN_1.value,
                "plan_name": "Starter",
                "subscription_status": "UNKNOWN",
                "features": PLAN_FEATURES[BillingPlan.PLAN_1],
                "is_active": False
            }
        
        plan_str = client.get("billing_plan", "PLAN_1")
        try:
            plan = BillingPlan(plan_str)
        except ValueError:
            plan = BillingPlan.PLAN_1
        
        subscription_status = client.get("subscription_status", "PENDING")
        is_active = subscription_status == "ACTIVE"
        
        return {
            "plan": plan.value,
            "plan_name": self._get_plan_name(plan),
            "subscription_status": subscription_status,
            "features": self.get_plan_features(plan),
            "is_active": is_active
        }
    
    async def enforce_feature(self, client_id: str, feature: str) -> Tuple[bool, Optional[str]]:
        """
        Server-side enforcement of feature access.
        
        Returns:
            (is_allowed, error_message)
            
        If not allowed, error_message contains the reason.
        """
        db = database.get_db()
        
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "billing_plan": 1, "subscription_status": 1}
        )
        
        if not client:
            return False, "Client not found"
        
        # Check subscription is active
        subscription_status = client.get("subscription_status", "PENDING")
        if subscription_status != "ACTIVE":
            return False, f"Subscription is {subscription_status}. Active subscription required."
        
        # Get plan
        plan_str = client.get("billing_plan", "PLAN_1")
        try:
            plan = BillingPlan(plan_str)
        except ValueError:
            plan = BillingPlan.PLAN_1
        
        # Check feature access
        return self.check_feature_access(plan, feature)
    
    async def can_send_notification(self, client_id: str, notification_type: str) -> Tuple[bool, Optional[str]]:
        """
        Check if notifications can be sent to this client.
        
        Verifies:
        1. Subscription is active
        2. Feature (e.g., SMS) is available on plan
        3. User has opted in to this notification type
        """
        db = database.get_db()
        
        # Get client
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "billing_plan": 1, "subscription_status": 1}
        )
        
        if not client:
            return False, "Client not found"
        
        # Must have active subscription
        if client.get("subscription_status") != "ACTIVE":
            return False, "Subscription not active"
        
        # Get plan
        plan_str = client.get("billing_plan", "PLAN_1")
        try:
            plan = BillingPlan(plan_str)
        except ValueError:
            plan = BillingPlan.PLAN_1
        
        # Check SMS specifically
        if notification_type == "sms":
            if not self.is_feature_available(plan, "sms_reminders"):
                return False, "SMS reminders not available on current plan"
            
            # Check if user opted in
            prefs = await db.notification_preferences.find_one(
                {"client_id": client_id},
                {"_id": 0, "sms_enabled": 1, "sms_phone_verified": 1}
            )
            
            if not prefs or not prefs.get("sms_enabled"):
                return False, "SMS not enabled in preferences"
            
            if not prefs.get("sms_phone_verified"):
                return False, "SMS phone not verified"
        
        return True, None


# Singleton instance
plan_gating_service = PlanGatingService()
