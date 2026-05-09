from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from services.live_semantic_copy_audit import CLIENT_STATUS_CHIP, PORTFOLIO_SCORE, REPORT_EXPORT
from services.trigger_propagation_audit import SEMANTIC_TRANSITIONS

# --- UX representation layers (deterministic) ---
LAYER_COMPACT_SIGNAL = "LAYER_COMPACT_SIGNAL"
LAYER_CONTEXTUAL_SUMMARY = "LAYER_CONTEXTUAL_SUMMARY"
LAYER_DISCLOSURE_SUPPORT = "LAYER_DISCLOSURE_SUPPORT"
LAYER_EXPANDED_EXPLANATION = "LAYER_EXPANDED_EXPLANATION"
LAYER_AUDIT_DETAIL = "LAYER_AUDIT_DETAIL"

# --- Truthful simplification framework ---
SAFE_TRUTHFUL_SIMPLIFICATION = "SAFE_TRUTHFUL_SIMPLIFICATION"
DISCLOSURE_REQUIRED_SIMPLIFICATION = "DISCLOSURE_REQUIRED_SIMPLIFICATION"
RISKY_SEMANTIC_COMPRESSION = "RISKY_SEMANTIC_COMPRESSION"
PROHIBITED_SIMPLIFICATION = "PROHIBITED_SIMPLIFICATION"
AUDIT_DETAIL_REQUIRED = "AUDIT_DETAIL_REQUIRED"

# --- Disclosure-layer UX patterns ---
BADGE_PLUS_SUBLINE = "BADGE_PLUS_SUBLINE"
BADGE_PLUS_TOOLTIP = "BADGE_PLUS_TOOLTIP"
BADGE_PLUS_MODAL = "BADGE_PLUS_MODAL"
SUMMARY_PLUS_EXPANDER = "SUMMARY_PLUS_EXPANDER"
EXPORT_PLUS_DISCLOSURE_BLOCK = "EXPORT_PLUS_DISCLOSURE_BLOCK"
SCORE_PLUS_CONTEXT_PANEL = "SCORE_PLUS_CONTEXT_PANEL"

# --- Cognitive-load classifications ---
LOW_COGNITIVE_LOAD = "LOW_COGNITIVE_LOAD"
MODERATE_COGNITIVE_LOAD = "MODERATE_COGNITIVE_LOAD"
HIGH_COGNITIVE_LOAD = "HIGH_COGNITIVE_LOAD"
EXCESSIVE_DISCLOSURE_COMPLEXITY = "EXCESSIVE_DISCLOSURE_COMPLEXITY"

# --- Remediation sequencing categories (implementation planning order) ---
FOUNDATIONAL_TRUST_FIX = "FOUNDATIONAL_TRUST_FIX"
HIGH_RISK_PUBLIC_SURFACE = "HIGH_RISK_PUBLIC_SURFACE"
DISCLOSURE_ALIGNMENT = "DISCLOSURE_ALIGNMENT"
SAFE_SIMPLIFICATION_UPGRADE = "SAFE_SIMPLIFICATION_UPGRADE"
LOW_PRIORITY_ALIGNMENT = "LOW_PRIORITY_ALIGNMENT"
OBSERVE_ONLY_GOVERNANCE = "OBSERVE_ONLY_GOVERNANCE"

_PHASE5_CONSUMERS: Tuple[str, ...] = (CLIENT_STATUS_CHIP, REPORT_EXPORT, PORTFOLIO_SCORE)

_STATE_MODEL_LIMITATION = (
    "UX trust architecture maps governance semantics to presentation layers; runtime binding per record is out of scope."
)
_RUNTIME_LIMITATION = (
    "Planning artifact does not observe live user comprehension or A/B outcomes."
)

