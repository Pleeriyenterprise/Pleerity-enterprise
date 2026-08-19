"""
Lifecycle reminder template registry — Phase 4 S4.4.

Canonical mapping from attention_kind → notification template_key, email alias,
and customer-facing copy. Consumed by lifecycle_reminder_gates, seed definitions,
EmailService, and jobs subject lines.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from services.lifecycle_semantics_types import AttentionKind

ATTENTION_KINDS: Tuple[AttentionKind, ...] = (
    "CERTIFICATE_EXPIRING",
    "REVIEW_DUE",
    "EVENT_ACTION_REQUIRED",
    "TENANCY_TERM_ENDING",
    "OCCUPANCY_REVIEW_DUE",
    "OPERATIONAL_ACTION_REQUIRED",
)

_LEGACY_EMAIL_TEMPLATE = "COMPLIANCE_EXPIRY_REMINDER"
_LEGACY_SMS_TEMPLATE = "COMPLIANCE_EXPIRY_REMINDER_SMS"

_LIFECYCLE_REMINDER_SPECS: Dict[str, Dict[str, str]] = {
    "CERTIFICATE_EXPIRING": {
        "email_alias": "reminder",
        "header_title": "Compliance renewal reminder",
        "why_received": "compliance monitoring and expiry reminders are enabled for your account.",
        "intro_html": (
            "This is a reminder that <strong>{req_name}</strong> for your property at "
            "<strong>{prop_addr}</strong> is due on <strong>{due_date}</strong>."
        ),
        "intro_text": (
            "This is a reminder that {req_name} for your property at {prop_addr} "
            "is due on {due_date}."
        ),
        "subject_expiring": "Renewal reminder: {req_name} due soon",
        "subject_overdue": "Renewal reminder: {req_name} is overdue",
        "sms_body": "Pleerity: {{count}} compliance item(s) need attention. View: {{portal_link}}",
    },
    "REVIEW_DUE": {
        "email_alias": "lifecycle-reminder-review-due",
        "header_title": "Compliance review reminder",
        "why_received": "compliance monitoring and review reminders are enabled for your account.",
        "intro_html": (
            "This is a reminder that <strong>{req_name}</strong> for your property at "
            "<strong>{prop_addr}</strong> has a review due on <strong>{due_date}</strong>."
        ),
        "intro_text": (
            "This is a reminder that {req_name} for your property at {prop_addr} "
            "has a review due on {due_date}."
        ),
        "subject_expiring": "Review reminder: {req_name} due soon",
        "subject_overdue": "Review reminder: {req_name} is overdue",
        "sms_body": "Pleerity: {{count}} compliance review(s) need attention. View: {{portal_link}}",
    },
    "EVENT_ACTION_REQUIRED": {
        "email_alias": "lifecycle-reminder-event-action-required",
        "header_title": "Compliance action reminder",
        "why_received": "compliance monitoring and action reminders are enabled for your account.",
        "intro_html": (
            "This is a reminder that <strong>{req_name}</strong> for your property at "
            "<strong>{prop_addr}</strong> requires action by <strong>{due_date}</strong>."
        ),
        "intro_text": (
            "This is a reminder that {req_name} for your property at {prop_addr} "
            "requires action by {due_date}."
        ),
        "subject_expiring": "Action reminder: {req_name} due soon",
        "subject_overdue": "Action reminder: {req_name} is overdue",
        "sms_body": "Pleerity: {{count}} compliance action(s) need attention. View: {{portal_link}}",
    },
    "TENANCY_TERM_ENDING": {
        "email_alias": "lifecycle-reminder-tenancy-term-ending",
        "header_title": "Tenancy milestone reminder",
        "why_received": "compliance monitoring and tenancy reminders are enabled for your account.",
        "intro_html": (
            "This is a reminder that <strong>{req_name}</strong> for your property at "
            "<strong>{prop_addr}</strong> has a tenancy milestone on <strong>{due_date}</strong>."
        ),
        "intro_text": (
            "This is a reminder that {req_name} for your property at {prop_addr} "
            "has a tenancy milestone on {due_date}."
        ),
        "subject_expiring": "Tenancy reminder: {req_name} due soon",
        "subject_overdue": "Tenancy reminder: {req_name} is overdue",
        "sms_body": "Pleerity: {{count}} tenancy milestone(s) need attention. View: {{portal_link}}",
    },
    "OCCUPANCY_REVIEW_DUE": {
        "email_alias": "lifecycle-reminder-occupancy-review-due",
        "header_title": "Occupancy review reminder",
        "why_received": "compliance monitoring and occupancy review reminders are enabled for your account.",
        "intro_html": (
            "This is a reminder that <strong>{req_name}</strong> for your property at "
            "<strong>{prop_addr}</strong> has an occupancy review due on <strong>{due_date}</strong>."
        ),
        "intro_text": (
            "This is a reminder that {req_name} for your property at {prop_addr} "
            "has an occupancy review due on {due_date}."
        ),
        "subject_expiring": "Occupancy review reminder: {req_name} due soon",
        "subject_overdue": "Occupancy review reminder: {req_name} is overdue",
        "sms_body": "Pleerity: {{count}} occupancy review(s) need attention. View: {{portal_link}}",
    },
    "OPERATIONAL_ACTION_REQUIRED": {
        "email_alias": "lifecycle-reminder-operational-action-required",
        "header_title": "Operational action reminder",
        "why_received": "compliance monitoring and operational reminders are enabled for your account.",
        "intro_html": (
            "This is a reminder that <strong>{req_name}</strong> for your property at "
            "<strong>{prop_addr}</strong> requires your attention by <strong>{due_date}</strong>."
        ),
        "intro_text": (
            "This is a reminder that {req_name} for your property at {prop_addr} "
            "requires your attention by {due_date}."
        ),
        "subject_expiring": "Operational reminder: {req_name} due soon",
        "subject_overdue": "Operational reminder: {req_name} is overdue",
        "sms_body": "Pleerity: {{count}} operational item(s) need attention. View: {{portal_link}}",
    },
}


def lifecycle_reminder_email_template_key(attention_kind: str) -> str:
    return f"LIFECYCLE_REMINDER_{attention_kind}"


def lifecycle_reminder_sms_template_key(attention_kind: str) -> str:
    return f"{lifecycle_reminder_email_template_key(attention_kind)}_SMS"


def planned_email_template_by_attention() -> Dict[str, str]:
    return {kind: lifecycle_reminder_email_template_key(kind) for kind in ATTENTION_KINDS}


def planned_sms_template_by_attention() -> Dict[str, str]:
    return {kind: lifecycle_reminder_sms_template_key(kind) for kind in ATTENTION_KINDS}


def lifecycle_reminder_spec(attention_kind: Optional[str]) -> Dict[str, str]:
    kind = str(attention_kind or "CERTIFICATE_EXPIRING")
    legacy = dict(_LIFECYCLE_REMINDER_SPECS.get(kind, _LIFECYCLE_REMINDER_SPECS["CERTIFICATE_EXPIRING"]))
    try:
        from lifecycle_communication.headings import reminder_header_title
        from lifecycle_communication.resolver import resolve_customer_communication

        row = {"lifecycle_attention_kind": kind, "attention_kind": kind}
        comm = resolve_customer_communication(row, surface="reminder_email", channel="EMAIL")
        sv = comm.get("surface_variants") or {}
        legacy["header_title"] = reminder_header_title(kind)
        if sv.get("why_received"):
            legacy["why_received"] = str(sv["why_received"])
        if sv.get("intro_html"):
            legacy["intro_html"] = str(sv["intro_html"])
        if sv.get("intro_text"):
            legacy["intro_text"] = str(sv["intro_text"])
        if sv.get("sms_body"):
            legacy["sms_body"] = str(sv["sms_body"])
    except Exception:
        pass
    return legacy


def lifecycle_reminder_email_alias(attention_kind: Optional[str]) -> str:
    return lifecycle_reminder_spec(attention_kind)["email_alias"]


def is_lifecycle_reminder_email_alias(alias_str: str) -> bool:
    if alias_str == "reminder":
        return True
    return alias_str in frozenset(spec["email_alias"] for spec in _LIFECYCLE_REMINDER_SPECS.values())


def lifecycle_reminder_subject(
    *,
    attention_kind: Optional[str],
    requirement_name: str,
    is_overdue: bool,
    days_remaining: Optional[int] = None,
    requirement_code: Optional[str] = None,
) -> str:
    try:
        from lifecycle_communication.resolver import resolve_reminder_subject

        row = {
            "requirement_name": requirement_name,
            "requirement_code": requirement_code,
            "lifecycle_attention_kind": attention_kind,
            "attention_kind": attention_kind,
        }
        return resolve_reminder_subject(
            row,
            is_overdue=is_overdue,
            days_remaining=days_remaining,
        )
    except Exception:
        spec = lifecycle_reminder_spec(attention_kind)
        pattern = spec["subject_overdue"] if is_overdue else spec["subject_expiring"]
        return pattern.format(req_name=requirement_name)


def lifecycle_reminder_notification_seed_rows() -> List[Dict[str, Any]]:
    """Seed rows for S4.4 lifecycle reminder templates (EMAIL + SMS per attention_kind)."""
    rows: List[Dict[str, Any]] = []
    for kind in ATTENTION_KINDS:
        spec = _LIFECYCLE_REMINDER_SPECS[kind]
        rows.append(
            {
                "template_key": lifecycle_reminder_email_template_key(kind),
                "channel": "EMAIL",
                "email_template_alias": spec["email_alias"],
                "sms_body": None,
                "requires_provisioned": True,
                "requires_active_subscription": True,
                "requires_entitlement_enabled": True,
                "plan_required_feature_key": None,
                "email_category": "compliance_notifications",
                "is_active": True,
            }
        )
        rows.append(
            {
                "template_key": lifecycle_reminder_sms_template_key(kind),
                "channel": "SMS",
                "email_template_alias": None,
                "sms_body": spec["sms_body"],
                "requires_provisioned": True,
                "requires_active_subscription": True,
                "requires_entitlement_enabled": True,
                "plan_required_feature_key": "sms_reminders",
                "is_active": True,
            }
        )
    return rows


def all_lifecycle_reminder_template_keys() -> FrozenSet[str]:
    keys: List[str] = []
    for kind in ATTENTION_KINDS:
        keys.append(lifecycle_reminder_email_template_key(kind))
        keys.append(lifecycle_reminder_sms_template_key(kind))
    return frozenset(keys)


def legacy_reminder_template_keys() -> Tuple[str, str]:
    return _LEGACY_EMAIL_TEMPLATE, _LEGACY_SMS_TEMPLATE
