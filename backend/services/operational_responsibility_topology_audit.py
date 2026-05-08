from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from services.trigger_propagation_audit import (
    BLOCKED_FOR_RUNTIME_ENFORCEMENT,
    CACHE_INVALIDATION_UNKNOWN,
    COMPLIANCE_CRITICAL,
    CONSUMERS,
    DERIVED_ON_READ,
    FRAGMENTED_BEHAVIOR,
    FRAGMENTED_MULTI_SOURCE_REFRESH,
    FRAGMENTED_PROPAGATION,
    LIVE_READ_PROJECTION,
    NO_KNOWN_PROPAGATION,
    NO_OPERATIONAL_FOLLOWTHROUGH,
    OPERATIONAL_CRITICAL,
    OPERATIONAL_GAP,
    PARTIAL_PROPAGATION,
    PERIODIC_JOB,
    PERIODIC_ONLY_REFRESH,
    ROLLUP_STALE_RISK,
    SAFETY_CRITICAL,
    SCHEDULED_RECALC,
    SCORE_REGENERATION,
    SEMANTIC_COLLAPSE_RISK,
    SEMANTIC_TRANSITIONS,
    TASK_REBUILD as REACTION_TASK_REBUILD,
    UNKNOWN,
    UNKNOWN_GUARANTEE,
    UNKNOWN_REFRESH_GUARANTEE,
    build_expected_vs_current_matrix,
)

LOW_TOPOLOGY_RISK = "LOW_TOPOLOGY_RISK"
MODERATE_TOPOLOGY_RISK = "MODERATE_TOPOLOGY_RISK"
HIGH_TOPOLOGY_RISK = "HIGH_TOPOLOGY_RISK"
CRITICAL_TOPOLOGY_RISK = "CRITICAL_TOPOLOGY_RISK"

# --- Part A: ownership domains (governance labels, not runtime modes) ---
SEMANTIC_AUTHORITY = "SEMANTIC_AUTHORITY"
READ_PROJECTION = "READ_PROJECTION"
TASK_REBUILD = "TASK_REBUILD"
OPERATIONAL_ORCHESTRATION = "OPERATIONAL_ORCHESTRATION"
REMINDER_ORCHESTRATION = "REMINDER_ORCHESTRATION"
SLA_ORCHESTRATION = "SLA_ORCHESTRATION"
REPORT_PROJECTION = "REPORT_PROJECTION"
SCORING_REGENERATION = "SCORING_REGENERATION"
CACHE_REFRESH = "CACHE_REFRESH"
USER_VISIBILITY = "USER_VISIBILITY"
NOTIFICATION_DISPATCH = "NOTIFICATION_DISPATCH"
UNKNOWN_OWNERSHIP = "UNKNOWN_OWNERSHIP"

# Part C: ownership quality
CLEAR_SINGLE_OWNER = "CLEAR_SINGLE_OWNER"
CLEAR_MULTI_STAGE_CHAIN = "CLEAR_MULTI_STAGE_CHAIN"
SHARED_BUT_DEFINED = "SHARED_BUT_DEFINED"
FRAGMENTED = "FRAGMENTED"
AMBIGUOUS = "AMBIGUOUS"
NO_CLEAR_OWNER = "NO_CLEAR_OWNER"

# Part D: topology failure modes
NO_OPERATIONAL_CONSUMER = "NO_OPERATIONAL_CONSUMER"
DERIVED_WITHOUT_ACTION_PATH = "DERIVED_WITHOUT_ACTION_PATH"
MULTIPLE_REFRESH_AUTHORITIES = "MULTIPLE_REFRESH_AUTHORITIES"
STALE_READ_DEPENDENCY = "STALE_READ_DEPENDENCY"
PERIODIC_SWEEP_ONLY = "PERIODIC_SWEEP_ONLY"
NO_ESCALATION_OWNER = "NO_ESCALATION_OWNER"
NO_FALLBACK_OWNER = "NO_FALLBACK_OWNER"
VISIBILITY_WITHOUT_ORCHESTRATION = "VISIBILITY_WITHOUT_ORCHESTRATION"
ORCHESTRATION_WITHOUT_CONFIRMATION = "ORCHESTRATION_WITHOUT_CONFIRMATION"
UNKNOWN_REFRESH_BOUNDARY = "UNKNOWN_REFRESH_BOUNDARY"