# Truthful simplification by semantic state (planning guidance)
_TRUTHFUL_SIMPLIFICATION_BY_STATE: Dict[str, Dict[str, Any]] = {
    "VERIFIED_CURRENT": {
        "simplification_class": SAFE_TRUTHFUL_SIMPLIFICATION,
        "when_safe": "Single-token compact labels acceptable if verification scope is unchanged and unchanged elsewhere.",
        "disclosure_required_note": "Optional reinforcement on export if mixed-state portfolios.",
        "compression_risk_note": "Misleading only if scope implied exceeds verification evidence.",
    },
    "PARTIALLY_COMPLETE": {
        "simplification_class": DISCLOSURE_REQUIRED_SIMPLIFICATION,
        "when_safe": "Never safe as a single green success signal.",
        "disclosure_required_note": "Outstanding evidence must be visible adjacent to any compact signal.",
        "compression_risk_note": "Badge-only complete states are misleading.",
    },
    "DECLARATION_RECORDED": {
        "simplification_class": RISKY_SEMANTIC_COMPRESSION,
        "when_safe": "Only with explicit not-independently-verified disclosure paired on same surface.",
        "disclosure_required_note": "Independence disclaimer mandatory near headline.",
        "compression_risk_note": "Chip-only compliance wording collapses declaration vs verification.",
    },
    "ASSESSMENT_FOLLOWUP_REQUIRED": {
        "simplification_class": PROHIBITED_SIMPLIFICATION,
        "when_safe": "Never collapse to resolved/passed tokens.",
        "disclosure_required_note": "Follow-up visibility mandatory.",
        "compression_risk_note": "Resolved wording suppresses open obligations.",
    },
    "EXPIRY_REVIEW_REQUIRED": {
        "simplification_class": DISCLOSURE_REQUIRED_SIMPLIFICATION,
        "when_safe": "Never current/valid-only chips without expiry-review cue.",
        "disclosure_required_note": "Expiry basis or review prompt adjacent.",
        "compression_risk_note": "Current language implies validity without review.",
    },
    "OPERATIONALLY_OPEN": {
        "simplification_class": DISCLOSURE_REQUIRED_SIMPLIFICATION,
        "when_safe": "Open/in-progress tokens only with operational context.",
        "disclosure_required_note": "Documentary vs operational distinction.",
        "compression_risk_note": "Complete/compliant implies closure.",
    },
    "MISSING": {
        "simplification_class": AUDIT_DETAIL_REQUIRED,
        "when_safe": "Neutral absence wording only.",
        "disclosure_required_note": "Avoid implying compliance by omission.",
        "compression_risk_note": "Any positive compliance language prohibited.",
    },
}

_DEFAULT_TRUTHFUL: Dict[str, Any] = {
    "simplification_class": DISCLOSURE_REQUIRED_SIMPLIFICATION,
    "when_safe": "Prefer contextual summary plus disclosure support.",
    "disclosure_required_note": "Pair compact signal with explanation affordance.",
    "compression_risk_note": "Single headline labels risk semantic collapse.",
}


def _minimum_layer_for(state: str, consumer: str) -> str:
    s = state.upper()
    c = consumer.upper()
    if s == "VERIFIED_CURRENT" and c == CLIENT_STATUS_CHIP:
        return LAYER_COMPACT_SIGNAL
    if s in ("PARTIALLY_COMPLETE", "DECLARATION_RECORDED", "EXPIRY_REVIEW_REQUIRED", "OPERATIONALLY_OPEN"):
        if c == CLIENT_STATUS_CHIP:
            return LAYER_CONTEXTUAL_SUMMARY
        if c == REPORT_EXPORT:
            return LAYER_DISCLOSURE_SUPPORT
        return LAYER_CONTEXTUAL_SUMMARY
    if c == REPORT_EXPORT:
        return LAYER_DISCLOSURE_SUPPORT
    if c == PORTFOLIO_SCORE:
        return LAYER_CONTEXTUAL_SUMMARY
    return LAYER_CONTEXTUAL_SUMMARY


def _prohibited_compression(state: str, consumer: str) -> str:
    s = state.upper()
    if s in ("ASSESSMENT_FOLLOWUP_REQUIRED", "OPERATIONALLY_OPEN", "PARTIALLY_COMPLETE"):
        return PROHIBITED_SIMPLIFICATION
    if s in ("DECLARATION_RECORDED", "MISSING", "UPLOADED_UNCONFIRMED"):
        return RISKY_SEMANTIC_COMPRESSION
    if s == "VERIFIED_CURRENT":
        return SAFE_TRUTHFUL_SIMPLIFICATION
    return DISCLOSURE_REQUIRED_SIMPLIFICATION


