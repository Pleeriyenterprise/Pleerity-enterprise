"""Grouped outcome metrics for Control Centre (mixed-unit safety)."""
import pytest

from services.control_centre_outcome_aggregation import summarize_outcome_metrics_24h_by_family


@pytest.mark.asyncio
async def test_summarize_buckets_queue_and_monitoring_separately():
    rows = [
        {
            "_id": "compliance_recalc_worker",
            "finished_runs": 2,
            "outcome_success_sum": 5,
            "outcome_failed_sum": 1,
            "outcome_attempted_sum": 6,
        },
        {
            "_id": "scheduler_heartbeat",
            "finished_runs": 10,
            "outcome_success_sum": 10,
            "outcome_failed_sum": 0,
            "outcome_attempted_sum": 10,
        },
    ]

    class _Agg:
        def __init__(self, data):
            self._data = data

        async def to_list(self, _n):
            return self._data

    class _Coll:
        def __init__(self, data):
            self._data = data

        def aggregate(self, _pipeline):
            return _Agg(self._data)

    class _Db:
        job_runs = _Coll(rows)

    out = await summarize_outcome_metrics_24h_by_family(_Db(), "2026-01-01T00:00:00+00:00")
    by_key = {r["family_key"]: r for r in out}
    assert "queue_processing" in by_key
    assert by_key["queue_processing"]["outcome_success_sum"] == 5
    assert "monitoring_and_watchdog" in by_key
    assert by_key["monitoring_and_watchdog"]["finished_runs"] == 10


@pytest.mark.asyncio
async def test_summarize_empty_aggregate():
    class _Agg:
        async def to_list(self, _n):
            return []

    class _Coll:
        def aggregate(self, _pipeline):
            return _Agg()

    class _Db:
        job_runs = _Coll()

    out = await summarize_outcome_metrics_24h_by_family(_Db(), "2026-01-01T00:00:00+00:00")
    assert out == []
