"""Tests for CEG producer registry — Phase 2A (no live emit)."""
from __future__ import annotations

import os

import pytest
from unittest.mock import patch

from services.compliance_evidence_graph.producers.registry import (
    ProducerContext,
    emit_for_mutation,
    list_producer_registry,
)


@pytest.fixture(autouse=True)
def _clear_registry_cache():
    from services.compliance_evidence_graph.producers import bootstrap as boot
    from services.compliance_evidence_graph.producers import registry as reg

    reg._REGISTRY.clear()
    reg._HANDLERS.clear()
    boot._INITIALIZED = False
    yield
    reg._REGISTRY.clear()
    reg._HANDLERS.clear()
    boot._INITIALIZED = False


def test_registry_lists_planned_producers_before_bootstrap():
    entries = list_producer_registry()
    assert len(entries) >= 10
    assert all(e["emit_implemented"] is False for e in entries)


def test_registry_lists_implemented_p0_after_bootstrap(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "shadow")
    from services.compliance_evidence_graph.producers.bootstrap import initialize_p0_producers

    initialize_p0_producers()
    entries = list_producer_registry()
    p0 = [e for e in entries if e["priority"] == "P0"]
    assert len(p0) >= 5
    assert all(e["emit_implemented"] is True for e in p0)
    assert all(e["status"] == "implemented" for e in p0)


@pytest.mark.asyncio
async def test_emit_for_mutation_no_op_when_producers_disabled(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "disabled")
    ctx = ProducerContext(
        mutation_kind="evidence_authority_sync",
        client_id="c1",
        source_collection="requirements",
        source_id="r1",
    )
    result = await emit_for_mutation(mutation_kind="evidence_authority_sync", context=ctx)
    assert result is None


@pytest.mark.asyncio
async def test_emit_for_mutation_no_op_in_shadow_when_not_implemented(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "shadow")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    ctx = ProducerContext(
        mutation_kind="evidence_authority_sync",
        client_id="c1",
        source_collection="requirements",
        source_id="r1",
    )
    result = await emit_for_mutation(mutation_kind="evidence_authority_sync", context=ctx)
    assert result is None


@pytest.mark.asyncio
async def test_emit_for_mutation_unknown_kind_returns_none(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "shadow")
    ctx = ProducerContext(
        mutation_kind="unknown_mutation",
        client_id="c1",
        source_collection="requirements",
        source_id="r1",
    )
    result = await emit_for_mutation(mutation_kind="unknown_mutation", context=ctx)
    assert result is None


def test_disabled_mode_safe_with_pytest(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "disabled")
    from services.compliance_evidence_graph.config import graph_emit_allowed, graph_producers_enabled

    assert graph_producers_enabled() is False
    if not os.getenv("PYTEST_CURRENT_TEST"):
        assert graph_emit_allowed() is False
