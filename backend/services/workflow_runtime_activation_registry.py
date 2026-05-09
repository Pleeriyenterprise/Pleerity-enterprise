"""
Deterministic runtime activation registry (controlled activation Phase 1 + Phase 2 + Phase 2A backbone).

Code-based only: no feature flags, no dynamic config. COMPLIANCE_SCORE_RECALC,
REGENERATION_RECALC, and REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE may be
ACTIVATION_LIMITED at the registry ceiling; other families remain disabled at
activation gates unless deferred (always disabled).
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from services.workflow_activation_readiness import (
    FAMILY_COMPLIANCE_SCORE_RECALC,
    FAMILY_REGENERATION_RECALC,
    FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE,
    GOVERNANCE_DEFERRED_FAMILIES,
)

ACTIVATION_GOVERNANCE_VERSION = "workflow_runtime_activation_registry_v3"

ACTIVATION_DISABLED = "ACTIVATION_DISABLED"
ACTIVATION_OBSERVE_ONLY = "ACTIVATION_OBSERVE_ONLY"
ACTIVATION_LIMITED = "ACTIVATION_LIMITED"
ACTIVATION_ENABLED = "ACTIVATION_ENABLED"

_ACTIVATION_ORDER = {
    ACTIVATION_DISABLED: 0,
    ACTIVATION_OBSERVE_ONLY: 1,
    ACTIVATION_LIMITED: 2,
    ACTIVATION_ENABLED: 3,
}

# Families with a dedicated limited-activation gate path in Phase 1/2 (enqueue surfaces only).
_PHASE2_LIMITED_ACTIVATION_FAMILIES = frozenset(
    {
        FAMILY_COMPLIANCE_SCORE_RECALC,
        FAMILY_REGENERATION_RECALC,
    }
)

_RST_CORE_BACKBONE_ACTIVATION_FAMILIES = frozenset({FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE})

# Registry ceiling per family (reversible by editing constants only).
_REGISTRY_CEILING: Dict[str, str] = {
    FAMILY_COMPLIANCE_SCORE_RECALC: ACTIVATION_LIMITED,
    FAMILY_REGENERATION_RECALC: ACTIVATION_LIMITED,
    FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE: ACTIVATION_LIMITED,
}

GUARD_RESULT_PERMITTED = "GUARD_RESULT_PERMITTED"
GUARD_RESULT_BLOCKED_DEFERRED_FAMILY = "GUARD_RESULT_BLOCKED_DEFERRED_FAMILY"
GUARD_RESULT_BLOCKED_NON_SCOPED_FAMILY = "GUARD_RESULT_BLOCKED_NON_SCOPED_FAMILY"
GUARD_RESULT_BLOCKED_REGISTRY_DISABLED = "GUARD_RESULT_BLOCKED_REGISTRY_DISABLED"
GUARD_RESULT_BLOCKED_REGISTRY_OBSERVE_ONLY = "GUARD_RESULT_BLOCKED_REGISTRY_OBSERVE_ONLY"
GUARD_RESULT_BLOCKED_CORE_BACKBONE_COMPOSITE_CHILD = "GUARD_RESULT_BLOCKED_CORE_BACKBONE_COMPOSITE_CHILD"


def _registry_ceiling(workflow_family: str) -> str:
    return _REGISTRY_CEILING.get(workflow_family, ACTIVATION_DISABLED)


def get_workflow_activation_state(workflow_family: str) -> str:
    """
    Effective activation state for governance-scoped checks (never above registry ceiling).

    Phase 2 limited enqueue families and the RST core backbone family read the registry ceiling;
    all others are ACTIVATION_DISABLED unless governance-deferred (also disabled at gate).
    """
    if workflow_family in GOVERNANCE_DEFERRED_FAMILIES:
        return ACTIVATION_DISABLED
    if workflow_family in _RST_CORE_BACKBONE_ACTIVATION_FAMILIES:
        return _registry_ceiling(workflow_family)
    if workflow_family in _PHASE2_LIMITED_ACTIVATION_FAMILIES:
        return _registry_ceiling(workflow_family)
    return ACTIVATION_DISABLED


def is_workflow_activation_enabled(
    workflow_family: str,
    *,
    required_minimum: str = ACTIVATION_LIMITED,
) -> bool:
    """True iff effective state meets or exceeds required_minimum (deterministic, no side effects)."""
    eff = get_workflow_activation_state(workflow_family)
    return _ACTIVATION_ORDER.get(eff, 0) >= _ACTIVATION_ORDER.get(required_minimum, 0)


def _activation_scope_for_family(workflow_family: str) -> str:
    if workflow_family == FAMILY_COMPLIANCE_SCORE_RECALC:
        return "compliance_recalc_enqueue_only"
    if workflow_family == FAMILY_REGENERATION_RECALC:
        return "risk_signal_regen_enqueue_only"
    if workflow_family == FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE:
        return "requirement_state_transition_core_backbone_only"
    return "unspecified_activation_scope"


def _min_activation_state(*states: str) -> str:
    return min(states, key=lambda s: _ACTIVATION_ORDER.get(s, -1))


def _slice_gate_for_child_embedding(ctx: Mapping[str, Any]) -> Dict[str, Any]:
    keys = (
        "activation_family",
        "activation_guard_result",
        "activation_reason",
        "activation_scope",
        "activation_state",
        "permitted",
        "registry_ceiling",
    )
    return {k: ctx.get(k) for k in keys}


def build_workflow_activation_context(workflow_family: str) -> Dict[str, Any]:
    """Read-only context for observability and guards (no mutation)."""
    if workflow_family == FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE:
        return build_rst_core_backbone_activation_context()

    ceiling = _registry_ceiling(workflow_family)
    effective = get_workflow_activation_state(workflow_family)
    permitted = is_workflow_activation_enabled(workflow_family, required_minimum=ACTIVATION_LIMITED)
    scope = _activation_scope_for_family(workflow_family)

    if workflow_family in GOVERNANCE_DEFERRED_FAMILIES:
        guard = GUARD_RESULT_BLOCKED_DEFERRED_FAMILY
        reason = "workflow_family_governance_deferred_registry_ceiling_not_applied"
    elif workflow_family not in _PHASE2_LIMITED_ACTIVATION_FAMILIES:
        guard = GUARD_RESULT_BLOCKED_NON_SCOPED_FAMILY
        reason = "phase2_activation_scope_limited_to_compliance_and_regeneration_recalc_only"
    elif ceiling == ACTIVATION_DISABLED:
        guard = GUARD_RESULT_BLOCKED_REGISTRY_DISABLED
        reason = "registry_ceiling_activation_disabled"
    elif ceiling == ACTIVATION_OBSERVE_ONLY:
        guard = GUARD_RESULT_BLOCKED_REGISTRY_OBSERVE_ONLY
        reason = "registry_ceiling_activation_observe_only"
    elif not permitted:
        guard = GUARD_RESULT_BLOCKED_REGISTRY_DISABLED
        reason = "effective_activation_below_required_minimum"
    elif workflow_family == FAMILY_REGENERATION_RECALC:
        guard = GUARD_RESULT_PERMITTED
        reason = "registry_allows_limited_regeneration_recalc_enqueue"
    else:
        guard = GUARD_RESULT_PERMITTED
        reason = "registry_allows_limited_compliance_score_recalc_enqueue"
    return {
        "activation_family": workflow_family,
        "activation_governance_version": ACTIVATION_GOVERNANCE_VERSION,
        "activation_guard_result": guard,
        "activation_reason": reason,
        "activation_scope": scope,
        "activation_state": effective,
        "registry_ceiling": ceiling,
        "permitted": permitted,
    }


def resolve_compliance_recalc_activation_gate() -> Dict[str, Any]:
    """Activation decision for compliance recalc enqueue path."""
    return build_workflow_activation_context(FAMILY_COMPLIANCE_SCORE_RECALC)


def resolve_regeneration_recalc_activation_gate() -> Dict[str, Any]:
    """Activation decision for risk signal regeneration enqueue path."""
    return build_workflow_activation_context(FAMILY_REGENERATION_RECALC)


def build_rst_core_backbone_activation_context() -> Dict[str, Any]:
    """
    Composite guard for requirement-state propagation entrypoints (authority → gap → gated enqueues).

    Permitted only when backbone ceiling allows LIMITED-or-higher and both child enqueue gates permit.
    Read-only; no DB.
    """
    fam = FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE
    comp = resolve_compliance_recalc_activation_gate()
    regen = resolve_regeneration_recalc_activation_gate()
    ceiling = _registry_ceiling(fam)
    backbone_eff = get_workflow_activation_state(fam)
    effective_state = _min_activation_state(
        backbone_eff,
        str(comp.get("activation_state") or ACTIVATION_DISABLED),
        str(regen.get("activation_state") or ACTIVATION_DISABLED),
    )
    backbone_enabled = is_workflow_activation_enabled(fam, required_minimum=ACTIVATION_LIMITED)

    if ceiling == ACTIVATION_DISABLED:
        guard = GUARD_RESULT_BLOCKED_REGISTRY_DISABLED
        reason = "rst_core_backbone_registry_ceiling_disabled"
    elif ceiling == ACTIVATION_OBSERVE_ONLY:
        guard = GUARD_RESULT_BLOCKED_REGISTRY_OBSERVE_ONLY
        reason = "rst_core_backbone_registry_ceiling_observe_only"
    elif not backbone_enabled:
        guard = GUARD_RESULT_BLOCKED_REGISTRY_DISABLED
        reason = "rst_core_backbone_effective_activation_below_limited"
    elif not bool(comp.get("permitted")):
        guard = GUARD_RESULT_BLOCKED_CORE_BACKBONE_COMPOSITE_CHILD
        reason = "rst_core_backbone_blocked_child_compliance_recalc_gate"
    elif not bool(regen.get("permitted")):
        guard = GUARD_RESULT_BLOCKED_CORE_BACKBONE_COMPOSITE_CHILD
        reason = "rst_core_backbone_blocked_child_regeneration_recalc_gate"
    else:
        guard = GUARD_RESULT_PERMITTED
        reason = "rst_core_backbone_registry_allows_authority_gap_recalc_regen_chain"

    permitted = guard == GUARD_RESULT_PERMITTED

    return {
        "activation_family": fam,
        "activation_governance_version": ACTIVATION_GOVERNANCE_VERSION,
        "activation_guard_result": guard,
        "activation_reason": reason,
        "activation_scope": _activation_scope_for_family(fam),
        "activation_state": effective_state,
        "child_compliance_recalc_gate": _slice_gate_for_child_embedding(comp),
        "child_regeneration_recalc_gate": _slice_gate_for_child_embedding(regen),
        "permitted": permitted,
        "registry_ceiling": ceiling,
    }


def resolve_requirement_state_transition_core_backbone_gate() -> Dict[str, Any]:
    """Public resolver alias for RST core backbone propagation (non-throwing)."""
    return build_rst_core_backbone_activation_context()


def build_runtime_activation_snapshot(*, generated_at_iso: str) -> Dict[str, Any]:
    """Read-only snapshot of registry-derived activation posture."""
    fams = sorted(set(_REGISTRY_CEILING.keys()) | _PHASE2_LIMITED_ACTIVATION_FAMILIES | _RST_CORE_BACKBONE_ACTIVATION_FAMILIES)
    rows = [build_workflow_activation_context(f) for f in fams]
    rows = sorted(rows, key=lambda r: str(r.get("activation_family") or ""))
    return {
        "activation_governance_version": ACTIVATION_GOVERNANCE_VERSION,
        "families": rows,
        "generated_at_iso": generated_at_iso,
        "schema_version": "workflow_runtime_activation_snapshot_v1",
    }


def build_activation_state_summary(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    rows = list(snapshot.get("families") or [])
    by_state: Dict[str, int] = {}
    for r in rows:
        k = str(r.get("activation_state") or "")
        by_state[k] = by_state.get(k, 0) + 1
    return {
        "by_activation_state": dict(sorted(by_state.items())),
        "schema_version": "activation_state_summary_v1",
    }


def build_activation_rollout_visibility(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    rows = list(snapshot.get("families") or [])
    active = sorted(
        str(r.get("activation_family") or "")
        for r in rows
        if str(r.get("activation_state")) == ACTIVATION_ENABLED and r.get("permitted")
    )
    limited = sorted(
        str(r.get("activation_family") or "")
        for r in rows
        if str(r.get("activation_state")) == ACTIVATION_LIMITED and r.get("permitted")
    )
    observe = sorted(
        str(r.get("activation_family") or "")
        for r in rows
        if str(r.get("activation_state")) == ACTIVATION_OBSERVE_ONLY
    )
    blocked = sorted(str(r.get("activation_family") or "") for r in rows if not r.get("permitted"))
    return {
        "activation_governance_version": snapshot.get("activation_governance_version"),
        "active_families": active,
        "blocked_families": blocked,
        "limited_families": limited,
        "observe_only_families": observe,
        "schema_version": "activation_rollout_visibility_v1",
    }


def build_rst_core_backbone_activation_operational_visibility(*, generated_at_iso: str) -> Dict[str, Any]:
    """Read-only RST core backbone slice for operators (authority/gap/recalc/regen chain gate)."""
    gate = build_rst_core_backbone_activation_context()
    snap = build_runtime_activation_snapshot(generated_at_iso=generated_at_iso)
    rows = list(snap.get("families") or [])
    brow = next(
        (r for r in rows if str(r.get("activation_family") or "") == FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE),
        {},
    )
    return {
        "activation_drift_visibility": "RST_CORE_BACKBONE_COMPOSITE_GATE_SUBJECT_TO_REGISTRY_V3",
        "child_compliance_permitted": bool((gate.get("child_compliance_recalc_gate") or {}).get("permitted")),
        "child_regeneration_permitted": bool((gate.get("child_regeneration_recalc_gate") or {}).get("permitted")),
        "convergence_continuity_visibility": "RST_CORE_BACKBONE_CHAIN_LIMITED_TO_GATED_ENQUEUES_ONLY",
        "downstream_propagation_visibility": "RST_CORE_BACKBONE_NO_BROAD_FANOUT",
        "generated_at_iso": generated_at_iso,
        "replay_reconciliation_continuity_visibility": "RST_CORE_BACKBONE_TRACE_ROWS_AND_MATRIX_UNCHANGED",
        "rollback_posture_visibility": "RST_CORE_BACKBONE_CODE_CEILING_ONLY_NO_QUEUE_RESET",
        "rst_core_backbone_activation_guard_result": brow.get("activation_guard_result") or gate.get("activation_guard_result"),
        "rst_core_backbone_activation_state": brow.get("activation_state") or gate.get("activation_state"),
        "rst_core_backbone_permitted": bool(gate.get("permitted")),
        "rst_core_backbone_registry_ceiling": brow.get("registry_ceiling") or gate.get("registry_ceiling"),
        "schema_version": "rst_core_backbone_activation_operational_visibility_v1",
        "skipped_propagation_visibility": "RST_CORE_BACKBONE_FANOUT_ROWS_ON_SKIP",
    }


def build_regeneration_limited_activation_visibility(*, generated_at_iso: str) -> Dict[str, Any]:
    """Read-only regeneration slice for operational / governance visibility (no DB)."""
    snap = build_runtime_activation_snapshot(generated_at_iso=generated_at_iso)
    rows = list(snap.get("families") or [])
    rrow = next((r for r in rows if str(r.get("activation_family") or "") == FAMILY_REGENERATION_RECALC), {})
    limited_fams = sorted(
        str(r.get("activation_family") or "")
        for r in rows
        if str(r.get("activation_state")) == ACTIVATION_LIMITED and r.get("permitted")
    )
    return {
        "limited_activation_families": limited_fams,
        "limited_activation_family_count": len(limited_fams),
        "regeneration_activation_guard_result": rrow.get("activation_guard_result"),
        "regeneration_activation_state": rrow.get("activation_state"),
        "regeneration_enqueue_continuity_visibility": "REGEN_ENQUEUE_SUBJECT_TO_RUNTIME_ACTIVATION_GATE",
        "regeneration_permitted": bool(rrow.get("permitted")),
        "regeneration_registry_ceiling": rrow.get("registry_ceiling"),
        "schema_version": "regeneration_limited_activation_visibility_v1",
    }


def list_registry_family_keys() -> List[str]:
    """Deterministic list of families with an explicit registry ceiling entry."""
    return sorted(_REGISTRY_CEILING.keys())
