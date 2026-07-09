"""Command Center fallback observability and operational value bundle performance."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest


def test_format_degraded_exception_includes_type_for_empty_timeout():
    from services.command_center_service import _format_degraded_exception

    assert _format_degraded_exception(asyncio.TimeoutError()) == "TimeoutError"


def test_classify_operational_value_timeout_as_service_failure():
    from services.command_center_service import (
        FALLBACK_CLASS_SERVICE_FAILURE,
        _classify_command_center_fallback,
    )

    assert (
        _classify_command_center_fallback(
            asyncio.TimeoutError(),
            section="operational_value_v1",
            properties_count=8,
            urgent_open_total=3,
        )
        == FALLBACK_CLASS_SERVICE_FAILURE
    )


def test_classify_empty_portfolio_as_expected_empty():
    from services.command_center_service import (
        FALLBACK_CLASS_EXPECTED_EMPTY,
        _classify_command_center_fallback,
    )

    assert (
        _classify_command_center_fallback(
            asyncio.TimeoutError(),
            section="primary_urgent_and_summary",
            properties_count=0,
            urgent_open_total=0,
        )
        == FALLBACK_CLASS_EXPECTED_EMPTY
    )


@pytest.mark.asyncio
async def test_operational_value_bundle_builds_sub_bundles_in_parallel():
    from services import operational_value_compression_service as ovcs

    calls: list[str] = []

    async def _slow(*_args, **kwargs):
        name = kwargs.get("builder_path") or "x"
        await asyncio.sleep(0.05)
        calls.append(name)
        return {"available": True, "programme": name}

    with patch.object(
        ovcs,
        "asyncio_gather_bundle",
        new=AsyncMock(return_value=({"groups": []}, {}, {})),
    ), patch.object(
        ovcs,
        "_build_optional_operational_sub_bundle",
        side_effect=_slow,
    ):
        t0 = asyncio.get_event_loop().time()
        await ovcs.build_operational_value_bundle_v1("client_parallel")
        elapsed = asyncio.get_event_loop().time() - t0

    assert len(calls) == 4
    assert elapsed < 0.25


@pytest.mark.asyncio
async def test_primary_bundle_surfaces_timeout_classification_on_operational_value_failure():
    from services.command_center_service import (
        FALLBACK_CLASS_SERVICE_FAILURE,
        get_command_center_primary_bundle,
    )

    urgent_slice = {
        "urgent_actions": [{"id": "wo:1", "title": "Job"}],
        "urgent_open_total": 1,
        "urgent_continuation": 0,
        "freshness": {"tasks_refreshed_at": "2026-01-01T00:00:00Z"},
    }
    compliance = {
        "score": None,
        "properties_count": 8,
        "requirements_total": 10,
        "score_status": "ok",
    }

    async def _timeout(*_a, **_k):
        await asyncio.sleep(0)
        raise asyncio.TimeoutError()

    with patch(
        "services.command_center_service._load_urgent_slice_from_priority_stream",
        new=AsyncMock(return_value=urgent_slice),
    ), patch(
        "services.command_center_service._primary_compliance_status_summary",
        new=AsyncMock(return_value=compliance),
    ), patch(
        "services.operational_value_compression_service.build_operational_value_bundle_v1",
        new=AsyncMock(side_effect=_timeout),
    ):
        out = await get_command_center_primary_bundle("client-1", predictive_enabled=False)

    assert out["pressure_degraded"] is True
    assert out["pressure_fallback_classification"] == FALLBACK_CLASS_SERVICE_FAILURE
    assert out["pressure_fallback_reason"].startswith("primary_timeout_or_failure:TimeoutError")
    assert out["operational_value_v1"]["error"] == "TimeoutError"
