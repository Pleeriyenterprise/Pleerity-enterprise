"""
Billing recovery operations — governed orchestration inside Admin Billing authority.

No silent Stripe mutation, bulk admin-set-mode, or destructive cleanup.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from database import database
from models import AuditAction
from services.billing_recovery_state_machine import (
    ESCALATION_AWAITING_CUSTOMER,
    ESCALATION_NORMAL,
    ESCALATION_UNRESOLVED_BACKLOG,
    STATE_ADMIN_VERIFIED,
    STATE_CHECKOUT_REGENERATED,
    STATE_CUSTOMER_PENDING,
    STATE_MODE_UNVERIFIED,
    STATE_RECOVERY_REQUIRED,
    STATE_RECOVERY_RESOLVED,
    initial_recovery_state,
    transition_recovery_state,
    BillingRecoveryTransitionError,
)
from services.stripe_mode_client_remediation_service import (
    classify_orphaned_checkout_sessions,
    remediation_code_to_recommended_action,
)
from services.stripe_mode_containment_service import (
    CUSTOMER_BILLING_REFRESH_MESSAGE,
    MODE_UNVERIFIED as CONTAINMENT_MODE_UNVERIFIED,
    StripeModeDriftError,
    normalize_persisted_mode,
    resolve_stripe_context,
)
from services.stripe_mode_backfill_service import (
    REMEDIATION_MODE_UNVERIFIED,
    REMEDIATION_REGENERATE_CHECKOUT,
    classify_remediation,
    get_remediation_guidance,
    resolve_authoritative_mode,
)
from services.stripe_mode_authority import get_stripe_mode
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

COL_RECOVERY_CASES = "billing_recovery_cases"
COL_RECOVERY_AUDIT = "billing_recovery_audit"
COL_RECOVERY_METRICS = "billing_recovery_metrics"

CUSTOMER_CONTINUATION_SUBJECT = "Complete your secure billing continuation"


class BillingRecoveryRegenerationError(Exception):
    """Governed regeneration failure — safe for HTTP 4xx mapping (never raw Stripe)."""

    def __init__(self, message: str, *, status_code: int = 409, error_code: str = "recovery_regeneration_blocked"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


def _requires_deployment_checkout_regeneration(
    billing: Optional[Dict[str, Any]],
    case: Optional[Dict[str, Any]],
) -> bool:
    """Use deployment-mode Checkout (not upgrade/portal preflight) for drift / MODE_UNVERIFIED rows."""
    if not billing:
        return True
    verification = (billing.get("stripe_mode_verification_status") or "").strip()
    if verification == CONTAINMENT_MODE_UNVERIFIED:
        return True
    remediation = (case or {}).get("remediation_code") or ""
    if remediation in (REMEDIATION_MODE_UNVERIFIED, REMEDIATION_REGENERATE_CHECKOUT):
        return True
    dep = normalize_persisted_mode(get_stripe_mode())
    stored = normalize_persisted_mode(billing.get("stripe_mode"))
    if billing.get("stripe_subscription_id") and stored is None:
        return True
    if stored and dep and stored != dep:
        return True
    return False


CUSTOMER_CONTINUATION_BODY = (
    "Your billing access needs to be refreshed before plan changes can continue. "
    "Please use the secure link below to complete your billing continuation. "
    "Your compliance records remain available in the portal."
)

BULK_MAX_BATCH = 25


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _record_audit(
    *,
    client_id: Optional[str],
    action_type: str,
    actor_id: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    doc = {
        "client_id": client_id,
        "action_type": action_type,
        "actor_id": actor_id,
        "metadata": metadata or {},
        "created_at": _now(),
    }
    try:
        db = database.get_db()
        await db[COL_RECOVERY_AUDIT].insert_one(doc)
        await db[COL_RECOVERY_METRICS].update_one(
            {"scope": "global"},
            {"$inc": {f"events.{action_type}": 1}, "$set": {"last_event_at": _now()}},
            upsert=True,
        )
    except Exception as exc:
        logger.warning("billing_recovery_audit write failed: %s", exc)
    try:
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role="ROLE_ADMIN",
            actor_id=actor_id,
            client_id=client_id,
            metadata={"action_type": action_type, **(metadata or {})},
        )
    except Exception as exc:
        logger.warning("billing_recovery audit log failed: %s", exc)


async def _get_or_create_case(client_id: str, *, actor_id: str = "system") -> Dict[str, Any]:
    db = database.get_db()
    existing = await db[COL_RECOVERY_CASES].find_one({"client_id": client_id}, {"_id": 0})
    if existing:
        return existing

    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0}) or {}
    verification = billing.get("stripe_mode_verification_status")
    state = initial_recovery_state(verification_status=verification)
    resolution = await resolve_authoritative_mode(client_id, billing=billing)
    code, risk, path = classify_remediation(billing, resolution, deployment_mode=resolution.get("deployment_mode"))

    doc = {
        "client_id": client_id,
        "recovery_state": state,
        "remediation_code": code,
        "operational_risk": risk,
        "recommended_action": remediation_code_to_recommended_action(
            code,
            subscription_status=billing.get("subscription_status"),
            has_webhook=False,
            has_checkout=False,
        ),
        "escalation_state": ESCALATION_UNRESOLVED_BACKLOG if state == STATE_MODE_UNVERIFIED else ESCALATION_NORMAL,
        "owner": None,
        "assigned_at": None,
        "resolution_summary": None,
        "operational_notes": None,
        "recovery_started_at": _now(),
        "recovery_updated_at": _now(),
        "last_recovery_action": "case_opened",
        "transition_history": [],
    }
    await db[COL_RECOVERY_CASES].insert_one(doc)
    await _record_audit(
        client_id=client_id,
        action_type="recovery_started",
        actor_id=actor_id,
        metadata={"recovery_state": state, "remediation_code": code},
    )
    doc.pop("_id", None)
    return doc


def _recovery_age_days(case: Dict[str, Any]) -> Optional[int]:
    started = case.get("recovery_started_at")
    if not started:
        return None
    try:
        if isinstance(started, str):
            started = datetime.fromisoformat(started.replace("Z", "+00:00"))
        if isinstance(started, datetime) and started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if not isinstance(started, datetime):
            return None
        delta = _now() - started
        return max(0, delta.days)
    except Exception:
        return None


async def _enrich_case_row(client_id: str, case: Dict[str, Any]) -> Dict[str, Any]:
    db = database.get_db()
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0}) or {}
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "email": 1, "customer_reference": 1, "full_name": 1})

    client_id_text = str(client_id) if client_id is not None else ""
    sub_id = str(billing.get("stripe_subscription_id") or "").strip()
    wh = await db.stripe_events.find_one(
        {"$or": [{"related_client_id": client_id}, {"related_subscription_id": sub_id}]},
        {"_id": 0, "created": 1},
        sort=[("created", -1)],
    )
    ch = await db.checkout_sessions.find_one({"client_id": client_id}, {"_id": 0, "created_at": 1}, sort=[("created_at", -1)])

    return {
        "client_id": client_id_text,
        "client_label": (client or {}).get("full_name") or client_id_text[:8] or "unknown",
        "crn": (client or {}).get("customer_reference"),
        "remediation_code": case.get("remediation_code"),
        "operational_risk": case.get("operational_risk"),
        "billing_status": billing.get("subscription_status"),
        "entitlement_status": billing.get("entitlement_status"),
        "recommended_action": case.get("recommended_action"),
        "recovery_state": case.get("recovery_state"),
        "owner": case.get("owner"),
        "assigned_at": case.get("assigned_at"),
        "escalation_state": case.get("escalation_state"),
        "last_checkout": ch.get("created_at") if ch else None,
        "last_webhook": wh.get("created") if wh else None,
        "last_recovery_action": case.get("last_recovery_action"),
        "recovery_age_days": _recovery_age_days(case),
        "customer_safe_message": CUSTOMER_BILLING_REFRESH_MESSAGE,
    }


async def build_recovery_dashboard(*, limit: int = 200) -> Dict[str, Any]:
    """Recovery layer sections for Admin Billing."""
    db = database.get_db()
    from services.stripe_mode_authority import get_stripe_mode

    deployment_mode = get_stripe_mode()
    sections: Dict[str, List[Dict[str, Any]]] = {
        "mode_unverified_clients": [],
        "mixed_mode_drift_clients": [],
        "orphaned_checkout_sessions": [],
        "failed_upgrade_recoveries": [],
        "pending_regeneration": [],
        "recently_remediated": [],
        "drift_metrics_summary": [],
    }

    billing_cursor = db.client_billing.find(
        {
            "$or": [
                {"stripe_mode_verification_status": "MODE_UNVERIFIED"},
                {"stripe_mode": {"$in": [None, ""]}, "stripe_subscription_id": {"$nin": [None, ""]}},
            ]
        },
        {"_id": 0, "client_id": 1},
    ).limit(limit)

    skipped_rows = 0
    async for row in billing_cursor:
        cid = row.get("client_id")
        if not cid:
            continue
        try:
            case = await _get_or_create_case(cid)
            enriched = await _enrich_case_row(cid, case)
            state = case.get("recovery_state")
            if state in (STATE_MODE_UNVERIFIED, STATE_RECOVERY_REQUIRED):
                sections["mode_unverified_clients"].append(enriched)
            if case.get("recommended_action") == "REGENERATE_CHECKOUT_REQUIRED":
                sections["pending_regeneration"].append(enriched)
        except Exception as exc:
            skipped_rows += 1
            logger.warning("billing_recovery dashboard skipped row client_id=%s error=%s", str(cid)[:24], exc)

    remediated = db[COL_RECOVERY_CASES].find(
        {"recovery_state": STATE_RECOVERY_RESOLVED},
        {"_id": 0},
    ).sort("recovery_updated_at", -1).limit(20)
    async for case in remediated:
        cid = case.get("client_id")
        if cid:
            try:
                sections["recently_remediated"].append(await _enrich_case_row(cid, case))
            except Exception as exc:
                skipped_rows += 1
                logger.warning("billing_recovery dashboard skipped remediated row client_id=%s error=%s", str(cid)[:24], exc)

    try:
        orphans = await classify_orphaned_checkout_sessions(limit=100)
    except Exception as exc:
        logger.warning("billing_recovery orphan classification failed: %s", exc)
        orphans = {"summary": {}, "categories": {"requires_regeneration": []}}
    sections["orphaned_checkout_sessions"] = orphans.get("categories", {}).get("requires_regeneration", [])[:50]

    metrics = await db[COL_RECOVERY_METRICS].find_one({"scope": "global"}, {"_id": 0})
    active_count = await db[COL_RECOVERY_CASES].count_documents(
        {"recovery_state": {"$nin": [STATE_RECOVERY_RESOLVED]}}
    )
    sections["drift_metrics_summary"] = [
        {
            "deployment_mode": deployment_mode,
            "active_recovery_count": active_count,
            "mode_unverified_count": len(sections["mode_unverified_clients"]),
            "pending_regeneration_count": len(sections["pending_regeneration"]),
            "orphaned_checkout_count": orphans.get("summary", {}).get("requires_regeneration", 0),
            "metrics": metrics.get("events") if isinstance(metrics, dict) else {},
            "skipped_rows": skipped_rows,
        }
    ]

    return {
        "generated_at": _now().isoformat(),
        "deployment_mode": deployment_mode,
        "sections": sections,
        "summary": {k: len(v) for k, v in sections.items() if k != "drift_metrics_summary"},
    }


async def assign_recovery_owner(
    client_id: str,
    *,
    owner: str,
    actor_id: str,
    operational_notes: Optional[str] = None,
) -> Dict[str, Any]:
    case = await _get_or_create_case(client_id, actor_id=actor_id)
    now = _now()
    update = {
        "owner": owner.strip(),
        "assigned_at": now,
        "recovery_updated_at": now,
        "last_recovery_action": "assigned_owner",
        "escalation_state": ESCALATION_NORMAL,
    }
    if operational_notes:
        update["operational_notes"] = operational_notes
    db = database.get_db()
    await db[COL_RECOVERY_CASES].update_one({"client_id": client_id}, {"$set": update})
    await _record_audit(
        client_id=client_id,
        action_type="recovery_assigned",
        actor_id=actor_id,
        metadata={"owner": owner},
    )
    case.update(update)
    return await _enrich_case_row(client_id, case)


async def transition_case(
    client_id: str,
    *,
    target_state: str,
    action: str,
    actor_id: str,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    case = await _get_or_create_case(client_id, actor_id=actor_id)
    new_state, record = transition_recovery_state(
        case.get("recovery_state", STATE_MODE_UNVERIFIED),
        target_state,
        action=action,
        actor_id=actor_id,
        idempotency_key=idempotency_key,
    )
    db = database.get_db()
    await db[COL_RECOVERY_CASES].update_one(
        {"client_id": client_id},
        {
            "$set": {
                "recovery_state": new_state,
                "recovery_updated_at": _now(),
                "last_recovery_action": action,
            },
            "$push": {"transition_history": {"$each": [record], "$slice": -50}},
        },
    )
    await _record_audit(
        client_id=client_id,
        action_type="recovery_transition",
        actor_id=actor_id,
        metadata=record,
    )
    case["recovery_state"] = new_state
    return await _enrich_case_row(client_id, case)


async def regenerate_checkout_for_recovery(
    client_id: str,
    *,
    plan_code: str,
    actor_id: str,
    origin_url: str,
    send_email: bool = False,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Regenerate authoritative checkout — no duplicate subscription creation."""
    from services.stripe_service import StripeService
    await resolve_stripe_context(client_id=client_id, operation="recovery_regenerate_checkout", require_preflight=False)

    # Ensure transition path is valid before any checkout mutation or Stripe side effects.
    case = await _get_or_create_case(client_id, actor_id=actor_id)
    if case.get("recovery_state") == STATE_MODE_UNVERIFIED:
        await transition_case(
            client_id,
            target_state=STATE_RECOVERY_REQUIRED,
            action="prepare_recovery_regeneration",
            actor_id=actor_id,
            idempotency_key=f"prepare_regen:{client_id}",
        )

    db = database.get_db()
    # Mark stale pending sessions as superseded (no delete)
    await db.checkout_sessions.update_many(
        {"client_id": client_id, "status": "pending"},
        {"$set": {"status": "superseded", "superseded_at": _now(), "superseded_by": "billing_recovery"}},
    )

    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})
    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "email": 1, "contact_email": 1, "customer_reference": 1},
    )
    stripe_svc = StripeService()
    use_deployment_checkout = _requires_deployment_checkout_regeneration(billing, case)
    try:
        if use_deployment_checkout:
            customer_email = (client or {}).get("email") or (client or {}).get("contact_email")
            result = await stripe_svc.create_checkout_session(
                client_id=client_id,
                plan_code=plan_code,
                origin_url=origin_url,
                customer_email=customer_email,
                customer_reference=(client or {}).get("customer_reference"),
            )
            result["regeneration_path"] = "deployment_checkout"
        else:
            result = await stripe_svc.create_upgrade_session(
                client_id=client_id,
                new_plan_code=plan_code,
                origin_url=origin_url,
            )
            result["regeneration_path"] = "upgrade_session"
    except StripeModeDriftError as drift:
        raise BillingRecoveryRegenerationError(
            drift.customer_message,
            status_code=409,
            error_code=drift.error_code,
        ) from drift

    session_id = result.get("session_id") or ""
    if not session_id and not result.get("checkout_url") and not result.get("portal_url"):
        raise BillingRecoveryRegenerationError(
            CUSTOMER_BILLING_REFRESH_MESSAGE,
            status_code=422,
            error_code="checkout_not_created",
        )

    await transition_case(
        client_id,
        target_state=STATE_CHECKOUT_REGENERATED,
        action="regenerate_checkout",
        actor_id=actor_id,
        idempotency_key=idempotency_key or f"regen:{client_id}:{session_id}",
    )
    await transition_case(
        client_id,
        target_state=STATE_CUSTOMER_PENDING,
        action="awaiting_customer",
        actor_id=actor_id,
        idempotency_key=f"pending:{client_id}",
    )

    email_result = None
    checkout_url = result.get("checkout_url") or result.get("portal_url")
    if send_email and checkout_url:
        email_result = await _send_continuation_email(client_id, checkout_url, actor_id=actor_id)

    await _record_audit(
        client_id=client_id,
        action_type="regeneration_sent",
        actor_id=actor_id,
        metadata={
            "session_id": session_id,
            "send_email": send_email,
            "regeneration_path": result.get("regeneration_path"),
        },
    )
    return {
        "checkout": result,
        "email": email_result,
        "customer_message": CUSTOMER_CONTINUATION_BODY,
    }


