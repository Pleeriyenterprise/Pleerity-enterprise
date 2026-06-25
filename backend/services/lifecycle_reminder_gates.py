"""
Lifecycle-aware reminder gates — Phase 4 S4.2 (shadow) + S4.3 (active).

ADR: backend/docs/architecture/ADR_REQUIREMENT_LIFECYCLE_SEMANTICS.md constraints #4, #8.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from services.lifecycle_aware_reminders_config import (
    get_effective_reminder_mode,
    is_lifecycle_aware_reminder_active,
    is_lifecycle_aware_reminder_off,
    is_lifecycle_aware_reminder_shadow,
)
from services.lifecycle_semantics_resolver import resolve_lifecycle_semantics
from services.lifecycle_semantics_types import AttentionKind, LifecycleSemantics

logger = logging.getLogger(__name__)

# Mirror reminder_truth_service suppression codes (avoid circular import at load).
REASON_NOT_RELEVANT = "NOT_RELEVANT"
REASON_NO_EFFECTIVE_DATE = "NO_EFFECTIVE_DATE"
REASON_NO_LONGER_DUE = "NO_LONGER_DUE"

_LEGACY_EMAIL_TEMPLATE = "COMPLIANCE_EXPIRY_REMINDER"
_LEGACY_SMS_TEMPLATE = "COMPLIANCE_EXPIRY_REMINDER_SMS"

# Planned template families per attention_kind (S4.3 routing; seed keys unchanged until Phase 4+).
_PLANNED_EMAIL_TEMPLATE_BY_ATTENTION: Dict[str, str] = {
    "CERTIFICATE_EXPIRING": _LEGACY_EMAIL_TEMPLATE,
    "REVIEW_DUE": _LEGACY_EMAIL_TEMPLATE,
    "EVENT_ACTION_REQUIRED": _LEGACY_EMAIL_TEMPLATE,
    "TENANCY_TERM_ENDING": _LEGACY_EMAIL_TEMPLATE,
    "OCCUPANCY_REVIEW_DUE": _LEGACY_EMAIL_TEMPLATE,
    "OPERATIONAL_ACTION_REQUIRED": _LEGACY_EMAIL_TEMPLATE,
}

_PLANNED_SMS_TEMPLATE_BY_ATTENTION: Dict[str, str] = {
    "CERTIFICATE_EXPIRING": _LEGACY_SMS_TEMPLATE,
    "REVIEW_DUE": _LEGACY_SMS_TEMPLATE,
    "EVENT_ACTION_REQUIRED": _LEGACY_SMS_TEMPLATE,
    "TENANCY_TERM_ENDING": _LEGACY_SMS_TEMPLATE,
    "OCCUPANCY_REVIEW_DUE": _LEGACY_SMS_TEMPLATE,
    "OPERATIONAL_ACTION_REQUIRED": _LEGACY_SMS_TEMPLATE,
}


@dataclass(frozen=True)
class ReminderLifecycleContext:
    requirement_code: str
    lifecycle_semantics: LifecycleSemantics
    requires_expiry_date: bool
    attention_kind: Optional[AttentionKind]
    effective_attention_date: Optional[datetime]
    legacy_effective_expiry: Optional[datetime]
    resolution_source: str


def build_reminder_lifecycle_context(
    requirement: Optional[Dict[str, Any]],
    *,
    as_of: Optional[datetime] = None,
) -> ReminderLifecycleContext:
    req = dict(requirement or {})
    resolved = resolve_lifecycle_semantics(req, as_of=as_of)
    from utils.expiry_utils import get_effective_expiry_date

    return ReminderLifecycleContext(
        requirement_code=str(resolved.requirement_code or ""),
        lifecycle_semantics=resolved.lifecycle_semantics,
        requires_expiry_date=bool(resolved.field_contract.requires_expiry_date),
        attention_kind=resolved.attention_kind,
        effective_attention_date=resolved.effective_attention_date,
        legacy_effective_expiry=get_effective_expiry_date(req),
        resolution_source=str(resolved.resolution_source),
    )


def lifecycle_reminder_enabled() -> bool:
    return not is_lifecycle_aware_reminder_off()


def lifecycle_certificate_expiry_pipeline_allowed(
    reminder_type: str,
    *,
    apply_lifecycle_gates: bool,
    lifecycle_semantics: Optional[str],
    requires_expiry_date: bool,
) -> bool:
    """Gate DAILY_COMPLIANCE_EXPIRY_* pipeline to EXPIRY_BASED + requires_expiry_date when active."""
    if not apply_lifecycle_gates:
        return True
    normalized = str(reminder_type or "").upper()
    if not normalized.startswith("DAILY_COMPLIANCE_EXPIRY"):
        return True
    if lifecycle_semantics != "EXPIRY_BASED":
        return False
    return requires_expiry_date


def lifecycle_reminder_due_date(
    ctx: ReminderLifecycleContext,
    legacy_due_date: Optional[datetime],
    *,
    apply_lifecycle_gates: bool,
) -> Optional[datetime]:
    if not apply_lifecycle_gates:
        return legacy_due_date
    if ctx.lifecycle_semantics == "EXPIRY_BASED":
        return ctx.effective_attention_date or legacy_due_date
    return ctx.effective_attention_date


def classify_reminder_timing(
    due_date: Optional[datetime],
    *,
    now: datetime,
    reminder_days: int,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Return (eligible, classification, suppression_reason) for date-window only."""
    if due_date is None:
        return False, None, REASON_NO_EFFECTIVE_DATE
    days_until_due = (due_date - now).days
    if days_until_due < 0:
        return True, "overdue", None
    if 0 <= days_until_due <= int(reminder_days):
        return True, "expiring", None
    return False, None, REASON_NO_LONGER_DUE


