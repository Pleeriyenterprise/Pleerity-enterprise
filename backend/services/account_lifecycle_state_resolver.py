"""
Account Lifecycle State Resolver (ILP-1).

Pure read-only resolver: maps existing billing, subscription, entitlement, organisation,
and client facts to the governed ``account_lifecycle_state`` enum.

Does not mutate data, enforce access, or wire into middleware/jobs/frontend.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from models import ClientLifecycleStatus, OnboardingStatus
from services.client_lifecycle_service import derive_client_lifecycle_status
from services.subscription_lifecycle_service import (
    BillingLifecycleState,
    compute_billing_lifecycle_state,
)

logger = logging.getLogger(__name__)

POLICY_VERSION = "account_lifecycle_policy_v1"
RESOLVER_VERSION = "ilp1_lifecycle_state_resolver_v1"

# Billing field names consumed (prefer ``client_billing`` over ``clients`` mirror).
BILLING_FACT_FIELDS = (
    "subscription_status",
    "billing_lifecycle_state",
    "canonical_entitlement_state",
    "entitlement_status",
    "cancel_at_period_end",
    "grace_period_ends_at",
    "current_period_end",
    "payment_failed_at",
    "read_only_retention",
    "account_lifecycle_read_only",
    "retention_tier",
)

CLIENT_FACT_FIELDS = (
    "client_id",
    "subscription_status",
    "billing_lifecycle_state",
    "canonical_entitlement_state",
    "entitlement_status",
    "client_lifecycle_status",
    "lifecycle_status",
    "onboarding_status",
    "is_deleted",
    "purged_at",
    "pilot_status",
    "pilot_program_type",
    "read_only_retention",
    "account_lifecycle_read_only",
    "retention_tier",
)


class AccountLifecycleState(str, Enum):
    ACTIVE = "ACTIVE"
    TRIAL = "TRIAL"
    TRIAL_EXPIRED = "TRIAL_EXPIRED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    GRACE_PERIOD = "GRACE_PERIOD"
    CANCELLATION_SCHEDULED = "CANCELLATION_SCHEDULED"
    CANCELLED_IMMEDIATE = "CANCELLED_IMMEDIATE"
    SUBSCRIPTION_EXPIRED = "SUBSCRIPTION_EXPIRED"
    READ_ONLY = "READ_ONLY"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"
    ACCOUNT_DELETED = "ACCOUNT_DELETED"
    UNKNOWN = "UNKNOWN"
    LEGACY = "LEGACY"


class ResolutionConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class LifecycleStateResolution:
    account_lifecycle_state: str
    source_facts: Dict[str, Any]
    reason: str
    confidence: str
    policy_version: str = POLICY_VERSION
    resolver_version: str = RESOLVER_VERSION
    resolved_at: str = ""
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _utc_now(now: Optional[datetime] = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def _upper(value: Any) -> str:
    return str(value or "").strip().upper()


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _utc_now(value)
    if isinstance(value, str) and value.strip():
        try:
            return _utc_now(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            return None
    return None


def _pick(
    billing: Optional[Dict[str, Any]],
    client: Optional[Dict[str, Any]],
    key: str,
    *,
    prefer_billing: bool = True,
) -> Any:
    if prefer_billing:
        if billing and billing.get(key) is not None:
            return billing.get(key)
        if client and client.get(key) is not None:
            return client.get(key)
    else:
        if client and client.get(key) is not None:
            return client.get(key)
        if billing and billing.get(key) is not None:
            return billing.get(key)
    return None


def _extract_source_facts(
    client: Optional[Dict[str, Any]],
    billing: Optional[Dict[str, Any]],
    *,
    computed_billing_lifecycle: Optional[str] = None,
) -> Dict[str, Any]:
    facts: Dict[str, Any] = {
        "client_id": _pick(billing, client, "client_id"),
        "has_client_record": client is not None,
        "has_billing_record": billing is not None,
    }
    for key in BILLING_FACT_FIELDS:
        facts[f"billing.{key}"] = billing.get(key) if billing else None
        facts[f"client.{key}"] = client.get(key) if client else None
        facts[key] = _pick(billing, client, key)
    for key in ("client_lifecycle_status", "lifecycle_status", "onboarding_status", "is_deleted", "purged_at", "pilot_status"):
        facts[key] = _pick(billing, client, key, prefer_billing=False) if key in CLIENT_FACT_FIELDS else None
        if client:
            facts[f"client.{key}"] = client.get(key)
    if computed_billing_lifecycle is not None:
        facts["computed_billing_lifecycle_state"] = computed_billing_lifecycle
    derived_org = derive_client_lifecycle_status(client or {})
    facts["derived_client_lifecycle_status"] = derived_org
    return facts


def _is_read_only_tier(client: Optional[Dict[str, Any]], billing: Optional[Dict[str, Any]]) -> bool:
    for doc in (billing, client):
        if not doc:
            continue
        if doc.get("read_only_retention") is True or doc.get("account_lifecycle_read_only") is True:
            return True
        tier = _upper(doc.get("retention_tier"))
        if tier in ("READ_ONLY", "READ_ONLY_WINDOW"):
            return True
    return False


def _collect_fact_warnings(
    client: Optional[Dict[str, Any]],
    billing: Optional[Dict[str, Any]],
    subscription_status: str,
    billing_lifecycle: str,
) -> List[str]:
    warnings: List[str] = []
    if client and not billing:
        warnings.append("missing_billing_record")
    if billing and not client:
        warnings.append("missing_client_record")
    if client and billing:
        for fld in ("subscription_status", "billing_lifecycle_state", "canonical_entitlement_state", "entitlement_status"):
            bc = _upper(billing.get(fld))
            cc = _upper(client.get(fld))
            if bc and cc and bc != cc:
                warnings.append(f"mirror_drift:{fld}:billing={bc}:client={cc}")
    if client:
        pilot = _lower(client.get("pilot_status"))
        if pilot and pilot not in ("", "none", "active", "extended", "comped", "converted_to_paid"):
            warnings.append(f"pilot_overlay:{pilot}")
    org = _upper(client.get("client_lifecycle_status") if client else "")
    if org == ClientLifecycleStatus.ARCHIVED.value and subscription_status in ("ACTIVE", "TRIALING"):
        warnings.append("org_archived_with_active_subscription")
    if org == ClientLifecycleStatus.SUSPENDED.value and subscription_status in ("ACTIVE", "TRIALING"):
        warnings.append("org_suspended_with_active_subscription")
    if subscription_status in ("ACTIVE", "TRIALING") and billing_lifecycle in (
        BillingLifecycleState.CANCELLED.value,
        BillingLifecycleState.EXPIRED.value,
    ):
        warnings.append("active_subscription_status_with_terminal_billing_lifecycle")
    return warnings


def _has_hard_billing_contradiction(subscription_status: str, billing_lifecycle: str) -> bool:
    """Stripe still claims access while stored billing lifecycle is terminal."""
    if subscription_status in ("ACTIVE", "TRIALING") and billing_lifecycle in (
        BillingLifecycleState.CANCELLED.value,
        BillingLifecycleState.EXPIRED.value,
        BillingLifecycleState.LIMITED.value,
    ):
        return True
    if subscription_status in ("CANCELED", "CANCELLED", "UNPAID") and billing_lifecycle in (
        BillingLifecycleState.ACTIVE.value,
        BillingLifecycleState.RENEWING.value,
        BillingLifecycleState.CANCEL_AT_PERIOD_END.value,
    ):
        return True
    return False


def resolve_account_lifecycle_state(
    *,
    client: Optional[Dict[str, Any]] = None,
    billing: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> LifecycleStateResolution:
    """
    Deterministic lifecycle state resolution.

    Precedence (highest first):
      1. ACCOUNT_DELETED — ``purged_at`` set on client
      2. ARCHIVED — soft delete / archived org lifecycle / legacy archived funnel
      3. SUSPENDED — explicit org ``client_lifecycle_status`` SUSPENDED (ops)
      4. LEGACY / PAYMENT_PENDING — legacy funnel without standard billing
      5. Billing-derived states (prefer ``client_billing`` facts)
      6. UNKNOWN — inconsistent or unmapped facts
    """
    now = _utc_now(now)
    warnings: List[str] = []

    subscription_status = _upper(_pick(billing, client, "subscription_status"))
    stored_billing_lc = _lower(_pick(billing, client, "billing_lifecycle_state"))
    cancel_at_period_end = bool(_pick(billing, client, "cancel_at_period_end"))
    grace_end = _parse_dt(_pick(billing, client, "grace_period_ends_at"))
    period_end = _parse_dt(_pick(billing, client, "current_period_end"))

    computed_billing_lc = compute_billing_lifecycle_state(
        subscription_status_upper=subscription_status,
        cancel_at_period_end=cancel_at_period_end,
        grace_period_ends_at=grace_end,
        current_period_end=period_end,
        now=now,
    )
    billing_lifecycle = stored_billing_lc or computed_billing_lc
    if stored_billing_lc and stored_billing_lc != computed_billing_lc:
        warnings.append(
            f"billing_lifecycle_recomputed:{stored_billing_lc}!={computed_billing_lc}"
        )

    source_facts = _extract_source_facts(client, billing, computed_billing_lifecycle=computed_billing_lc)
    warnings.extend(_collect_fact_warnings(client, billing, subscription_status, billing_lifecycle))

    purged_at = _pick(billing, client, "purged_at", prefer_billing=False)
    if client and purged_at is not None:
        return LifecycleStateResolution(
            account_lifecycle_state=AccountLifecycleState.ACCOUNT_DELETED.value,
            source_facts=source_facts,
            reason="client_purged_at_set",
            confidence=ResolutionConfidence.HIGH.value,
            resolved_at=now.isoformat(),
            warnings=warnings,
        )

    is_deleted = bool(client.get("is_deleted")) if client else False
    org_status = _upper(client.get("client_lifecycle_status") if client else "")
    legacy_lc = _lower(client.get("lifecycle_status") if client else "")
    onboarding = _upper(client.get("onboarding_status") if client else "")

    if is_deleted or org_status in (
        ClientLifecycleStatus.ARCHIVED.value,
        ClientLifecycleStatus.PURGE_ELIGIBLE.value,
    ) or legacy_lc == "archived":
        return LifecycleStateResolution(
            account_lifecycle_state=AccountLifecycleState.ARCHIVED.value,
            source_facts=source_facts,
            reason="organisation_archived_or_soft_deleted",
            confidence=ResolutionConfidence.HIGH.value,
            resolved_at=now.isoformat(),
            warnings=warnings,
        )

    if org_status == ClientLifecycleStatus.SUSPENDED.value:
        return LifecycleStateResolution(
            account_lifecycle_state=AccountLifecycleState.SUSPENDED.value,
            source_facts=source_facts,
            reason="organisation_suspended",
            confidence=ResolutionConfidence.HIGH.value,
            resolved_at=now.isoformat(),
            warnings=warnings,
        )

    if legacy_lc == "pending_payment":
        return LifecycleStateResolution(
            account_lifecycle_state=AccountLifecycleState.PAYMENT_PENDING.value,
            source_facts=source_facts,
            reason="legacy_lifecycle_pending_payment",
            confidence=ResolutionConfidence.MEDIUM.value,
            resolved_at=now.isoformat(),
            warnings=warnings,
        )

    if legacy_lc == "abandoned" and onboarding != OnboardingStatus.PROVISIONED.value:
        return LifecycleStateResolution(
            account_lifecycle_state=AccountLifecycleState.LEGACY.value,
            source_facts=source_facts,
            reason="legacy_lifecycle_abandoned",
            confidence=ResolutionConfidence.MEDIUM.value,
            resolved_at=now.isoformat(),
            warnings=warnings,
        )

    if not billing and not subscription_status:
        if onboarding in (
            OnboardingStatus.INTAKE_PENDING.value,
            OnboardingStatus.PROVISIONING.value,
            ClientLifecycleStatus.PENDING_SETUP.value,
            ClientLifecycleStatus.LEAD.value,
        ) or org_status in (ClientLifecycleStatus.LEAD.value, ClientLifecycleStatus.PENDING_SETUP.value):
            return LifecycleStateResolution(
                account_lifecycle_state=AccountLifecycleState.PAYMENT_PENDING.value,
                source_facts=source_facts,
                reason="onboarding_without_billing",
                confidence=ResolutionConfidence.MEDIUM.value,
                resolved_at=now.isoformat(),
                warnings=warnings,
            )
        if legacy_lc or (client and client.get("pilot_status")):
            return LifecycleStateResolution(
                account_lifecycle_state=AccountLifecycleState.LEGACY.value,
                source_facts=source_facts,
                reason="legacy_or_pilot_without_billing",
                confidence=ResolutionConfidence.LOW.value,
                resolved_at=now.isoformat(),
                warnings=warnings + ["no_billing_or_subscription_status"],
            )

    if subscription_status == "INCOMPLETE":
        return LifecycleStateResolution(
            account_lifecycle_state=AccountLifecycleState.PAYMENT_PENDING.value,
            source_facts=source_facts,
            reason="stripe_incomplete_checkout",
            confidence=ResolutionConfidence.HIGH.value,
            resolved_at=now.isoformat(),
            warnings=warnings,
        )

    if _is_read_only_tier(client, billing):
        return LifecycleStateResolution(
            account_lifecycle_state=AccountLifecycleState.READ_ONLY.value,
            source_facts=source_facts,
            reason="read_only_retention_tier",
            confidence=ResolutionConfidence.HIGH.value,
            resolved_at=now.isoformat(),
            warnings=warnings,
        )

    if subscription_status == "TRIALING" and billing_lifecycle in (
        BillingLifecycleState.ACTIVE.value,
        BillingLifecycleState.RENEWING.value,
        BillingLifecycleState.CANCEL_AT_PERIOD_END.value,
    ):
        return LifecycleStateResolution(
            account_lifecycle_state=AccountLifecycleState.TRIAL.value,
            source_facts=source_facts,
            reason="stripe_trialing",
            confidence=ResolutionConfidence.HIGH.value,
            resolved_at=now.isoformat(),
            warnings=warnings,
        )

    if subscription_status in ("INCOMPLETE_EXPIRED",) or (
        subscription_status == "TRIALING"
        and billing_lifecycle == BillingLifecycleState.EXPIRED.value
    ):
        return LifecycleStateResolution(
            account_lifecycle_state=AccountLifecycleState.TRIAL_EXPIRED.value,
            source_facts=source_facts,
            reason="trial_expired",
            confidence=ResolutionConfidence.HIGH.value,
            resolved_at=now.isoformat(),
            warnings=warnings,
        )

    if billing_lifecycle == BillingLifecycleState.CANCEL_AT_PERIOD_END.value and subscription_status in (
        "ACTIVE",
        "TRIALING",
    ):
        return LifecycleStateResolution(
            account_lifecycle_state=AccountLifecycleState.CANCELLATION_SCHEDULED.value,
            source_facts=source_facts,
            reason="cancel_at_period_end_with_access",
            confidence=ResolutionConfidence.HIGH.value,
            resolved_at=now.isoformat(),
            warnings=warnings,
        )

    if billing_lifecycle == BillingLifecycleState.GRACE_PERIOD.value or (
        subscription_status == "PAST_DUE" and grace_end and now < grace_end
    ):
        return LifecycleStateResolution(
            account_lifecycle_state=AccountLifecycleState.GRACE_PERIOD.value,
            source_facts=source_facts,
            reason="grace_period_active",
            confidence=ResolutionConfidence.HIGH.value,
            resolved_at=now.isoformat(),
            warnings=warnings,
        )

    if billing_lifecycle == BillingLifecycleState.PAST_DUE.value or (
        subscription_status == "PAST_DUE" and grace_end is None
    ):
        return LifecycleStateResolution(
            account_lifecycle_state=AccountLifecycleState.PAYMENT_FAILED.value,
            source_facts=source_facts,
            reason="payment_failed_pre_grace",
            confidence=ResolutionConfidence.HIGH.value,
            resolved_at=now.isoformat(),
            warnings=warnings,
        )

    if billing_lifecycle == BillingLifecycleState.LIMITED.value:
        if _has_hard_billing_contradiction(subscription_status, billing_lifecycle):
            return LifecycleStateResolution(
                account_lifecycle_state=AccountLifecycleState.UNKNOWN.value,
                source_facts=source_facts,
                reason="contradictory_billing_facts",
                confidence=ResolutionConfidence.LOW.value,
                resolved_at=now.isoformat(),
                warnings=warnings + ["contradictory_subscription_and_billing_lifecycle"],
            )
        return LifecycleStateResolution(
            account_lifecycle_state=AccountLifecycleState.SUSPENDED.value,
            source_facts=source_facts,
            reason="post_grace_payment_suspension",
            confidence=ResolutionConfidence.HIGH.value,
            resolved_at=now.isoformat(),
            warnings=warnings,
        )

    if billing_lifecycle == BillingLifecycleState.CANCELLED.value or subscription_status in (
        "CANCELED",
        "CANCELLED",
    ):
        if _has_hard_billing_contradiction(subscription_status, billing_lifecycle):
            return LifecycleStateResolution(
                account_lifecycle_state=AccountLifecycleState.UNKNOWN.value,
                source_facts=source_facts,
                reason="contradictory_billing_facts",
                confidence=ResolutionConfidence.LOW.value,
                resolved_at=now.isoformat(),
                warnings=warnings + ["contradictory_subscription_and_billing_lifecycle"],
            )
        return LifecycleStateResolution(
            account_lifecycle_state=AccountLifecycleState.CANCELLED_IMMEDIATE.value,
            source_facts=source_facts,
            reason="subscription_cancelled",
            confidence=ResolutionConfidence.HIGH.value,
            resolved_at=now.isoformat(),
            warnings=warnings,
        )

    if billing_lifecycle == BillingLifecycleState.EXPIRED.value or subscription_status == "UNPAID":
        if _has_hard_billing_contradiction(subscription_status, billing_lifecycle):
            return LifecycleStateResolution(
                account_lifecycle_state=AccountLifecycleState.UNKNOWN.value,
                source_facts=source_facts,
                reason="contradictory_billing_facts",
                confidence=ResolutionConfidence.LOW.value,
                resolved_at=now.isoformat(),
                warnings=warnings + ["contradictory_subscription_and_billing_lifecycle"],
            )
        state = AccountLifecycleState.READ_ONLY.value if _is_read_only_tier(client, billing) else AccountLifecycleState.SUBSCRIPTION_EXPIRED.value
        return LifecycleStateResolution(
            account_lifecycle_state=state,
            source_facts=source_facts,
            reason="subscription_expired_unpaid",
            confidence=ResolutionConfidence.HIGH.value,
            resolved_at=now.isoformat(),
            warnings=warnings,
        )

    if subscription_status in ("ACTIVE", "TRIALING") and billing_lifecycle in (
        BillingLifecycleState.ACTIVE.value,
        BillingLifecycleState.RENEWING.value,
    ):
        state = AccountLifecycleState.TRIAL.value if subscription_status == "TRIALING" else AccountLifecycleState.ACTIVE.value
        return LifecycleStateResolution(
            account_lifecycle_state=state,
            source_facts=source_facts,
            reason="active_subscription",
            confidence=ResolutionConfidence.HIGH.value,
            resolved_at=now.isoformat(),
            warnings=warnings,
        )

    if subscription_status in ("PAUSED",):
        return LifecycleStateResolution(
            account_lifecycle_state=AccountLifecycleState.SUSPENDED.value,
            source_facts=source_facts,
            reason="stripe_paused",
            confidence=ResolutionConfidence.MEDIUM.value,
            resolved_at=now.isoformat(),
            warnings=warnings,
        )

    if not client and not billing:
        return LifecycleStateResolution(
            account_lifecycle_state=AccountLifecycleState.UNKNOWN.value,
            source_facts=source_facts,
            reason="no_client_or_billing_facts",
            confidence=ResolutionConfidence.LOW.value,
            resolved_at=now.isoformat(),
            warnings=warnings + ["empty_input"],
        )

    return LifecycleStateResolution(
        account_lifecycle_state=AccountLifecycleState.UNKNOWN.value,
        source_facts=source_facts,
        reason="unmapped_fact_combination",
        confidence=ResolutionConfidence.LOW.value,
        resolved_at=now.isoformat(),
        warnings=warnings + [f"subscription={subscription_status}", f"billing_lifecycle={billing_lifecycle}"],
    )


async def load_client_and_billing(db, client_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Read-only fact load from Mongo."""
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})
    return client, billing


