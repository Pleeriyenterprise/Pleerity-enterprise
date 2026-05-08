from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Propagation type classifications
DIRECT_SYNCHRONOUS = "DIRECT_SYNCHRONOUS"
DERIVED_ON_READ = "DERIVED_ON_READ"
EVENTUAL_RECALC = "EVENTUAL_RECALC"
PARTIAL_PROPAGATION = "PARTIAL_PROPAGATION"
FRAGMENTED_PROPAGATION = "FRAGMENTED_PROPAGATION"
NO_KNOWN_PROPAGATION = "NO_KNOWN_PROPAGATION"

# Confidence classifications
HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
MEDIUM_CONFIDENCE = "MEDIUM_CONFIDENCE"
LOW_CONFIDENCE = "LOW_CONFIDENCE"
UNKNOWN_CONFIDENCE = "UNKNOWN_CONFIDENCE"

# Reaction source-of-truth classifications
AUTHORITY_WRITE = "AUTHORITY_WRITE"
LIVE_READ_PROJECTION = "LIVE_READ_PROJECTION"
SCHEDULED_RECALC = "SCHEDULED_RECALC"
TASK_REBUILD = "TASK_REBUILD"
SCORE_REGENERATION = "SCORE_REGENERATION"
UI_DERIVATION = "UI_DERIVATION"
PERIODIC_JOB = "PERIODIC_JOB"
MANUAL_REFRESH = "MANUAL_REFRESH"
UNKNOWN = "UNKNOWN"

# Freshness expectation classes (expected contracts)
IMMEDIATE = "IMMEDIATE"
NEAR_REAL_TIME = "NEAR_REAL_TIME"
EVENTUAL = "EVENTUAL"
PERIODIC = "PERIODIC"
BEST_EFFORT = "BEST_EFFORT"
UNKNOWN_FRESHNESS = "UNKNOWN"

# Propagation criticality classes
SAFETY_CRITICAL = "SAFETY_CRITICAL"
COMPLIANCE_CRITICAL = "COMPLIANCE_CRITICAL"
OPERATIONAL_CRITICAL = "OPERATIONAL_CRITICAL"
UX_CRITICAL = "UX_CRITICAL"
ANALYTICS_ONLY = "ANALYTICS_ONLY"

# Refresh guarantee classes (current behavior quality)
DETERMINISTIC = "DETERMINISTIC"
LIKELY = "LIKELY"
INCIDENTAL = "INCIDENTAL"
FRAGMENTED = "FRAGMENTED"
UNKNOWN_GUARANTEE = "UNKNOWN"

# Expected-vs-current gap classes
CONTRACT_SATISFIED = "CONTRACT_SATISFIED"
PARTIALLY_SATISFIED = "PARTIALLY_SATISFIED"
UNDER_PROPAGATED = "UNDER_PROPAGATED"
FRAGMENTED_BEHAVIOR = "FRAGMENTED_BEHAVIOR"
ROLLUP_STALE_RISK = "ROLLUP_STALE_RISK"
OPERATIONAL_GAP = "OPERATIONAL_GAP"
BLOCKED_FOR_RUNTIME_ENFORCEMENT = "BLOCKED_FOR_RUNTIME_ENFORCEMENT"

# Deterministic blocker reason enums
UNKNOWN_REFRESH_GUARANTEE = "UNKNOWN_REFRESH_GUARANTEE"
PERIODIC_ONLY_REFRESH = "PERIODIC_ONLY_REFRESH"
NO_DIRECT_PROPAGATION = "NO_DIRECT_PROPAGATION"
FRAGMENTED_MULTI_SOURCE_REFRESH = "FRAGMENTED_MULTI_SOURCE_REFRESH"
CACHE_INVALIDATION_UNKNOWN = "CACHE_INVALIDATION_UNKNOWN"
NO_OPERATIONAL_FOLLOWTHROUGH = "NO_OPERATIONAL_FOLLOWTHROUGH"
LOW_CONFIDENCE_PATH = "LOW_CONFIDENCE_PATH"
DERIVED_ONLY_NO_PUSH_SIGNAL = "DERIVED_ONLY_NO_PUSH_SIGNAL"
SEMANTIC_COLLAPSE_RISK = "SEMANTIC_COLLAPSE_RISK"

# Phase 3 — consumer rollout gate states (audit-only)
READY = "READY"
CONDITIONAL = "CONDITIONAL"
BLOCKED = "BLOCKED"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
OBSERVE_ONLY = "OBSERVE_ONLY"
NOT_ELIGIBLE = "NOT_ELIGIBLE"

# Phase 3 — waiver policy metadata (audit-only; does not change behavior)
WAIVER_NOT_ALLOWED = "WAIVER_NOT_ALLOWED"
WAIVER_ALLOWED_WITH_MANUAL_REVIEW = "WAIVER_ALLOWED_WITH_MANUAL_REVIEW"
WAIVER_ALLOWED_FOR_UX_ONLY = "WAIVER_ALLOWED_FOR_UX_ONLY"
WAIVER_ALLOWED_FOR_ANALYTICS_ONLY = "WAIVER_ALLOWED_FOR_ANALYTICS_ONLY"

# High-impact criticality for rollout blocking
_HIGH_IMPACT_CRITICALITY = frozenset({SAFETY_CRITICAL, COMPLIANCE_CRITICAL, OPERATIONAL_CRITICAL})

# Action-driving consumers (higher consequence for semantic-aware rollout)
_ACTION_DRIVING_CONSUMERS = frozenset(
    {
        "REMINDER_ENGINE",
        "PRIORITY_ACTIONS",
        "SLA_ESCALATION_PATHS",
        "NOTIFICATION_EMAIL_PATHS",
    }
)

# Passive / display-weighted consumers (CONDITIONAL bias when blockers are UX/analytics-only)
_PASSIVE_DISPLAY_CONSUMERS = frozenset(
    {
        "REQUIREMENT_LIST",
        "PROPERTY_SUMMARY",
        "COMMAND_CENTER",
        "DASHBOARD_SUMMARY",
        "TODAY_VIEW",
        "UNIFIED_TASKS",
    }
)

# Consumers with observe-only semantic delta instrumentation (no production telemetry required)
_OBSERVE_INSTRUMENTED_CONSUMERS = frozenset({"REMINDER_ENGINE", "PORTFOLIO_SCORE", "REPORT_EXPORT"})

# Minimum evidence thresholds (deterministic audit matrix coverage; must match SEMANTIC_TRANSITIONS length)
_MIN_ROWS_PER_CONSUMER = 13
_MIN_NON_UNKNOWN_CONFIDENCE_ROWS = 8
_MIN_CRITICAL_TRANSITION_ROWS = 3
_CRITICAL_TRANSITIONS_FOR_EVIDENCE = frozenset(
    {
        "ASSESSMENT_FOLLOWUP_REQUIRED",
        "OPERATIONALLY_OPEN",
        "EXPIRY_REVIEW_REQUIRED",
        "PARTIALLY_COMPLETE",
    }
)

SEMANTIC_TRANSITIONS: List[str] = [
    "MISSING",
    "VERIFIED_CURRENT",
    "VERIFIED_EXPIRED",
    "UPLOADED_UNCONFIRMED",
    "PARTIALLY_COMPLETE",
    "DECLARATION_RECORDED",
    "REGISTRATION_RECORDED",
    "TENANT_DELIVERY_RECORDED",
    "ASSESSMENT_FOLLOWUP_REQUIRED",
    "OPERATIONALLY_OPEN",
    "FOLLOWUP_REQUIRED",
    "COMPLETENESS_PENDING",
    "EXPIRY_REVIEW_REQUIRED",
]

