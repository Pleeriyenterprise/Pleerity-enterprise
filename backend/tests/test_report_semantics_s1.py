"""Phase S1 — report semantics trust and contradiction guards."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.report_compliance_summary_executive import (
    build_compliance_summary_executive_model,
    build_executive_interpretation,
    human_property_dashboard_status,
    portfolio_material_exposure,
)
from services.report_requirements_operational import (
    build_requirements_operational_csv_rows,
    build_requirements_scheduled_email_rows,
)
from services.reporting_service import ReportingService


def _req(**kw):
    base = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "gas_safety",
        "description": "Annual gas safety inspection",
        "status": "OVERDUE",
        "due_date": "2026-07-14",
        "client_lifecycle_state": "ACTION_REQUIRED",
        "requirement_satisfied": False,
        "missing_required_document": True,
    }
    base.update(kw)
    return base


def _self_recorded(**kw):
    defaults = {
        "requirement_id": "sr1",
        "client_lifecycle_state": "SATISFIED_UNVERIFIED",
        "assurance_tier": "SELF_RECORDED",
        "requirement_satisfied": True,
        "missing_required_document": False,
        "document_upload_required": False,
        "requirement_attention_eligible": False,
        "truth_presentation_stage": "declaration_recorded",
        "status": "COMPLIANT",
    }
    defaults.update(kw)
    return _req(**defaults)


def test_portfolio_material_exposure_detects_overdue_and_missing():
    assert portfolio_material_exposure(
        overdue=1,
        missing_evidence=0,
        counts={"pending": 0},
        readiness={"unresolved_evidence_exposure": 0},
        risk_concentration=[],
    )
    assert portfolio_material_exposure(
        overdue=0,
        missing_evidence=2,
        counts={"pending": 0},
        readiness={"unresolved_evidence_exposure": 0},
        risk_concentration=[],
    )


def test_executive_interpretation_suppresses_all_clear_when_exposure_exists():
    lines = build_executive_interpretation(
        counts={"pending": 0, "compliant": 1},
        readiness={"audit_confidence": "High", "unresolved_evidence_exposure": 0},
        risk_concentration=[],
        overdue=2,
        missing_evidence=0,
        expiring=0,
        completion_pct=50,
        total_reqs=2,
    )
    blob = " ".join(lines).lower()
    assert "no material compliance posture concerns" not in blob
    assert "exposure" in blob or "unresolved" in blob or "overdue" in blob


def test_executive_interpretation_softens_high_confidence_when_exposure_exists():
    lines = build_executive_interpretation(
        counts={"pending": 0},
        readiness={"audit_confidence": "High", "unresolved_evidence_exposure": 1},
        risk_concentration=[{"theme": "Fire safety", "unresolved": 1}],
        overdue=0,
        missing_evidence=1,
        expiring=0,
        completion_pct=80,
        total_reqs=5,
    )
    blob = " ".join(lines).lower()
    assert "substantially strong" not in blob
    assert "warrants" in blob or "review" in blob


def test_green_dashboard_downgrades_when_property_overdue():
    label = human_property_dashboard_status(
        "GREEN",
        stats={"overdue": 2, "missing_evidence": 0, "expiring_soon": 0},
    )
    assert label == "Elevated attention"
    assert label != "Favourable posture"


def test_property_readiness_not_strong_when_overdue_in_model():
    readiness = {
        "evidence_completeness_pct": 90,
        "audit_confidence": "High",
        "unresolved_evidence_exposure": 0,
        "evidence_completeness_note": "Broadly complete",
    }
    model = build_compliance_summary_executive_model(
        requirements=[_req()],
        properties=[
            {
                "property_id": "p1",
                "address_line_1": "1 High Street",
                "postcode": "AB1 2CD",
                "compliance_status": "GREEN",
            }
        ],
        client_doc={},
        matrix_rows=[],
        readiness=readiness,
        counts={
            "total_requirements": 1,
            "compliant": 0,
            "overdue": 1,
            "expiring_soon": 0,
            "missing_evidence": 0,
            "pending": 0,
        },
        total_props=1,
        green=1,
        amber=0,
        red=0,
    )
    posture = model["property_posture"][0]
    assert posture["status"] != "Favourable posture"
    assert posture["readiness"] != "Strong"


def test_scheduled_email_recorded_not_mapped_to_compliant():
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    _, _, enriched = build_requirements_operational_csv_rows(
        requirements=[_self_recorded()],
        properties=[{"property_id": "p1", "address_line_1": "1 High St", "postcode": "AB1 2CD"}],
        client_doc={},
        now=now,
    )
    email_rows = build_requirements_scheduled_email_rows(enriched)
    assert email_rows
    assert email_rows[0]["status"] == "RECORDED_UNVERIFIED"
    assert email_rows[0]["status"] != "COMPLIANT"


def test_compliance_csv_humanises_score_and_posture_labels():
    svc = ReportingService()
    now = datetime.now(timezone.utc)
    data = {
        "report_type": "Compliance Summary",
        "generated_at": now.isoformat(),
        "client": {"name": "Test Client"},
        "summary": {
            "total_properties": 1,
            "compliance_rate": 0.0,
            "compliance_breakdown": {"green": 1, "amber": 0, "red": 0},
            "total_requirements": 1,
            "requirements_breakdown": {
                "compliant": 0,
                "pending": 0,
                "overdue": 1,
                "expiring_soon": 0,
            },
            "expiring_next_30_days": 0,
            "expiring_next_60_days": 0,
            "expiring_next_90_days": 0,
            "compliance_score_headline": {
                "compliance_score_display": "72",
                "score_authority": "persisted_property_score",
                "score_status": "ok",
                "last_calculated_at": "2026-04-01T10:00:00+00:00",
                "score_status_message": "Headline stable.",
            },
            "async_reporting_disclosure": {"messages": []},
        },
        "reporting_semantics": {
            "counts": {
                "score_tracked_requirement_count": 1,
                "compliant_requirement_count": 0,
            }
        },
        "portal_requirements": [_req()],
        "properties_portal": [
            {
                "property_id": "p1",
                "address_line_1": "1 High Street",
                "postcode": "AB1 2CD",
                "compliance_status": "GREEN",
            }
        ],
        "client_doc": {},
    }
    text = svc._generate_compliance_csv(data)["content"]
    assert "Green (Favourable posture)" in text
    assert "Green (Compliant)" not in text
    assert "Score status (human-readable),Current" in text
    assert "Score authority (human-readable),Stored property scores" in text
    assert "score_status,ok" not in text
    assert "# reporting_semantics_version" in text
    assert "not a legal compliance determination" in text