_STATE_MODEL_LIMITATION = (
    "Topology is derived from the static propagation audit matrix and declared subsystem names; "
    "it does not reflect org-specific runbooks or on-call boundaries."
)
_RUNTIME_CONVERGENCE_LIMITATION = (
    "Handoff chains are audit narratives aligned to known code paths, not verified distributed traces."
)

_RISK_ORDER = (
    LOW_TOPOLOGY_RISK,
    MODERATE_TOPOLOGY_RISK,
    HIGH_TOPOLOGY_RISK,
    CRITICAL_TOPOLOGY_RISK,
)

_HANDOFF_BASE: Dict[str, List[str]] = {
    "REMINDER_ENGINE": [
        "requirement_evidence_authority",
        "requirement_truth",
        "semantic_state_adapter_observe",
        "reminder_truth_service",
        "periodic_reminder_job",
    ],
    "COMMAND_CENTER": [
        "requirement_truth",
        "unified_tasks_service",
        "command_center_read_composition",
    ],
    "TODAY_VIEW": [
        "requirement_truth",
        "priority_stream",
        "unified_tasks_service",
        "today_view_projection",
    ],
    "PORTFOLIO_SCORE": [
        "requirement_truth",
        "compliance_score_calculator",
        "portfolio_score_aggregate",
    ],
    "PROPERTY_SUMMARY": [
        "requirement_truth",
        "unified_tasks_service",
        "property_summary_projection",
    ],
    "REPORT_EXPORT": [
        "requirement_evidence_authority",
        "reporting_service",
        "report_row_projection",
    ],
    "UNIFIED_TASKS": [
        "requirement_truth",
        "unified_tasks_service",
        "task_rebuild_on_fetch",
    ],
    "DASHBOARD_SUMMARY": [
        "requirement_truth",
        "unified_tasks_service",
        "dashboard_summary_projection",
    ],
    "REQUIREMENT_LIST": [
        "requirement_evidence_authority",
        "requirement_truth",
        "enrich_requirement_dict",
    ],
    "PRIORITY_ACTIONS": [
        "requirement_truth",
        "priority_stream",
        "unified_tasks_service",
        "priority_actions_surface",
    ],
    "SCORE_DRIVERS": [
        "requirement_truth",
        "compliance_score_calculator",
        "score_driver_shaping",
    ],
    "NOTIFICATION_EMAIL_PATHS": [
        "template_runtime",
        "periodic_email_jobs",
        "notification_dispatch",
    ],
    "SLA_ESCALATION_PATHS": [
        "compliance_sla_monitor",
        "sla_watchdog",
        "periodic_operational_monitoring",
    ],
    "CACHE_INVALIDATION_REFRESH": [
        "read_time_recomposition",
        "unknown_cache_invalidation_boundary",
    ],
    "REGENERATION_RECALC_PATHS": [
        "compliance_recalc_queue",
        "scheduled_workers",
        "lazy_backfill",
    ],
}

_READ_COHESIVE_PIPELINE = frozenset({SEMANTIC_AUTHORITY, READ_PROJECTION, REPORT_PROJECTION, USER_VISIBILITY})

_UI_CONSUMERS = frozenset(
    {
        "COMMAND_CENTER",
        "TODAY_VIEW",
        "UNIFIED_TASKS",
        "DASHBOARD_SUMMARY",
        "PROPERTY_SUMMARY",
        "PRIORITY_ACTIONS",
        "REQUIREMENT_LIST",
    }
)


