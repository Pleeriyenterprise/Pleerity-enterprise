"""
VOCABULARY_CONTRACT_v1 — governed semantic vocabulary, authority hierarchy, and drift enforcement.

Codifies Vocabulary Contract v0.1 (+ §11–§13 drafts). Presentation and interpretation governance only;
does not alter scoring formulas, satisfaction truth, or export byte contracts.

Ownership:
  - Canonical customer labels: report_human_language_v1
  - Metric semantics: reporting_semantics_v1
  - Audience adaptation: audience_governance_v1
  - Cross-surface rules, authority, prohibited phrases: this module
"""
from __future__ import annotations

import re
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

VOCABULARY_CONTRACT_VERSION = "v0.1"

# ---------------------------------------------------------------------------
# §1 Semantic axes
# ---------------------------------------------------------------------------

SEMANTIC_AXIS_COMPLIANCE_STATUS = "compliance_status"
SEMANTIC_AXIS_EVIDENCE_CONFIDENCE = "evidence_confidence"
SEMANTIC_AXIS_VERIFICATION_MATURITY = "verification_maturity"
SEMANTIC_AXIS_AUDIT_READINESS = "audit_readiness"
SEMANTIC_AXIS_OPERATIONAL_POSTURE = "operational_posture"
SEMANTIC_AXIS_PROPERTY_READINESS = "property_readiness"
SEMANTIC_AXIS_OPERATIONAL_EXPOSURE = "operational_exposure"
SEMANTIC_AXIS_RISK_CONCENTRATION = "risk_concentration"
SEMANTIC_AXIS_MONITORING_STATE = "monitoring_state"
SEMANTIC_AXIS_REVIEW_STATE = "review_state"
SEMANTIC_AXIS_TEMPORAL_CONFIDENCE = "temporal_confidence"

SEMANTIC_AXES: Dict[str, Dict[str, str]] = {
    SEMANTIC_AXIS_COMPLIANCE_STATUS: {
        "label": "Compliance status",
        "measures": "Projected obligation state at generation boundary within export scope",
        "does_not_measure": "Legal compliance or statutory sufficiency",
    },
    SEMANTIC_AXIS_EVIDENCE_CONFIDENCE: {
        "label": "Evidence confidence",
        "measures": "Strength of evidence on file (presence, tier, verification state)",
        "does_not_measure": "Independent legal proof or audit opinion",
    },
    SEMANTIC_AXIS_VERIFICATION_MATURITY: {
        "label": "Verification maturity",
        "measures": "Stage: missing → recorded → review → verified/accepted",
        "does_not_measure": "That an obligation is legally satisfied",
    },
    SEMANTIC_AXIS_AUDIT_READINESS: {
        "label": "Audit readiness",
        "measures": "Operational preparedness for external/evidentiary review",
        "does_not_measure": "Pass/fail audit outcome or regulator approval",
    },
    SEMANTIC_AXIS_OPERATIONAL_POSTURE: {
        "label": "Operational posture",
        "measures": "Dashboard-level directional indicator (GREEN/AMBER/RED semantics)",
        "does_not_measure": "Legal status or zero risk",
    },
    SEMANTIC_AXIS_PROPERTY_READINESS: {
        "label": "Property readiness",
        "measures": "Property-scoped follow-up burden from local unresolved counts",
        "does_not_measure": "Portfolio audit confidence or audit-ready",
    },
    SEMANTIC_AXIS_OPERATIONAL_EXPOSURE: {
        "label": "Operational exposure",
        "measures": "Overdue, missing evidence, pending review in export scope",
        "does_not_measure": "Financial loss or litigation outcome",
    },
    SEMANTIC_AXIS_RISK_CONCENTRATION: {
        "label": "Risk concentration",
        "measures": "Thematic clustering of unresolved exposure",
        "does_not_measure": "Individual obligation legal merit",
    },
    SEMANTIC_AXIS_MONITORING_STATE: {
        "label": "Monitoring state",
        "measures": "Satisfied obligations under routine watch",
        "does_not_measure": "Verified compliance or closed risk",
    },
    SEMANTIC_AXIS_REVIEW_STATE: {
        "label": "Review state",
        "measures": "Evidence submitted; platform decision pending",
        "does_not_measure": "Missing evidence or verified acceptance",
    },
    SEMANTIC_AXIS_TEMPORAL_CONFIDENCE: {
        "label": "Temporal confidence",
        "measures": "Reliance given age, recency, expiry (future disclosures)",
        "does_not_measure": "Current compliance status at boundary",
    },
}

