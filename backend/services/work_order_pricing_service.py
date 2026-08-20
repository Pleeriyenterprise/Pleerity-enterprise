"""
Controlled quote / approval / invoice gating for compliance and maintenance work orders.

Legacy work orders without ``pricing_mode`` are exempt from enforcement (backward compatibility).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from auth import generate_secure_token, hash_token
from database import database
from models import AuditAction
from utils.audit import create_audit_log

from services.work_order_execution_constants import WORK_ORDER_KIND_COMPLIANCE, WORK_ORDER_KIND_MAINTENANCE
from services.work_order_workflow_constants import workflow_mode_for_create
from services.work_order_pricing_constants import (
    ALLOWED_PRICE_STATUSES,
    ALLOWED_PRICING_MODES,
    DEFAULT_PRICE_CURRENCY,
    PRICE_STATUS_APPROVED,
    PRICE_STATUS_AWAITING_QUOTE,
    PRICE_STATUS_QUOTED,
    PRICE_STATUS_REJECTED,
    PRICE_STATUS_REJECTED_FINAL,
    PRICE_STATUS_REVISION_REQUESTED,
    PRICE_STATUS_DISPUTED,
    QUOTE_NEGOTIATION_STATUS_LABELS,
    QUOTE_REVISION_REASON_CODES,
    PRICING_MODE_COMPLIANCE_FIXED_QUOTE,
    PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED,
    PRICING_MODE_MAINTENANCE_PREQUOTE,
)

logger = logging.getLogger(__name__)


def _contractor_job_token_ttl_days() -> int:
    raw = (os.getenv("CONTRACTOR_JOB_TOKEN_TTL_DAYS") or "").strip()
    if not raw:
        return 30
    try:
        n = int(raw)
        return max(1, min(n, 365))
    except ValueError:
        return 30


def _next_action_line_for_quote_approved(wo: Dict[str, Any]) -> str:
    """Short guidance for contractor email after client approves quote."""
    kind = (wo.get("work_order_kind") or "").strip().upper()
    if kind == WORK_ORDER_KIND_COMPLIANCE:
        return (
            "Schedule the visit, complete the work, and upload the required certificate or proof when finished."
        )
    mode = _norm_pricing_mode(wo)
    if mode == PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED:
        if not wo.get("inspection_completed_at"):
            return (
                "If the inspection visit is not yet complete, finish it first; then schedule and carry out the agreed repair work."
            )
        return "Schedule and carry out the agreed repair work."
    return "Schedule and carry out the agreed work."


async def _send_contractor_quote_approved_email(wo: Dict[str, Any], *, quote_approved_at: datetime) -> None:
    """Notify assigned contractor that the client approved the quote (orchestrator + message_logs)."""
    cid = (wo.get("client_id") or "").strip()
    wid = (wo.get("work_order_id") or "").strip()
    ctr = (wo.get("contractor_id") or "").strip()
    if not cid or not wid or not ctr:
        return
    db = database.get_db()
    contractor = await db.contractors.find_one(
        {"contractor_id": ctr},
        {"_id": 0, "email": 1, "name": 1, "company_name": 1},
    )
    to_email = (contractor or {}).get("email") if contractor else None
    if not to_email or not str(to_email).strip():
        return
    contractor_disp = (
        (str((contractor or {}).get("name") or "").strip())
        or (str((contractor or {}).get("company_name") or "").strip())
        or None
    )
    property_address = "Property"
    prop_id = wo.get("property_id")
    if prop_id:
        prop = await db.properties.find_one(
            {"property_id": prop_id, "client_id": cid},
            {"_id": 0, "address_line_1": 1, "city": 1, "postcode": 1},
        )
        if prop:
            parts = [prop.get("address_line_1"), prop.get("city"), prop.get("postcode")]
            property_address = ", ".join(p for p in parts if p) or property_address
    job_link_final = "See portal"
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        from utils.public_app_url import get_frontend_base_url

        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=_contractor_job_token_ttl_days())).isoformat()
        await db.contractor_job_tokens.insert_one({
            "token_hash": token_hash,
            "work_order_id": wid,
            "contractor_id": ctr,
            "created_at": now_iso,
            "expires_at": expires_at,
            "revoked_at": None,
        })
        base_url = get_frontend_base_url().rstrip("/")
        job_link_final = f"{base_url}/job?token={raw_token}"
    except Exception as exc:
        logger.warning("Contractor quote-approved email: job token failed (non-fatal): %s", exc)

    kind = (wo.get("work_order_kind") or "").strip().upper()
    is_compliance = kind == WORK_ORDER_KIND_COMPLIANCE
    next_action = _next_action_line_for_quote_approved(wo)
    from services.notification_orchestrator import notification_orchestrator

    await notification_orchestrator.send(
        template_key="CONTRACTOR_QUOTE_APPROVED",
        client_id=cid,
        context={
            "recipient": str(to_email).strip(),
            "subject": "Your quote has been approved",
            "contractor_name": contractor_disp or "",
            "property_address": property_address,
            "job_title": (wo.get("description") or "Work order")[:200],
            "work_order_id": wid,
            "approved_price": wo.get("quoted_price"),
            "price_currency": wo.get("price_currency") or DEFAULT_PRICE_CURRENCY,
            "secure_job_link": job_link_final,
            "next_action": next_action,
            "is_compliance": is_compliance,
        },
        idempotency_key=f"contractor_quote_approved:{wid}:{quote_approved_at.isoformat()}",
        event_type="CONTRACTOR_QUOTE_APPROVED",
    )


def _quote_resubmit_allowed_statuses() -> frozenset:
    return frozenset(
        {
            PRICE_STATUS_AWAITING_QUOTE,
            PRICE_STATUS_REJECTED,
            PRICE_STATUS_REVISION_REQUESTED,
        }
    )


def _iso_dt(value: Any) -> Any:
    if value and hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _next_quote_version(history: Optional[list]) -> int:
    if not history:
        return 1
    return max(int(h.get("version") or 0) for h in history) + 1


def _append_quote_history(
    wo: Dict[str, Any],
    entry: Dict[str, Any],
) -> list:
    history = list(wo.get("quote_negotiation_history") or [])
    history.append(entry)
    return history


def _history_shows_revised_quote(wo: Dict[str, Any]) -> bool:
    """True when the active quoted amount is a resubmission, not the first quote."""
    history = wo.get("quote_negotiation_history") or []
    if any(str(h.get("event") or "").strip().lower() == "resubmitted" for h in history):
        return True
    versions = []
    for h in history:
        try:
            versions.append(int(h.get("version") or 0))
        except (TypeError, ValueError):
            continue
    return max(versions) > 1 if versions else False


def derive_quote_presentation_state(wo: Dict[str, Any]) -> Dict[str, Any]:
    """
    Single quote-state authority for header, Billing, progress rail, and API payloads.

    Do not infer 'Quote approved' from an incomplete rail step. Approval is only
    PRICE_STATUS_APPROVED.
    """
    ps = _norm_price_status(wo)
    if not pricing_workflow_applies(wo):
        return {
            "key": "not_applicable",
            "label": None,
            "price_status": ps or None,
            "is_approved": True,
            "revision_active": False,
        }
    if ps == PRICE_STATUS_APPROVED:
        key, label = "quote_approved", QUOTE_NEGOTIATION_STATUS_LABELS[PRICE_STATUS_APPROVED]
    elif ps == PRICE_STATUS_REJECTED_FINAL:
        key, label = "quote_rejected", QUOTE_NEGOTIATION_STATUS_LABELS[PRICE_STATUS_REJECTED_FINAL]
    elif ps in (PRICE_STATUS_REVISION_REQUESTED, PRICE_STATUS_REJECTED):
        key, label = "changes_requested", QUOTE_NEGOTIATION_STATUS_LABELS[PRICE_STATUS_REVISION_REQUESTED]
    elif ps == PRICE_STATUS_QUOTED and _history_shows_revised_quote(wo):
        key, label = "revised_quote_submitted", "Revised quote submitted"
    elif ps == PRICE_STATUS_QUOTED:
        key, label = "quote_submitted", QUOTE_NEGOTIATION_STATUS_LABELS[PRICE_STATUS_QUOTED]
    elif ps == PRICE_STATUS_DISPUTED:
        key, label = "disputed", QUOTE_NEGOTIATION_STATUS_LABELS[PRICE_STATUS_DISPUTED]
    else:
        key, label = "quote_requested", QUOTE_NEGOTIATION_STATUS_LABELS[PRICE_STATUS_AWAITING_QUOTE]
    return {
        "key": key,
        "label": label,
        "price_status": ps or PRICE_STATUS_AWAITING_QUOTE,
        "is_approved": ps == PRICE_STATUS_APPROVED,
        "revision_active": ps in (PRICE_STATUS_REVISION_REQUESTED, PRICE_STATUS_REJECTED),
    }


def negotiation_status_label(wo: Dict[str, Any]) -> str:
    return derive_quote_presentation_state(wo).get("label") or "—"


async def _send_contractor_quote_revision_requested_email(
    wo: Dict[str, Any],
    *,
    revision_at: datetime,
    reason_code: Optional[str],
    message: Optional[str],
    target_budget: Optional[float],
) -> None:
    cid = (wo.get("client_id") or "").strip()
    wid = (wo.get("work_order_id") or "").strip()
    ctr = (wo.get("contractor_id") or "").strip()
    if not cid or not wid or not ctr:
        return
    db = database.get_db()
    contractor = await db.contractors.find_one(
        {"contractor_id": ctr},
        {"_id": 0, "email": 1, "name": 1, "company_name": 1},
    )
    to_email = (contractor or {}).get("email") if contractor else None
    if not to_email or not str(to_email).strip():
        return
    job_link_final = "See portal"
    now_iso = revision_at.isoformat()
    try:
        from utils.public_app_url import get_frontend_base_url

        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=_contractor_job_token_ttl_days())).isoformat()
        await db.contractor_job_tokens.insert_one({
            "token_hash": token_hash,
            "work_order_id": wid,
            "contractor_id": ctr,
            "created_at": now_iso,
            "expires_at": expires_at,
            "revoked_at": None,
        })
        base_url = get_frontend_base_url().rstrip("/")
        job_link_final = f"{base_url}/job?token={raw_token}"
    except Exception as exc:
        logger.warning("Contractor revision email: job token failed (non-fatal): %s", exc)

    reason_labels = {
        "price_too_high": "Price too high",
        "scope_unclear": "Scope unclear",
        "missing_breakdown": "Missing breakdown",
        "wrong_work_proposed": "Wrong work proposed",
        "incomplete_quote": "Incomplete quote",
        "timeline_unsuitable": "Timeline unsuitable",
        "other": "Other",
    }
    reason_label = reason_labels.get((reason_code or "").strip(), "Changes requested")
    body_parts = [
        f"<p>The client has requested changes to your quote for job <strong>{wid}</strong>.</p>",
        f"<p><strong>Reason:</strong> {reason_label}</p>",
    ]
    if message:
        body_parts.append(f"<p><strong>Client message:</strong> {message}</p>")
    if target_budget is not None:
        body_parts.append(f"<p><strong>Target budget:</strong> £{float(target_budget):.2f}</p>")
    body_parts.append(
        f'<p>Your assignment is still active. Submit a revised quote using your secure job link: '
        f'<a href="{job_link_final}">Open job</a></p>'
    )
    from services.notification_orchestrator import notification_orchestrator

    await notification_orchestrator.send(
        template_key="ADMIN_MANUAL",
        client_id=cid,
        context={
            "recipient": str(to_email).strip(),
            "subject": "Quote changes requested — submit a revised quote",
            "message": "".join(body_parts),
            "company_name": "Pleerity Enterprise Ltd",
        },
        idempotency_key=f"contractor_quote_revision:{wid}:{revision_at.timestamp()}",
        event_type="contractor_quote_revision_requested",
    )


async def _send_client_quote_review_email(wo: Dict[str, Any], *, quote_submitted_at: datetime) -> None:
    """Notify client portal contact that a contractor quote needs approval (orchestrator + message_logs)."""
    cid = (wo.get("client_id") or "").strip()
    wid = (wo.get("work_order_id") or "").strip()
    ctr = (wo.get("contractor_id") or "").strip()
    if not cid or not wid or not ctr:
        return
    db = database.get_db()
    client = await db.clients.find_one(
        {"client_id": cid},
        {"_id": 0, "contact_email": 1, "email": 1, "full_name": 1, "contact_name": 1, "customer_reference": 1},
    )
    if not client:
        return
    to_email = (client.get("contact_email") or client.get("email") or "").strip()
    if not to_email:
        return
    property_address = "Property"
    prop_id = wo.get("property_id")
    if prop_id:
        prop = await db.properties.find_one(
            {"property_id": prop_id, "client_id": cid},
            {"_id": 0, "address_line_1": 1, "city": 1, "postcode": 1},
        )
        if prop:
            parts = [prop.get("address_line_1"), prop.get("city"), prop.get("postcode")]
            property_address = ", ".join(p for p in parts if p) or property_address
    contractor_row = await db.contractors.find_one(
        {"contractor_id": ctr},
        {"_id": 0, "name": 1, "company_name": 1},
    )
    contractor_name = "Contractor"
    if contractor_row:
        contractor_name = (
            (str(contractor_row.get("name") or "").strip())
            or (str(contractor_row.get("company_name") or "").strip())
            or "Contractor"
        )
    client_name = (
        (str(client.get("full_name") or "").strip())
        or (str(client.get("contact_name") or "").strip())
        or None
    )
    from utils.public_app_url import get_frontend_base_url

    base = get_frontend_base_url().rstrip("/")
    client_job_link = f"{base}/operations/jobs/{wid}"
    from services.notification_orchestrator import notification_orchestrator

    await notification_orchestrator.send(
        template_key="CLIENT_QUOTE_REVIEW_REQUIRED",
        client_id=cid,
        context={
            "recipient": to_email,
            "subject": "A quote has been submitted for your review",
            "client_name": client_name or "",
            "property_address": property_address,
            "job_title": (wo.get("description") or "Work order")[:200],
            "work_order_id": wid,
            "quoted_price": wo.get("quoted_price"),
            "price_currency": wo.get("price_currency") or DEFAULT_PRICE_CURRENCY,
            "quote_notes": (wo.get("quote_notes") or "") or "",
            "contractor_name": contractor_name,
            "client_job_link": client_job_link,
            "secure_client_job_link": client_job_link,
            "portal_link": client_job_link,
            "customer_reference": client.get("customer_reference"),
        },
        idempotency_key=f"client_quote_review:{wid}:{quote_submitted_at.isoformat()}",
        event_type="CLIENT_QUOTE_REVIEW_REQUIRED",
    )


def pricing_workflow_applies(wo: Dict[str, Any]) -> bool:
    """True when this work order participates in quote/approval enforcement (post-rollout creates)."""
    mode = wo.get("pricing_mode")
    return mode is not None and str(mode).strip() != ""


def _norm_price_status(wo: Dict[str, Any]) -> str:
    raw = (wo.get("price_status") or "").strip().upper()
    return raw if raw in ALLOWED_PRICE_STATUSES else ""


def _norm_pricing_mode(wo: Dict[str, Any]) -> str:
    raw = (wo.get("pricing_mode") or "").strip().upper()
    return raw if raw in ALLOWED_PRICING_MODES else ""


def quote_is_approved_for_api(wo: Dict[str, Any]) -> bool:
    return _norm_price_status(wo) == PRICE_STATUS_APPROVED


def assert_may_transition_to_in_progress(wo: Dict[str, Any]) -> None:
    """
    Block contractor/client moves to IN_PROGRESS when quote rules require approval first.

    Maintenance + inspection-required: allow first visit (inspection) before approval when
    ``inspection_completed_at`` is not set. After inspection is marked complete, approved quote required.
    """
    if not pricing_workflow_applies(wo):
        return
    if quote_is_approved_for_api(wo):
        return
    mode = _norm_pricing_mode(wo)
    kind = (wo.get("work_order_kind") or "").strip().upper()
    if kind == WORK_ORDER_KIND_MAINTENANCE and mode == PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED:
        if not wo.get("inspection_completed_at"):
            return
    raise ValueError(
        "An approved quote is required before work can start. "
        "Submit a quote for client approval, or complete inspection first if this job requires it."
    )


def assert_may_transition_to_completed(wo: Dict[str, Any]) -> None:
    if not pricing_workflow_applies(wo):
        return
    if not quote_is_approved_for_api(wo):
        raise ValueError(
            "An approved quote is required before marking this job complete. "
            "Wait for the client to approve your quote, or submit a revised quote if it was rejected."
        )


def assert_invoice_submission_allowed(wo: Dict[str, Any]) -> None:
    if not pricing_workflow_applies(wo):
        return
    if not quote_is_approved_for_api(wo):
        raise ValueError("Invoices cannot be submitted until the client has approved the quote for this job.")


def contractor_may_propose_visit(wo: Dict[str, Any]) -> bool:
    """Whether contractor may propose a visit (QUOTE_FIRST requires approved quote first)."""
    if not pricing_workflow_applies(wo):
        return True
    from services.work_order_workflow_constants import WORKFLOW_MODE_INSPECTION_FIRST, resolve_workflow_mode

    if resolve_workflow_mode(wo) == WORKFLOW_MODE_INSPECTION_FIRST:
        return True
    return quote_is_approved_for_api(wo)


def contractor_may_offer_start_job(wo: Dict[str, Any]) -> bool:
    """Whether contractor next_actions may include start_job (inspection-first exception)."""
    if not pricing_workflow_applies(wo):
        return True
    if quote_is_approved_for_api(wo):
        return True
    kind = (wo.get("work_order_kind") or "").strip().upper()
    mode = _norm_pricing_mode(wo)
    if kind == WORK_ORDER_KIND_MAINTENANCE and mode == PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED:
        return not wo.get("inspection_completed_at")
    return False


def contractor_may_offer_complete_job(wo: Dict[str, Any]) -> bool:
    if not pricing_workflow_applies(wo):
        return True
    return quote_is_approved_for_api(wo)


def client_may_offer_start_for_pricing(wo: Dict[str, Any]) -> bool:
    """Client portal start / mark in progress — same gating as contractor start_job."""
    return contractor_may_offer_start_job(wo)


def assert_invoice_amount_within_approved_quote(wo: Dict[str, Any], submitted_amount: float) -> None:
    if not pricing_workflow_applies(wo):
        return
    if not quote_is_approved_for_api(wo):
        raise ValueError("Cannot validate invoice amount without an approved quote.")
    quoted = wo.get("quoted_price")
    if quoted is None:
        raise ValueError("Approved quote amount is missing; contact support.")
    try:
        cap = float(quoted)
    except (TypeError, ValueError):
        raise ValueError("Approved quote amount is invalid.") from None
    amt = float(submitted_amount)
    if amt > cap + 1e-6:
        raise ValueError(
            f"Invoice amount (£{amt:.2f}) exceeds the approved quote (£{cap:.2f}). "
            "Submit an amount at or below the approved quote, or ask the client to approve a new quote."
        )


def default_pricing_fields_for_create(
    *,
    work_order_kind: str,
    inspection_required: bool = False,
) -> Dict[str, Any]:
    kind = (work_order_kind or WORK_ORDER_KIND_MAINTENANCE).strip().upper()
    if kind == WORK_ORDER_KIND_COMPLIANCE:
        return {
            "workflow_mode": workflow_mode_for_create(work_order_kind=kind),
            "visit_negotiation_history": [],
            "pricing_mode": PRICING_MODE_COMPLIANCE_FIXED_QUOTE,
            "price_status": PRICE_STATUS_AWAITING_QUOTE,
            "quoted_price": None,
            "price_currency": DEFAULT_PRICE_CURRENCY,
            "quote_notes": None,
            "quote_submitted_at": None,
            "quote_approved_at": None,
            "quote_rejected_at": None,
            "quote_rejection_reason": None,
            "quote_revision_requested_at": None,
            "quote_revision_reason_code": None,
            "quote_revision_message": None,
            "quote_revision_target_budget": None,
            "quote_revision_target_date": None,
            "quote_negotiation_history": [],
            "inspection_required": False,
            "inspection_completed_at": None,
        }
    mode = (
        PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED
        if inspection_required
        else PRICING_MODE_MAINTENANCE_PREQUOTE
    )
    return {
        "workflow_mode": workflow_mode_for_create(work_order_kind=kind, inspection_required=inspection_required),
        "visit_negotiation_history": [],
        "pricing_mode": mode,
        "price_status": PRICE_STATUS_AWAITING_QUOTE,
        "quoted_price": None,
        "price_currency": DEFAULT_PRICE_CURRENCY,
        "quote_notes": None,
        "quote_submitted_at": None,
        "quote_approved_at": None,
        "quote_rejected_at": None,
        "quote_rejection_reason": None,
        "quote_revision_requested_at": None,
        "quote_revision_reason_code": None,
        "quote_revision_message": None,
        "quote_revision_target_budget": None,
        "quote_revision_target_date": None,
        "quote_negotiation_history": [],
        "inspection_required": bool(inspection_required),
        "inspection_completed_at": None,
    }


async def _fetch_wo(work_order_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    doc = await db.work_orders.find_one({"work_order_id": work_order_id}, {"_id": 0})
    return doc


async def submit_quote_for_work_order(
    work_order_id: str,
    contractor_id: str,
    *,
    amount: float,
    currency: str = DEFAULT_PRICE_CURRENCY,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    wo = await _fetch_wo(work_order_id)
    if not wo:
        raise ValueError("Work order not found")
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        raise ValueError("This job is not assigned to you")
    if not pricing_workflow_applies(wo):
        raise ValueError("Pricing workflow does not apply to this legacy job")
    st = _norm_price_status(wo)
    if st not in _quote_resubmit_allowed_statuses():
        raise ValueError(
            "A quote can only be submitted when awaiting a quote or after the client has requested changes"
        )
    if amount is None or float(amount) <= 0:
        raise ValueError("Quote amount must be greater than zero")
    if _norm_pricing_mode(wo) == PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED and not wo.get("inspection_completed_at"):
        raise ValueError(
            "Complete the inspection visit first, then submit a quote for the repair work."
        )

    now = datetime.now(timezone.utc)
    history = list(wo.get("quote_negotiation_history") or [])
    prior_versions = [h for h in history if h.get("event") in ("submitted", "resubmitted")]
    is_resubmit = st in (PRICE_STATUS_REJECTED, PRICE_STATUS_REVISION_REQUESTED) or bool(prior_versions)
    version = _next_quote_version(history) if is_resubmit else 1
    history_entry = {
        "version": version,
        "event": "resubmitted" if is_resubmit else "submitted",
        "amount": float(amount),
        "currency": (currency or DEFAULT_PRICE_CURRENCY).strip() or DEFAULT_PRICE_CURRENCY,
        "notes": (notes or "").strip() or None,
        "at": now.isoformat(),
        "actor_id": contractor_id,
        "actor_role": "contractor",
    }
    history.append(history_entry)

    db = database.get_db()
    await db.work_orders.update_one(
        {"work_order_id": work_order_id},
        {
            "$set": {
                "quoted_price": float(amount),
                "price_currency": (currency or DEFAULT_PRICE_CURRENCY).strip() or DEFAULT_PRICE_CURRENCY,
                "quote_notes": (notes or "").strip() or None,
                "price_status": PRICE_STATUS_QUOTED,
                "quote_submitted_at": now,
                "quote_approved_at": None,
                "quote_rejected_at": None,
                "quote_rejection_reason": None,
                "quote_revision_requested_at": None,
                "quote_revision_reason_code": None,
                "quote_revision_message": None,
                "quote_revision_target_budget": None,
                "quote_revision_target_date": None,
                "quote_negotiation_history": history,
                "updated_at": now.isoformat(),
            }
        },
    )
    try:
        from services.workflow_timer_service import on_work_order_quote_submitted

        await on_work_order_quote_submitted(work_order_id, actor_id=contractor_id)
    except Exception as timer_exc:
        logger.warning("Workflow timer quote_submitted hook failed (non-fatal): %s", timer_exc)
    await create_audit_log(
        action=AuditAction.CONTRACTOR_WORK_ORDER_STATUS_CHANGED,
        actor_id=contractor_id,
        client_id=wo.get("client_id"),
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={
            "pricing_event": "quote_resubmitted" if is_resubmit else "quote_submitted",
            "quoted_price": float(amount),
            "quote_version": version,
        },
    )
    out = await _fetch_wo(work_order_id)
    if not out:
        raise RuntimeError("Work order missing after update")
    try:
        await _send_client_quote_review_email(out, quote_submitted_at=now)
    except Exception as exc:
        logger.warning("Client quote review email failed (non-fatal): %s", exc)
    try:
        from services.work_order_workflow_notification_service import notify_client_work_order_event

        await notify_client_work_order_event(
            client_id=(wo.get("client_id") or "").strip(),
            work_order_id=work_order_id,
            title="Quote submitted for review",
            message="A contractor has submitted a quote for your approval.",
            notification_type="work_order_quote_submitted",
            cta_label="Review quote",
        )
    except Exception as exc:
        logger.warning("Client in-app quote submit notify failed (non-fatal): %s", exc)
    return out


async def approve_quote_for_work_order(work_order_id: str, client_id: str, *, actor_id: Optional[str]) -> Dict[str, Any]:
    wo = await _fetch_wo(work_order_id)
    if not wo:
        raise ValueError("Work order not found")
    if (wo.get("client_id") or "").strip() != (client_id or "").strip():
        raise ValueError("Work order not found")
    if not pricing_workflow_applies(wo):
        raise ValueError("Pricing workflow does not apply to this legacy job")
    if _norm_price_status(wo) != PRICE_STATUS_QUOTED:
        raise ValueError("Only a quoted price can be approved")

    now = datetime.now(timezone.utc)
    history = list(wo.get("quote_negotiation_history") or [])
    history.append({
        "version": max((int(h.get("version") or 0) for h in history), default=0) or 1,
        "event": "approved",
        "amount": wo.get("quoted_price"),
        "currency": wo.get("price_currency") or DEFAULT_PRICE_CURRENCY,
        "notes": wo.get("quote_notes"),
        "at": now.isoformat(),
        "actor_id": actor_id or client_id,
        "actor_role": "client",
    })

    db = database.get_db()
    await db.work_orders.update_one(
        {"work_order_id": work_order_id},
        {
            "$set": {
                "price_status": PRICE_STATUS_APPROVED,
                "quote_approved_at": now,
                "quote_rejected_at": None,
                "quote_rejection_reason": None,
                "quote_revision_requested_at": None,
                "quote_revision_reason_code": None,
                "quote_revision_message": None,
                "quote_revision_target_budget": None,
                "quote_revision_target_date": None,
                "quote_negotiation_history": history,
                "updated_at": now.isoformat(),
            }
        },
    )
    try:
        from services.workflow_timer_service import on_work_order_quote_approved

        await on_work_order_quote_approved(work_order_id, actor_id=actor_id or client_id)
    except Exception as timer_exc:
        logger.warning("Workflow timer quote_approved hook failed (non-fatal): %s", timer_exc)
    await create_audit_log(
        action=AuditAction.WORK_ORDER_QUOTE_APPROVED_BY_CLIENT,
        actor_id=actor_id or client_id,
        client_id=client_id,
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={"pricing_event": "quote_approved"},
    )
    out = await _fetch_wo(work_order_id)
    if not out:
        raise RuntimeError("Work order missing after update")
    try:
        await _send_contractor_quote_approved_email(out, quote_approved_at=now)
    except Exception as exc:
        logger.warning("Contractor quote approved email failed (non-fatal): %s", exc)
    try:
        from services.invoice_service import maybe_send_contractor_invoice_ready_notification

        await maybe_send_contractor_invoice_ready_notification(
            out,
            eligibility_timestamp_iso=now.isoformat(),
        )
    except Exception as exc:
        logger.warning("Contractor invoice-ready email failed (non-fatal): %s", exc)
    return out


async def request_quote_revision_for_work_order(
    work_order_id: str,
    client_id: str,
    *,
    reason_code: str,
    message: Optional[str] = None,
    target_budget: Optional[float] = None,
    target_date: Optional[str] = None,
    actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Default landlord response to a quote: request changes without ending assignment or work order."""
    wo = await _fetch_wo(work_order_id)
    if not wo:
        raise ValueError("Work order not found")
    if (wo.get("client_id") or "").strip() != (client_id or "").strip():
        raise ValueError("Work order not found")
    if not pricing_workflow_applies(wo):
        raise ValueError("Pricing workflow does not apply to this legacy job")
    if _norm_price_status(wo) != PRICE_STATUS_QUOTED:
        raise ValueError("Only a submitted quote can have changes requested")

    code = (reason_code or "").strip().lower()
    if code not in QUOTE_REVISION_REASON_CODES:
        raise ValueError("A valid revision reason is required")

    now = datetime.now(timezone.utc)
    history = list(wo.get("quote_negotiation_history") or [])
    version = max((int(h.get("version") or 0) for h in history if h.get("event") in ("submitted", "resubmitted")), default=1)
    history.append({
        "version": version,
        "event": "revision_requested",
        "amount": wo.get("quoted_price"),
        "currency": wo.get("price_currency") or DEFAULT_PRICE_CURRENCY,
        "notes": wo.get("quote_notes"),
        "at": now.isoformat(),
        "actor_id": actor_id or client_id,
        "actor_role": "client",
        "reason_code": code,
        "message": (message or "").strip() or None,
        "target_budget": float(target_budget) if target_budget is not None else None,
        "target_date": (target_date or "").strip() or None,
    })

    legacy_reason = (message or "").strip() or code.replace("_", " ")
    db = database.get_db()
    await db.work_orders.update_one(
        {"work_order_id": work_order_id},
        {
            "$set": {
                "price_status": PRICE_STATUS_REVISION_REQUESTED,
                "quote_revision_requested_at": now,
                "quote_revision_reason_code": code,
                "quote_revision_message": (message or "").strip() or None,
                "quote_revision_target_budget": float(target_budget) if target_budget is not None else None,
                "quote_revision_target_date": (target_date or "").strip() or None,
                "quote_rejected_at": now,
                "quote_rejection_reason": legacy_reason,
                "quote_approved_at": None,
                "quote_negotiation_history": history,
                "updated_at": now.isoformat(),
            }
        },
    )
    try:
        from services.workflow_timer_service import on_work_order_quote_revision_requested

        await on_work_order_quote_revision_requested(work_order_id, actor_id=actor_id or client_id)
    except Exception as timer_exc:
        logger.warning("Workflow timer quote_revision hook failed (non-fatal): %s", timer_exc)
    await create_audit_log(
        action=AuditAction.WORK_ORDER_QUOTE_REJECTED_BY_CLIENT,
        actor_id=actor_id or client_id,
        client_id=client_id,
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={
            "pricing_event": "quote_revision_requested",
            "reason_code": code,
            "message": (message or "")[:500],
            "target_budget": target_budget,
        },
    )
    out = await _fetch_wo(work_order_id)
    if not out:
        raise RuntimeError("Work order missing after update")
    try:
        await _send_contractor_quote_revision_requested_email(
            out,
            revision_at=now,
            reason_code=code,
            message=(message or "").strip() or None,
            target_budget=float(target_budget) if target_budget is not None else None,
        )
    except Exception as exc:
        logger.warning("Contractor quote revision email failed (non-fatal): %s", exc)
    return out


