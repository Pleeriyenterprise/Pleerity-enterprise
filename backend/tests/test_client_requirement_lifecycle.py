"""Unit tests for client requirement lifecycle derivation."""

from services.client_requirement_lifecycle import (
    ACTION_REQUIRED,
    NOT_APPLICABLE,
    PENDING_REVIEW,
    SATISFIED_UNVERIFIED,
    VERIFIED,
    derive_client_lifecycle_fields,
)
from services.requirement_evidence_authority import (
    EA_EXTRACTION_PENDING_CONFIRMATION,
    EA_MISSING,
    EA_PENDING_ADMIN_REVIEW,
    EA_UPLOADED_UNCONFIRMED,
    EA_VERIFIED_CURRENT,
)


def _base_row(**kwargs):
    r = {
        "requirement_id": "r1",
        "property_id": "p1",
        "applicability": "REQUIRED",
        "status": "PENDING",
        "evidence_state": "MISSING",
        "evidence_authority": {"version": 1, "state": EA_MISSING},
    }
    r.update(kwargs)
    return r


def test_not_applicable_applicability():
    out = derive_client_lifecycle_fields(_base_row(applicability="NOT_REQUIRED", status="PENDING"))
    assert out["client_lifecycle_state"] == NOT_APPLICABLE


def test_pending_review_admin_authority():
    out = derive_client_lifecycle_fields(
        _base_row(
            status="PENDING",
            evidence_state="UPLOADED_UNVERIFIED",
            evidence_authority={"state": EA_PENDING_ADMIN_REVIEW, "state_reason": "uploaded_pending_admin"},
        )
    )
    assert out["client_lifecycle_state"] == PENDING_REVIEW
    assert "review" in out["client_lifecycle_label"].lower()


def test_verified_current():
    out = derive_client_lifecycle_fields(
        _base_row(
            status="COMPLIANT",
            evidence_state="VERIFIED",
            evidence_authority={"state": EA_VERIFIED_CURRENT},
        )
    )
    assert out["client_lifecycle_state"] == VERIFIED


def test_satisfied_unverified_uploaded_unconfirmed():
    out = derive_client_lifecycle_fields(
        _base_row(
            status="PENDING",
            evidence_state="UPLOADED_UNVERIFIED",
            evidence_authority={"state": EA_UPLOADED_UNCONFIRMED},
            evidence_doc_id="d1",
        )
    )
    assert out["client_lifecycle_state"] == SATISFIED_UNVERIFIED


def test_action_required_extraction_pending():
    out = derive_client_lifecycle_fields(
        _base_row(
            status="PENDING",
            evidence_state="AWAITING_USER_CONFIRM",
            evidence_authority={"state": EA_EXTRACTION_PENDING_CONFIRMATION},
        )
    )
    assert out["client_lifecycle_state"] == ACTION_REQUIRED


def test_stale_overdue_deferred_for_non_document_assessment():
    out = derive_client_lifecycle_fields(
        _base_row(
            status="OVERDUE",
            due_date="2026-05-16T00:00:00+00:00",
            evidence_authority={
                "version": 1,
                "state": EA_UPLOADED_UNCONFIRMED,
                "primary_evidence_record_id": "cer1",
            },
            semantic_state="DECLARATION_RECORDED",
            governance_family="PLATFORM_OVERSIGHT_OPTIONAL",
        )
    )
    assert out["client_lifecycle_state"] == SATISFIED_UNVERIFIED


def test_v2_review_pending_linked_doc(monkeypatch):
    monkeypatch.setattr(
        "services.client_requirement_lifecycle.is_feature_evidence_review_v2",
        lambda: True,
    )
    doc = {"document_id": "d1", "evidence_review_state": "UNDER_REVIEW", "review_required": True}
    out = derive_client_lifecycle_fields(
        _base_row(
            status="PENDING",
            evidence_state="UPLOADED_UNVERIFIED",
            evidence_authority={"state": EA_UPLOADED_UNCONFIRMED},
            evidence_doc_id="d1",
        ),
        linked_primary_document=doc,
    )
    assert out["client_lifecycle_state"] == PENDING_REVIEW
