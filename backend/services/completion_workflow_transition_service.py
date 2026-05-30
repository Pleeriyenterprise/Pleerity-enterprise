"""
Authoritative completion proof → review → invoice convergence transitions.

Proof upload must advance operational workflow state — not only store files.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from services import compliance_workflow_service as cws
from services import maintenance_service as ms
from services.work_order_execution_constants import (
    COMPLETION_REVIEW_ACCEPTED,
    COMPLETION_REVIEW_CLARIFICATION_REQUESTED,
    COMPLETION_REVIEW_PENDING,
    COMPLETION_REVIEW_REJECTED,
    COMPLIANCE_BOOKING_OPERATIONALLY_COMPLETE,
    COMPLIANCE_PROOF_SUBMITTED,
    COMPLIANCE_PROOF_VERIFIED,
    OPERATIONAL_STATUS_WORK_COMPLETED_PENDING_REVIEW,
    WORK_ORDER_KIND_COMPLIANCE,
)
from services.work_order_schedule_constants import SCHEDULE_STATUS_COMPLETED

logger = logging.getLogger(__name__)

_POST_EXECUTION_TERMINAL = frozenset(
    {
        ms.STATUS_COMPLETED,
        ms.STATUS_VERIFIED,
        ms.STATUS_CLOSED,
    }
)

_POST_EXECUTION_VISIT_ACTION_IDS = frozenset(
    {
        "propose_visit",
        "confirm_visit",
        "reschedule_visit",
        "cancel_scheduled_visit",
        "mark_no_access",
        "reschedule_booking",
        "cancel_booking",
        "request_booking",
        "propose_schedule",
        "request_visit_reschedule",
        "mark_reschedule_required",
    }
)

_LANDLORD_SCHEDULING_ACTION_IDS = frozenset(
    _POST_EXECUTION_VISIT_ACTION_IDS
    | {
        "start",
        "approve_quote",
        "request_quote_revision",
        "reject_quote_final",
    }
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_awaiting_completion_review(wo: Dict[str, Any]) -> bool:
    op = (wo.get("operational_status") or "").strip().upper()
    if op == OPERATIONAL_STATUS_WORK_COMPLETED_PENDING_REVIEW:
        return True
    review = (wo.get("completion_review_status") or "").strip().upper()
    st = (wo.get("status") or "").strip().upper()
    if st == ms.STATUS_COMPLETED and review == COMPLETION_REVIEW_PENDING:
        return True
    return False


def post_execution_visit_controls_locked(wo: Dict[str, Any]) -> bool:
    if wo.get("visit_controls_locked"):
        return True
    if is_awaiting_completion_review(wo):
        return True
    st = (wo.get("status") or "").strip().upper()
    if st in _POST_EXECUTION_TERMINAL:
        return True
    if cws.contractor_has_completion_proof(wo) and st in (
        ms.STATUS_COMPLETED,
        ms.STATUS_VERIFIED,
        ms.STATUS_CLOSED,
    ):
        return True
    return False


def collapse_post_execution_visit_controls() -> Dict[str, Any]:
    """Marker fields applied when execution is recorded via proof upload."""
    return {"visit_controls_locked": True}


def suppress_invalid_post_completion_actions(actions: List[Dict[str, Any]], wo: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not post_execution_visit_controls_locked(wo):
        return actions
    blocked = _POST_EXECUTION_VISIT_ACTION_IDS | {"start_job", "start", "accept_assignment", "decline_assignment"}
    if is_awaiting_completion_review(wo):
        blocked = blocked | {"complete_job", "upload_completion_proof"}
    return [a for a in actions if a.get("id") not in blocked]


def generate_completion_review_actions(wo: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Landlord/admin review CTAs after completion proof submitted."""
    from services.compliance_workflow_service import _action

    review = (wo.get("completion_review_status") or "").strip().upper()
    if review == COMPLETION_REVIEW_CLARIFICATION_REQUESTED:
        return [
            _action(
                "review_completion",
                "Review completion proof",
                "You asked for clarification — review the contractor's response when ready.",
                section="execution",
            ),
        ]
    if review == COMPLETION_REVIEW_REJECTED:
        return [
            _action(
                "review_completion",
                "Review completion again",
                "Completion was rejected — review updated proof when the contractor resubmits.",
                section="execution",
            ),
        ]
    return [
        _action(
            "accept_completion",
            "Accept completion",
            "Confirm the work and proof meet your expectations before invoicing.",
            section="execution",
        ),
        _action(
            "request_proof_clarification",
            "Request clarification",
            "Ask the contractor to explain or replace the proof before you accept.",
            section="execution",
        ),
        _action(
            "reject_completion",
            "Reject completion",
            "Send the job back for further work if the proof is not acceptable.",
            section="execution",
        ),
        _action(
            "verify",
            "Verify and close",
            "Verify the job and linked evidence in your compliance workflow.",
            section="execution",
        ),
    ]


