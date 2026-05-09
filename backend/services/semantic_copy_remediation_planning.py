from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from services.live_semantic_copy_audit import (
    CLIENT_STATUS_CHIP,
    CURRENTNESS_COLLAPSE,
    MISSING_REQUIRED_DISCLOSURE,
    OPERATIONAL_CLOSURE_COLLAPSE,
    PORTFOLIO_SCORE,
    PROHIBITED_WORDING_VIOLATION,
    REPORT_EXPORT,
    SEMANTIC_COLLAPSE_RISK,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MODERATE,
    UNKNOWN_SEMANTIC_MAPPING,
    UNSAFE_SIMPLIFICATION,
    VERIFICATION_COLLAPSE,
    build_semantic_copy_inventory,
    evaluate_inventory_violations,
    extract_live_semantic_strings,
    map_audit_consumer_to_contract_consumer,
)
from services.trigger_propagation_audit import SEMANTIC_TRANSITIONS

# --- Priority tiers (deterministic remediation sequencing) ---
P0_CRITICAL_TRUST_RISK = "P0_CRITICAL_TRUST_RISK"
P1_HIGH_RISK_EXTERNAL_REPRESENTATION = "P1_HIGH_RISK_EXTERNAL_REPRESENTATION"
P2_HIGH_RISK_SIMPLIFICATION = "P2_HIGH_RISK_SIMPLIFICATION"
P3_DISCLOSURE_GAP = "P3_DISCLOSURE_GAP"
P4_CONTEXT_ALIGNMENT = "P4_CONTEXT_ALIGNMENT"
P5_LOW_PRIORITY_GOVERNANCE = "P5_LOW_PRIORITY_GOVERNANCE"
P6_OBSERVE_ONLY = "P6_OBSERVE_ONLY"

_PRIORITY_RANK: Dict[str, int] = {
    P0_CRITICAL_TRUST_RISK: 0,
    P1_HIGH_RISK_EXTERNAL_REPRESENTATION: 1,
    P2_HIGH_RISK_SIMPLIFICATION: 2,
    P3_DISCLOSURE_GAP: 3,
    P4_CONTEXT_ALIGNMENT: 4,
    P5_LOW_PRIORITY_GOVERNANCE: 5,
    P6_OBSERVE_ONLY: 6,
}

# --- Compression / simplification safety ---
NO_SIMPLIFICATION_ALLOWED = "NO_SIMPLIFICATION_ALLOWED"
LIMITED_SIMPLIFICATION = "LIMITED_SIMPLIFICATION"
DISCLOSURE_REQUIRED_FOR_SIMPLIFICATION = "DISCLOSURE_REQUIRED_FOR_SIMPLIFICATION"
SAFE_FOR_COMPACT_REPRESENTATION = "SAFE_FOR_COMPACT_REPRESENTATION"

# --- Recommended remediation classes (planning-only labels) ---
REMEDIATION_VOCABULARY_PLAN = "APPROVED_VOCABULARY_REPLACEMENT_PLAN"
REMEDIATION_DISCLOSURE_PLAN = "DISCLOSURE_PAIRING_PLAN"
REMEDIATION_SIMPLIFICATION_PLAN = "SIMPLIFICATION_SAFETY_PLAN"
REMEDIATION_CONTEXT_PLAN = "CONTEXT_ALIGNMENT_PLAN"
REMEDIATION_OBSERVE_PLAN = "OBSERVE_ONLY_PLAN"

_HIGH_TRUST_CONSUMERS = frozenset({CLIENT_STATUS_CHIP, REPORT_EXPORT, PORTFOLIO_SCORE})

_STATE_MODEL_LIMITATION = (
    "Remediation planning inherits Phase 3 heuristic semantic_state mapping and static string extraction limits."
)
_RUNTIME_LIMITATION = (
    "No runtime semantic binding per UI control; priorities reflect audit inference only."
)

# Global prohibited compact tokens for chips/scores (planning guidance)
PROHIBITED_COMPACT_LABELS_GLOBAL = [
    "Compliant",
    "Fully compliant",
    "Current",
    "Verified",
    "Complete",
    "Passed",
    "Resolved",
    "Valid",
    "Up to date",
]

