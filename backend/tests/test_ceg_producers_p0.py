"""Tests for Phase 2B P0 producers."""
from __future__ import annotations

import os

import pytest
from unittest.mock import AsyncMock, patch

from services.compliance_evidence_graph.producers.bootstrap import initialize_p0_producers
from services.compliance_evidence_graph.producers.registry import ProducerContext, emit_for_mutation, get_registry_entry


@pytest.fixture(autouse=True)
def _reset_registry(monkeypatch):
    from services.compliance_evidence_graph.producers import bootstrap as boot
    from services.compliance_evidence_graph.producers import registry as reg

    reg._REGISTRY.clear()
    reg._HANDLERS.clear()
    boot._INITIALIZED = False
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "shadow")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    yield
    reg._REGISTRY.clear()
    reg._HANDLERS.clear()
    boot._INITIALIZED = False


@pytest.mark.asyncio
async def test_p0_registry_emit_implemented_after_bootstrap():
    initialize_p0_producers()
    entry = get_registry_entry("compliance_score_recalc")
    assert entry is not None
    assert entry.emit_implemented is True
    assert entry.status == "implemented"


@pytest.mark.asyncio
async def test_score_recalc_producer_emits_decision():
    initialize_p0_producers()
    with patch(
        "services.compliance_evidence_graph.producers.score.emit_p0_decision",
        new_callable=AsyncMock,
        return_value=("dec_test", "snap_test"),
    ), patch(
        "services.compliance_evidence_graph.producers.score.stamp_document",
        new_callable=AsyncMock,
    ):
        ctx = ProducerContext(
            mutation_kind="compliance_score_recalc",
            client_id="c1",
            source_collection="properties",
            source_id="p1",
            property_id="p1",
            correlation_id="corr-1",
            authoritative_payload={
                "previous_score": 70,
                "new_score": 80,
                "reason": "TEST",
                "history_created_at": "2026-01-01T00:00:00+00:00",
                "score_change_log_created_at": "2026-01-01T00:00:00+00:00",
            },
        )
        result = await emit_for_mutation(mutation_kind="compliance_score_recalc", context=ctx)
        assert result == "dec_test"


@pytest.mark.asyncio
async def test_dispatch_disabled_mode_returns_none(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "disabled")
    from services.compliance_evidence_graph.producers.hooks import dispatch_p0_producer

    ctx = ProducerContext(
        mutation_kind="compliance_score_recalc",
        client_id="c1",
        source_collection="properties",
        source_id="p1",
    )
    assert await dispatch_p0_producer(ctx) is None


@pytest.mark.asyncio
async def test_emit_idempotent_returns_same_decision():
    initialize_p0_producers()
    with patch(
        "services.compliance_evidence_graph.producers._emit.emit_compliance_decision",
        new_callable=AsyncMock,
        return_value="dec_dup",
    ) as mock_emit, patch(
        "services.compliance_evidence_graph.storage.decisions.get_decision",
        new_callable=AsyncMock,
        return_value={"decision_id": "dec_dup", "snapshot_id": "snap_dup"},
    ):
        from services.compliance_evidence_graph.producers.score import handle_compliance_score_recalc

        ctx = ProducerContext(
            mutation_kind="compliance_score_recalc",
            client_id="c1",
            source_collection="properties",
            source_id="p1",
            property_id="p1",
            correlation_id="corr-dup",
            authoritative_payload={"previous_score": 1, "new_score": 2, "reason": "R"},
        )
        r1 = await handle_compliance_score_recalc(ctx)
        r2 = await handle_compliance_score_recalc(ctx)
        assert r1 == "dec_dup"
        assert r2 == "dec_dup"
        assert mock_emit.call_count == 2
