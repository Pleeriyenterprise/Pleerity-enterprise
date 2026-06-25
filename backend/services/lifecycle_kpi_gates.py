"""
Lifecycle-aware KPI gates — Phase 5 P5-S2 (shadow).

ADR: backend/docs/architecture/ADR_REQUIREMENT_LIFECYCLE_SEMANTICS.md constraint #9.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from services.lifecycle_aware_kpis_config import (
    get_effective_kpi_mode,
    is_lifecycle_aware_kpi_off,
    is_lifecycle_aware_kpi_shadow,
)
from services.lifecycle_semantics_resolver import resolve_lifecycle_semantics
from services.lifecycle_semantics_types import AttentionKind, LifecycleSemantics

logger = logging.getLogger(__name__)

_ATTENTION_KIND_BUCKETS: tuple[str, ...] = (
    "CERTIFICATE_EXPIRING",
    "REVIEW_DUE",
    "EVENT_ACTION_REQUIRED",
    "TENANCY_TERM_ENDING",
    "OCCUPANCY_REVIEW_DUE",
    "OPERATIONAL_ACTION_REQUIRED",
)


@dataclass(frozen=True)
class KpiLifecycleContext:
    requirement_code: str
    lifecycle_semantics: LifecycleSemantics
    requires_expiry_date: bool
    attention_kind: Optional[AttentionKind]
    resolution_source: str


def build_kpi_lifecycle_context(requirement: Optional[Dict[str, Any]]) -> KpiLifecycleContext:
    req = dict(requirement or {})
    resolved = resolve_lifecycle_semantics(req)
    return KpiLifecycleContext(
        requirement_code=str(resolved.requirement_code or ""),
        lifecycle_semantics=resolved.lifecycle_semantics,
        requires_expiry_date=bool(resolved.field_contract.requires_expiry_date),
        attention_kind=resolved.attention_kind,
        resolution_source=str(resolved.resolution_source),
    )


def lifecycle_kpi_enabled() -> bool:
    return not is_lifecycle_aware_kpi_off()


def _attention_kind_for_kpi_bucket(ctx: KpiLifecycleContext) -> str:
    if ctx.attention_kind:
        return str(ctx.attention_kind)
    semantics_to_kind = {
        "EXPIRY_BASED": "CERTIFICATE_EXPIRING",
        "REVIEW_BASED": "REVIEW_DUE",
        "EVENT_BASED": "EVENT_ACTION_REQUIRED",
        "TENANCY_LIFECYCLE": "TENANCY_TERM_ENDING",
        "OCCUPANCY_LIFECYCLE": "OCCUPANCY_REVIEW_DUE",
        "OPERATIONAL": "OPERATIONAL_ACTION_REQUIRED",
    }
    return semantics_to_kind.get(str(ctx.lifecycle_semantics), "CERTIFICATE_EXPIRING")


def lifecycle_kpi_monolithic_expiring_soon_allowed(ctx: KpiLifecycleContext) -> bool:
    """
    Planned lifecycle monolithic ``expiring_soon`` count — certificate-style expiry only.

    Review-based and other non-certificate attention kinds route to ``attention_kind`` buckets
    without inflating the legacy monolithic ``expiring_soon`` KPI.
    """
    if ctx.lifecycle_semantics == "REVIEW_BASED":
        return False
    if ctx.lifecycle_semantics == "EXPIRY_BASED":
        return ctx.requires_expiry_date
    return str(ctx.attention_kind or "") == "CERTIFICATE_EXPIRING"


def _empty_attention_kind_buckets() -> Dict[str, int]:
    return {kind: 0 for kind in _ATTENTION_KIND_BUCKETS}


def compute_lifecycle_kpi_stats(portal_projected_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Parallel lifecycle-gated KPI aggregation for shadow observe-only.

    Legacy ``compute_client_portal_requirement_stats`` remains authoritative on staging shadow.
    """
    from services.requirement_satisfaction_service import is_requirement_satisfied, row_counts_as_missing_evidence

    total = len(portal_projected_rows)
    compliant = 0
    satisfied = 0
    pending = 0
    missing_evidence = 0
    expiring_soon = 0
    overdue = 0
    attention_kind_buckets = _empty_attention_kind_buckets()

    for r in portal_projected_rows:
        if is_requirement_satisfied(r):
            satisfied += 1
        s = (str(r.get("status") or "PENDING")).strip().upper()
        if s in ("COMPLIANT", "VALID"):
            compliant += 1
        elif s == "PENDING":
            pending += 1
            if row_counts_as_missing_evidence(r):
                missing_evidence += 1
        elif s == "MISSING":
            if row_counts_as_missing_evidence(r):
                missing_evidence += 1
        elif s == "EXPIRING_SOON":
            ctx = build_kpi_lifecycle_context(r)
            kind = _attention_kind_for_kpi_bucket(ctx)
            if kind in attention_kind_buckets:
                attention_kind_buckets[kind] += 1
            if lifecycle_kpi_monolithic_expiring_soon_allowed(ctx):
                expiring_soon += 1
        elif s in ("OVERDUE", "EXPIRED"):
            overdue += 1

    return {
        "total_requirements": total,
        "compliant": satisfied,
        "satisfied": satisfied,
        "status_valid": compliant,
        "pending": pending,
        "missing_evidence": missing_evidence,
        "expiring_soon": expiring_soon,
        "overdue": overdue,
        "attention_kind_buckets": attention_kind_buckets,
    }


def observe_kpi_shadow(
    *,
    legacy_stats: Dict[str, int],
    lifecycle_stats: Dict[str, Any],
) -> None:
    """Shadow observe-only: log lifecycle-gated vs legacy KPI divergence."""
    if is_lifecycle_aware_kpi_off() or not is_lifecycle_aware_kpi_shadow():
        return

    extra: Dict[str, Any] = {
        "legacy_expiring_soon": int(legacy_stats.get("expiring_soon") or 0),
        "lifecycle_expiring_soon": int(lifecycle_stats.get("expiring_soon") or 0),
        "legacy_overdue": int(legacy_stats.get("overdue") or 0),
        "lifecycle_overdue": int(lifecycle_stats.get("overdue") or 0),
        "legacy_pending": int(legacy_stats.get("pending") or 0),
        "lifecycle_pending": int(lifecycle_stats.get("pending") or 0),
        "attention_kind_buckets": dict(lifecycle_stats.get("attention_kind_buckets") or {}),
        "effective_mode": get_effective_kpi_mode(),
    }
    logger.info("lifecycle_kpi_shadow_complete", extra=extra)
    if (
        extra["legacy_expiring_soon"] != extra["lifecycle_expiring_soon"]
        or extra["legacy_overdue"] != extra["lifecycle_overdue"]
        or extra["legacy_pending"] != extra["lifecycle_pending"]
    ):
        extra["divergence"] = True
        logger.info("lifecycle_kpi_shadow_divergence", extra=extra)