def _handoff_chain(consumer: str, semantic_transition: str) -> Tuple[List[str], bool, bool, bool]:
    c = str(consumer or "").upper()
    base = list(_HANDOFF_BASE.get(c, ["unknown_subsystem_boundary"]))
    t = str(semantic_transition or "").upper()
    periodic_only = "periodic" in " ".join(base).lower() or c in (
        "NOTIFICATION_EMAIL_PATHS",
        "SLA_ESCALATION_PATHS",
        "REMINDER_ENGINE",
    )
    fragmented = len(set(base)) >= 4 or c in ("NOTIFICATION_EMAIL_PATHS", "SLA_ESCALATION_PATHS", "CACHE_INVALIDATION_REFRESH")
    undefined_boundary = c == "CACHE_INVALIDATION_REFRESH" or "unknown" in base[-1].lower()
    if t in ("EXPIRY_REVIEW_REQUIRED", "OPERATIONALLY_OPEN") and c == "SLA_ESCALATION_PATHS":
        base = base + ["sla_escalation_escalation_owner"]
    return base, fragmented, undefined_boundary, periodic_only


def _propagation_owner(reaction: str, consumer: str) -> str:
    c = str(consumer or "").upper()
    r = str(reaction or "")
    if r == LIVE_READ_PROJECTION:
        if c == "REPORT_EXPORT":
            return REPORT_PROJECTION
        return READ_PROJECTION
    if r == REACTION_TASK_REBUILD:
        return TASK_REBUILD
    if r == SCORE_REGENERATION:
        return SCORING_REGENERATION
    if r == SCHEDULED_RECALC:
        return SCORING_REGENERATION
    if r == PERIODIC_JOB:
        if c == "NOTIFICATION_EMAIL_PATHS":
            return NOTIFICATION_DISPATCH
        if c == "SLA_ESCALATION_PATHS":
            return SLA_ORCHESTRATION
        if c == "REMINDER_ENGINE":
            return REMINDER_ORCHESTRATION
        return OPERATIONAL_ORCHESTRATION
    if r == UNKNOWN:
        return UNKNOWN_OWNERSHIP
    return READ_PROJECTION


def _refresh_owner(consumer: str, dep: str, reaction: str) -> str:
    c = str(consumer or "").upper()
    d = str(dep or "").lower()
    r = str(reaction or "")
    if c == "CACHE_INVALIDATION_REFRESH":
        return CACHE_REFRESH
    if "task_rebuild" in d or r == REACTION_TASK_REBUILD:
        return TASK_REBUILD
    if "reminder" in d:
        return REMINDER_ORCHESTRATION
    if "periodic" in d and c == "SLA_ESCALATION_PATHS":
        return SLA_ORCHESTRATION
    if "periodic" in d and c == "NOTIFICATION_EMAIL_PATHS":
        return NOTIFICATION_DISPATCH
    if "score" in d or "recalc" in d or "queued" in d:
        return SCORING_REGENERATION
    if "report" in d:
        return REPORT_PROJECTION
    if "live_read" in d:
        return READ_PROJECTION
    if r == LIVE_READ_PROJECTION:
        return READ_PROJECTION
    return UNKNOWN_OWNERSHIP


def _visibility_owner(consumer: str) -> str:
    c = str(consumer or "").upper()
    if c == "REPORT_EXPORT":
        return REPORT_PROJECTION
    if c in _UI_CONSUMERS:
        return USER_VISIBILITY
    if c in ("PORTFOLIO_SCORE", "SCORE_DRIVERS"):
        return USER_VISIBILITY
    if c == "NOTIFICATION_EMAIL_PATHS":
        return NOTIFICATION_DISPATCH
    if c == "REMINDER_ENGINE":
        return REMINDER_ORCHESTRATION
    if c == "SLA_ESCALATION_PATHS":
        return SLA_ORCHESTRATION
    if c == "REGENERATION_RECALC_PATHS":
        return SCORING_REGENERATION
    if c == "CACHE_INVALIDATION_REFRESH":
        return UNKNOWN_OWNERSHIP
    return READ_PROJECTION


