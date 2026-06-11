"""Cancel lifecycle governance — whole-job cancel in next_actions."""
from __future__ import annotations

from services import maintenance_service as ms
from services.compliance_workflow_service import next_job_actions


def _ids(actions):
    return [a["id"] for a in actions]


def test_open_job_includes_lifecycle_cancel():
    wo = {
        "work_order_id": "wo-1",
        "work_order_kind": ms.WORK_ORDER_KIND_MAINTENANCE,
        "status": ms.STATUS_OPEN,
        "contractor_id": "",
    }
    ids = _ids(next_job_actions(wo))
    assert "assign_contractor" in ids
    assert "cancel" in ids
    cancel = next(a for a in next_job_actions(wo) if a["id"] == "cancel")
    assert cancel["section"] == "lifecycle"
    assert "before" in (cancel.get("hint") or "").lower()


def test_terminal_jobs_exclude_cancel():
    wo = {"work_order_id": "wo-1", "work_order_kind": ms.WORK_ORDER_KIND_MAINTENANCE, "status": ms.STATUS_CANCELLED}
    assert "cancel" not in _ids(next_job_actions(wo))


def test_assigned_job_cancel_hint_differs():
    wo = {
        "work_order_id": "wo-1",
        "work_order_kind": ms.WORK_ORDER_KIND_MAINTENANCE,
        "status": ms.STATUS_ASSIGNED,
        "contractor_id": "ctr-1",
        "schedule_status": "",
        "scheduled_at": "",
    }
    cancel = next(a for a in next_job_actions(wo) if a["id"] == "cancel")
    assert "cancel visit" in (cancel.get("hint") or "").lower()
