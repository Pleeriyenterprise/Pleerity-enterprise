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
operational-exception, resume-after-parts, cancel (whole job), decision-log (append-only notes).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services import invoice_service
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
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"id": action_id, "label": label, "hint": hint, "section": section}
    if payload:
        out["payload"] = payload
    return out


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
    ss = (wo.get("schedule_status") or "").strip().lower()
    sat = (wo.get("scheduled_at") or "").strip()
    if ss == "proposed" and sat:
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
                _action(
                    "request_visit_reschedule",
                    "Request another date",
                    "Ask the contractor to propose a different visit time without cancelling the job.",
                    section="scheduling",
                ),
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
    if ss == "reschedule_requested" and sat:
        return [
            _action(
                "propose_schedule",
                "Propose new visit time",
                "Propose a replacement visit slot directly.",
                section="scheduling",
            ),
            _action(
                "cancel_booking",
                "Cancel booking request",
                "Withdraw the visit negotiation before confirming.",
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
                "request_visit_reschedule",
                "Request another date",
                "Ask the contractor to propose a different visit time.",
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
    if not sat or ss in ("", "cancelled"):
        return [
            _action(
                "propose_schedule",
                "Schedule visit",
                "Propose a visit window with the assigned contractor.",
                section="scheduling",
            )
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
                "request_visit_reschedule",
                "Request another date",
                "Ask the contractor to propose a different visit time.",
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
                _action(
                    "request_visit_reschedule",
                    "Request another date",
                    "Ask the contractor to propose a different visit time without cancelling the job.",
                    section="scheduling",
                ),
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
                "request_visit_reschedule",
                "Request another date",
                "Ask the contractor to propose a different visit time.",
                section="scheduling",
            ),
            _action(
                "reschedule_booking",
                "Propose new visit time",
                "Propose a replacement visit slot directly.",
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


def _apply_client_pricing_overrides(wo: Dict[str, Any], actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from services.work_order_pricing_service import (
        client_may_offer_start_for_pricing,
        pricing_workflow_applies,
        quote_is_approved_for_api,
    )
    from services.work_order_pricing_constants import PRICE_STATUS_QUOTED

    if not pricing_workflow_applies(wo):
        return actions
    ps = (wo.get("price_status") or "").strip().upper()
    extra: List[Dict[str, Any]] = []
    if ps == PRICE_STATUS_QUOTED:
        extra.append(
            _action(
                "approve_quote",
                "Approve and authorise work",
                "Confirm the contractor's price before work continues or invoices are submitted.",
                section="billing",
            )
        )
        extra.append(
            _action(
                "request_quote_revision",
                "Request changes",
                "Ask the contractor to revise their quote. Your assignment stays active and they can resubmit.",
                section="billing",
            )
        )
        extra.append(
            _action(
                "reject_quote_final",
                "Decline quote (final)",
                "Mark this quote as finally declined without cancelling the job. Reassign or close separately if needed.",
                section="billing",
            )
        )
    filtered: List[Dict[str, Any]] = []
    for a in actions:
        aid = a.get("id")
        if aid == "start" and not client_may_offer_start_for_pricing(wo):
            continue
        if aid == "complete" and not quote_is_approved_for_api(wo):
            continue
        filtered.append(a)
    return extra + filtered


def next_job_actions(wo: Dict[str, Any]) -> List[Dict[str, str]]:
    """Next steps for COMPLIANCE or MAINTENANCE work orders (labels aligned with client job UI)."""
    kind = (wo.get("work_order_kind") or "").strip().upper() or WORK_ORDER_KIND_MAINTENANCE
    canonical = derive_canonical_job_status(wo)
    st = (wo.get("status") or "").strip().upper()
    if kind == WORK_ORDER_KIND_MAINTENANCE:
        base = _maintenance_next_job_actions(wo, canonical, st)
    else:
        base = _compliance_next_job_actions(wo, canonical, st)
    return _apply_client_pricing_overrides(wo, base)


def contractor_completion_proof_required(wo: Dict[str, Any]) -> bool:
    """Whether the contractor should upload completion proof before marking work complete."""
    kind = (wo.get("work_order_kind") or "").strip().upper() or WORK_ORDER_KIND_MAINTENANCE
    if kind == WORK_ORDER_KIND_COMPLIANCE:
        return True
    if (wo.get("expected_output_document_type") or "").strip():
        return True
    return False


def contractor_has_completion_proof(wo: Dict[str, Any]) -> bool:
    """True if any evidence pointer exists (vault link or uploaded file)."""
    return maintenance_has_completion_evidence(wo)


def _contractor_terminal_billing_actions(
    wo: Dict[str, Any],
    invoice: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Next billing steps when the job is completed/verified/closed (contractor portal)."""
    from services.work_order_pricing_service import pricing_workflow_applies, quote_is_approved_for_api

    if pricing_workflow_applies(wo) and not quote_is_approved_for_api(wo):
        return [
            _action(
                "open_job_detail",
                "Quote approval required",
                "The client must approve your quote before you can submit an invoice for this job.",
                section="billing",
            ),
        ]
    if not invoice:
        return [
            _action(
                "submit_invoice",
                "Submit invoice",
                "Send your invoice to the client for approval.",
                section="billing",
            )
        ]
    inv_id = (invoice.get("invoice_id") or "").strip()
    payload = {"invoice_id": inv_id} if inv_id else {}
    raw = (invoice.get("status") or "").strip().lower()
    if raw == "pending":
        return [
            _action(
                "view_invoice",
                "View invoice",
                "Waiting for approval",
                section="billing",
                payload=payload,
            )
        ]
    if raw == "needs_info":
        return [
            _action(
                "edit_invoice",
                "Edit and resubmit invoice",
                "The client requested changes or clarification.",
                section="billing",
                payload=payload,
            )
        ]
    if raw == "rejected":
        return [
            _action(
                "edit_invoice",
                "Edit and resubmit invoice",
                "Update your invoice and send it back for review.",
                section="billing",
                payload=payload,
            )
        ]
    if raw == "approved":
        return [
            _action(
                "view_invoice",
                "View invoice",
                "Approved — awaiting payment from your client.",
                section="billing",
                payload=payload,
            )
        ]
    if raw == "paid":
        paid_raw = invoice.get("paid_at")
        paid_hint = f"Paid on {paid_raw}" if paid_raw else "Payment recorded."
        return [
            _action(
                "view_invoice",
                "View invoice",
                paid_hint,
                section="billing",
                payload=payload,
            )
        ]
    return []


def contractor_next_job_actions(
    wo: Dict[str, Any],
    *,
    invoice: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Portal-only next steps: ids are mapped in the contractor frontend to contractor API calls.
    Includes scheduling (propose_visit, confirm_visit, reschedule_visit, cancel_scheduled_visit),
    execution (start_job, awaiting_parts, resume_job, complete_job), evidence (upload_completion_proof),
    operational (mark_no_access → POST .../mark-no-access), billing (submit_invoice), and navigation (open_job_detail).
    """
    st = (wo.get("status") or "").strip().upper()
    if st == maintenance_service.STATUS_CANCELLED:
        return []

    oe = (wo.get("operational_exception") or "").strip().upper()
    if oe in (OE_NO_ACCESS, OE_RESCHEDULE, OE_FOLLOW_UP):
        return [
            _action(
                "open_job_detail",
                "Open job",
                "This job is on hold. Review details or contact your client.",
                section="navigation",
            )
        ]

    if st in (maintenance_service.STATUS_VERIFIED, maintenance_service.STATUS_CLOSED):
        return _contractor_terminal_billing_actions(wo, invoice)

    if st == maintenance_service.STATUS_COMPLETED:
        need = contractor_completion_proof_required(wo)
        has = contractor_has_completion_proof(wo)
        if need and not has:
            return [
                _action(
                    "upload_completion_proof",
                    "Upload proof",
                    "Upload completion proof before invoicing.",
                    section="evidence",
                ),
            ]
        return _contractor_terminal_billing_actions(wo, invoice)

    if st in (maintenance_service.STATUS_OPEN, maintenance_service.STATUS_ASSIGNED):
        return [
            _action(
                "accept_assignment",
                "Accept job",
                "Confirm you will take this job to unlock scheduling and field work.",
                section="assignment",
            ),
            _action("decline_assignment", "Decline", "Decline if you cannot take this job.", section="assignment"),
        ]

    if st == maintenance_service.STATUS_SCHEDULED:
        ss = (wo.get("schedule_status") or "").strip().lower()
        sat = (wo.get("scheduled_at") or "").strip()
        sb = (wo.get("scheduled_by") or "").strip().lower()

        if not sat or ss == "cancelled":
            return [
                _action(
                    "propose_visit",
                    "Propose time",
                    "Suggest when you can attend the property.",
                    section="scheduling",
                )
            ]

        if ss == "proposed":
            if sb in ("client", "admin"):
                return [
                    _action("confirm_visit", "Confirm visit", "Confirm the proposed visit time.", section="scheduling"),
                    _action(
                        "reschedule_visit",
                        "Reschedule",
                        "Request a different visit time.",
                        section="scheduling",
                    ),
                    _action(
                        "cancel_scheduled_visit",
                        "Cancel visit",
                        "Withdraw this proposed visit before it is confirmed.",
                        section="scheduling",
                    ),
                ]
            return [
                _action(
                    "open_job_detail",
                    "Open job",
                    "Waiting for the client to confirm your proposed visit time.",
                    section="navigation",
                )
            ]

        if ss == "confirmed":
            return [
                _action(
                    "start_job",
                    "Start job",
                    "Mark the job in progress when you arrive or begin work.",
                    section="execution",
                ),
                _action(
                    "mark_no_access",
                    "Mark no access",
                    "Record that the visit could not go ahead (property not accessible, etc.). Your client can reschedule.",
                    section="scheduling",
                ),
                _action(
                    "reschedule_visit",
                    "Reschedule",
                    "Request a different visit time.",
                    section="scheduling",
                ),
                _action(
                    "cancel_scheduled_visit",
                    "Cancel visit",
                    "Cancel this scheduled visit window if the booking should be cleared.",
                    section="scheduling",
                ),
            ]

        return [
            _action(
                "propose_visit",
                "Propose time",
                "Suggest when you can attend the property.",
                section="scheduling",
            )
        ]

    if st == maintenance_service.STATUS_IN_PROGRESS:
        need = contractor_completion_proof_required(wo)
        has = contractor_has_completion_proof(wo)
        if need and not has:
            return [
                _action(
                    "upload_completion_proof",
                    "Upload proof",
                    "Upload certificate or photos before marking the job complete.",
                    section="evidence",
                ),
                _action(
                    "awaiting_parts",
                    "Awaiting parts",
                    "Pause the job until parts arrive.",
                    section="execution",
                ),
                _action(
                    "mark_no_access",
                    "Mark no access",
                    "Put the job on hold if the visit could not proceed.",
                    section="scheduling",
                ),
            ]
        return [
            _action("complete_job", "Complete job", "Mark work finished when the job is done.", section="execution"),
            _action(
                "awaiting_parts",
                "Awaiting parts",
                "Pause the job until parts arrive.",
                section="execution",
            ),
            _action(
                "mark_no_access",
                "Mark no access",
                "Put the job on hold if the visit could not proceed.",
                section="scheduling",
            ),
        ]

    if st == maintenance_service.STATUS_AWAITING_PARTS:
        need = contractor_completion_proof_required(wo)
        has = contractor_has_completion_proof(wo)
        primary_complete = not (need and not has)
        out = [
            _action(
                "resume_job",
                "Resume job",
                "Continue work when parts are on site.",
                section="execution",
            )
        ]
        if primary_complete:
            out.append(
                _action("complete_job", "Complete job", "Mark work finished when the job is done.", section="execution")
            )
        else:
            out.append(
                _action(
                    "upload_completion_proof",
                    "Upload proof",
                    "Upload certificate or photos before completing.",
                    section="evidence",
                )
            )
        out.append(
            _action(
                "mark_no_access",
                "Mark no access",
                "Put the job on hold if the visit could not proceed.",
                section="scheduling",
            )
        )
        return out

    return []


def _filter_contractor_actions_for_pricing(wo: Dict[str, Any], actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from services.work_order_pricing_service import (
        contractor_may_offer_complete_job,
        contractor_may_offer_start_job,
        contractor_may_propose_visit,
    )

    out: List[Dict[str, Any]] = []
    for a in actions:
        aid = a.get("id")
        if aid == "propose_visit" and not contractor_may_propose_visit(wo):
            continue
        if aid == "start_job" and not contractor_may_offer_start_job(wo):
            continue
        if aid == "complete_job" and not contractor_may_offer_complete_job(wo):
            continue
        out.append(a)
    return out


_CONTRACTOR_PUSH_ACTION_IDS = frozenset(
    {
        "accept_assignment",
        "decline_assignment",
        "confirm_visit",
        "upload_completion_proof",
        "submit_invoice",
        "edit_invoice",
        "submit_quote",
        "mark_inspection_complete",
        "start_job",
        "resume_job",
        "complete_job",
        "propose_visit",
        "awaiting_parts",
        "mark_no_access",
        "cancel_scheduled_visit",
        "reschedule_visit",
    }
)


def contractor_portal_waiting_on_others(wo: Dict[str, Any]) -> bool:
    """True when next_actions are navigation-only — contractor is waiting on client/system."""
    ids = [a.get("id") for a in (wo.get("next_actions") or []) if a.get("id")]
    if not ids:
        return False
    if any(i in _CONTRACTOR_PUSH_ACTION_IDS for i in ids):
        return False
    return all(i in ("open_job_detail", "view_invoice") for i in ids)


def _prepend_contractor_pricing_actions(wo: Dict[str, Any]) -> List[Dict[str, Any]]:
    from services.work_order_pricing_constants import (
        PRICE_STATUS_AWAITING_QUOTE,
        PRICE_STATUS_REJECTED,
        PRICE_STATUS_REVISION_REQUESTED,
        PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED,
    )
    from services.work_order_pricing_service import pricing_workflow_applies

    if not pricing_workflow_applies(wo):
        return []
    st = (wo.get("status") or "").strip().upper()
    if st in (maintenance_service.STATUS_OPEN, maintenance_service.STATUS_ASSIGNED):
        return []
    if not (wo.get("contractor_id") or "").strip():
        return []
    mode = (wo.get("pricing_mode") or "").strip().upper()
    ps = (wo.get("price_status") or "").strip().upper()
    extra: List[Dict[str, Any]] = []
    if mode == PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED and not wo.get("inspection_completed_at"):
        if st in (maintenance_service.STATUS_SCHEDULED, maintenance_service.STATUS_IN_PROGRESS):
            extra.append(
                _action(
                    "mark_inspection_complete",
                    "Mark inspection complete",
                    "After the inspection visit, confirm it is done; then submit a quote for any repair work.",
                    section="execution",
                )
            )
        return extra
    if ps in (PRICE_STATUS_AWAITING_QUOTE, PRICE_STATUS_REJECTED, PRICE_STATUS_REVISION_REQUESTED):
        is_revision = ps in (PRICE_STATUS_REJECTED, PRICE_STATUS_REVISION_REQUESTED)
        hint = (
            "The client requested changes to your quote — submit a revised price."
            if is_revision
            else "Propose a fixed price for this job for client approval before further work and invoicing."
        )
        label = "Submit revised quote" if is_revision else "Submit quote"
        extra.append(_action("submit_quote", label, hint, section="billing"))
    return extra


def apply_contractor_job_enrichment(
    wo: Dict[str, Any],
    *,
    invoice: Optional[Dict[str, Any]] = None,
) -> None:
    """Mutates work order dict in place for contractor portal list/detail responses."""
    wo["job_status"] = derive_canonical_job_status(wo)
    base_actions = contractor_next_job_actions(wo, invoice=invoice)
    merged = _prepend_contractor_pricing_actions(wo) + base_actions
    wo["next_actions"] = _filter_contractor_actions_for_pricing(wo, merged)
    wo["completion_proof_required"] = contractor_completion_proof_required(wo)
    wo["completion_proof_satisfied"] = contractor_has_completion_proof(wo)
    wo["timeline_events"] = client_job_timeline_events(wo)
    linked: Optional[Dict[str, Any]] = None
    if invoice:
        linked = {k: v for k, v in invoice.items() if k != "_id"}
        invoice_service.enrich_invoice_for_contractor_portal(linked)
    wo["linked_invoice"] = linked
    from services.work_order_pricing_service import serialize_pricing_snapshot

    wo["pricing"] = serialize_pricing_snapshot(wo)
    from services.work_order_schedule_service import serialize_schedule_snapshot, _enrich_schedule_snapshot_labels

    wo["scheduling"] = _enrich_schedule_snapshot_labels(serialize_schedule_snapshot(wo))


_ALLOWED_DECISION_ACTORS = frozenset({"client", "admin", "contractor"})


def normalize_decision_log_for_client(raw: Any) -> List[Dict[str, Any]]:
    """Sanitize persisted decision_log for API clients (message, actor, timestamp only)."""
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for x in raw:
        if not isinstance(x, dict):
            continue
        m = x.get("message")
        if m is None or not str(m).strip():
            continue
        actor = str(x.get("actor") or "unknown").strip().lower()
        if actor not in _ALLOWED_DECISION_ACTORS:
            actor = "unknown"
        out.append(
            {
                "message": str(m).strip()[:4000],
                "actor": actor,
                "timestamp": str(x.get("timestamp") or ""),
            }
        )
    return out


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


def client_job_sla_policy(wo: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Effective compliance SLA policy for API transparency. Uses stamped work order fields only;
    does not call the registry. Maintenance jobs → None. Legacy compliance jobs without stamps
    → default constants with policy_source \"default\".
    """
    kind = (wo.get("work_order_kind") or "").strip().upper() or WORK_ORDER_KIND_MAINTENANCE
    if kind != WORK_ORDER_KIND_COMPLIANCE:
        return None

    from services.compliance_rules_registry import (
        DEFAULT_COMPLIANCE_WO_SLA_COMPLETE_DAYS,
        DEFAULT_COMPLIANCE_WO_SLA_RESPOND_HOURS,
        DEFAULT_COMPLIANCE_WO_SLA_RISK_DAYS_BEFORE_COMPLETE,
        DEFAULT_COMPLIANCE_WO_SLA_RISK_HOURS_BEFORE_RESPOND,
    )

    jurisdiction = wo.get("jurisdiction")
    requirement_code = wo.get("requirement_code")

    def _defaults_payload() -> Dict[str, Any]:
        return {
            "jurisdiction": jurisdiction,
            "requirement_code": requirement_code,
            "compliance_sla_complete_days": DEFAULT_COMPLIANCE_WO_SLA_COMPLETE_DAYS,
            "compliance_sla_respond_hours": DEFAULT_COMPLIANCE_WO_SLA_RESPOND_HOURS,
            "compliance_sla_risk_days_before_complete": DEFAULT_COMPLIANCE_WO_SLA_RISK_DAYS_BEFORE_COMPLETE,
            "compliance_sla_risk_hours_before_respond": DEFAULT_COMPLIANCE_WO_SLA_RISK_HOURS_BEFORE_RESPOND,
            "policy_source": "default",
        }

    if wo.get("compliance_sla_complete_days") is None:
        return _defaults_payload()

    try:
        cd = int(wo["compliance_sla_complete_days"])
        rh = int(wo["compliance_sla_respond_hours"])
        rd = int(wo["compliance_sla_risk_days_before_complete"])
        rr = int(wo["compliance_sla_risk_hours_before_respond"])
    except (TypeError, ValueError, KeyError):
        return _defaults_payload()

    return {
        "jurisdiction": jurisdiction,
        "requirement_code": requirement_code,
        "compliance_sla_complete_days": cd,
        "compliance_sla_respond_hours": rh,
        "compliance_sla_risk_days_before_complete": rd,
        "compliance_sla_risk_hours_before_respond": rr,
        "policy_source": "compliance_registry",
    }


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
        "jurisdiction": wo.get("jurisdiction"),
        "next_actions": next_job_actions(wo),
        "timeline_events": client_job_timeline_events(wo),
        "decision_log": normalize_decision_log_for_client(wo.get("decision_log")),
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
    base["sla_policy"] = client_job_sla_policy(wo)
    from services.work_order_pricing_service import serialize_pricing_snapshot

    base["pricing"] = serialize_pricing_snapshot(wo)
    from services.work_order_schedule_service import serialize_schedule_snapshot, _enrich_schedule_snapshot_labels

    base["scheduling"] = _enrich_schedule_snapshot_labels(serialize_schedule_snapshot(wo))
    base["workflow_mode"] = base["scheduling"].get("workflow_mode")
    return base


def serialize_compliance_job(wo: Dict[str, Any]) -> Dict[str, Any]:
    """Backward-compatible alias; prefer serialize_client_job."""
    return serialize_client_job(wo)


def _requirement_workflow_status_labels(workflow_status: str, compliance_state: str) -> Dict[str, str]:
    """Human-facing labels for portal intelligence surfaces (never show raw enum tokens alone)."""
    ws = (workflow_status or "").strip().upper()
    cs = (compliance_state or "").strip().upper()
    ws_labels = {
        "NOT_APPLICABLE": "Not applicable",
        "IN_PROGRESS": "In progress",
        "COMPLIANT": "Compliant",
        "OVERDUE": "Overdue",
        "ACTION_REQUIRED": "Action required",
    }
    cs_labels = {
        "NOT_APPLICABLE": "Not applicable",
        "PENDING_VERIFICATION": "Pending verification",
        "VALID": "Verified and current",
        "OVERDUE": "Overdue",
        "MISSING": "Evidence missing",
        "EXPIRING": "Expiring soon",
    }
    return {
        "workflow_status_label": ws_labels.get(ws, ws.replace("_", " ").title() if ws else "—"),
        "compliance_state_label": cs_labels.get(cs, cs.replace("_", " ").title() if cs else "—"),
    }


def derive_requirement_workflow_fields(
    req: Dict[str, Any],
    *,
    active_compliance_job: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """UI-oriented status/compliance_state without mutating stored requirement rows."""
    app = (req.get("applicability") or "").strip().upper()
    raw_status = (req.get("status") or "").strip().upper()
    if app == "NOT_REQUIRED" or raw_status == "NOT_REQUIRED":
        base = {
            "workflow_status": "NOT_APPLICABLE",
            "compliance_state": "NOT_APPLICABLE",
        }
        return {**base, **_requirement_workflow_status_labels(base["workflow_status"], base["compliance_state"])}
    if active_compliance_job:
        base = {
            "workflow_status": "IN_PROGRESS",
            "compliance_state": "PENDING_VERIFICATION",
        }
        return {**base, **_requirement_workflow_status_labels(base["workflow_status"], base["compliance_state"])}
    if raw_status == "COMPLIANT":
        base = {"workflow_status": "COMPLIANT", "compliance_state": "VALID"}
        return {**base, **_requirement_workflow_status_labels(base["workflow_status"], base["compliance_state"])}
    if raw_status == "OVERDUE":
        base = {"workflow_status": "OVERDUE", "compliance_state": "OVERDUE"}
        return {**base, **_requirement_workflow_status_labels(base["workflow_status"], base["compliance_state"])}
    if raw_status == "EXPIRING_SOON":
        base = {"workflow_status": "ACTION_REQUIRED", "compliance_state": "EXPIRING"}
        return {**base, **_requirement_workflow_status_labels(base["workflow_status"], base["compliance_state"])}
    if raw_status == "PENDING":
        base = {"workflow_status": "ACTION_REQUIRED", "compliance_state": "MISSING"}
        return {**base, **_requirement_workflow_status_labels(base["workflow_status"], base["compliance_state"])}
    base = {"workflow_status": "ACTION_REQUIRED", "compliance_state": "MISSING"}
    return {**base, **_requirement_workflow_status_labels(base["workflow_status"], base["compliance_state"])}


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
