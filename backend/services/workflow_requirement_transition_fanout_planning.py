"""
Planning-only: Requirement-State Transition fanout boundaries (Phase 2 planning).

Advisory metadata and deterministic snapshots. No activation, no registry changes,
no orchestration/queue/worker mutations. Do not consume planning outputs for enforcement.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple

PLANNING_SCHEMA_VERSION = "requirement_transition_fanout_planning_v1"

# --- Propagation boundary categories (what kind of propagation applies conceptually) ---
PROP_SYNC = "synchronous_propagation"
PROP_ASYNC = "async_propagation"
PROP_DEFERRED = "deferred_propagation"
PROP_OBSERVE_ONLY = "observe_only_propagation"
PROP_BLOCKED = "blocked_propagation"

# --- Fanout participation posture (per surface; planning only) ---
FANOUT_PARTICIPANT_ALLOWED = "FANOUT_PARTICIPANT_ALLOWED"
FANOUT_PARTICIPANT_OBSERVE_ONLY = "FANOUT_PARTICIPANT_OBSERVE_ONLY"
FANOUT_PARTICIPANT_BLOCKED = "FANOUT_PARTICIPANT_BLOCKED"
FANOUT_PARTICIPANT_DEFERRED = "FANOUT_PARTICIPANT_DEFERRED"
FANOUT_PARTICIPANT_PASSIVE = "FANOUT_PARTICIPANT_PASSIVE"

# --- Convergence expectation labels ---
CONVERGENCE_REQUIRED = "CONVERGENCE_REQUIRED"
CONVERGENCE_PARTIAL_ALLOWED = "CONVERGENCE_PARTIAL_ALLOWED"
CONVERGENCE_OBSERVE_ONLY = "CONVERGENCE_OBSERVE_ONLY"
CONVERGENCE_BLOCKED = "CONVERGENCE_BLOCKED"

# --- Advisory risk bands (must not drive runtime behavior) ---
FANOUT_RISK_LOW = "FANOUT_RISK_LOW"
FANOUT_RISK_MODERATE = "FANOUT_RISK_MODERATE"
FANOUT_RISK_HIGH = "FANOUT_RISK_HIGH"
FANOUT_RISK_CRITICAL = "FANOUT_RISK_CRITICAL"

# --- Rollback posture (advisory) ---
ROLLBACK_SIMPLE = "ROLLBACK_SIMPLE"
ROLLBACK_CONTROLLED = "ROLLBACK_CONTROLLED"
ROLLBACK_COMPLEX = "ROLLBACK_COMPLEX"
ROLLBACK_UNSAFE_FOR_PHASE2 = "ROLLBACK_UNSAFE_FOR_PHASE2"

# --- Observability readiness for future activation (planning only) ---
OBSERVABILITY_READY = "OBSERVABILITY_READY"
OBSERVABILITY_PARTIAL = "OBSERVABILITY_PARTIAL"
OBSERVABILITY_INSUFFICIENT = "OBSERVABILITY_INSUFFICIENT"

_RISK_ORDER = {
    FANOUT_RISK_LOW: 0,
    FANOUT_RISK_MODERATE: 1,
    FANOUT_RISK_HIGH: 2,
    FANOUT_RISK_CRITICAL: 3,
}

# Canonical surfaces (deterministic ordering)
SURFACE_AUTHORITY_SYNC = "authority_sync"
SURFACE_COMPLIANCE_GAP_SYNC = "compliance_gap_sync"
SURFACE_COMPLIANCE_RECALC = "compliance_recalc"
SURFACE_REGENERATION_RECALC = "regeneration_recalc"
SURFACE_REMINDERS = "reminders"
SURFACE_UNIFIED_TASKS = "unified_tasks"
SURFACE_REPORTING = "reporting"
SURFACE_EXPORTS = "exports"
SURFACE_COMMAND_CENTER = "command_center"
SURFACE_PORTFOLIO_SUMMARY = "portfolio_summary"
SURFACE_NOTIFICATIONS = "notifications"
SURFACE_CACHE_INVALIDATION = "cache_invalidation"

FANOUT_PLANNING_SURFACE_KEYS: Tuple[str, ...] = (
    SURFACE_AUTHORITY_SYNC,
    SURFACE_CACHE_INVALIDATION,
    SURFACE_COMMAND_CENTER,
    SURFACE_COMPLIANCE_GAP_SYNC,
    SURFACE_COMPLIANCE_RECALC,
    SURFACE_EXPORTS,
    SURFACE_NOTIFICATIONS,
    SURFACE_PORTFOLIO_SUMMARY,
    SURFACE_REGENERATION_RECALC,
    SURFACE_REMINDERS,
    SURFACE_REPORTING,
    SURFACE_UNIFIED_TASKS,
)

# Planning propagation-chain boundaries (conceptual; no runtime wiring)
PROPAGATION_BOUNDARY_CHAIN: Dict[str, Dict[str, Any]] = {
    "async_enqueue": {
        "boundary_category": PROP_ASYNC,
        "does_not_participate_in_planning_phase": (),
        "observability_posture": "observational_minimum_enqueue_trace_required_before_activation",
        "participates_in_chain": True,
        "planning_notes": "async_queue_surfaces_require_activation_metadata_and_downstream_rows",
    },
    "authority_sync": {
        "boundary_category": PROP_SYNC,
        "does_not_participate_in_planning_phase": ("trust_surface_materialization",),
        "observability_posture": "trace_correlation_required",
        "participates_in_chain": True,
        "planning_notes": "requirement_transition_authority_sync_core_path",
    },
    "degraded_propagation_visibility": {
        "boundary_category": PROP_OBSERVE_ONLY,
        "does_not_participate_in_planning_phase": ("silent_failure_paths",),
        "observability_posture": "degraded_possible_on_downstream_rows",
        "participates_in_chain": True,
        "planning_notes": "must_remain_visible_before_fanout_expansion",
    },
    "downstream_propagation": {
        "boundary_category": PROP_ASYNC,
        "does_not_participate_in_planning_phase": ("broad_multi_family_fanout_without_governance",),
        "observability_posture": "downstream_trigger_targets_required",
        "participates_in_chain": True,
        "planning_notes": "bounded_targets_only_per_phase_planning",
    },
    "mutation_source": {
        "boundary_category": PROP_SYNC,
        "does_not_participate_in_planning_phase": ("cross_tenant_side_effects",),
        "observability_posture": "transition_origin_and_correlation_required",
        "participates_in_chain": True,
        "planning_notes": "document_touch_outcome_engine_admin_paths_only_scoped",
    },
    "reconciliation": {
        "boundary_category": PROP_ASYNC,
        "does_not_participate_in_planning_phase": ("unbounded_replay_without_filters",),
        "observability_posture": "reconciliation_visibility_fields_on_matrix",
        "participates_in_chain": True,
        "planning_notes": "bounded_reconciliation_signals_only",
    },
    "rollback_visibility": {
        "boundary_category": PROP_OBSERVE_ONLY,
        "does_not_participate_in_planning_phase": ("automatic_rollback_execution",),
        "observability_posture": "registry_and_governance_reports_only",
        "participates_in_chain": True,
        "planning_notes": "code_ceiling_rollback_no_queue_replay_engine",
    },
    "stale_state_visibility": {
        "boundary_category": PROP_OBSERVE_ONLY,
        "does_not_participate_in_planning_phase": ("hiding_stale_reads",),
        "observability_posture": "stale_read_dependency_hint_on_convergence",
        "participates_in_chain": True,
        "planning_notes": "convergence_matrix_and_trace_hints",
    },
    "trust_surfaces_passive": {
        "boundary_category": PROP_BLOCKED,
        "does_not_participate_in_planning_phase": ("notification_dispatch", "portfolio_refresh_orchestration", "command_center_orchestration"),
        "observability_posture": "passive_operational_snapshot_only",
        "participates_in_chain": False,
        "planning_notes": "phase2_planning_excludes_trust_surface_activation",
    },
}


def _participation_row(surface: str) -> Dict[str, Any]:
    """Single surface planning row (deterministic fields)."""
    participation = _PARTICIPATION_BY_SURFACE[surface]
    conv = _CONVERGENCE_EXPECTATION_BY_SURFACE[surface]
    rollback = _ROLLBACK_POSTURE_BY_SURFACE[surface]
    risk = _derive_risk_band(surface, participation)
    obs = _derive_observability_readiness(surface, participation, risk)
    return {
        "convergence_expectation": conv,
        "fanout_risk_band": risk,
        "observability_readiness_for_future_activation": obs,
        "participation_posture": participation,
        "rollback_posture_expectation": rollback,
        "surface": surface,
    }


_PARTICIPATION_BY_SURFACE: Dict[str, str] = {
    SURFACE_AUTHORITY_SYNC: FANOUT_PARTICIPANT_ALLOWED,
    SURFACE_COMPLIANCE_GAP_SYNC: FANOUT_PARTICIPANT_ALLOWED,
    SURFACE_COMPLIANCE_RECALC: FANOUT_PARTICIPANT_ALLOWED,
    SURFACE_REGENERATION_RECALC: FANOUT_PARTICIPANT_ALLOWED,
    SURFACE_REMINDERS: FANOUT_PARTICIPANT_OBSERVE_ONLY,
    SURFACE_UNIFIED_TASKS: FANOUT_PARTICIPANT_OBSERVE_ONLY,
    SURFACE_REPORTING: FANOUT_PARTICIPANT_OBSERVE_ONLY,
    SURFACE_EXPORTS: FANOUT_PARTICIPANT_OBSERVE_ONLY,
    SURFACE_COMMAND_CENTER: FANOUT_PARTICIPANT_DEFERRED,
    SURFACE_PORTFOLIO_SUMMARY: FANOUT_PARTICIPANT_DEFERRED,
    SURFACE_NOTIFICATIONS: FANOUT_PARTICIPANT_BLOCKED,
    SURFACE_CACHE_INVALIDATION: FANOUT_PARTICIPANT_BLOCKED,
}

_CONVERGENCE_EXPECTATION_BY_SURFACE: Dict[str, str] = {
    SURFACE_AUTHORITY_SYNC: CONVERGENCE_REQUIRED,
    SURFACE_COMPLIANCE_GAP_SYNC: CONVERGENCE_REQUIRED,
    SURFACE_COMPLIANCE_RECALC: CONVERGENCE_REQUIRED,
    SURFACE_REGENERATION_RECALC: CONVERGENCE_PARTIAL_ALLOWED,
    SURFACE_REMINDERS: CONVERGENCE_PARTIAL_ALLOWED,
    SURFACE_UNIFIED_TASKS: CONVERGENCE_PARTIAL_ALLOWED,
    SURFACE_REPORTING: CONVERGENCE_OBSERVE_ONLY,
    SURFACE_EXPORTS: CONVERGENCE_OBSERVE_ONLY,
    SURFACE_COMMAND_CENTER: CONVERGENCE_OBSERVE_ONLY,
    SURFACE_PORTFOLIO_SUMMARY: CONVERGENCE_OBSERVE_ONLY,
    SURFACE_NOTIFICATIONS: CONVERGENCE_BLOCKED,
    SURFACE_CACHE_INVALIDATION: CONVERGENCE_BLOCKED,
}

_ROLLBACK_POSTURE_BY_SURFACE: Dict[str, str] = {
    SURFACE_AUTHORITY_SYNC: ROLLBACK_CONTROLLED,
    SURFACE_COMPLIANCE_GAP_SYNC: ROLLBACK_CONTROLLED,
    SURFACE_COMPLIANCE_RECALC: ROLLBACK_CONTROLLED,
    SURFACE_REGENERATION_RECALC: ROLLBACK_CONTROLLED,
    SURFACE_REMINDERS: ROLLBACK_COMPLEX,
    SURFACE_UNIFIED_TASKS: ROLLBACK_COMPLEX,
    SURFACE_REPORTING: ROLLBACK_COMPLEX,
    SURFACE_EXPORTS: ROLLBACK_COMPLEX,
    SURFACE_COMMAND_CENTER: ROLLBACK_UNSAFE_FOR_PHASE2,
    SURFACE_PORTFOLIO_SUMMARY: ROLLBACK_UNSAFE_FOR_PHASE2,
    SURFACE_NOTIFICATIONS: ROLLBACK_UNSAFE_FOR_PHASE2,
    SURFACE_CACHE_INVALIDATION: ROLLBACK_UNSAFE_FOR_PHASE2,
}


def _derive_risk_band(surface: str, participation: str) -> str:
    """Deterministic advisory risk from planning attributes (not runtime telemetry)."""
    if participation == FANOUT_PARTICIPANT_BLOCKED:
        return FANOUT_RISK_CRITICAL
    if surface == SURFACE_NOTIFICATIONS:
        return FANOUT_RISK_CRITICAL
    if surface in (SURFACE_CACHE_INVALIDATION, SURFACE_COMMAND_CENTER, SURFACE_PORTFOLIO_SUMMARY):
        return FANOUT_RISK_HIGH
    if participation == FANOUT_PARTICIPANT_DEFERRED:
        return FANOUT_RISK_HIGH
    if surface in (SURFACE_REMINDERS, SURFACE_UNIFIED_TASKS, SURFACE_REPORTING, SURFACE_EXPORTS):
        return FANOUT_RISK_MODERATE
    if participation == FANOUT_PARTICIPANT_OBSERVE_ONLY:
        return FANOUT_RISK_MODERATE
    return FANOUT_RISK_LOW


def _derive_observability_readiness(surface: str, participation: str, risk: str) -> str:
    if participation in (FANOUT_PARTICIPANT_BLOCKED, FANOUT_PARTICIPANT_PASSIVE):
        return OBSERVABILITY_INSUFFICIENT
    if risk == FANOUT_RISK_CRITICAL:
        return OBSERVABILITY_INSUFFICIENT
    if participation == FANOUT_PARTICIPANT_DEFERRED or risk == FANOUT_RISK_HIGH:
        return OBSERVABILITY_PARTIAL
    if participation in (FANOUT_PARTICIPANT_ALLOWED, FANOUT_PARTICIPANT_OBSERVE_ONLY):
        return OBSERVABILITY_READY if risk == FANOUT_RISK_LOW else OBSERVABILITY_PARTIAL
    return OBSERVABILITY_PARTIAL


PHASE_2A_SURFACES: Tuple[str, ...] = (
    SURFACE_AUTHORITY_SYNC,
    SURFACE_COMPLIANCE_GAP_SYNC,
    SURFACE_COMPLIANCE_RECALC,
    SURFACE_REGENERATION_RECALC,
)
PHASE_2B_SURFACES: Tuple[str, ...] = (SURFACE_REMINDERS, SURFACE_UNIFIED_TASKS)
PHASE_2C_SURFACES: Tuple[str, ...] = (SURFACE_REPORTING, SURFACE_EXPORTS)
DEFERRED_FANOUT_SURFACES: Tuple[str, ...] = (
    SURFACE_NOTIFICATIONS,
    SURFACE_COMMAND_CENTER,
    SURFACE_CACHE_INVALIDATION,
    SURFACE_PORTFOLIO_SUMMARY,
)

OBSERVABILITY_MINIMUM_REQUIREMENTS: Tuple[str, ...] = (
    "downstream_trace_visibility",
    "enqueue_visibility",
    "replay_visibility",
    "degraded_visibility",
    "stale_state_visibility",
    "reconciliation_visibility",
    "convergence_evidence_visibility",
)


def build_propagation_boundary_planning_snapshot(*, generated_at_iso: str) -> Dict[str, Any]:
    chains = [dict(sorted({"key": k, **dict(sorted(v.items(), key=lambda kv: str(kv[0])))}.items())) for k, v in sorted(PROPAGATION_BOUNDARY_CHAIN.items())]
    return {
        "boundary_chains": chains,
        "generated_at_iso": generated_at_iso,
        "schema_version": "fanout_propagation_boundary_planning_v1",
    }


def build_fanout_participation_planning_snapshot(*, generated_at_iso: str) -> Dict[str, Any]:
    rows = [_participation_row(s) for s in FANOUT_PLANNING_SURFACE_KEYS]
    rows = sorted(rows, key=lambda r: str(r.get("surface") or ""))
    return {
        "generated_at_iso": generated_at_iso,
        "surfaces": rows,
        "schema_version": "fanout_participation_planning_v1",
    }


def build_convergence_expectation_planning_snapshot(*, generated_at_iso: str) -> Dict[str, Any]:
    exp = {s: _CONVERGENCE_EXPECTATION_BY_SURFACE[s] for s in FANOUT_PLANNING_SURFACE_KEYS}
    return {
        "by_surface": dict(sorted(exp.items())),
        "generated_at_iso": generated_at_iso,
        "schema_version": "fanout_convergence_expectation_planning_v1",
    }


def build_rollback_posture_planning_snapshot(*, generated_at_iso: str) -> Dict[str, Any]:
    rb = {s: _ROLLBACK_POSTURE_BY_SURFACE[s] for s in FANOUT_PLANNING_SURFACE_KEYS}
    return {
        "by_surface": dict(sorted(rb.items())),
        "generated_at_iso": generated_at_iso,
        "schema_version": "fanout_rollback_posture_planning_v1",
    }


def build_fanout_risk_planning_snapshot(*, generated_at_iso: str) -> Dict[str, Any]:
    risks = {s: _derive_risk_band(s, _PARTICIPATION_BY_SURFACE[s]) for s in FANOUT_PLANNING_SURFACE_KEYS}
    return {
        "by_surface": dict(sorted(risks.items())),
        "generated_at_iso": generated_at_iso,
        "schema_version": "fanout_risk_planning_v1",
    }


def build_observability_readiness_planning_snapshot(*, generated_at_iso: str) -> Dict[str, Any]:
    obs = {}
    for s in FANOUT_PLANNING_SURFACE_KEYS:
        p = _PARTICIPATION_BY_SURFACE[s]
        r = _derive_risk_band(s, p)
        obs[s] = _derive_observability_readiness(s, p, r)
    return {
        "by_surface": dict(sorted(obs.items())),
        "minimum_visibility_axes": list(OBSERVABILITY_MINIMUM_REQUIREMENTS),
        "generated_at_iso": generated_at_iso,
        "schema_version": "fanout_observability_readiness_planning_v1",
    }


def build_activation_sequencing_planning_snapshot(*, generated_at_iso: str) -> Dict[str, Any]:
    return {
        "deferred_surfaces": list(DEFERRED_FANOUT_SURFACES),
        "generated_at_iso": generated_at_iso,
        "phase_2a_surfaces": list(PHASE_2A_SURFACES),
        "phase_2b_surfaces": list(PHASE_2B_SURFACES),
        "phase_2c_surfaces": list(PHASE_2C_SURFACES),
        "schema_version": "fanout_activation_sequencing_planning_v1",
        "sequencing_advisory_only": True,
    }


def highest_risk_propagation_surfaces(participation_snapshot: Mapping[str, Any], *, limit: Optional[int] = None) -> List[str]:
    rows = participation_snapshot.get("surfaces") or []
    if not isinstance(rows, list):
        return []
    scored: List[Tuple[int, str]] = []
    for r in rows:
        if not isinstance(r, Mapping):
            continue
        surf = str(r.get("surface") or "")
        band = str(r.get("fanout_risk_band") or "")
        scored.append((_RISK_ORDER.get(band, -1), surf))
    scored.sort(key=lambda x: (-x[0], x[1]))
    out = [s for _, s in scored]
    if limit is not None:
        return out[:limit]
    return out


def safest_future_activation_candidates(participation_snapshot: Mapping[str, Any], *, limit: Optional[int] = None) -> List[str]:
    rows = participation_snapshot.get("surfaces") or []
    if not isinstance(rows, list):
        return []
    scored: List[Tuple[int, str]] = []
    for r in rows:
        if not isinstance(r, Mapping):
            continue
        surf = str(r.get("surface") or "")
        band = str(r.get("fanout_risk_band") or "")
        part = str(r.get("participation_posture") or "")
        if part not in (FANOUT_PARTICIPANT_ALLOWED, FANOUT_PARTICIPANT_OBSERVE_ONLY):
            continue
        scored.append((_RISK_ORDER.get(band, 99), surf))
    scored.sort(key=lambda x: (x[0], x[1]))
    out = [s for _, s in scored]
    if limit is not None:
        return out[:limit]
    return out


def build_requirement_transition_fanout_planning_bundle(*, generated_at_iso: str) -> Dict[str, Any]:
    """Single deterministic planning bundle (read-only)."""
    part = build_fanout_participation_planning_snapshot(generated_at_iso=generated_at_iso)
    bundle: Dict[str, Any] = {
        "activation_sequencing": build_activation_sequencing_planning_snapshot(generated_at_iso=generated_at_iso),
        "convergence_expectations": build_convergence_expectation_planning_snapshot(generated_at_iso=generated_at_iso),
        "fanout_participation": part,
        "fanout_risk": build_fanout_risk_planning_snapshot(generated_at_iso=generated_at_iso),
        "generated_at_iso": generated_at_iso,
        "highest_risk_propagation_surfaces": highest_risk_propagation_surfaces(part),
        "observability_readiness": build_observability_readiness_planning_snapshot(generated_at_iso=generated_at_iso),
        "planning_schema_version": PLANNING_SCHEMA_VERSION,
        "propagation_boundaries": build_propagation_boundary_planning_snapshot(generated_at_iso=generated_at_iso),
        "rollback_posture": build_rollback_posture_planning_snapshot(generated_at_iso=generated_at_iso),
        "safest_future_activation_candidates": safest_future_activation_candidates(part),
        "schema_version": "requirement_transition_fanout_planning_bundle_v1",
    }
    return dict(sorted(bundle.items(), key=lambda kv: str(kv[0])))


def summarize_planning_bundle(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    """Compact operator-facing summary (read-only)."""
    seq = bundle.get("activation_sequencing") if isinstance(bundle.get("activation_sequencing"), Mapping) else {}
    return {
        "deferred_surface_count": len(seq.get("deferred_surfaces") or []),
        "highest_risk_top": (bundle.get("highest_risk_propagation_surfaces") or [])[:5],
        "phase_2a_surface_count": len(seq.get("phase_2a_surfaces") or []),
        "planning_schema_version": bundle.get("planning_schema_version"),
        "safest_candidates_top": (bundle.get("safest_future_activation_candidates") or [])[:5],
        "schema_version": "fanout_planning_summary_v1",
    }
