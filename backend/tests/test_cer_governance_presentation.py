import pytest

from services.cer_governance_presentation import (
    GF_PLATFORM_OPT,
    GF_PLATFORM_VER,
    GF_SELF,
    attach_cer_governance_presentation,
    derive_truth_presentation,
    resolve_governance_meta,
    stale_allowed_for_requirement,
)


def _smoke_incomplete():
    return {
        "requirement_type": "smoke_heat_alarms",
        "client_lifecycle_state": "ACTION_REQUIRED",
        "evidence_authority": {
            "state": "MISSING",
            "state_reason": "multi_evidence_components_incomplete",
            "primary_evidence_record_id": "cer_1",
        },
        "evidence_completeness": {"is_complete": False, "required_missing_count": 1},
    }


def _legionella_followup():
    return {
        "requirement_type": "legionella",
        "client_lifecycle_state": "ACTION_REQUIRED",
        "evidence_authority": {
            "state": "UPLOADED_UNCONFIRMED",
            "state_reason": "external_assessment_remediation_or_followup_unresolved",
            "semantic_state": "ASSESSMENT_FOLLOWUP_REQUIRED",
            "primary_evidence_record_id": "cer_2",
        },
    }


def _gas_pending():
    return {
        "requirement_type": "gas_safety",
        "workflow_class": "DOCUMENT_UPLOAD",
        "client_lifecycle_state": "PENDING_REVIEW",
        "evidence_authority": {"state": "PENDING_ADMIN_REVIEW"},
    }


def test_smoke_incomplete_truth_label():
    fields = attach_cer_governance_presentation(_smoke_incomplete())
    assert fields["governance_family"] == GF_SELF
    assert fields["truth_presentation_label"] == "Additional action still required"
    assert fields["review_owner"] is None
    assert fields["queue_backed_review"] is False


def test_legionella_followup_not_generic_review():
    fields = attach_cer_governance_presentation(_legionella_followup())
    assert fields["governance_family"] == GF_PLATFORM_OPT
    assert fields["truth_presentation_label"] == "Follow-up evidence required"
    assert fields["review_owner"] is None
    assert fields["queue_backed_review"] is False


def test_gas_platform_verification_pending():
    fields = attach_cer_governance_presentation(_gas_pending())
    assert fields["governance_family"] == GF_PLATFORM_VER
    assert fields["truth_presentation_label"] == "Platform verification pending"
    assert fields["review_owner"] == "platform_admin"
    assert fields["queue_backed_review"] is True


def test_right_to_rent_self_recorded_not_org_queue():
    row = {
        "requirement_type": "right_to_rent",
        "client_lifecycle_state": "SATISFIED_UNVERIFIED",
        "evidence_authority": {
            "state": "UPLOADED_UNCONFIRMED",
            "primary_evidence_record_id": "cer_org",
            "non_document_verification_status": "PENDING_REVIEW",
        },
    }
    fields = attach_cer_governance_presentation(row)
    assert fields["governance_family"] == GF_SELF
    assert fields["truth_presentation_label"] == "Recorded on file"
    assert fields["review_owner"] is None
    assert fields["queue_backed_review"] is False
    assert fields["assurance_tier"] == "SELF_RECORDED"


def test_stale_not_allowed_without_review_owner():
    row = attach_cer_governance_presentation(_smoke_incomplete())
    merged = {**_smoke_incomplete(), **row}
    assert stale_allowed_for_requirement(merged) is True


def test_stale_not_allowed_declaration_recorded():
    row = {
        "requirement_type": "how_to_rent",
        "client_lifecycle_state": "SATISFIED_UNVERIFIED",
        "evidence_authority": {"state": "UPLOADED_UNCONFIRMED", "primary_evidence_record_id": "cer_3"},
    }
    fields = attach_cer_governance_presentation(row)
    merged = {**row, **fields}
    assert fields["truth_presentation_label"] == "Recorded on file"
    assert stale_allowed_for_requirement(merged) is False
