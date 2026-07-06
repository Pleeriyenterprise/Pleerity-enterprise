"""ILP-4 closeout — lifecycle journey validation against Runtime Contract."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import build_runtime_contract, runtime_contract_to_dict

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)

CLOSEOUT_LIFECYCLES = {
    "ACTIVE": (
        {"client_id": "c-closeout", "billing_plan": "PLAN_3_PRO"},
        {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
        "FULL_ACCESS",
    ),
    "READ_ONLY": (
        {"client_id": "c-closeout", "billing_plan": "PLAN_3_PRO"},
        {
            "subscription_status": "UNPAID",
            "billing_lifecycle_state": "expired",
            "read_only_retention": True,
        },
        "READ_ONLY",
    ),
    "CANCELLED_IMMEDIATE": (
        {"client_id": "c-closeout", "billing_plan": "PLAN_3_PRO"},
        {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"},
        "BILLING_RECOVERY",
    ),
    "SUBSCRIPTION_EXPIRED": (
        {"client_id": "c-closeout", "billing_plan": "PLAN_3_PRO"},
        {"subscription_status": "UNPAID", "billing_lifecycle_state": "expired"},
        "BILLING_RECOVERY",
    ),
    "SUSPENDED": (
        {"client_id": "c-closeout", "billing_plan": "PLAN_3_PRO", "client_lifecycle_status": "SUSPENDED"},
        {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
        "SUSPENDED",
    ),
    "ARCHIVED": (
        {"client_id": "c-closeout", "billing_plan": "PLAN_3_PRO", "is_deleted": True, "client_lifecycle_status": "ARCHIVED"},
        {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
        "ARCHIVED",
    ),
}

BILLING_RECOVERY_LIFECYCLES = ("CANCELLED_IMMEDIATE", "SUBSCRIPTION_EXPIRED", "READ_ONLY")


def _contract(client, billing):
    return build_runtime_contract(client=client, billing=billing, now=NOW)


def _allowed(contract, cap_id: str, action: str) -> bool:
    return CapabilityEnforcementService(db=None).evaluate_from_contract(contract, cap_id, action).allowed


@pytest.mark.parametrize("lifecycle", list(CLOSEOUT_LIFECYCLES.keys()))
def test_closeout_lifecycle_resolves_expected_portal_mode(lifecycle):
    client, billing, expected_mode = CLOSEOUT_LIFECYCLES[lifecycle]
    payload = runtime_contract_to_dict(_contract(client, billing))
    assert payload["lifecycle_state"] == lifecycle
    assert payload["portal_mode"] == expected_mode


@pytest.mark.parametrize("lifecycle", BILLING_RECOVERY_LIFECYCLES)
def test_closeout_billing_recovery_caps_remain_available(lifecycle):
    client, billing, _ = CLOSEOUT_LIFECYCLES[lifecycle]
    contract = _contract(client, billing)
    assert _allowed(contract, "CAP_BILLING_VIEW", "read")
    assert _allowed(contract, "CAP_BILLING_CHECKOUT", "write")


def test_closeout_cancelled_immediate_denies_ops_write_not_billing_storm():
    client, billing, _ = CLOSEOUT_LIFECYCLES["CANCELLED_IMMEDIATE"]
    contract = _contract(client, billing)
    assert _allowed(contract, "CAP_BILLING_VIEW", "read")
    assert not _allowed(contract, "CAP_OPS_MAINTENANCE", "write")


def test_closeout_read_only_allows_property_read_denies_create():
    client, billing, _ = CLOSEOUT_LIFECYCLES["READ_ONLY"]
    contract = _contract(client, billing)
    assert _allowed(contract, "CAP_PROP_VIEW", "read")
    assert not _allowed(contract, "CAP_PROP_CREATE", "write")


def test_closeout_suspended_denies_dashboard_mutations():
    client, billing, _ = CLOSEOUT_LIFECYCLES["SUSPENDED"]
    contract = _contract(client, billing)
    assert not _allowed(contract, "CAP_PROFILE_EDIT", "write")
    assert not _allowed(contract, "CAP_OPS_MAINTENANCE", "write")


def test_closeout_archived_denies_customer_surfaces():
    client, billing, _ = CLOSEOUT_LIFECYCLES["ARCHIVED"]
    contract = _contract(client, billing)
    assert not _allowed(contract, "CAP_BILLING_VIEW", "read")
    assert not _allowed(contract, "CAP_PROP_VIEW", "read")