async def _send_continuation_email(client_id: str, checkout_url: str, *, actor_id: str) -> Dict[str, Any]:
    from services.notification_orchestrator import notification_orchestrator

    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "email": 1, "contact_name": 1, "full_name": 1})
    if not client or not client.get("email"):
        return {"sent": False, "reason": "no_email"}

    # rate limit: max 3 continuation emails per client per hour
    since = _now() - timedelta(hours=1)
    recent = await db[COL_RECOVERY_AUDIT].count_documents(
        {
            "client_id": client_id,
            "action_type": "regeneration_sent",
            "created_at": {"$gte": since},
        }
    )
    if recent >= 3:
        return {"sent": False, "reason": "rate_limited"}

    name = client.get("contact_name") or client.get("full_name") or "Valued Customer"
    body = (
        f"<p>{CUSTOMER_CONTINUATION_BODY}</p>"
        f'<p><a href="{checkout_url}">Complete secure billing continuation</a></p>'
    )
    try:
        await notification_orchestrator.send(
            template_key="BILLING_CONTINUATION",
            client_id=client_id,
            context={
                "client_name": name,
                "subject": CUSTOMER_CONTINUATION_SUBJECT,
                "message": body,
            },
            idempotency_key=f"billing_recovery_continuation_{client_id}_{_now().strftime('%Y%m%d%H')}",
            event_type="billing_recovery_continuation",
        )
        return {"sent": True}
    except Exception as exc:
        logger.warning("continuation email failed client_id=%s: %s", client_id, exc)
        return {"sent": False, "reason": str(exc)[:120]}


