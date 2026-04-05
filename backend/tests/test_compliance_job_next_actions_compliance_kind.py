"""next_actions for COMPLIANCE work_order_kind (booking, holds, execution)."""
from __future__ import annotations

from services import maintenance_service as ms
from services.compliance_workflow_service import derive_canonical_job_status, next_job_actions
from services.work_order_execution_constants import WORK_ORDER_KIND_COMPLIANCE


def _ids(actions):
    return [a["id"] for a in actions]


def _compliance_wo(**kwargs):
    row = {
        "work_order_id": "wo-c-1",
        "client_id": "cli-1",
        "property_id": "prop-1",
        "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
        "description": "EPC",
        "contractor_id": "ctr-1",
        "status": ms.STATUS_ASSIGNED,
        "schedule_status": "confirmed",
        "scheduled_at": "2026-03-01T10:00:00+00:00",
        "scheduled_timezone": "Europe/London",
        "scheduled_by": "client",
        "evidence_keys": [],
    }
    row.update(kwargs)
    return row


def test_compliance_booked_includes_reschedule_hold_actions():
    wo = _compliance_wo()
    assert derive_canonical_job_status(wo) == "BOOKED"
    ids = _ids(next_job_actions(wo))
    assert "mark_no_access" in ids
    assert "mark_reschedule_required" in ids
    assert "start" in ids


def test_compliance_in_progress_includes_holds_and_complete():
    wo = _compliance_wo(status=ms.STATUS_IN_PROGRESS)
    assert derive_canonical_job_status(wo) == "IN_PROGRESS"
    ids = _ids(next_job_actions(wo))
    assert "mark_no_access" in ids
    assert "mark_reschedule_required" in ids
    assert "complete" in ids