# Prohibited axis equivalences (readers must not collapse these)
PROHIBITED_AXIS_EQUIVALENCES: Tuple[Tuple[str, str], ...] = (
    (SEMANTIC_AXIS_AUDIT_READINESS, SEMANTIC_AXIS_COMPLIANCE_STATUS),
    (SEMANTIC_AXIS_EVIDENCE_CONFIDENCE, SEMANTIC_AXIS_COMPLIANCE_STATUS),
    (SEMANTIC_AXIS_OPERATIONAL_POSTURE, SEMANTIC_AXIS_VERIFICATION_MATURITY),
    (SEMANTIC_AXIS_PROPERTY_READINESS, SEMANTIC_AXIS_AUDIT_READINESS),
)

# ---------------------------------------------------------------------------
# §11 Authority hierarchy (epistemic tiers)
# ---------------------------------------------------------------------------

AUTHORITY_TIER_EVIDENTIARY = 1
AUTHORITY_TIER_OPERATIONAL = 2
AUTHORITY_TIER_EXECUTIVE = 3
AUTHORITY_TIER_DIRECTIONAL = 4
AUTHORITY_TIER_INDICATOR = 5

AUTHORITY_TIER_LABELS: Dict[int, str] = {
    AUTHORITY_TIER_EVIDENTIARY: "Evidentiary truth",
    AUTHORITY_TIER_OPERATIONAL: "Operational truth",
    AUTHORITY_TIER_EXECUTIVE: "Executive synthesis",
    AUTHORITY_TIER_DIRECTIONAL: "Directional intelligence",
    AUTHORITY_TIER_INDICATOR: "Directional indicator",
}

REPORT_CLASS_AUTHORITY_MAP: Dict[str, int] = {
    "audit_evidence_pack": AUTHORITY_TIER_EVIDENTIARY,
    "audit_logs": AUTHORITY_TIER_EVIDENTIARY,
    "evidence_readiness": AUTHORITY_TIER_OPERATIONAL,
    "requirements": AUTHORITY_TIER_OPERATIONAL,
    "compliance_summary": AUTHORITY_TIER_EXECUTIVE,
    "monthly_digest": AUTHORITY_TIER_DIRECTIONAL,
    "scheduled_email": AUTHORITY_TIER_INDICATOR,
    "dashboard": AUTHORITY_TIER_INDICATOR,
    "score_explanation": AUTHORITY_TIER_EXECUTIVE,
}

SURFACE_AUTHORITY_RULES: Dict[str, Dict[str, Any]] = {
    "audit_evidence_pack": {
        "tier": AUTHORITY_TIER_EVIDENTIARY,
        "authoritative_for": ("evidentiary_handoff", "immutable_snapshot"),
        "must_not_contradict": (),
    },
    "requirements": {
        "tier": AUTHORITY_TIER_OPERATIONAL,
        "authoritative_for": ("action_priority", "obligation_triage"),
        "must_not_contradict": ("audit_evidence_pack",),
    },
    "compliance_summary": {
        "tier": AUTHORITY_TIER_EXECUTIVE,
        "authoritative_for": ("portfolio_posture_synthesis", "cvp_headline_context"),
        "must_not_contradict": ("audit_evidence_pack", "requirements"),
    },
    "monthly_digest": {
        "tier": AUTHORITY_TIER_DIRECTIONAL,
        "authoritative_for": ("period_movement", "trend_vs_prior_snapshot"),
        "must_not_contradict": ("requirements",),
    },
    "scheduled_email": {
        "tier": AUTHORITY_TIER_INDICATOR,
        "authoritative_for": ("thin_scheduled_snapshot",),
        "must_not_contradict": ("requirements", "compliance_summary"),
    },
}