async def closeout_recovery(
    client_id: str,
    *,
    resolution_summary: str,
    actor_id: str,
) -> Dict[str, Any]:
    await transition_case(
        client_id,
        target_state=STATE_RECOVERY_RESOLVED,
        action="recovery_closeout",
        actor_id=actor_id,
    )
    db = database.get_db()
    await db[COL_RECOVERY_CASES].update_one(
        {"client_id": client_id},
        {"$set": {"resolution_summary": resolution_summary, "recovery_updated_at": _now()}},
    )
    await _record_audit(
        client_id=client_id,
        action_type="recovery_completed",
        actor_id=actor_id,
        metadata={"resolution_summary": resolution_summary[:500]},
    )
    case = await db[COL_RECOVERY_CASES].find_one({"client_id": client_id}, {"_id": 0})
    return await _enrich_case_row(client_id, case or {})


async def bulk_resend_continuation(
    client_ids: List[str],
    *,
    actor_id: str,
    preview: bool = False,
) -> Dict[str, Any]:
    if len(client_ids) > BULK_MAX_BATCH:
        raise ValueError(f"Batch limit is {BULK_MAX_BATCH} clients")
    results = []
    for cid in client_ids[:BULK_MAX_BATCH]:
        if preview:
            results.append({"client_id": cid, "preview": True, "action": "resend_continuation"})
            continue
        ch = await database.get_db().checkout_sessions.find_one(
            {"client_id": cid, "status": "pending"},
            {"_id": 0, "checkout_url": 1},
            sort=[("created_at", -1)],
        )
        url = (ch or {}).get("checkout_url")
        if not url:
            results.append({"client_id": cid, "sent": False, "reason": "no_pending_checkout"})
            continue
        email_result = await _send_continuation_email(cid, url, actor_id=actor_id)
        results.append({"client_id": cid, **email_result})
    await _record_audit(
        client_id=None,
        action_type="bulk_resend_continuation",
        actor_id=actor_id,
        metadata={"count": len(client_ids), "preview": preview},
    )
    return {"preview": preview, "results": results, "batch_size": len(client_ids)}


