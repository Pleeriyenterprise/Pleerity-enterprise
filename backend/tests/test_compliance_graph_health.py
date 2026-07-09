"""Tests for Compliance Graph Health service."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from services.compliance_graph_health.service import generate_health_report, generate_health_summary


@pytest.mark.asyncio
async def test_health_report_healthy_when_no_failures():
    validation_dict = {
        "valid": True,
        "failures": [],
        "warnings": [],
        "stats": {"decisions_examined": 5},
        "duration_ms": 12.5,
        "checks_run": 5,
    }
    mock_result = type(
        "R",
        (),
        {
            "to_dict": lambda self: validation_dict,
            "stats": {"decisions_examined": 5},
            "checks_run": 5,
            "duration_ms": 12.5,
            "failures": [],
            "warnings": [],
            "valid": True,
        },
    )()

    with patch(
        "services.compliance_graph_health.service.validate_graph",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        report = await generate_health_report(client_id="c1")
        assert report["overall_status"] == "healthy"
        assert report["service"] == "compliance_graph_health"
        assert report["producer_registry"]["live_emit_active_count"] == 0


@pytest.mark.asyncio
async def test_health_summary_returns_subset():
    with patch(
        "services.compliance_graph_health.service.generate_health_report",
        new_callable=AsyncMock,
        return_value={
            "service": "compliance_graph_health",
            "generated_at": "2026-01-01T00:00:00+00:00",
            "overall_status": "healthy",
            "summary": {"decisions_examined": 1},
            "metrics": {"integrity_failure_count": 0},
        },
    ):
        summary = await generate_health_summary()
        assert "overall_status" in summary
        assert "metrics" in summary
        assert "failures" not in summary