def _disclosure_adjacency(state: str, consumer: str) -> List[str]:
    s = state.upper()
    c = consumer.upper()
    base = ["disclosure must be within one interaction of compact signal (expand, tooltip, or subline)"]
    if c == REPORT_EXPORT:
        base.append("disclosure block required in export body for non-VERIFIED_CURRENT states")
    if c == CLIENT_STATUS_CHIP and s != "VERIFIED_CURRENT":
        base.append("subline or tooltip mandatory for risky states")
    if c == PORTFOLIO_SCORE:
        base.append("context panel or summary line when portfolio mixes semantic states")
    return sorted(set(base))


def _expansion_requirements(state: str, consumer: str) -> List[str]:
    s = state.upper()
    if s in ("DECLARATION_RECORDED", "PARTIALLY_COMPLETE", "EXPIRY_REVIEW_REQUIRED"):
        return sorted(["SUMMARY_PLUS_EXPANDER or BADGE_PLUS_MODAL", "what this means copy available"])
    if s == "VERIFIED_CURRENT":
        return ["optional expanded explanation for audit-friendly landlords"]
    return sorted(["contextual summary available on demand"])


def build_ux_trust_layer_matrix() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for st in SEMANTIC_TRANSITIONS:
        for consumer in _PHASE5_CONSUMERS:
            rows.append(
                {
                    "semantic_state": st,
                    "consumer": consumer,
                    "minimum_required_layer": _minimum_layer_for(st, consumer),
                    "prohibited_compression_level": _prohibited_compression(st, consumer),
                    "disclosure_adjacency_requirements": _disclosure_adjacency(st, consumer),
                    "expansion_requirements": _expansion_requirements(st, consumer),
                }
            )
    return sorted(rows, key=lambda r: (r["semantic_state"], r["consumer"]))


def build_truthful_simplification_matrix() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for st in SEMANTIC_TRANSITIONS:
        out[st] = dict(_TRUTHFUL_SIMPLIFICATION_BY_STATE.get(st, _DEFAULT_TRUTHFUL))
    return dict(sorted(out.items()))


_DISCLOSURE_LAYERING_BY_CONSUMER: Dict[str, Dict[str, Any]] = {
    CLIENT_STATUS_CHIP: {
        "preferred_patterns": [BADGE_PLUS_SUBLINE, BADGE_PLUS_TOOLTIP, BADGE_PLUS_MODAL],
        "prohibited_patterns": ["BADGE_ONLY_FOR_RISKY_STATES"],
        "minimum_disclosure_proximity": "same_card_or_row",
        "compact_label_constraints": "neutral tokens unless VERIFIED_CURRENT; no standalone Compliant/Current/Verified on risky states",
    },
    REPORT_EXPORT: {
        "preferred_patterns": [EXPORT_PLUS_DISCLOSURE_BLOCK, SUMMARY_PLUS_EXPANDER],
        "prohibited_patterns": ["HEADLINE_ONLY_EXPORT_FOR_NON_SAFE_STATES"],
        "minimum_disclosure_proximity": "first_page_body_adjacent_to_summary",
        "compact_label_constraints": "non-safe states require disclosure block before tables",
    },
    PORTFOLIO_SCORE: {
        "preferred_patterns": [SCORE_PLUS_CONTEXT_PANEL, SUMMARY_PLUS_EXPANDER],
        "prohibited_patterns": ["SINGLE_NUMBER_IMPLIES_FULL_COMPLIANCE"],
        "minimum_disclosure_proximity": "adjacent_panel_or_subline",
        "compact_label_constraints": "no portfolio-wide compliant language; mixed-state caveat",
    },
}


def build_consumer_disclosure_layering_catalog() -> Dict[str, Any]:
    return dict(sorted(_DISCLOSURE_LAYERING_BY_CONSUMER.items()))