# Approved vocabulary catalog (deterministic guidance; not enforced at runtime)
APPROVED_SAFE_VOCABULARY_CATALOG: Dict[str, Dict[str, List[str]]] = {
    "DECLARATION_RECORDED": {
        "approved_short_chip_labels": ["Recorded", "Self-declared"],
        "approved_export_phrases": [
            "Self-declared information on file",
            "Declaration recorded — not independently verified",
        ],
        "approved_summary_phrases": [
            "Self-declared",
            "Recorded declaration",
            "Awaiting independent verification where applicable",
        ],
        "prohibited_compact_labels": ["Compliant", "Verified", "Current certificate"],
    },
    "PARTIALLY_COMPLETE": {
        "approved_short_chip_labels": ["Partial", "Evidence needed"],
        "approved_export_phrases": [
            "Partially complete — additional evidence required",
            "Incomplete submission; further evidence needed",
        ],
        "approved_summary_phrases": [
            "Partially complete",
            "Additional evidence required",
            "Not all requirements satisfied",
        ],
        "prohibited_compact_labels": ["Complete", "Done", "Compliant"],
    },
    "EXPIRY_REVIEW_REQUIRED": {
        "approved_short_chip_labels": ["Expiry review", "Review due"],
        "approved_export_phrases": [
            "Validity requires review of expiry information",
            "Expiry review required before claiming currency",
        ],
        "approved_summary_phrases": [
            "Requires expiry review",
            "Validity requires confirmation",
        ],
        "prohibited_compact_labels": ["Current", "Valid", "Up to date"],
    },
    "ASSESSMENT_FOLLOWUP_REQUIRED": {
        "approved_short_chip_labels": ["Follow-up", "Action pending"],
        "approved_export_phrases": [
            "Follow-up outstanding; further action may be required",
            "Assessment follow-up not closed",
        ],
        "approved_summary_phrases": [
            "Follow-up outstanding",
            "Further action may be required",
            "Remediation may still be required",
        ],
        "prohibited_compact_labels": ["Passed", "Closed", "Resolved", "Complete"],
    },
    "OPERATIONALLY_OPEN": {
        "approved_short_chip_labels": ["Open", "In progress"],
        "approved_export_phrases": [
            "Operationally open — pending operational follow-through",
            "Not closed operationally",
        ],
        "approved_summary_phrases": [
            "Operationally open",
            "Pending operational follow-through",
            "Work in progress",
        ],
        "prohibited_compact_labels": ["Complete", "Resolved", "Compliant"],
    },
    "VERIFIED_CURRENT": {
        "approved_short_chip_labels": ["Verified", "Current (verified)"],
        "approved_export_phrases": [
            "Verified current against declared verification standard",
            "On file as verified within stated scope",
        ],
        "approved_summary_phrases": [
            "Verified current",
            "Meets declared verification standard",
        ],
        "prohibited_compact_labels": ["Guaranteed", "Warranty", "Legal certification"],
    },
    "MISSING": {
        "approved_short_chip_labels": ["Missing", "Not recorded"],
        "approved_export_phrases": ["No submission on file", "Not recorded"],
        "approved_summary_phrases": ["Awaiting record", "No evidence on file"],
        "prohibited_compact_labels": ["Compliant", "Complete", "Verified"],
    },
}

# Disclosure pairing catalog (planning)
DISCLOSURE_PAIRING_CATALOG: Dict[str, Dict[str, Any]] = {
    "PARTIALLY_COMPLETE": {
        "required_disclosure_pairing": ["Additional evidence is still required for this requirement."],
        "optional_disclosure_pairing": ["Outstanding items are listed in the requirement detail."],
        "disclosure_safe_compact_wording": ["Partial — evidence needed"],
        "prohibited_disclosure_omission": ['Badge-only label "Complete"', "Green-only status without caveat"],
    },
    "DECLARATION_RECORDED": {
        "required_disclosure_pairing": [
            "This information has not been independently verified unless separately stated.",
        ],
        "optional_disclosure_pairing": ["Self-declared attestation recorded on file."],
        "disclosure_safe_compact_wording": ["Recorded (not independently verified)"],
        "prohibited_disclosure_omission": ["Implied third-party verification"],
    },
    "EXPIRY_REVIEW_REQUIRED": {
        "required_disclosure_pairing": ["Validity requires review of expiry information."],
        "optional_disclosure_pairing": ["Renewal or review may be required before reliance."],
        "disclosure_safe_compact_wording": ["Expiry review due"],
        "prohibited_disclosure_omission": ["Implies current validity without review"],
    },
    "OPERATIONALLY_OPEN": {
        "required_disclosure_pairing": ["Operational work is not closed; documentary state may differ."],
        "optional_disclosure_pairing": ["Follow operational tasks for closure."],
        "disclosure_safe_compact_wording": ["Operationally open"],
        "prohibited_disclosure_omission": ["Implies documentary completion"],
    },
    "ASSESSMENT_FOLLOWUP_REQUIRED": {
        "required_disclosure_pairing": ["Follow-up is outstanding; outcomes may change."],
        "optional_disclosure_pairing": [],
        "disclosure_safe_compact_wording": ["Follow-up pending"],
        "prohibited_disclosure_omission": ["Implies passed/completed assessment"],
    },
}

