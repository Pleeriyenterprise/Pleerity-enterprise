"""
Outcome semantics for risk_signal_regen_worker (job_runs / run_instrumented contract).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.job_run_service import (
    OUTCOME_CONDITIONAL_NO_OUTPUT,
    OUTCOME_DEGRADED,
    OUTCOME_FAILED,
    OUTCOME_SUCCESS,
)
from services.risk_signal_regen_queue import run_risk_signal_regen_worker


def _make_job(jid="jid1", property_id="p1", client_id="c1", attempts=0):
    return {
        "_id": jid,
        "property_id": property_id,
        "client_id": client_id,
        "attempts": attempts,
        "trigger_reasons": [],
    }


def _mock_db_for_queue(find_one_and_update_side_effect):
    mock_db = MagicMock()
    coll = MagicMock()
    coll.update_many = AsyncMock(return_value=MagicMock(modified_count=0))
    coll.find_one_and_update = AsyncMock(side_effect=find_one_and_update_side_effect)
    coll.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
    coll.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.risk_signal_regen_queue = coll
    mock_db.properties = MagicMock()
    mock_db.properties.find_one = AsyncMock(return_value={"client_id": "c1", "billing_plan": "PLAN_1_SOLO"})
    mock_db.clients = MagicMock()
    mock_db.clients.find_one = AsyncMock(return_value={"billing_plan": "PLAN_1_SOLO"})
    return mock_db


@pytest.mark.asyncio
async def test_risk_regen_worker_empty_queue_conditional_no_output():
    mock_db = _mock_db_for_queue([None])

    with patch("services.risk_signal_regen_queue.database.get_db", return_value=mock_db):
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            out = await run_risk_signal_regen_worker(batch_limit=5)

    assert out["outcome_status"] == OUTCOME_CONDITIONAL_NO_OUTPUT
    assert out["outcome_metrics"]["queue_empty"] is True
    assert out["outcome_metrics"]["attempted_count"] == 0
    assert out["outcome_metrics"]["regenerated_count"] == 0
    assert out["outcome_metrics"]["skipped_feature_flag_count"] == 0
    assert out["outcome_metrics"]["failed_count"] == 0
    assert out["outcome_metrics"]["outcome_kind"] == "NO_WORK_ELIGIBLE"
    assert out["count"] == 0


@pytest.mark.asyncio
async def test_risk_regen_worker_skipped_feature_flag_not_counted_as_regenerated():
    job = _make_job()

    async def gen_flags(client_id, billing):
        return {"PREDICTIVE_MAINTENANCE": False}

    mock_db = _mock_db_for_queue([job, None])

    with patch("services.risk_signal_regen_queue.database.get_db", return_value=mock_db):
        with patch("services.ops_compliance_feature_flags.get_effective_flags", side_effect=gen_flags):
            with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
                out = await run_risk_signal_regen_worker(batch_limit=5)

    assert out["outcome_metrics"]["attempted_count"] == 1
    assert out["outcome_metrics"]["skipped_feature_flag_count"] == 1
    assert out["outcome_metrics"]["regenerated_count"] == 0
    assert out["outcome_metrics"]["failed_count"] == 0
    assert out["outcome_metrics"]["outcome_kind"] == "BLOCKED"
    assert out["outcome_status"] == OUTCOME_CONDITIONAL_NO_OUTPUT
    assert out["count"] == 0


@pytest.mark.asyncio
async def test_risk_regen_worker_successful_regeneration():
    job = _make_job()

    async def gen_flags(client_id, billing):
        return {"PREDICTIVE_MAINTENANCE": True}

    mock_db = _mock_db_for_queue([job, None])

    with patch("services.risk_signal_regen_queue.database.get_db", return_value=mock_db):
        with patch("services.ops_compliance_feature_flags.get_effective_flags", side_effect=gen_flags):
            with patch(
                "services.risk_signal_service.generate_risk_signals_for_property",
                new_callable=AsyncMock,
                return_value={"generated": 2, "previous_active_removed": 0},
            ):
                with patch(
                    "services.operational_automation_service.evaluate_operational_automation_after_risk_refresh",
                    new_callable=AsyncMock,
                ):
                    with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
                        out = await run_risk_signal_regen_worker(batch_limit=5)

    assert out["outcome_status"] == OUTCOME_SUCCESS
    assert out["outcome_metrics"]["regenerated_count"] == 1
    assert out["outcome_metrics"]["failed_count"] == 0
    assert out["outcome_metrics"]["outcome_kind"] == "WORK_PERFORMED"
    assert out["count"] == 1


@pytest.mark.asyncio
async def test_risk_regen_worker_failure_terminal_dead_outcome_failed_with_metrics():
    """attempts=4 → 5th failure marks queue row DEAD; job outcome remains OUTCOME_FAILED (no regens)."""
    job = _make_job(attempts=4)

    async def gen_flags(client_id, billing):
        return {"PREDICTIVE_MAINTENANCE": True}

    mock_db = _mock_db_for_queue([job, None])

    with patch("services.risk_signal_regen_queue.database.get_db", return_value=mock_db):
        with patch("services.ops_compliance_feature_flags.get_effective_flags", side_effect=gen_flags):
            with patch(
                "services.risk_signal_service.generate_risk_signals_for_property",
                new_callable=AsyncMock,
                side_effect=RuntimeError("boom"),
            ):
                with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
                    out = await run_risk_signal_regen_worker(batch_limit=5)

    assert out["outcome_status"] == OUTCOME_FAILED
    assert out["outcome_metrics"]["failed_count"] == 1
    assert out["outcome_metrics"]["regenerated_count"] == 0
    assert out["outcome_metrics"]["outcome_kind"] == "FAILED"
    assert out["count"] == 0
    mock_db.risk_signal_regen_queue.update_one.assert_awaited()
    call_kw = mock_db.risk_signal_regen_queue.update_one.await_args
    assert call_kw[0][1]["$set"]["status"] == "DEAD"


@pytest.mark.asyncio
async def test_risk_regen_worker_mixed_batch_degraded():
    j1 = _make_job("j1", "p1", "c1", 0)
    j2 = _make_job("j2", "p2", "c2", 0)

    calls = {"n": 0}

    async def foe(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return j1
        if calls["n"] == 2:
            return j2
        return None

    async def gen_flags(client_id, billing):
        return {"PREDICTIVE_MAINTENANCE": True}

    mock_db = MagicMock()
    coll = MagicMock()
    coll.update_many = AsyncMock(return_value=MagicMock(modified_count=0))
    coll.find_one_and_update = AsyncMock(side_effect=foe)
    coll.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
    coll.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.risk_signal_regen_queue = coll
    mock_db.properties = MagicMock()
    mock_db.properties.find_one = AsyncMock(
        side_effect=[
            {"client_id": "c1", "billing_plan": "PLAN_1_SOLO"},
            {"client_id": "c2", "billing_plan": "PLAN_1_SOLO"},
        ]
    )
    mock_db.clients = MagicMock()
    mock_db.clients.find_one = AsyncMock(return_value={"billing_plan": "PLAN_1_SOLO"})

    gen_mock = AsyncMock(side_effect=[{"generated": 1}, RuntimeError("second fails")])

    with patch("services.risk_signal_regen_queue.database.get_db", return_value=mock_db):
        with patch("services.ops_compliance_feature_flags.get_effective_flags", side_effect=gen_flags):
            with patch(
                "services.risk_signal_service.generate_risk_signals_for_property",
                gen_mock,
            ):
                with patch(
                    "services.operational_automation_service.evaluate_operational_automation_after_risk_refresh",
                    new_callable=AsyncMock,
                ):
                    with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
                        out = await run_risk_signal_regen_worker(batch_limit=5)

    assert out["outcome_status"] == OUTCOME_DEGRADED
    assert out["outcome_metrics"]["regenerated_count"] == 1
    assert out["outcome_metrics"]["failed_count"] == 1
    assert out["outcome_metrics"]["outcome_kind"] == "DEGRADED"
    assert out["count"] == 1


@pytest.mark.asyncio
async def test_risk_regen_worker_retry_path_still_updates_queue_on_transient_failure():
    """attempts < 5 → FAILED + backoff on queue row (existing behaviour)."""
    job = _make_job(attempts=0)

    async def gen_flags(client_id, billing):
        return {"PREDICTIVE_MAINTENANCE": True}

    mock_db = _mock_db_for_queue([job, None])

    with patch("services.risk_signal_regen_queue.database.get_db", return_value=mock_db):
        with patch("services.ops_compliance_feature_flags.get_effective_flags", side_effect=gen_flags):
            with patch(
                "services.risk_signal_service.generate_risk_signals_for_property",
                new_callable=AsyncMock,
                side_effect=ValueError("transient"),
            ):
                with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
                    out = await run_risk_signal_regen_worker(batch_limit=5)

    assert out["outcome_status"] == OUTCOME_FAILED
    assert out["outcome_metrics"]["failed_count"] == 1
    mock_db.risk_signal_regen_queue.update_one.assert_awaited()
    call_kw = mock_db.risk_signal_regen_queue.update_one.await_args
    assert call_kw[0][1]["$set"]["status"] == "FAILED"
