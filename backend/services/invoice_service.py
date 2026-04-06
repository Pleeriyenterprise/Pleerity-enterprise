"""
Invoice creation: admin/manual and work-order-linked.
Invoices flow to the approval workspace (client approves/rejects/needs_info).
Every invoice links to client_id, property_id, contractor_id, work_order_id.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid
import logging

from database import database
from models import AuditAction
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
BENCHMARK_NONE = "none"
BENCHMARK_BELOW = "below"
BENCHMARK_WITHIN = "within"
BENCHMARK_ABOVE = "above"
SOURCE_ADMIN = "admin"
SOURCE_CLIENT = "client"
SOURCE_CONTRACTOR = "contractor"

# Align with approval_service invoice statuses
_INV_PENDING = "pending"
_INV_NEEDS_INFO = "needs_info"
_INV_REJECTED = "rejected"
_INV_APPROVED = "approved"
_INV_PAID = "paid"


def _invoice_state_rank(inv: Dict[str, Any]) -> int:
    s = (inv.get("status") or "").lower()
    return {_INV_PAID: 5, _INV_APPROVED: 4, _INV_PENDING: 3, _INV_NEEDS_INFO: 2, _INV_REJECTED: 1}.get(s, 0)


def _assert_work_order_eligible_for_invoicing(wo: Dict[str, Any]) -> None:
    """
    Invoices linked to a work order are only allowed when the job is verified/closed,
    or completed with completion proof rules satisfied (same as contractor completion gate).
    """
    from services import compliance_workflow_service as cws
    from services import maintenance_service as ms

    st = (wo.get("status") or "").strip().upper()
    if st in (ms.STATUS_VERIFIED, ms.STATUS_CLOSED):
        return
    if st != ms.STATUS_COMPLETED:
        raise ValueError("Invoices can only be created when the work order is completed with proof or verified.")
    if cws.contractor_completion_proof_required(wo) and not cws.contractor_has_completion_proof(wo):
        raise ValueError("Upload completion proof for this job before creating or resubmitting an invoice.")


def work_order_cost_benchmark(wo: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """Estimate band from work order for invoice benchmark_fit."""
    mn = wo.get("cost_estimate_min")
    mx = wo.get("cost_estimate_max")
    mn_f: Optional[float] = None
    mx_f: Optional[float] = None
    try:
        if mn is not None:
            mn_f = float(mn)
    except (TypeError, ValueError):
        mn_f = None
    try:
        if mx is not None:
            mx_f = float(mx)
    except (TypeError, ValueError):
        mx_f = None
    return mn_f, mx_f


async def contractor_best_invoice_for_work_order(contractor_id: str, work_order_id: str) -> Optional[Dict[str, Any]]:
    """Highest-priority invoice for this contractor + work order (paid > approved > pending > …)."""
    db = database.get_db()
    cursor = db.invoices.find(
        {"contractor_id": contractor_id, "work_order_id": work_order_id},
        {"_id": 0},
    )
    items = await cursor.to_list(length=100)
    best: Optional[Dict[str, Any]] = None
    for inv in items:
        if not best or _invoice_state_rank(inv) > _invoice_state_rank(best):
            best = inv
    return best


def enrich_invoice_for_contractor_portal(inv: Dict[str, Any]) -> None:
    """Mutates invoice dict: ISO date strings + contractor-facing state labels for API JSON."""
    for key in ("submitted_at", "paid_at", "reviewed_at"):
        v = inv.get(key)
        if v and hasattr(v, "isoformat"):
            inv[key] = v.isoformat()
    raw = (inv.get("status") or "").strip().lower()
    if raw == _INV_PENDING:
        inv["contractor_invoice_state"] = "SUBMITTED"
    elif raw == _INV_NEEDS_INFO:
        inv["contractor_invoice_state"] = "UNDER_REVIEW"
    elif raw == _INV_APPROVED:
        inv["contractor_invoice_state"] = "APPROVED"
    elif raw == _INV_REJECTED:
        inv["contractor_invoice_state"] = "REJECTED"
    elif raw == _INV_PAID:
        inv["contractor_invoice_state"] = "PAID"
    else:
        inv["contractor_invoice_state"] = (raw or "unknown").upper()
    inv["contractor_correction_required"] = raw in (_INV_NEEDS_INFO, _INV_REJECTED)


async def contractor_resubmit_invoice(
    invoice_id: str,
    contractor_id: str,
    *,
    reference: str,
    description: Optional[str] = None,
    submitted_amount: float,
    currency: str = "GBP",
    attachment_storage_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Contractor updates and re-queues an invoice after needs_info or rejected.
    Resets status to pending and clears reviewer fields.
    """
    db = database.get_db()
    inv = await db.invoices.find_one({"invoice_id": invoice_id, "contractor_id": contractor_id})
    if not inv:
        return None
    st = (inv.get("status") or "").strip().lower()
    if st not in (_INV_NEEDS_INFO, _INV_REJECTED):
        raise ValueError("Invoice cannot be resubmitted in its current state")

    wo = await db.work_orders.find_one(
        {"work_order_id": inv.get("work_order_id"), "client_id": inv.get("client_id")},
        {
            "_id": 0,
            "work_order_id": 1,
            "status": 1,
            "evidence_keys": 1,
            "work_order_kind": 1,
            "expected_output_document_type": 1,
        },
    )
    if not wo:
        raise ValueError("Work order not found for this invoice")
    _assert_work_order_eligible_for_invoicing(wo)

    now = datetime.now(timezone.utc)
    benchmark_min = inv.get("benchmark_min")
    benchmark_max = inv.get("benchmark_max")
    benchmark_fit = _compute_benchmark_fit(submitted_amount, benchmark_min, benchmark_max)

    set_doc: Dict[str, Any] = {
        "status": _INV_PENDING,
        "reference": (reference or "").strip() or inv.get("reference") or f"INV-{invoice_id[:8]}",
        "description": (description or "").strip() or None,
        "submitted_amount": submitted_amount,
        "currency": (currency or "GBP").strip(),
        "benchmark_fit": benchmark_fit,
        "submitted_at": now,
        "reviewed_at": None,
        "reviewer_id": None,
    }
    if attachment_storage_key is not None:
        set_doc["attachment_storage_key"] = attachment_storage_key

    await db.invoices.update_one({"invoice_id": invoice_id}, {"$set": set_doc})
    out = await db.invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
    if not out:
        return None
    if out.get("submitted_at") and hasattr(out["submitted_at"], "isoformat"):
        out["submitted_at"] = out["submitted_at"].isoformat()
    if out.get("paid_at") and hasattr(out["paid_at"], "isoformat"):
        out["paid_at"] = out["paid_at"].isoformat()
    if out.get("reviewed_at") and hasattr(out["reviewed_at"], "isoformat"):
        out["reviewed_at"] = out["reviewed_at"].isoformat()

    enrich_invoice_for_contractor_portal(out)

    await create_audit_log(
        action=AuditAction.CONTRACTOR_INVOICE_RESUBMITTED,
        actor_id=contractor_id,
        client_id=out.get("client_id"),
        resource_type="invoice",
        resource_id=invoice_id,
        metadata={
            "work_order_id": out.get("work_order_id"),
            "reference": out.get("reference"),
            "submitted_amount": submitted_amount,
        },
    )
    logger.info("Invoice resubmitted invoice_id=%s contractor_id=%s", invoice_id, contractor_id)
    return out


