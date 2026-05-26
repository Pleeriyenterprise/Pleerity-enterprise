"""
Composed client Command Center payload: reuses unified tasks, risk signals, compliance score.
Single read-model for dashboard / integrations; does not duplicate prioritisation logic.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import database
from services import risk_signal_service
from services.scoring_semantics_v1 import SCORE_STATUS_STALE
from services.trust_surface_observability import (
    SECTION_STATUS_DEGRADED_FALLBACK,
    SECTION_STATUS_FAILED,
    SECTION_STATUS_OMITTED,
    SECTION_STATUS_PARTIAL_DATA,
    SECTION_STATUS_STALE_DATA_POSSIBLE,
    SURFACE_COMMAND_CENTER_REFRESH,
    SURFACE_TODAY_TASK_REBUILD,
    build_command_center_health_summary,
    build_trust_surface_section_record,
    compute_trust_surface_freshness_observability,
    ensure_trust_surface_correlation_id,
    normalize_trust_surface_context,
)
from services.unified_tasks_service import digest_from_unified_tasks_full, get_unified_tasks_for_client
from utils.compliance_fanout_log import compliance_fanout_extra

logger = logging.getLogger(__name__)

_LEVEL_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _slim_task(t: Dict[str, Any]) -> Dict[str, Any]:
    metadata = t.get("metadata") if isinstance(t.get("metadata"), dict) else {}
    jur = t.get("jurisdiction") or t.get("property_jurisdiction") or metadata.get("property_jurisdiction") or metadata.get(
        "jurisdiction"
    )
    rid = t.get("requirement_id") or metadata.get("requirement_id") or metadata.get("linked_property_requirement_id")
    out = {
        "id": t.get("id"),
        "task_id": t.get("id"),
        "title": t.get("title"),
        "description": (t.get("description") or "").strip() or None,
        "section": t.get("section"),
        "source_type": t.get("source_type"),
        "source_id": t.get("source_id"),
        "source_entity_type": t.get("source_entity_type") or t.get("source_type"),
        "source_entity_id": t.get("source_entity_id") or t.get("source_id"),
        "property_id": t.get("property_id"),
        "requirement_id": rid,
        "jurisdiction": jur,
        "property_jurisdiction": t.get("property_jurisdiction") or jur,
        "work_order_id": t.get("work_order_id"),
        "property_label": t.get("property_label"),
        "priority_level": t.get("urgency_level"),
        "urgency_level": t.get("urgency_level"),
        "due_date": t.get("due_date"),
        "overdue_days": t.get("overdue_days"),
        "impact_score": t.get("impact_score"),
        "impact_label": t.get("impact_label"),
        "filter_tags": t.get("filter_tags"),
        "metadata": metadata,
        "timing_label": metadata.get("timing_label"),
        "action_type": t.get("primary_action_type"),
        "primary_action_type": t.get("primary_action_type"),
        "primary_action_label": t.get("primary_action_label"),
        "primary_cta": {
            "label": t.get("primary_action_label"),
            "route": t.get("primary_action_url"),
            "action_type": t.get("primary_action_type"),
        },
        "secondary_actions": [
            {"action_type": "snooze", "label": "Hide from Today (snooze)"},
            {"action_type": "dismiss", "label": "Hide from Today"},
            {"action_type": "reviewed", "label": "Mark reviewed in Today"},
        ],
        "audit_metadata": {
            "task_id": t.get("id"),
            "source_type": t.get("source_type"),
            "action_context_type": t.get("action_context_type") or t.get("primary_action_type"),
        },
        "primary_action_url": t.get("primary_action_url"),
        "cta_url": t.get("primary_action_url") or "/tasks",
    }
    if str(t.get("source_type") or "").strip().lower() == "requirement":
        # Preserve converged requirement semantics for requirement-shaped rows only.
        for k in (
            "semantic_state",
            "workflow_class",
            "take_action",
            "requirement_display",
            "evidence_authority",
            "evidence_completeness",
            "guidance_target",
            "allowed_evidence_modes",
        ):
            if metadata.get(k) is not None:
                out[k] = metadata.get(k)
    return out


def _slim_risk(s: Dict[str, Any]) -> Dict[str, Any]:
    sid = s.get("signal_id") or ""
    return {
        "signal_id": sid,
        "risk_type": s.get("risk_type"),
        "risk_type_label_client": s.get("risk_type_label_client"),
        "recommended_action_client": s.get("recommended_action_client"),
        "risk_level": s.get("risk_level"),
        "property_id": s.get("property_id"),
        "description": (s.get("description") or "")[:240] or None,
        "status": s.get("status"),
        "cta_url": f"/operations/risk-signals?signal_id={sid}" if sid else "/operations/risk-signals",
    }


def _risk_sort_key(s: Dict[str, Any]):
    lvl = (s.get("risk_level") or "").lower()
    return (_LEVEL_ORDER.get(lvl, 9), s.get("updated_at") or s.get("generated_at") or "")


def _profile_mark(profile: Optional[Dict[str, Any]], key: str, started: float) -> None:
    if profile is None:
        return
    profile[key] = round((time.perf_counter() - started) * 1000, 1)


async def _load_urgent_slice_from_priority_stream(
    client_id: str,
    *,
    property_id_filter: Optional[str],
    portal_user_id: Optional[str],
    display_cap: int = 12,
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from services.client_priority_stream import fetch_client_priority_actions
    from services.unified_tasks_service import _action_to_task, _freshness_block, _load_property_labels

    t0 = time.perf_counter()
    now = datetime.now(timezone.utc)
    actions = await fetch_client_priority_actions(client_id, property_id_filter, 28)
    _profile_mark(profile, "priority_stream_ms", t0)
    t1 = time.perf_counter()
    prop_ids = [a.get("related_property_id") for a in actions if a.get("related_property_id")]
    property_labels = await _load_property_labels(client_id, [str(x) for x in prop_ids if x])
    _profile_mark(profile, "property_labels_ms", t1)
    urgent_open_total = 0
    slim_rows: List[Dict[str, Any]] = []
    for a in actions:
        t = _action_to_task(a, property_labels, now)
        if t.get("section") not in ("urgent", "in_progress"):
            continue
        urgent_open_total += 1
        if len(slim_rows) < display_cap:
            slim_rows.append(_slim_task(t))
    try:
        from services.ops_compliance_feature_flags import RENT_OPERATIONS, get_effective_flags
        from services.rent_attention_projection import (
            append_rent_to_command_center_urgent,
            list_rent_attention_tasks,
        )

        flags = await get_effective_flags(client_id)
        if flags.get(RENT_OPERATIONS):
            rent_tasks = await list_rent_attention_tasks(
                client_id,
                property_id_filter=property_id_filter,
                limit=4,
            )
            slim_rows = append_rent_to_command_center_urgent(slim_rows, rent_tasks)
            urgent_open_total += len(rent_tasks or [])
    except Exception as rent_exc:
        logger.warning("command_center primary rent merge failed: %s", rent_exc)
    t2 = time.perf_counter()
    freshness = await _freshness_block(client_id)
    _profile_mark(profile, "freshness_ms", t2)
    return {
        "urgent_actions": slim_rows[:display_cap],
        "urgent_open_total": urgent_open_total,
        "urgent_continuation": max(0, urgent_open_total - len(slim_rows)),
        "freshness": freshness,
    }


async def _primary_compliance_status_summary(
    client_id: str,
    *,
    property_id_filter: Optional[str],
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from services.compliance_gap_sync import aggregate_gap_counts_for_client
    from services.compliance_score import get_persisted_portfolio_headline_for_summary
    from services.operational_surface_cache import (
        compliance_score_cache_key,
        get_cached_compliance_score,
    )

    async def _headline() -> Dict[str, Any]:
        t0 = time.perf_counter()
        ck = compliance_score_cache_key(client_id)
        cached = get_cached_compliance_score(ck)
        if cached:
            out = dict(cached["payload"])
            fresh = dict(out.get("_cache_freshness") or {})
            fresh["cache_hit"] = True
            fresh["cached_at"] = cached["cached_at"]
            fresh["cache_ttl_seconds"] = cached["ttl_seconds"]
            out["_cache_freshness"] = fresh
            _profile_mark(profile, "compliance_cache_hit_ms", t0)
            return out
        head = await get_persisted_portfolio_headline_for_summary(client_id, skip_lazy_backfill=True)
        _profile_mark(profile, "compliance_persisted_headline_ms", t0)
        return {
            "score": head.get("score"),
            "grade": head.get("grade"),
            "color": head.get("color") or "gray",
            "message": head.get("score_status_message") or head.get("message"),
            "score_status": head.get("score_status"),
            "last_calculated_at": head.get("last_calculated_at") or head.get("portfolio_last_calculated_at"),
            "score_authority": "persisted_portfolio_aggregate",
            "score_status_message": head.get("score_status_message"),
            "properties_count": len(head.get("properties") or []),
            "stats": head.get("stats") if isinstance(head.get("stats"), dict) else {},
            "jurisdiction_compliance_notice": head.get("jurisdiction_compliance_notice") or {
                "active": False,
                "affected_property_ids": [],
                "affected_property_count": 0,
            },
            "jurisdiction_required": head.get("jurisdiction_required"),
            "compliance_confidence": head.get("compliance_confidence"),
            "jurisdiction_fallback_acknowledged": head.get("jurisdiction_fallback_acknowledged"),
            "client_default_jurisdiction": head.get("client_default_jurisdiction"),
            "_primary_stats_source": "persisted_headline",
        }

    async def _gaps() -> Dict[str, Any]:
        t0 = time.perf_counter()
        out = await aggregate_gap_counts_for_client(
            database.get_db(), client_id, property_id_filter
        )
        _profile_mark(profile, "gap_aggregate_ms", t0)
        return out

    cs, gap_engine_counts = await asyncio.gather(_headline(), _gaps())
    stats = cs.get("stats") if isinstance(cs.get("stats"), dict) else {}
    return {
        "score": cs.get("score"),
        "grade": cs.get("grade"),
        "message": cs.get("message"),
        "color": cs.get("color"),
        "properties_count": cs.get("properties_count"),
        "score_authority": cs.get("score_authority") or "persisted_portfolio_aggregate",
        "score_status": cs.get("score_status"),
        "last_calculated_at": cs.get("last_calculated_at"),
        "score_coverage": cs.get("score_coverage"),
        "score_status_message": cs.get("score_status_message"),
        "scoring_semantics_version": cs.get("scoring_semantics_version"),
        "properties_pending_score_recalc_count": cs.get("properties_pending_score_recalc_count"),
        "portfolio_score_recalc_pending_note": cs.get("portfolio_score_recalc_pending_note"),
        "compliance_counts_authority": "calculate_compliance_score.stats"
        if cs.get("_primary_stats_source") != "persisted_headline"
        else "persisted_portfolio_headline.stats",
        "requirements_overdue": stats.get("overdue"),
        "requirements_expiring_soon": stats.get("expiring_soon"),
        "requirements_pending": stats.get("pending"),
        "requirements_missing_evidence": stats.get("missing_evidence"),
        "requirements_total": stats.get("total_requirements"),
        "properties_at_risk_count": stats.get("properties_at_risk_count"),
        "gap_engine": gap_engine_counts,
        "hiua_operational_uncertainty": {
            "hiua_active": False,
            "hiua_open_gap_count": 0,
            "hiua_reason_codes": [],
            "hiua_gap_details": [],
            "hiua_command_centre_message": None,
            "hiua_command_centre_tooltip": None,
            "hiua_command_centre_filter_label": None,
            "hiua_digest_line": None,
            "hiua_report_framing_notice": None,
            "_deferred": True,
        },
        "jurisdiction_compliance_notice": cs.get("jurisdiction_compliance_notice") or {},
        "jurisdiction_required": cs.get("jurisdiction_required"),
        "compliance_confidence": cs.get("compliance_confidence"),
        "jurisdiction_fallback_acknowledged": cs.get("jurisdiction_fallback_acknowledged"),
        "client_default_jurisdiction": cs.get("client_default_jurisdiction"),
        "_primary_projection": True,
    }


async def get_command_center_primary_bundle(
    client_id: str,
    *,
    predictive_enabled: bool,
    property_id_filter: Optional[str] = None,
    portal_user_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Fast Command Centre primary contract — urgent slice + headline compliance; secondary deferred."""
    corr = ensure_trust_surface_correlation_id(SURFACE_COMMAND_CENTER_REFRESH, client_id, correlation_id)
    gen_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    urgent_block, compliance_status_summary = await asyncio.gather(
        _load_urgent_slice_from_priority_stream(
            client_id,
            property_id_filter=property_id_filter,
            portal_user_id=portal_user_id,
            profile=profile,
        ),
        _primary_compliance_status_summary(
            client_id, property_id_filter=property_id_filter, profile=profile
        ),
    )
    _profile_mark(profile, "primary_gather_ms", t0)
    urgent_actions = urgent_block.get("urgent_actions") or []
    urgent_open = int(urgent_block.get("urgent_open_total") or len(urgent_actions))
    freshness = urgent_block.get("freshness") or {}
    freshness = {**freshness, "projection": "primary", "cache_hit": False}
    tasks_digest_summary = {
        "urgent_count": urgent_open,
        "upcoming_count": None,
        "in_progress_count": None,
        "habit": {"urgent_open_total": urgent_open},
        "urgent_continuation": urgent_block.get("urgent_continuation"),
    }
    freshness_obs = compute_trust_surface_freshness_observability(
        generated_at=gen_at,
        freshness=freshness,
        headline_score_status=str(compliance_status_summary.get("score_status") or "") or None,
    )
    trust_surface_operational_metadata: Dict[str, Any] = {
        "surface_name": SURFACE_COMMAND_CENTER_REFRESH,
        "client_id": client_id,
        "correlation_id": corr,
        "degraded_sections": [],
        "stale_sections": [],
        "partial_sections": [
            build_trust_surface_section_record(
                section_name="command_center_secondary",
                section_status=SECTION_STATUS_PARTIAL_DATA,
                correlation_id=corr,
                degraded_reason="secondary_projection_deferred",
                downstream_dependency="get_command_center_secondary_bundle",
            )
        ],
        "failed_sections": [],
        "omitted_sections": [],
        "operational_health": build_command_center_health_summary(
            {
                "surface_name": SURFACE_COMMAND_CENTER_REFRESH,
                "correlation_id": corr,
                "degraded_sections": [],
                "stale_sections": [],
                "partial_sections": [],
                "failed_sections": [],
                "omitted_sections": [],
            }
        ),
        "non_blocking": True,
        **freshness_obs,
    }
    return {
        "projection": "primary",
        "urgent_actions": urgent_actions,
        "upcoming_risks": [],
        "recent_activity": [],
        "compliance_status_summary": compliance_status_summary,
        "tasks_digest_summary": tasks_digest_summary,
        "freshness": freshness,
        "trust_surface_operational_metadata": trust_surface_operational_metadata,
        "secondary_sections_deferred": True,
        "primary_complete": True,
        "deferred_sections": ["upcoming_risks", "recent_activity", "hiua_operational_uncertainty"],
        "predictive_enabled": predictive_enabled,
    }


