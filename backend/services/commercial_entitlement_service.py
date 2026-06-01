"""Commercial entitlement governance — platform-authoritative exception orchestration (Phase 2C)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from database import database
from services.entitlement_access import compute_canonical_entitlement_state

logger = logging.getLogger(__name__)

COL_GOVERNANCE = "commercial_entitlement_governance"

# Commercial governance states (exception truth)
STATE_ACTIVE = "ACTIVE"
STATE_GRACE_PERIOD = "GRACE_PERIOD"
STATE_BILLING_SUSPENDED = "BILLING_SUSPENDED"
STATE_PAYMENT_HOLD = "PAYMENT_HOLD"
STATE_SPONSORED_ACCESS = "SPONSORED_ACCESS"
STATE_RECOVERY_CONTINUITY = "RECOVERY_CONTINUITY"
STATE_RETENTION_EXTENSION = "RETENTION_EXTENSION"
STATE_WAIVED = "WAIVED"
STATE_RESTRICTED = "RESTRICTED"
STATE_TERMINATION_PENDING = "TERMINATION_PENDING"
STATE_ENTITLEMENT_DRIFT = "ENTITLEMENT_DRIFT"
STATE_MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"

ALL_GOVERNANCE_STATES = frozenset(
    {
        STATE_ACTIVE,
        STATE_GRACE_PERIOD,
        STATE_BILLING_SUSPENDED,
        STATE_PAYMENT_HOLD,
        STATE_SPONSORED_ACCESS,
        STATE_RECOVERY_CONTINUITY,
        STATE_RETENTION_EXTENSION,
        STATE_WAIVED,
        STATE_RESTRICTED,
        STATE_TERMINATION_PENDING,
        STATE_ENTITLEMENT_DRIFT,
        STATE_MANUAL_REVIEW_REQUIRED,
    }
)

# Exception categories A–F
EXCEPTION_ONBOARDING_WAIVER = "onboarding_waiver"
EXCEPTION_GRACE_EXTENSION = "grace_extension"
EXCEPTION_BILLING_SUSPENSION = "billing_suspension"
EXCEPTION_SPONSORED_ACCESS = "sponsored_access"
EXCEPTION_RECOVERY_COMPENSATION = "recovery_compensation"
EXCEPTION_RETENTION_CONTINUITY = "retention_continuity"
EXCEPTION_RESTRICTED = "restricted_entitlement"

ALL_EXCEPTION_TYPES = frozenset(
    {
        EXCEPTION_ONBOARDING_WAIVER,
        EXCEPTION_GRACE_EXTENSION,
        EXCEPTION_BILLING_SUSPENSION,
        EXCEPTION_SPONSORED_ACCESS,
        EXCEPTION_RECOVERY_COMPENSATION,
        EXCEPTION_RETENTION_CONTINUITY,
        EXCEPTION_RESTRICTED,
    }
)

# Access continuity policies (commercial ≠ compliance destruction)
ACCESS_FULL = "full_access"
ACCESS_OPERATIONAL_READ_ONLY = "operational_read_only"
ACCESS_RESTRICTED_UPLOADS = "restricted_uploads"
ACCESS_RESTRICTED_OPERATIONS = "restricted_operations"
ACCESS_SUSPENDED = "suspended"

ALL_ACCESS_POLICIES = frozenset(
    {
        ACCESS_FULL,
        ACCESS_OPERATIONAL_READ_ONLY,
        ACCESS_RESTRICTED_UPLOADS,
        ACCESS_RESTRICTED_OPERATIONS,
        ACCESS_SUSPENDED,
    }
)

GOVERNANCE_STATUS_ACTIVE = "active"
GOVERNANCE_STATUS_EXPIRED = "expired"
GOVERNANCE_STATUS_REVOKED = "revoked"
GOVERNANCE_STATUS_SUPERSEDED = "superseded"

_EXCEPTION_TO_DEFAULT_STATE: Dict[str, str] = {
    EXCEPTION_ONBOARDING_WAIVER: STATE_WAIVED,
    EXCEPTION_GRACE_EXTENSION: STATE_GRACE_PERIOD,
    EXCEPTION_BILLING_SUSPENSION: STATE_BILLING_SUSPENDED,
    EXCEPTION_SPONSORED_ACCESS: STATE_SPONSORED_ACCESS,
    EXCEPTION_RECOVERY_COMPENSATION: STATE_RECOVERY_CONTINUITY,
    EXCEPTION_RETENTION_CONTINUITY: STATE_RETENTION_EXTENSION,
    EXCEPTION_RESTRICTED: STATE_RESTRICTED,
}

_EXCEPTION_DEFAULT_ACCESS: Dict[str, str] = {
    EXCEPTION_ONBOARDING_WAIVER: ACCESS_FULL,
    EXCEPTION_GRACE_EXTENSION: ACCESS_FULL,
    EXCEPTION_BILLING_SUSPENSION: ACCESS_FULL,
    EXCEPTION_SPONSORED_ACCESS: ACCESS_FULL,
    EXCEPTION_RECOVERY_COMPENSATION: ACCESS_FULL,
    EXCEPTION_RETENTION_CONTINUITY: ACCESS_FULL,
    EXCEPTION_RESTRICTED: ACCESS_SUSPENDED,
}

_MAX_DURATION_DAYS: Dict[str, int] = {
    EXCEPTION_GRACE_EXTENSION: 30,
    EXCEPTION_BILLING_SUSPENSION: 90,
    EXCEPTION_SPONSORED_ACCESS: 90,
    EXCEPTION_RECOVERY_COMPENSATION: 30,
    EXCEPTION_RETENTION_CONTINUITY: 30,
    EXCEPTION_ONBOARDING_WAIVER: 30,
    EXCEPTION_RESTRICTED: 30,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raw = str(value).strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _format_date(dt: Optional[datetime]) -> str:
    if not dt:
        return "—"
    return dt.strftime("%Y-%m-%d")


async def get_active_governance(client_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    doc = await db[COL_GOVERNANCE].find_one(
        {"client_id": client_id, "status": GOVERNANCE_STATUS_ACTIVE},
        {"_id": 0},
    )
    return doc


async def load_client_billing_signals(client_id: str) -> Dict[str, Any]:
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        return {"found": False}
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})
    return {"found": True, "client": client, "billing": billing}


def classify_entitlement_state(signals: Dict[str, Any]) -> str:
    """Classify commercial governance need from platform + billing signals."""
    if not signals.get("found"):
        return STATE_MANUAL_REVIEW_REQUIRED
    client = signals["client"]
    billing = signals.get("billing") or {}
    governance = signals.get("active_governance")

    if governance:
        exp = _parse_iso(governance.get("entitlement_expiry_at"))
        if exp and exp <= _now():
            return STATE_ENTITLEMENT_DRIFT
        return governance.get("entitlement_state") or STATE_ACTIVE

    sub = (billing.get("subscription_status") or client.get("subscription_status") or "").upper()
    lc = (billing.get("billing_lifecycle_state") or client.get("billing_lifecycle_state") or "active").lower()

    if lc in ("grace_period", "past_due") or sub == "PAST_DUE":
        return STATE_GRACE_PERIOD
    if lc in ("expired", "limited") or sub == "UNPAID":
        return STATE_RESTRICTED
    if lc == "cancelled" or sub in ("CANCELED", "CANCELLED"):
        return STATE_TERMINATION_PENDING
    if sub in ("ACTIVE", "TRIALING") and lc in ("active", "renewing"):
        return STATE_ACTIVE
    if sub in ("INCOMPLETE", "PAUSED"):
        return STATE_PAYMENT_HOLD
    return STATE_ACTIVE


def derive_commercial_risk(signals: Dict[str, Any], governance_state: str) -> str:
    if governance_state in (STATE_ENTITLEMENT_DRIFT, STATE_MANUAL_REVIEW_REQUIRED):
        return "high"
    if governance_state in (STATE_SPONSORED_ACCESS, STATE_BILLING_SUSPENDED, STATE_TERMINATION_PENDING):
        return "medium"
    if signals.get("active_governance"):
        return "low"
    return "low"


def derive_continuity_strategy(
    governance_state: str,
    *,
    exception_type: Optional[str] = None,
    access_policy: Optional[str] = None,
) -> Dict[str, Any]:
    policy = access_policy or _EXCEPTION_DEFAULT_ACCESS.get(exception_type or "", ACCESS_FULL)
    preserve_compliance = governance_state != STATE_RESTRICTED and policy != ACCESS_SUSPENDED
    return {
        "governance_state": governance_state,
        "access_policy": policy,
        "preserve_compliance_records": preserve_compliance,
        "preserve_evidence_visibility": preserve_compliance,
        "billing_collection_paused": governance_state
        in (STATE_BILLING_SUSPENDED, STATE_PAYMENT_HOLD, STATE_SPONSORED_ACCESS),
        "full_operational_continuity": policy == ACCESS_FULL
        and governance_state
        in (
            STATE_GRACE_PERIOD,
            STATE_RETENTION_EXTENSION,
            STATE_RECOVERY_CONTINUITY,
            STATE_BILLING_SUSPENDED,
            STATE_SPONSORED_ACCESS,
        ),
    }


def derive_effective_access_reason(governance: Optional[Dict[str, Any]]) -> Optional[str]:
    if not governance:
        return None
    state = governance.get("entitlement_state")
    exp = _format_date(_parse_iso(governance.get("entitlement_expiry_at")))
    sponsor = (governance.get("sponsor_reference") or "").strip()
    if state == STATE_GRACE_PERIOD:
        return f"Grace period until {exp}"
    if state == STATE_BILLING_SUSPENDED:
        return "Billing suspended pending review"
    if state == STATE_SPONSORED_ACCESS:
        ref = f" ({sponsor})" if sponsor else ""
        return f"Sponsored access{ref} until {exp}"
    if state == STATE_RETENTION_EXTENSION:
        return f"Retention extension until {exp}"
    if state == STATE_RECOVERY_CONTINUITY:
        return "Recovery continuity arrangement"
    if state == STATE_WAIVED:
        return "Onboarding fee waiver in effect"
    if state == STATE_RESTRICTED:
        return "Account access restricted pending resolution"
    if state == STATE_PAYMENT_HOLD:
        return "Payment hold while billing is reviewed"
    return governance.get("entitlement_reason") or state


def derive_customer_access_state(signals: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sole bridge: commercial governance → canonical access band (ENABLED/GRACE/SUSPENDED/CANCELLED).
    Platform governance is authoritative for exceptions; Stripe lifecycle fills baseline.
    """
    client = signals.get("client") or {}
    billing = signals.get("billing") or {}
    governance = signals.get("active_governance")

    baseline = compute_canonical_entitlement_state(
        billing_lifecycle_state=(billing.get("billing_lifecycle_state") or client.get("billing_lifecycle_state")),
        subscription_status_upper=(billing.get("subscription_status") or client.get("subscription_status")),
    )

    if not governance:
        return {
            "canonical_entitlement_state": baseline,
            "governance_applied": False,
            "effective_access_reason": None,
            "access_policy": ACCESS_FULL,
        }

    g_state = governance.get("entitlement_state") or STATE_ACTIVE
    policy = governance.get("access_policy") or ACCESS_FULL

    if g_state in (STATE_ENTITLEMENT_DRIFT, STATE_MANUAL_REVIEW_REQUIRED):
        canon = baseline
    elif g_state == STATE_TERMINATION_PENDING:
        canon = "CANCELLED"
    elif g_state == STATE_RESTRICTED or policy == ACCESS_SUSPENDED:
        canon = "SUSPENDED"
    elif g_state == STATE_PAYMENT_HOLD:
        canon = "GRACE"
    elif policy == ACCESS_FULL and g_state in (
        STATE_GRACE_PERIOD,
        STATE_BILLING_SUSPENDED,
        STATE_SPONSORED_ACCESS,
        STATE_RETENTION_EXTENSION,
        STATE_RECOVERY_CONTINUITY,
        STATE_WAIVED,
        STATE_ACTIVE,
    ):
        # Operational continuity preserved — do not downgrade access band
        canon = "ENABLED" if baseline != "CANCELLED" else baseline
    else:
        canon = baseline

    return {
        "canonical_entitlement_state": canon,
        "governance_applied": True,
        "governance_state": g_state,
        "effective_access_reason": derive_effective_access_reason(governance),
        "access_policy": policy,
    }