REPORT_CLASS_GOVERNANCE_INTENSITY: Dict[str, str] = {
    "audit_evidence_pack": "very_high",
    "audit_logs": "very_high",
    "evidence_readiness": "high",
    "compliance_summary": "moderate",
    "requirements": "operational_first",
    "monthly_digest": "lightest",
    "scheduled_email": "light",
    "dashboard": "light",
}

# ---------------------------------------------------------------------------
# Escalation ladders
# ---------------------------------------------------------------------------

POSTURE_LADDER: Tuple[Dict[str, str], ...] = (
    {"tier": "0", "canonical": "Favourable posture", "token": "GREEN"},
    {"tier": "1", "canonical": "Attention advised", "token": "AMBER"},
    {"tier": "2", "canonical": "Elevated attention", "token": "RED"},
    {"tier": "?", "canonical": "Status under review", "token": "UNKNOWN"},
)

VERIFICATION_LADDER: Tuple[str, ...] = (
    "Missing evidence",
    "Recorded (not independently verified)",
    "Awaiting platform review",
    "Verified or accepted",
)

PROPERTY_READINESS_LADDER: Tuple[str, ...] = (
    "Strong",
    "Adequate with review",
    "Review recommended",
)

AUDIT_READINESS_LADDER: Tuple[str, ...] = (
    "Audit-ready",
    "Substantially ready — limited exceptions",
    "Not audit-ready — material gaps remain",
)

EXPOSURE_LADDER: Tuple[str, ...] = (
    "No elevated export-scope exposure",
    "Limited operational exposure",
    "Material operational exposure",
    "Elevated operational exposure",
)

# Known cross-surface variants (drift registry — convergence targets for S2-B+)
POSTURE_SURFACE_VARIANTS: Dict[str, Tuple[str, ...]] = {
    "tier_0_favourable": ("Favourable posture", "on track (green)", "On track", "Stable operational posture"),
}

# ---------------------------------------------------------------------------
# Prohibited / scoped vocabulary
# ---------------------------------------------------------------------------

PROHIBITED_PHRASES: Tuple[str, ...] = (
    "fully compliant",
    "legally compliant",
    "risk free",
    "risk-free",
    "audit-safe",
    "audit safe",
    "regulator approved",
    "regulator-approved",
    "guaranteed compliant",
    "verified compliant",
    "no risk",
    "everything is fine",
    "certified compliant",
    "compliance guarantee",
)

PROHIBITED_PHRASE_CATEGORIES: Dict[str, str] = {
    "fully compliant": "legal_overstatement",
    "legally compliant": "legal_overstatement",
    "risk free": "false_reassurance",
    "risk-free": "false_reassurance",
    "audit-safe": "readiness_overstatement",
    "audit safe": "readiness_overstatement",
    "regulator approved": "authority_overstatement",
    "regulator-approved": "authority_overstatement",
    "guaranteed compliant": "legal_overstatement",
    "verified compliant": "verification_collapse",
    "no risk": "false_reassurance",
    "everything is fine": "false_reassurance",
    "certified compliant": "legal_overstatement",
    "compliance guarantee": "legal_overstatement",
}

PROHIBITED_PHRASE_PATTERNS: Tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"\b{re.escape(p)}\b", re.I) for p in PROHIBITED_PHRASES
)

# Unguarded optimistic fallback — blocked in executive/scheduled paths when exposure exists
UNGARDED_OPTIMISTIC_PHRASES: Tuple[str, ...] = (
    "no material compliance posture concerns",
    "all clear in this scheduled summary",
    "no concerns detected",
)

SCOPE_REQUIRED_TERMS: Dict[str, str] = {
    "operationally compliant": "export scope",
    "favourable posture": "dashboard indicator",
    "audit-ready": "operational assessment",
    "compliance posture": "generation boundary",
    "verified or accepted": "platform acceptance at generation time",
}

