from __future__ import annotations

from typing import Any, Dict, List

# Consumer types (Phase 1 audited set)
SCORING_ENGINE = "SCORING_ENGINE"
PORTFOLIO_SCORE = "PORTFOLIO_SCORE"
REPORT_EXPORT = "REPORT_EXPORT"
COMMAND_CENTER = "COMMAND_CENTER"
REMINDER_ENGINE = "REMINDER_ENGINE"
TODAY_VIEW = "TODAY_VIEW"
PROPERTY_SUMMARY = "PROPERTY_SUMMARY"
REQUIREMENT_LIST = "REQUIREMENT_LIST"
ADMIN_AUDIT = "ADMIN_AUDIT"
DASHBOARD_SUMMARY = "DASHBOARD_SUMMARY"
CLIENT_STATUS_CHIP = "CLIENT_STATUS_CHIP"
WORKFLOW_OUTCOME_HARNESS = "WORKFLOW_OUTCOME_HARNESS"

# Phase 2 target consumers only
PHASE2_TARGET_CONSUMERS = (REMINDER_ENGINE, PORTFOLIO_SCORE, REPORT_EXPORT)

# Interpretation modes
USES_SEMANTIC_STATE = "USES_SEMANTIC_STATE"
USES_STATE_REASON = "USES_STATE_REASON"
USES_EVIDENCE_AUTHORITY = "USES_EVIDENCE_AUTHORITY"
USES_LEGACY_STATUS_ONLY = "USES_LEGACY_STATUS_ONLY"
USES_EVIDENCE_STATE_ONLY = "USES_EVIDENCE_STATE_ONLY"
USES_COMBINED_MODEL = "USES_COMBINED_MODEL"
TASK_NATIVE_ONLY = "TASK_NATIVE_ONLY"

# Precedence models (Phase 2)
SEMANTIC_STATE_PRIMARY = "SEMANTIC_STATE_PRIMARY"
SEMANTIC_STATE_WITH_AUTHORITY_FALLBACK = "SEMANTIC_STATE_WITH_AUTHORITY_FALLBACK"
AUTHORITY_PRIMARY = "AUTHORITY_PRIMARY"
LEGACY_STATUS_PRIMARY = "LEGACY_STATUS_PRIMARY"
LEGACY_ONLY = "LEGACY_ONLY"
MIXED_UNDEFINED = "MIXED_UNDEFINED"

# Declared precedence contracts (Phase 3 audit-only; not runtime enforced)
DECLARED_PRECEDENCE_CONTRACTS: Dict[str, str] = {
    REMINDER_ENGINE: SEMANTIC_STATE_WITH_AUTHORITY_FALLBACK,
    PORTFOLIO_SCORE: SEMANTIC_STATE_WITH_AUTHORITY_FALLBACK,
    REPORT_EXPORT: SEMANTIC_STATE_PRIMARY,
}

# Risk classifications
SAFE = "SAFE"
LEGACY_COMPATIBILITY = "LEGACY_COMPATIBILITY"
SEMANTIC_COLLAPSE_RISK = "SEMANTIC_COLLAPSE_RISK"
OPERATIONAL_CONVERGENCE_RISK = "OPERATIONAL_CONVERGENCE_RISK"
PARTIAL_COMPLETENESS_RISK = "PARTIAL_COMPLETENESS_RISK"
DECLARATION_VERIFICATION_COLLAPSE = "DECLARATION_VERIFICATION_COLLAPSE"
ASSESSMENT_FOLLOWUP_COLLAPSE = "ASSESSMENT_FOLLOWUP_COLLAPSE"
EXPIRY_REVIEW_COLLAPSE = "EXPIRY_REVIEW_COLLAPSE"

# Expected interpretation outcomes (Phase 2 audit contract)
ATTENTION_ELIGIBLE = "ATTENTION_ELIGIBLE"
RISK_BEARING = "RISK_BEARING"
NOT_CURRENT = "NOT_CURRENT"
NOT_VERIFIED = "NOT_VERIFIED"
INCOMPLETE_VISIBLE = "INCOMPLETE_VISIBLE"
CURRENT_VALID = "CURRENT_VALID"
EXPIRED = "EXPIRED"

