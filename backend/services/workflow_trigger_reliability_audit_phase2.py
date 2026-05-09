"""
Workflow Trigger Reliability Audit — Phase 2 (evidence-based static call-path inventory).

Read-only: frozen observations from repository inspection (files/symbols/patterns).
Does not execute workflows, mutate runtime state, or add enforcement.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

# --- Call-path model ---
CALL_PATH_SYNCHRONOUS = "CALL_PATH_SYNCHRONOUS"
CALL_PATH_ASYNC = "CALL_PATH_ASYNC"
CALL_PATH_PERIODIC = "CALL_PATH_PERIODIC"
CALL_PATH_READ_DERIVED = "CALL_PATH_READ_DERIVED"
CALL_PATH_MIXED = "CALL_PATH_MIXED"
CALL_PATH_UNKNOWN = "CALL_PATH_UNKNOWN"

# --- Orchestration maturity ---
ORCHESTRATION_DETERMINISTIC = "ORCHESTRATION_DETERMINISTIC"
ORCHESTRATION_PARTIAL = "ORCHESTRATION_PARTIAL"
ORCHESTRATION_FRAGMENTED = "ORCHESTRATION_FRAGMENTED"
ORCHESTRATION_READ_REBUILD_HEAVY = "ORCHESTRATION_READ_REBUILD_HEAVY"
ORCHESTRATION_UNKNOWN = "ORCHESTRATION_UNKNOWN"

# --- Retry evidence ---
RETRY_PRESENT = "RETRY_PRESENT"
RETRY_PARTIAL = "RETRY_PARTIAL"
RETRY_UNKNOWN = "RETRY_UNKNOWN"
NO_RETRY_EVIDENCE = "NO_RETRY_EVIDENCE"

# --- Reconciliation evidence ---
RECONCILIATION_PRESENT = "RECONCILIATION_PRESENT"
RECONCILIATION_PARTIAL = "RECONCILIATION_PARTIAL"
NO_RECONCILIATION_EVIDENCE = "NO_RECONCILIATION_EVIDENCE"

# --- Idempotency evidence ---
STRONG_IDEMPOTENCY_EVIDENCE = "STRONG_IDEMPOTENCY_EVIDENCE"
PARTIAL_IDEMPOTENCY_EVIDENCE = "PARTIAL_IDEMPOTENCY_EVIDENCE"
WEAK_IDEMPOTENCY_EVIDENCE = "WEAK_IDEMPOTENCY_EVIDENCE"
NO_IDEMPOTENCY_EVIDENCE = "NO_IDEMPOTENCY_EVIDENCE"

# --- Silent failure risk ---
LOW_SILENT_FAILURE_RISK = "LOW_SILENT_FAILURE_RISK"
MODERATE_SILENT_FAILURE_RISK = "MODERATE_SILENT_FAILURE_RISK"
HIGH_SILENT_FAILURE_RISK = "HIGH_SILENT_FAILURE_RISK"
CRITICAL_SILENT_FAILURE_RISK = "CRITICAL_SILENT_FAILURE_RISK"

# --- Stale-state dependency ---
LOW_STALE_STATE_DEPENDENCY = "LOW_STALE_STATE_DEPENDENCY"
MODERATE_STALE_STATE_DEPENDENCY = "MODERATE_STALE_STATE_DEPENDENCY"
HIGH_STALE_STATE_DEPENDENCY = "HIGH_STALE_STATE_DEPENDENCY"
CRITICAL_STALE_STATE_DEPENDENCY = "CRITICAL_STALE_STATE_DEPENDENCY"

PHASE2_HIGH_PRIORITY_FAMILIES: Tuple[str, ...] = (
    "CACHE_INVALIDATION",
    "REQUIREMENT_STATE_TRANSITION",
    "COMPLIANCE_GAP_SYNC",
    "COMMAND_CENTER_REFRESH",
    "NOTIFICATION_DISPATCH",
    "COMPLIANCE_SCORE_RECALC",
    "TODAY_TASK_REBUILD",
    "REGENERATION_RECALC",
)

PHASE2_OPTIONAL_FAMILIES: Tuple[str, ...] = ("PORTFOLIO_SUMMARY_REFRESH", "REMINDER_TRIGGER")


def _cp(
    file: str,
    symbol: str,
    trigger_direction: str,
    call_path_classification: str,
    sync_async_nature: str,
    explicit_retries: bool,
    explicit_idempotency_protections: bool,
    audit_logging_present: bool,
    swallowed_exception_pattern: bool,
    read_derived_dependency: bool,
    periodic_job_dependency: bool,
) -> Dict[str, Any]:
    return {
        "file": file,
        "function": symbol,
        "trigger_direction": trigger_direction,
        "call_path_classification": call_path_classification,
        "sync_async_nature": sync_async_nature,
        "explicit_retries_observed": explicit_retries,
        "explicit_idempotency_protections_observed": explicit_idempotency_protections,
        "audit_logging_observed": audit_logging_present,
        "swallowed_exception_pattern_observed": swallowed_exception_pattern,
        "read_derived_dependency": read_derived_dependency,
        "periodic_job_dependency": periodic_job_dependency,
    }


def _evidence_matrix() -> Tuple[Dict[str, Any], ...]:
    """Static inventory keyed to repository paths (Phase 2 v1)."""
    return (
        {
            "workflow_family": "CACHE_INVALIDATION",
            "audit_priority": "high",
            "runtime_call_paths": (
                _cp(
                    "routes/calendar.py",
                    "response headers Cache-Control",
                    "http_response",
                    CALL_PATH_SYNCHRONOUS,
                    "header_only",
                    False,
                    False,
                    False,
                    False,
                    False,
                    False,
                ),
                _cp(
                    "routes/cms.py",
                    "public Cache-Control max-age",
                    "http_response",
                    CALL_PATH_SYNCHRONOUS,
                    "header_only",
                    False,
                    False,
                    False,
                    False,
                    False,
                    False,
                ),
                _cp(
                    "services/work_order_contractor_routing_service.py",
                    "invalidate_pending_routing_for_work_order",
                    "domain_write",
                    CALL_PATH_ASYNC,
                    "async_mongo_updates",
                    False,
                    False,
                    True,
                    True,
                    False,
                    False,
                ),
            ),
            "trigger_entry_points": [
                "HTTP response headers (multiple routes)",
                "services/work_order_contractor_routing_service.py",
            ],
            "downstream_propagation_chain_summary": "No unified cache coordinator; CDN/browser + ad-hoc Mongo invalidations.",
            "orchestration_maturity": ORCHESTRATION_FRAGMENTED,
            "retry_evidence_class": NO_RETRY_EVIDENCE,
            "reconciliation_evidence_class": NO_RECONCILIATION_EVIDENCE,
            "idempotency_evidence_class": NO_IDEMPOTENCY_EVIDENCE,
            "silent_failure_risk_class": HIGH_SILENT_FAILURE_RISK,
            "stale_state_dependency_class": CRITICAL_STALE_STATE_DEPENDENCY,
            "operational_confidence": "LOW",
            "strongest_evidence_found": ["Explicit invalidate_pending_routing_for_work_order with audit attempt"],
            "weakest_evidence_found": ["No central invalidation registry across API surfaces"],
            "known_ambiguity_areas": ["Browser/CDN vs API Cache-Control policy ownership split"],
        },
        {
            "workflow_family": "REQUIREMENT_STATE_TRANSITION",
            "audit_priority": "high",
            "runtime_call_paths": (
                _cp(
                    "routes/client.py",
                    "requirements.update_one / insert_one (mark not applicable path)",
                    "client_write",
                    CALL_PATH_MIXED,
                    "sync_db_then_async_enqueue",
                    False,
                    True,
                    True,
                    False,
                    False,
                    False,
                ),
                _cp(
                    "routes/client_compliance_evidence.py",
                    "enqueue_compliance_recalc",
                    "client_evidence_write",
                    CALL_PATH_ASYNC,
                    "async_enqueue",
                    False,
                    True,
                    True,
                    False,
                    False,
                    False,
                ),
                _cp(
                    "services/requirement_evidence_authority.py",
                    "sync_compliance_gaps_for_requirement (imported)",
                    "semantic_followthrough",
                    CALL_PATH_ASYNC,
                    "async_service_call",
                    False,
                    False,
                    True,
                    True,
                    False,
                    False,
                ),
            ),
            "trigger_entry_points": [
                "routes/client.py",
                "routes/client_compliance_evidence.py",
                "services/requirement_evidence_authority.py",
            ],
            "downstream_propagation_chain_summary": "Requirement row mutation → recalc enqueue → gap sync / score worker (multiple writers).",
            "orchestration_maturity": ORCHESTRATION_FRAGMENTED,
            "retry_evidence_class": RETRY_PARTIAL,
            "reconciliation_evidence_class": RECONCILIATION_PARTIAL,
            "idempotency_evidence_class": PARTIAL_IDEMPOTENCY_EVIDENCE,
            "silent_failure_risk_class": MODERATE_SILENT_FAILURE_RISK,
            "stale_state_dependency_class": MODERATE_STALE_STATE_DEPENDENCY,
            "operational_confidence": "MODERATE",
            "strongest_evidence_found": ["enqueue correlation dedupe on compliance_recalc_queue"],
            "weakest_evidence_found": ["Multiple entrypoints to requirement row without single saga coordinator"],
            "known_ambiguity_areas": ["Ordering between gap sync and score read in UI"],
        },
        {
            "workflow_family": "COMPLIANCE_GAP_SYNC",
            "audit_priority": "high",
            "runtime_call_paths": (
                _cp(
                    "services/compliance_gap_sync.py",
                    "sync_compliance_gaps_for_requirement",
                    "truth_change",
                    CALL_PATH_ASYNC,
                    "async_persist",
                    False,
                    False,
                    True,
                    False,
                    False,
                    False,
                ),
                _cp(
                    "services/compliance_gap_sync.py",
                    "aggregate_gap_counts_for_client",
                    "read_aggregate",
                    CALL_PATH_READ_DERIVED,
                    "async_read",
                    False,
                    False,
                    False,
                    True,
                    True,
                    False,
                ),
                _cp(
                    "routes/properties.py",
                    "_sync_compliance_gaps_for_property_requirements_after_materialization",
                    "property_materialization",
                    CALL_PATH_MIXED,
                    "async_batch",
                    False,
                    False,
                    True,
                    False,
                    False,
                    False,
                ),
            ),
            "trigger_entry_points": [
                "services/compliance_gap_sync.py",
                "services/requirement_evidence_authority.py",
                "routes/properties.py",
            ],
            "downstream_propagation_chain_summary": "Infer gaps → upsert compliance_gaps → optional operational bridge → aggregates read by Command Centre / portfolio.",
            "orchestration_maturity": ORCHESTRATION_PARTIAL,
            "retry_evidence_class": NO_RETRY_EVIDENCE,
            "reconciliation_evidence_class": RECONCILIATION_PARTIAL,
            "idempotency_evidence_class": PARTIAL_IDEMPOTENCY_EVIDENCE,
            "silent_failure_risk_class": MODERATE_SILENT_FAILURE_RISK,
            "stale_state_dependency_class": MODERATE_STALE_STATE_DEPENDENCY,
            "operational_confidence": "MODERATE",
            "strongest_evidence_found": ["Explicit errors[] return contract on sync_compliance_gaps_for_requirement"],
            "weakest_evidence_found": ["No observed queue replay for gap upsert batch"],
            "known_ambiguity_areas": ["Runtime visibility gating resolves gaps without full propagation audit"],
        },
        {
            "workflow_family": "COMMAND_CENTER_REFRESH",
            "audit_priority": "high",
            "runtime_call_paths": (
                _cp(
                    "services/command_center_service.py",
                    "get_command_center_bundle",
                    "client_read",
                    CALL_PATH_READ_DERIVED,
                    "async_compose",
                    False,
                    False,
                    True,
                    True,
                    True,
                    False,
                ),
                _cp(
                    "services/command_center_service.py",
                    "get_unified_tasks_digest / get_unified_tasks_for_client",
                    "delegated_read",
                    CALL_PATH_READ_DERIVED,
                    "async_subcalls",
                    False,
                    False,
                    True,
                    True,
                    True,
                    False,
                ),
                _cp(
                    "services/command_center_service.py",
                    "calculate_compliance_score + aggregate_gap_counts_for_client",
                    "nested_read",
                    CALL_PATH_READ_DERIVED,
                    "async_nested",
                    False,
                    False,
                    True,
                    True,
                    True,
                    False,
                ),
            ),
            "trigger_entry_points": ["services/command_center_service.py"],
            "downstream_propagation_chain_summary": "Per-section try/except with degraded empty payloads; no single failure boundary.",
            "orchestration_maturity": ORCHESTRATION_READ_REBUILD_HEAVY,
            "retry_evidence_class": NO_RETRY_EVIDENCE,
            "reconciliation_evidence_class": NO_RECONCILIATION_EVIDENCE,
            "idempotency_evidence_class": WEAK_IDEMPOTENCY_EVIDENCE,
            "silent_failure_risk_class": HIGH_SILENT_FAILURE_RISK,
            "stale_state_dependency_class": HIGH_STALE_STATE_DEPENDENCY,
            "operational_confidence": "LOW",
            "strongest_evidence_found": ["Structured logging on each swallowed subsystem failure"],
            "weakest_evidence_found": ["Partial UI success with empty sections after failures"],
            "known_ambiguity_areas": ["Read-model composition: idempotency is operational best-effort only at bundle level"],
        },
    )


def _matrix_full() -> List[Dict[str, Any]]:
    rows = list(_evidence_matrix())
    rows.extend(
        [
            {
                "workflow_family": "NOTIFICATION_DISPATCH",
                "audit_priority": "high",
                "runtime_call_paths": (
                    _cp(
                        "services/notification_orchestrator.py",
                        "NotificationOrchestrator.send (+ idempotency_key path)",
                        "outbound_send",
                        CALL_PATH_MIXED,
                        "async_with_retry_queue",
                        True,
                        True,
                        True,
                        False,
                        False,
                        False,
                    ),
                    _cp(
                        "job_runner.py",
                        "notification retry queue processor",
                        "deferred_retry",
                        CALL_PATH_PERIODIC,
                        "async_worker_poll",
                        True,
                        True,
                        True,
                        False,
                        False,
                        True,
                    ),
                ),
                "trigger_entry_points": ["services/notification_orchestrator.py", "job_runner.py"],
                "downstream_propagation_chain_summary": "message_logs + Postmark/Twilio + retry backoff tables.",
                "orchestration_maturity": ORCHESTRATION_PARTIAL,
                "retry_evidence_class": RETRY_PRESENT,
                "reconciliation_evidence_class": RECONCILIATION_PARTIAL,
                "idempotency_evidence_class": STRONG_IDEMPOTENCY_EVIDENCE,
                "silent_failure_risk_class": MODERATE_SILENT_FAILURE_RISK,
                "stale_state_dependency_class": LOW_STALE_STATE_DEPENDENCY,
                "operational_confidence": "MODERATE",
                "strongest_evidence_found": ["Sparse unique idempotency_key on message_logs", "duplicate_ignored outcome"],
                "weakest_evidence_found": ["Branching email vs SMS retry semantics differ"],
                "known_ambiguity_areas": ["Inline Postmark retry vs deferred queue overlap risk (documented in module header)"],
            },
            {
                "workflow_family": "COMPLIANCE_SCORE_RECALC",
                "audit_priority": "high",
                "runtime_call_paths": (
                    _cp(
                        "services/compliance_recalc_queue.py",
                        "enqueue_compliance_recalc",
                        "ingress_enqueue",
                        CALL_PATH_ASYNC,
                        "async_mongo_insert",
                        False,
                        True,
                        True,
                        False,
                        False,
                        False,
                    ),
                    _cp(
                        "job_runner.py",
                        "run_compliance_recalc_worker",
                        "worker_claim",
                        CALL_PATH_ASYNC,
                        "async_worker_batch",
                        True,
                        True,
                        True,
                        True,
                        False,
                        True,
                    ),
                    _cp(
                        "services/compliance_score.py",
                        "calculate_compliance_score",
                        "read_aggregate",
                        CALL_PATH_READ_DERIVED,
                        "async_read_persisted",
                        False,
                        False,
                        False,
                        False,
                        True,
                        False,
                    ),
                ),
                "trigger_entry_points": [
                    "services/compliance_recalc_queue.py",
                    "job_runner.py",
                    "services/compliance_score.py",
                    "routes/client.py",
                    "routes/client_compliance_evidence.py",
                ],
                "downstream_propagation_chain_summary": "Queue doc → recalculate_and_persist → score_events (warn-only) → automation_status (debug-only on failure).",
                "orchestration_maturity": ORCHESTRATION_PARTIAL,
                "retry_evidence_class": RETRY_PRESENT,
                "reconciliation_evidence_class": RECONCILIATION_PRESENT,
                "idempotency_evidence_class": STRONG_IDEMPOTENCY_EVIDENCE,
                "silent_failure_risk_class": MODERATE_SILENT_FAILURE_RISK,
                "stale_state_dependency_class": MODERATE_STALE_STATE_DEPENDENCY,
                "operational_confidence": "MODERATE",
                "strongest_evidence_found": ["Mongo duplicate key treated as enqueue no-op", "Worker backoff to DEAD with audit"],
                "weakest_evidence_found": ["risk_signal_regen enqueue failure swallowed in enqueue finally"],
                "known_ambiguity_areas": ["Lazy backfill path vs queue saturation under burst uploads"],
            },
            {
                "workflow_family": "TODAY_TASK_REBUILD",
                "audit_priority": "high",
                "runtime_call_paths": (
                    _cp(
                        "services/unified_tasks_service.py",
                        "get_unified_tasks_for_client",
                        "client_read",
                        CALL_PATH_READ_DERIVED,
                        "async_compose",
                        False,
                        False,
                        False,
                        True,
                        True,
                        False,
                    ),
                    _cp(
                        "services/unified_tasks_service.py",
                        "get_unified_tasks_digest",
                        "client_read_digest",
                        CALL_PATH_READ_DERIVED,
                        "async_compose",
                        False,
                        False,
                        False,
                        True,
                        True,
                        False,
                    ),
                ),
                "trigger_entry_points": ["services/unified_tasks_service.py", "services/command_center_service.py"],
                "downstream_propagation_chain_summary": "Composes priority actions + tenant tasks + freshness blocks; rebuild implicit on each read.",
                "orchestration_maturity": ORCHESTRATION_READ_REBUILD_HEAVY,
                "retry_evidence_class": NO_RETRY_EVIDENCE,
                "reconciliation_evidence_class": NO_RECONCILIATION_EVIDENCE,
                "idempotency_evidence_class": NO_IDEMPOTENCY_EVIDENCE,
                "silent_failure_risk_class": MODERATE_SILENT_FAILURE_RISK,
                "stale_state_dependency_class": HIGH_STALE_STATE_DEPENDENCY,
                "operational_confidence": "LOW",
                "strongest_evidence_found": ["Centralized composition for Today / Command Centre urgent lists"],
                "weakest_evidence_found": ["No durable rebuild cursor; depends on upstream requirement truth freshness"],
                "known_ambiguity_areas": ["Partial failure surfaces as shorter task lists without explicit stale banner"],
            },
            {
                "workflow_family": "REGENERATION_RECALC",
                "audit_priority": "high",
                "runtime_call_paths": (
                    _cp(
                        "services/jobs.py",
                        "enqueue_compliance_recalc (TRIGGER_EXPIRY_JOB etc.)",
                        "scheduled_job",
                        CALL_PATH_ASYNC,
                        "async_enqueue_from_job",
                        False,
                        True,
                        True,
                        False,
                        False,
                        True,
                    ),
                    _cp(
                        "job_runner.py",
                        "run_expiry_rollover_recalc (+ worker)",
                        "periodic_enqueue",
                        CALL_PATH_PERIODIC,
                        "async_batch",
                        False,
                        True,
                        True,
                        False,
                        False,
                        True,
                    ),
                ),
                "trigger_entry_points": ["services/jobs.py", "job_runner.py"],
                "downstream_propagation_chain_summary": "Scheduled triggers enqueue property-scoped recalcs; worker same as COMPLIANCE_SCORE_RECALC.",
                "orchestration_maturity": ORCHESTRATION_PARTIAL,
                "retry_evidence_class": RETRY_PRESENT,
                "reconciliation_evidence_class": RECONCILIATION_PRESENT,
                "idempotency_evidence_class": STRONG_IDEMPOTENCY_EVIDENCE,
                "silent_failure_risk_class": LOW_SILENT_FAILURE_RISK,
                "stale_state_dependency_class": MODERATE_STALE_STATE_DEPENDENCY,
                "operational_confidence": "MODERATE",
                "strongest_evidence_found": ["Shared queue/worker path with explicit DEAD state"],
                "weakest_evidence_found": ["Batch enqueue patterns depend on correlation discipline per job type"],
                "known_ambiguity_areas": ["Overlap between manual admin regen and scheduled sweeps"],
            },
            {
                "workflow_family": "PORTFOLIO_SUMMARY_REFRESH",
                "audit_priority": "optional",
                "runtime_call_paths": (
                    _cp(
                        "routes/portfolio.py",
                        "aggregate_gap_counts_for_client",
                        "client_read",
                        CALL_PATH_READ_DERIVED,
                        "async_read",
                        False,
                        False,
                        False,
                        True,
                        True,
                        False,
                    ),
                    _cp(
                        "services/compliance_score.py",
                        "calculate_compliance_score",
                        "read_aggregate",
                        CALL_PATH_READ_DERIVED,
                        "async_read",
                        False,
                        False,
                        False,
                        False,
                        True,
                        False,
                    ),
                ),
                "trigger_entry_points": ["routes/portfolio.py", "services/compliance_score.py"],
                "downstream_propagation_chain_summary": "Read-time aggregation of persisted scores and gap counts.",
                "orchestration_maturity": ORCHESTRATION_READ_REBUILD_HEAVY,
                "retry_evidence_class": NO_RETRY_EVIDENCE,
                "reconciliation_evidence_class": NO_RECONCILIATION_EVIDENCE,
                "idempotency_evidence_class": NO_IDEMPOTENCY_EVIDENCE,
                "silent_failure_risk_class": LOW_SILENT_FAILURE_RISK,
                "stale_state_dependency_class": HIGH_STALE_STATE_DEPENDENCY,
                "operational_confidence": "LOW",
                "strongest_evidence_found": ["Reuses same aggregate primitives as Command Centre"],
                "weakest_evidence_found": ["No portfolio-specific invalidation hook distinct from property writes"],
                "known_ambiguity_areas": ["Portfolio KPI freshness tied to underlying property recalc latency"],
            },
            {
                "workflow_family": "REMINDER_TRIGGER",
                "audit_priority": "optional",
                "runtime_call_paths": (
                    _cp(
                        "services/reminder_truth_service.py",
                        "gap engine context helper (infer_compliance_gaps_for_requirement)",
                        "read_derived",
                        CALL_PATH_READ_DERIVED,
                        "sync_infer_with_swallowed_engine_failure",
                        False,
                        False,
                        False,
                        True,
                        True,
                        False,
                    ),
                ),
                "trigger_entry_points": ["services/reminder_truth_service.py", "services/compliance_sla_monitor.py"],
                "downstream_propagation_chain_summary": "Periodic / evaluation-driven reminder selection with governed gap context.",
                "orchestration_maturity": ORCHESTRATION_PARTIAL,
                "retry_evidence_class": RETRY_UNKNOWN,
                "reconciliation_evidence_class": RECONCILIATION_PARTIAL,
                "idempotency_evidence_class": PARTIAL_IDEMPOTENCY_EVIDENCE,
                "silent_failure_risk_class": MODERATE_SILENT_FAILURE_RISK,
                "stale_state_dependency_class": MODERATE_STALE_STATE_DEPENDENCY,
                "operational_confidence": "MODERATE",
                "strongest_evidence_found": ["Explicit REMINDER_ENGINE / observe_consumer_precedence_delta integration"],
                "weakest_evidence_found": ["Broad except Exception → empty gap context on engine failure"],
                "known_ambiguity_areas": ["Cooldown state vs requirement truth race"],
            },
        ]
    )
    # Normalize tuples to lists for JSON
    for r in rows:
        r["runtime_call_paths"] = [dict(p) for p in r["runtime_call_paths"]]
    return rows


def build_workflow_trigger_reliability_evidence_matrix_phase2() -> List[Dict[str, Any]]:
    m = _matrix_full()
    assert {r["workflow_family"] for r in m} == set(PHASE2_HIGH_PRIORITY_FAMILIES) | set(PHASE2_OPTIONAL_FAMILIES)
    return [dict(r) for r in m]


def _derive_phase2_rollups(matrix: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    strongest_orch = sorted(
        r["workflow_family"] for r in matrix if r["orchestration_maturity"] == ORCHESTRATION_DETERMINISTIC
    )
    weakest_orch = sorted(
        r["workflow_family"] for r in matrix if r["orchestration_maturity"] in (ORCHESTRATION_FRAGMENTED, ORCHESTRATION_UNKNOWN)
    )
    strongest_idem = sorted(
        r["workflow_family"] for r in matrix if r["idempotency_evidence_class"] == STRONG_IDEMPOTENCY_EVIDENCE
    )
    weakest_idem = sorted(
        r["workflow_family"] for r in matrix if r["idempotency_evidence_class"] == NO_IDEMPOTENCY_EVIDENCE
    )
    stale_hotspots = sorted(
        r["workflow_family"]
        for r in matrix
        if r["stale_state_dependency_class"]
        in (HIGH_STALE_STATE_DEPENDENCY, CRITICAL_STALE_STATE_DEPENDENCY, MODERATE_STALE_STATE_DEPENDENCY)
    )
    silent_hotspots = sorted(
        r["workflow_family"]
        for r in matrix
        if r["silent_failure_risk_class"]
        in (HIGH_SILENT_FAILURE_RISK, CRITICAL_SILENT_FAILURE_RISK, MODERATE_SILENT_FAILURE_RISK)
    )
    retry_gaps = sorted(
        r["workflow_family"] for r in matrix if r["retry_evidence_class"] in (NO_RETRY_EVIDENCE, RETRY_UNKNOWN)
    )
    recon_gaps = sorted(
        r["workflow_family"] for r in matrix if r["reconciliation_evidence_class"] == NO_RECONCILIATION_EVIDENCE
    )
    cache_ambiguity = [
        "CACHE_INVALIDATION: HTTP Cache-Control varies by route (calendar/cms/leads/admin_orders) without shared policy module.",
        "CACHE_INVALIDATION: Contractor routing invalidation is domain-local; not unified with portal asset cache.",
    ]
    safest = sorted(
        r["workflow_family"]
        for r in matrix
        if r["idempotency_evidence_class"] == STRONG_IDEMPOTENCY_EVIDENCE
        and r["retry_evidence_class"] == RETRY_PRESENT
        and r["silent_failure_risk_class"] == LOW_SILENT_FAILURE_RISK
    )
    unsafe = sorted(
        r["workflow_family"]
        for r in matrix
        if r["orchestration_maturity"] in (ORCHESTRATION_FRAGMENTED, ORCHESTRATION_UNKNOWN, ORCHESTRATION_READ_REBUILD_HEAVY)
        and r["operational_confidence"] == "LOW"
    )
    return {
        "strongest_orchestration_paths": strongest_orch,
        "weakest_orchestration_paths": weakest_orch,
        "strongest_idempotency_evidence": strongest_idem,
        "weakest_idempotency_evidence": weakest_idem,
        "stale_state_hotspots": stale_hotspots,
        "silent_failure_hotspots": silent_hotspots,
        "retry_reconciliation_gaps": {
            "retry_weak_or_unknown": retry_gaps,
            "reconciliation_missing": recon_gaps,
        },
        "cache_ownership_ambiguity_findings": cache_ambiguity,
        "safest_stabilization_candidates": safest,
        "unsafe_stabilization_candidates": unsafe,
    }


def build_workflow_trigger_reliability_phase2_snapshot(
    *,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    matrix = build_workflow_trigger_reliability_evidence_matrix_phase2()
    roll = _derive_phase2_rollups(matrix)
    ts = generated_at or datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": "workflow_trigger_reliability_phase2_v1",
        "generated_at": ts,
        "phase2_scope": {
            "high_priority_families": list(PHASE2_HIGH_PRIORITY_FAMILIES),
            "optional_families": list(PHASE2_OPTIONAL_FAMILIES),
        },
        "evidence_based_reliability_matrix": matrix,
        **roll,
        "remaining_limitations": [
            "Evidence is static repository inspection only; no live traces or metrics.",
            "Call-path inventory is non-exhaustive (representative entrypoints per family).",
            "Classifications are conservative where code evidence is ambiguous.",
        ],
        "runtime_behavior_changed": False,
        "audit_only": True,
        "non_blocking": True,
    }


def write_workflow_trigger_reliability_phase2_json(
    output_path: Optional[Path] = None,
    *,
    generated_at: Optional[str] = None,
) -> Path:
    root = Path(__file__).resolve().parents[1]
    dest = output_path or (root / "docs" / "audit" / "WORKFLOW_TRIGGER_RELIABILITY_PHASE2.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    snap = build_workflow_trigger_reliability_phase2_snapshot(generated_at=generated_at)
    dest.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return dest


def stable_phase2_snapshot_for_tests() -> Dict[str, Any]:
    return build_workflow_trigger_reliability_phase2_snapshot(generated_at="1970-01-01T00:00:00+00:00")
