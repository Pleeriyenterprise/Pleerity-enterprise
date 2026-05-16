"""Unit tests for admin pending-verification enrichment readiness derivation."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from services.admin_verification_readiness import (
    READINESS_FAILED,
    READINESS_PARTIAL,
    READINESS_PROCESSING,
    READINESS_READY,
    MATCH_STATUS_COMPLETE,
    MATCH_STATUS_PENDING,
    attach_verification_readiness_fields,
    derive_enrichment_readiness,
    match_evaluation_attempted,
)


def test_ready_when_extraction_terminal_and_match_complete():
    doc = {
        "document_id": "d1",
        "uploaded_at": "2026-05-15T10:00:00+00:00",
        "extraction_status": "EXTRACTED",
        "match_outcome": "MATCH_LIKELY",
        "predicted_document_type": "GAS_SAFETY",
        "requirement_id": "req-1",
        "requirement_label": "Gas safety",
    }
    out = derive_enrichment_readiness(doc, requirement_label_resolved=True)
    assert out["enrichment_readiness"] == READINESS_READY
    assert out["match_status"] == MATCH_STATUS_COMPLETE
    assert out["enrichment_readiness_label"] == "Ready for review"


def test_processing_when_match_not_attempted_and_no_extraction_status():
    doc = {
        "document_id": "d2",
        "uploaded_at": "2026-05-15T10:00:00+00:00",
    }
    out = derive_enrichment_readiness(doc)
    assert out["enrichment_readiness"] == READINESS_PROCESSING
    assert out["match_status"] == MATCH_STATUS_PENDING
    assert "progress" in out["enrichment_readiness_label"].lower() or "preparation" in out["enrichment_readiness_label"].lower()


def test_failed_when_extraction_failed_without_match():
    doc = {
        "document_id": "d3",
        "uploaded_at": "2026-05-15T10:00:00+00:00",
        "extraction_status": "FAILED",
        "ai_extraction": {"status": "failed", "error": "NO_KEY"},
    }
    out = derive_enrichment_readiness(doc)
    assert out["enrichment_readiness"] == READINESS_FAILED
    assert "failed" in out["enrichment_readiness_label"].lower()


def test_partial_when_match_pending_after_extraction():
    doc = {
        "document_id": "d4",
        "uploaded_at": "2026-05-15T10:00:00+00:00",
        "extraction_status": "EXTRACTED",
    }
    out = derive_enrichment_readiness(doc)
    assert out["enrichment_readiness"] == READINESS_PARTIAL
    assert out["match_status"] == MATCH_STATUS_PENDING
    assert "match" in out["enrichment_readiness_label"].lower()


def test_partial_when_requirement_label_missing():
    doc = {
        "document_id": "d5",
        "uploaded_at": "2026-05-15T10:00:00+00:00",
        "extraction_status": "CONFIRMED",
        "match_outcome": "MATCH_LIKELY",
        "requirement_id": "req-x",
        "requirement_label": None,
    }
    out = derive_enrichment_readiness(doc, requirement_label_resolved=False)
    assert out["enrichment_readiness"] == READINESS_PARTIAL
    assert "requirement" in out["enrichment_readiness_label"].lower()


def test_match_evaluation_attempted_signals():
    assert match_evaluation_attempted({"match_outcome": "MATCH_LIKELY"}) is True
    assert match_evaluation_attempted({"mismatch_reason_code": "NO_REQUIREMENT_LINK"}) is True
    assert match_evaluation_attempted({}) is False


def test_attach_fields_adds_readiness_to_all_rows():
    items = [
        {
            "document_id": "a",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "match_outcome": "MATCH_LIKELY",
            "extraction_status": "EXTRACTED",
            "property_id": "prop-1",
            "requirement_id": "req-1",
            "requirement_label": "Gas safety",
        },
        {"document_id": "b", "uploaded_at": datetime.now(timezone.utc).isoformat(), "extraction_status": "PENDING", "extraction_id": "ext-1"},
    ]
    obs = attach_verification_readiness_fields(items, {"ext-1": {"extraction_id": "ext-1", "status": "PENDING"}})
    assert items[0]["enrichment_readiness"] == READINESS_READY
    assert items[1]["enrichment_readiness"] == READINESS_PROCESSING
    assert obs["readiness_counts"][READINESS_READY] == 1
    assert obs["readiness_counts"][READINESS_PROCESSING] == 1
