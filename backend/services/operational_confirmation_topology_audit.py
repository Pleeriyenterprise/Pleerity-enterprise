from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from services.trigger_propagation_audit import (
    ANALYTICS_ONLY,
    BLOCKED_FOR_RUNTIME_ENFORCEMENT,
    COMPLIANCE_CRITICAL,
    CONSUMERS,
    DERIVED_ON_READ,
    EVENTUAL_RECALC,
    FRAGMENTED_PROPAGATION,
    HIGH_CONFIDENCE,
    LIVE_READ_PROJECTION,
    LOW_CONFIDENCE,
    MEDIUM_CONFIDENCE,
    NO_KNOWN_PROPAGATION,
    NO_OPERATIONAL_FOLLOWTHROUGH,
    OPERATIONAL_CRITICAL,
    PARTIAL_PROPAGATION,
    PERIODIC_JOB,
    SAFETY_CRITICAL,
    SEMANTIC_COLLAPSE_RISK,
    SEMANTIC_TRANSITIONS,
    TASK_REBUILD as REACTION_TASK_REBUILD,
    UNKNOWN_CONFIDENCE,
    UNKNOWN_GUARANTEE,
    UX_CRITICAL,
    build_expected_vs_current_matrix,
)

# --- Part A: confirmation domains (governance only) ---
INTENT_INITIATOR = "INTENT_INITIATOR"
OPERATIONAL_DISPATCH = "OPERATIONAL_DISPATCH"
USER_ACTION_CONFIRMATION = "USER_ACTION_CONFIRMATION"
HUMAN_REVIEW_CONFIRMATION = "HUMAN_REVIEW_CONFIRMATION"
DOCUMENT_CONFIRMATION = "DOCUMENT_CONFIRMATION"
EXTERNAL_CONFIRMATION = "EXTERNAL_CONFIRMATION"
SYSTEM_RECALC_CONFIRMATION = "SYSTEM_RECALC_CONFIRMATION"
REMINDER_CONFIRMATION = "REMINDER_CONFIRMATION"
ESCALATION_CONFIRMATION = "ESCALATION_CONFIRMATION"
NO_CONFIRMATION_OWNER = "NO_CONFIRMATION_OWNER"
UNKNOWN_CONFIRMATION = "UNKNOWN_CONFIRMATION"

# Part C: confirmation quality
DETERMINISTIC_CONFIRMATION = "DETERMINISTIC_CONFIRMATION"
CONFIRMATION_WITH_REVIEW = "CONFIRMATION_WITH_REVIEW"
INFERRED_CONFIRMATION = "INFERRED_CONFIRMATION"
PERIODIC_CONFIRMATION = "PERIODIC_CONFIRMATION"
HUMAN_DEPENDENT_CONFIRMATION = "HUMAN_DEPENDENT_CONFIRMATION"
FRAGMENTED_CONFIRMATION = "FRAGMENTED_CONFIRMATION"
NO_CONFIRMATION_PATH = "NO_CONFIRMATION_PATH"
UNKNOWN_CONFIRMATION_QUALITY = "UNKNOWN_CONFIRMATION_QUALITY"

# Part D: confirmation failure modes
INTENT_WITHOUT_CONFIRMATION = "INTENT_WITHOUT_CONFIRMATION"
CONFIRMATION_WITHOUT_CLOSURE = "CONFIRMATION_WITHOUT_CLOSURE"
CLOSURE_WITHOUT_CONFIRMATION = "CLOSURE_WITHOUT_CONFIRMATION"
PERIODIC_STALE_CONFIRMATION = "PERIODIC_STALE_CONFIRMATION"
NO_RETRY_OWNER = "NO_RETRY_OWNER"
NO_STALE_STATE_DETECTION = "NO_STALE_STATE_DETECTION"
HUMAN_CONFIRMATION_GAP = "HUMAN_CONFIRMATION_GAP"
ESCALATION_WITHOUT_ACKNOWLEDGEMENT = "ESCALATION_WITHOUT_ACKNOWLEDGEMENT"
VISIBILITY_ONLY_CONFIRMATION = "VISIBILITY_ONLY_CONFIRMATION"
UNKNOWN_CONFIRMATION_BOUNDARY = "UNKNOWN_CONFIRMATION_BOUNDARY"

# Part G: confirmation risk
LOW_CONFIRMATION_RISK = "LOW_CONFIRMATION_RISK"
MODERATE_CONFIRMATION_RISK = "MODERATE_CONFIRMATION_RISK"
HIGH_CONFIRMATION_RISK = "HIGH_CONFIRMATION_RISK"
CRITICAL_CONFIRMATION_RISK = "CRITICAL_CONFIRMATION_RISK"

# --- Phase 2: confirmation criticality (governance) ---
SAFETY_CONFIRMATION_CRITICAL = "SAFETY_CONFIRMATION_CRITICAL"
COMPLIANCE_CONFIRMATION_CRITICAL = "COMPLIANCE_CONFIRMATION_CRITICAL"
OPERATIONAL_CONFIRMATION_CRITICAL = "OPERATIONAL_CONFIRMATION_CRITICAL"
UX_CONFIRMATION_ONLY = "UX_CONFIRMATION_ONLY"
ANALYTICS_CONFIRMATION_ONLY = "ANALYTICS_CONFIRMATION_ONLY"

# Phase 2: confirmation freshness expectations (separate from quality labels where both use strings)
IMMEDIATE_CONFIRMATION = "IMMEDIATE_CONFIRMATION"
NEAR_REAL_TIME_CONFIRMATION = "NEAR_REAL_TIME_CONFIRMATION"
EVENTUAL_CONFIRMATION = "EVENTUAL_CONFIRMATION"
PERIODIC_CONFIRMATION_FRESHNESS = "PERIODIC_CONFIRMATION"
BEST_EFFORT_CONFIRMATION = "BEST_EFFORT_CONFIRMATION"
UNKNOWN_CONFIRMATION_FRESHNESS = "UNKNOWN_CONFIRMATION_FRESHNESS"

# Phase 2: acknowledgement guarantee (current/expected governance)
DETERMINISTIC_ACKNOWLEDGEMENT = "DETERMINISTIC_ACKNOWLEDGEMENT"
LIKELY_ACKNOWLEDGEMENT = "LIKELY_ACKNOWLEDGEMENT"
INFERRED_ACKNOWLEDGEMENT = "INFERRED_ACKNOWLEDGEMENT"
FRAGMENTED_ACKNOWLEDGEMENT = "FRAGMENTED_ACKNOWLEDGEMENT"
UNKNOWN_ACKNOWLEDGEMENT = "UNKNOWN_ACKNOWLEDGEMENT"

# Phase 2: expected-vs-current gap classifications
CONFIRMATION_CONTRACT_SATISFIED = "CONFIRMATION_CONTRACT_SATISFIED"
CONFIRMATION_PARTIALLY_SATISFIED = "CONFIRMATION_PARTIALLY_SATISFIED"
CONFIRMATION_UNDER_GOVERNED = "CONFIRMATION_UNDER_GOVERNED"
CONFIRMATION_FRAGMENTED = "CONFIRMATION_FRAGMENTED"
STALE_CONFIRMATION_RISK = "STALE_CONFIRMATION_RISK"
ACKNOWLEDGEMENT_GAP = "ACKNOWLEDGEMENT_GAP"
RETRY_OWNERSHIP_GAP = "RETRY_OWNERSHIP_GAP"
BLOCKED_FOR_RUNTIME_CONFIRMATION_ENFORCEMENT = "BLOCKED_FOR_RUNTIME_CONFIRMATION_ENFORCEMENT"

# Phase 2: promotion blockers (governance; does not enforce at runtime)
NO_ACKNOWLEDGEMENT_OWNER = "NO_ACKNOWLEDGEMENT_OWNER"
NO_STALE_CONFIRMATION_DETECTION = "NO_STALE_CONFIRMATION_DETECTION"
PERIODIC_ONLY_CONFIRMATION = "PERIODIC_ONLY_CONFIRMATION"
FRAGMENTED_CONFIRMATION_CHAIN = "FRAGMENTED_CONFIRMATION_CHAIN"
HUMAN_ONLY_CONFIRMATION = "HUMAN_ONLY_CONFIRMATION"
NO_RETRY_OR_ESCALATION_OWNER = "NO_RETRY_OR_ESCALATION_OWNER"
INFERRED_CLOSURE_ONLY = "INFERRED_CLOSURE_ONLY"
SEMANTIC_CONFIRMATION_COLLAPSE_RISK = "SEMANTIC_CONFIRMATION_COLLAPSE_RISK"

# --- Remediation audit (Phase 1): planning classifications only; no runtime changes ---
CODE_REMEDIATION = "CODE_REMEDIATION"
ORCHESTRATION_REMEDIATION = "ORCHESTRATION_REMEDIATION"
EVENT_ARCHITECTURE_REMEDIATION = "EVENT_ARCHITECTURE_REMEDIATION"
PRODUCT_POLICY_REMEDIATION = "PRODUCT_POLICY_REMEDIATION"
HUMAN_PROCESS_REMEDIATION = "HUMAN_PROCESS_REMEDIATION"
REPORTING_SEMANTIC_REMEDIATION = "REPORTING_SEMANTIC_REMEDIATION"
CACHE_INVALIDATION_REMEDIATION = "CACHE_INVALIDATION_REMEDIATION"
OBSERVABILITY_REMEDIATION = "OBSERVABILITY_REMEDIATION"
ACCEPTABLE_RISK = "ACCEPTABLE_RISK"
UNKNOWN_REMEDIATION = "UNKNOWN_REMEDIATION"

BACKEND_RUNTIME_OWNER = "BACKEND_RUNTIME_OWNER"
WORKFLOW_GOVERNANCE_OWNER = "WORKFLOW_GOVERNANCE_OWNER"
SEMANTIC_TRUTH_OWNER = "SEMANTIC_TRUTH_OWNER"
PRODUCT_POLICY_OWNER = "PRODUCT_POLICY_OWNER"
OPERATIONS_PROCESS_OWNER = "OPERATIONS_PROCESS_OWNER"
REPORTING_OWNER = "REPORTING_OWNER"
PLATFORM_INFRASTRUCTURE_OWNER = "PLATFORM_INFRASTRUCTURE_OWNER"
SHARED_OWNERSHIP = "SHARED_OWNERSHIP"
UNKNOWN_OWNER = "UNKNOWN_OWNER"

REMEDIATION_OWNER_CONFIDENCE_HIGH = "HIGH"
REMEDIATION_OWNER_CONFIDENCE_MEDIUM = "MEDIUM"
REMEDIATION_OWNER_CONFIDENCE_LOW = "LOW"

CRITICAL_IMMEDIATE = "CRITICAL_IMMEDIATE"
HIGH_PRIORITY = "HIGH_PRIORITY"
MEDIUM_PRIORITY = "MEDIUM_PRIORITY"
LOW_PRIORITY = "LOW_PRIORITY"
DEFERRED = "DEFERRED"
MONITOR_ONLY = "MONITOR_ONLY"

HARD_BLOCKER = "HARD_BLOCKER"
SOFT_BLOCKER = "SOFT_BLOCKER"
OBSERVATION_ONLY = "OBSERVATION_ONLY"
NON_BLOCKING = "NON_BLOCKING"

ACCEPTABLE_FOR_PASSIVE_DISPLAY = "ACCEPTABLE_FOR_PASSIVE_DISPLAY"
ACCEPTABLE_FOR_ANALYTICS = "ACCEPTABLE_FOR_ANALYTICS"
ACCEPTABLE_WITH_HUMAN_REVIEW = "ACCEPTABLE_WITH_HUMAN_REVIEW"
UNACCEPTABLE_FOR_RUNTIME_ENFORCEMENT = "UNACCEPTABLE_FOR_RUNTIME_ENFORCEMENT"
UNACCEPTABLE_FOR_OPERATIONAL_AUTOMATION = "UNACCEPTABLE_FOR_OPERATIONAL_AUTOMATION"
UNKNOWN_ACCEPTABILITY = "UNKNOWN_ACCEPTABILITY"

STATE_MODEL_DEBT = "STATE_MODEL_DEBT"
PROPAGATION_FRAGMENTATION = "PROPAGATION_FRAGMENTATION"
ACKNOWLEDGEMENT_GAP_DEBT = "ACKNOWLEDGEMENT_GAP_DEBT"
STALE_STATE_DETECTION_DEBT = "STALE_STATE_DETECTION_DEBT"
ORCHESTRATION_DEBT = "ORCHESTRATION_DEBT"
CACHE_REFRESH_DEBT = "CACHE_REFRESH_DEBT"
SEMANTIC_COLLAPSE_DEBT = "SEMANTIC_COLLAPSE_DEBT"
REPORTING_COLLAPSE_DEBT = "REPORTING_COLLAPSE_DEBT"
PROCESS_GOVERNANCE_DEBT = "PROCESS_GOVERNANCE_DEBT"
OBSERVABILITY_DEBT = "OBSERVABILITY_DEBT"
UNKNOWN_ROOT_CAUSE = "UNKNOWN_ROOT_CAUSE"

# --- Remediation triage Phase 2: sequencing & batching (audit-only) ---
SAFE_ENGINEERING_FIX = "SAFE_ENGINEERING_FIX"
RUNTIME_ARCHITECTURE_REQUIRED = "RUNTIME_ARCHITECTURE_REQUIRED"
EVENT_MODEL_REQUIRED = "EVENT_MODEL_REQUIRED"
PROCESS_GOVERNANCE_REQUIRED = "PROCESS_GOVERNANCE_REQUIRED"
PRODUCT_POLICY_REQUIRED = "PRODUCT_POLICY_REQUIRED"
OBSERVABILITY_FIRST = "OBSERVABILITY_FIRST"
CACHE_GOVERNANCE_REQUIRED = "CACHE_GOVERNANCE_REQUIRED"
REPORTING_SEMANTIC_ALIGNMENT = "REPORTING_SEMANTIC_ALIGNMENT"
DEFER_UNTIL_STATE_MODEL_REFINEMENT = "DEFER_UNTIL_STATE_MODEL_REFINEMENT"
DO_NOT_IMPLEMENT_YET = "DO_NOT_IMPLEMENT_YET"

READY_FOR_IMPLEMENTATION = "READY_FOR_IMPLEMENTATION"
READY_WITH_GOVERNANCE_REVIEW = "READY_WITH_GOVERNANCE_REVIEW"
REQUIRES_RUNTIME_DESIGN = "REQUIRES_RUNTIME_DESIGN"
REQUIRES_PRODUCT_DECISION = "REQUIRES_PRODUCT_DECISION"
REQUIRES_PROCESS_DESIGN = "REQUIRES_PROCESS_DESIGN"
REQUIRES_OBSERVABILITY_FIRST = "REQUIRES_OBSERVABILITY_FIRST"
REQUIRES_STATE_MODEL_REFINEMENT = "REQUIRES_STATE_MODEL_REFINEMENT"
NOT_SAFE_TO_IMPLEMENT = "NOT_SAFE_TO_IMPLEMENT"