# Current interpretation labels (audit-only approximations)
CURRENT_LIKE = "CURRENT_LIKE"
VERIFIED_LIKE = "VERIFIED_LIKE"
PENDING_LIKE = "PENDING_LIKE"
RISK_BEARING_LIKE = "RISK_BEARING_LIKE"
UNKNOWN_LIKE = "UNKNOWN_LIKE"

# Impact levels (Phase 3)
LOW_IMPACT = "LOW_IMPACT"
MEDIUM_IMPACT = "MEDIUM_IMPACT"
HIGH_IMPACT = "HIGH_IMPACT"
WIDESPREAD_COLLAPSE_DEPENDENCY = "WIDESPREAD_COLLAPSE_DEPENDENCY"


CONSUMER_PROFILES: Dict[str, Dict[str, Any]] = {
    PORTFOLIO_SCORE: {
        "module": "services/compliance_score.py",
        "interpretation_mode": USES_COMBINED_MODEL,
        "semantic_state_awareness": False,
        "reads": ["status", "evidence_state", "evidence_authority", "workflow_class", "take_action"],
        "notes": [
            "Driver logic still primarily status/evidence driven.",
            "semantic_state currently carried but not primary interpretation source.",
        ],
    },
    SCORING_ENGINE: {
        "module": "services/compliance_scoring_v2.py",
        "interpretation_mode": USES_LEGACY_STATUS_ONLY,
        "semantic_state_awareness": False,
        "reads": ["status", "evidence_state"],
        "notes": ["Scoring remains legacy compatibility path by design in this phase."],
    },
    COMMAND_CENTER: {
        "module": "services/command_center_service.py",
        "interpretation_mode": USES_COMBINED_MODEL,
        "semantic_state_awareness": False,
        "reads": ["source_type", "primary_action_*", "metadata", "status"],
        "notes": ["Requirement semantics are mostly pass-through; command-center behavior remains task/action centric."],
    },
    TODAY_VIEW: {
        "module": "services/unified_tasks_service.py",
        "interpretation_mode": USES_COMBINED_MODEL,
        "semantic_state_awareness": False,
        "reads": ["source_type", "action_type", "status", "take_action"],
        "notes": ["Requirement-backed rows include semantic fields but prioritization logic is not semantic_state-driven."],
    },
    REMINDER_ENGINE: {
        "module": "services/reminder_truth_service.py",
        "interpretation_mode": USES_LEGACY_STATUS_ONLY,
        "semantic_state_awareness": False,
        "reads": ["authority_runtime_requirement_status", "status", "applicability", "due_date"],
        "notes": ["Reminder gating currently keyed to legacy-compatible status projection."],
    },
    REPORT_EXPORT: {
        "module": "services/reporting_service.py + services/pdf_report_builder.py",
        "interpretation_mode": USES_COMBINED_MODEL,
        "semantic_state_awareness": False,
        "reads": ["status", "evidence_state", "computed_status", "score_status"],
        "notes": ["Exports aggregate/report from coarse mirrors and computed status labels."],
    },
    REQUIREMENT_LIST: {
        "module": "services/requirement_truth.py",
        "interpretation_mode": USES_STATE_REASON,
        "semantic_state_awareness": False,
        "reads": ["evidence_authority.state", "evidence_authority.state_reason", "status"],
        "notes": ["Truth projection emits semantic_state additively but copy rules still mainly use state_reason."],
    },
    PROPERTY_SUMMARY: {
        "module": "services/requirement_truth.py + services/compliance_score.py",
        "interpretation_mode": USES_COMBINED_MODEL,
        "semantic_state_awareness": False,
        "reads": ["status", "evidence_state", "workflow_class"],
        "notes": ["Property summary surfaces remain legacy-compatible with mixed sources."],
    },
    DASHBOARD_SUMMARY: {
        "module": "services/command_center_service.py + services/compliance_score.py",
        "interpretation_mode": USES_COMBINED_MODEL,
        "semantic_state_awareness": False,
        "reads": ["score_status", "stats", "status-like counts"],
        "notes": ["Dashboard KPIs are intentionally mirror-compatible in this phase."],
    },
    ADMIN_AUDIT: {
        "module": "services/requirement_workflow_audit.py",
        "interpretation_mode": USES_EVIDENCE_AUTHORITY,
        "semantic_state_awareness": False,
        "reads": ["workflow_class_reference", "workflow_mismatch_flags", "state_reason"],
        "notes": ["Admin audit uses workflow diagnostics; semantic_state not yet first-class audit axis."],
    },
    CLIENT_STATUS_CHIP: {
        "module": "frontend semantic projections (test-level classification only)",
        "interpretation_mode": USES_COMBINED_MODEL,
        "semantic_state_awareness": False,
        "reads": ["status", "workflow_class", "take_action", "evidence_authority"],
        "notes": ["Client chips still resolve from legacy/status-focused view-model semantics."],
    },
    WORKFLOW_OUTCOME_HARNESS: {
        "module": "tests/test_workflow_outcome_enforcement.py",
        "interpretation_mode": USES_COMBINED_MODEL,
        "semantic_state_awareness": True,
        "reads": ["state_reason", "workflow_class", "mirror.status", "semantic_state"],
        "notes": ["Harness now asserts semantic_state for hardened outcomes, but runtime consumers remain mostly legacy-aware."],
    },
}


