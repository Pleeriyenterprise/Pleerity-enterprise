"""S2-A — cross-surface semantic parity and drift detection."""
from __future__ import annotations

from email_templates.unified.scheduled_report_digest import build_scheduled_report_digest_html
from services.report_compliance_summary_executive import _STATUS_HUMAN
from services.report_human_language_v1 import SCORE_STATUS_LABELS
from services.report_requirements_operational import TRIAGE_SECTION_TITLES
from services.vocabulary_contract_v1 import (
    POSTURE_SURFACE_VARIANTS,
    VERIFICATION_LADDER,
    assert_semantic_safe_text,
    find_prohibited_phrases,
    find_raw_telemetry_leaks,
    human_authority_tier,
    scan_registered_customer_surfaces,
)


def _status_human_blob() -> str:
    return "\n".join(_STATUS_HUMAN.values())


def test_executive_posture_uses_favourable_not_on_track():
    assert _STATUS_HUMAN["GREEN"] == "Favourable posture"
    assert "On track" not in _status_human_blob()


def test_requirements_triage_preserves_recorded_section():
    assert "Recorded but not independently verified" in TRIAGE_SECTION_TITLES.values()
    assert "Verified or accepted obligations" in TRIAGE_SECTION_TITLES.values()


def test_score_labels_humanised_not_raw_enums():
    for key, label in SCORE_STATUS_LABELS.items():
        assert key not in label
        leaks = find_raw_telemetry_leaks(label)
        assert not leaks, f"leak in score label for {key}"


def test_scheduled_email_html_no_prohibited_phrases():
    html, _ = build_scheduled_report_digest_html(
        {
            "frequency": "weekly",
            "report_type": "requirements",
            "generated_date": "10 Jun 2026",
            "portal_link": "https://example.com",
            "report_rows": [
                {
                    "status": "RECORDED_UNVERIFIED",
                    "triage_category": "Recorded but not independently verified",
                    "description": "Test obligation",
                    "operational_status": "Recorded on file",
                }
            ],
        }
    )
    assert find_prohibited_phrases(html) == []
    assert "Recorded (not independently verified)" in html
    assert_semantic_safe_text(html, context="scheduled_requirements_email", allow_stale=True)


def test_scheduled_compliance_email_cvp_humanised():
    html, _ = build_scheduled_report_digest_html(
        {
            "frequency": "weekly",
            "report_type": "compliance_summary",
            "generated_date": "10 Jun 2026",
            "portal_link": "https://example.com",
            "report_summary": {
                "total_properties": 2,
                "compliance_breakdown": {"green": 1, "amber": 1, "red": 0},
                "requirements_breakdown": {"compliant": 1, "overdue": 1, "pending": 0, "expiring_soon": 0},
                "compliance_rate": 50,
                "compliance_score_headline": {
                    "compliance_score_display": "72",
                    "score_status": "ok",
                    "score_authority": "persisted_property_score",
                },
            },
            "properties_snapshot": [],
        }
    )
    low = html.lower()
    assert "score_status=ok" not in low
    assert "persisted_property_score" not in low
    assert "current" in low


def test_posture_variant_registry_documents_known_drift():
    variants = POSTURE_SURFACE_VARIANTS["tier_0_favourable"]
    assert "Favourable posture" in variants
    assert any("on track" in v.lower() for v in variants)


def test_verification_ladder_matches_requirements_email_buckets():
    recorded_label = VERIFICATION_LADDER[1]
    assert "not independently verified" in recorded_label.lower()


def test_authority_tier_ordering_across_report_classes():
    assert human_authority_tier("audit_evidence_pack") < human_authority_tier("requirements")
    assert human_authority_tier("requirements") < human_authority_tier("compliance_summary")
    assert human_authority_tier("compliance_summary") < human_authority_tier("monthly_digest")
    assert human_authority_tier("monthly_digest") < human_authority_tier("scheduled_email")


def test_surface_scan_report_structure():
    report = scan_registered_customer_surfaces()
    assert "surfaces" in report
    assert "prohibited_hits" in report
    assert report["prohibited_hits"] == {}