CONSUMERS: List[str] = [
    "REMINDER_ENGINE",
    "COMMAND_CENTER",
    "TODAY_VIEW",
    "PORTFOLIO_SCORE",
    "PROPERTY_SUMMARY",
    "REPORT_EXPORT",
    "UNIFIED_TASKS",
    "DASHBOARD_SUMMARY",
    "REQUIREMENT_LIST",
    "PRIORITY_ACTIONS",
    "SCORE_DRIVERS",
    "NOTIFICATION_EMAIL_PATHS",
    "SLA_ESCALATION_PATHS",
    "CACHE_INVALIDATION_REFRESH",
    "REGENERATION_RECALC_PATHS",
]


def _consumer_default_profile(consumer: str) -> Dict[str, Any]:
    c = str(consumer or "").upper()
    if c == "REQUIREMENT_LIST":
        return {
            "propagation_type": DERIVED_ON_READ,
            "confidence": HIGH_CONFIDENCE,
            "reaction_source_of_truth": LIVE_READ_PROJECTION,
            "trigger_source": "requirement_truth.enrich_requirement_dict semantic_state pass-through",
            "known_gaps": [],
            "operational_followthrough": False,
            "refresh_dependency": "live_read_model_derivation",
        }
    if c in ("COMMAND_CENTER", "DASHBOARD_SUMMARY", "PROPERTY_SUMMARY"):
        return {
            "propagation_type": DERIVED_ON_READ,
            "confidence": MEDIUM_CONFIDENCE,
            "reaction_source_of_truth": LIVE_READ_PROJECTION,
            "trigger_source": "unified task/score summary composition on read",
            "known_gaps": ["composite read-model; not transition-triggered orchestration"],
            "operational_followthrough": False,
            "refresh_dependency": "live_read_model_derivation_and_user_refresh",
        }
    if c in ("UNIFIED_TASKS", "TODAY_VIEW", "PRIORITY_ACTIONS"):
        return {
            "propagation_type": TASK_REBUILD and DERIVED_ON_READ,
            "confidence": MEDIUM_CONFIDENCE,
            "reaction_source_of_truth": TASK_REBUILD,
            "trigger_source": "priority stream + unified task projection rebuild on read",
            "known_gaps": ["task visibility derives on fetch; no semantic transition dispatcher"],
            "operational_followthrough": False,
            "refresh_dependency": "task_rebuild_on_fetch_and_user_refresh",
        }
    if c in ("PORTFOLIO_SCORE", "SCORE_DRIVERS"):
        return {
            "propagation_type": EVENTUAL_RECALC,
            "confidence": MEDIUM_CONFIDENCE,
            "reaction_source_of_truth": SCORE_REGENERATION,
            "trigger_source": "calculate_compliance_score with persisted score aggregate + runtime driver shaping",
            "known_gaps": ["semantic_state observed but not runtime-selected interpretation"],
            "operational_followthrough": False,
            "refresh_dependency": "score_regeneration_lazy_backfill_and_read_projection",
        }
    if c == "REPORT_EXPORT":
        return {
            "propagation_type": DERIVED_ON_READ,
            "confidence": MEDIUM_CONFIDENCE,
            "reaction_source_of_truth": LIVE_READ_PROJECTION,
            "trigger_source": "reporting_service project_requirement_row_client_runtime at export time",
            "known_gaps": ["semantic deltas observed only; no semantic-aware runtime switch"],
            "operational_followthrough": False,
            "refresh_dependency": "report_generation_time_derivation",
        }
    if c == "REMINDER_ENGINE":
        return {
            "propagation_type": PARTIAL_PROPAGATION,
            "confidence": LOW_CONFIDENCE,
            "reaction_source_of_truth": LIVE_READ_PROJECTION,
            "trigger_source": "reminder_truth_service runtime status/date eligibility checks",
            "known_gaps": ["semantic_state hook is observe-only", "reminder reaction remains legacy-status-primary"],
            "operational_followthrough": False,
            "refresh_dependency": "periodic_reminder_job_with_runtime_read",
        }
    if c == "NOTIFICATION_EMAIL_PATHS":
        return {
            "propagation_type": FRAGMENTED_PROPAGATION,
            "confidence": LOW_CONFIDENCE,
            "reaction_source_of_truth": PERIODIC_JOB,
            "trigger_source": "email/reminder/report jobs and templates across multiple services",
            "known_gaps": ["no single semantic transition contract for email fanout"],
            "operational_followthrough": False,
            "refresh_dependency": "periodic_jobs_and_template_runtime",
        }
    if c == "SLA_ESCALATION_PATHS":
        return {
            "propagation_type": FRAGMENTED_PROPAGATION,
            "confidence": LOW_CONFIDENCE,
            "reaction_source_of_truth": PERIODIC_JOB,
            "trigger_source": "compliance_sla_monitor / sla_watchdog / operational monitors",
            "known_gaps": ["not directly keyed to requirement semantic_state transitions"],
            "operational_followthrough": False,
            "refresh_dependency": "periodic_monitoring_jobs",
        }
    if c == "CACHE_INVALIDATION_REFRESH":
        return {
            "propagation_type": NO_KNOWN_PROPAGATION,
            "confidence": UNKNOWN_CONFIDENCE,
            "reaction_source_of_truth": UNKNOWN,
            "trigger_source": "no explicit semantic-transition cache invalidation contract identified",
            "known_gaps": ["refresh behavior mostly read-time recomposition and client refresh"],
            "operational_followthrough": False,
            "refresh_dependency": "unknown_explicit_cache_invalidation",
        }
    if c == "REGENERATION_RECALC_PATHS":
        return {
            "propagation_type": EVENTUAL_RECALC,
            "confidence": MEDIUM_CONFIDENCE,
            "reaction_source_of_truth": SCHEDULED_RECALC,
            "trigger_source": "compliance_recalc_queue / lazy backfill / scheduled worker outcomes",
            "known_gaps": ["recalc exists but semantic transition-to-recalc mapping is not exhaustive"],
            "operational_followthrough": False,
            "refresh_dependency": "queued_and_scheduled_recalculation",
        }
    return {
        "propagation_type": NO_KNOWN_PROPAGATION,
        "confidence": UNKNOWN_CONFIDENCE,
        "reaction_source_of_truth": UNKNOWN,
        "trigger_source": "unknown",
        "known_gaps": ["no audited propagation path"],
        "operational_followthrough": False,
        "refresh_dependency": "unknown",
    }


