"""Tests for score cognition service."""
from services.score_cognition_service import (
    build_property_score_cognition_line,
    build_score_risk_explanation,
)


def test_no_open_gaps_with_low_score_gets_explanation():
    row = {
        "property_score": 55,
        "overdue_count": 0,
        "missing_count": 0,
        "expiring_30_count": 0,
        "compliance_top_deficits": [
            {"requirement_code": "LEGIONELLA", "status": "SATISFIED_UNVERIFIED"},
        ],
    }
    line = build_property_score_cognition_line(row)
    assert line != "No open gaps in this snapshot"
    assert "assurance" in line.lower() or "self-recorded" in line.lower()


def test_blocker_kpis_take_precedence():
    row = {
        "property_score": 55,
        "overdue_count": 0,
        "missing_count": 1,
        "expiring_30_count": 0,
        "compliance_top_deficits": [],
    }
    assert build_property_score_cognition_line(row) == "1 missing documents"


def test_pending_score_shows_updating():
    row = {"compliance_score_pending": True, "property_score": 55}
    assert "updating" in build_property_score_cognition_line(row).lower()


def test_risk_explanation_for_platform_review():
    row = {
        "property_score": 60,
        "missing_count": 0,
        "compliance_top_deficits": [{"status": "ASSURANCE_PENDING"}],
    }
    expl = build_score_risk_explanation(row)
    assert expl and "verification" in expl.lower()