async def get_command_center_secondary_bundle(
    client_id: str,
    *,
    predictive_enabled: bool,
    property_id_filter: Optional[str] = None,
    portal_user_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    include_secondary_sections: bool = True,
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Deferred Command Centre blocks: risks, activity, HIUA (optional), full compliance enrichment."""
    corr = ensure_trust_surface_correlation_id(SURFACE_COMMAND_CENTER_REFRESH, client_id, correlation_id)
    partial_bundle = await get_command_center_bundle(
        client_id,
        predictive_enabled=predictive_enabled,
        property_id_filter=property_id_filter,
        portal_user_id=portal_user_id,
        correlation_id=corr,
        include_secondary_sections=include_secondary_sections,
    )
    return {
        "projection": "secondary",
        "upcoming_risks": partial_bundle.get("upcoming_risks") or [],
        "recent_activity": partial_bundle.get("recent_activity") or [],
        "compliance_status_summary": partial_bundle.get("compliance_status_summary") or {},
        "tasks_digest_summary": partial_bundle.get("tasks_digest_summary") or {},
        "freshness": partial_bundle.get("freshness") or {},
        "trust_surface_operational_metadata": partial_bundle.get("trust_surface_operational_metadata") or {},
        "secondary_sections_deferred": False,
    }


async def get_command_center_bundle(
    client_id: str,
    *,
    predictive_enabled: bool,
    property_id_filter: Optional[str] = None,
    portal_user_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    include_secondary_sections: bool = False,
) -> Dict[str, Any]:
    """
    Return urgent_actions, upcoming_risks, recent_activity, compliance_status_summary
    plus tasks_digest_summary and freshness for cohesion with /tasks/digest.

    Optional ``correlation_id`` is propagated through composed readers for observability (additive).
    """
    urgent_actions: List[Dict[str, Any]] = []
    digest: Dict[str, Any] = {}
    full_tasks: Dict[str, Any] = {}
    upcoming_risks: List[Dict[str, Any]] = []
    prow_scoped: Optional[Dict[str, Any]] = None

    corr = ensure_trust_surface_correlation_id(SURFACE_COMMAND_CENTER_REFRESH, client_id, correlation_id)
    gen_at = datetime.now(timezone.utc)
    degraded_sections: List[Dict[str, Any]] = []
    stale_sections: List[Dict[str, Any]] = []
    partial_sections: List[Dict[str, Any]] = []
    failed_sections: List[Dict[str, Any]] = []
    omitted_sections: List[Dict[str, Any]] = []

    digest_ctx = {
        **normalize_trust_surface_context(
            surface_name=SURFACE_COMMAND_CENTER_REFRESH,
            client_id=client_id,
            correlation_id=corr,
            property_id_filter=property_id_filter,
            portal_user_id=portal_user_id,
        )
    }
    tasks_ctx = {
        **normalize_trust_surface_context(
            surface_name=SURFACE_TODAY_TASK_REBUILD,
            client_id=client_id,
            correlation_id=corr,
            property_id_filter=property_id_filter,
            portal_user_id=portal_user_id,
        )
    }

    async def _load_unified_tasks() -> None:
        nonlocal digest, full_tasks, urgent_actions
        full_tasks = await get_unified_tasks_for_client(
            client_id,
            property_id_filter=property_id_filter,
            raw_limit=45,
            portal_user_id=portal_user_id,
            trust_surface_composition_context=tasks_ctx,
            surface_profile="command_center",
        )
        digest = digest_from_unified_tasks_full(full_tasks, activity_limit=20)
        tasks = full_tasks.get("tasks") or {}
        urgent = tasks.get("urgent") or []
        in_prog = tasks.get("in_progress") or []
        for t in (urgent[:10] + in_prog[:6]):
            urgent_actions.append(_slim_task(t))
        try:
            from services.ops_compliance_feature_flags import RENT_OPERATIONS, get_effective_flags
            from services.rent_attention_projection import (
                append_rent_to_command_center_urgent,
                list_rent_attention_tasks,
            )

            flags = await get_effective_flags(client_id)
            if flags.get(RENT_OPERATIONS):
                rent_tasks = await list_rent_attention_tasks(
                    client_id,
                    property_id_filter=property_id_filter,
                    limit=6,
                )
                urgent_actions = append_rent_to_command_center_urgent(urgent_actions, rent_tasks)
        except Exception as rent_exc:
            logger.warning("command_center rent attention merge failed: %s", rent_exc)

    async def _load_risk_signals() -> List[Dict[str, Any]]:
        if not predictive_enabled:
            omitted_sections.append(
                build_trust_surface_section_record(
                    section_name="risk_signals",
                    section_status=SECTION_STATUS_OMITTED,
                    correlation_id=corr,
                    degraded_reason="predictive_maintenance_disabled",
                    downstream_dependency="risk_signal_service.get_risk_signals_for_client",
                )
            )
            return []
        try:
            r = await risk_signal_service.get_risk_signals_for_client(
                client_id,
                property_id_filter=property_id_filter,
                status_filter=risk_signal_service.STATUS_ACTIVE,
                limit=60,
            )
            signals = [s for s in (r.get("signals") or []) if (s.get("status") or "").lower() == "active"]
            signals.sort(key=_risk_sort_key)
            return [_slim_risk(s) for s in signals[:18]]
        except Exception as e:
            failed_sections.append(
                build_trust_surface_section_record(
                    section_name="risk_signals",
                    section_status=SECTION_STATUS_FAILED,
                    correlation_id=corr,
                    failure_stage="get_risk_signals_for_client",
                    degraded_reason=str(e),
                    fallback_used=True,
                    downstream_dependency="risk_signal_service.get_risk_signals_for_client",
                )
            )
            logger.warning(
                "command_center risk signals failed: %s",
                e,
                extra=compliance_fanout_extra(
                    op="trust_surface",
                    stage="risk_signals_failed",
                    client_id=client_id,
                    property_id=property_id_filter,
                    correlation_id=corr,
                    surface_name=SURFACE_COMMAND_CENTER_REFRESH,
                    section_name="risk_signals",
                    degraded_reason=str(e),
                    fallback_used=True,
                    downstream_dependency="risk_signal_service.get_risk_signals_for_client",
                ),
            )
            return []

    async def _build_compliance_status_summary() -> Dict[str, Any]:
        nonlocal prow_scoped
        from services.compliance_score import calculate_compliance_score
        from services.operational_surface_cache import (
            compliance_score_cache_key,
            get_cached_compliance_score,
            set_cached_compliance_score,
        )

        async def _score():
            ck = compliance_score_cache_key(client_id)
            cached = get_cached_compliance_score(ck)
            if cached:
                out = dict(cached["payload"])
                fresh = dict(out.get("_cache_freshness") or {})
                fresh["cache_hit"] = True
                fresh["cached_at"] = cached["cached_at"]
                fresh["cache_ttl_seconds"] = cached["ttl_seconds"]
                out["_cache_freshness"] = fresh
                return out
            cs = await calculate_compliance_score(client_id)
            set_cached_compliance_score(ck, cs)
            return cs

        async def _gaps():
            from services.compliance_gap_sync import aggregate_gap_counts_for_client

            return await aggregate_gap_counts_for_client(
                database.get_db(), client_id, property_id_filter
            )

        async def _hiua():
            if not include_secondary_sections:
                return {
                    "hiua_active": False,
                    "hiua_open_gap_count": 0,
                    "hiua_reason_codes": [],
                    "hiua_gap_details": [],
                    "hiua_command_centre_message": None,
                    "hiua_command_centre_tooltip": None,
                    "hiua_command_centre_filter_label": None,
                    "hiua_digest_line": None,
                    "hiua_report_framing_notice": None,
                    "_deferred": True,
                }
            from services.hiua_operational_uncertainty import hiua_tenant_operational_summary

            _db = database.get_db()
            _pids = {str(property_id_filter)} if property_id_filter else None
            return await hiua_tenant_operational_summary(
                _db, client_id, property_ids=_pids, max_gaps_scan=120, max_detail=10
            )

        cs, gap_engine_counts, hiua_block = await asyncio.gather(
            _score(),
            _gaps(),
            _hiua(),
            return_exceptions=True,
        )

        if isinstance(cs, BaseException):
            raise cs
        if isinstance(gap_engine_counts, BaseException):
            e = gap_engine_counts
            partial_sections.append(
                build_trust_surface_section_record(
                    section_name="gap_engine_aggregate",
                    section_status=SECTION_STATUS_PARTIAL_DATA,
                    correlation_id=corr,
                    failure_stage="aggregate_gap_counts_for_client",
                    degraded_reason=str(e),
                    fallback_used=True,
                    downstream_dependency="compliance_gap_sync.aggregate_gap_counts_for_client",
                )
            )
            logger.warning(
                "command_center gap_engine aggregate failed: %s",
                e,
                extra=compliance_fanout_extra(
                    op="trust_surface",
                    stage="gap_engine_failed",
                    client_id=client_id,
                    property_id=property_id_filter,
                    correlation_id=corr,
                    surface_name=SURFACE_COMMAND_CENTER_REFRESH,
                    section_name="gap_engine_aggregate",
                    degraded_reason=str(e),
                    fallback_used=True,
                    downstream_dependency="compliance_gap_sync.aggregate_gap_counts_for_client",
                ),
            )
            gap_engine_counts = {"by_kind": {}, "by_severity": {}, "total_open": 0}
        if isinstance(hiua_block, BaseException):
            e = hiua_block
            partial_sections.append(
                build_trust_surface_section_record(
                    section_name="hiua_operational_uncertainty",
                    section_status=SECTION_STATUS_DEGRADED_FALLBACK,
                    correlation_id=corr,
                    failure_stage="hiua_tenant_operational_summary",
                    degraded_reason=str(e),
                    fallback_used=True,
                    downstream_dependency="hiua_operational_uncertainty.hiua_tenant_operational_summary",
                )
            )
            logger.warning(
                "command_center hiua summary failed: %s",
                e,
                extra=compliance_fanout_extra(
                    op="trust_surface",
                    stage="hiua_failed",
                    client_id=client_id,
                    property_id=property_id_filter,
                    correlation_id=corr,
                    surface_name=SURFACE_COMMAND_CENTER_REFRESH,
                    section_name="hiua_operational_uncertainty",
                    degraded_reason=str(e),
                    fallback_used=True,
                    downstream_dependency="hiua_operational_uncertainty.hiua_tenant_operational_summary",
                ),
            )
            hiua_block = {
                "hiua_active": False,
                "hiua_open_gap_count": 0,
                "hiua_reason_codes": [],
                "hiua_gap_details": [],
                "hiua_command_centre_message": None,
                "hiua_command_centre_tooltip": None,
                "hiua_command_centre_filter_label": None,
                "hiua_digest_line": None,
                "hiua_report_framing_notice": None,
            }

        stats = cs.get("stats") if isinstance(cs.get("stats"), dict) else {}
        notice = cs.get("jurisdiction_compliance_notice") or {}
        jreq_ids = list(cs.get("jurisdiction_required_property_ids") or [])
        jreq = bool(cs.get("jurisdiction_required"))
        jconf = cs.get("compliance_confidence")
        if property_id_filter:
            aff = [x for x in (notice.get("affected_property_ids") or []) if x == property_id_filter]
            notice = {
                **notice,
                "affected_property_ids": aff,
                "affected_property_count": len(aff),
                "active": bool(aff),
                "compliance_basis": "default_fallback" if aff else None,
            }
            prow_scoped = next(
                (x for x in (cs.get("property_breakdown") or []) if x.get("property_id") == property_id_filter),
                None,
            )
            if prow_scoped is not None:
                jreq = bool(prow_scoped.get("jurisdiction_required"))
                jconf = prow_scoped.get("compliance_confidence")
            else:
                jreq = property_id_filter in jreq_ids
                jconf = "fallback" if jreq else "explicit"
        summary_out: Dict[str, Any] = {
            "score": cs.get("score"),
            "grade": cs.get("grade"),
            "message": cs.get("message"),
            "color": cs.get("color"),
            "properties_count": cs.get("properties_count"),
            "score_authority": cs.get("score_authority"),
            "score_status": cs.get("score_status"),
            "last_calculated_at": cs.get("last_calculated_at") or cs.get("portfolio_last_calculated_at"),
            "score_coverage": cs.get("score_coverage"),
            "score_status_message": cs.get("score_status_message"),
            "scoring_semantics_version": cs.get("scoring_semantics_version"),
            "properties_pending_score_recalc_count": cs.get("properties_pending_score_recalc_count"),
            "portfolio_score_recalc_pending_note": cs.get("portfolio_score_recalc_pending_note"),
            "compliance_counts_authority": "calculate_compliance_score.stats",
            "requirements_overdue": stats.get("overdue"),
            "requirements_expiring_soon": stats.get("expiring_soon"),
            "requirements_pending": stats.get("pending"),
            "requirements_missing_evidence": stats.get("missing_evidence"),
            "requirements_total": stats.get("total_requirements"),
            "properties_at_risk_count": stats.get("properties_at_risk_count"),
            "gap_engine": gap_engine_counts,
            "hiua_operational_uncertainty": hiua_block,
            "jurisdiction_compliance_notice": notice,
            "jurisdiction_required": jreq,
            "compliance_confidence": jconf,
            "jurisdiction_fallback_acknowledged": cs.get("jurisdiction_fallback_acknowledged"),
            "client_default_jurisdiction": cs.get("client_default_jurisdiction"),
        }
        if property_id_filter and prow_scoped:
            summary_out["scoped_property_jurisdiction"] = {
                "property_id": property_id_filter,
                "compliance_basis": prow_scoped.get("compliance_basis"),
                "effective_jurisdiction_label": prow_scoped.get("effective_jurisdiction_label"),
                "jurisdiction_required": prow_scoped.get("jurisdiction_required"),
                "compliance_confidence": prow_scoped.get("compliance_confidence"),
            }
        return summary_out

    compliance_status_summary: Dict[str, Any] = {}
    unified_exc, compliance_exc, risks_list = await asyncio.gather(
        _load_unified_tasks(),
        _build_compliance_status_summary(),
        _load_risk_signals(),
        return_exceptions=True,
    )
    if isinstance(unified_exc, BaseException):
        failed_sections.append(
            build_trust_surface_section_record(
                section_name="unified_tasks_urgent_actions",
                section_status=SECTION_STATUS_FAILED,
                correlation_id=corr,
                failure_stage="get_unified_tasks_for_client",
                degraded_reason=str(unified_exc),
                fallback_used=True,
                downstream_dependency="unified_tasks_service.get_unified_tasks_for_client",
            )
        )
        logger.warning(
            "command_center unified tasks failed: %s",
            unified_exc,
            extra=compliance_fanout_extra(
                op="trust_surface",
                stage="unified_tasks_failed",
                client_id=client_id,
                property_id=property_id_filter,
                correlation_id=corr,
                surface_name=SURFACE_COMMAND_CENTER_REFRESH,
                section_name="unified_tasks_urgent_actions",
                degraded_reason=str(unified_exc),
                fallback_used=True,
                downstream_dependency="unified_tasks_service.get_unified_tasks_for_client",
            ),
        )
        digest = {"summary": {}, "freshness": {}, "activity_feed": []}
    if isinstance(compliance_exc, BaseException):
        failed_sections.append(
            build_trust_surface_section_record(
                section_name="compliance_score_summary",
                section_status=SECTION_STATUS_FAILED,
                correlation_id=corr,
                failure_stage="calculate_compliance_score",
                degraded_reason=str(compliance_exc),
                fallback_used=True,
                downstream_dependency="compliance_score.calculate_compliance_score",
            )
        )
        logger.warning(
            "command_center compliance score failed: %s",
            compliance_exc,
            extra=compliance_fanout_extra(
                op="trust_surface",
                stage="compliance_score_failed",
                client_id=client_id,
                property_id=property_id_filter,
                correlation_id=corr,
                surface_name=SURFACE_COMMAND_CENTER_REFRESH,
                section_name="compliance_score_summary",
                degraded_reason=str(compliance_exc),
                fallback_used=True,
                downstream_dependency="compliance_score.calculate_compliance_score",
            ),
        )
        compliance_status_summary = {
            "score": None,
            "grade": None,
            "message": "Compliance score summary unavailable.",
            "color": "gray",
            "score_authority": "unavailable",
            "score_status": "unavailable",
            "last_calculated_at": None,
            "score_coverage": None,
            "score_status_message": None,
            "scoring_semantics_version": None,
            "properties_pending_score_recalc_count": None,
            "portfolio_score_recalc_pending_note": None,
            "gap_engine": {"by_kind": {}, "by_severity": {}, "total_open": 0},
            "hiua_operational_uncertainty": {
                "hiua_active": False,
                "hiua_open_gap_count": 0,
                "hiua_reason_codes": [],
                "hiua_gap_details": [],
                "hiua_command_centre_message": None,
                "hiua_command_centre_tooltip": None,
                "hiua_command_centre_filter_label": None,
                "hiua_digest_line": None,
                "hiua_report_framing_notice": None,
            },
            "jurisdiction_compliance_notice": {
                "active": False,
                "compliance_basis": None,
                "affected_property_ids": [],
                "affected_property_count": 0,
            },
            "jurisdiction_required": None,
            "compliance_confidence": None,
            "jurisdiction_fallback_acknowledged": None,
            "client_default_jurisdiction": None,
        }
    else:
        compliance_status_summary = compliance_exc
    if isinstance(risks_list, BaseException):
        upcoming_risks = []
    else:
        upcoming_risks = risks_list

    recent_activity = digest.get("activity_feed") or []

    st = str(compliance_status_summary.get("score_status") or "").strip().lower()
    if st in (SCORE_STATUS_STALE, "stale", "partial"):
        stale_sections.append(
            build_trust_surface_section_record(
                section_name="compliance_score_summary",
                section_status=SECTION_STATUS_STALE_DATA_POSSIBLE,
                correlation_id=corr,
                degraded_reason=f"score_status={compliance_status_summary.get('score_status')}",
                stale_data_possible=True,
                downstream_dependency="compliance_score.calculate_compliance_score",
            )
        )

    freshness_obs = compute_trust_surface_freshness_observability(
        generated_at=gen_at,
        freshness=digest.get("freshness") or {},
        headline_score_status=str(compliance_status_summary.get("score_status") or "") or None,
    )
    health_input: Dict[str, Any] = {
        "surface_name": SURFACE_COMMAND_CENTER_REFRESH,
        "correlation_id": corr,
        "degraded_sections": degraded_sections,
        "stale_sections": stale_sections,
        "partial_sections": partial_sections,
        "failed_sections": failed_sections,
        "omitted_sections": omitted_sections,
        "rebuild_age_seconds": freshness_obs.get("rebuild_age_seconds"),
    }
    trust_surface_operational_metadata: Dict[str, Any] = {
        "surface_name": SURFACE_COMMAND_CENTER_REFRESH,
        "client_id": client_id,
        "correlation_id": corr,
        "degraded_sections": sorted(degraded_sections, key=lambda x: (x.get("section_name"), x.get("section_status"))),
        "stale_sections": sorted(stale_sections, key=lambda x: (x.get("section_name"), x.get("section_status"))),
        "partial_sections": sorted(partial_sections, key=lambda x: (x.get("section_name"), x.get("section_status"))),
        "failed_sections": sorted(failed_sections, key=lambda x: (x.get("section_name"), x.get("section_status"))),
        "omitted_sections": sorted(omitted_sections, key=lambda x: (x.get("section_name"), x.get("section_status"))),
        "operational_health": build_command_center_health_summary(health_input),
        "non_blocking": True,
        **freshness_obs,
    }

    return {
        "urgent_actions": urgent_actions,
        "upcoming_risks": upcoming_risks,
        "recent_activity": recent_activity,
        "compliance_status_summary": compliance_status_summary,
        "tasks_digest_summary": digest.get("summary") or {},
        "freshness": digest.get("freshness") or {},
        "trust_surface_operational_metadata": trust_surface_operational_metadata,
        "secondary_sections_deferred": not include_secondary_sections,
    }
