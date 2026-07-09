"""Tests for Phase 2C P1 producers."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from services.compliance_evidence_graph.producers.bootstrap import initialize_p1_producers, initialize_p0_producers
from services.compliance_evidence_graph.producers.registry import ProducerContext, emit_for_mutation, get_registry_entry


@pytest.fixture(autouse=True)
def _reset_registry(monkeypatch):
    from services.compliance_evidence_graph.producers import bootstrap as boot
    from services.compliance_evidence_graph.producers import registry as reg

    reg._REGISTRY.clear()
    reg._HANDLERS.clear()
    boot._P0_INITIALIZED = False
    boot._P1_INITIALIZED = False
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "shadow")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    yield
    reg._REGISTRY.clear()
    reg._HANDLERS.clear()
    boot._P0_INITIALIZED = False
    boot._P1_INITIALIZED = False


@pytest.mark.asyncio
async def test_p1_registry_emit_implemented_after_bootstrap():
    initialize_p0_producers()
    initialize_p1_producers()
    entry = get_registry_entry("applicability_operator")
    assert entry is not None
    assert entry.emit_implemented is True
    assert entry.implementation_stage == "2C"


@pytest.mark.asyncio
async def test_applicability_operator_producer_emits():
    initialize_p0_producers()
    initialize_p1_producers()
    with patch(
        "services.compliance_evidence_graph.producers.applicability.emit_producer_decision",
        new_callable=AsyncMock,
        return_value=("dec_p1", "snap_p1"),
    ):
        ctx = ProducerContext(
            mutation_kind="applicability_operator",
            client_id="c1",
            source_collection="requirements",
            source_id="r1",
            requirement_id="r1",
            property_id="p1",
            authoritative_payload={
                "command": "MARK_REQUIRED",
                "pipeline_applicability_state": "REQUIRED",
                "effective_applicability_state": "REQUIRED",
            },
        )
        result = await emit_for_mutation(mutation_kind="applicability_operator", context=ctx)
        assert result == "dec_p1"


@pytest.mark.asyncio
async def test_risk_signal_generation_producer():
    initialize_p0_producers()
    initialize_p1_producers()
    with patch(
        "services.compliance_evidence_graph.producers.risk.emit_producer_decision",
        new_callable=AsyncMock,
        return_value=("dec_risk", "snap_risk"),
    ):
        from services.compliance_evidence_graph.producers.risk import handle_risk_signal_generation

        ctx = ProducerContext(
            mutation_kind="risk_signal_generation",
            client_id="c1",
            source_collection="risk_signals",
            source_id="p1",
            property_id="p1",
            authoritative_payload={"generated": 2, "signals": []},
        )
        assert await handle_risk_signal_generation(ctx) == "dec_risk"


@pytest.mark.asyncio
async def test_lineage_builder_marks_incomplete_without_refs():
    from services.compliance_evidence_graph.producers.lineage import build_rule_lineage_from_refs

    lineage = build_rule_lineage_from_refs({})
    assert lineage["lineage_incomplete"] is True
    assert "lineage_hash" in lineage
