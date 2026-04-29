"""
Single implementation for admin customer discovery (support / billing entry).

Used by GET /api/admin/search (canonical) and GET /api/admin/billing/clients/search (compatibility wrapper).
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from services.billing_presentation import lifecycle_status_label
from services.client_lifecycle_service import default_active_client_match


def _iso(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, str) and val.strip():
        return val.strip()
    return None


def _with_visibility(query: Dict[str, Any], visibility_match: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not visibility_match:
        return query
    return {"$and": [query, visibility_match]}


CLIENT_SEARCH_PROJECTION: Dict[str, int] = {
    "_id": 0,
    "client_id": 1,
    "customer_reference": 1,
    "full_name": 1,
    "email": 1,
    "company_name": 1,
    "subscription_status": 1,
    "onboarding_status": 1,
    "billing_plan": 1,
    "phone": 1,
    "created_at": 1,
    "client_lifecycle_status": 1,
    "is_deleted": 1,
    "is_test_like": 1,
    "entitlement_status": 1,
    "billing_lifecycle_state": 1,
    "canonical_entitlement_state": 1,
}

BILLING_ENRICH_PROJECTION: Dict[str, int] = {
    "_id": 0,
    "client_id": 1,
    "stripe_customer_id": 1,
    "stripe_subscription_id": 1,
    "current_period_end": 1,
    "last_payment_at": 1,
    "billing_last_synced_at": 1,
    "billing_sync_state": 1,
    "billing_lifecycle_state": 1,
    "cancel_at_period_end": 1,
    "billing_reconciliation_needed": 1,
    "billing_reconciliation_reason": 1,
    "canonical_entitlement_state": 1,
}


def _plan_label(plan_code: Optional[str]) -> str:
    if not plan_code:
        return "—"
    try:
        from services.plan_registry import plan_registry

        d = plan_registry.get_plan_by_code_string(str(plan_code))
        return str(d.get("name") or plan_code) if d else str(plan_code)
    except Exception:
        return str(plan_code)


def _build_support_row(
    client: Dict[str, Any],
    billing: Optional[Dict[str, Any]],
    property_count: int,
    *,
    plan_label_override: Optional[str] = None,
) -> Dict[str, Any]:
    cid = client.get("client_id") or ""
    b = billing or {}
    has_sub = bool(b.get("stripe_subscription_id"))
    lifecycle_lbl = lifecycle_status_label(
        has_subscription=has_sub,
        cancel_at_period_end=bool(b.get("cancel_at_period_end")),
        billing_lifecycle_state=b.get("billing_lifecycle_state"),
    )
    sync_state = (b.get("billing_sync_state") or "unknown") or "unknown"
    rec_flag = bool(b.get("billing_reconciliation_needed"))
    billing_sync_label = sync_state + (" · reconciliation flagged" if rec_flag else "")

    plan_code = client.get("billing_plan")
    plan_label = plan_label_override if plan_label_override is not None else _plan_label(plan_code)

    row: Dict[str, Any] = {
        **client,
        "client_name": client.get("full_name"),
        "crn": client.get("customer_reference"),
        "name": client.get("full_name"),
        "plan": plan_code,
        "plan_name": plan_label,
        "current_plan": plan_code,
        "current_plan_label": plan_label,
        "status": client.get("subscription_status"),
        "property_count": property_count,
        "last_payment_date": _iso(b.get("last_payment_at")),
        "next_renewal_date": _iso(b.get("current_period_end")),
        "billing_sync_state": sync_state,
        "billing_sync_label": billing_sync_label,
        "billing_reconciliation_status": "needed" if rec_flag else "ok",
        "billing_last_synced_at": _iso(b.get("billing_last_synced_at")),
        "subscription_lifecycle_label": lifecycle_lbl,
        "stripe_customer_id": b.get("stripe_customer_id"),
        "stripe_subscription_id": b.get("stripe_subscription_id"),
        "primary_support_url": f"/admin/clients/{cid}",
        "canonical_entitlement_state": b.get("canonical_entitlement_state") or client.get("canonical_entitlement_state"),
    }
    # Billing UI legacy aliases (no sensitive payment payloads)
    row["contact_name"] = client.get("full_name")
    row["contact_email"] = client.get("email")
    return row


async def _property_client_ids(db: Any, search_term: str, cap: int) -> List[str]:
    pc = search_term.upper().replace(" ", "")
    qprop = {
        "$or": [
            {"postcode": {"$regex": pc, "$options": "i"}},
            {"address_line_1": {"$regex": search_term, "$options": "i"}},
            {"address": {"$regex": search_term, "$options": "i"}},
        ]
    }
    props = await db.properties.find(qprop, {"_id": 0, "client_id": 1}).limit(cap).to_list(cap)
    return [p["client_id"] for p in props if p.get("client_id")]


async def _stripe_hit_client_ids(db: Any, term: str, limit: int) -> List[str]:
    t = term.strip()
    if re.match(r"^cus_[A-Za-z0-9]+$", t):
        cur = db.client_billing.find({"stripe_customer_id": t}, {"_id": 0, "client_id": 1}).limit(limit)
        rows = await cur.to_list(limit)
        return [r["client_id"] for r in rows if r.get("client_id")]
    if re.match(r"^sub_[A-Za-z0-9]+$", t):
        cur = db.client_billing.find({"stripe_subscription_id": t}, {"_id": 0, "client_id": 1}).limit(limit)
        rows = await cur.to_list(limit)
        return [r["client_id"] for r in rows if r.get("client_id")]
    return []


async def run_admin_client_support_search(
    db: Any,
    *,
    search_term: str,
    limit: int,
    include_archived: bool = False,
) -> List[Dict[str, Any]]:
    """
    Return merged client rows with billing/property enrichment (support-safe fields only).
    """
    term = (search_term or "").strip()
    if len(term) < 2:
        return []

    visibility_match: Optional[Dict[str, Any]] = None if include_archived else default_active_client_match()
    search_regex = {"$regex": term, "$options": "i"}

    client_query: Dict[str, Any] = {
        "$or": [
            {"customer_reference": search_regex},
            {"email": search_regex},
            {"full_name": search_regex},
            {"company_name": search_regex},
            {"phone": search_regex},
            {"client_id": search_regex},
        ]
    }

    clients: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def _append_batch(batch: List[Dict[str, Any]], cap: int) -> None:
        for c in batch:
            cid = c.get("client_id")
            if not cid or cid in seen:
                continue
            if len(clients) >= cap:
                break
            seen.add(cid)
            clients.append(c)

    direct = await db.clients.find(_with_visibility(client_query, visibility_match), CLIENT_SEARCH_PROJECTION).limit(limit).to_list(limit)
    _append_batch(direct, limit)

    # Order reference → clients
    if len(clients) < limit:
        order_hits = await db.orders.find({"order_reference": search_regex}, {"_id": 0, "client_id": 1, "order_reference": 1}).limit(50).to_list(50)
        order_client_ids = list({o.get("client_id") for o in order_hits if o.get("client_id")})
        new_ids = [cid for cid in order_client_ids if cid not in seen]
        if new_ids:
            oc = await db.clients.find(_with_visibility({"client_id": {"$in": new_ids}}, visibility_match), CLIENT_SEARCH_PROJECTION).to_list(limit)
            for c in oc:
                match_order = next((o for o in order_hits if o.get("client_id") == c.get("client_id")), None)
                if match_order:
                    c["matched_via"] = "order_reference"
                    c["matched_order_reference"] = match_order.get("order_reference")
            _append_batch(oc, limit)

    # Property address / postcode
    if len(clients) < limit:
        prop_ids = await _property_client_ids(db, term, 50)
        new_ids = [cid for cid in prop_ids if cid not in seen]
        if new_ids:
            ac = await db.clients.find(_with_visibility({"client_id": {"$in": new_ids}}, visibility_match), CLIENT_SEARCH_PROJECTION).to_list(limit)
            props = await db.properties.find({"client_id": {"$in": [c.get("client_id") for c in ac if c.get("client_id")]}}, {"_id": 0, "client_id": 1, "postcode": 1}).to_list(200)
            for c in ac:
                matched_props = [p for p in props if p.get("client_id") == c.get("client_id")]
                if matched_props:
                    c["matched_via"] = "property"
                    c["matched_postcode"] = matched_props[0].get("postcode")
            _append_batch(ac, limit)

    # Stripe customer / subscription id
    if len(clients) < limit:
        stripe_ids = await _stripe_hit_client_ids(db, term, limit)
        new_ids = [cid for cid in stripe_ids if cid not in seen]
        if new_ids:
            sc = await db.clients.find(_with_visibility({"client_id": {"$in": new_ids}}, visibility_match), CLIENT_SEARCH_PROJECTION).to_list(limit)
            for c in sc:
                c["matched_via"] = "stripe_id"
            _append_batch(sc, limit)

    clients = clients[:limit]
    if not clients:
        return []

    ids = [c["client_id"] for c in clients if c.get("client_id")]
    billings = await db.client_billing.find({"client_id": {"$in": ids}}, BILLING_ENRICH_PROJECTION).to_list(len(ids))
    billing_by_id = {b["client_id"]: b for b in billings if b.get("client_id")}

    agg = await db.properties.aggregate(
        [
            {"$match": {"client_id": {"$in": ids}}},
            {"$group": {"_id": "$client_id", "n": {"$sum": 1}}},
        ]
    ).to_list(len(ids))
    counts = {doc["_id"]: int(doc.get("n") or 0) for doc in agg}

    out: List[Dict[str, Any]] = []
    for c in clients:
        cid = c.get("client_id")
        out.append(_build_support_row(c, billing_by_id.get(cid), counts.get(cid, 0)))
    return out


def assert_support_row_has_no_sensitive_payment_blob(row: Dict[str, Any]) -> None:
    """Guard for tests: disallow amount / raw invoice payloads on search rows."""
    banned_substrings = ("last_payment_amount", "payment_method", "card_", "cvc", "iban")
    for k in row.keys():
        lk = k.lower()
        if any(b in lk for b in banned_substrings):
            raise AssertionError(f"unexpected key on support search row: {k}")