def _operational_followthrough_owner(consumer: str, transition: str, follow: bool, expected: bool) -> str:
    c = str(consumer or "").upper()
    t = str(transition or "").upper()
    if follow:
        if c == "REMINDER_ENGINE":
            return REMINDER_ORCHESTRATION
        if c == "SLA_ESCALATION_PATHS":
            return SLA_ORCHESTRATION
        if c in ("PRIORITY_ACTIONS", "NOTIFICATION_EMAIL_PATHS"):
            return OPERATIONAL_ORCHESTRATION
    if expected and not follow:
        if c == "REMINDER_ENGINE":
            return REMINDER_ORCHESTRATION
        if c == "SLA_ESCALATION_PATHS":
            return SLA_ORCHESTRATION
        if c in ("PRIORITY_ACTIONS",):
            return OPERATIONAL_ORCHESTRATION
    if t in ("EXPIRY_REVIEW_REQUIRED", "OPERATIONALLY_OPEN", "ASSESSMENT_FOLLOWUP_REQUIRED") and c in (
        "REMINDER_ENGINE",
        "SLA_ESCALATION_PATHS",
        "PRIORITY_ACTIONS",
    ):
        return REMINDER_ORCHESTRATION if c == "REMINDER_ENGINE" else SLA_ORCHESTRATION if c == "SLA_ESCALATION_PATHS" else OPERATIONAL_ORCHESTRATION
    return UNKNOWN_OWNERSHIP


def _escalation_owner(consumer: str, transition: str, crit: str) -> str:
    c = str(consumer or "").upper()
    t = str(transition or "").upper()
    if c == "SLA_ESCALATION_PATHS":
        return SLA_ORCHESTRATION
    if c == "NOTIFICATION_EMAIL_PATHS" and t in ("EXPIRY_REVIEW_REQUIRED", "VERIFIED_EXPIRED", "MISSING"):
        return NOTIFICATION_DISPATCH
    if c == "REMINDER_ENGINE" and t in ("EXPIRY_REVIEW_REQUIRED", "VERIFIED_EXPIRED", "MISSING"):
        return REMINDER_ORCHESTRATION
    if crit in (OPERATIONAL_CRITICAL, SAFETY_CRITICAL) and t == "OPERATIONALLY_OPEN":
        if c == "SLA_ESCALATION_PATHS":
            return SLA_ORCHESTRATION
        return UNKNOWN_OWNERSHIP
    if crit == COMPLIANCE_CRITICAL and t in ("EXPIRY_REVIEW_REQUIRED", "VERIFIED_EXPIRED"):
        if c in ("REMINDER_ENGINE", "NOTIFICATION_EMAIL_PATHS"):
            return REMINDER_ORCHESTRATION if c == "REMINDER_ENGINE" else NOTIFICATION_DISPATCH
    return UNKNOWN_OWNERSHIP


def _fallback_owner(consumer: str, dep: str) -> str:
    d = str(dep or "").lower()
    c = str(consumer or "").upper()
    if "user_refresh" in d or "user" in d:
        return USER_VISIBILITY
    if "periodic" in d:
        if c == "SLA_ESCALATION_PATHS":
            return SLA_ORCHESTRATION
        if c == "NOTIFICATION_EMAIL_PATHS":
            return NOTIFICATION_DISPATCH
        if c == "REMINDER_ENGINE":
            return REMINDER_ORCHESTRATION
    if "unknown" in d:
        return UNKNOWN_OWNERSHIP
    if "read" in d:
        return USER_VISIBILITY
    return READ_PROJECTION


