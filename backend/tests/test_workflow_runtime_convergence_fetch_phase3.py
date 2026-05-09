"""Phase 3: read-only compliance_recalc_queue fetch for convergence join (mocked DB)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from services.workflow_runtime_convergence_fetch import (
    build_recalc_joined_convergence_snapshot_from_db,
    fetch_recalc_jobs_for_convergence_join,
    normalize_correlation_hints,
)


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.compliance_recalc_queue = MagicMock()
    db.compliance_recalc_queue.insert_one = AsyncMock()
    db.compliance_recalc_queue.update_one = AsyncMock()
    db.compliance_recalc_queue.delete_one = AsyncMock()
    db.compliance_recalc_queue.replace_one = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_unbounded_scan_prevention(mock_db):
    out = await fetch_recalc_jobs_for_convergence_join(
        mock_db,
        status_in=["PENDING"],
        limit=50,
    )
    assert out["jobs"] == []
    assert out["diagnostics"]["skipped_unbounded_scan"] is True
    assert out["diagnostics"]["warning"] == "insufficient_filters_for_safe_query"
    mock_db.compliance_recalc_queue.find.assert_not_called()


@pytest.mark.asyncio
async def test_property_filter_invokes_find(mock_db):
    docs = [
        {"_id": "a", "property_id": "p1", "client_id": "c1", "correlation_id": "x", "status": "DONE"},
    ]
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=docs)
    mock_db.compliance_recalc_queue.find = MagicMock(return_value=cursor)

    out = await fetch_recalc_jobs_for_convergence_join(mock_db, property_id="p1", limit=10)
    assert len(out["jobs"]) == 1
    mock_db.compliance_recalc_queue.find.assert_called_once()
    call_query = mock_db.compliance_recalc_queue.find.call_args[0][0]
    assert call_query == {"property_id": "p1"}
    cursor.to_list.assert_called_once()
    mock_db.compliance_recalc_queue.insert_one.assert_not_called()
    mock_db.compliance_recalc_queue.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_correlation_hints_normalized_and_exact_in_query(mock_db):
    docs = [
        {"_id": "1", "property_id": "p1", "client_id": "c1", "correlation_id": "ROOT", "status": "PENDING"},
    ]
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=docs)
    mock_db.compliance_recalc_queue.find = MagicMock(return_value=cursor)

    out = await fetch_recalc_jobs_for_convergence_join(
        mock_db,
        property_id="p1",
        correlation_hints=["  ROOT  ", "ROOT", ""],
        limit=20,
    )
    assert len(out["jobs"]) == 1
    q = mock_db.compliance_recalc_queue.find.call_args[0][0]
    assert q["$and"][1]["correlation_id"]["$in"] == ["ROOT"]


@pytest.mark.asyncio
async def test_deterministic_sort_after_fetch(mock_db):
    docs = [
        {"_id": "b", "property_id": "p1", "client_id": "c1", "correlation_id": "B", "status": "DONE"},
        {"_id": "a", "property_id": "p1", "client_id": "c1", "correlation_id": "A", "status": "DONE"},
    ]
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=docs)
    mock_db.compliance_recalc_queue.find = MagicMock(return_value=cursor)

    out = await fetch_recalc_jobs_for_convergence_join(mock_db, property_id="p1", limit=50)
    assert [j["correlation_id"] for j in out["jobs"]] == ["A", "B"]


@pytest.mark.asyncio
async def test_limit_cap(mock_db):
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=[])
    mock_db.compliance_recalc_queue.find = MagicMock(return_value=cursor)

    out = await fetch_recalc_jobs_for_convergence_join(
        mock_db,
        property_id="p1",
        limit=99999,
        max_limit_cap=50,
    )
    assert out["diagnostics"]["limit"] == 50
    cursor.to_list.assert_called_once_with(length=51)


@pytest.mark.asyncio
async def test_truncated_diagnostics(mock_db):
    docs = [{"_id": str(i), "property_id": "p1", "client_id": "c1", "correlation_id": f"c{i}", "status": "DONE"} for i in range(3)]
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=docs)
    mock_db.compliance_recalc_queue.find = MagicMock(return_value=cursor)

    out = await fetch_recalc_jobs_for_convergence_join(mock_db, property_id="p1", limit=2)
    assert out["diagnostics"]["truncated"] is True
    assert out["diagnostics"]["matched_count"] is None
    assert out["diagnostics"]["matched_lower_bound"] == 3
    assert len(out["jobs"]) == 2


@pytest.mark.asyncio
async def test_bounded_time_window_meaningful(mock_db):
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=[])
    mock_db.compliance_recalc_queue.find = MagicMock(return_value=cursor)

    await fetch_recalc_jobs_for_convergence_join(
        mock_db,
        created_at_min="2026-01-01T00:00:00Z",
        created_at_max="2026-01-02T00:00:00Z",
        limit=10,
    )
    mock_db.compliance_recalc_queue.find.assert_called_once()


@pytest.mark.asyncio
async def test_integration_wrapper_attaches_diagnostics(mock_db):
    docs = [
        {"_id": "j1", "property_id": "p1", "client_id": "c1", "correlation_id": "x", "status": "DONE"},
    ]
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=docs)
    mock_db.compliance_recalc_queue.find = MagicMock(return_value=cursor)

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
    snap = await build_recalc_joined_convergence_snapshot_from_db(
        transition_traces=traces,
        generated_at_iso="2026-05-08T00:00:00Z",
        db=mock_db,
        property_id="p1",
        limit=50,
    )
    assert "fetch_diagnostics" in snap
    assert snap["fetch_diagnostics"].get("jobs_fetched") == 1
    assert snap["schema_version"] == "workflow_runtime_convergence_snapshot_joined_v2"


def test_normalize_correlation_hints_cap():
    hints = [f"h{i}" for i in range(50)]
    out = normalize_correlation_hints(hints, max_hints=5)
    assert len(out) == 5


def test_deterministic_sort_key_export():
    from services.workflow_runtime_convergence_observability import deterministic_recalc_job_sort_key

    a = deterministic_recalc_job_sort_key({"property_id": "p", "client_id": "c", "correlation_id": "x", "status": "S", "_id": "1"})
    b = deterministic_recalc_job_sort_key({"property_id": "p", "client_id": "c", "correlation_id": "y", "status": "S", "_id": "1"})
    assert a < b