DEPENDENCY_NONE = "DEPENDENCY_NONE"
DEPENDENCY_RUNTIME_ARCHITECTURE = "DEPENDENCY_RUNTIME_ARCHITECTURE"
DEPENDENCY_EVENT_ORCHESTRATION = "DEPENDENCY_EVENT_ORCHESTRATION"
DEPENDENCY_ACKNOWLEDGEMENT_MODEL = "DEPENDENCY_ACKNOWLEDGEMENT_MODEL"
DEPENDENCY_STATE_MODEL = "DEPENDENCY_STATE_MODEL"
DEPENDENCY_PRODUCT_POLICY = "DEPENDENCY_PRODUCT_POLICY"
DEPENDENCY_OPERATIONS_PROCESS = "DEPENDENCY_OPERATIONS_PROCESS"
DEPENDENCY_REPORTING_SEMANTICS = "DEPENDENCY_REPORTING_SEMANTICS"
DEPENDENCY_CACHE_INVALIDATION = "DEPENDENCY_CACHE_INVALIDATION"
DEPENDENCY_OBSERVABILITY = "DEPENDENCY_OBSERVABILITY"
DEPENDENCY_UNKNOWN = "DEPENDENCY_UNKNOWN"

FIRST_WAVE_ELIGIBLE = "FIRST_WAVE_ELIGIBLE"
FIRST_WAVE_WITH_REVIEW = "FIRST_WAVE_WITH_REVIEW"
SECOND_WAVE_ONLY = "SECOND_WAVE_ONLY"
BLOCKED_FROM_IMPLEMENTATION = "BLOCKED_FROM_IMPLEMENTATION"
OBSERVE_ONLY_FOR_NOW = "OBSERVE_ONLY_FOR_NOW"

UNSAFE_RUNTIME_FRAGMENTATION = "UNSAFE_RUNTIME_FRAGMENTATION"
UNSAFE_ACKNOWLEDGEMENT_COLLAPSE = "UNSAFE_ACKNOWLEDGEMENT_COLLAPSE"
UNSAFE_STALE_STATE_GAP = "UNSAFE_STALE_STATE_GAP"
UNSAFE_SEMANTIC_COLLAPSE = "UNSAFE_SEMANTIC_COLLAPSE"
UNSAFE_EVENT_DEPENDENCY = "UNSAFE_EVENT_DEPENDENCY"
UNSAFE_STATE_MODEL_DEPENDENCY = "UNSAFE_STATE_MODEL_DEPENDENCY"
UNSAFE_UNKNOWN_BOUNDARY = "UNSAFE_UNKNOWN_BOUNDARY"
UNSAFE_PROCESS_DEPENDENCY = "UNSAFE_PROCESS_DEPENDENCY"

BATCH_SAFE_READ_PATHS = "BATCH_SAFE_READ_PATHS"
BATCH_OBSERVABILITY_FIRST = "BATCH_OBSERVABILITY_FIRST"
BATCH_ACKNOWLEDGEMENT_GOVERNANCE = "BATCH_ACKNOWLEDGEMENT_GOVERNANCE"
BATCH_STALE_STATE_DETECTION = "BATCH_STALE_STATE_DETECTION"
BATCH_RUNTIME_ORCHESTRATION = "BATCH_RUNTIME_ORCHESTRATION"
BATCH_CACHE_REFRESH_GOVERNANCE = "BATCH_CACHE_REFRESH_GOVERNANCE"
BATCH_REPORTING_ALIGNMENT = "BATCH_REPORTING_ALIGNMENT"
BATCH_PROCESS_AND_POLICY = "BATCH_PROCESS_AND_POLICY"
BATCH_STATE_MODEL_REFINEMENT = "BATCH_STATE_MODEL_REFINEMENT"

_PASSIVE_DISPLAY_CONSUMERS_REMEDIATION = frozenset(
    {
        "COMMAND_CENTER",
        "PROPERTY_SUMMARY",
        "DASHBOARD_SUMMARY",
        "TODAY_VIEW",
        "REQUIREMENT_LIST",
    }
)

_URGENCY_ORDER = (MONITOR_ONLY, DEFERRED, LOW_PRIORITY, MEDIUM_PRIORITY, HIGH_PRIORITY, CRITICAL_IMMEDIATE)

_STATE_MODEL_LIMITATION = (
    "Confirmation topology is synthesized from the propagation audit matrix; it does not observe "
    "actual acknowledgement payloads, webhook receipts, or human attestation records."
)
_RUNTIME_CONVERGENCE_LIMITATION = (
    "Inferred vs deterministic confirmation cannot be proven without runtime traces; audit uses "
    "declared propagation contracts only."
)

_RISK_ORDER = (
    LOW_CONFIRMATION_RISK,
    MODERATE_CONFIRMATION_RISK,
    HIGH_CONFIRMATION_RISK,
    CRITICAL_CONFIRMATION_RISK,
)

_CONFIRM_HANDOFF_BASE: Dict[str, List[str]] = {
    "REQUIREMENT_LIST": [
        "semantic_transition",
        "requirement_evidence_authority",
        "document_confirmation",
        "read_projection_visibility",
    ],
    "COMMAND_CENTER": [
        "semantic_transition",
        "unified_tasks_projection",
        "user_visibility_only",
        "no_explicit_operational_ack",
    ],
    "TODAY_VIEW": [
        "semantic_transition",
        "priority_stream",
        "task_rebuild_on_fetch",
        "inferred_state_alignment",
    ],
    "UNIFIED_TASKS": [
        "semantic_transition",
        "unified_tasks_service",
        "user_action_surface",
        "implicit_closure_on_task_change",
    ],
    "PRIORITY_ACTIONS": [
        "semantic_transition",
        "priority_actions_surface",
        "operational_intent",
        "missing_guaranteed_ack",
    ],
    "PROPERTY_SUMMARY": [
        "semantic_transition",
        "read_composition",
        "visibility_only",
    ],
    "DASHBOARD_SUMMARY": [
        "semantic_transition",
        "dashboard_read_composition",
        "visibility_only",
    ],
    "REPORT_EXPORT": [
        "semantic_transition",
        "reporting_projection",
        "export_time_derivation",
        "document_row_materialization",
    ],
    "PORTFOLIO_SCORE": [
        "semantic_transition",
        "score_regeneration",
        "system_recalc_confirmation",
    ],
    "SCORE_DRIVERS": [
        "semantic_transition",
        "driver_shaping",
        "system_recalc_confirmation",
    ],
    "REMINDER_ENGINE": [
        "semantic_transition",
        "reminder_truth_service",
        "periodic_reminder_job",
        "notification_dispatch",
        "inferred_closure",
    ],
    "NOTIFICATION_EMAIL_PATHS": [
        "semantic_transition",
        "template_runtime",
        "email_dispatch",
        "no_delivery_ack_in_contract",
    ],
    "SLA_ESCALATION_PATHS": [
        "semantic_transition",
        "sla_watchdog",
        "periodic_monitoring",
        "escalation_without_explicit_ack",
    ],
    "CACHE_INVALIDATION_REFRESH": [
        "semantic_transition",
        "unknown_invalidation_boundary",
        "read_recomposition",
    ],
    "REGENERATION_RECALC_PATHS": [
        "semantic_transition",
        "recalc_queue",
        "scheduled_worker",
        "lazy_backfill_confirmation",
    ],
}


def _confirmation_handoff_chain(consumer: str, transition: str) -> Tuple[List[str], int, bool, bool, bool, bool]:
    c = str(consumer or "").upper()
    chain = list(_CONFIRM_HANDOFF_BASE.get(c, ["unknown_confirmation_boundary"]))
    t = str(transition or "").upper()
    if t in ("EXPIRY_REVIEW_REQUIRED", "OPERATIONALLY_OPEN", "ASSESSMENT_FOLLOWUP_REQUIRED"):
        if c in ("REMINDER_ENGINE", "NOTIFICATION_EMAIL_PATHS", "SLA_ESCALATION_PATHS"):
            chain = chain + ["human_or_operational_followup_checkpoint"]
    handoff_count = max(0, len(chain) - 1)
    undefined_boundary = c == "CACHE_INVALIDATION_REFRESH" or "unknown" in " ".join(chain).lower()
    human_dep = "human" in " ".join(chain).lower() or c in ("PRIORITY_ACTIONS", "UNIFIED_TASKS", "TODAY_VIEW")
    periodic_only = c in ("REMINDER_ENGINE", "SLA_ESCALATION_PATHS", "NOTIFICATION_EMAIL_PATHS") or "periodic" in " ".join(
        chain
    ).lower()
    stale_window = periodic_only or undefined_boundary or c == "CACHE_INVALIDATION_REFRESH"
    return chain, handoff_count, undefined_boundary, human_dep, periodic_only, stale_window


def _intent_owner(consumer: str, transition: str) -> str:
    c = str(consumer or "").upper()
    if c == "REMINDER_ENGINE":
        return REMINDER_CONFIRMATION
    if c == "SLA_ESCALATION_PATHS":
        return ESCALATION_CONFIRMATION
    if c == "NOTIFICATION_EMAIL_PATHS":
        return REMINDER_CONFIRMATION
    if c == "CACHE_INVALIDATION_REFRESH":
        return UNKNOWN_CONFIRMATION
    return INTENT_INITIATOR


def _dispatch_owner(consumer: str, reaction: str) -> str:
    c = str(consumer or "").upper()
    r = str(reaction or "")
    if c == "CACHE_INVALIDATION_REFRESH":
        return UNKNOWN_CONFIRMATION
    if c == "NOTIFICATION_EMAIL_PATHS":
        return OPERATIONAL_DISPATCH
    if c == "REMINDER_ENGINE":
        return REMINDER_CONFIRMATION
    if c == "SLA_ESCALATION_PATHS":
        return ESCALATION_CONFIRMATION
    if c in ("UNIFIED_TASKS", "TODAY_VIEW", "PRIORITY_ACTIONS"):
        return OPERATIONAL_DISPATCH
    if c == "REPORT_EXPORT":
        return OPERATIONAL_DISPATCH
    if c in ("PORTFOLIO_SCORE", "SCORE_DRIVERS", "REGENERATION_RECALC_PATHS"):
        return SYSTEM_RECALC_CONFIRMATION
    if r == PERIODIC_JOB:
        return OPERATIONAL_DISPATCH
    if r == REACTION_TASK_REBUILD:
        return OPERATIONAL_DISPATCH
    return NO_CONFIRMATION_OWNER


def _confirmation_owner(consumer: str, transition: str, ptype: str) -> str:
    c = str(consumer or "").upper()
    t = str(transition or "").upper()
    if c == "CACHE_INVALIDATION_REFRESH":
        return UNKNOWN_CONFIRMATION
    if c in ("PORTFOLIO_SCORE", "SCORE_DRIVERS", "REGENERATION_RECALC_PATHS"):
        return SYSTEM_RECALC_CONFIRMATION
    if c == "REPORT_EXPORT":
        return DOCUMENT_CONFIRMATION
    if c == "REQUIREMENT_LIST":
        return DOCUMENT_CONFIRMATION
    if c == "REMINDER_ENGINE":
        return REMINDER_CONFIRMATION
    if c == "NOTIFICATION_EMAIL_PATHS":
        return REMINDER_CONFIRMATION
    if c == "SLA_ESCALATION_PATHS":
        return ESCALATION_CONFIRMATION
    if c in ("UNIFIED_TASKS", "PRIORITY_ACTIONS", "TODAY_VIEW"):
        return USER_ACTION_CONFIRMATION
    if ptype == DERIVED_ON_READ and c in ("COMMAND_CENTER", "PROPERTY_SUMMARY", "DASHBOARD_SUMMARY"):
        return NO_CONFIRMATION_OWNER
    return NO_CONFIRMATION_OWNER


def _closure_owner(consumer: str, confirmation_owner: str, follow: bool, expected: bool) -> str:
    c = str(consumer or "").upper()
    if confirmation_owner == DOCUMENT_CONFIRMATION:
        return DOCUMENT_CONFIRMATION
    if confirmation_owner == SYSTEM_RECALC_CONFIRMATION:
        return SYSTEM_RECALC_CONFIRMATION
    if confirmation_owner == USER_ACTION_CONFIRMATION:
        return USER_ACTION_CONFIRMATION
    if confirmation_owner == REMINDER_CONFIRMATION:
        return REMINDER_CONFIRMATION
    if confirmation_owner == ESCALATION_CONFIRMATION:
        return ESCALATION_CONFIRMATION
    if expected and not follow:
        return HUMAN_REVIEW_CONFIRMATION
    if c in ("COMMAND_CENTER", "PROPERTY_SUMMARY", "DASHBOARD_SUMMARY"):
        return NO_CONFIRMATION_OWNER
    return NO_CONFIRMATION_OWNER


def _stale_state_detection_owner(consumer: str, reaction: str, refresh_g: str) -> str:
    c = str(consumer or "").upper()
    r = str(reaction or "")
    if c in ("PORTFOLIO_SCORE", "SCORE_DRIVERS", "REGENERATION_RECALC_PATHS"):
        return SYSTEM_RECALC_CONFIRMATION
    if c == "SLA_ESCALATION_PATHS":
        return ESCALATION_CONFIRMATION
    if c == "REMINDER_ENGINE":
        return REMINDER_CONFIRMATION
    if refresh_g == UNKNOWN_GUARANTEE or c == "CACHE_INVALIDATION_REFRESH":
        return UNKNOWN_CONFIRMATION
    if r == LIVE_READ_PROJECTION and c in ("REQUIREMENT_LIST", "REPORT_EXPORT"):
        return DOCUMENT_CONFIRMATION
    return NO_CONFIRMATION_OWNER


def _retry_owner(consumer: str, reaction: str) -> str:
    c = str(consumer or "").upper()
    r = str(reaction or "")
    if c in ("REGENERATION_RECALC_PATHS", "PORTFOLIO_SCORE", "SCORE_DRIVERS"):
        return SYSTEM_RECALC_CONFIRMATION
    if c in ("REMINDER_ENGINE", "NOTIFICATION_EMAIL_PATHS"):
        return REMINDER_CONFIRMATION
    if c == "SLA_ESCALATION_PATHS":
        return ESCALATION_CONFIRMATION
    if r == PERIODIC_JOB:
        return OPERATIONAL_DISPATCH
    return NO_CONFIRMATION_OWNER


def _fallback_confirmation_owner(consumer: str, expected_follow: bool, follow: bool, crit: str) -> str:
    c = str(consumer or "").upper()
    if expected_follow and not follow:
        return HUMAN_REVIEW_CONFIRMATION
    if crit in (COMPLIANCE_CRITICAL, SAFETY_CRITICAL, OPERATIONAL_CRITICAL) and c in (
        "PRIORITY_ACTIONS",
        "SLA_ESCALATION_PATHS",
        "REMINDER_ENGINE",
    ):
        return HUMAN_REVIEW_CONFIRMATION
    if c in ("UNIFIED_TASKS", "TODAY_VIEW", "PRIORITY_ACTIONS"):
        return USER_ACTION_CONFIRMATION
    return NO_CONFIRMATION_OWNER


