"""
Canonical pilot lifecycle governance — platform authority for pilot state; Stripe for billing.

All admin and webhook pilot mutations must go through this module.
"""
from __future__ import annotations

import calendar
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from database import database
from models import AuditAction, UserRole
from models.pilot_lifecycle import PilotDiscountSource, PilotLifecycleAction, PilotStatus
from services.pilot_lifecycle_audit import build_pilot_lifecycle_audit_document, insert_pilot_lifecycle_audit
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

# Terminal / non-extendable statuses
_TERMINAL = frozenset(
    {
        PilotStatus.CANCELLED.value,
        PilotStatus.COMPED.value,
        PilotStatus.CONVERTED_TO_PAID.value,
    }
)
_EXTENDABLE = frozenset({PilotStatus.ACTIVE.value, PilotStatus.EXTENDED.value, PilotStatus.PAUSED.value})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _add_months(start: datetime, months: int) -> datetime:
    if months <= 0:
        return start
    y, m = start.year, start.month + months
    while m > 12:
        m -= 12
        y += 1
    last_day = calendar.monthrange(y, m)[1]
    d = min(start.day, last_day)
    return start.replace(year=y, month=m, day=d)


def _add_days(start: datetime, days: int) -> datetime:
    return start + timedelta(days=days)


def _effective_expiry(doc: Dict[str, Any]) -> Optional[datetime]:
    exp = doc.get("pilot_expires_at")
    ext = doc.get("pilot_extended_until")
    candidates = []
    for v in (exp, ext):
        if v is None:
            continue
        if isinstance(v, str):
            try:
                v = datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                continue
        if isinstance(v, datetime):
            candidates.append(v if v.tzinfo else v.replace(tzinfo=timezone.utc))
    if not candidates:
        return None
    return max(candidates)


def _snapshot_pilot_fields(doc: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "pilot_status",
        "pilot_program_type",
        "pilot_started_at",
        "pilot_expires_at",
        "pilot_extended_until",
        "pilot_cancelled_at",
        "pilot_converted_to_paid_at",
        "pilot_comped_at",
        "pilot_duration_months",
        "pilot_invite_code",
        "pilot_discount_percent",
        "pilot_discount_source",
        "pilot_notes",
        "pilot_manually_overridden",
        "pilot_override_reason",
        "pilot_expected_first_paid_invoice_at",
        "pilot_governance_revoke_access",
        "onboarding_fee_policy",
        "onboarding_fee_waived",
        "onboarding_fee_waived_at",
        "onboarding_fee_waived_by",
        "onboarding_fee_waiver_reason",
        "onboarding_fee_deferred_until",
        "onboarding_fee_charged_at",
        "onboarding_fee_amount",
        "onboarding_fee_currency",
    )
    out: Dict[str, Any] = {}
    for k in keys:
        if k in doc:
            v = doc[k]
            out[k] = v.isoformat() if isinstance(v, datetime) else v
    return out


