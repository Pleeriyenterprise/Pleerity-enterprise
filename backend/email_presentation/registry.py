"""Email Presentation Registry — metadata for every customer EMAIL template_key."""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional

from notification_template_seed_definitions import (
    ADMIN_CLIENT_COMMUNICATION_NOTIFICATION_SEED_DEFINITIONS,
    CORE_NOTIFICATION_TEMPLATE_SEED_DEFINITIONS,
)
from services.email_template_runtime_metadata import _HYBRID_ALIASES, _UNCONDITIONAL_CODE_BUILT

from email_presentation.constants import (
    AUTHORITY_VERSION,
    BRAND_PROFILE,
    COLOUR_PROFILE,
    CTA_PROFILE,
    FOOTER_VERSION,
    GREETING_STYLE,
    SHELL_VERSION,
)

_INTERNAL_TEMPLATE_KEYS = frozenset(
    {
        "INTERNAL_ALERT",
        "LEAD_SLA_BREACH_ADMIN",
        "LEAD_HIGH_INTENT_ADMIN",
        "PROVISIONING_FAILED_ADMIN",
        "STRIPE_WEBHOOK_FAILURE_ADMIN",
        "OPS_ALERT_NOTIFICATION_SPIKE",
        "COMPLIANCE_SLA_ALERT",
        "PENDING_VERIFICATION_DIGEST",
        "AUTH_ADMIN_MFA_CODE",
        "SUPPORT_INTERNAL_NOTIFICATION",
        "AUTH_ACCOUNT_LOCKED",
        "AUTH_LOGIN_RECOVERED",
    }
)

_PRESENTATION_FAMILY = {
    "compliance_status": {
        "COMPLIANCE_ALERT",
        "ORDER_NOTIFICATION",
    },
    "document_lifecycle": {
        "ENABLEMENT_DELIVERY",
        "AI_EXTRACTION_APPLIED",
        "DOCUMENT_MISSING_ALERT",
    },
    "compliance_gap": {"LEAD_FOLLOWUP"},
    "digest": {"MONTHLY_DIGEST", "SCHEDULED_REPORT", "PENDING_VERIFICATION_DIGEST"},
    "renewal": {"RENEWAL_REMINDER", "COMPLIANCE_EXPIRY_REMINDER", "LIFECYCLE_REMINDER_CERTIFICATE_EXPIRING"},
    "onboarding": {
        "ONBOARDING_DAY0_WELCOME",
        "ONBOARDING_DAY1_SETUP_REMINDER",
        "ONBOARDING_DAY2_COMPLIANCE_EDUCATION",
        "ONBOARDING_DAY3_PRODUCT_VALUE",
        "ONBOARDING_DAY4_DOCUMENT_PACK_INTRO",
        "ONBOARDING_DAY5_RISK_AWARENESS",
        "ONBOARDING_DAY6_CASE_EXAMPLE",
        "ONBOARDING_DAY7_ACTIVATION_PUSH",
        "WELCOME_EMAIL",
        "DASHBOARD_READY",
        "ACTIVATION_REMINDER",
    },
    "auth_account": {"PASSWORD_RESET", "PASSWORD_CHANGED_CONFIRMATION", "WELCOME_EMAIL"},
    "invite": {"TENANT_INVITE", "ADMIN_INVITE", "PILOT_INVITE_SEND"},
    "billing": {
        "SUBSCRIPTION_CONFIRMED",
        "SUBSCRIPTION_RENEWAL_PAID",
        "PAYMENT_FAILED",
        "SUBSCRIPTION_CANCELED",
        "SUBSCRIPTION_RENEWAL_REMINDER_3D",
        "SUBSCRIPTION_RENEWAL_REMINDER_7D",
        "SUBSCRIPTION_GRACE_REMINDER",
    },
    "contractor_ops": {
        "CONTRACTOR_JOB_ASSIGNMENT_QUOTE_REQUIRED",
        "CONTRACTOR_QUOTE_APPROVED",
        "CONTRACTOR_VISIT_CONFIRMED",
        "CONTRACTOR_PROOF_REQUIRED",
        "CONTRACTOR_INVOICE_READY",
        "CLIENT_QUOTE_REVIEW_REQUIRED",
        "CLIENT_PROOF_UPLOADED",
        "CLIENT_INVOICE_REVIEW_REQUIRED",
    },
    "risk_lead": {"LEAD_FOLLOWUP", "LEAD_TRANSACTIONAL_RISK_CHECK_COMPLETED"},
    "admin_manual": {"ADMIN_MANUAL", "CUSTOM_NOTIFICATION", "RENT_REMINDER"},
    "operational_notice": {"ADMIN_CLIENT_COMMUNICATION_CRITICAL", "ADMIN_CLIENT_COMMUNICATION_ANNOUNCEMENT"},
}

# Flatten family lookup
_FAMILY_BY_KEY: Dict[str, str] = {}
for fam, keys in _PRESENTATION_FAMILY.items():
    for k in keys:
        _FAMILY_BY_KEY[k] = fam


def _shell_class_for_alias(alias: str) -> str:
    if alias in _UNCONDITIONAL_CODE_BUILT:
        return "canonical_code_built"
    if alias in _HYBRID_ALIASES:
        return "hybrid"
    if alias == "admin-manual":
        return "legacy_or_canonical_fragment"
    if alias == "internal-alert":
        return "internal"
    return "db_first_canonical_fallback"


def _registry_row(seed_row: Dict[str, Any]) -> Dict[str, Any]:
    tk = str(seed_row["template_key"])
    alias = str(seed_row.get("email_template_alias") or "")
    family = _FAMILY_BY_KEY.get(tk, "general_customer")
    return {
        "template_key": tk,
        "email_template_alias": alias,
        "presentation_family": family,
        "shell_version": SHELL_VERSION,
        "greeting_style": GREETING_STYLE,
        "footer_version": FOOTER_VERSION,
        "colour_profile": COLOUR_PROFILE if family in ("compliance_status", "renewal", "digest") else None,
        "cta_profile": CTA_PROFILE,
        "brand_profile": BRAND_PROFILE,
        "authority_version": AUTHORITY_VERSION,
        "shell_class": _shell_class_for_alias(alias),
        "production_facing": tk not in _INTERNAL_TEMPLATE_KEYS,
        "is_active_seed": bool(seed_row.get("is_active", True)),
        "email_category": seed_row.get("email_category"),
    }


def iter_registry_entries() -> Iterator[Dict[str, Any]]:
    rows = CORE_NOTIFICATION_TEMPLATE_SEED_DEFINITIONS + ADMIN_CLIENT_COMMUNICATION_NOTIFICATION_SEED_DEFINITIONS
    for row in sorted(rows, key=lambda r: r["template_key"]):
        if row.get("channel") != "EMAIL":
            continue
        yield _registry_row(row)


def get_registry_entry(template_key: str) -> Optional[Dict[str, Any]]:
    for entry in iter_registry_entries():
        if entry["template_key"] == template_key:
            return entry
    return None


def registry_as_list() -> List[Dict[str, Any]]:
    return list(iter_registry_entries())
