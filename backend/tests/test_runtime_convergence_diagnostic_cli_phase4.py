"""Phase 4: ops-only runtime convergence diagnostic CLI (mocked DB, no live Mongo)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.runtime_convergence_diagnostic import (
    CLI_HARD_MAX_LIMIT,
    _parse_args,
    _cli_scope_meaningful,
    run_diagnostic,
)


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.compliance_recalc_queue = MagicMock()
    db.compliance_recalc_queue.insert_one = AsyncMock()
    db.compliance_recalc_queue.update_one = AsyncMock()
    db.compliance_recalc_queue.delete_one = AsyncMock()
    db.properties = MagicMock()
    db.properties.update_one = AsyncMock()
    return db


def _queue_cursor(items):
    c = MagicMock()
    c.to_list = AsyncMock(side_effect=lambda length=None: list(items)[: length if length is not None else len(items)])
    return c


@pytest.mark.asyncio
async def test_insufficient_scope_exit(mock_db):
    code, out = await run_diagnostic(
        time_window_hours=24,
        connect_database=False,
        db=mock_db,
        output_format="json",
    )
    assert code == 2
    assert "Insufficient scope" in out or "insufficient" in out.lower()
    mock_db.compliance_recalc_queue.find.assert_not_called()


@pytest.mark.asyncio
async def test_bounded_limit_cap(mock_db):
    jobs = [
        {"_id": "1", "property_id": "p1", "client_id": "c1", "correlation_id": "a", "status": "DONE"},
    ]
    cursor = _queue_cursor(jobs)
    mock_db.compliance_recalc_queue.find = MagicMock(return_value=cursor)
    mock_db.properties.find_one = AsyncMock(return_value=None)

    code, _out = await run_diagnostic(
        property_id="p1",
        limit=99999,
        connect_database=False,
        db=mock_db,
        generated_at_iso="2026-05-08T12:00:00Z",
    )
    assert code == 0
    mock_db.compliance_recalc_queue.find.assert_called_once()
    call = mock_db.compliance_recalc_queue.find.call_args[0][0]
    assert call == {"property_id": "p1"}
    cursor.to_list.assert_awaited()
    assert cursor.to_list.await_args.kwargs.get("length") == CLI_HARD_MAX_LIMIT + 1


@pytest.mark.asyncio
async def test_correlation_repeatable_normalized_in_query(mock_db):
    mock_db.compliance_recalc_queue.find = MagicMock(return_value=_queue_cursor([]))
    mock_db.properties.find_one = AsyncMock(return_value=None)

    await run_diagnostic(
        property_id="p1",
        correlation_ids=["  a  ", "a", "b"],
        connect_database=False,
        db=mock_db,
        generated_at_iso="2026-05-08T12:00:00Z",
    )
    q = mock_db.compliance_recalc_queue.find.call_args[0][0]
    assert "$and" in q
    corr_part = next(p for p in q["$and"] if "correlation_id" in p)
    assert corr_part["correlation_id"]["$in"] == ["a", "b"]


@pytest.mark.asyncio
async def test_json_output_determinism(mock_db):
    mock_db.compliance_recalc_queue.find = MagicMock(return_value=_queue_cursor([]))
    mock_db.properties.find_one = AsyncMock(
        return_value={
            "property_id": "p1",
            "client_id": "c1",
            "compliance_last_calculated_at": "2026-01-01T00:00:00Z",
            "compliance_score_pending": False,
        }
    )

    _, out = await run_diagnostic(
        property_id="p1",
        connect_database=False,
        db=mock_db,
        output_format="json",
        generated_at_iso="2026-05-08T12:00:00Z",
    )
    j1 = json.loads(out)
    _, out2 = await run_diagnostic(
        property_id="p1",
        connect_database=False,
        db=mock_db,
        output_format="json",
        generated_at_iso="2026-05-08T12:00:00Z",
    )
    j2 = json.loads(out2)
    assert j1 == j2
    assert j1["freshness_enrichment"]["compliance_score_pending"] is False


@pytest.mark.asyncio
async def test_summary_output_stable_lines(mock_db):
    mock_db.compliance_recalc_queue.find = MagicMock(return_value=_queue_cursor([]))
    mock_db.properties.find_one = AsyncMock(return_value=None)

    _, s1 = await run_diagnostic(
        property_id="p1",
        connect_database=False,
        db=mock_db,
        output_format="summary",
        generated_at_iso="2026-05-08T12:00:00Z",
    )
    _, s2 = await run_diagnostic(
        property_id="p1",
        connect_database=False,
        db=mock_db,
        output_format="summary",
        generated_at_iso="2026-05-08T12:00:00Z",
    )
    assert s1 == s2
    assert "runtime convergence diagnostic (summary)" in s1


@pytest.mark.asyncio
async def test_no_writes_on_queue(mock_db):
    mock_db.compliance_recalc_queue.find = MagicMock(return_value=_queue_cursor([]))
    mock_db.properties.find_one = AsyncMock(return_value=None)

    await run_diagnostic(property_id="p1", connect_database=False, db=mock_db)
    mock_db.compliance_recalc_queue.insert_one.assert_not_called()
    mock_db.compliance_recalc_queue.update_one.assert_not_called()
    mock_db.compliance_recalc_queue.delete_one.assert_not_called()


@pytest.mark.asyncio
async def test_helpers_invoked_via_run(mock_db):
    jobs = [
        {"_id": "1", "property_id": "p1", "client_id": "c1", "correlation_id": "x", "status": "DONE"},
    ]
    mock_db.compliance_recalc_queue.find = MagicMock(return_value=_queue_cursor(jobs))
    mock_db.properties.find_one = AsyncMock(return_value=None)
    traces = [
        {
            "correlation_id": "x",
            "property_id": "p1",
            "client_id": "c1",
            "requirement_id": "r1",
            "transition_origin": "OUTCOME_ENGINE_SYNC:t",
            "transition_outcome": "TRANSITION_APPLIED",
            "downstream_trigger_targets": [],
            "downstream_propagation": [
                {
                    "downstream_target": "compliance_gap_sync.sync_compliance_gaps_for_requirement",
                    "propagation_degraded_possible": False,
                }
            ],
            "partial_downstream_failure": False,
        }
    ]
    with patch(
        "services.workflow_runtime_convergence_fetch.fetch_recalc_jobs_for_convergence_join",
        new_callable=AsyncMock,
    ) as m_fetch:
        with patch(
            "services.workflow_runtime_convergence_fetch.build_recalc_joined_convergence_snapshot_from_db",
            new_callable=AsyncMock,
        ) as m_join:
            m_fetch.return_value = {"jobs": jobs, "diagnostics": {"limit": 50, "truncated": False, "skipped_unbounded_scan": False}}
            m_join.return_value = {
                "schema_version": "workflow_runtime_convergence_snapshot_joined_v2",
                "joined_rows": [],
                "recalc_convergence_summary": {},
                "fetch_diagnostics": {},
            }
            with patch(
                "services.workflow_runtime_convergence_observability.build_runtime_convergence_snapshot",
                MagicMock(return_value={}),
            ):
                with patch(
                    "services.workflow_runtime_convergence_observability.build_convergence_join_operational_summary",
                    MagicMock(return_value={}),
                ):
                    await run_diagnostic(
                        property_id="p1",
                        connect_database=False,
                        db=mock_db,
                        traces_json_path=None,
                    )
            m_fetch.assert_awaited_once()
            m_join.assert_awaited_once()
            call_kw = m_join.await_args[1]
            assert call_kw.get("fetch_result") is m_fetch.return_value


def test_parse_args_correlation_append():
    ns = _parse_args(["--property-id", "p", "--correlation-id", "a", "--correlation-id", "b"])
    assert ns.correlation_ids == ["a", "b"]


def test_cli_scope_meaningful():
    assert _cli_scope_meaningful(property_id=None, client_id="c", correlation_ids=None) is True
    assert _cli_scope_meaningful(property_id=None, client_id=None, correlation_ids=["x"]) is True
    assert _cli_scope_meaningful(property_id=None, client_id=None, correlation_ids=None) is False


@pytest.mark.asyncio
async def test_traces_json_load(tmp_path: Path, mock_db):
    mock_db.compliance_recalc_queue.find = MagicMock(return_value=_queue_cursor([]))
    mock_db.properties.find_one = AsyncMock(return_value=None)
    p = tmp_path / "t.json"
    p.write_text(
        json.dumps(
            [
                {
                    "correlation_id": "c1",
                    "property_id": "p1",
                    "client_id": "cl",
                    "requirement_id": "r1",
                    "transition_origin": "test",
                    "transition_outcome": "TRANSITION_APPLIED",
                    "downstream_trigger_targets": [],
                    "downstream_propagation": [],
                    "partial_downstream_failure": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    _, out = await run_diagnostic(
        property_id="p1",
        traces_json_path=str(p),
        connect_database=False,
        db=mock_db,
        output_format="json",
        generated_at_iso="2026-05-08T12:00:00Z",
    )
    assert json.loads(out)["transition_trace_count"] == 1


@pytest.mark.asyncio
async def test_from_db_reuses_fetch_result(mock_db):
    from services.workflow_runtime_convergence_fetch import build_recalc_joined_convergence_snapshot_from_db

    fr = {"jobs": [], "diagnostics": {"limit": 10, "truncated": False, "skipped_unbounded_scan": False}}
    with patch(
        "services.workflow_runtime_convergence_fetch.fetch_recalc_jobs_for_convergence_join",
        new_callable=AsyncMock,
    ) as m_f:
        await build_recalc_joined_convergence_snapshot_from_db(
            transition_traces=[],
            generated_at_iso="2026-05-08T12:00:00Z",
            db=mock_db,
            fetch_result=fr,
            property_id="should_not_query",
        )
        m_f.assert_not_called()