def _transition_adjustments(transition: str, consumer: str, row: Dict[str, Any]) -> Dict[str, Any]:
    t = str(transition or "").upper()
    c = str(consumer or "").upper()
    out = dict(row)
    gaps = list(out.get("known_gaps") or [])
    follow = bool(out.get("operational_followthrough"))
    ptype = out.get("propagation_type")
    conf = out.get("confidence")
    source = out.get("reaction_source_of_truth")
    trig = str(out.get("trigger_source") or "")
    dep = out.get("refresh_dependency")

    if t in ("MISSING", "VERIFIED_CURRENT", "VERIFIED_EXPIRED", "UPLOADED_UNCONFIRMED"):
        if c in ("REQUIREMENT_LIST", "REPORT_EXPORT"):
            conf = HIGH_CONFIDENCE
            ptype = DERIVED_ON_READ
            source = LIVE_READ_PROJECTION
        if c == "UNIFIED_TASKS":
            conf = MEDIUM_CONFIDENCE
            ptype = TASK_REBUILD
            source = TASK_REBUILD
    if t == "PARTIALLY_COMPLETE":
        if c in ("PORTFOLIO_SCORE", "SCORE_DRIVERS", "REMINDER_ENGINE"):
            gaps.append("partial completeness may collapse into coarse pending/current interpretations")
            ptype = PARTIAL_PROPAGATION
            conf = LOW_CONFIDENCE if c == "REMINDER_ENGINE" else MEDIUM_CONFIDENCE
    if t in ("DECLARATION_RECORDED", "REGISTRATION_RECORDED", "TENANT_DELIVERY_RECORDED"):
        if c in ("REPORT_EXPORT", "PORTFOLIO_SCORE", "REMINDER_ENGINE"):
            gaps.append("declaration/recorded states may flatten into legacy verified/pending buckets")
            ptype = PARTIAL_PROPAGATION if c != "REMINDER_ENGINE" else FRAGMENTED_PROPAGATION
            conf = LOW_CONFIDENCE if c == "REMINDER_ENGINE" else MEDIUM_CONFIDENCE
    if t == "ASSESSMENT_FOLLOWUP_REQUIRED":
        follow = False
        gaps.append("semantic follow-up state exists without guaranteed remediation workflow creation")
        if c in ("PRIORITY_ACTIONS", "UNIFIED_TASKS", "TODAY_VIEW", "REMINDER_ENGINE"):
            ptype = FRAGMENTED_PROPAGATION
            conf = LOW_CONFIDENCE
    if t == "OPERATIONALLY_OPEN":
        follow = False
        gaps.append("operational-open semantics not guaranteed to trigger orchestration/escalation")
        if c in ("SLA_ESCALATION_PATHS", "REMINDER_ENGINE", "PRIORITY_ACTIONS"):
            ptype = FRAGMENTED_PROPAGATION
            conf = LOW_CONFIDENCE
    if t in ("FOLLOWUP_REQUIRED", "COMPLETENESS_PENDING"):
        gaps.append("state represented semantically but consumer contracts are mixed and often derived-on-read")
        if c in ("NOTIFICATION_EMAIL_PATHS", "SLA_ESCALATION_PATHS", "CACHE_INVALIDATION_REFRESH"):
            ptype = NO_KNOWN_PROPAGATION if c == "CACHE_INVALIDATION_REFRESH" else FRAGMENTED_PROPAGATION
            conf = UNKNOWN_CONFIDENCE if c == "CACHE_INVALIDATION_REFRESH" else LOW_CONFIDENCE
    if t == "EXPIRY_REVIEW_REQUIRED":
        follow = False
        gaps.append("expiry-review semantics do not guarantee reminder refresh or escalation refresh")
        if c in ("REMINDER_ENGINE", "NOTIFICATION_EMAIL_PATHS"):
            ptype = PARTIAL_PROPAGATION
            conf = LOW_CONFIDENCE
            dep = "periodic_jobs_and_runtime_read_evaluation"
    if c == "CACHE_INVALIDATION_REFRESH":
        source = UNKNOWN
        dep = "unknown_explicit_cache_invalidation"
        if "no explicit semantic-transition cache invalidation contract identified" not in gaps:
            gaps.append("no explicit semantic-transition cache invalidation contract identified")
    if c == "REGENERATION_RECALC_PATHS":
        source = SCHEDULED_RECALC
        ptype = EVENTUAL_RECALC
        dep = "queued_or_scheduled_recalculation"
        trig = "compliance recalc queue and worker pathways"

    # de-dup gaps, keep order
    dedup_gaps: List[str] = []
    for g in gaps:
        if g not in dedup_gaps:
            dedup_gaps.append(g)
    out.update(
        {
            "propagation_type": ptype,
            "confidence": conf,
            "reaction_source_of_truth": source,
            "trigger_source": trig,
            "known_gaps": dedup_gaps,
            "operational_followthrough": follow,
            "refresh_recalc_dependency": dep,
        }
    )
    return out


def build_trigger_propagation_matrix() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for transition in SEMANTIC_TRANSITIONS:
        for consumer in CONSUMERS:
            base = _consumer_default_profile(consumer)
            row = {
                "semantic_transition": transition,
                "consumer": consumer,
                "propagation_type": base["propagation_type"],
                "confidence": base["confidence"],
                "reaction_source_of_truth": base["reaction_source_of_truth"],
                "trigger_source": base["trigger_source"],
                "known_gaps": list(base.get("known_gaps") or []),
                "operational_followthrough": bool(base.get("operational_followthrough")),
                "refresh_recalc_dependency": base.get("refresh_dependency"),
            }
            rows.append(_transition_adjustments(transition, consumer, row))
    return rows


