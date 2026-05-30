"""
Traceability: maintenance COMPLIANCE work orders share serialize_client_job / next_job_actions with
compliance jobs, but maintenance-specific branches live in compliance_workflow_service.

These tests lock canonical status, next_actions shape, proof/completion rules, and issue hints for
MAINTENANCE work_order_kind. See also: test_document_verify_compliance_http.py (compliance proof path).
"""
from __future__ import annotations

import pytest

from services import maintenance_service as ms
from services.compliance_workflow_service import (
    derive_canonical_job_status,
    maintenance_has_completion_evidence,
    maintenance_issue_resolution_hint,
    next_job_actions,
    serialize_client_job,
    work_order_has_proof_document,
)
from services.work_order_execution_constants import WORK_ORDER_KIND_COMPLIANCE


def _ids(actions):
    return [a["id"] for a in actions]


def _base_maintenance(**kwargs):
    row = {
        "work_order_id": "wo-m-1",
        "client_id": "cli-1",
        "property_id": "prop-1",
        "work_order_kind": ms.WORK_ORDER_KIND_MAINTENANCE,
        "description": "Fix leak",
        "contractor_id": "ctr-1",
        "schedule_status": "confirmed",
        "scheduled_at": "2026-03-01T10:00:00+00:00",
        "scheduled_timezone": "Europe/London",
        "scheduled_by": "client",
        "evidence_keys": [],
    }
    row.update(kwargs)
    return row


@pytest.mark.parametrize(
    "operational_exception,expected_canonical",
    [
        ("NO_ACCESS", "NO_ACCESS"),
        ("RESCHEDULE_REQUIRED", "RESCHEDULE_REQUIRED"),
        ("FOLLOW_UP_REQUIRED", "FOLLOW_UP_REQUIRED"),
    ],
)
def test_maintenance_operational_exception_canonical_status(operational_exception, expected_canonical):
    wo = _base_maintenance(status=ms.STATUS_ASSIGNED, operational_exception=operational_exception)
    assert derive_canonical_job_status(wo) == expected_canonical
    ids = _ids(next_job_actions(wo))
    assert "clear_operational_exception" in ids
    assert "propose_schedule" in ids
    assert "start" not in ids
    assert "complete" not in ids
    assert "verify" not in ids
    assert "link_document" not in ids


def test_maintenance_in_progress_plus_follow_up_hold_prefers_exception_canonical():
    """Operational exception is evaluated before raw IN_PROGRESS (derive_canonical_job_status order)."""
    wo = _base_maintenance(
        status=ms.STATUS_IN_PROGRESS,
        operational_exception=ms.OPERATIONAL_EXCEPTION_FOLLOW_UP_REQUIRED,
    )
    assert derive_canonical_job_status(wo) == "FOLLOW_UP_REQUIRED"
    ids = _ids(next_job_actions(wo))
    assert "clear_operational_exception" in ids
    assert "complete" not in ids


def test_maintenance_awaiting_parts_canonical_and_actions():
    wo = _base_maintenance(status=ms.STATUS_AWAITING_PARTS)
    assert derive_canonical_job_status(wo) == "AWAITING_PARTS"
    ids = _ids(next_job_actions(wo))
    assert ids == ["resume_after_parts", "complete"]
    ser = serialize_client_job(wo)
    assert ser["job_status"] == "AWAITING_PARTS"
    assert not (wo.get("completed_at")), "fixture should not imply completion while awaiting parts"


def test_maintenance_in_progress_offers_awaiting_parts_and_complete():
    wo = _base_maintenance(status=ms.STATUS_IN_PROGRESS)
    assert derive_canonical_job_status(wo) == "IN_PROGRESS"
    ids = _ids(next_job_actions(wo))
    assert "awaiting_parts" in ids
    assert "complete" in ids
    assert ids.index("awaiting_parts") < ids.index("complete")