def _confirmation_dimensions(row: Dict[str, Any]) -> Dict[str, str]:
    c = str(row.get("consumer") or "")
    t = str(row.get("semantic_transition") or "")
    ptype = str(row.get("propagation_type") or "")
    reaction = str(row.get("reaction_source_of_truth") or "")
    refresh_g = str(row.get("refresh_guarantee") or "")
    crit = str(row.get("propagation_criticality") or "")
    follow = bool(row.get("operational_followthrough"))
    expected = bool(row.get("expected_operational_followthrough"))
    conf_o = _confirmation_owner(c, t, ptype)
    return {
        "intent_owner": _intent_owner(c, t),
        "dispatch_owner": _dispatch_owner(c, reaction),
        "confirmation_owner": conf_o,
        "closure_owner": _closure_owner(c, conf_o, follow, expected),
        "stale_state_detection_owner": _stale_state_detection_owner(c, reaction, refresh_g),
        "retry_owner": _retry_owner(c, reaction),
        "fallback_confirmation_owner": _fallback_confirmation_owner(c, expected, follow, crit),
    }


def _confirmation_quality(
    dims: Dict[str, str],
    row: Dict[str, Any],
    periodic_only_bridge: bool,
    human_boundary: bool,
) -> str:
    c = str(row.get("consumer") or "").upper()
    ptype = str(row.get("propagation_type") or "")
    conf = str(row.get("confidence") or "")
    follow = bool(row.get("operational_followthrough"))
    expected = bool(row.get("expected_operational_followthrough"))
    co = dims["confirmation_owner"]
    clo = dims["closure_owner"]
    stale = dims["stale_state_detection_owner"]

    if co == UNKNOWN_CONFIRMATION or ptype == NO_KNOWN_PROPAGATION:
        return UNKNOWN_CONFIRMATION_QUALITY
    if co == NO_CONFIRMATION_OWNER and clo == NO_CONFIRMATION_OWNER:
        return NO_CONFIRMATION_PATH
    if co == DOCUMENT_CONFIRMATION and ptype == DERIVED_ON_READ and conf == HIGH_CONFIDENCE:
        return DETERMINISTIC_CONFIRMATION
    if co == SYSTEM_RECALC_CONFIRMATION and ptype == EVENTUAL_RECALC:
        return CONFIRMATION_WITH_REVIEW
    if periodic_only_bridge:
        return PERIODIC_CONFIRMATION
    if human_boundary and dims["fallback_confirmation_owner"] == HUMAN_REVIEW_CONFIRMATION:
        return HUMAN_DEPENDENT_CONFIRMATION
    if ptype == DERIVED_ON_READ and co == NO_CONFIRMATION_OWNER:
        return INFERRED_CONFIRMATION
    if ptype in (FRAGMENTED_PROPAGATION, PARTIAL_PROPAGATION) or row.get("gap_classification") == BLOCKED_FOR_RUNTIME_ENFORCEMENT:
        return FRAGMENTED_CONFIRMATION
    if not follow and expected:
        return FRAGMENTED_CONFIRMATION
    if co == USER_ACTION_CONFIRMATION:
        return HUMAN_DEPENDENT_CONFIRMATION
    if stale == NO_CONFIRMATION_OWNER and co != DOCUMENT_CONFIRMATION:
        return INFERRED_CONFIRMATION
    return CONFIRMATION_WITH_REVIEW


def _confirmation_failure_modes(dims: Dict[str, str], row: Dict[str, Any], quality: str) -> List[str]:
    modes: List[str] = []
    c = str(row.get("consumer") or "").upper()
    crit = str(row.get("propagation_criticality") or "")
    br = list(row.get("runtime_enforcement_blocker_reasons") or [])
    follow = bool(row.get("operational_followthrough"))
    intent = dims["intent_owner"]
    conf_o = dims["confirmation_owner"]
    clo = dims["closure_owner"]
    stale = dims["stale_state_detection_owner"]
    retry = dims["retry_owner"]

    if intent not in (NO_CONFIRMATION_OWNER, UNKNOWN_CONFIRMATION) and conf_o in (NO_CONFIRMATION_OWNER, UNKNOWN_CONFIRMATION):
        modes.append(INTENT_WITHOUT_CONFIRMATION)
    if conf_o not in (NO_CONFIRMATION_OWNER, UNKNOWN_CONFIRMATION) and clo == NO_CONFIRMATION_OWNER:
        modes.append(CONFIRMATION_WITHOUT_CLOSURE)
    if clo not in (NO_CONFIRMATION_OWNER, UNKNOWN_CONFIRMATION) and conf_o == NO_CONFIRMATION_OWNER:
        modes.append(CLOSURE_WITHOUT_CONFIRMATION)
    if quality == PERIODIC_CONFIRMATION:
        modes.append(PERIODIC_STALE_CONFIRMATION)
    if retry == NO_CONFIRMATION_OWNER and c in ("NOTIFICATION_EMAIL_PATHS", "SLA_ESCALATION_PATHS", "REMINDER_ENGINE"):
        modes.append(NO_RETRY_OWNER)
    if stale in (NO_CONFIRMATION_OWNER, UNKNOWN_CONFIRMATION) and crit in (
        COMPLIANCE_CRITICAL,
        SAFETY_CRITICAL,
        OPERATIONAL_CRITICAL,
    ):
        modes.append(NO_STALE_STATE_DETECTION)
    if dims["fallback_confirmation_owner"] == HUMAN_REVIEW_CONFIRMATION and not follow:
        modes.append(HUMAN_CONFIRMATION_GAP)
    if c == "SLA_ESCALATION_PATHS" and crit in (OPERATIONAL_CRITICAL, SAFETY_CRITICAL):
        modes.append(ESCALATION_WITHOUT_ACKNOWLEDGEMENT)
    ptype = str(row.get("propagation_type") or "")
    if quality == INFERRED_CONFIRMATION and ptype == DERIVED_ON_READ:
        modes.append(VISIBILITY_ONLY_CONFIRMATION)
    if c == "CACHE_INVALIDATION_REFRESH":
        modes.append(UNKNOWN_CONFIRMATION_BOUNDARY)
    if NO_OPERATIONAL_FOLLOWTHROUGH in br:
        modes.append(INTENT_WITHOUT_CONFIRMATION)

    out: List[str] = []
    for m in modes:
        if m not in out:
            out.append(m)
    return sorted(out)


def _operational_reality_gaps(
    row: Dict[str, Any],
    dims: Dict[str, str],
    quality: str,
    periodic_only: bool,
    human_boundary: bool,
) -> Dict[str, bool]:
    follow = bool(row.get("operational_followthrough"))
    ptype = str(row.get("propagation_type") or "")
    dep = str(row.get("refresh_recalc_dependency") or "").lower()
    silent = (
        quality in (INFERRED_CONFIRMATION, PERIODIC_CONFIRMATION, NO_CONFIRMATION_PATH)
        and dims["retry_owner"] == NO_CONFIRMATION_OWNER
        and dims["stale_state_detection_owner"] in (NO_CONFIRMATION_OWNER, UNKNOWN_CONFIRMATION)
    )
    return {
        "assumes_completion_without_explicit_confirmation": quality in (INFERRED_CONFIRMATION, PERIODIC_CONFIRMATION),
        "infers_closure_from_read_projection": ptype == DERIVED_ON_READ
        and dims["confirmation_owner"] == NO_CONFIRMATION_OWNER,
        "lacks_confirmation_ownership": dims["confirmation_owner"] == NO_CONFIRMATION_OWNER,
        "lacks_stale_state_detection": dims["stale_state_detection_owner"] == NO_CONFIRMATION_OWNER,
        "depends_on_periodic_sweep": periodic_only,
        "depends_on_user_revisit": "user_refresh" in dep or "fetch" in dep,
        "depends_on_human_reconciliation": human_boundary or dims["fallback_confirmation_owner"] == HUMAN_REVIEW_CONFIRMATION,
        "operational_closure_can_silently_fail": silent or quality == FRAGMENTED_CONFIRMATION,
    }


def _bump_risk(current: str, levels: int) -> str:
    idx = _RISK_ORDER.index(current)
    return _RISK_ORDER[min(len(_RISK_ORDER) - 1, idx + levels)]


def _confirmation_risk(
    quality: str,
    failures: List[str],
    reality: Dict[str, bool],
    handoff_count: int,
    blockers: List[str],
) -> str:
    if quality == DETERMINISTIC_CONFIRMATION:
        risk = LOW_CONFIRMATION_RISK
    elif quality in (CONFIRMATION_WITH_REVIEW, INFERRED_CONFIRMATION):
        risk = MODERATE_CONFIRMATION_RISK
    elif quality in (PERIODIC_CONFIRMATION, HUMAN_DEPENDENT_CONFIRMATION):
        risk = HIGH_CONFIRMATION_RISK
    elif quality == FRAGMENTED_CONFIRMATION:
        risk = HIGH_CONFIRMATION_RISK
    elif quality == NO_CONFIRMATION_PATH:
        risk = CRITICAL_CONFIRMATION_RISK
    elif quality == UNKNOWN_CONFIRMATION_QUALITY:
        risk = CRITICAL_CONFIRMATION_RISK
    else:
        risk = MODERATE_CONFIRMATION_RISK

    if reality.get("operational_closure_can_silently_fail"):
        risk = _bump_risk(risk, 1)
    if reality.get("depends_on_periodic_sweep") and quality != DETERMINISTIC_CONFIRMATION:
        risk = _bump_risk(risk, 1)
    if len(failures) >= 3:
        risk = _bump_risk(risk, 1)
    if handoff_count >= 4:
        risk = _bump_risk(risk, 1)
    if ESCALATION_WITHOUT_ACKNOWLEDGEMENT in failures:
        risk = _bump_risk(risk, 1)
    if SEMANTIC_COLLAPSE_RISK in blockers:
        risk = CRITICAL_CONFIRMATION_RISK
    if UNKNOWN_CONFIRMATION_BOUNDARY in failures:
        risk = _bump_risk(risk, 1)
    return risk


def _risk_rank(risk: str) -> int:
    return _RISK_ORDER.index(risk) if risk in _RISK_ORDER else len(_RISK_ORDER)


def _confirmation_criticality_from_propagation(row: Dict[str, Any]) -> str:
    pc = str(row.get("propagation_criticality") or "")
    return {
        SAFETY_CRITICAL: SAFETY_CONFIRMATION_CRITICAL,
        COMPLIANCE_CRITICAL: COMPLIANCE_CONFIRMATION_CRITICAL,
        OPERATIONAL_CRITICAL: OPERATIONAL_CONFIRMATION_CRITICAL,
        UX_CRITICAL: UX_CONFIRMATION_ONLY,
        ANALYTICS_ONLY: ANALYTICS_CONFIRMATION_ONLY,
    }.get(pc, UX_CONFIRMATION_ONLY)


_PROP_EXP_TO_CONF_FRESH = {
    "IMMEDIATE": IMMEDIATE_CONFIRMATION,
    "NEAR_REAL_TIME": NEAR_REAL_TIME_CONFIRMATION,
    "EVENTUAL": EVENTUAL_CONFIRMATION,
    "PERIODIC": PERIODIC_CONFIRMATION_FRESHNESS,
    "BEST_EFFORT": BEST_EFFORT_CONFIRMATION,
    "UNKNOWN": UNKNOWN_CONFIRMATION_FRESHNESS,
}

_FRESH_RANK = {
    IMMEDIATE_CONFIRMATION: 0,
    NEAR_REAL_TIME_CONFIRMATION: 1,
    EVENTUAL_CONFIRMATION: 2,
    BEST_EFFORT_CONFIRMATION: 3,
    PERIODIC_CONFIRMATION_FRESHNESS: 4,
    UNKNOWN_CONFIRMATION_FRESHNESS: 5,
}

_QUALITY_RANK = {
    DETERMINISTIC_CONFIRMATION: 0,
    CONFIRMATION_WITH_REVIEW: 1,
    HUMAN_DEPENDENT_CONFIRMATION: 2,
    INFERRED_CONFIRMATION: 3,
    PERIODIC_CONFIRMATION: 4,
    FRAGMENTED_CONFIRMATION: 5,
    NO_CONFIRMATION_PATH: 6,
    UNKNOWN_CONFIRMATION_QUALITY: 7,
}

_ACK_RANK = {
    DETERMINISTIC_ACKNOWLEDGEMENT: 0,
    LIKELY_ACKNOWLEDGEMENT: 1,
    INFERRED_ACKNOWLEDGEMENT: 2,
    FRAGMENTED_ACKNOWLEDGEMENT: 3,
    UNKNOWN_ACKNOWLEDGEMENT: 4,
}


def _expected_confirmation_freshness_governance(consumer: str) -> str:
    c = str(consumer or "").upper()
    if c == "CACHE_INVALIDATION_REFRESH":
        return UNKNOWN_CONFIRMATION_FRESHNESS
    if c in ("PORTFOLIO_SCORE", "SCORE_DRIVERS", "REGENERATION_RECALC_PATHS"):
        return EVENTUAL_CONFIRMATION
    if c in ("REMINDER_ENGINE", "NOTIFICATION_EMAIL_PATHS", "SLA_ESCALATION_PATHS"):
        return PERIODIC_CONFIRMATION_FRESHNESS
    if c in ("DASHBOARD_SUMMARY", "PRIORITY_ACTIONS"):
        return BEST_EFFORT_CONFIRMATION
    if c in (
        "REQUIREMENT_LIST",
        "REPORT_EXPORT",
        "COMMAND_CENTER",
        "TODAY_VIEW",
        "UNIFIED_TASKS",
        "PROPERTY_SUMMARY",
    ):
        return NEAR_REAL_TIME_CONFIRMATION
    return UNKNOWN_CONFIRMATION_FRESHNESS


def _expected_confirmation_quality_governance(consumer: str, ccrit: str) -> str:
    c = str(consumer or "").upper()
    if c == "CACHE_INVALIDATION_REFRESH":
        return UNKNOWN_CONFIRMATION_QUALITY
    if c == "REQUIREMENT_LIST":
        return DETERMINISTIC_CONFIRMATION
    if c == "REPORT_EXPORT":
        return DETERMINISTIC_CONFIRMATION
    if c in ("PORTFOLIO_SCORE", "SCORE_DRIVERS", "REGENERATION_RECALC_PATHS"):
        return CONFIRMATION_WITH_REVIEW
    if c in ("REMINDER_ENGINE", "NOTIFICATION_EMAIL_PATHS", "SLA_ESCALATION_PATHS"):
        return CONFIRMATION_WITH_REVIEW
    if c in ("UNIFIED_TASKS", "PRIORITY_ACTIONS", "TODAY_VIEW"):
        if ccrit in (
            OPERATIONAL_CONFIRMATION_CRITICAL,
            SAFETY_CONFIRMATION_CRITICAL,
            COMPLIANCE_CONFIRMATION_CRITICAL,
        ):
            return CONFIRMATION_WITH_REVIEW
        return HUMAN_DEPENDENT_CONFIRMATION
    if c in ("COMMAND_CENTER", "PROPERTY_SUMMARY", "DASHBOARD_SUMMARY"):
        return INFERRED_CONFIRMATION
    return CONFIRMATION_WITH_REVIEW


