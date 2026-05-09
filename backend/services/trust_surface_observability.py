"""
Trust-surface observability (Command Centre, Today / unified tasks, portfolio summary).

Additive metadata and logging helpers only — no scoring or task semantics changes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

from services.scoring_semantics_v1 import SCORE_STATUS_STALE

# Workflow / audit surface identifiers (align with reliability audits)
SURFACE_COMMAND_CENTER_REFRESH = "COMMAND_CENTER_REFRESH"
SURFACE_TODAY_TASK_REBUILD = "TODAY_TASK_REBUILD"
SURFACE_PORTFOLIO_SUMMARY_REFRESH = "PORTFOLIO_SUMMARY_REFRESH"

# Section-level operational truth (additive; not client UX contract)
SECTION_STATUS_HEALTHY_EMPTY = "HEALTHY_EMPTY"
SECTION_STATUS_HEALTHY = "HEALTHY"
SECTION_STATUS_DEGRADED_FALLBACK = "DEGRADED_FALLBACK"
SECTION_STATUS_PARTIAL_DATA = "PARTIAL_DATA"
SECTION_STATUS_STALE_DATA_POSSIBLE = "STALE_DATA_POSSIBLE"
SECTION_STATUS_FAILED = "FAILED"
SECTION_STATUS_OMITTED = "OMITTED"


def ensure_trust_surface_correlation_id(
    surface_name: str,
    client_id: str,
    correlation_id: Optional[str],
) -> str:
    raw = (correlation_id or "").strip()
    if raw:
        return raw
    return f"{surface_name}:{client_id}:{uuid.uuid4().hex}"


def normalize_trust_surface_context(
    *,
    surface_name: str,
    client_id: str,
    correlation_id: str,
    property_id_filter: Optional[str] = None,
    portal_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "surface_name": surface_name,
        "client_id": client_id,
        "correlation_id": correlation_id,
        "property_id_filter": property_id_filter,
        "portal_user_id": portal_user_id,
    }


def build_trust_surface_section_record(
    *,
    section_name: str,
    section_status: str,
    correlation_id: str,
    failure_stage: Optional[str] = None,
    degraded_reason: Optional[str] = None,
    fallback_used: bool = False,
    stale_data_possible: bool = False,
    downstream_dependency: Optional[str] = None,
) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "section_name": section_name,
        "section_status": section_status,
        "correlation_id": correlation_id,
        "fallback_used": fallback_used,
        "stale_data_possible": stale_data_possible,
    }
    if failure_stage is not None:
        rec["failure_stage"] = failure_stage
    if degraded_reason is not None:
        rec["degraded_reason"] = degraded_reason[:2000] if isinstance(degraded_reason, str) else degraded_reason
    if downstream_dependency is not None:
        rec["downstream_dependency"] = downstream_dependency
    return rec


def _parse_iso(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            s = value.replace("Z", "+00:00") if value.endswith("Z") else value
            dt = datetime.fromisoformat(s)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_trust_surface_freshness_observability(
    *,
    generated_at: datetime,
    freshness: Mapping[str, Any],
    headline_score_status: Optional[str] = None,
) -> Dict[str, Any]:
    """Best-effort staleness markers from freshness block and optional headline hint."""
    now = generated_at if generated_at.tzinfo else generated_at.replace(tzinfo=timezone.utc)
    tasks_ref = _parse_iso(freshness.get("tasks_refreshed_at"))
    score_at = _parse_iso(freshness.get("score_updated_at"))
    rebuild_age: Optional[float] = None
    if tasks_ref:
        rebuild_age = max(0.0, (now - tasks_ref).total_seconds())
    stale_hint = (headline_score_status or "").strip().lower() in (
        "stale",
        "partial",
        "unknown",
        "unavailable",
        "reconciliation_required",
    )
    score_stale_possible = freshness.get("score_updated_at") in (None, "") or stale_hint
    return {
        "generated_at": now.isoformat(),
        "source_last_updated_at": freshness.get("score_updated_at") or freshness.get("risk_signals_updated_at"),
        "rebuild_age_seconds": round(rebuild_age, 3) if rebuild_age is not None else None,
        "stale_read_possible": bool(score_stale_possible),
        "score_freshness_timestamp": freshness.get("score_updated_at"),
        "risk_signals_freshness_timestamp": freshness.get("risk_signals_updated_at"),
        "tasks_refreshed_at": freshness.get("tasks_refreshed_at"),
    }


def build_unified_tasks_trust_surface_metadata(
    *,
    client_id: str,
    composition_context: Mapping[str, Any],
    freshness: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> Dict[str, Any]:
    """Attach to unified tasks payload when composition_context is provided."""
    surface = str(composition_context.get("surface_name") or SURFACE_TODAY_TASK_REBUILD)
    corr = str(composition_context.get("correlation_id") or ensure_trust_surface_correlation_id(surface, client_id, None))
    gen = datetime.now(timezone.utc)
    fo = compute_trust_surface_freshness_observability(
        generated_at=gen,
        freshness=freshness,
        headline_score_status=None,
    )
    urgent = int((summary or {}).get("urgent_count") or 0)
    section_rows: List[Dict[str, Any]] = []
    if urgent == 0 and (summary or {}).get("upcoming_count", 0) == 0 and (summary or {}).get("in_progress_count", 0) == 0:
        section_rows.append(
            build_trust_surface_section_record(
                section_name="task_rebuild_priority_counts",
                section_status=SECTION_STATUS_HEALTHY_EMPTY,
                correlation_id=corr,
                downstream_dependency="fetch_client_priority_actions",
            )
        )
    else:
        section_rows.append(
            build_trust_surface_section_record(
                section_name="task_rebuild_priority_counts",
                section_status=SECTION_STATUS_HEALTHY,
                correlation_id=corr,
                downstream_dependency="fetch_client_priority_actions",
            )
        )
    return {
        "surface_name": surface,
        "client_id": client_id,
        "correlation_id": corr,
        **fo,
        "sections": sorted(section_rows, key=lambda r: r.get("section_name", "")),
        "non_blocking": True,
    }


def build_command_center_health_summary(bundle_metadata: Mapping[str, Any]) -> Dict[str, Any]:
    """Roll up Command Centre trust metadata for ops (deterministic for fixed input)."""
    degraded = list(bundle_metadata.get("degraded_sections") or [])
    stale = list(bundle_metadata.get("stale_sections") or [])
    partial = list(bundle_metadata.get("partial_sections") or [])
    failed = list(bundle_metadata.get("failed_sections") or [])
    omitted = list(bundle_metadata.get("omitted_sections") or [])
    fallback_n = sum(1 for s in degraded + partial + failed + stale if s.get("fallback_used"))
    missing_corr = sum(1 for s in degraded + stale + partial + failed + omitted if not (s.get("correlation_id") or "").strip())
    return {
        "surface_name": bundle_metadata.get("surface_name"),
        "correlation_id": bundle_metadata.get("correlation_id"),
        "degraded_section_count": len(degraded),
        "stale_section_count": len(stale),
        "partial_section_count": len(partial),
        "failed_section_count": len(failed),
        "omitted_section_count": len(omitted),
        "missing_correlation_section_count": missing_corr,
        "fallback_section_count": fallback_n,
        "latest_rebuild_age_seconds": bundle_metadata.get("rebuild_age_seconds"),
        "health_posture": "NON_BLOCKING_OBSERVABILITY_ONLY",
    }


def build_portfolio_refresh_health_summary(metadata: Mapping[str, Any]) -> Dict[str, Any]:
    """Roll up portfolio summary trust metadata."""
    return build_command_center_health_summary(metadata)


def build_portfolio_summary_trust_surface_metadata(
    *,
    client_id: str,
    correlation_id: str,
    gap_engine_unavailable: bool,
    headline: Mapping[str, Any],
    gap_error: Optional[Exception] = None,
) -> Dict[str, Any]:
    """
    Trust metadata for GET /api/portfolio/compliance-summary composition.

    Read-only; does not alter headline or gap payloads.
    """
    degraded: List[Dict[str, Any]] = []
    stale: List[Dict[str, Any]] = []
    partial: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    omitted: List[Dict[str, Any]] = []

    if gap_engine_unavailable:
        partial.append(
            build_trust_surface_section_record(
                section_name="gap_engine_aggregate",
                section_status=SECTION_STATUS_DEGRADED_FALLBACK,
                correlation_id=correlation_id,
                failure_stage="aggregate_gap_counts_for_client",
                degraded_reason=str(gap_error) if gap_error else "gap_aggregate_unavailable",
                fallback_used=True,
                downstream_dependency="compliance_gap_sync.aggregate_gap_counts_for_client",
            )
        )

    st_head = str(headline.get("score_status") or "").strip().lower()
    if st_head in (SCORE_STATUS_STALE, "stale"):
        stale.append(
            build_trust_surface_section_record(
                section_name="persisted_portfolio_headline",
                section_status=SECTION_STATUS_STALE_DATA_POSSIBLE,
                correlation_id=correlation_id,
                degraded_reason=f"portfolio_score_status={headline.get('score_status')}",
                stale_data_possible=True,
                downstream_dependency="compliance_score.get_persisted_portfolio_headline_for_summary",
            )
        )

    try:
        stale_mix = int(headline.get("unknown_or_stale_property_count") or 0)
    except (TypeError, ValueError):
        stale_mix = 0
    if stale_mix > 0:
        partial.append(
            build_trust_surface_section_record(
                section_name="portfolio_stale_property_mix",
                section_status=SECTION_STATUS_PARTIAL_DATA,
                correlation_id=correlation_id,
                degraded_reason=f"unknown_or_stale_property_count={stale_mix}",
                stale_data_possible=True,
                downstream_dependency="compliance_score.aggregate_persisted_portfolio_headline",
            )
        )

    gen = datetime.now(timezone.utc)
    freshness_like = {
        "score_updated_at": headline.get("portfolio_last_calculated_at"),
        "tasks_refreshed_at": None,
        "risk_signals_updated_at": None,
    }
    fo = compute_trust_surface_freshness_observability(
        generated_at=gen,
        freshness=freshness_like,
        headline_score_status=str(headline.get("score_status") or "") or None,
    )
    health_in: Dict[str, Any] = {
        "surface_name": SURFACE_PORTFOLIO_SUMMARY_REFRESH,
        "correlation_id": correlation_id,
        "degraded_sections": degraded,
        "stale_sections": stale,
        "partial_sections": partial,
        "failed_sections": failed,
        "omitted_sections": omitted,
        "rebuild_age_seconds": fo.get("rebuild_age_seconds"),
    }
    return {
        "surface_name": SURFACE_PORTFOLIO_SUMMARY_REFRESH,
        "client_id": client_id,
        "correlation_id": correlation_id,
        "degraded_sections": sorted(degraded, key=lambda x: (x.get("section_name"), x.get("section_status"))),
        "stale_sections": sorted(stale, key=lambda x: (x.get("section_name"), x.get("section_status"))),
        "partial_sections": sorted(partial, key=lambda x: (x.get("section_name"), x.get("section_status"))),
        "failed_sections": sorted(failed, key=lambda x: (x.get("section_name"), x.get("section_status"))),
        "omitted_sections": sorted(omitted, key=lambda x: (x.get("section_name"), x.get("section_status"))),
        "operational_health": build_portfolio_refresh_health_summary(health_in),
        "missing_regeneration_marker_visible": headline.get("portfolio_score") is None
        and bool(headline.get("properties")),
        "non_blocking": True,
        **fo,
    }


def build_trust_surface_operational_snapshot(
    *,
    surfaces: Mapping[str, Mapping[str, Any]],
    generated_at_iso: str,
) -> Dict[str, Any]:
    """
    Combine per-surface trust metadata dicts (e.g. COMMAND_CENTER_REFRESH, PORTFOLIO_SUMMARY_REFRESH).

    ``surfaces`` values should include the same keys as bundle trust_surface_operational_metadata.
    """
    keys = sorted(surfaces.keys())
    summaries = {k: build_command_center_health_summary(surfaces[k]) for k in keys}
    return {
        "schema_version": "trust_surface_operational_snapshot_v1",
        "generated_at": generated_at_iso,
        "surfaces": {k: surfaces[k] for k in keys},
        "surface_health_summaries": {k: summaries[k] for k in keys},
        "audit_only_visibility": True,
        "non_blocking": True,
    }
