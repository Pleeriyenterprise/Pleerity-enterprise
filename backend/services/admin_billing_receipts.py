"""
Admin Billing — aggregate receipt/invoice list and resend helpers.

Uses canonical storage only:
- `stripe_checkout_invoices` + GridFS (subscription checkout PDFs)
- `orders` + `receipt_pdf_gridfs_id` (intake / one-off service PDFs)
"""
from __future__ import annotations

import base64
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from database import database
from services.order_receipt_service import (
    STRIPE_CHECKOUT_INVOICES,
    get_receipt_for_order,
    order_to_invoice_data,
    read_receipt_pdf_bytes,
)
from services.plan_registry import plan_registry

logger = logging.getLogger(__name__)

# Order statuses that imply payment captured (receipt-relevant)
_ORDER_POST_PAYMENT_STATUSES = frozenset(
    {
        "PAID",
        "QUEUED",
        "IN_PROGRESS",
        "DRAFT_READY",
        "INTERNAL_REVIEW",
        "REGEN_REQUESTED",
        "REGENERATING",
        "CLIENT_INPUT_REQUIRED",
        "FINALISING",
        "DELIVERING",
        "COMPLETED",
        "DELIVERY_FAILED",
        "FAILED",
    }
)


def _client_email_set(client_doc: Dict[str, Any]) -> Set[str]:
    out: Set[str] = set()
    for key in ("email", "contact_email"):
        v = (client_doc.get(key) or "").strip().lower()
        if v:
            out.add(v)
    return out


def _order_source_detail(order: Dict[str, Any]) -> str:
    if order.get("source_draft_id"):
        return "intake_order"
    ot = str(order.get("order_type") or "").upper()
    if "CVP" in ot or order.get("cvp_user_ref"):
        return "cvp_order"
    return "one_off_order"


def _dt_iso(v: Any) -> Optional[str]:
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v) if v else None


def _money_display(pence: Optional[int], currency: str) -> Optional[str]:
    if pence is None:
        return None
    cur = (currency or "gbp").upper()
    sym = "£" if cur in ("GBP", "GB") else f"{cur} "
    return f"{sym}{pence / 100:.2f}"


def _subscription_row(
    doc: Dict[str, Any],
    *,
    synthetic: bool = False,
) -> Dict[str, Any]:
    inv = doc.get("invoice_number") or ""
    sid = doc.get("_id")
    created = doc.get("created_at")
    cur = (doc.get("currency") or "gbp").upper()
    pence = doc.get("amount_total_pence")
    gid = doc.get("gridfs_id")
    return {
        "source": "subscription",
        "source_detail": "subscription_checkout",
        "receipt_key": f"subscription:{inv or sid}",
        "invoice_number": inv,
        "order_reference": str(sid) if sid is not None else "",
        "stripe_checkout_session_id": str(sid) if sid is not None else None,
        "date_issued": _dt_iso(created),
        "amount_total_pence": pence,
        "amount_display": _money_display(pence, cur),
        "currency": cur,
        "payment_status": (doc.get("payment_status") or "PAID").upper(),
        "payment_method": "Card (Stripe)",
        "pdf_available": bool(gid),
        "receipt_generated_at": _dt_iso(created) if gid else None,
        "email_sent_at": _dt_iso(doc.get("receipt_email_sent_at")),
        "synthetic_ledger": synthetic,
    }


def _order_row(order: Dict[str, Any]) -> Dict[str, Any]:
    oid = order.get("order_id") or ""
    snap = order.get("pricing_snapshot") or {}
    pricing = order.get("pricing") or {}
    total_pence = int(snap.get("total_price_pence") or pricing.get("total_amount") or 0)
    cur = str(snap.get("currency") or pricing.get("currency") or "gbp").upper()
    inv = order.get("invoice_number") or ""
    ref = order.get("order_ref") or oid
    paid_at = order.get("paid_at") or order.get("created_at")
    gid = order.get("receipt_pdf_gridfs_id")

    try:
        pm = order_to_invoice_data(order).get("payment_method") or "Card (Stripe)"
    except Exception:
        pm = "Card (Stripe)"
    return {
        "source": "order",
        "source_detail": _order_source_detail(order),
        "receipt_key": f"order:{oid}",
        "invoice_number": inv,
        "order_reference": ref,
        "stripe_checkout_session_id": None,
        "date_issued": _dt_iso(paid_at),
        "amount_total_pence": total_pence,
        "amount_display": _money_display(total_pence, cur),
        "currency": cur,
        "payment_status": "PAID" if order.get("paid_at") or order.get("status") in _ORDER_POST_PAYMENT_STATUSES else "PENDING",
        "payment_method": pm,
        "pdf_available": bool(gid),
        "receipt_generated_at": _dt_iso(order.get("receipt_generated_at")),
        "email_sent_at": _dt_iso(order.get("order_confirmation_email_sent_at")),
        "synthetic_ledger": False,
        "order_id": oid,
    }


