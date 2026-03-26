"""
Live data tools for the public support assistant.
All account-specific facts come from Mongo after verification (CRN + email or order ref + email).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from database import database

CRN_PATTERN = re.compile(
    r"\b(PLE-[A-Z]{2,10}-\d{4}-\d{4,}|[A-Z]{2,}-\d{4}-\d{4,})\b",
    re.I,
)
ORDER_REF_PATTERN = re.compile(r"\b(PLE-\d{8}-\d{4})\b", re.I)
EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
)


def extract_verification_tokens(message: str) -> Dict[str, Optional[str]]:
    """Pull CRN, order reference, and first email from free text."""
    text = message or ""
    crn_m = CRN_PATTERN.search(text.upper())
    order_m = ORDER_REF_PATTERN.search(text.upper())
    emails = EMAIL_PATTERN.findall(text)
    return {
        "crn": crn_m.group(1).upper() if crn_m else None,
        "order_ref": order_m.group(1).upper() if order_m else None,
        "email": emails[0].lower() if emails else None,
    }


async def resolve_client_by_crn_email(crn: str, email: str) -> Optional[Dict[str, Any]]:
    """Return minimal client doc fields if CRN + email match; else None."""
    db = database.get_db()
    c = await db["clients"].find_one(
        {"customer_reference": crn.upper()},
        {
            "_id": 0,
            "client_id": 1,
            "email": 1,
            "full_name": 1,
            "subscription_status": 1,
            "onboarding_status": 1,
            "provisioning_status": 1,
            "activation_email_status": 1,
            "activation_email_sent_at": 1,
            "customer_reference": 1,
            "created_at": 1,
        },
    )
    if not c:
        return None
    if (c.get("email") or "").lower() != (email or "").lower():
        return None
    return c


def _iso_utc(dt: Any) -> Optional[str]:
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        try:
            return dt.isoformat()
        except Exception:
            return str(dt)
    return str(dt)


async def get_onboarding_snapshot_for_verified_client(client: Dict[str, Any]) -> Dict[str, Any]:
    """Facts for onboarding / setup questions (no internal IDs beyond what user already has)."""
    db = database.get_db()
    client_id = client.get("client_id")
    pending_uploads = await db["documents"].count_documents(
        {"client_id": client_id, "status": "UPLOADED"}
    )
    return {
        "onboarding_status": client.get("onboarding_status"),
        "provisioning_status": client.get("provisioning_status"),
        "activation_email_status": client.get("activation_email_status"),
        "activation_email_sent_at": _iso_utc(client.get("activation_email_sent_at")),
        "subscription_status": client.get("subscription_status"),
        "documents_awaiting_processing_count": int(pending_uploads),
    }


async def get_billing_subscription_snapshot(client_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    row = await db["client_billing"].find_one(
        {"client_id": client_id},
        {
            "_id": 0,
            "subscription_status": 1,
            "current_plan_code": 1,
            "cancel_at_period_end": 1,
            "current_period_end": 1,
            "entitlement_status": 1,
        },
    )
    if not row:
        return None
    out = dict(row)
    cpe = out.get("current_period_end")
    out["current_period_end"] = _iso_utc(cpe) if cpe is not None else None
    return out


async def list_recent_checkout_receipt_summaries(client_id: str, limit: int = 8) -> List[Dict[str, Any]]:
    from services.order_receipt_service import STRIPE_CHECKOUT_INVOICES

    db = database.get_db()
    cur = (
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
            },
        )
        .sort("created_at", -1)
        .limit(limit)
    )
    out: List[Dict[str, Any]] = []
    async for doc in cur:
        out.append(
            {
                "invoice_number": doc.get("invoice_number") or str(doc.get("_id")),
                "created_at": _iso_utc(doc.get("created_at")),
                "amount_total_pence": doc.get("amount_total_pence"),
                "currency": doc.get("currency"),
                "payment_status": doc.get("payment_status"),
            }
        )
    return out


async def lookup_order_for_email(order_ref: str, email: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Returns ("ok", summary), ("not_found", None), or ("email_mismatch", None).
    """
    db = database.get_db()
    order = await db["orders"].find_one(
        {"order_ref": order_ref.upper()},
        {
            "_id": 0,
            "order_ref": 1,
            "status": 1,
            "workflow_state": 1,
            "service_name": 1,
            "service_code": 1,
            "created_at": 1,
            "updated_at": 1,
            "customer": 1,
            "sla_hours": 1,
        },
    )
    if not order:
        return "not_found", None
    cust = order.get("customer") or {}
    em = (cust.get("email") or "").lower()
    if em != (email or "").lower():
        return "email_mismatch", None
    return "ok", {
        "order_ref": order.get("order_ref"),
        "status": order.get("status") or order.get("workflow_state"),
        "service_name": order.get("service_name"),
        "service_code": order.get("service_code"),
        "created_at": _iso_utc(order.get("created_at")),
        "updated_at": _iso_utc(order.get("updated_at")),
        "sla_hours": order.get("sla_hours"),
    }