async def get_recovery_case(client_id: str, *, actor_id: str = "system") -> Dict[str, Any]:
    case = await _get_or_create_case(client_id, actor_id=actor_id)
    guidance = await get_remediation_guidance(client_id)
    row = await _enrich_case_row(client_id, case)
    row["remediation_guidance"] = guidance
    row["recovery_case"] = {k: v for k, v in case.items() if k != "_id"}
    return row


async def update_escalation(
    client_id: str,
    *,
    escalation_state: str,
    actor_id: str,
    operational_notes: Optional[str] = None,
) -> Dict[str, Any]:
    from services.billing_recovery_state_machine import ALL_ESCALATION_STATES, STATE_ESCALATED_TO_SUPPORT

    if escalation_state not in ALL_ESCALATION_STATES:
        raise ValueError(f"Invalid escalation_state: {escalation_state}")
    case = await _get_or_create_case(client_id, actor_id=actor_id)
    update: Dict[str, Any] = {
        "escalation_state": escalation_state,
        "recovery_updated_at": _now(),
        "last_recovery_action": "escalation_updated",
    }
    if operational_notes:
        update["operational_notes"] = operational_notes
    if escalation_state in ("escalation_required", "operational_risk", "awaiting_support"):
        await transition_case(
            client_id,
            target_state=STATE_ESCALATED_TO_SUPPORT,
            action="escalate",
            actor_id=actor_id,
        )
    db = database.get_db()
    await db[COL_RECOVERY_CASES].update_one({"client_id": client_id}, {"$set": update})
    await _record_audit(
        client_id=client_id,
        action_type="recovery_escalation",
        actor_id=actor_id,
        metadata={"escalation_state": escalation_state},
    )
    case.update(update)
    return await _enrich_case_row(client_id, case)