def _ownership_dimensions(row: Dict[str, Any]) -> Dict[str, str]:
    c = str(row.get("consumer") or "")
    t = str(row.get("semantic_transition") or "")
    reaction = str(row.get("reaction_source_of_truth") or "")
    dep = str(row.get("refresh_recalc_dependency") or "")
    crit = str(row.get("propagation_criticality") or "")
    follow = bool(row.get("operational_followthrough"))
    expected = bool(row.get("expected_operational_followthrough"))
    det = SEMANTIC_AUTHORITY
    if c == "CACHE_INVALIDATION_REFRESH":
        det = UNKNOWN_OWNERSHIP
    return {
        "detection_owner": det,
        "propagation_owner": _propagation_owner(reaction, c),
        "refresh_owner": _refresh_owner(c, dep, reaction),
        "operational_followthrough_owner": _operational_followthrough_owner(c, t, follow, expected),
        "visibility_owner": _visibility_owner(c),
        "escalation_owner": _escalation_owner(c, t, crit),
        "fallback_owner": _fallback_owner(c, dep),
    }


def _ownership_quality(owners: Dict[str, str], propagation_type: str, consumer: str) -> str:
    vals = [owners[k] for k in sorted(owners.keys())]
    non_u = [v for v in vals if v != UNKNOWN_OWNERSHIP]
    uniq: Set[str] = set(non_u)
    n = len(uniq)
    c = str(consumer or "").upper()
    if propagation_type in (NO_KNOWN_PROPAGATION,) or owners["propagation_owner"] == UNKNOWN_OWNERSHIP:
        return AMBIGUOUS
    if n == 0:
        return NO_CLEAR_OWNER
    if propagation_type == DERIVED_ON_READ and uniq.issubset(_READ_COHESIVE_PIPELINE) and n <= 3:
        return CLEAR_SINGLE_OWNER
    canonical_read = {SEMANTIC_AUTHORITY, READ_PROJECTION}
    if uniq.issubset(canonical_read) and n <= 2:
        return CLEAR_SINGLE_OWNER
    if n == 2:
        return CLEAR_MULTI_STAGE_CHAIN
    if n == 3:
        if c in ("NOTIFICATION_EMAIL_PATHS", "SLA_ESCALATION_PATHS"):
            return FRAGMENTED
        return SHARED_BUT_DEFINED
    if n >= 4:
        return FRAGMENTED
    return AMBIGUOUS


def _failure_modes(row: Dict[str, Any], owners: Dict[str, str]) -> List[str]:
    modes: List[str] = []
    c = str(row.get("consumer") or "").upper()
    ptype = str(row.get("propagation_type") or "")
    gap = str(row.get("gap_classification") or "")
    refresh_g = str(row.get("refresh_guarantee") or "")
    br = list(row.get("runtime_enforcement_blocker_reasons") or [])
    follow = bool(row.get("operational_followthrough"))
    expected = bool(row.get("expected_operational_followthrough"))

    if expected and not follow:
        modes.append(DERIVED_WITHOUT_ACTION_PATH)
        modes.append(ORCHESTRATION_WITHOUT_CONFIRMATION)
    if ptype == NO_KNOWN_PROPAGATION:
        if NO_OPERATIONAL_CONSUMER not in modes and not follow:
            modes.append(NO_OPERATIONAL_CONSUMER)
    if ptype in (FRAGMENTED_PROPAGATION, PARTIAL_PROPAGATION) and gap in (
        FRAGMENTED_BEHAVIOR,
        OPERATIONAL_GAP,
        BLOCKED_FOR_RUNTIME_ENFORCEMENT,
    ):
        modes.append(MULTIPLE_REFRESH_AUTHORITIES)
    if gap == ROLLUP_STALE_RISK:
        modes.append(STALE_READ_DEPENDENCY)
    if PERIODIC_ONLY_REFRESH in br or "periodic" in str(row.get("refresh_recalc_dependency") or "").lower():
        if c in ("REMINDER_ENGINE", "SLA_ESCALATION_PATHS", "NOTIFICATION_EMAIL_PATHS"):
            modes.append(PERIODIC_SWEEP_ONLY)
    if UNKNOWN_REFRESH_GUARANTEE in br or CACHE_INVALIDATION_UNKNOWN in br or refresh_g == UNKNOWN_GUARANTEE:
        modes.append(UNKNOWN_REFRESH_BOUNDARY)
    if FRAGMENTED_MULTI_SOURCE_REFRESH in br:
        modes.append(MULTIPLE_REFRESH_AUTHORITIES)
    if owners["escalation_owner"] == UNKNOWN_OWNERSHIP and str(row.get("propagation_criticality") or "") in (
        OPERATIONAL_CRITICAL,
        SAFETY_CRITICAL,
        COMPLIANCE_CRITICAL,
    ):
        modes.append(NO_ESCALATION_OWNER)
    if owners["fallback_owner"] == UNKNOWN_OWNERSHIP:
        modes.append(NO_FALLBACK_OWNER)
    if owners["visibility_owner"] != UNKNOWN_OWNERSHIP and owners["operational_followthrough_owner"] == UNKNOWN_OWNERSHIP:
        if _visibility_owner(c) == USER_VISIBILITY and not follow:
            modes.append(VISIBILITY_WITHOUT_ORCHESTRATION)
    if NO_OPERATIONAL_FOLLOWTHROUGH in br:
        modes.append(ORCHESTRATION_WITHOUT_CONFIRMATION)

    out: List[str] = []
    for m in modes:
        if m not in out:
            out.append(m)
    return sorted(out)


