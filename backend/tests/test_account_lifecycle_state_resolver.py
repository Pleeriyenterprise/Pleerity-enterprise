"""Unit tests for Account Lifecycle State Resolver (ILP-1)."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import pytest

from services.account_lifecycle_state_resolver import (
    POLICY_VERSION,
    RESOLVER_VERSION,
    AccountLifecycleState,
    compare_resolution_with_existing_fields,
    resolve_account_lifecycle_state,
)

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
GRACE_END = datetime(2026, 6, 20, 0, 0, 0, tzinfo=timezone.utc)


def _resolve(client=None, billing=None, now=NOW):
    return resolve_account_lifecycle_state(client=client, billing=billing, now=now)


def _assert_meta(res, state: str):
    assert res.account_lifecycle_state == state
    assert res.policy_version == POLICY_VERSION
    assert res.resolver_version == RESOLVER_VERSION
    assert res.resolved_at
    assert isinstance(res.source_facts, dict)
    assert isinstance(res.warnings, list)


def test_active_paid_subscription():
    billing = {
        "client_id": "c-active",
        "subscription_status": "ACTIVE",
        "billing_lifecycle_state": "active",
        "canonical_entitlement_state": "ENABLED",
    }
    client = {"client_id": "c-active", "client_lifecycle_status": "ACTIVE", "onboarding_status": "PROVISIONED"}
    res = _resolve(client=client, billing=billing)
    _assert_meta(res, AccountLifecycleState.ACTIVE.value)
    assert res.confidence == "HIGH"


def test_trialing_subscription():
    billing = {
        "subscription_status": "TRIALING",
        "billing_lifecycle_state": "active",
    }
    res = _resolve(billing=billing)
    _assert_meta(res, AccountLifecycleState.TRIAL.value)


def test_trial_expired():
    billing = {"subscription_status": "INCOMPLETE_EXPIRED", "billing_lifecycle_state": "expired"}
    res = _resolve(billing=billing)
    _assert_meta(res, AccountLifecycleState.TRIAL_EXPIRED.value)


def test_payment_pending_incomplete():
    billing = {"subscription_status": "INCOMPLETE"}
    client = {"onboarding_status": "PROVISIONING"}
    res = _resolve(client=client, billing=billing)
    _assert_meta(res, AccountLifecycleState.PAYMENT_PENDING.value)


def test_payment_pending_onboarding_without_billing():
    client = {"client_lifecycle_status": "PENDING_SETUP", "onboarding_status": "INTAKE_PENDING"}
    res = _resolve(client=client)
    _assert_meta(res, AccountLifecycleState.PAYMENT_PENDING.value)


def test_payment_failed():
    billing = {
        "subscription_status": "PAST_DUE",
        "billing_lifecycle_state": "past_due",
        "grace_period_ends_at": None,
    }
    res = _resolve(billing=billing)
    _assert_meta(res, AccountLifecycleState.PAYMENT_FAILED.value)


def test_grace_period():
    billing = {
        "subscription_status": "PAST_DUE",
        "billing_lifecycle_state": "grace_period",
        "grace_period_ends_at": GRACE_END.isoformat(),
    }
    res = _resolve(billing=billing, now=NOW)
    _assert_meta(res, AccountLifecycleState.GRACE_PERIOD.value)


def test_cancellation_scheduled():
    billing = {
        "subscription_status": "ACTIVE",
        "billing_lifecycle_state": "cancel_at_period_end",
        "cancel_at_period_end": True,
        "current_period_end": PERIOD_END.isoformat(),
    }
    res = _resolve(billing=billing)
    _assert_meta(res, AccountLifecycleState.CANCELLATION_SCHEDULED.value)


def test_immediate_cancellation():
    billing = {
        "subscription_status": "CANCELED",
        "billing_lifecycle_state": "cancelled",
        "canonical_entitlement_state": "CANCELLED",
    }
    res = _resolve(billing=billing)
    _assert_meta(res, AccountLifecycleState.CANCELLED_IMMEDIATE.value)


def test_subscription_expired():
    billing = {
        "subscription_status": "UNPAID",
        "billing_lifecycle_state": "expired",
        "canonical_entitlement_state": "SUSPENDED",
    }
    res = _resolve(billing=billing)
    _assert_meta(res, AccountLifecycleState.SUBSCRIPTION_EXPIRED.value)


def test_read_only_retention_tier():
    billing = {
        "subscription_status": "UNPAID",
        "billing_lifecycle_state": "expired",
        "read_only_retention": True,
    }
    res = _resolve(billing=billing)
    _assert_meta(res, AccountLifecycleState.READ_ONLY.value)


def test_suspended_org():
    client = {"client_lifecycle_status": "SUSPENDED", "subscription_status": "ACTIVE"}
    billing = {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}
    res = _resolve(client=client, billing=billing)
    _assert_meta(res, AccountLifecycleState.SUSPENDED.value)
    assert "org_suspended_with_active_subscription" in res.warnings


def test_archived_account():
    client = {"is_deleted": True, "client_lifecycle_status": "ARCHIVED"}
    billing = {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"}
    res = _resolve(client=client, billing=billing)
    _assert_meta(res, AccountLifecycleState.ARCHIVED.value)


def test_deleted_account():
    client = {"client_id": "c-del", "purged_at": NOW.isoformat()}
    res = _resolve(client=client)
    _assert_meta(res, AccountLifecycleState.ACCOUNT_DELETED.value)


def test_legacy_abandoned():
    client = {"lifecycle_status": "abandoned", "onboarding_status": "INTAKE_PENDING"}
    res = _resolve(client=client)
    _assert_meta(res, AccountLifecycleState.LEGACY.value)


def test_unknown_unmapped():
    billing = {"subscription_status": "WEIRD_STATUS", "billing_lifecycle_state": "active"}
    res = _resolve(billing=billing)
    _assert_meta(res, AccountLifecycleState.UNKNOWN.value)
    assert res.confidence == "LOW"


def test_billing_exists_client_mirror_stale():
    billing = {
        "subscription_status": "CANCELED",
        "billing_lifecycle_state": "cancelled",
        "canonical_entitlement_state": "CANCELLED",
    }
    client = {
        "subscription_status": "ACTIVE",
        "billing_lifecycle_state": "active",
        "canonical_entitlement_state": "ENABLED",
    }
    res = _resolve(client=client, billing=billing)
    _assert_meta(res, AccountLifecycleState.CANCELLED_IMMEDIATE.value)
    assert any("mirror_drift" in w for w in res.warnings)


def test_client_mirror_active_billing_cancelled():
    billing = {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"}
    client = {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}
    res = _resolve(client=client, billing=billing)
    _assert_meta(res, AccountLifecycleState.CANCELLED_IMMEDIATE.value)


def test_stripe_active_org_archived():
    client = {"is_deleted": True, "client_lifecycle_status": "ARCHIVED"}
    billing = {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}
    res = _resolve(client=client, billing=billing)
    _assert_meta(res, AccountLifecycleState.ARCHIVED.value)
    assert "org_archived_with_active_subscription" in res.warnings


def test_stripe_cancelled_data_retained():
    billing = {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"}
    client = {"client_lifecycle_status": "ACTIVE", "onboarding_status": "PROVISIONED"}
    res = _resolve(client=client, billing=billing)
    _assert_meta(res, AccountLifecycleState.CANCELLED_IMMEDIATE.value)


def test_reactivated_account():
    billing = {
        "subscription_status": "ACTIVE",
        "billing_lifecycle_state": "active",
        "canonical_entitlement_state": "ENABLED",
        "cancel_at_period_end": False,
    }
    client = {"client_lifecycle_status": "ACTIVE", "onboarding_status": "PROVISIONED"}
    res = _resolve(client=client, billing=billing)
    _assert_meta(res, AccountLifecycleState.ACTIVE.value)


def test_pilot_entitlement_overlay():
    client = {"pilot_status": "paused", "client_lifecycle_status": "ACTIVE"}
    billing = {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}
    res = _resolve(client=client, billing=billing)
    _assert_meta(res, AccountLifecycleState.ACTIVE.value)
    assert any("pilot_overlay" in w for w in res.warnings)


def test_missing_billing_record():
    client = {"client_id": "c1", "subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}
    res = _resolve(client=client, billing=None)
    _assert_meta(res, AccountLifecycleState.ACTIVE.value)
    assert "missing_billing_record" in res.warnings


def test_multiple_contradictory_fields():
    billing = {
        "subscription_status": "ACTIVE",
        "billing_lifecycle_state": "cancelled",
        "canonical_entitlement_state": "CANCELLED",
        "entitlement_status": "DISABLED",
    }
    res = _resolve(billing=billing)
    _assert_meta(res, AccountLifecycleState.UNKNOWN.value)
    assert "contradictory" in res.reason or any("contradictory" in w for w in res.warnings)


def test_period_end_boundary_renewing():
    near_end = NOW + timedelta(days=3)
    billing = {
        "subscription_status": "ACTIVE",
        "current_period_end": near_end.isoformat(),
        "cancel_at_period_end": False,
    }
    res = _resolve(billing=billing, now=NOW)
    _assert_meta(res, AccountLifecycleState.ACTIVE.value)
    assert res.source_facts["computed_billing_lifecycle_state"] == "renewing"


def test_grace_expiry_boundary_limited():
    billing = {
        "subscription_status": "PAST_DUE",
        "grace_period_ends_at": (NOW - timedelta(hours=1)).isoformat(),
    }
    res = _resolve(billing=billing, now=NOW)
    _assert_meta(res, AccountLifecycleState.SUSPENDED.value)
    assert res.reason == "post_grace_payment_suspension"


def test_idempotent_repeated_resolution():
    billing = {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}
    client = {"client_lifecycle_status": "ACTIVE"}
    r1 = _resolve(client=client, billing=billing)
    r2 = _resolve(client=copy.deepcopy(client), billing=copy.deepcopy(billing))
    assert r1.account_lifecycle_state == r2.account_lifecycle_state
    assert r1.reason == r2.reason
    assert r1.source_facts == r2.source_facts
    assert r1.warnings == r2.warnings


def test_malformed_partial_data_no_exception():
    res = _resolve(client={"client_id": "x"}, billing={"subscription_status": None})
    assert res.account_lifecycle_state in (
        AccountLifecycleState.UNKNOWN.value,
        AccountLifecycleState.PAYMENT_PENDING.value,
        AccountLifecycleState.LEGACY.value,
    )


def test_empty_input_unknown():
    res = _resolve()
    _assert_meta(res, AccountLifecycleState.UNKNOWN.value)
    assert "empty_input" in res.warnings


def test_compare_drift_diagnostic():
    billing = {
        "subscription_status": "UNPAID",
        "billing_lifecycle_state": "expired",
        "canonical_entitlement_state": "ENABLED",
    }
    res = _resolve(billing=billing)
    drift = compare_resolution_with_existing_fields(res)
    assert drift["account_lifecycle_state"] == AccountLifecycleState.SUBSCRIPTION_EXPIRED.value
    assert drift["drift_flags"]


def test_legacy_pending_payment():
    client = {"lifecycle_status": "pending_payment"}
    res = _resolve(client=client)
    _assert_meta(res, AccountLifecycleState.PAYMENT_PENDING.value)


def test_post_grace_limited_maps_suspended():
    billing = {
        "subscription_status": "PAST_DUE",
        "billing_lifecycle_state": "limited",
        "grace_period_ends_at": (NOW - timedelta(days=1)).isoformat(),
    }
    res = _resolve(billing=billing, now=NOW)
    _assert_meta(res, AccountLifecycleState.SUSPENDED.value)
