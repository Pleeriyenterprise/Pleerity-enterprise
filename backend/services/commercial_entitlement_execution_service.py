"""Governed commercial entitlement action execution (Phase 2C)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from database import database
from services.commercial_entitlement_service import (
    ALL_ACCESS_POLICIES,
    COL_GOVERNANCE,
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
) -> Dict[str, Any]:
    exception_type = _ACTION_TO_EXCEPTION.get(action)
    if action in _REVOCABLE_ACTIONS:
        return {
            "customer_impact": "Standard billing and access rules will resume for this account.",
            "access_impact": "Access returns to subscription-derived rules.",
            "billing_impact": "Billing collection resumes per platform policy.",
            "expiry_behaviour": "Active commercial exception will be closed.",
            "stripe_impact": "No automatic Stripe mutation in v1; reconciliation runs separately.",
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
        customer_lines.append("Billing for your account is temporarily paused while we review your request.")
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
    return {
        "customer_impact": " ".join(customer_lines) if customer_lines else "Customer will receive a continuity notice.",
        "access_impact": (
            "Full operational access preserved."
            if continuity.get("full_operational_continuity")
            else "Access may be limited per policy."
        ),
        "billing_impact": (
            "Billing collection paused."
            if continuity.get("billing_collection_paused")
            else "Billing continues unless otherwise stated."
        ),
        "expiry_behaviour": f"Exception ends on {exp_label} unless reviewed earlier.",
        "stripe_impact": "Platform authoritative in v1; Stripe reconciliation is lightweight and non-destructive.",
        "operational_continuity": (
            "Existing compliance records and evidence remain accessible."
            if continuity.get("preserve_compliance_records")
            else "Operational access may be restricted; records are not deleted."
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
) -> Dict[str, Any]:
    now = _now()
    if not entitlement_expiry_at and duration_days:
        entitlement_expiry_at = now + timedelta(days=duration_days)
    if exception_type == EXCEPTION_SPONSORED_ACCESS and not entitlement_review_at and entitlement_expiry_at:
        entitlement_review_at = entitlement_expiry_at

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
        "stripe_reconciliation_status": "pending_lightweight",
        "stripe_action_plan": "reconcile_lightweight_v1",
        "customer_notification_status": "pending" if send_customer_email else "skipped",
        "status": GOVERNANCE_STATUS_ACTIVE,
        "supersedes_governance_id": supersedes_governance_id,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    doc["effective_access_reason"] = derive_effective_access_reason(doc)

    db = database.get_db()
    await db[COL_GOVERNANCE].insert_one(doc)
    doc.pop("_id", None)

    signals = await load_client_billing_signals(client_id)
    signals["active_governance"] = doc
    access = derive_customer_access_state(signals)
    canon = access.get("canonical_entitlement_state")
    await db.clients.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "canonical_entitlement_state": canon,
                "commercial_governance_id": doc["governance_id"],
                "commercial_governance_state": entitlement_state,
                "effective_access_reason": doc["effective_access_reason"],
            }
        },
    )
    billing = signals.get("billing") or {}
    if billing:
        await db.client_billing.update_one(
            {"client_id": client_id},
            {"$set": {"canonical_entitlement_state": canon}},
        )
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

    preview = derive_customer_impact_preview(
        action=action,
        duration_days=duration_days,
        entitlement_expiry_at=entitlement_expiry_at,
        sponsor_reference=sponsor_reference,
        access_policy=policy,
        customer_note=customer_note,
    )

    entitlement_state = _EXCEPTION_TO_DEFAULT_STATE[exception_type]
    if action == ACTION_RESTRICT:
        policy = ACCESS_SUSPENDED

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
    )

    email_result: Dict[str, Any] = {}
    if send_customer_email:
        from services.commercial_entitlement_notification_service import (
            send_commercial_continuity_email,
        )

        client = signals["client"]
        recipient = (client.get("email") or client.get("contact_email") or "").strip()
        if recipient:
            email_result = await send_commercial_continuity_email(
                client_id=client_id,
                recipient=recipient,
                action=action,
                impact_preview=preview,
                effective_access_reason=governance_doc.get("effective_access_reason") or "",
                expiry_at=governance_doc.get("entitlement_expiry_at"),
            )
            db = database.get_db()
            status = "sent" if email_result.get("email_sent") else "failed"
            await db[COL_GOVERNANCE].update_one(
                {"governance_id": governance_doc["governance_id"]},
                {"$set": {"customer_notification_status": status}},
            )

    from services.commercial_entitlement_observability_service import (
        EVENT_COMMERCIAL_GRANTED,
        record_commercial_entitlement_event,
    )
    from services.commercial_entitlement_stripe_convergence_service import (
        reconcile_entitlement_billing_state,
    )

    await record_commercial_entitlement_event(
        event_type=EVENT_COMMERCIAL_GRANTED,
        client_id=client_id,
        governance_id=governance_doc["governance_id"],
        action=action,
        actor_id=actor_id,
        metadata={"reason_preview": reason[:200], "ip_address": ip_address, "preview": preview},
    )
    recon = await reconcile_entitlement_billing_state(client_id)

    from services.commercial_entitlement_service import build_commercial_entitlement_assessment

    return {
        "ok": True,
        "client_id": client_id,
        "action": action,
        "governance": governance_doc,
        "impact_preview": preview,
        "email_result": email_result,
        "stripe_reconciliation": recon,
        "assessment": await build_commercial_entitlement_assessment(client_id),
    }


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
            "$unset": {
                "commercial_governance_id": "",
                "commercial_governance_state": "",
                "effective_access_reason": "",
            },
        },
    )
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
        "assessment": await build_commercial_entitlement_assessment(client_id),
    }
