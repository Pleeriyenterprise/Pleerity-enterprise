"""
Workflow Trigger Reliability Audit — Phase 1 (read-only, non-blocking).

Deterministic operational mapping of critical workflow trigger families:
propagation posture, idempotency, recovery, observability, and fragmentation risks.
Does not invoke orchestration, mutate runtime state, or enforce policies.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

# --- Trigger activation (propagation / scheduling model) ---
TRIGGER_DIRECT_SYNCHRONOUS = "TRIGGER_DIRECT_SYNCHRONOUS"
TRIGGER_EVENTUAL = "TRIGGER_EVENTUAL"
TRIGGER_PERIODIC = "TRIGGER_PERIODIC"
TRIGGER_DERIVED_ON_READ = "TRIGGER_DERIVED_ON_READ"
TRIGGER_FRAGMENTED = "TRIGGER_FRAGMENTED"
TRIGGER_UNKNOWN = "TRIGGER_UNKNOWN"

_TRIGGER_TYPES = frozenset(
    {
        TRIGGER_DIRECT_SYNCHRONOUS,
        TRIGGER_EVENTUAL,
        TRIGGER_PERIODIC,
        TRIGGER_DERIVED_ON_READ,
        TRIGGER_FRAGMENTED,
        TRIGGER_UNKNOWN,
    }
)

# --- Reliability (aggregate judgment for activation confidence) ---
HIGH_RELIABILITY = "HIGH_RELIABILITY"
MODERATE_RELIABILITY = "MODERATE_RELIABILITY"
LOW_RELIABILITY = "LOW_RELIABILITY"
UNVERIFIED_RELIABILITY = "UNVERIFIED_RELIABILITY"
UNKNOWN_RELIABILITY = "UNKNOWN_RELIABILITY"

_RELIABILITY_CLASSES = frozenset(
    {
        HIGH_RELIABILITY,
        MODERATE_RELIABILITY,
        LOW_RELIABILITY,
        UNVERIFIED_RELIABILITY,
        UNKNOWN_RELIABILITY,
    }
)

# --- Propagation / integrity failure classes (subset per family) ---
NO_RETRY_STRATEGY = "NO_RETRY_STRATEGY"
NO_RECONCILIATION_PATH = "NO_RECONCILIATION_PATH"
POTENTIAL_DUPLICATE_TRIGGER = "POTENTIAL_DUPLICATE_TRIGGER"
STALE_READ_DEPENDENCY = "STALE_READ_DEPENDENCY"
PARTIAL_PROPAGATION_RISK = "PARTIAL_PROPAGATION_RISK"
ORPHAN_STATE_RISK = "ORPHAN_STATE_RISK"
SILENT_FAILURE_RISK = "SILENT_FAILURE_RISK"
FRAGMENTED_TRIGGER_CHAIN = "FRAGMENTED_TRIGGER_CHAIN"
UNKNOWN_DOWNSTREAM_STATE = "UNKNOWN_DOWNSTREAM_STATE"

_FAILURE_CLASSES = frozenset(
    {
        NO_RETRY_STRATEGY,
        NO_RECONCILIATION_PATH,
        POTENTIAL_DUPLICATE_TRIGGER,
        STALE_READ_DEPENDENCY,
        PARTIAL_PROPAGATION_RISK,
        ORPHAN_STATE_RISK,
        SILENT_FAILURE_RISK,
        FRAGMENTED_TRIGGER_CHAIN,
        UNKNOWN_DOWNSTREAM_STATE,
    }
)

# --- Idempotency posture ---
IDEMPOTENT = "IDEMPOTENT"
PARTIALLY_IDEMPOTENT = "PARTIALLY_IDEMPOTENT"
NON_IDEMPOTENT = "NON_IDEMPOTENT"
UNKNOWN_IDEMPOTENCY = "UNKNOWN_IDEMPOTENCY"

_IDEMPOTENCY_CLASSES = frozenset({IDEMPOTENT, PARTIALLY_IDEMPOTENT, NON_IDEMPOTENT, UNKNOWN_IDEMPOTENCY})

# --- Recovery / reconciliation posture ---
RECOVERY_READY = "RECOVERY_READY"
PARTIAL_RECOVERY = "PARTIAL_RECOVERY"
MANUAL_RECOVERY_HEAVY = "MANUAL_RECOVERY_HEAVY"
NO_KNOWN_RECOVERY = "NO_KNOWN_RECOVERY"
UNKNOWN_RECOVERY = "UNKNOWN_RECOVERY"

_RECOVERY_CLASSES = frozenset(
    {RECOVERY_READY, PARTIAL_RECOVERY, MANUAL_RECOVERY_HEAVY, NO_KNOWN_RECOVERY, UNKNOWN_RECOVERY}
)

# --- Observability ---
FULL_OBSERVABILITY = "FULL_OBSERVABILITY"
PARTIAL_OBSERVABILITY = "PARTIAL_OBSERVABILITY"
LIMITED_OBSERVABILITY = "LIMITED_OBSERVABILITY"
BLACK_BOX_BEHAVIOR = "BLACK_BOX_BEHAVIOR"

_OBSERVABILITY_CLASSES = frozenset(
    {FULL_OBSERVABILITY, PARTIAL_OBSERVABILITY, LIMITED_OBSERVABILITY, BLACK_BOX_BEHAVIOR}
)

# --- Exposure / confidence (row-level scalars) ---
_EXPOSURE_LEVELS = frozenset({"NONE", "LOW", "MODERATE", "HIGH"})
_RUNTIME_CONFIDENCE = frozenset({"HIGH", "MODERATE", "LOW", "UNVERIFIED"})
_MATURITY = frozenset({"MATURE", "EVOLVING", "EXPERIMENTAL", "LEGACY_MIXED"})


def _row(
    workflow_family: str,
    trigger_source: str,
    trigger_activation_type: str,
    downstream_consumers: Sequence[str],
    orchestration_path: str,
    refresh_model: str,
    operational_owner: str,
    propagation_failure_flags: Sequence[str],
    idempotency_posture: str,
    recovery_posture: str,
    observability_posture: str,
    reliability_class: str,
    stale_state_exposure: str,
    orphan_risk_exposure: str,
    duplicate_trigger_exposure: str,
    runtime_activation_confidence: str,
    operational_maturity_level: str,
) -> Dict[str, Any]:
    flags = tuple(sorted({f for f in propagation_failure_flags if f in _FAILURE_CLASSES}))
    for f in flags:
        assert f in _FAILURE_CLASSES, f
    assert trigger_activation_type in _TRIGGER_TYPES
    assert reliability_class in _RELIABILITY_CLASSES
    assert idempotency_posture in _IDEMPOTENCY_CLASSES
    assert recovery_posture in _RECOVERY_CLASSES
    assert observability_posture in _OBSERVABILITY_CLASSES
    assert stale_state_exposure in _EXPOSURE_LEVELS
    assert orphan_risk_exposure in _EXPOSURE_LEVELS
    assert duplicate_trigger_exposure in _EXPOSURE_LEVELS
    assert runtime_activation_confidence in _RUNTIME_CONFIDENCE
    assert operational_maturity_level in _MATURITY
    return {
        "workflow_family": workflow_family,
        "trigger_source": trigger_source,
        "trigger_activation_type": trigger_activation_type,
        "downstream_consumers": list(downstream_consumers),
        "orchestration_path": orchestration_path,
        "refresh_model": refresh_model,
        "operational_owner": operational_owner,
        "propagation_failure_flags": list(flags),
        "idempotency_posture": idempotency_posture,
        "recovery_posture": recovery_posture,
        "observability_posture": observability_posture,
        "reliability_class": reliability_class,
        "stale_state_exposure": stale_state_exposure,
        "orphan_risk_exposure": orphan_risk_exposure,
        "duplicate_trigger_exposure": duplicate_trigger_exposure,
        "runtime_activation_confidence": runtime_activation_confidence,
        "operational_maturity_level": operational_maturity_level,
    }


def _catalog_rows() -> Tuple[Dict[str, Any], ...]:
    """Frozen Phase-1 catalog: curated operational model (audit-only)."""
    return (
        _row(
            "DOCUMENT_UPLOAD",
            "Client portal / API evidence attach; ingestion hooks",
            TRIGGER_DIRECT_SYNCHRONOUS,
            (
                "REQUIREMENT_ROW",
                "EVIDENCE_AUTHORITY",
                "SEMANTIC_STATE_TRANSITION",
                "COMPLIANCE_SCORE_RECALC",
                "TODAY_TASK_REBUILD",
            ),
            "API handler → persistence → downstream recalc hooks",
            "Synchronous commit + queued/eventual rollups",
            "compliance_runtime_ingestion",
            (PARTIAL_PROPAGATION_RISK, POTENTIAL_DUPLICATE_TRIGGER, STALE_READ_DEPENDENCY),
            PARTIALLY_IDEMPOTENT,
            PARTIAL_RECOVERY,
            PARTIAL_OBSERVABILITY,
            MODERATE_RELIABILITY,
            "MODERATE",
            "LOW",
            "MODERATE",
            "MODERATE",
            "MATURE",
        ),
        _row(
            "REQUIREMENT_STATE_TRANSITION",
            "Registry resolver; status engine; admin corrections",
            TRIGGER_FRAGMENTED,
            ("COMMAND_CENTER_REFRESH", "TODAY_TASK_REBUILD", "REMINDER_TRIGGER", "COMPLIANCE_SCORE_RECALC"),
            "Multiple writers + read models; cross-service fan-out",
            "Mixed sync/async by entrypoint",
            "compliance_requirement_engine",
            (FRAGMENTED_TRIGGER_CHAIN, POTENTIAL_DUPLICATE_TRIGGER, PARTIAL_PROPAGATION_RISK),
            PARTIALLY_IDEMPOTENT,
            PARTIAL_RECOVERY,
            PARTIAL_OBSERVABILITY,
            LOW_RELIABILITY,
            "HIGH",
            "MODERATE",
            "HIGH",
            "LOW",
            "EVOLVING",
        ),
        _row(
            "SEMANTIC_STATE_TRANSITION",
            "Evidence authority / semantic projection updates",
            TRIGGER_EVENTUAL,
            ("REMINDER_TRIGGER", "REPORT_GENERATION", "COMMAND_CENTER_REFRESH", "NOTIFICATION_DISPATCH"),
            "Semantic write → projection lag → consumer reads",
            "Eventual consistency; read-time guards",
            "semantic_governance_plane",
            (STALE_READ_DEPENDENCY, PARTIAL_PROPAGATION_RISK, UNKNOWN_DOWNSTREAM_STATE),
            PARTIALLY_IDEMPOTENT,
            PARTIAL_RECOVERY,
            PARTIAL_OBSERVABILITY,
            MODERATE_RELIABILITY,
            "HIGH",
            "MODERATE",
            "MODERATE",
            "MODERATE",
            "EVOLVING",
        ),
        _row(
            "COMPLIANCE_SCORE_RECALC",
            "Scoring engine; property/portfolio rollups",
            TRIGGER_EVENTUAL,
            ("PORTFOLIO_SUMMARY_REFRESH", "COMMAND_CENTER_REFRESH", "REPORT_GENERATION"),
            "Job or inline trigger → score tables → dashboards",
            "Async worker / deferred batch",
            "compliance_scoring_runtime",
            (POTENTIAL_DUPLICATE_TRIGGER, STALE_READ_DEPENDENCY, NO_RETRY_STRATEGY),
            PARTIALLY_IDEMPOTENT,
            RECOVERY_READY,
            PARTIAL_OBSERVABILITY,
            MODERATE_RELIABILITY,
            "MODERATE",
            "LOW",
            "HIGH",
            "MODERATE",
            "MATURE",
        ),
        _row(
            "TODAY_TASK_REBUILD",
            "Unified tasks / priority surfaces",
            TRIGGER_EVENTUAL,
            ("COMMAND_CENTER_REFRESH", "NOTIFICATION_DISPATCH"),
            "Task builder job → task tables",
            "Queued rebuild; partial sync paths",
            "unified_tasks_service",
            (PARTIAL_PROPAGATION_RISK, ORPHAN_STATE_RISK, SILENT_FAILURE_RISK),
            PARTIALLY_IDEMPOTENT,
            PARTIAL_RECOVERY,
            LIMITED_OBSERVABILITY,
            LOW_RELIABILITY,
            "HIGH",
            "MODERATE",
            "MODERATE",
            "LOW",
            "EVOLVING",
        ),
        _row(
            "COMMAND_CENTER_REFRESH",
            "Control centre aggregates",
            TRIGGER_DERIVED_ON_READ,
            ("UI_CLIENT_CACHE", "ADMIN_OPERATOR_VIEW"),
            "Read API composes from multiple sources",
            "On-read + opportunistic cache",
            "control_centre_service",
            (STALE_READ_DEPENDENCY, FRAGMENTED_TRIGGER_CHAIN, UNKNOWN_DOWNSTREAM_STATE),
            UNKNOWN_IDEMPOTENCY,
            MANUAL_RECOVERY_HEAVY,
            LIMITED_OBSERVABILITY,
            LOW_RELIABILITY,
            "HIGH",
            "LOW",
            "LOW",
            "UNVERIFIED",
            "LEGACY_MIXED",
        ),
        _row(
            "REMINDER_TRIGGER",
            "Reminder / SLA cadence engines",
            TRIGGER_PERIODIC,
            ("NOTIFICATION_DISPATCH", "SLA_ESCALATION"),
            "Scheduler → reminder truth → outbound channels",
            "Cron / interval tick",
            "reminder_truth_service",
            (POTENTIAL_DUPLICATE_TRIGGER, SILENT_FAILURE_RISK, PARTIAL_PROPAGATION_RISK),
            PARTIALLY_IDEMPOTENT,
            PARTIAL_RECOVERY,
            PARTIAL_OBSERVABILITY,
            MODERATE_RELIABILITY,
            "MODERATE",
            "MODERATE",
            "HIGH",
            "MODERATE",
            "MATURE",
        ),
        _row(
            "NOTIFICATION_DISPATCH",
            "Email / in-app notification pipeline",
            TRIGGER_EVENTUAL,
            ("USER_INBOX", "AUDIT_LOG", "EXTERNAL_PROVIDER"),
            "Queue worker → provider APIs",
            "At-least-once delivery semantics",
            "notification_runtime",
            (POTENTIAL_DUPLICATE_TRIGGER, NO_RETRY_STRATEGY, SILENT_FAILURE_RISK),
            NON_IDEMPOTENT,
            PARTIAL_RECOVERY,
            PARTIAL_OBSERVABILITY,
            LOW_RELIABILITY,
            "LOW",
            "LOW",
            "HIGH",
            "LOW",
            "MATURE",
        ),
        _row(
            "SLA_ESCALATION",
            "SLA watchdog / escalation ladder",
            TRIGGER_PERIODIC,
            ("NOTIFICATION_DISPATCH", "CONTROL_CENTRE_ALERTS"),
            "Monitor job → escalation actions",
            "Periodic evaluation",
            "compliance_sla_monitor",
            (NO_RECONCILIATION_PATH, SILENT_FAILURE_RISK, PARTIAL_PROPAGATION_RISK),
            PARTIALLY_IDEMPOTENT,
            MANUAL_RECOVERY_HEAVY,
            LIMITED_OBSERVABILITY,
            LOW_RELIABILITY,
            "MODERATE",
            "MODERATE",
            "MODERATE",
            "LOW",
            "EVOLVING",
        ),
        _row(
            "REPORT_GENERATION",
            "PDF/CSV/report builders",
            TRIGGER_EVENTUAL,
            ("OBJECT_STORAGE", "CLIENT_DOWNLOAD"),
            "Report service → blob write",
            "On-demand + cache",
            "reporting_service",
            (STALE_READ_DEPENDENCY, PARTIAL_PROPAGATION_RISK),
            IDEMPOTENT,
            RECOVERY_READY,
            FULL_OBSERVABILITY,
            HIGH_RELIABILITY,
            "LOW",
            "LOW",
            "LOW",
            "HIGH",
            "MATURE",
        ),
        _row(
            "EXPORT_REFRESH",
            "Export artifact refresh / signed URLs",
            TRIGGER_EVENTUAL,
            ("CLIENT_DOWNLOAD", "AUDIT_LOG"),
            "Export job → storage",
            "Async regeneration",
            "reporting_service",
            (STALE_READ_DEPENDENCY, POTENTIAL_DUPLICATE_TRIGGER),
            PARTIALLY_IDEMPOTENT,
            PARTIAL_RECOVERY,
            PARTIAL_OBSERVABILITY,
            MODERATE_RELIABILITY,
            "MODERATE",
            "LOW",
            "MODERATE",
            "MODERATE",
            "MATURE",
        ),
        _row(
            "COMPLIANCE_GAP_SYNC",
            "Gap engine / registry sync",
            TRIGGER_PERIODIC,
            ("REQUIREMENT_CATALOG", "SCORING_INPUTS"),
            "Batch sync → requirement applicability",
            "Scheduled + manual admin",
            "compliance_gap_engine",
            (FRAGMENTED_TRIGGER_CHAIN, PARTIAL_PROPAGATION_RISK, NO_RECONCILIATION_PATH),
            UNKNOWN_IDEMPOTENCY,
            MANUAL_RECOVERY_HEAVY,
            LIMITED_OBSERVABILITY,
            UNVERIFIED_RELIABILITY,
            "HIGH",
            "MODERATE",
            "LOW",
            "UNVERIFIED",
            "EXPERIMENTAL",
        ),
        _row(
            "WORK_ORDER_TRANSITION",
            "Maintenance / work-order state machine",
            TRIGGER_DIRECT_SYNCHRONOUS,
            ("OPERATIONAL_ALERTS", "NOTIFICATION_DISPATCH"),
            "Transactional state change",
            "Synchronous domain transition",
            "operations_workflow_team",
            (ORPHAN_STATE_RISK, PARTIAL_PROPAGATION_RISK),
            PARTIALLY_IDEMPOTENT,
            PARTIAL_RECOVERY,
            PARTIAL_OBSERVABILITY,
            MODERATE_RELIABILITY,
            "MODERATE",
            "MODERATE",
            "LOW",
            "MODERATE",
            "EVOLVING",
        ),
        _row(
            "BOOKING_CONFIRMATION",
            "Booking pipeline confirmations",
            TRIGGER_DIRECT_SYNCHRONOUS,
            ("NOTIFICATION_DISPATCH", "CALENDAR_INTEGRATION"),
            "Booking service → notifications",
            "Synchronous confirm + async side-effects",
            "compliance_booking_service",
            (POTENTIAL_DUPLICATE_TRIGGER, SILENT_FAILURE_RISK),
            PARTIALLY_IDEMPOTENT,
            PARTIAL_RECOVERY,
            PARTIAL_OBSERVABILITY,
            MODERATE_RELIABILITY,
            "LOW",
            "LOW",
            "MODERATE",
            "MODERATE",
            "MATURE",
        ),
        _row(
            "VERIFICATION_CONFIRMATION",
            "Evidence verification completion",
            TRIGGER_EVENTUAL,
            ("SEMANTIC_STATE_TRANSITION", "REMINDER_TRIGGER", "COMPLIANCE_SCORE_RECALC"),
            "Verifier outcome → semantic projection",
            "Async propagation",
            "requirement_evidence_authority",
            (STALE_READ_DEPENDENCY, PARTIAL_PROPAGATION_RISK),
            PARTIALLY_IDEMPOTENT,
            RECOVERY_READY,
            PARTIAL_OBSERVABILITY,
            MODERATE_RELIABILITY,
            "MODERATE",
            "LOW",
            "MODERATE",
            "MODERATE",
            "MATURE",
        ),
        _row(
            "PORTFOLIO_SUMMARY_REFRESH",
            "Portfolio aggregates / summaries",
            TRIGGER_DERIVED_ON_READ,
            ("DASHBOARD_API", "REPORT_GENERATION"),
            "Read-time aggregation + cached rollups",
            "Derived on read + periodic warm",
            "portfolio_analytics_runtime",
            (STALE_READ_DEPENDENCY, UNKNOWN_DOWNSTREAM_STATE),
            UNKNOWN_IDEMPOTENCY,
            PARTIAL_RECOVERY,
            LIMITED_OBSERVABILITY,
            LOW_RELIABILITY,
            "HIGH",
            "LOW",
            "LOW",
            "LOW",
            "LEGACY_MIXED",
        ),
        _row(
            "CACHE_INVALIDATION",
            "CDN / app cache bust",
            TRIGGER_FRAGMENTED,
            ("UI_CLIENT_CACHE", "EDGE_CACHE"),
            "Multi-layer invalidation; inconsistent guarantees",
            "Best-effort broadcast",
            "platform_infra_team",
            (FRAGMENTED_TRIGGER_CHAIN, UNKNOWN_DOWNSTREAM_STATE, SILENT_FAILURE_RISK),
            NON_IDEMPOTENT,
            NO_KNOWN_RECOVERY,
            BLACK_BOX_BEHAVIOR,
            UNKNOWN_RELIABILITY,
            "HIGH",
            "HIGH",
            "HIGH",
            "UNVERIFIED",
            "LEGACY_MIXED",
        ),
        _row(
            "REGENERATION_RECALC",
            "Admin / risk regen / bulk rebuild jobs",
            TRIGGER_PERIODIC,
            ("COMPLIANCE_SCORE_RECALC", "TODAY_TASK_REBUILD", "RISK_SIGNALS"),
            "Job runner → fan-out recalcs",
            "Batch; long-running",
            "compliance_recalc_worker",
            (POTENTIAL_DUPLICATE_TRIGGER, NO_RETRY_STRATEGY, PARTIAL_PROPAGATION_RISK),
            PARTIALLY_IDEMPOTENT,
            RECOVERY_READY,
            PARTIAL_OBSERVABILITY,
            MODERATE_RELIABILITY,
            "MODERATE",
            "MODERATE",
            "HIGH",
            "MODERATE",
            "MATURE",
        ),
    )


def build_workflow_trigger_reliability_matrix() -> List[Dict[str, Any]]:
    """Return the Phase-1 reliability matrix (one row per catalogued workflow family)."""
    return [dict(r) for r in _catalog_rows()]


def _risk_score(row: Mapping[str, Any]) -> int:
    rel = row["reliability_class"]
    rel_w = {
        UNKNOWN_RELIABILITY: 5,
        UNVERIFIED_RELIABILITY: 4,
        LOW_RELIABILITY: 3,
        MODERATE_RELIABILITY: 2,
        HIGH_RELIABILITY: 0,
    }[rel]
    flags = row["propagation_failure_flags"]
    exp = {"NONE": 0, "LOW": 1, "MODERATE": 2, "HIGH": 3}
    stale = exp.get(row["stale_state_exposure"], 2)
    dup = exp.get(row["duplicate_trigger_exposure"], 2)
    return rel_w * 10 + len(flags) * 3 + stale + dup


def _derive_hotspots_and_candidates(matrix: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    by_family = {r["workflow_family"]: r for r in matrix}

    stale_hotspots = sorted(
        r["workflow_family"]
        for r in matrix
        if r["stale_state_exposure"] in ("HIGH", "MODERATE")
        or STALE_READ_DEPENDENCY in r["propagation_failure_flags"]
    )
    dup_hotspots = sorted(
        r["workflow_family"] for r in matrix if POTENTIAL_DUPLICATE_TRIGGER in r["propagation_failure_flags"]
    )
    weakest_recovery = sorted(
        (r["workflow_family"] for r in matrix),
        key=lambda f: (
            {
                NO_KNOWN_RECOVERY: 0,
                UNKNOWN_RECOVERY: 1,
                MANUAL_RECOVERY_HEAVY: 2,
                PARTIAL_RECOVERY: 3,
                RECOVERY_READY: 4,
            }[by_family[f]["recovery_posture"]],
            f,
        ),
    )
    weakest_obs = sorted(
        (r["workflow_family"] for r in matrix),
        key=lambda f: (
            {
                BLACK_BOX_BEHAVIOR: 0,
                LIMITED_OBSERVABILITY: 1,
                PARTIAL_OBSERVABILITY: 2,
                FULL_OBSERVABILITY: 3,
            }[by_family[f]["observability_posture"]],
            f,
        ),
    )

    ranked = sorted(matrix, key=lambda r: (-_risk_score(r), r["workflow_family"]))
    highest_risk = [r["workflow_family"] for r in ranked[:6]]
    strongest = sorted(r["workflow_family"] for r in matrix if r["reliability_class"] == HIGH_RELIABILITY)
    safest_activation = sorted(
        r["workflow_family"]
        for r in matrix
        if r["reliability_class"] in (HIGH_RELIABILITY, MODERATE_RELIABILITY)
        and r["runtime_activation_confidence"] in ("HIGH", "MODERATE")
        and POTENTIAL_DUPLICATE_TRIGGER not in r["propagation_failure_flags"]
        and r["duplicate_trigger_exposure"] in ("NONE", "LOW")
    )
    unsafe_activation = sorted(
        r["workflow_family"]
        for r in matrix
        if r["reliability_class"] in (LOW_RELIABILITY, UNKNOWN_RELIABILITY, UNVERIFIED_RELIABILITY)
        or r["runtime_activation_confidence"] == "LOW"
        or r["duplicate_trigger_exposure"] == "HIGH"
    )

    fragmentation = sorted(
        {
            f"FRAGMENTED_CHAIN::{r['workflow_family']}"
            for r in matrix
            if FRAGMENTED_TRIGGER_CHAIN in r["propagation_failure_flags"]
            or r["trigger_activation_type"] == TRIGGER_FRAGMENTED
        }
    )

    return {
        "highest_risk_workflow_families": highest_risk,
        "strongest_workflow_families": strongest,
        "stale_state_hotspots": stale_hotspots,
        "duplicate_trigger_hotspots": dup_hotspots,
        "weakest_recovery_paths": weakest_recovery[:8],
        "weakest_observability_paths": weakest_obs[:8],
        "orchestration_fragmentation_findings": fragmentation,
        "safest_activation_candidates": safest_activation,
        "unsafe_activation_candidates": unsafe_activation,
    }


def build_workflow_trigger_reliability_phase1_snapshot(
    *,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build the full Phase-1 audit snapshot (JSON-serializable).

    ``generated_at`` is injectable for deterministic tests (ISO-8601 string).
    """
    matrix = build_workflow_trigger_reliability_matrix()
    derived = _derive_hotspots_and_candidates(matrix)
    ts = generated_at or datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": "workflow_trigger_reliability_phase1_v1",
        "generated_at": ts,
        "workflow_reliability_matrix": matrix,
        **derived,
        "remaining_limitations": [
            "Catalog is curated static assessment; live code paths are not instrumented by this module.",
            "Cross-tenant and deployment-specific queue topology is not modeled.",
            "Failure flags are orthogonal; co-occurrence does not imply observed incident rates.",
        ],
        "runtime_behavior_changed": False,
        "audit_only": True,
        "non_blocking": True,
    }


