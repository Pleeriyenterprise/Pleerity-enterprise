"""Invoice readiness governance after completion proof and review."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services import compliance_workflow_service as cws
from services import maintenance_service as ms
from services.completion_workflow_transition_service import is_awaiting_completion_review
from services.work_order_execution_constants import (
    COMPLETION_REVIEW_ACCEPTED,
    COMPLIANCE_PROOF_VERIFIED,
    OPERATIONAL_STATUS_WORK_COMPLETED_PENDING_REVIEW,
)
from services.work_order_pricing_service import pricing_workflow_applies, quote_is_approved_for_api

logger = logging.getLogger(__name__)

INVOICE_READINESS_NOT_READY = "NOT_READY"
INVOICE_READINESS_PENDING_REVIEW = "PENDING_REVIEW"
INVOICE_READINESS_READY = "READY"


def evaluate_invoice_readiness(
    wo: Dict[str, Any],
    *,
    invoice: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Governed invoice paths:
    - READY: verified/closed, or completion accepted, or compliance proof verified
    - PENDING_REVIEW: proof submitted, awaiting human review
    - NOT_READY: otherwise (including BOOKED/SCHEDULED without completion)
    """
    st = (wo.get("status") or "").strip().upper()
    if invoice and (invoice.get("status") or "").strip().lower() in (
        "pending",
        "approved",
        "paid",
        "needs_info",
        "rejected",
    ):
        inv_st = (invoice.get("status") or "").strip().lower()
        return {
            "state": INVOICE_READINESS_READY if inv_st in ("pending", "approved", "paid") else INVOICE_READINESS_NOT_READY,
            "label": "Invoice on file" if inv_st != "rejected" else "Invoice needs attention",
            "may_submit_invoice": False,
            "reason": "An invoice already exists for this job.",
        }

    if st in (ms.STATUS_VERIFIED, ms.STATUS_CLOSED):
        return _ready_payload("Job verified — you may submit an invoice.")

    review = (wo.get("completion_review_status") or "").strip().upper()
    cps = (wo.get("compliance_proof_status") or "").strip().upper()

    if review == COMPLETION_REVIEW_ACCEPTED or cps == COMPLIANCE_PROOF_VERIFIED:
        if _quote_gate_blocks(wo):
            return {
                "state": INVOICE_READINESS_NOT_READY,
                "label": "Not ready to invoice",
                "may_submit_invoice": False,
                "reason": "An approved quote is required before invoicing.",
            }
        if cws.contractor_completion_proof_required(wo) and not cws.contractor_has_completion_proof(wo):
            return {
                "state": INVOICE_READINESS_NOT_READY,
                "label": "Not ready to invoice",
                "may_submit_invoice": False,
                "reason": "Upload completion proof before invoicing.",
            }
        return _ready_payload("Completion accepted — you may submit your invoice.")

    if is_awaiting_completion_review(wo) or (
        st == ms.STATUS_COMPLETED and cws.contractor_has_completion_proof(wo)
    ):
        return {
            "state": INVOICE_READINESS_PENDING_REVIEW,
            "label": "Awaiting completion review",
            "may_submit_invoice": False,
            "reason": "Review completion before approving invoice.",
        }

    if st == ms.STATUS_COMPLETED and cws.contractor_has_completion_proof(wo):
        return {
            "state": INVOICE_READINESS_PENDING_REVIEW,
            "label": "Awaiting completion review",
            "may_submit_invoice": False,
            "reason": "Review completion before approving invoice.",
        }

    return {
        "state": INVOICE_READINESS_NOT_READY,
        "label": "Not ready to invoice",
        "may_submit_invoice": False,
        "reason": "Complete the job and upload proof before invoicing.",
    }


def _ready_payload(reason: str) -> Dict[str, Any]:
    return {
        "state": INVOICE_READINESS_READY,
        "label": "Ready to invoice",
        "may_submit_invoice": True,
        "reason": reason,
    }


def _quote_gate_blocks(wo: Dict[str, Any]) -> bool:
    return pricing_workflow_applies(wo) and not quote_is_approved_for_api(wo)


def assert_may_submit_invoice(wo: Dict[str, Any]) -> None:
    readiness = evaluate_invoice_readiness(wo)
    if not readiness.get("may_submit_invoice"):
        raise ValueError(readiness.get("reason") or "This job is not ready for invoicing yet.")
    from services.work_order_pricing_service import assert_invoice_submission_allowed

    assert_invoice_submission_allowed(wo)


def serialize_invoice_readiness(wo: Dict[str, Any], *, invoice: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return evaluate_invoice_readiness(wo, invoice=invoice)


async def notify_invoice_unlocked_if_ready(wo: Dict[str, Any], *, actor_id: Optional[str] = None) -> None:
    readiness = evaluate_invoice_readiness(wo)
    if not readiness.get("may_submit_invoice"):
        return
    try:
        from services.invoice_service import maybe_send_contractor_invoice_ready_notification

        ts = wo.get("completion_review_accepted_at") or wo.get("completed_at")
        await maybe_send_contractor_invoice_ready_notification(wo, eligibility_timestamp_iso=str(ts or ""))
    except Exception as exc:
        logger.warning("Invoice unlocked notification skipped: %s", exc)

    from models.core import AuditAction
    from utils.audit import create_audit_log

    wid = (wo.get("work_order_id") or "").strip()
    if wid:
        await create_audit_log(
            action=AuditAction.WORKFLOW_INVOICE_UNLOCKED,
            actor_id=actor_id or "system",
            client_id=wo.get("client_id"),
            resource_type="work_order",
            resource_id=wid,
            metadata={"invoice_readiness": readiness.get("state")},
        )
