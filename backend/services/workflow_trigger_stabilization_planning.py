"""
Workflow Trigger Stabilization Planning — Phase 3 (planning-only).

Consumes Phase 2 evidence matrix; emits deterministic stabilization backlog labels.
No runtime mutation, no enforcement, no queue/retry implementation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from services.workflow_trigger_reliability_audit_phase2 import (
    HIGH_SILENT_FAILURE_RISK,
    MODERATE_SILENT_FAILURE_RISK,
    NO_RECONCILIATION_EVIDENCE,
    NO_RETRY_EVIDENCE,
    ORCHESTRATION_FRAGMENTED,
    ORCHESTRATION_READ_REBUILD_HEAVY,
    build_workflow_trigger_reliability_evidence_matrix_phase2,
)

# --- Stabilization tracks (planning labels only) ---
SAFE_ENGINEERING_STABILIZATION = "SAFE_ENGINEERING_STABILIZATION"
QUEUE_PATTERN_ALIGNMENT = "QUEUE_PATTERN_ALIGNMENT"
IDEMPOTENCY_HARDENING = "IDEMPOTENCY_HARDENING"
RETRY_RECOVERY_HARDENING = "RETRY_RECOVERY_HARDENING"
OBSERVABILITY_HARDENING = "OBSERVABILITY_HARDENING"
DEGRADED_STATE_VISIBILITY = "DEGRADED_STATE_VISIBILITY"
CACHE_GOVERNANCE_REQUIRED = "CACHE_GOVERNANCE_REQUIRED"
ARCHITECTURE_REDESIGN_REQUIRED = "ARCHITECTURE_REDESIGN_REQUIRED"
EVENT_MODEL_REQUIRED = "EVENT_MODEL_REQUIRED"
DO_NOT_IMPLEMENT_YET = "DO_NOT_IMPLEMENT_YET"
OBSERVE_ONLY = "OBSERVE_ONLY"

# --- Implementation readiness ---
READY_FOR_STABILIZATION = "READY_FOR_STABILIZATION"
READY_WITH_GOVERNANCE_REVIEW = "READY_WITH_GOVERNANCE_REVIEW"
REQUIRES_ARCHITECTURE_DECISION = "REQUIRES_ARCHITECTURE_DECISION"
REQUIRES_EVENT_MODEL = "REQUIRES_EVENT_MODEL"
REQUIRES_CACHE_OWNERSHIP = "REQUIRES_CACHE_OWNERSHIP"
REQUIRES_OBSERVABILITY_FIRST = "REQUIRES_OBSERVABILITY_FIRST"
REQUIRES_IDEMPOTENCY_FIRST = "REQUIRES_IDEMPOTENCY_FIRST"
NOT_SAFE_TO_MODIFY = "NOT_SAFE_TO_MODIFY"
INSUFFICIENT_RUNTIME_EVIDENCE = "INSUFFICIENT_RUNTIME_EVIDENCE"

# --- Urgency ---
P0_CRITICAL_RUNTIME_RISK = "P0_CRITICAL_RUNTIME_RISK"
P1_HIGH_TRUST_SURFACE = "P1_HIGH_TRUST_SURFACE"
P2_HIGH_DUPLICATE_RISK = "P2_HIGH_DUPLICATE_RISK"
P3_HIGH_STALE_STATE_RISK = "P3_HIGH_STALE_STATE_RISK"
P4_OBSERVABILITY_GAP = "P4_OBSERVABILITY_GAP"
P5_LOW_RISK_ALIGNMENT = "P5_LOW_RISK_ALIGNMENT"
P6_OBSERVE_ONLY = "P6_OBSERVE_ONLY"

# --- Architecture blockers ---
NO_SINGLE_OWNER = "NO_SINGLE_OWNER"
FRAGMENTED_REFRESH_MODEL = "FRAGMENTED_REFRESH_MODEL"
READ_REBUILD_HEAVY = "READ_REBUILD_HEAVY"
CACHE_BOUNDARY_UNDEFINED = "CACHE_BOUNDARY_UNDEFINED"
NO_RETRY_CONTRACT = "NO_RETRY_CONTRACT"
NO_RECONCILIATION_CONTRACT = "NO_RECONCILIATION_CONTRACT"
NO_DEGRADED_STATE_SIGNALING = "NO_DEGRADED_STATE_SIGNALING"
MIXED_SYNC_ASYNC_CHAIN = "MIXED_SYNC_ASYNC_CHAIN"
PARTIAL_PROPAGATION_RISK = "PARTIAL_PROPAGATION_RISK"
SILENT_FAILURE_EXPOSURE = "SILENT_FAILURE_EXPOSURE"

HARD_BLOCKER = "HARD_BLOCKER"
SOFT_BLOCKER = "SOFT_BLOCKER"
OBSERVATION_ONLY = "OBSERVATION_ONLY"
NON_BLOCKING = "NON_BLOCKING"

# --- Rollout safety posture ---
SAFE_FOR_INCREMENTAL_STABILIZATION = "SAFE_FOR_INCREMENTAL_STABILIZATION"
SAFE_FOR_OBSERVABILITY_ONLY = "SAFE_FOR_OBSERVABILITY_ONLY"
SAFE_FOR_READ_PATH_IMPROVEMENT = "SAFE_FOR_READ_PATH_IMPROVEMENT"
UNSAFE_FOR_RUNTIME_ENFORCEMENT = "UNSAFE_FOR_RUNTIME_ENFORCEMENT"
UNSAFE_FOR_AUTOMATION_EXPANSION = "UNSAFE_FOR_AUTOMATION_EXPANSION"
DEFER_UNTIL_ARCHITECTURE_REVIEW = "DEFER_UNTIL_ARCHITECTURE_REVIEW"


REFERENCE_STABILIZATION_PATTERNS: Dict[str, Any] = {
    "COMPLIANCE_SCORE_RECALC": {
        "summary": "Mongo-backed enqueue with correlation dedupe + worker backoff/DEAD + audit on failure",
        "reusability": "reusable",
        "primary_modules": [
            "services/compliance_recalc_queue.py",
            "job_runner.py",
        ],
        "governance_note": "Treat as canonical queue pattern for property-scoped async recompute.",
    },
    "REGENERATION_RECALC": {
        "summary": "Scheduled/admin triggers reuse same queue/worker path as score recalc",
        "reusability": "reusable",
        "primary_modules": ["services/jobs.py", "job_runner.py"],
        "governance_note": "Keep correlation discipline consistent with COMPLIANCE_SCORE_RECALC.",
    },
    "NOTIFICATION_DISPATCH": {
        "summary": "message_logs idempotency_key + deferred retry queue; branch-specific retry semantics",
        "reusability": "partially_reusable",
        "primary_modules": ["services/notification_orchestrator.py", "job_runner.py"],
        "governance_note": "Do not generalize inline Postmark retry vs deferred queue without explicit contract.",
    },
}


def _blocker(tag: str, severity: str) -> Dict[str, str]:
    return {"blocker": tag, "severity": severity}


def _derive_blockers(ev: Mapping[str, Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    fam = ev["workflow_family"]
    orch = ev["orchestration_maturity"]
    if orch == ORCHESTRATION_FRAGMENTED:
        out.append(_blocker(FRAGMENTED_REFRESH_MODEL, SOFT_BLOCKER))
        out.append(_blocker(NO_SINGLE_OWNER, OBSERVATION_ONLY))
    if orch == ORCHESTRATION_READ_REBUILD_HEAVY:
        out.append(_blocker(READ_REBUILD_HEAVY, SOFT_BLOCKER))
        out.append(_blocker(NO_DEGRADED_STATE_SIGNALING, HARD_BLOCKER if ev["silent_failure_risk_class"] == HIGH_SILENT_FAILURE_RISK else SOFT_BLOCKER))
    if ev["retry_evidence_class"] == NO_RETRY_EVIDENCE:
        out.append(_blocker(NO_RETRY_CONTRACT, SOFT_BLOCKER))
    if ev["reconciliation_evidence_class"] == NO_RECONCILIATION_EVIDENCE:
        out.append(_blocker(NO_RECONCILIATION_CONTRACT, OBSERVATION_ONLY))
    if ev["silent_failure_risk_class"] in (HIGH_SILENT_FAILURE_RISK, MODERATE_SILENT_FAILURE_RISK):
        out.append(_blocker(SILENT_FAILURE_EXPOSURE, SOFT_BLOCKER))
    if fam == "CACHE_INVALIDATION":
        out.append(_blocker(CACHE_BOUNDARY_UNDEFINED, HARD_BLOCKER))
    if fam == "REQUIREMENT_STATE_TRANSITION":
        out.append(_blocker(MIXED_SYNC_ASYNC_CHAIN, SOFT_BLOCKER))
        out.append(_blocker(PARTIAL_PROPAGATION_RISK, OBSERVATION_ONLY))
    # Dedupe same blocker type
    seen = set()
    deduped: List[Dict[str, str]] = []
    for b in out:
        k = (b["blocker"], b["severity"])
        if k not in seen:
            seen.add(k)
            deduped.append(b)
    return sorted(deduped, key=lambda x: (x["blocker"], x["severity"]))


def _plan_row(ev: Mapping[str, Any]) -> Dict[str, Any]:
    """Deterministic planning row from Phase 2 evidence (explicit per family)."""
    fam = ev["workflow_family"]
    strongest = list(ev.get("strongest_evidence_found") or [])
    weakest = list(ev.get("weakest_evidence_found") or [])
    gov_notes: List[str] = []

    if fam == "COMPLIANCE_SCORE_RECALC":
        return {
            "workflow_family": fam,
            "stabilization_track": QUEUE_PATTERN_ALIGNMENT,
            "implementation_readiness": READY_FOR_STABILIZATION,
            "urgency_class": P5_LOW_RISK_ALIGNMENT,
            "rollout_safety_posture": SAFE_FOR_INCREMENTAL_STABILIZATION,
            "recommended_stabilization_order": 1,
            "dependency_chains": ["enqueue → worker → persisted score → read surfaces"],
            "reference_pattern_applicability": "reusable",
            "governance_notes": gov_notes + ["Reference pattern: REFERENCE_STABILIZATION_PATTERNS.COMPLIANCE_SCORE_RECALC"],
        }
    if fam == "REGENERATION_RECALC":
        return {
            "workflow_family": fam,
            "stabilization_track": QUEUE_PATTERN_ALIGNMENT,
            "implementation_readiness": READY_FOR_STABILIZATION,
            "urgency_class": P5_LOW_RISK_ALIGNMENT,
            "rollout_safety_posture": SAFE_FOR_INCREMENTAL_STABILIZATION,
            "recommended_stabilization_order": 2,
            "dependency_chains": ["jobs.py periodic → enqueue → same worker as score recalc"],
            "reference_pattern_applicability": "reusable",
            "governance_notes": gov_notes + ["Align correlation naming with COMPLIANCE_SCORE_RECALC before expanding sweep breadth"],
        }
    if fam == "COMMAND_CENTER_REFRESH":
        return {
            "workflow_family": fam,
            "stabilization_track": DEGRADED_STATE_VISIBILITY,
            "implementation_readiness": REQUIRES_OBSERVABILITY_FIRST,
            "urgency_class": P1_HIGH_TRUST_SURFACE,
            "rollout_safety_posture": UNSAFE_FOR_AUTOMATION_EXPANSION,
            "recommended_stabilization_order": 3,
            "dependency_chains": ["unified_tasks → compliance_score → gap aggregate → optional HIUA"],
            "reference_pattern_applicability": "unsafe_to_generalize",
            "governance_notes": gov_notes + ["Trust surface: explicit degraded flags before adding automation"],
        }
    if fam == "TODAY_TASK_REBUILD":
        return {
            "workflow_family": fam,
            "stabilization_track": DEGRADED_STATE_VISIBILITY,
            "implementation_readiness": REQUIRES_OBSERVABILITY_FIRST,
            "urgency_class": P1_HIGH_TRUST_SURFACE,
            "rollout_safety_posture": UNSAFE_FOR_AUTOMATION_EXPANSION,
            "recommended_stabilization_order": 4,
            "dependency_chains": ["requirement truth → priority actions → digest composition"],
            "reference_pattern_applicability": "unsafe_to_generalize",
            "governance_notes": gov_notes + ["Coordinate with Command Centre sequencing to avoid duplicate UX signals"],
        }
    if fam == "REQUIREMENT_STATE_TRANSITION":
        return {
            "workflow_family": fam,
            "stabilization_track": IDEMPOTENCY_HARDENING,
            "implementation_readiness": REQUIRES_IDEMPOTENCY_FIRST,
            "urgency_class": P2_HIGH_DUPLICATE_RISK,
            "rollout_safety_posture": SAFE_FOR_INCREMENTAL_STABILIZATION,
            "recommended_stabilization_order": 5,
            "dependency_chains": ["DB write → enqueue recalc → gap sync / semantic follow-through"],
            "reference_pattern_applicability": "partially_reusable",
            "governance_notes": gov_notes + ["Governance review before widening auto-transition triggers"],
        }
    if fam == "NOTIFICATION_DISPATCH":
        return {
            "workflow_family": fam,
            "stabilization_track": QUEUE_PATTERN_ALIGNMENT,
            "implementation_readiness": READY_WITH_GOVERNANCE_REVIEW,
            "urgency_class": P4_OBSERVABILITY_GAP,
            "rollout_safety_posture": SAFE_FOR_INCREMENTAL_STABILIZATION,
            "recommended_stabilization_order": 6,
            "dependency_chains": ["orchestrator.send → provider → retry queue"],
            "reference_pattern_applicability": "partially_reusable",
            "governance_notes": gov_notes + ["Document inline vs deferred retry contract before hardening"],
        }
    if fam == "COMPLIANCE_GAP_SYNC":
        return {
            "workflow_family": fam,
            "stabilization_track": SAFE_ENGINEERING_STABILIZATION,
            "implementation_readiness": REQUIRES_OBSERVABILITY_FIRST,
            "urgency_class": P4_OBSERVABILITY_GAP,
            "rollout_safety_posture": SAFE_FOR_OBSERVABILITY_ONLY,
            "recommended_stabilization_order": 7,
            "dependency_chains": ["infer gaps → upsert compliance_gaps → operational bridge"],
            "reference_pattern_applicability": "partially_reusable",
            "governance_notes": gov_notes + ["Observability-first: surface sync errors[] to operators without widening writes"],
        }
    if fam == "REMINDER_TRIGGER":
        return {
            "workflow_family": fam,
            "stabilization_track": OBSERVABILITY_HARDENING,
            "implementation_readiness": READY_WITH_GOVERNANCE_REVIEW,
            "urgency_class": P6_OBSERVE_ONLY,
            "rollout_safety_posture": SAFE_FOR_OBSERVABILITY_ONLY,
            "recommended_stabilization_order": 8,
            "dependency_chains": ["evaluation cadence → reminder truth → optional notification"],
            "reference_pattern_applicability": "unsafe_to_generalize",
            "governance_notes": gov_notes + ["Observe-only batch until gap-context swallowing is classified"],
        }
    if fam == "PORTFOLIO_SUMMARY_REFRESH":
        return {
            "workflow_family": fam,
            "stabilization_track": OBSERVABILITY_HARDENING,
            "implementation_readiness": REQUIRES_OBSERVABILITY_FIRST,
            "urgency_class": P1_HIGH_TRUST_SURFACE,
            "rollout_safety_posture": UNSAFE_FOR_AUTOMATION_EXPANSION,
            "recommended_stabilization_order": 9,
            "dependency_chains": ["portfolio route → gap aggregate / score read"],
            "reference_pattern_applicability": "unsafe_to_generalize",
            "governance_notes": gov_notes + ["Align with Command Centre freshness semantics"],
        }
    if fam == "CACHE_INVALIDATION":
        return {
            "workflow_family": fam,
            "stabilization_track": CACHE_GOVERNANCE_REQUIRED,
            "implementation_readiness": REQUIRES_CACHE_OWNERSHIP,
            "urgency_class": P0_CRITICAL_RUNTIME_RISK,
            "rollout_safety_posture": DEFER_UNTIL_ARCHITECTURE_REVIEW,
            "recommended_stabilization_order": 10,
            "dependency_chains": ["HTTP headers (multi-route) || domain invalidate_pending_routing"],
            "reference_pattern_applicability": "unsafe_to_generalize",
            "governance_notes": gov_notes + ["Architecture + infra ownership required before engineering stabilization"],
        }
    raise ValueError(f"Unknown workflow family for planning: {fam}")


def _blocker_severity_summary(blockers: Sequence[Mapping[str, str]]) -> str:
    if any(b["severity"] == HARD_BLOCKER for b in blockers):
        return HARD_BLOCKER
    if any(b["severity"] == SOFT_BLOCKER for b in blockers):
        return SOFT_BLOCKER
    return OBSERVATION_ONLY


def build_workflow_trigger_stabilization_matrix_phase3() -> List[Dict[str, Any]]:
    evidence = build_workflow_trigger_reliability_evidence_matrix_phase2()
    matrix: List[Dict[str, Any]] = []
    for ev in sorted(evidence, key=lambda r: r["workflow_family"]):
        plan = _plan_row(ev)
        blockers = _derive_blockers(ev)
        row = {
            **plan,
            "phase2_orchestration_maturity": ev["orchestration_maturity"],
            "phase2_retry_evidence_class": ev["retry_evidence_class"],
            "phase2_idempotency_evidence_class": ev["idempotency_evidence_class"],
            "phase2_stale_state_dependency_class": ev["stale_state_dependency_class"],
            "phase2_silent_failure_risk_class": ev["silent_failure_risk_class"],
            "strongest_evidence": list(ev.get("strongest_evidence_found") or []),
            "weakest_evidence": list(ev.get("weakest_evidence_found") or []),
            "architecture_blockers": blockers,
            "blocker_severity_summary": _blocker_severity_summary(blockers),
        }
        matrix.append(row)
    return matrix


def _rollup(matrix: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    by_f = {r["workflow_family"]: r for r in matrix}
    safest = sorted(
        r["workflow_family"]
        for r in matrix
        if r["rollout_safety_posture"] == SAFE_FOR_INCREMENTAL_STABILIZATION
        and r["implementation_readiness"] == READY_FOR_STABILIZATION
    )
    highest_risk = sorted(
        by_f.keys(),
        key=lambda f: (
            0 if by_f[f]["urgency_class"] == P0_CRITICAL_RUNTIME_RISK else 1,
            0 if by_f[f]["rollout_safety_posture"] == DEFER_UNTIL_ARCHITECTURE_REVIEW else 1,
            f,
        ),
    )
    arch_redesign = sorted(f for f, r in by_f.items() if r["stabilization_track"] == ARCHITECTURE_REDESIGN_REQUIRED)
    # none explicitly mapped to ARCHITECTURE_REDESIGN_REQUIRED — CACHE uses CACHE_GOVERNANCE; add CACHE to redesign candidates list
    arch_redesign_candidates = sorted(set(arch_redesign) | {f for f, r in by_f.items() if f == "CACHE_INVALIDATION"})
    queue_ref = sorted(f for f, r in by_f.items() if r["stabilization_track"] == QUEUE_PATTERN_ALIGNMENT)
    obs_first = sorted(f for f, r in by_f.items() if r["implementation_readiness"] == REQUIRES_OBSERVABILITY_FIRST)
    idem_first = sorted(f for f, r in by_f.items() if r["implementation_readiness"] == REQUIRES_IDEMPOTENCY_FIRST)
    degraded = sorted(f for f, r in by_f.items() if r["stabilization_track"] == DEGRADED_STATE_VISIBILITY)
    unsafe_auto = sorted(
        f
        for f, r in by_f.items()
        if r["rollout_safety_posture"] in (UNSAFE_FOR_AUTOMATION_EXPANSION, UNSAFE_FOR_RUNTIME_ENFORCEMENT, DEFER_UNTIL_ARCHITECTURE_REVIEW)
    )
    sequencing = [r["workflow_family"] for r in sorted(matrix, key=lambda x: (x["recommended_stabilization_order"], x["workflow_family"]))]
    return {
        "safest_stabilization_candidates": safest,
        "highest_risk_workflow_families": highest_risk,
        "architecture_redesign_candidates": arch_redesign_candidates,
        "queue_reference_pattern_candidates": queue_ref,
        "observability_first_candidates": obs_first,
        "idempotency_hardening_candidates": idem_first,
        "degraded_state_visibility_candidates": degraded,
        "unsafe_for_automation_expansion_families": unsafe_auto,
        "recommended_stabilization_sequencing": sequencing,
    }


def build_workflow_trigger_stabilization_phase3_snapshot(
    *,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    matrix = build_workflow_trigger_stabilization_matrix_phase3()
    roll = _rollup(matrix)
    ts = generated_at or datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": "workflow_trigger_stabilization_phase3_v1",
        "generated_at": ts,
        "reference_stabilization_patterns": REFERENCE_STABILIZATION_PATTERNS,
        "stabilization_matrix": matrix,
        **roll,
        "remaining_limitations": [
            "Planning consumes Phase 2 static evidence only; no live SLO or trace linkage.",
            "Readiness and urgency are governance labels, not production approvals.",
            "First implementation slice must still pass change control and staged rollout.",
        ],
        "runtime_behavior_changed": False,
        "audit_only": True,
        "non_blocking": True,
    }


def write_workflow_trigger_stabilization_phase3_json(
    output_path: Optional[Path] = None,
    *,
    generated_at: Optional[str] = None,
) -> Path:
    root = Path(__file__).resolve().parents[1]
    dest = output_path or (root / "docs" / "audit" / "WORKFLOW_TRIGGER_STABILIZATION_PHASE3.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    snap = build_workflow_trigger_stabilization_phase3_snapshot(generated_at=generated_at)
    dest.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return dest


def stable_phase3_snapshot_for_tests() -> Dict[str, Any]:
    return build_workflow_trigger_stabilization_phase3_snapshot(generated_at="1970-01-01T00:00:00+00:00")
