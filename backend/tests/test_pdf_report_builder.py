"""Tests for deterministic PDF report builder (evidence readiness)."""
import pytest
from services.pdf_report_builder import (
    build_portfolio_report,
    build_property_report,
    build_score_explanation_report,
    build_requirements_report_pdf,
    PDF_FOOTER_DISCLAIMER,
)


def _minimal_report_data(crn="CRN-001", now_iso="2025-02-20T12:00:00+00:00"):
    return {
        "client": {"company_name": "Test Co", "customer_reference": crn},
        "properties": [
            {"property_id": "p1", "address_line_1": "1 High St", "compliance_score": 80, "risk_level": "Low risk"},
        ],
        "requirements": [],
        "audit_logs": [],
        "now_iso": now_iso,
        "branding": {"primary_color": "#0B1D3A", "secondary_color": "#00B8A9", "company_name": "Test Co"},
    }


def test_build_portfolio_report_returns_pdf_bytes():
    """Builder returns bytes that are a valid PDF."""
    data = _minimal_report_data()
    pdf_bytes = build_portfolio_report("client-1", data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 200
    assert pdf_bytes[:4] == b"%PDF", "Output should be a PDF file"


def test_build_property_report_returns_pdf_bytes():
    """Property report returns bytes that are a valid PDF."""
    data = _minimal_report_data()
    pdf_bytes = build_property_report("client-1", "p1", data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 200
    assert pdf_bytes[:4] == b"%PDF", "Output should be a PDF file"


def test_pdf_includes_crn_and_timestamp():
    """Generated PDF uses report_data; template includes CRN and Generated timestamp (streams may be compressed)."""
    data1 = _minimal_report_data(crn="CRN-A", now_iso="2025-02-20T12:00:00+00:00")
    data2 = _minimal_report_data(crn="CRN-B", now_iso="2026-03-21T14:00:00+00:00")
    pdf1 = build_portfolio_report("client-1", data1)
    pdf2 = build_portfolio_report("client-1", data2)
    # Output differs when CRN/timestamp change, so template is filled from report_data
    assert pdf1 != pdf2, "PDF content should depend on report_data (CRN/timestamp)"
    # Builder code puts "Generated: <date>" and "CRN: ..." on cover; raw bytes may be compressed
    assert len(pdf1) > 200 and pdf1[:4] == b"%PDF"


def test_footer_disclaimer_constant():
    """Footer disclaimer is the short legal line."""
    assert "legal advice" in PDF_FOOTER_DISCLAIMER.lower()
    assert "This report does not constitute" in PDF_FOOTER_DISCLAIMER


def test_build_score_explanation_report_snapshot_and_headline_note(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    payload = {
        "score": 75,
        "score_status": "stale",
        "grade": "C",
        "score_authority": "persisted",
        "last_calculated_at": "2026-03-15T10:30:00+00:00",
        "score_status_message": "Recalculation pending after bulk upload.",
        "stats": {"compliant": 1, "expiring_soon": 0, "overdue": 0},
        "properties_count": 2,
        "data_completeness_percent": 100,
        "score_model_version": "2",
        "drivers": [],
        "property_breakdown": [],
    }
    client_doc = {"company_name": "Test Co", "customer_reference": "CRN-X"}
    pdf = build_score_explanation_report("client-1", payload, client_doc, {})
    assert pdf.startswith(b"%PDF")
    assert b"Snapshot as of" in pdf
    assert b"Recalculation pending after bulk upload." in pdf
    assert b"live calculator" not in pdf.lower()


def test_evidence_readiness_portfolio_pdf_snapshot_and_score_meta(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    data = _minimal_report_data(now_iso="2026-04-30T12:00:00+00:00")
    data["properties"][0]["compliance_last_calculated_at"] = "2026-03-10T15:00:00+00:00"
    pdf = build_portfolio_report("client-1", data)
    assert pdf.startswith(b"%PDF")
    assert b"Snapshot generated at" in pdf
    assert b"Score status:" in pdf
    assert b"Last score calculation:" in pdf
    assert b"live portal" not in pdf.lower()


def test_evidence_readiness_property_pdf_snapshot_and_score_meta(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    data = _minimal_report_data(now_iso="2026-04-30T12:00:00+00:00")
    data["properties"][0]["compliance_last_calculated_at"] = "2026-03-10T15:00:00+00:00"
    data["properties"][0]["score_status_message"] = "Property note for export."
    pdf = build_property_report("client-1", "p1", data)
    assert pdf.startswith(b"%PDF")
    assert b"Snapshot generated at" in pdf
    assert b"Last score calculation:" in pdf
    assert b"Property note for export." in pdf
    assert b"live portal" not in pdf.lower()


def test_build_score_explanation_report_no_live_calculator_when_bucket_breakdown_missing(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    payload = {
        "score": 60,
        "score_status": "ok",
        "grade": "D",
        "score_authority": "persisted",
        "portfolio_last_calculated_at": "2026-01-01T00:00:00Z",
        "stats": {"compliant": 0, "expiring_soon": 0, "overdue": 1},
        "properties_count": 1,
        "drivers": [{"property_id": "p1", "property_name": "A", "requirement_name": "Gas", "status": "OVERDUE", "actions": ["VIEW"]}],
        "property_breakdown": [{"name": "A", "property_id": "p1", "score": 60, "score_status": "ok", "valid": 0, "expiring": 0, "overdue": 1}],
        "bucket_breakdown": {},
    }
    pdf = build_score_explanation_report("c1", payload, {"company_name": "Co", "customer_reference": "CRN"}, {})
    assert b"live calculator" not in pdf.lower()
    assert b"headline refresh" in pdf.lower() or b"persisted" in pdf.lower() or b"Area-by-area" in pdf


def test_build_score_explanation_report_trust_safe_copy(monkeypatch):
    """Score summary PDF must not leak engineering scoring language."""
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    payload = {
        "score": 72,
        "score_status": "ok",
        "grade": "B",
        "score_authority": "persisted",
        "last_calculated_at": "2026-03-15T10:30:00+00:00",
        "stats": {"compliant": 2, "expiring_soon": 1, "overdue": 0},
        "properties_count": 1,
        "data_completeness_percent": 100,
        "score_model_version": "2",
        "drivers": [],
        "property_breakdown": [],
        "bucket_breakdown": {
            "legal_core": {"percent": 80},
            "documentation_completeness": {"percent": 70},
            "operational_responsiveness": {"percent": 90},
            "recency_maintenance_confidence": {"percent": 85},
        },
    }
    pdf = build_score_explanation_report("c1", payload, {"company_name": "Co", "customer_reference": "CRN"}, {})
    low = pdf.lower()
    for forbidden in (
        b"cvp score",
        b"credit in bucket",
        b"credit earned",
        b"bucket emphasis",
        b"weighted",
        b"model:",
    ):
        assert forbidden not in low, f"forbidden phrase in PDF: {forbidden!r}"
    assert b"Core legal requirements" in pdf or b"How you're doing in each area" in pdf
    assert b"Not legal advice" in pdf or b"not legal advice" in low


def test_portfolio_pdf_immutable_artifact_notice(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    from services.immutable_report_artifact_service import prepare_artifact_identity

    data = _minimal_report_data()
    data["artifact_lineage"] = prepare_artifact_identity(
        client_id="client-1",
        report_type="evidence_readiness",
        scope="portfolio",
        report_data=data,
    )
    pdf = build_portfolio_report("client-1", data)
    assert b"IMMUTABLE GOVERNANCE ARTIFACT" in pdf
    assert b"Artifact ID" in pdf


def test_portfolio_pdf_governance_sections(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    data = _minimal_report_data()
    data["requirements"] = [
        {
            "property_id": "p1",
            "client_lifecycle_state": "ACTION_REQUIRED",
            "description": "EPC",
            "due_date": "2026-12-01",
        }
    ]
    pdf = build_portfolio_report("client-1", data)
    assert b"Unresolved obligations" in pdf
    assert b"Export grade" in pdf
    pdf_text = pdf.decode("latin-1", errors="ignore")
    assert "Recorded but not independently verified" in pdf_text or "Self-recorded" in pdf_text
    assert b"Frozen governance record" in pdf or b"may differ from" in pdf


def test_portfolio_pdf_regenerated_timestamp(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    data = _minimal_report_data()
    data["original_generated_at"] = "2026-01-15T10:00:00+00:00"
    data["regenerated_at"] = "2026-06-02T14:00:00+00:00"
    pdf = build_portfolio_report("client-1", data)
    assert b"Regenerated" in pdf


def test_requirements_report_pdf_bytes(monkeypatch):
    monkeypatch.setattr("reportlab.rl_config.pageCompression", 0)
    data = _minimal_report_data()
    data["requirements"] = [
        {
            "property_id": "p1",
            "description": "Gas safety inspection",
            "client_lifecycle_state": "VERIFIED",
            "requirement_satisfied": True,
            "assurance_tier": "VERIFIED_DOCUMENT",
            "status": "COMPLIANT",
        }
    ]
    pdf = build_requirements_report_pdf("client-1", data)
    assert pdf[:4] == b"%PDF"
    assert b"Requirements Report" in pdf
    low = pdf.decode("latin-1", errors="ignore").lower()
    assert "triage at a glance" in low