async def contractor_submit_or_resubmit_for_work_order(
    work_order: Dict[str, Any],
    contractor_id: str,
    *,
    reference: str,
    description: Optional[str] = None,
    submitted_amount: float,
    currency: str = "GBP",
    attachment_storage_key: Optional[str] = None,
) -> Tuple[Dict[str, Any], str]:
    """
    Portal/job-link: create a new invoice or resubmit after needs_info/rejected.
    Returns (invoice_document, "created" | "resubmitted").
    Raises ValueError on validation or business-rule errors.
    """
    client_id = work_order.get("client_id")
    property_id = work_order.get("property_id")
    work_order_id = work_order.get("work_order_id")
    if not client_id or not property_id or not work_order_id:
        raise ValueError("Work order missing property or client")
    ref = (reference or "").strip()
    if not ref:
        raise ValueError("Invoice reference is required")
    if submitted_amount is None or float(submitted_amount) <= 0:
        raise ValueError("Invoice amount must be greater than zero")
    amt = float(submitted_amount)

    bench_min, bench_max = work_order_cost_benchmark(work_order)
    best = await contractor_best_invoice_for_work_order(contractor_id, work_order_id)
    if best:
        st = (best.get("status") or "").lower()
        if st in (_INV_PENDING, _INV_APPROVED, _INV_PAID):
            raise ValueError("An invoice for this job is already with the client or settled.")
        if st in (_INV_NEEDS_INFO, _INV_REJECTED):
            iid = best.get("invoice_id")
            if not iid:
                raise ValueError("Invalid invoice record")
            out = await contractor_resubmit_invoice(
                iid,
                contractor_id,
                reference=ref,
                description=description,
                submitted_amount=amt,
                currency=currency,
                attachment_storage_key=attachment_storage_key,
            )
            if not out:
                raise ValueError("Invoice resubmit failed")
            return out, "resubmitted"

    doc = await create_invoice(
        client_id=client_id,
        property_id=property_id,
        contractor_id=contractor_id,
        work_order_id=work_order_id,
        reference=ref,
        description=description,
        submitted_amount=amt,
        currency=currency,
        benchmark_min=bench_min,
        benchmark_max=bench_max,
        attachment_storage_key=attachment_storage_key,
        source=SOURCE_CONTRACTOR,
        created_by_id=contractor_id,
    )
    enrich_invoice_for_contractor_portal(doc)
    return doc, "created"