async def reject_quote_final_for_work_order(
    work_order_id: str,
    client_id: str,
    *,
    reason: Optional[str],
    actor_id: Optional[str],
) -> Dict[str, Any]:
    """Explicit final quote decline — does not remove contractor or cancel work order."""
    wo = await _fetch_wo(work_order_id)
    if not wo:
        raise ValueError("Work order not found")
    if (wo.get("client_id") or "").strip() != (client_id or "").strip():
        raise ValueError("Work order not found")
    if not pricing_workflow_applies(wo):
        raise ValueError("Pricing workflow does not apply to this legacy job")
    st = _norm_price_status(wo)
    if st not in (PRICE_STATUS_QUOTED, PRICE_STATUS_REVISION_REQUESTED, PRICE_STATUS_REJECTED):
        raise ValueError("Only an active quote negotiation can be finally declined")

    now = datetime.now(timezone.utc)
    history = list(wo.get("quote_negotiation_history") or [])
    version = max((int(h.get("version") or 0) for h in history if h.get("event") in ("submitted", "resubmitted")), default=1)
    history.append({
        "version": version,
        "event": "rejected_final",
        "amount": wo.get("quoted_price"),
        "currency": wo.get("price_currency") or DEFAULT_PRICE_CURRENCY,
        "notes": wo.get("quote_notes"),
        "at": now.isoformat(),
        "actor_id": actor_id or client_id,
        "actor_role": "client",
        "message": (reason or "").strip() or None,
    })

    db = database.get_db()
    await db.work_orders.update_one(
        {"work_order_id": work_order_id},
        {
            "$set": {
                "price_status": PRICE_STATUS_REJECTED_FINAL,
                "quote_rejected_at": now,
                "quote_rejection_reason": (reason or "").strip() or None,
                "quote_approved_at": None,
                "quote_negotiation_history": history,
                "updated_at": now.isoformat(),
            }
        },
    )
    await create_audit_log(
        action=AuditAction.WORK_ORDER_QUOTE_REJECTED_BY_CLIENT,
        actor_id=actor_id or client_id,
        client_id=client_id,
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={"pricing_event": "quote_rejected_final", "reason": (reason or "")[:500]},
    )
    out = await _fetch_wo(work_order_id)
    if not out:
        raise RuntimeError("Work order missing after update")
    try:
        cid = (wo.get("client_id") or "").strip()
        ctr = (wo.get("contractor_id") or "").strip()
        wid = work_order_id
        db = database.get_db()
        contractor = await db.contractors.find_one({"contractor_id": ctr}, {"_id": 0, "email": 1}) if ctr else None
        to_email = (contractor or {}).get("email") if contractor else None
        if cid and to_email:
            from services.notification_orchestrator import notification_orchestrator

            await notification_orchestrator.send(
                template_key="ADMIN_MANUAL",
                client_id=cid,
                context={
                    "recipient": str(to_email).strip(),
                    "subject": "Quote declined (final) — contact your client",
                    "message": (
                        f"<p>The client has finally declined the quote for job <strong>{wid}</strong>.</p>"
                        f"<p><strong>Reason:</strong> {(reason or '').strip() or 'Not specified'}</p>"
                        f"<p>Your assignment may still be active — contact the client or wait for reassignment guidance.</p>"
                    ),
                    "company_name": "Pleerity Enterprise Ltd",
                },
                idempotency_key=f"contractor_quote_rejected_final:{wid}:{now.timestamp()}",
                event_type="contractor_quote_rejected_final",
            )
    except Exception as exc:
        logger.warning("Contractor quote final decline email failed (non-fatal): %s", exc)
    return out


