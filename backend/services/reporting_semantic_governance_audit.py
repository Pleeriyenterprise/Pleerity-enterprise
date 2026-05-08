from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from services.operational_confirmation_topology_audit import (
    CONFIRMATION_CONTRACT_SATISFIED,
    SEMANTIC_COLLAPSE_DEBT,
    SEMANTIC_CONFIRMATION_COLLAPSE_RISK,
    STALE_CONFIRMATION_RISK,
    build_operational_confirmation_remediation_triage_matrix,
)
from services.trigger_propagation_audit import SEMANTIC_TRANSITIONS

# --- Reporting governance consumers (audit scope) ---
REPORT_EXPORT = "REPORT_EXPORT"
PORTFOLIO_SCORE = "PORTFOLIO_SCORE"
DASHBOARD_SUMMARY = "DASHBOARD_SUMMARY"
PROPERTY_SUMMARY = "PROPERTY_SUMMARY"
REQUIREMENT_LIST = "REQUIREMENT_LIST"
CLIENT_STATUS_CHIP = "CLIENT_STATUS_CHIP"

REPORTING_GOVERNANCE_CONSUMERS: Tuple[str, ...] = (
    REPORT_EXPORT,
    PORTFOLIO_SCORE,
    DASHBOARD_SUMMARY,
    PROPERTY_SUMMARY,
    REQUIREMENT_LIST,
    CLIENT_STATUS_CHIP,
)

_CONSUMER_TRIAGE_PROXY: Dict[str, str] = {
    CLIENT_STATUS_CHIP: PROPERTY_SUMMARY,
}

# Representation safety
SAFE_FOR_DIRECT_REPRESENTATION = "SAFE_FOR_DIRECT_REPRESENTATION"
SAFE_WITH_CONTEXT = "SAFE_WITH_CONTEXT"
SAFE_WITH_DISCLAIMER = "SAFE_WITH_DISCLAIMER"
UNSAFE_FOR_SIMPLIFIED_REPORTING = "UNSAFE_FOR_SIMPLIFIED_REPORTING"
UNSAFE_FOR_COMPLIANT_LANGUAGE = "UNSAFE_FOR_COMPLIANT_LANGUAGE"
UNSAFE_FOR_CURRENT_LANGUAGE = "UNSAFE_FOR_CURRENT_LANGUAGE"
UNKNOWN_REPRESENTATION_SAFETY = "UNKNOWN_REPRESENTATION_SAFETY"

# Semantic collapse (reporting/export flattening)
NO_COLLAPSE_RISK = "NO_COLLAPSE_RISK"
PARTIAL_COMPLETENESS_COLLAPSE = "PARTIAL_COMPLETENESS_COLLAPSE"
DECLARATION_VERIFICATION_COLLAPSE = "DECLARATION_VERIFICATION_COLLAPSE"
FOLLOWUP_RESOLUTION_COLLAPSE = "FOLLOWUP_RESOLUTION_COLLAPSE"
EXPIRY_CURRENTNESS_COLLAPSE = "EXPIRY_CURRENTNESS_COLLAPSE"
OPERATIONAL_OPEN_COLLAPSE = "OPERATIONAL_OPEN_COLLAPSE"
REPORTING_SIMPLIFICATION_COLLAPSE = "REPORTING_SIMPLIFICATION_COLLAPSE"
MULTI_STATE_COLLAPSE = "MULTI_STATE_COLLAPSE"
UNKNOWN_COLLAPSE_RISK = "UNKNOWN_COLLAPSE_RISK"

# Language governance labels (deterministic classes; rows also expose booleans + lists)
SAFE_FOR_COMPLIANT_WORDING = "SAFE_FOR_COMPLIANT_WORDING"
SAFE_FOR_CURRENT_WORDING = "SAFE_FOR_CURRENT_WORDING"
REQUIRES_QUALIFIED_LANGUAGE = "REQUIRES_QUALIFIED_LANGUAGE"
REQUIRES_OPERATIONAL_CONTEXT = "REQUIRES_OPERATIONAL_CONTEXT"
REQUIRES_VERIFICATION_CONTEXT = "REQUIRES_VERIFICATION_CONTEXT"
REQUIRES_FOLLOWUP_CONTEXT = "REQUIRES_FOLLOWUP_CONTEXT"
MUST_NOT_USE_COMPLIANT_LANGUAGE = "MUST_NOT_USE_COMPLIANT_LANGUAGE"
MUST_NOT_USE_CURRENT_LANGUAGE = "MUST_NOT_USE_CURRENT_LANGUAGE"

