"""Contractor portal next_actions derivation (API-driven CTAs)."""
import pytest

from services import maintenance_service as ms
from services.compliance_workflow_service import (
    apply_contractor_job_enrichment,
    contractor_next_job_actions,
)


def _wo(**kwargs):
    base = {
        "work_order_id": "wo-1",
        "client_id": "c1",
        "property_id": "p1",
        "work_order_kind": ms.WORK_ORDER_KIND_MAINTENANCE,
        "contractor_id": "ctr1",
        "evidence_keys": [],
    }
    base.update(kwargs)
    return base


def _ids(actions):
    return [a["id"] for a in actions]


def test_contractor_actions_open_assigned_accept_decline():
    w = _wo(status=ms.STATUS_ASSIGNED)
    ids = _ids(contractor_next_job_actions(w, invoice=None))
    assert ids[0] == "accept_assignment"
    assert "decline_assignment" in ids


def test_contractor_actions_scheduled_no_visit_propose():
    w = _wo(status=ms.STATUS_SCHEDULED, schedule_status="", scheduled_at="")
    assert _ids(contractor_next_job_actions(w)) == ["propose_visit"]


def test_contractor_actions_confirm_visit_when_client_proposed():
    w = _wo(
        status=ms.STATUS_SCHEDULED,
        schedule_status="proposed",
        scheduled_at="2026-04-01T10:00:00+00:00",
        scheduled_by="client",
    )
    ids = _ids(contractor_next_job_actions(w))
    assert ids[0] == "confirm_visit"
    assert "reschedule_visit" in ids
    assert "cancel_scheduled_visit" in ids


def test_contractor_actions_waiting_after_contractor_proposed():
    w = _wo(
        status=ms.STATUS_SCHEDULED,
        schedule_status="proposed",
        scheduled_at="2026-04-01T10:00:00+00:00",
        scheduled_by="contractor",
    )
    ids = _ids(contractor_next_job_actions(w))
    assert ids == ["open_job_detail"]


def test_contractor_actions_confirmed_schedule_start_job():
    w = _wo(
        status=ms.STATUS_SCHEDULED,
        schedule_status="confirmed",
        scheduled_at="2026-04-01T10:00:00+00:00",
        scheduled_by="client",
    )
    ids = _ids(contractor_next_job_actions(w))
    assert ids[0] == "start_job"
    assert "mark_no_access" in ids
    assert "reschedule_visit" in ids
    assert "cancel_scheduled_visit" in ids


def test_contractor_in_progress_requires_proof_before_complete():
    w = _wo(
        status=ms.STATUS_IN_PROGRESS,
        work_order_kind=ms.WORK_ORDER_KIND_COMPLIANCE,
        requirement_code="gas_safety",
        evidence_keys=[],
    )
    ids = _ids(contractor_next_job_actions(w))
    assert "upload_completion_proof" in ids
    assert "complete_job" not in ids
    assert "mark_no_access" in ids


def test_contractor_in_progress_complete_when_proof_present():
    w = _wo(
        status=ms.STATUS_IN_PROGRESS,
        work_order_kind=ms.WORK_ORDER_KIND_COMPLIANCE,
        evidence_keys=["file:abc"],
    )
    ids = _ids(contractor_next_job_actions(w))
    assert "complete_job" in ids
    assert "upload_completion_proof" not in ids


def test_contractor_awaiting_parts_includes_mark_no_access():
    w = _wo(status=ms.STATUS_AWAITING_PARTS, evidence_keys=["file:x"])
    ids = _ids(contractor_next_job_actions(w))
    assert "resume_job" in ids
    assert "mark_no_access" in ids


def test_contractor_operational_hold_navigation_only():
    w = _wo(status=ms.STATUS_IN_PROGRESS, operational_exception=ms.OPERATIONAL_EXCEPTION_NO_ACCESS)
    ids = _ids(contractor_next_job_actions(w))
    assert ids == ["open_job_detail"]


def test_contractor_completed_submit_invoice_no_invoice():
    w = _wo(status=ms.STATUS_COMPLETED)
    ids = _ids(contractor_next_job_actions(w, invoice=None))
    assert ids == ["submit_invoice"]


def test_contractor_completed_compliance_no_proof_upload_only():
    w = _wo(status=ms.STATUS_COMPLETED, work_order_kind=ms.WORK_ORDER_KIND_COMPLIANCE, evidence_keys=[])
    assert _ids(contractor_next_job_actions(w, invoice=None)) == ["upload_completion_proof"]


def test_contractor_completed_compliance_with_proof_submit_invoice():
    w = _wo(
        status=ms.STATUS_COMPLETED,
        work_order_kind=ms.WORK_ORDER_KIND_COMPLIANCE,
        evidence_keys=["file:abc"],
    )
    assert _ids(contractor_next_job_actions(w, invoice=None)) == ["submit_invoice"]


def test_contractor_completed_maintenance_expected_doc_no_evidence_upload_only():
    w = _wo(status=ms.STATUS_COMPLETED, expected_output_document_type="CERTIFICATE", evidence_keys=[])
    assert _ids(contractor_next_job_actions(w, invoice=None)) == ["upload_completion_proof"]


def test_contractor_completed_invoice_pending_view_invoice():
    w = _wo(status=ms.STATUS_COMPLETED)
    inv = {"invoice_id": "inv-1", "status": "pending"}
    acts = contractor_next_job_actions(w, invoice=inv)
    assert _ids(acts) == ["view_invoice"]
    assert acts[0].get("payload", {}).get("invoice_id") == "inv-1"
    assert "Waiting for approval" in (acts[0].get("hint") or "")


def test_contractor_completed_invoice_needs_info_edit():
    w = _wo(status=ms.STATUS_COMPLETED)
    inv = {"invoice_id": "inv-2", "status": "needs_info"}
    acts = contractor_next_job_actions(w, invoice=inv)
    assert _ids(acts) == ["edit_invoice"]


def test_contractor_completed_invoice_paid_view():
    w = _wo(status=ms.STATUS_COMPLETED)
    inv = {"invoice_id": "inv-3", "status": "paid", "paid_at": "2026-04-01T12:00:00+00:00"}
    acts = contractor_next_job_actions(w, invoice=inv)
    assert _ids(acts) == ["view_invoice"]
    assert "Paid on" in (acts[0].get("hint") or "")


def test_apply_enrichment_sets_flags():
    w = _wo(status=ms.STATUS_IN_PROGRESS, work_order_kind=ms.WORK_ORDER_KIND_COMPLIANCE, evidence_keys=[])
    apply_contractor_job_enrichment(w, invoice=None)
    assert w.get("job_status")
    assert isinstance(w.get("next_actions"), list)
    assert isinstance(w.get("timeline_events"), list)
    assert w.get("completion_proof_required") is True
    assert w.get("completion_proof_satisfied") is False
    assert w.get("linked_invoice") is None


def test_apply_enrichment_linked_invoice():
    w = _wo(status=ms.STATUS_COMPLETED)
    inv = {"invoice_id": "i-x", "status": "pending", "submitted_amount": 100.0}
    apply_contractor_job_enrichment(w, invoice=inv)
    li = w.get("linked_invoice")
    assert li is not None
    assert li.get("contractor_invoice_state") == "SUBMITTED"
    assert li.get("invoice_id") == "i-x"