async def reject_quote_for_work_order(
    work_order_id: str,
    client_id: str,
    *,
    reason: Optional[str],
    actor_id: Optional[str],
) -> Dict[str, Any]:
    """Backward-compatible alias: reject-quote → request changes (revision workflow)."""
    return await request_quote_revision_for_work_order(
        work_order_id,
        client_id,
        reason_code="other",
        message=reason,
        actor_id=actor_id,
    )


async def mark_inspection_complete_for_work_order(work_order_id: str, contractor_id: str) -> Dict[str, Any]:
    wo = await _fetch_wo(work_order_id)
    if not wo:
        raise ValueError("Work order not found")
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        raise ValueError("This job is not assigned to you")
    kind = (wo.get("work_order_kind") or "").strip().upper()
    if kind != WORK_ORDER_KIND_MAINTENANCE:
        raise ValueError("Inspection completion applies to maintenance jobs only")
    if _norm_pricing_mode(wo) != PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED:
        raise ValueError("This job does not require an inspection-before-quote flow")
    if wo.get("inspection_completed_at"):
        raise ValueError("Inspection is already marked complete")

    now = datetime.now(timezone.utc)
    db = database.get_db()
    # After inspection, client must approve a quote before repair execution; allow AWAITING_QUOTE / keep QUOTED if resubmitted.
    set_fields: Dict[str, Any] = {
        "inspection_completed_at": now,
        "updated_at": now.isoformat(),
    }
    st = _norm_price_status(wo)
    if st not in (PRICE_STATUS_QUOTED, PRICE_STATUS_APPROVED):
        set_fields["price_status"] = PRICE_STATUS_AWAITING_QUOTE
        set_fields["quoted_price"] = None
        set_fields["quote_notes"] = None
        set_fields["quote_submitted_at"] = None
        set_fields["quote_approved_at"] = None
        set_fields["quote_rejected_at"] = None
        set_fields["quote_rejection_reason"] = None

    await db.work_orders.update_one({"work_order_id": work_order_id}, {"$set": set_fields})
    await create_audit_log(
        action=AuditAction.CONTRACTOR_WORK_ORDER_STATUS_CHANGED,
        actor_id=contractor_id,
        client_id=wo.get("client_id"),
        resource_type="work_order",
        resource_id=work_order_id,
        metadata={"pricing_event": "inspection_completed"},
    )
    out = await _fetch_wo(work_order_id)
    if not out:
        raise RuntimeError("Work order missing after update")
    return out