async def list_receipts_for_client(
    client_id: str,
    *,
    type_filter: str = "all",
    status_filter: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = 200,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Merge subscription ledger rows and paid orders linked by client_id or customer email.
    """
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        return [], {}

    emails = _client_email_set(client)
    rows: List[Dict[str, Any]] = []

    # --- Subscription checkout invoices ---
    if type_filter in ("all", "subscription", "subscription_checkout"):
        cur = (
            db[STRIPE_CHECKOUT_INVOICES]
            .find({"client_id": client_id})
            .sort("created_at", -1)
            .limit(500)
        )
        subs = await cur.to_list(500)
        seen_inv = {d.get("invoice_number") for d in subs if d.get("invoice_number")}
        for d in subs:
            rows.append(_subscription_row(d))
        # Pinned last receipt on client if not in ledger (same as portal fallback)
        pin_inv = client.get("last_subscription_invoice_number")
        pin_gid = client.get("last_subscription_receipt_gridfs_id")
        if pin_inv and pin_inv not in seen_inv and pin_gid:
            synthetic_doc = {
                "_id": client.get("last_subscription_receipt_session_id") or f"pinned_{pin_inv}",
                "client_id": client_id,
                "invoice_number": pin_inv,
                "gridfs_id": pin_gid,
                "filename": f"{pin_inv}.pdf",
                "created_at": client.get("updated_at"),
                "amount_total_pence": None,
                "currency": "gbp",
                "payment_status": "PAID",
            }
            rows.append(_subscription_row(synthetic_doc, synthetic=True))

    # --- Orders (paid / post-payment) ---
    if type_filter in ("all", "order", "intake_order", "one_off_order", "cvp_order"):
        or_clauses: List[Dict[str, Any]] = [{"client_id": client_id}]
        for em in emails:
            or_clauses.append(
                {"customer.email": {"$regex": f"^{re.escape(em)}$", "$options": "i"}}
            )
        oquery: Dict[str, Any] = {
            "$and": [
                {"$or": or_clauses},
                {
                    "$or": [
                        {"paid_at": {"$exists": True, "$ne": None}},
                        {"status": {"$in": list(_ORDER_POST_PAYMENT_STATUSES)}},
                    ]
                },
            ]
        }
        ocursor = db.orders.find(oquery).sort([("paid_at", -1), ("created_at", -1)]).limit(500)
        orders = await ocursor.to_list(500)
        for o in orders:
            o.pop("_id", None)
            row = _order_row(o)
            sd = row["source_detail"]
            if type_filter == "intake_order" and sd != "intake_order":
                continue
            if type_filter == "one_off_order" and sd != "one_off_order":
                continue
            if type_filter == "cvp_order" and sd != "cvp_order":
                continue
            if type_filter == "order" and row["source"] != "order":
                continue
            rows.append(row)

    # --- Filters ---
    def _parse_status(s: Optional[str]) -> Optional[str]:
        if not s:
            return None
        return s.strip().upper()

    st = _parse_status(status_filter)
    if st:
        rows = [r for r in rows if (r.get("payment_status") or "").upper() == st]

    if date_from or date_to:
        filtered: List[Dict[str, Any]] = []
        for r in rows:
            raw = r.get("date_issued")
            if not raw:
                filtered.append(r)
                continue
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except Exception:
                filtered.append(r)
                continue
            if date_from and dt < date_from:
                continue
            if date_to and dt > date_to:
                continue
            filtered.append(r)
        rows = filtered

    rows.sort(
        key=lambda x: x.get("date_issued") or "",
        reverse=True,
    )
    rows = rows[:limit]

    meta = {
        "client_id": client_id,
        "count": len(rows),
        "email_match_used": bool(emails),
    }
    return rows, meta


async def get_subscription_receipt_doc_for_client(
    client_id: str,
    ref: str,
) -> Optional[Dict[str, Any]]:
    """ref = invoice_number or Stripe checkout session id cs_..."""
    db = database.get_db()
    col = db[STRIPE_CHECKOUT_INVOICES]
    doc = await col.find_one({"client_id": client_id, "invoice_number": ref})
    if doc:
        return doc
    if ref.startswith("cs_"):
        return await col.find_one({"_id": ref, "client_id": client_id})
    # Pinned-only
    cl = await db.clients.find_one(
        {"client_id": client_id, "last_subscription_invoice_number": ref},
        {
            "_id": 0,
            "last_subscription_receipt_gridfs_id": 1,
            "last_subscription_invoice_number": 1,
            "last_subscription_receipt_session_id": 1,
            "updated_at": 1,
        },
    )
    if cl and cl.get("last_subscription_receipt_gridfs_id"):
        return {
            "_id": cl.get("last_subscription_receipt_session_id") or f"pinned_{ref}",
            "client_id": client_id,
            "invoice_number": ref,
            "gridfs_id": cl["last_subscription_receipt_gridfs_id"],
            "filename": f"{ref}.pdf",
            "created_at": cl.get("updated_at"),
            "amount_total_pence": None,
            "currency": "gbp",
            "payment_status": "PAID",
        }
    return None


async def get_order_for_client(client_id: str, order_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    order = await db.orders.find_one({"order_id": order_id})
    if not order:
        return None
    emails = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "email": 1, "contact_email": 1})
    emset = _client_email_set(emails or {})
    if order.get("client_id") == client_id:
        return order
    ce = ((order.get("customer") or {}).get("email") or "").strip().lower()
    if ce and ce in emset:
        return order
    return None


async def admin_resend_subscription_receipt_email(
    *,
    client_id: str,
    ref: str,
    admin_portal_user_id: Optional[str],
) -> Tuple[bool, str]:
    """
    Resend SUBSCRIPTION_CONFIRMED with PDF attachment from canonical GridFS.
    ref: invoice_number or cs_ session id.
    """
    from services.notification_orchestrator import notification_orchestrator
    from utils.audit import create_audit_log
    from models import AuditAction, UserRole

    doc = await get_subscription_receipt_doc_for_client(client_id, ref)
    if not doc or not doc.get("gridfs_id"):
        return False, "Subscription receipt not found or PDF not available"

    client = await database.get_db().clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "full_name": 1, "contact_name": 1, "email": 1, "contact_email": 1, "customer_reference": 1, "billing_plan": 1},
    )
    if not client:
        return False, "Client not found"

    client_name = (client.get("contact_name") or client.get("full_name") or "Valued Customer").strip()
    client_email = (client.get("email") or client.get("contact_email") or "").strip()
    if not client_email:
        return False, "Client has no email on file"

    pdf = await read_receipt_pdf_bytes(str(doc["gridfs_id"]))
    if not pdf:
        return False, "Could not read PDF from storage"

    inv = doc.get("invoice_number") or ref
    plan_code_str = client.get("billing_plan") or "PLAN_1_SOLO"
    plan_def = plan_registry.get_plan_by_code_string(plan_code_str) or {}
    plan_name = plan_def.get("name") or plan_code_str

    pence = doc.get("amount_total_pence")
    currency = (doc.get("currency") or "gbp").strip().upper()
    if pence is not None:
        sym = "£" if currency == "GBP" else ""
        amt_display = f"{sym}{int(pence) / 100:.2f}" + ("" if sym else f" {currency}")
    else:
        amt_display = f"£{plan_def.get('monthly_price', 0):.2f}/month + £{plan_def.get('onboarding_fee', 0):.2f} setup"

    created = doc.get("created_at")
    if isinstance(created, datetime):
        payment_date_display = created.strftime("%d %B %Y %H:%M UTC")
    else:
        payment_date_display = datetime.now(timezone.utc).strftime("%d %B %Y %H:%M UTC")

    sid = str(doc.get("_id") or "")
    support_email = (os.getenv("SUPPORT_EMAIL") or "info@pleerityenterprise.co.uk").strip()
    sub_ctx = {
        "payment_receipt_layout": "structured",
        "client_name": client_name,
        "plan_name": plan_name,
        "amount_display": amt_display,
        "payment_date_display": payment_date_display,
        "reference_display": sid or ref,
        "support_email": support_email,
        "customer_reference": client.get("customer_reference") or "",
        "subject": "Payment received — Compliance Vault Pro",
        "attachments": [
            {
                "Name": f"{inv}.pdf",
                "Content": base64.b64encode(pdf).decode("utf-8"),
                "ContentType": "application/pdf",
            }
        ],
    }

    idem = f"admin_resend_sub_{client_id}_{ref}_{uuid.uuid4().hex}"
    result = await notification_orchestrator.send(
        template_key="SUBSCRIPTION_CONFIRMED",
        client_id=client_id,
        context=sub_ctx,
        idempotency_key=idem,
        event_type="admin_resend_subscription_receipt",
    )
    ok = result.outcome in ("sent", "duplicate_ignored")
    if not ok:
        return False, (result.error_message or result.block_reason or "Email send failed")[:500]

    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=admin_portal_user_id,
        client_id=client_id,
        resource_type="subscription_receipt",
        resource_id=str(inv),
        metadata={
            "action_type": "ADMIN_RECEIPT_RESENT",
            "channel": "email",
            "template_key": "SUBSCRIPTION_CONFIRMED",
            "recipient": client_email,
            "invoice_number": inv,
            "stripe_session_id": sid,
        },
    )
    return True, client_email


async def admin_resend_order_receipt_email(
    *,
    client_id: str,
    order_id: str,
    admin_portal_user_id: Optional[str],
) -> Tuple[bool, str]:
    from services.intake_draft_service import admin_resend_order_confirmation_email
    from utils.audit import create_audit_log
    from models import AuditAction, UserRole

    order = await get_order_for_client(client_id, order_id)
    if not order:
        return False, "Order not found or not linked to this client"

    ok, msg = await admin_resend_order_confirmation_email(order_id)
    if ok:
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=admin_portal_user_id,
            client_id=client_id,
            resource_type="order",
            resource_id=order_id,
            metadata={
                "action_type": "ADMIN_RECEIPT_RESENT",
                "channel": "email",
                "template_key": "ORDER_CONFIRMATION",
            },
        )
    return ok, msg
