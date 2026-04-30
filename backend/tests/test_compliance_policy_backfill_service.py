from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.compliance_policy_backfill_service import (
    JOB_GAP_RECONCILIATION,
    JOB_REQUIREMENT_FIELDS,
    _retry,
    run_tenant_gap_policy_reconciliation,
    run_tenant_requirement_policy_backfill,
)


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    async def to_list(self, _n):
        return self._rows


@pytest.mark.asyncio
async def test_retry_backoff_eventually_succeeds():
    state = {"n": 0}

    async def _fn():
        state["n"] += 1
        if state["n"] < 3:
            raise RuntimeError("boom")
        return "ok"

    out = await _retry(_fn, max_retries=3, backoff_seconds=0.001)
    assert out == "ok"
    assert state["n"] == 3


@pytest.mark.asyncio
async def test_requirement_policy_backfill_tenant_scoped_and_checkpointed():
    req_rows = [
        {
            "client_id": "c1",
            "requirement_id": "r1",
            "requirement_code": "EPC",
            "requirement_type": "epc",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "evidence_state": "MISSING",
        }
    ]
    db = MagicMock()
    db.applicability_resolution_audit = MagicMock(insert_one=AsyncMock())
    db.compliance_policy_backfill_checkpoints.find_one = AsyncMock(return_value=None)
    db.compliance_policy_backfill_checkpoints.update_one = AsyncMock()
    db.compliance_policy_backfill_dead_letters.insert_one = AsyncMock()
    db.requirements.find = MagicMock(side_effect=[_Cursor(req_rows), _Cursor([])])
    db.requirements.update_one = AsyncMock()

    out = await run_tenant_requirement_policy_backfill(
        db,
        client_id="c1",
        batch_size=50,
        max_retries=1,
        backoff_seconds=0.001,
        max_writes_per_sec=500.0,
    )
    assert out["job_name"] == JOB_REQUIREMENT_FIELDS
    assert out["client_id"] == "c1"
    assert out["processed"] == 1
    # Tenant isolation proof on query path.
    q = db.requirements.find.call_args_list[0][0][0]
    assert q["client_id"] == "c1"
    assert db.compliance_policy_backfill_checkpoints.update_one.await_count >= 2


@pytest.mark.asyncio
async def test_gap_policy_reconciliation_updates_open_gap_snapshots():
    req_rows = [
        {
            "client_id": "c1",
            "property_id": "p1",
            "requirement_id": "r1",
            "requirement_code": "EPC",
            "requirement_type": "epc",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "evidence_state": "MISSING",
        }
    ]
    fake_gap_row = {
        "gap_key": "c1:p1:r1:MISSING_EVIDENCE",
        "requirement_code_normalized": "epc",
        "applicability_state": "REQUIRED",
        "is_mandatory": True,
        "policy_criticality": "HIGH",
        "evidence_state_normalized": "MISSING",
        "critical_mandatory_breach": True,
        "high_risk_gap": True,
        "attention_only_gap": False,
        "unknown_or_stale_signal": False,
        "policy_reason_codes": ["UNRESOLVED_CRITICAL_MANDATORY_BREACH"],
        "policy_classification_version": "v1",
    }

    db = MagicMock()
    db.compliance_policy_backfill_checkpoints.find_one = AsyncMock(return_value=None)
    db.compliance_policy_backfill_checkpoints.update_one = AsyncMock()
    db.compliance_policy_backfill_dead_letters.insert_one = AsyncMock()
    db.requirements.find = MagicMock(side_effect=[_Cursor(req_rows), _Cursor([])])
    db.properties.find_one = AsyncMock(return_value={"client_id": "c1", "property_id": "p1"})
    db.compliance_gaps.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[{"gap_key": fake_gap_row["gap_key"]}])))
    db.compliance_gaps.update_one = AsyncMock()

    class _Gap:
        def to_mongo(self, **_kwargs):
            return dict(fake_gap_row)

    with patch(
        "services.compliance_policy_backfill_service.infer_compliance_gaps_for_requirement",
        return_value=[_Gap()],
    ):
        out = await run_tenant_gap_policy_reconciliation(
            db,
            client_id="c1",
            batch_size=100,
            max_retries=1,
            backoff_seconds=0.001,
            max_writes_per_sec=500.0,
        )

    assert out["job_name"] == JOB_GAP_RECONCILIATION
    assert out["client_id"] == "c1"
    assert out["updated"] == 1
    uq = db.compliance_gaps.update_one.await_args[0][0]
    assert uq["client_id"] == "c1"
    assert uq["status"] == "open"
