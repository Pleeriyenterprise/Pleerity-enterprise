"""Canonical document operational state derivation."""
from services.document_operational_state import (
    DocumentOperationalState,
    attach_document_operational_projection,
    derive_document_operational_state,
    document_needs_extraction_reconciliation,
    is_match_resolved_pending_verification,
)


def test_verified_doc_operational_state_accepted_on_file():
    doc = {
        "status": "VERIFIED",
        "evidence_review_state": "ACCEPTED_UNVERIFIED",
        "assurance_tier": "HUMAN_ACCEPTED",
        "extraction_status": "CONFIRMED",
        "extraction_confirmation_superseded": True,
        "ai_extraction": {"review_status": "approved", "status": "completed", "data": {"x": 1}},
    }
    out = derive_document_operational_state(doc)
    assert out["document_operational_state"] == DocumentOperationalState.EVIDENCE_ACCEPTED_ON_FILE.value
    assert "EXTRACTION_CONFIRMATION_SUPERSEDED" in out["document_operational_reason_codes"]


def test_extraction_pending_without_admin_decision():
    doc = {
        "status": "UPLOADED",
        "evidence_review_state": "UPLOADED",
        "extraction_status": "NEEDS_REVIEW",
        "ai_extraction": {"status": "completed", "review_status": "PENDING", "data": {"a": 1}},
    }
    out = derive_document_operational_state(doc)
    assert out["document_operational_state"] == DocumentOperationalState.EXTRACTION_CONFIRMATION_PENDING.value


def test_match_resolved_pending_verification_distinct_from_verify():
    doc = {
        "status": "UPLOADED",
        "evidence_review_state": "UPLOADED",
        "requirement_id": "r1",
        "reviewed_match_outcome": "MATCH_CONFIRMED",
        "requirement_evidence_mismatch": False,
    }
    assert is_match_resolved_pending_verification(doc) is True
    out = derive_document_operational_state(doc)
    assert out["document_operational_state"] == DocumentOperationalState.MATCH_RESOLVED_VERIFICATION_PENDING.value
    assert "MATCH_RESOLVED_NOT_VERIFIED" in out["document_operational_reason_codes"]


def test_historical_verified_needs_reconciliation():
    doc = {
        "status": "VERIFIED",
        "evidence_review_state": "ACCEPTED_UNVERIFIED",
        "assurance_tier": "HUMAN_ACCEPTED",
        "extraction_status": "NEEDS_REVIEW",
        "ai_extraction": {"status": "completed", "review_status": "PENDING", "data": {"x": 1}},
    }
    assert document_needs_extraction_reconciliation(doc) is True


def test_reconciled_aligned_skips_reconciliation():
    doc = {
        "status": "VERIFIED",
        "evidence_review_state": "ACCEPTED_UNVERIFIED",
        "extraction_status": "CONFIRMED",
        "extraction_confirmation_superseded": True,
        "ai_extraction": {"review_status": "approved", "superseded_by_admin_decision": "accepted"},
    }
    assert document_needs_extraction_reconciliation(doc) is False


def test_attach_projection_mutates_doc():
    doc = {"status": "REJECTED", "evidence_review_state": "REJECTED"}
    attach_document_operational_projection(doc)
    assert doc["document_operational_state"] == DocumentOperationalState.EVIDENCE_REJECTED.value
    assert doc["document_operational_label"]
