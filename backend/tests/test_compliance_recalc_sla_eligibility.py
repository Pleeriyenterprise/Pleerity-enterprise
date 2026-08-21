"""SLA class mapping over canonical background runtime authority (queue_processing)."""
from datetime import datetime, timezone

import pytest

from services.account_background_runtime_authority import BackgroundRuntimeAuthority
from services.account_lifecycle_runtime_contract import build_runtime_contract
from services.compliance_recalc_sla_eligibility import (
    COMPLIANCE_RECALC_QUEUE_JOB_TYPE,
    ComplianceRecalcSlaClass,
    classify_compliance_recalc_sla_decision,
)

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)


def _contract(client, billing=None):
    billing = billing if billing is not None else {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}
    return build_runtime_contract(client=client, billing=billing, now=NOW)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lifecycle,client_extra,billing,expected_class,expected_decision",
    [
        ("ACTIVE", {}, {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}, ComplianceRecalcSlaClass.ACTIONABLE, "CONTINUE"),
        (
            "TRIAL",
            {"billing_plan": "PLAN_1_SOLO"},
            {"subscription_status": "TRIALING", "billing_lifecycle_state": "active"},
            ComplianceRecalcSlaClass.ACTIONABLE,
            "CONTINUE",
        ),
        (
            "GRACE_PERIOD",
            {},
            {"subscription_status": "PAST_DUE", "billing_lifecycle_state": "grace_period"},
            ComplianceRecalcSlaClass.ACTIONABLE,
            "CONTINUE",
        ),
        (
            "PAYMENT_PENDING",
            {"lifecycle_status": "pending_payment"},
            None,
            ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED,
            "SKIP",
        ),
        (
            "SUSPENDED",
            {"client_lifecycle_status": "SUSPENDED"},
            {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
            ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED,
            "PAUSE",
        ),
        (
            "CANCELLED_IMMEDIATE",
            {},
            {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"},
            ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED,
            "PAUSE",
        ),
        (
            "ACCOUNT_DELETED",
            {"purged_at": NOW.isoformat()},
            {},
            ComplianceRecalcSlaClass.TERMINATED,
            "TERMINATE",
        ),
        (
            "ARCHIVED",
            {"is_deleted": True, "client_lifecycle_status": "ARCHIVED"},
            {},
            ComplianceRecalcSlaClass.TERMINATED,
            "TERMINATE",
        ),
        (
            "UNKNOWN",
            {},
            {"subscription_status": "ACTIVE", "billing_lifecycle_state": "cancelled"},
            ComplianceRecalcSlaClass.UNKNOWN_SAFE_SKIP,
            "SKIP",
        ),
    ],
)
async def test_queue_sla_class_matches_worker_job_type(
    lifecycle, client_extra, billing, expected_class, expected_decision
):
    client = {"client_id": "c-sla", "billing_plan": "PLAN_3_PRO", **client_extra}
    contract = _contract(client, billing)
    assert contract["lifecycle_state"] == lifecycle

    authority = BackgroundRuntimeAuthority(db=None)
    decision = await authority.evaluate("c-sla", COMPLIANCE_RECALC_QUEUE_JOB_TYPE, contract=contract)
    eligibility = classify_compliance_recalc_sla_decision(decision)
    assert eligibility.sla_class == expected_class
    assert eligibility.decision == expected_decision
    assert eligibility.operationally_actionable is (expected_class == ComplianceRecalcSlaClass.ACTIONABLE)


@pytest.mark.asyncio
async def test_missing_client_id_is_unknown_safe_skip():
    authority = BackgroundRuntimeAuthority(db=None)
    decision = await authority.evaluate("", COMPLIANCE_RECALC_QUEUE_JOB_TYPE)
    eligibility = classify_compliance_recalc_sla_decision(decision)
    assert eligibility.sla_class == ComplianceRecalcSlaClass.UNKNOWN_SAFE_SKIP
    assert eligibility.operationally_actionable is False
