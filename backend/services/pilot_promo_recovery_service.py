"""
Promo / invite redemption recovery context for any client account (not pilot-lifecycle gated).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from database import database
from services.pilot_invite_service import COL_REDEMPTIONS
from services.pilot_redemption_eligibility_service import (
    find_active_overrides,
    list_overrides_for_client,
)
from services.pilot_redemption_lifecycle import (
    RECOVERABLE_STATUSES,
    PilotRedemptionStatus,
    normalize_redemption_status,
    summarize_redemption_for_admin,
)


async def list_redemptions_for_account(client_id: str, *, limit: int = 100) -> List[Dict[str, Any]]:
    """Redemptions tied to client_id and/or account email(s)."""
    db = database.get_db()
    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "client_id": 1, "email": 1, "contact_email": 1},
    )
    or_clauses: List[Dict[str, Any]] = [{"client_id": client_id}]
    if client:
        for field in ("email", "contact_email"):
            em = (client.get(field) or "").strip().lower()
            if em:
                or_clauses.append({"redemption_email": em})
    filt: Dict[str, Any] = or_clauses[0] if len(or_clauses) == 1 else {"$or": or_clauses}
    cursor = db[COL_REDEMPTIONS].find(filt, {"_id": 0}).sort("created_at", -1).limit(limit)
    rows = [doc async for doc in cursor]
    return [summarize_redemption_for_admin(r) for r in rows]


def _client_promo_metadata(client: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not client:
        return {}
    snap = client.get("pilot_redeemed_campaign_snapshot") or {}
    return {
        "pilot_invite_code": client.get("pilot_invite_code"),
        "pilot_code_type": client.get("pilot_code_type") or snap.get("code_type"),
        "pilot_program_type": client.get("pilot_program_type"),
        "pilot_redeemed_campaign_snapshot_id": client.get("pilot_redeemed_campaign_snapshot_id"),
        "campaign_name": snap.get("campaign_name"),
        "onboarding_status": client.get("onboarding_status"),
        "provisioning_status": client.get("provisioning_status"),
        "subscription_status": client.get("subscription_status"),
        "billing_lifecycle_state": client.get("billing_lifecycle_state"),
        "onboarding_fee_policy": client.get("onboarding_fee_policy"),
        "onboarding_fee_waived": client.get("onboarding_fee_waived"),
        "pilot_status": client.get("pilot_status"),
        "email": client.get("email") or client.get("contact_email"),
    }


def build_recovery_indicators(
    *,
    redemptions: List[Dict[str, Any]],
    overrides: List[Dict[str, Any]],
    client: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Operational flags for admin UI (derived from persisted state, not eligibility logic)."""
    badges: List[str] = []
    stranded_onboarding = False
    payment_failed = False
    provisioning_failed = False
    incomplete_redemption = False
    retry_blocked = False
    override_active = False
    first_time_consumed = False

    for r in redemptions:
        st = normalize_redemption_status(r.get("status"))
        if st == PilotRedemptionStatus.PAYMENT_FAILED.value:
            payment_failed = True
            stranded_onboarding = True
            badges.append("payment_failed")
        if st == PilotRedemptionStatus.PROVISIONING_FAILED.value:
            provisioning_failed = True
            stranded_onboarding = True
            badges.append("provisioning_failed")
        if st in RECOVERABLE_STATUSES and st not in (
            PilotRedemptionStatus.REVOKED.value,
            PilotRedemptionStatus.EXPIRED.value,
        ):
            incomplete_redemption = True
        if st in (PilotRedemptionStatus.PENDING.value, PilotRedemptionStatus.PAYMENT_STARTED.value):
            incomplete_redemption = True
            if r.get("within_grace"):
                badges.append("pending_in_grace")
            else:
                stranded_onboarding = True
                badges.append("incomplete_redemption")
        if r.get("retry_eligible") is False and not r.get("consumes_eligibility"):
            retry_blocked = True
            badges.append("retry_blocked")
        if r.get("consumes_eligibility"):
            first_time_consumed = True

    active_overrides = [o for o in overrides if _override_active_doc(o)]
    waiver_active = False
    if active_overrides:
        override_active = True
        badges.append("override_active")
        for o in active_overrides:
            if o.get("override_type") == "bypass_first_time":
                badges.append("first_time_bypass")
            if o.get("override_type") == "recover_onboarding":
                waiver_active = True
                badges.append("waiver_active")

    meta = _client_promo_metadata(client)
    if meta.get("pilot_redeemed_campaign_snapshot_id"):
        first_time_consumed = True
    ob = str(meta.get("onboarding_status") or "").upper()
    if ob in ("INTAKE_PENDING", "PENDING_PAYMENT", "PROVISIONING_FAILED", "PAYMENT_FAILED"):
        stranded_onboarding = True
        if ob == "INTAKE_PENDING":
            badges.append("intake_pending")
        if ob in ("PROVISIONING_FAILED", "PAYMENT_FAILED"):
            badges.append("onboarding_recovery_needed")
    prov = str(meta.get("provisioning_status") or "").upper()
    if prov in ("FAILED", "PROVISIONING_FAILED"):
        provisioning_failed = True
        stranded_onboarding = True
        if "provisioning_failed" not in badges:
            badges.append("provisioning_failed")
    sub = str(meta.get("subscription_status") or "").lower()
    billing_lc = str(meta.get("billing_lifecycle_state") or "").lower()
    if not sub or sub in ("none", "inactive", "cancelled", "intake_pending"):
        badges.append("no_subscription")
        if meta.get("pilot_invite_code") or redemptions:
            stranded_onboarding = True
    if billing_lc in ("pending_payment", "payment_failed", "past_due", "unpaid", "abandoned"):
        payment_failed = True
        stranded_onboarding = True
        if "payment_failed" not in badges:
            badges.append("payment_failed")
    if any(r.get("retry_eligible") for r in redemptions):
        badges.append("retry_eligible")

    # de-dupe badges preserve order
    seen = set()
    unique_badges = []
    for b in badges:
        if b not in seen:
            seen.add(b)
            unique_badges.append(b)

    return {
        "stranded_onboarding": stranded_onboarding,
        "payment_failed": payment_failed,
        "provisioning_failed": provisioning_failed,
        "incomplete_redemption": incomplete_redemption,
        "retry_blocked": retry_blocked,
        "override_active": override_active,
        "first_time_consumed": first_time_consumed,
        "badges": unique_badges,
        "recoverable_count": sum(
            1
            for r in redemptions
            if normalize_redemption_status(r.get("status")) in RECOVERABLE_STATUSES
            and not r.get("consumes_eligibility")
        ),
    }


