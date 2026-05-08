from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from services.reporting_semantic_governance_audit import (
    build_reporting_semantic_governance_matrix,
)
from services.trigger_propagation_audit import SEMANTIC_TRANSITIONS

# --- Representation safety (contract vocabulary; aligns with Phase 1) ---
SAFE_FOR_DIRECT_REPRESENTATION = "SAFE_FOR_DIRECT_REPRESENTATION"
SAFE_WITH_CONTEXT = "SAFE_WITH_CONTEXT"
SAFE_WITH_DISCLAIMER = "SAFE_WITH_DISCLAIMER"
UNSAFE_FOR_SIMPLIFIED_REPORTING = "UNSAFE_FOR_SIMPLIFIED_REPORTING"
UNSAFE_FOR_COMPLIANT_LANGUAGE = "UNSAFE_FOR_COMPLIANT_LANGUAGE"
UNSAFE_FOR_CURRENT_LANGUAGE = "UNSAFE_FOR_CURRENT_LANGUAGE"
UNKNOWN_REPRESENTATION_SAFETY = "UNKNOWN_REPRESENTATION_SAFETY"

# --- Copy governance (Phase 2) ---
ALLOWED_WORDING = "ALLOWED_WORDING"
CONTEXT_REQUIRED = "CONTEXT_REQUIRED"
DISCLAIMER_REQUIRED = "DISCLAIMER_REQUIRED"
PROHIBITED_WORDING = "PROHIBITED_WORDING"
HUMAN_REVIEW_RECOMMENDED = "HUMAN_REVIEW_RECOMMENDED"

# --- Disclosure requirements (Phase 2 naming) ---
NO_DISCLOSURE_REQUIRED = "NO_DISCLOSURE_REQUIRED"
FOLLOWUP_PENDING_DISCLOSURE = "FOLLOWUP_PENDING_DISCLOSURE"
PARTIAL_COMPLETENESS_DISCLOSURE = "PARTIAL_COMPLETENESS_DISCLOSURE"
NOT_INDEPENDENTLY_VERIFIED_DISCLOSURE = "NOT_INDEPENDENTLY_VERIFIED_DISCLOSURE"
EXPIRY_REVIEW_DISCLOSURE = "EXPIRY_REVIEW_DISCLOSURE"
OPERATIONALLY_OPEN_DISCLOSURE = "OPERATIONALLY_OPEN_DISCLOSURE"
HUMAN_CONFIRMATION_DISCLOSURE = "HUMAN_CONFIRMATION_DISCLOSURE"
UNKNOWN_DISCLOSURE_REQUIREMENT = "UNKNOWN_DISCLOSURE_REQUIREMENT"

# --- Trust / export (Phase 2 export uses DISCLOSURE suffix) ---
LOW_TRUST_RISK = "LOW_TRUST_RISK"
MODERATE_TRUST_RISK = "MODERATE_TRUST_RISK"
HIGH_TRUST_RISK = "HIGH_TRUST_RISK"
CRITICAL_TRUST_RISK = "CRITICAL_TRUST_RISK"

EXPORT_READY = "EXPORT_READY"
EXPORT_READY_WITH_CONTEXT = "EXPORT_READY_WITH_CONTEXT"
EXPORT_READY_WITH_DISCLOSURE = "EXPORT_READY_WITH_DISCLOSURE"
EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT = "EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT"
EXPORT_BLOCKED_PENDING_GOVERNANCE = "EXPORT_BLOCKED_PENDING_GOVERNANCE"

# --- Unsafe wording exposure (audit signals) ---
EXPOSURE_SEMANTIC_COLLAPSE = "SEMANTIC_COLLAPSE_EXPOSURE"
EXPOSURE_COMPLIANT_LANGUAGE = "COMPLIANT_LANGUAGE_EXPOSURE"
EXPOSURE_CURRENT_LANGUAGE = "CURRENT_LANGUAGE_EXPOSURE"
EXPOSURE_OPERATIONAL_CLOSURE = "OPERATIONAL_CLOSURE_EXPOSURE"
EXPOSURE_EXPIRY_VALIDITY = "EXPIRY_VALIDITY_EXPOSURE"
EXPOSURE_FOLLOWUP_SUPPRESSION = "FOLLOWUP_SUPPRESSION_EXPOSURE"

