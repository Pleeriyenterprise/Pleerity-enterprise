import pytest

from services.cer_governance_presentation import GF_ORG, attach_cer_governance_presentation
from services.review_queue_service import (
    audit_orphan_queue_states,
    build_queue_row_payload,
    matches_escalation_queue,
    matches_org_review_queue,
)


def _org_pending():
    return {
        "requirement_type": "right_to_rent",
        "client_lifecycle_state": "SATISFIED_UNVERIFIED",
        "evidence_authority": {
            "state": "UPLOADED_UNCONFIRMED",
            "primary_evidence_record_id": "cer_org_1",
            "non_document_verification_status": "PENDING_REVIEW",
            "pending_non_document_evidence_count": 1,
        },
    }


def test_org_review_pending_governance_fields():
    fields = attach_cer_governance_presentation(_org_pending())
    assert fields["governance_family"] == GF_ORG
    assert fields["truth_presentation_label"] == "Organisation review pending"
    assert fields["review_owner"] == "org_admin"
    assert fields["queue_backed_review"] is True
    assert fields["truth_presentation_stage"] == "org_verification_pending"


def test_org_queue_inclusion_requires_governance_invariant():
    row = {**_org_pending(), **attach_cer_governance_presentation(_org_pending())}
    assert matches_org_review_queue(row) is True


def test_self_certified_not_in_org_queue():
    row = {
        "governance_family": "SELF_CERTIFIED",
        "queue_backed_review": False,
        "review_owner": None,
    }
    assert matches_org_review_queue(row) is False


def test_escalation_queue_inclusion():
    row = {
        "governance_family": "PLATFORM_OVERSIGHT_OPTIONAL",
        "queue_backed_review": True,
        "review_owner": "platform_admin_escalation",
        "truth_presentation_stage": "escalation_review",
    }
    assert matches_escalation_queue(row) is True


def test_orphan_queue_state_detection():
    orphans = audit_orphan_queue_states(
        [
            {"requirement_id": "a", "queue_backed_review": True, "review_owner": None},
            {"requirement_id": "b", "queue_backed_review": False, "review_owner": "org_admin"},
        ]
    )
    assert len(orphans) == 2


def test_queue_row_payload_deeplink():
    req = {
        "requirement_id": "rid",
        "property_id": "pid",
        "requirement_type": "right_to_rent",
        "truth_presentation_label": "Organisation review pending",
        "governance_family": GF_ORG,
        "review_owner": "org_admin",
        "queue_backed_review": True,
    }
    payload = build_queue_row_payload(req, property_label="Test Property", cer_record={"evidence_record_id": "cer_x"})
    assert payload["review_deeplink"] == "/properties/pid?resolve_requirement=rid"
    assert payload["evidence_record_id"] == "cer_x"