def validate_entitlement_authority(
    *,
    exception_type: str,
    duration_days: Optional[int],
    sponsor_reference: Optional[str],
    entitlement_expiry_at: Optional[datetime],
) -> Tuple[bool, Optional[str]]:
    if exception_type not in ALL_EXCEPTION_TYPES:
        return False, f"Unknown exception type: {exception_type}"
    max_days = _MAX_DURATION_DAYS.get(exception_type)
    if max_days is not None:
        if duration_days is None or duration_days < 1:
            return False, "Duration is required for this exception type."
        if duration_days > max_days:
            return False, f"Maximum duration for {exception_type} is {max_days} days."
    if exception_type == EXCEPTION_SPONSORED_ACCESS:
        if not (sponsor_reference or "").strip():
            return False, "Sponsor reference is required for sponsored access."
        if not entitlement_expiry_at and not duration_days:
            return False, "Sponsored access requires expiry or review date."
    if entitlement_expiry_at and entitlement_expiry_at <= _now():
        return False, "Expiry must be in the future."
    return True, None


async def detect_entitlement_drift(client_id: str) -> Dict[str, Any]:
    """Platform governance vs billing/Stripe-derived canonical band."""
    signals = await load_client_billing_signals(client_id)
    if not signals.get("found"):
        return {"found": False, "drift_detected": False}
    signals["active_governance"] = await get_active_governance(client_id)
    access = derive_customer_access_state(signals)
    client = signals["client"]
    billing = signals.get("billing") or {}
    stored_canon = (billing.get("canonical_entitlement_state") or client.get("canonical_entitlement_state") or "").upper()
    derived = access.get("canonical_entitlement_state")
    drift = bool(stored_canon and derived and stored_canon != derived)
    governance = signals.get("active_governance")
    expired_governance = False
    if governance:
        exp = _parse_iso(governance.get("entitlement_expiry_at"))
        expired_governance = bool(exp and exp <= _now())
    return {
        "found": True,
        "drift_detected": drift or expired_governance,
        "stored_canonical_entitlement_state": stored_canon or None,
        "derived_canonical_entitlement_state": derived,
        "governance_expired": expired_governance,
        "active_governance_id": (governance or {}).get("governance_id"),
        "stripe_reconciliation_status": (governance or {}).get("stripe_reconciliation_status"),
    }


