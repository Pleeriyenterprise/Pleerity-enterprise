"""
Admin-only documentation of how each email_template_alias is resolved at runtime.

Aligned with notification_orchestrator._render_email ordering (DB vs code-built paths).
`template_key` ↔ `email_template_alias` comes from `notification_template_seed_definitions` only.
Does not affect sending or rendering — metadata for UI and guardrails only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from notification_template_seed_definitions import email_template_keys_by_alias_from_notification_seed


def template_keys_by_alias() -> Dict[str, List[str]]:
    """Alias → sorted template_keys from canonical notification seed definitions."""
    return email_template_keys_by_alias_from_notification_seed()


TEMPLATE_KEYS_BY_ALIAS: Dict[str, List[str]] = email_template_keys_by_alias_from_notification_seed()

# Aliases where orchestrator always takes a code path before the DB row is consulted.
_UNCONDITIONAL_CODE_BUILT = frozenset(
    {
        "activation-reminder",
        "monthly-digest",
        "client-operational-notice",
        "client-quote-review-required",
        "client-proof-uploaded",
        "client-invoice-review-required",
        "contractor-job-assignment-quote-required",
        "contractor-quote-approved",
        "contractor-visit-confirmed",
        "contractor-proof-required",
        "contractor-invoice-ready",
        "reminder",
        "lifecycle-reminder-review-due",
        "lifecycle-reminder-event-action-required",
        "lifecycle-reminder-tenancy-term-ending",
        "lifecycle-reminder-occupancy-review-due",
        "lifecycle-reminder-operational-action-required",
        "payment-failed",
        "subscription-canceled",
    }
)

# Aliases with conditional bypass / dominant non-DB behaviour documented in orchestrator.
_HYBRID_ALIASES = frozenset(
    {
        "payment-receipt",
        "portal-ready",
        "scheduled-report",
        "order-intake-confirmation",
    }
)


def _core_row(
    *,
    runtime_source: str,
    admin_editable: bool,
    edit_risk_level: str,
    runtime_notes: str,
    attachment_policy: str,
    legal_or_financial_flow: bool,
    recommended_admin_action: str,
    db_visible_at_runtime: bool,
    placeholders_hint: str,
    tests_covering: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "runtime_source": runtime_source,
        "admin_editable": admin_editable,
        "edit_risk_level": edit_risk_level,
        "runtime_notes": runtime_notes,
        "attachment_policy": attachment_policy,
        "legal_or_financial_flow": legal_or_financial_flow,
        "uses_template_versioning": False,
        "stores_rendered_snapshot": False,
        "recommended_admin_action": recommended_admin_action,
        "db_visible_at_runtime": db_visible_at_runtime,
        "changes_affect_future_sends_only": True,
        "past_sent_emails_note": (
            "Sent messages are logged with template_key and provider metadata; "
            "full rendered HTML is not versioned as immutable snapshots in this system."
        ),
        "delivery_log_coverage": (
            "message_logs / notification audit typically record template_key, recipient, "
            "and Postmark identifiers where applicable — not guaranteed full-body archival."
        ),
        "runtime_sender_service": "notification_orchestrator → Postmark (sender per environment configuration)",
        "placeholders_hint": placeholders_hint,
        "tests_covering": tests_covering or [],
    }


def _for_alias(alias: str) -> Dict[str, Any]:
    if alias in _UNCONDITIONAL_CODE_BUILT:
        return _core_row(
            runtime_source="code_built",
            admin_editable=False,
            edit_risk_level="immutable",
            runtime_notes=(
                "notification_orchestrator always renders this alias via EmailService before "
                "reading email_templates. An active DB row is not used for body/subject at send time."
            ),
            attachment_policy="Flow-dependent (see product docs); admin preview does not validate attachments.",
            legal_or_financial_flow=(
                alias in {"payment-failed", "subscription-canceled"}
                or alias.startswith("client-")
                or alias.startswith("contractor-")
            ),
            recommended_admin_action="Do not edit DB template for runtime copy; use engineering change requests for layout.",
            db_visible_at_runtime=False,
            placeholders_hint="Built-in layout placeholders (EmailService); DB available_variables do not drive production.",
            tests_covering=["backend/tests/test_notification_orchestrator.py (when exercised for this family)"],
        )
    if alias == "payment-receipt":
        return _core_row(
            runtime_source="hybrid",
            admin_editable=False,
            edit_risk_level="high",
            runtime_notes=(
                "Subscription receipts with payment_receipt_layout=structured use the canonical code-built layout. "
                "Other contexts may still resolve an active DB row first."
            ),
            attachment_policy="Usually none from template; invoices/receipts may attach upstream of template render.",
            legal_or_financial_flow=True,
            recommended_admin_action="Treat DB row as non-authoritative for subscription receipts; do not rely on admin edits for financial copy.",
            db_visible_at_runtime=True,
            placeholders_hint="Structured receipt uses service-defined fields; DB placeholders apply only if DB path is used.",
            tests_covering=["backend/tests (Stripe / subscription flows where applicable)"],
        )
    if alias == "portal-ready":
        return _core_row(
            runtime_source="hybrid",
            admin_editable=True,
            edit_risk_level="medium",
            runtime_notes=(
                "When context includes dashboard_milestone_email, orchestrator uses the built-in portal-ready layout "
                "instead of the DB template so milestone copy stays canonical."
            ),
            attachment_policy="Typically none.",
            legal_or_financial_flow=False,
            recommended_admin_action="Safe to tune general portal-ready DB copy; expect milestone sends to ignore DB overrides.",
            db_visible_at_runtime=True,
            placeholders_hint="DB row placeholders when DB path used; milestone path uses EmailService model keys.",
            tests_covering=[],
        )
    if alias == "scheduled-report":
        return _core_row(
            runtime_source="hybrid",
            admin_editable=False,
            edit_risk_level="high",
            runtime_notes=(
                "Job-driven and pre-rendered scheduled report paths use code-built or pre-supplied HTML before DB. "
                "An edge fallthrough could still consult email_templates if neither branch matches."
            ),
            attachment_policy="Reports often include CSV/PDF attachments assembled outside DB template body.",
            legal_or_financial_flow=False,
            recommended_admin_action="Do not use DB template to control scheduled report layout.",
            db_visible_at_runtime=True,
            placeholders_hint="Service-defined when code path; DB placeholders only if DB path used.",
            tests_covering=[],
        )
    if alias == "order-intake-confirmation":
        return _core_row(
            runtime_source="hybrid",
            admin_editable=False,
            edit_risk_level="high",
            runtime_notes=(
                "When context includes a pre-built message, orchestrator returns that HTML and skips the DB row. "
                "Intake order emails otherwise may use an active DB template."
            ),
            attachment_policy="May include order documents when pipeline attaches files.",
            legal_or_financial_flow=True,
            recommended_admin_action="Assume DB edits may not affect intake receipts that pass pre-rendered message.",
            db_visible_at_runtime=True,
            placeholders_hint="Pre-rendered path: none from DB; DB path uses row placeholders.",
            tests_covering=[],
        )
    if alias == "admin-manual":
        return _core_row(
            runtime_source="db_template",
            admin_editable=True,
            edit_risk_level="medium",
            runtime_notes=(
                "Many notification_template_keys share this alias; runtime body comes from the active DB row "
                "when present, otherwise EmailService fallback. Some sends pass structured context — "
                "effectiveness of DB copy depends on whether callers rely on placeholders in that row."
            ),
            attachment_policy="Varies by triggering flow; often none.",
            legal_or_financial_flow=False,
            recommended_admin_action="Edit cautiously: one row affects multiple operational and internal flows.",
            db_visible_at_runtime=True,
            placeholders_hint="Shared row — ensure placeholders match all major callers or use conservative copy.",
            tests_covering=[],
        )
    if alias == "internal-alert":
        return _core_row(
            runtime_source="db_template",
            admin_editable=True,
            edit_risk_level="medium",
            runtime_notes=(
                "No orchestrator bypass; active DB template is used when present. "
                "Fallback uses EmailService internal-alert layout when no row exists."
            ),
            attachment_policy="Usually none.",
            legal_or_financial_flow=False,
            recommended_admin_action="Safe for wording tweaks; validate SLA/ops alert readability after changes.",
            db_visible_at_runtime=True,
            placeholders_hint="Match internal alert model keys when using DB path; see EmailService fallback for defaults.",
            tests_covering=[],
        )
    if alias == "compliance-alert":
        return _core_row(
            runtime_source="db_template",
            admin_editable=True,
            edit_risk_level="medium",
            runtime_notes=(
                "Used for compliance status and order-related notifications (multiple template_keys). "
                "Orchestrator uses DB row when active."
            ),
            attachment_policy="May include evidence or document attachments from the triggering workflow.",
            legal_or_financial_flow=False,
            recommended_admin_action="Edit for clarity; verify order vs compliance sends in staging.",
            db_visible_at_runtime=True,
            placeholders_hint="Row available_variables; callers supply requirement/order-specific keys.",
            tests_covering=[],
        )

    # Default: DB-first orchestrator path, EmailService fallback if no active row.
    legal = alias in {
        "payment-failed",
        "payment-received",
        "subscription-canceled",
        "renewal-reminder",
        "order-delivered",
    }
    risk = (
        "high"
        if legal or alias in {"password-setup", "password-reset", "tenant-invite", "admin-invite"}
        else "low"
    )
    return _core_row(
        runtime_source="db_template",
        admin_editable=True,
        edit_risk_level=risk,
        runtime_notes=(
            "Orchestrator loads an active email_templates document for this alias when present; "
            "otherwise it falls back to EmailService built-ins for the alias."
        ),
        attachment_policy="None unless upstream workflow attaches files.",
        legal_or_financial_flow=legal,
        recommended_admin_action="Safe to edit copy for branding and clarity; test in staging before production.",
        db_visible_at_runtime=True,
        placeholders_hint="Use available_variables on the template row; admin preview substitutes sample values only.",
        tests_covering=["backend/tests/test_notification_orchestrator.py"],
    )


def get_email_alias_runtime_metadata(alias: str) -> Dict[str, Any]:
    """Return public metadata dict for API and UI (includes template_keys)."""
    alias = (alias or "").strip()
    if alias in _UNCONDITIONAL_CODE_BUILT:
        base = _for_alias(alias)
    elif alias in _HYBRID_ALIASES:
        base = _for_alias(alias)
    elif alias in ("welcome", "order-client-info-request"):
        base = _core_row(
            runtime_source="fallback_only",
            admin_editable=True,
            edit_risk_level="low",
            runtime_notes=(
                "Not referenced by default notification_templates seed for this alias value; "
                "if a row exists it may still be used when explicitly addressed by code."
            ),
            attachment_policy="None by default.",
            legal_or_financial_flow=False,
            recommended_admin_action="Confirm engineering wiring before investing in copy.",
            db_visible_at_runtime=True,
            placeholders_hint="Define placeholders to match calling code when wired.",
            tests_covering=[],
        )
    else:
        base = _for_alias(alias)

    out = dict(base)
    out["template_keys"] = TEMPLATE_KEYS_BY_ALIAS.get(alias, [])
    out["alias"] = alias
    return out


def merge_runtime_metadata_into_template_row(template_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Return template_doc with runtime_metadata attached (mutates a copy)."""
    doc = dict(template_doc)
    alias = str(doc.get("alias") or "")
    doc["runtime_metadata"] = get_email_alias_runtime_metadata(alias)
    return doc


def is_admin_template_content_editable(alias: str) -> bool:
    return bool(get_email_alias_runtime_metadata(alias).get("admin_editable"))


def preview_disclaimer_for_alias(alias: str) -> str:
    meta = get_email_alias_runtime_metadata(alias)
    if not meta.get("db_visible_at_runtime", True):
        return (
            "This alias is not rendered from the database template at runtime. "
            "Preview shows DB content only and does not guarantee production rendering."
        )
    if meta.get("runtime_source") != "db_template":
        return (
            "Preview substitutes placeholders on the database row only. "
            "Production may use a code-built path or pre-rendered message for some sends — preview does not guarantee production rendering."
        )
    return (
        "Preview substitutes sample values on the stored template only. "
        "Branding merge and orchestrator context may differ in production."
    )
