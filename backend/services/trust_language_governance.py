"""
Trust-language governance — canonical rules for customer-facing operational explanations.

Principle: transparent operational outcomes, opaque implementation mechanics.

Does NOT define scoring logic. Governs how explanations are phrased across portal,
exports, email, timeline, KB, and assistant context.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Governance categories (normative)
# ---------------------------------------------------------------------------

SAFE_OPERATIONAL_LANGUAGE = (
    "accepted evidence",
    "overdue actions",
    "expiring records",
    "maintenance issues",
    "unresolved items",
    "review pending",
    "score may improve",
    "uploads may not count until accepted",
    "open maintenance",
    "due soon",
)

FORBIDDEN_ENGINEERING_TERMS: Tuple[str, ...] = (
    "scoring engine",
    "weighted contribution",
    "weighted contributions",
    "bucket emphasis",
    "model weighting",
    "heuristic allocation",
    "point distribution",
    "scoring formula",
    "internal confidence model",
    "cvp score v",
    "credit within each bucket",
    "credit in bucket",
    "credit earned within each bucket",
    "re-aggregation",
    "risk-style weighting",
    "hand-tuned percentage",
    "rigid formula",
    "approximate emphasis",
    "status score",
    "expiry score",
    "document score",
    "overdue_penalty_score",
    "overdue penalty score",
    "server-confirmed",
    "remediation step",
    "remediation metadata",
)

FORBIDDEN_FALSE_PRECISION_PATTERNS: Tuple[str, ...] = (
    r"\+\s*\d+\s*points?",
    r"moved by\s*[+-]?\d+\s*points?",
    r"changed by\s*\d+\s*points?",
    r"improved by\s*\d+\s*points?",
    r"decreased by\s*\d+\s*points?",
    r"score\s*[+-]\d+",
    r"delta\s*[+-]?\d+",
    r"this guarantees",
    r"guarantees compliance",
    r"certifies compliance",
)

# Flagged in lint — acceptable in disclaimers/timing notes, not as sole causal explanation.
VAGUE_CAUSAL_PATTERNS: Tuple[str, ...] = (
    r"based on recent activity",
    r"recent changes affected your score",
    r"system updates",
    r"score changed based on recent",
)

EXPLAINABILITY_TIERS: Dict[str, Dict[str, Any]] = {
    "tier_1_casual": {
        "audience": "Casual landlords",
        "needs": ("what is wrong", "what to do next", "simple next-step guidance"),
        "surfaces": ("dashboard KPI", "quick actions", "empty states", "notifications"),
        "must_not_expose": ("weighting", "model internals", "component percentages"),
    },
    "tier_2_active": {
        "audience": "Active operators",
        "needs": ("operational area causing drag", "category-level guidance", "causal understanding"),
        "surfaces": ("compliance score areas", "score drivers", "requirements confidence"),
        "must_not_expose": ("heuristic allocation", "formula", "engine architecture"),
    },
    "tier_3_professional": {
        "audience": "Professional / compliance-heavy users",
        "needs": ("transparent operational reasoning", "progression clarity", "cross-surface consistency"),
        "surfaces": ("PDF exports", "definitions modal", "KB articles", "assistant with portal context"),
        "must_not_expose": ("internal weights", "model version", "reverse-engineering hints"),
    },
}

# Copy authority registry — extend here when adding new explanation surfaces.
COPY_AUTHORITY_REGISTRY: Dict[str, str] = {
    "portal_scoring_ui": "frontend/src/utils/scoringExplanationCopy.js",
    "portal_confidence": "frontend/src/utils/confidenceUxCopy.js",
    "portal_freshness": "frontend/src/utils/scoreFreshnessUi.js",
    "portal_workspace": "frontend/src/utils/workspaceOrientationCopy.js",
    "portal_jurisdiction": "frontend/src/utils/jurisdictionComplianceCopy.js",
    "portal_presentation": "frontend/src/utils/presentationLanguage.js",
    "backend_scoring_copy": "backend/services/scoring_explanation_copy.py",
    "backend_pdf": "backend/services/pdf_report_builder.py",
    "backend_email_timeline": "backend/services/email_service.py + property_timeline_service.py",
    "backend_assistant_kb": "backend/docs/assistant_kb/",
    "backend_help_centre_seed": "backend/scripts/seed_kb_articles.py",
    "assistant_prompt": "backend/services/assistant_prompt.py",
    "assistant_score_context": "backend/services/assistant_retrieval_service.py",
    "score_trend_explanation": "backend/services/compliance_trending.py",
}

_BREAKDOWN_REASON_THRESHOLD = 100.0


def validate_customer_copy(text: str, *, allow_vague: bool = False) -> List[Dict[str, str]]:
    """Return governance violations for customer-visible copy. Empty list = pass."""
    if not text or not str(text).strip():
        return []
    violations: List[Dict[str, str]] = []
    low = str(text).lower()

    for term in FORBIDDEN_ENGINEERING_TERMS:
        if term.lower() in low:
            violations.append({"category": "FORBIDDEN_ENGINEERING_LANGUAGE", "match": term})

    for pat in FORBIDDEN_FALSE_PRECISION_PATTERNS:
        if re.search(pat, text, re.I):
            violations.append({"category": "FORBIDDEN_FALSE_PRECISION", "match": pat})

    if not allow_vague:
        for pat in VAGUE_CAUSAL_PATTERNS:
            if re.search(pat, text, re.I):
                violations.append({"category": "VAGUE_CAUSAL_LANGUAGE", "match": pat})

    return violations


def assert_customer_copy_safe(text: str, *, context: str = "", allow_vague: bool = False) -> None:
    violations = validate_customer_copy(text, allow_vague=allow_vague)
    if violations:
        detail = "; ".join(f"{v['category']}: {v['match']}" for v in violations)
        raise ValueError(f"Trust-language violation ({context}): {detail}")


def sanitize_customer_copy(text: str) -> str:
    """Best-effort post-filter for generated/support copy — preserves meaning, strips precision leaks."""
    if not text:
        return text
    out = str(text)
    out = re.sub(r"\b(status|expiry|document|overdue penalty)\s+score\s+\d+%", "", out, flags=re.I)
    out = re.sub(r"(improved|decreased|changed|moved)\s+by\s+[+-]?\d+\s+points?", r"\1", out, flags=re.I)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def operational_score_key_reasons(breakdown: Optional[Dict[str, Any]]) -> List[str]:
    """
    Operational key reasons for a property score — no internal component names or percentages.
    Used by assistant context and client score-explanation API.
    """
    if not isinstance(breakdown, dict):
        return []

    reasons: List[str] = []

    def _low(key: str) -> bool:
        val = breakdown.get(key)
        if val is None:
            return False
        try:
            return float(val) < _BREAKDOWN_REASON_THRESHOLD
        except (TypeError, ValueError):
            return False

    if _low("status_score"):
        reasons.append("Some requirements still need accepted evidence or are not yet in date.")
    if _low("expiry_score"):
        reasons.append("One or more items are overdue or due soon.")
    if _low("document_score"):
        reasons.append("Some required items still need accepted evidence.")
    if _low("overdue_penalty_score"):
        reasons.append("Overdue items may be reducing this property's score.")

    return reasons


def build_score_trend_explanation(
    *,
    compare_days: int,
    score_change: int,
    change_summaries: Sequence[str],
) -> str:
    """
    Causal portfolio score trend explanation — directional headline, operational causes listed.
    No point arithmetic or emojis.
    """
    summaries = [s.strip() for s in change_summaries if s and str(s).strip()]

    if score_change > 0:
        headline = f"Your compliance score improved over the last {compare_days} days."
    elif score_change < 0:
        headline = f"Your compliance score decreased over the last {compare_days} days."
    else:
        headline = f"Your compliance score stayed about the same over the last {compare_days} days."

    if summaries:
        return f"{headline} Main changes: {'; '.join(summaries)}."
    if score_change > 0:
        return f"{headline} Accepted evidence, cleared overdue items, or resolved expiring records may have contributed."
    if score_change < 0:
        return f"{headline} New overdue items, items due soon, missing accepted evidence, or open maintenance may have contributed."
    return headline


def filter_assistant_score_context(score_explanation: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure assistant-injected score context uses governed operational language."""
    if not isinstance(score_explanation, dict):
        return score_explanation

    out = dict(score_explanation)
    by_property = []
    for row in out.get("by_property") or []:
        if not isinstance(row, dict):
            continue
        cleaned = dict(row)
        breakdown = row.get("compliance_breakdown") or row.get("breakdown")
        if breakdown:
            cleaned["key_reasons"] = operational_score_key_reasons(breakdown)
        else:
            cleaned["key_reasons"] = [
                sanitize_customer_copy(r)
                for r in (row.get("key_reasons") or [])
                if r and not validate_customer_copy(str(r))
            ]
        by_property.append(cleaned)
    out["by_property"] = by_property

    trend = out.get("trend")
    if trend:
        sanitized = sanitize_customer_copy(str(trend))
        if validate_customer_copy(sanitized, allow_vague=True):
            out["trend"] = build_score_trend_explanation(
                compare_days=7,
                score_change=0,
                change_summaries=[],
            )
        else:
            out["trend"] = sanitized
    return out


ASSISTANT_TRUST_LANGUAGE_RULES = """
TRUST-LANGUAGE GOVERNANCE (operational explanations)
- Explain scores using operational causes: accepted evidence, overdue items, expiring records, open maintenance, review pending.
- Do NOT quote internal weights, formulas, model versions, bucket names, status/expiry/document scores, or point changes (+N points).
- Do NOT invent scoring mechanics or guarantee outcomes.
- Prefer causal language: "Your score may improve when gas safety evidence is accepted" not "Your score changed based on recent activity."
- Use score_explanation.key_reasons and trend as hints only; phrase in plain English tied to the user's records.
- Never expose engineering terms listed in trust_language_governance.FORBIDDEN_ENGINEERING_TERMS.
"""