# Disclaimer requirements
NO_DISCLAIMER_REQUIRED = "NO_DISCLAIMER_REQUIRED"
FOLLOWUP_PENDING_DISCLAIMER = "FOLLOWUP_PENDING_DISCLAIMER"
NOT_INDEPENDENTLY_VERIFIED_DISCLAIMER = "NOT_INDEPENDENTLY_VERIFIED_DISCLAIMER"
PARTIAL_COMPLETENESS_DISCLAIMER = "PARTIAL_COMPLETENESS_DISCLAIMER"
EXPIRY_REVIEW_DISCLAIMER = "EXPIRY_REVIEW_DISCLAIMER"
OPERATIONALLY_OPEN_DISCLAIMER = "OPERATIONALLY_OPEN_DISCLAIMER"
HUMAN_CONFIRMATION_REQUIRED_DISCLAIMER = "HUMAN_CONFIRMATION_REQUIRED_DISCLAIMER"
UNKNOWN_DISCLAIMER_REQUIREMENT = "UNKNOWN_DISCLAIMER_REQUIREMENT"

# Report trust risk
LOW_TRUST_RISK = "LOW_TRUST_RISK"
MODERATE_TRUST_RISK = "MODERATE_TRUST_RISK"
HIGH_TRUST_RISK = "HIGH_TRUST_RISK"
CRITICAL_TRUST_RISK = "CRITICAL_TRUST_RISK"

# Export readiness
EXPORT_READY = "EXPORT_READY"
EXPORT_READY_WITH_CONTEXT = "EXPORT_READY_WITH_CONTEXT"
EXPORT_READY_WITH_DISCLAIMER = "EXPORT_READY_WITH_DISCLAIMER"
EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT = "EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT"
EXPORT_BLOCKED_PENDING_GOVERNANCE = "EXPORT_BLOCKED_PENDING_GOVERNANCE"

# Governance blockers
SEMANTIC_REPRESENTATION_BLOCKER = "SEMANTIC_REPRESENTATION_BLOCKER"
COMPLIANT_LANGUAGE_BLOCKER = "COMPLIANT_LANGUAGE_BLOCKER"
CURRENT_LANGUAGE_BLOCKER = "CURRENT_LANGUAGE_BLOCKER"
FOLLOWUP_VISIBILITY_BLOCKER = "FOLLOWUP_VISIBILITY_BLOCKER"
PARTIAL_COMPLETENESS_BLOCKER = "PARTIAL_COMPLETENESS_BLOCKER"
VERIFICATION_CONTEXT_BLOCKER = "VERIFICATION_CONTEXT_BLOCKER"
EXPIRY_AMBIGUITY_BLOCKER = "EXPIRY_AMBIGUITY_BLOCKER"
REPORT_TRUST_BLOCKER = "REPORT_TRUST_BLOCKER"
UNKNOWN_REPORTING_BLOCKER = "UNKNOWN_REPORTING_BLOCKER"

_STATE_MODEL_LIMITATION = (
    "Confirmation topology is synthesized from the propagation audit matrix; it does not observe "
    "actual acknowledgement payloads, webhook receipts, or human attestation records."
)
_RUNTIME_CONVERGENCE_LIMITATION = (
    "Inferred vs deterministic confirmation cannot be proven without runtime traces; audit uses "
    "declared propagation contracts only."
)

_HIGH_AUTHORITY_EXPORT_CONSUMERS = frozenset({REPORT_EXPORT, PORTFOLIO_SCORE})
_COMPACT_SURFACE_CONSUMERS = frozenset({CLIENT_STATUS_CHIP, PROPERTY_SUMMARY, DASHBOARD_SUMMARY})