def _build_client_patch(state: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten lifecycle state onto client document (+ nested pilot for backward compat)."""
    patch: Dict[str, Any] = dict(state)
    nested = {
        "program_type": state.get("pilot_program_type"),
        "invite_code": state.get("pilot_invite_code"),
        "status": state.get("pilot_status"),
        "started_at": _iso(state.get("pilot_started_at")),
        "expires_at": _iso(state.get("pilot_expires_at")),
        "extended_until": _iso(state.get("pilot_extended_until")),
        "discount_percent": state.get("pilot_discount_percent"),
        "discount_source": state.get("pilot_discount_source"),
        "expected_first_paid_invoice_at": _iso(state.get("pilot_expected_first_paid_invoice_at")),
    }
    patch["pilot"] = {k: v for k, v in nested.items() if v is not None}
    # Legacy mirrors
    if state.get("pilot_program_type"):
        patch["pilot_program_type"] = state["pilot_program_type"]
    if state.get("pilot_invite_code"):
        patch["pilot_invite_code"] = state["pilot_invite_code"]
    if state.get("pilot_started_at"):
        patch["pilot_started_at"] = state["pilot_started_at"]
    patch["pilot_discount_applied"] = state.get("pilot_status") in (
        PilotStatus.ACTIVE.value,
        PilotStatus.EXTENDED.value,
        PilotStatus.PAUSED.value,
    )
    if state.get("pilot_converted_to_paid_at"):
        patch["pilot_transitioned_to_paid_at"] = state["pilot_converted_to_paid_at"]
    return patch


def _iso(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


async def _load_client(client_id: str) -> Dict[str, Any]:
    db = database.get_db()
    doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not doc:
        raise ValueError("CLIENT_NOT_FOUND")
    return doc


async def _persist_transition(
    *,
    client_id: str,
    before: Dict[str, Any],
    patch: Dict[str, Any],
    action: PilotLifecycleAction,
    actor: Dict[str, Any],
    reason: Optional[str] = None,
    notes: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    stripe_event_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    db = database.get_db()
    now = _utc_now()
    patch = dict(patch)
    patch["pilot_last_admin_action_at"] = now
    if actor.get("type") == "admin" and actor.get("id"):
        patch["pilot_last_admin_actor_id"] = str(actor["id"])

    client_patch = _build_client_patch(patch)
    await db.clients.update_one({"client_id": client_id}, {"$set": client_patch})
    after_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0})

    audit_doc = build_pilot_lifecycle_audit_document(
        client_id=client_id,
        action_type=action.value,
        actor=actor,
        previous_values=_snapshot_pilot_fields(before),
        new_values=_snapshot_pilot_fields(after_doc or patch),
        reason=reason,
        notes=notes,
        stripe_subscription_id=stripe_subscription_id,
        stripe_event_id=stripe_event_id,
        idempotency_key=idempotency_key,
    )
    await insert_pilot_lifecycle_audit(audit_doc)

    if actor.get("type") == "admin":
        try:
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role=UserRole.ADMIN,
                actor_id=str(actor.get("id") or ""),
                client_id=client_id,
                metadata={
                    "action_type": f"PILOT_LIFECYCLE_{action.value.upper()}",
                    "reason": reason,
                    "pilot_status": patch.get("pilot_status"),
                },
            )
        except Exception:
            pass

    return after_doc or patch


def is_pilot_comped_entitled(client: Dict[str, Any]) -> bool:
    return str(client.get("pilot_status") or "").lower() == PilotStatus.COMPED.value


def pilot_governance_blocks_access(client: Dict[str, Any]) -> bool:
    """When admin cancelled pilot with immediate revoke — blocks beyond Stripe state."""
    if not client.get("pilot_governance_revoke_access"):
        return False
    return str(client.get("pilot_status") or "").lower() == PilotStatus.CANCELLED.value


def evaluate_pilot_governance_access(client: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Return (message, details) if pilot governance denies access; None if OK.
    Comped accounts bypass governance blocks. Stripe entitlement checks run separately.
    """
    if is_pilot_comped_entitled(client):
        return None
    if pilot_governance_blocks_access(client):
        return (
            "Your pilot access has been ended. Contact support if you believe this is an error.",
            {"error_code": "PILOT_ACCESS_REVOKED", "pilot_status": client.get("pilot_status")},
        )
    status = str(client.get("pilot_status") or "").lower()
    if status == PilotStatus.PAUSED.value:
        return (
            "Your pilot access is paused. Contact support to resume.",
            {"error_code": "PILOT_PAUSED", "pilot_status": status},
        )
    # expired: Stripe subscription may still grant access — do not block here
    return None


async def sync_expired_if_due(client_id: str) -> bool:
    """Mark pilot expired when past effective expiry (active/extended only)."""
    client = await _load_client(client_id)
    status = str(client.get("pilot_status") or "").lower()
    if status not in (PilotStatus.ACTIVE.value, PilotStatus.EXTENDED.value):
        return False
    eff = _effective_expiry(client)
    if not eff or eff > _utc_now():
        return False
    await _persist_transition(
        client_id=client_id,
        before=client,
        patch={**_extract_state(client), "pilot_status": PilotStatus.EXPIRED.value},
        action=PilotLifecycleAction.EXPIRED,
        actor={"type": "system", "id": "pilot_expiry_job"},
        reason="Pilot period ended",
        idempotency_key=f"pilot_expired:{client_id}:{eff.date().isoformat()}",
    )
    return True


def _extract_state(client: Dict[str, Any]) -> Dict[str, Any]:
    return {k: client.get(k) for k in _snapshot_pilot_fields(client).keys() if client.get(k) is not None}


async def create_from_invite_checkout(
    *,
    client_id: str,
    invite_doc: Dict[str, Any],
    checkout_session_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    stripe_event_id: Optional[str] = None,
    duration_months_override: Optional[int] = None,
) -> Dict[str, Any]:
    """Create pilot lifecycle after successful Stripe checkout (webhook)."""
    from services.pilot_invite_service import discount_config_from_doc

    cfg = discount_config_from_doc(invite_doc)
    months = int(duration_months_override or cfg["discount_duration_in_months"] or 0)
    now = _utc_now()
    expires = _add_months(now, months) if months > 0 else None
    expected_paid = _add_months(now, months) if cfg["expected_transition_to_paid"] and months > 0 else None

    before = await _load_client(client_id)
    if before.get("pilot_status") and str(before.get("pilot_status")) not in ("", "none"):
        logger.info("Pilot lifecycle already exists for %s — skipping create", client_id)
        return before

    state = {
        "pilot_status": PilotStatus.ACTIVE.value,
        "pilot_program_type": str(invite_doc.get("program_type") or "FOUNDING_PILOT"),
        "pilot_started_at": now,
        "pilot_expires_at": expires,
        "pilot_duration_months": months or None,
        "pilot_invite_code": str(invite_doc.get("code") or ""),
        "pilot_discount_percent": cfg["discount_percent"],
        "pilot_discount_source": PilotDiscountSource.INVITE_CODE.value,
        "pilot_expected_first_paid_invoice_at": expected_paid,
        "pilot_manually_overridden": False,
        "pilot_governance_revoke_access": False,
    }
    return await _persist_transition(
        client_id=client_id,
        before=before,
        patch=state,
        action=PilotLifecycleAction.CREATED,
        actor={"type": "system", "id": "stripe_webhook"},
        reason="Founding pilot checkout completed",
        stripe_subscription_id=stripe_subscription_id,
        stripe_event_id=stripe_event_id,
        idempotency_key=f"pilot_created:{checkout_session_id}" if checkout_session_id else None,
    )
    if onb_policy == PilotOnboardingFeePolicy.WAIVED:
        db = database.get_db()
        await db.client_billing.update_one(
            {"client_id": client_id},
            {
                "$set": {
                    "onboarding_fee_paid": True,
                    **{k: v for k, v in onb_fields.items() if k.startswith("onboarding_fee")},
                }
            },
            upsert=True,
        )
    return result


async def admin_set_onboarding_fee_policy(
    *,
    client_id: str,
    actor_id: str,
    actor_email: Optional[str],
    policy: str,
    reason: str,
    waiver_reason: Optional[str] = None,
    deferred_until: Optional[datetime] = None,
    mark_charged: bool = False,
) -> Dict[str, Any]:
    """Admin override onboarding fee policy for a pilot account."""
    from models.pilot_invite import PilotOnboardingFeePolicy
    from services.pilot_onboarding_fee import onboarding_fields_for_waived_client

    before = await _load_client(client_id)
    if not before.get("pilot_status") and not before.get("pilot_program_type"):
        raise ValueError("NOT_PILOT")

    try:
        onb_policy = PilotOnboardingFeePolicy(policy.strip().lower())
    except ValueError:
        raise ValueError("INVALID_ONBOARDING_POLICY")

    plan_code = str(before.get("billing_plan") or "PLAN_1_SOLO")
    fields = onboarding_fields_for_waived_client(
        policy=onb_policy,
        plan_code=plan_code,
        reason=waiver_reason or reason,
        waived_by=actor_id,
        deferred_until=deferred_until,
    )
    if mark_charged:
        fields["onboarding_fee_charged_at"] = _utc_now()
        fields["onboarding_fee_waived"] = False

    patch = dict(fields)
    patch["pilot_manually_overridden"] = True
    patch["pilot_override_reason"] = reason

    after = await _persist_transition(
        client_id=client_id,
        before=before,
        patch=patch,
        action=PilotLifecycleAction.NOTES_UPDATED,
        actor={"type": "admin", "id": actor_id, "email": actor_email},
        reason=reason,
        notes=waiver_reason,
        idempotency_key=f"pilot_onb_policy:{client_id}:{onb_policy.value}:{reason[:32]}",
    )

    billing_set: Dict[str, Any] = {k: v for k, v in fields.items() if k.startswith("onboarding_fee")}
    if onb_policy == PilotOnboardingFeePolicy.WAIVED:
        billing_set["onboarding_fee_paid"] = True
    elif onb_policy == PilotOnboardingFeePolicy.DEFERRED:
        billing_set["onboarding_fee_paid"] = False
    elif mark_charged or onb_policy == PilotOnboardingFeePolicy.CHARGE_NOW:
        billing_set["onboarding_fee_paid"] = True
    if billing_set:
        db = database.get_db()
        await db.client_billing.update_one(
            {"client_id": client_id},
            {"$set": billing_set},
            upsert=True,
        )
    return after


async def admin_create_override(
    *,
    client_id: str,
    actor_id: str,
    actor_email: Optional[str],
    program_type: str,
    duration_months: int,
    expires_at: Optional[datetime],
    discount_percent: int,
    invite_code: Optional[str],
    reason: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    before = await _load_client(client_id)
    now = _utc_now()
    exp = expires_at or _add_months(now, duration_months)
    state = {
        "pilot_status": PilotStatus.ACTIVE.value,
        "pilot_program_type": program_type,
        "pilot_started_at": now,
        "pilot_expires_at": exp,
        "pilot_duration_months": duration_months,
        "pilot_invite_code": invite_code,
        "pilot_discount_percent": discount_percent,
        "pilot_discount_source": PilotDiscountSource.ADMIN_OVERRIDE.value,
        "pilot_notes": notes,
        "pilot_manually_overridden": True,
        "pilot_override_reason": reason,
        "pilot_expected_first_paid_invoice_at": exp,
        "pilot_governance_revoke_access": False,
    }
    return await _persist_transition(
        client_id=client_id,
        before=before,
        patch=state,
        action=PilotLifecycleAction.CREATED,
        actor={"type": "admin", "id": actor_id, "email": actor_email},
        reason=reason,
        notes=notes,
    )


async def extend_pilot(
    *,
    client_id: str,
    actor_id: str,
    actor_email: Optional[str],
    reason: str,
    days: Optional[int] = None,
    weeks: Optional[int] = None,
    months: Optional[int] = None,
    until: Optional[datetime] = None,
) -> Dict[str, Any]:
    client = await _load_client(client_id)
    status = str(client.get("pilot_status") or "").lower()
    if status in _TERMINAL:
        raise ValueError(f"Cannot extend pilot in status {status}")
    if status not in _EXTENDABLE and status != PilotStatus.EXPIRED.value:
        raise ValueError(f"Cannot extend pilot in status {status}")

    base = _effective_expiry(client) or _utc_now()
    if until:
        new_until = until if until.tzinfo else until.replace(tzinfo=timezone.utc)
    elif months:
        new_until = _add_months(base, months)
    elif weeks:
        new_until = _add_days(base, weeks * 7)
    elif days:
        new_until = _add_days(base, days)
    else:
        raise ValueError("Extension requires days, weeks, months, or until")

    state = _extract_state(client)
    state["pilot_status"] = PilotStatus.EXTENDED.value
    state["pilot_extended_until"] = new_until
    state["pilot_manually_overridden"] = True
    state["pilot_override_reason"] = reason

    return await _persist_transition(
        client_id=client_id,
        before=client,
        patch=state,
        action=PilotLifecycleAction.EXTENDED,
        actor={"type": "admin", "id": actor_id, "email": actor_email},
        reason=reason,
    )


async def set_pilot_expiry(
    *,
    client_id: str,
    actor_id: str,
    actor_email: Optional[str],
    reason: str,
    expires_at: datetime,
) -> Dict[str, Any]:
    client = await _load_client(client_id)
    status = str(client.get("pilot_status") or "").lower()
    if status in _TERMINAL:
        raise ValueError(f"Cannot change expiry in status {status}")

    exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    started = client.get("pilot_started_at")
    if isinstance(started, datetime) and exp < (started if started.tzinfo else started.replace(tzinfo=timezone.utc)):
        raise ValueError("Expiry cannot be before pilot start")

    state = _extract_state(client)
    state["pilot_expires_at"] = exp
    state["pilot_extended_until"] = None
    state["pilot_manually_overridden"] = True
    state["pilot_override_reason"] = reason
    if status == PilotStatus.EXPIRED.value and exp > _utc_now():
        state["pilot_status"] = PilotStatus.ACTIVE.value

    return await _persist_transition(
        client_id=client_id,
        before=client,
        patch=state,
        action=PilotLifecycleAction.EXPIRY_SET,
        actor={"type": "admin", "id": actor_id, "email": actor_email},
        reason=reason,
    )


async def cancel_pilot(
    *,
    client_id: str,
    actor_id: str,
    actor_email: Optional[str],
    reason: str,
    cancel_stripe_subscription: bool = False,
    revoke_access_immediately: bool = False,
) -> Dict[str, Any]:
    client = await _load_client(client_id)
    status = str(client.get("pilot_status") or "").lower()
    if status == PilotStatus.CANCELLED.value:
        return client

    if cancel_stripe_subscription:
        from services.stripe_service import stripe_service

        await stripe_service.cancel_subscription(client_id, cancel_immediately=revoke_access_immediately)

    now = _utc_now()
    state = _extract_state(client)
    state["pilot_status"] = PilotStatus.CANCELLED.value
    state["pilot_cancelled_at"] = now
    state["pilot_manually_overridden"] = True
    state["pilot_override_reason"] = reason
    state["pilot_governance_revoke_access"] = bool(revoke_access_immediately)

    return await _persist_transition(
        client_id=client_id,
        before=client,
        patch=state,
        action=PilotLifecycleAction.CANCELLED,
        actor={"type": "admin", "id": actor_id, "email": actor_email},
        reason=reason,
    )


async def convert_to_paid(
    *,
    client_id: str,
    actor_id: str,
    actor_email: Optional[str],
    reason: str,
) -> Dict[str, Any]:
    """Mark pilot governance complete; does not mutate Stripe or reprovision."""
    client = await _load_client(client_id)
    status = str(client.get("pilot_status") or "").lower()
    if status == PilotStatus.CONVERTED_TO_PAID.value:
        return client
    if status == PilotStatus.COMPED.value:
        raise ValueError("Cannot convert comped account to paid pilot status")

    now = _utc_now()
    state = _extract_state(client)
    state["pilot_status"] = PilotStatus.CONVERTED_TO_PAID.value
    state["pilot_converted_to_paid_at"] = now
    state["pilot_manually_overridden"] = True
    state["pilot_override_reason"] = reason

    return await _persist_transition(
        client_id=client_id,
        before=client,
        patch=state,
        action=PilotLifecycleAction.CONVERTED_TO_PAID,
        actor={"type": "admin", "id": actor_id, "email": actor_email},
        reason=reason,
    )


async def comp_account(
    *,
    client_id: str,
    actor_id: str,
    actor_email: Optional[str],
    reason: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    client = await _load_client(client_id)
    now = _utc_now()
    state = _extract_state(client)
    state["pilot_status"] = PilotStatus.COMPED.value
    state["pilot_comped_at"] = now
    state["pilot_program_type"] = state.get("pilot_program_type") or "FOUNDING_PILOT"
    state["pilot_discount_source"] = PilotDiscountSource.COMP.value
    state["pilot_manually_overridden"] = True
    state["pilot_override_reason"] = reason
    state["pilot_notes"] = notes or state.get("pilot_notes")
    state["pilot_governance_revoke_access"] = False

    return await _persist_transition(
        client_id=client_id,
        before=client,
        patch=state,
        action=PilotLifecycleAction.COMPED,
        actor={"type": "admin", "id": actor_id, "email": actor_email},
        reason=reason,
        notes=notes,
    )


async def pause_pilot(
    *,
    client_id: str,
    actor_id: str,
    actor_email: Optional[str],
    reason: str,
) -> Dict[str, Any]:
    client = await _load_client(client_id)
    status = str(client.get("pilot_status") or "").lower()
    if status in _TERMINAL:
        raise ValueError(f"Cannot pause pilot in status {status}")
    state = _extract_state(client)
    state["pilot_status"] = PilotStatus.PAUSED.value
    state["pilot_manually_overridden"] = True
    state["pilot_override_reason"] = reason
    return await _persist_transition(
        client_id=client_id,
        before=client,
        patch=state,
        action=PilotLifecycleAction.PAUSED,
        actor={"type": "admin", "id": actor_id, "email": actor_email},
        reason=reason,
    )


async def resume_pilot(
    *,
    client_id: str,
    actor_id: str,
    actor_email: Optional[str],
    reason: str,
) -> Dict[str, Any]:
    client = await _load_client(client_id)
    if str(client.get("pilot_status") or "").lower() != PilotStatus.PAUSED.value:
        raise ValueError("Pilot is not paused")
    state = _extract_state(client)
    eff = _effective_expiry(client)
    new_status = PilotStatus.EXTENDED.value if client.get("pilot_extended_until") else PilotStatus.ACTIVE.value
    if eff and eff <= _utc_now():
        new_status = PilotStatus.EXPIRED.value
    state["pilot_status"] = new_status
    state["pilot_override_reason"] = reason
    return await _persist_transition(
        client_id=client_id,
        before=client,
        patch=state,
        action=PilotLifecycleAction.RESUMED,
        actor={"type": "admin", "id": actor_id, "email": actor_email},
        reason=reason,
    )


async def update_notes(
    *,
    client_id: str,
    actor_id: str,
    actor_email: Optional[str],
    notes: str,
) -> Dict[str, Any]:
    client = await _load_client(client_id)
    if not client.get("pilot_status"):
        raise ValueError("Client has no pilot lifecycle")
    state = _extract_state(client)
    state["pilot_notes"] = notes
    return await _persist_transition(
        client_id=client_id,
        before=client,
        patch=state,
        action=PilotLifecycleAction.NOTES_UPDATED,
        actor={"type": "admin", "id": actor_id, "email": actor_email},
        notes=notes,
    )


async def record_stripe_paid_transition(
    *,
    client_id: str,
    invoice: Dict[str, Any],
    stripe_event_id: Optional[str] = None,
) -> bool:
    amount_pence = int(invoice.get("amount_paid") or 0)
    if amount_pence <= 0:
        return False
    try:
        client = await _load_client(client_id)
    except ValueError:
        return False
    if not client.get("pilot_program_type") and not client.get("pilot_status"):
        return False
    if client.get("pilot_converted_to_paid_at") or client.get("pilot_transitioned_to_paid_at"):
        return False
    if str(client.get("pilot_status") or "").lower() == PilotStatus.COMPED.value:
        return False

    now = _utc_now()
    state = _extract_state(client)
    state["pilot_status"] = PilotStatus.CONVERTED_TO_PAID.value
    state["pilot_converted_to_paid_at"] = now

    await _persist_transition(
        client_id=client_id,
        before=client,
        patch=state,
        action=PilotLifecycleAction.STRIPE_PAID_TRANSITION,
        actor={"type": "system", "id": "stripe_webhook"},
        reason="First non-zero subscription invoice paid",
        stripe_event_id=stripe_event_id,
        idempotency_key=f"pilot_paid:{invoice.get('id')}" if invoice.get("id") else None,
    )
    return True


async def record_stripe_cancelled_before_paid(
    *,
    client_id: str,
    stripe_event_id: Optional[str] = None,
) -> bool:
    try:
        client = await _load_client(client_id)
    except ValueError:
        return False
    if not client.get("pilot_program_type") and not client.get("pilot_status"):
        return False
    if client.get("pilot_converted_to_paid_at") or client.get("pilot_cancelled_at"):
        return False
    if not client.get("pilot_expected_first_paid_invoice_at") and not client.get("pilot_expected_transition_to_paid"):
        return False

    now = _utc_now()
    state = _extract_state(client)
    state["pilot_status"] = PilotStatus.CANCELLED.value
    state["pilot_cancelled_at"] = now

    await _persist_transition(
        client_id=client_id,
        before=client,
        patch=state,
        action=PilotLifecycleAction.STRIPE_CANCELLED_BEFORE_PAID,
        actor={"type": "system", "id": "stripe_webhook"},
        reason="Subscription ended before pilot paid conversion",
        stripe_event_id=stripe_event_id,
        idempotency_key=f"pilot_pre_paid_cancel:{client_id}",
    )
    db = database.get_db()
    await db.clients.update_one(
        {"client_id": client_id},
        {"$set": {"pilot_cancelled_before_paid_conversion": True}},
    )
    return True


async def get_pilot_state(client_id: str) -> Dict[str, Any]:
    client = await _load_client(client_id)
    if not client.get("pilot_status") and not client.get("pilot_program_type"):
        raise ValueError("NOT_PILOT")
    eff = _effective_expiry(client)
    pilot_snap = _snapshot_pilot_fields(client)
    return {
        "client_id": client_id,
        "pilot": pilot_snap,
        "onboarding_fee": {
            k: pilot_snap.get(k)
            for k in (
                "onboarding_fee_policy",
                "onboarding_fee_waived",
                "onboarding_fee_waived_at",
                "onboarding_fee_waived_by",
                "onboarding_fee_waiver_reason",
                "onboarding_fee_deferred_until",
                "onboarding_fee_charged_at",
                "onboarding_fee_amount",
                "onboarding_fee_currency",
            )
            if pilot_snap.get(k) is not None
        },
        "effective_expires_at": eff.isoformat() if eff else None,
        "is_expired_by_date": bool(eff and eff <= _utc_now()),
    }


async def list_pilot_accounts(
    *,
    status: Optional[str] = None,
    limit: int = 200,
    skip: int = 0,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    q: Dict[str, Any] = {"pilot_status": {"$exists": True, "$ne": None}}
    if status:
        q["pilot_status"] = status.strip().lower()
    cursor = (
        db.clients.find(
            q,
            {
                "_id": 0,
                "client_id": 1,
                "email": 1,
                "contact_email": 1,
                "full_name": 1,
                "billing_plan": 1,
                "subscription_status": 1,
                "pilot_status": 1,
                "pilot_program_type": 1,
                "pilot_invite_code": 1,
                "pilot_started_at": 1,
                "pilot_expires_at": 1,
                "pilot_extended_until": 1,
                "pilot_cancelled_at": 1,
                "pilot_converted_to_paid_at": 1,
                "pilot_comped_at": 1,
                "pilot_duration_months": 1,
                "pilot_discount_percent": 1,
                "pilot_discount_source": 1,
                "pilot_expected_first_paid_invoice_at": 1,
                "pilot_notes": 1,
                "pilot_manually_overridden": 1,
                "pilot_last_admin_action_at": 1,
                "onboarding_fee_policy": 1,
                "onboarding_fee_waived": 1,
                "onboarding_fee_waiver_reason": 1,
                "onboarding_fee_deferred_until": 1,
                "onboarding_fee_charged_at": 1,
            },
        )
        .sort("pilot_started_at", -1)
        .skip(skip)
        .limit(limit)
    )
    rows = []
    async for doc in cursor:
        eff = _effective_expiry(doc)
        doc["effective_expires_at"] = eff
        rows.append(doc)
    return rows


async def get_lifecycle_history(
    client_id: str,
    *,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    cursor = (
        db.pilot_lifecycle_audit.find({"client_id": client_id}, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
    )
    return [doc async for doc in cursor]