STALE_PHRASE_REGISTRY: Dict[str, str] = {
    "on track (green)": "Use POSTURE_LADDER tier_0 canonical (Favourable posture) per contract",
    "Green (Compliant)": "Use Green (Favourable posture) in executive CSV",
    "fully compliant obligations": "Use verified/accepted section framing with scope",
}

# ---------------------------------------------------------------------------
# §13 Temporal governance placeholders (no scoring behaviour)
# ---------------------------------------------------------------------------

FRESHNESS_STATE_CURRENT = "current_at_boundary"
FRESHNESS_STATE_AGING = "valid_but_aging"
FRESHNESS_STATE_RENEWAL_APPROACHING = "renewal_approaching"
FRESHNESS_STATE_STALE_CONFIDENCE = "stale_confidence"
FRESHNESS_STATE_STALE_RISKY = "stale_and_risky"
FRESHNESS_STATE_INDETERMINATE = "indeterminate"

TEMPORAL_CONFIDENCE_LADDER: Tuple[Dict[str, str], ...] = (
    {"id": FRESHNESS_STATE_CURRENT, "label": "Current at boundary"},
    {"id": FRESHNESS_STATE_AGING, "label": "Valid but aging"},
    {"id": FRESHNESS_STATE_RENEWAL_APPROACHING, "label": "Renewal approaching"},
    {"id": FRESHNESS_STATE_STALE_CONFIDENCE, "label": "Stale confidence"},
    {"id": FRESHNESS_STATE_STALE_RISKY, "label": "Stale-and-risky"},
    {"id": FRESHNESS_STATE_INDETERMINATE, "label": "Indeterminate"},
)

# ---------------------------------------------------------------------------
# §12 AI governance foundations (no conversational UX change in S2-A)
# ---------------------------------------------------------------------------

AI_PROHIBITED_VERDICTS: Tuple[str, ...] = PROHIBITED_PHRASES + (
    "you are compliant",
    "you are non-compliant",
    "you are non compliant",
    "this is illegal",
    "you will be fined",
    "this guarantees compliance",
)

AI_PROHIBITED_VERDICT_PATTERNS: Tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"\byou\s+are\s+compliant\b",
        r"\byou\s+are\s+non[- ]?compliant\b",
        r"\byou\s+are\s+legally\s+required\s+to\b",
        r"\bthis\s+guarantees\s+compliance\b",
        r"\byou\s+will\s+be\s+fined\b",
        r"\bthis\s+is\s+illegal\b",
        r"\bregulator\s+approved\b",
        r"\baudit[- ]safe\b",
    )
)

AI_REQUIRED_DISCLOSURES: Tuple[str, ...] = (
    "Not legal advice",
    "Portal shows",
    "generation boundary",
    "export scope",
)

AI_ESCALATION_TRIGGERS: Tuple[str, ...] = (
    "legal advice",
    "tribunal",
    "court",
    "solicitor",
    "insurer submission",
    "regulator",
)

AI_GROUNDING_REQUIREMENTS: Dict[str, str] = {
    "axis": "Semantic axis identifier required for posture/readiness/score claims",
    "tier": "Authority tier required for synthesis claims",
    "source_surface": "Report class or portal surface required",
    "generated_at": "Time boundary required for export claims",
}

# ---------------------------------------------------------------------------
# Interpretation boundary notes (centralised prose — use when adding new copy)
# ---------------------------------------------------------------------------