# Simplification safety by consumer (planning)
SIMPLIFICATION_SAFETY_CATALOG: Dict[str, Dict[str, Any]] = {
    CLIENT_STATUS_CHIP: {
        "maximum_safe_compression_level": DISCLOSURE_REQUIRED_FOR_SIMPLIFICATION,
        "verified_current_exception": SAFE_FOR_COMPACT_REPRESENTATION,
        "chip_safe_wording_rule": "Short labels only with disclosure pairing unless semantic state is VERIFIED_CURRENT.",
        "score_safe_wording_rule": "N/A — not score surface",
        "export_safe_wording_rule": "N/A — not primary export surface",
        "summary_safe_wording_rule": "Prefer neutral tokens; avoid compliant/current unless verified-current path",
    },
    PORTFOLIO_SCORE: {
        "maximum_safe_compression_level": LIMITED_SIMPLIFICATION,
        "verified_current_exception": LIMITED_SIMPLIFICATION,
        "chip_safe_wording_rule": "Avoid single-word compliance claims on portfolio rollups",
        "score_safe_wording_rule": "Must not imply operational closure or full portfolio compliance",
        "export_safe_wording_rule": "Pair numeric summaries with state scope disclaimer where rollups span mixed states",
        "summary_safe_wording_rule": "No “fully compliant portfolio” framing",
    },
    REPORT_EXPORT: {
        "maximum_safe_compression_level": DISCLOSURE_REQUIRED_FOR_SIMPLIFICATION,
        "verified_current_exception": LIMITED_SIMPLIFICATION,
        "chip_safe_wording_rule": "N/A",
        "score_safe_wording_rule": "N/A",
        "export_safe_wording_rule": "Strongest disclosure pairing; safest wording templates only",
        "summary_safe_wording_rule": "Export subtitles must not flatten nuanced states into binary compliant/non-compliant",
    },
}


def _normalize_semantic_state(raw: Optional[str]) -> str:
    s = str(raw or "").upper()
    if s in ("UNKNOWN_MAPPED", "", "UNKNOWN"):
        return "MISSING"
    if s in SEMANTIC_TRANSITIONS:
        return s
    return "MISSING"


def _priority_tier_for_violation(v: Dict[str, Any]) -> str:
    consumer = str(v.get("consumer") or "")
    vt = str(v.get("violation_type") or "")
    sev = str(v.get("severity") or "")
    high = consumer in _HIGH_TRUST_CONSUMERS

    if vt == MISSING_REQUIRED_DISCLOSURE:
        return P3_DISCLOSURE_GAP

    if high and sev == SEVERITY_CRITICAL:
        return P0_CRITICAL_TRUST_RISK
    if consumer in (REPORT_EXPORT, PORTFOLIO_SCORE) and vt == PROHIBITED_WORDING_VIOLATION and sev in (
        SEVERITY_CRITICAL,
        SEVERITY_HIGH,
    ):
        return P1_HIGH_RISK_EXTERNAL_REPRESENTATION
    if consumer == CLIENT_STATUS_CHIP and vt == PROHIBITED_WORDING_VIOLATION:
        return P1_HIGH_RISK_EXTERNAL_REPRESENTATION
    if vt == UNSAFE_SIMPLIFICATION and high:
        return P2_HIGH_RISK_SIMPLIFICATION
    if vt in (
        OPERATIONAL_CLOSURE_COLLAPSE,
        CURRENTNESS_COLLAPSE,
        SEMANTIC_COLLAPSE_RISK,
        VERIFICATION_COLLAPSE,
    ):
        return P4_CONTEXT_ALIGNMENT
    if vt == UNKNOWN_SEMANTIC_MAPPING and sev == SEVERITY_LOW:
        return P6_OBSERVE_ONLY
    if vt == UNKNOWN_SEMANTIC_MAPPING:
        return P5_LOW_PRIORITY_GOVERNANCE
    if high:
        return P4_CONTEXT_ALIGNMENT
    return P5_LOW_PRIORITY_GOVERNANCE