def serialize_pricing_snapshot(wo: Dict[str, Any]) -> Dict[str, Any]:
    """Stable pricing subset for API payloads (safe for legacy rows without fields)."""
    if not pricing_workflow_applies(wo):
        return {"pricing_workflow": False}
    ps = _norm_price_status(wo)
    presentation = derive_quote_presentation_state(wo)
    out: Dict[str, Any] = {
        "pricing_workflow": True,
        "pricing_mode": wo.get("pricing_mode"),
        "price_status": wo.get("price_status"),
        "quote_presentation": presentation,
        "negotiation_status_label": presentation.get("label") or negotiation_status_label(wo),
        "quoted_price": wo.get("quoted_price"),
        "price_currency": wo.get("price_currency") or DEFAULT_PRICE_CURRENCY,
        "quote_notes": wo.get("quote_notes"),
        "quote_submitted_at": wo.get("quote_submitted_at"),
        "quote_approved_at": wo.get("quote_approved_at"),
        "quote_rejected_at": wo.get("quote_rejected_at"),
        "quote_rejection_reason": wo.get("quote_rejection_reason"),
        "quote_revision_requested_at": wo.get("quote_revision_requested_at"),
        "quote_revision_reason_code": wo.get("quote_revision_reason_code"),
        "quote_revision_message": wo.get("quote_revision_message"),
        "quote_revision_target_budget": wo.get("quote_revision_target_budget"),
        "quote_revision_target_date": wo.get("quote_revision_target_date"),
        "quote_negotiation_history": wo.get("quote_negotiation_history") or [],
        "inspection_required": bool(wo.get("inspection_required")),
        "inspection_completed_at": wo.get("inspection_completed_at"),
    }
    if ps in (PRICE_STATUS_REJECTED, PRICE_STATUS_REVISION_REQUESTED):
        out["revision_active"] = True
    for k in (
        "quote_submitted_at",
        "quote_approved_at",
        "quote_rejected_at",
        "quote_revision_requested_at",
        "inspection_completed_at",
    ):
        v = out.get(k)
        if v and hasattr(v, "isoformat"):
            out[k] = v.isoformat()
    history = out.get("quote_negotiation_history") or []
    normalized_history = []
    for entry in history:
        row = dict(entry)
        at_val = row.get("at")
        if at_val and hasattr(at_val, "isoformat"):
            row["at"] = at_val.isoformat()
        normalized_history.append(row)
    out["quote_negotiation_history"] = normalized_history
    return out
