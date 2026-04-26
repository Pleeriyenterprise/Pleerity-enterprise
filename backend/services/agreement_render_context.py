"""Single source of truth for agreement HTML/text render context (preview + acceptance + checkout validation)."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Tuple

# Shown only in pre-acceptance preview compiles — never a fake ISO timestamp.
PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER = (
    "Acceptance timestamp will be recorded when you accept this agreement."
)

_CANONICAL_SUPPORT_EMAIL = "info@pleerityenterprise.co.uk"

# Forbidden demo / placeholder tokens (case-insensitive where noted).
_FORBIDDEN_EMAIL_LOWER = "client@example.com"
_FORBIDDEN_SUPPORT_LOWER = "support@pleerity.com"
_FORBIDDEN_ADDRESS_SUBSTRING = "property address on file"
_DEMO_NAME_LOWER = "client"


def canonical_support_email(settings: Dict[str, Any] | None) -> str:
    """Provider support email for agreements and footers."""
    env = (os.getenv("SUPPORT_EMAIL") or os.getenv("EMAIL_REPLY_TO") or "").strip()
    if env:
        return env
    from_settings = str((settings or {}).get("provider_email") or "").strip()
    if from_settings:
        return from_settings
    return _CANONICAL_SUPPORT_EMAIL


def build_agreement_render_context(
    *,
    commercial_snapshot: Dict[str, Any],
    settings: Dict[str, Any] | None,
    accepted_signatory_name: str,
    acceptance_timestamp_display: str,
    agreement_version_number: int,
) -> Dict[str, Any]:
    """
    Build the dict passed to compile_agreement_document(render_context=...).

    ``acceptance_timestamp_display`` must be either:
    - PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER for intake preview, or
    - an ISO-8601 UTC string (e.g. acceptance ``accepted_at``) for recorded acceptance / checkout revalidation.
    """
    snap = commercial_snapshot or {}
    st = settings or {}
    monthly_minor = int(snap.get("billing_amount_minor") or 0)
    onboarding_minor = int(snap.get("onboarding_fee_minor") or 0)
    return {
        "provider_company_name": st.get("provider_company_name") or "Pleerity Enterprise Ltd",
        "client_full_name": str(snap.get("client_full_name") or "").strip(),
        "client_company_name": str(snap.get("client_company_name") or "").strip(),
        "client_email": str(snap.get("client_email") or "").strip(),
        "client_address": str(snap.get("client_address") or "").strip(),
        "plan_name": str(snap.get("plan_label") or snap.get("selected_plan_code") or "").strip(),
        "billing_interval": str(snap.get("billing_interval") or "month").strip() or "month",
        "monthly_fee": f"£{monthly_minor / 100:.2f}",
        "currency": str(snap.get("currency") or "GBP").strip() or "GBP",
        "onboarding_fee_line": (
            f"£{onboarding_minor / 100:.2f}" if onboarding_minor > 0 else "None"
        ),
        "accepted_signatory_name": (accepted_signatory_name or "").strip()[:200],
        "acceptance_timestamp": (acceptance_timestamp_display or "").strip(),
        "agreement_version": str(int(agreement_version_number or 1)),
        "support_email": canonical_support_email(st),
    }


def validate_checkout_grade_render_context(
    ctx: Dict[str, Any],
    *,
    billing_amount_minor: int,
    preview_mode: bool,
) -> Tuple[bool, List[str]]:
    """
    Enforce no demo placeholders in production-grade agreement renders.

    When ``preview_mode`` is True, ``acceptance_timestamp`` must be the preview-safe sentence, not an ISO clock.
    When False, ``acceptance_timestamp`` must look like a real timestamp (ISO), not the preview sentence or
    generic placeholder copy.
    """
    errors: List[str] = []
    name = str(ctx.get("client_full_name") or "").strip()
    email = str(ctx.get("client_email") or "").strip().lower()
    addr = str(ctx.get("client_address") or "").strip().lower()
    plan = str(ctx.get("plan_name") or "").strip()
    monthly_fee = str(ctx.get("monthly_fee") or "").strip()
    support = str(ctx.get("support_email") or "").strip().lower()
    ts = str(ctx.get("acceptance_timestamp") or "").strip()

    if not name:
        errors.append("missing_client_full_name")
    elif name.strip().lower() == _DEMO_NAME_LOWER:
        errors.append("forbidden_client_name_token")

    if not email:
        errors.append("missing_client_email")
    elif email == _FORBIDDEN_EMAIL_LOWER:
        errors.append("forbidden_demo_client_email")
    elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        errors.append("invalid_client_email_shape")

    if not addr:
        errors.append("missing_client_address")
    elif _FORBIDDEN_ADDRESS_SUBSTRING in addr:
        errors.append("forbidden_demo_address_token")

    if not plan:
        errors.append("missing_plan_name")

    if billing_amount_minor > 0:
        if monthly_fee in ("", "£0.00", "£0", "£0.0"):
            errors.append("forbidden_zero_monthly_fee_when_plan_priced")
    # billing_amount_minor == 0: £0.00 is allowed (genuine free tier).

    if not support:
        errors.append("missing_support_email")

    _iso_start = re.compile(r"^\d{4}-\d{2}-\d{2}T")
    if preview_mode:
        if ts != PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER:
            errors.append("preview_acceptance_timestamp_must_be_safe_sentence")
    else:
        if not ts:
            errors.append("missing_acceptance_timestamp")
        elif ts == PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER:
            errors.append("forbidden_preview_timestamp_in_acceptance_render")
        elif not _iso_start.match(ts):
            errors.append("acceptance_timestamp_not_iso")

    if support and support == _FORBIDDEN_SUPPORT_LOWER:
        errors.append("forbidden_legacy_support_email")
    elif not os.getenv("SUPPORT_EMAIL") and support and support != _CANONICAL_SUPPORT_EMAIL.lower():
        errors.append("support_email_must_match_canonical_unless_env_override")

    return (len(errors) == 0, errors)
