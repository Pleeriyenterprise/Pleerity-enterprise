"""
Canonical compliance job (work order) workflow mapping and invariants for client API.

Work orders remain the source of truth; this module derives job_status, next_actions,
and enforces rules (one active compliance job per requirement, verify requires proof, etc.).

Regression / traceability (maintenance + compliance job rules):
- tests/test_compliance_workflow_maintenance_canonical.py — maintenance statuses, exception holds,
  AWAITING_PARTS, completion vs proof, issue hints, compliance link_document vs verify.
- tests/test_document_verify_compliance_http.py — document verify → requirement VALID/COMPLIANT and job VERIFIED.
- tests/test_today_items_unified_projection_http.py — Today payload tracks unified task feed changes.

Canonical job HTTP surface (booking / execution / closeout): POST /api/jobs/{id}/assign-contractor,
request-booking, reschedule (alias), confirm-booking, cancel-booking (schedule only; clears visit fields),
mark-no-access, mark-reschedule-required (operational exceptions → canonical NO_ACCESS / RESCHEDULE_REQUIRED),
start, awaiting-parts (maintenance IN_PROGRESS → AWAITING_PARTS), complete,
link-document (compliance), attach-completion-proof (maintenance), verify (compliance only), close (maintenance only),
operational-exception, resume-after-parts, cancel (whole job).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services import maintenance_service
from services.work_order_execution_constants import WORK_ORDER_KIND_COMPLIANCE
from services.work_order_schedule_constants import SCHEDULE_STATUS_CONFIRMED, SCHEDULE_STATUS_PROPOSED

WORK_ORDER_KIND_MAINTENANCE = maintenance_service.WORK_ORDER_KIND_MAINTENANCE
OE_NO_ACCESS = maintenance_service.OPERATIONAL_EXCEPTION_NO_ACCESS
OE_RESCHEDULE = maintenance_service.OPERATIONAL_EXCEPTION_RESCHEDULE_REQUIRED
OE_FOLLOW_UP = maintenance_service.OPERATIONAL_EXCEPTION_FOLLOW_UP_REQUIRED

_TERMINAL_WO_STATUSES = frozenset(
    {
        maintenance_service.STATUS_CANCELLED,
        maintenance_service.STATUS_COMPLETED,
        maintenance_service.STATUS_CLOSED,
        maintenance_service.STATUS_VERIFIED,
    }
)


async def find_active_compliance_job_for_requirement(
    *,
    client_id: str,
    property_id: str,
    linked_property_requirement_id: str,
) -> Optional[Dict[str, Any]]:
    """Return a non-terminal COMPLIANCE work order for this requirement, if any."""
    from database import database

    db = database.get_db()
    doc = await db.work_orders.find_one(
        {
            "client_id": client_id.strip(),
            "property_id": property_id.strip(),
            "linked_property_requirement_id": linked_property_requirement_id.strip(),
            "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
            "status": {"$nin": list(_TERMINAL_WO_STATUSES)},
        },
        {"_id": 0},
    )
    if doc:
        doc.pop("_id", None)
    return doc


async def assert_max_one_active_compliance_job(
    *,
    client_id: str,
    property_id: str,
    linked_property_requirement_id: str,
) -> None:
    existing = await find_active_compliance_job_for_requirement(
        client_id=client_id,
        property_id=property_id,
        linked_property_requirement_id=linked_property_requirement_id,
    )
    if existing:
        wid = existing.get("work_order_id", "")
        raise ValueError(
            f"An active compliance job already exists for this requirement (work_order_id={wid}). "
            "Complete or cancel it before creating another."
        )


def work_order_has_proof_document(wo: Dict[str, Any]) -> bool:
    for k in wo.get("evidence_keys") or []:
        if str(k).startswith("document:"):
            return True
    return False


def maintenance_has_completion_evidence(wo: Dict[str, Any]) -> bool:
    """True if any evidence pointer is recorded (vault document or contractor file key)."""
    keys = wo.get("evidence_keys") or []
    return len(keys) > 0


def derive_canonical_job_status(wo: Dict[str, Any]) -> str:
    """
    Map persisted work order to a workflow label. Operational exceptions surface as first-class states.
    Maintenance AWAITING_PARTS maps to AWAITING_PARTS.
    """
    st = (wo.get("status") or "").strip().upper()
    kind = (wo.get("work_order_kind") or "").strip().upper() or WORK_ORDER_KIND_MAINTENANCE
    if st == maintenance_service.STATUS_CANCELLED:
        return "CANCELLED"
    if st == maintenance_service.STATUS_VERIFIED:
        return "VERIFIED"
    if st == maintenance_service.STATUS_CLOSED:
        return "CLOSED"
    if st == maintenance_service.STATUS_COMPLETED:
        return "COMPLETED"
    if kind == WORK_ORDER_KIND_MAINTENANCE and st == maintenance_service.STATUS_DRAFT:
        return "DRAFT"
    if kind == WORK_ORDER_KIND_MAINTENANCE and st == maintenance_service.STATUS_AWAITING_PARTS:
        return "AWAITING_PARTS"
    if kind == WORK_ORDER_KIND_MAINTENANCE and st == maintenance_service.STATUS_SCHEDULED:
        return "SCHEDULED"

    oe = (wo.get("operational_exception") or "").strip().upper()
    if oe == OE_NO_ACCESS:
        return "NO_ACCESS"
    if oe == OE_RESCHEDULE:
        return "RESCHEDULE_REQUIRED"
    if oe == OE_FOLLOW_UP:
        return "FOLLOW_UP_REQUIRED"

    if st == maintenance_service.STATUS_IN_PROGRESS:
        return "IN_PROGRESS"

    sched = (wo.get("schedule_status") or "").strip().lower()
    if kind == WORK_ORDER_KIND_COMPLIANCE:
        if sched == SCHEDULE_STATUS_CONFIRMED:
            return "BOOKED"
        if sched == SCHEDULE_STATUS_PROPOSED and (wo.get("scheduled_at") or "").strip():
            return "BOOKING_REQUESTED"

    cid = (wo.get("contractor_id") or "").strip()
    if cid:
        return "ASSIGNED"
    return "OPEN"


def _action(
    action_id: str,
    label: str,
    hint: str = "",
    *,
    section: str = "execution",
) -> Dict[str, str]:
    return {"id": action_id, "label": label, "hint": hint, "section": section}


def _maintenance_next_job_actions(wo: Dict[str, Any], canonical: str, st: str) -> List[Dict[str, str]]:
    if st == maintenance_service.STATUS_CANCELLED:
        return [_action("none", "Job cancelled", "")]
    if canonical == "VERIFIED":
        return [_action("close_job", "Mark closed", "Archive the job after verification (maintenance).", section="execution")]
    if canonical == "CLOSED":
        return [_action("none", "Job closed", "")]
    if canonical == "DRAFT":
        return [
            _action(
                "assign_contractor",
                "Assign contractor",
                "Finish setup and assign someone to attend.",
                section="assignment",
            )
        ]
    if canonical == "COMPLETED":
        if not maintenance_has_completion_evidence(wo):
            return [
                _action(
                    "attach_completion_proof",
                    "Attach completion proof",
                    "Link a certificate or photo from your vault before closing the job.",
                    section="evidence",
                )
            ]
        hint = "Closes the job and linked maintenance issue when you are satisfied."
        return [_action("close_job", "Close job", hint, section="execution")]
    if canonical == "AWAITING_PARTS":
        return [
            _action(
                "resume_after_parts",
                "Parts received — resume work",
                "Move the job back in progress when parts are on site.",
                section="execution",
            ),
            _action(
                "complete",
                "Mark work complete",
                "Use when work is finished while waiting on parts, or when closing out without resuming.",
                section="execution",
            ),
        ]
    if canonical in ("NO_ACCESS", "RESCHEDULE_REQUIRED", "FOLLOW_UP_REQUIRED"):
        labels = {
            "NO_ACCESS": "No access — job on hold",
            "RESCHEDULE_REQUIRED": "Reschedule required",
            "FOLLOW_UP_REQUIRED": "Follow-up required",
        }
        return [
            _action(
                "clear_operational_exception",
                f"Clear hold ({labels.get(canonical, canonical)})",
                "Use when the situation is resolved.",
                section="execution",
            ),
            _action(
                "set_operational_exception",
                "Update hold reason",
                "Switch between no-access, reschedule, or follow-up if needed.",
                section="execution",
            ),
            _action(
                "propose_schedule",
                "Propose a new visit time",
                "After access or agreement, propose a revised window with your contractor.",
                section="scheduling",
            ),
        ]
    if canonical == "SCHEDULED":
        return [
            _action(
                "start",
                "Mark in progress",
                "Use when the contractor is on site or work has started.",
                section="execution",
            ),
            _action(
                "mark_no_access",
                "Mark no access",
                "Put the job on hold if the visit could not go ahead.",
                section="scheduling",
            ),
            _action(
                "propose_schedule",
                "Reschedule visit",
                "Propose a new visit window on the job (booking sub-flow).",
                section="scheduling",
            ),
            _action(
                "cancel_booking",
                "Cancel scheduled visit",
                "Clears the current visit; assign and request booking again when ready.",
                section="scheduling",
            ),
        ]
    if canonical == "IN_PROGRESS":
        return [
            _action(
                "awaiting_parts",
                "Mark awaiting parts",
                "Pause work until parts or materials arrive.",
                section="execution",
            ),
            _action("complete", "Mark work complete", "When repair or visit work is finished.", section="execution"),
        ]
    if not (wo.get("contractor_id") or "").strip():
        return [
            _action(
                "assign_contractor",
                "Assign contractor",
                "Search your network or add a contractor for this job.",
                section="assignment",
            )
        ]
    ss = (wo.get("schedule_status") or "").strip().lower()
    sat = (wo.get("scheduled_at") or "").strip()
    if not sat or ss in ("", "cancelled"):
        return [
            _action(
                "propose_schedule",
                "Schedule visit",
                "Propose a visit window with the assigned contractor.",
                section="scheduling",
            )
        ]
    if ss == "proposed":
        sb = (wo.get("scheduled_by") or "").strip().lower()
        base_cancel = _action(
            "cancel_booking",
            "Cancel booking request",
            "Withdraw the proposed visit before it is confirmed.",
            section="scheduling",
        )
        if sb in ("contractor", "admin"):
            return [
                _action("confirm_visit", "Confirm visit", "Confirm the proposed time.", section="scheduling"),
                base_cancel,
            ]
        return [
            _action(
                "confirm_visit",
                "Awaiting contractor confirmation",
                "The contractor confirms your proposed time.",
                section="scheduling",
            ),
            base_cancel,
        ]
    if ss == "confirmed" or canonical == "BOOKED":
        return [
            _action("start", "Mark in progress", "Contractor on site or work underway.", section="execution"),
            _action(
                "mark_no_access",
                "Mark no access",
                "Record that the visit could not proceed; reschedule when resolved.",
                section="scheduling",
            ),
            _action(
                "propose_schedule",
                "Reschedule visit",
                "Propose a different visit time (booking sub-flow).",
                section="scheduling",
            ),
            _action(
                "cancel_booking",
                "Cancel scheduled visit",
                "Cancel the confirmed visit window on this job.",
                section="scheduling",
            ),
        ]
    return [_action("propose_schedule", "Schedule visit", "Set or adjust the visit window.", section="scheduling")]


def _compliance_next_job_actions(wo: Dict[str, Any], canonical: str, st: str) -> List[Dict[str, str]]:
    if st == maintenance_service.STATUS_CANCELLED:
        return [_action("none", "Job cancelled", "")]
    if canonical == "VERIFIED":
        return [_action("none", "Verified and closed", "")]
    if canonical in ("NO_ACCESS", "RESCHEDULE_REQUIRED"):
        return [
            _action(
                "clear_operational_exception",
                "Clear operational hold",
                "Use when access is restored or reschedule is agreed.",
                section="execution",
            ),
            _action(
                "propose_schedule",
                "Propose visit time",
                "Use scheduling when you need a new window.",
                section="scheduling",
            ),
        ]
    if canonical == "FOLLOW_UP_REQUIRED":
        return [
            _action(
                "clear_operational_exception",
                "Follow-up complete — clear hold",
                "",
                section="execution",
            )
        ]
    if canonical == "OPEN":
        return [
            _action(
                "assign_contractor",
                "Assign contractor",
                "Choose who will carry out the compliance visit or work.",
                section="assignment",
            )
        ]
    if canonical == "ASSIGNED":
        return [
            _action(
                "request_booking",
                "Request booking",
                "Propose a visit date and time (or wait for the contractor to propose, then confirm).",
                section="scheduling",
            )
        ]
    if canonical == "BOOKING_REQUESTED":
        sched_by = (wo.get("scheduled_by") or "").strip().lower()
        cancel_b = _action(
            "cancel_booking",
            "Cancel booking request",
            "Withdraw the proposed visit before confirming.",
            section="scheduling",
        )
        if sched_by == "contractor":
            return [
                _action("confirm_visit", "Confirm visit", "Confirm the proposed visit window.", section="scheduling"),
                cancel_b,
            ]
        return [
            _action(
                "confirm_visit",
                "Confirm visit",
                "Wait for the contractor to confirm your proposed time, or propose a new time.",
                section="scheduling",
            ),
            _action(
                "reschedule_booking",
                "Propose new visit time",
                "Replace the pending proposal with a different slot (booking sub-flow).",
                section="scheduling",
            ),
            cancel_b,
        ]
    if canonical == "BOOKED":
        return [
            _action(
                "start",
                "Mark visit in progress",
                "Use when the contractor is on site or work has started.",
                section="execution",
            ),
            _action(
                "mark_no_access",
                "Mark no access",
                "Record that the visit could not proceed; clear the hold when access is restored.",
                section="scheduling",
            ),
            _action(
                "mark_reschedule_required",
                "Mark reschedule required",
                "Put the job on hold until a new visit window is agreed.",
                section="scheduling",
            ),
            _action(
                "reschedule_booking",
                "Reschedule visit",
                "Propose a new visit time without cancelling the job.",
                section="scheduling",
            ),
            _action(
                "cancel_booking",
                "Cancel scheduled visit",
                "Cancel the confirmed visit; request booking again when ready.",
                section="scheduling",
            ),
        ]
    if canonical == "IN_PROGRESS":
        return [
            _action(
                "mark_no_access",
                "Mark no access",
                "Record that the visit could not proceed; clear the hold when access is restored.",
                section="scheduling",
            ),
            _action(
                "mark_reschedule_required",
                "Mark reschedule required",
                "Put the job on hold until a new visit window is agreed.",
                section="scheduling",
            ),
            _action(
                "complete",
                "Mark work complete",
                "When the visit or installation work is finished.",
                section="execution",
            ),
        ]
    if canonical == "COMPLETED":
        if not work_order_has_proof_document(wo):
            return [
                _action(
                    "link_document",
                    "Attach compliance certificate",
                    "Link vault evidence before verification.",
                    section="evidence",
                )
            ]
        return [
            _action(
                "verify",
                "Verify and close",
                "Confirms the job and linked evidence in your workflow.",
                section="execution",
            )
        ]
    return []


def next_job_actions(wo: Dict[str, Any]) -> List[Dict[str, str]]:
    """Next steps for COMPLIANCE or MAINTENANCE work orders (labels aligned with client job UI)."""
    kind = (wo.get("work_order_kind") or "").strip().upper() or WORK_ORDER_KIND_MAINTENANCE
    canonical = derive_canonical_job_status(wo)
    st = (wo.get("status") or "").strip().upper()
    if kind == WORK_ORDER_KIND_MAINTENANCE:
        return _maintenance_next_job_actions(wo, canonical, st)
    return _compliance_next_job_actions(wo, canonical, st)


def client_job_timeline_events(wo: Dict[str, Any]) -> List[Dict[str, str]]:
    """Read-only milestone list for client job UI (no separate query)."""
    out: List[Dict[str, str]] = []
    for label, key in (
        ("Created", "created_at"),
        ("Updated", "updated_at"),
        ("Contractor assigned", "assigned_at"),
        ("Contractor accepted", "accepted_at"),
        ("Visit time recorded", "scheduled_at"),
        ("Schedule last updated", "last_schedule_update_at"),
        ("Work completed", "completed_at"),
    ):
        v = wo.get(key)
        if v:
            out.append({"label": label, "at": str(v)})
    return out


def maintenance_issue_resolution_hint(wo: Dict[str, Any]) -> Optional[str]:
    if not (wo.get("issue_id") or "").strip():
        return None
    if (wo.get("work_order_kind") or "").strip().upper() != WORK_ORDER_KIND_MAINTENANCE:
        return None
    st = (wo.get("status") or "").strip().upper()
    if st == maintenance_service.STATUS_VERIFIED:
        return "The linked maintenance issue was closed when this job was verified."
    if st in (maintenance_service.STATUS_COMPLETED, maintenance_service.STATUS_CLOSED):
        return "Verify this job when you are satisfied; that closes the linked maintenance issue."
    return None


def serialize_client_job(wo: Dict[str, Any]) -> Dict[str, Any]:
    """Canonical GET /api/jobs/{id} payload for any work order kind."""
    wid = wo.get("work_order_id")
    kind = (wo.get("work_order_kind") or "").strip().upper() or WORK_ORDER_KIND_MAINTENANCE
    job_status = derive_canonical_job_status(wo)
    base: Dict[str, Any] = {
        "job_id": wid,
        "work_order_id": wid,
        "work_order_kind": kind,
        "client_id": wo.get("client_id"),
        "property_id": wo.get("property_id"),
        "description": wo.get("description"),
        "status": (wo.get("status") or "").strip().upper(),
        "job_status": job_status,
        "operational_exception": wo.get("operational_exception"),
        "contractor_id": wo.get("contractor_id"),
        "scheduled_at": wo.get("scheduled_at"),
        "scheduled_timezone": wo.get("scheduled_timezone"),
        "schedule_status": wo.get("schedule_status"),
        "scheduled_by": wo.get("scheduled_by"),
        "evidence_keys": wo.get("evidence_keys") or [],
        "severity": wo.get("severity"),
        "category": wo.get("category"),
        "issue_id": wo.get("issue_id"),
        "asset_id": wo.get("asset_id"),
        "sla_respond_by": wo.get("sla_respond_by"),
        "sla_complete_by": wo.get("sla_complete_by"),
        "created_at": wo.get("created_at"),
        "updated_at": wo.get("updated_at"),
        "completed_at": wo.get("completed_at"),
        "next_actions": next_job_actions(wo),
        "timeline_events": client_job_timeline_events(wo),
        "resolution_outcome": wo.get("resolution_outcome"),
    }
    if kind == WORK_ORDER_KIND_COMPLIANCE:
        base["linked_property_requirement_id"] = wo.get("linked_property_requirement_id")
        base["requirement_code"] = wo.get("requirement_code")
        base["compliance_purpose"] = wo.get("compliance_purpose")
        base["compliance_booking_status"] = wo.get("compliance_booking_status")
        base["compliance_proof_status"] = wo.get("compliance_proof_status")
    if kind == WORK_ORDER_KIND_MAINTENANCE:
        mh = maintenance_issue_resolution_hint(wo)
        if mh:
            base["issue_resolution_hint"] = mh
    return base


def serialize_compliance_job(wo: Dict[str, Any]) -> Dict[str, Any]:
    """Backward-compatible alias; prefer serialize_client_job."""
    return serialize_client_job(wo)


def derive_requirement_workflow_fields(
    req: Dict[str, Any],
    *,
    active_compliance_job: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """UI-oriented status/compliance_state without mutating stored requirement rows."""
    app = (req.get("applicability") or "").strip().upper()
    raw_status = (req.get("status") or "").strip().upper()
    if app == "NOT_REQUIRED" or raw_status == "NOT_REQUIRED":
        return {
            "workflow_status": "NOT_APPLICABLE",
            "compliance_state": "NOT_APPLICABLE",
        }
    if active_compliance_job:
        return {
            "workflow_status": "IN_PROGRESS",
            "compliance_state": "PENDING_VERIFICATION",
        }
    if raw_status == "COMPLIANT":
        return {"workflow_status": "COMPLIANT", "compliance_state": "VALID"}
    if raw_status == "OVERDUE":
        return {"workflow_status": "OVERDUE", "compliance_state": "OVERDUE"}
    if raw_status == "EXPIRING_SOON":
        return {"workflow_status": "ACTION_REQUIRED", "compliance_state": "EXPIRING"}
    if raw_status == "PENDING":
        return {"workflow_status": "ACTION_REQUIRED", "compliance_state": "MISSING"}
    return {"workflow_status": "ACTION_REQUIRED", "compliance_state": "MISSING"}


async def load_compliance_work_order_for_client(*, work_order_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    wo = await load_client_work_order(work_order_id=work_order_id, client_id=client_id)
    if not wo:
        return None
    if (wo.get("work_order_kind") or "").strip().upper() != WORK_ORDER_KIND_COMPLIANCE:
        return None
    return wo


async def load_client_work_order(*, work_order_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    from database import database

    db = database.get_db()
    wo = await db.work_orders.find_one(
        {"work_order_id": work_order_id.strip(), "client_id": client_id.strip()},
        {"_id": 0},
    )
    if not wo:
        return None
    wo.pop("_id", None)
    return wo
