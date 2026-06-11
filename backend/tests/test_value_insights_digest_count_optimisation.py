"""VALUE-INSIGHTS-DIGEST-COUNT-OPTIMISATION-01 — cached digest counts for value insights."""

from unittest.mock import AsyncMock, patch

import pytest

from services import operational_surface_cache as osc
from services.unified_tasks_service import resolve_value_insights_task_counts


@pytest.fixture(autouse=True)
def clear_operational_cache():
    osc._store.clear()
    yield
    osc._store.clear()


@pytest.mark.asyncio
async def test_resolve_counts_from_cached_digest():
    key = osc.unified_tasks_cache_key("vi-client", None, None, 60, "full")
    osc.set_cached_unified_tasks(
        key,
        {"summary": {"urgent_count": 12, "upcoming_count": 4}, "freshness": {}},
    )

    with patch(
        "services.unified_tasks_service.get_unified_tasks_digest",
        new=AsyncMock(),
    ) as digest_mock:
        out = await resolve_value_insights_task_counts("vi-client")

    assert out["urgent_count"] == 12
    assert out["upcoming_count"] == 4
    assert out["source_used"] == "cached_digest"
    assert out["fallback_reason"] is None
    assert out["duration_ms"] >= 0
    digest_mock.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_counts_from_command_center_summary():
    key = osc.command_center_primary_cache_key("vi-client", None)
    osc.set_cached_command_center_primary(
        key,
        {
            "tasks_digest_summary": {"urgent_count": 7, "upcoming_count": 2},
            "freshness": {},
        },
    )

    with patch(
        "services.unified_tasks_service.get_unified_tasks_digest",
        new=AsyncMock(),
    ) as digest_mock:
        out = await resolve_value_insights_task_counts("vi-client")

    assert out["urgent_count"] == 7
    assert out["upcoming_count"] == 2
    assert out["source_used"] == "command_center_summary"
    assert out["fallback_reason"] is None
    digest_mock.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_counts_prefers_cached_digest_over_command_center():
    ut_key = osc.unified_tasks_cache_key("vi-client", None, None, 60, "full")
    cc_key = osc.command_center_primary_cache_key("vi-client", None)
    osc.set_cached_unified_tasks(
        ut_key,
        {"summary": {"urgent_count": 10, "upcoming_count": 1}, "freshness": {}},
    )
    osc.set_cached_command_center_primary(
        cc_key,
        {
            "tasks_digest_summary": {"urgent_count": 99, "upcoming_count": 99},
            "freshness": {},
        },
    )

    with patch(
        "services.unified_tasks_service.get_unified_tasks_digest",
        new=AsyncMock(),
    ) as digest_mock:
        out = await resolve_value_insights_task_counts("vi-client")

    assert out["source_used"] == "cached_digest"
    assert out["urgent_count"] == 10
    digest_mock.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_counts_fallback_when_cache_empty():
    digest_mock = AsyncMock(
        return_value={
            "summary": {"urgent_count": 136, "upcoming_count": 10},
            "freshness": {"cache_hit": False},
        }
    )
    with patch(
        "services.unified_tasks_service.get_unified_tasks_digest",
        new=digest_mock,
    ):
        out = await resolve_value_insights_task_counts("vi-client")

    assert out["urgent_count"] == 136
    assert out["upcoming_count"] == 10
    assert out["source_used"] == "fallback_full_unified_tasks"
    assert out["fallback_reason"] == "no_cached_digest_or_command_center_summary"
    digest_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_command_center_summary_skipped_when_upcoming_missing():
    key = osc.command_center_primary_cache_key("vi-client", None)
    osc.set_cached_command_center_primary(
        key,
        {
            "tasks_digest_summary": {"urgent_count": 7, "upcoming_count": None},
            "freshness": {},
        },
    )
    digest_mock = AsyncMock(
        return_value={
            "summary": {"urgent_count": 3, "upcoming_count": 1},
            "freshness": {},
        }
    )
    with patch(
        "services.unified_tasks_service.get_unified_tasks_digest",
        new=digest_mock,
    ):
        out = await resolve_value_insights_task_counts("vi-client")

    assert out["source_used"] == "fallback_full_unified_tasks"
    digest_mock.assert_awaited_once()
