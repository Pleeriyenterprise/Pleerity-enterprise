"""
Canonical operational continuation resolution for cross-surface CTA coherence.

When active lineage exists, surfaces must show continuation (not workflow creation).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.maintenance_wo_from_issue_idempotency import find_existing_work_order_for_issue
from services.risk_signal_wo_idempotency import find_active_work_order_for_risk_signal

ISSUE_TERMINAL = frozenset({"closed", "cancelled", "resolved"})
WO_TERMINAL = frozenset({"COMPLETED", "VERIFIED", "CLOSED", "CANCELLED"})


def _job_path(work_order_id: str) -> str:
    return f"/operations/jobs/{work_order_id}"


def _wo_list_path(work_order_id: str) -> str:
    return f"/operations/work-orders?work_order_id={work_order_id}"


def _continuation_label_for_work_order(wo: Dict[str, Any]) -> str:
    from services.compliance_workflow_service import derive_canonical_job_status, next_job_actions

    canonical = derive_canonical_job_status(wo)
    actions = next_job_actions(wo)
    if actions:
        return str(actions[0].get("label") or "Continue workflow")
    labels = {
        "ASSIGNED": "Awaiting contractor",
        "BOOKED": "Inspection scheduled",
        "BOOKING_REQUESTED": "Confirm visit",
        "IN_PROGRESS": "Job in progress",
        "AWAITING_PARTS": "Awaiting parts",
        "NO_ACCESS": "No access — follow up",
        "SCHEDULED": "Visit scheduled",
        "OPEN": "View workflow",
        "COMPLETED": "Review completion",
    }
    return labels.get(canonical, "View workflow")


def _continuation_state_for_work_order(wo: Dict[str, Any]) -> str:
    from services.compliance_workflow_service import derive_canonical_job_status

    return derive_canonical_job_status(wo)


def build_continuation_envelope(
    *,
    existing_work_order_id: Optional[str],
    existing_issue_id: Optional[str],
    work_order: Optional[Dict[str, Any]] = None,
    user_safe_reason: Optional[str] = None,
) -> Dict[str, Any]:
    wo = work_order or {}
    wo_id = existing_work_order_id or wo.get("work_order_id")
    if not wo_id:
        return {
            "mode": "create",
            "has_active_lineage": False,
        }
    label = _continuation_label_for_work_order(wo) if wo else "View workflow"
    state = _continuation_state_for_work_order(wo) if wo else "ACTIVE"
    reason = user_safe_reason or (
        "An active maintenance workflow already exists for this operational objective. "
        "Continue the existing workflow instead of starting a new one."
    )
    return {
        "mode": "continuation",
        "has_active_lineage": True,
        "existing_work_order_id": wo_id,
        "existing_issue_id": existing_issue_id,
        "continuation_state": state,
        "continuation_cta": {
            "key": "view_workflow",
            "label": label,
            "url": _job_path(str(wo_id)),
        },
        "user_safe_reason": reason,
    }


def merge_continuation_into_payload(payload: Dict[str, Any], continuation: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload)
    out["operational_continuation"] = continuation
    if continuation.get("has_active_lineage"):
        out["idempotent_replay"] = True
        if continuation.get("existing_work_order_id"):
            out["existing_work_order_id"] = continuation["existing_work_order_id"]
    return out


async def resolve_continuation_for_risk_signal(
    signal_doc: Dict[str, Any],
    client_id: str,
) -> Dict[str, Any]:
    signal_id = (signal_doc.get("signal_id") or "").strip()
    if not signal_id:
        return {"mode": "create", "has_active_lineage": False}

    propagation = signal_doc.get("propagation") if isinstance(signal_doc.get("propagation"), dict) else {}
    prop_wo = (propagation.get("work_order_id") or "").strip()
    prop_issue = (propagation.get("issue_id") or "").strip()

    from database import database
    from services import maintenance_service

    db = database.get_db()
    wo_doc = None
    wo_id = prop_wo or None
    if wo_id:
        wo_doc = await maintenance_service.get_work_order(wo_id)
        if wo_doc and (wo_doc.get("status") or "").upper() in WO_TERMINAL:
            wo_doc = None
            wo_id = None
    if not wo_doc:
        wo_doc = await find_active_work_order_for_risk_signal(db, signal_id=signal_id, client_id=client_id)
        wo_id = (wo_doc or {}).get("work_order_id")

    issue_id = prop_issue or None
    if not wo_doc:
        return build_continuation_envelope(
            existing_work_order_id=None,
            existing_issue_id=issue_id,
        )

    return build_continuation_envelope(
        existing_work_order_id=str(wo_id) if wo_id else None,
        existing_issue_id=issue_id,
        work_order=wo_doc,
    )


async def resolve_continuation_for_issue(issue_doc: Dict[str, Any], client_id: str) -> Dict[str, Any]:
    issue_id = (issue_doc.get("issue_id") or "").strip()
    if not issue_id:
        return {"mode": "create", "has_active_lineage": False}
    if (issue_doc.get("status") or "").lower() in ISSUE_TERMINAL:
        return {"mode": "create", "has_active_lineage": False}

    wo_doc = await find_existing_work_order_for_issue(issue_id, client_id)
    if not wo_doc:
        return build_continuation_envelope(existing_work_order_id=None, existing_issue_id=issue_id)

    return build_continuation_envelope(
        existing_work_order_id=wo_doc.get("work_order_id"),
        existing_issue_id=issue_id,
        work_order=wo_doc,
    )


async def enrich_risk_signals_with_continuation(signals: List[Dict[str, Any]], client_id: str) -> None:
    for s in signals:
        cont = await resolve_continuation_for_risk_signal(s, client_id)
        s["operational_continuation"] = cont
        if cont.get("has_active_lineage"):
            s["suggested_actions_suppressed_reason"] = cont.get("user_safe_reason")


async def enrich_issue_with_continuation(issue_doc: Dict[str, Any], client_id: str) -> Dict[str, Any]:
    cont = await resolve_continuation_for_issue(issue_doc, client_id)
    out = dict(issue_doc)
    out["operational_continuation"] = cont
    if cont.get("existing_work_order_id"):
        out["linked_work_order_id"] = cont["existing_work_order_id"]
    return out
