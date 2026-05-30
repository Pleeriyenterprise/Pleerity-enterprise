"""
Composed client Command Center payload: reuses unified tasks, risk signals, compliance score.
Single read-model for dashboard / integrations; does not duplicate prioritisation logic.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

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


def _priority_action_to_slim_urgent(
    a: Dict[str, Any],
    property_labels: Dict[str, str],
) -> Dict[str, Any]:
    """Map priority-stream row to Command Centre slim task without full unified enrichment."""
    from services.unified_tasks_service import ACTION_TO_SOURCE

    action_type = a.get("action_type") or ""
    source_type = ACTION_TO_SOURCE.get(action_type, "priority_action")
    source_id = (
        a.get("related_requirement_id")
        or a.get("related_work_order_id")
        or a.get("related_risk_signal_id")
        or a.get("related_issue_id")
        or a.get("related_invoice_id")
        or a.get("title")
    )
    task_id = f"{source_type}:{source_id}"
    prop_id = a.get("related_property_id")
    rid = a.get("related_requirement_id")
    jur = a.get("jurisdiction")
    meta: Dict[str, Any] = {
        "action_type": action_type,
        "requirement_code": a.get("requirement_code"),
    }
    if rid:
        meta["requirement_id"] = rid
        meta["linked_property_requirement_id"] = rid
    if a.get("gap_key"):
        meta["gap_key"] = a.get("gap_key")
    if a.get("consequence_category"):
        meta["consequence_category"] = a.get("consequence_category")
    if a.get("if_ignored"):
        meta["if_ignored"] = a.get("if_ignored")
    if a.get("closure_likelihood") is not None:
        meta["closure_likelihood"] = a.get("closure_likelihood")
    if a.get("operational_momentum_score") is not None:
        meta["operational_momentum_score"] = a.get("operational_momentum_score")
    if a.get("why_matters"):
        meta["why_matters"] = a.get("why_matters")
    if action_type.startswith("closure_"):
        meta["closure_momentum_action"] = True
    if action_type.startswith("execution_capacity_"):
        meta["execution_capacity_action"] = True
        meta["blockage_class"] = "execution_capacity_blockage"
    if action_type.startswith("coordination_"):
        meta["coordination_momentum_action"] = True
        meta["blockage_class"] = "coordination_failure"
    return {
        "id": task_id,
        "task_id": task_id,
        "title": a.get("title"),
        "description": (a.get("description") or "").strip() or None,
        "section": "urgent",
        "source_type": source_type,
        "property_id": prop_id,
        "requirement_id": rid,
        "jurisdiction": jur,
        "property_jurisdiction": jur,
        "property_label": property_labels.get(prop_id or "", "") if prop_id else None,
        "urgency_level": "high" if (a.get("severity") or "").lower() == "high" else "medium",
        "primary_action_type": action_type,
        "primary_action_label": a.get("recommended_action_label") or "View",
        "primary_action_url": a.get("recommended_url") or "/today",
        "metadata": meta,
    }


def _profile_mark(profile: Optional[Dict[str, Any]], key: str, started: float) -> None:
    if profile is None:
        return
    profile[key] = round((time.perf_counter() - started) * 1000, 1)


def _build_primary_pressure_fallback(
    *,
    urgent_open_total: int,
    compliance_status_summary: Dict[str, Any],
    reason: str,
) -> Dict[str, Any]:
    overdue = int(compliance_status_summary.get("requirements_overdue") or 0)
    missing = int(compliance_status_summary.get("requirements_missing_evidence") or 0)
    pressure_units = max(urgent_open_total, 0) + overdue + missing
    return {
        "groups": [
            {
                "group_key": "degraded_primary_pressure_fallback",
                "headline": "Pressure visibility degraded; fallback pressure indicators shown",
                "detail": "Primary pressure remains non-empty in degraded mode. Investigate full operational value recovery.",
                "consequence_category": "operationally_dangerous",
                "count": pressure_units,
                "affected_properties": compliance_status_summary.get("properties_at_risk_count"),
                "action_paths_available": 1,
                "unresolved_dependencies": pressure_units,
                "sample_ids": [],
            }
        ],
        "compressed_from": {
            "raw_pressure_items": pressure_units,
            "raw_active_risk_signals": None,
            "raw_open_issues": None,
            "raw_open_jobs": urgent_open_total,
        },
        "cognitive_load": {
            "estimated_raw_units": pressure_units,
            "compressed_decision_units": 1 if pressure_units > 0 else 0,
            "compression_ratio": float(pressure_units) if pressure_units > 0 else 1.0,
        },
        "snapshot_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "freshness_seconds": None,
            "stale": True,
            "degraded": True,
            "source": "primary_fallback_pressure",
            "recompute_reason": reason,
        },
    }


def _build_primary_compliance_fallback(reason: str) -> Dict[str, Any]:
    return {
        "compliance_percent": 0,
        "score_status": SCORE_STATUS_STALE,
        "score_updated_at": None,
        "requirements_overdue": 0,
        "requirements_expiring_soon": 0,
        "requirements_pending": 0,
        "requirements_missing_evidence": 0,
        "requirements_total": 0,
        "properties_at_risk_count": 0,
        "fallback_reason": reason,
    }


async def _load_maintenance_debt_urgent_rows(
    client_id: str,
    *,
    property_id_filter: Optional[str] = None,
    cap: int = 8,
) -> Tuple[List[Dict[str, Any]], int]:
    """Lightweight maintenance issues/WOs for degraded Command Centre — never false calm."""
    from database import database

    db = database.get_db()
    issue_q: Dict[str, Any] = {
        "client_id": client_id,
        "status": {"$nin": ["closed", "cancelled", "resolved"]},
    }
    wo_q: Dict[str, Any] = {
        "client_id": client_id,
        "status": {"$nin": ["COMPLETED", "VERIFIED", "CLOSED", "CANCELLED"]},
    }
    if property_id_filter:
        issue_q["property_id"] = property_id_filter
        wo_q["property_id"] = property_id_filter
    open_issues = await db.maintenance_issues.count_documents(issue_q)
    open_wos = await db.work_orders.count_documents(wo_q)
    debt_total = int(open_issues) + int(open_wos)
    if debt_total <= 0:
        return [], 0
    rows: List[Dict[str, Any]] = []
    async for wo in db.work_orders.find(wo_q, {"_id": 0, "work_order_id": 1, "status": 1, "description": 1}).sort(
        "updated_at", -1
    ).limit(cap):
        wid = wo.get("work_order_id")
        if not wid:
            continue
        st = (wo.get("status") or "OPEN").upper()
        label = "View active job" if st == "ASSIGNED" else "Continue maintenance workflow"
        rows.append(
            {
                "id": f"maintenance:wo:{wid}",
                "task_id": f"maintenance:wo:{wid}",
                "title": (wo.get("description") or "Maintenance job")[:120],
                "description": f"Active maintenance workflow ({st})",
                "section": "urgent",
                "source_type": "maintenance_work_order",
                "primary_action_type": "open_work_order",
                "primary_action_label": label,
                "primary_action_url": f"/operations/jobs/{wid}",
                "related_work_order_id": wid,
                "urgency_level": "high",
                "metadata": {"degraded_maintenance_fallback": True},
            }
        )
    if len(rows) < cap:
        async for issue in db.maintenance_issues.find(
            issue_q, {"_id": 0, "issue_id": 1, "description": 1, "status": 1}
        ).sort("updated_at", -1).limit(max(0, cap - len(rows))):
            iid = issue.get("issue_id")
            if not iid:
                continue
            rows.append(
                {
                    "id": f"maintenance:issue:{iid}",
                    "task_id": f"maintenance:issue:{iid}",
                    "title": (issue.get("description") or "Maintenance issue")[:120],
                    "description": "Open maintenance issue requires coordination",
                    "section": "urgent",
                    "source_type": "maintenance_issue",
                    "primary_action_type": "open_issue",
                    "primary_action_label": "Review issue",
                    "primary_action_url": f"/operations/issues/{iid}",
                    "related_issue_id": iid,
                    "urgency_level": "medium",
                    "metadata": {"degraded_maintenance_fallback": True},
                }
            )
    return rows, debt_total


def _build_primary_urgent_fallback(
    *,
    reason: str,
    compliance_status_summary: Dict[str, Any],
    maintenance_debt_total: int = 0,
    maintenance_urgent_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    overdue = int(compliance_status_summary.get("requirements_overdue") or 0)
    missing = int(compliance_status_summary.get("requirements_missing_evidence") or 0)
    maint_rows = list(maintenance_urgent_rows or [])
    urgent_open_total = max(0, overdue + missing, maintenance_debt_total, len(maint_rows))
    actions = list(maint_rows)
    if urgent_open_total > 0 and not actions:
        actions.append(
            {
                "id": "degraded:fallback:urgent",
                "task_id": "degraded:fallback:urgent",
                "title": "Urgent items remain active while pressure metrics refresh",
                "description": "Open the operations workspace to review and action urgent debt.",
                "section": "urgent",
                "source_type": "degraded_fallback",
                "property_id": None,
                "requirement_id": None,
                "jurisdiction": None,
                "property_jurisdiction": None,
                "property_label": None,
                "urgency_level": "high",
                "primary_action_type": "open_operations",
                "primary_action_label": "Review urgent items",
                "primary_action_url": "/operations",
                "metadata": {
                    "degraded": True,
                    "fallback_reason": reason,
                    "derived_overdue": overdue,
                    "derived_missing_evidence": missing,
                },
            }
        )
    elif overdue + missing > 0 and not any(a.get("id") == "degraded:fallback:urgent" for a in actions):
        actions.insert(
            0,
            {
                "id": "degraded:fallback:compliance",
                "task_id": "degraded:fallback:compliance",
                "title": "Compliance items need attention",
                "description": "Pressure metrics are refreshing; compliance debt remains visible.",
                "section": "urgent",
                "source_type": "degraded_fallback",
                "urgency_level": "high",
                "primary_action_type": "open_requirements",
                "primary_action_label": "Review compliance",
                "primary_action_url": "/requirements",
                "metadata": {"degraded": True, "fallback_reason": reason},
            },
        )
    return {
        "urgent_actions": actions[:12],
        "urgent_open_total": urgent_open_total,
        "urgent_continuation": max(0, urgent_open_total - len(actions)),
        "freshness": {
            "tasks_refreshed_at": datetime.now(timezone.utc).isoformat(),
            "projection": "primary",
            "freshness_scope": "primary_degraded_fallback",
            "fallback_reason": reason,
        },
    }


async def _load_urgent_slice_from_priority_stream(
    client_id: str,
    *,
    property_id_filter: Optional[str],
    portal_user_id: Optional[str],
    display_cap: int = 12,
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from services.client_priority_stream import fetch_client_priority_actions_primary
    from services.unified_tasks_service import _freshness_block, _load_property_labels

    t0 = time.perf_counter()
    compliance_actions = await fetch_client_priority_actions_primary(client_id, property_id_filter, 20)
    actions = list(compliance_actions)
    try:
        from services.operational_closure_conversion_service import (
            fetch_momentum_closure_priority_actions,
            merge_momentum_with_compliance_actions,
        )

        momentum = await fetch_momentum_closure_priority_actions(client_id, property_id_filter, limit=8)
        actions = merge_momentum_with_compliance_actions(momentum, compliance_actions, cap=20)
        try:
            from services.execution_capacity_network_service import (
                fetch_execution_capacity_priority_actions,
                merge_execution_with_momentum_actions,
            )

            exec_actions = await fetch_execution_capacity_priority_actions(client_id, property_id_filter, limit=5)
            actions = merge_execution_with_momentum_actions(exec_actions, actions, cap=22)
        except Exception as exc_exec:
            logger.debug("execution capacity merge skipped: %s", exc_exec)
        try:
            from services.assignment_execution_momentum_service import (
                fetch_coordination_momentum_priority_actions,
                merge_coordination_with_urgent,
            )

            coord_actions = await fetch_coordination_momentum_priority_actions(
                client_id, property_id_filter, limit=5
            )
            actions = merge_coordination_with_urgent(coord_actions, actions, cap=24)
        except Exception as exc_coord:
            logger.debug("coordination momentum merge skipped: %s", exc_coord)
        try:
            from services.workflow_stall_priority_service import (
                fetch_workflow_stall_priority_actions,
                merge_workflow_stall_with_urgent,
            )

            stall_actions = await fetch_workflow_stall_priority_actions(
                client_id, property_id_filter, limit=5
            )
            actions = merge_workflow_stall_with_urgent(stall_actions, actions, cap=24)
        except Exception as exc_stall:
            logger.debug("workflow stall merge skipped: %s", exc_stall)
        try:
            from services.recovery_priority_service import (
                fetch_operational_recovery_priority_actions,
                merge_recovery_with_urgent,
            )

            recovery_actions = await fetch_operational_recovery_priority_actions(
                client_id, property_id_filter, limit=5
            )
            actions = merge_recovery_with_urgent(recovery_actions, actions, cap=24)
        except Exception as exc_recovery:
            logger.debug("operational recovery merge skipped: %s", exc_recovery)
    except Exception as exc:
        logger.debug("momentum closure merge skipped: %s", exc)
    try:
        from services.operational_value_compression_service import attach_consequence_to_priority_action

        actions = [attach_consequence_to_priority_action(a) for a in actions]
    except Exception as exc:
        logger.debug("consequence enrich on priority stream skipped: %s", exc)
    _profile_mark(profile, "priority_stream_ms", t0)
    t1 = time.perf_counter()
    prop_ids = [a.get("related_property_id") for a in actions if a.get("related_property_id")]
    property_labels = await _load_property_labels(client_id, [str(x) for x in prop_ids if x])
    _profile_mark(profile, "property_labels_ms", t1)
    urgent_open_total = len(actions)
    slim_rows = [_priority_action_to_slim_urgent(a, property_labels) for a in actions[:display_cap]]
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
    now = datetime.now(timezone.utc)
    freshness = {
        "tasks_refreshed_at": now.isoformat(),
        "projection": "primary",
        "freshness_scope": "primary_priority_stream",
    }
    _profile_mark(profile, "freshness_ms", t2)
    capped_rows = slim_rows[:display_cap]
    continuation_count = max(0, urgent_open_total - len(capped_rows))
    return {
        "urgent_actions": capped_rows,
        "urgent_open_total": urgent_open_total,
        "urgent_continuation": continuation_count,
        "freshness": freshness,
    }


async def _primary_compliance_status_summary(
    client_id: str,
    *,
    property_id_filter: Optional[str],
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
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
        db = database.get_db()
        props = await db.properties.find(
            {"client_id": client_id},
            {
                "_id": 0,
                "property_id": 1,
                "compliance_score": 1,
                "compliance_last_calculated_at": 1,
                "score_status": 1,
            },
        ).to_list(200)
        from services.compliance_score import aggregate_persisted_portfolio_headline

        head = aggregate_persisted_portfolio_headline(props)
        head["properties"] = props
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

    cs = await _headline()
    gap_engine_counts = {
        "by_kind": {},
        "by_severity": {},
        "total_open": None,
        "_deferred": True,
    }
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
    bypass_cache: bool = False,
) -> Dict[str, Any]:
    """Fast Command Centre primary contract — urgent slice + headline compliance; secondary deferred."""
    from services.operational_surface_cache import (
        command_center_primary_cache_key,
        get_cached_command_center_primary,
        set_cached_command_center_primary,
    )

    ck = command_center_primary_cache_key(client_id, property_id_filter)
    if not bypass_cache:
        cached = get_cached_command_center_primary(ck)
        if cached:
            out = dict(cached["payload"])
            fresh = dict(out.get("freshness") or {})
            fresh["cache_hit"] = True
            fresh["cached_at"] = cached["cached_at"]
            fresh["cache_ttl_seconds"] = cached["ttl_seconds"]
            out["freshness"] = fresh
            if profile is not None:
                profile["cache_hit"] = True
            return out

    corr = ensure_trust_surface_correlation_id(SURFACE_COMMAND_CENTER_REFRESH, client_id, correlation_id)
    gen_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    gather_degraded_reasons: List[str] = []
    try:
        urgent_block, compliance_status_summary = await asyncio.wait_for(
            asyncio.gather(
                _load_urgent_slice_from_priority_stream(
                    client_id,
                    property_id_filter=property_id_filter,
                    portal_user_id=portal_user_id,
                    profile=profile,
                ),
                _primary_compliance_status_summary(
                    client_id, property_id_filter=property_id_filter, profile=profile
                ),
            ),
            timeout=12.0,
        )
    except Exception as exc:
        reason = f"primary_urgent_or_summary_timeout_or_failure:{str(exc)[:80]}"
        logger.warning("command_center primary urgent/summary fallback client_id=%s: %s", client_id, exc)
        gather_degraded_reasons.append(reason)
        compliance_status_summary = _build_primary_compliance_fallback(reason)
        maint_rows, maint_debt = await _load_maintenance_debt_urgent_rows(
            client_id, property_id_filter=property_id_filter
        )
        try:
            from services.recovery_priority_service import fetch_operational_recovery_priority_actions

            recovery_actions = await asyncio.wait_for(
                fetch_operational_recovery_priority_actions(client_id, property_id_filter, limit=4),
                timeout=6.0,
            )
            prop_ids = [a.get("related_property_id") for a in recovery_actions if a.get("related_property_id")]
            property_labels = await _load_property_labels(client_id, [str(x) for x in prop_ids if x])
            recovery_slim = [_priority_action_to_slim_urgent(a, property_labels) for a in recovery_actions]
            seen: set = set()
            merged_maint: List[Dict[str, Any]] = []
            for row in recovery_slim + maint_rows:
                key = row.get("related_work_order_id") or row.get("task_id") or row.get("id")
                if key and key in seen:
                    continue
                if key:
                    seen.add(key)
                merged_maint.append(row)
            maint_rows = merged_maint
            maint_debt = max(maint_debt, len(recovery_slim))
        except Exception as rec_exc:
            logger.debug("degraded fallback recovery merge skipped: %s", rec_exc)
        urgent_block = _build_primary_urgent_fallback(
            reason=reason,
            compliance_status_summary=compliance_status_summary,
            maintenance_debt_total=maint_debt,
            maintenance_urgent_rows=maint_rows,
        )
    _profile_mark(profile, "primary_gather_ms", t0)
    t_ov = time.perf_counter()
    operational_value_v1: Dict[str, Any] = {}
    ov_degraded_reason: Optional[str] = None
    try:
        from services.operational_value_compression_service import build_operational_value_bundle_v1

        operational_value_v1 = await asyncio.wait_for(
            build_operational_value_bundle_v1(
                client_id,
                property_id_filter,
            ),
            timeout=9.0,
        )
    except Exception as exc:
        logger.warning("operational_value_bundle_v1 failed client_id=%s: %s", client_id, exc)
        ov_degraded_reason = f"primary_timeout_or_failure:{str(exc)[:80]}"
        pressure_fallback = _build_primary_pressure_fallback(
            urgent_open_total=int(urgent_block.get("urgent_open_total") or 0),
            compliance_status_summary=compliance_status_summary,
            reason=ov_degraded_reason,
        )
        operational_value_v1 = {
            "available": False,
            "error": str(exc)[:200],
            "pressure_compression_v1": pressure_fallback,
            "snapshot_meta": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "freshness_seconds": None,
                "stale": True,
                "degraded": True,
                "source": "fallback",
                "recompute_reason": ov_degraded_reason,
            },
        }
    _profile_mark(profile, "operational_value_ms", t_ov)
    urgent_actions = urgent_block.get("urgent_actions") or []
    urgent_open = int(urgent_block.get("urgent_open_total") or len(urgent_actions))
    if (ov_degraded_reason or gather_degraded_reasons) and urgent_open == 0:
        maint_rows, maint_debt = await _load_maintenance_debt_urgent_rows(
            client_id, property_id_filter=property_id_filter
        )
        if maint_debt > 0:
            urgent_actions = maint_rows
            urgent_open = max(urgent_open, maint_debt, len(maint_rows))
    freshness = urgent_block.get("freshness") or {}
    freshness = {**freshness, "projection": "primary", "cache_hit": False}
    pc_block = operational_value_v1.get("pressure_compression_v1") or {}
    cl = pc_block.get("cognitive_load") or {}
    tasks_digest_summary = {
        "urgent_count": urgent_open,
        "upcoming_count": None,
        "in_progress_count": None,
        "habit": {"urgent_open_total": urgent_open},
        "urgent_continuation": urgent_block.get("urgent_continuation"),
        "pressure_compression": {
            "compressed_decision_units": cl.get("compressed_decision_units"),
            "estimated_raw_pressure_units": cl.get("estimated_raw_units"),
            "compression_ratio": cl.get("compression_ratio"),
        },
    }
    freshness_obs = compute_trust_surface_freshness_observability(
        generated_at=gen_at,
        freshness=freshness,
        headline_score_status=str(compliance_status_summary.get("score_status") or "") or None,
    )
    degraded_sections: List[Dict[str, Any]] = []
    for reason in gather_degraded_reasons:
        degraded_sections.append(
            build_trust_surface_section_record(
                section_name="primary_urgent_and_summary",
                section_status=SECTION_STATUS_DEGRADED_FALLBACK,
                correlation_id=corr,
                degraded_reason=reason,
                fallback_used=True,
                downstream_dependency="priority_stream_and_compliance_headline",
            )
        )
    if ov_degraded_reason:
        degraded_sections.append(
            build_trust_surface_section_record(
                section_name="operational_value_v1",
                section_status=SECTION_STATUS_DEGRADED_FALLBACK,
                correlation_id=corr,
                degraded_reason=ov_degraded_reason,
                fallback_used=True,
                downstream_dependency="operational_value_compression_service.build_operational_value_bundle_v1",
            )
        )
    trust_surface_operational_metadata: Dict[str, Any] = {
        "surface_name": SURFACE_COMMAND_CENTER_REFRESH,
        "client_id": client_id,
        "correlation_id": corr,
        "degraded_sections": degraded_sections,
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
                "degraded_sections": degraded_sections,
                "stale_sections": [],
                "partial_sections": [],
                "failed_sections": [],
                "omitted_sections": [],
            }
        ),
        "non_blocking": True,
        **freshness_obs,
    }
    out = {
        "projection": "primary",
        "urgent_actions": urgent_actions,
        "pressure_urgent_count": urgent_open,
        "pressure_urgent_rows": urgent_actions,
        "pressure_degraded": bool(ov_degraded_reason or gather_degraded_reasons),
        "pressure_status": "degraded" if (ov_degraded_reason or gather_degraded_reasons) else "ok",
        "pressure_fallback_reason": ov_degraded_reason or (gather_degraded_reasons[0] if gather_degraded_reasons else None),
        "pressure_message": (
            "Some pressure metrics are still refreshing. Urgent items remain visible below."
            if (ov_degraded_reason or gather_degraded_reasons)
            else None
        ),
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
        "operational_value_v1": operational_value_v1,
    }
    if not bypass_cache:
        set_cached_command_center_primary(ck, out)
    return out


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
