"""Tests for Phase 2D P2 producers and backfill."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from services.compliance_evidence_graph.producers.bootstrap import initialize_p2_producers, initialize_p0_producers, initialize_p1_producers
from services.compliance_evidence_graph.producers.registry import ProducerContext, emit_for_mutation, get_registry_entry
from services.compliance_evidence_graph.acceptance import evaluate_mutation_coverage


@pytest.fixture(autouse=True)
def _reset_registry(monkeypatch):
    from services.compliance_evidence_graph.producers import bootstrap as boot
    from services.compliance_evidence_graph.producers import registry as reg

    reg._REGISTRY.clear()
    reg._HANDLERS.clear()
    boot._P0_INITIALIZED = False
    boot._P1_INITIALIZED = False
    boot._P2_INITIALIZED = False
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "shadow")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    yield
    reg._REGISTRY.clear()
    reg._HANDLERS.clear()
    boot._P0_INITIALIZED = False
    boot._P1_INITIALIZED = False
    boot._P2_INITIALIZED = False


@pytest.mark.asyncio
async def test_p2_registry_implemented_after_bootstrap():
    initialize_p0_producers()
    initialize_p1_producers()
    initialize_p2_producers()
    entry = get_registry_entry("daily_reminder")
    assert entry is not None
    assert entry.emit_implemented is True
    assert entry.implementation_stage == "2D"


@pytest.mark.asyncio
async def test_daily_reminder_producer_emits():
    initialize_p0_producers()
    initialize_p1_producers()
    initialize_p2_producers()
    with patch(
        "services.compliance_evidence_graph.producers.reminder.emit_producer_decision",
        new_callable=AsyncMock,
        return_value=("dec_p2", "snap_p2"),
    ):
        ctx = ProducerContext(
            mutation_kind="daily_reminder",
            client_id="c1",
            source_collection="reminders",
            source_id="r1",
            authoritative_payload={"success_count": 3},
        )
        result = await emit_for_mutation(mutation_kind="daily_reminder", context=ctx)
        assert result == "dec_p2"


def test_acceptance_coverage_thresholds():
    from services.compliance_evidence_graph.producers.bootstrap import ensure_producers_initialized
    from services.compliance_evidence_graph.producers.registry import list_producer_registry

    ensure_producers_initialized()
    cov = evaluate_mutation_coverage(list_producer_registry())
    assert cov["p0"]["passed"] is True
    assert cov["p1"]["passed"] is True
    assert cov["p2"]["rate"] >= 0.95


@pytest.mark.asyncio
async def test_report_generation_producer_emits_with_artifact_dedupe():
    initialize_p0_producers()
    initialize_p1_producers()
    initialize_p2_producers()
    with patch(
        "services.compliance_evidence_graph.producers.score.emit_p0_decision",
        new_callable=AsyncMock,
        return_value=("dec_report", "snap_report"),
    ) as emit:
        ctx = ProducerContext(
            mutation_kind="report_generation",
            client_id="c1",
            source_collection="report_schedules",
            source_id="sched1:2026-06-28T12:00:00+00:00",
            correlation_id="REPORT:sched1:2026-06-28T12:00:00+00:00",
            mutation_timestamp="2026-06-28T12:00:00+00:00",
            authoritative_payload={
                "report_artifact_id": "sched1:2026-06-28T12:00:00+00:00",
                "report_type": "compliance_summary",
                "generated_at": "2026-06-28T12:00:00+00:00",
                "portfolio_scope": {"scope": "portfolio", "total_properties": 3},
            },
        )
        result = await emit_for_mutation(mutation_kind="report_generation", context=ctx)
        assert result == "dec_report"
        assert emit.await_args.kwargs["dedupe_key"]
        assert emit.await_args.kwargs["source_id"] == "sched1:2026-06-28T12:00:00+00:00"


@pytest.mark.asyncio
async def test_maintenance_issue_resolve_producer_emits():
    initialize_p0_producers()
    initialize_p1_producers()
    initialize_p2_producers()
    with patch(
        "services.compliance_evidence_graph.producers.work_order.emit_producer_decision",
        new_callable=AsyncMock,
        return_value=("dec_issue", "snap_issue"),
    ) as emit:
        ctx = ProducerContext(
            mutation_kind="maintenance_issue_lifecycle",
            client_id="c1",
            source_collection="maintenance_issues",
            source_id="iss1",
            property_id="p1",
            correlation_id="ISSUE:iss1:resolved:2026-06-28T12:00:00+00:00",
            mutation_timestamp="2026-06-28T12:00:00+00:00",
            authoritative_payload={
                "lifecycle": "resolved",
                "status": "resolved",
                "previous_status": "in_progress",
                "resolved_at": "2026-06-28T12:00:00+00:00",
                "work_order_id": "wo1",
            },
        )
        result = await emit_for_mutation(mutation_kind="maintenance_issue_lifecycle", context=ctx)
        assert result == "dec_issue"
        assert emit.await_args.kwargs["dedupe_key"]
        assert emit.await_args.kwargs["decision_outcome"] == "RESOLVED"
