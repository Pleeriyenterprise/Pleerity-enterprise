import pytest

from services.cer_governance_presentation import attach_cer_governance_presentation
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


def test_org_queue_inclusion_removed():
    row = {**_org_pending(), **attach_cer_governance_presentation(_org_pending())}
    assert matches_org_review_queue(row) is False


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


def test_orphan_stale_org_owner_detected():
    orphans = audit_orphan_queue_states(
        [
            {"requirement_id": "a", "queue_backed_review": True, "review_owner": None},
            {"requirement_id": "b", "review_owner": "org_admin", "queue_backed_review": False},
        ]
    )
    issues = {o["issue"] for o in orphans}
    assert "queue_backed_without_owner" in issues
    assert "stale_org_review_owner" in issues


def test_queue_row_payload_deeplink():
    req = {
        "requirement_id": "rid",
        "property_id": "pid",
        "requirement_type": "right_to_rent",
        "truth_presentation_label": "Recorded on file",
        "governance_family": "SELF_CERTIFIED",
        "review_owner": None,
        "queue_backed_review": False,
    }
    payload = build_queue_row_payload(req, property_label="Test Property", cer_record={"evidence_record_id": "cer_x"})
    assert payload["review_deeplink"] == "/properties/pid?resolve_requirement=rid"
    assert payload["evidence_record_id"] == "cer_x"