def _risk_classes(profile: Dict[str, Any]) -> List[str]:
    mode = str(profile.get("interpretation_mode") or "")
    aware = bool(profile.get("semantic_state_awareness"))
    risks: List[str] = []
    if aware:
        return [SAFE]

    if mode in (USES_LEGACY_STATUS_ONLY, USES_EVIDENCE_STATE_ONLY):
        risks.extend([LEGACY_COMPATIBILITY, SEMANTIC_COLLAPSE_RISK])
    elif mode in (USES_COMBINED_MODEL, USES_STATE_REASON, USES_EVIDENCE_AUTHORITY):
        risks.append(LEGACY_COMPATIBILITY)
        risks.append(SEMANTIC_COLLAPSE_RISK)
    elif mode == TASK_NATIVE_ONLY:
        risks.append(SAFE)

    reads = set(profile.get("reads") or [])
    if "status" in reads or "evidence_state" in reads or mode == USES_LEGACY_STATUS_ONLY:
        risks.extend(
            [
                PARTIAL_COMPLETENESS_RISK,
                DECLARATION_VERIFICATION_COLLAPSE,
                ASSESSMENT_FOLLOWUP_COLLAPSE,
                EXPIRY_REVIEW_COLLAPSE,
            ]
        )
    if "state_reason" not in reads and mode in (USES_LEGACY_STATUS_ONLY, USES_EVIDENCE_STATE_ONLY, USES_COMBINED_MODEL):
        risks.append(OPERATIONAL_CONVERGENCE_RISK)

    out = []
    for r in risks:
        if r not in out:
            out.append(r)
    return out or [SAFE]


def _precedence_model(profile: Dict[str, Any]) -> str:
    mode = str(profile.get("interpretation_mode") or "")
    aware = bool(profile.get("semantic_state_awareness"))
    reads = set(profile.get("reads") or [])
    if aware and "semantic_state" in reads:
        return SEMANTIC_STATE_PRIMARY
    if aware:
        return SEMANTIC_STATE_WITH_AUTHORITY_FALLBACK
    if mode == USES_EVIDENCE_AUTHORITY:
        return AUTHORITY_PRIMARY
    if mode == USES_LEGACY_STATUS_ONLY:
        return LEGACY_STATUS_PRIMARY
    if mode == USES_EVIDENCE_STATE_ONLY:
        return LEGACY_ONLY
    if mode == TASK_NATIVE_ONLY:
        return LEGACY_ONLY
    return MIXED_UNDEFINED


