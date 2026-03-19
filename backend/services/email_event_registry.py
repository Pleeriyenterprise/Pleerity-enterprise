"""
Centralized lifecycle email event registry.
Maps lifecycle event IDs to template_key (used by notification_orchestrator) and category.
This is the single source of truth for "which email events exist"; actual send rules
remain in notification_templates (DB). Do not duplicate gating logic here.
"""
from typing import Any, Dict, Optional

# Event ID -> { category, template_key, trigger }
# template_key must exist in notification_templates (seeded in database.py).
EMAIL_EVENTS: Dict[str, Dict[str, Any]] = {
    # --- ACCOUNT EVENTS (system_critical) ---
    "ACCOUNT_VERIFICATION": {
        "category": "system_critical",
        "template_key": "WELCOME_EMAIL",
        "trigger": "user_signup; provisioning_runner after PROVISIONING_COMPLETED",
    },
    "WELCOME_EMAIL": {
        "category": "system_critical",
        "template_key": "WELCOME_EMAIL",
        "trigger": "portal ready / password setup link sent",
    },
    "PASSWORD_RESET": {
        "category": "system_critical",
        "template_key": "PASSWORD_RESET",
        "trigger": "password_reset_requested; auth forgot-password",
    },
    "PASSWORD_CHANGED_CONFIRMATION": {
        "category": "system_critical",
        "template_key": "PASSWORD_CHANGED_CONFIRMATION",
        "trigger": "password_successfully_updated (e.g. profile change-password)",
    },
    # --- PORTAL ACCESS EVENTS ---
    "PORTAL_INVITATION_ADMIN": {
        "category": "system_critical",
        "template_key": "ADMIN_INVITE",
        "trigger": "admin invites another user to portal",
    },
    "PORTAL_INVITATION_TENANT": {
        "category": "system_critical",
        "template_key": "TENANT_INVITE",
        "trigger": "client invites tenant to portal",
    },
    "ACCESS_GRANTED": {
        "category": "internal",
        "template_key": "ADMIN_MANUAL",
        "trigger": "permissions_change (template ready; trigger when implemented)",
    },
    "ACCESS_REVOKED": {
        "category": "internal",
        "template_key": "ADMIN_MANUAL",
        "trigger": "access_removed (template ready; trigger when implemented)",
    },
    # --- COMPLIANCE MONITORING EVENTS ---
    "CERTIFICATE_EXPIRY_REMINDER": {
        "category": "compliance_notifications",
        "template_key": "COMPLIANCE_EXPIRY_REMINDER",
        "trigger": "compliance_engine; jobs send_daily_reminders",
    },
    "CERTIFICATE_OVERDUE": {
        "category": "compliance_notifications",
        "template_key": "COMPLIANCE_EXPIRY_REMINDER",
        "trigger": "same reminder email includes overdue items",
    },
    "COMPLIANCE_RISK_ALERT": {
        "category": "compliance_notifications",
        "template_key": "COMPLIANCE_ALERT",
        "trigger": "compliance status change; jobs check_compliance_status_changes",
    },
    "COMPLIANCE_SCORE_UPDATE": {
        "category": "compliance_notifications",
        "template_key": "COMPLIANCE_SCORE_UPDATE",
        "trigger": "compliance_score_recalculated (template ready; trigger when implemented)",
    },
    "DOCUMENT_MISSING_ALERT": {
        "category": "compliance_notifications",
        "template_key": "DOCUMENT_MISSING_ALERT",
        "trigger": "required_documents_missing (template ready; trigger when implemented)",
    },
    # --- DOCUMENT VAULT EVENTS ---
    "DOCUMENT_UPLOADED_CONFIRMATION": {
        "category": "compliance_notifications",
        "template_key": "AI_EXTRACTION_APPLIED",
        "trigger": "certificate_uploaded; AI extraction applied",
    },
    "DOCUMENT_REPLACED": {
        "category": "compliance_notifications",
        "template_key": "ADMIN_MANUAL",
        "trigger": "certificate_replaced (template ready; trigger when implemented)",
    },
    # --- REPORTING EVENTS ---
    "DAILY_COMPLIANCE_REPORT": {
        "category": "reporting_notifications",
        "template_key": "SCHEDULED_REPORT",
        "trigger": "scheduler; report schedule frequency daily",
    },
    "WEEKLY_PORTFOLIO_REPORT": {
        "category": "reporting_notifications",
        "template_key": "SCHEDULED_REPORT",
        "trigger": "scheduler; report schedule frequency weekly",
    },
    "MONTHLY_PORTFOLIO_SUMMARY": {
        "category": "reporting_notifications",
        "template_key": "MONTHLY_DIGEST",
        "trigger": "scheduler; jobs monthly digest",
    },
    "RENEWAL_REMINDER": {
        "category": "reporting_notifications",
        "template_key": "RENEWAL_REMINDER",
        "trigger": "scheduler; jobs send_renewal_reminders",
    },
    # --- LANDLORD ONBOARDING SEQUENCE (7-day behaviour-aware) ---
    "ONBOARDING_DAY0_WELCOME": {
        "category": "reporting_notifications",
        "template_key": "ONBOARDING_DAY0_WELCOME",
        "trigger": "after password set: onboarding_lifecycle_service then onboarding_sequence_processing",
    },
    "ONBOARDING_DAY1_SETUP_REMINDER": {
        "category": "reporting_notifications",
        "template_key": "ONBOARDING_DAY1_SETUP_REMINDER",
        "trigger": "onboarding_sequence_processing",
    },
    "ONBOARDING_DAY2_COMPLIANCE_EDUCATION": {
        "category": "reporting_notifications",
        "template_key": "ONBOARDING_DAY2_COMPLIANCE_EDUCATION",
        "trigger": "onboarding_sequence_processing",
    },
    "ONBOARDING_DAY3_PRODUCT_VALUE": {
        "category": "reporting_notifications",
        "template_key": "ONBOARDING_DAY3_PRODUCT_VALUE",
        "trigger": "onboarding_sequence_processing",
    },
    "ONBOARDING_DAY4_DOCUMENT_PACK_INTRO": {
        "category": "reporting_notifications",
        "template_key": "ONBOARDING_DAY4_DOCUMENT_PACK_INTRO",
        "trigger": "onboarding_sequence_processing",
    },
    "ONBOARDING_DAY5_RISK_AWARENESS": {
        "category": "reporting_notifications",
        "template_key": "ONBOARDING_DAY5_RISK_AWARENESS",
        "trigger": "onboarding_sequence_processing",
    },
    "ONBOARDING_DAY6_CASE_EXAMPLE": {
        "category": "reporting_notifications",
        "template_key": "ONBOARDING_DAY6_CASE_EXAMPLE",
        "trigger": "onboarding_sequence_processing",
    },
    "ONBOARDING_DAY7_ACTIVATION_PUSH": {
        "category": "reporting_notifications",
        "template_key": "ONBOARDING_DAY7_ACTIVATION_PUSH",
        "trigger": "onboarding_sequence_processing",
    },
    # --- DOCUMENT PACK PURCHASE EVENTS ---
    "DOCUMENT_PACK_ORDER_CONFIRMATION": {
        "category": "compliance_notifications",
        "template_key": "ORDER_NOTIFICATION",
        "trigger": "customer_purchases_document_pack; order_service / order_notification_service",
    },
    "INTAKE_ORDER_CONFIRMATION": {
        "category": "system_critical",
        "template_key": "ORDER_CONFIRMATION",
        "trigger": "intake_draft_service._send_order_confirmation_email after draft→order payment",
    },
    "DOCUMENT_PACK_DELIVERY": {
        "category": "system_critical",
        "template_key": "ORDER_DELIVERED",
        "trigger": "order_delivery_service when documents ready",
    },
    # --- BILLING EVENTS ---
    "SUBSCRIPTION_STARTED": {
        "category": "system_critical",
        "template_key": "SUBSCRIPTION_CONFIRMED",
        "trigger": "stripe checkout.session.completed (structured payment receipt; no dashboard link)",
    },
    "DASHBOARD_READY_MILESTONE": {
        "category": "system_critical",
        "template_key": "DASHBOARD_READY",
        "trigger": "auth set_password success (client); then schedule_onboarding_sequence",
    },
    "ACTIVATION_REMINDER_CLIENT": {
        "category": "system_critical",
        "template_key": "ACTIVATION_REMINDER",
        "trigger": "activation_reminder_processing job if activation sent and password not set",
    },
    "PAYMENT_SUCCESS": {
        "category": "system_critical",
        "template_key": "SUBSCRIPTION_CONFIRMED",
        "trigger": "stripe payment success / receipt",
    },
    "PAYMENT_FAILED": {
        "category": "system_critical",
        "template_key": "PAYMENT_FAILED",
        "trigger": "stripe invoice.payment_failed",
    },
    "INVOICE_AVAILABLE": {
        "category": "system_critical",
        "template_key": "INVOICE_AVAILABLE",
        "trigger": "invoice_available (template ready; trigger when implemented)",
    },
    "SUBSCRIPTION_CANCELLED": {
        "category": "system_critical",
        "template_key": "SUBSCRIPTION_CANCELED",
        "trigger": "stripe subscription.deleted",
    },
    # --- SUPPORT EVENTS ---
    "SUPPORT_TICKET_CREATED": {
        "category": "internal",
        "template_key": "SUPPORT_TICKET_CONFIRMATION",
        "trigger": "support_email_service send_ticket_confirmation_email",
    },
    "SUPPORT_TICKET_UPDATED": {
        "category": "internal",
        "template_key": "SUPPORT_TICKET_UPDATED",
        "trigger": "support_ticket_updated (template ready; trigger when implemented)",
    },
    "SUPPORT_TICKET_RESOLVED": {
        "category": "internal",
        "template_key": "SUPPORT_TICKET_RESOLVED",
        "trigger": "support_ticket_resolved (template ready; trigger when implemented)",
    },
    # --- MARKETING EVENTS ---
    "FEATURE_ANNOUNCEMENT": {
        "category": "marketing_notifications",
        "template_key": "FEATURE_ANNOUNCEMENT",
        "trigger": "feature_announcement (template ready; trigger when implemented)",
    },
    "PRODUCT_UPDATE": {
        "category": "marketing_notifications",
        "template_key": "PRODUCT_UPDATE",
        "trigger": "product_update (template ready; trigger when implemented)",
    },
    # --- INTERNAL / OPS (no customer preference check) ---
    "PENDING_VERIFICATION_DIGEST": {
        "category": "internal",
        "template_key": "PENDING_VERIFICATION_DIGEST",
        "trigger": "jobs send_pending_verification_digest",
    },
    "CLEARFORM_WELCOME": {
        "category": "system_critical",
        "template_key": "CLEARFORM_WELCOME",
        "trigger": "clearform signup",
    },
}


