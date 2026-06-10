"""S2-A — vocabulary contract codification and enforcement."""
from __future__ import annotations

import re

import pytest

from services.report_compliance_summary_executive import (
    build_executive_interpretation,
    portfolio_material_exposure,
)
from services.vocabulary_contract_v1 import (
    AUTHORITY_TIER_EVIDENTIARY,
    AUTHORITY_TIER_OPERATIONAL,
    POSTURE_LADDER,
    REPORT_CLASS_AUTHORITY_MAP,
    VERIFICATION_LADDER,
    ai_verdict_patterns,
    assert_no_recorded_compliant_collapse,
    assert_semantic_safe_text,
    contract_export_snapshot,
    find_prohibited_phrases,
    find_raw_telemetry_leaks,
    find_semantic_drift,
    find_stale_phrases,
    human_authority_tier,
    may_override_surface,
    metric_boundary_note,
    posture_boundary_note,
    readiness_boundary_note,
    requires_conflict_disclosure,
    requires_evidentiary_disclaimer,
    scan_registered_customer_surfaces,
    semantic_scope_note,
)


def test_contract_snapshot_structure():
    snap = contract_export_snapshot()
    assert snap["version"] == "v0.1"
    assert "compliance_status" in snap["semantic_axes"]
    assert snap["report_class_authority"]["audit_evidence_pack"] == AUTHORITY_TIER_EVIDENTIARY
    assert snap["report_class_authority"]["requirements"] == AUTHORITY_TIER_OPERATIONAL
    assert len(snap["posture_ladder"]) >= 3
    assert len(snap["verification_ladder"]) == 4


def test_authority_hierarchy_mapping():
    assert human_authority_tier("compliance_summary") == 3
    assert human_authority_tier("monthly_digest") == 4
    assert requires_evidentiary_disclaimer(3) is True
    assert requires_evidentiary_disclaimer(1) is True
    assert may_override_surface(source_tier=1, target_tier=3, question_class="evidentiary")
    assert requires_conflict_disclosure(source_tier=2, target_tier=5)


def test_prohibited_phrase_detection():
    hits = find_prohibited_phrases("Portfolio is fully compliant today.")
    assert any(h["phrase"] == "fully compliant" for h in hits)
    assert_semantic_safe_text("Routine monitoring in scope.", context="test")


def test_prohibited_phrase_blocks():
    with pytest.raises(ValueError, match="fully compliant"):
        assert_semantic_safe_text("You are fully compliant.", context="test")


def test_telemetry_leak_detection():
    leaks = find_raw_telemetry_leaks("score_status=ok persisted_property_score")
    assert len(leaks) >= 2
    with pytest.raises(ValueError, match="telemetry"):
        assert_semantic_safe_text("score_status=ok", context="test")


def test_stale_phrase_registry_detects_known_fork():
    stale = find_stale_phrases("Properties — on track (green)")
    assert any(s["phrase"] == "on track (green)" for s in stale)


def test_boundary_notes_non_empty():
    assert "legal" in semantic_scope_note().lower()
    assert "CVP" in metric_boundary_note("cvp") or "headline" in metric_boundary_note("cvp").lower()
    assert posture_boundary_note()
    assert readiness_boundary_note()


def test_verification_ladder_order():
    assert VERIFICATION_LADDER[0] == "Missing evidence"
    assert "not independently verified" in VERIFICATION_LADDER[1]
    assert "Verified or accepted" in VERIFICATION_LADDER[-1]


def test_posture_ladder_canonical_green():
    green = next(p for p in POSTURE_LADDER if p["token"] == "GREEN")
    assert green["canonical"] == "Favourable posture"


def test_recorded_compliant_collapse_guard():
    assert_no_recorded_compliant_collapse("RECORDED_UNVERIFIED")
    with pytest.raises(ValueError, match="RECORDED"):
        assert_no_recorded_compliant_collapse("COMPLIANT")


def test_ai_verdict_patterns_cover_legacy_assistant_blocks():
    sample = "You are compliant with all requirements."
    assert any(p.search(sample) for p in ai_verdict_patterns())


def test_assistant_rewrite_does_not_raise_on_verdict_match():
    from services.assistant_chat_service import _rewrite_compliance_verdict_language

    out = _rewrite_compliance_verdict_language("You are compliant with all requirements.")
    assert "you are compliant" not in out.lower()


def test_scan_registered_surfaces_no_prohibited_in_core_maps():
    report = scan_registered_customer_surfaces()
    assert report["version"] == "v0.1"
    assert not report["prohibited_hits"], report["prohibited_hits"]
    assert not report["telemetry_leaks"], report["telemetry_leaks"]


def test_executive_interpretation_passes_semantic_safe():
    lines = build_executive_interpretation(
        counts={"pending": 0},
        readiness={"audit_confidence": "High", "unresolved_evidence_exposure": 0},
        risk_concentration=[],
        overdue=0,
        missing_evidence=0,
        expiring=0,
        completion_pct=100,
        total_reqs=1,
    )
    for ln in lines:
        assert_semantic_safe_text(ln, context="executive_interpretation", allow_stale=True)


def test_executive_all_clear_suppressed_with_exposure():
    lines = build_executive_interpretation(
        counts={"pending": 0},
        readiness={"audit_confidence": "High", "unresolved_evidence_exposure": 0},
        risk_concentration=[],
        overdue=3,
        missing_evidence=0,
        expiring=0,
        completion_pct=50,
        total_reqs=2,
    )
    blob = " ".join(lines).lower()
    assert "no material compliance posture concerns" not in blob


def test_report_class_authority_complete_for_catalog():
    for report_id in (
        "audit_evidence_pack",
        "evidence_readiness",
        "requirements",
        "compliance_summary",
        "monthly_digest",
    ):
        assert report_id in REPORT_CLASS_AUTHORITY_MAP


def test_find_semantic_drift_scope_warning_optional():
    drift = find_semantic_drift("Operationally compliant items only.", include_scope_warnings=True)
    assert any(d["kind"] == "scope_disclaimer_missing" for d in drift)