def format_tool_answer_account_overview(
    snapshot: Dict[str, Any],
    billing: Optional[Dict[str, Any]],
    receipts: List[Dict[str, Any]],
) -> str:
    lines = [
        "Here is what we can confirm from your account (verified with your CRN and email):",
        "",
        f"• **Subscription (client record):** {snapshot.get('subscription_status') or 'unknown'}",
        f"• **Onboarding:** {snapshot.get('onboarding_status') or 'unknown'}",
        f"• **Provisioning:** {snapshot.get('provisioning_status') or 'unknown'}",
        f"• **Activation email:** {snapshot.get('activation_email_status') or 'unknown'}",
    ]
    if snapshot.get("activation_email_sent_at"):
        lines.append(f"  – Last activation email timestamp: {snapshot['activation_email_sent_at']}")
    pc = snapshot.get("documents_awaiting_processing_count")
    if pc is not None:
        lines.append(f"• **Documents awaiting processing:** {pc}")
    lines.append("")
    if billing:
        lines.append("**Billing (subscription record):**")
        lines.append(f"• Status: {billing.get('subscription_status') or 'unknown'}")
        lines.append(f"• Plan: {billing.get('current_plan_code') or 'unknown'}")
        lines.append(f"• Entitlement: {billing.get('entitlement_status') or 'unknown'}")
        if billing.get("cancel_at_period_end"):
            lines.append("• Cancels at end of current period: yes")
        if billing.get("current_period_end"):
            lines.append(f"• Current period ends: {billing['current_period_end']}")
    else:
        lines.append("No separate subscription billing record is on file (common for document-only purchases).")
    lines.append("")
    if receipts:
        lines.append("**Recent subscription checkout receipts (newest first):**")
        for r in receipts[:5]:
            amt = r.get("amount_total_pence")
            cur = (r.get("currency") or "gbp").lower()
            gbp = f"£{int(amt)/100:.2f}" if amt is not None and cur == "gbp" else f"{amt} {cur}"
            lines.append(
                f"• {r.get('invoice_number') or '—'} — {gbp} — {r.get('payment_status') or ''} — {r.get('created_at') or ''}"
            )
    else:
        lines.append("No subscription receipt rows found in the portal ledger for this account.")
    lines.extend([
        "",
        "Sign in to manage billing and download receipts: use **Billing** in your dashboard.",
    ])
    return "\n".join(lines)


def format_tool_answer_order(order: Dict[str, Any]) -> str:
    return "\n".join([
        "Order verified with your email:",
        "",
        f"• **Reference:** {order.get('order_ref')}",
        f"• **Status:** {order.get('status')}",
        f"• **Service:** {order.get('service_name') or order.get('service_code')}",
        f"• **Created:** {order.get('created_at') or '—'}",
        f"• **Updated:** {order.get('updated_at') or '—'}",
        "",
        "If something looks stuck or the SLA has passed, say **speak to a human** and we will prioritise it.",
    ])


ASK_VERIFY = (
    "To look that up securely, please send your **CRN** (e.g. PLE-CVP-2026-01234) and the **email address on the account**, in one message."
)

ASK_ORDER_VERIFY = (
    "To check an order, send your **order reference** (e.g. PLE-20260326-0001) and the **email used at checkout**, in one message."
)
