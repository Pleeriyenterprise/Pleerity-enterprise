"""
Producer base utilities — dedupe keys, provenance templates, Decision Quality.

Decision Quality is descriptive only and must never modify compliance outcomes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

COMPUTED_BY = "compliance_evidence_graph.producers._base"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_dedupe_key(
    *,
    mutation_kind: str,
    client_id: str,
    entity_id: str,
    fact_signature: str,
) -> str:
    return f"{mutation_kind}:{client_id}:{entity_id}:{fact_signature}"


def build_provenance_template(
    *,
    why_exists: str,
    created_by_component: str,
    created_by_authority: str,
    decision_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "why_exists": why_exists,
        "created_by_component": created_by_component,
        "created_by_authority": created_by_authority,
        "created_at": _now_iso(),
        "decision_id": decision_id,
        "runtime_event_id": None,
        "operational_event_id": None,
        "correlation_id": correlation_id,
        "is_active": True,
        "superseded_by_edge_id": None,
    }


def _label_from_score(score: Optional[int], *, high: int = 80, partial: int = 50) -> str:
    if score is None:
        return "unknown"
    if score >= high:
        return "confirmed" if score >= 95 else "high"
    if score >= partial:
        return "partial"
    return "insufficient"


def compute_decision_quality(
    *,
    evidence_completeness: Optional[str] = None,
    evidence_confidence_score: Optional[int] = None,
    ai_extraction_confidence_score: Optional[int] = None,
    human_verification_status: Optional[str] = None,
    missing_required_evidence: Optional[List[Any]] = None,
    conflicting_evidence: Optional[List[Any]] = None,
    rule_certainty_score: Optional[int] = None,
    jurisdiction_certainty_score: Optional[int] = None,
    decision_stability: Optional[str] = None,
    outstanding_review_requirements: Optional[List[Any]] = None,
    backfill: bool = False,
) -> Dict[str, Any]:
    """
    Deterministic Decision Quality from authoritative inputs only.
    Does not read graph state or influence compliance outcomes.
    """
    missing = list(missing_required_evidence or [])
    conflicts = list(conflicting_evidence or [])
    outstanding = list(outstanding_review_requirements or [])

    ev_score = evidence_confidence_score
    if evidence_completeness == "complete" and ev_score is None:
        ev_score = 100
    elif evidence_completeness == "insufficient" and ev_score is None:
        ev_score = 20
    elif evidence_completeness == "partial" and ev_score is None:
        ev_score = 60

    rule_score = rule_certainty_score if rule_certainty_score is not None else 100
    jur_score = jurisdiction_certainty_score if jurisdiction_certainty_score is not None else 100

    human = human_verification_status or "unknown"
    stability = decision_stability or "unknown"

    if backfill:
        overall = "inferred"
    elif missing or conflicts:
        overall = "partial" if ev_score and ev_score >= 50 else "insufficient"
    elif ev_score is not None and ev_score >= 95 and not outstanding:
        overall = "confirmed"
    elif ev_score is not None and ev_score >= 50:
        overall = "partial"
    elif ev_score is not None:
        overall = "insufficient"
    else:
        overall = "unknown"

    return {
        "evidence_completeness": evidence_completeness or "unknown",
        "evidence_confidence": {
            "score": ev_score,
            "label": _label_from_score(ev_score),
        },
        "ai_extraction_confidence": (
            {"score": ai_extraction_confidence_score, "label": _label_from_score(ai_extraction_confidence_score)}
            if ai_extraction_confidence_score is not None
            else None
        ),
        "human_verification_status": human,
        "missing_required_evidence": missing,
        "conflicting_evidence": conflicts,
        "rule_certainty": {"score": rule_score, "label": _label_from_score(rule_score)},
        "jurisdiction_certainty": {"score": jur_score, "label": _label_from_score(jur_score)},
        "decision_stability": stability,
        "outstanding_review_requirements": outstanding,
        "overall_label": overall,
        "computed_at": _now_iso(),
        "computed_by": COMPUTED_BY,
    }
