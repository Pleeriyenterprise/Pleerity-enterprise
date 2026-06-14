"""EVIDENCE-AUTHORITY-CONVERGENCE-FIX-01 regression tests."""
from __future__ import annotations

import pytest

from services.cer_governance_presentation import derive_truth_presentation, resolve_governance_meta
from services.compliance_evidence_record_service import (
    EVIDENCE_MODE_DOCUMENT_UPLOAD,
    EVIDENCE_MODE_STRUCTURED_DECLARATION,
    VERIFICATION_PENDING,
    VERIFICATION_VERIFIED,
    non_document_record_satisfies_policy,
)
from services.operational_cognition_service import build_envelope_for_requirement
from services.requirement_evidence_authority import EA_VERIFIED_CURRENT


def test_platform_opt_pending_structured_declaration_satisfies_policy():
    req = {
        "requirement_code": "legionella",
        "requirement_type": "legionella",
        "registry_metadata": {
            "evidence_resolution": {
                "allowed_evidence_modes": ["STRUCTURED_DECLARATION"],
            }
        },
    }
    rec = {
        "evidence_mode": EVIDENCE_MODE_STRUCTURED_DECLARATION,
        "verification_status": VERIFICATION_PENDING,
        "evidence_confidence_level": "MEDIUM",
    }
    policy = {"allowed_evidence_modes": ["STRUCTURED_DECLARATION"], "allow_medium_non_document_satisfaction": True}
    assert non_document_record_satisfies_policy(
        record=rec,
        requirement=req,
        policy=policy,
        is_critical_obligation=True,
    )


def test_verified_authority_cognition_suppresses_uploaded_not_verified():
    req = {
        "requirement_id": "r-fra",
        "property_id": "p-1",
        "client_lifecycle_state": "ACTION_REQUIRED",
        "truth_presentation_stage": "verified",
        "truth_presentation_label": "Verified",
        "evidence_authority": {"state": "VERIFIED_CURRENT", "state_reason": "verified_no_expiry_on_file"},
        "take_action": {"primary": {"label": "Add compliance evidence", "intent": "upload"}},
        "evidence_completeness": {"required_missing_count": 0},
    }
    env = build_envelope_for_requirement(req)
    assert env["operational_truth_flags"]["uploaded_not_verified"] is False
    assert env["operational_truth_flags"]["submitted_not_compliant"] is False
    assert env["primary_action"]["label"] == "View evidence"
    assert env["user_safe_summary"] == "No further evidence required"


def test_legionella_style_assessment_cognition_after_authority_promotion():
    req = {
        "requirement_id": "r-leg",
        "property_id": "p-1",
        "requirement_code": "legionella",
        "requirement_type": "legionella",
        "client_lifecycle_state": "SATISFIED_UNVERIFIED",
        "truth_presentation_stage": "assessment_recorded",
        "truth_presentation_label": "Assessment recorded",
        "requirement_satisfied": True,
        "evidence_authority": {
            "state": EA_VERIFIED_CURRENT,
            "state_reason": "verified_non_document_evidence",
            "primary_evidence_record_id": "cer-leg-1",
        },
        "take_action": {"primary": {"label": "Record Legionella risk assessment", "intent": "guided_evidence_resolution"}},
        "evidence_completeness": {"required_missing_count": 0},
    }
    env = build_envelope_for_requirement(req)
    assert env["operational_truth_flags"]["uploaded_not_verified"] is False
    assert env["primary_action"]["label"] == "View evidence"


def test_expiry_semantics_truth_presentation_not_platform_review():
    req = {
        "requirement_id": "r-epc",
        "evidence_authority": {
            "state": "UPLOADED_UNCONFIRMED",
            "state_reason": "document_upload_missing_required_expiry_semantics",
        },
        "client_lifecycle_state": "ACTION_REQUIRED",
        "governance_family": "PLATFORM_VERIFIED",
    }
    meta = resolve_governance_meta(req)
    truth = derive_truth_presentation(req, meta)
    assert truth["truth_presentation_stage"] == "expiry_confirmation_required"
    assert truth["truth_presentation_label"] == "Expiry date needed"
    assert truth.get("queue_backed_review") is not True


def test_expiry_semantics_cognition_no_fake_upload_warning():
    req = {
        "requirement_id": "r-epc",
        "property_id": "p-1",
        "truth_presentation_stage": "expiry_confirmation_required",
        "truth_presentation_label": "Expiry date needed",
        "truth_presentation_subline": "Add expiry date information so this certificate can count as fully valid.",
        "client_lifecycle_state": "ACTION_REQUIRED",
        "evidence_authority": {
            "state": "UPLOADED_UNCONFIRMED",
            "state_reason": "document_upload_missing_required_expiry_semantics",
        },
        "take_action": {"primary": {"label": "Upload valid EPC document", "intent": "upload"}},
        "evidence_completeness": {"required_missing_count": 0},
        "queue_backed_review": False,
    }
    env = build_envelope_for_requirement(req)
    assert env["operational_truth_flags"]["uploaded_not_verified"] is False
    assert env["primary_action"]["label"] == "Expiry date needed"


def test_gas_safety_verified_control_path():
    req = {
        "requirement_id": "r-gas",
        "property_id": "p-1",
        "client_lifecycle_state": "VERIFIED",
        "truth_presentation_stage": "verified",
        "truth_presentation_label": "Verified",
        "evidence_authority": {"state": "VERIFIED_CURRENT", "effective_verified_document_id": "doc-1"},
        "take_action": {"primary": {"label": "Upload valid gas safety certificate", "intent": "upload"}},
        "evidence_completeness": {"required_missing_count": 0},
    }
    env = build_envelope_for_requirement(req)
    assert env["primary_action"]["label"] == "View evidence"
    assert env["operational_truth_flags"]["uploaded_not_verified"] is False


@pytest.mark.asyncio
async def test_link_verified_document_creates_verified_cer():
    from unittest.mock import AsyncMock, MagicMock

    from services.compliance_evidence_record_service import upsert_document_upload_evidence_for_linked_document

    coll = MagicMock()
    coll.find_one = AsyncMock(return_value=None)
    coll.insert_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.compliance_evidence_records = coll
    mock_db.requirements = MagicMock()
    mock_db.requirements.find_one = AsyncMock(
        return_value={"requirement_id": "req-1", "client_id": "c-1", "property_id": "p-1"},
    )
    mock_db.documents = MagicMock()
    mock_db.documents.find_one = AsyncMock(
        return_value={
            "document_id": "doc-verified-link",
            "status": "VERIFIED",
            "evidence_review_state": "ACCEPTED_UNVERIFIED",
            "verified_at": "2026-06-01T00:00:00+00:00",
        }
    )

    out = await upsert_document_upload_evidence_for_linked_document(
        mock_db,
        client_id="c-1",
        property_id="p-1",
        requirement_id="req-1",
        document_id="doc-verified-link",
        actor_user_id="user-1",
    )
    assert out is not None
    assert out["verification_status"] == VERIFICATION_VERIFIED
    assert out["verified_at"] is not None
