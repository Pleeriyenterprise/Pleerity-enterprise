"""REPORTING-TRUTH-CONVERGENCE-PHASE-01 — reporting semantics layer."""

import pytest

from services.reporting_semantics_v1 import (
    LIVE_REGENERATED_DISCLOSURE,
    METRIC_COMPLIANT_SCORING,
    METRIC_SCORE_TRACKED,
    METRIC_TRACKED,
    METRIC_VERIFIED,
    REPORTING_METRIC_DEFINITIONS,
    SURFACE_EXPORT_REGISTRY,
    apply_registry_display_semantics,
    build_reporting_semantics_payload,
    compute_registry_display_semantic_overrides,
    compute_reporting_semantic_counts,
    csv_semantics_preamble_rows,
    requirement_row_in_tracked_attention_views,
    legacy_stats_from_semantic_counts,
    GRADE_AUDIT_ARTIFACT,
    PDF_ENGINE_JSPDF,
)


def test_metric_definitions_cover_required_keys():
    required = {
        "tracked_requirement_count",
        "score_tracked_requirement_count",
        "compliant_requirement_count",
        "satisfied_requirement_count",
        "verified_requirement_count",
        "missing_document_count",
        "expiring_requirement_count",
        "platform_review_pending_count",
        "self_recorded_count",
        "visible_requirement_count",
        "lifecycle_satisfied_count",
    }
    assert required == set(REPORTING_METRIC_DEFINITIONS.keys())


def test_tracked_attention_excludes_not_applicable_lifecycle():
    row = {
        "client_surface_visible": True,
        "client_lifecycle_state": "NOT_APPLICABLE",
        "applicability": "MANDATORY",
        "status": "PENDING",
    }
    assert requirement_row_in_tracked_attention_views(row) is False


def test_semantic_counts_score_vs_tracked_diverge_by_design():
    rows = [
        {
            "client_surface_visible": True,
            "client_lifecycle_state": "VERIFIED",
            "status": "COMPLIANT",
            "applicability": "MANDATORY",
            "compliance_requirement_class": "DOCUMENT",
        },
        {
            "client_surface_visible": True,
            "client_lifecycle_state": "ACTION_REQUIRED",
            "status": "PENDING",
            "applicability": "MANDATORY",
            "compliance_requirement_class": "DOCUMENT",
        },
        {
            "client_surface_visible": True,
            "client_lifecycle_state": "NOT_APPLICABLE",
            "status": "NOT_REQUIRED",
            "applicability": "NOT_REQUIRED",
            "compliance_requirement_class": "DOCUMENT",
        },
    ]
    counts = compute_reporting_semantic_counts(rows)
    assert counts[METRIC_SCORE_TRACKED] == 3
    assert counts[METRIC_TRACKED] == 2
    assert counts[METRIC_COMPLIANT_SCORING] == 1
    assert counts[METRIC_VERIFIED] == 1


def test_lifecycle_satisfied_counts_all_visible_satisfied_rows():
    from services.requirement_satisfaction_service import is_requirement_satisfied

    rows = [
        {
            "client_surface_visible": True,
            "client_lifecycle_state": "SATISFIED_UNVERIFIED",
            "status": "COMPLIANT",
            "applicability": "MANDATORY",
            "compliance_requirement_class": "OBLIGATION",
        },
        {
            "client_surface_visible": True,
            "client_lifecycle_state": "VERIFIED",
            "status": "COMPLIANT",
            "applicability": "MANDATORY",
            "compliance_requirement_class": "DOCUMENT",
        },
    ]
    counts = compute_reporting_semantic_counts(rows)
    assert counts["visible_requirement_count"] == 2
    assert counts["lifecycle_satisfied_count"] == sum(1 for r in rows if is_requirement_satisfied(r))


def test_grouping_note_when_visible_exceeds_score_tracked():
    payload = build_reporting_semantics_payload(
        {"visible_requirement_count": 10, "score_tracked_requirement_count": 8, "tracked_requirement_count": 8}
    )
    assert payload.get("grouping_note")


