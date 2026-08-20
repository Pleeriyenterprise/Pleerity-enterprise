"""Tests for progress_contract_v1 — cross-role workflow parity."""
from __future__ import annotations

from services.progress_contract_service import build_progress_contract_v1


def _base_wo(**overrides):
    wo = {
        "work_order_id": "wo-test-1",
        "work_order_kind": "COMPLIANCE",
        "status": "SCHEDULED",
        "contractor_id": "c-1",
        "schedule_status": "confirmed",
        "scheduled_at": "2026-06-30T19:56:00Z",
        "pricing_mode": "COMPLIANCE_FIXED_QUOTE",
        "price_status": "QUOTED",
        "workflow_mode": "QUOTE_FIRST",
        "compliance_proof_status": "SUBMITTED",
    }
    wo.update(overrides)
    return wo


def test_booked_visit_not_work_completed_landlord():
    """Quote pending blocks visit-booked stage even when a visit exists on calendar."""
    wo = _base_wo(compliance_proof_status="")
    pc = build_progress_contract_v1(wo, audience="landlord")
    assert pc["current_stage"] == "quote_approved"
    assert pc["work_execution_status"] == "NOT_STARTED"
    steps = {s["key"]: s["state"] for s in pc["progress_steps"] if s["state"] != "skipped"}
    assert steps["work_started"] == "pending"
    assert steps.get("proof_uploaded") == "pending"


def test_booked_visit_not_in_progress_contractor():
    wo = _base_wo(compliance_proof_status="")
    pc = build_progress_contract_v1(wo, audience="contractor")
    assert pc["current_stage"] == "quote_approved"
    labels = [s["label"] for s in pc["progress_steps"] if s["state"] == "current"]
    assert labels == ["Quote approved"]
    assert pc["canonical_status"] == "BOOKED"


def test_visit_booked_when_quote_approved():
    wo = _base_wo(price_status="APPROVED", compliance_proof_status="")
    pc = build_progress_contract_v1(wo, audience="landlord")
    assert pc["current_stage"] == "work_started"
    assert pc["work_execution_status"] == "NOT_STARTED"
    steps = {s["key"]: s["state"] for s in pc["progress_steps"] if s["state"] != "skipped"}
    assert steps["visit_booked"] == "complete"
    assert steps["work_started"] == "current"


def test_landlord_contractor_share_current_stage():
    wo = _base_wo(compliance_proof_status="")
    ll = build_progress_contract_v1(wo, audience="landlord")
    ct = build_progress_contract_v1(wo, audience="contractor")
    assert ll["current_stage"] == ct["current_stage"]
    assert ll["canonical_status"] == ct["canonical_status"]
    assert ll["work_execution_status"] == ct["work_execution_status"]
    assert ll["proof_status"] == ct["proof_status"]


def test_contractor_primary_not_mark_no_access_when_quote_pending():
    wo = _base_wo(price_status="QUOTED")
    pc = build_progress_contract_v1(wo, audience="contractor")
    primary = pc["next_primary_action"]
    assert primary is not None
    assert primary["id"] != "mark_no_access"
    assert pc["waiting_on"] == "landlord"


def test_landlord_primary_approve_quote_when_quoted():
    wo = _base_wo(price_status="QUOTED")
    pc = build_progress_contract_v1(wo, audience="landlord")
    primary = pc["next_primary_action"]
    assert primary is not None
    assert primary["id"] == "approve_quote"


def test_work_started_only_when_in_progress():
    wo = _base_wo(
        status="IN_PROGRESS",
        price_status="APPROVED",
        compliance_proof_status="",
        evidence_keys=[],
    )
    pc = build_progress_contract_v1(wo, audience="landlord")
    assert pc["current_stage"] == "work_started"
    assert pc["work_execution_status"] == "IN_PROGRESS"


def test_proof_uploaded_does_not_imply_proof_reviewed():
    wo = _base_wo(
        status="COMPLETED",
        price_status="APPROVED",
        evidence_keys=["ev-1"],
        compliance_proof_status="SUBMITTED",
    )
    pc = build_progress_contract_v1(wo, audience="landlord")
    steps = {s["key"]: s["state"] for s in pc["progress_steps"] if s["state"] != "skipped"}
    assert steps["proof_uploaded"] == "complete"
    assert steps["proof_reviewed"] == "current"


