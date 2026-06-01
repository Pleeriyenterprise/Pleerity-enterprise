"""Lightweight Stripe vs platform commercial entitlement reconciliation (Phase 2C v1)."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from database import database
from services.commercial_entitlement_service import (
    derive_customer_access_state,
    detect_entitlement_drift,
    load_client_billing_signals,
    reconcile_stripe_vs_platform_state,
)

logger = logging.getLogger(__name__)


async def reconcile_entitlement_billing_state(client_id: str) -> Dict[str, Any]:
    """
    v1: sync stored canonical_entitlement_state from platform governance bridge.
    Does not mutate Stripe subscriptions or pause_collection.
    """
    signals = await load_client_billing_signals(client_id)
    if not signals.get("found"):
        return {"ok": False, "error": "CLIENT_NOT_FOUND"}

    from services.commercial_entitlement_service import get_active_governance

    signals["active_governance"] = await get_active_governance(client_id)
    access = derive_customer_access_state(signals)
    canon = access.get("canonical_entitlement_state")
    if not canon:
        return {"ok": True, "client_id": client_id, "canonical_updated": False}

    db = database.get_db()
    await db.clients.update_one(
        {"client_id": client_id},
        {"$set": {"canonical_entitlement_state": canon}},
    )
    billing = signals.get("billing") or {}
    if billing:
        await db.client_billing.update_one(
            {"client_id": client_id},
            {"$set": {"canonical_entitlement_state": canon}},
        )

    drift = await detect_entitlement_drift(client_id)
    recon = await reconcile_stripe_vs_platform_state(client_id)
    return {
        "ok": True,
        "client_id": client_id,
        "canonical_entitlement_state": canon,
        "canonical_updated": True,
        "drift": drift,
        "reconciliation": recon,
    }


async def prevent_duplicate_subscription_risk(client_id: str) -> Dict[str, Any]:
    """Advisory check — v1 records risk only; does not create/cancel Stripe subscriptions."""
    db = database.get_db()
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})
    if not billing:
        return {"found": False, "duplicate_risk": False}
    sub_ids = []
    primary = (billing.get("stripe_subscription_id") or "").strip()
    if primary:
        sub_ids.append(primary)
    extra = billing.get("stripe_subscription_ids") or []
    if isinstance(extra, list):
        sub_ids.extend(str(s).strip() for s in extra if s)
    unique = {s for s in sub_ids if s}
    duplicate_risk = len(unique) > 1
    return {
        "found": True,
        "duplicate_risk": duplicate_risk,
        "subscription_ids": sorted(unique),
        "notes": (
            "Multiple subscription IDs detected — manual review recommended."
            if duplicate_risk
            else "Single or no subscription reference — no duplicate risk flagged."
        ),
    }
