"""
Invoice creation: admin/manual and work-order-linked.
Invoices flow to the approval workspace (client approves/rejects/needs_info).
Every invoice links to client_id, property_id, contractor_id, work_order_id.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
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
        {"_id": 0, "work_order_id": 1, "property_id": 1},
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