# Target consumers for Phase 2 contract matrix
REPORT_EXPORT = "REPORT_EXPORT"
PORTFOLIO_SCORE = "PORTFOLIO_SCORE"
CLIENT_STATUS_CHIP = "CLIENT_STATUS_CHIP"

PHASE2_CONTRACT_CONSUMERS: Tuple[str, ...] = (REPORT_EXPORT, PORTFOLIO_SCORE, CLIENT_STATUS_CHIP)

_STRICT = "STRICT"
_STANDARD = "STANDARD"
_RELAXED = "RELAXED"

_MAX_SIMPLIFICATION_NONE = "NONE"
_MAX_SIMPLIFICATION_LOW = "LOW"
_MAX_SIMPLIFICATION_MODERATE = "MODERATE"

_STATE_MODEL_LIMITATION = (
    "Confirmation topology is synthesized from the propagation audit matrix; it does not observe "
    "actual acknowledgement payloads, webhook receipts, or human attestation records."
)
_RUNTIME_CONVERGENCE_LIMITATION = (
    "Inferred vs deterministic confirmation cannot be proven without runtime traces; audit uses "
    "declared propagation contracts only."
)


def _sorted_unique(seq: Sequence[str]) -> List[str]:
    return sorted({str(x) for x in seq if x})