def get_template_key_for_event(event_id: str) -> Optional[str]:
    """Return template_key for a lifecycle event_id. Used by callers that prefer event_id over template_key."""
    entry = EMAIL_EVENTS.get(event_id)
    if entry:
        return entry.get("template_key")
    return None


def get_category_for_event(event_id: str) -> Optional[str]:
    """Return email_category for a lifecycle event_id."""
    entry = EMAIL_EVENTS.get(event_id)
    if entry:
        return entry.get("category")
    return None


def get_category_for_template_key(template_key: str) -> Optional[str]:
    """Return email_category for a template_key by finding first event that uses it."""
    for entry in EMAIL_EVENTS.values():
        if entry.get("template_key") == template_key:
            return entry.get("category")
    return None


# Ordered event IDs for the landlord onboarding sequence (Day 0 .. Day 7).
LANDLORD_ONBOARDING_EVENT_IDS = [
    "ONBOARDING_DAY0_WELCOME",
    "ONBOARDING_DAY1_SETUP_REMINDER",
    "ONBOARDING_DAY2_COMPLIANCE_EDUCATION",
    "ONBOARDING_DAY3_PRODUCT_VALUE",
    "ONBOARDING_DAY4_DOCUMENT_PACK_INTRO",
    "ONBOARDING_DAY5_RISK_AWARENESS",
    "ONBOARDING_DAY6_CASE_EXAMPLE",
    "ONBOARDING_DAY7_ACTIVATION_PUSH",
]
