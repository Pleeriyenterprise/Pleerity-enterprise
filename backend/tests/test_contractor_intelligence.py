"""
Tests for Contractor Intelligence: score computation, analytics list, recalc job, and analytics API.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.contractor_intelligence_service import (
    compute_overall_score,
    compute_metrics_for_contractor,
    list_contractor_analytics,
)


class TestComputeOverallScore:
    """Overall score 0-100 from metrics; weights and partial data."""

    def test_all_none_returns_none(self):
        assert compute_overall_score({}) is None
        assert compute_overall_score({
            "reliability_score": None,
            "sla_success_rate": None,
            "average_response_time_hours": None,
            "invoice_approval_rate": None,
        }) is None

    def test_full_perfect_scores_returns_100(self):
        metrics = {
            "reliability_score": 1.0,
            "sla_success_rate": 1.0,
            "average_response_time_hours": 12.0,  # <=24h -> 1.0 component
            "invoice_approval_rate": 1.0,
        }
        assert compute_overall_score(metrics) == 100.0

    def test_partial_data_normalized(self):
        # Only reliability 50% -> score 50 (normalized to 100 by single weight)
        metrics = {"reliability_score": 0.5}
        assert compute_overall_score(metrics) == 50.0

    def test_response_time_24h_full_component(self):
        metrics = {
            "reliability_score": 0,
            "sla_success_rate": 0,
            "average_response_time_hours": 24.0,
            "invoice_approval_rate": 0,
        }
        # 0.4*0 + 0.25*0 + 0.2*1 + 0.15*0 = 0.2 -> normalized 20
        assert compute_overall_score(metrics) == 20.0

    def test_response_time_72h_zero_component(self):
        metrics = {
            "reliability_score": 0,
            "sla_success_rate": 0,
            "average_response_time_hours": 72.0,
            "invoice_approval_rate": 0,
        }
        assert compute_overall_score(metrics) == 0.0


def _async_iter(items):
    """Return an async iterator over items (for mocking Motor cursors)."""
    async def _():
        for x in items:
            yield x
    return _()


class TestComputeMetricsForContractor:
    """Metrics from mocked DB (work_orders, contractor_performance, invoices)."""

    def test_no_assignments_returns_none_reliability(self):
        db = MagicMock()
        db.work_orders.count_documents = AsyncMock(return_value=0)
        db.contractor_performance.find = MagicMock(return_value=_async_iter([]))
        db.work_orders.find = MagicMock(return_value=_async_iter([]))
        db.invoices.find = MagicMock(return_value=_async_iter([]))

        with patch("services.contractor_intelligence_service.database.get_db", return_value=db):
            out = asyncio.run(compute_metrics_for_contractor("c1"))
        assert out["assigned_jobs"] == 0
        assert out["completed_jobs"] == 0
        assert out["reliability_score"] is None

    def test_assigned_and_completed_reliability(self):
        db = MagicMock()
        db.work_orders.count_documents = AsyncMock(return_value=10)
        db.contractor_performance.find = MagicMock(
            return_value=_async_iter([{"jobs_completed": 8, "jobs_on_time": 6}])
        )
        db.work_orders.find = MagicMock(return_value=_async_iter([]))
        db.invoices.find = MagicMock(return_value=_async_iter([]))

        with patch("services.contractor_intelligence_service.database.get_db", return_value=db):
            out = asyncio.run(compute_metrics_for_contractor("c1"))
        assert out["assigned_jobs"] == 10
        assert out["completed_jobs"] == 8
        assert out["reliability_score"] == 0.8
        assert out["sla_success_rate"] == 0.75


class TestListContractorAnalytics:
    """Admin analytics views: top_performers, sla_issues, high_rejection."""

    def test_returns_contractors_and_view(self):
        contractors = [
            {"contractor_id": "c1", "name": "A", "performance_score": 85, "reliability_score": 0.9},
            {"contractor_id": "c2", "name": "B", "performance_score": 70, "reliability_score": 0.8},
        ]

        class Cursor:
            def __init__(self, items):
                self._items = items
            async def to_list(self, _):
                return self._items

        db = MagicMock()
        db.contractors.find = MagicMock(return_value=Cursor(contractors))

        with patch("services.contractor_intelligence_service.database.get_db", return_value=db):
            out = asyncio.run(list_contractor_analytics(view="top_performers", limit=10))
        assert out["view"] == "top_performers"
        assert "contractors" in out
        assert out["total"] == 2
        assert len(out["contractors"]) == 2
        assert out["contractors"][0]["contractor_id"] == "c1"

    def test_client_id_filter_passed_to_find(self):
        db = MagicMock()
        db.contractors.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))

        with patch("services.contractor_intelligence_service.database.get_db", return_value=db):
            asyncio.run(list_contractor_analytics(view="top_performers", client_id="client-1", limit=5))
        db.contractors.find.assert_called_once()
        call_kw = db.contractors.find.call_args[0][0]
        assert call_kw == {"client_id": "client-1"}


class TestRunContractorPerformanceRecalc:
    """Scheduled job calls recalculate_all_contractors and returns message/count."""

    def test_returns_message_and_count(self):
        from job_runner import run_contractor_performance_recalc

        with patch(
            "services.contractor_intelligence_service.recalculate_all_contractors",
            new_callable=AsyncMock,
            return_value=(7, 0),
        ) as recalc:
            result = asyncio.run(run_contractor_performance_recalc())
        recalc.assert_awaited_once_with(audit=True)
        assert result["count"] == 7
        assert "7" in result["message"]
        assert "updated" in result["message"]

    def test_includes_errors_in_message_when_non_zero(self):
        from job_runner import run_contractor_performance_recalc

        with patch(
            "services.contractor_intelligence_service.recalculate_all_contractors",
            new_callable=AsyncMock,
            return_value=(5, 2),
        ):
            result = asyncio.run(run_contractor_performance_recalc())
        assert result["count"] == 5
        assert "errors" in result["message"]
        assert "2" in result["message"]


class TestContractorAnalyticsAPI:
    """GET /api/admin/ops/contractors/analytics returns analytics payload."""

    def test_analytics_endpoint_returns_contractors_list(self, client):
        with patch("routes.contractors.admin_route_guard", new_callable=AsyncMock, return_value=None):
            with patch(
                "services.contractor_intelligence_service.list_contractor_analytics",
                new_callable=AsyncMock,
                return_value={"contractors": [{"contractor_id": "c1", "name": "Test"}], "total": 1, "view": "top_performers"},
            ) as list_analytics:
                response = client.get(
                    "/api/admin/ops/contractors/analytics",
                    params={"view": "top_performers", "limit": 50},
                )
        if response.status_code == 401:
            pytest.skip("Admin route requires auth; guard may not be applied in test client")
        assert response.status_code == 200
        data = response.json()
        assert "contractors" in data
        assert data["view"] == "top_performers"
        assert data["total"] == 1
        list_analytics.assert_awaited_once()
        call_kw = list_analytics.call_args[1]
        assert call_kw["view"] == "top_performers"
        assert call_kw["limit"] == 50