def _expected_confirmation_confidence(consumer: str) -> str:
    c = str(consumer or "").upper()
    if c == "CACHE_INVALIDATION_REFRESH":
        return UNKNOWN_CONFIDENCE
    if c == "REQUIREMENT_LIST":
        return HIGH_CONFIDENCE
    if c == "REPORT_EXPORT":
        return HIGH_CONFIDENCE
    if c in ("COMMAND_CENTER", "PROPERTY_SUMMARY", "DASHBOARD_SUMMARY", "TODAY_VIEW"):
        return MEDIUM_CONFIDENCE
    if c in ("REMINDER_ENGINE", "NOTIFICATION_EMAIL_PATHS", "SLA_ESCALATION_PATHS"):
        return LOW_CONFIDENCE
    return MEDIUM_CONFIDENCE


def _expected_confirmation_flags(row: Dict[str, Any], ccrit: str, consumer: str) -> Dict[str, bool]:
    c = str(consumer or "").upper()
    t = str(row.get("semantic_transition") or "").upper()
    action_t = t in (
        "ASSESSMENT_FOLLOWUP_REQUIRED",
        "OPERATIONALLY_OPEN",
        "EXPIRY_REVIEW_REQUIRED",
        "FOLLOWUP_REQUIRED",
    )
    high_cc = ccrit in (
        SAFETY_CONFIRMATION_CRITICAL,
        COMPLIANCE_CONFIRMATION_CRITICAL,
        OPERATIONAL_CONFIRMATION_CRITICAL,
    )
    op_req = high_cc and (
        action_t
        or c
        in (
            "PRIORITY_ACTIONS",
            "SLA_ESCALATION_PATHS",
            "REMINDER_ENGINE",
            "NOTIFICATION_EMAIL_PATHS",
        )
    )
    ack_req = op_req or c in ("REMINDER_ENGINE", "NOTIFICATION_EMAIL_PATHS", "SLA_ESCALATION_PATHS", "REPORT_EXPORT")
    stale_req = high_cc
    retry_req = c in (
        "REMINDER_ENGINE",
        "NOTIFICATION_EMAIL_PATHS",
        "SLA_ESCALATION_PATHS",
        "REGENERATION_RECALC_PATHS",
        "PRIORITY_ACTIONS",
    )
    return {
        "expected_operational_confirmation_required": op_req,
        "expected_acknowledgement_required": ack_req,
        "expected_stale_detection_required": stale_req,
        "expected_retry_owner_required": retry_req,
    }


def _expected_confirmation_contract(row: Dict[str, Any]) -> Dict[str, Any]:
    ccrit = _confirmation_criticality_from_propagation(row)
    c = str(row.get("consumer") or "")
    flags = _expected_confirmation_flags(row, ccrit, c)
    return {
        "expected_confirmation_quality": _expected_confirmation_quality_governance(c, ccrit),
        "expected_confirmation_freshness": _expected_confirmation_freshness_governance(c),
        "expected_confirmation_confidence": _expected_confirmation_confidence(c),
        "confirmation_criticality": ccrit,
        **flags,
    }


def _derive_current_effective_confirmation_freshness(
    row: Dict[str, Any], periodic_b: bool, quality: str
) -> str:
    if quality == UNKNOWN_CONFIRMATION_QUALITY:
        return UNKNOWN_CONFIRMATION_FRESHNESS
    if periodic_b or quality == PERIODIC_CONFIRMATION:
        return PERIODIC_CONFIRMATION_FRESHNESS
    exp = str(row.get("expected_freshness_expectation") or "UNKNOWN")
    return _PROP_EXP_TO_CONF_FRESH.get(exp, UNKNOWN_CONFIRMATION_FRESHNESS)


def _acknowledgement_guarantee_current(quality: str) -> str:
    if quality == DETERMINISTIC_CONFIRMATION:
        return DETERMINISTIC_ACKNOWLEDGEMENT
    if quality == UNKNOWN_CONFIRMATION_QUALITY:
        return UNKNOWN_ACKNOWLEDGEMENT
    if quality == FRAGMENTED_CONFIRMATION:
        return FRAGMENTED_ACKNOWLEDGEMENT
    if quality == INFERRED_CONFIRMATION:
        return INFERRED_ACKNOWLEDGEMENT
    if quality in (CONFIRMATION_WITH_REVIEW, PERIODIC_CONFIRMATION):
        return LIKELY_ACKNOWLEDGEMENT
    if quality == HUMAN_DEPENDENT_CONFIRMATION:
        return INFERRED_ACKNOWLEDGEMENT
    if quality == NO_CONFIRMATION_PATH:
        return UNKNOWN_ACKNOWLEDGEMENT
    return LIKELY_ACKNOWLEDGEMENT


def _expected_acknowledgement_guarantee(exp_quality: str, exp_ack_required: bool) -> str:
    if not exp_ack_required:
        return INFERRED_ACKNOWLEDGEMENT
    if exp_quality == DETERMINISTIC_CONFIRMATION:
        return DETERMINISTIC_ACKNOWLEDGEMENT
    if exp_quality in (CONFIRMATION_WITH_REVIEW, HUMAN_DEPENDENT_CONFIRMATION):
        return LIKELY_ACKNOWLEDGEMENT
    return LIKELY_ACKNOWLEDGEMENT


def _promotion_blockers_phase2(
    row: Dict[str, Any],
    dims: Dict[str, str],
    contract: Dict[str, Any],
    current_quality: str,
    current_ack: str,
    expected_ack: str,
    periodic_b: bool,
    exp_fresh: str,
    cur_fresh: str,
    stale_mismatch: bool,
    retry_mismatch: bool,
) -> List[str]:
    blockers: List[str] = []
    c = str(row.get("consumer") or "").upper()
    br = list(row.get("runtime_enforcement_blocker_reasons") or [])
    conf_o = dims["confirmation_owner"]
    if contract["expected_acknowledgement_required"] and conf_o in (NO_CONFIRMATION_OWNER, UNKNOWN_CONFIRMATION):
        blockers.append(NO_ACKNOWLEDGEMENT_OWNER)
    if contract["expected_stale_detection_required"] and dims["stale_state_detection_owner"] in (
        NO_CONFIRMATION_OWNER,
        UNKNOWN_CONFIRMATION,
    ):
        blockers.append(NO_STALE_CONFIRMATION_DETECTION)
    if periodic_b and _FRESH_RANK.get(cur_fresh, 5) > _FRESH_RANK.get(exp_fresh, 4):
        blockers.append(PERIODIC_ONLY_CONFIRMATION)
    if current_quality == FRAGMENTED_CONFIRMATION or current_ack == FRAGMENTED_ACKNOWLEDGEMENT:
        blockers.append(FRAGMENTED_CONFIRMATION_CHAIN)
    if current_quality == HUMAN_DEPENDENT_CONFIRMATION and contract["expected_confirmation_quality"] == DETERMINISTIC_CONFIRMATION:
        blockers.append(HUMAN_ONLY_CONFIRMATION)
    if c == "CACHE_INVALIDATION_REFRESH":
        blockers.append(UNKNOWN_CONFIRMATION_BOUNDARY)
    if retry_mismatch:
        blockers.append(NO_RETRY_OR_ESCALATION_OWNER)
    if current_quality == INFERRED_CONFIRMATION and contract["expected_operational_confirmation_required"]:
        blockers.append(VISIBILITY_ONLY_CONFIRMATION)
    if current_quality == INFERRED_CONFIRMATION and contract["expected_confirmation_quality"] not in (
        INFERRED_CONFIRMATION,
        UNKNOWN_CONFIRMATION_QUALITY,
    ):
        blockers.append(INFERRED_CLOSURE_ONLY)
    if SEMANTIC_COLLAPSE_RISK in br:
        blockers.append(SEMANTIC_CONFIRMATION_COLLAPSE_RISK)

    return sorted(set(blockers))


def _confirmation_gap_classification(
    row: Dict[str, Any],
    contract: Dict[str, Any],
    current_quality: str,
    exp_fresh: str,
    cur_fresh: str,
    stale_mismatch: bool,
    retry_mismatch: bool,
    ack_mismatch: bool,
    freshness_mismatch: bool,
    promotion_blockers: List[str],
) -> str:
    if str(row.get("gap_classification") or "") == BLOCKED_FOR_RUNTIME_ENFORCEMENT:
        return BLOCKED_FOR_RUNTIME_CONFIRMATION_ENFORCEMENT
    if SEMANTIC_CONFIRMATION_COLLAPSE_RISK in promotion_blockers:
        return BLOCKED_FOR_RUNTIME_CONFIRMATION_ENFORCEMENT
    if retry_mismatch:
        return RETRY_OWNERSHIP_GAP
    if ack_mismatch:
        return ACKNOWLEDGEMENT_GAP
    if stale_mismatch or (
        freshness_mismatch and _FRESH_RANK.get(cur_fresh, 5) > _FRESH_RANK.get(exp_fresh, 5)
    ):
        return STALE_CONFIRMATION_RISK
    cq = _QUALITY_RANK.get(current_quality, 99)
    eq = _QUALITY_RANK.get(str(contract.get("expected_confirmation_quality") or ""), 99)
    if current_quality == FRAGMENTED_CONFIRMATION or FRAGMENTED_CONFIRMATION_CHAIN in promotion_blockers:
        return CONFIRMATION_FRAGMENTED
    if cq > eq:
        return CONFIRMATION_UNDER_GOVERNED
    if (
        cq <= eq
        and not promotion_blockers
        and not freshness_mismatch
        and not ack_mismatch
        and not retry_mismatch
        and not stale_mismatch
    ):
        return CONFIRMATION_CONTRACT_SATISFIED
    if promotion_blockers:
        return CONFIRMATION_PARTIALLY_SATISFIED
    return CONFIRMATION_PARTIALLY_SATISFIED


_GAP_RANK = {
    CONFIRMATION_CONTRACT_SATISFIED: 0,
    CONFIRMATION_PARTIALLY_SATISFIED: 1,
    CONFIRMATION_UNDER_GOVERNED: 2,
    CONFIRMATION_FRAGMENTED: 3,
    STALE_CONFIRMATION_RISK: 4,
    ACKNOWLEDGEMENT_GAP: 5,
    RETRY_OWNERSHIP_GAP: 6,
    BLOCKED_FOR_RUNTIME_CONFIRMATION_ENFORCEMENT: 7,
}