_BOUNDARY_NOTES: Dict[str, str] = {
    "semantic_scope": (
        "Operational posture reflects export-scope operational conditions at the generation boundary "
        "and is distinct from legal or regulatory determination."
    ),
    "metric_cvp": (
        "The CVP headline score reflects persisted property scores as of the last completed calculation. "
        "It is not a legal compliance determination and may differ from obligation completion rates."
    ),
    "metric_completion": (
        "Completion rates show operationally compliant status within export scope — distinct from the CVP "
        "headline score and not a legal compliance determination."
    ),
    "posture": (
        "Dashboard posture labels are operational indicators from tracked requirements and recorded evidence — "
        "not a legal guarantee."
    ),
    "readiness": (
        "Audit readiness is an operational preparedness assessment at the generation boundary — "
        "not a regulator sign-off or tribunal-ready determination."
    ),
    "evidence_confidence": (
        "Evidence confidence reflects platform evidence state at the generation boundary and does not "
        "independently verify legal sufficiency."
    ),
    "verification": (
        "Recorded on file is not the same as independently verified evidence unless separately stated."
    ),
    "temporal": (
        "Snapshot exports describe state at generation time; recency and freshness may affect external reliance."
    ),
}


def semantic_scope_note(*, kind: str = "semantic_scope") -> str:
    return _BOUNDARY_NOTES.get(kind, _BOUNDARY_NOTES["semantic_scope"])


def metric_boundary_note(metric_id: str) -> str:
    key = {
        "cvp": "metric_cvp",
        "completion_pct": "metric_completion",
        "compliance_rate": "metric_completion",
    }.get(metric_id, "metric_cvp")
    return _BOUNDARY_NOTES[key]


def posture_boundary_note() -> str:
    return _BOUNDARY_NOTES["posture"]


def readiness_boundary_note() -> str:
    return _BOUNDARY_NOTES["readiness"]


# ---------------------------------------------------------------------------
# Authority helpers
# ---------------------------------------------------------------------------


def human_authority_tier(report_class: str) -> int:
    key = str(report_class or "").strip().lower().replace("-", "_")
    return REPORT_CLASS_AUTHORITY_MAP.get(key, AUTHORITY_TIER_INDICATOR)


def human_authority_tier_label(tier: int) -> str:
    return AUTHORITY_TIER_LABELS.get(tier, "Directional indicator")


def requires_evidentiary_disclaimer(tier: int) -> bool:
    return tier <= AUTHORITY_TIER_EXECUTIVE


def may_override_surface(*, source_tier: int, target_tier: int, question_class: str = "evidentiary") -> bool:
    """True when source may override target for the given question class."""
    if question_class == "evidentiary":
        return source_tier < target_tier
    if question_class == "action_priority":
        return source_tier == AUTHORITY_TIER_OPERATIONAL and target_tier > AUTHORITY_TIER_OPERATIONAL
    if question_class == "movement":
        return source_tier == AUTHORITY_TIER_DIRECTIONAL
    return False


def requires_conflict_disclosure(*, source_tier: int, target_tier: int) -> bool:
    """True when surfaces at different tiers address the same portfolio and may be misread as contradictory."""
    return abs(source_tier - target_tier) >= 2


# ---------------------------------------------------------------------------
# Drift detection & enforcement
# ---------------------------------------------------------------------------


def find_prohibited_phrases(text: str) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    if not text or not str(text).strip():
        return findings
    for phrase, pat in zip(PROHIBITED_PHRASES, PROHIBITED_PHRASE_PATTERNS):
        if pat.search(text):
            findings.append(
                {
                    "kind": "prohibited_phrase",
                    "phrase": phrase,
                    "category": PROHIBITED_PHRASE_CATEGORIES.get(phrase, "semantic_risk"),
                }
            )
    return findings


def _prohibited_hits_blocking(text: str) -> List[Dict[str, str]]:
    """Prohibited phrases excluding those tracked as stale convergence targets."""
    hits = find_prohibited_phrases(text)
    if not hits:
        return hits
    low = text.lower()
    blocking: List[Dict[str, str]] = []
    for hit in hits:
        phrase = hit.get("phrase") or ""
        deferred = any(
            phrase.lower() in stale_key.lower() and stale_key.lower() in low
            for stale_key in STALE_PHRASE_REGISTRY
        )
        if not deferred:
            blocking.append(hit)
    return blocking


def find_stale_phrases(text: str) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    low = (text or "").lower()
    for stale, guidance in STALE_PHRASE_REGISTRY.items():
        if stale.lower() in low:
            findings.append({"kind": "stale_phrase", "phrase": stale, "guidance": guidance})
    return findings