def _override_active_doc(doc: Dict[str, Any]) -> bool:
    from services.pilot_redemption_eligibility_service import _override_active

    return _override_active(doc)


def should_show_recovery_panel(
    *,
    redemptions: List[Dict[str, Any]],
    overrides: List[Dict[str, Any]],
    client: Optional[Dict[str, Any]],
    indicators: Dict[str, Any],
) -> bool:
    if redemptions or overrides:
        return True
    if not client:
        return False
    if client.get("pilot_invite_code") or client.get("pilot_redeemed_campaign_snapshot_id"):
        return True
    if client.get("pilot_redeemed_campaign_snapshot"):
        return True
    if indicators.get("stranded_onboarding"):
        return True
    if indicators.get("override_active") or indicators.get("waiver_active"):
        return True
    if indicators.get("retry_blocked") or any(r.get("retry_eligible") for r in redemptions):
        return True
    if client:
        ob = str(client.get("onboarding_status") or "").upper()
        if ob in ("INTAKE_PENDING", "PENDING_PAYMENT", "PROVISIONING_FAILED", "PAYMENT_FAILED"):
            return True
        prov = str(client.get("provisioning_status") or "").upper()
        if prov in ("FAILED", "PROVISIONING_FAILED"):
            return True
    return False


async def get_account_promo_recovery_context(client_id: str, *, limit: int = 100) -> Dict[str, Any]:
    """Full recovery bundle for Client Control Panel and pilot ops (not gated on active pilot)."""
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    redemptions = await list_redemptions_for_account(client_id, limit=limit)
    overrides = await list_overrides_for_client(client_id, limit=limit)
    indicators = build_recovery_indicators(redemptions=redemptions, overrides=overrides, client=client)
    visible = should_show_recovery_panel(
        redemptions=redemptions,
        overrides=overrides,
        client=client,
        indicators=indicators,
    )
    invite_meta = _client_promo_metadata(client)
    # Active bypass for display hint only
    em = (client or {}).get("email") or (client or {}).get("contact_email")
    active_bypass = False
    if em:
        active_bypass = bool(
            await find_active_overrides(
                email=str(em).lower(),
                client_id=client_id,
                override_types=["bypass_first_time"],
            )
        )
    indicators["first_time_bypass_active"] = active_bypass

    latest = redemptions[0] if redemptions else None
    waiver_history = [o for o in overrides if o.get("override_type") == "recover_onboarding"]
    override_history = sorted(
        overrides,
        key=lambda o: o.get("override_created_at") or "",
        reverse=True,
    )

    return {
        "client_id": client_id,
        "redemptions": redemptions,
        "eligibility_overrides": overrides,
        "override_history": override_history,
        "waiver_history": waiver_history,
        "indicators": indicators,
        "show_recovery_panel": visible,
        "invite_metadata": invite_meta,
        "latest_redemption": latest,
        "count": len(redemptions),
    }

