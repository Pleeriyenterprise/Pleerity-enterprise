"""Property RAG convergence — operational attention only."""
from __future__ import annotations

from services.property_compliance_status_service import compute_property_compliance_rag


def test_satisfied_portfolio_is_green():
    rows = [
        {
            "status": "PENDING",
            "truth_presentation_stage": "verified",
            "evidence_authority_synced_at": "2026-01-01",
            "evidence_authority": {"version": 1, "state": "VERIFIED_CURRENT", "effective_expiry_date": "2027-01-01"},
        },
        {
            "status": "PENDING",
            "truth_presentation_stage": "recorded_on_file",
            "semantic_state": "DECLARATION_RECORDED",
        },
    ]
    assert compute_property_compliance_rag(rows) == "GREEN"


def test_assurance_review_pending_on_satisfied_file_is_green():
    rows = [
        {
            "status": "PENDING",
            "truth_presentation_stage": "recorded_on_file",
            "semantic_state": "EVIDENCE_ACCEPTED",
            "evidence_authority_synced_at": "2026-01-01",
            "evidence_authority": {"version": 1, "state": "PENDING_ADMIN_REVIEW"},
        },
    ]
    assert compute_property_compliance_rag(rows) == "GREEN"


def test_missing_evidence_is_amber():
    rows = [
        {
            "status": "PENDING",
            "truth_presentation_stage": "collect_evidence",
            "take_action": {"primary": {"label": "Upload", "route": "/documents"}},
        },
    ]
    assert compute_property_compliance_rag(rows) == "AMBER"