# Deterministic base contract per semantic state (governance-only; not UI copy)
_SEMANTIC_WORDING_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "MISSING": {
        "allowed_wording": ["not recorded", "no submission on file", "awaiting record"],
        "prohibited_wording": ["compliant", "complete", "current", "verified", "passed"],
        "required_contexts": ["absence of evidence must be explicit"],
        "required_disclosures": [UNKNOWN_DISCLOSURE_REQUIREMENT],
        "unsafe_simplifications": ["treat as compliant by default", "omit missing state"],
        "representation_safety": UNKNOWN_REPRESENTATION_SAFETY,
        "trust_risk": HIGH_TRUST_RISK,
        "export_readiness": EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT,
    },
    "VERIFIED_CURRENT": {
        "allowed_wording": ["verified current", "meets declared verification standard", "on file as verified"],
        "prohibited_wording": ["guaranteed field condition", "independently audited", "legal warranty"],
        "required_contexts": ["verification scope and date if shown"],
        "required_disclosures": [NO_DISCLOSURE_REQUIRED],
        "unsafe_simplifications": ["collapse to score without evidence line"],
        "representation_safety": SAFE_FOR_DIRECT_REPRESENTATION,
        "trust_risk": LOW_TRUST_RISK,
        "export_readiness": EXPORT_READY,
    },
    "VERIFIED_EXPIRED": {
        "allowed_wording": ["expired verification", "past validity window", "renewal required"],
        "prohibited_wording": ["current", "valid now", "compliant", "up to date"],
        "required_contexts": ["expiry basis must be visible"],
        "required_disclosures": [EXPIRY_REVIEW_DISCLOSURE],
        "unsafe_simplifications": ["label as current certificate"],
        "representation_safety": UNSAFE_FOR_CURRENT_LANGUAGE,
        "trust_risk": MODERATE_TRUST_RISK,
        "export_readiness": EXPORT_READY_WITH_DISCLOSURE,
    },
    "UPLOADED_UNCONFIRMED": {
        "allowed_wording": ["uploaded pending review", "awaiting confirmation", "not yet attested"],
        "prohibited_wording": ["verified", "compliant", "fully compliant", "current certificate"],
        "required_contexts": ["upload does not equal verification"],
        "required_disclosures": [NOT_INDEPENDENTLY_VERIFIED_DISCLOSURE],
        "unsafe_simplifications": ["treat upload as proof"],
        "representation_safety": SAFE_WITH_CONTEXT,
        "trust_risk": MODERATE_TRUST_RISK,
        "export_readiness": EXPORT_READY_WITH_CONTEXT,
    },
    "PARTIALLY_COMPLETE": {
        "allowed_wording": ["partially complete", "additional evidence required", "incomplete submission"],
        "prohibited_wording": ["complete", "compliant", "resolved", "closed"],
        "required_contexts": ["list outstanding requirements where space allows"],
        "required_disclosures": [PARTIAL_COMPLETENESS_DISCLOSURE],
        "unsafe_simplifications": ["green status", "done"],
        "representation_safety": SAFE_WITH_CONTEXT,
        "trust_risk": MODERATE_TRUST_RISK,
        "export_readiness": EXPORT_READY_WITH_DISCLOSURE,
    },
    "DECLARATION_RECORDED": {
        "allowed_wording": ["self-declared", "declaration on file", "declarant attestation recorded"],
        "prohibited_wording": ["compliant", "verified", "fully compliant", "current certificate"],
        "required_contexts": ["declaration is not third-party verification"],
        "required_disclosures": [NOT_INDEPENDENTLY_VERIFIED_DISCLOSURE],
        "unsafe_simplifications": ["map declaration to compliance badge"],
        "representation_safety": SAFE_WITH_DISCLAIMER,
        "trust_risk": MODERATE_TRUST_RISK,
        "export_readiness": EXPORT_READY_WITH_DISCLOSURE,
    },
    "REGISTRATION_RECORDED": {
        "allowed_wording": ["registration recorded", "registry event captured"],
        "prohibited_wording": ["compliant", "verified outcome", "fully compliant"],
        "required_contexts": ["registration ≠ operational closure"],
        "required_disclosures": [NOT_INDEPENDENTLY_VERIFIED_DISCLOSURE],
        "unsafe_simplifications": ["registration implies compliance"],
        "representation_safety": SAFE_WITH_DISCLAIMER,
        "trust_risk": MODERATE_TRUST_RISK,
        "export_readiness": EXPORT_READY_WITH_DISCLOSURE,
    },
    "TENANT_DELIVERY_RECORDED": {
        "allowed_wording": ["delivery event recorded", "handover recorded"],
        "prohibited_wording": ["compliant", "resolved", "all obligations closed"],
        "required_contexts": ["delivery record may omit follow-up work"],
        "required_disclosures": [PARTIAL_COMPLETENESS_DISCLOSURE],
        "unsafe_simplifications": ["tenant delivered = complete compliance"],
        "representation_safety": SAFE_WITH_CONTEXT,
        "trust_risk": MODERATE_TRUST_RISK,
        "export_readiness": EXPORT_READY_WITH_CONTEXT,
    },
    "ASSESSMENT_FOLLOWUP_REQUIRED": {
        "allowed_wording": ["follow-up outstanding", "remediation may still be required", "assessment action pending"],
        "prohibited_wording": ["passed", "completed", "resolved", "closed"],
        "required_contexts": ["follow-up type and owner if known"],
        "required_disclosures": [FOLLOWUP_PENDING_DISCLOSURE],
        "unsafe_simplifications": ["suppress open follow-up"],
        "representation_safety": SAFE_WITH_DISCLAIMER,
        "trust_risk": HIGH_TRUST_RISK,
        "export_readiness": EXPORT_READY_WITH_DISCLOSURE,
    },
    "OPERATIONALLY_OPEN": {
        "allowed_wording": ["operationally open", "work in progress", "not closed operationally"],
        "prohibited_wording": ["compliant", "complete", "resolved", "closed"],
        "required_contexts": ["operational state differs from documentary state"],
        "required_disclosures": [OPERATIONALLY_OPEN_DISCLOSURE],
        "unsafe_simplifications": ["show as done in rollup"],
        "representation_safety": UNSAFE_FOR_COMPLIANT_LANGUAGE,
        "trust_risk": HIGH_TRUST_RISK,
        "export_readiness": EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT,
    },
    "FOLLOWUP_REQUIRED": {
        "allowed_wording": ["follow-up required", "pending response", "action needed"],
        "prohibited_wording": ["resolved", "closed", "passed", "completed"],
        "required_contexts": ["follow-up visibility"],
        "required_disclosures": [FOLLOWUP_PENDING_DISCLOSURE],
        "unsafe_simplifications": ["hide pending follow-up"],
        "representation_safety": SAFE_WITH_DISCLAIMER,
        "trust_risk": MODERATE_TRUST_RISK,
        "export_readiness": EXPORT_READY_WITH_DISCLOSURE,
    },
    "COMPLETENESS_PENDING": {
        "allowed_wording": ["completeness pending", "awaiting further evidence"],
        "prohibited_wording": ["complete", "compliant", "audit-ready"],
        "required_contexts": ["what is missing at high level"],
        "required_disclosures": [PARTIAL_COMPLETENESS_DISCLOSURE],
        "unsafe_simplifications": ["treat as complete for scoring"],
        "representation_safety": SAFE_WITH_CONTEXT,
        "trust_risk": MODERATE_TRUST_RISK,
        "export_readiness": EXPORT_READY_WITH_DISCLOSURE,
    },
    "EXPIRY_REVIEW_REQUIRED": {
        "allowed_wording": ["expiry review required", "validity requires review", "renewal or review pending"],
        "prohibited_wording": ["current", "valid", "compliant", "up to date"],
        "required_contexts": ["review basis"],
        "required_disclosures": [EXPIRY_REVIEW_DISCLOSURE],
        "unsafe_simplifications": ["valid until stated without review flag"],
        "representation_safety": UNSAFE_FOR_CURRENT_LANGUAGE,
        "trust_risk": HIGH_TRUST_RISK,
        "export_readiness": EXPORT_READY_WITH_DISCLOSURE,
    },
}