def _operational_followthrough_analysis(row: Dict[str, Any], owners: Dict[str, str]) -> Dict[str, Any]:
    follow = bool(row.get("operational_followthrough"))
    expected = bool(row.get("expected_operational_followthrough"))
    dep = str(row.get("refresh_recalc_dependency") or "").lower()
    gaps = " ".join(row.get("known_gaps") or []).lower()
    quality = str(row.get("ownership_quality") or "")
    periodic = "periodic" in dep or "periodic" in gaps
    user_revisit = "user_refresh" in dep or "user refresh" in gaps or "fetch" in dep
    regeneration = "recalc" in dep or "score" in dep or "regeneration" in dep
    return {
        "operational_followthrough_exists": follow,
        "operational_followthrough_guaranteed": follow and expected,
        "operational_followthrough_inferred_only": not follow and not periodic and "read" in dep,
        "operational_followthrough_periodic": periodic,
        "depends_on_user_revisit_or_read_refresh": user_revisit,
        "depends_on_regeneration_or_recalc": regeneration,
        "operational_followthrough_ownership_ambiguous": quality in (FRAGMENTED, AMBIGUOUS, NO_CLEAR_OWNER),
    }


def _bump_risk(current: str, levels: int) -> str:
    idx = _RISK_ORDER.index(current)
    idx = min(len(_RISK_ORDER) - 1, idx + levels)
    return _RISK_ORDER[idx]


def _topology_risk(
    quality: str,
    failure_modes: List[str],
    handoff_count: int,
    periodic_only_bridge: bool,
    blockers: List[str],
) -> str:
    if quality == CLEAR_SINGLE_OWNER:
        risk = LOW_TOPOLOGY_RISK
    elif quality == CLEAR_MULTI_STAGE_CHAIN:
        risk = LOW_TOPOLOGY_RISK
    elif quality == SHARED_BUT_DEFINED:
        risk = MODERATE_TOPOLOGY_RISK
    elif quality == FRAGMENTED:
        risk = HIGH_TOPOLOGY_RISK
    elif quality == AMBIGUOUS:
        risk = HIGH_TOPOLOGY_RISK
    else:
        risk = CRITICAL_TOPOLOGY_RISK

    if len(failure_modes) >= 4:
        risk = _bump_risk(risk, 2)
    elif len(failure_modes) >= 2:
        risk = _bump_risk(risk, 1)
    if handoff_count >= 5:
        risk = _bump_risk(risk, 1)
    if periodic_only_bridge:
        risk = _bump_risk(risk, 1)
    if SEMANTIC_COLLAPSE_RISK in blockers:
        risk = CRITICAL_TOPOLOGY_RISK
    if UNKNOWN_REFRESH_BOUNDARY in failure_modes and len(failure_modes) >= 3:
        risk = _bump_risk(risk, 1)
    return risk


