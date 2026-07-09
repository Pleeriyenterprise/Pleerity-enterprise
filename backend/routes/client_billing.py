"""
Client billing / subscription receipts (CVP portal).
Self-service list, latest, detail, and PDF download — scoped to authenticated client_id only.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from database import database
from middleware import client_route_guard
from middleware.capability_gating import assert_client_capability
from models import AuditAction
from services.order_receipt_service import (
    CVP_SUBSCRIPTION_RENEWAL_RECEIPTS,
    STRIPE_CHECKOUT_INVOICES,
    read_receipt_pdf_bytes,
)
from utils.app_urls import get_api_base_url
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/client/billing", tags=["client-billing"])


def _money_display(pence: Optional[int], currency: str) -> Optional[str]:
    if pence is None:
        return None
    cur = (currency or "gbp").upper()
    sym = "£" if cur in ("GBP", "GB") else f"{cur} "
    return f"{sym}{pence / 100:.2f}" + ("" if sym else f" {cur}")


def _receipt_kind_from_doc(doc: Dict[str, Any]) -> str:
    sid = doc.get("_id")
    if isinstance(sid, str) and sid.startswith("in_"):
        return "subscription_renewal"
    return "subscription_checkout"


def _pdf_download_url(receipt_id: str) -> str:
    """Absolute API URL for authenticated PDF download."""
    base = get_api_base_url().rstrip("/")
    safe = quote(receipt_id, safe="")
    return f"{base}/api/client/billing/receipt/{safe}/download"


def _doc_to_summary(doc: Dict[str, Any], *, receipt_kind: str = "subscription_checkout") -> Dict[str, Any]:
    inv = doc.get("invoice_number") or ""
    sid = doc.get("_id")
    created = doc.get("paid_at") if receipt_kind == "subscription_renewal" else doc.get("created_at")
    if isinstance(created, datetime):
        date_issued = created.isoformat()
    else:
        date_issued = str(created) if created else None
    cur = (doc.get("currency") or "gbp").upper()
    pence = doc.get("amount_total_pence")
    breakdown = doc.get("billing_breakdown")
    if not isinstance(breakdown, list):
        breakdown = []
    line_descriptions = [str(x.get("description") or "").strip() for x in breakdown if isinstance(x, dict)]
    line_summary = "; ".join(line_descriptions[:4]) if line_descriptions else None
    out: Dict[str, Any] = {
        "receipt_id": inv,
        "receipt_kind": receipt_kind,
        "stripe_checkout_session_id": sid if receipt_kind == "subscription_checkout" else None,
        "stripe_invoice_id": str(sid) if receipt_kind == "subscription_renewal" and sid else None,
        "invoice_number": inv,
        "date_issued": date_issued,
        "amount_total_pence": pence,
        "amount_display": _money_display(pence, cur),
        "currency": cur,
        "payment_status": doc.get("payment_status") or "PAID",
        "pdf_download_url": _pdf_download_url(inv) if inv else None,
        "billing_breakdown": breakdown,
        "line_summary": line_summary,
    }
    if receipt_kind == "subscription_renewal":
        h = (doc.get("hosted_invoice_url") or "").strip()
        if h:
            out["hosted_invoice_url"] = h
        sn = doc.get("stripe_invoice_number")
        if sn:
            out["stripe_invoice_number"] = sn
        bps = doc.get("billing_period_start")
        bpe = doc.get("billing_period_end")
        if isinstance(bps, datetime):
            out["billing_period_start"] = bps.isoformat()
        elif bps:
            out["billing_period_start"] = str(bps)
        if isinstance(bpe, datetime):
            out["billing_period_end"] = bpe.isoformat()
        elif bpe:
            out["billing_period_end"] = str(bpe)
    return out


async def _find_receipt_for_client(client_id: str, receipt_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    col = db[STRIPE_CHECKOUT_INVOICES]
    doc = await col.find_one({"client_id": client_id, "invoice_number": receipt_id})
    if doc:
        return doc
    if receipt_id.startswith("cs_"):
        doc = await col.find_one({"_id": receipt_id, "client_id": client_id})
        if doc:
            return doc
    rcol = db[CVP_SUBSCRIPTION_RENEWAL_RECEIPTS]
    rdoc = await rcol.find_one({"client_id": client_id, "invoice_number": receipt_id})
    if rdoc:
        return rdoc
    if receipt_id.startswith("in_"):
        rdoc2 = await rcol.find_one({"_id": receipt_id, "client_id": client_id})
        if rdoc2:
            return rdoc2
    # Fallback: pinned fields on client (e.g. ledger row missing)
    cl = await db.clients.find_one(
        {"client_id": client_id, "last_subscription_invoice_number": receipt_id},
        {
            "_id": 0,
            "last_subscription_receipt_gridfs_id": 1,
            "last_subscription_receipt_session_id": 1,
            "updated_at": 1,
        },
    )
    if cl and cl.get("last_subscription_receipt_gridfs_id"):
        return {
            "_id": cl.get("last_subscription_receipt_session_id"),
            "client_id": client_id,
            "invoice_number": receipt_id,
            "gridfs_id": cl["last_subscription_receipt_gridfs_id"],
            "filename": f"{receipt_id}.pdf",
            "created_at": cl.get("updated_at"),
            "amount_total_pence": None,
            "currency": "gbp",
            "payment_status": "PAID",
        }
    return None


@router.get("/receipts")
async def list_subscription_receipts(current_user: dict = Depends(client_route_guard)):
    """Subscription checkout and renewal receipts for this client (newest first by issued date)."""
    await assert_client_capability(current_user, "CAP_BILLING_INVOICES", "read")
    client_id = current_user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="Missing client context")
    db = database.get_db()
    cursor = (
        db[STRIPE_CHECKOUT_INVOICES]
        .find(
            {"client_id": client_id},
            {
                "_id": 1,
                "invoice_number": 1,
                "created_at": 1,
                "amount_total_pence": 1,
                "currency": 1,
                "payment_status": 1,
                "billing_breakdown": 1,
            },
        )
        .sort("created_at", -1)
        .limit(100)
    )
    docs = await cursor.to_list(100)
    rcur = (
        db[CVP_SUBSCRIPTION_RENEWAL_RECEIPTS]
        .find(
            {"client_id": client_id},
            {
                "_id": 1,
                "invoice_number": 1,
                "paid_at": 1,
                "created_at": 1,
                "amount_total_pence": 1,
                "currency": 1,
                "payment_status": 1,
                "billing_breakdown": 1,
                "hosted_invoice_url": 1,
                "stripe_invoice_number": 1,
                "billing_period_start": 1,
                "billing_period_end": 1,
            },
        )
        .sort("paid_at", -1)
        .limit(100)
    )
    rdocs = await rcur.to_list(100)
    merged: list[tuple[datetime, Dict[str, Any], str]] = []
    for d in docs:
        ts = d.get("created_at")
        if not isinstance(ts, datetime):
            ts = datetime.min.replace(tzinfo=timezone.utc)
        merged.append((ts, d, "subscription_checkout"))
    for d in rdocs:
        ts = d.get("paid_at") or d.get("created_at")
        if not isinstance(ts, datetime):
            ts = datetime.min.replace(tzinfo=timezone.utc)
        merged.append((ts, d, "subscription_renewal"))
    merged.sort(key=lambda x: x[0], reverse=True)
    receipts = [_doc_to_summary(d, receipt_kind=k) for _, d, k in merged[:100]]
    return {"receipts": receipts, "count": len(receipts)}


@router.get("/receipt/latest")
async def get_latest_subscription_receipt(current_user: dict = Depends(client_route_guard)):
    """Most recent checkout or renewal receipt, or synthetic row from client `last_subscription_*` if both empty."""
    await assert_client_capability(current_user, "CAP_BILLING_INVOICES", "read")
    client_id = current_user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="Missing client context")
    db = database.get_db()
    cur = db[STRIPE_CHECKOUT_INVOICES].find({"client_id": client_id}).sort("created_at", -1).limit(1)
    docs = await cur.to_list(1)
    doc = docs[0] if docs else None
    rcur = db[CVP_SUBSCRIPTION_RENEWAL_RECEIPTS].find({"client_id": client_id}).sort("paid_at", -1).limit(1)
    rdocs = await rcur.to_list(1)
    rdoc = rdocs[0] if rdocs else None
    if doc and rdoc:
        d_ts = doc.get("created_at")
        r_ts = rdoc.get("paid_at") or rdoc.get("created_at")
        if isinstance(r_ts, datetime) and (not isinstance(d_ts, datetime) or r_ts >= d_ts):
            return {"receipt": _doc_to_summary(rdoc, receipt_kind="subscription_renewal")}
        return {"receipt": _doc_to_summary(doc)}
    if doc:
        return {"receipt": _doc_to_summary(doc)}
    if rdoc:
        return {"receipt": _doc_to_summary(rdoc, receipt_kind="subscription_renewal")}
    client = await db.clients.find_one(
        {"client_id": client_id},
        {
            "_id": 0,
            "last_subscription_invoice_number": 1,
            "last_subscription_receipt_gridfs_id": 1,
            "last_subscription_receipt_session_id": 1,
            "updated_at": 1,
        },
    )
    if not client or not client.get("last_subscription_invoice_number") or not client.get("last_subscription_receipt_gridfs_id"):
        return {"receipt": None}
    inv = client["last_subscription_invoice_number"]
    ua = client.get("updated_at")
    if isinstance(ua, datetime):
        date_issued = ua.isoformat()
    else:
        date_issued = datetime.now(timezone.utc).isoformat()
    return {
        "receipt": {
            "receipt_id": inv,
            "stripe_checkout_session_id": client.get("last_subscription_receipt_session_id"),
            "invoice_number": inv,
            "date_issued": date_issued,
            "amount_total_pence": None,
            "amount_display": None,
            "currency": "GBP",
            "payment_status": "PAID",
            "pdf_download_url": _pdf_download_url(inv),
        }
    }


@router.get("/receipt/{receipt_id}")
async def get_subscription_receipt(receipt_id: str, current_user: dict = Depends(client_route_guard)):
    """Single receipt metadata by invoice number (or Stripe session id `cs_...`)."""
    await assert_client_capability(current_user, "CAP_BILLING_INVOICES", "read")
    client_id = current_user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="Missing client context")
    doc = await _find_receipt_for_client(client_id, receipt_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return {"receipt": _doc_to_summary(doc, receipt_kind=_receipt_kind_from_doc(doc))}


@router.get("/receipt/{receipt_id}/download")
async def download_subscription_receipt(
    receipt_id: str,
    request: Request,
    current_user: dict = Depends(client_route_guard),
):
    """Stream PDF; restricted to owning client."""
    await assert_client_capability(current_user, "CAP_BILLING_INVOICES", "read")
    client_id = current_user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="Missing client context")
    doc = await _find_receipt_for_client(client_id, receipt_id)
    if not doc or not doc.get("gridfs_id"):
        raise HTTPException(status_code=404, detail="Receipt not found")
    pdf = await read_receipt_pdf_bytes(str(doc["gridfs_id"]))
    if not pdf:
        raise HTTPException(status_code=404, detail="Receipt file not available")
    filename = doc.get("filename") or f"{doc.get('invoice_number', 'receipt')}.pdf"
    try:
        await create_audit_log(
            action=AuditAction.ORDER_RECEIPT_PDF_ACCESSED,
            client_id=client_id,
            actor_id=current_user.get("portal_user_id"),
            resource_type="subscription_receipt",
            resource_id=str(doc.get("invoice_number") or receipt_id),
            metadata={
                "channel": "cvp_portal_billing",
                "stripe_session_id": doc.get("_id"),
                "path": str(request.url.path),
            },
        )
    except Exception as e:
        logger.warning("Receipt access audit failed: %s", e)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