def semantic_wording_contract_base(semantic_state: str) -> Dict[str, Any]:
    t = str(semantic_state or "").upper()
    base = _SEMANTIC_WORDING_CONTRACTS.get(t)
    if base is None:
        return {
            "allowed_wording": [],
            "prohibited_wording": ["compliant", "verified", "complete"],
            "required_contexts": ["unknown semantic boundary"],
            "required_disclosures": [UNKNOWN_DISCLOSURE_REQUIREMENT],
            "unsafe_simplifications": ["any single-word status"],
            "representation_safety": UNKNOWN_REPRESENTATION_SAFETY,
            "trust_risk": HIGH_TRUST_RISK,
            "export_readiness": EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT,
        }
    return {k: (list(v) if isinstance(v, list) else v) for k, v in base.items()}


_CONSUMER_SIMPLIFICATION_POLICIES: Dict[str, Dict[str, Any]] = {
    REPORT_EXPORT: {
        "maximum_simplification_allowed": _MAX_SIMPLIFICATION_LOW,
        "disclosure_strictness": _STRICT,
        "wording_strictness": _STRICT,
        "export_safe_wording": [
            "use full disclosure lines from contract",
            "avoid headline-only compliance claims",
            "pair numeric facts with disclosure class",
        ],
        "score_safe_wording": [],
        "chip_safe_wording": [],
    },
    PORTFOLIO_SCORE: {
        "maximum_simplification_allowed": _MAX_SIMPLIFICATION_LOW,
        "disclosure_strictness": _STANDARD,
        "wording_strictness": _STRICT,
        "score_safe_wording": [
            "score reflects recorded signals not operational closure",
            "do not imply all obligations satisfied",
            "defer single-word compliance labels",
        ],
        "export_safe_wording": [],
        "chip_safe_wording": [],
    },
    CLIENT_STATUS_CHIP: {
        "maximum_simplification_allowed": _MAX_SIMPLIFICATION_NONE,
        "disclosure_strictness": _STRICT,
        "wording_strictness": _STRICT,
        "chip_safe_wording": [
            "short labels only when VERIFIED_CURRENT and export_readiness EXPORT_READY",
            "otherwise use neutral non-compliant tokens",
            "never chip-map to compliant/current without disclosure",
        ],
        "export_safe_wording": [],
        "score_safe_wording": [],
    },
}