def generate_contractor_post_proof_actions(wo: Dict[str, Any]) -> List[Dict[str, Any]]:
    from services.compliance_workflow_service import _action

    review = (wo.get("completion_review_status") or "").strip().upper()
    if review == COMPLETION_REVIEW_CLARIFICATION_REQUESTED:
        hint = "Your client asked for clarification — upload revised proof or add a note on the job."
        label = "Clarification requested"
    elif review == COMPLETION_REVIEW_REJECTED:
        hint = "Completion was rejected — review the job and upload corrected proof when ready."
        label = "Completion rejected"
    elif review == COMPLETION_REVIEW_ACCEPTED:
        hint = "Your client accepted completion — you can submit your invoice when ready."
        label = "Completion accepted"
    else:
        hint = "Your client will review the proof — awaiting review before invoicing can proceed."
        label = "Completion proof submitted"
    return [
        _action(
            "open_job_detail",
            label,
            hint,
            section="navigation",
        ),
    ]


def maybe_apply_proof_upload_transition_fields(
    wo_after_evidence: Dict[str, Any],
    *,
    prev: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Return Mongo $set fields when completion proof upload should advance authoritative state.
    Idempotent when already in post-review terminal path.
    """
    if not cws.contractor_completion_proof_required(wo_after_evidence):
        return {}
    if not cws.contractor_has_completion_proof(wo_after_evidence):
        return {}

    st = (wo_after_evidence.get("status") or "").strip().upper()
    if st in (ms.STATUS_VERIFIED, ms.STATUS_CLOSED, ms.STATUS_CANCELLED):
        return {}

    prev_keys: Set[str] = set((prev or {}).get("evidence_keys") or [])
    new_keys = set(wo_after_evidence.get("evidence_keys") or [])
    if prev and new_keys == prev_keys:
        return {}

    # Already converged — ensure flags present only.
    if st == ms.STATUS_COMPLETED and is_awaiting_completion_review(wo_after_evidence):
        out = collapse_post_execution_visit_controls()
        if (wo_after_evidence.get("compliance_proof_status") or "").upper() != COMPLIANCE_PROOF_SUBMITTED:
            out["compliance_proof_status"] = COMPLIANCE_PROOF_SUBMITTED
        return out

    now = _now_iso()
    fields: Dict[str, Any] = {
        "status": ms.STATUS_COMPLETED,
        "operational_status": OPERATIONAL_STATUS_WORK_COMPLETED_PENDING_REVIEW,
        "completion_review_status": COMPLETION_REVIEW_PENDING,
        "compliance_proof_status": COMPLIANCE_PROOF_SUBMITTED,
        "completion_proof_submitted_at": now,
        "completed_at": wo_after_evidence.get("completed_at") or now,
        **collapse_post_execution_visit_controls(),
    }
    kind = (wo_after_evidence.get("work_order_kind") or "").strip().upper()
    if kind == WORK_ORDER_KIND_COMPLIANCE:
        fields["compliance_booking_status"] = COMPLIANCE_BOOKING_OPERATIONALLY_COMPLETE
    if (wo_after_evidence.get("scheduled_at") or "").strip() or (
        wo_after_evidence.get("schedule_status") or ""
    ).strip():
        fields["schedule_status"] = SCHEDULE_STATUS_COMPLETED
        fields["last_schedule_update_at"] = now
    return fields


def evaluate_completion_review_state(wo: Dict[str, Any]) -> str:
    review = (wo.get("completion_review_status") or "").strip().upper()
    if review in (
        COMPLETION_REVIEW_ACCEPTED,
        COMPLETION_REVIEW_CLARIFICATION_REQUESTED,
        COMPLETION_REVIEW_REJECTED,
        COMPLETION_REVIEW_PENDING,
    ):
        return review
    cps = (wo.get("compliance_proof_status") or "").strip().upper()
    if cps == COMPLIANCE_PROOF_VERIFIED:
        return COMPLETION_REVIEW_ACCEPTED
    if is_awaiting_completion_review(wo):
        return COMPLETION_REVIEW_PENDING
    return ""


def synchronize_progress_indicators(wo: Dict[str, Any]) -> None:
    """No-op hook — progress_contract_service reads authoritative fields directly."""
    return None


async def transition_after_completion_proof_upload(
    wo: Dict[str, Any],
    *,
    actor_id: Optional[str] = None,
    proof_event_id: Optional[str] = None,
) -> None:
    """Post-persist side effects: audit, timers."""
    from models.core import AuditAction
    from utils.audit import create_audit_log

    wid = (wo.get("work_order_id") or "").strip()
    if not wid:
        return

    await create_audit_log(
        action=AuditAction.WORKFLOW_COMPLETION_PROOF_SUBMITTED,
        actor_id=actor_id or wo.get("contractor_id") or "system",
        client_id=wo.get("client_id"),
        resource_type="work_order",
        resource_id=wid,
        metadata={
            "operational_status": wo.get("operational_status"),
            "completion_review_status": wo.get("completion_review_status"),
            "proof_event_id": proof_event_id,
        },
    )

    try:
        from services.workflow_timer_service import on_work_order_awaiting_completion_review

        await on_work_order_awaiting_completion_review(wid, actor_id=actor_id)
    except Exception as exc:
        logger.warning("Completion review timer update failed: %s", exc)


async def apply_completion_review_decision(
    work_order_id: str,
    decision: str,
    *,
    actor_id: str,
    note: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Landlord/admin completion review — authoritative state only."""
    from database import database

    decision = (decision or "").strip().upper()
    if decision not in (
        COMPLETION_REVIEW_ACCEPTED,
        COMPLETION_REVIEW_CLARIFICATION_REQUESTED,
        COMPLETION_REVIEW_REJECTED,
    ):
        raise ValueError("Invalid completion review decision")

    db = database.get_db()
    wo = await db.work_orders.find_one({"work_order_id": work_order_id}, {"_id": 0})
    if not wo:
        return None
    if not is_awaiting_completion_review(wo) and (wo.get("status") or "").upper() != ms.STATUS_COMPLETED:
        raise ValueError("This job is not awaiting completion review")

    now = _now_iso()
    set_fields: Dict[str, Any] = {
        "completion_review_status": decision,
        "updated_at": now,
    }
    if decision == COMPLETION_REVIEW_ACCEPTED:
        set_fields["operational_status"] = None
        set_fields["completion_review_accepted_at"] = now
    elif decision == COMPLETION_REVIEW_CLARIFICATION_REQUESTED:
        set_fields["completion_review_clarification_requested_at"] = now
    elif decision == COMPLETION_REVIEW_REJECTED:
        set_fields["operational_status"] = None
        set_fields["status"] = ms.STATUS_IN_PROGRESS
        set_fields["visit_controls_locked"] = False
        set_fields["completion_review_status"] = COMPLETION_REVIEW_REJECTED

    result = await db.work_orders.find_one_and_update(
        {"work_order_id": work_order_id},
        {"$set": set_fields},
        return_document=True,
    )
    if result:
        result.pop("_id", None)
        await transition_after_completion_review_decision(result, decision=decision, actor_id=actor_id)
    return result


async def transition_after_completion_review_decision(
    wo: Dict[str, Any],
    *,
    decision: str,
    actor_id: Optional[str] = None,
) -> None:
    from models.core import AuditAction
    from utils.audit import create_audit_log

    wid = (wo.get("work_order_id") or "").strip()
    audit_map = {
        COMPLETION_REVIEW_ACCEPTED: AuditAction.WORKFLOW_COMPLETION_ACCEPTED,
        COMPLETION_REVIEW_CLARIFICATION_REQUESTED: AuditAction.WORKFLOW_COMPLETION_CLARIFICATION_REQUESTED,
        COMPLETION_REVIEW_REJECTED: AuditAction.WORKFLOW_COMPLETION_REJECTED,
    }
    action = audit_map.get(decision)
    if action and wid:
        await create_audit_log(
            action=action,
            actor_id=actor_id or "client",
            client_id=wo.get("client_id"),
            resource_type="work_order",
            resource_id=wid,
            metadata={"completion_review_status": decision},
        )

    if decision == COMPLETION_REVIEW_ACCEPTED:
        try:
            from services.invoice_readiness_service import notify_invoice_unlocked_if_ready

            await notify_invoice_unlocked_if_ready(wo, actor_id=actor_id)
        except Exception as exc:
            logger.warning("Invoice unlock notification failed: %s", exc)