def _remediation_class_for_violation(vt: str) -> str:
    if vt == MISSING_REQUIRED_DISCLOSURE:
        return REMEDIATION_DISCLOSURE_PLAN
    if vt == UNSAFE_SIMPLIFICATION:
        return REMEDIATION_SIMPLIFICATION_PLAN
    if vt in (PROHIBITED_WORDING_VIOLATION, SEMANTIC_COLLAPSE_RISK):
        return REMEDIATION_VOCABULARY_PLAN
    if vt == UNKNOWN_SEMANTIC_MAPPING:
        return REMEDIATION_OBSERVE_PLAN
    return REMEDIATION_CONTEXT_PLAN


def _complexity_and_confidence(state: str, tier: str) -> Tuple[str, str]:
    if state == "MISSING" or tier in (P5_LOW_PRIORITY_GOVERNANCE, P6_OBSERVE_ONLY):
        return "LOW", "LOW"
    if tier in (P0_CRITICAL_TRUST_RISK, P1_HIGH_RISK_EXTERNAL_REPRESENTATION):
        return "HIGH", "MEDIUM"
    if tier == P3_DISCLOSURE_GAP:
        return "MEDIUM", "HIGH"
    return "MEDIUM", "HIGH"


def _ux_risk_note(tier: str, consumer: str) -> str:
    if tier == P0_CRITICAL_TRUST_RISK:
        return "Highest user trust exposure; coordinate content review before any copy change."
    if consumer == CLIENT_STATUS_CHIP:
        return "Compact surface amplifies misinterpretation; prefer disclosure-adjacent layouts."
    if consumer == REPORT_EXPORT:
        return "External persistence increases reputational risk; pair headline with disclosure body."
    if consumer == PORTFOLIO_SCORE:
        return "Avoid implying portfolio-wide operational closure from aggregate scores."
    return "Standard governance review recommended."


def _compression_for_consumer_state(consumer: str, state: str) -> str:
    cc = map_audit_consumer_to_contract_consumer(consumer)
    if cc == CLIENT_STATUS_CHIP:
        return SAFE_FOR_COMPACT_REPRESENTATION if state == "VERIFIED_CURRENT" else DISCLOSURE_REQUIRED_FOR_SIMPLIFICATION
    if cc == PORTFOLIO_SCORE:
        return LIMITED_SIMPLIFICATION
    if cc == REPORT_EXPORT:
        return DISCLOSURE_REQUIRED_FOR_SIMPLIFICATION
    return LIMITED_SIMPLIFICATION


