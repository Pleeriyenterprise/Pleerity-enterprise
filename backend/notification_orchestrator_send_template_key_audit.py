"""
L-008e — audited ``template_key`` string literals passed to ``notification_orchestrator.send``.

**Governance:** Every production ``template_key="..."`` on ``notification_orchestrator.send`` must exist in
``notification_template_seed_definitions`` so DB seed / Postmark alias wiring cannot drift silently.

**Maintenance:** When adding a new orchestrator send with a string literal ``template_key``, add the key
here and add the row to ``CORE_NOTIFICATION_TEMPLATE_SEED_DEFINITIONS`` or
``ADMIN_CLIENT_COMMUNICATION_NOTIFICATION_SEED_DEFINITIONS``. CI enforces
``PRODUCTION_ORCHESTRATOR_SEND_TEMPLATE_KEY_LITERALS`` ⊆ ``all_notification_template_keys_from_seed()``.

**Out of scope for this frozenset:** dynamic ``template_key=`` variables (e.g. onboarding queue uses
``get_template_key_for_event`` — covered by ``tests/test_l008_orchestrator_template_seed_contract.py`` on
``EMAIL_EVENTS``).
"""

from __future__ import annotations

from typing import FrozenSet

# grep: template_key\s*=\s*["'][A-Z0-9_]+["'] across backend/**/*.py excluding tests/ (periodic re-audit).
PRODUCTION_ORCHESTRATOR_SEND_TEMPLATE_KEY_LITERALS: FrozenSet[str] = frozenset(
    {
        "ACTIVATION_REMINDER",
        "ADMIN_INVITE",
        "ADMIN_MANUAL",
        "ADMIN_MANUAL_SMS",
        "AI_EXTRACTION_APPLIED",
        "AUTH_ACCOUNT_LOCKED",
        "AUTH_ADMIN_MFA_CODE",
        "AUTH_LOGIN_RECOVERED",
        "CLEARFORM_WELCOME",
        "CLIENT_INVOICE_REVIEW_REQUIRED",
        "CLIENT_PROOF_UPLOADED",
        "CLIENT_QUOTE_REVIEW_REQUIRED",
        "COMPLIANCE_ALERT",
        "COMPLIANCE_EXPIRY_REMINDER",
        "COMPLIANCE_EXPIRY_REMINDER_SMS",
        "COMPLIANCE_SLA_ALERT",
        "CONTRACTOR_ASSIGNED",
        "CONTRACTOR_INVOICE_READY",
        "CONTRACTOR_JOB_ASSIGNMENT_QUOTE_REQUIRED",
        "CONTRACTOR_PROOF_REQUIRED",
        "CONTRACTOR_QUOTE_APPROVED",
        "CONTRACTOR_VISIT_CONFIRMED",
        "CUSTOM_NOTIFICATION",
        "DASHBOARD_READY",
        "ENABLEMENT_DELIVERY",
        "INTERNAL_ALERT",
        "LEAD_FOLLOWUP",
        "LEAD_HIGH_INTENT_ADMIN",
        "LEAD_MANUAL_MESSAGE",
        "LEAD_SLA_BREACH_ADMIN",
        "LEAD_TRANSACTIONAL_RISK_CHECK_COMPLETED",
        "MONTHLY_DIGEST",
        "ORDER_CONFIRMATION",
        "ORDER_DOCUMENTS_READY",
        "ORDER_INFO_REQUEST",
        "ORDER_NOTIFICATION",
        "OPS_ALERT_NOTIFICATION_SPIKE",
        "OTP_CODE_SMS",
        "PARTNERSHIP_ACK",
        "PASSWORD_RESET",
        "PAYMENT_FAILED",
        "PENDING_VERIFICATION_DIGEST",
        "PROVISIONING_FAILED_ADMIN",
        "SCHEDULED_REPORT",
        "STRIPE_WEBHOOK_FAILURE_ADMIN",
        "SUBSCRIPTION_CANCELED",
        "SUBSCRIPTION_CONFIRMED",
        "SUBSCRIPTION_GRACE_REMINDER",
        "SUBSCRIPTION_RENEWAL_REMINDER_3D",
        "SUBSCRIPTION_RENEWAL_REMINDER_7D",
        "SUBSCRIPTION_RENEWAL_PAID",
        "SUPPORT_INTERNAL_NOTIFICATION",
        "SUPPORT_TICKET_CONFIRMATION",
        "TENANT_INVITE",
        "WELCOME_EMAIL",
    }
)