def consumer_simplification_policy(consumer: str) -> Dict[str, Any]:
    c = str(consumer or "").upper()
    policy = _CONSUMER_SIMPLIFICATION_POLICIES.get(c, {})
    return {k: (list(v) if isinstance(v, list) else v) for k, v in policy.items()}


def _copy_governance_primary(
    representation: str,
    required_contexts: List[str],
    required_disclosures: List[str],
    trust: str,
) -> str:
    if representation == UNSAFE_FOR_SIMPLIFIED_REPORTING:
        return PROHIBITED_WORDING
    if any(d != NO_DISCLOSURE_REQUIRED for d in required_disclosures):
        return DISCLAIMER_REQUIRED
    if required_contexts:
        return CONTEXT_REQUIRED
    if trust in (HIGH_TRUST_RISK, CRITICAL_TRUST_RISK):
        return HUMAN_REVIEW_RECOMMENDED
    if representation in (UNSAFE_FOR_COMPLIANT_LANGUAGE, UNSAFE_FOR_CURRENT_LANGUAGE):
        return PROHIBITED_WORDING
    return ALLOWED_WORDING


def _map_phase1_export_to_phase2(phase1_export: str) -> str:
    if phase1_export == "EXPORT_READY_WITH_DISCLAIMER":
        return EXPORT_READY_WITH_DISCLOSURE
    return str(phase1_export or "")


