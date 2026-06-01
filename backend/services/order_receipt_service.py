"""
Paid order / subscription checkout: invoice PDF (branded), GridFS, invoice numbers.

Order PDF line items:
  Built from ``orders.pricing_snapshot``: ``base_price_pence`` as the main service row and
  each entry in ``addons`` (``name``, ``price_pence``) as its own row. If the sum of those
  lines does not match ``total_price_pence``, a single collapsed line is used (logged).

CVP subscription checkout PDF:
  Line items from expanded Checkout Session ``line_items`` (subscription vs setup fee), or
  reconstructed from ``Subscription.retrieve`` + recorded setup fee when expand is missing.
  Optional ``Billing period: …`` note is appended to the subscription line only.
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
from services.billing_period_utils import (
    period_end_from_stripe_subscription_dict,
    period_start_from_stripe_subscription_dict,
)
from services.invoice_pdf_builder import build_branded_invoice_pdf_bytes

logger = logging.getLogger(__name__)

GRIDFS_BUCKET = "order_files"
STRIPE_CHECKOUT_INVOICES = "stripe_checkout_invoices"
# Subscription renewals / proration invoices (invoice.paid) — not checkout sessions
CVP_SUBSCRIPTION_RENEWAL_RECEIPTS = "cvp_subscription_renewal_receipts"


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


async def build_order_receipt_pdf_bytes(order: Dict[str, Any]) -> bytes:
    """Build receipt PDF; applies resolver when ``order`` has ``client_id``."""
    from services.branding_resolver_service import prepare_invoice_pdf_data_with_branding

    data = order_to_invoice_data(order)
    if not data.get("invoice_number"):
        raise ValueError("order.invoice_number is required to build invoice PDF")
    cid = (order.get("client_id") or "").strip() or None
    if cid:
        data = await prepare_invoice_pdf_data_with_branding(cid, data)
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
        pdf_bytes = await build_order_receipt_pdf_bytes(order_with_inv)
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
    setup_fee_amount_cents: Optional[int] = None,
    force_regenerate: bool = False,
) -> Tuple[bool, Optional[bytes], Optional[str], Optional[str]]:
    """
    Idempotent PDF for Stripe subscription checkout (CVP). Keyed by checkout_session_id.
    Returns (ok, pdf_bytes, invoice_number, error_message).

    ``force_regenerate`` (admin): rebuild PDF from Stripe; keeps existing ``invoice_number`` and
    ``created_at`` when the ledger row already exists; updates GridFS id and line breakdown.
    """
    if not checkout_session_id:
        return False, None, None, "missing checkout_session_id"

    db = database.get_db()
    existing = await db[STRIPE_CHECKOUT_INVOICES].find_one({"_id": checkout_session_id})
    if force_regenerate:
        if existing and existing.get("client_id") and existing.get("client_id") != client_id:
            return False, None, None, "checkout session ledger belongs to a different client"
    elif existing and existing.get("gridfs_id"):
        b = await read_receipt_pdf_bytes(str(existing["gridfs_id"]))
        if b:
            return True, b, existing.get("invoice_number"), None

    import os

    import stripe
    from services.billing_line_normalization import build_checkout_pdf_lines_and_breakdown
    from services.plan_registry import plan_registry

    session_dict: Dict[str, Any] = dict(session) if isinstance(session, dict) else {}
    from services.stripe_mode_authority import configure_stripe_sdk

    configure_stripe_sdk()
    if stripe.api_key:
        try:
            full = stripe.checkout.Session.retrieve(
                checkout_session_id,
                expand=["line_items.data.price"],
            )
            session_dict = full.to_dict() if hasattr(full, "to_dict") else dict(full)
        except Exception as e:
            logger.warning("Could not expand checkout session for itemised PDF: %s", e)

    amount_total = session_dict.get("amount_total")
    if amount_total is None:
        amount_total = 0
    amount_total_pence = int(amount_total)
    currency = (session_dict.get("currency") or "gbp").lower()
    td = session_dict.get("total_details") or {}
    vat_pence = int(td.get("amount_tax") or 0)
    if not vat_pence and td.get("breakdown"):
        tax_vals = [t.get("amount", 0) for t in (td.get("breakdown") or {}).get("taxes", []) or []]
        vat_pence = int(sum(tax_vals)) if tax_vals else 0

    note = _format_billing_period_note(billing_period_start, billing_period_end)
    pdf_rows, breakdown = build_checkout_pdf_lines_and_breakdown(
        session_dict, plan_code, billing_period_note=note
    )
    net_subtotal = max(0, amount_total_pence - vat_pence)
    stripe_sub_raw = session_dict.get("subscription")
    stripe_sub_id = (
        stripe_sub_raw.get("id")
        if isinstance(stripe_sub_raw, dict)
        else (stripe_sub_raw or "")
    )
    if not pdf_rows:
        pdf_rows, breakdown = _fallback_checkout_lines_from_subscription(
            str(stripe_sub_id),
            plan_code,
            setup_fee_amount_cents=setup_fee_amount_cents,
            billing_period_note=note,
            net_expected_pence=net_subtotal,
        )

    if force_regenerate and existing and existing.get("invoice_number"):
        inv = str(existing["invoice_number"])
    else:
        inv = await allocate_invoice_number()
    ref_display = checkout_session_id
    if not pdf_rows:
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
    else:
        data = _subscription_checkout_multiline_invoice_data(
            invoice_number=inv,
            order_reference=ref_display,
            customer_name=customer_name or "Customer",
            customer_email=customer_email or "",
            line_items=pdf_rows,
            amount_total_pence=amount_total_pence,
            currency=currency,
            vat_pence=vat_pence,
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
        sub_part = sum(x["amount"] for x in breakdown if x.get("type") == "subscription")
        setup_part = sum(x["amount"] for x in breakdown if x.get("type") == "setup_fee")
        created_at = (existing or {}).get("created_at") if force_regenerate else None
        if created_at is None:
            created_at = now
        ledger: Dict[str, Any] = {
            "client_id": client_id,
            "invoice_number": inv,
            "gridfs_id": grid_id,
            "filename": filename,
            "created_at": created_at,
            "amount_total_pence": amount_total_pence,
            "currency": currency,
            "payment_status": "PAID",
            "billing_breakdown": breakdown,
        }
        if force_regenerate:
            ledger["pdf_regenerated_at"] = now
        if sub_part:
            ledger["subscription_amount_pence"] = sub_part
        if setup_part:
            ledger["setup_fee_amount_pence"] = setup_part
        await db[STRIPE_CHECKOUT_INVOICES].update_one(
            {"_id": checkout_session_id},
            {"$set": ledger},
            upsert=True,
        )
        pin = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "last_subscription_receipt_session_id": 1},
        )
        pinned_sid = (pin or {}).get("last_subscription_receipt_session_id")
        update_client_pointer = (not force_regenerate) or (
            pinned_sid == checkout_session_id or pinned_sid is None
        )
        if update_client_pointer:
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


def _subscription_checkout_multiline_invoice_data(
    *,
    invoice_number: str,
    order_reference: str,
    customer_name: str,
    customer_email: str,
    line_items: List[Dict[str, Any]],
    amount_total_pence: int,
    currency: str,
    vat_pence: int = 0,
    payment_method: str = "Card (Stripe)",
) -> Dict[str, Any]:
    subtotal_pence = max(0, amount_total_pence - vat_pence)
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%d %B %Y %H:%M UTC")
    sum_lines = sum(int(x.get("line_total_pence") or 0) for x in line_items)
    if line_items and sum_lines != subtotal_pence:
        logger.warning(
            "subscription checkout PDF: line sum %s != subtotal %s (vat=%s total=%s)",
            sum_lines,
            subtotal_pence,
            vat_pence,
            amount_total_pence,
        )
    first = line_items[0] if line_items else {}
    return {
        "document_title": "INVOICE" if vat_pence > 0 else "RECEIPT",
        "invoice_number": invoice_number,
        "order_reference": order_reference,
        "date_issued": date_str,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "line_items": line_items,
        "line_description": str(first.get("description") or "Service"),
        "line_quantity": int(first.get("quantity") or 1),
        "line_unit_pence": int(first.get("unit_pence") or 0),
        "line_total_pence": int(first.get("line_total_pence") or 0),
        "subtotal_pence": subtotal_pence,
        "vat_pence": vat_pence,
        "total_pence": amount_total_pence,
        "currency": currency,
        "payment_status": "PAID",
        "payment_method": payment_method,
    }


def _fallback_checkout_lines_from_subscription(
    subscription_id: str,
    plan_code: "PlanCode",
    *,
    setup_fee_amount_cents: Optional[int],
    billing_period_note: Optional[str],
    net_expected_pence: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    import os

    import stripe
    from services.billing_line_normalization import (
        setup_line_description,
        subscription_line_description,
    )

    from services.stripe_mode_authority import configure_stripe_sdk

    configure_stripe_sdk()
    if not stripe.api_key or not subscription_id:
        return [], []
    try:
        sub = stripe.Subscription.retrieve(subscription_id, expand=["items.data.price"])
        sub_d = sub.to_dict() if hasattr(sub, "to_dict") else dict(sub)
    except Exception as e:
        logger.warning("fallback checkout lines: Subscription.retrieve failed: %s", e)
        return [], []
    pdf_rows: List[Dict[str, Any]] = []
    breakdown: List[Dict[str, Any]] = []
    for item in (sub_d.get("items") or {}).get("data") or []:
        price = item.get("price") or {}
        if isinstance(price, dict) and price.get("recurring") is not None:
            ua = int(price.get("unit_amount") or 0)
            desc = subscription_line_description(plan_code)
            if billing_period_note:
                desc = f"{desc}\n{billing_period_note}"
            pdf_rows.append(
                {"description": desc, "quantity": 1, "unit_pence": ua, "line_total_pence": ua}
            )
            breakdown.append(
                {
                    "type": "subscription",
                    "description": subscription_line_description(plan_code),
                    "amount": ua,
                }
            )
            break
    sf = int(setup_fee_amount_cents or 0)
    if sf > 0:
        sdesc = setup_line_description(plan_code)
        pdf_rows.append(
            {"description": sdesc, "quantity": 1, "unit_pence": sf, "line_total_pence": sf}
        )
        breakdown.append({"type": "setup_fee", "description": sdesc, "amount": sf})
    sum_lines = sum(r["line_total_pence"] for r in pdf_rows)
    if pdf_rows and net_expected_pence != sum_lines:
        adj = net_expected_pence - sum_lines
        if adj != 0:
            pdf_rows.append(
                {
                    "description": "Billing adjustment",
                    "quantity": 1,
                    "unit_pence": adj,
                    "line_total_pence": adj,
                }
            )
            breakdown.append({"type": "adjustment", "description": "Billing adjustment", "amount": adj})
    return pdf_rows, breakdown


async def regenerate_subscription_checkout_invoice_pdf_for_client(
    client_id: str,
    checkout_session_id: str,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Admin/maintenance: re-fetch Stripe Checkout Session and rebuild itemised PDF for an existing
    ``stripe_checkout_invoices`` row. Preserves invoice number and original ``created_at``.

    Returns (success, invoice_number_if_ok, error_message).
    """
    import os

    import stripe

    if not checkout_session_id.startswith("cs_"):
        return False, None, "checkout_session_id must be a Stripe id (cs_...)"

    db = database.get_db()
    row = await db[STRIPE_CHECKOUT_INVOICES].find_one({"_id": checkout_session_id, "client_id": client_id})
    if not row:
        return False, None, "No subscription checkout ledger row for this client and session id"

    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})
    client_row = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "contact_name": 1, "full_name": 1, "email": 1, "contact_email": 1, "billing_plan": 1},
    )
    if not client_row:
        return False, None, "Client not found"

    from services.plan_registry import plan_registry

    plan_str = (billing or {}).get("current_plan_code") or client_row.get("billing_plan") or "PLAN_1_SOLO"
    plan_code = plan_registry.resolve_plan_code(str(plan_str))

    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    from services.stripe_mode_authority import configure_stripe_sdk

    configure_stripe_sdk()
    sub_id = (billing or {}).get("stripe_subscription_id")
    if sub_id and stripe.api_key:
        try:
            sub = stripe.Subscription.retrieve(sub_id, expand=["items.data.price"])
            sub_d = sub.to_dict() if hasattr(sub, "to_dict") else dict(sub)
            period_start = period_start_from_stripe_subscription_dict(sub_d)
            period_end = period_end_from_stripe_subscription_dict(sub_d)
        except Exception as e:
            logger.warning("regenerate receipt: Subscription.retrieve failed: %s", e)

    setup_fee = (billing or {}).get("setup_fee_amount_cents")
    name = (client_row.get("contact_name") or client_row.get("full_name") or "Customer").strip()
    email = (client_row.get("email") or client_row.get("contact_email") or "").strip()

    ok, _pdf, inv_no, err = await ensure_subscription_checkout_invoice_pdf(
        client_id=client_id,
        checkout_session_id=checkout_session_id,
        session={},
        customer_name=name,
        customer_email=email,
        plan_code=plan_code,
        billing_period_start=period_start,
        billing_period_end=period_end,
        setup_fee_amount_cents=int(setup_fee) if setup_fee is not None else None,
        force_regenerate=True,
    )
    if not ok:
        return False, None, err or "PDF regeneration failed"
    return True, inv_no, None


