"""
Paid order / subscription checkout: invoice PDF (branded), GridFS, invoice numbers.

Order PDF line items:
  Built from ``orders.pricing_snapshot``: ``base_price_pence`` as the main service row and
  each entry in ``addons`` (``name``, ``price_pence``) as its own row. If the sum of those
  lines does not match ``total_price_pence``, a single collapsed line is used (logged).

CVP subscription checkout PDF:
  Primary description from ``plan_registry.format_cvp_invoice_product_line(plan_code)``.
  Optional ``Billing period: …`` line when Stripe subscription period start/end are known
  (passed from ``checkout.session.completed`` after ``Subscription.retrieve``).
"""
from __future__ import annotations

import io
import logging
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from services.plan_registry import PlanCode

from bson import ObjectId
from pymongo import ReturnDocument

from database import database
from services.invoice_pdf_builder import build_branded_invoice_pdf_bytes

logger = logging.getLogger(__name__)

GRIDFS_BUCKET = "order_files"
STRIPE_CHECKOUT_INVOICES = "stripe_checkout_invoices"


async def allocate_invoice_number() -> str:
    """Monotonic per-calendar-year sequence: INV-YYYY-NNNNNN."""
    db = database.get_db()
    year = datetime.now(timezone.utc).year
    key = f"invoice_seq_{year}"
    doc = await db.counters.find_one_and_update(
        {"_id": key},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    seq = int((doc or {}).get("seq") or 1)
    return f"INV-{year}-{seq:06d}"


def _format_billing_period_note(start: Optional[datetime], end: Optional[datetime]) -> Optional[str]:
    if start is None or end is None:
        return None
    try:
        if start.timestamp() <= 0 or end.timestamp() <= 0:
            return None
    except (OSError, ValueError, OverflowError):
        return None
    fmt = "%d %b %Y"
    return f"Billing period: {start.strftime(fmt)} to {end.strftime(fmt)}"


def _single_line_order_pdf_item(order: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Legacy single-row invoice line (VAT-aware)."""
    snap = order.get("pricing_snapshot") or {}
    pricing = order.get("pricing") or {}
    total_pence = int(snap.get("total_price_pence") or pricing.get("total_amount") or 0)
    vat_pence = int(snap.get("vat_pence", pricing.get("vat_amount") or 0) or 0)
    service_name = str(order.get("service_name") or order.get("service_code") or "Service")
    if vat_pence > 0:
        subtotal_pence = max(0, total_pence - vat_pence)
        unit_pence = subtotal_pence
        line_total_pence = subtotal_pence
    else:
        unit_pence = total_pence
        line_total_pence = total_pence
    return [
        {
            "description": service_name,
            "quantity": 1,
            "unit_pence": unit_pence,
            "line_total_pence": line_total_pence,
        }
    ]


def _build_order_line_items_for_pdf(order: Dict[str, Any]) -> List[Dict[str, Any]]:
    snap = order.get("pricing_snapshot") or {}
    pricing = order.get("pricing") or {}
    vat_pence = int(snap.get("vat_pence", pricing.get("vat_amount") or 0) or 0)
    if vat_pence > 0:
        return _single_line_order_pdf_item(order)

    service_name = str(order.get("service_name") or order.get("service_code") or "Service")
    addons = snap.get("addons") if isinstance(snap.get("addons"), list) else []
    base_pence = int(snap.get("base_price_pence") or 0) if snap else 0
    total_snap = int(snap.get("total_price_pence") or 0) if snap else 0

    if not snap or (base_pence <= 0 and not addons):
        return _single_line_order_pdf_item(order)

    items: List[Dict[str, Any]] = []
    if base_pence > 0:
        items.append(
            {
                "description": service_name,
                "quantity": 1,
                "unit_pence": base_pence,
                "line_total_pence": base_pence,
            }
        )
    for a in addons:
        p = int(a.get("price_pence") or 0)
        n = str(a.get("name") or a.get("code") or "Add-on")
        items.append(
            {
                "description": n,
                "quantity": 1,
                "unit_pence": p,
                "line_total_pence": p,
            }
        )
    sum_items = sum(int(x["line_total_pence"]) for x in items)
    if total_snap and sum_items != total_snap:
        logger.warning(
            "Order %s pricing_snapshot line sum %s != total_price_pence %s; collapsing PDF lines",
            order.get("order_id"),
            sum_items,
            total_snap,
        )
        return _single_line_order_pdf_item(order)
    return items if items else _single_line_order_pdf_item(order)


def _payment_method_for_order(order: Dict[str, Any]) -> str:
    p = order.get("pricing") or {}
    pm = (p.get("payment_method") or p.get("payment_method_label") or "").strip()
    if pm:
        return pm
    if p.get("stripe_payment_intent_id") or p.get("stripe_checkout_session_id"):
        return "Card (Stripe)"
    return "Card (Stripe)"


def order_to_invoice_data(order: Dict[str, Any]) -> Dict[str, Any]:
    """Map orders collection document to branded PDF payload."""
    customer = order.get("customer") or {}
    snap = order.get("pricing_snapshot") or {}
    pricing = order.get("pricing") or {}
    total_pence = int(snap.get("total_price_pence") or pricing.get("total_amount") or 0)
    vat_pence = int(snap.get("vat_pence", pricing.get("vat_amount") or 0) or 0)
    currency = str(snap.get("currency") or pricing.get("currency") or "gbp")

    line_items = _build_order_line_items_for_pdf(order)
    sum_lines = sum(int(x["line_total_pence"]) for x in line_items)

    if vat_pence > 0:
        subtotal_pence = max(0, total_pence - vat_pence)
    else:
        subtotal_pence = sum_lines if line_items else total_pence

    paid_at = order.get("paid_at") or order.get("created_at")
    if isinstance(paid_at, datetime):
        date_str = paid_at.strftime("%d %B %Y %H:%M UTC")
    else:
        date_str = datetime.now(timezone.utc).strftime("%d %B %Y %H:%M UTC")

    invoice_number = str(order.get("invoice_number") or "")
    order_ref = str(order.get("order_ref") or order.get("order_id") or "—")

    first = line_items[0] if line_items else {}
    return {
        "document_title": "INVOICE" if vat_pence > 0 else "RECEIPT",
        "invoice_number": invoice_number,
        "order_reference": order_ref,
        "date_issued": date_str,
        "customer_name": customer.get("full_name") or "Customer",
        "customer_email": customer.get("email") or "",
        "line_items": line_items,
        "line_description": str(first.get("description") or "Service"),
        "line_quantity": int(first.get("quantity") or 1),
        "line_unit_pence": int(first.get("unit_pence") or 0),
        "line_total_pence": int(first.get("line_total_pence") or 0),
        "subtotal_pence": subtotal_pence,
        "vat_pence": vat_pence,
        "total_pence": total_pence,
        "currency": currency,
        "payment_status": "PAID",
        "payment_method": _payment_method_for_order(order),
    }


def build_order_receipt_pdf_bytes(order: Dict[str, Any]) -> bytes:
    """Sync PDF build; `order` must include `invoice_number` when required."""
    data = order_to_invoice_data(order)
    if not data.get("invoice_number"):
        raise ValueError("order.invoice_number is required to build invoice PDF")
    return build_branded_invoice_pdf_bytes(data)


async def _upload_pdf_to_gridfs(
    filename: str,
    pdf_bytes: bytes,
    metadata: Dict[str, Any],
) -> str:
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket

    db = database.get_db()
    fs = AsyncIOMotorGridFSBucket(db, bucket_name=GRIDFS_BUCKET)
    grid_id = await fs.upload_from_stream(filename, io.BytesIO(pdf_bytes), metadata=metadata)
    return str(grid_id)


async def _ensure_order_invoice_number(order_id: str, order: Dict[str, Any]) -> Dict[str, Any]:
    """Persist and return order dict with invoice_number."""
    if order.get("invoice_number"):
        return order
    inv = await allocate_invoice_number()
    now = datetime.now(timezone.utc)
    await database.get_db().orders.update_one(
        {"order_id": order_id},
        {"$set": {"invoice_number": inv, "updated_at": now}},
    )
    merged = {**order, "invoice_number": inv}
    return merged


async def _upload_receipt_pdf(order_id: str, invoice_number: str, pdf_bytes: bytes) -> str:
    safe_inv = re.sub(r"[^\w\-]+", "_", invoice_number)[:60]
    filename = f"{safe_inv}.pdf"
    meta = {
        "order_id": order_id,
        "invoice_number": invoice_number,
        "kind": "payment_receipt",
        "content_type": "application/pdf",
    }
    return await _upload_pdf_to_gridfs(filename, pdf_bytes, meta)


async def ensure_order_receipt_stored(
    order_id: str,
    order: Dict[str, Any],
    *,
    force_regenerate: bool = False,
) -> Tuple[bool, Optional[bytes], Optional[str]]:
    """
    Ensure order has branded invoice PDF in GridFS.
    Invoice number is allocated once per order and kept on regeneration.
    """
    db = database.get_db()
    existing_id = order.get("receipt_pdf_gridfs_id")
    if existing_id and not force_regenerate:
        try:
            b = await read_receipt_pdf_bytes(str(existing_id))
            if b:
                return True, b, None
        except Exception as e:
            logger.warning("Existing receipt unreadable for %s, regenerating: %s", order_id, e)

    try:
        order_with_inv = await _ensure_order_invoice_number(order_id, order)
        pdf_bytes = build_order_receipt_pdf_bytes(order_with_inv)
    except Exception as e:
        logger.exception("Order receipt PDF build failed for %s: %s", order_id, e)
        return False, None, str(e)

    inv = order_with_inv.get("invoice_number") or ""
    try:
        grid_id = await _upload_receipt_pdf(order_id, inv, pdf_bytes)
        now = datetime.now(timezone.utc)
        fn = f"{inv}.pdf"
        await db.orders.update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "receipt_pdf_gridfs_id": grid_id,
                    "receipt_pdf_filename": fn,
                    "receipt_generated_at": now,
                    "updated_at": now,
                }
            },
        )
    except Exception as e:
        logger.exception("Order receipt GridFS upload failed for %s: %s", order_id, e)
        return False, None, str(e)

    return True, pdf_bytes, None


async def read_receipt_pdf_bytes(gridfs_id: str) -> Optional[bytes]:
    try:
        db = database.get_db()
        from motor.motor_asyncio import AsyncIOMotorGridFSBucket

        fs = AsyncIOMotorGridFSBucket(db, bucket_name=GRIDFS_BUCKET)
        stream = io.BytesIO()
        await fs.download_to_stream(ObjectId(gridfs_id), stream)
        return stream.getvalue()
    except Exception as e:
        logger.error("read_receipt_pdf_bytes failed for %s: %s", gridfs_id, e)
        return None


async def get_receipt_for_order(
    order_id: str,
    order: Dict[str, Any],
    *,
    allow_generate: bool = False,
) -> Tuple[Optional[bytes], Optional[str]]:
    inv = order.get("invoice_number")
    fn = order.get("receipt_pdf_filename") or (f"{inv}.pdf" if inv else None) or f"{order.get('order_ref', order_id)}.pdf"
    gid = order.get("receipt_pdf_gridfs_id")
    if gid:
        data = await read_receipt_pdf_bytes(str(gid))
        if data:
            return data, fn

    if allow_generate:
        ok, pdf_bytes, err = await ensure_order_receipt_stored(order_id, order, force_regenerate=True)
        if ok and pdf_bytes:
            order_updated = await database.get_db().orders.find_one(
                {"order_id": order_id},
                {"_id": 0, "receipt_pdf_filename": 1, "invoice_number": 1},
            )
            if order_updated:
                fn = order_updated.get("receipt_pdf_filename") or fn
            return pdf_bytes, fn
        logger.error("Lazy receipt generation failed for %s: %s", order_id, err)

    return None, None


def subscription_session_to_invoice_data(
    *,
    invoice_number: str,
    order_reference: str,
    customer_name: str,
    customer_email: str,
    primary_line_description: str,
    amount_total_pence: int,
    currency: str,
    vat_pence: int = 0,
    payment_method: str = "Card (Stripe)",
    billing_period_start: Optional[datetime] = None,
    billing_period_end: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Payload for CVP subscription checkout receipt."""
    subtotal_pence = max(0, amount_total_pence - vat_pence)
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%d %B %Y %H:%M UTC")
    unit_pence = subtotal_pence if vat_pence else amount_total_pence
    line_total = subtotal_pence if vat_pence else amount_total_pence
    note = _format_billing_period_note(billing_period_start, billing_period_end)
    full_desc = f"{primary_line_description}\n{note}" if note else primary_line_description
    return {
        "document_title": "INVOICE" if vat_pence > 0 else "RECEIPT",
        "invoice_number": invoice_number,
        "order_reference": order_reference,
        "date_issued": date_str,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "line_items": [
            {
                "description": full_desc,
                "quantity": 1,
                "unit_pence": unit_pence,
                "line_total_pence": line_total,
            }
        ],
        "line_description": full_desc,
        "line_quantity": 1,
        "line_unit_pence": unit_pence,
        "line_total_pence": line_total,
        "subtotal_pence": subtotal_pence,
        "vat_pence": vat_pence,
        "total_pence": amount_total_pence,
        "currency": currency,
        "payment_status": "PAID",
        "payment_method": payment_method,
    }


async def ensure_subscription_checkout_invoice_pdf(
    *,
    client_id: str,
    checkout_session_id: str,
    session: Dict[str, Any],
    customer_name: str,
    customer_email: str,
    plan_code: "PlanCode",
    billing_period_start: Optional[datetime] = None,
    billing_period_end: Optional[datetime] = None,
) -> Tuple[bool, Optional[bytes], Optional[str], Optional[str]]:
    """
    Idempotent PDF for Stripe subscription checkout (CVP). Keyed by checkout_session_id.
    Returns (ok, pdf_bytes, invoice_number, error_message).
    """
    if not checkout_session_id:
        return False, None, None, "missing checkout_session_id"

    db = database.get_db()
    existing = await db[STRIPE_CHECKOUT_INVOICES].find_one({"_id": checkout_session_id})
    if existing and existing.get("gridfs_id"):
        b = await read_receipt_pdf_bytes(str(existing["gridfs_id"]))
        if b:
            return True, b, existing.get("invoice_number"), None

    amount_total = session.get("amount_total")
    if amount_total is None:
        amount_total = 0
    amount_total_pence = int(amount_total)
    currency = (session.get("currency") or "gbp").lower()
    td = session.get("total_details") or {}
    vat_pence = int(td.get("amount_tax") or 0)
    if not vat_pence and td.get("breakdown"):
        tax_vals = [t.get("amount", 0) for t in (td.get("breakdown") or {}).get("taxes", []) or []]
        vat_pence = int(sum(tax_vals)) if tax_vals else 0

    from services.plan_registry import plan_registry

    inv = await allocate_invoice_number()
    ref_display = checkout_session_id
    primary_line = plan_registry.format_cvp_invoice_product_line(plan_code)
    data = subscription_session_to_invoice_data(
        invoice_number=inv,
        order_reference=ref_display,
        customer_name=customer_name or "Customer",
        customer_email=customer_email or "",
        primary_line_description=primary_line,
        amount_total_pence=amount_total_pence,
        currency=currency,
        vat_pence=vat_pence,
        billing_period_start=billing_period_start,
        billing_period_end=billing_period_end,
    )
    try:
        pdf_bytes = build_branded_invoice_pdf_bytes(data)
    except Exception as e:
        logger.exception("Subscription invoice PDF build failed: %s", e)
        return False, None, None, str(e)

    safe_inv = re.sub(r"[^\w\-]+", "_", inv)[:60]
    filename = f"{safe_inv}.pdf"
    meta = {
        "client_id": client_id,
        "stripe_session_id": checkout_session_id,
        "invoice_number": inv,
        "kind": "subscription_checkout_receipt",
        "content_type": "application/pdf",
    }
    try:
        grid_id = await _upload_pdf_to_gridfs(filename, pdf_bytes, meta)
        now = datetime.now(timezone.utc)
        await db[STRIPE_CHECKOUT_INVOICES].update_one(
            {"_id": checkout_session_id},
            {
                "$set": {
                    "client_id": client_id,
                    "invoice_number": inv,
                    "gridfs_id": grid_id,
                    "filename": filename,
                    "created_at": now,
                    "amount_total_pence": amount_total_pence,
                    "currency": currency,
                    "payment_status": "PAID",
                }
            },
            upsert=True,
        )
        await db.clients.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "last_subscription_invoice_number": inv,
                    "last_subscription_receipt_gridfs_id": grid_id,
                    "last_subscription_receipt_session_id": checkout_session_id,
                    "updated_at": now,
                }
            },
        )
    except Exception as e:
        logger.exception("Subscription invoice storage failed: %s", e)
        return False, None, None, str(e)

    return True, pdf_bytes, inv, None