def find_raw_telemetry_leaks(text: str) -> List[Dict[str, str]]:
    from services.report_human_language_v1 import contains_internal_language_leak

    findings: List[Dict[str, str]] = []
    if not text:
        return findings
    if contains_internal_language_leak(text):
        findings.append({"kind": "telemetry_leak", "detail": "internal_language_leak"})
    if re.search(r"\bscore_status\s*=", text, re.I):
        findings.append({"kind": "telemetry_leak", "detail": "score_status_assignment"})
    if re.search(r"\bpersisted_property_score\b", text, re.I):
        findings.append({"kind": "telemetry_leak", "detail": "score_authority_enum"})
    return findings


def requires_scope_disclaimer(text: str) -> bool:
    low = (text or "").lower()
    for term in SCOPE_REQUIRED_TERMS:
        if term in low:
            scope = SCOPE_REQUIRED_TERMS[term]
            if scope not in low and "not a legal" not in low and "export scope" not in low:
                return True
    return False


def find_semantic_drift(
    text: str,
    *,
    include_stale: bool = True,
    include_scope_warnings: bool = True,
) -> List[Dict[str, str]]:
    """Return all semantic drift findings for customer-facing text."""
    findings: List[Dict[str, str]] = []
    findings.extend(find_prohibited_phrases(text))
    findings.extend(find_raw_telemetry_leaks(text))
    if include_stale:
        findings.extend(find_stale_phrases(text))
    if include_scope_warnings and requires_scope_disclaimer(text):
        findings.append(
            {
                "kind": "scope_disclaimer_missing",
                "detail": "Scoped term present without export-scope or legal-boundary qualifier in same text",
            }
        )
    return findings


def assert_semantic_safe_text(
    text: str,
    *,
    context: str = "",
    allow_stale: bool = False,
    allow_scope_warning: bool = True,
) -> None:
    """Raise ValueError on prohibited phrases and telemetry leaks. Stale/scope are warnings unless strict."""
    blocking: List[Dict[str, str]] = []
    for hit in _prohibited_hits_blocking(text):
        blocking.append({**hit, "kind": "prohibited_phrase"})
    blocking.extend(find_raw_telemetry_leaks(text))
    if not allow_stale:
        blocking.extend(find_stale_phrases(text))
    if not allow_scope_warning and requires_scope_disclaimer(text):
        blocking.append(
            {
                "kind": "scope_disclaimer_missing",
                "detail": "Scoped term present without export-scope or legal-boundary qualifier in same text",
            }
        )
    if blocking:
        detail = "; ".join(
            f"{f['kind']}:{f.get('phrase') or f.get('detail')}" for f in blocking
        )
        raise ValueError(f"Semantic governance violation ({context}): {detail}")


def assert_no_recorded_compliant_collapse(status: str) -> None:
    """Scheduled/export paths must not map recorded satisfaction to COMPLIANT bucket."""
    st = str(status or "").upper()
    if st == "COMPLIANT":
        raise ValueError("RECORDED→COMPLIANT collapse: COMPLIANT used where RECORDED_UNVERIFIED required")


def ai_verdict_patterns() -> Tuple[re.Pattern[str], ...]:
    """Patterns for assistant post-processing — extends legacy VERDICT_BLOCK_PATTERNS."""
    return AI_PROHIBITED_VERDICT_PATTERNS


# ---------------------------------------------------------------------------
# Cross-surface inventory scanner (deterministic, for tests/CI)
# ---------------------------------------------------------------------------

_CUSTOMER_SURFACE_IMPORTS: Tuple[Tuple[str, str], ...] = (
    ("report_compliance_summary_executive", "_STATUS_HUMAN"),
    ("report_requirements_operational", "TRIAGE_SECTION_TITLES"),
    ("report_human_language_v1", "COMPLIANCE_STATUS_LABELS"),
    ("report_human_language_v1", "SCORE_STATUS_LABELS"),
)


