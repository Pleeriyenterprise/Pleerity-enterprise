"""
P0-RUNTIME-CONTRACT-STATE-MATRIX-VALIDATION-01

Permanent regression tests: lifecycle state matrix, mirror drift, transitions,
and Runtime Contract authority convergence. Pure resolver/contract assembly — no DB.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

import pytest

from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import (
    _LIFECYCLE_COLUMNS,
    build_runtime_contract,
    resolve_runtime_contract_for_client,
    runtime_contract_to_dict,
)
from services.account_lifecycle_state_resolver import (
    AccountLifecycleState,
    resolve_account_lifecycle_state,
)

NOW = datetime(2026, 7, 7, 12, 0, 0, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
GRACE_END = datetime(2026, 7, 20, 0, 0, 0, tzinfo=timezone.utc)

PLAN_FEATURES = {
    "reports_pdf": True,
    "scheduled_reports": True,
    "maintenance_workflows": True,
    "rent_operations": True,
    "predictive_maintenance": True,
}


def _contract(client=None, billing=None, **kwargs):
    return build_runtime_contract(
        client={**(client or {}), "billing_plan": (client or {}).get("billing_plan", "PLAN_3_PRO")},
        billing=billing,
        now=NOW,
        **kwargs,
    )


def _payload(client=None, billing=None):
    return runtime_contract_to_dict(_contract(client, billing))


def _allowed(contract, cap_id: str, action: str) -> bool:
    return CapabilityEnforcementService(db=None).evaluate_from_contract(contract, cap_id, action).allowed


# Canonical billing-authoritative fixtures per lifecycle band.
STATE_MATRIX: Dict[str, Dict[str, Any]] = {
    "ACTIVE": {
        "client": {"client_id": "mx", "onboarding_status": "PROVISIONED", "client_lifecycle_status": "ACTIVE"},
        "billing": {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
        "lifecycle": "ACTIVE",
        "portal_mode": "FULL_ACCESS",
        "read_caps": ("CAP_PROP_VIEW", "CAP_PROFILE_VIEW", "CAP_DASHBOARD_VIEW"),
        "write_caps": ("CAP_PROP_CREATE", "CAP_PROFILE_EDIT"),
        "deny_write": (),
        "recovery_eligible": False,
        "banner_heading_nonempty": False,
    },
    "TRIAL": {
        "client": {"client_id": "mx", "onboarding_status": "PROVISIONED"},
        "billing": {"subscription_status": "TRIALING", "billing_lifecycle_state": "active"},
        "lifecycle": "TRIAL",
        "portal_mode": "FULL_ACCESS",
        "read_caps": ("CAP_PROP_VIEW", "CAP_DASHBOARD_VIEW"),
        "write_caps": ("CAP_PROP_CREATE",),
        "deny_write": (),
        "recovery_eligible": False,
        "banner_heading_nonempty": False,
    },
    "ONBOARDING": {
        "client": {"client_id": "mx", "onboarding_status": "INTAKE_PENDING", "client_lifecycle_status": "LEAD"},
        "billing": None,
        "lifecycle": "PAYMENT_PENDING",
        "portal_mode": "PAYMENT_REQUIRED",
        "read_caps": ("CAP_PROFILE_VIEW",),
        "write_caps": (),
        "deny_write": ("CAP_PROP_CREATE",),
        "recovery_eligible": True,
        "banner_heading_nonempty": True,
    },
    "GRACE_PERIOD": {
        "client": {"client_id": "mx"},
        "billing": {
            "subscription_status": "PAST_DUE",
            "billing_lifecycle_state": "grace_period",
            "grace_period_ends_at": GRACE_END.isoformat(),
        },
        "lifecycle": "GRACE_PERIOD",
        "portal_mode": "GRACE",
        "read_caps": ("CAP_PROP_VIEW", "CAP_PROFILE_VIEW"),
        "write_caps": (),
        "deny_write": (),
        "recovery_eligible": True,
        "banner_heading_nonempty": True,
    },
    "CANCELLATION_SCHEDULED": {
        "client": {"client_id": "mx"},
        "billing": {
            "subscription_status": "ACTIVE",
            "billing_lifecycle_state": "cancel_at_period_end",
            "cancel_at_period_end": True,
            "current_period_end": PERIOD_END.isoformat(),
        },
        "lifecycle": "CANCELLATION_SCHEDULED",
        "portal_mode": "FULL_ACCESS",
        "read_caps": ("CAP_PROP_VIEW",),
        "write_caps": ("CAP_PROP_CREATE",),
        "deny_write": (),
        "recovery_eligible": False,
        "banner_heading_nonempty": False,
    },
    "SUBSCRIPTION_EXPIRED": {
        "client": {"client_id": "mx"},
        "billing": {"subscription_status": "UNPAID", "billing_lifecycle_state": "expired"},
        "lifecycle": "SUBSCRIPTION_EXPIRED",
        "portal_mode": "BILLING_RECOVERY",
        "read_caps": ("CAP_BILLING_VIEW", "CAP_PROP_VIEW"),
        "write_caps": (),
        "deny_write": ("CAP_PROP_CREATE", "CAP_OPS_MAINTENANCE"),
        "recovery_eligible": True,
        "banner_heading_nonempty": True,
    },
    "READ_ONLY": {
        "client": {"client_id": "mx"},
        "billing": {
            "subscription_status": "UNPAID",
            "billing_lifecycle_state": "expired",
            "read_only_retention": True,
        },
        "lifecycle": "READ_ONLY",
        "portal_mode": "READ_ONLY",
        "read_caps": ("CAP_PROP_VIEW", "CAP_BILLING_VIEW"),
        "write_caps": (),
        "deny_write": ("CAP_PROP_CREATE", "CAP_PROFILE_EDIT"),
        "recovery_eligible": True,
        "banner_heading_nonempty": True,
    },
    "CANCELLED_IMMEDIATE": {
        "client": {"client_id": "mx"},
        "billing": {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"},
        "lifecycle": "CANCELLED_IMMEDIATE",
        "portal_mode": "BILLING_RECOVERY",
        "read_caps": ("CAP_BILLING_VIEW",),
        "write_caps": (),
        "deny_write": ("CAP_OPS_MAINTENANCE",),
        "recovery_eligible": True,
        "banner_heading_nonempty": True,
    },
    "SUSPENDED": {
        "client": {"client_id": "mx", "client_lifecycle_status": "SUSPENDED"},
        "billing": {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
        "lifecycle": "SUSPENDED",
        "portal_mode": "SUSPENDED",
        "read_caps": (),
        "write_caps": (),
        "deny_write": ("CAP_PROFILE_EDIT", "CAP_PROP_VIEW", "CAP_DASHBOARD_VIEW"),
        "recovery_eligible": True,
        "banner_heading_nonempty": True,
    },
    "ARCHIVED": {
        "client": {"client_id": "mx", "is_deleted": True, "client_lifecycle_status": "ARCHIVED"},
        "billing": {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
        "lifecycle": "ARCHIVED",
        "portal_mode": "ARCHIVED",
        "read_caps": (),
        "write_caps": (),
        "deny_write": ("CAP_PROP_VIEW", "CAP_BILLING_VIEW"),
        "recovery_eligible": False,
        "banner_heading_nonempty": True,
    },
    "ACCOUNT_DELETED": {
        "client": {"client_id": "mx", "purged_at": NOW.isoformat()},
        "billing": None,
        "lifecycle": "ACCOUNT_DELETED",
        "portal_mode": "ACCOUNT_DELETED",
        "read_caps": (),
        "write_caps": (),
        "deny_write": ("CAP_AUTH_LOGIN", "CAP_PROP_VIEW"),
        "recovery_eligible": False,
        "banner_heading_nonempty": True,
    },
    "UNKNOWN": {
        "client": {"client_id": "mx"},
        "billing": {"subscription_status": "WEIRD_STATUS", "billing_lifecycle_state": "active"},
        "lifecycle": "UNKNOWN",
        "portal_mode": "BILLING_RECOVERY",
        "read_caps": ("CAP_PROFILE_VIEW",),
        "write_caps": (),
        "deny_write": ("CAP_PROP_CREATE",),
        "recovery_eligible": False,
        "banner_heading_nonempty": False,
    },
}

MIRROR_DRIFT_MATRIX: Dict[str, Dict[str, Any]] = {
    "active_sub_pending_payment_mirror": {
        "client": {
            "client_id": "drift",
            "subscription_status": "ACTIVE",
            "onboarding_status": "PROVISIONED",
            "client_lifecycle_status": "ACTIVE",
            "lifecycle_status": "pending_payment",
        },
        "billing": None,
        "expected_lifecycle": "ACTIVE",
        "expected_portal": "FULL_ACCESS",
    },
    "active_sub_cancelled_mirror": {
        "client": {
            "client_id": "drift",
            "subscription_status": "ACTIVE",
            "onboarding_status": "PROVISIONED",
            "client_lifecycle_status": "ACTIVE",
            "lifecycle_status": "cancelled",
        },
        "billing": None,
        "expected_lifecycle": "ACTIVE",
        "expected_portal": "FULL_ACCESS",
    },
    "active_sub_expired_mirror": {
        "client": {
            "client_id": "drift",
            "subscription_status": "ACTIVE",
            "onboarding_status": "PROVISIONED",
            "lifecycle_status": "expired",
        },
        "billing": None,
        "expected_lifecycle": "ACTIVE",
        "expected_portal": "FULL_ACCESS",
    },
    "active_sub_unknown_mirror": {
        "client": {
            "client_id": "drift",
            "subscription_status": "ACTIVE",
            "onboarding_status": "PROVISIONED",
            "lifecycle_status": "unknown",
        },
        "billing": None,
        "expected_lifecycle": "ACTIVE",
        "expected_portal": "FULL_ACCESS",
    },
    "active_sub_null_mirror": {
        "client": {
            "client_id": "drift",
            "subscription_status": "ACTIVE",
            "onboarding_status": "PROVISIONED",
            "lifecycle_status": None,
        },
        "billing": None,
        "expected_lifecycle": "ACTIVE",
        "expected_portal": "FULL_ACCESS",
    },
    "trial_sub_active_org_mirror": {
        "client": {"client_id": "drift", "client_lifecycle_status": "ACTIVE", "onboarding_status": "PROVISIONED"},
        "billing": {"subscription_status": "TRIALING", "billing_lifecycle_state": "active"},
        "expected_lifecycle": "TRIAL",
        "expected_portal": "FULL_ACCESS",
    },
    "grace_billing_active_client_mirror": {
        "client": {"client_id": "drift", "client_lifecycle_status": "ACTIVE", "subscription_status": "ACTIVE"},
        "billing": {
            "subscription_status": "PAST_DUE",
            "billing_lifecycle_state": "grace_period",
            "grace_period_ends_at": GRACE_END.isoformat(),
        },
        "expected_lifecycle": "GRACE_PERIOD",
        "expected_portal": "GRACE",
    },
    "cancelled_billing_active_client_mirror": {
        "client": {"client_id": "drift", "subscription_status": "ACTIVE", "client_lifecycle_status": "ACTIVE"},
        "billing": {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"},
        "expected_lifecycle": "CANCELLED_IMMEDIATE",
        "expected_portal": "BILLING_RECOVERY",
    },
    "suspended_org_active_billing_mirror": {
        "client": {"client_id": "drift", "client_lifecycle_status": "SUSPENDED"},
        "billing": {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
        "expected_lifecycle": "SUSPENDED",
        "expected_portal": "SUSPENDED",
    },
    "billing_authoritative_over_stale_client_mirror": {
        "client": {"client_id": "drift", "subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
        "billing": {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"},
        "expected_lifecycle": "CANCELLED_IMMEDIATE",
        "expected_portal": "BILLING_RECOVERY",
    },
}

LIFECYCLE_JOURNEY: List[Tuple[str, Dict, Dict, str, str]] = [
    ("onboarding", {"onboarding_status": "INTAKE_PENDING"}, None, "PAYMENT_PENDING", "PAYMENT_REQUIRED"),
    ("trial", {"onboarding_status": "PROVISIONED"}, {"subscription_status": "TRIALING", "billing_lifecycle_state": "active"}, "TRIAL", "FULL_ACCESS"),
    ("active", {"onboarding_status": "PROVISIONED", "client_lifecycle_status": "ACTIVE"}, {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}, "ACTIVE", "FULL_ACCESS"),
    ("grace", {}, {"subscription_status": "PAST_DUE", "billing_lifecycle_state": "grace_period", "grace_period_ends_at": GRACE_END.isoformat()}, "GRACE_PERIOD", "GRACE"),
    ("cancelled", {}, {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"}, "CANCELLED_IMMEDIATE", "BILLING_RECOVERY"),
    ("resubscribed", {"onboarding_status": "PROVISIONED", "client_lifecycle_status": "ACTIVE"}, {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}, "ACTIVE", "FULL_ACCESS"),
    ("archived", {"is_deleted": True, "client_lifecycle_status": "ARCHIVED"}, {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}, "ARCHIVED", "ARCHIVED"),
    ("deleted", {"purged_at": NOW.isoformat()}, None, "ACCOUNT_DELETED", "ACCOUNT_DELETED"),
]


@pytest.mark.parametrize("label", list(STATE_MATRIX.keys()))
def test_state_matrix_lifecycle_and_portal_mode(label):
    spec = STATE_MATRIX[label]
    payload = _payload(spec["client"], spec["billing"])
    assert payload["lifecycle_state"] == spec["lifecycle"]
    assert payload["portal_mode"] == spec["portal_mode"]
    assert payload["capabilities"]
    assert payload["runtime_version"] >= 1


@pytest.mark.parametrize("label", list(STATE_MATRIX.keys()))
def test_state_matrix_capability_grants(label):
    spec = STATE_MATRIX[label]
    contract = _contract(spec["client"], spec["billing"])
    for cap in spec["read_caps"]:
        assert _allowed(contract, cap, "read"), f"{label} read {cap}"
    for cap in spec["write_caps"]:
        assert _allowed(contract, cap, "write"), f"{label} write {cap}"
    for cap in spec["deny_write"]:
        assert not _allowed(contract, cap, "write"), f"{label} deny write {cap}"


@pytest.mark.parametrize("label", list(STATE_MATRIX.keys()))
def test_state_matrix_reactivation_policy(label):
    spec = STATE_MATRIX[label]
    payload = _payload(spec["client"], spec["billing"])
    eligible = payload["reactivation_policy"]["eligible"]
    assert eligible is spec["recovery_eligible"], label


@pytest.mark.parametrize("label", list(MIRROR_DRIFT_MATRIX.keys()))
def test_mirror_drift_resolves_authoritatively(label):
    spec = MIRROR_DRIFT_MATRIX[label]
    payload = _payload(spec["client"], spec.get("billing"))
    assert payload["lifecycle_state"] == spec["expected_lifecycle"], label
    assert payload["portal_mode"] == spec["expected_portal"], label


def test_valid_active_account_never_unknown():
    """Provisioned paying accounts must not resolve UNKNOWN."""
    client = {
        "client_id": "valid",
        "subscription_status": "ACTIVE",
        "onboarding_status": "PROVISIONED",
        "client_lifecycle_status": "ACTIVE",
        "lifecycle_status": "pending_payment",
    }
    res = resolve_account_lifecycle_state(client=client, billing=None, now=NOW)
    assert res.account_lifecycle_state != AccountLifecycleState.UNKNOWN.value
    assert res.account_lifecycle_state == AccountLifecycleState.ACTIVE.value


def test_unknown_only_for_unmapped_or_contradictory_facts():
    res = resolve_account_lifecycle_state(
        billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "cancelled"},
        now=NOW,
    )
    assert res.account_lifecycle_state == AccountLifecycleState.UNKNOWN.value


@pytest.mark.parametrize("step,_client,_billing,life,portal", LIFECYCLE_JOURNEY)
def test_lifecycle_journey_transitions(step, _client, _billing, life, portal):
    client = {"client_id": "journey", "billing_plan": "PLAN_3_PRO", **_client}
    payload = _payload(client, _billing)
    assert payload["lifecycle_state"] == life, step
    assert payload["portal_mode"] == portal, step


def test_resubscription_restores_full_capabilities_without_manual_recovery():
    cancelled = _contract(
        {"client_id": "j", "billing_plan": "PLAN_3_PRO"},
        {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"},
    )
    assert not _allowed(cancelled, "CAP_PROP_CREATE", "write")

    restored = _contract(
        {"client_id": "j", "billing_plan": "PLAN_3_PRO", "onboarding_status": "PROVISIONED"},
        {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
    )
    assert _allowed(restored, "CAP_PROP_CREATE", "write")
    assert restored["lifecycle_state"] == "ACTIVE"
    assert restored["portal_mode"] == "FULL_ACCESS"


def test_runtime_contract_regenerates_on_fact_change():
    c1 = _contract({"client_id": "v1"}, {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"})
    c2 = _contract({"client_id": "v1"}, {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"})
    assert c1["lifecycle_state"] == "ACTIVE"
    assert c2["lifecycle_state"] == "CANCELLED_IMMEDIATE"
    assert c1["runtime_version"] != c2["runtime_version"]


def test_runtime_contract_is_read_only_no_mutation():
    client = {"client_id": "immutable", "billing_plan": "PLAN_3_PRO", "subscription_status": "ACTIVE"}
    billing = {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}
    before_c = copy.deepcopy(client)
    before_b = copy.deepcopy(billing)
    _contract(client, billing)
    assert client == before_c
    assert billing == before_b


def test_all_lifecycle_columns_present_in_capability_matrix():
    for col in (
        "ACTIVE",
        "TRIAL",
        "GRACE_PERIOD",
        "CANCELLATION_SCHEDULED",
        "SUBSCRIPTION_EXPIRED",
        "READ_ONLY",
        "CANCELLED_IMMEDIATE",
        "SUSPENDED",
        "ARCHIVED",
        "ACCOUNT_DELETED",
        "UNKNOWN",
    ):
        assert col in _LIFECYCLE_COLUMNS


def test_payment_failed_portal_mode_full_access():
    payload = _payload(
        {},
        {"subscription_status": "PAST_DUE", "billing_lifecycle_state": "past_due", "grace_period_ends_at": None},
    )
    assert payload["lifecycle_state"] == "PAYMENT_FAILED"
    assert payload["portal_mode"] == "FULL_ACCESS"


def test_subscription_expired_read_only_retention_portal_override():
    payload = _payload(
        {},
        {
            "subscription_status": "UNPAID",
            "billing_lifecycle_state": "expired",
            "read_only_retention": True,
        },
    )
    assert payload["lifecycle_state"] == "READ_ONLY"
    assert payload["portal_mode"] == "READ_ONLY"


def test_data_retention_policy_survives_lifecycle_transitions():
    for label in ("ACTIVE", "CANCELLED_IMMEDIATE", "READ_ONLY", "ARCHIVED"):
        spec = STATE_MATRIX[label]
        payload = _payload(spec["client"], spec["billing"])
        tier = payload["retention_policy"]["tier"]
        assert tier in ("STANDARD", "READ_ONLY_WINDOW", "PURGE_ELIGIBLE")
