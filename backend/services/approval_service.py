"""
Invoice approval workspace: list, filter, approve/reject/needs_info, export.
Gated by INVOICING feature flag. Integrates with work orders, contractors, properties.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import uuid
import csv
import io
import logging

from database import database
from models import AuditAction
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

# Invoice status and benchmark fit (task §7, §11)
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_NEEDS_INFO = "needs_info"
BENCHMARK_BELOW = "below"
BENCHMARK_WITHIN = "within"
BENCHMARK_ABOVE = "above"
BENCHMARK_NONE = "none"
ACTION_APPROVED = "approved"
ACTION_REJECTED = "rejected"
ACTION_NEEDS_INFO = "needs_info"

AUDIT_ACTION_MAP = {
    ACTION_APPROVED: AuditAction.INVOICE_APPROVED,
    ACTION_REJECTED: AuditAction.INVOICE_REJECTED,
    ACTION_NEEDS_INFO: AuditAction.INVOICE_NEEDS_INFO,
}


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


async def _resolve_labels(
    db,
    client_id: str,
    property_ids: List[str],
    contractor_ids: List[str],
    work_order_ids: List[str],
) -> Dict[str, Dict[str, str]]:
    """Resolve property, contractor, work order labels for display."""
    out = {"properties": {}, "contractors": {}, "work_orders": {}}
    if property_ids:
        cursor = db.properties.find(
            {"client_id": client_id, "property_id": {"$in": list(set(property_ids))}},
            {"property_id": 1, "nickname": 1, "address_line_1": 1},
        )
        async for p in cursor:
            out["properties"][p["property_id"]] = p.get("nickname") or p.get("address_line_1") or p["property_id"]
    if contractor_ids:
        cursor = db.contractors.find(
            {"contractor_id": {"$in": list(set(contractor_ids))}},
            {"contractor_id": 1, "company_name": 1},
        )
        async for c in cursor:
            out["contractors"][c["contractor_id"]] = c.get("company_name") or c["contractor_id"]
    if work_order_ids:
        cursor = db.work_orders.find(
            {"work_order_id": {"$in": list(set(work_order_ids))}, "client_id": client_id},
            {"work_order_id": 1, "description": 1},
        )
        async for w in cursor:
            desc = (w.get("description") or "")[:50]
            out["work_orders"][w["work_order_id"]] = desc or w["work_order_id"]
    return out


async def list_approvals(
    client_id: str,
    status: Optional[str] = None,
    contractor_id: Optional[str] = None,
    property_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    benchmark_fit: Optional[str] = None,
    q: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    """List invoices with filters; return summary, approvals list, and exceptions."""
    db = database.get_db()
    query = {"client_id": client_id}

    if status:
        query["status"] = status
    if contractor_id:
        query["contractor_id"] = contractor_id
    if property_id:
        query["property_id"] = property_id
    if work_order_id:
        query["work_order_id"] = work_order_id
    if benchmark_fit:
        query["benchmark_fit"] = benchmark_fit

    if from_date or to_date:
        submitted_q = {}
        if from_date:
            try:
                submitted_q["$gte"] = datetime.fromisoformat(from_date.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
            except Exception:
                pass
        if to_date:
            try:
                end = datetime.fromisoformat(to_date.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
                submitted_q["$lte"] = end
            except Exception:
                pass
        if submitted_q:
            query["submitted_at"] = submitted_q

    if q and q.strip():
        q_strip = q.strip()
        query["$or"] = [
            {"reference": {"$regex": q_strip, "$options": "i"}},
            {"description": {"$regex": q_strip, "$options": "i"}},
        ]

    cursor = db.invoices.find(query).sort("submitted_at", -1).skip(skip).limit(limit)
    invoices = await cursor.to_list(length=limit)

    # Resolve labels
    property_ids = [i.get("property_id") for i in invoices if i.get("property_id")]
    contractor_ids = [i.get("contractor_id") for i in invoices if i.get("contractor_id")]
    work_order_ids = [i.get("work_order_id") for i in invoices if i.get("work_order_id")]
    labels = await _resolve_labels(db, client_id, property_ids, contractor_ids, work_order_ids)

    # Apply text search on resolved labels if q provided (post-filter)
    if q and q.strip():
        q_lower = q.strip().lower()
        def matches(inv):
            if q_lower in (inv.get("reference") or "").lower():
                return True
            if q_lower in (inv.get("description") or "").lower():
                return True
            pid = inv.get("property_id")
            if pid and q_lower in (labels["properties"].get(pid) or "").lower():
                return True
            cid = inv.get("contractor_id")
            if cid and q_lower in (labels["contractors"].get(cid) or "").lower():
                return True
            wid = inv.get("work_order_id")
            if wid and q_lower in (labels["work_orders"].get(wid) or "").lower():
                return True
            return False
        invoices = [i for i in invoices if matches(i)]

    now = datetime.now(timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Summary (portfolio-wide with same filters)
    summary_query = {"client_id": client_id}
    if status:
        summary_query["status"] = status
    if contractor_id:
        summary_query["contractor_id"] = contractor_id
    if property_id:
        summary_query["property_id"] = property_id
    if work_order_id:
        summary_query["work_order_id"] = work_order_id
    if benchmark_fit:
        summary_query["benchmark_fit"] = benchmark_fit
    if from_date or to_date:
        if "submitted_at" not in summary_query:
            summary_query["submitted_at"] = {}
        if from_date:
            try:
                summary_query["submitted_at"]["$gte"] = datetime.fromisoformat(from_date.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
            except Exception:
                pass
        if to_date:
            try:
                summary_query["submitted_at"]["$lte"] = datetime.fromisoformat(to_date.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
            except Exception:
                pass

    pending_count = await db.invoices.count_documents({**summary_query, "status": STATUS_PENDING})
    approved_this_month = await db.invoices.count_documents({
        **summary_query,
        "status": STATUS_APPROVED,
        "reviewed_at": {"$gte": start_of_month.isoformat()},
    })
    rejected_count = await db.invoices.count_documents({**summary_query, "status": STATUS_REJECTED})
    needs_info_count = await db.invoices.count_documents({**summary_query, "status": STATUS_NEEDS_INFO})
    out_of_range_count = await db.invoices.count_documents({
        **summary_query,
        "benchmark_fit": BENCHMARK_ABOVE,
        "status": STATUS_PENDING,
    })
    pending_value_cursor = db.invoices.aggregate([
        {"$match": {**summary_query, "status": STATUS_PENDING}},
        {"$group": {"_id": None, "total": {"$sum": "$submitted_amount"}}},
    ])
    pending_value_result = await pending_value_cursor.to_list(length=1)
    total_pending_value = int(pending_value_result[0]["total"]) if pending_value_result else 0

    summary = {
        "pending": pending_count,
        "approvedThisMonth": approved_this_month,
        "rejected": rejected_count,
        "needsInfo": needs_info_count,
        "outOfRange": out_of_range_count,
        "totalPendingValue": total_pending_value,
    }

    # Enrich each invoice for response
    approvals = []
    for inv in invoices:
        approvals.append({
            **inv,
            "property_label": labels["properties"].get(inv.get("property_id") or "", inv.get("property_id") or "—"),
            "contractor_label": labels["contractors"].get(inv.get("contractor_id") or "", inv.get("contractor_id") or "—"),
            "work_order_label": labels["work_orders"].get(inv.get("work_order_id") or "", inv.get("work_order_id") or "—"),
        })

    # Exceptions: above benchmark, missing work order, missing contractor, missing attachment (pending only)
    exceptions = []
    for inv in invoices:
        if inv.get("status") != STATUS_PENDING:
            continue
        inv_id = inv.get("invoice_id")
        issues = []
        if inv.get("benchmark_fit") == BENCHMARK_ABOVE:
            issues.append("Above benchmark")
        if not inv.get("work_order_id"):
            issues.append("Missing work order link")
        if not inv.get("contractor_id"):
            issues.append("Missing contractor details")
        if not inv.get("attachment_storage_key"):
            issues.append("Missing attached invoice evidence")
        if issues:
            exceptions.append({
                "invoice_id": inv_id,
                "reference": inv.get("reference"),
                "property_id": inv.get("property_id"),
                "property_label": labels["properties"].get(inv.get("property_id") or "", inv.get("property_id") or "—"),
                "contractor_id": inv.get("contractor_id"),
                "contractor_label": labels["contractors"].get(inv.get("contractor_id") or "", inv.get("contractor_id") or "—"),
                "issues": issues,
                "reason_flagged": "; ".join(issues),
            })

    return {"summary": summary, "approvals": approvals, "exceptions": exceptions}


async def get_approval(client_id: str, invoice_id: str) -> Optional[Dict[str, Any]]:
    """Get a single invoice with approval history for the detail drawer."""
    db = database.get_db()
    inv = await db.invoices.find_one({"client_id": client_id, "invoice_id": invoice_id})
    if not inv:
        return None
    history = await db.invoice_approvals.find({"invoice_id": invoice_id}).sort("created_at", 1).to_list(100)
    labels = await _resolve_labels(
        db, client_id,
        [inv.get("property_id")] if inv.get("property_id") else [],
        [inv.get("contractor_id")] if inv.get("contractor_id") else [],
        [inv.get("work_order_id")] if inv.get("work_order_id") else [],
    )
    return {
        **inv,
        "property_label": labels["properties"].get(inv.get("property_id") or "", inv.get("property_id") or "—"),
        "contractor_label": labels["contractors"].get(inv.get("contractor_id") or "", inv.get("contractor_id") or "—"),
        "work_order_label": labels["work_orders"].get(inv.get("work_order_id") or "", inv.get("work_order_id") or "—"),
        "history": history,
    }


async def update_approval(
    client_id: str,
    invoice_id: str,
    action: str,
    notes: Optional[str] = None,
    reviewer_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Set approval action (approved | rejected | needs_info); write invoice_approvals and audit."""
    if action not in (ACTION_APPROVED, ACTION_REJECTED, ACTION_NEEDS_INFO):
        return None
    db = database.get_db()
    inv = await db.invoices.find_one({"client_id": client_id, "invoice_id": invoice_id})
    if not inv:
        return None
    if inv.get("status") != STATUS_PENDING:
        return None  # already decided

    now = datetime.now(timezone.utc).isoformat()
    status_map = {ACTION_APPROVED: STATUS_APPROVED, ACTION_REJECTED: STATUS_REJECTED, ACTION_NEEDS_INFO: STATUS_NEEDS_INFO}
    new_status = status_map[action]

    approval_id = str(uuid.uuid4())
    await db.invoice_approvals.insert_one({
        "approval_id": approval_id,
        "invoice_id": invoice_id,
        "reviewer_id": reviewer_id,
        "action": action,
        "notes": notes or None,
        "created_at": now,
    })
    await db.invoices.update_one(
        {"client_id": client_id, "invoice_id": invoice_id},
        {"$set": {"status": new_status, "reviewed_at": now, "reviewer_id": reviewer_id}},
    )

    audit_action = AUDIT_ACTION_MAP.get(action)
    if audit_action:
        await create_audit_log(
            action=audit_action,
            actor_id=reviewer_id,
            client_id=client_id,
            resource_type="invoice",
            resource_id=invoice_id,
            metadata={"notes": notes, "submitted_amount": inv.get("submitted_amount"), "status": new_status},
        )
    return await get_approval(client_id, invoice_id)