def test_registry_display_overrides_enriched_visible_rows():
    rows = [
        {
            "client_surface_visible": True,
            "client_lifecycle_state": "SATISFIED_UNVERIFIED",
            "status": "COMPLIANT",
            "applicability": "MANDATORY",
            "compliance_requirement_class": "DOCUMENT",
        },
        {
            "client_surface_visible": True,
            "client_lifecycle_state": "VERIFIED",
            "status": "COMPLIANT",
            "applicability": "MANDATORY",
            "compliance_requirement_class": "DOCUMENT",
        },
    ]
    overrides = compute_registry_display_semantic_overrides(rows)
    assert overrides["visible_requirement_count"] == 2
    merged = apply_registry_display_semantics({"score_tracked_requirement_count": 1}, rows)
    assert merged["visible_requirement_count"] == 2
    assert merged["score_tracked_requirement_count"] == 1


def test_apply_registry_preserves_score_tracked_while_expanding_visible():
    """Score-scoped portal rows (8) + full registry enriched (10) → display parity without score drift."""
    score_portal = [
        {
            "client_surface_visible": True,
            "client_lifecycle_state": "VERIFIED",
            "status": "COMPLIANT",
            "applicability": "MANDATORY",
            "compliance_requirement_class": "DOCUMENT",
        }
        for _ in range(8)
    ]
    registry_enriched = [
        {
            "client_surface_visible": True,
            "client_lifecycle_state": "VERIFIED" if i < 6 else "SATISFIED_UNVERIFIED",
            "status": "COMPLIANT",
            "applicability": "MANDATORY",
            "compliance_requirement_class": "DOCUMENT",
        }
        for i in range(10)
    ]
    base = compute_reporting_semantic_counts(score_portal)
    assert base["score_tracked_requirement_count"] == 8
    merged = apply_registry_display_semantics(base, registry_enriched)
    assert merged["visible_requirement_count"] == 10
    assert merged["lifecycle_satisfied_count"] == 10
    assert merged["score_tracked_requirement_count"] == 8
    payload = build_reporting_semantics_payload(merged)
    assert payload.get("grouping_note")


def test_legacy_stats_alias_score_tracked():
    counts = {
        METRIC_SCORE_TRACKED: 10,
        METRIC_COMPLIANT_SCORING: 4,
        "pending": 3,
        "missing_document_count": 2,
        "expiring_requirement_count": 1,
        "overdue": 0,
    }
    legacy = legacy_stats_from_semantic_counts(counts)
    assert legacy["total_requirements"] == 10
    assert legacy["compliant"] == 4


def test_csv_preamble_includes_metrics():
    rows = csv_semantics_preamble_rows(
        {METRIC_SCORE_TRACKED: 5, METRIC_TRACKED: 7},
        generated_at="2026-06-04T12:00:00+00:00",
    )
    flat = "\n".join(",".join(r) for r in rows)
    assert "reporting_semantics_version" in flat
    assert "metric_score_tracked_requirement_count" in flat


def test_audit_pack_export_grade_immutable():
    reg = SURFACE_EXPORT_REGISTRY["audit_evidence_pack_zip"]
    assert reg["export_grade"] == GRADE_AUDIT_ARTIFACT
    assert reg["determinism"] == "immutable_artifact"


def test_evidence_readiness_pdf_immutable_grade():
    from services.reporting_semantics_v1 import EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT

    reg = SURFACE_EXPORT_REGISTRY["evidence_readiness_pdf"]
    assert reg["export_grade"] == GRADE_AUDIT_ARTIFACT
    assert reg["determinism"] == EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT


def test_professional_compliance_pdf_immutable_grade():
    from services.reporting_semantics_v1 import EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT, GRADE_REGULATORY

    reg = SURFACE_EXPORT_REGISTRY["professional_compliance_pdf"]
    assert reg["export_grade"] == GRADE_REGULATORY
    assert reg["determinism"] == EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT


def test_jspdf_not_regulatory_grade():
    from services.reporting_semantics_v1 import PDF_ENGINE_JSPDF, PDF_ENGINE_RULES

    assert GRADE_AUDIT_ARTIFACT in PDF_ENGINE_RULES[PDF_ENGINE_JSPDF]["prohibited_grades"]


def test_live_regenerated_disclosure_present():
    assert "latest portfolio" in LIVE_REGENERATED_DISCLOSURE.lower()


def test_build_payload_includes_definitions():
    payload = build_reporting_semantics_payload({METRIC_SCORE_TRACKED: 1})
    assert payload["version"] == "v1"
    assert "definitions" in payload
    assert payload["counts"][METRIC_SCORE_TRACKED] == 1