async def reconcile_stripe_vs_platform_state(client_id: str) -> Dict[str, Any]:
    """
    Lightweight v1 reconciliation — platform authoritative; Stripe downstream.
    Records plan only; does not mutate Stripe aggressively.
    """
    drift = await detect_entitlement_drift(client_id)
    if not drift.get("found"):
        return {"ok": False, "error": "CLIENT_NOT_FOUND"}
    governance = await get_active_governance(client_id)
    plan = "no_action"
    notes = "Platform governance authoritative; Stripe reconciliation deferred (v1)."
    if drift.get("governance_expired"):
        plan = "expire_governance"
        notes = "Active governance past expiry — run expiry enforcement."
    elif drift.get("drift_detected"):
        plan = "sync_canonical_entitlement_to_client"
        notes = "Update stored canonical_entitlement_state from derive_customer_access_state."
    if governance:
        db = database.get_db()
        await db[COL_GOVERNANCE].update_one(
            {"governance_id": governance["governance_id"]},
            {
                "$set": {
                    "stripe_reconciliation_status": "reconciled_lightweight",
                    "stripe_action_plan": plan,
                    "updated_at": _now().isoformat(),
                }
            },
        )
    return {
        "ok": True,
        "client_id": client_id,
        "drift": drift,
        "stripe_action_plan": plan,
        "notes": notes,
    }