def build_operational_responsibility_topology_matrix(
    matrix: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    base = matrix if matrix is not None else build_expected_vs_current_matrix()
    out: List[Dict[str, Any]] = []
    for row in sorted(
        base,
        key=lambda r: (str(r.get("semantic_transition") or ""), str(r.get("consumer") or "")),
    ):
        owners = _ownership_dimensions(row)
        ptype = str(row.get("propagation_type") or "")
        c = str(row.get("consumer") or "")
        t = str(row.get("semantic_transition") or "")
        chain, frag_handoff, undefined_boundary, periodic_only_bridge = _handoff_chain(c, t)
        quality = _ownership_quality(owners, ptype, c)
        enriched = {**row, **owners, "ownership_quality": quality}
        failures = _failure_modes(enriched, owners)
        handoff_count = max(0, len(chain) - 1)
        risk = _topology_risk(
            quality,
            failures,
            handoff_count,
            periodic_only_bridge,
            list(row.get("runtime_enforcement_blocker_reasons") or []),
        )
        follow_analysis = _operational_followthrough_analysis(enriched, owners)
        out.append(
            {
                **enriched,
                "topology_failure_modes": failures,
                "handoff_chain": chain,
                "handoff_count": handoff_count,
                "fragmented_handoff_chain": frag_handoff,
                "undefined_handoff_boundary": undefined_boundary,
                "periodic_only_bridge": periodic_only_bridge,
                "topology_risk": risk,
                "operational_followthrough_analysis": follow_analysis,
            }
        )
    return out


def _count_by(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        k = str(r.get(key) or "")
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


def _risk_rank(risk: str) -> int:
    return _RISK_ORDER.index(risk) if risk in _RISK_ORDER else len(_RISK_ORDER)


def _aggregate_transition_risk(matrix: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_t: Dict[str, List[Dict[str, Any]]] = {}
    for r in matrix:
        t = str(r.get("semantic_transition") or "")
        by_t.setdefault(t, []).append(r)
    worst: List[Tuple[str, str, int]] = []
    best: List[Tuple[str, str, int]] = []
    for t, rows in sorted(by_t.items()):
        risks = [_risk_rank(str(x.get("topology_risk") or "")) for x in rows]
        w = max(risks)
        b = min(risks)
        worst.append((t, _RISK_ORDER[w], w))
        best.append((t, _RISK_ORDER[b], b))
    worst.sort(key=lambda x: (-x[2], x[0]))
    best.sort(key=lambda x: (x[2], x[0]))
    return {
        "most_dangerous_semantic_transitions": [{"semantic_transition": a[0], "worst_case_risk": a[1]} for a in worst[:8]],
        "safest_semantic_transitions": [{"semantic_transition": a[0], "best_case_risk": a[1]} for a in best[:8]],
    }


def build_operational_responsibility_topology_phase1_snapshot() -> Dict[str, Any]:
    matrix = build_operational_responsibility_topology_matrix()
    agg = _aggregate_transition_risk(matrix)
    failure_flat: List[str] = []
    for r in matrix:
        failure_flat.extend(r.get("topology_failure_modes") or [])
    failure_summary = _count_by([{"f": x} for x in failure_flat], "f")
    quality_summary = _count_by(matrix, "ownership_quality")
    risk_summary = _count_by(matrix, "topology_risk")
    handoff_summary = {
        "mean_handoff_count": round(sum(r.get("handoff_count", 0) for r in matrix) / max(len(matrix), 1), 4),
        "rows_fragmented_handoff": sum(1 for r in matrix if r.get("fragmented_handoff_chain")),
        "rows_undefined_boundary": sum(1 for r in matrix if r.get("undefined_handoff_boundary")),
        "rows_periodic_only_bridge": sum(1 for r in matrix if r.get("periodic_only_bridge")),
    }
    highest_risk_paths = sorted(
        [r for r in matrix if r.get("topology_risk") in (HIGH_TOPOLOGY_RISK, CRITICAL_TOPOLOGY_RISK)],
        key=lambda x: (
            -_risk_rank(str(x.get("topology_risk") or "")),
            str(x.get("semantic_transition") or ""),
            str(x.get("consumer") or ""),
        ),
    )[:40]
    safest_paths = sorted(
        matrix,
        key=lambda x: (
            _risk_rank(str(x.get("topology_risk") or "")),
            str(x.get("semantic_transition") or ""),
            str(x.get("consumer") or ""),
        ),
    )[:40]
    return {
        "phase": "Operational Responsibility Topology Audit Phase 1",
        "scope": "semantic transition ownership and follow-through mapping",
        "runtime_behavior_changed": False,
        "audit_only": True,
        "ownership_domains": sorted(
            {
                SEMANTIC_AUTHORITY,
                READ_PROJECTION,
                TASK_REBUILD,
                OPERATIONAL_ORCHESTRATION,
                REMINDER_ORCHESTRATION,
                SLA_ORCHESTRATION,
                REPORT_PROJECTION,
                SCORING_REGENERATION,
                CACHE_REFRESH,
                USER_VISIBILITY,
                NOTIFICATION_DISPATCH,
                UNKNOWN_OWNERSHIP,
            }
        ),
        "ownership_quality_classifications": [
            CLEAR_SINGLE_OWNER,
            CLEAR_MULTI_STAGE_CHAIN,
            SHARED_BUT_DEFINED,
            FRAGMENTED,
            AMBIGUOUS,
            NO_CLEAR_OWNER,
        ],
        "topology_failure_mode_classifications": [
            NO_OPERATIONAL_CONSUMER,
            DERIVED_WITHOUT_ACTION_PATH,
            MULTIPLE_REFRESH_AUTHORITIES,
            STALE_READ_DEPENDENCY,
            PERIODIC_SWEEP_ONLY,
            NO_ESCALATION_OWNER,
            NO_FALLBACK_OWNER,
            VISIBILITY_WITHOUT_ORCHESTRATION,
            ORCHESTRATION_WITHOUT_CONFIRMATION,
            UNKNOWN_REFRESH_BOUNDARY,
        ],
        "topology_risk_classifications": list(_RISK_ORDER),
        "semantic_transitions": list(SEMANTIC_TRANSITIONS),
        "consumers": list(CONSUMERS),
        "ownership_topology_matrix": matrix,
        "ownership_quality_summary": quality_summary,
        "topology_failure_summary": failure_summary,
        "topology_risk_summary": risk_summary,
        "handoff_chain_summary": handoff_summary,
        "highest_risk_topology_paths": highest_risk_paths,
        "safest_topology_paths": safest_paths,
        "semantic_transition_risk_ranking": agg,
        "remaining_state_model_limitation": _STATE_MODEL_LIMITATION,
        "remaining_runtime_convergence_limitation": _RUNTIME_CONVERGENCE_LIMITATION,
        "non_blocking": True,
    }


def write_operational_responsibility_topology_phase1_json(target_path: Optional[Path] = None) -> Path:
    snap = build_operational_responsibility_topology_phase1_snapshot()
    base = Path(__file__).resolve().parents[1]
    path = target_path or (base / "docs" / "audit" / "OPERATIONAL_RESPONSIBILITY_TOPOLOGY_PHASE1.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