def write_workflow_trigger_reliability_phase1_json(
    output_path: Optional[Path] = None,
    *,
    generated_at: Optional[str] = None,
) -> Path:
    """Write snapshot JSON next to other backend audit artifacts."""
    root = Path(__file__).resolve().parents[1]
    dest = output_path or (root / "docs" / "audit" / "WORKFLOW_TRIGGER_RELIABILITY_PHASE1.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    snap = build_workflow_trigger_reliability_phase1_snapshot(generated_at=generated_at)
    dest.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return dest


def stable_snapshot_for_tests() -> Dict[str, Any]:
    """Deterministic snapshot (fixed timestamp) for unit tests."""
    return build_workflow_trigger_reliability_phase1_snapshot(generated_at="1970-01-01T00:00:00+00:00")


# --- Phase 2: evidence-based static call-path audit (implementation in sibling module) ---
from services.workflow_trigger_reliability_audit_phase2 import (  # noqa: E402
    PHASE2_HIGH_PRIORITY_FAMILIES,
    PHASE2_OPTIONAL_FAMILIES,
    build_workflow_trigger_reliability_evidence_matrix_phase2,
    build_workflow_trigger_reliability_phase2_snapshot,
    stable_phase2_snapshot_for_tests,
    write_workflow_trigger_reliability_phase2_json,
)

# --- Phase 3: stabilization planning (consumes Phase 2; planning-only) ---
from services.workflow_trigger_stabilization_planning import (  # noqa: E402
    REFERENCE_STABILIZATION_PATTERNS,
    build_workflow_trigger_stabilization_matrix_phase3,
    build_workflow_trigger_stabilization_phase3_snapshot,
    stable_phase3_snapshot_for_tests,
    write_workflow_trigger_stabilization_phase3_json,
)
