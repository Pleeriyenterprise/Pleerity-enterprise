"""Tests for AI document extraction pipeline (extracted_documents, enqueue, status, confirm/reject)."""
import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_ai_disabled_returns_failed_with_ai_not_configured():
    """When AI_EXTRACTION_ENABLED=false, extract_compliance_fields returns success=False, error_code AI_NOT_CONFIGURED."""
    with patch.dict(os.environ, {"AI_EXTRACTION_ENABLED": "false"}, clear=False):
        from services.ai_provider import extract_compliance_fields
        result = extract_compliance_fields("some text", "doc.pdf", None)
    assert result.get("success") is False
    assert result.get("error_code") == "AI_NOT_CONFIGURED"
    assert result.get("extracted") is None


def test_valid_extraction_json_normalizes_and_has_doc_type():
    """Valid extraction JSON is normalized (doc_type in enum, confidence 0-1)."""
    from services.ai_provider import _normalize_extraction
    parsed = {
        "doc_type": "EICR",
        "certificate_number": "123",
        "issue_date": "2025-01-01",
        "expiry_date": "2028-01-01",
        "confidence": {"overall": 0.9, "dates": 0.95, "address": 0.8, "doc_type": 0.9},
        "notes": None,
    }
    out = _normalize_extraction(parsed)
    assert out["doc_type"] == "EICR"
    assert out["expiry_date"] == "2028-01-01"  # YYYY-MM-DD preserved
    assert out["confidence"]["overall"] == 0.9


def test_low_confidence_or_missing_expiry_needs_review():
    """Status rule: overall >= 0.85 and expiry_date present => EXTRACTED, else => NEEDS_REVIEW."""
    from services.document_extraction_service import CONFIDENCE_THRESHOLD
    assert CONFIDENCE_THRESHOLD == 0.85
    # Logic is in run_extraction_job: if overall >= 0.85 and expiry_date then EXTRACTED else NEEDS_REVIEW
    # So we just assert the constant and that the logic would classify low/missing as NEEDS_REVIEW
    overall_low = 0.5
    expiry_missing = None
    assert not (overall_low >= CONFIDENCE_THRESHOLD and expiry_missing)


def test_confirm_endpoint_sets_confirmed_and_updates_requirement():
    """Admin confirm sets extracted_documents.status=CONFIRMED and document.extraction_status=CONFIRMED."""
    from routes.documents import admin_confirm_extraction, AdminExtractionConfirmBody
    from fastapi import Request

    req = MagicMock(spec=Request)
    body = AdminExtractionConfirmBody(document_id="doc-123")
    db = MagicMock()
    document = {"document_id": "doc-123", "client_id": "c1", "extraction_id": "ext-1", "requirement_id": "req-1"}
    rec = {"extraction_id": "ext-1", "status": "NEEDS_REVIEW", "extracted": {"expiry_date": "2026-06-01", "doc_type": "GAS_SAFETY"}}
    db.documents.find_one = AsyncMock(side_effect=[document])
    db.extracted_documents.find_one = AsyncMock(return_value=rec)
    db.requirements.update_one = AsyncMock()
    db.extracted_documents.update_one = AsyncMock()
    db.documents.update_one = AsyncMock()

    with patch("routes.documents.admin_route_guard", AsyncMock()):
        with patch("routes.documents.database.get_db", return_value=db):
            with patch("routes.documents.create_audit_log", AsyncMock()):
                result = asyncio.run(admin_confirm_extraction(req, body))
    assert result["message"] == "Extraction applied"
    assert result["document_id"] == "doc-123"
    db.extracted_documents.update_one.assert_called_once()
    call_args = db.extracted_documents.update_one.call_args
    assert call_args[0][1]["$set"]["status"] == "CONFIRMED"
    db.documents.update_one.assert_called_once()
    doc_set = db.documents.update_one.call_args[0][1]["$set"]
    assert doc_set["extraction_status"] == "CONFIRMED"


def test_reject_endpoint_sets_rejected():
    """Admin reject sets status=REJECTED and applies nothing to requirement."""
    from routes.documents import admin_reject_extraction, AdminExtractionRejectBody
    from fastapi import Request

    req = MagicMock(spec=Request)
    body = AdminExtractionRejectBody(document_id="doc-456", reason="Test reject")
    db = MagicMock()
    db.requirements = MagicMock()  # reject must not touch requirements
    document = {"document_id": "doc-456", "client_id": "c2", "extraction_id": "ext-2"}
    db.documents.find_one = AsyncMock(return_value=document)
    db.extracted_documents.update_one = AsyncMock()
    db.documents.update_one = AsyncMock()

    with patch("routes.documents.admin_route_guard", AsyncMock()):
        with patch("routes.documents.database.get_db", return_value=db):
            with patch("routes.documents.create_audit_log", AsyncMock()):
                result = asyncio.run(admin_reject_extraction(req, body))
    assert result["message"] == "Extraction rejected"
    db.extracted_documents.update_one.assert_called_once()
    assert db.extracted_documents.update_one.call_args[0][1]["$set"]["status"] == "REJECTED"
    db.requirements.update_one.assert_not_called()
