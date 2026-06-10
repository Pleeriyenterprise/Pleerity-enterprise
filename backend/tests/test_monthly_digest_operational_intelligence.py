"""Monthly Operations Intelligence Digest presentation tests."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.monthly_digest_naming import (
    DIGEST_REPORT_TITLE,
    digest_attachment_filename,
    digest_email_subject,
)
from services.monthly_digest_operational_intelligence import (
    APPENDIX_MAX_ROWS,
    assert_client_safe_text,
    build_condensed_appendix_rows,
    build_digest_intelligence,
    build_executive_interpretation,
    build_portfolio_stability,
    build_what_changed_lines,
    collect_all_client_text,
    curate_priority_actions,
    humanize_recommendation,
    humanize_risk_driver,
    interpret_evidence_posture,
)
from services.monthly_digest_pdf_service import build_monthly_digest_pdf_bytes
from services.monthly_digest_pdf_service import _DIGEST_FROZEN_NOTE


def _leaky_driver() -> dict:
    return {
        "property_id": "p1",
        "property_name": "12 High Street",
        "requirement_id": "r1",
        "requirement_name": "Gas Safety Certificate",
        "workflow_class": "document_upload",
        "status": "OVERDUE",
        "take_action": {
            "primary": {"kind": "upload_document", "route": "/requirements/r1"},
            "contract": "requirement_take_action_v1",
            "provenance": {"handler": "requirement_action_resolver"},
        },
    }


def _base_model(**overrides):
    model = {
        "reporting_month_label": "March 2026",
        "generated_at_display": "01 April 2026 10:00 UTC",
        "account_name": "Test Portfolio Ltd",
        "properties_count": 3,
        "compliance_score": 62,
        "compliance_score_display": "62",
        "risk_level": "Medium Risk",
        "total_requirements": 12,
        "valid_count": 6,
        "compliant": 6,
        "expiring_soon": 2,
        "overdue": 3,
        "missing_evidence_count": 2,
        "documents_uploaded_period": 4,
        "open_compliance_jobs": 1,
        "open_maintenance_jobs": 0,
        "deltas": {
            "has_prior_snapshot": True,
            "score_delta": 5,
            "resolved_improved_labels": ["Gas Safety — 12 High Street"],
            "newly_overdue_labels": [],
            "newly_expiring_labels": ["EICR — 14 Low Road"],
            "documents_uploaded_delta_vs_prev_period": 2,
            "newly_missing_evidence_delta": -1,
        },
        "include_compliance_summary": True,
        "include_action_items": True,
        "include_recommendations": True,
        "include_property_breakdown": True,
        "include_recent_documents": True,
        "property_rows_pdf": [
            {
                "name": "12 High Street",
                "score": 70,
                "risk_level": "Medium",
                "overdue_count": 1,
                "expiring_soon_count": 0,
                "missing_evidence_count": 0,
                "open_jobs_count": 0,
            },
            {
                "name": "14 Low Road",
                "score": 55,
                "risk_level": "High",
                "overdue_count": 2,
                "expiring_soon_count": 1,
                "missing_evidence_count": 1,
                "open_jobs_count": 1,
            },
        ],
        "requirement_rows_pdf": [
            {
                "property_name": "12 High Street",
                "requirement_name": "Gas Safety Certificate",
                "state": "Overdue",
                "evidence_state": "Missing",
                "next_action": "Upload evidence",
            },
            {
                "property_name": "14 Low Road",
                "requirement_name": "Gas Safety Certificate",
                "state": "Overdue",
                "evidence_state": "Missing",
                "next_action": "Upload evidence",
            },
            {
                "property_name": "14 Low Road",
                "requirement_name": "EICR",
                "state": "Expiring soon",
                "evidence_state": "Verified",
                "next_action": "Plan renewal",
            },
        ],
        "score_block": {
            "drivers": [_leaky_driver()],
            "recommendations": [
                {
                    "priority": "high",
                    "action": "Upload gas safety evidence for 12 High Street",
                    "impact": "+8 points",
                    "display_label": "12 High Street",
                }
            ],
        },
        "urgent_items": [{"line": "Renew EICR (14 Low Road) — overdue", "title": "Renew EICR"}],
        "top_risk_drivers": [],
        "top_next_actions": [],
    }
    model.update(overrides)
    return model


def test_naming_no_legacy_compliance_summary():
    subj = digest_email_subject("March 2026")
    assert DIGEST_REPORT_TITLE in subj
    assert "Monthly Compliance Summary" not in subj
    assert digest_attachment_filename("2026-03").startswith("monthly-operations-intelligence-digest")


def test_interpret_evidence_posture_pending_not_noncompliant():
    label, note = interpret_evidence_posture("Pending", "Pending review")
    assert "Pending review" in label
    assert "not a compliance determination" in note.lower() or "pending" in note.lower()


def test_portfolio_stability_improving():
    s = build_portfolio_stability(
        _base_model(deltas={"has_prior_snapshot": True, "score_delta": 10, "resolved_improved_labels": ["A"], "newly_overdue_labels": []})
    )
    assert s["trajectory"] == "Improving"


def test_portfolio_stability_onboarding_first_report():
    s = build_portfolio_stability(_base_model(deltas={"has_prior_snapshot": False}, missing_evidence_count=5))
    assert s["trajectory"] == "Evidence onboarding phase"


def test_what_changed_includes_trajectory_narrative():
    lines = build_what_changed_lines(_base_model())
    assert any("trajectory" in ln.lower() for ln in lines)
    assert any("resolved" in ln.lower() or "strengthened" in ln.lower() for ln in lines)


def test_appendix_respects_max_rows():
    reqs = [
        {
            "property_name": f"P{i}",
            "requirement_name": "EICR",
            "state": "Overdue",
            "evidence_state": "Missing",
        }
        for i in range(30)
    ]
    rows = build_condensed_appendix_rows(_base_model(requirement_rows_pdf=reqs))
    assert len(rows) <= APPENDIX_MAX_ROWS


def test_email_subject_in_assembly_payload_shape():
    from services.monthly_digest_naming import digest_email_subject

    assert digest_email_subject("April 2026", subset=True).endswith("(selected properties)")


def test_deterministic_snapshot_wording_in_pdf(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    brand = MagicMock()
    brand.company_name = "Co"
    brand.primary_color = "#0B1D3A"
    brand.logo_path = None
    brand.include_pleerity_attribution = False
    brand.powered_by_text = ""
    pdf = build_monthly_digest_pdf_bytes(_pdf_model(), brand=brand)
    assert _DIGEST_FROZEN_NOTE[:40].encode() in pdf or b"point-in-time operational intelligence" in pdf.lower()


def test_humanize_risk_driver_strips_internal_fields():
    line = humanize_risk_driver(_leaky_driver())
    assert "12 High Street" in line
    assert "Gas Safety" in line
    assert "property_id" not in line
    assert "workflow_class" not in line
    assert "take_action" not in line


def test_humanize_recommendation_from_dict():
    text = humanize_recommendation({"action": "Upload EICR evidence", "impact": "+5 points"})
    assert "Upload EICR evidence" in text
    assert "{" not in text


def test_no_raw_json_leakage_in_intelligence_model():
    intel = build_digest_intelligence(_base_model())
    blob = collect_all_client_text(intel)
    assert assert_client_safe_text(blob)
    assert "workflow_class" not in blob.lower()
    assert "take_action" not in blob.lower()
    assert "property_id" not in blob.lower()
    assert "provenance" not in blob.lower()
    assert "handler" not in blob.lower()


def test_executive_interpretation_synthesises():
    text = build_executive_interpretation(_base_model())
    assert len(text) > 40
    assert "improved" in text.lower() or "posture" in text.lower()


def test_what_changed_with_prior_snapshot():
    lines = build_what_changed_lines(_base_model())
    assert any("improved" in ln.lower() for ln in lines)
    assert not any("first stored" in ln.lower() for ln in lines)


def test_what_changed_first_report_baseline():
    model = _base_model(deltas={"has_prior_snapshot": False})
    lines = build_what_changed_lines(model)
    assert any("baseline" in ln.lower() or "first" in ln.lower() for ln in lines)


def test_priority_deduplication_groups_by_requirement_type():
    intel = build_digest_intelligence(_base_model())
    immediate = intel["priority_actions"]["immediate"]
    grouped = [a for a in immediate if "properties" in (a.get("property") or "").lower()]
    assert grouped or immediate  # grouped gas safety or individual urgent items


def test_condensed_appendix_high_risk_only():
    rows = build_condensed_appendix_rows(_base_model(), max_rows=10)
    assert len(rows) <= 10
    assert all(r["status"] for r in rows)
    assert len(rows) >= 2


def test_property_movement_rows():
    intel = build_digest_intelligence(_base_model())
    movement = intel["property_movement"]
    assert len(movement) == 2
    assert any(m["direction"] == "Improved" for m in movement)


def _pdf_model(**overrides):
    return _base_model(**overrides)


def test_pdf_executive_digest_structure(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    brand = MagicMock()
    brand.company_name = "Acme Ltd"
    brand.tagline = "T"
    brand.primary_color = "#0B1D3A"
    brand.logo_path = None
    brand.include_pleerity_attribution = False
    brand.powered_by_text = ""
    pdf = build_monthly_digest_pdf_bytes(_pdf_model(), brand=brand)
    assert pdf.startswith(b"%PDF")
    assert b"Monthly Operations Intelligence Digest" in pdf
    assert b"Executive snapshot" in pdf
    assert b"What changed this month" in pdf
    assert b"Priority actions" in pdf
    assert b"Portfolio risk highlights" in pdf
    assert b"Property movement summary" in pdf
    assert b"Evidence activity summary" in pdf
    assert b"Requirement breakdown" not in pdf


def test_pdf_no_internal_leakage_with_raw_drivers(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    brand = MagicMock()
    brand.company_name = "Co"
    brand.tagline = ""
    brand.primary_color = "#0B1D3A"
    brand.logo_path = None
    brand.include_pleerity_attribution = False
    brand.powered_by_text = ""
    model = _pdf_model()
    model["top_risk_drivers"] = [str(_leaky_driver())]  # legacy bad data must not surface
    pdf = build_monthly_digest_pdf_bytes(model, brand=brand)
    text = pdf.decode("latin-1", errors="ignore").lower()
    assert "workflow_class" not in text
    assert "take_action" not in text
    assert "provenance" not in text
    assert "requirement_take_action" not in text


def test_pdf_sparse_portfolio_readable(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    brand = MagicMock()
    brand.company_name = "Solo"
    brand.primary_color = "#0B1D3A"
    brand.logo_path = None
    brand.include_pleerity_attribution = False
    brand.powered_by_text = ""
    model = _pdf_model(
        properties_count=1,
        property_rows_pdf=[
            {
                "name": "Flat 1",
                "score": 88,
                "risk_level": "Low",
                "overdue_count": 0,
                "expiring_soon_count": 0,
                "missing_evidence_count": 0,
                "open_jobs_count": 0,
            }
        ],
        requirement_rows_pdf=[],
        overdue=0,
        missing_evidence_count=0,
        score_block={"drivers": [], "recommendations": []},
        urgent_items=[],
    )
    pdf = build_monthly_digest_pdf_bytes(model, brand=brand)
    from pypdf import PdfReader
    import io

    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) >= 3
    assert b"Executive snapshot" in pdf


def test_pdf_large_portfolio_pagination_stable(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    brand = MagicMock()
    brand.company_name = "Large Co"
    brand.primary_color = "#0B1D3A"
    brand.logo_path = None
    brand.include_pleerity_attribution = False
    brand.powered_by_text = ""
    props = []
    reqs = []
    for i in range(25):
        props.append(
            {
                "name": f"Property {i} Long Address Name",
                "score": 50 + (i % 30),
                "risk_level": "Medium",
                "overdue_count": i % 3,
                "expiring_soon_count": i % 2,
                "missing_evidence_count": i % 2,
                "open_jobs_count": 0,
            }
        )
        if i % 4 == 0:
            reqs.append(
                {
                    "property_name": f"Property {i} Long Address Name",
                    "requirement_name": "EICR",
                    "state": "Overdue",
                    "evidence_state": "Missing",
                }
            )
    model = _pdf_model(properties_count=25, property_rows_pdf=props, requirement_rows_pdf=reqs)
    pdf = build_monthly_digest_pdf_bytes(model, brand=brand)
    from pypdf import PdfReader
    import io

    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) >= 4
    full = "\n".join((p.extract_text() or "") for p in reader.pages).lower()
    assert "requirement breakdown" not in full
    assert "workflow_class" not in full
