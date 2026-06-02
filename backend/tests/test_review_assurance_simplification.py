"""REVIEW-ASSURANCE-SIMPLIFICATION-01 regression tests."""
from __future__ import annotations

from services.cer_governance_presentation import (
    ASSURANCE_SELF_RECORDED,
    GF_SELF,
    attach_cer_governance_presentation,
)
from services.review_queue_service import matches_org_review_queue


def test_org_queue_match_always_false():
    row = {
        "governance_family": "ORG_ADMIN_REVIEWED",
        "queue_backed_review": True,
        "review_owner": "org_admin",
    }
    assert matches_org_review_queue(row) is False


def test_landlord_registration_self_recorded_assurance():
    row = {
        "requirement_type": "landlord_registration_ni",
        "client_lifecycle_state": "SATISFIED_UNVERIFIED",
        "evidence_authority": {
            "state": "UPLOADED_UNCONFIRMED",
            "primary_evidence_record_id": "cer_lr",
        },
    }
    fields = attach_cer_governance_presentation(row)
    assert fields["governance_family"] == GF_SELF
    assert fields["assurance_tier"] == ASSURANCE_SELF_RECORDED
    assert "org_verification" not in str(fields.get("truth_presentation_stage") or "")