_COGNITIVE_LOAD_RULES: Dict[str, Dict[str, Any]] = {
    "defaults": {
        "maximum_disclosure_density": "one_primary_disclosure_per_surface",
        "safe_compactness_limits": "chip <= 22 chars; subline <= 120 chars planning bounds",
        "progressive_disclosure": "compact → summary → expander → audit detail",
        "overload_risk_default": MODERATE_COGNITIVE_LOAD,
    },
    "score_rollups": {
        "overload_risk_when_mixed_states": HIGH_COGNITIVE_LOAD,
        "mitigation": "context panel summarizing dominant risk categories without legal essay",
    },
    "exports": {
        "overload_risk_when_disclosure_stacking": EXCESSIVE_DISCLOSURE_COMPLEXITY,
        "mitigation": "single disclosure block with bullets; avoid duplicate warnings in subtitle and footer",
    },
}


def build_cognitive_load_governance_summary() -> Dict[str, Any]:
    return dict(sorted(_COGNITIVE_LOAD_RULES.items()))


_SEQUENCING_ORDER: List[Tuple[str, str, int]] = [
    (FOUNDATIONAL_TRUST_FIX, "Establish neutral vocabulary and layer rules before visual polish.", 0),
    (HIGH_RISK_PUBLIC_SURFACE, "CLIENT_STATUS_CHIP, REPORT_EXPORT, PORTFOLIO_SCORE sequencing first.", 1),
    (DISCLOSURE_ALIGNMENT, "Align disclosure adjacency and pairing patterns across surfaces.", 2),
    (SAFE_SIMPLIFICATION_UPGRADE, "Introduce truthful compact labels only where layers exist.", 3),
    (LOW_PRIORITY_ALIGNMENT, "Broader REQUIREMENT_LIST and secondary surfaces.", 4),
    (OBSERVE_ONLY_GOVERNANCE, "Metrics and unknown-mapping strings without copy churn.", 5),
]


def build_remediation_sequencing_plan() -> List[Dict[str, Any]]:
    return [
        {
            "sequencing_category": cat,
            "description": desc,
            "sequence_rank": rank,
        }
        for cat, desc, rank in _SEQUENCING_ORDER
    ]


_HIGHEST_RISK_UX_ANTI_PATTERNS: List[str] = [
    "Green Compliant chip without adjacent disclosure on declaration or partial states",
    "Current validation language on EXPIRY_REVIEW_REQUIRED without review cue",
    "Resolved or passed wording on ASSESSMENT_FOLLOWUP_REQUIRED or OPERATIONALLY_OPEN",
    "Export title implying portfolio-wide compliance from mixed semantic states",
    "Score headline that implies operational closure when follow-ups remain",
    "Badge-only completion for PARTIALLY_COMPLETE",
]

_SAFEST_TRUTHFUL_SIMPLIFICATIONS: List[str] = [
    "VERIFIED_CURRENT: short Verified (scope unchanged) with optional scope footnote",
    "Neutral Missing / Not recorded for absent evidence",
    "Partial / Evidence needed paired with subline",
    "Follow-up pending with visible next-step affordance",
]

_PROHIBITED_COMPRESSION_PATTERNS: List[str] = [
    "Single-word Compliant for non-VERIFIED_CURRENT",
    "Portfolio score titled Fully compliant",
    "Export subtitle Valid without expiry review context",
    "Chip Resolved on operational-open workflows",
]

_SAFE_CHIP_GUIDANCE: List[str] = [
    "Prefer neutral nouns over authority adjectives on risky states.",
    "Pair every compact chip with subline or tooltip on CLIENT_STATUS_CHIP unless VERIFIED_CURRENT.",
    "Use Recorded / Partial / Open / Review due instead of Compliant / Current when uncertain.",
]

_SAFE_SCORE_GUIDANCE: List[str] = [
    "Describe what the number aggregates (recorded signals), not legal outcome.",
    "Add mixed-state caveat when portfolio blends semantic states.",
    "Defer closure language to requirement-level detail.",
]

_SAFE_EXPORT_GUIDANCE: List[str] = [
    "Mandatory disclosure block for non-safe states before evidence tables.",
    "Summary sentence stating verification vs declaration distinction where relevant.",
    "Avoid binary compliant/non-compliant chapter titles when states are mixed.",
]