def _collect_mapping_strings(obj: Any) -> List[str]:
    out: List[str] = []
    if isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, str):
                out.append(v)
            elif isinstance(v, (dict, list, tuple)):
                out.extend(_collect_mapping_strings(v))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            out.extend(_collect_mapping_strings(item))
    return out


def scan_registered_customer_surfaces() -> Dict[str, Any]:
    """Inventory customer-facing label maps for drift audits."""
    import importlib

    surfaces: Dict[str, Any] = {}
    prohibited_hits: Dict[str, List[str]] = {}
    stale_hits: Dict[str, List[str]] = {}
    leak_hits: Dict[str, List[str]] = {}

    for module_name, attr in _CUSTOMER_SURFACE_IMPORTS:
        mod = importlib.import_module(f"services.{module_name}")
        raw = getattr(mod, attr, None)
        strings = _collect_mapping_strings(raw)
        surfaces[f"{module_name}.{attr}"] = strings
        blob = "\n".join(strings)
        blocked = _prohibited_hits_blocking(blob)
        if blocked:
            prohibited_hits[f"{module_name}.{attr}"] = [f["phrase"] for f in blocked]
        stale = find_stale_phrases(blob)
        if stale:
            stale_hits[f"{module_name}.{attr}"] = [s["phrase"] for s in stale]
        leaks = find_raw_telemetry_leaks(blob)
        if leaks:
            leak_hits[f"{module_name}.{attr}"] = [l["detail"] for l in leaks]

    from email_templates.unified import scheduled_report_digest

    email_src = scheduled_report_digest.build_scheduled_report_digest_html.__doc__ or ""
    # Sample render strings from module constants via lightweight model
    try:
        html, _ = scheduled_report_digest.build_scheduled_report_digest_html(
            {
                "frequency": "weekly",
                "report_type": "compliance_summary",
                "generated_date": "2026-06-10",
                "portal_link": "https://example.com",
                "report_summary": {
                    "total_properties": 1,
                    "compliance_breakdown": {"green": 1, "amber": 0, "red": 0},
                    "requirements_breakdown": {"compliant": 0, "overdue": 0, "pending": 0, "expiring_soon": 0},
                    "compliance_rate": 0,
                },
                "properties_snapshot": [],
            }
        )
        email_src += html
    except Exception:
        pass

    surfaces["scheduled_report_digest.sample_html"] = [email_src]
    blocked = _prohibited_hits_blocking(email_src)
    if blocked:
        prohibited_hits["scheduled_report_digest"] = [f["phrase"] for f in blocked]
    stale_email = find_stale_phrases(email_src)
    if stale_email:
        stale_hits["scheduled_report_digest"] = [s["phrase"] for s in stale_email]

    return {
        "version": VOCABULARY_CONTRACT_VERSION,
        "surfaces": {k: len(v) if isinstance(v, list) else 1 for k, v in surfaces.items()},
        "prohibited_hits": prohibited_hits,
        "stale_hits": stale_hits,
        "telemetry_leaks": leak_hits,
        "posture_variants_registered": POSTURE_SURFACE_VARIANTS,
    }


def contract_export_snapshot() -> Dict[str, Any]:
    """Machine-readable contract snapshot for tests and governance tooling."""
    return {
        "version": VOCABULARY_CONTRACT_VERSION,
        "semantic_axes": list(SEMANTIC_AXES.keys()),
        "authority_tiers": AUTHORITY_TIER_LABELS,
        "report_class_authority": REPORT_CLASS_AUTHORITY_MAP,
        "governance_intensity": REPORT_CLASS_GOVERNANCE_INTENSITY,
        "posture_ladder": [p["canonical"] for p in POSTURE_LADDER],
        "verification_ladder": list(VERIFICATION_LADDER),
        "prohibited_phrase_count": len(PROHIBITED_PHRASES),
        "scoped_term_count": len(SCOPE_REQUIRED_TERMS),
        "temporal_ladder_ids": [t["id"] for t in TEMPORAL_CONFIDENCE_LADDER],
        "ai_prohibited_verdict_count": len(AI_PROHIBITED_VERDICT_PATTERNS),
    }