PHASE2_EXPECTED_INTERPRETATIONS: Dict[str, Dict[str, str]] = {
    PORTFOLIO_SCORE: {
        "PARTIALLY_COMPLETE": INCOMPLETE_VISIBLE,
        "DECLARATION_RECORDED": NOT_VERIFIED,
        "TENANT_DELIVERY_RECORDED": NOT_VERIFIED,
        "REGISTRATION_RECORDED": NOT_VERIFIED,
        "ASSESSMENT_FOLLOWUP_REQUIRED": RISK_BEARING,
        "OPERATIONALLY_OPEN": RISK_BEARING,
        "EXPIRY_REVIEW_REQUIRED": NOT_CURRENT,
        "VERIFIED_CURRENT": CURRENT_VALID,
        "VERIFIED_EXPIRED": EXPIRED,
    },
    REPORT_EXPORT: {
        "PARTIALLY_COMPLETE": INCOMPLETE_VISIBLE,
        "DECLARATION_RECORDED": NOT_VERIFIED,
        "TENANT_DELIVERY_RECORDED": NOT_VERIFIED,
        "REGISTRATION_RECORDED": NOT_VERIFIED,
        "ASSESSMENT_FOLLOWUP_REQUIRED": RISK_BEARING,
        "OPERATIONALLY_OPEN": NOT_CURRENT,
        "EXPIRY_REVIEW_REQUIRED": NOT_CURRENT,
        "VERIFIED_CURRENT": CURRENT_VALID,
        "VERIFIED_EXPIRED": EXPIRED,
    },
    REMINDER_ENGINE: {
        "PARTIALLY_COMPLETE": ATTENTION_ELIGIBLE,
        "DECLARATION_RECORDED": ATTENTION_ELIGIBLE,
        "TENANT_DELIVERY_RECORDED": ATTENTION_ELIGIBLE,
        "REGISTRATION_RECORDED": ATTENTION_ELIGIBLE,
        "ASSESSMENT_FOLLOWUP_REQUIRED": ATTENTION_ELIGIBLE,
        "OPERATIONALLY_OPEN": ATTENTION_ELIGIBLE,
        "EXPIRY_REVIEW_REQUIRED": ATTENTION_ELIGIBLE,
        "VERIFIED_CURRENT": CURRENT_VALID,
        "VERIFIED_EXPIRED": ATTENTION_ELIGIBLE,
    },
}


def _collapse_risks_for_state(semantic_state: str) -> List[str]:
    st = str(semantic_state or "").strip().upper()
    if st == "PARTIALLY_COMPLETE":
        return [PARTIAL_COMPLETENESS_RISK, SEMANTIC_COLLAPSE_RISK]
    if st in ("DECLARATION_RECORDED", "REGISTRATION_RECORDED", "TENANT_DELIVERY_RECORDED"):
        return [DECLARATION_VERIFICATION_COLLAPSE, SEMANTIC_COLLAPSE_RISK]
    if st == "ASSESSMENT_FOLLOWUP_REQUIRED":
        return [ASSESSMENT_FOLLOWUP_COLLAPSE, SEMANTIC_COLLAPSE_RISK]
    if st in ("EXPIRY_REVIEW_REQUIRED",):
        return [EXPIRY_REVIEW_COLLAPSE, SEMANTIC_COLLAPSE_RISK]
    if st in ("OPERATIONALLY_OPEN",):
        return [OPERATIONAL_CONVERGENCE_RISK, SEMANTIC_COLLAPSE_RISK]
    return [SEMANTIC_COLLAPSE_RISK]