def _breakdown_rows_to_pdf_line_items(breakdown: Any) -> List[Dict[str, Any]]:
    if not isinstance(breakdown, list) or not breakdown:
        return []
    out: List[Dict[str, Any]] = []
    for row in breakdown:
        if not isinstance(row, dict):
            continue
        amt = int(row.get("amount") or 0)
        desc = str(row.get("description") or row.get("type") or "Subscription").strip() or "Subscription"
        out.append({"description": desc, "quantity": 1, "unit_pence": amt, "line_total_pence": amt})
    return out


async def persist_cvp_subscription_renewal_receipt(
    *,
    client_id: str,
    stripe_invoice_id: str,
    stripe_invoice_dict: Dict[str, Any],
    pleerity_invoice_number: Optional[str],
    paid_at: datetime,
    billing_period_start: Optional[datetime],
    billing_period_end: Optional[datetime],
    amount_total_pence: int,
    currency: str,
    hosted_invoice_url: Optional[str],
    billing_breakdown: Optional[List[Dict[str, Any]]],
    plan_code: Any,
    customer_name: str,
    customer_email: str,
    billing_reason: str,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Upsert a renewal/proration receipt row + optional Pleerity PDF (GridFS).
    Document _id is the Stripe invoice id (in_...) for idempotency across invoice.paid / payment_succeeded.

    ``pleerity_invoice_number``: if None, reuse an existing row's number or allocate a new INV-YYYY-NNNNNN.

    Returns (ok, error_message, gridfs_id_or_none).
    """
    from services.plan_registry import plan_registry

    db = database.get_db()
    existing_full = await db[CVP_SUBSCRIPTION_RENEWAL_RECEIPTS].find_one({"_id": stripe_invoice_id})
    if existing_full and existing_full.get("invoice_number"):
        inv_no = str(existing_full["invoice_number"])
    elif pleerity_invoice_number:
        inv_no = str(pleerity_invoice_number)
    else:
        inv_no = await allocate_invoice_number()
    tax_vals = []
    for t in (stripe_invoice_dict.get("total_tax_amounts") or []) or []:
        try:
            tax_vals.append(int(t.get("amount") or 0))
        except (TypeError, ValueError):
            continue
    vat_pence = int(sum(tax_vals)) if tax_vals else 0
    if not vat_pence:
        td_obj = stripe_invoice_dict.get("total_details") or {}
        try:
            vat_pence = int(td_obj.get("amount_tax") or 0)
        except (TypeError, ValueError):
            vat_pence = 0

    note = _format_billing_period_note(billing_period_start, billing_period_end)
    pdf_rows = _breakdown_rows_to_pdf_line_items(billing_breakdown)
    if not pdf_rows:
        primary = plan_registry.format_cvp_invoice_product_line(plan_code) if plan_code else "Subscription"
        full_desc = f"{primary}\n{note}" if note else primary
        data = subscription_session_to_invoice_data(
            invoice_number=inv_no,
            order_reference=stripe_invoice_id,
            customer_name=customer_name or "Customer",
            customer_email=customer_email or "",
            primary_line_description=full_desc,
            amount_total_pence=amount_total_pence,
            currency=currency,
            vat_pence=vat_pence,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
        )
    else:
        if note:
            adj = []
            for i, r in enumerate(pdf_rows):
                if i == 0:
                    d = str(r.get("description") or "")
                    r = {**r, "description": f"{d}\n{note}".strip() if d else note}
                adj.append(r)
            pdf_rows = adj
        data = _subscription_checkout_multiline_invoice_data(
            invoice_number=inv_no,
            order_reference=stripe_invoice_id,
            customer_name=customer_name or "Customer",
            customer_email=customer_email or "",
            line_items=pdf_rows,
            amount_total_pence=amount_total_pence,
            currency=currency,
            vat_pence=vat_pence,
        )
    data["date_issued"] = paid_at.strftime("%d %B %Y %H:%M UTC")

    pdf_bytes: Optional[bytes] = None
    pdf_err: Optional[str] = None
    try:
        pdf_bytes = build_branded_invoice_pdf_bytes(data)
    except Exception as e:
        logger.warning("Renewal receipt PDF build failed client_id=%s inv=%s: %s", client_id, stripe_invoice_id, e)
        pdf_err = str(e)

    gridfs_id: Optional[str] = None
    safe_inv = re.sub(r"[^\w\-]+", "_", inv_no)[:60]
    filename = f"{safe_inv}.pdf"
    if pdf_bytes:
        try:
            meta = {
                "client_id": client_id,
                "stripe_invoice_id": stripe_invoice_id,
                "invoice_number": inv_no,
                "kind": "subscription_renewal_receipt",
                "content_type": "application/pdf",
            }
            gridfs_id = await _upload_pdf_to_gridfs(filename, pdf_bytes, meta)
        except Exception as e:
            logger.warning("Renewal receipt GridFS upload failed client_id=%s: %s", client_id, e)
            pdf_err = (pdf_err or "") + str(e)

    now = datetime.now(timezone.utc)
    stripe_num = (stripe_invoice_dict.get("number") or "").strip() or None
    ledger: Dict[str, Any] = {
        "client_id": client_id,
        "invoice_number": inv_no,
        "stripe_invoice_id": stripe_invoice_id,
        "stripe_invoice_number": stripe_num,
        "hosted_invoice_url": (hosted_invoice_url or "").strip() or None,
        "billing_reason": billing_reason,
        "amount_total_pence": amount_total_pence,
        "currency": (currency or "gbp").lower(),
        "payment_status": "PAID",
        "paid_at": paid_at,
        "billing_period_start": billing_period_start,
        "billing_period_end": billing_period_end,
        "billing_breakdown": billing_breakdown or [],
        "pdf_build_error": pdf_err,
        "updated_at": now,
    }
    if gridfs_id:
        ledger["gridfs_id"] = gridfs_id
        ledger["filename"] = filename
    elif existing_full and existing_full.get("gridfs_id"):
        ledger["gridfs_id"] = existing_full["gridfs_id"]
        ledger["filename"] = existing_full.get("filename") or filename
    existing = await db[CVP_SUBSCRIPTION_RENEWAL_RECEIPTS].find_one({"_id": stripe_invoice_id}, {"_id": 0, "created_at": 1})
    if not existing or not existing.get("created_at"):
        ledger["created_at"] = now
    try:
        await db[CVP_SUBSCRIPTION_RENEWAL_RECEIPTS].update_one(
            {"_id": stripe_invoice_id},
            {"$set": ledger},
            upsert=True,
        )
    except Exception as e:
        logger.exception("persist_cvp_subscription_renewal_receipt failed: %s", e)
        return False, str(e), gridfs_id
    return True, None, gridfs_id