_DISCLOSURE_PLACEMENT_GUIDANCE: List[str] = [
    "Place disclosure within one tap/scroll of the headline it qualifies.",
    "Do not bury sole disclaimer in footer if headline makes a strong claim.",
]

_TOOLTIP_MODAL_GUIDANCE: List[str] = [
    "Tooltip for density; modal for obligation-heavy explanations.",
    "Reuse consistent Why this matters framing across surfaces.",
]

_WHAT_THIS_MEANS_GUIDANCE: List[str] = [
    "Plain-language clause: what was recorded, what was not verified, what happens next.",
]


def _classify_cognitive_load_row(state: str, consumer: str) -> str:
    if consumer == REPORT_EXPORT and state != "VERIFIED_CURRENT":
        return HIGH_COGNITIVE_LOAD
    if consumer == PORTFOLIO_SCORE and state in ("OPERATIONALLY_OPEN", "PARTIALLY_COMPLETE", "MISSING"):
        return HIGH_COGNITIVE_LOAD
    if state == "VERIFIED_CURRENT":
        return LOW_COGNITIVE_LOAD
    return MODERATE_COGNITIVE_LOAD


def build_cognitive_load_matrix() -> List[Dict[str, Any]]:
    rows = []
    for st in SEMANTIC_TRANSITIONS:
        for c in _PHASE5_CONSUMERS:
            rows.append(
                {
                    "semantic_state": st,
                    "consumer": c,
                    "cognitive_load_class": _classify_cognitive_load_row(st, c),
                }
            )
    return sorted(rows, key=lambda r: (r["semantic_state"], r["consumer"]))


def build_consumer_trust_guidance() -> Dict[str, Dict[str, List[str]]]:
    return {
        CLIENT_STATUS_CHIP: {
            "implementation_notes": _SAFE_CHIP_GUIDANCE,
            "anti_patterns_to_avoid": _HIGHEST_RISK_UX_ANTI_PATTERNS[:3],
        },
        REPORT_EXPORT: {
            "implementation_notes": _SAFE_EXPORT_GUIDANCE,
            "anti_patterns_to_avoid": _HIGHEST_RISK_UX_ANTI_PATTERNS[3:5],
        },
        PORTFOLIO_SCORE: {
            "implementation_notes": _SAFE_SCORE_GUIDANCE,
            "anti_patterns_to_avoid": _HIGHEST_RISK_UX_ANTI_PATTERNS[4:6],
        },
    }


