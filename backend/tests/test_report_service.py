"""Tests for Evidence Readiness PDF and report service."""
import asyncio
import pytest
from services.report_service import generate_evidence_readiness_pdf, EVIDENCE_READINESS_DISCLAIMER


def test_generate_evidence_readiness_pdf_returns_pdf_bytes():
    """Generate Evidence Readiness PDF returns non-empty buffer that looks like a PDF."""
    from unittest.mock import AsyncMock, MagicMock, patch

    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value={"company_name": "Test Co", "customer_reference": "CRN-001"})
    db.properties.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[
        {"property_id": "p1", "address_line_1": "1 High St", "compliance_score": 80, "risk_level": "Low risk", "compliance_last_calculated_at": "2025-01-01T12:00:00Z"},
    ])))
    db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    db.audit_logs.find = MagicMock(return_value=MagicMock(sort=MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))))

    with patch("services.report_service.database.get_db", return_value=db):
        with patch("services.professional_reports.professional_report_generator", None):
            buf = asyncio.run(generate_evidence_readiness_pdf("client-1", "portfolio", property_id=None))
    assert buf is not None
    data = buf.read()
    assert len(data) > 200
    assert data[:4] == b"%PDF", "Output should be a PDF file"


def test_disclaimer_constant():
    assert "legal advice" in EVIDENCE_READINESS_DISCLAIMER.lower()
    assert "document status" in EVIDENCE_READINESS_DISCLAIMER.lower()
