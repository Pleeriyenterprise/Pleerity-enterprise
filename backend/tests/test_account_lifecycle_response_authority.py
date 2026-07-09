"""Tests for ILP-7 Lifecycle Response Authority."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_response_authority import (
    LifecycleResponseAuthority,
    LifecycleResponseType,
    capability_denied_http_detail,
)
from services.account_lifecycle_runtime_contract import build_runtime_contract

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)


def _client(**overrides):
    base = {"client_id": "c-lr-1", "billing_plan": "PLAN_3_PRO"}
    base.update(overrides)
    return base


def _billing(**overrides):
    base = {
        "client_id": "c-lr-1",
        "subscription_status": "ACTIVE",
        "billing_lifecycle_state": "active",
    }
    base.update(overrides)
    return base


def _contract(client=None, billing=None):
    return build_runtime_contract(
        client=client or _client(),
        billing=billing or _billing(),
        now=NOW,
    )


LIFECYCLE_MATRIX = [
    ("ACTIVE", {}, {}, LifecycleResponseType.LIFECYCLE_DENIED),
    ("TRIAL", {}, {"subscription_status": "TRIALING"}, LifecycleResponseType.LIFECYCLE_DENIED),
    (
        "GRACE_PERIOD",
        {},
        {"subscription_status": "PAST_DUE", "billing_lifecycle_state": "grace_period"},
        LifecycleResponseType.LIFECYCLE_DENIED,
    ),
    (
        "CANCELLATION_SCHEDULED",
        {},
        {
            "subscription_status": "ACTIVE",
            "billing_lifecycle_state": "cancel_at_period_end",
            "cancel_at_period_end": True,
            "current_period_end": PERIOD_END.isoformat(),
        },
        LifecycleResponseType.LIFECYCLE_DENIED,
    ),
    (
        "READ_ONLY",
        {"read_only_retention": True},
        {"subscription_status": "UNPAID", "billing_lifecycle_state": "expired", "read_only_retention": True},
        LifecycleResponseType.READ_ONLY,
    ),
    (
        "CANCELLED_IMMEDIATE",
        {},
        {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"},
        LifecycleResponseType.BILLING_RECOVERY,
    ),
    (
        "SUBSCRIPTION_EXPIRED",
        {},
        {"subscription_status": "UNPAID", "billing_lifecycle_state": "expired"},
        LifecycleResponseType.BILLING_RECOVERY,
    ),
    (
        "SUSPENDED",
        {"client_lifecycle_status": "SUSPENDED"},
        {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
        LifecycleResponseType.SUSPENDED,
    ),
    (
        "ARCHIVED",
        {"is_deleted": True, "client_lifecycle_status": "ARCHIVED"},
        {},
        LifecycleResponseType.ARCHIVED,
    ),
    (
        "ACCOUNT_DELETED",
        {"purged_at": NOW.isoformat()},
        {},
        LifecycleResponseType.DELETED,
    ),
]


@pytest.mark.parametrize("lifecycle,client_extra,billing,expected_type", LIFECYCLE_MATRIX)
def test_lifecycle_denial_schema_by_state(lifecycle, client_extra, billing, expected_type):
    contract = _contract(_client(**client_extra), _billing(**billing))
    assert contract["lifecycle_state"] == lifecycle
    detail = LifecycleResponseAuthority.from_contract_lifecycle_denial(contract).to_http_detail()
    assert detail["lifecycle_state"] == lifecycle
    assert detail["portal_mode"] == contract["portal_mode"]
    assert detail["response_type"] == expected_type.value
    assert isinstance(detail["message"], str) and detail["message"]
    assert detail["lifecycle_redirect"]["route"]
    assert detail["lifecycle_redirect"]["surface"]
    assert detail["recovery"]["route"] == detail["lifecycle_redirect"]["route"]
    assert detail["runtime_version"] == contract["runtime_version"]
    assert detail["contract_version"] == contract["contract_version"]
    assert detail["policy_version"] == "account_lifecycle_response_v1"
    assert detail["customer_experience"]["primary_cta"]["route"]


def test_capability_denied_read_only_mutation():
    contract = _contract(
        _client(),
        _billing(
            subscription_status="UNPAID",
            billing_lifecycle_state="expired",
            read_only_retention=True,
        ),
    )
    decision = CapabilityEnforcementService(None).evaluate_from_contract(
        contract, "CAP_PROP_EDIT", "write"
    )
    assert not decision.allowed
    detail = capability_denied_http_detail(decision, contract=contract)
    assert detail["error"] == "capability_denied"
    assert detail["response_type"] == LifecycleResponseType.READ_ONLY.value
    assert detail["lifecycle_redirect"]["route"] == "/settings/billing"
    assert detail["recovery"]["route"] == "/settings/billing"


def test_contract_lifecycle_denial_no_legacy_entitlement_leak():
    contract = _contract(
        _client(),
        _billing(subscription_status="CANCELED", billing_lifecycle_state="cancelled"),
    )
    detail = LifecycleResponseAuthority.from_contract_lifecycle_denial(contract).to_http_detail()
    assert detail["response_type"] == LifecycleResponseType.BILLING_RECOVERY.value
    assert detail["lifecycle_redirect"]["route"] == "/settings/billing"
    assert detail["recovery"]["action"] == "complete_payment"
    assert "canonical_entitlement_state" not in detail


def test_authentication_expired_response():
    detail = LifecycleResponseAuthority.authentication_expired().to_http_detail()
    assert detail["response_type"] == LifecycleResponseType.AUTHENTICATION_EXPIRED.value
    assert detail["lifecycle_redirect"]["route"] == "/login"


def test_session_refresh_required_safe_to_retry():
    detail = LifecycleResponseAuthority.session_refresh_required(runtime_version=42).to_http_detail()
    assert detail["safe_to_retry"] is True
    assert detail["runtime_version"] == 42


def test_support_reference_stable_for_same_inputs():
    contract = _contract()
    decision = CapabilityEnforcementService(None).evaluate_from_contract(
        contract, "CAP_PROP_VIEW", "write"
    )
    d1 = capability_denied_http_detail(decision, contract=contract)
    d2 = capability_denied_http_detail(decision, contract=contract)
    assert d1["support_reference"] == d2["support_reference"]