def _triage_index(matrix: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in matrix:
        k = (str(row.get("semantic_transition") or ""), str(row.get("consumer") or ""))
        out[k] = row
    return out


def _resolve_triage_row(
    transition: str,
    consumer: str,
    index: Dict[Tuple[str, str], Dict[str, Any]],
) -> Tuple[Dict[str, Any], str]:
    """Return triage row and label of consumer that supplied triage data."""
    c = str(consumer or "").upper()
    direct = index.get((transition, c))
    if direct is not None:
        return direct, c
    proxy = _CONSUMER_TRIAGE_PROXY.get(c)
    if proxy:
        fallback = index.get((transition, proxy))
        if fallback is not None:
            return fallback, proxy
    return {}, "UNRESOLVED"


def _semantic_collapse_risk(transition: str, triage: Dict[str, Any]) -> str:
    t = str(transition or "").upper()
    blockers: Set[str] = set(triage.get("runtime_confirmation_blocker_reasons") or [])
    root = str(triage.get("root_cause_family") or "")
    gap = str(triage.get("confirmation_gap_classification") or "")

    if SEMANTIC_CONFIRMATION_COLLAPSE_RISK in blockers or root == SEMANTIC_COLLAPSE_DEBT:
        return MULTI_STATE_COLLAPSE
    if gap == STALE_CONFIRMATION_RISK and t not in ("VERIFIED_EXPIRED", "EXPIRY_REVIEW_REQUIRED"):
        return REPORTING_SIMPLIFICATION_COLLAPSE
    if t == "OPERATIONALLY_OPEN":
        return OPERATIONAL_OPEN_COLLAPSE
    if t in ("EXPIRY_REVIEW_REQUIRED", "VERIFIED_EXPIRED"):
        return EXPIRY_CURRENTNESS_COLLAPSE
    if t in ("FOLLOWUP_REQUIRED", "ASSESSMENT_FOLLOWUP_REQUIRED"):
        return FOLLOWUP_RESOLUTION_COLLAPSE
    if t in ("PARTIALLY_COMPLETE", "COMPLETENESS_PENDING"):
        return PARTIAL_COMPLETENESS_COLLAPSE
    if t in ("DECLARATION_RECORDED", "REGISTRATION_RECORDED", "TENANT_DELIVERY_RECORDED", "UPLOADED_UNCONFIRMED"):
        return DECLARATION_VERIFICATION_COLLAPSE
    if t == "VERIFIED_CURRENT":
        return NO_COLLAPSE_RISK
    if t == "MISSING":
        return REPORTING_SIMPLIFICATION_COLLAPSE
    return UNKNOWN_COLLAPSE_RISK


def _representation_safety(
    transition: str,
    consumer: str,
    collapse: str,
    triage: Dict[str, Any],
) -> str:
    c = str(consumer or "").upper()
    unsafe_impl = bool(triage.get("unsafe_to_implement"))
    gap_ok = str(triage.get("confirmation_gap_classification") or "") == CONFIRMATION_CONTRACT_SATISFIED

    if unsafe_impl or collapse == MULTI_STATE_COLLAPSE:
        return UNSAFE_FOR_SIMPLIFIED_REPORTING
    if collapse == REPORTING_SIMPLIFICATION_COLLAPSE or collapse == UNKNOWN_COLLAPSE_RISK:
        if c in _COMPACT_SURFACE_CONSUMERS:
            return UNSAFE_FOR_SIMPLIFIED_REPORTING
        return UNKNOWN_REPRESENTATION_SAFETY
    if collapse == OPERATIONAL_OPEN_COLLAPSE:
        return UNSAFE_FOR_COMPLIANT_LANGUAGE
    if collapse == EXPIRY_CURRENTNESS_COLLAPSE:
        return UNSAFE_FOR_CURRENT_LANGUAGE
    if collapse in (PARTIAL_COMPLETENESS_COLLAPSE, DECLARATION_VERIFICATION_COLLAPSE):
        if c == CLIENT_STATUS_CHIP:
            return UNSAFE_FOR_SIMPLIFIED_REPORTING
        return SAFE_WITH_CONTEXT
    if collapse == FOLLOWUP_RESOLUTION_COLLAPSE:
        return SAFE_WITH_DISCLAIMER
    if collapse == NO_COLLAPSE_RISK and gap_ok:
        return SAFE_FOR_DIRECT_REPRESENTATION
    if collapse == NO_COLLAPSE_RISK:
        return SAFE_WITH_CONTEXT
    return UNKNOWN_REPRESENTATION_SAFETY


def _language_governance(
    transition: str,
    collapse: str,
    representation: str,
    triage: Dict[str, Any],
) -> Tuple[bool, bool, List[str], List[str], str, str]:
    """compliant_allowed, current_allowed, required_contexts, prohibited_wording, compliant_class, current_class."""
    t = str(transition or "").upper()
    periodic_human = bool(triage.get("periodic_only_confirmation_bridge"))
    human_boundary = bool(triage.get("human_dependent_confirmation_boundary"))
    blockers: Set[str] = set(triage.get("runtime_confirmation_blocker_reasons") or [])

    required_contexts: List[str] = []
    prohibited: List[str] = []
    compliant_class = SAFE_FOR_COMPLIANT_WORDING
    current_class = SAFE_FOR_CURRENT_WORDING

    if representation == UNSAFE_FOR_SIMPLIFIED_REPORTING:
        compliant_class = MUST_NOT_USE_COMPLIANT_LANGUAGE
        current_class = MUST_NOT_USE_CURRENT_LANGUAGE
        prohibited.extend(["compliant", "fully compliant", "certified compliant", "audit-ready", "current", "up to date"])
    elif representation == UNSAFE_FOR_COMPLIANT_LANGUAGE:
        compliant_class = MUST_NOT_USE_COMPLIANT_LANGUAGE
        prohibited.append("compliant")
        prohibited.append("fully compliant")
        current_class = REQUIRES_QUALIFIED_LANGUAGE
        required_contexts.append(REQUIRES_OPERATIONAL_CONTEXT)
    elif representation == UNSAFE_FOR_CURRENT_LANGUAGE:
        current_class = MUST_NOT_USE_CURRENT_LANGUAGE
        prohibited.extend(["current", "up to date", "live status"])
        compliant_class = REQUIRES_QUALIFIED_LANGUAGE
    elif representation == SAFE_WITH_DISCLAIMER:
        compliant_class = REQUIRES_QUALIFIED_LANGUAGE
        current_class = REQUIRES_QUALIFIED_LANGUAGE
        required_contexts.append(REQUIRES_FOLLOWUP_CONTEXT)
        prohibited.extend(["closed", "resolved"])
    elif representation == SAFE_WITH_CONTEXT:
        compliant_class = REQUIRES_QUALIFIED_LANGUAGE
        current_class = REQUIRES_QUALIFIED_LANGUAGE
        required_contexts.append(REQUIRES_VERIFICATION_CONTEXT)
        if collapse == DECLARATION_VERIFICATION_COLLAPSE:
            prohibited.extend(["independently verified", "field-verified"])
    elif representation == UNKNOWN_REPRESENTATION_SAFETY:
        compliant_class = REQUIRES_QUALIFIED_LANGUAGE
        current_class = REQUIRES_QUALIFIED_LANGUAGE
        required_contexts.append(REQUIRES_VERIFICATION_CONTEXT)
    # SAFE_FOR_DIRECT_REPRESENTATION and any unclassified safety: keep SAFE_* wording defaults

    if human_boundary or periodic_human:
        if REQUIRES_OPERATIONAL_CONTEXT not in required_contexts:
            required_contexts.append(REQUIRES_OPERATIONAL_CONTEXT)
    if "NO_STALE_CONFIRMATION_DETECTION" in blockers or str(triage.get("confirmation_gap_classification") or "") == STALE_CONFIRMATION_RISK:
        current_class = MUST_NOT_USE_CURRENT_LANGUAGE
        prohibited.append("as-of timestamp implied")

    if t == "OPERATIONALLY_OPEN":
        prohibited.append("complete")

    required_contexts = sorted(set(required_contexts))
    prohibited = sorted(set(prohibited))
    compliant_ok = compliant_class == SAFE_FOR_COMPLIANT_WORDING
    current_ok = current_class == SAFE_FOR_CURRENT_WORDING
    return compliant_ok, current_ok, required_contexts, prohibited, compliant_class, current_class


def _disclaimer_requirement(collapse: str, triage: Dict[str, Any]) -> str:
    human_boundary = bool(triage.get("human_dependent_confirmation_boundary"))
    if collapse == NO_COLLAPSE_RISK:
        return NO_DISCLAIMER_REQUIRED
    if collapse == FOLLOWUP_RESOLUTION_COLLAPSE:
        return FOLLOWUP_PENDING_DISCLAIMER
    if collapse == DECLARATION_VERIFICATION_COLLAPSE:
        return NOT_INDEPENDENTLY_VERIFIED_DISCLAIMER
    if collapse == PARTIAL_COMPLETENESS_COLLAPSE:
        return PARTIAL_COMPLETENESS_DISCLAIMER
    if collapse == EXPIRY_CURRENTNESS_COLLAPSE:
        return EXPIRY_REVIEW_DISCLAIMER
    if collapse == OPERATIONAL_OPEN_COLLAPSE:
        return OPERATIONALLY_OPEN_DISCLAIMER
    if collapse == MULTI_STATE_COLLAPSE or collapse == REPORTING_SIMPLIFICATION_COLLAPSE:
        return PARTIAL_COMPLETENESS_DISCLAIMER
    if human_boundary:
        return HUMAN_CONFIRMATION_REQUIRED_DISCLAIMER
    if collapse == UNKNOWN_COLLAPSE_RISK:
        return UNKNOWN_DISCLAIMER_REQUIREMENT
    return UNKNOWN_DISCLAIMER_REQUIREMENT


def _trust_risk(
    consumer: str,
    representation: str,
    collapse: str,
    triage: Dict[str, Any],
) -> str:
    c = str(consumer or "").upper()
    score = 0
    if representation == UNSAFE_FOR_SIMPLIFIED_REPORTING:
        score += 4
    elif representation in (UNSAFE_FOR_COMPLIANT_LANGUAGE, UNSAFE_FOR_CURRENT_LANGUAGE):
        score += 3
    elif representation == UNKNOWN_REPRESENTATION_SAFETY:
        score += 2
    elif representation == SAFE_WITH_DISCLAIMER:
        score += 1
    elif representation == SAFE_WITH_CONTEXT:
        score += 1

    if collapse in (MULTI_STATE_COLLAPSE, REPORTING_SIMPLIFICATION_COLLAPSE):
        score += 3
    elif collapse in (OPERATIONAL_OPEN_COLLAPSE, EXPIRY_CURRENTNESS_COLLAPSE):
        score += 2
    elif collapse in (PARTIAL_COMPLETENESS_COLLAPSE, DECLARATION_VERIFICATION_COLLAPSE, UNKNOWN_COLLAPSE_RISK):
        score += 1

    if bool(triage.get("unsafe_to_implement")):
        score += 2
    if c in _HIGH_AUTHORITY_EXPORT_CONSUMERS:
        score += 1
    if c == CLIENT_STATUS_CHIP:
        score += 2
    if c in (DASHBOARD_SUMMARY, PROPERTY_SUMMARY):
        score += 1

    if score >= 8:
        return CRITICAL_TRUST_RISK
    if score >= 5:
        return HIGH_TRUST_RISK
    if score >= 2:
        return MODERATE_TRUST_RISK
    return LOW_TRUST_RISK


def _export_readiness(
    consumer: str,
    representation: str,
    trust: str,
    blockers: List[str],
    triage: Dict[str, Any],
) -> str:
    _ = consumer
    _ = blockers
    if bool(triage.get("unsafe_to_implement")):
        return EXPORT_BLOCKED_PENDING_GOVERNANCE
    if representation == UNSAFE_FOR_SIMPLIFIED_REPORTING or trust == CRITICAL_TRUST_RISK:
        return EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT
    if representation == SAFE_FOR_DIRECT_REPRESENTATION and trust == LOW_TRUST_RISK:
        return EXPORT_READY
    if representation == SAFE_WITH_CONTEXT:
        return EXPORT_READY_WITH_CONTEXT
    if representation == SAFE_WITH_DISCLAIMER:
        return EXPORT_READY_WITH_DISCLAIMER
    if representation in (UNSAFE_FOR_COMPLIANT_LANGUAGE, UNSAFE_FOR_CURRENT_LANGUAGE, UNKNOWN_REPRESENTATION_SAFETY):
        return EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT
    return EXPORT_READY_WITH_CONTEXT


def _governance_blockers(
    transition: str,
    consumer: str,
    representation: str,
    collapse: str,
    compliant_ok: bool,
    current_ok: bool,
    trust: str,
    triage: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    out: List[str] = []
    c = str(consumer or "").upper()
    gap = str(triage.get("confirmation_gap_classification") or "")
    blockers: Set[str] = set(triage.get("runtime_confirmation_blocker_reasons") or [])

    if representation == UNSAFE_FOR_SIMPLIFIED_REPORTING or collapse == MULTI_STATE_COLLAPSE:
        out.append(SEMANTIC_REPRESENTATION_BLOCKER)
    if not compliant_ok:
        out.append(COMPLIANT_LANGUAGE_BLOCKER)
    if not current_ok:
        out.append(CURRENT_LANGUAGE_BLOCKER)
    if collapse == FOLLOWUP_RESOLUTION_COLLAPSE:
        out.append(FOLLOWUP_VISIBILITY_BLOCKER)
    if collapse == PARTIAL_COMPLETENESS_COLLAPSE:
        out.append(PARTIAL_COMPLETENESS_BLOCKER)
    if collapse == DECLARATION_VERIFICATION_COLLAPSE:
        out.append(VERIFICATION_CONTEXT_BLOCKER)
    if collapse in (EXPIRY_CURRENTNESS_COLLAPSE,):
        out.append(EXPIRY_AMBIGUITY_BLOCKER)
    if trust in (HIGH_TRUST_RISK, CRITICAL_TRUST_RISK):
        out.append(REPORT_TRUST_BLOCKER)
    if gap == "ACKNOWLEDGEMENT_GAP" and c in _HIGH_AUTHORITY_EXPORT_CONSUMERS:
        out.append(VERIFICATION_CONTEXT_BLOCKER)
    if representation == UNKNOWN_REPRESENTATION_SAFETY or collapse == UNKNOWN_COLLAPSE_RISK:
        out.append(UNKNOWN_REPORTING_BLOCKER)

    out = sorted(set(out))
    blocked = bool(out)
    if bool(triage.get("unsafe_to_implement")):
        blocked = True
        if SEMANTIC_REPRESENTATION_BLOCKER not in out:
            out.insert(0, SEMANTIC_REPRESENTATION_BLOCKER)
        out = sorted(set(out))
    return blocked, out


def _count_by(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    acc: Dict[str, int] = {}
    for r in rows:
        k = str(r.get(key) or "")
        acc[k] = acc.get(k, 0) + 1
    return dict(sorted(acc.items()))


def _count_blockers(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    acc: Dict[str, int] = {}
    for r in rows:
        for b in r.get("reporting_governance_blockers") or []:
            acc[str(b)] = acc.get(str(b), 0) + 1
    return dict(sorted(acc.items()))


def build_reporting_semantic_governance_matrix(
    triage_matrix: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    base = triage_matrix if triage_matrix is not None else build_operational_confirmation_remediation_triage_matrix()
    index = _triage_index(base)
    out: List[Dict[str, Any]] = []

    for transition in SEMANTIC_TRANSITIONS:
        for consumer in REPORTING_GOVERNANCE_CONSUMERS:
            triage, triage_source = _resolve_triage_row(transition, consumer, index)
            collapse = _semantic_collapse_risk(transition, triage)
            representation = _representation_safety(transition, consumer, collapse, triage)
            comp_ok, cur_ok, req_ctx, prohib, comp_class, cur_class = _language_governance(
                transition, collapse, representation, triage
            )
            disclaimer = _disclaimer_requirement(collapse, triage)
            trust = _trust_risk(consumer, representation, collapse, triage)
            blocked, blockers = _governance_blockers(
                transition, consumer, representation, collapse, comp_ok, cur_ok, trust, triage
            )
            export = _export_readiness(consumer, representation, trust, blockers, triage)

            out.append(
                {
                    "semantic_transition": transition,
                    "consumer": consumer,
                    "governance_triage_source_consumer": triage_source,
                    "representation_safety": representation,
                    "semantic_collapse_risk": collapse,
                    "compliant_language_allowed": comp_ok,
                    "current_language_allowed": cur_ok,
                    "compliant_language_governance": comp_class,
                    "current_language_governance": cur_class,
                    "required_contexts": req_ctx,
                    "prohibited_wording": prohib,
                    "disclaimer_requirement": disclaimer,
                    "report_trust_risk": trust,
                    "export_readiness": export,
                    "reporting_governance_blocked": blocked,
                    "reporting_governance_blockers": blockers,
                    "triage_unsafe_to_implement": bool(triage.get("unsafe_to_implement")),
                    "triage_confirmation_gap_classification": str(triage.get("confirmation_gap_classification") or ""),
                }
            )

    return sorted(out, key=lambda r: (str(r.get("semantic_transition") or ""), str(r.get("consumer") or "")))


def build_reporting_semantic_governance_phase1_snapshot(
    governance_matrix: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    matrix = governance_matrix if governance_matrix is not None else build_reporting_semantic_governance_matrix()
    safest = sorted(
        [
            {"semantic_transition": r["semantic_transition"], "consumer": r["consumer"], "representation_safety": r["representation_safety"]}
            for r in matrix
            if r["representation_safety"] == SAFE_FOR_DIRECT_REPRESENTATION
        ],
        key=lambda x: (x["consumer"], x["semantic_transition"]),
    )
    highest_risk = sorted(
        [
            {
                "semantic_transition": r["semantic_transition"],
                "consumer": r["consumer"],
                "representation_safety": r["representation_safety"],
                "report_trust_risk": r["report_trust_risk"],
            }
            for r in matrix
            if r["representation_safety"] == UNSAFE_FOR_SIMPLIFIED_REPORTING or r["report_trust_risk"] == CRITICAL_TRUST_RISK
        ],
        key=lambda x: (x["consumer"], x["semantic_transition"]),
    )
    compliant_blocked = sorted(
        [{"semantic_transition": r["semantic_transition"], "consumer": r["consumer"]} for r in matrix if not r["compliant_language_allowed"]],
        key=lambda x: (x["consumer"], x["semantic_transition"]),
    )
    current_blocked = sorted(
        [{"semantic_transition": r["semantic_transition"], "consumer": r["consumer"]} for r in matrix if not r["current_language_allowed"]],
        key=lambda x: (x["consumer"], x["semantic_transition"]),
    )
    disclaimer_required = sorted(
        [
            {"semantic_transition": r["semantic_transition"], "consumer": r["consumer"], "disclaimer_requirement": r["disclaimer_requirement"]}
            for r in matrix
            if r["disclaimer_requirement"] != NO_DISCLAIMER_REQUIRED
        ],
        key=lambda x: (x["consumer"], x["semantic_transition"], x["disclaimer_requirement"]),
    )
    export_blocked = sorted(
        [
            {"semantic_transition": r["semantic_transition"], "consumer": r["consumer"], "export_readiness": r["export_readiness"]}
            for r in matrix
            if r["export_readiness"] in (EXPORT_BLOCKED_PENDING_GOVERNANCE, EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT)
        ],
        key=lambda x: (x["consumer"], x["semantic_transition"]),
    )

    return {
        "phase": "Reporting Semantic Governance Audit Phase 1",
        "scope": "audit-only semantic representation governance for reporting/export surfaces",
        "runtime_behavior_changed": False,
        "audit_only": True,
        "non_blocking": True,
        "reporting_governance_consumers": list(REPORTING_GOVERNANCE_CONSUMERS),
        "semantic_transitions": list(SEMANTIC_TRANSITIONS),
        "representation_safety_classifications": [
            SAFE_FOR_DIRECT_REPRESENTATION,
            SAFE_WITH_CONTEXT,
            SAFE_WITH_DISCLAIMER,
            UNSAFE_FOR_SIMPLIFIED_REPORTING,
            UNSAFE_FOR_COMPLIANT_LANGUAGE,
            UNSAFE_FOR_CURRENT_LANGUAGE,
            UNKNOWN_REPRESENTATION_SAFETY,
        ],
        "semantic_collapse_classifications": [
            NO_COLLAPSE_RISK,
            PARTIAL_COMPLETENESS_COLLAPSE,
            DECLARATION_VERIFICATION_COLLAPSE,
            FOLLOWUP_RESOLUTION_COLLAPSE,
            EXPIRY_CURRENTNESS_COLLAPSE,
            OPERATIONAL_OPEN_COLLAPSE,
            REPORTING_SIMPLIFICATION_COLLAPSE,
            MULTI_STATE_COLLAPSE,
            UNKNOWN_COLLAPSE_RISK,
        ],
        "language_governance_classifications": [
            SAFE_FOR_COMPLIANT_WORDING,
            SAFE_FOR_CURRENT_WORDING,
            REQUIRES_QUALIFIED_LANGUAGE,
            REQUIRES_OPERATIONAL_CONTEXT,
            REQUIRES_VERIFICATION_CONTEXT,
            REQUIRES_FOLLOWUP_CONTEXT,
            MUST_NOT_USE_COMPLIANT_LANGUAGE,
            MUST_NOT_USE_CURRENT_LANGUAGE,
        ],
        "disclaimer_classifications": [
            NO_DISCLAIMER_REQUIRED,
            FOLLOWUP_PENDING_DISCLAIMER,
            NOT_INDEPENDENTLY_VERIFIED_DISCLAIMER,
            PARTIAL_COMPLETENESS_DISCLAIMER,
            EXPIRY_REVIEW_DISCLAIMER,
            OPERATIONALLY_OPEN_DISCLAIMER,
            HUMAN_CONFIRMATION_REQUIRED_DISCLAIMER,
            UNKNOWN_DISCLAIMER_REQUIREMENT,
        ],
        "trust_risk_classifications": [LOW_TRUST_RISK, MODERATE_TRUST_RISK, HIGH_TRUST_RISK, CRITICAL_TRUST_RISK],
        "export_readiness_classifications": [
            EXPORT_READY,
            EXPORT_READY_WITH_CONTEXT,
            EXPORT_READY_WITH_DISCLAIMER,
            EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT,
            EXPORT_BLOCKED_PENDING_GOVERNANCE,
        ],
        "governance_blocker_classifications": [
            SEMANTIC_REPRESENTATION_BLOCKER,
            COMPLIANT_LANGUAGE_BLOCKER,
            CURRENT_LANGUAGE_BLOCKER,
            FOLLOWUP_VISIBILITY_BLOCKER,
            PARTIAL_COMPLETENESS_BLOCKER,
            VERIFICATION_CONTEXT_BLOCKER,
            EXPIRY_AMBIGUITY_BLOCKER,
            REPORT_TRUST_BLOCKER,
            UNKNOWN_REPORTING_BLOCKER,
        ],
        "reporting_governance_matrix": matrix,
        "safest_reporting_states": safest,
        "highest_reporting_risk_states": highest_risk,
        "compliant_language_blocked_states": compliant_blocked,
        "current_language_blocked_states": current_blocked,
        "disclaimer_required_states": disclaimer_required,
        "export_blocked_states": export_blocked,
        "trust_risk_summary": _count_by(matrix, "report_trust_risk"),
        "collapse_risk_summary": _count_by(matrix, "semantic_collapse_risk"),
        "representation_safety_summary": _count_by(matrix, "representation_safety"),
        "disclaimer_requirement_summary": _count_by(matrix, "disclaimer_requirement"),
        "export_readiness_summary": _count_by(matrix, "export_readiness"),
        "governance_blocker_summary": _count_blockers(matrix),
        "reporting_readiness_summary": _count_by(matrix, "export_readiness"),
        "remaining_state_model_limitation": _STATE_MODEL_LIMITATION,
        "remaining_runtime_convergence_limitation": _RUNTIME_CONVERGENCE_LIMITATION,
    }


def write_reporting_semantic_governance_phase1_json(target_path: Optional[Path] = None) -> Path:
    snap = build_reporting_semantic_governance_phase1_snapshot()
    base = Path(__file__).resolve().parents[1]
    path = target_path or (base / "docs" / "audit" / "REPORTING_SEMANTIC_GOVERNANCE_PHASE1.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
