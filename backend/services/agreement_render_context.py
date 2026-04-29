"""Single source of truth for agreement HTML/text render context (preview + acceptance + checkout validation)."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
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
    ts_raw = (acceptance_timestamp_display or "").strip()
    is_preview = ts_raw == PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER
    ts_utc = _normalize_iso_utc(ts_raw) if not is_preview else ""
    ts_display = PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER if is_preview else _format_human_utc(ts_utc)
    client_full_name = str(snap.get("client_full_name") or "").strip()
    client_company_name = str(snap.get("client_company_name") or "").strip()
    parties_statement = _build_parties_statement(
        provider_company_name=str(st.get("provider_company_name") or "Pleerity Enterprise Ltd"),
        client_full_name=client_full_name,
        client_company_name=client_company_name,
    )
    return {
        "provider_company_name": st.get("provider_company_name") or "Pleerity Enterprise Ltd",
        "client_full_name": client_full_name,
        "client_company_name": client_company_name,
        "parties_statement": parties_statement,
        "client_email": str(snap.get("client_email") or "").strip(),
        "client_address": str(snap.get("client_address") or "").strip(),
        "client_address_raw": str(snap.get("client_address_raw") or "").strip(),
        "client_postcode": str(snap.get("client_postcode") or "").strip().upper(),
        "plan_name": str(snap.get("plan_label") or snap.get("selected_plan_code") or "").strip(),
        "billing_interval": str(snap.get("billing_interval") or "month").strip() or "month",
        "monthly_fee": f"£{monthly_minor / 100:.2f}",
        "currency": str(snap.get("currency") or "GBP").strip() or "GBP",
        "onboarding_fee_line": (
            f"One-time onboarding fee: £{onboarding_minor / 100:.2f}" if onboarding_minor > 0 else "One-time onboarding fee: None"
        ),
        "accepted_signatory_name": (accepted_signatory_name or "").strip()[:200],
        "acceptance_timestamp": ts_display,
        "acceptance_timestamp_utc": ts_utc,
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
    ts_utc = str(ctx.get("acceptance_timestamp_utc") or "").strip()
    postcode = str(ctx.get("client_postcode") or "").strip().upper()

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
        if not ts_utc:
            errors.append("missing_acceptance_timestamp_utc")
        elif not _iso_start.match(ts_utc) or not ts_utc.endswith("Z"):
            errors.append("acceptance_timestamp_utc_not_normalized")
        elif "UTC" not in ts:
            errors.append("acceptance_timestamp_display_must_include_utc")

    if postcode and not _looks_like_uk_postcode(postcode):
        errors.append("client_postcode_malformed_or_truncated")
    if _address_looks_truncated(addr):
        errors.append("client_address_malformed_or_truncated")

    if support and support == _FORBIDDEN_SUPPORT_LOWER:
        errors.append("forbidden_legacy_support_email")
    elif not os.getenv("SUPPORT_EMAIL") and support and support != _CANONICAL_SUPPORT_EMAIL.lower():
        errors.append("support_email_must_match_canonical_unless_env_override")

    return (len(errors) == 0, errors)


def validate_accepted_artifact_text(
    *,
    canonical_text: str,
    render_context: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Final legal-grade checks for accepted artifact text only."""
    txt = str(canonical_text or "")
    errs: List[str] = []
    if not txt.strip():
        errs.append("accepted_artifact_empty")
        return False, errs
    if PREVIEW_ACCEPTANCE_TIMESTAMP_PLACEHOLDER in txt:
        errs.append("accepted_artifact_contains_preview_timestamp_placeholder")
    if "{{" in txt or "}}" in txt:
        errs.append("accepted_artifact_contains_unresolved_placeholder")
    if "where applicable" in txt.lower():
        errs.append("accepted_artifact_contains_forbidden_conditional_phrase")
    if "billed on a month basis" in txt.lower():
        errs.append("accepted_artifact_contains_weak_billing_wording")
    if "applicable onboarding or setup fees" in txt.lower():
        errs.append("accepted_artifact_contains_weak_onboarding_wording")
    if re.search(r"[ \t]{2,}", txt):
        errs.append("accepted_artifact_contains_duplicate_whitespace")
    if not str(render_context.get("client_full_name") or "").strip():
        errs.append("accepted_artifact_missing_client_name")
    if not str(render_context.get("acceptance_timestamp_utc") or "").strip():
        errs.append("accepted_artifact_missing_acceptance_timestamp_utc")
    if "UTC" not in str(render_context.get("acceptance_timestamp") or ""):
        errs.append("accepted_artifact_missing_human_utc_timestamp")
    return (len(errs) == 0, errs)


def _normalize_iso_utc(v: str) -> str:
    s = str(v or "").strip()
    if not s:
        return ""
    s2 = s.replace("+00:00", "Z")
    if s2.endswith("Z"):
        s2 = s2[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s2)
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.isoformat().replace("+00:00", "Z")
    except Exception:
        return ""


def _format_human_utc(iso_utc: str) -> str:
    s = _normalize_iso_utc(iso_utc)
    if not s:
        return ""
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
        return dt.strftime("%d %B %Y at %H:%M UTC")
    except Exception:
        return ""


def _looks_like_uk_postcode(v: str) -> bool:
    p = str(v or "").strip().upper()
    if not p:
        return False
    rx = re.compile(r"^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$")
    return rx.match(p) is not None


def _address_looks_truncated(v: str) -> bool:
    s = str(v or "").strip()
    if not s:
        return True
    # Common truncation patterns seen in malformed legal artifacts, e.g. "Chelsea, SW."
    if re.search(r",\s*[A-Z]{1,3}\.?$", s):
        return True
    return False


def _build_parties_statement(
    *,
    provider_company_name: str,
    client_full_name: str,
    client_company_name: str,
) -> str:
    p = (provider_company_name or "Pleerity Enterprise Ltd").strip()
    c = (client_full_name or "").strip()
    co = (client_company_name or "").strip()
    if co:
        return (
            f'This Property Compliance Management Agreement ("Agreement") is entered into between '
            f'{p} ("Provider") and {c} ("Client"), operating as {co}.'
        )
    return (
        f'This Property Compliance Management Agreement ("Agreement") is entered into between '
        f'{p} ("Provider") and {c} ("Client").'
    )