def build_operational_confirmation_expected_vs_current_matrix(
    phase1_matrix: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    p1 = phase1_matrix if phase1_matrix is not None else build_operational_confirmation_topology_matrix()
    out: List[Dict[str, Any]] = []
    for row in p1:
        contract = _expected_confirmation_contract(row)
        dims = {
            "intent_owner": row.get("intent_owner"),
            "dispatch_owner": row.get("dispatch_owner"),
            "confirmation_owner": row.get("confirmation_owner"),
            "closure_owner": row.get("closure_owner"),
            "stale_state_detection_owner": row.get("stale_state_detection_owner"),
            "retry_owner": row.get("retry_owner"),
            "fallback_confirmation_owner": row.get("fallback_confirmation_owner"),
        }
        periodic_b = bool(row.get("periodic_only_confirmation_bridge"))
        current_quality = str(row.get("confirmation_quality") or "")
        cur_fresh = _derive_current_effective_confirmation_freshness(row, periodic_b, current_quality)
        exp_fresh = str(contract["expected_confirmation_freshness"])
        exp_ack = _expected_acknowledgement_guarantee(
            str(contract["expected_confirmation_quality"]),
            bool(contract["expected_acknowledgement_required"]),
        )
        current_ack = _acknowledgement_guarantee_current(current_quality)
        freshness_mismatch = _FRESH_RANK.get(cur_fresh, 5) > _FRESH_RANK.get(exp_fresh, 5)
        ack_mismatch = _ACK_RANK.get(current_ack, 4) > _ACK_RANK.get(exp_ack, 4)
        stale_mismatch = bool(contract["expected_stale_detection_required"]) and str(
            row.get("stale_state_detection_owner") or ""
        ) in (NO_CONFIRMATION_OWNER, UNKNOWN_CONFIRMATION)
        retry_mismatch = bool(contract["expected_retry_owner_required"]) and str(row.get("retry_owner") or "") == NO_CONFIRMATION_OWNER
        promotion_blockers = _promotion_blockers_phase2(
            row,
            {k: str(v or "") for k, v in dims.items()},
            contract,
            current_quality,
            current_ack,
            exp_ack,
            periodic_b,
            exp_fresh,
            cur_fresh,
            stale_mismatch,
            retry_mismatch,
        )
        gap = _confirmation_gap_classification(
            row,
            contract,
            current_quality,
            exp_fresh,
            cur_fresh,
            stale_mismatch,
            retry_mismatch,
            ack_mismatch,
            freshness_mismatch,
            promotion_blockers,
        )
        enforcement_blocked = bool(promotion_blockers) or gap == BLOCKED_FOR_RUNTIME_CONFIRMATION_ENFORCEMENT
        out.append(
            {
                **row,
                **contract,
                "current_confirmation_freshness_effective": cur_fresh,
                "current_acknowledgement_guarantee": current_ack,
                "expected_acknowledgement_guarantee": exp_ack,
                "confirmation_freshness_mismatch": freshness_mismatch,
                "confirmation_acknowledgement_mismatch": ack_mismatch,
                "stale_detection_mismatch": stale_mismatch,
                "retry_owner_mismatch": retry_mismatch,
                "confirmation_gap_classification": gap,
                "promotion_blockers": promotion_blockers,
                "runtime_confirmation_enforcement_blocked": enforcement_blocked,
                "runtime_confirmation_blocker_reasons": list(promotion_blockers),
            }
        )
    return sorted(
        out,
        key=lambda r: (str(r.get("semantic_transition") or ""), str(r.get("consumer") or "")),
    )


def build_operational_confirmation_topology_matrix(
    matrix: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    base = matrix if matrix is not None else build_expected_vs_current_matrix()
    out: List[Dict[str, Any]] = []
    for row in sorted(
        base,
        key=lambda r: (str(r.get("semantic_transition") or ""), str(r.get("consumer") or "")),
    ):
        dims = _confirmation_dimensions(row)
        c = str(row.get("consumer") or "")
        t = str(row.get("semantic_transition") or "")
        chain, handoff_count, undefined_b, human_b, periodic_b, stale_win = _confirmation_handoff_chain(c, t)
        quality = _confirmation_quality(dims, row, periodic_b, human_b)
        failures = _confirmation_failure_modes(dims, row, quality)
        reality = _operational_reality_gaps(row, dims, quality, periodic_b, human_b)
        risk = _confirmation_risk(
            quality,
            failures,
            reality,
            handoff_count,
            list(row.get("runtime_enforcement_blocker_reasons") or []),
        )
        out.append(
            {
                **row,
                **dims,
                "confirmation_quality": quality,
                "confirmation_failure_modes": failures,
                "operational_reality_gaps": reality,
                "confirmation_handoff_chain": chain,
                "confirmation_handoff_count": handoff_count,
                "undefined_confirmation_boundary": undefined_b,
                "human_dependent_confirmation_boundary": human_b,
                "periodic_only_confirmation_bridge": periodic_b,
                "stale_confirmation_window": stale_win,
                "confirmation_risk": risk,
            }
        )
    return out


def _count_by(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        k = str(r.get(key) or "")
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


def _aggregate_path_ranking(matrix: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_t: Dict[str, List[Dict[str, Any]]] = {}
    for r in matrix:
        by_t.setdefault(str(r.get("semantic_transition") or ""), []).append(r)
    worst: List[Tuple[str, str, int]] = []
    best: List[Tuple[str, str, int]] = []
    for t, rows in sorted(by_t.items()):
        risks = [_risk_rank(str(x.get("confirmation_risk") or "")) for x in rows]
        worst.append((t, _RISK_ORDER[max(risks)], max(risks)))
        best.append((t, _RISK_ORDER[min(risks)], min(risks)))
    worst.sort(key=lambda x: (-x[2], x[0]))
    best.sort(key=lambda x: (x[2], x[0]))
    return {
        "most_dangerous_by_semantic_transition": [
            {"semantic_transition": a[0], "worst_case_confirmation_risk": a[1]} for a in worst[:10]
        ],
        "safest_by_semantic_transition": [
            {"semantic_transition": a[0], "best_case_confirmation_risk": a[1]} for a in best[:10]
        ],
    }


def build_operational_confirmation_topology_phase1_snapshot() -> Dict[str, Any]:
    matrix = build_operational_confirmation_topology_matrix()
    failure_flat: List[str] = []
    for r in matrix:
        failure_flat.extend(r.get("confirmation_failure_modes") or [])
    stale_findings = [
        {
            "semantic_transition": r.get("semantic_transition"),
            "consumer": r.get("consumer"),
            "stale_confirmation_window": r.get("stale_confirmation_window"),
            "confirmation_failure_modes": r.get("confirmation_failure_modes"),
            "operational_reality_gaps": r.get("operational_reality_gaps"),
        }
        for r in matrix
        if r.get("stale_confirmation_window") or PERIODIC_STALE_CONFIRMATION in (r.get("confirmation_failure_modes") or [])
    ]
    handoff_summary = {
        "mean_confirmation_handoff_count": round(
            sum(r.get("confirmation_handoff_count", 0) for r in matrix) / max(len(matrix), 1), 4
        ),
        "rows_undefined_confirmation_boundary": sum(1 for r in matrix if r.get("undefined_confirmation_boundary")),
        "rows_human_dependent_boundary": sum(1 for r in matrix if r.get("human_dependent_confirmation_boundary")),
        "rows_periodic_only_confirmation_bridge": sum(1 for r in matrix if r.get("periodic_only_confirmation_bridge")),
        "rows_stale_confirmation_window": sum(1 for r in matrix if r.get("stale_confirmation_window")),
    }
    highest = sorted(
        [r for r in matrix if r.get("confirmation_risk") in (HIGH_CONFIRMATION_RISK, CRITICAL_CONFIRMATION_RISK)],
        key=lambda x: (
            -_risk_rank(str(x.get("confirmation_risk") or "")),
            str(x.get("semantic_transition") or ""),
            str(x.get("consumer") or ""),
        ),
    )[:45]
    safest = sorted(
        matrix,
        key=lambda x: (
            _risk_rank(str(x.get("confirmation_risk") or "")),
            str(x.get("semantic_transition") or ""),
            str(x.get("consumer") or ""),
        ),
    )[:45]
    reality_flags = {
        "rows_assumes_completion": sum(
            1 for r in matrix if (r.get("operational_reality_gaps") or {}).get("assumes_completion_without_explicit_confirmation")
        ),
        "rows_infer_closure_read": sum(
            1 for r in matrix if (r.get("operational_reality_gaps") or {}).get("infers_closure_from_read_projection")
        ),
        "rows_silent_fail": sum(
            1 for r in matrix if (r.get("operational_reality_gaps") or {}).get("operational_closure_can_silently_fail")
        ),
    }
    return {
        "phase": "Operational Confirmation Topology Audit Phase 1",
        "scope": "intent vs confirmed operational reality",
        "runtime_behavior_changed": False,
        "audit_only": True,
        "confirmation_domains": sorted(
            {
                INTENT_INITIATOR,
                OPERATIONAL_DISPATCH,
                USER_ACTION_CONFIRMATION,
                HUMAN_REVIEW_CONFIRMATION,
                DOCUMENT_CONFIRMATION,
                EXTERNAL_CONFIRMATION,
                SYSTEM_RECALC_CONFIRMATION,
                REMINDER_CONFIRMATION,
                ESCALATION_CONFIRMATION,
                NO_CONFIRMATION_OWNER,
                UNKNOWN_CONFIRMATION,
            }
        ),
        "confirmation_quality_classifications": [
            DETERMINISTIC_CONFIRMATION,
            CONFIRMATION_WITH_REVIEW,
            INFERRED_CONFIRMATION,
            PERIODIC_CONFIRMATION,
            HUMAN_DEPENDENT_CONFIRMATION,
            FRAGMENTED_CONFIRMATION,
            NO_CONFIRMATION_PATH,
            UNKNOWN_CONFIRMATION_QUALITY,
        ],
        "confirmation_failure_mode_classifications": [
            INTENT_WITHOUT_CONFIRMATION,
            CONFIRMATION_WITHOUT_CLOSURE,
            CLOSURE_WITHOUT_CONFIRMATION,
            PERIODIC_STALE_CONFIRMATION,
            NO_RETRY_OWNER,
            NO_STALE_STATE_DETECTION,
            HUMAN_CONFIRMATION_GAP,
            ESCALATION_WITHOUT_ACKNOWLEDGEMENT,
            VISIBILITY_ONLY_CONFIRMATION,
            UNKNOWN_CONFIRMATION_BOUNDARY,
        ],
        "confirmation_risk_classifications": list(_RISK_ORDER),
        "semantic_transitions": list(SEMANTIC_TRANSITIONS),
        "consumers": list(CONSUMERS),
        "confirmation_topology_matrix": matrix,
        "confirmation_quality_summary": _count_by(matrix, "confirmation_quality"),
        "confirmation_failure_summary": _count_by([{"f": x} for x in failure_flat], "f"),
        "confirmation_risk_summary": _count_by(matrix, "confirmation_risk"),
        "confirmation_handoff_summary": handoff_summary,
        "operational_reality_gap_summary": reality_flags,
        "stale_confirmation_findings": stale_findings[:80],
        "highest_risk_confirmation_paths": highest,
        "safest_confirmation_paths": safest,
        "semantic_transition_confirmation_ranking": _aggregate_path_ranking(matrix),
        "remaining_state_model_limitation": _STATE_MODEL_LIMITATION,
        "remaining_runtime_convergence_limitation": _RUNTIME_CONVERGENCE_LIMITATION,
        "non_blocking": True,
    }


def write_operational_confirmation_topology_phase1_json(target_path: Optional[Path] = None) -> Path:
    snap = build_operational_confirmation_topology_phase1_snapshot()
    base = Path(__file__).resolve().parents[1]
    path = target_path or (base / "docs" / "audit" / "OPERATIONAL_CONFIRMATION_TOPOLOGY_PHASE1.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_operational_confirmation_topology_phase2_snapshot() -> Dict[str, Any]:
    matrix = build_operational_confirmation_expected_vs_current_matrix()
    blocker_flat: List[str] = []
    for r in matrix:
        blocker_flat.extend(r.get("runtime_confirmation_blocker_reasons") or [])
    gap_summary = _count_by(matrix, "confirmation_gap_classification")
    criticality_summary = _count_by(matrix, "confirmation_criticality")
    expected_fresh_summary = _count_by(matrix, "expected_confirmation_freshness")
    current_fresh_summary = _count_by(matrix, "current_confirmation_freshness_effective")
    ack_guarantee_summary = _count_by(matrix, "current_acknowledgement_guarantee")
    stale_risk_rows = [r for r in matrix if r.get("confirmation_gap_classification") == STALE_CONFIRMATION_RISK]
    ack_gap_rows = [r for r in matrix if r.get("confirmation_gap_classification") == ACKNOWLEDGEMENT_GAP]
    retry_gap_rows = [r for r in matrix if r.get("confirmation_gap_classification") == RETRY_OWNERSHIP_GAP]
    fragmented_rows = [
        r
        for r in matrix
        if r.get("confirmation_gap_classification") == CONFIRMATION_FRAGMENTED
        or r.get("confirmation_quality") == FRAGMENTED_CONFIRMATION
    ]
    blocked_consumers = sorted(
        {str(r.get("consumer") or "") for r in matrix if r.get("runtime_confirmation_enforcement_blocked")}
    )
    safest_rollout = sorted(
        matrix,
        key=lambda x: (
            bool(x.get("runtime_confirmation_enforcement_blocked")),
            _GAP_RANK.get(str(x.get("confirmation_gap_classification") or ""), 8),
            _risk_rank(str(x.get("confirmation_risk") or "")),
            str(x.get("semantic_transition") or ""),
            str(x.get("consumer") or ""),
        ),
    )[:50]
    highest_risk = sorted(
        matrix,
        key=lambda x: (
            -int(bool(x.get("runtime_confirmation_enforcement_blocked"))),
            -_risk_rank(str(x.get("confirmation_risk") or "")),
            -len(x.get("runtime_confirmation_blocker_reasons") or []),
            str(x.get("semantic_transition") or ""),
            str(x.get("consumer") or ""),
        ),
    )[:50]
    freshness_mismatch_count = sum(1 for r in matrix if r.get("confirmation_freshness_mismatch"))
    return {
        "phase": "Operational Confirmation Topology Audit Phase 2",
        "scope": "expected-vs-current confirmation governance contracts",
        "runtime_behavior_changed": False,
        "audit_only": True,
        "confirmation_criticality_classifications": [
            SAFETY_CONFIRMATION_CRITICAL,
            COMPLIANCE_CONFIRMATION_CRITICAL,
            OPERATIONAL_CONFIRMATION_CRITICAL,
            UX_CONFIRMATION_ONLY,
            ANALYTICS_CONFIRMATION_ONLY,
        ],
        "confirmation_freshness_expectations": [
            IMMEDIATE_CONFIRMATION,
            NEAR_REAL_TIME_CONFIRMATION,
            EVENTUAL_CONFIRMATION,
            PERIODIC_CONFIRMATION_FRESHNESS,
            BEST_EFFORT_CONFIRMATION,
            UNKNOWN_CONFIRMATION_FRESHNESS,
        ],
        "acknowledgement_guarantee_classifications": [
            DETERMINISTIC_ACKNOWLEDGEMENT,
            LIKELY_ACKNOWLEDGEMENT,
            INFERRED_ACKNOWLEDGEMENT,
            FRAGMENTED_ACKNOWLEDGEMENT,
            UNKNOWN_ACKNOWLEDGEMENT,
        ],
        "confirmation_gap_classifications": [
            CONFIRMATION_CONTRACT_SATISFIED,
            CONFIRMATION_PARTIALLY_SATISFIED,
            CONFIRMATION_UNDER_GOVERNED,
            CONFIRMATION_FRAGMENTED,
            STALE_CONFIRMATION_RISK,
            ACKNOWLEDGEMENT_GAP,
            RETRY_OWNERSHIP_GAP,
            BLOCKED_FOR_RUNTIME_CONFIRMATION_ENFORCEMENT,
        ],
        "promotion_blocker_classifications": [
            NO_ACKNOWLEDGEMENT_OWNER,
            NO_STALE_CONFIRMATION_DETECTION,
            PERIODIC_ONLY_CONFIRMATION,
            FRAGMENTED_CONFIRMATION_CHAIN,
            HUMAN_ONLY_CONFIRMATION,
            UNKNOWN_CONFIRMATION_BOUNDARY,
            NO_RETRY_OR_ESCALATION_OWNER,
            VISIBILITY_ONLY_CONFIRMATION,
            INFERRED_CLOSURE_ONLY,
            SEMANTIC_CONFIRMATION_COLLAPSE_RISK,
        ],
        "semantic_transitions": list(SEMANTIC_TRANSITIONS),
        "consumers": list(CONSUMERS),
        "confirmation_expected_vs_current_matrix": matrix,
        "confirmation_gap_summary": gap_summary,
        "confirmation_criticality_summary": criticality_summary,
        "expected_confirmation_freshness_summary": expected_fresh_summary,
        "current_confirmation_freshness_summary": current_fresh_summary,
        "confirmation_freshness_mismatch_row_count": freshness_mismatch_count,
        "current_acknowledgement_guarantee_summary": ack_guarantee_summary,
        "promotion_blocker_summary": _count_by([{"b": x} for x in blocker_flat], "b"),
        "safest_confirmation_rollout_candidates": safest_rollout,
        "highest_risk_confirmation_paths": highest_risk,
        "blocked_confirmation_consumers": blocked_consumers,
        "stale_confirmation_risk_summary": {
            "rows_with_stale_confirmation_gap": len(stale_risk_rows),
            "rows_with_stale_detection_mismatch": sum(1 for r in matrix if r.get("stale_detection_mismatch")),
        },
        "acknowledgement_gap_summary": {
            "rows_with_acknowledgement_gap": len(ack_gap_rows),
            "rows_with_ack_mismatch_flag": sum(1 for r in matrix if r.get("confirmation_acknowledgement_mismatch")),
        },
        "retry_ownership_gap_summary": {
            "rows_with_retry_ownership_gap": len(retry_gap_rows),
            "rows_with_retry_mismatch_flag": sum(1 for r in matrix if r.get("retry_owner_mismatch")),
        },
        "fragmented_confirmation_summary": {
            "rows_fragmented_gap_or_quality": len(fragmented_rows),
        },
        "operational_reality_gaps_retained_from_phase1": True,
        "remaining_state_model_limitation": _STATE_MODEL_LIMITATION,
        "remaining_runtime_convergence_limitation": _RUNTIME_CONVERGENCE_LIMITATION,
        "non_blocking": True,
    }


def write_operational_confirmation_topology_phase2_json(target_path: Optional[Path] = None) -> Path:
    snap = build_operational_confirmation_topology_phase2_snapshot()
    base = Path(__file__).resolve().parents[1]
    path = target_path or (base / "docs" / "audit" / "OPERATIONAL_CONFIRMATION_TOPOLOGY_PHASE2.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _remediation_categories(row: Dict[str, Any]) -> Tuple[str, List[str]]:
    c = str(row.get("consumer") or "").upper()
    gap = str(row.get("confirmation_gap_classification") or "")
    blockers = set(row.get("runtime_confirmation_blocker_reasons") or [])
    ccrit = str(row.get("confirmation_criticality") or "")

    if gap == CONFIRMATION_CONTRACT_SATISFIED and not blockers:
        return ACCEPTABLE_RISK, []

    primary = CODE_REMEDIATION
    sec: List[str] = []

    if SEMANTIC_CONFIRMATION_COLLAPSE_RISK in blockers:
        primary = REPORTING_SEMANTIC_REMEDIATION
        sec = [CODE_REMEDIATION, OBSERVABILITY_REMEDIATION]
    elif c == "CACHE_INVALIDATION_REFRESH":
        primary = CACHE_INVALIDATION_REMEDIATION
        sec = [OBSERVABILITY_REMEDIATION, CODE_REMEDIATION]
    elif HUMAN_ONLY_CONFIRMATION in blockers:
        primary = HUMAN_PROCESS_REMEDIATION
        sec = [PRODUCT_POLICY_REMEDIATION]
    elif FRAGMENTED_CONFIRMATION_CHAIN in blockers or gap == CONFIRMATION_FRAGMENTED:
        primary = ORCHESTRATION_REMEDIATION
        sec = [EVENT_ARCHITECTURE_REMEDIATION]
    elif gap == ACKNOWLEDGEMENT_GAP or NO_ACKNOWLEDGEMENT_OWNER in blockers:
        primary = EVENT_ARCHITECTURE_REMEDIATION
        sec = [ORCHESTRATION_REMEDIATION]
    elif gap == STALE_CONFIRMATION_RISK or NO_STALE_CONFIRMATION_DETECTION in blockers:
        primary = OBSERVABILITY_REMEDIATION
        sec = [CODE_REMEDIATION]
    elif gap == RETRY_OWNERSHIP_GAP or NO_RETRY_OR_ESCALATION_OWNER in blockers:
        primary = ORCHESTRATION_REMEDIATION
        sec = [PRODUCT_POLICY_REMEDIATION, EVENT_ARCHITECTURE_REMEDIATION]
    elif PERIODIC_ONLY_CONFIRMATION in blockers:
        primary = ORCHESTRATION_REMEDIATION
        sec = [EVENT_ARCHITECTURE_REMEDIATION]
    elif INFERRED_CLOSURE_ONLY in blockers or VISIBILITY_ONLY_CONFIRMATION in blockers:
        primary = PRODUCT_POLICY_REMEDIATION
        sec = [CODE_REMEDIATION]
    elif gap == BLOCKED_FOR_RUNTIME_CONFIRMATION_ENFORCEMENT:
        primary = ORCHESTRATION_REMEDIATION
        sec = [EVENT_ARCHITECTURE_REMEDIATION, CODE_REMEDIATION]
    elif gap == CONFIRMATION_UNDER_GOVERNED:
        primary = CODE_REMEDIATION
        sec = [PRODUCT_POLICY_REMEDIATION]
    elif ccrit == ANALYTICS_CONFIRMATION_ONLY and gap not in (
        BLOCKED_FOR_RUNTIME_CONFIRMATION_ENFORCEMENT,
        ACKNOWLEDGEMENT_GAP,
        RETRY_OWNERSHIP_GAP,
    ):
        primary = ACCEPTABLE_RISK
        sec = [OBSERVABILITY_REMEDIATION]

    sec = sorted({x for x in sec if x != primary})
    return primary, sec


def _remediation_owner_guidance(row: Dict[str, Any], primary_cat: str) -> Tuple[str, str]:
    c = str(row.get("consumer") or "").upper()
    if primary_cat == CACHE_INVALIDATION_REMEDIATION:
        return PLATFORM_INFRASTRUCTURE_OWNER, REMEDIATION_OWNER_CONFIDENCE_HIGH
    if primary_cat == REPORTING_SEMANTIC_REMEDIATION:
        return REPORTING_OWNER, REMEDIATION_OWNER_CONFIDENCE_HIGH
    if primary_cat == ACCEPTABLE_RISK:
        return PRODUCT_POLICY_OWNER, REMEDIATION_OWNER_CONFIDENCE_MEDIUM
    if primary_cat == HUMAN_PROCESS_REMEDIATION:
        return OPERATIONS_PROCESS_OWNER, REMEDIATION_OWNER_CONFIDENCE_HIGH
    if primary_cat == PRODUCT_POLICY_REMEDIATION:
        return PRODUCT_POLICY_OWNER, REMEDIATION_OWNER_CONFIDENCE_MEDIUM
    if primary_cat == OBSERVABILITY_REMEDIATION:
        return PLATFORM_INFRASTRUCTURE_OWNER, REMEDIATION_OWNER_CONFIDENCE_MEDIUM
    if c == "REQUIREMENT_LIST":
        return SEMANTIC_TRUTH_OWNER, REMEDIATION_OWNER_CONFIDENCE_HIGH
    if c in ("REMINDER_ENGINE", "NOTIFICATION_EMAIL_PATHS", "SLA_ESCALATION_PATHS"):
        return WORKFLOW_GOVERNANCE_OWNER, REMEDIATION_OWNER_CONFIDENCE_HIGH
    if c in ("PRIORITY_ACTIONS", "UNIFIED_TASKS", "TODAY_VIEW"):
        return BACKEND_RUNTIME_OWNER, REMEDIATION_OWNER_CONFIDENCE_MEDIUM
    if c in ("PORTFOLIO_SCORE", "SCORE_DRIVERS", "REGENERATION_RECALC_PATHS"):
        return BACKEND_RUNTIME_OWNER, REMEDIATION_OWNER_CONFIDENCE_MEDIUM
    if primary_cat in (ORCHESTRATION_REMEDIATION, EVENT_ARCHITECTURE_REMEDIATION):
        return SHARED_OWNERSHIP, REMEDIATION_OWNER_CONFIDENCE_LOW
    if primary_cat == CODE_REMEDIATION:
        return BACKEND_RUNTIME_OWNER, REMEDIATION_OWNER_CONFIDENCE_MEDIUM
    return SHARED_OWNERSHIP, REMEDIATION_OWNER_CONFIDENCE_LOW


def _enforcement_blocker_severity_and_reasoning(row: Dict[str, Any], primary_cat: str) -> Tuple[str, str]:
    gap = str(row.get("confirmation_gap_classification") or "")
    blockers = set(row.get("runtime_confirmation_blocker_reasons") or [])
    follow = bool(row.get("operational_followthrough"))
    exp_follow = bool(row.get("expected_operational_followthrough"))

    if gap == CONFIRMATION_CONTRACT_SATISFIED and not blockers:
        sev = NON_BLOCKING
    elif SEMANTIC_CONFIRMATION_COLLAPSE_RISK in blockers or gap == BLOCKED_FOR_RUNTIME_CONFIRMATION_ENFORCEMENT:
        sev = HARD_BLOCKER
    elif UNKNOWN_CONFIRMATION_BOUNDARY in blockers and str(row.get("consumer") or "").upper() == "CACHE_INVALIDATION_REFRESH":
        sev = HARD_BLOCKER
    elif gap in (ACKNOWLEDGEMENT_GAP, RETRY_OWNERSHIP_GAP):
        sev = SOFT_BLOCKER
    elif gap == STALE_CONFIRMATION_RISK:
        sev = SOFT_BLOCKER
    elif gap == CONFIRMATION_PARTIALLY_SATISFIED:
        sev = OBSERVATION_ONLY
    elif gap == CONFIRMATION_UNDER_GOVERNED:
        sev = SOFT_BLOCKER
    else:
        sev = OBSERVATION_ONLY

    reasoning = (
        f"gap_classification={gap}; blockers={','.join(sorted(blockers)) if blockers else 'none'};"
        f"primary_remediation={primary_cat}; operational_followthrough={follow}; expected_followthrough={exp_follow}"
    )
    return sev, reasoning


def _acceptable_risk_classification(row: Dict[str, Any], severity: str) -> str:
    ccrit = str(row.get("confirmation_criticality") or "")
    c = str(row.get("consumer") or "").upper()
    gap = str(row.get("confirmation_gap_classification") or "")
    blockers = set(row.get("runtime_confirmation_blocker_reasons") or [])
    if severity == NON_BLOCKING and gap == CONFIRMATION_CONTRACT_SATISFIED:
        if ccrit == UX_CONFIRMATION_ONLY and c in _PASSIVE_DISPLAY_CONSUMERS_REMEDIATION:
            return ACCEPTABLE_FOR_PASSIVE_DISPLAY
        if ccrit == ANALYTICS_CONFIRMATION_ONLY:
            return ACCEPTABLE_FOR_ANALYTICS
    if HUMAN_ONLY_CONFIRMATION in blockers or str(row.get("confirmation_quality") or "") == HUMAN_DEPENDENT_CONFIRMATION:
        return ACCEPTABLE_WITH_HUMAN_REVIEW
    if severity == HARD_BLOCKER and ccrit in (SAFETY_CONFIRMATION_CRITICAL, COMPLIANCE_CONFIRMATION_CRITICAL):
        return UNACCEPTABLE_FOR_RUNTIME_ENFORCEMENT
    if (
        severity == HARD_BLOCKER
        and ccrit == OPERATIONAL_CONFIRMATION_CRITICAL
        and c in ("PRIORITY_ACTIONS", "SLA_ESCALATION_PATHS", "REMINDER_ENGINE")
    ):
        return UNACCEPTABLE_FOR_OPERATIONAL_AUTOMATION
    if severity == HARD_BLOCKER:
        return UNACCEPTABLE_FOR_RUNTIME_ENFORCEMENT
    if ccrit == UX_CONFIRMATION_ONLY:
        return ACCEPTABLE_FOR_PASSIVE_DISPLAY
    if ccrit == ANALYTICS_CONFIRMATION_ONLY:
        return ACCEPTABLE_FOR_ANALYTICS
    return UNKNOWN_ACCEPTABILITY


def _remediation_urgency(row: Dict[str, Any], severity: str, acceptable: str, primary_cat: str) -> str:
    if primary_cat == ACCEPTABLE_RISK and severity == NON_BLOCKING:
        return MONITOR_ONLY
    if acceptable in (ACCEPTABLE_FOR_PASSIVE_DISPLAY, ACCEPTABLE_FOR_ANALYTICS) and severity == NON_BLOCKING:
        return MONITOR_ONLY
    if acceptable == ACCEPTABLE_WITH_HUMAN_REVIEW and severity != HARD_BLOCKER:
        return LOW_PRIORITY
    if severity == HARD_BLOCKER:
        ccrit = str(row.get("confirmation_criticality") or "")
        if ccrit in (SAFETY_CONFIRMATION_CRITICAL, COMPLIANCE_CONFIRMATION_CRITICAL):
            return CRITICAL_IMMEDIATE
        return HIGH_PRIORITY
    if str(row.get("confirmation_gap_classification") or "") == ACKNOWLEDGEMENT_GAP:
        return HIGH_PRIORITY
    if str(row.get("confirmation_gap_classification") or "") == STALE_CONFIRMATION_RISK:
        return MEDIUM_PRIORITY
    if severity == OBSERVATION_ONLY:
        return LOW_PRIORITY
    if severity == SOFT_BLOCKER:
        return MEDIUM_PRIORITY
    return LOW_PRIORITY


def _root_cause_family(row: Dict[str, Any], primary_cat: str) -> str:
    blockers = set(row.get("runtime_confirmation_blocker_reasons") or [])
    gap = str(row.get("confirmation_gap_classification") or "")
    c = str(row.get("consumer") or "").upper()
    if SEMANTIC_CONFIRMATION_COLLAPSE_RISK in blockers:
        return SEMANTIC_COLLAPSE_DEBT
    if c == "CACHE_INVALIDATION_REFRESH":
        return CACHE_REFRESH_DEBT
    if gap == ACKNOWLEDGEMENT_GAP or NO_ACKNOWLEDGEMENT_OWNER in blockers:
        return ACKNOWLEDGEMENT_GAP_DEBT
    if gap == STALE_CONFIRMATION_RISK or NO_STALE_CONFIRMATION_DETECTION in blockers:
        return STALE_STATE_DETECTION_DEBT
    if FRAGMENTED_CONFIRMATION_CHAIN in blockers or gap == CONFIRMATION_FRAGMENTED:
        return ORCHESTRATION_DEBT
    if primary_cat == REPORTING_SEMANTIC_REMEDIATION:
        return REPORTING_COLLAPSE_DEBT
    if primary_cat == HUMAN_PROCESS_REMEDIATION:
        return PROCESS_GOVERNANCE_DEBT
    if primary_cat == OBSERVABILITY_REMEDIATION:
        return OBSERVABILITY_DEBT
    if gap == CONFIRMATION_UNDER_GOVERNED:
        return STATE_MODEL_DEBT
    if VISIBILITY_ONLY_CONFIRMATION in blockers or INFERRED_CLOSURE_ONLY in blockers:
        return PROPAGATION_FRAGMENTATION
    if primary_cat in (EVENT_ARCHITECTURE_REMEDIATION, ORCHESTRATION_REMEDIATION):
        return ORCHESTRATION_DEBT
    return UNKNOWN_ROOT_CAUSE


def _urgency_rank(u: str) -> int:
    return _URGENCY_ORDER.index(u) if u in _URGENCY_ORDER else len(_URGENCY_ORDER)


def build_operational_confirmation_remediation_matrix(
    phase2_matrix: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    base = phase2_matrix if phase2_matrix is not None else build_operational_confirmation_expected_vs_current_matrix()
    out: List[Dict[str, Any]] = []
    for row in base:
        pcat, secondaries = _remediation_categories(row)
        owner, oconf = _remediation_owner_guidance(row, pcat)
        sev, reasoning = _enforcement_blocker_severity_and_reasoning(row, pcat)
        acceptable = _acceptable_risk_classification(row, sev)
        urgency = _remediation_urgency(row, sev, acceptable, pcat)
        root = _root_cause_family(row, pcat)
        out.append(
            {
                **row,
                "primary_remediation_category": pcat,
                "secondary_remediation_categories": secondaries,
                "remediation_owner": owner,
                "remediation_owner_confidence": oconf,
                "remediation_urgency": urgency,
                "enforcement_blocker_severity": sev,
                "enforcement_blocker_reasoning": reasoning,
                "acceptable_risk_classification": acceptable,
                "root_cause_family": root,
            }
        )
    return sorted(
        out,
        key=lambda r: (str(r.get("semantic_transition") or ""), str(r.get("consumer") or "")),
    )


def build_operational_confirmation_remediation_phase1_snapshot() -> Dict[str, Any]:
    matrix = build_operational_confirmation_remediation_matrix()
    must_block = [
        {
            "semantic_transition": r.get("semantic_transition"),
            "consumer": r.get("consumer"),
            "acceptable_risk_classification": r.get("acceptable_risk_classification"),
            "enforcement_blocker_severity": r.get("enforcement_blocker_severity"),
            "remediation_urgency": r.get("remediation_urgency"),
        }
        for r in matrix
        if r.get("acceptable_risk_classification") == UNACCEPTABLE_FOR_RUNTIME_ENFORCEMENT
        or r.get("acceptable_risk_classification") == UNACCEPTABLE_FOR_OPERATIONAL_AUTOMATION
        or (
            r.get("enforcement_blocker_severity") == HARD_BLOCKER
            and r.get("confirmation_criticality")
            in (SAFETY_CONFIRMATION_CRITICAL, COMPLIANCE_CONFIRMATION_CRITICAL)
        )
    ]
    must_block = sorted(
        must_block,
        key=lambda x: (
            str(x.get("consumer") or ""),
            str(x.get("semantic_transition") or ""),
        ),
    )
    orch = _count_by(
        [{"k": r.get("consumer")} for r in matrix if r.get("primary_remediation_category") in (ORCHESTRATION_REMEDIATION, EVENT_ARCHITECTURE_REMEDIATION)],
        "k",
    )
    ack_clusters = _count_by(
        [{"k": r.get("consumer")} for r in matrix if r.get("confirmation_gap_classification") == ACKNOWLEDGEMENT_GAP],
        "k",
    )
    stale_clusters = _count_by(
        [{"k": r.get("consumer")} for r in matrix if r.get("stale_detection_mismatch") or r.get("confirmation_gap_classification") == STALE_CONFIRMATION_RISK],
        "k",
    )
    collapse_clusters = _count_by(
        [
            {"k": r.get("consumer")}
            for r in matrix
            if SEMANTIC_CONFIRMATION_COLLAPSE_RISK in (r.get("runtime_confirmation_blocker_reasons") or [])
        ],
        "k",
    )
    cache_clusters = _count_by([{"k": r.get("consumer")} for r in matrix if str(r.get("consumer") or "") == "CACHE_INVALIDATION_REFRESH"], "k")
    acceptable_clusters = _count_by(matrix, "acceptable_risk_classification")
    priority_ranking = sorted(
        [
            {
                "semantic_transition": r.get("semantic_transition"),
                "consumer": r.get("consumer"),
                "remediation_urgency": r.get("remediation_urgency"),
                "primary_remediation_category": r.get("primary_remediation_category"),
                "root_cause_family": r.get("root_cause_family"),
            }
            for r in matrix
        ],
        key=lambda x: (
            -_urgency_rank(str(x.get("remediation_urgency") or "")),
            str(x.get("consumer") or ""),
            str(x.get("semantic_transition") or ""),
        ),
    )
    observe_only = sorted(
        [
            {
                "semantic_transition": r.get("semantic_transition"),
                "consumer": r.get("consumer"),
                "remediation_urgency": r.get("remediation_urgency"),
                "enforcement_blocker_severity": r.get("enforcement_blocker_severity"),
            }
            for r in matrix
            if r.get("remediation_urgency") == MONITOR_ONLY
            and r.get("enforcement_blocker_severity") in (NON_BLOCKING, OBSERVATION_ONLY)
        ],
        key=lambda x: (str(x.get("consumer") or ""), str(x.get("semantic_transition") or "")),
    )[:55]
    return {
        "phase": "Operational Confirmation Governance Remediation Audit Phase 1",
        "scope": "audit-only remediation planning from confirmation governance gaps",
        "runtime_behavior_changed": False,
        "audit_only": True,
        "remediation_category_classifications": [
            CODE_REMEDIATION,
            ORCHESTRATION_REMEDIATION,
            EVENT_ARCHITECTURE_REMEDIATION,
            PRODUCT_POLICY_REMEDIATION,
            HUMAN_PROCESS_REMEDIATION,
            REPORTING_SEMANTIC_REMEDIATION,
            CACHE_INVALIDATION_REMEDIATION,
            OBSERVABILITY_REMEDIATION,
            ACCEPTABLE_RISK,
            UNKNOWN_REMEDIATION,
        ],
        "remediation_owner_classifications": [
            BACKEND_RUNTIME_OWNER,
            WORKFLOW_GOVERNANCE_OWNER,
            SEMANTIC_TRUTH_OWNER,
            PRODUCT_POLICY_OWNER,
            OPERATIONS_PROCESS_OWNER,
            REPORTING_OWNER,
            PLATFORM_INFRASTRUCTURE_OWNER,
            SHARED_OWNERSHIP,
            UNKNOWN_OWNER,
        ],
        "remediation_urgency_classifications": list(_URGENCY_ORDER),
        "enforcement_blocker_severity_classifications": [HARD_BLOCKER, SOFT_BLOCKER, OBSERVATION_ONLY, NON_BLOCKING],
        "acceptable_risk_classifications": [
            ACCEPTABLE_FOR_PASSIVE_DISPLAY,
            ACCEPTABLE_FOR_ANALYTICS,
            ACCEPTABLE_WITH_HUMAN_REVIEW,
            UNACCEPTABLE_FOR_RUNTIME_ENFORCEMENT,
            UNACCEPTABLE_FOR_OPERATIONAL_AUTOMATION,
            UNKNOWN_ACCEPTABILITY,
        ],
        "root_cause_classifications": [
            STATE_MODEL_DEBT,
            PROPAGATION_FRAGMENTATION,
            ACKNOWLEDGEMENT_GAP_DEBT,
            STALE_STATE_DETECTION_DEBT,
            ORCHESTRATION_DEBT,
            CACHE_REFRESH_DEBT,
            SEMANTIC_COLLAPSE_DEBT,
            REPORTING_COLLAPSE_DEBT,
            PROCESS_GOVERNANCE_DEBT,
            OBSERVABILITY_DEBT,
            UNKNOWN_ROOT_CAUSE,
        ],
        "semantic_transitions": list(SEMANTIC_TRANSITIONS),
        "consumers": list(CONSUMERS),
        "remediation_matrix": matrix,
        "must_block_runtime_enforcement": must_block,
        "orchestration_debt_clusters": orch,
        "acknowledgement_gap_clusters": ack_clusters,
        "stale_detection_clusters": stale_clusters,
        "semantic_collapse_clusters": collapse_clusters,
        "cache_refresh_debt_clusters": cache_clusters,
        "acceptable_risk_clusters": acceptable_clusters,
        "fragmented_confirmation_summary": _count_by(
            [
                {"k": r.get("consumer")}
                for r in matrix
                if r.get("confirmation_quality") == FRAGMENTED_CONFIRMATION
                or r.get("confirmation_gap_classification") == CONFIRMATION_FRAGMENTED
            ],
            "k",
        ),
        "remediation_priority_ranking": priority_ranking,
        "remediation_owner_summary": _count_by(matrix, "remediation_owner"),
        "safest_observe_only_candidates": observe_only,
        "remediation_urgency_summary": _count_by(matrix, "remediation_urgency"),
        "enforcement_blocker_severity_summary": _count_by(matrix, "enforcement_blocker_severity"),
        "primary_remediation_category_summary": _count_by(matrix, "primary_remediation_category"),
        "root_cause_family_summary": _count_by(matrix, "root_cause_family"),
        "remaining_state_model_limitation": _STATE_MODEL_LIMITATION,
        "remaining_runtime_convergence_limitation": _RUNTIME_CONVERGENCE_LIMITATION,
        "non_blocking": True,
    }


def write_operational_confirmation_remediation_phase1_json(target_path: Optional[Path] = None) -> Path:
    snap = build_operational_confirmation_remediation_phase1_snapshot()
    base = Path(__file__).resolve().parents[1]
    path = target_path or (base / "docs" / "audit" / "OPERATIONAL_CONFIRMATION_REMEDIATION_PHASE1.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _unsafe_reasons_and_flag(row: Dict[str, Any]) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    blockers = set(row.get("runtime_confirmation_blocker_reasons") or [])
    sev = str(row.get("enforcement_blocker_severity") or "")
    acceptable = str(row.get("acceptable_risk_classification") or "")
    gap = str(row.get("confirmation_gap_classification") or "")
    root = str(row.get("root_cause_family") or "")
    pcat = str(row.get("primary_remediation_category") or "")

    if FRAGMENTED_CONFIRMATION_CHAIN in blockers:
        reasons.append(UNSAFE_RUNTIME_FRAGMENTATION)
    if NO_ACKNOWLEDGEMENT_OWNER in blockers or gap == ACKNOWLEDGEMENT_GAP:
        reasons.append(UNSAFE_ACKNOWLEDGEMENT_COLLAPSE)
    if NO_STALE_CONFIRMATION_DETECTION in blockers or gap == STALE_CONFIRMATION_RISK:
        reasons.append(UNSAFE_STALE_STATE_GAP)
    if SEMANTIC_CONFIRMATION_COLLAPSE_RISK in blockers:
        reasons.append(UNSAFE_SEMANTIC_COLLAPSE)
    if pcat == EVENT_ARCHITECTURE_REMEDIATION and sev == HARD_BLOCKER:
        reasons.append(UNSAFE_EVENT_DEPENDENCY)
    if root == STATE_MODEL_DEBT:
        reasons.append(UNSAFE_STATE_MODEL_DEPENDENCY)
    if UNKNOWN_CONFIRMATION_BOUNDARY in blockers:
        reasons.append(UNSAFE_UNKNOWN_BOUNDARY)
    if pcat == HUMAN_PROCESS_REMEDIATION or root == PROCESS_GOVERNANCE_DEBT:
        reasons.append(UNSAFE_PROCESS_DEPENDENCY)

    unsafe = bool(reasons) and (
        sev == HARD_BLOCKER
        or acceptable in (UNACCEPTABLE_FOR_RUNTIME_ENFORCEMENT, UNACCEPTABLE_FOR_OPERATIONAL_AUTOMATION)
        or SEMANTIC_CONFIRMATION_COLLAPSE_RISK in blockers
        or UNKNOWN_CONFIRMATION_BOUNDARY in blockers
    )
    return unsafe, sorted(set(reasons))


def _remediation_track_phase2(row: Dict[str, Any], unsafe: bool) -> Tuple[str, str]:
    pcat = str(row.get("primary_remediation_category") or "")
    root = str(row.get("root_cause_family") or "")
    sev = str(row.get("enforcement_blocker_severity") or "")
    acceptable = str(row.get("acceptable_risk_classification") or "")
    gap = str(row.get("confirmation_gap_classification") or "")

    if unsafe and acceptable in (UNACCEPTABLE_FOR_RUNTIME_ENFORCEMENT, UNACCEPTABLE_FOR_OPERATIONAL_AUTOMATION):
        return DO_NOT_IMPLEMENT_YET, "Acceptability class forbids runtime enforcement until governance resolves blockers."
    if pcat == ACCEPTABLE_RISK and sev == NON_BLOCKING:
        return SAFE_ENGINEERING_FIX, "Satisfied confirmation contract; low-risk incremental engineering only."
    if pcat == CACHE_INVALIDATION_REMEDIATION:
        return CACHE_GOVERNANCE_REQUIRED, "Cache invalidation boundary undefined; platform/cache governance precedes enforcement."
    if pcat == REPORTING_SEMANTIC_REMEDIATION:
        return REPORTING_SEMANTIC_ALIGNMENT, "Reporting or score semantics collapse risk; align projections before automation."
    if pcat == OBSERVABILITY_REMEDIATION:
        return OBSERVABILITY_FIRST, "Stale or unobserved confirmation paths; telemetry and detection precede hardening."
    if pcat == HUMAN_PROCESS_REMEDIATION:
        return PROCESS_GOVERNANCE_REQUIRED, "Human-in-the-loop confirmation; operations process design required."
    if pcat == PRODUCT_POLICY_REMEDIATION:
        return PRODUCT_POLICY_REQUIRED, "Product policy defines acceptable inferred or visibility-only confirmation."
    if pcat == EVENT_ARCHITECTURE_REMEDIATION:
        return EVENT_MODEL_REQUIRED, "Acknowledgement and fan-out span event-shaped boundaries."
    if pcat == ORCHESTRATION_REMEDIATION:
        return RUNTIME_ARCHITECTURE_REQUIRED, "Orchestration fragmentation across runtime subsystems."
    if root == STATE_MODEL_DEBT and gap != CONFIRMATION_CONTRACT_SATISFIED:
        return DEFER_UNTIL_STATE_MODEL_REFINEMENT, "State model / contract under-governed relative to expectations."
    if pcat == CODE_REMEDIATION and sev in (SOFT_BLOCKER, OBSERVATION_ONLY):
        return SAFE_ENGINEERING_FIX, "Targeted code or projection adjustments within existing architecture."
    return SAFE_ENGINEERING_FIX, "Default engineering-track batching for incremental confirmation clarity."


def _dependency_families_phase2(row: Dict[str, Any], track: str) -> Tuple[str, List[str]]:
    blockers = set(row.get("runtime_confirmation_blocker_reasons") or [])
    gap = str(row.get("confirmation_gap_classification") or "")
    root = str(row.get("root_cause_family") or "")
    pcat = str(row.get("primary_remediation_category") or "")
    sec: List[str] = []
    primary = DEPENDENCY_NONE

    if SEMANTIC_CONFIRMATION_COLLAPSE_RISK in blockers or pcat == REPORTING_SEMANTIC_REMEDIATION:
        primary = DEPENDENCY_REPORTING_SEMANTICS
        sec.extend([DEPENDENCY_STATE_MODEL])
    elif UNKNOWN_CONFIRMATION_BOUNDARY in blockers or pcat == CACHE_INVALIDATION_REMEDIATION:
        primary = DEPENDENCY_CACHE_INVALIDATION
    elif NO_ACKNOWLEDGEMENT_OWNER in blockers or gap == ACKNOWLEDGEMENT_GAP:
        primary = DEPENDENCY_ACKNOWLEDGEMENT_MODEL
        sec.append(DEPENDENCY_EVENT_ORCHESTRATION)
    elif NO_STALE_CONFIRMATION_DETECTION in blockers or gap == STALE_CONFIRMATION_RISK or pcat == OBSERVABILITY_REMEDIATION:
        primary = DEPENDENCY_OBSERVABILITY
    elif FRAGMENTED_CONFIRMATION_CHAIN in blockers:
        primary = DEPENDENCY_RUNTIME_ARCHITECTURE
        sec.append(DEPENDENCY_EVENT_ORCHESTRATION)
    elif track == EVENT_MODEL_REQUIRED:
        primary = DEPENDENCY_EVENT_ORCHESTRATION
    elif track == RUNTIME_ARCHITECTURE_REQUIRED:
        primary = DEPENDENCY_RUNTIME_ARCHITECTURE
    elif root == STATE_MODEL_DEBT:
        primary = DEPENDENCY_STATE_MODEL
    elif pcat == PRODUCT_POLICY_REMEDIATION:
        primary = DEPENDENCY_PRODUCT_POLICY
    elif pcat == HUMAN_PROCESS_REMEDIATION:
        primary = DEPENDENCY_OPERATIONS_PROCESS
    elif track == CACHE_GOVERNANCE_REQUIRED:
        primary = DEPENDENCY_CACHE_INVALIDATION
    elif primary == DEPENDENCY_NONE and gap != CONFIRMATION_CONTRACT_SATISFIED:
        primary = DEPENDENCY_UNKNOWN

    sec = sorted({x for x in sec if x != primary})
    return primary, sec


def _recommended_batch_phase2(row: Dict[str, Any], track: str, primary_dep: str) -> str:
    if track == OBSERVABILITY_FIRST or primary_dep == DEPENDENCY_OBSERVABILITY:
        return BATCH_OBSERVABILITY_FIRST
    if primary_dep == DEPENDENCY_ACKNOWLEDGEMENT_MODEL:
        return BATCH_ACKNOWLEDGEMENT_GOVERNANCE
    if str(row.get("confirmation_gap_classification") or "") == STALE_CONFIRMATION_RISK or primary_dep == DEPENDENCY_OBSERVABILITY:
        return BATCH_STALE_STATE_DETECTION
    if track in (RUNTIME_ARCHITECTURE_REQUIRED, EVENT_MODEL_REQUIRED):
        return BATCH_RUNTIME_ORCHESTRATION
    if track == CACHE_GOVERNANCE_REQUIRED or primary_dep == DEPENDENCY_CACHE_INVALIDATION:
        return BATCH_CACHE_REFRESH_GOVERNANCE
    if track == REPORTING_SEMANTIC_ALIGNMENT or primary_dep == DEPENDENCY_REPORTING_SEMANTICS:
        return BATCH_REPORTING_ALIGNMENT
    if track in (PROCESS_GOVERNANCE_REQUIRED, PRODUCT_POLICY_REQUIRED) or primary_dep in (
        DEPENDENCY_OPERATIONS_PROCESS,
        DEPENDENCY_PRODUCT_POLICY,
    ):
        return BATCH_PROCESS_AND_POLICY
    if track == DEFER_UNTIL_STATE_MODEL_REFINEMENT or primary_dep == DEPENDENCY_STATE_MODEL:
        return BATCH_STATE_MODEL_REFINEMENT
    if track == SAFE_ENGINEERING_FIX:
        return BATCH_SAFE_READ_PATHS
    if track == DO_NOT_IMPLEMENT_YET:
        return BATCH_STATE_MODEL_REFINEMENT
    return BATCH_SAFE_READ_PATHS


def _first_wave_eligibility_phase2(row: Dict[str, Any], track: str, unsafe: bool) -> str:
    sev = str(row.get("enforcement_blocker_severity") or "")
    acceptable = str(row.get("acceptable_risk_classification") or "")
    urgency = str(row.get("remediation_urgency") or "")

    if unsafe or track == DO_NOT_IMPLEMENT_YET:
        return BLOCKED_FROM_IMPLEMENTATION
    if track == OBSERVABILITY_FIRST:
        return SECOND_WAVE_ONLY
    if track == DEFER_UNTIL_STATE_MODEL_REFINEMENT:
        return SECOND_WAVE_ONLY
    if track in (RUNTIME_ARCHITECTURE_REQUIRED, EVENT_MODEL_REQUIRED, CACHE_GOVERNANCE_REQUIRED, REPORTING_SEMANTIC_ALIGNMENT):
        return SECOND_WAVE_ONLY
    if track == SAFE_ENGINEERING_FIX and sev == NON_BLOCKING and acceptable in (
        ACCEPTABLE_FOR_PASSIVE_DISPLAY,
        ACCEPTABLE_FOR_ANALYTICS,
    ):
        if urgency == MONITOR_ONLY:
            return OBSERVE_ONLY_FOR_NOW
        return FIRST_WAVE_ELIGIBLE
    if track == SAFE_ENGINEERING_FIX and sev == SOFT_BLOCKER:
        return FIRST_WAVE_WITH_REVIEW
    if track in (PROCESS_GOVERNANCE_REQUIRED, PRODUCT_POLICY_REQUIRED):
        return FIRST_WAVE_WITH_REVIEW
    if urgency == MONITOR_ONLY:
        return OBSERVE_ONLY_FOR_NOW
    return SECOND_WAVE_ONLY


def _implementation_readiness_phase2(
    row: Dict[str, Any], track: str, first_wave: str, unsafe: bool
) -> Tuple[str, str]:
    if unsafe or track == DO_NOT_IMPLEMENT_YET or first_wave == BLOCKED_FROM_IMPLEMENTATION:
        return NOT_SAFE_TO_IMPLEMENT, "Unsafe-to-implement signals or blocked first-wave posture."
    if track == OBSERVABILITY_FIRST:
        return REQUIRES_OBSERVABILITY_FIRST, "Establish detection and confirmation signals before tightening enforcement."
    if track == RUNTIME_ARCHITECTURE_REQUIRED or track == CACHE_GOVERNANCE_REQUIRED:
        return REQUIRES_RUNTIME_DESIGN, "Cross-service runtime design required before implementation."
    if track == EVENT_MODEL_REQUIRED:
        return REQUIRES_RUNTIME_DESIGN, "Event and acknowledgement topology design required."
    if track == PROCESS_GOVERNANCE_REQUIRED:
        return REQUIRES_PROCESS_DESIGN, "Operations process and attestation paths must be defined."
    if track == PRODUCT_POLICY_REQUIRED:
        return REQUIRES_PRODUCT_DECISION, "Product policy must bound inferred or visibility-only confirmation."
    if track == REPORTING_SEMANTIC_ALIGNMENT:
        return READY_WITH_GOVERNANCE_REVIEW, "Reporting alignment can proceed under explicit semantic governance review."
    if track == DEFER_UNTIL_STATE_MODEL_REFINEMENT:
        return REQUIRES_STATE_MODEL_REFINEMENT, "Refine state and contract model before engineering execution."
    if first_wave == FIRST_WAVE_ELIGIBLE:
        return READY_FOR_IMPLEMENTATION, "Eligible for first-wave engineering under audit guidance only."
    if first_wave == FIRST_WAVE_WITH_REVIEW:
        return READY_WITH_GOVERNANCE_REVIEW, "Implementation allowed with mandatory governance review gates."
    if first_wave == OBSERVE_ONLY_FOR_NOW:
        return READY_WITH_GOVERNANCE_REVIEW, "Observe and monitor; no enforcement implementation without review."
    return READY_WITH_GOVERNANCE_REVIEW, "Second-wave sequencing; review batch dependencies before starting."


def build_operational_confirmation_remediation_triage_matrix(
    remediation_matrix: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    base = remediation_matrix if remediation_matrix is not None else build_operational_confirmation_remediation_matrix()
    out: List[Dict[str, Any]] = []
    for row in base:
        unsafe, unsafe_reasons = _unsafe_reasons_and_flag(row)
        track, track_reasoning = _remediation_track_phase2(row, unsafe)
        primary_dep, secondary_deps = _dependency_families_phase2(row, track)
        batch = _recommended_batch_phase2(row, track, primary_dep)
        first_wave = _first_wave_eligibility_phase2(row, track, unsafe)
        readiness, readiness_reasoning = _implementation_readiness_phase2(row, track, first_wave, unsafe)
        out.append(
            {
                **row,
                "remediation_track": track,
                "remediation_track_reasoning": track_reasoning,
                "primary_dependency": primary_dep,
                "secondary_dependencies": secondary_deps,
                "recommended_batch": batch,
                "first_wave_eligibility": first_wave,
                "unsafe_to_implement": unsafe,
                "unsafe_reasons": unsafe_reasons,
                "implementation_readiness": readiness,
                "implementation_readiness_reasoning": readiness_reasoning,
            }
        )
    return sorted(
        out,
        key=lambda r: (str(r.get("semantic_transition") or ""), str(r.get("consumer") or "")),
    )


def build_operational_confirmation_remediation_phase2_triage_snapshot() -> Dict[str, Any]:
    matrix = build_operational_confirmation_remediation_triage_matrix()
    first_wave_candidates = sorted(
        [
            {
                "semantic_transition": r.get("semantic_transition"),
                "consumer": r.get("consumer"),
                "first_wave_eligibility": r.get("first_wave_eligibility"),
                "remediation_track": r.get("remediation_track"),
                "recommended_batch": r.get("recommended_batch"),
            }
            for r in matrix
            if r.get("first_wave_eligibility") in (FIRST_WAVE_ELIGIBLE, FIRST_WAVE_WITH_REVIEW)
        ],
        key=lambda x: (str(x.get("consumer") or ""), str(x.get("semantic_transition") or "")),
    )
    blocked_impl = sorted(
        [
            {
                "semantic_transition": r.get("semantic_transition"),
                "consumer": r.get("consumer"),
                "first_wave_eligibility": r.get("first_wave_eligibility"),
                "implementation_readiness": r.get("implementation_readiness"),
            }
            for r in matrix
            if r.get("first_wave_eligibility") == BLOCKED_FROM_IMPLEMENTATION
            or r.get("implementation_readiness") == NOT_SAFE_TO_IMPLEMENT
        ],
        key=lambda x: (str(x.get("consumer") or ""), str(x.get("semantic_transition") or "")),
    )
    obs_first = [
        r
        for r in matrix
        if r.get("remediation_track") == OBSERVABILITY_FIRST or r.get("recommended_batch") == BATCH_OBSERVABILITY_FIRST
    ]
    runtime_clusters = _count_by(
        [{"k": r.get("consumer")} for r in matrix if r.get("remediation_track") == RUNTIME_ARCHITECTURE_REQUIRED],
        "k",
    )
    process_clusters = _count_by(
        [{"k": r.get("consumer")} for r in matrix if r.get("remediation_track") == PROCESS_GOVERNANCE_REQUIRED],
        "k",
    )
    product_clusters = _count_by(
        [{"k": r.get("consumer")} for r in matrix if r.get("remediation_track") == PRODUCT_POLICY_REQUIRED],
        "k",
    )
    unsafe_clusters = _count_by(
        [{"k": r.get("consumer")} for r in matrix if r.get("unsafe_to_implement")],
        "k",
    )
    unsafe_reason_flat: List[str] = []
    for r in matrix:
        unsafe_reason_flat.extend(r.get("unsafe_reasons") or [])
    return {
        "phase": "Operational Confirmation Governance Remediation Triage Phase 2",
        "scope": "audit-only prioritization and sequencing from remediation findings",
        "runtime_behavior_changed": False,
        "audit_only": True,
        "remediation_track_classifications": [
            SAFE_ENGINEERING_FIX,
            RUNTIME_ARCHITECTURE_REQUIRED,
            EVENT_MODEL_REQUIRED,
            PROCESS_GOVERNANCE_REQUIRED,
            PRODUCT_POLICY_REQUIRED,
            OBSERVABILITY_FIRST,
            CACHE_GOVERNANCE_REQUIRED,
            REPORTING_SEMANTIC_ALIGNMENT,
            DEFER_UNTIL_STATE_MODEL_REFINEMENT,
            DO_NOT_IMPLEMENT_YET,
        ],
        "implementation_readiness_classifications": [
            READY_FOR_IMPLEMENTATION,
            READY_WITH_GOVERNANCE_REVIEW,
            REQUIRES_RUNTIME_DESIGN,
            REQUIRES_PRODUCT_DECISION,
            REQUIRES_PROCESS_DESIGN,
            REQUIRES_OBSERVABILITY_FIRST,
            REQUIRES_STATE_MODEL_REFINEMENT,
            NOT_SAFE_TO_IMPLEMENT,
        ],
        "dependency_family_classifications": [
            DEPENDENCY_NONE,
            DEPENDENCY_RUNTIME_ARCHITECTURE,
            DEPENDENCY_EVENT_ORCHESTRATION,
            DEPENDENCY_ACKNOWLEDGEMENT_MODEL,
            DEPENDENCY_STATE_MODEL,
            DEPENDENCY_PRODUCT_POLICY,
            DEPENDENCY_OPERATIONS_PROCESS,
            DEPENDENCY_REPORTING_SEMANTICS,
            DEPENDENCY_CACHE_INVALIDATION,
            DEPENDENCY_OBSERVABILITY,
            DEPENDENCY_UNKNOWN,
        ],
        "first_wave_eligibility_classifications": [
            FIRST_WAVE_ELIGIBLE,
            FIRST_WAVE_WITH_REVIEW,
            SECOND_WAVE_ONLY,
            BLOCKED_FROM_IMPLEMENTATION,
            OBSERVE_ONLY_FOR_NOW,
        ],
        "unsafe_reason_classifications": [
            UNSAFE_RUNTIME_FRAGMENTATION,
            UNSAFE_ACKNOWLEDGEMENT_COLLAPSE,
            UNSAFE_STALE_STATE_GAP,
            UNSAFE_SEMANTIC_COLLAPSE,
            UNSAFE_EVENT_DEPENDENCY,
            UNSAFE_STATE_MODEL_DEPENDENCY,
            UNSAFE_UNKNOWN_BOUNDARY,
            UNSAFE_PROCESS_DEPENDENCY,
        ],
        "remediation_batch_classifications": [
            BATCH_SAFE_READ_PATHS,
            BATCH_OBSERVABILITY_FIRST,
            BATCH_ACKNOWLEDGEMENT_GOVERNANCE,
            BATCH_STALE_STATE_DETECTION,
            BATCH_RUNTIME_ORCHESTRATION,
            BATCH_CACHE_REFRESH_GOVERNANCE,
            BATCH_REPORTING_ALIGNMENT,
            BATCH_PROCESS_AND_POLICY,
            BATCH_STATE_MODEL_REFINEMENT,
        ],
        "semantic_transitions": list(SEMANTIC_TRANSITIONS),
        "consumers": list(CONSUMERS),
        "remediation_triage_matrix": matrix,
        "first_wave_candidates": first_wave_candidates,
        "blocked_implementation_candidates": blocked_impl,
        "observability_first_candidates": [
            {
                "semantic_transition": r.get("semantic_transition"),
                "consumer": r.get("consumer"),
                "remediation_track": r.get("remediation_track"),
                "recommended_batch": r.get("recommended_batch"),
            }
            for r in sorted(
                obs_first,
                key=lambda x: (str(x.get("consumer") or ""), str(x.get("semantic_transition") or "")),
            )
        ],
        "runtime_architecture_required_clusters": runtime_clusters,
        "process_governance_required_clusters": process_clusters,
        "product_policy_required_clusters": product_clusters,
        "unsafe_to_implement_clusters": unsafe_clusters,
        "unsafe_reason_summary": _count_by([{"u": x} for x in unsafe_reason_flat], "u"),
        "remediation_batch_summary": _count_by(matrix, "recommended_batch"),
        "implementation_readiness_summary": _count_by(matrix, "implementation_readiness"),
        "remediation_track_summary": _count_by(matrix, "remediation_track"),
        "first_wave_eligibility_summary": _count_by(matrix, "first_wave_eligibility"),
        "dependency_summary": _count_by(matrix, "primary_dependency"),
        "remaining_state_model_limitation": _STATE_MODEL_LIMITATION,
        "remaining_runtime_convergence_limitation": _RUNTIME_CONVERGENCE_LIMITATION,
        "non_blocking": True,
    }


def write_operational_confirmation_remediation_phase2_triage_json(target_path: Optional[Path] = None) -> Path:
    snap = build_operational_confirmation_remediation_phase2_triage_snapshot()
    base = Path(__file__).resolve().parents[1]
    path = target_path or (base / "docs" / "audit" / "OPERATIONAL_CONFIRMATION_REMEDIATION_PHASE2_TRIAGE.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