def _current_interpretation_for_state(consumer: str, semantic_state: str) -> str:
    """
    Audit approximation of current interpretation from current precedence profile.
    This is intentionally diagnostic and non-enforcing.
    """
    st = str(semantic_state or "").strip().upper()
    current_precedence = str(audit_semantic_state_consumer(consumer).get("precedence_model") or "")

    if current_precedence in (LEGACY_STATUS_PRIMARY, LEGACY_ONLY, MIXED_UNDEFINED):
        if st in ("VERIFIED_CURRENT",):
            return CURRENT_LIKE
        if st in ("VERIFIED_EXPIRED",):
            return RISK_BEARING_LIKE
        if st in (
            "PARTIALLY_COMPLETE",
            "DECLARATION_RECORDED",
            "TENANT_DELIVERY_RECORDED",
            "REGISTRATION_RECORDED",
            "ASSESSMENT_FOLLOWUP_REQUIRED",
            "OPERATIONALLY_OPEN",
            "EXPIRY_REVIEW_REQUIRED",
        ):
            return CURRENT_LIKE if consumer == REPORT_EXPORT else PENDING_LIKE
    if current_precedence in (SEMANTIC_STATE_PRIMARY, SEMANTIC_STATE_WITH_AUTHORITY_FALLBACK, AUTHORITY_PRIMARY):
        # closer to expected semantics; still diagnostic only
        if st in ("VERIFIED_CURRENT",):
            return CURRENT_LIKE
        if st in ("VERIFIED_EXPIRED",):
            return RISK_BEARING_LIKE
        if st in ("PARTIALLY_COMPLETE", "EXPIRY_REVIEW_REQUIRED", "OPERATIONALLY_OPEN", "ASSESSMENT_FOLLOWUP_REQUIRED"):
            return RISK_BEARING_LIKE
        if st in ("DECLARATION_RECORDED", "TENANT_DELIVERY_RECORDED", "REGISTRATION_RECORDED"):
            return VERIFIED_LIKE
    return UNKNOWN_LIKE


def _impact_level(
    consumer: str,
    state: str,
    current_interpretation: str,
    expected_interpretation: str,
    collapse_detected: bool,
) -> str:
    if not collapse_detected:
        return LOW_IMPACT
    st = str(state or "").strip().upper()
    if consumer == REPORT_EXPORT and st in ("EXPIRY_REVIEW_REQUIRED", "OPERATIONALLY_OPEN"):
        return HIGH_IMPACT
    if consumer == PORTFOLIO_SCORE and st in ("PARTIALLY_COMPLETE", "ASSESSMENT_FOLLOWUP_REQUIRED"):
        return HIGH_IMPACT
    if consumer == REMINDER_ENGINE and st in ("OPERATIONALLY_OPEN", "EXPIRY_REVIEW_REQUIRED", "PARTIALLY_COMPLETE"):
        return WIDESPREAD_COLLAPSE_DEPENDENCY
    if current_interpretation != expected_interpretation:
        return MEDIUM_IMPACT
    return LOW_IMPACT


def audit_semantic_state_consumer(consumer: str) -> Dict[str, Any]:
    profile = CONSUMER_PROFILES.get(consumer)
    if not isinstance(profile, dict):
        return {
            "consumer": consumer,
            "interpretation_mode": None,
            "semantic_state_awareness": False,
            "risk_classifications": [SEMANTIC_COLLAPSE_RISK],
            "notes": [f"Unknown consumer profile: {consumer}"],
            "non_blocking": True,
        }
    return {
        "consumer": consumer,
        "module": profile.get("module"),
        "interpretation_mode": profile.get("interpretation_mode"),
        "precedence_model": _precedence_model(profile),
        "semantic_state_awareness": bool(profile.get("semantic_state_awareness")),
        "risk_classifications": _risk_classes(profile),
        "notes": list(profile.get("notes") or []),
        "non_blocking": True,
    }


def audit_consumer_semantic_precedence(consumer: str) -> Dict[str, Any]:
    base = audit_semantic_state_consumer(consumer)
    return {
        "consumer": consumer,
        "module": base.get("module"),
        "interpretation_mode": base.get("interpretation_mode"),
        "precedence_model": base.get("precedence_model"),
        "semantic_state_awareness": base.get("semantic_state_awareness"),
        "unsafe_precedence_patterns": _unsafe_precedence_patterns(base),
        "risk_classifications": base.get("risk_classifications") or [],
        "notes": base.get("notes") or [],
        "non_blocking": True,
    }


