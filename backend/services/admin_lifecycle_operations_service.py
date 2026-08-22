"""Admin Lifecycle Operations — governed read models and actions (no manual lifecycle override)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import database
from services.account_lifecycle_runtime_contract import (
    invalidate_runtime_cache_for_client,
    resolve_runtime_contract_for_client,
    runtime_contract_to_dict,
)
from services.billing_period_utils import normalize_stored_period_end_for_api
from services.billing_scheduled_cancellation_authority import is_stale_scheduled_cancellation_mirror
from services.billing_stripe_sync_service import sync_client_billing_from_stripe_subscription_id
from services.stripe_mode_containment_service import requires_deployment_checkout_for_plan_change
from services.subscription_lifecycle_service import sync_subscription_lifecycle
from services.admin_customer_operations_centre_service import (
    build_background_processing_summary,
    build_communications_summary,
    build_operational_timeline,
    build_phase2_extensions,
    support_bundle_zip_bytes,
)
from services.stripe_service import stripe_service

logger = logging.getLogger(__name__)

_REPLAY_SAFE_EVENT_PREFIXES = (
    "customer.subscription.",
    "invoice.payment_",
    "checkout.session.completed",
)


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _capability_summary(contract: Dict[str, Any]) -> Dict[str, Any]:
    caps = contract.get("capabilities") or {}
    allowed = [k for k, v in caps.items() if v == "ALLOW"]
    denied = [k for k, v in caps.items() if v == "DENY"]
    restricted = [k for k, v in caps.items() if v not in ("ALLOW", "DENY", None)]
    return {
        "allowed_count": len(allowed),
        "denied_count": len(denied),
        "restricted_count": len(restricted),
        "denied_sample": denied[:12],
        "restricted_sample": restricted[:12],
    }


def _derive_action_eligibility(
    *,
    contract: Dict[str, Any],
    billing: Optional[Dict[str, Any]],
    client: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    billing = billing or {}
    lifecycle_state = contract.get("lifecycle_state")
    cancel_scheduled = bool(billing.get("cancel_at_period_end"))
    sub_status = (billing.get("subscription_status") or "").upper()
    has_sub = bool((billing.get("stripe_subscription_id") or "").strip())
    stale_mirror = is_stale_scheduled_cancellation_mirror(billing)
    stripe_mode_missing = not billing.get("stripe_mode")
    recovery_checkout = requires_deployment_checkout_for_plan_change(billing)

    resume_blocked_reason = None
    if not has_sub:
        resume_blocked_reason = "No Stripe subscription on record"
    elif not cancel_scheduled:
        resume_blocked_reason = "Subscription is not scheduled for cancellation"
    elif sub_status in ("CANCELED", "CANCELLED"):
        resume_blocked_reason = "Stripe subscription is already terminal (canceled)"

    return {
        "reconcile_from_stripe": {
            "available": bool(has_sub or billing.get("stripe_customer_id") or (client or {}).get("stripe_customer_id")),
            "blocked_reason": None if has_sub or billing.get("stripe_customer_id") else "No Stripe customer or subscription",
        },
        "refresh_runtime_contract": {"available": True, "blocked_reason": None},
        "resume_scheduled_cancellation": {
            "available": resume_blocked_reason is None,
            "blocked_reason": resume_blocked_reason,
        },
        "regenerate_recovery_checkout": {
            "available": recovery_checkout or lifecycle_state in (
                "BILLING_RECOVERY",
                "PAYMENT_REQUIRED",
                "GRACE_PERIOD",
                "SUSPENDED",
                "SUBSCRIPTION_EXPIRED",
            ),
            "blocked_reason": None
            if recovery_checkout
            or lifecycle_state
            in ("BILLING_RECOVERY", "PAYMENT_REQUIRED", "GRACE_PERIOD", "SUSPENDED", "SUBSCRIPTION_EXPIRED")
            else "Account is not in a billing recovery state",
        },
        "billing_portal": {
            "available": bool(billing.get("stripe_customer_id")),
            "blocked_reason": None if billing.get("stripe_customer_id") else "No Stripe customer",
        },
        "mark_support_review": {"available": True, "blocked_reason": None},
        "replay_stripe_webhook": {
            "available": False,
            "blocked_reason": "Use reconcile from Stripe for subscription lifecycle; governed webhook replay is not exposed",
            "alternative": "reconcile_from_stripe",
        },
        "mirror_stale_scheduled_cancellation": stale_mirror,
        "stripe_mode_missing": stripe_mode_missing,
    }


async def build_lifecycle_operations_snapshot(client_id: str) -> Dict[str, Any]:
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        raise ValueError("Client not found")

    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0}) or {}
    contract = await resolve_runtime_contract_for_client(
        db,
        client_id,
        use_cache=False,
        emit_events=False,
        include_audit=False,
    )
    contract_dict = runtime_contract_to_dict(contract)
    cx = contract_dict.get("customer_experience") or {}
    ctx = contract_dict.get("lifecycle_context") or {}

    raw_events = await (
        db.stripe_events.find({"related_client_id": client_id})
        .sort("created", -1)
        .limit(25)
        .to_list(25)
    )
    failed_count = await db.stripe_events.count_documents(
        {"related_client_id": client_id, "status": "FAILED"}
    )
    stripe_timeline: List[Dict[str, Any]] = []
    replay_candidates: List[Dict[str, Any]] = []
    for ev in raw_events:
        row = {
            "event_id": ev.get("event_id"),
            "type": ev.get("type"),
            "status": ev.get("status"),
            "created": _iso(ev.get("created")),
            "error_preview": (ev.get("error") or "")[:200] or None,
        }
        stripe_timeline.append(row)
        if ev.get("status") == "FAILED" and str(ev.get("type") or "").startswith(_REPLAY_SAFE_EVENT_PREFIXES):
            replay_candidates.append(
                {
                    "event_id": ev.get("event_id"),
                    "type": ev.get("type"),
                    "replay_via": "reconcile_from_stripe",
                    "note": "Failed webhook events are not replayed directly; run Stripe reconciliation",
                }
            )

    audit_rows = await (
        db.audit_logs.find(
            {"client_id": client_id, "action": {"$in": ["ADMIN_ACTION", "BILLING", "SUBSCRIPTION"]}},
        )
        .sort("timestamp", -1)
        .limit(20)
        .to_list(20)
    )
    lifecycle_audit = [
        {
            "timestamp": _iso(r.get("timestamp")),
            "action": r.get("action"),
            "metadata": {
                k: r.get("metadata", {}).get(k)
                for k in ("action_type", "result", "resume_source", "event_source", "reason")
                if r.get("metadata", {}).get(k) is not None
            },
        }
        for r in audit_rows
    ]

    period_end = normalize_stored_period_end_for_api(billing.get("current_period_end"))
    now = datetime.now(timezone.utc)

    background_summary = await build_background_processing_summary(db, client_id, contract_dict)
    communications_summary = await build_communications_summary(db, client_id, contract_dict)
    operational_timeline = await build_operational_timeline(
        db,
        client_id,
        stripe_events=raw_events,
    )
    phase2 = build_phase2_extensions(
        contract=contract_dict,
        billing={
            **billing,
            "current_period_end_past": bool(period_end and period_end < now),
            "stale_scheduled_cancellation_mirror": is_stale_scheduled_cancellation_mirror(billing),
            "stripe_webhook_last_received_at": billing.get("stripe_webhook_last_received_at"),
            "stripe_webhook_last_event_type": billing.get("stripe_webhook_last_event_type"),
        },
        client=client,
        client_id=client_id,
        failed_webhook_count=failed_count,
        raw_stripe_events=raw_events,
        background_summary=background_summary,
        communications_summary=communications_summary,
        operational_timeline=operational_timeline,
        now=now,
    )

    base = {
        "client_id": client_id,
        "generated_at": _iso(now),
        "source_of_truth": {
            "billing": "Stripe API (via governed sync)",
            "lifecycle": "Runtime Contract resolver",
            "capabilities": "Runtime Contract capability matrix",
        },
        "lifecycle": {
            "lifecycle_state": contract_dict.get("lifecycle_state"),
            "portal_mode": contract_dict.get("portal_mode"),
            "state_reason": ctx.get("state_reason"),
            "state_label": ctx.get("state_label"),
            "transition_pending": ctx.get("transition_pending"),
            "runtime_version": contract_dict.get("runtime_version"),
            "recovery_eligible": contract_dict.get("recovery_eligible"),
            "customer_experience_heading": cx.get("heading"),
            "customer_experience_explanation": cx.get("explanation"),
            "primary_cta": cx.get("primary_cta"),
            "background_policy": contract_dict.get("background_policy"),
            "communication_policy": contract_dict.get("communication_policy"),
        },
        "billing": {
            "plan_code": client.get("billing_plan") or billing.get("current_plan_code"),
            "stripe_customer_id": billing.get("stripe_customer_id") or client.get("stripe_customer_id"),
            "stripe_subscription_id": billing.get("stripe_subscription_id"),
            "subscription_status": billing.get("subscription_status"),
            "cancel_at_period_end": billing.get("cancel_at_period_end"),
            "current_period_end": _iso(billing.get("current_period_end")),
            "current_period_end_past": bool(period_end and period_end < now),
            "last_payment_at": _iso(billing.get("last_payment_at")),
            "billing_sync_state": billing.get("billing_sync_state"),
            "billing_last_synced_at": _iso(billing.get("billing_last_synced_at")),
            "billing_reconciliation_needed": billing.get("billing_reconciliation_needed"),
            "billing_reconciliation_reason": billing.get("billing_reconciliation_reason"),
            "billing_lifecycle_state": billing.get("billing_lifecycle_state"),
            "stripe_mode": billing.get("stripe_mode"),
            "stripe_mode_verification_status": billing.get("stripe_mode_verification_status"),
            "stripe_mode_drift_risk": not billing.get("stripe_mode"),
            "mirror_label": "client_billing (mirror)",
            "stale_scheduled_cancellation_mirror": is_stale_scheduled_cancellation_mirror(billing),
        },
        "stripe_webhooks": {
            "last_received_at": _iso(billing.get("stripe_webhook_last_received_at")),
            "last_event_type": billing.get("stripe_webhook_last_event_type"),
            "failed_event_count": failed_count,
            "recent_events": stripe_timeline,
            "replay_candidates": replay_candidates,
            "webhook_endpoint_note": "Ingress health: System Health → scheduler; per-client events below",
        },
        "capabilities": _capability_summary(contract_dict),
        "recovery": {
            "recovery_guidance": cx.get("recovery_guidance"),
            "support_guidance": cx.get("support_guidance"),
        },
        "actions": _derive_action_eligibility(contract=contract_dict, billing=billing, client=client),
        "lifecycle_audit_timeline": lifecycle_audit,
    }
    base.update(phase2)
    return base


async def build_support_bundle_for_client(client_id: str) -> tuple[Dict[str, Any], bytes]:
    """Full snapshot + ZIP bytes for support escalation export."""
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        raise ValueError("Client not found")
    snapshot = await build_lifecycle_operations_snapshot(client_id)
    return snapshot, support_bundle_zip_bytes(snapshot, client)


async def admin_refresh_runtime_contract(
    client_id: str,
    *,
    actor_id: Optional[str],
    actor_role: str,
    reason: str,
) -> Dict[str, Any]:
    invalidate_runtime_cache_for_client(client_id)
    db = database.get_db()
    before = await resolve_runtime_contract_for_client(db, client_id, use_cache=False, emit_events=False)
    after = await resolve_runtime_contract_for_client(db, client_id, use_cache=False, emit_events=False)
    try:
        from services.account_lifecycle_event_authority import publish_runtime_contract_transition

        await publish_runtime_contract_transition(
            db, before, after, trigger="admin_refresh_runtime_contract"
        )
    except Exception:
        logger.warning("lifecycle event emit skipped after admin refresh client_id=%s", client_id, exc_info=True)
    return {
        "success": True,
        "runtime_version_before": before.get("runtime_version"),
        "runtime_version_after": after.get("runtime_version"),
        "lifecycle_state": after.get("lifecycle_state"),
        "portal_mode": after.get("portal_mode"),
        "reason": reason,
        "actor_id": actor_id,
        "actor_role": actor_role,
    }


async def admin_reconcile_from_stripe(
    client_id: str,
    *,
    actor_id: Optional[str],
    actor_role: str,
    reason: str,
) -> Dict[str, Any]:
    db = database.get_db()
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})
    if not billing:
        raise ValueError("No billing record for client")
    sid = (billing.get("stripe_subscription_id") or "").strip()
    if not sid:
        raise ValueError("No Stripe subscription ID — use billing recovery checkout for new subscription")

    previous_contract = await resolve_runtime_contract_for_client(
        db, client_id, use_cache=False, emit_events=False
    )
    before_status = billing.get("subscription_status")
    await sync_client_billing_from_stripe_subscription_id(
        client_id,
        sid,
        event_source="admin_lifecycle_operations_reconcile",
        update_plan=True,
        increment_entitlements_version=0,
    )
    await sync_subscription_lifecycle(client_id, bump_version=True)
    invalidate_runtime_cache_for_client(client_id)
    billing_after = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0}) or {}
    try:
        from services.account_lifecycle_runtime_contract import publish_runtime_contract_after_mutation

        await publish_runtime_contract_after_mutation(
            db, client_id, previous_contract, trigger="admin_reconcile_from_stripe"
        )
    except Exception:
        logger.warning("lifecycle event emit skipped after admin stripe reconcile client_id=%s", client_id, exc_info=True)
    contract = await resolve_runtime_contract_for_client(db, client_id, use_cache=False, emit_events=False)
    return {
        "success": True,
        "subscription_status_before": before_status,
        "subscription_status_after": billing_after.get("subscription_status"),
        "billing_sync_state": billing_after.get("billing_sync_state"),
        "lifecycle_state": contract.get("lifecycle_state"),
        "portal_mode": contract.get("portal_mode"),
        "runtime_version": contract.get("runtime_version"),
        "reason": reason,
        "actor_id": actor_id,
        "actor_role": actor_role,
    }


async def admin_resume_scheduled_cancellation(
    client_id: str,
    *,
    actor_id: Optional[str],
    actor_role: str,
    reason: str,
) -> Dict[str, Any]:
    db = database.get_db()
    previous_contract = await resolve_runtime_contract_for_client(
        db, client_id, use_cache=False, emit_events=False
    )
    result = await stripe_service.resume_subscription(
        client_id=client_id,
        actor_role=actor_role,
        actor_id=actor_id,
        resume_source="admin_lifecycle_operations_resume",
    )
    invalidate_runtime_cache_for_client(client_id)
    try:
        from services.account_lifecycle_runtime_contract import publish_runtime_contract_after_mutation

        await publish_runtime_contract_after_mutation(
            db, client_id, previous_contract, trigger="admin_resume_scheduled_cancellation"
        )
    except Exception:
        logger.warning("lifecycle event emit skipped after admin resume cancellation client_id=%s", client_id, exc_info=True)
    contract = await resolve_runtime_contract_for_client(db, client_id, use_cache=False, emit_events=False)
    return {
        **result,
        "lifecycle_state": contract.get("lifecycle_state"),
        "portal_mode": contract.get("portal_mode"),
        "runtime_version": contract.get("runtime_version"),
        "reason": reason,
    }
