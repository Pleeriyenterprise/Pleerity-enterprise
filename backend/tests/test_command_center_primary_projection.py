"""Command Centre primary projection — fast path without full unified rebuild."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_primary_bundle_skips_full_unified_and_marks_deferred():
    from services.command_center_service import get_command_center_primary_bundle

    urgent_slice = {
        "urgent_actions": [{"id": "requirement:r1", "title": "Overdue gas"}],
        "urgent_open_total": 3,
        "urgent_continuation": 2,
        "freshness": {"tasks_refreshed_at": "2026-01-01T00:00:00Z"},
    }
    compliance = {
        "score": 72,
        "grade": "C",
        "score_status": "current",
        "stats": {"overdue": 1},
        "gap_engine": {"total_open": 1},
        "hiua_operational_uncertainty": {"_deferred": True},
    }

    with patch(
        "services.command_center_service._load_urgent_slice_from_priority_stream",
        new_callable=AsyncMock,
        return_value=urgent_slice,
    ), patch(
        "services.command_center_service._primary_compliance_status_summary",
        new_callable=AsyncMock,
        return_value=compliance,
    ), patch(
        "services.unified_tasks_service.get_unified_tasks_for_client",
        new_callable=AsyncMock,
    ) as unified_mock:
        out = await get_command_center_primary_bundle(
            "client-1",
            predictive_enabled=True,
        )

    unified_mock.assert_not_called()
    assert out.get("projection") == "primary"
    assert out.get("primary_complete") is True
    assert out.get("secondary_sections_deferred") is True
    assert len(out.get("urgent_actions") or []) == 1
    assert out["tasks_digest_summary"]["urgent_count"] == 3
    assert out["tasks_digest_summary"]["urgent_continuation"] == 2
    assert out["compliance_status_summary"]["hiua_operational_uncertainty"]["_deferred"] is True


@pytest.mark.asyncio
async def test_primary_bundle_degraded_pressure_uses_urgent_rows_without_false_calm():
    from services.command_center_service import get_command_center_primary_bundle

    urgent_slice = {
        "urgent_actions": [{"id": "requirement:r1", "title": "Overdue gas"}],
        "urgent_open_total": 1,
        "urgent_continuation": 0,
        "freshness": {"tasks_refreshed_at": "2026-01-01T00:00:00Z"},
    }
    compliance = {
        "score": 72,
        "grade": "C",
        "score_status": "current",
        "stats": {"overdue": 1, "missing_evidence": 0},
        "gap_engine": {"total_open": 1},
        "hiua_operational_uncertainty": {"_deferred": True},
        "requirements_overdue": 1,
        "requirements_missing_evidence": 0,
        "properties_at_risk_count": 1,
    }

    with patch(
        "services.command_center_service._load_urgent_slice_from_priority_stream",
        new_callable=AsyncMock,
        return_value=urgent_slice,
    ), patch(
        "services.command_center_service._primary_compliance_status_summary",
        new_callable=AsyncMock,
        return_value=compliance,
    ), patch(
        "services.operational_value_compression_service.build_operational_value_bundle_v1",
        new_callable=AsyncMock,
        side_effect=TypeError("unexpected keyword argument"),
    ):
        out = await get_command_center_primary_bundle(
            "client-1",
            predictive_enabled=True,
            bypass_cache=True,
        )

    assert out.get("pressure_degraded") is True
    assert out.get("pressure_status") == "degraded"
    assert out.get("pressure_fallback_reason")
    assert out.get("pressure_urgent_count", 0) > 0
    assert len(out.get("pressure_urgent_rows") or []) > 0
    assert out.get("pressure_urgent_rows") == out.get("urgent_actions")
