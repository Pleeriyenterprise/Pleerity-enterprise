from unittest.mock import AsyncMock, MagicMock

import pytest

from services.portfolio_override_policy_health import JOB_GAP_RECONCILIATION
from services.policy_reason_codes import PolicyReasonCode
from services.portfolio_risk_override_latch import (
    LATCH_COLLECTION,
    apply_persistent_critical_escalation_latch,
    gap_reconciliation_cycle_is_newer_than,
)


def test_gap_reconciliation_cycle_tuple_ordering():
    cur = {"checkpoint_completed_at": "2026-04-30T10:00:00", "checkpoint_updated_at": "2026-04-30T10:00:01"}
    old = {"checkpoint_completed_at": "2026-04-29T10:00:00", "checkpoint_updated_at": "2026-04-29T10:00:01"}
    assert gap_reconciliation_cycle_is_newer_than(cur, old) is True
    assert gap_reconciliation_cycle_is_newer_than(old, cur) is False


class _FakeDb:
    def __init__(self, latch_coll: MagicMock) -> None:
        self._latch_coll = latch_coll

    def __getitem__(self, key):
        if key == LATCH_COLLECTION:
            return self._latch_coll
        out = MagicMock()
        out.find_one = AsyncMock(return_value=None)
        return out


def _db_with_latch_coll(coll: MagicMock) -> _FakeDb:
    return _FakeDb(coll)


@pytest.mark.asyncio
async def test_latch_sets_on_critical_breach():
    coll = MagicMock()
    coll.find_one = AsyncMock(return_value=None)
    coll.update_one = AsyncMock()
    db = _db_with_latch_coll(coll)

    policy_out = {
        "effective_portfolio_risk_state": "Critical Risk",
        "risk_override_reasons": [PolicyReasonCode.UNRESOLVED_CRITICAL_MANDATORY_BREACH.value],
        "critical_property_escalation": True,
        "attention_required": True,
        "suppress_positive_headline": True,
    }
    gap_engine = {"policy": {"critical_mandatory_breach_count": 2}}
    chk = {"status": "running", "completed_at": None, "updated_at": "2026-04-30T09:00:00"}
    out = await apply_persistent_critical_escalation_latch(
        db,
        client_id="c1",
        policy_override_output=policy_out,
        gap_engine=gap_engine,
        gap_reconciliation_checkpoint=chk,
    )
    assert out["effective_portfolio_risk_state"] == "Critical Risk"
    coll.update_one.assert_awaited()


@pytest.mark.asyncio
async def test_latch_holds_after_breach_cleared_until_newer_checkpoint():
    latch_doc = {
        "active": True,
        "latched_critical_escalation": True,
        "last_effective_portfolio_risk_state": "Critical Risk",
        "latch_reconciliation_cycle_ref": {
            "job_name": JOB_GAP_RECONCILIATION,
            "checkpoint_completed_at": "2026-04-28T00:00:00",
            "checkpoint_updated_at": "2026-04-28T00:00:01",
            "status": "completed",
        },
    }
    coll = MagicMock()
    coll.find_one = AsyncMock(return_value=latch_doc)
    coll.update_one = AsyncMock()
    db = _db_with_latch_coll(coll)

    policy_out = {
        "effective_portfolio_risk_state": "Low Risk",
        "risk_override_reasons": [],
        "critical_property_escalation": False,
        "attention_required": False,
        "suppress_positive_headline": False,
    }
    gap_engine = {"policy": {"critical_mandatory_breach_count": 0}}
    chk = {"status": "completed", "completed_at": "2026-04-28T00:00:00", "updated_at": "2026-04-28T00:00:01"}
    out = await apply_persistent_critical_escalation_latch(
        db,
        client_id="c1",
        policy_override_output=policy_out,
        gap_engine=gap_engine,
        gap_reconciliation_checkpoint=chk,
    )
    assert out["effective_portfolio_risk_state"] == "Critical Risk"
    assert PolicyReasonCode.ANTI_FLAPPING_RECONCILIATION_HOLD.value in out["risk_override_reasons"]


@pytest.mark.asyncio
async def test_latch_clears_when_no_breach_completed_and_newer_cycle():
    latch_doc = {
        "active": True,
        "latched_critical_escalation": True,
        "last_effective_portfolio_risk_state": "Critical Risk",
        "latch_reconciliation_cycle_ref": {
            "job_name": JOB_GAP_RECONCILIATION,
            "checkpoint_completed_at": "2026-04-28T00:00:00",
            "checkpoint_updated_at": "2026-04-28T00:00:01",
            "status": "completed",
        },
    }
    coll = MagicMock()
    coll.find_one = AsyncMock(return_value=latch_doc)
    coll.update_one = AsyncMock()
    db = _db_with_latch_coll(coll)

    policy_out = {
        "effective_portfolio_risk_state": "Low Risk",
        "risk_override_reasons": [],
        "critical_property_escalation": False,
        "attention_required": False,
        "suppress_positive_headline": False,
    }
    gap_engine = {"policy": {"critical_mandatory_breach_count": 0}}
    chk = {"status": "completed", "completed_at": "2026-04-30T12:00:00", "updated_at": "2026-04-30T12:00:01"}
    out = await apply_persistent_critical_escalation_latch(
        db,
        client_id="c1",
        policy_override_output=policy_out,
        gap_engine=gap_engine,
        gap_reconciliation_checkpoint=chk,
    )
    assert out["effective_portfolio_risk_state"] == "Low Risk"
    assert coll.update_one.await_count >= 1
