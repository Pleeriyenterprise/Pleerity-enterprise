"""Tests for ILP-6 background runtime authority."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.account_background_runtime_authority import (
    BackgroundJobDecision,
    BackgroundRuntimeAuthority,
)
from services.account_lifecycle_runtime_contract import build_runtime_contract

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)


def _contract(client, billing=None):
    billing = billing or {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}
    return build_runtime_contract(client=client, billing=billing, now=NOW)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lifecycle,client_extra,billing,job_type,expected",
    [
        ("ACTIVE", {}, {}, "daily_reminders", BackgroundJobDecision.CONTINUE),
        ("TRIAL", {"billing_plan": "PLAN_1_SOLO"}, {"subscription_status": "TRIALING", "billing_lifecycle_state": "active"}, "daily_reminders", BackgroundJobDecision.CONTINUE),
        ("GRACE_PERIOD", {}, {"subscription_status": "PAST_DUE", "billing_lifecycle_state": "grace_period"}, "monthly_digest", BackgroundJobDecision.CONTINUE),
        (
            "CANCELLATION_SCHEDULED",
            {},
            {
                "subscription_status": "ACTIVE",
                "billing_lifecycle_state": "cancel_at_period_end",
                "cancel_at_period_end": True,
                "current_period_end": PERIOD_END.isoformat(),
            },
            "daily_reminders",
            BackgroundJobDecision.CONTINUE,
        ),
        ("READ_ONLY", {"read_only_retention": True}, {"subscription_status": "UNPAID", "billing_lifecycle_state": "expired", "read_only_retention": True}, "daily_reminders", BackgroundJobDecision.SKIP),
        ("CANCELLED_IMMEDIATE", {}, {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"}, "daily_reminders", BackgroundJobDecision.SKIP),
        ("SUBSCRIPTION_EXPIRED", {}, {"subscription_status": "UNPAID", "billing_lifecycle_state": "expired"}, "compliance_check", BackgroundJobDecision.SKIP),
        ("SUSPENDED", {"client_lifecycle_status": "SUSPENDED"}, {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}, "compliance_recalc", BackgroundJobDecision.SKIP),
        ("ARCHIVED", {"is_deleted": True, "client_lifecycle_status": "ARCHIVED"}, {}, "daily_reminders", BackgroundJobDecision.TERMINATE),
        ("ACCOUNT_DELETED", {"purged_at": NOW.isoformat()}, {}, "daily_reminders", BackgroundJobDecision.TERMINATE),
    ],
)
async def test_background_runtime_lifecycle_matrix(lifecycle, client_extra, billing, job_type, expected):
    client = {"client_id": "c-bg", "billing_plan": "PLAN_3_PRO", **client_extra}
    contract = _contract(client, billing)
    assert contract["lifecycle_state"] == lifecycle

    authority = BackgroundRuntimeAuthority(db=None)
    decision = await authority.evaluate("c-bg", job_type, contract=contract)
    assert decision.decision == expected
    assert decision.lifecycle_state == lifecycle
    assert decision.runtime_version == contract["runtime_version"]


@pytest.mark.asyncio
async def test_unknown_lifecycle_safe_skip():
    client = {"client_id": "c-bg", "billing_plan": "PLAN_3_PRO"}
    billing = {"subscription_status": "ACTIVE", "billing_lifecycle_state": "cancelled"}
    contract = _contract(client, billing)
    assert contract["lifecycle_state"] == "UNKNOWN"
    authority = BackgroundRuntimeAuthority(db=None)
    decision = await authority.evaluate("c-bg", "daily_reminders", contract=contract)
    assert decision.decision == BackgroundJobDecision.SKIP
    assert decision.reason == "lifecycle_unknown_safe_skip"


@pytest.mark.asyncio
async def test_scheduled_reports_revoked_when_cancelled():
    client = {"client_id": "c-bg", "billing_plan": "PLAN_3_PRO"}
    billing = {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"}
    contract = _contract(client, billing)
    authority = BackgroundRuntimeAuthority(db=None)
    decision = await authority.evaluate("c-bg", "scheduled_reports", contract=contract)
    assert decision.decision == BackgroundJobDecision.SKIP
    assert decision.background_policy_key == "scheduled_reports"
    assert "REVOKE" in decision.background_policy_action or decision.reason.startswith("background_policy")


@pytest.mark.asyncio
async def test_communication_policy_blocks_operational_email_when_billing_recovery():
    client = {"client_id": "c-bg", "billing_plan": "PLAN_3_PRO"}
    billing = {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"}
    contract = _contract(client, billing)
    authority = BackgroundRuntimeAuthority(db=None)
    # Policy pauses reminders first; if we force CONTINUE path via digest on grace - test billing comms
    decision = await authority.evaluate("c-bg", "renewal_reminders", contract=contract)
    assert decision.decision != BackgroundJobDecision.CONTINUE


@pytest.mark.asyncio
async def test_idempotency_key_stable_for_same_runtime_version():
    client = {"client_id": "c-bg", "billing_plan": "PLAN_3_PRO"}
    contract = _contract(client)
    authority = BackgroundRuntimeAuthority(db=None)
    d1 = await authority.evaluate("c-bg", "daily_reminders", contract=contract, idempotency_suffix="run1")
    d2 = await authority.evaluate("c-bg", "daily_reminders", contract=contract, idempotency_suffix="run1")
    assert d1.idempotency_key == d2.idempotency_key
    assert d1.runtime_version == contract["runtime_version"]