def build_governance_ux_trust_architecture_phase5_snapshot() -> Dict[str, Any]:
    layer_matrix = build_ux_trust_layer_matrix()
    truthful = build_truthful_simplification_matrix()
    disclosure_catalog = build_consumer_disclosure_layering_catalog()
    cognitive_summary = build_cognitive_load_governance_summary()
    cog_matrix = build_cognitive_load_matrix()
    sequencing = build_remediation_sequencing_plan()
    consumer_guidance = build_consumer_trust_guidance()

    cognitive_distribution: Dict[str, int] = {}
    for r in cog_matrix:
        cognitive_distribution[r["cognitive_load_class"]] = cognitive_distribution.get(r["cognitive_load_class"], 0) + 1
    cognitive_distribution = dict(sorted(cognitive_distribution.items()))

    simplification_distribution: Dict[str, int] = {}
    for _st, payload in truthful.items():
        sc = str(payload.get("simplification_class") or "")
        simplification_distribution[sc] = simplification_distribution.get(sc, 0) + 1
    simplification_distribution = dict(sorted(simplification_distribution.items()))

    return {
        "phase": "Governance-Aware UX Trust Architecture Planning Phase 5",
        "scope": "implementation planning for truthful simplification and disclosure layering; audit-only",
        "runtime_behavior_changed": False,
        "audit_only": True,
        "non_blocking": True,
        "ux_trust_layers": [
            LAYER_COMPACT_SIGNAL,
            LAYER_CONTEXTUAL_SUMMARY,
            LAYER_DISCLOSURE_SUPPORT,
            LAYER_EXPANDED_EXPLANATION,
            LAYER_AUDIT_DETAIL,
        ],
        "truthful_simplification_classes": [
            SAFE_TRUTHFUL_SIMPLIFICATION,
            DISCLOSURE_REQUIRED_SIMPLIFICATION,
            RISKY_SEMANTIC_COMPRESSION,
            PROHIBITED_SIMPLIFICATION,
            AUDIT_DETAIL_REQUIRED,
        ],
        "disclosure_layer_patterns": [
            BADGE_PLUS_SUBLINE,
            BADGE_PLUS_TOOLTIP,
            BADGE_PLUS_MODAL,
            SUMMARY_PLUS_EXPANDER,
            EXPORT_PLUS_DISCLOSURE_BLOCK,
            SCORE_PLUS_CONTEXT_PANEL,
        ],
        "cognitive_load_classes": [
            LOW_COGNITIVE_LOAD,
            MODERATE_COGNITIVE_LOAD,
            HIGH_COGNITIVE_LOAD,
            EXCESSIVE_DISCLOSURE_COMPLEXITY,
        ],
        "remediation_sequencing_categories": [
            FOUNDATIONAL_TRUST_FIX,
            HIGH_RISK_PUBLIC_SURFACE,
            DISCLOSURE_ALIGNMENT,
            SAFE_SIMPLIFICATION_UPGRADE,
            LOW_PRIORITY_ALIGNMENT,
            OBSERVE_ONLY_GOVERNANCE,
        ],
        "phase5_high_trust_consumers": list(_PHASE5_CONSUMERS),
        "ux_trust_layer_matrix": layer_matrix,
        "truthful_simplification_governance_matrix": truthful,
        "truthful_simplification_distribution": simplification_distribution,
        "disclosure_layering_catalog": disclosure_catalog,
        "cognitive_load_governance_summary": cognitive_summary,
        "cognitive_load_matrix": cog_matrix,
        "cognitive_load_distribution": cognitive_distribution,
        "remediation_sequencing_plan": sequencing,
        "consumer_specific_trust_guidance": consumer_guidance,
        "safe_chip_wording_guidance": _SAFE_CHIP_GUIDANCE,
        "safe_score_summary_guidance": _SAFE_SCORE_GUIDANCE,
        "safe_export_summary_guidance": _SAFE_EXPORT_GUIDANCE,
        "disclosure_placement_guidance": _DISCLOSURE_PLACEMENT_GUIDANCE,
        "tooltip_and_modal_guidance": _TOOLTIP_MODAL_GUIDANCE,
        "what_this_means_explanation_guidance": _WHAT_THIS_MEANS_GUIDANCE,
        "highest_risk_ux_anti_patterns": list(_HIGHEST_RISK_UX_ANTI_PATTERNS),
        "safest_truthful_simplifications": list(_SAFEST_TRUTHFUL_SIMPLIFICATIONS),
        "prohibited_compression_patterns": list(_PROHIBITED_COMPRESSION_PATTERNS),
        "semantic_transitions_reference": list(SEMANTIC_TRANSITIONS),
        "remaining_state_model_limitation": _STATE_MODEL_LIMITATION,
        "remaining_runtime_limitation": _RUNTIME_LIMITATION,
    }


def write_governance_ux_trust_architecture_phase5_json(target_path: Optional[Path] = None) -> Path:
    snap = build_governance_ux_trust_architecture_phase5_snapshot()
    base = Path(__file__).resolve().parents[1]
    path = target_path or (base / "docs" / "audit" / "GOVERNANCE_UX_TRUST_ARCHITECTURE_PHASE5.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def phase5_snapshot_fingerprint() -> str:
    """Stable subset hash for deterministic tests."""
    snap = build_governance_ux_trust_architecture_phase5_snapshot()
    payload = {
        "layer_matrix_len": len(snap["ux_trust_layer_matrix"]),
        "truthful_keys": list(snap["truthful_simplification_governance_matrix"].keys()),
        "sequencing": snap["remediation_sequencing_plan"],
        "cog_dist": snap["cognitive_load_distribution"],
        "simp_dist": snap["truthful_simplification_distribution"],
        "first_layer_row": snap["ux_trust_layer_matrix"][0] if snap["ux_trust_layer_matrix"] else {},
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