async def portal_relink_for_recovery(
    client_id: str,
    *,
    actor_id: str,
) -> Dict[str, Any]:
    """Safely regenerate billing portal context — no subscription mutation."""
    import stripe
    from utils.public_app_url import get_public_app_url

    await resolve_stripe_context(
        client_id=client_id,
        operation="billing_recovery_portal_relink",
        require_preflight=False,
    )
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0}) or {}
    stripe_customer_id = (client or {}).get("stripe_customer_id") or billing.get("stripe_customer_id")
    if not stripe_customer_id:
        return {"success": False, "reason": "no_stripe_customer"}

    base_url = get_public_app_url(for_email_links=False)
    portal_session = stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=f"{base_url}/app/billing",
    )
    await _record_audit(
        client_id=client_id,
        action_type="portal_relink",
        actor_id=actor_id,
        metadata={"portal_created": True},
    )
    return {
        "success": True,
        "portal_url": portal_session.url,
        "customer_message": "Share the secure billing portal link so the customer can review their subscription.",
    }


async def admin_verified_recovery(
    client_id: str,
    *,
    stripe_mode: str,
    reason: str,
    verification_source: str,
    actor_id: str,
    backfill_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Record admin verification in recovery state machine after governed backfill."""
    from services.billing_recovery_state_machine import STATE_ADMIN_VERIFIED

    await transition_case(
        client_id,
        target_state=STATE_ADMIN_VERIFIED,
        action="admin_verified",
        actor_id=actor_id,
        idempotency_key=f"admin_verified:{client_id}:{stripe_mode}",
    )
    db = database.get_db()
    await db[COL_RECOVERY_CASES].update_one(
        {"client_id": client_id},
        {
            "$set": {
                "recovery_updated_at": _now(),
                "last_recovery_action": "admin_set_mode",
                "verification_source": verification_source,
                "admin_verification_reason": reason[:500],
            }
        },
    )
    await _record_audit(
        client_id=client_id,
        action_type="admin_verified",
        actor_id=actor_id,
        metadata={"stripe_mode": stripe_mode, "verification_source": verification_source, "backfill": backfill_result.get("action")},
    )
    case = await db[COL_RECOVERY_CASES].find_one({"client_id": client_id}, {"_id": 0})
    return await _enrich_case_row(client_id, case or {})


async def get_recovery_metrics() -> Dict[str, Any]:
    db = database.get_db()
    total = await db[COL_RECOVERY_CASES].count_documents({})
    unresolved = await db[COL_RECOVERY_CASES].count_documents(
        {"recovery_state": {"$nin": [STATE_RECOVERY_RESOLVED]}}
    )
    resolved = await db[COL_RECOVERY_CASES].count_documents({"recovery_state": STATE_RECOVERY_RESOLVED})
    events = await db[COL_RECOVERY_METRICS].find_one({"scope": "global"}, {"_id": 0})
    return {
        "generated_at": _now().isoformat(),
        "active_recovery_count": unresolved,
        "resolved_count": resolved,
        "total_cases": total,
        "recovery_completion_rate": round(resolved / max(total, 1), 4),
        "unresolved_backlog": unresolved,
        "events": (events or {}).get("events", {}),
    }
