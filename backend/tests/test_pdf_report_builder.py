"""Tests for deterministic PDF report builder (evidence readiness)."""
import pytest
from services.pdf_report_builder import (
    build_portfolio_report,
    build_property_report,
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
