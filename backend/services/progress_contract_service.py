"""
Canonical progress contract (progress_contract_v1) for work-order lifecycle parity.

Single source of operational truth for progress steps, current stage, and primary next action
across landlord, contractor, and admin surfaces.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple

from services import maintenance_service
from services.compliance_workflow_service import (
    contractor_has_completion_proof,
    contractor_next_job_actions,
    derive_canonical_job_status,
    next_job_actions,
)
from services.work_order_pricing_constants import (
    PRICE_STATUS_APPROVED,
    PRICE_STATUS_AWAITING_QUOTE,
    PRICE_STATUS_QUOTED,
    PRICE_STATUS_REJECTED,
    PRICE_STATUS_REVISION_REQUESTED,
)
from services.work_order_pricing_service import pricing_workflow_applies, quote_is_approved_for_api
from services.work_order_workflow_constants import (
    WORKFLOW_MODE_INSPECTION_FIRST,
    WORKFLOW_MODE_QUOTE_FIRST,
    resolve_workflow_mode,
)
from services.workflow_timer_service import work_order_stall_context

Audience = Literal["landlord", "contractor", "admin"]
StepState = Literal["pending", "current", "complete", "blocked", "skipped"]

CONTRACT_VERSION = "progress_contract_v1"

_ALL_ROLES = frozenset({"landlord", "contractor", "admin"})

# --- Step definitions ---------------------------------------------------------

QUOTE_FIRST_STEP_KEYS = (
    "assigned",
    "quote_submitted",
    "quote_approved",
    "visit_booked",
    "work_started",
    "proof_uploaded",
    "proof_reviewed",
    "closed",
)

INSPECTION_FIRST_STEP_KEYS = (
    "assigned",
    "inspection_visit_booked",
    "inspection_completed",
    "quote_submitted",
    "quote_approved",
    "work_started",
    "proof_uploaded",
    "proof_reviewed",
    "closed",
)

_STEP_LABELS: Dict[str, Dict[str, str]] = {
    "assigned": {
        "landlord": "Contractor assigned",
        "contractor": "Assigned",
        "admin": "Assigned",
    },
    "quote_submitted": {
        "landlord": "Quote submitted",
        "contractor": "Quote submitted",
        "admin": "Quote submitted",
    },
    "quote_approved": {
        "landlord": "Quote approved",
        "contractor": "Quote approved",
        "admin": "Quote approved",
    },
    "visit_booked": {
        "landlord": "Visit booked",
        "contractor": "Scheduled",
        "admin": "Booked / scheduled",
    },
    "inspection_visit_booked": {
        "landlord": "Inspection visit booked",
        "contractor": "Inspection scheduled",
        "admin": "Inspection booked",
    },
    "inspection_completed": {
        "landlord": "Inspection completed",
        "contractor": "Inspection completed",
        "admin": "Inspection completed",
    },
    "work_started": {
        "landlord": "Work started",
        "contractor": "In progress",
        "admin": "In progress",
    },
    "proof_uploaded": {
        "landlord": "Work completed",
        "contractor": "Proof submitted",
        "admin": "Execution recorded",
    },
    "proof_reviewed": {
        "landlord": "Proof reviewed",
        "contractor": "Reviewed",
        "admin": "Review pending",
    },
    "closed": {
        "landlord": "Closed",
        "contractor": "Closed",
        "admin": "Closed",
    },
}

_STEP_EXPLANATIONS: Dict[str, str] = {
    "assigned": "A contractor is linked to this job.",
    "quote_submitted": "Contractor has submitted a price for client review.",
    "quote_approved": "Client has approved the quote; field work may proceed.",
    "visit_booked": "A visit time is confirmed on the calendar.",
    "inspection_visit_booked": "An inspection visit is confirmed before quoting repair work.",
    "inspection_completed": "The inspection visit is recorded complete.",
    "work_started": "On-site work has explicitly started (in progress).",
    "proof_uploaded": "Completion evidence has been uploaded.",
    "proof_reviewed": "Client or ops has verified the completion proof.",
    "closed": "Job is closed out.",
}

LANDLORD_NEXT_ACTION_PRIORITY = [
    "clear_operational_exception",
    "resume_after_parts",
    "accept_completion",
    "review_completion",
    "request_proof_clarification",
    "reject_completion",
    "verify",
    "propose_schedule",
    "request_booking",
    "reschedule_booking",
    "confirm_visit",
    "assign_contractor",
    "approve_quote",
    "request_quote_revision",
    "reject_quote_final",
    "link_document",
    "attach_completion_proof",
    "verify",
    "complete",
    "start",
    "awaiting_parts",
    "close_job",
    "set_operational_exception",
    "cancel_booking",
    "mark_no_access",
    "mark_reschedule_required",
    "cancel",
]

CONTRACTOR_NEXT_ACTION_PRIORITY = [
    "accept_assignment",
    "decline_assignment",
    "submit_quote",
    "mark_inspection_complete",
    "confirm_visit",
    "propose_visit",
    "start_job",
    "resume_job",
    "upload_completion_proof",
    "complete_job",
    "awaiting_parts",
    "reschedule_visit",
    "cancel_scheduled_visit",
    "submit_invoice",
    "edit_invoice",
    "view_invoice",
    "mark_no_access",
    "open_job_detail",
]

_TERMINAL = frozenset(
    {
        maintenance_service.STATUS_CANCELLED,
        maintenance_service.STATUS_CLOSED,
        maintenance_service.STATUS_VERIFIED,
    }
)

_EXECUTION_STARTED = frozenset(
    {
        maintenance_service.STATUS_IN_PROGRESS,
        maintenance_service.STATUS_AWAITING_PARTS,
        maintenance_service.STATUS_COMPLETED,
        maintenance_service.STATUS_VERIFIED,
        maintenance_service.STATUS_CLOSED,
    }
)


def _norm_status(wo: Dict[str, Any]) -> str:
    return (wo.get("status") or "").strip().upper()


def _norm_price_status(wo: Dict[str, Any]) -> str:
    return (wo.get("price_status") or "").strip().upper()


def _norm_schedule_status(wo: Dict[str, Any]) -> str:
    return (wo.get("schedule_status") or "").strip().lower()


def _visit_confirmed(wo: Dict[str, Any]) -> bool:
    return _norm_schedule_status(wo) == "confirmed" and bool((wo.get("scheduled_at") or "").strip())


def _visit_booked(wo: Dict[str, Any]) -> bool:
    if not _visit_confirmed(wo):
        return False
    mode = resolve_workflow_mode(wo)
    if mode == WORKFLOW_MODE_QUOTE_FIRST and pricing_workflow_applies(wo) and not _quote_approved(wo):
        return False
    return True


def _quote_submitted(wo: Dict[str, Any]) -> bool:
    ps = _norm_price_status(wo)
    if not ps or ps == PRICE_STATUS_AWAITING_QUOTE:
        return False
    return True


def _quote_approved(wo: Dict[str, Any]) -> bool:
    if not pricing_workflow_applies(wo):
        return True
    return quote_is_approved_for_api(wo)


def _work_started(wo: Dict[str, Any]) -> bool:
    """True when on-site execution has begun (in progress or later)."""
    return _norm_status(wo) in _EXECUTION_STARTED


def _work_started_step_complete(wo: Dict[str, Any]) -> bool:
    """Progress step: complete once execution has moved past active in-progress."""
    st = _norm_status(wo)
    if st in (
        maintenance_service.STATUS_AWAITING_PARTS,
        maintenance_service.STATUS_COMPLETED,
        maintenance_service.STATUS_VERIFIED,
        maintenance_service.STATUS_CLOSED,
    ):
        return True
    return False


def _proof_uploaded(wo: Dict[str, Any]) -> bool:
    st = _norm_status(wo)
    if st in (
        maintenance_service.STATUS_COMPLETED,
        maintenance_service.STATUS_VERIFIED,
        maintenance_service.STATUS_CLOSED,
    ):
        return True
    if not _work_started(wo):
        return False
    if contractor_has_completion_proof(wo):
        return True
    cps = (wo.get("compliance_proof_status") or "").strip().upper()
    return cps in ("SUBMITTED", "APPROVED", "VERIFIED")


def _proof_reviewed(wo: Dict[str, Any]) -> bool:
    st = _norm_status(wo)
    if st in (maintenance_service.STATUS_VERIFIED, maintenance_service.STATUS_CLOSED):
        return True
    cps = (wo.get("compliance_proof_status") or "").strip().upper()
    return cps in ("APPROVED", "VERIFIED")


def _closed(wo: Dict[str, Any]) -> bool:
    return _norm_status(wo) == maintenance_service.STATUS_CLOSED


def _assigned(wo: Dict[str, Any]) -> bool:
    """True only when a contractor_id is linked — status alone must not imply assignment."""
    st = _norm_status(wo)
    if st == maintenance_service.STATUS_CANCELLED:
        return False
    return bool((wo.get("contractor_id") or "").strip())


def _assigned_step_label(key: str, audience: Audience, wo: Dict[str, Any], *, complete: bool) -> str:
    """Prefer factual assignment; surface drift when status suggests assignment without contractor_id."""
    if key != "assigned":
        return _STEP_LABELS.get(key, {}).get(audience, key.replace("_", " ").title())
    has_contractor = bool((wo.get("contractor_id") or "").strip())
    if has_contractor or complete:
        return _STEP_LABELS["assigned"][audience]
    if audience == "landlord":
        return "Awaiting contractor assignment"
    if audience == "contractor":
        return "Assignment needed"
    return "Assignment needed"


def _inspection_completed(wo: Dict[str, Any]) -> bool:
    if wo.get("inspection_completed_at"):
        return True
    if _quote_submitted(wo) and resolve_workflow_mode(wo) == WORKFLOW_MODE_INSPECTION_FIRST:
        return True
    return _work_started(wo)


def _derive_work_execution_status(wo: Dict[str, Any]) -> str:
    st = _norm_status(wo)
    if st in (maintenance_service.STATUS_VERIFIED, maintenance_service.STATUS_CLOSED):
        return "CLOSED" if st == maintenance_service.STATUS_CLOSED else "VERIFIED"
    if st == maintenance_service.STATUS_COMPLETED:
        return "COMPLETED"
    if st in (maintenance_service.STATUS_IN_PROGRESS, maintenance_service.STATUS_AWAITING_PARTS):
        return st
    if st == maintenance_service.STATUS_CANCELLED:
        return "CANCELLED"
    return "NOT_STARTED"


def _derive_proof_status(wo: Dict[str, Any]) -> str:
    if _proof_reviewed(wo):
        return "REVIEWED"
    if _proof_uploaded(wo):
        return "UPLOADED"
    return "NOT_UPLOADED"


def _derive_invoice_status(invoice: Optional[Dict[str, Any]]) -> str:
    if not invoice:
        return "NONE"
    raw = (invoice.get("status") or "").strip().lower()
    return raw.upper() if raw else "NONE"


def _step_completion_flags(wo: Dict[str, Any], step_keys: Tuple[str, ...]) -> Dict[str, bool]:
    flags = {
        "assigned": _assigned(wo),
        "quote_submitted": _quote_submitted(wo),
        "quote_approved": _quote_approved(wo),
        "visit_booked": _visit_booked(wo),
        "inspection_visit_booked": _visit_confirmed(wo),
        "inspection_completed": _inspection_completed(wo),
        "work_started": _work_started_step_complete(wo),
        "proof_uploaded": _proof_uploaded(wo),
        "proof_reviewed": _proof_reviewed(wo),
        "closed": _closed(wo),
    }
    return {k: flags.get(k, False) for k in step_keys}


def _skipped_step_keys(wo: Dict[str, Any], step_keys: Tuple[str, ...]) -> frozenset:
    skipped: set = set()
    if not pricing_workflow_applies(wo):
        skipped.update({"quote_submitted", "quote_approved"})
    mode = resolve_workflow_mode(wo)
    if mode == WORKFLOW_MODE_QUOTE_FIRST:
        skipped.update({"inspection_visit_booked", "inspection_completed"})
    if mode == WORKFLOW_MODE_INSPECTION_FIRST:
        skipped.add("visit_booked")
    return frozenset(k for k in skipped if k in step_keys)


def _resolve_step_states(
    wo: Dict[str, Any],
    step_keys: Tuple[str, ...],
) -> Tuple[str, List[Dict[str, Any]]]:
    """Return (current_stage_key, raw step dicts with completion booleans)."""
    completion = _step_completion_flags(wo, step_keys)
    skipped = _skipped_step_keys(wo, step_keys)
    st = _norm_status(wo)
    oe = (wo.get("operational_exception") or "").strip().upper()

    raw_steps: List[Dict[str, Any]] = []
    current_key = step_keys[-1]

    if st == maintenance_service.STATUS_CANCELLED:
        for key in step_keys:
            raw_steps.append({"key": key, "complete": False, "skipped": key in skipped, "blocked": False})
        return "cancelled", raw_steps

    # Explicit in-progress execution: work_started is current, not yet complete.
    if st == maintenance_service.STATUS_IN_PROGRESS and "work_started" in step_keys and "work_started" not in skipped:
        current_key = "work_started"
        found_current = True
        for key in step_keys:
            if key in skipped:
                raw_steps.append({"key": key, "complete": False, "skipped": True, "blocked": False})
                continue
            if key == "work_started":
                raw_steps.append({"key": key, "complete": False, "skipped": False, "blocked": bool(oe)})
                continue
            if completion.get(key, False):
                raw_steps.append({"key": key, "complete": True, "skipped": False, "blocked": False})
            else:
                raw_steps.append({"key": key, "complete": False, "skipped": False, "blocked": False})
        return current_key, raw_steps

    found_current = False
    for key in step_keys:
        if key in skipped:
            raw_steps.append({"key": key, "complete": False, "skipped": True, "blocked": False})
            continue
        complete = completion.get(key, False)
        blocked = bool(oe) and key in ("work_started", "proof_uploaded", "proof_reviewed", "closed") and not complete
        if found_current:
            raw_steps.append({"key": key, "complete": False, "skipped": False, "blocked": blocked})
            continue
        if complete:
            raw_steps.append({"key": key, "complete": True, "skipped": False, "blocked": False})
            continue
        raw_steps.append({"key": key, "complete": False, "skipped": False, "blocked": blocked})
        current_key = key
        found_current = True

    if not found_current:
        current_key = step_keys[-1]
        for i, rs in enumerate(raw_steps):
            if rs["key"] == current_key and not rs.get("skipped"):
                raw_steps[i] = {**rs, "complete": True}

    return current_key, raw_steps


def _materialize_steps(
    raw_steps: List[Dict[str, Any]],
    *,
    audience: Audience,
    current_key: str,
    wo: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for rs in raw_steps:
        key = rs["key"]
        if rs.get("skipped"):
            state: StepState = "skipped"
        elif rs.get("complete"):
            state = "complete"
        elif key == current_key:
            state = "blocked" if rs.get("blocked") else "current"
        else:
            state = "pending"
        label = (
            _assigned_step_label(key, audience, wo or {}, complete=bool(rs.get("complete")))
            if wo is not None
            else _STEP_LABELS.get(key, {}).get(audience, key.replace("_", " ").title())
        )
        out.append(
            {
                "key": key,
                "label": label,
                "state": state,
                "visible_to_roles": sorted(_ALL_ROLES),
                "explanation": _STEP_EXPLANATIONS.get(key, ""),
            }
        )
    return out


def _resolve_primary_action(
    actions: List[Dict[str, Any]],
    *,
    audience: Audience,
    wo: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    na = [a for a in (actions or []) if a.get("id") and a.get("id") != "none"]
    if not na:
        return None

    ps = _norm_price_status(wo)
    if audience in ("landlord", "admin") and ps == PRICE_STATUS_QUOTED:
        approve = next((a for a in na if a.get("id") == "approve_quote"), None)
        if approve:
            return dict(approve)

    from services.completion_workflow_transition_service import is_awaiting_completion_review

    if is_awaiting_completion_review(wo):
        for aid in ("accept_completion", "review_completion", "verify", "request_proof_clarification"):
            match = next((a for a in na if a.get("id") == aid), None)
            if match:
                return dict(match)

    priority = LANDLORD_NEXT_ACTION_PRIORITY if audience == "landlord" else CONTRACTOR_NEXT_ACTION_PRIORITY
    if audience == "admin":
        priority = LANDLORD_NEXT_ACTION_PRIORITY

    for aid in priority:
        for a in na:
            if a.get("id") == aid:
                return dict(a)

    # Contractor: do not surface mark_no_access as primary when quote approval is pending.
    if audience == "contractor" and not _quote_approved(wo) and pricing_workflow_applies(wo):
        ps = _norm_price_status(wo)
        if ps in (PRICE_STATUS_QUOTED, PRICE_STATUS_REVISION_REQUESTED, PRICE_STATUS_REJECTED):
            waiting = next((a for a in na if a.get("id") == "open_job_detail"), None)
            if waiting:
                return dict(waiting)
            return {
                "id": "open_job_detail",
                "label": "Waiting on client",
                "hint": "The client must approve your quote before you can start work or attend as execution.",
                "section": "navigation",
            }

    return dict(na[0])


def _current_stage_label(steps: List[Dict[str, Any]], audience: Audience) -> str:
    for s in steps:
        if s.get("state") == "current":
            return str(s.get("label") or "")
    for s in reversed(steps):
        if s.get("state") == "complete":
            return str(s.get("label") or "")
    return ""


def _waiting_on(
    wo: Dict[str, Any],
    *,
    audience: Audience,
    stall: Optional[Dict[str, Any]],
) -> Optional[str]:
    if stall and stall.get("waiting_on"):
        return str(stall["waiting_on"])
    st = _norm_status(wo)
    if st in _TERMINAL:
        return None
    if not _quote_approved(wo) and pricing_workflow_applies(wo):
        ps = _norm_price_status(wo)
        if ps == PRICE_STATUS_AWAITING_QUOTE:
            return "contractor"
        if ps in (PRICE_STATUS_QUOTED, PRICE_STATUS_REVISION_REQUESTED, PRICE_STATUS_REJECTED):
            return "landlord"
    ss = _norm_schedule_status(wo)
    if ss == "proposed" and wo.get("scheduled_at"):
        sb = (wo.get("scheduled_by") or "").strip().lower()
        return "landlord" if sb == "contractor" else "contractor"
    if _visit_confirmed(wo) and not _work_started(wo):
        if _quote_approved(wo) or not pricing_workflow_applies(wo):
            return "contractor"
    return None


def _headline_for_audience(wo: Dict[str, Any], *, audience: Audience, current_stage_label: str) -> str:
    from services.completion_workflow_transition_service import is_awaiting_completion_review

    if is_awaiting_completion_review(wo):
        if audience == "contractor":
            return "Completion proof submitted — awaiting review."
        return "Completion proof submitted — awaiting review."

    canonical = derive_canonical_job_status(wo)
    st = _norm_status(wo)
    if st == maintenance_service.STATUS_CANCELLED:
        return "Job cancelled"
    if current_stage_label:
        if audience == "landlord":
            if canonical == "BOOKED" and not _work_started(wo):
                return "Visit booked — awaiting completion"
            if canonical == "IN_PROGRESS":
                return "Work in progress"
            if st == maintenance_service.STATUS_COMPLETED:
                return "Work complete — review proof"
            if canonical in ("VERIFIED", "CLOSED"):
                return "Verified — close-out may remain" if canonical == "VERIFIED" else "Job closed"
        return current_stage_label
    return current_stage_label or canonical.replace("_", " ").title()


def build_progress_contract_v1(
    wo: Dict[str, Any],
    *,
    audience: Audience,
    next_actions: Optional[List[Dict[str, Any]]] = None,
    invoice: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build shared progress_contract_v1 payload for landlord, contractor, or admin."""
    mode = resolve_workflow_mode(wo)
    step_keys = INSPECTION_FIRST_STEP_KEYS if mode == WORKFLOW_MODE_INSPECTION_FIRST else QUOTE_FIRST_STEP_KEYS

    if next_actions is None:
        if audience == "contractor":
            next_actions = contractor_next_job_actions(wo, invoice=invoice)
        else:
            next_actions = next_job_actions(wo)

    current_key, raw_steps = _resolve_step_states(wo, step_keys)
    progress_steps = _materialize_steps(raw_steps, audience=audience, current_key=current_key, wo=wo)
    stage_label = _current_stage_label(progress_steps, audience)
    stall = work_order_stall_context(wo)
    primary = _resolve_primary_action(next_actions, audience=audience, wo=wo)
    waiting = _waiting_on(wo, audience=audience, stall=stall)

    role_actions = {
        "landlord": next_job_actions(wo) if audience != "landlord" else next_actions,
        "contractor": contractor_next_job_actions(wo, invoice=invoice) if audience != "contractor" else next_actions,
        "admin": next_job_actions(wo),
    }

    return {
        "version": CONTRACT_VERSION,
        "workflow_mode": mode,
        "canonical_status": derive_canonical_job_status(wo),
        "persisted_status": _norm_status(wo),
        "price_status": _norm_price_status(wo) or None,
        "schedule_status": _norm_schedule_status(wo) or None,
        "work_execution_status": _derive_work_execution_status(wo),
        "proof_status": _derive_proof_status(wo),
        "invoice_status": _derive_invoice_status(invoice),
        "current_stage": current_key,
        "current_stage_label": stage_label,
        "headline": _headline_for_audience(wo, audience=audience, current_stage_label=stage_label),
        "waiting_on": waiting,
        "next_primary_action": primary,
        "progress_steps": progress_steps,
        "role_specific_actions": {
            k: v for k, v in role_actions.items()
        },
    }


def attach_progress_contract(
    wo: Dict[str, Any],
    *,
    audience: Audience,
    invoice: Optional[Dict[str, Any]] = None,
) -> None:
    """Mutates work order dict in place with progress_contract."""
    actions = wo.get("next_actions")
    wo["progress_contract"] = build_progress_contract_v1(
        wo,
        audience=audience,
        next_actions=actions if isinstance(actions, list) else None,
        invoice=invoice,
    )
