"""Canonical subscription payment ledger (financial evidence).

Rows are inserted/updated only when Stripe confirms invoice status ``paid``.
Operational webhook history remains in ``stripe_events``; normalized analytics
payments remain in ``payments``. This ledger powers admin last-payment /
receipts reconciliation without conflating audit logs with ledger rows.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import stripe
from pymongo.errors import DuplicateKeyError

from database import database

logger = logging.getLogger(__name__)

COLLECTION_NAME = "subscription_payment_ledger"

PAYMENT_EVIDENCE_STRIPE_EVENT_TYPES = frozenset(
    {
        "checkout.session.completed",
        "invoice.paid",
        "invoice.payment_succeeded",
    }
)


def _dt_from_unix(ts: Any) -> Optional[datetime]:
    try:
        if ts is None:
            return None
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _payment_intent_id(inv: Dict[str, Any]) -> Optional[str]:
    pi = inv.get("payment_intent")
    if isinstance(pi, dict):
        rid = str(pi.get("id") or "").strip()
        return rid or None
    if isinstance(pi, str):
        rid = pi.strip()
        return rid or None
    return None


def _charge_id(inv: Dict[str, Any]) -> Optional[str]:
    ch = inv.get("charge")
    if isinstance(ch, dict):
        rid = str(ch.get("id") or "").strip()
        return rid or None
    if isinstance(ch, str):
        rid = ch.strip()
        return rid or None
    return None


def _receipt_url(inv: Dict[str, Any]) -> Optional[str]:
    ch = inv.get("charge")
    if isinstance(ch, dict):
        url = str(ch.get("receipt_url") or "").strip()
        return url or None
    return None


def _period_from_invoice_lines(inv: Dict[str, Any]) -> Tuple[Optional[datetime], Optional[datetime]]:
    lines = ((inv.get("lines") or {}).get("data") or []) if isinstance(inv.get("lines"), dict) else []
    if not lines or not isinstance(lines[0], dict):
        return None, None
    period = lines[0].get("period") or {}
    if not isinstance(period, dict):
        return None, None
    return _dt_from_unix(period.get("start")), _dt_from_unix(period.get("end"))


def _paid_at_from_invoice(inv: Dict[str, Any]) -> Optional[datetime]:
    st = inv.get("status_transitions") or {}
    return _dt_from_unix(st.get("paid_at")) or _dt_from_unix(inv.get("created"))


def build_ledger_doc(
    *,
    client_id: str,
    stripe_customer_id: str,
    stripe_subscription_id: str,
    invoice_dict: Dict[str, Any],
    source_event_type: str,
    source_event_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    inv_id = str(invoice_dict.get("id") or "").strip()
    if not inv_id:
        return None
    if str(invoice_dict.get("status") or "").lower() != "paid":
        return None
    try:
        amount_paid = int(invoice_dict.get("amount_paid") or 0)
    except (TypeError, ValueError):
        amount_paid = 0

    cur = str(invoice_dict.get("currency") or "gbp").lower()
    paid_at = _paid_at_from_invoice(invoice_dict) or datetime.now(timezone.utc)
    ps = _dt_from_unix(invoice_dict.get("period_start"))
    pe = _dt_from_unix(invoice_dict.get("period_end"))
    if ps is None or pe is None:
        l_ps, l_pe = _period_from_invoice_lines(invoice_dict)
        ps = ps or l_ps
        pe = pe or l_pe

    now = datetime.now(timezone.utc)
    inv_pdf = str(invoice_dict.get("invoice_pdf") or "").strip() or None
    hosted = str(invoice_dict.get("hosted_invoice_url") or "").strip() or None
    stripe_num = str(invoice_dict.get("number") or "").strip() or None

    return {
        "client_id": client_id,
        "stripe_customer_id": stripe_customer_id,
        "stripe_subscription_id": stripe_subscription_id,
        "stripe_invoice_id": inv_id,
        "stripe_payment_intent_id": _payment_intent_id(invoice_dict),
        "stripe_charge_id": _charge_id(invoice_dict),
        "amount_paid": amount_paid,
        "currency": cur,
        "paid_at": paid_at,
        "period_start": ps,
        "period_end": pe,
        "invoice_pdf": inv_pdf,
        "hosted_invoice_url": hosted,
        "receipt_url": _receipt_url(invoice_dict),
        "stripe_invoice_number": stripe_num,
        "source_event_type": source_event_type,
        "source_event_id": str(source_event_id or "").strip() or None,
        "status": "paid",
        "updated_at": now,
    }


async def upsert_subscription_payment_ledger_row(
    *,
    client_id: str,
    stripe_customer_id: str,
    stripe_subscription_id: str,
    invoice_dict: Dict[str, Any],
    source_event_type: str,
    source_event_id: Optional[str],
) -> bool:
    doc = build_ledger_doc(
        client_id=client_id,
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
        invoice_dict=invoice_dict,
        source_event_type=source_event_type,
        source_event_id=source_event_id,
    )
    if not doc:
        return False
    db = database.get_db()
    if db is None:
        return False
    inv_id = doc["stripe_invoice_id"]
    now = datetime.now(timezone.utc)
    try:
        await db[COLLECTION_NAME].update_one(
            {"stripe_invoice_id": inv_id},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    except DuplicateKeyError:
        logger.info("subscription_payment_ledger duplicate upsert suppressed invoice_id=%s", inv_id)
    return True


async def fetch_latest_paid_ledger_for_client(client_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    if db is None:
        return None
    row = await db[COLLECTION_NAME].find_one(
        {"client_id": client_id, "status": "paid"},
        {"_id": 0},
        sort=[("paid_at", -1)],
    )
    return row


def ledger_row_to_billing_payment_overlay(ledger: Dict[str, Any]) -> Dict[str, Any]:
    overlay: Dict[str, Any] = {}
    paid_at = ledger.get("paid_at")
    if paid_at:
        overlay["last_payment_at"] = paid_at
    try:
        overlay["last_payment_amount_pence"] = int(ledger.get("amount_paid") or 0)
    except (TypeError, ValueError):
        overlay["last_payment_amount_pence"] = 0
    overlay["last_payment_status"] = "paid"
    iid = (ledger.get("stripe_invoice_id") or "").strip()
    if iid:
        overlay["last_payment_stripe_invoice_id"] = iid
    num = (ledger.get("stripe_invoice_number") or "").strip()
    if num:
        overlay["last_payment_invoice_number"] = num
    cur = (ledger.get("currency") or "").strip()
    if cur:
        overlay["last_payment_currency"] = cur.lower()
    se = (ledger.get("source_event_id") or "").strip()
    if se:
        overlay["last_payment_source_event_id"] = se
    return overlay


async def sync_client_billing_last_payment_from_latest_ledger(client_id: str) -> bool:
    row = await fetch_latest_paid_ledger_for_client(client_id)
    if not row:
        return False
    db = database.get_db()
    if db is None:
        return False
    overlay = ledger_row_to_billing_payment_overlay(row)
    overlay["updated_at"] = datetime.now(timezone.utc)
    await db.client_billing.update_one({"client_id": client_id}, {"$set": overlay})
    return True


async def reconcile_client_subscription_payment_ledger(
    client_id: str,
    *,
    from_stripe_events: bool = True,
    from_stripe_invoice_api_limit: int = 0,
) -> Dict[str, Any]:
    """Idempotent reconciliation: hydrate ledger from archived webhook pointers and/or Stripe API."""
    db = database.get_db()
    if db is None:
        return {"client_id": client_id, "ok": False, "reason": "no_database"}

    billing = (
        await db.client_billing.find_one({"client_id": client_id}, {"_id": 0}) or {}
    )
    upserted_invoice_ids: List[str] = []
    skipped: List[str] = []
    errors: List[str] = []

    async def _do_invoice(inv_id: str, source_evt_type: str, source_evt_id: str) -> None:
        if not inv_id.startswith("in_"):
            return
        try:
            inv_x = stripe.Invoice.retrieve(
                inv_id, expand=["lines.data.price", "payment_intent", "charge"]
            )
            inv_dict = inv_x.to_dict() if hasattr(inv_x, "to_dict") else dict(inv_x)
            if str(inv_dict.get("status") or "").lower() != "paid":
                skipped.append(f"{inv_id}:not_paid")
                return
            ok = await upsert_subscription_payment_ledger_row(
                client_id=client_id,
                stripe_customer_id=str(
                    inv_dict.get("customer") or billing.get("stripe_customer_id") or ""
                ),
                stripe_subscription_id=str(
                    inv_dict.get("subscription") or billing.get("stripe_subscription_id") or ""
                ),
                invoice_dict=inv_dict,
                source_event_type=source_evt_type,
                source_event_id=source_evt_id or None,
            )
            if ok:
                upserted_invoice_ids.append(inv_id)
        except Exception as ex:  # noqa: BLE001
            errors.append(f"{inv_id}:{ex}")  # capped narrative
            logger.warning(
                "reconcile ledger invoice retrieve failed client_id=%s invoice_id=%s err=%s",
                client_id,
                inv_id,
                ex,
                exc_info=True,
            )

    if from_stripe_events:
        cursor = db.stripe_events.find(
            {
                "related_client_id": client_id,
                "status": "PROCESSED",
                "type": {"$in": sorted(PAYMENT_EVIDENCE_STRIPE_EVENT_TYPES)},
            },
            {"_id": 0, "type": 1, "event_id": 1, "raw_minimal": 1},
        ).sort("created", -1).limit(500)
        processed_checkouts: set[str] = set()
        async for ev in cursor:
            et = str(ev.get("type") or "")
            eid = str(ev.get("event_id") or "")
            raw = ev.get("raw_minimal") or {}
            oid = str(raw.get("object_id") or "").strip()
            if et in {"invoice.paid", "invoice.payment_succeeded"} and oid.startswith("in_"):
                await _do_invoice(oid, f"reconcile:{et}", eid)
            elif et == "checkout.session.completed" and oid.startswith("cs_"):
                if oid in processed_checkouts:
                    continue
                processed_checkouts.add(oid)
                try:
                    sess = stripe.checkout.Session.retrieve(
                        oid, expand=["invoice", "subscription"]
                    )
                    sdict = sess.to_dict() if hasattr(sess, "to_dict") else dict(sess)
                    inv_ref = sdict.get("invoice")
                    inv_key = (
                        inv_ref.strip()
                        if isinstance(inv_ref, str)
                        else str((inv_ref or {}).get("id") or "").strip()
                    )
                    if inv_key.startswith("in_"):
                        await _do_invoice(inv_key, "reconcile:checkout.session.completed", eid)
                except Exception as ex:  # noqa: BLE001
                    errors.append(f"{oid}:{ex}")

    lim = max(0, min(int(from_stripe_invoice_api_limit or 0), 100))
    if lim > 0 and stripe.api_key:
        cid = billing.get("stripe_customer_id") or ""
        if isinstance(cid, str) and cid.startswith("cus_"):
            try:
                inv_iter = stripe.Invoice.list(customer=cid, limit=lim)
                data = getattr(inv_iter, "data", None) or []
                for inv_obj in data:
                    inv_dict = inv_obj.to_dict() if hasattr(inv_obj, "to_dict") else dict(inv_obj)
                    iid = str(inv_dict.get("id") or "").strip()
                    if not iid:
                        continue
                    await _do_invoice(iid, "reconcile:stripe_invoice.list", "")
            except Exception as ex:  # noqa: BLE001
                errors.append(f"invoice_list:{ex}")

    synced = False
    if upserted_invoice_ids:
        synced = await sync_client_billing_last_payment_from_latest_ledger(client_id)

    return {
        "client_id": client_id,
        "ok": True,
        "upserted_invoice_ids": sorted(set(upserted_invoice_ids)),
        "upsert_count": len(set(upserted_invoice_ids)),
        "skipped": skipped[:50],
        "errors": [e[:800] for e in errors[:20]],
        "client_billing_last_payment_synced": synced,
    }