def _phase1_row_index(matrix: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    return {(str(r["semantic_transition"]), str(r["consumer"])): r for r in matrix}


def _merge_trust_export(
    semantic_state: str,
    base_trust: str,
    base_export: str,
    consumer: str,
    representation: str,
    phase1_row: Optional[Dict[str, Any]],
) -> Tuple[str, str]:
    trust = base_trust
    export = _map_phase1_export_to_phase2(base_export)
    c = str(consumer or "").upper()
    t = str(semantic_state or "").upper()

    if c == CLIENT_STATUS_CHIP:
        if trust == LOW_TRUST_RISK:
            trust = MODERATE_TRUST_RISK
        elif trust == MODERATE_TRUST_RISK:
            trust = HIGH_TRUST_RISK
        if representation != SAFE_FOR_DIRECT_REPRESENTATION:
            export = EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT
    elif c == REPORT_EXPORT:
        if trust != LOW_TRUST_RISK:
            trust = HIGH_TRUST_RISK if trust == MODERATE_TRUST_RISK else trust
        if representation not in (SAFE_FOR_DIRECT_REPRESENTATION, SAFE_WITH_CONTEXT):
            if export == EXPORT_READY:
                export = EXPORT_READY_WITH_DISCLOSURE
    elif c == PORTFOLIO_SCORE:
        if (
            t == "OPERATIONALLY_OPEN"
            or representation == UNSAFE_FOR_COMPLIANT_LANGUAGE
            or representation == UNSAFE_FOR_SIMPLIFIED_REPORTING
        ):
            trust = CRITICAL_TRUST_RISK if trust != CRITICAL_TRUST_RISK else trust
        if representation == SAFE_FOR_DIRECT_REPRESENTATION and export == EXPORT_READY:
            export = EXPORT_READY_WITH_CONTEXT

    if phase1_row and bool(phase1_row.get("triage_unsafe_to_implement")):
        export = EXPORT_BLOCKED_PENDING_GOVERNANCE

    return trust, export


def _unsafe_wording_exposures(
    semantic_state: str,
    representation: str,
    prohibited_wording: List[str],
    required_disclosures: List[str],
) -> List[str]:
    t = str(semantic_state or "").upper()
    out: List[str] = []
    if representation == UNSAFE_FOR_SIMPLIFIED_REPORTING or (
        t in ("MISSING", "PARTIALLY_COMPLETE", "COMPLETENESS_PENDING") and representation == UNKNOWN_REPRESENTATION_SAFETY
    ):
        out.append(EXPOSURE_SEMANTIC_COLLAPSE)
    if representation == UNSAFE_FOR_COMPLIANT_LANGUAGE or any(
        x in ("compliant", "fully compliant") for x in prohibited_wording
    ):
        out.append(EXPOSURE_COMPLIANT_LANGUAGE)
    if representation == UNSAFE_FOR_CURRENT_LANGUAGE or any(x in ("current", "valid", "up to date") for x in prohibited_wording):
        out.append(EXPOSURE_CURRENT_LANGUAGE)
    if t == "OPERATIONALLY_OPEN" or OPERATIONALLY_OPEN_DISCLOSURE in required_disclosures:
        out.append(EXPOSURE_OPERATIONAL_CLOSURE)
    if t in ("EXPIRY_REVIEW_REQUIRED", "VERIFIED_EXPIRED") or EXPIRY_REVIEW_DISCLOSURE in required_disclosures:
        out.append(EXPOSURE_EXPIRY_VALIDITY)
    if t in ("ASSESSMENT_FOLLOWUP_REQUIRED", "FOLLOWUP_REQUIRED") or FOLLOWUP_PENDING_DISCLOSURE in required_disclosures:
        out.append(EXPOSURE_FOLLOWUP_SUPPRESSION)
    return _sorted_unique(out)


def build_semantic_copy_contract_row(
    semantic_state: str,
    consumer: str,
    phase1_matrix: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    base = semantic_wording_contract_base(semantic_state)
    policy = consumer_simplification_policy(consumer)
    representation = str(base["representation_safety"])
    trust = str(base["trust_risk"])
    export = str(base["export_readiness"])

    matrix = phase1_matrix if phase1_matrix is not None else build_reporting_semantic_governance_matrix()
    idx = _phase1_row_index(matrix)
    p1 = idx.get((str(semantic_state or "").upper(), str(consumer or "").upper()))

    if p1:
        representation = str(p1.get("representation_safety") or representation)
        trust = str(p1.get("report_trust_risk") or trust)
        export = _map_phase1_export_to_phase2(str(p1.get("export_readiness") or export))

    trust, export = _merge_trust_export(str(semantic_state or "").upper(), trust, export, consumer, representation, p1)

    allowed = _sorted_unique(base["allowed_wording"])
    prohibited = _sorted_unique(base["prohibited_wording"])
    contexts = _sorted_unique(base["required_contexts"])
    disclosures = _sorted_unique(base["required_disclosures"])

    copy_gov = _copy_governance_primary(representation, contexts, disclosures, trust)
    exposures = _unsafe_wording_exposures(semantic_state, representation, prohibited, disclosures)

    return {
        "semantic_state": str(semantic_state or "").upper(),
        "consumer": str(consumer or "").upper(),
        "allowed_wording": allowed,
        "prohibited_wording": prohibited,
        "required_contexts": contexts,
        "required_disclosures": disclosures,
        "unsafe_simplifications": _sorted_unique(base["unsafe_simplifications"]),
        "representation_safety": representation,
        "trust_risk": trust,
        "export_readiness": export,
        "copy_governance_primary": copy_gov,
        "consumer_simplification_policy": policy,
        "unsafe_wording_exposures": exposures,
    }


def build_reporting_semantic_copy_contract_matrix(
    phase1_matrix: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    rows = [
        build_semantic_copy_contract_row(t, c, phase1_matrix)
        for t in SEMANTIC_TRANSITIONS
        for c in PHASE2_CONTRACT_CONSUMERS
    ]
    return sorted(rows, key=lambda r: (r["semantic_state"], r["consumer"]))


def audit_reporting_wording_contract(semantic_state: str, consumer: str) -> Dict[str, Any]:
    row = build_semantic_copy_contract_row(semantic_state, consumer)
    return {
        "semantic_state": row["semantic_state"],
        "consumer": row["consumer"],
        "allowed_wording": row["allowed_wording"],
        "prohibited_wording": row["prohibited_wording"],
        "required_contexts": row["required_contexts"],
        "copy_governance_primary": row["copy_governance_primary"],
        "prohibited_wording_enforced": bool(row["prohibited_wording"]),
    }


def audit_reporting_disclosure_contract(semantic_state: str, consumer: str) -> Dict[str, Any]:
    row = build_semantic_copy_contract_row(semantic_state, consumer)
    disclosures = row["required_disclosures"]
    return {
        "semantic_state": row["semantic_state"],
        "consumer": row["consumer"],
        "required_disclosures": disclosures,
        "disclosure_strictness": row["consumer_simplification_policy"].get("disclosure_strictness"),
        "disclosure_required": any(d != NO_DISCLOSURE_REQUIRED for d in disclosures),
    }


def audit_reporting_representation_risk(semantic_state: str, consumer: str) -> Dict[str, Any]:
    row = build_semantic_copy_contract_row(semantic_state, consumer)
    return {
        "semantic_state": row["semantic_state"],
        "consumer": row["consumer"],
        "representation_safety": row["representation_safety"],
        "unsafe_wording_exposures": row["unsafe_wording_exposures"],
        "unsafe_simplifications": row["unsafe_simplifications"],
    }


def audit_reporting_export_readiness(semantic_state: str, consumer: str) -> Dict[str, Any]:
    row = build_semantic_copy_contract_row(semantic_state, consumer)
    return {
        "semantic_state": row["semantic_state"],
        "consumer": row["consumer"],
        "export_readiness": row["export_readiness"],
        "trust_risk": row["trust_risk"],
        "maximum_simplification_allowed": row["consumer_simplification_policy"].get("maximum_simplification_allowed"),
    }


def _count_by(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    acc: Dict[str, int] = {}
    for r in rows:
        k = str(r.get(key) or "")
        acc[k] = acc.get(k, 0) + 1
    return dict(sorted(acc.items()))


def _count_exposures(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    acc: Dict[str, int] = {}
    for r in rows:
        for e in r.get("unsafe_wording_exposures") or []:
            acc[str(e)] = acc.get(str(e), 0) + 1
    return dict(sorted(acc.items()))


def build_reporting_semantic_governance_phase2_snapshot(
    contract_matrix: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    matrix = contract_matrix if contract_matrix is not None else build_reporting_semantic_copy_contract_matrix()
    wording_contracts_by_state = {t: semantic_wording_contract_base(t) for t in SEMANTIC_TRANSITIONS}
    consumer_policies = {c: consumer_simplification_policy(c) for c in PHASE2_CONTRACT_CONSUMERS}

    safest_states = sorted(
        {r["semantic_state"] for r in matrix if r["representation_safety"] == SAFE_FOR_DIRECT_REPRESENTATION}
    )
    highest_risk_states = sorted(
        {
            r["semantic_state"]
            for r in matrix
            if r["representation_safety"] == UNSAFE_FOR_SIMPLIFIED_REPORTING or r["trust_risk"] == CRITICAL_TRUST_RISK
        }
    )
    export_blocked = sorted(
        [
            {"semantic_state": r["semantic_state"], "consumer": r["consumer"], "export_readiness": r["export_readiness"]}
            for r in matrix
            if r["export_readiness"] in (EXPORT_BLOCKED_PENDING_GOVERNANCE, EXPORT_NOT_READY_FOR_SIMPLIFIED_OUTPUT)
        ],
        key=lambda x: (x["consumer"], x["semantic_state"]),
    )
    trust_ranking = sorted(
        [
            {
                "semantic_state": r["semantic_state"],
                "consumer": r["consumer"],
                "trust_risk": r["trust_risk"],
                "representation_safety": r["representation_safety"],
            }
            for r in matrix
        ],
        key=lambda x: (
            {"CRITICAL_TRUST_RISK": 0, "HIGH_TRUST_RISK": 1, "MODERATE_TRUST_RISK": 2, "LOW_TRUST_RISK": 3}.get(
                x["trust_risk"], 9
            ),
            x["consumer"],
            x["semantic_state"],
        ),
    )

    prohibited_matrix = [
        {"semantic_state": r["semantic_state"], "consumer": r["consumer"], "prohibited_wording": r["prohibited_wording"]}
        for r in matrix
    ]

    return {
        "phase": "Reporting Semantic Governance Phase 2 — Copy / Disclosure Contract",
        "scope": "deterministic wording and disclosure governance; audit-only",
        "runtime_behavior_changed": False,
        "audit_only": True,
        "non_blocking": True,
        "semantic_transitions": list(SEMANTIC_TRANSITIONS),
        "phase2_contract_consumers": list(PHASE2_CONTRACT_CONSUMERS),
        "representation_safety_classifications": [
            SAFE_FOR_DIRECT_REPRESENTATION,
            SAFE_WITH_CONTEXT,
            SAFE_WITH_DISCLAIMER,
            UNSAFE_FOR_SIMPLIFIED_REPORTING,
            UNSAFE_FOR_COMPLIANT_LANGUAGE,
            UNSAFE_FOR_CURRENT_LANGUAGE,
            UNKNOWN_REPRESENTATION_SAFETY,
        ],
        "copy_governance_classifications": [
            ALLOWED_WORDING,
            CONTEXT_REQUIRED,
            DISCLAIMER_REQUIRED,
            PROHIBITED_WORDING,
            HUMAN_REVIEW_RECOMMENDED,
        ],
        "disclosure_classifications": [
            NO_DISCLOSURE_REQUIRED,
            FOLLOWUP_PENDING_DISCLOSURE,
            PARTIAL_COMPLETENESS_DISCLOSURE,
            NOT_INDEPENDENTLY_VERIFIED_DISCLOSURE,
            EXPIRY_REVIEW_DISCLOSURE,
            OPERATIONALLY_OPEN_DISCLOSURE,
            HUMAN_CONFIRMATION_DISCLOSURE,
            UNKNOWN_DISCLOSURE_REQUIREMENT,
        ],
        "semantic_wording_contracts_by_state": wording_contracts_by_state,
        "consumer_simplification_policies": consumer_policies,
        "reporting_semantic_copy_contract_matrix": matrix,
        "prohibited_wording_matrix": prohibited_matrix,
        "safest_reporting_states": safest_states,
        "highest_risk_semantic_states": highest_risk_states,
        "export_blocked_states": export_blocked,
        "trust_risk_rankings": trust_ranking,
        "representation_safety_summary": _count_by(matrix, "representation_safety"),
        "copy_governance_summary": _count_by(matrix, "copy_governance_primary"),
        "export_readiness_summary": _count_by(matrix, "export_readiness"),
        "trust_risk_summary": _count_by(matrix, "trust_risk"),
        "unsafe_wording_exposure_summary": _count_exposures(matrix),
        "remaining_state_model_limitation": _STATE_MODEL_LIMITATION,
        "remaining_runtime_convergence_limitation": _RUNTIME_CONVERGENCE_LIMITATION,
    }


def write_reporting_semantic_governance_phase2_json(target_path: Optional[Path] = None) -> Path:
    snap = build_reporting_semantic_governance_phase2_snapshot()
    base = Path(__file__).resolve().parents[1]
    path = target_path or (base / "docs" / "audit" / "REPORTING_SEMANTIC_GOVERNANCE_PHASE2.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
