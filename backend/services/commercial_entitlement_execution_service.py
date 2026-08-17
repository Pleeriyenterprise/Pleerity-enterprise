"""Governed commercial entitlement action execution (Phase 2C)."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from pymongo.errors import DuplicateKeyError

from database import database
from services.commercial_entitlement_service import (
    ALL_ACCESS_POLICIES,
    COL_GOVERNANCE,
    COMMERCIAL_OVERLAY_UNSET,
    EXCEPTION_BILLING_SUSPENSION,
    EXCEPTION_GRACE_EXTENSION,
    EXCEPTION_ONBOARDING_WAIVER,
    EXCEPTION_RECOVERY_COMPENSATION,
    EXCEPTION_RETENTION_CONTINUITY,
    EXCEPTION_RESTRICTED,
    EXCEPTION_SPONSORED_ACCESS,
    ACCESS_SUSPENDED,
    GOVERNANCE_STATUS_ACTIVE,
    _EXCEPTION_DEFAULT_ACCESS,
    _EXCEPTION_TO_DEFAULT_STATE,
    _MAX_DURATION_DAYS,
    derive_continuity_strategy,
    derive_customer_access_state,
    derive_effective_access_reason,
    get_active_governance,
    load_client_billing_signals,
    plan_display_label,
    resolve_authoritative_plan_code,
    supersede_active_governance,
    validate_entitlement_authority,
)
from services.entitlement_access import compute_canonical_entitlement_state

logger = logging.getLogger(__name__)

ACTION_GRANT_GRACE = "grant_grace_period"
ACTION_SUSPEND_BILLING = "suspend_billing"
ACTION_RESUME_BILLING = "resume_billing"
ACTION_SPONSORED_ACCESS = "grant_sponsored_access"
ACTION_RETENTION_EXTENSION = "retention_extension"
ACTION_WAIVE_ONBOARDING = "waive_onboarding_fee"
ACTION_RECOVERY_COMPENSATION = "apply_recovery_compensation"
ACTION_RESTRICT = "restrict_entitlement"
ACTION_REVOKE = "revoke_commercial_exception"

_ACTION_TO_EXCEPTION = {
    ACTION_GRANT_GRACE: EXCEPTION_GRACE_EXTENSION,
    ACTION_SUSPEND_BILLING: EXCEPTION_BILLING_SUSPENSION,
    ACTION_SPONSORED_ACCESS: EXCEPTION_SPONSORED_ACCESS,
    ACTION_RETENTION_EXTENSION: EXCEPTION_RETENTION_CONTINUITY,
    ACTION_WAIVE_ONBOARDING: EXCEPTION_ONBOARDING_WAIVER,
    ACTION_RECOVERY_COMPENSATION: EXCEPTION_RECOVERY_COMPENSATION,
    ACTION_RESTRICT: EXCEPTION_RESTRICTED,
}

_REVOCABLE_ACTIONS = frozenset({ACTION_RESUME_BILLING, ACTION_REVOKE})


class CommercialEntitlementExecutionError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def prevent_duplicate_active_exception(client_id: str) -> None:
    if await get_active_governance(client_id):
        raise CommercialEntitlementExecutionError(
            "ACTIVE_EXCEPTION_EXISTS",
            "An active commercial entitlement exception already exists. Revoke or wait for expiry before issuing another.",
        )


def validate_transition(action: str, *, has_active: bool) -> None:
    if action in _REVOCABLE_ACTIONS:
        if not has_active:
            raise CommercialEntitlementExecutionError(
                "NO_ACTIVE_EXCEPTION",
                "No active commercial exception to resume or revoke.",
            )
        return
    if has_active:
        raise CommercialEntitlementExecutionError(
            "ACTIVE_EXCEPTION_EXISTS",
            "Only one active commercial exception per client is allowed.",
        )


def derive_customer_impact_preview(
    *,
    action: str,
    duration_days: Optional[int],
    entitlement_expiry_at: Optional[datetime],
    sponsor_reference: Optional[str],
    access_policy: str,
    customer_note: Optional[str],
    underlying_canonical: Optional[str] = None,
    restored_plan_code: Optional[str] = None,
    stripe_pause_mode: Optional[str] = None,
) -> Dict[str, Any]:
    exception_type = _ACTION_TO_EXCEPTION.get(action)
    underlying = (underlying_canonical or "").upper()
    cancelled_underlying = underlying == "CANCELLED"
    plan_label = plan_display_label(restored_plan_code)
    if action in _REVOCABLE_ACTIONS:
        resume_billing = (
            "Billing collection resumes only if the underlying subscription remains billable."
            if cancelled_underlying
            else "Billing collection resumes per the underlying subscription."
        )
        return {
            "customer_impact": "Standard billing and access rules will resume for this account.",
            "access_impact": "Access returns to the underlying subscription and lifecycle rules.",
            "billing_impact": resume_billing,
            "expiry_behaviour": "Active commercial exception will be closed.",
            "stripe_impact": (
                "No Stripe subscription recreation. Collection resume applies only where the subscription is still billable."
                if cancelled_underlying
                else "Stripe pause_collection is cleared when the underlying subscription remains billable."
            ),
            "operational_continuity": "Compliance records and evidence remain available.",
        }
    state = _EXCEPTION_TO_DEFAULT_STATE.get(exception_type or "", "ACTIVE")
    exp = entitlement_expiry_at
    if not exp and duration_days:
        exp = _now() + timedelta(days=duration_days)
    exp_label = exp.strftime("%Y-%m-%d") if exp else "the configured end date"
    continuity = derive_continuity_strategy(state, exception_type=exception_type, access_policy=access_policy)
    customer_lines = []
    if action == ACTION_GRANT_GRACE:
        customer_lines.append(f"Your access has been temporarily extended until {exp_label}.")
    elif action == ACTION_SUSPEND_BILLING:
        if cancelled_underlying:
            customer_lines.append(
                f"Temporary {plan_label} plan access has been restored until {exp_label}. "
                "Billing will not be collected during this period. "
                "Your underlying account remains cancelled and that status will apply again after "
                f"{exp_label} unless otherwise changed."
            )
        else:
            customer_lines.append(
                f"Billing collection is paused until {exp_label}. "
                f"You keep {plan_label} plan access during this period. "
                "This does not change your underlying subscription status."
            )
    elif action == ACTION_SPONSORED_ACCESS:
        customer_lines.append("Your organisation currently has sponsored access through your programme arrangement.")
    elif action == ACTION_RETENTION_EXTENSION:
        customer_lines.append(f"Your access has been extended until {exp_label} while we help you continue setup.")
    elif action == ACTION_WAIVE_ONBOARDING:
        customer_lines.append("Your onboarding fee has been waived for this account.")
    elif action == ACTION_RECOVERY_COMPENSATION:
        customer_lines.append("A service credit has been applied while we resolve your account issue.")
    elif action == ACTION_RESTRICT:
        customer_lines.append("Some account capabilities are temporarily limited until the issue is resolved.")
    if customer_note:
        customer_lines.append(customer_note.strip())

    if action == ACTION_SUSPEND_BILLING:
        if cancelled_underlying or stripe_pause_mode == "already_non_collecting":
            billing_impact = (
                "Underlying subscription is already non-collecting. No Stripe subscription will be created. "
                "Temporary plan-equivalent access is platform-governed."
            )
            stripe_impact = "No Stripe mutation; cancelled/non-collecting subscription left in place."
            access_impact = f"Effective access restored to the customer's {plan_label} plan. Underlying cancellation is preserved."
        else:
            billing_impact = (
                "Stripe collection is paused via pause_collection (void) for the exception duration. "
                "Recurring invoices will not be collected while the exception is active."
            )
            stripe_impact = "stripe.Subscription.modify pause_collection behavior=void on the existing subscription."
            access_impact = f"{plan_label} plan access remains available. Underlying lifecycle is unchanged."
    else:
        access_impact = (
            "Full operational access preserved."
            if continuity.get("full_operational_continuity")
            else "Access may be limited per policy."
        )
        billing_impact = (
            "Platform billing collection flagged paused."
            if continuity.get("billing_collection_paused")
            else "Billing continues unless otherwise stated."
        )
        stripe_impact = "No automatic Stripe subscription recreation. Reconciliation remains idempotent."

    return {
        "customer_impact": " ".join(customer_lines) if customer_lines else "Customer will receive a continuity notice.",
        "access_impact": access_impact,
        "billing_impact": billing_impact,
        "expiry_behaviour": (
            f"Exception ends on {exp_label}. Underlying lifecycle then resumes unless another valid event has changed the account."
        ),
        "stripe_impact": stripe_impact,
            "operational_continuity": (
            "Existing compliance records and evidence remain accessible."
            if continuity.get("preserve_compliance_records")
            else "Operational access may be restricted; records are not deleted."
        ),
        "underlying_canonical_entitlement_state": underlying or None,
        "restored_plan_code": restored_plan_code,
        "notification_subject": (
            "Temporary access restored on your account"
            if action == ACTION_SUSPEND_BILLING and cancelled_underlying
            else None
        ),
    }


async def _persist_governance_row(
    *,
    client_id: str,
    exception_type: str,
    entitlement_state: str,
    reason: str,
    scope: str,
    actor: Dict[str, Any],
    origin: str,
    duration_days: Optional[int],
    entitlement_expiry_at: Optional[datetime],
    entitlement_review_at: Optional[datetime],
    entitlement_review_required: bool,
    sponsor_reference: Optional[str],
    access_policy: str,
    supersedes_governance_id: Optional[str],
    send_customer_email: bool,
    restored_plan_code: Optional[str] = None,
    restored_plan_source: Optional[str] = None,
    previous_canonical_state: Optional[str] = None,
    previous_lifecycle_state: Optional[str] = None,
    stripe_pause_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    now = _now()
    if not entitlement_expiry_at and duration_days:
        entitlement_expiry_at = now + timedelta(days=duration_days)
    if exception_type == EXCEPTION_SPONSORED_ACCESS and not entitlement_review_at and entitlement_expiry_at:
        entitlement_review_at = entitlement_expiry_at

    stripe_status = "pending_lightweight"
    stripe_plan = "reconcile_lightweight_v1"
    if stripe_pause_result:
        stripe_status = stripe_pause_result.get("reconciliation_status") or "applied"
        stripe_plan = stripe_pause_result.get("mutation") or stripe_plan

    doc = {
        "governance_id": str(uuid.uuid4()),
        "client_id": client_id,
        "entitlement_state": entitlement_state,
        "exception_type": exception_type,
        "entitlement_reason": reason.strip(),
        "entitlement_scope": scope,
        "entitlement_expiry_at": entitlement_expiry_at.isoformat() if entitlement_expiry_at else None,
        "entitlement_review_at": entitlement_review_at.isoformat() if entitlement_review_at else None,
        "entitlement_review_required": entitlement_review_required,
        "entitlement_actor": {
            "type": "admin",
            "id": actor.get("id"),
            "email": actor.get("email"),
        },
        "entitlement_origin": origin,
        "sponsor_reference": (sponsor_reference or "").strip() or None,
        "access_policy": access_policy,
        "effective_access_reason": None,
        "restored_plan_code": restored_plan_code,
        "restored_plan_source": restored_plan_source,
        "previous_canonical_entitlement_state": previous_canonical_state,
        "previous_lifecycle_state": previous_lifecycle_state,
        "stripe_reconciliation_status": stripe_status,
        "stripe_action_plan": stripe_plan,
        "stripe_pause_result": stripe_pause_result,
        "customer_notification_status": "pending" if send_customer_email else "skipped",
        "status": GOVERNANCE_STATUS_ACTIVE,
        "supersedes_governance_id": supersedes_governance_id,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    doc["effective_access_reason"] = derive_effective_access_reason(doc)

    db = database.get_db()
    try:
        await db[COL_GOVERNANCE].insert_one(doc)
    except DuplicateKeyError as exc:
        raise CommercialEntitlementExecutionError(
            "ACTIVE_EXCEPTION_EXISTS",
            "An active commercial entitlement exception already exists. Revoke or wait for expiry before issuing another.",
        ) from exc
    doc.pop("_id", None)

    signals = await load_client_billing_signals(client_id)
    signals["active_governance"] = doc
    access = derive_customer_access_state(signals)
    canon = access.get("canonical_entitlement_state")
    effective = access.get("effective_entitlement_state")
    restored = access.get("restored_plan_code") or restored_plan_code
    client_set: Dict[str, Any] = {
        "canonical_entitlement_state": canon,
        "commercial_governance_id": doc["governance_id"],
        "commercial_governance_state": entitlement_state,
        "effective_access_reason": doc["effective_access_reason"],
        "commercial_effective_entitlement_state": effective,
        "commercial_restored_plan_code": restored,
    }
    if exception_type == EXCEPTION_BILLING_SUSPENSION:
        client_set["commercial_billing_collection_paused"] = True
    await db.clients.update_one({"client_id": client_id}, {"$set": client_set})
    billing = signals.get("billing") or {}
    if billing:
        billing_set = {
            "canonical_entitlement_state": canon,
            "commercial_effective_entitlement_state": effective,
            "commercial_restored_plan_code": restored,
        }
        if exception_type == EXCEPTION_BILLING_SUSPENSION:
            billing_set["commercial_billing_collection_paused"] = True
        await db.client_billing.update_one({"client_id": client_id}, {"$set": billing_set})
    try:
        from services.account_lifecycle_runtime_contract import invalidate_runtime_cache_for_client

        invalidate_runtime_cache_for_client(client_id)
    except Exception:
        logger.debug("runtime cache invalidate skipped client_id=%s", client_id)
    return doc


async def apply_governed_entitlement_action(
    *,
    client_id: str,
    action: str,
    reason: str,
    actor: Dict[str, Any],
    origin: str = "admin_commercial_controls",
    duration_days: Optional[int] = None,
    entitlement_expiry_at: Optional[datetime] = None,
    entitlement_review_at: Optional[datetime] = None,
    entitlement_review_required: bool = False,
    sponsor_reference: Optional[str] = None,
    access_policy: Optional[str] = None,
    scope: str = "account",
    send_customer_email: bool = False,
    customer_note: Optional[str] = None,
    actor_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    signals = await load_client_billing_signals(client_id)
    if not signals.get("found"):
        raise CommercialEntitlementExecutionError("CLIENT_NOT_FOUND", "Client not found.", 404)

    active = await get_active_governance(client_id)
    validate_transition(action, has_active=bool(active))

    if action in _REVOCABLE_ACTIONS:
        return await _revoke_active(client_id, reason=reason, actor=actor, actor_id=actor_id, ip_address=ip_address)

    await prevent_duplicate_active_exception(client_id)

    exception_type = _ACTION_TO_EXCEPTION.get(action)
    if not exception_type:
        raise CommercialEntitlementExecutionError("ACTION_NOT_SUPPORTED", f"Unknown action: {action}")

    policy = access_policy or _EXCEPTION_DEFAULT_ACCESS.get(exception_type, "full_access")
    if policy not in ALL_ACCESS_POLICIES:
        raise CommercialEntitlementExecutionError("INVALID_ACCESS_POLICY", f"Invalid access_policy: {policy}")

    ok, err = validate_entitlement_authority(
        exception_type=exception_type,
        duration_days=duration_days,
        sponsor_reference=sponsor_reference,
        entitlement_expiry_at=entitlement_expiry_at,
    )
    if not ok:
        raise CommercialEntitlementExecutionError("VALIDATION_FAILED", err or "Validation failed.")

    if exception_type == EXCEPTION_SPONSORED_ACCESS:
        entitlement_review_required = True

    plan_code, plan_source = resolve_authoritative_plan_code(signals)
    if action == ACTION_SUSPEND_BILLING and not plan_code:
        raise CommercialEntitlementExecutionError(
            "PLAN_UNRESOLVED",
            "Cannot determine the customer's last valid subscribed plan. Suspend billing was not applied.",
            409,
        )

    baseline_access = derive_customer_access_state({**signals, "active_governance": None})
    underlying_canonical = baseline_access.get("canonical_entitlement_state")
    previous_lifecycle = (signals.get("billing") or {}).get("billing_lifecycle_state") or (
        signals.get("client") or {}
    ).get("billing_lifecycle_state")

    stripe_pause_result: Optional[Dict[str, Any]] = None
    if action == ACTION_SUSPEND_BILLING:
        from services.stripe_service import stripe_service

        try:
            stripe_pause_result = await stripe_service.pause_subscription_collection(
                client_id,
                actor_id=actor_id,
            )
        except Exception as exc:
            raise CommercialEntitlementExecutionError(
                "STRIPE_PAUSE_FAILED",
                f"Could not pause Stripe collection. Suspend billing was not applied. {str(exc)[:240]}",
                502,
            ) from exc

    preview = derive_customer_impact_preview(
        action=action,
        duration_days=duration_days,
        entitlement_expiry_at=entitlement_expiry_at,
        sponsor_reference=sponsor_reference,
        access_policy=policy,
        customer_note=customer_note,
        underlying_canonical=underlying_canonical,
        restored_plan_code=plan_code,
        stripe_pause_mode=(stripe_pause_result or {}).get("mutation"),
    )

    entitlement_state = _EXCEPTION_TO_DEFAULT_STATE[exception_type]
    if action == ACTION_RESTRICT:
        policy = ACCESS_SUSPENDED

    try:
        governance_doc = await _persist_governance_row(
            client_id=client_id,
            exception_type=exception_type,
            entitlement_state=entitlement_state,
            reason=reason,
            scope=scope,
            actor=actor,
            origin=origin,
            duration_days=duration_days,
            entitlement_expiry_at=entitlement_expiry_at,
            entitlement_review_at=entitlement_review_at,
            entitlement_review_required=entitlement_review_required,
            sponsor_reference=sponsor_reference,
            access_policy=policy,
            supersedes_governance_id=None,
            send_customer_email=send_customer_email,
            restored_plan_code=plan_code,
            restored_plan_source=plan_source,
            previous_canonical_state=underlying_canonical,
            previous_lifecycle_state=previous_lifecycle,
            stripe_pause_result=stripe_pause_result,
        )
    except Exception:
        if action == ACTION_SUSPEND_BILLING and (stripe_pause_result or {}).get("mutation") == "pause_collection":
            try:
                from services.stripe_service import stripe_service as _stripe

                await _stripe.resume_subscription_collection(client_id, actor_id=actor_id)
            except Exception as resume_exc:
                logger.warning(
                    "compensating stripe resume failed after persist error client_id=%s: %s",
                    client_id,
                    resume_exc,
                )
        raise

    if exception_type == EXCEPTION_ONBOARDING_WAIVER:
        await _persist_onboarding_fee_waiver(
            client_id=client_id,
            client=signals.get("client") or {},
            reason=reason,
            actor_id=actor.get("id"),
        )

    email_result: Dict[str, Any] = {}
    if send_customer_email:
        email_result = await _send_continuity_email_isolated(
            client_id=client_id,
            client=signals.get("client") or {},
            action=action,
            preview=preview,
            governance_doc=governance_doc,
        )
        db = database.get_db()
        status = "sent" if email_result.get("email_sent") else (
            "skipped" if email_result.get("outcome") == "no_recipient" else "failed"
        )
        await db[COL_GOVERNANCE].update_one(
            {"governance_id": governance_doc["governance_id"]},
            {"$set": {"customer_notification_status": status}},
        )

    from services.commercial_entitlement_observability_service import (
        EVENT_COMMERCIAL_GRANTED,
        record_commercial_entitlement_event,
    )

    await record_commercial_entitlement_event(
        event_type=EVENT_COMMERCIAL_GRANTED,
        client_id=client_id,
        governance_id=governance_doc["governance_id"],
        action=action,
        actor_id=actor_id,
        metadata={
            "reason_preview": reason[:200],
            "ip_address": ip_address,
            "preview": preview,
            "notification_outcome": email_result.get("outcome"),
            "restored_plan_code": plan_code,
            "underlying_canonical_entitlement_state": underlying_canonical,
            "stripe_pause": stripe_pause_result,
        },
    )
    recon = await _reconcile_billing_isolated(client_id)

    from services.commercial_entitlement_service import build_commercial_entitlement_assessment

    return {
        "ok": True,
        "client_id": client_id,
        "action": action,
        "governance": governance_doc,
        "impact_preview": preview,
        "email_result": email_result,
        "stripe_reconciliation": recon,
        "stripe_pause": stripe_pause_result,
        "restored_plan_code": plan_code,
        "underlying_canonical_entitlement_state": underlying_canonical,
        "assessment": await build_commercial_entitlement_assessment(client_id),
    }


async def _persist_onboarding_fee_waiver(
    *,
    client_id: str,
    client: Dict[str, Any],
    reason: str,
    actor_id: Optional[str],
) -> None:
    """Connect commercial waive action to the existing checkout waiver flags (idempotent)."""
    from models.pilot_invite import PilotOnboardingFeePolicy
    from services.pilot_onboarding_fee import onboarding_fields_for_waived_client

    plan_code = (
        client.get("plan_code")
        or client.get("selected_plan")
        or client.get("plan")
        or "PLAN_1_SOLO"
    )
    fields = onboarding_fields_for_waived_client(
        policy=PilotOnboardingFeePolicy.WAIVED,
        plan_code=str(plan_code),
        reason=reason,
        waived_by=actor_id,
    )
    db = database.get_db()
    await db.clients.update_one({"client_id": client_id}, {"$set": fields})
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 1})
    if billing:
        await db.client_billing.update_one({"client_id": client_id}, {"$set": fields})


async def _send_continuity_email_isolated(
    *,
    client_id: str,
    client: Dict[str, Any],
    action: str,
    preview: Dict[str, Any],
    governance_doc: Dict[str, Any],
) -> Dict[str, Any]:
    recipient = (client.get("email") or client.get("contact_email") or "").strip()
    if not recipient:
        return {"email_sent": False, "outcome": "no_recipient"}
    from services.commercial_entitlement_notification_service import (
        send_commercial_continuity_email,
    )

    try:
        return await asyncio.wait_for(
            send_commercial_continuity_email(
                client_id=client_id,
                recipient=recipient,
                action=action,
                impact_preview=preview,
                effective_access_reason=governance_doc.get("effective_access_reason") or "",
                expiry_at=governance_doc.get("entitlement_expiry_at"),
                governance_id=governance_doc.get("governance_id"),
            ),
            timeout=25,
        )
    except Exception as exc:
        logger.warning(
            "commercial continuity email failed client_id=%s action=%s: %s",
            client_id,
            action,
            exc,
        )
        return {
            "email_sent": False,
            "outcome": "failed",
            "block_reason": str(exc)[:200],
        }


async def _reconcile_billing_isolated(client_id: str) -> Dict[str, Any]:
    from services.commercial_entitlement_stripe_convergence_service import (
        reconcile_entitlement_billing_state,
    )

    try:
        return await asyncio.wait_for(reconcile_entitlement_billing_state(client_id), timeout=20)
    except Exception as exc:
        logger.warning("commercial stripe reconciliation failed client_id=%s: %s", client_id, exc)
        return {"ok": False, "error": "RECONCILIATION_FAILED", "detail": str(exc)[:200]}


async def _revoke_active(
    client_id: str,
    *,
    reason: str,
    actor: Dict[str, Any],
    actor_id: Optional[str],
    ip_address: Optional[str],
) -> Dict[str, Any]:
    db = database.get_db()
    prev_id = await supersede_active_governance(
        client_id, actor_id=actor_id or "", reason=reason
    )
    await db[COL_GOVERNANCE].update_one(
        {"governance_id": prev_id},
        {"$set": {"status": "revoked", "revoked_at": _now().isoformat()}},
    )
    signals = await load_client_billing_signals(client_id)
    client = signals["client"]
    billing = signals.get("billing") or {}
    canon = compute_canonical_entitlement_state(
        billing_lifecycle_state=(billing.get("billing_lifecycle_state") or client.get("billing_lifecycle_state")),
        subscription_status_upper=(billing.get("subscription_status") or client.get("subscription_status")),
    )
    await db.clients.update_one(
        {"client_id": client_id},
        {
            "$set": {"canonical_entitlement_state": canon},
            "$unset": COMMERCIAL_OVERLAY_UNSET,
        },
    )
    if billing:
        await db.client_billing.update_one(
            {"client_id": client_id},
            {
                "$set": {"canonical_entitlement_state": canon},
                "$unset": {
                    "commercial_effective_entitlement_state": "",
                    "commercial_restored_plan_code": "",
                    "commercial_billing_collection_paused": "",
                },
            },
        )
    stripe_resume: Dict[str, Any] = {}
    if (signals.get("client") or {}).get("commercial_billing_collection_paused") or billing.get(
        "commercial_billing_collection_paused"
    ):
        try:
            from services.stripe_service import stripe_service

            stripe_resume = await stripe_service.resume_subscription_collection(
                client_id, actor_id=actor_id
            )
        except Exception as exc:
            logger.warning("commercial stripe resume failed client_id=%s: %s", client_id, exc)
            stripe_resume = {"ok": False, "error": str(exc)[:200]}
    try:
        from services.account_lifecycle_runtime_contract import invalidate_runtime_cache_for_client

        invalidate_runtime_cache_for_client(client_id)
    except Exception:
        logger.debug("runtime cache invalidate skipped client_id=%s", client_id)
    from services.commercial_entitlement_observability_service import (
        EVENT_COMMERCIAL_REVOKED,
        record_commercial_entitlement_event,
    )

    await record_commercial_entitlement_event(
        event_type=EVENT_COMMERCIAL_REVOKED,
        client_id=client_id,
        governance_id=prev_id,
        action=ACTION_RESUME_BILLING,
        actor_id=actor_id,
        metadata={"reason_preview": reason[:200], "ip_address": ip_address},
    )
    from services.commercial_entitlement_service import build_commercial_entitlement_assessment

    return {
        "ok": True,
        "client_id": client_id,
        "action": ACTION_RESUME_BILLING,
        "revoked_governance_id": prev_id,
        "stripe_resume": stripe_resume,
        "assessment": await build_commercial_entitlement_assessment(client_id),
    }
