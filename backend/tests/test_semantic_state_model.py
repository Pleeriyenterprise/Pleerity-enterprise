from __future__ import annotations

from services.semantic_state_model import (
    ASSESSMENT_FOLLOWUP_REQUIRED,
    DECLARATION_RECORDED,
    EXPIRY_REVIEW_REQUIRED,
    NOT_REQUIRED,
    PARTIALLY_COMPLETE,
    VERIFIED_CURRENT,
    VERIFIED_EXPIRED,
    derive_semantic_state,
    semantic_state_to_legacy_evidence_state,
    semantic_state_to_legacy_status,
    semantic_state_to_scoring_projection,
)


def test_semantic_state_reason_derivation_for_known_hardened_outcomes():
    assert derive_semantic_state(authority_state="UPLOADED_UNCONFIRMED", state_reason="multi_evidence_components_incomplete") == PARTIALLY_COMPLETE
    assert derive_semantic_state(authority_state="UPLOADED_UNCONFIRMED", state_reason="guided_declaration_not_independently_verified") == DECLARATION_RECORDED
    assert derive_semantic_state(authority_state="UPLOADED_UNCONFIRMED", state_reason="external_assessment_remediation_or_followup_unresolved") == ASSESSMENT_FOLLOWUP_REQUIRED
    assert derive_semantic_state(authority_state="UPLOADED_UNCONFIRMED", state_reason="document_upload_missing_required_expiry_semantics") == EXPIRY_REVIEW_REQUIRED


def test_semantic_state_legacy_mirror_mapping_is_safe():
    assert semantic_state_to_legacy_status(VERIFIED_CURRENT) == "COMPLIANT"
    assert semantic_state_to_legacy_status(VERIFIED_EXPIRED) == "OVERDUE"
    assert semantic_state_to_legacy_status(PARTIALLY_COMPLETE) == "PENDING"
    assert semantic_state_to_legacy_status(DECLARATION_RECORDED) == "PENDING"
    assert semantic_state_to_legacy_status(NOT_REQUIRED) == "NOT_REQUIRED"

    assert semantic_state_to_legacy_evidence_state(VERIFIED_CURRENT) == "VERIFIED_CURRENT"
    assert semantic_state_to_legacy_evidence_state(VERIFIED_EXPIRED) == "VERIFIED_EXPIRED"
    assert semantic_state_to_legacy_evidence_state(PARTIALLY_COMPLETE) == "UPLOADED_UNCONFIRMED"


def test_scoring_projection_mapping_is_compatibility_only():
    out = semantic_state_to_scoring_projection(ASSESSMENT_FOLLOWUP_REQUIRED)
    assert out == {"legacy_status": "PENDING", "legacy_evidence_state": "UPLOADED_UNCONFIRMED"}
