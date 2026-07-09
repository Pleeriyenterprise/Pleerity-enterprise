"""Tests for Decision Quality computation — descriptive only."""
from __future__ import annotations

from services.compliance_evidence_graph.producers._base import compute_decision_quality


def test_decision_quality_confirmed_when_complete_verified():
    q = compute_decision_quality(
        evidence_completeness="complete",
        evidence_confidence_score=100,
        human_verification_status="approved",
        rule_certainty_score=100,
        jurisdiction_certainty_score=100,
        decision_stability="stable",
    )
    assert q["overall_label"] == "confirmed"
    assert q["evidence_completeness"] == "complete"
    assert q["human_verification_status"] == "approved"


def test_decision_quality_insufficient_when_missing_evidence():
    q = compute_decision_quality(
        evidence_completeness="insufficient",
        missing_required_evidence=["gas_certificate"],
    )
    assert q["overall_label"] in ("insufficient", "partial")
    assert q["missing_required_evidence"] == ["gas_certificate"]


def test_decision_quality_deterministic():
    kwargs = dict(
        evidence_completeness="partial",
        evidence_confidence_score=60,
        human_verification_status="pending",
    )
    q1 = compute_decision_quality(**kwargs)
    q2 = compute_decision_quality(**kwargs)
    assert q1["overall_label"] == q2["overall_label"]
    assert q1["evidence_confidence"]["score"] == q2["evidence_confidence"]["score"]
    assert q1["computed_by"] == q2["computed_by"]


def test_decision_quality_backfill_inferred():
    q = compute_decision_quality(
        evidence_completeness="partial",
        backfill=True,
    )
    assert q["overall_label"] == "inferred"


def test_decision_quality_does_not_include_outcome_fields():
    q = compute_decision_quality(evidence_completeness="complete", evidence_confidence_score=100)
    assert "decision_outcome" not in q
    assert "compliance_score" not in q