def _unsafe_precedence_patterns(base: Dict[str, Any]) -> List[str]:
    patterns: List[str] = []
    precedence = str(base.get("precedence_model") or "")
    aware = bool(base.get("semantic_state_awareness"))
    if precedence in (LEGACY_STATUS_PRIMARY, LEGACY_ONLY):
        patterns.append("legacy_status_checked_before_semantic_state")
    if not aware:
        patterns.append("semantic_state_ignored")
    if precedence == MIXED_UNDEFINED:
        patterns.append("mixed_interpretation_order_without_explicit_precedence")
    return patterns


def audit_consumer_expected_interpretation(consumer: str, semantic_state: str) -> Dict[str, Any]:
    state = str(semantic_state or "").strip().upper()
    base = audit_semantic_state_consumer(consumer)
    expected = (PHASE2_EXPECTED_INTERPRETATIONS.get(consumer) or {}).get(state)
    collapse_detected = bool(
        expected
        and (
            "semantic_state_ignored" in _unsafe_precedence_patterns(base)
            or str(base.get("precedence_model") or "") in (LEGACY_STATUS_PRIMARY, LEGACY_ONLY, MIXED_UNDEFINED)
        )
    )
    return {
        "consumer": consumer,
        "semantic_state": state,
        "expected_behavior": expected,
        "current_interpretation_mode": base.get("interpretation_mode"),
        "precedence_model": base.get("precedence_model"),
        "semantic_state_awareness": base.get("semantic_state_awareness"),
        "collapse_detected": collapse_detected,
        "risk": _collapse_risks_for_state(state) if collapse_detected else [SAFE],
        "non_blocking": True,
    }


def audit_consumer_precedence_diff(consumer: str) -> Dict[str, Any]:
    current = audit_consumer_semantic_precedence(consumer)
    declared = DECLARED_PRECEDENCE_CONTRACTS.get(consumer)
    mismatch = bool(declared and declared != current.get("precedence_model"))
    return {
        "consumer": consumer,
        "current_precedence": current.get("precedence_model"),
        "declared_precedence": declared,
        "precedence_mismatch": mismatch,
        "unsafe_precedence_patterns": current.get("unsafe_precedence_patterns") or [],
        "risk_classifications": current.get("risk_classifications") or [],
        "non_blocking": True,
    }


def audit_semantic_state_interpretation_diff(consumer: str, semantic_state: str) -> Dict[str, Any]:
    snap = audit_consumer_expected_interpretation(consumer, semantic_state)
    current_precedence = str(snap.get("precedence_model") or "")
    declared_precedence = DECLARED_PRECEDENCE_CONTRACTS.get(consumer)
    current_interpretation = _current_interpretation_for_state(consumer, semantic_state)
    expected_interpretation = snap.get("expected_behavior")
    collapse_detected = bool(
        snap.get("collapse_detected")
        or (expected_interpretation is not None and current_interpretation != expected_interpretation)
    )
    impact = _impact_level(
        consumer=consumer,
        state=semantic_state,
        current_interpretation=current_interpretation,
        expected_interpretation=str(expected_interpretation),
        collapse_detected=collapse_detected,
    )
    return {
        "consumer": consumer,
        "semantic_state": str(semantic_state or "").strip().upper(),
        "current_precedence": current_precedence,
        "declared_precedence": declared_precedence,
        "current_interpretation": current_interpretation,
        "expected_interpretation": expected_interpretation,
        "collapse_detected": collapse_detected,
        "flattening_exposure_detected": collapse_detected,
        "impact_level": impact,
        "risk": snap.get("risk") or [],
        "non_blocking": True,
    }


def audit_semantic_state_consumer_batch(consumers: List[str]) -> Dict[str, Any]:
    diagnostics = [audit_semantic_state_consumer(c) for c in consumers]
    matrix = [
        {
            "consumer": d.get("consumer"),
            "interpretation_mode": d.get("interpretation_mode"),
            "precedence_model": d.get("precedence_model"),
            "semantic_state_aware": d.get("semantic_state_awareness"),
            "risk": ", ".join(d.get("risk_classifications") or []),
        }
        for d in diagnostics
    ]
    return {
        "diagnostics": diagnostics,
        "consumer_interpretation_matrix": matrix,
        "non_blocking": True,
    }