async def export_approvals_csv(
    client_id: str,
    status: Optional[str] = None,
    contractor_id: Optional[str] = None,
    property_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    benchmark_fit: Optional[str] = None,
    q: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 2000,
) -> str:
    """Export filtered approvals as CSV. Columns: Invoice Ref, Property, Work Order, Contractor, Submitted Amount, Benchmark Range, Benchmark Fit, Approval Status, Submitted At, Reviewed At, Reviewer."""
    data = await list_approvals(
        client_id=client_id,
        status=status,
        contractor_id=contractor_id,
        property_id=property_id,
        work_order_id=work_order_id,
        benchmark_fit=benchmark_fit,
        q=q,
        from_date=from_date,
        to_date=to_date,
        skip=0,
        limit=limit,
    )
    approvals = data.get("approvals") or []
    rows = []
    for a in approvals:
        min_b = a.get("benchmark_min")
        max_b = a.get("benchmark_max")
        if min_b is not None and max_b is not None:
            currency = a.get("currency") or "GBP"
            benchmark_range = f"{min_b}–{max_b} {currency}"
        else:
            benchmark_range = "No benchmark"
        rows.append({
            "Invoice Ref": a.get("reference") or "",
            "Property": a.get("property_label") or "",
            "Work Order": a.get("work_order_label") or "",
            "Contractor": a.get("contractor_label") or "",
            "Submitted Amount": a.get("submitted_amount"),
            "Benchmark Range": benchmark_range,
            "Benchmark Fit": a.get("benchmark_fit") or "none",
            "Approval Status": a.get("status") or "",
            "Submitted At": a.get("submitted_at") or "",
            "Reviewed At": a.get("reviewed_at") or "",
            "Reviewer": a.get("reviewer_id") or "",
        })
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return buf.getvalue()