def evaluate_lifecycle_certificate_expiry_reminder(
    ctx: ReminderLifecycleContext,
    *,
    reminder_type: str,
    now: datetime,
    reminder_days: int,
    legacy_due_date: Optional[datetime],
    apply_lifecycle_gates: bool,
) -> Tuple[bool, Optional[str], Optional[str]]:
    if not lifecycle_certificate_expiry_pipeline_allowed(
        reminder_type,
        apply_lifecycle_gates=apply_lifecycle_gates,
        lifecycle_semantics=ctx.lifecycle_semantics,
        requires_expiry_date=ctx.requires_expiry_date,
    ):
        return False, None, REASON_NOT_RELEVANT
    due = lifecycle_reminder_due_date(
        ctx,
        legacy_due_date,
        apply_lifecycle_gates=apply_lifecycle_gates,
    )
    return classify_reminder_timing(due, now=now, reminder_days=reminder_days)


def observe_reminder_shadow(
    *,
    requirement_code: str,
    reminder_type: str,
    legacy_eligible: bool,
    legacy_classification: Optional[str],
    legacy_suppression_reason: Optional[str],
    lifecycle_eligible: bool,
    lifecycle_classification: Optional[str],
    lifecycle_suppression_reason: Optional[str],
    lifecycle_context: ReminderLifecycleContext,
) -> None:
    if is_lifecycle_aware_reminder_off() or not is_lifecycle_aware_reminder_shadow():
        return

    extra: Dict[str, Any] = {
        "requirement_code": requirement_code,
        "reminder_type": reminder_type,
        "lifecycle_semantics": lifecycle_context.lifecycle_semantics,
        "requires_expiry_date": lifecycle_context.requires_expiry_date,
        "attention_kind": lifecycle_context.attention_kind,
        "resolution_source": lifecycle_context.resolution_source,
        "legacy_eligible": legacy_eligible,
        "legacy_classification": legacy_classification,
        "legacy_suppression_reason": legacy_suppression_reason,
        "lifecycle_eligible": lifecycle_eligible,
        "lifecycle_classification": lifecycle_classification,
        "lifecycle_suppression_reason": lifecycle_suppression_reason,
        "effective_mode": get_effective_reminder_mode(),
    }
    logger.info("lifecycle_reminder_shadow_complete", extra=extra)
    if (
        legacy_eligible != lifecycle_eligible
        or legacy_classification != lifecycle_classification
        or legacy_suppression_reason != lifecycle_suppression_reason
    ):
        extra["divergence"] = True
        logger.info("lifecycle_reminder_shadow_divergence", extra=extra)


def resolve_lifecycle_reminder_template_key(
    attention_kind: Optional[str],
    *,
    channel: str = "EMAIL",
) -> str:
    """
    S4.3 template routing authority.

    off: legacy template only.
    shadow: legacy template authoritative; logs planned routing when attention_kind present.
    active: planned mapping (currently all seed keys resolve to legacy COMPLIANCE_EXPIRY_*).
    """
    legacy = _LEGACY_EMAIL_TEMPLATE if str(channel).upper() == "EMAIL" else _LEGACY_SMS_TEMPLATE
    if is_lifecycle_aware_reminder_off():
        return legacy

    mapping = (
        _PLANNED_EMAIL_TEMPLATE_BY_ATTENTION
        if str(channel).upper() == "EMAIL"
        else _PLANNED_SMS_TEMPLATE_BY_ATTENTION
    )
    planned = mapping.get(str(attention_kind or ""), legacy)

    if is_lifecycle_aware_reminder_shadow() and attention_kind:
        logger.info(
            "lifecycle_reminder_shadow_template_routing",
            extra={
                "attention_kind": attention_kind,
                "planned_template_key": planned,
                "authoritative_template_key": legacy,
                "channel": channel,
                "effective_mode": get_effective_reminder_mode(),
            },
        )
        return legacy

    if is_lifecycle_aware_reminder_active():
        return planned

    return legacy


def dominant_attention_kind_for_batch(
    expiring: list,
    overdue: list,
) -> Optional[str]:
    """Pick attention_kind from first item when lifecycle metadata attached."""
    for row in overdue + expiring:
        kind = row.get("lifecycle_attention_kind")
        if kind:
            return str(kind)
    return None
