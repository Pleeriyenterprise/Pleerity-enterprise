"""Tests for ILP-8 Customer Communication & Reactivation Authority."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.account_customer_communication_authority import (
    CustomerCommunicationAuthority,
    POLICY_VERSION,
)
from services.account_lifecycle_reactivation_authority import (
    LifecycleReactivationAuthority,
    POLICY_VERSION as REACT_POLICY_VERSION,
)
from services.account_lifecycle_runtime_contract import build_runtime_contract

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _client(**overrides):
    base = {"client_id": "c-comm-1", "billing_plan": "PLAN_3_PRO"}
    base.update(overrides)
    return base


def _billing(**overrides):
    base = {
        "client_id": "c-comm-1",
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
    ("ACTIVE", {}, {}, True, "email_operational"),
    ("TRIAL", {}, {"subscription_status": "TRIALING"}, True, "email_operational"),
    (
        "GRACE_PERIOD",
        {},
        {"subscription_status": "PAST_DUE", "billing_lifecycle_state": "grace_period"},
        True,
        "email_operational",
    ),
    (
        "CANCELLATION_SCHEDULED",
        {},
        {
            "subscription_status": "ACTIVE",
            "billing_lifecycle_state": "cancel_at_period_end",
            "cancel_at_period_end": True,
        },
        True,
        "email_operational",
    ),
    (
        "READ_ONLY",
        {"read_only_retention": True},
        {"subscription_status": "UNPAID", "billing_lifecycle_state": "expired", "read_only_retention": True},
        True,
        "email_operational",
    ),
    (
        "CANCELLED_IMMEDIATE",
        {},
        {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"},
        False,
        "email_operational",
    ),
    (
        "SUBSCRIPTION_EXPIRED",
        {},
        {"subscription_status": "UNPAID", "billing_lifecycle_state": "expired"},
        False,
        "email_operational",
    ),
    (
        "SUSPENDED",
        {"client_lifecycle_status": "SUSPENDED"},
        {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
        False,
        "email_operational",
    ),
    (
        "ARCHIVED",
        {"is_deleted": True, "client_lifecycle_status": "ARCHIVED"},
        {},
        False,
        "email_operational",
    ),
    (
        "ACCOUNT_DELETED",
        {"purged_at": NOW.isoformat()},
        {},
        False,
        "email_operational",
    ),
]


@pytest.mark.parametrize("lifecycle,client_extra,billing,allowed,category", LIFECYCLE_MATRIX)
def test_operational_email_eligibility_by_lifecycle(lifecycle, client_extra, billing, allowed, category):
    contract = _contract(_client(**client_extra), _billing(**billing))
    assert contract["lifecycle_state"] == lifecycle
    decision = CustomerCommunicationAuthority.from_contract(
        contract,
        client_id="c-comm-1",
        channel="email",
        template={"email_category": "compliance"},
        event_type="compliance_reminder",
    )
    assert decision.communication_category == category
    assert decision.allowed is allowed
    assert decision.policy_version == POLICY_VERSION
    assert decision.template_context.get("lifecycle_state") == lifecycle
    assert decision.template_context.get("portal_mode") == contract["portal_mode"]
    if allowed:
        assert decision.message
        assert decision.template_context.get("lifecycle_message")


def test_billing_email_allowed_when_operational_suppressed():
    contract = _contract(
        _client(),
        _billing(subscription_status="CANCELED", billing_lifecycle_state="cancelled"),
    )
    operational = CustomerCommunicationAuthority.from_contract(
        contract,
        client_id="c-comm-1",
        template={"email_category": "compliance"},
    )
    billing = CustomerCommunicationAuthority.from_contract(
        contract,
        client_id="c-comm-1",
        template={"email_category": "billing"},
        template_key="SUBSCRIPTION_RENEWAL_7D",
    )
    assert not operational.allowed
    assert billing.allowed
    assert billing.communication_category == "email_billing"


def test_sms_channel_uses_communication_policy_sms():
    contract = _contract()
    allowed = CustomerCommunicationAuthority.from_contract(
        contract, client_id="c-comm-1", channel="sms"
    )
    assert allowed.channel_policy_key == "sms"
    assert allowed.allowed is True

    contract_ro = _contract(
        _client(),
        _billing(subscription_status="UNPAID", billing_lifecycle_state="expired", read_only_retention=True),
    )
    denied = CustomerCommunicationAuthority.from_contract(
        contract_ro, client_id="c-comm-1", channel="sms"
    )
    assert denied.allowed is False


def test_template_context_placeholders():
    contract = _contract()
    decision = CustomerCommunicationAuthority.from_contract(contract, client_id="c-comm-1")
    ctx = decision.template_context
    assert "lifecycle_message" in ctx
    assert "lifecycle_cta" in ctx
    assert "lifecycle_status" in ctx
    assert "recovery_url" in ctx
    assert "portal_mode" in ctx


@pytest.mark.parametrize("lifecycle,client_extra,billing,eligible", [
    ("ACTIVE", {}, {}, False),
    ("CANCELLED_IMMEDIATE", {}, {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"}, True),
    ("READ_ONLY", {"read_only_retention": True}, {"subscription_status": "UNPAID", "billing_lifecycle_state": "expired", "read_only_retention": True}, True),
    ("SUSPENDED", {"client_lifecycle_status": "SUSPENDED"}, {}, True),
    ("ARCHIVED", {"is_deleted": True, "client_lifecycle_status": "ARCHIVED"}, {}, False),
])
def test_reactivation_plan(lifecycle, client_extra, billing, eligible):
    contract = _contract(_client(**client_extra), _billing(**billing))
    plan = LifecycleReactivationAuthority.reactivation_plan(contract)
    assert plan.lifecycle_state == lifecycle
    assert plan.eligible is eligible
    assert plan.policy_version == REACT_POLICY_VERSION
    assert plan.recovery_journey.journey_id
    assert plan.recovery_journey.steps


def test_recovery_journey_complete_payment_steps():
    contract = _contract(
        _client(),
        _billing(subscription_status="CANCELED", billing_lifecycle_state="cancelled"),
    )
    journey = LifecycleReactivationAuthority.recovery_journey("complete_payment", contract=contract)
    assert journey.eligible is True
    assert len(journey.steps) >= 2
    assert journey.cta_route == "/settings/billing"
