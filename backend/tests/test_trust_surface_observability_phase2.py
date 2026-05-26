"""Trust surface observability (Command Centre, Today/unified tasks, portfolio summary)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.trust_surface_observability import (
    SECTION_STATUS_DEGRADED_FALLBACK,
    SECTION_STATUS_HEALTHY_EMPTY,
    SURFACE_COMMAND_CENTER_REFRESH,
    SURFACE_PORTFOLIO_SUMMARY_REFRESH,
    build_command_center_health_summary,
    build_portfolio_summary_trust_surface_metadata,
    build_trust_surface_operational_snapshot,
    build_trust_surface_section_record,
    ensure_trust_surface_correlation_id,
    normalize_trust_surface_context,
)


def test_ensure_trust_surface_correlation_id_stable_explicit():
    assert (
        ensure_trust_surface_correlation_id(SURFACE_COMMAND_CENTER_REFRESH, "c1", "  abc  ")
        == "abc"
    )


def test_ensure_trust_surface_correlation_id_generates():
    cid = ensure_trust_surface_correlation_id(SURFACE_PORTFOLIO_SUMMARY_REFRESH, "c1", None)
    assert cid.startswith(f"{SURFACE_PORTFOLIO_SUMMARY_REFRESH}:c1:")


def test_normalize_trust_surface_context():
    ctx = normalize_trust_surface_context(
        surface_name=SURFACE_COMMAND_CENTER_REFRESH,
        client_id="c1",
        correlation_id="x",
        property_id_filter="p9",
    )
    assert ctx["correlation_id"] == "x"
    assert ctx["property_id_filter"] == "p9"


def test_build_trust_surface_section_record_determinism():
    a = build_trust_surface_section_record(
        section_name="z",
        section_status=SECTION_STATUS_HEALTHY_EMPTY,
        correlation_id="c",
    )
    b = build_trust_surface_section_record(
        section_name="z",
        section_status=SECTION_STATUS_HEALTHY_EMPTY,
        correlation_id="c",
    )
    assert a == b


def test_portfolio_trust_metadata_gap_and_stale():
    meta = build_portfolio_summary_trust_surface_metadata(
        client_id="c1",
        correlation_id="corr-1",
        gap_engine_unavailable=True,
        headline={
            "score_status": "stale",
            "unknown_or_stale_property_count": 2,
            "portfolio_score": 50,
            "portfolio_last_calculated_at": "2019-01-01T00:00:00+00:00",
        },
        gap_error=RuntimeError("boom"),
    )
    assert meta["correlation_id"] == "corr-1"
    assert any(s["section_name"] == "gap_engine_aggregate" for s in meta["partial_sections"])
    assert any(s["section_status"] == SECTION_STATUS_DEGRADED_FALLBACK for s in meta["partial_sections"])
    assert any(s["section_name"] == "persisted_portfolio_headline" for s in meta["stale_sections"])
    h = build_command_center_health_summary(meta)
    assert h["partial_section_count"] >= 1
    assert h["stale_section_count"] >= 1


def test_operational_snapshot_determinism():
    m1 = {
        "surface_name": "X",
        "correlation_id": "1",
        "degraded_sections": [],
        "stale_sections": [],
        "partial_sections": [],
        "failed_sections": [],
        "omitted_sections": [],
    }
    snap = build_trust_surface_operational_snapshot(
        surfaces={"A": m1, "B": dict(m1, surface_name="Y", correlation_id="2")},
        generated_at_iso="2020-01-01T00:00:00+00:00",
    )
    snap2 = build_trust_surface_operational_snapshot(
        surfaces={"A": m1, "B": dict(m1, surface_name="Y", correlation_id="2")},
        generated_at_iso="2020-01-01T00:00:00+00:00",
    )
    assert snap == snap2
    assert list(snap["surfaces"].keys()) == ["A", "B"]


@pytest.mark.asyncio
async def test_command_center_bundle_includes_trust_metadata():
    from services import command_center_service as ccs

    digest = {
        "summary": {"urgent_count": 0},
        "freshness": {"tasks_refreshed_at": "2024-01-01T00:00:00+00:00"},
        "activity_feed": [],
    }
    full_tasks = {
        "tasks": {"urgent": [], "in_progress": [], "upcoming": []},
        "summary": {"urgent_count": 0, "upcoming_count": 0, "in_progress_count": 0},
        "freshness": digest["freshness"],
        "activity_feed": [],
    }

    async def fake_calculate(client_id: str):
        return {
            "score": 80,
            "grade": "A",
            "message": "ok",
            "color": "green",
            "properties_count": 1,
            "score_authority": "persisted",
            "score_status": "ok",
            "stats": {},
            "jurisdiction_compliance_notice": {},
            "jurisdiction_required_property_ids": [],
            "jurisdiction_required": False,
            "compliance_confidence": "explicit",
        }

    async def fake_gap(db, cid, prop=None):
        return {"by_kind": {}, "by_severity": {}, "total_open": 0}

    async def fake_hiua(db, cid, **kwargs):
        return {
            "hiua_active": False,
            "hiua_open_gap_count": 0,
            "hiua_reason_codes": [],
            "hiua_gap_details": [],
            "hiua_command_centre_message": None,
            "hiua_command_centre_tooltip": None,
            "hiua_command_centre_filter_label": None,
            "hiua_digest_line": None,
            "hiua_report_framing_notice": None,
        }

    import services.compliance_score as cs_mod
    import services.compliance_gap_sync as gap_mod
    import services.hiua_operational_uncertainty as hiua_mod

    with patch.object(cs_mod, "calculate_compliance_score", new=fake_calculate), patch.object(
        gap_mod, "aggregate_gap_counts_for_client", new=fake_gap
    ), patch.object(hiua_mod, "hiua_tenant_operational_summary", new=fake_hiua), patch.object(
        ccs, "get_unified_tasks_for_client", new=AsyncMock(return_value=full_tasks)
    ), patch.object(
        ccs.risk_signal_service, "get_risk_signals_for_client", new=AsyncMock(return_value={"signals": []})
    ):
        bundle = await ccs.get_command_center_bundle("cc-test", predictive_enabled=False, correlation_id="fixed")
        assert bundle["trust_surface_operational_metadata"]["correlation_id"] == "fixed"
        assert bundle["trust_surface_operational_metadata"]["surface_name"] == SURFACE_COMMAND_CENTER_REFRESH
        assert "operational_health" in bundle["trust_surface_operational_metadata"]


@pytest.mark.asyncio
async def test_command_center_digest_failure_records_failed_section():
    from services import command_center_service as ccs

    async def boom_unified(*_a, **_k):
        raise RuntimeError("unified tasks down")

    full_tasks = {
        "tasks": {"urgent": [], "in_progress": [], "upcoming": []},
        "summary": {"urgent_count": 0, "upcoming_count": 0, "in_progress_count": 0},
        "freshness": {},
        "activity_feed": [],
    }

    async def fake_calculate(client_id: str):
        return {
            "score": None,
            "grade": None,
            "message": "x",
            "color": "gray",
            "properties_count": 0,
            "score_authority": "unavailable",
            "score_status": "unavailable",
            "stats": {},
            "jurisdiction_compliance_notice": {},
            "jurisdiction_required_property_ids": [],
            "jurisdiction_required": False,
            "compliance_confidence": None,
        }

    async def fake_gap(db, cid, prop=None):
        return {"by_kind": {}, "by_severity": {}, "total_open": 0}

    async def fake_hiua(db, cid, **kwargs):
        return {
            "hiua_active": False,
            "hiua_open_gap_count": 0,
            "hiua_reason_codes": [],
            "hiua_gap_details": [],
            "hiua_command_centre_message": None,
            "hiua_command_centre_tooltip": None,
            "hiua_command_centre_filter_label": None,
            "hiua_digest_line": None,
            "hiua_report_framing_notice": None,
        }

    import services.compliance_score as cs_mod
    import services.compliance_gap_sync as gap_mod
    import services.hiua_operational_uncertainty as hiua_mod

    with patch.object(cs_mod, "calculate_compliance_score", new=fake_calculate), patch.object(
        gap_mod, "aggregate_gap_counts_for_client", new=fake_gap
    ), patch.object(hiua_mod, "hiua_tenant_operational_summary", new=fake_hiua), patch.object(
        ccs, "get_unified_tasks_for_client", new=boom_unified
    ), patch.object(
        ccs.risk_signal_service, "get_risk_signals_for_client", new=AsyncMock(return_value={"signals": []})
    ):
        bundle = await ccs.get_command_center_bundle("cc-test", predictive_enabled=False)
        failed = bundle["trust_surface_operational_metadata"]["failed_sections"]
        assert any(s.get("section_name") == "unified_tasks_urgent_actions" for s in failed)


@pytest.mark.asyncio
async def test_unified_tasks_includes_metadata_when_context_passed():
    from services import unified_tasks_service as uts

    ctx = normalize_trust_surface_context(
        surface_name="TODAY_TASK_REBUILD",
        client_id="c1",
        correlation_id="tid-1",
    )
    with patch.object(uts, "fetch_client_priority_actions", new=AsyncMock(return_value=[])), patch.object(
        uts, "_tenant_message_tasks", new=AsyncMock(return_value=[])
    ), patch.object(uts, "_tenant_request_tasks", new=AsyncMock(return_value=[])), patch.object(
        uts, "_enforce_canonical_requirement_task_guard", new=AsyncMock(side_effect=lambda **k: k["tasks"])
    ), patch.object(uts.client_task_state, "load_active_overrides", new=AsyncMock(return_value=[])), patch.object(
        uts.client_task_state, "partition_tasks_by_override", return_value=([], [])
    ), patch.object(uts.client_task_state, "list_recent_activity", new=AsyncMock(return_value=[])), patch.object(
        uts.client_task_state, "merge_user_acknowledgements_into_recent", return_value=[]
    ), patch.object(uts.client_task_state, "count_activity_since", new=AsyncMock(return_value=0)), patch.object(
        uts.client_task_state, "list_hidden_inbox_items", new=AsyncMock(return_value=[])
    ), patch.object(uts, "_recently_completed_tasks", new=AsyncMock(return_value=[])), patch.object(
        uts, "_freshness_block", new=AsyncMock(return_value={"tasks_refreshed_at": "2025-01-01T00:00:00+00:00"})
    ):
        out = await uts.get_unified_tasks_for_client("c1", trust_surface_composition_context=ctx)
        assert "trust_surface_operational_metadata" in out
        assert out["trust_surface_operational_metadata"]["correlation_id"] == "tid-1"