def test_maintenance_completed_without_evidence_requires_attach_proof():
    wo = _base_maintenance(status=ms.STATUS_COMPLETED, issue_id="iss-1")
    assert not maintenance_has_completion_evidence(wo)
    ids = _ids(next_job_actions(wo))
    assert "attach_completion_proof" in ids
    assert "close_job" not in ids
    assert "verify" not in ids
    assert "link_document" not in ids


def test_maintenance_completed_with_evidence_offers_close_job():
    wo = _base_maintenance(status=ms.STATUS_COMPLETED, issue_id="iss-1", evidence_keys=["document:doc-1"])
    assert maintenance_has_completion_evidence(wo)
    ids = _ids(next_job_actions(wo))
    assert "close_job" in ids
    assert "attach_completion_proof" not in ids


def test_maintenance_terminal_and_cancelled_next_actions():
    wo_closed = _base_maintenance(status=ms.STATUS_CLOSED)
    assert derive_canonical_job_status(wo_closed) == "CLOSED"
    assert all(a["id"] == "none" for a in next_job_actions(wo_closed))

    wo_cancelled = _base_maintenance(status=ms.STATUS_CANCELLED)
    assert derive_canonical_job_status(wo_cancelled) == "CANCELLED"
    assert all(a["id"] == "none" for a in next_job_actions(wo_cancelled))

    wo_verified = _base_maintenance(status=ms.STATUS_VERIFIED)
    assert derive_canonical_job_status(wo_verified) == "VERIFIED"
    ids = _ids(next_job_actions(wo_verified))
    assert ids == ["close_job"]


def test_maintenance_completed_serialized_includes_issue_resolution_hint_when_linked_issue():
    wo = _base_maintenance(status=ms.STATUS_COMPLETED, issue_id="iss-99")
    hint = maintenance_issue_resolution_hint(wo)
    assert hint and "issue" in hint.lower()
    body = serialize_client_job(wo)
    assert body.get("issue_resolution_hint") == hint


def test_maintenance_verified_issue_resolution_hint():
    wo = _base_maintenance(status=ms.STATUS_VERIFIED, issue_id="iss-99")
    hint = maintenance_issue_resolution_hint(wo)
    assert hint and "closed" in hint.lower()


def test_maintenance_contractor_proposed_visit_offers_confirm_and_request_reschedule():
    wo = _base_maintenance(
        status=ms.STATUS_SCHEDULED,
        schedule_status="proposed",
        scheduled_by="contractor",
        price_status="APPROVED",
        pricing_mode="MAINTENANCE_PREQUOTE",
    )
    ids = _ids(next_job_actions(wo))
    assert "confirm_visit" in ids
    assert "request_visit_reschedule" in ids
    assert "cancel_booking" in ids
    assert ids.index("confirm_visit") < ids.index("request_visit_reschedule")


def test_maintenance_confirmed_visit_offers_request_reschedule():
    wo = _base_maintenance(status=ms.STATUS_SCHEDULED, schedule_status="confirmed", price_status="APPROVED")
    ids = _ids(next_job_actions(wo))
    assert "request_visit_reschedule" in ids
    assert "start" in ids


def test_compliance_completed_without_proof_requests_link_not_verify():
    wo = {
        "work_order_id": "wo-c-1",
        "client_id": "cli-1",
        "property_id": "prop-1",
        "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
        "status": ms.STATUS_COMPLETED,
        "linked_property_requirement_id": "lpr-1",
        "evidence_keys": [],
    }
    ids = _ids(next_job_actions(wo))
    assert "link_document" in ids
    assert "verify" not in ids


def test_compliance_completed_with_proof_allows_verify():
    wo = {
        "work_order_id": "wo-c-2",
        "client_id": "cli-1",
        "property_id": "prop-1",
        "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
        "status": ms.STATUS_COMPLETED,
        "linked_property_requirement_id": "lpr-1",
        "evidence_keys": ["document:doc-1"],
    }
    ids = _ids(next_job_actions(wo))
    assert "verify" in ids
    assert "link_document" not in ids
