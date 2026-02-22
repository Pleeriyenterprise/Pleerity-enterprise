"""
Unit tests for document status service.
- Multiple docs: choose furthest future expiry as evidence
- No expiry_date for expiring requirement -> NEEDS_REVIEW
- Expired -> EXPIRED
- Expiring within 60 -> EXPIRING_SOON
- No doc -> MISSING_EVIDENCE
- Determinism: tie-breakers stable
"""
import pytest
from datetime import date, datetime, timezone, timedelta
from services.document_status_service import (
    pick_evidence_document,
    compute_requirement_status,
    STATUS_MISSING_EVIDENCE,
    STATUS_NEEDS_REVIEW,
    STATUS_VALID,
    STATUS_EXPIRING_SOON,
    STATUS_EXPIRED,
    REASON_NO_DOCUMENT_FOUND,
    REASON_MISSING_EXPIRY_DATE,
    REASON_DOCUMENT_EXPIRED,
    REASON_DOCUMENT_EXPIRING_SOON,
    STATUS_TO_FRACTION,
    EXPIRING_SOON_DAYS,
)


class TestPickEvidenceDocument:
    """pick_evidence_document: filter excluded, then furthest future expiry, else newest uploaded_at."""

    def test_multiple_docs_choose_furthest_future_expiry(self):
        today = date.today()
        d1 = {"document_id": "a", "expiry_date": (today + timedelta(days=100)).isoformat(), "uploaded_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()}
        d2 = {"document_id": "b", "expiry_date": (today + timedelta(days=400)).isoformat(), "uploaded_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()}
        d3 = {"document_id": "c", "expiry_date": (today + timedelta(days=200)).isoformat(), "uploaded_at": (datetime.now(timezone.utc)).isoformat()}
        picked = pick_evidence_document([d1, d2, d3], "gas_safety")
        assert picked is not None
        assert picked["document_id"] == "b"

    def test_filter_deleted_quarantined_malware_disabled(self):
        today = date.today()
        good = {"document_id": "g", "expiry_date": (today + timedelta(days=30)).isoformat()}
        deleted = {"document_id": "d", "deleted": True, "expiry_date": (today + timedelta(days=60)).isoformat()}
        quarantined = {"document_id": "q", "quarantined": True, "expiry_date": (today + timedelta(days=60)).isoformat()}
        disabled = {"document_id": "x", "status": "DISABLED", "expiry_date": (today + timedelta(days=60)).isoformat()}
        picked = pick_evidence_document([deleted, quarantined, disabled, good], "eicr")
        assert picked is not None
        assert picked["document_id"] == "g"

    def test_no_future_expiry_pick_newest_uploaded_at(self):
        today = date.today()
        old_upload = {"document_id": "old", "uploaded_at": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()}
        new_upload = {"document_id": "new", "uploaded_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}
        picked = pick_evidence_document([old_upload, new_upload], "epc")
        assert picked is not None
        assert picked["document_id"] == "new"

    def test_tie_break_updated_at_then_id(self):
        now = datetime.now(timezone.utc).isoformat()
        d1 = {"document_id": "1", "uploaded_at": now, "updated_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}
        d2 = {"document_id": "2", "uploaded_at": now, "updated_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()}
        picked = pick_evidence_document([d1, d2], "gas_safety")
        assert picked is not None
        assert picked["document_id"] == "1"


class TestComputeRequirementStatus:
    """compute_requirement_status: MISSING_EVIDENCE, NEEDS_REVIEW (missing expiry), EXPIRED, EXPIRING_SOON, VALID."""

    def test_no_doc_missing_evidence(self):
        result = compute_requirement_status(date.today(), None, True, 60)
        assert result["status"] == STATUS_MISSING_EVIDENCE
        assert REASON_NO_DOCUMENT_FOUND in result["reason_codes"]

    def test_expects_expiry_no_expiry_date_needs_review(self):
        doc = {"document_id": "x", "status": "VERIFIED"}
        result = compute_requirement_status(date.today(), doc, True, 60)
        assert result["status"] == STATUS_NEEDS_REVIEW
        assert REASON_MISSING_EXPIRY_DATE in result["reason_codes"]

    def test_expired_document(self):
        today = date.today()
        doc = {"document_id": "x", "expiry_date": (today - timedelta(days=10)).isoformat(), "status": "VERIFIED"}
        result = compute_requirement_status(today, doc, True, 60)
        assert result["status"] == STATUS_EXPIRED
        assert REASON_DOCUMENT_EXPIRED in result["reason_codes"]
        assert result["days_to_expiry"] == -10

    def test_expiring_within_60_days(self):
        today = date.today()
        doc = {"document_id": "x", "expiry_date": (today + timedelta(days=30)).isoformat(), "status": "VERIFIED"}
        result = compute_requirement_status(today, doc, True, 60)
        assert result["status"] == STATUS_EXPIRING_SOON
        assert REASON_DOCUMENT_EXPIRING_SOON in result["reason_codes"]
        assert result["days_to_expiry"] == 30

    def test_valid_future_expiry(self):
        today = date.today()
        doc = {"document_id": "x", "expiry_date": (today + timedelta(days=200)).isoformat(), "status": "VERIFIED"}
        result = compute_requirement_status(today, doc, True, 60)
        assert result["status"] == STATUS_VALID
        assert result["days_to_expiry"] == 200


class TestStatusToFraction:
    """Map status to fraction per task."""
    def test_fractions(self):
        assert STATUS_TO_FRACTION[STATUS_VALID] == 1.0
        assert STATUS_TO_FRACTION[STATUS_EXPIRING_SOON] == 0.8
        assert STATUS_TO_FRACTION[STATUS_NEEDS_REVIEW] == 0.5
        assert STATUS_TO_FRACTION[STATUS_EXPIRED] == 0.1
        assert STATUS_TO_FRACTION[STATUS_MISSING_EVIDENCE] == 0.0