def build_grouped_summary(matrix: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in matrix:
        gap_risk = "LOW"
        if r.get("propagation_type") in (FRAGMENTED_PROPAGATION, NO_KNOWN_PROPAGATION):
            gap_risk = "HIGH"
        elif r.get("propagation_type") in (PARTIAL_PROPAGATION, EVENTUAL_RECALC):
            gap_risk = "MEDIUM"
        out.append(
            {
                "semantic_transition": r.get("semantic_transition"),
                "consumer": r.get("consumer"),
                "propagation": r.get("propagation_type"),
                "confidence": r.get("confidence"),
                "reaction_source_of_truth": r.get("reaction_source_of_truth"),
                "gap_risk": gap_risk,
            }
        )
    return out


def _filter_rows(matrix: List[Dict[str, Any]], *, include_types: Tuple[str, ...] = ()) -> List[Dict[str, Any]]:
    rows = list(matrix)
    if include_types:
        rows = [r for r in rows if r.get("propagation_type") in include_types]
    return rows


def build_semantic_without_operational_followthrough(matrix: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in matrix:
        text = " ".join(r.get("known_gaps") or []).lower()
        if r.get("operational_followthrough") is False and (
            "without guaranteed" in text
            or "without remediation workflow creation" in text
            or "not guaranteed to trigger orchestration" in text
            or "do not guarantee" in text
            or "without orchestration" in text
        ):
            out.append(r)
    return out


def build_refresh_dependency_summary(matrix: List[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in matrix:
        k = str(r.get("refresh_recalc_dependency") or "unknown")
        out[k] = out.get(k, 0) + 1
    return out


def build_trigger_propagation_audit_snapshot() -> Dict[str, Any]:
    matrix = build_trigger_propagation_matrix()
    grouped = build_grouped_summary(matrix)
    highest_conf = [
        r
        for r in matrix
        if r.get("confidence") == HIGH_CONFIDENCE
        and r.get("propagation_type") in (DIRECT_SYNCHRONOUS, DERIVED_ON_READ, EVENTUAL_RECALC, TASK_REBUILD)
    ]
    weakest = [
        r
        for r in matrix
        if r.get("propagation_type") in (NO_KNOWN_PROPAGATION, FRAGMENTED_PROPAGATION)
        or r.get("confidence") in (LOW_CONFIDENCE, UNKNOWN_CONFIDENCE)
    ]
    return {
        "phase": "Trigger Propagation Completeness Audit Phase 1",
        "scope": "semantic transition to operational reaction matrix",
        "runtime_behavior_changed": False,
        "audit_only": True,
        "semantic_transitions": list(SEMANTIC_TRANSITIONS),
        "consumers": list(CONSUMERS),
        "classification_catalog": {
            "propagation_type": [
                DIRECT_SYNCHRONOUS,
                DERIVED_ON_READ,
                EVENTUAL_RECALC,
                PARTIAL_PROPAGATION,
                FRAGMENTED_PROPAGATION,
                NO_KNOWN_PROPAGATION,
            ],
            "confidence": [HIGH_CONFIDENCE, MEDIUM_CONFIDENCE, LOW_CONFIDENCE, UNKNOWN_CONFIDENCE],
            "reaction_source_of_truth": [
                AUTHORITY_WRITE,
                LIVE_READ_PROJECTION,
                SCHEDULED_RECALC,
                TASK_REBUILD,
                SCORE_REGENERATION,
                UI_DERIVATION,
                PERIODIC_JOB,
                MANUAL_REFRESH,
                UNKNOWN,
            ],
        },
        "matrix": matrix,
        "grouped_summary": grouped,
        "highest_confidence_paths": highest_conf,
        "weakest_or_missing_paths": weakest,
        "semantic_without_operational_followthrough": build_semantic_without_operational_followthrough(matrix),
        "refresh_recalc_dependency_summary": build_refresh_dependency_summary(matrix),
        "non_blocking": True,
    }


def _expected_freshness_for_consumer(consumer: str) -> str:
    c = str(consumer or "").upper()
    if c in ("REQUIREMENT_LIST", "REPORT_EXPORT", "UNIFIED_TASKS", "TODAY_VIEW", "COMMAND_CENTER", "PROPERTY_SUMMARY"):
        return NEAR_REAL_TIME
    if c in ("PORTFOLIO_SCORE", "SCORE_DRIVERS", "REGENERATION_RECALC_PATHS"):
        return EVENTUAL
    if c in ("REMINDER_ENGINE", "NOTIFICATION_EMAIL_PATHS", "SLA_ESCALATION_PATHS"):
        return PERIODIC
    if c in ("CACHE_INVALIDATION_REFRESH",):
        return UNKNOWN_FRESHNESS
    if c in ("DASHBOARD_SUMMARY", "PRIORITY_ACTIONS"):
        return BEST_EFFORT
    return UNKNOWN_FRESHNESS


def _expected_criticality(transition: str, consumer: str) -> str:
    t = str(transition or "").upper()
    c = str(consumer or "").upper()
    if c in ("REMINDER_ENGINE", "NOTIFICATION_EMAIL_PATHS") and t in (
        "EXPIRY_REVIEW_REQUIRED",
        "VERIFIED_EXPIRED",
        "MISSING",
    ):
        return COMPLIANCE_CRITICAL
    if c in ("SLA_ESCALATION_PATHS",) and t in ("OPERATIONALLY_OPEN", "ASSESSMENT_FOLLOWUP_REQUIRED"):
        return OPERATIONAL_CRITICAL
    if c in ("PORTFOLIO_SCORE", "SCORE_DRIVERS"):
        return ANALYTICS_ONLY
    if c in ("REQUIREMENT_LIST", "COMMAND_CENTER", "TODAY_VIEW", "UNIFIED_TASKS", "DASHBOARD_SUMMARY", "PROPERTY_SUMMARY"):
        return UX_CRITICAL
    if c in ("PRIORITY_ACTIONS",):
        return OPERATIONAL_CRITICAL
    if c in ("REPORT_EXPORT",):
        return COMPLIANCE_CRITICAL
    if c in ("CACHE_INVALIDATION_REFRESH", "REGENERATION_RECALC_PATHS"):
        return ANALYTICS_ONLY
    if t in ("ASSESSMENT_FOLLOWUP_REQUIRED", "OPERATIONALLY_OPEN"):
        return SAFETY_CRITICAL
    return UX_CRITICAL


def _expected_propagation_contract(transition: str, consumer: str) -> Dict[str, Any]:
    t = str(transition or "").upper()
    c = str(consumer or "").upper()
    expected_propagation_type = DERIVED_ON_READ
    expected_operational_followthrough = False
    expected_confidence = MEDIUM_CONFIDENCE
    if c in ("REQUIREMENT_LIST", "REPORT_EXPORT", "COMMAND_CENTER", "PROPERTY_SUMMARY", "UNIFIED_TASKS"):
        expected_propagation_type = DERIVED_ON_READ
        expected_confidence = HIGH_CONFIDENCE if c in ("REQUIREMENT_LIST", "REPORT_EXPORT") else MEDIUM_CONFIDENCE
    elif c in ("TODAY_VIEW", "PRIORITY_ACTIONS"):
        expected_propagation_type = PARTIAL_PROPAGATION
    elif c in ("PORTFOLIO_SCORE", "SCORE_DRIVERS", "REGENERATION_RECALC_PATHS"):
        expected_propagation_type = EVENTUAL_RECALC
    elif c in ("REMINDER_ENGINE", "NOTIFICATION_EMAIL_PATHS", "SLA_ESCALATION_PATHS"):
        expected_propagation_type = EVENTUAL_RECALC
        expected_confidence = MEDIUM_CONFIDENCE
    elif c == "CACHE_INVALIDATION_REFRESH":
        expected_propagation_type = NO_KNOWN_PROPAGATION
        expected_confidence = UNKNOWN_CONFIDENCE

    if t in ("ASSESSMENT_FOLLOWUP_REQUIRED", "OPERATIONALLY_OPEN", "EXPIRY_REVIEW_REQUIRED"):
        if c in ("REMINDER_ENGINE", "PRIORITY_ACTIONS", "SLA_ESCALATION_PATHS"):
            expected_operational_followthrough = True
            expected_propagation_type = EVENTUAL_RECALC
        if c in ("REPORT_EXPORT", "REQUIREMENT_LIST", "COMMAND_CENTER", "TODAY_VIEW", "UNIFIED_TASKS"):
            expected_operational_followthrough = False
            expected_propagation_type = DERIVED_ON_READ
    if t == "PARTIALLY_COMPLETE":
        if c in ("COMMAND_CENTER", "TODAY_VIEW", "UNIFIED_TASKS", "PRIORITY_ACTIONS"):
            expected_propagation_type = PARTIAL_PROPAGATION
    if c == "CACHE_INVALIDATION_REFRESH":
        expected_operational_followthrough = False
        expected_confidence = UNKNOWN_CONFIDENCE

    return {
        "expected_propagation_type": expected_propagation_type,
        "expected_freshness_expectation": _expected_freshness_for_consumer(c),
        "expected_operational_followthrough": expected_operational_followthrough,
        "expected_confidence": expected_confidence,
        "propagation_criticality": _expected_criticality(t, c),
    }


def _refresh_guarantee_for_row(row: Dict[str, Any]) -> str:
    ptype = str(row.get("propagation_type") or "")
    dep = str(row.get("refresh_recalc_dependency") or "").lower()
    src = str(row.get("reaction_source_of_truth") or "")
    if ptype == DERIVED_ON_READ and src == LIVE_READ_PROJECTION:
        return DETERMINISTIC
    if ptype == EVENTUAL_RECALC and ("scheduled" in dep or "queued" in dep):
        return LIKELY
    if ptype in (FRAGMENTED_PROPAGATION,):
        return FRAGMENTED
    if ptype in (PARTIAL_PROPAGATION,) and ("periodic" in dep or src == PERIODIC_JOB):
        return INCIDENTAL
    if ptype == NO_KNOWN_PROPAGATION or src == UNKNOWN:
        return UNKNOWN_GUARANTEE
    return LIKELY


def _blocker_reasons(row: Dict[str, Any], contract: Dict[str, Any], refresh_guarantee: str) -> List[str]:
    reasons: List[str] = []
    ptype = str(row.get("propagation_type") or "")
    conf = str(row.get("confidence") or "")
    if ptype in (NO_KNOWN_PROPAGATION,):
        reasons.append(NO_DIRECT_PROPAGATION)
    if ptype in (FRAGMENTED_PROPAGATION,):
        reasons.append(FRAGMENTED_MULTI_SOURCE_REFRESH)
    if conf in (LOW_CONFIDENCE, UNKNOWN_CONFIDENCE):
        reasons.append(LOW_CONFIDENCE_PATH)
    if refresh_guarantee == UNKNOWN_GUARANTEE:
        reasons.append(UNKNOWN_REFRESH_GUARANTEE)
    if refresh_guarantee == FRAGMENTED:
        reasons.append(FRAGMENTED_MULTI_SOURCE_REFRESH)
    if str(row.get("reaction_source_of_truth") or "") == UNKNOWN and str(row.get("consumer") or "") == "CACHE_INVALIDATION_REFRESH":
        reasons.append(CACHE_INVALIDATION_UNKNOWN)
    if contract.get("expected_operational_followthrough") is True and row.get("operational_followthrough") is not True:
        reasons.append(NO_OPERATIONAL_FOLLOWTHROUGH)
    if str(row.get("reaction_source_of_truth") or "") in (LIVE_READ_PROJECTION, TASK_REBUILD) and ptype in (
        DERIVED_ON_READ,
        PARTIAL_PROPAGATION,
    ):
        reasons.append(DERIVED_ONLY_NO_PUSH_SIGNAL)
    text = " ".join(row.get("known_gaps") or []).lower()
    if "collapse" in text or "flatten" in text:
        reasons.append(SEMANTIC_COLLAPSE_RISK)
    if str(contract.get("expected_freshness_expectation") or "") in (IMMEDIATE, NEAR_REAL_TIME) and str(
        row.get("refresh_recalc_dependency") or ""
    ).lower().startswith("periodic"):
        reasons.append(PERIODIC_ONLY_REFRESH)
    out: List[str] = []
    for r in reasons:
        if r not in out:
            out.append(r)
    return out


def _gap_classification(row: Dict[str, Any], contract: Dict[str, Any], refresh_guarantee: str, blockers: List[str]) -> str:
    p_curr = str(row.get("propagation_type") or "")
    p_exp = str(contract.get("expected_propagation_type") or "")
    f_curr = bool(row.get("operational_followthrough"))
    f_exp = bool(contract.get("expected_operational_followthrough"))
    if len(blockers) > 0 and (
        NO_DIRECT_PROPAGATION in blockers
        or NO_OPERATIONAL_FOLLOWTHROUGH in blockers
        or UNKNOWN_REFRESH_GUARANTEE in blockers
    ):
        return BLOCKED_FOR_RUNTIME_ENFORCEMENT
    if p_curr == FRAGMENTED_PROPAGATION:
        return FRAGMENTED_BEHAVIOR
    if p_curr == NO_KNOWN_PROPAGATION:
        return UNDER_PROPAGATED
    if refresh_guarantee in (INCIDENTAL, FRAGMENTED) and contract.get("expected_freshness_expectation") in (
        IMMEDIATE,
        NEAR_REAL_TIME,
    ):
        return ROLLUP_STALE_RISK
    if f_exp and not f_curr:
        return OPERATIONAL_GAP
    if p_curr == p_exp and f_curr == f_exp:
        return CONTRACT_SATISFIED
    return PARTIALLY_SATISFIED


def build_expected_vs_current_matrix() -> List[Dict[str, Any]]:
    current = build_trigger_propagation_matrix()
    out: List[Dict[str, Any]] = []
    for row in current:
        contract = _expected_propagation_contract(row.get("semantic_transition"), row.get("consumer"))
        refresh_guarantee = _refresh_guarantee_for_row(row)
        blockers = _blocker_reasons(row, contract, refresh_guarantee)
        gap = _gap_classification(row, contract, refresh_guarantee, blockers)
        merged = {
            **row,
            **contract,
            "refresh_guarantee": refresh_guarantee,
            "gap_classification": gap,
            "runtime_enforcement_blocked": bool(gap == BLOCKED_FOR_RUNTIME_ENFORCEMENT or len(blockers) > 0),
            "runtime_enforcement_blocker_reasons": blockers,
        }
        out.append(merged)
    return out


def _count_by(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        k = str(r.get(key) or "")
        out[k] = out.get(k, 0) + 1
    return out


def _rollout_safety_score(row: Dict[str, Any]) -> int:
    score = 0
    if row.get("runtime_enforcement_blocked") is True:
        score -= 6
    if row.get("gap_classification") == CONTRACT_SATISFIED:
        score += 5
    if row.get("refresh_guarantee") == DETERMINISTIC:
        score += 3
    elif row.get("refresh_guarantee") == LIKELY:
        score += 1
    elif row.get("refresh_guarantee") in (FRAGMENTED, UNKNOWN_GUARANTEE):
        score -= 2
    if row.get("confidence") == HIGH_CONFIDENCE:
        score += 3
    elif row.get("confidence") == LOW_CONFIDENCE:
        score -= 2
    elif row.get("confidence") == UNKNOWN_CONFIDENCE:
        score -= 3
    if row.get("propagation_criticality") in (ANALYTICS_ONLY, UX_CRITICAL):
        score += 2
    if row.get("propagation_criticality") in (COMPLIANCE_CRITICAL, OPERATIONAL_CRITICAL, SAFETY_CRITICAL):
        score -= 2
    return score


def _rank_rollout_candidates(rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    ranked = sorted(
        rows,
        key=lambda r: (
            -_rollout_safety_score(r),
            str(r.get("consumer") or ""),
            str(r.get("semantic_transition") or ""),
        ),
    )
    safest = ranked[:20]
    highest_risk = sorted(
        rows,
        key=lambda r: (
            _rollout_safety_score(r),
            str(r.get("consumer") or ""),
            str(r.get("semantic_transition") or ""),
        ),
    )[:20]
    return safest, highest_risk


def build_trigger_propagation_audit_phase2_snapshot() -> Dict[str, Any]:
    matrix = build_expected_vs_current_matrix()
    grouped = [
        {
            "semantic_transition": r.get("semantic_transition"),
            "consumer": r.get("consumer"),
            "expected_propagation_type": r.get("expected_propagation_type"),
            "current_propagation_type": r.get("propagation_type"),
            "expected_freshness_expectation": r.get("expected_freshness_expectation"),
            "refresh_guarantee": r.get("refresh_guarantee"),
            "propagation_criticality": r.get("propagation_criticality"),
            "gap_classification": r.get("gap_classification"),
            "reaction_source_of_truth": r.get("reaction_source_of_truth"),
        }
        for r in matrix
    ]
    safest, highest_risk = _rank_rollout_candidates(matrix)
    highest_risk_gaps = [
        r
        for r in matrix
        if r.get("gap_classification") in (BLOCKED_FOR_RUNTIME_ENFORCEMENT, OPERATIONAL_GAP, FRAGMENTED_BEHAVIOR)
    ]
    highest_risk_gaps.sort(
        key=lambda r: (
            str(r.get("propagation_criticality") or ""),
            str(r.get("consumer") or ""),
            str(r.get("semantic_transition") or ""),
        )
    )
    return {
        "phase": "Trigger Propagation Completeness Audit Phase 2",
        "scope": "expected vs current propagation contracts",
        "runtime_behavior_changed": False,
        "audit_only": True,
        "semantic_transitions": list(SEMANTIC_TRANSITIONS),
        "consumers": list(CONSUMERS),
        "classification_catalog": {
            "propagation_type": [
                DIRECT_SYNCHRONOUS,
                DERIVED_ON_READ,
                EVENTUAL_RECALC,
                PARTIAL_PROPAGATION,
                FRAGMENTED_PROPAGATION,
                NO_KNOWN_PROPAGATION,
            ],
            "confidence": [HIGH_CONFIDENCE, MEDIUM_CONFIDENCE, LOW_CONFIDENCE, UNKNOWN_CONFIDENCE],
            "freshness_expectation": [IMMEDIATE, NEAR_REAL_TIME, EVENTUAL, PERIODIC, BEST_EFFORT, UNKNOWN_FRESHNESS],
            "refresh_guarantee": [DETERMINISTIC, LIKELY, INCIDENTAL, FRAGMENTED, UNKNOWN_GUARANTEE],
            "propagation_criticality": [
                SAFETY_CRITICAL,
                COMPLIANCE_CRITICAL,
                OPERATIONAL_CRITICAL,
                UX_CRITICAL,
                ANALYTICS_ONLY,
            ],
            "gap_classification": [
                CONTRACT_SATISFIED,
                PARTIALLY_SATISFIED,
                UNDER_PROPAGATED,
                FRAGMENTED_BEHAVIOR,
                ROLLUP_STALE_RISK,
                OPERATIONAL_GAP,
                BLOCKED_FOR_RUNTIME_ENFORCEMENT,
            ],
            "runtime_enforcement_blocker_reasons": [
                UNKNOWN_REFRESH_GUARANTEE,
                PERIODIC_ONLY_REFRESH,
                NO_DIRECT_PROPAGATION,
                FRAGMENTED_MULTI_SOURCE_REFRESH,
                CACHE_INVALIDATION_UNKNOWN,
                NO_OPERATIONAL_FOLLOWTHROUGH,
                LOW_CONFIDENCE_PATH,
                DERIVED_ONLY_NO_PUSH_SIGNAL,
                SEMANTIC_COLLAPSE_RISK,
            ],
            "reaction_source_of_truth": [
                AUTHORITY_WRITE,
                LIVE_READ_PROJECTION,
                SCHEDULED_RECALC,
                TASK_REBUILD,
                SCORE_REGENERATION,
                UI_DERIVATION,
                PERIODIC_JOB,
                MANUAL_REFRESH,
                UNKNOWN,
            ],
        },
        "matrix": matrix,
        "grouped_summary": grouped,
        "criticality_summary": _count_by(matrix, "propagation_criticality"),
        "freshness_expectation_summary": _count_by(matrix, "expected_freshness_expectation"),
        "refresh_guarantee_summary": _count_by(matrix, "refresh_guarantee"),
        "gap_summary": _count_by(matrix, "gap_classification"),
        "runtime_enforcement_blocker_summary": _count_by(
            [{"reason": br} for r in matrix for br in (r.get("runtime_enforcement_blocker_reasons") or [])], "reason"
        ),
        "highest_risk_gaps": highest_risk_gaps[:60],
        "safest_rollout_candidates": safest,
        "highest_risk_rollout_candidates": highest_risk,
        "non_blocking": True,
    }


# --- Phase 3: consumer rollout gate profiles (audit-only) ---

_STATE_MODEL_LIMITATION = (
    "Audit matrix uses declared consumer profiles and static expected contracts; it does not "
    "enumerate every runtime branch or environment-specific configuration."
)
_RUNTIME_CONVERGENCE_LIMITATION = (
    "Gap and refresh guarantees are inferred from propagation type and dependency labels, not "
    "from live traces, production metrics, or cross-service convergence proofs."
)

_WAIVER_STRICTNESS_ORDER = (
    WAIVER_NOT_ALLOWED,
    WAIVER_ALLOWED_WITH_MANUAL_REVIEW,
    WAIVER_ALLOWED_FOR_UX_ONLY,
    WAIVER_ALLOWED_FOR_ANALYTICS_ONLY,
)


def _strictest_waiver(policies: List[str]) -> str:
    best = WAIVER_ALLOWED_FOR_ANALYTICS_ONLY
    for p in policies:
        if _WAIVER_STRICTNESS_ORDER.index(p) < _WAIVER_STRICTNESS_ORDER.index(best):
            best = p
    return best


def _waiver_policy_for_blocker(blocker: str, criticality: str, consumer: str) -> str:
    """Deterministic waiver metadata for a single (blocker, criticality) pair (audit-only)."""
    c = str(consumer or "").upper()
    crit = str(criticality or "")
    b = str(blocker or "")
    if b == CACHE_INVALIDATION_UNKNOWN:
        if crit == COMPLIANCE_CRITICAL:
            return WAIVER_NOT_ALLOWED
        if crit in _HIGH_IMPACT_CRITICALITY:
            return WAIVER_ALLOWED_WITH_MANUAL_REVIEW
        if crit == ANALYTICS_ONLY:
            return WAIVER_ALLOWED_FOR_ANALYTICS_ONLY
        return WAIVER_ALLOWED_FOR_UX_ONLY
    if b == NO_OPERATIONAL_FOLLOWTHROUGH:
        if crit in (COMPLIANCE_CRITICAL, SAFETY_CRITICAL) and c in _ACTION_DRIVING_CONSUMERS:
            return WAIVER_NOT_ALLOWED
        if crit in _HIGH_IMPACT_CRITICALITY:
            return WAIVER_ALLOWED_WITH_MANUAL_REVIEW
        if crit == UX_CRITICAL:
            return WAIVER_ALLOWED_FOR_UX_ONLY
        if crit == ANALYTICS_ONLY:
            return WAIVER_ALLOWED_FOR_ANALYTICS_ONLY
        return WAIVER_ALLOWED_WITH_MANUAL_REVIEW
    if b in (NO_DIRECT_PROPAGATION, UNKNOWN_REFRESH_GUARANTEE, FRAGMENTED_MULTI_SOURCE_REFRESH):
        if crit in (COMPLIANCE_CRITICAL, SAFETY_CRITICAL):
            return WAIVER_ALLOWED_WITH_MANUAL_REVIEW
        if crit == OPERATIONAL_CRITICAL and c in _ACTION_DRIVING_CONSUMERS:
            return WAIVER_ALLOWED_WITH_MANUAL_REVIEW
        if crit == ANALYTICS_ONLY:
            return WAIVER_ALLOWED_FOR_ANALYTICS_ONLY
        return WAIVER_ALLOWED_FOR_UX_ONLY
    if b == LOW_CONFIDENCE_PATH:
        if crit in (COMPLIANCE_CRITICAL, SAFETY_CRITICAL):
            return WAIVER_ALLOWED_WITH_MANUAL_REVIEW
        if crit == ANALYTICS_ONLY:
            return WAIVER_ALLOWED_FOR_ANALYTICS_ONLY
        return WAIVER_ALLOWED_FOR_UX_ONLY
    if b == SEMANTIC_COLLAPSE_RISK:
        if crit in _HIGH_IMPACT_CRITICALITY:
            return WAIVER_ALLOWED_WITH_MANUAL_REVIEW
        return WAIVER_ALLOWED_FOR_ANALYTICS_ONLY
    if b in (DERIVED_ONLY_NO_PUSH_SIGNAL, PERIODIC_ONLY_REFRESH):
        if crit in _HIGH_IMPACT_CRITICALITY and c in _ACTION_DRIVING_CONSUMERS:
            return WAIVER_ALLOWED_WITH_MANUAL_REVIEW
        if crit == ANALYTICS_ONLY:
            return WAIVER_ALLOWED_FOR_ANALYTICS_ONLY
        return WAIVER_ALLOWED_FOR_UX_ONLY
    return WAIVER_ALLOWED_WITH_MANUAL_REVIEW


def _try_observed_delta_event_count() -> Optional[int]:
    """Optional observe-path signal; absence of telemetry must not crash audit."""
    try:
        from services.semantic_state_precedence_adapter import get_observed_delta_events  # type: ignore

        ev = get_observed_delta_events()
        if ev is None:
            return None
        return len(list(ev))
    except Exception:
        return None


def _minimum_evidence_met_for_consumer(rows: List[Dict[str, Any]], consumer: str) -> Tuple[bool, Dict[str, Any]]:
    detail: Dict[str, Any] = {
        "consumer": str(consumer or ""),
        "row_count": len(rows),
        "non_unknown_confidence_rows": 0,
        "critical_transition_non_unknown_rows": 0,
        "observed_delta_events_count": _try_observed_delta_event_count(),
    }
    if len(rows) < _MIN_ROWS_PER_CONSUMER:
        detail["minimum_evidence_met"] = False
        return False, detail
    non_unknown = 0
    crit_non_unknown = 0
    for r in rows:
        if str(r.get("confidence") or "") != UNKNOWN_CONFIDENCE:
            non_unknown += 1
        if str(r.get("semantic_transition") or "") in _CRITICAL_TRANSITIONS_FOR_EVIDENCE:
            if str(r.get("confidence") or "") != UNKNOWN_CONFIDENCE:
                crit_non_unknown += 1
    detail["non_unknown_confidence_rows"] = non_unknown
    detail["critical_transition_non_unknown_rows"] = crit_non_unknown
    ok = (
        non_unknown >= _MIN_NON_UNKNOWN_CONFIDENCE_ROWS
        and crit_non_unknown >= _MIN_CRITICAL_TRANSITION_ROWS
    )
    detail["minimum_evidence_met"] = ok
    return ok, detail


def _recommended_next_action(
    rollout_state: str,
    blocked_count: int,
    minimum_evidence_met: bool,
    overall_waiver: str,
    consumer: str,
) -> str:
    c = str(consumer or "").upper()
    if rollout_state == BLOCKED:
        return "Resolve high-impact blocked transitions or narrow semantic rollout scope before enforcement."
    if rollout_state == INSUFFICIENT_EVIDENCE:
        return "Expand audited coverage, confidence, or observe-path evidence before promotion."
    if rollout_state == READY:
        return "Eligible for staged semantic-aware rollout planning subject to program governance."
    if overall_waiver == WAIVER_NOT_ALLOWED:
        return "Waiver not allowed for at least one compliance- or safety-classified blocker; remediate or reclassify."
    if c in _PASSIVE_DISPLAY_CONSUMERS:
        return "Proceed with UX-weighted rollout gates; keep action-driving surfaces on stricter profiles."
    if blocked_count > 0:
        return "Treat as waiver-eligible rollout; require explicit manual review for action-driving paths."
    return "Continue monitoring; maintain audit matrix updates as contracts evolve."


def build_consumer_rollout_gate_profiles(matrix: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    Aggregate row-level Phase 2 matrix rows into per-consumer rollout gate profiles.
    Audit-only: does not enforce or change runtime behavior.
    """
    m = matrix if matrix is not None else build_expected_vs_current_matrix()
    by_consumer: Dict[str, List[Dict[str, Any]]] = {}
    for r in m:
        k = str(r.get("consumer") or "")
        by_consumer.setdefault(k, []).append(r)
    profiles: List[Dict[str, Any]] = []
    for consumer in sorted(by_consumer.keys()):
        rows = sorted(
            by_consumer[consumer],
            key=lambda x: (str(x.get("semantic_transition") or ""), str(x.get("consumer") or "")),
        )
        crit_mix = _count_by(rows, "propagation_criticality")
        highest_criticality = ""
        for tier in (SAFETY_CRITICAL, COMPLIANCE_CRITICAL, OPERATIONAL_CRITICAL, UX_CRITICAL, ANALYTICS_ONLY):
            if crit_mix.get(tier, 0) > 0:
                highest_criticality = tier
                break
        blocked_transition_count = sum(1 for r in rows if r.get("gap_classification") == BLOCKED_FOR_RUNTIME_ENFORCEMENT)
        high_risk_gap_count = sum(
            1
            for r in rows
            if r.get("gap_classification")
            in (BLOCKED_FOR_RUNTIME_ENFORCEMENT, OPERATIONAL_GAP, FRAGMENTED_BEHAVIOR)
        )
        unknown_refresh_count = sum(1 for r in rows if r.get("refresh_guarantee") == UNKNOWN_GUARANTEE)
        semantic_collapse_risk_count = sum(
            1 for r in rows if SEMANTIC_COLLAPSE_RISK in (r.get("runtime_enforcement_blocker_reasons") or [])
        )
        blocker_set: List[str] = []
        for r in rows:
            for br in r.get("runtime_enforcement_blocker_reasons") or []:
                if br not in blocker_set:
                    blocker_set.append(str(br))
        blocker_set.sort()

        waiver_entries: List[Dict[str, str]] = []
        policies: List[str] = []
        for r in rows:
            crit = str(r.get("propagation_criticality") or "")
            for br in r.get("runtime_enforcement_blocker_reasons") or []:
                pol = _waiver_policy_for_blocker(str(br), crit, consumer)
                policies.append(pol)
                waiver_entries.append({"blocker_reason": str(br), "propagation_criticality": crit, "waiver_policy": pol})
        waiver_entries.sort(key=lambda x: (x["blocker_reason"], x["propagation_criticality"], x["waiver_policy"]))
        _seen_waiver: set[Tuple[str, str, str]] = set()
        waiver_entries_deduped: List[Dict[str, str]] = []
        for e in waiver_entries:
            key = (e["blocker_reason"], e["propagation_criticality"], e["waiver_policy"])
            if key in _seen_waiver:
                continue
            _seen_waiver.add(key)
            waiver_entries_deduped.append(e)
        overall_waiver = _strictest_waiver(policies) if policies else WAIVER_ALLOWED_FOR_ANALYTICS_ONLY
        waiver_eligible = overall_waiver != WAIVER_NOT_ALLOWED

        high_impact_blocked = any(
            r.get("gap_classification") == BLOCKED_FOR_RUNTIME_ENFORCEMENT
            and str(r.get("propagation_criticality") or "") in _HIGH_IMPACT_CRITICALITY
            for r in rows
        )

        minimum_evidence_met, evidence_detail = _minimum_evidence_met_for_consumer(rows, consumer)

        rollout_state = CONDITIONAL
        if high_impact_blocked:
            if str(consumer) in _PASSIVE_DISPLAY_CONSUMERS:
                rollout_state = CONDITIONAL
            else:
                rollout_state = BLOCKED
        elif not minimum_evidence_met:
            rollout_state = INSUFFICIENT_EVIDENCE
        elif (
            blocked_transition_count == 0
            and high_risk_gap_count == 0
            and unknown_refresh_count <= 1
            and semantic_collapse_risk_count == 0
            and minimum_evidence_met
        ):
            rollout_state = READY

        supporting_state: Optional[str] = None
        if consumer in _OBSERVE_INSTRUMENTED_CONSUMERS and consumer != "CACHE_INVALIDATION_REFRESH":
            supporting_state = OBSERVE_ONLY
        if consumer == "CACHE_INVALIDATION_REFRESH":
            supporting_state = NOT_ELIGIBLE

        profile = {
            "consumer": consumer,
            "rollout_state": rollout_state,
            "supporting_rollout_state": supporting_state,
            "criticality_mix": crit_mix,
            "highest_criticality": highest_criticality,
            "blocked_transition_count": blocked_transition_count,
            "high_risk_gap_count": high_risk_gap_count,
            "unknown_refresh_count": unknown_refresh_count,
            "semantic_collapse_risk_count": semantic_collapse_risk_count,
            "minimum_evidence_met": minimum_evidence_met,
            "minimum_evidence_detail": evidence_detail,
            "waiver_eligible": waiver_eligible,
            "overall_waiver_policy": overall_waiver,
            "waiver_policy_by_blocker": waiver_entries_deduped,
            "blocker_reasons": blocker_set,
            "recommended_next_action": _recommended_next_action(
                rollout_state, blocked_transition_count, minimum_evidence_met, overall_waiver, consumer
            ),
        }
        profiles.append(profile)
    return profiles


def _group_profiles_by_rollout_state(profiles: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for p in profiles:
        st = str(p.get("rollout_state") or "")
        out.setdefault(st, []).append(str(p.get("consumer") or ""))
    for k in out:
        out[k].sort()
    return dict(sorted(out.items()))


def _profiles_by_highest_criticality(profiles: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for p in profiles:
        tier = str(p.get("highest_criticality") or "")
        out.setdefault(tier, []).append(str(p.get("consumer") or ""))
    for k in out:
        out[k].sort()
    return dict(sorted(out.items()))


def _blockers_by_consumer(profiles: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for p in profiles:
        c = str(p.get("consumer") or "")
        out[c] = list(p.get("blocker_reasons") or [])
    return dict(sorted(out.items()))


def _waiver_eligibility_by_consumer(profiles: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for p in profiles:
        c = str(p.get("consumer") or "")
        out[c] = {
            "waiver_eligible": bool(p.get("waiver_eligible")),
            "overall_waiver_policy": str(p.get("overall_waiver_policy") or ""),
        }
    return dict(sorted(out.items()))


def _consumer_rollout_safety_score(profile: Dict[str, Any]) -> int:
    score = 100
    st = str(profile.get("rollout_state") or "")
    if st == BLOCKED:
        score -= 80
    elif st == INSUFFICIENT_EVIDENCE:
        score -= 40
    elif st == CONDITIONAL:
        score -= 15
    score -= 4 * int(profile.get("blocked_transition_count") or 0)
    score -= 2 * int(profile.get("high_risk_gap_count") or 0)
    score -= 3 * int(profile.get("unknown_refresh_count") or 0)
    score -= 5 * int(profile.get("semantic_collapse_risk_count") or 0)
    if profile.get("minimum_evidence_met") is not True:
        score -= 25
    if profile.get("waiver_eligible") is not True:
        score -= 10
    return score


def build_trigger_propagation_audit_phase3_snapshot() -> Dict[str, Any]:
    matrix = build_expected_vs_current_matrix()
    profiles = build_consumer_rollout_gate_profiles(matrix)
    by_state = _group_profiles_by_rollout_state(profiles)
    by_crit = _profiles_by_highest_criticality(profiles)
    blocked_consumers = sorted(
        str(p.get("consumer") or "") for p in profiles if p.get("rollout_state") == BLOCKED
    )
    insufficient = sorted(
        str(p.get("consumer") or "") for p in profiles if p.get("rollout_state") == INSUFFICIENT_EVIDENCE
    )
    ready_consumers = sorted(str(p.get("consumer") or "") for p in profiles if p.get("rollout_state") == READY)
    conditional_consumers = sorted(
        str(p.get("consumer") or "") for p in profiles if p.get("rollout_state") == CONDITIONAL
    )
    ranked = sorted(
        profiles,
        key=lambda p: (
            -_consumer_rollout_safety_score(p),
            str(p.get("consumer") or ""),
        ),
    )
    safest_candidates = [
        {
            "consumer": p.get("consumer"),
            "rollout_state": p.get("rollout_state"),
            "score": _consumer_rollout_safety_score(p),
        }
        for p in ranked
    ]
    waiver_summary = _count_by([{"p": p.get("overall_waiver_policy")} for p in profiles], "p")
    blocked_detail = [
        {
            "consumer": p.get("consumer"),
            "blocker_reasons": p.get("blocker_reasons"),
            "rollout_state": p.get("rollout_state"),
        }
        for p in profiles
        if p.get("rollout_state") == BLOCKED
    ]
    return {
        "phase": "Trigger Propagation Completeness Audit Phase 3",
        "scope": "consumer-level rollout gate profiles",
        "runtime_behavior_changed": False,
        "audit_only": True,
        "rollout_gate_states": [
            READY,
            CONDITIONAL,
            BLOCKED,
            INSUFFICIENT_EVIDENCE,
            OBSERVE_ONLY,
            NOT_ELIGIBLE,
        ],
        "waiver_policies": list(_WAIVER_STRICTNESS_ORDER),
        "minimum_evidence_thresholds": {
            "min_rows_per_consumer": _MIN_ROWS_PER_CONSUMER,
            "min_non_unknown_confidence_rows": _MIN_NON_UNKNOWN_CONFIDENCE_ROWS,
            "min_critical_transition_non_unknown_rows": _MIN_CRITICAL_TRANSITION_ROWS,
            "critical_transitions_for_evidence": sorted(_CRITICAL_TRANSITIONS_FOR_EVIDENCE),
            "observe_instrumented_consumers_optional_delta": sorted(_OBSERVE_INSTRUMENTED_CONSUMERS),
        },
        "consumer_rollout_profiles": profiles,
        "grouped_summaries": {
            "consumers_by_rollout_state": by_state,
            "consumers_by_highest_criticality": by_crit,
            "blockers_by_consumer": _blockers_by_consumer(profiles),
            "waiver_eligibility_by_consumer": _waiver_eligibility_by_consumer(profiles),
            "safest_rollout_candidates": safest_candidates,
            "consumers_blocked_from_semantic_aware_rollout": blocked_consumers,
            "consumers_insufficient_evidence": insufficient,
            "consumers_ready": ready_consumers,
            "consumers_conditional": conditional_consumers,
        },
        "waiver_policy_summary": waiver_summary,
        "blocked_consumers_detail": blocked_detail,
        "matrix_row_count": len(matrix),
        "remaining_state_model_limitation": _STATE_MODEL_LIMITATION,
        "remaining_runtime_convergence_limitation": _RUNTIME_CONVERGENCE_LIMITATION,
        "non_blocking": True,
    }


def write_trigger_propagation_audit_phase3_json(target_path: Optional[Path] = None) -> Path:
    """Write Phase 3 JSON artifact for audit records (does not change runtime behavior)."""
    snapshot = build_trigger_propagation_audit_phase3_snapshot()
    base = Path(__file__).resolve().parents[1]
    path = target_path or (base / "docs" / "audit" / "TRIGGER_PROPAGATION_COMPLETENESS_PHASE3.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