async def build_commercial_entitlement_assessment(client_id: str) -> Dict[str, Any]:
    """Read-only assessment for admin Commercial Controls."""
    signals = await load_client_billing_signals(client_id)
    if not signals.get("found"):
        return {"found": False, "client_id": client_id}
    signals["active_governance"] = await get_active_governance(client_id)
    g_state = classify_entitlement_state(signals)
    access = derive_customer_access_state(signals)
    governance = signals.get("active_governance")
    drift = await detect_entitlement_drift(client_id)
    from services.stripe_mode_containment_service import assess_billing_stripe_mode_drift

    billing_mode_drift = await assess_billing_stripe_mode_drift(client_id)
    return {
        "found": True,
        "client_id": client_id,
        "classification": {
            "governance_state": g_state,
            "commercial_risk": derive_commercial_risk(signals, g_state),
        },
        "active_governance": governance,
        "has_active_exception": bool(governance),
        "access": access,
        "continuity": derive_continuity_strategy(
            g_state,
            exception_type=(governance or {}).get("exception_type"),
            access_policy=(governance or {}).get("access_policy"),
        ),
        "drift": drift,
        "billing_mode_drift": billing_mode_drift,
        "executable_actions": _derive_executable_actions(signals, governance),
        "completion_rule": (
            "Commercial exceptions require explicit authority, scope, duration, audit, and customer impact — "
            "not hidden billing mutations."
        ),
    }


def _derive_executable_actions(
    signals: Dict[str, Any], governance: Optional[Dict[str, Any]]
) -> List[str]:
    if governance:
        return ["resume_billing", "revoke_commercial_exception"]
    return [
        "grant_grace_period",
        "suspend_billing",
        "grant_sponsored_access",
        "retention_extension",
        "waive_onboarding_fee",
        "apply_recovery_compensation",
        "restrict_entitlement",
    ]


async def supersede_active_governance(
    client_id: str,
    *,
    actor_id: str,
    reason: str,
) -> Optional[str]:
    """Mark current active row superseded; returns previous governance_id."""
    db = database.get_db()
    active = await get_active_governance(client_id)
    if not active:
        return None
    now = _now()
    await db[COL_GOVERNANCE].update_one(
        {"governance_id": active["governance_id"]},
        {
            "$set": {
                "status": GOVERNANCE_STATUS_SUPERSEDED,
                "superseded_at": now.isoformat(),
                "superseded_by": actor_id,
                "supersede_reason": reason[:500],
            }
        },
    )
    return active["governance_id"]
