"""
Lifecycle-aware scoring gates — Phase 3 S3.2 (shadow) + S3.3 (active).

ADR: backend/docs/architecture/ADR_REQUIREMENT_LIFECYCLE_SEMANTICS.md constraints #5 and #10.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from services.compliance_rules_registry import expects_expiry_for_requirement
from services.lifecycle_aware_scoring_config import (
    get_effective_scoring_mode,
    is_lifecycle_aware_scoring_active,
    is_lifecycle_aware_scoring_off,
    is_lifecycle_aware_scoring_shadow,
)
from services.lifecycle_semantics_resolver import resolve_lifecycle_semantics
from services.lifecycle_semantics_types import LifecycleSemantics

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoringLifecycleContext:
    requirement_code: str
    lifecycle_semantics: LifecycleSemantics
    requires_expiry_date: bool
    legacy_expects_expiry: bool
    resolution_source: str


def build_scoring_lifecycle_context(
    requirement: Optional[Dict[str, Any]],
    *,
    jurisdiction: str,
    scoring_code: str,
) -> ScoringLifecycleContext:
    req = dict(requirement or {})
    if scoring_code and not req.get("requirement_code"):
        req["requirement_code"] = scoring_code.lower()
    resolved = resolve_lifecycle_semantics(req)
    legacy_expects = expects_expiry_for_requirement(jurisdiction, scoring_code)
    return ScoringLifecycleContext(
        requirement_code=scoring_code,
        lifecycle_semantics=resolved.lifecycle_semantics,
        requires_expiry_date=bool(resolved.field_contract.requires_expiry_date),
        legacy_expects_expiry=bool(legacy_expects),
        resolution_source=str(resolved.resolution_source),
    )


def lifecycle_scoring_enabled() -> bool:
    return not is_lifecycle_aware_scoring_off()


def lifecycle_due_date_expiry_penalties_allowed(
    lifecycle_semantics: Optional[str],
    *,
    apply_lifecycle_gates: bool,
) -> bool:
    if not apply_lifecycle_gates:
        return True
    return lifecycle_semantics == "EXPIRY_BASED"


def lifecycle_authority_expiry_calendar_allowed(
    *,
    apply_lifecycle_gates: bool,
    requires_expiry_date: bool,
) -> bool:
    if not apply_lifecycle_gates:
        return True
    return requires_expiry_date


def observe_scoring_shadow(
    *,
    requirement_code: str,
    legacy_fraction: float,
    legacy_status: str,
    lifecycle_fraction: float,
    lifecycle_status: str,
    lifecycle_context: ScoringLifecycleContext,
    legacy_reasons: Optional[List[str]] = None,
    lifecycle_reasons: Optional[List[str]] = None,
) -> None:
    """
    Shadow observe-only: log lifecycle-gated vs legacy scoring divergence.
    Legacy fractions remain authoritative unless effective mode is active.
    """
    if is_lifecycle_aware_scoring_off() or not is_lifecycle_aware_scoring_shadow():
        return

    extra: Dict[str, Any] = {
        "requirement_code": requirement_code,
        "lifecycle_semantics": lifecycle_context.lifecycle_semantics,
        "requires_expiry_date": lifecycle_context.requires_expiry_date,
        "legacy_expects_expiry": lifecycle_context.legacy_expects_expiry,
        "resolution_source": lifecycle_context.resolution_source,
        "legacy_fraction": legacy_fraction,
        "legacy_status": legacy_status,
        "lifecycle_fraction": lifecycle_fraction,
        "lifecycle_status": lifecycle_status,
        "legacy_reasons": list(legacy_reasons or []),
        "lifecycle_reasons": list(lifecycle_reasons or []),
        "effective_mode": get_effective_scoring_mode(),
    }
    logger.info("lifecycle_scoring_shadow_complete", extra=extra)
    if legacy_fraction != lifecycle_fraction or legacy_status != lifecycle_status:
        extra["divergence"] = True
        logger.info("lifecycle_scoring_shadow_divergence", extra=extra)


def emit_expiry_needed_overlay(requirement: Dict[str, Any], ea: Dict[str, Any]) -> bool:
    """
    Gate EXPIRY_DATE_NEEDED overlay on resolver field_contract when scoring is active.
  Legacy behaviour unchanged when scoring flag is off or shadow.
    """
    if str(ea.get("state_reason") or "") != "document_upload_missing_required_expiry_semantics":
        return False
    if not is_lifecycle_aware_scoring_active():
        return True
    resolved = resolve_lifecycle_semantics(requirement)
    return bool(resolved.field_contract.requires_expiry_date)