def build_semantic_copy_remediation_queue(
    violations: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Planning rows for each Phase 3 violation; deterministic sort."""
    rows: List[Dict[str, Any]] = []
    for v in violations:
        state = _normalize_semantic_state(v.get("associated_semantic_state"))
        tier = _priority_tier_for_violation(v)
        vt = str(v.get("violation_type") or "")
        consumer = str(v.get("consumer") or "")
        vocab = APPROVED_SAFE_VOCABULARY_CATALOG.get(state, APPROVED_SAFE_VOCABULARY_CATALOG["MISSING"])
        disc_meta = DISCLOSURE_PAIRING_CATALOG.get(state, {})
        required_disc = disc_meta.get("required_disclosure_pairing", [])
        disc_rec = required_disc[0] if required_disc else "Use disclosure pairing catalog for this semantic state."
        rem_class = _remediation_class_for_violation(vt)
        complexity, confidence = _complexity_and_confidence(state, tier)
        compression = _compression_for_consumer_state(consumer, state)

        rows.append(
            {
                "priority_tier": tier,
                "priority_rank": _PRIORITY_RANK[tier],
                "consumer": consumer,
                "semantic_state": state,
                "violation_type": vt,
                "severity": str(v.get("severity") or ""),
                "source_file": str(v.get("source_file") or ""),
                "detected_wording_excerpt": str(v.get("detected_wording") or "")[:200],
                "recommended_remediation_class": rem_class,
                "approved_replacement_vocabulary": vocab.get("approved_summary_phrases", [])[:6],
                "approved_chip_labels": vocab.get("approved_short_chip_labels", [])[:6],
                "disclosure_recommendation": disc_rec,
                "optional_disclosure_pairing": disc_meta.get("optional_disclosure_pairing", []),
                "ux_risk_note": _ux_risk_note(tier, consumer),
                "remediation_complexity": complexity,
                "remediation_safety_confidence": confidence,
                "simplification_compression_class": compression,
                "governance_contract_reference": str(v.get("governance_contract_reference") or ""),
            }
        )
    rows.sort(
        key=lambda r: (
            r["priority_rank"],
            r["consumer"],
            r["semantic_state"],
            r["source_file"],
            r["detected_wording_excerpt"],
        )
    )
    return rows


def _violations_from_repo(repo_root: Optional[Path] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    root = repo_root or Path(__file__).resolve().parents[2]
    ext = extract_live_semantic_strings(root)
    inv = build_semantic_copy_inventory(ext, root)
    viol: List[Dict[str, Any]] = []
    for row in inv:
        viol.extend(evaluate_inventory_violations(row))
    return viol, inv


def _cluster_key(v: Dict[str, Any]) -> Tuple[str, str]:
    return (str(v.get("consumer") or ""), str(v.get("violation_type") or ""))


def _safest_compact_labels() -> List[str]:
    vc = APPROVED_SAFE_VOCABULARY_CATALOG.get("VERIFIED_CURRENT", {})
    return sorted(set(vc.get("approved_short_chip_labels", []) + vc.get("approved_summary_phrases", [])))


def build_semantic_copy_remediation_phase4_snapshot(
    repo_root: Optional[Path] = None,
    violations_input: Optional[Sequence[Dict[str, Any]]] = None,
    max_queue_rows: int = 600,
) -> Dict[str, Any]:
    if violations_input is not None:
        violations = list(violations_input)
        inventory_rows: List[Dict[str, Any]] = []
    else:
        violations, inventory_rows = _violations_from_repo(repo_root)

    queue = build_semantic_copy_remediation_queue(violations)

    by_tier: Dict[str, List[Dict[str, Any]]] = {}
    for item in queue:
        by_tier.setdefault(item["priority_tier"], []).append(item)

    by_consumer: Dict[str, List[Dict[str, Any]]] = {}
    for item in queue:
        by_consumer.setdefault(item["consumer"], []).append(item)

    tier_counts = {k: len(v) for k, v in sorted(by_tier.items(), key=lambda x: _PRIORITY_RANK.get(x[0], 99))}

    clusters: Dict[str, int] = {}
    for v in violations:
        key = f"{v.get('consumer')}:{v.get('violation_type')}"
        clusters[key] = clusters.get(key, 0) + 1
    highest_risk_clusters = dict(sorted(clusters.items(), key=lambda x: (-x[1], x[0]))[:40])

    summary_by_state: Dict[str, int] = {}
    for item in queue:
        summary_by_state[item["semantic_state"]] = summary_by_state.get(item["semantic_state"], 0) + 1

    return {
        "phase": "Semantic Copy Remediation Planning Phase 4",
        "scope": "high-trust/high-risk wording remediation prioritization; audit-only planning",
        "runtime_behavior_changed": False,
        "audit_only": True,
        "non_blocking": True,
        "prioritized_remediation_queue": queue[:max_queue_rows],
        "prioritized_remediation_queue_total": len(queue),
        "remediation_queue_truncated": len(queue) > max_queue_rows,
        "remediation_counts_by_priority_tier": tier_counts,
        "remediation_grouped_by_consumer": {
            k: v[:80] for k, v in sorted(by_consumer.items(), key=lambda x: x[0])
        },
        "approved_safe_vocabulary_catalog": APPROVED_SAFE_VOCABULARY_CATALOG,
        "disclosure_pairing_catalog": DISCLOSURE_PAIRING_CATALOG,
        "simplification_safety_catalog": SIMPLIFICATION_SAFETY_CATALOG,
        "prohibited_compact_labels_global": PROHIBITED_COMPACT_LABELS_GLOBAL,
        "safest_approved_compact_labels": _safest_compact_labels(),
        "highest_risk_wording_clusters": highest_risk_clusters,
        "remediation_items_by_semantic_state_counts": dict(sorted(summary_by_state.items())),
        "semantic_transitions_reference": list(SEMANTIC_TRANSITIONS),
        "high_trust_consumers": sorted(_HIGH_TRUST_CONSUMERS),
        "inventory_row_count": len(inventory_rows),
        "phase3_violation_count": len(violations),
        "remaining_state_model_limitation": _STATE_MODEL_LIMITATION,
        "remaining_runtime_limitation": _RUNTIME_LIMITATION,
    }


def write_semantic_copy_remediation_phase4_json(
    target_path: Optional[Path] = None,
    repo_root: Optional[Path] = None,
    violations_input: Optional[Sequence[Dict[str, Any]]] = None,
) -> Path:
    snap = build_semantic_copy_remediation_phase4_snapshot(repo_root, violations_input)
    base = Path(__file__).resolve().parents[1]
    path = target_path or (base / "docs" / "audit" / "SEMANTIC_COPY_REMEDIATION_PHASE4.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