def test_inspection_first_separate_steps():
    wo = _base_wo(
        workflow_mode="INSPECTION_FIRST",
        pricing_mode="MAINTENANCE_INSPECTION_REQUIRED",
        price_status="AWAITING_QUOTE",
        status="SCHEDULED",
        compliance_proof_status="",
    )
    pc = build_progress_contract_v1(wo, audience="contractor")
    keys = [s["key"] for s in pc["progress_steps"] if s["state"] != "skipped"]
    assert "inspection_visit_booked" in keys
    assert "visit_booked" not in keys
    assert pc["current_stage"] == "inspection_completed"


def test_quote_first_omits_inspection_steps():
    wo = _base_wo(compliance_proof_status="")
    pc = build_progress_contract_v1(wo, audience="admin")
    keys = [s["key"] for s in pc["progress_steps"]]
    assert "inspection_visit_booked" not in keys
    assert "inspection_completed" not in keys


def test_assigned_no_quote_current_stage():
    wo = _base_wo(
        status="ASSIGNED",
        schedule_status="",
        scheduled_at="",
        price_status="AWAITING_QUOTE",
        compliance_proof_status="",
    )
    pc = build_progress_contract_v1(wo, audience="landlord")
    assert pc["current_stage"] == "quote_submitted"
    assert pc["waiting_on"] == "contractor"


def test_assigned_status_without_contractor_id_not_marked_assigned():
    """Status ASSIGNED without contractor_id must not show Contractor assigned as complete."""
    wo = _base_wo(
        contractor_id="",
        status="ASSIGNED",
        schedule_status="",
        scheduled_at="",
        price_status="AWAITING_QUOTE",
        compliance_proof_status="",
    )
    pc = build_progress_contract_v1(wo, audience="landlord")
    steps = {s["key"]: s for s in pc["progress_steps"] if s["state"] != "skipped"}
    assert steps["assigned"]["state"] == "current"
    assert steps["assigned"]["label"] == "Awaiting contractor assignment"
    assert steps["assigned"]["state"] != "complete"


def test_quote_first_assigned_no_visit_is_not_visit_booked():
    wo = _base_wo(
        work_order_kind="MAINTENANCE",
        status="ASSIGNED",
        schedule_status="",
        scheduled_at="",
        price_status="AWAITING_QUOTE",
        pricing_mode="MAINTENANCE_PREQUOTE",
        workflow_mode="QUOTE_FIRST",
        compliance_proof_status="",
    )
    pc = build_progress_contract_v1(wo, audience="landlord")
    current = next(s for s in pc["progress_steps"] if s["state"] == "current")
    assert current["key"] == "quote_submitted"
    assert "Visit booked" not in current["label"]
    assert "Visit booked" not in (pc.get("headline") or "")


def test_inspection_first_assigned_no_visit_schedule_inspection():
    wo = _base_wo(
        work_order_kind="MAINTENANCE",
        workflow_mode="INSPECTION_FIRST",
        pricing_mode="MAINTENANCE_INSPECTION_REQUIRED",
        price_status="AWAITING_QUOTE",
        status="ASSIGNED",
        schedule_status="",
        scheduled_at="",
        compliance_proof_status="",
    )
    pc = build_progress_contract_v1(wo, audience="landlord")
    current = next(s for s in pc["progress_steps"] if s["state"] == "current")
    assert current["key"] == "inspection_visit_booked"
    assert current["label"] == "Schedule inspection"
    assert "Visit booked" not in current["label"]
    assert "Visit booked" not in (pc.get("headline") or "")


def test_confirmed_visit_keeps_visit_booked_complete_label():
    wo = _base_wo(price_status="APPROVED", compliance_proof_status="")
    pc = build_progress_contract_v1(wo, audience="landlord")
    steps = {s["key"]: s for s in pc["progress_steps"] if s["state"] != "skipped"}
    assert steps["visit_booked"]["state"] == "complete"
    assert steps["visit_booked"]["label"] == "Visit booked"


def test_proposed_reschedule_is_not_visit_booked():
    wo = _base_wo(
        price_status="APPROVED",
        schedule_status="proposed",
        scheduled_at="2026-07-01T10:00:00Z",
        compliance_proof_status="",
        status="SCHEDULED",
        work_order_kind="MAINTENANCE",
    )
    pc = build_progress_contract_v1(wo, audience="landlord")
    visit = next(s for s in pc["progress_steps"] if s["key"] == "visit_booked")
    assert visit["state"] != "complete"
    assert "Visit booked" not in visit["label"]
    assert "Visit booked" not in (pc.get("headline") or "")
