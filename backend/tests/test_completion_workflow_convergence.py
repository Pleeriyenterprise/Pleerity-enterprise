"""Tests for completion proof workflow convergence."""
from __future__ import annotations

import pytest

from services.completion_workflow_transition_service import (
    generate_completion_review_actions,
    generate_contractor_post_proof_actions,
    is_awaiting_completion_review,
    maybe_apply_proof_upload_transition_fields,
    post_execution_visit_controls_locked,
    suppress_invalid_post_completion_actions,
)
from services.invoice_readiness_service import (
    INVOICE_READINESS_PENDING_REVIEW,
    INVOICE_READINESS_READY,
    evaluate_invoice_readiness,
)
from services.work_order_execution_constants import (
    COMPLETION_REVIEW_ACCEPTED,
    COMPLETION_REVIEW_PENDING,
    OPERATIONAL_STATUS_WORK_COMPLETED_PENDING_REVIEW,
)


def _scheduled_with_proof(**overrides):
    wo = {
        "work_order_id": "wo-cp-1",
        "work_order_kind": "COMPLIANCE",
        "status": "SCHEDULED",
        "contractor_id": "c-1",
        "schedule_status": "confirmed",
        "scheduled_at": "2026-06-30T19:56:00Z",
        "pricing_mode": "COMPLIANCE_FIXED_QUOTE",
        "price_status": "APPROVED",
        "evidence_keys": ["client/c/ev/file.pdf"],
        "compliance_proof_status": "SUBMITTED",
    }
    wo.update(overrides)
    return wo


def test_proof_upload_advances_status_from_scheduled():
    prev = _scheduled_with_proof(evidence_keys=[])
    after = _scheduled_with_proof()
    fields = maybe_apply_proof_upload_transition_fields(after, prev=prev)
    assert fields.get("status") == "COMPLETED"
    assert fields.get("operational_status") == OPERATIONAL_STATUS_WORK_COMPLETED_PENDING_REVIEW
    assert fields.get("completion_review_status") == COMPLETION_REVIEW_PENDING
    assert fields.get("visit_controls_locked") is True
    assert fields.get("schedule_status") == "completed"


def test_awaiting_review_suppresses_visit_actions():
    wo = _scheduled_with_proof(
        status="COMPLETED",
        operational_status=OPERATIONAL_STATUS_WORK_COMPLETED_PENDING_REVIEW,
        completion_review_status=COMPLETION_REVIEW_PENDING,
    )
    actions = [
        {"id": "mark_no_access", "label": "Mark no access"},
        {"id": "accept_completion", "label": "Accept completion"},
    ]
    filtered = suppress_invalid_post_completion_actions(actions, wo)
    assert not any(a["id"] == "mark_no_access" for a in filtered)


def test_landlord_review_actions_not_quote():
    wo = _scheduled_with_proof(
        status="COMPLETED",
        operational_status=OPERATIONAL_STATUS_WORK_COMPLETED_PENDING_REVIEW,
        completion_review_status=COMPLETION_REVIEW_PENDING,
    )
    actions = generate_completion_review_actions(wo)
    ids = {a["id"] for a in actions}
    assert "accept_completion" in ids
    assert "approve_quote" not in ids


def test_contractor_post_proof_message():
    wo = _scheduled_with_proof(
        status="COMPLETED",
        operational_status=OPERATIONAL_STATUS_WORK_COMPLETED_PENDING_REVIEW,
    )
    actions = generate_contractor_post_proof_actions(wo)
    assert actions[0]["label"] == "Completion proof submitted"
    assert "awaiting review" in actions[0]["hint"].lower()


def test_invoice_pending_review_until_accepted():
    wo = _scheduled_with_proof(
        status="COMPLETED",
        operational_status=OPERATIONAL_STATUS_WORK_COMPLETED_PENDING_REVIEW,
        completion_review_status=COMPLETION_REVIEW_PENDING,
    )
    readiness = evaluate_invoice_readiness(wo)
    assert readiness["state"] == INVOICE_READINESS_PENDING_REVIEW
    assert readiness["may_submit_invoice"] is False

    wo["completion_review_status"] = COMPLETION_REVIEW_ACCEPTED
    wo["operational_status"] = None
    readiness2 = evaluate_invoice_readiness(wo)
    assert readiness2["state"] == INVOICE_READINESS_READY
    assert readiness2["may_submit_invoice"] is True


def test_visit_controls_locked_after_proof():
    wo = _scheduled_with_proof(status="COMPLETED", visit_controls_locked=True)
    assert post_execution_visit_controls_locked(wo) is True


def test_is_awaiting_completion_review():
    wo = _scheduled_with_proof(
        status="COMPLETED",
        operational_status=OPERATIONAL_STATUS_WORK_COMPLETED_PENDING_REVIEW,
    )
    assert is_awaiting_completion_review(wo) is True