async def resolve_for_client_id(db, client_id: str, *, now: Optional[datetime] = None) -> LifecycleStateResolution:
    client, billing = await load_client_and_billing(db, client_id)
    if client and not billing:
        pass
    if billing and not client:
        pass
    resolution = resolve_account_lifecycle_state(client=client, billing=billing, now=now)
    if client_id and resolution.source_facts.get("client_id") is None:
        resolution.source_facts["client_id"] = client_id
    return resolution


def compare_resolution_with_existing_fields(resolution: LifecycleStateResolution) -> Dict[str, Any]:
    """
    Read-only drift comparison against stored bands (does not mutate).
    """
    facts = resolution.source_facts
    canonical = _upper(facts.get("canonical_entitlement_state"))
    billing_lc = _lower(facts.get("billing_lifecycle_state") or facts.get("computed_billing_lifecycle_state"))
    entitlement = _upper(facts.get("entitlement_status"))
    resolved = resolution.account_lifecycle_state

    implied_canonical = {
        AccountLifecycleState.ACTIVE.value: "ENABLED",
        AccountLifecycleState.TRIAL.value: "ENABLED",
        AccountLifecycleState.CANCELLATION_SCHEDULED.value: "ENABLED",
        AccountLifecycleState.PAYMENT_FAILED.value: "ENABLED",
        AccountLifecycleState.GRACE_PERIOD.value: "GRACE",
        AccountLifecycleState.CANCELLED_IMMEDIATE.value: "CANCELLED",
        AccountLifecycleState.SUBSCRIPTION_EXPIRED.value: "SUSPENDED",
        AccountLifecycleState.TRIAL_EXPIRED.value: "SUSPENDED",
        AccountLifecycleState.SUSPENDED.value: "SUSPENDED",
        AccountLifecycleState.READ_ONLY.value: "SUSPENDED",
    }.get(resolved)

    drift: List[str] = []
    if canonical and implied_canonical and canonical != implied_canonical:
        drift.append(f"canonical_mismatch:stored={canonical}:implied={implied_canonical}:resolved={resolved}")
    if billing_lc:
        billing_map = {
            AccountLifecycleState.ACTIVE.value: {BillingLifecycleState.ACTIVE.value, BillingLifecycleState.RENEWING.value},
            AccountLifecycleState.TRIAL.value: {BillingLifecycleState.ACTIVE.value, BillingLifecycleState.RENEWING.value},
            AccountLifecycleState.CANCELLATION_SCHEDULED.value: {BillingLifecycleState.CANCEL_AT_PERIOD_END.value},
            AccountLifecycleState.PAYMENT_FAILED.value: {BillingLifecycleState.PAST_DUE.value},
            AccountLifecycleState.GRACE_PERIOD.value: {BillingLifecycleState.GRACE_PERIOD.value},
            AccountLifecycleState.CANCELLED_IMMEDIATE.value: {BillingLifecycleState.CANCELLED.value},
            AccountLifecycleState.SUBSCRIPTION_EXPIRED.value: {BillingLifecycleState.EXPIRED.value, BillingLifecycleState.LIMITED.value},
            AccountLifecycleState.SUSPENDED.value: {BillingLifecycleState.LIMITED.value},
        }
        expected = billing_map.get(resolved)
        if expected and billing_lc not in expected:
            drift.append(f"billing_lifecycle_mismatch:stored={billing_lc}:resolved={resolved}")

    return {
        "account_lifecycle_state": resolved,
        "canonical_entitlement_state": canonical or None,
        "billing_lifecycle_state": billing_lc or None,
        "entitlement_status": entitlement or None,
        "implied_canonical_from_resolved": implied_canonical,
        "drift_flags": drift,
        "warnings": list(resolution.warnings),
    }