def _compute_benchmark_fit(
    submitted_amount: Optional[float],
    benchmark_min: Optional[float],
    benchmark_max: Optional[float],
) -> str:
    if submitted_amount is None or (benchmark_min is None and benchmark_max is None):
        return BENCHMARK_NONE
    if benchmark_min is not None and submitted_amount < benchmark_min:
        return BENCHMARK_BELOW
    if benchmark_max is not None and submitted_amount > benchmark_max:
        return BENCHMARK_ABOVE
    return BENCHMARK_WITHIN


async def create_invoice(
    client_id: str,
    property_id: str,
    contractor_id: str,
    work_order_id: str,
    reference: str,
    description: Optional[str] = None,
    submitted_amount: Optional[float] = None,
    currency: str = "GBP",
    benchmark_min: Optional[float] = None,
    benchmark_max: Optional[float] = None,
    attachment_storage_key: Optional[str] = None,
    source: str = SOURCE_ADMIN,
    created_by_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create an invoice linked to work order, contractor, property, client.
    Validates that work order and contractor exist and belong to client.
    Sets status=pending so it appears in Approvals. Audit INVOICE_CREATED.
    """
    db = database.get_db()

    # Validate work order belongs to client
    wo = await db.work_orders.find_one(
        {"work_order_id": work_order_id, "client_id": client_id},
        {
            "_id": 0,
            "work_order_id": 1,
            "property_id": 1,
            "status": 1,
            "evidence_keys": 1,
            "work_order_kind": 1,
            "expected_output_document_type": 1,
        },
    )
    if not wo:
        raise ValueError("Work order not found or does not belong to this client")

    if wo.get("property_id") != property_id:
        raise ValueError("Work order property_id does not match")

    # Validate contractor exists (and optionally is visible to client)
    contractor = await db.contractors.find_one(
        {"contractor_id": contractor_id},
        {"_id": 0, "contractor_id": 1, "client_id": 1},
    )
    if not contractor:
        raise ValueError("Contractor not found")

    # Property must belong to client
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 1},
    )
    if not prop:
        raise ValueError("Property not found or does not belong to this client")

    _assert_work_order_eligible_for_invoicing(wo)

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    invoice_id = str(uuid.uuid4())

    benchmark_fit = _compute_benchmark_fit(submitted_amount, benchmark_min, benchmark_max)

    doc = {
        "invoice_id": invoice_id,
        "client_id": client_id,
        "property_id": property_id,
        "contractor_id": contractor_id,
        "work_order_id": work_order_id,
        "reference": (reference or "").strip() or f"INV-{invoice_id[:8]}",
        "description": (description or "").strip() or None,
        "submitted_amount": submitted_amount,
        "currency": (currency or "GBP").strip(),
        "benchmark_min": benchmark_min,
        "benchmark_max": benchmark_max,
        "benchmark_fit": benchmark_fit,
        "status": STATUS_PENDING,
        "submitted_at": now,
        "attachment_storage_key": attachment_storage_key,
        "source": source,
        "created_by_id": created_by_id,
        "reviewed_at": None,
        "reviewer_id": None,
    }
    await db.invoices.insert_one(doc)
    doc.pop("_id", None)
    if doc.get("submitted_at") and hasattr(doc["submitted_at"], "isoformat"):
        doc["submitted_at"] = doc["submitted_at"].isoformat()

    await create_audit_log(
        action=AuditAction.INVOICE_CREATED,
        actor_id=created_by_id or "system",
        client_id=client_id,
        resource_type="invoice",
        resource_id=invoice_id,
        metadata={
            "work_order_id": work_order_id,
            "contractor_id": contractor_id,
            "property_id": property_id,
            "reference": doc["reference"],
            "submitted_amount": submitted_amount,
            "source": source,
        },
    )
    logger.info("Invoice created invoice_id=%s client_id=%s work_order_id=%s", invoice_id, client_id, work_order_id)
    return doc
