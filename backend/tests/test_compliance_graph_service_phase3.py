"""Phase 3 Graph Service — trace, impact, list, consumer adapter tests."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from services.compliance_graph_service.access import ActorContext
from services.compliance_graph_service import service as graph_service
from services.compliance_graph_service import consumer_adapter

SAMPLE_DECISION = {
    "decision_id": "dec_test_1",
    "decision_type": "compliance_assessment",
    "decision_outcome": "VALID",
    "decision_timestamp": "2026-06-01T10:00:00+00:00",
    "summary": "Test decision",
    "client_id": "client-1",
    "property_id": "prop-1",
    "requirement_id": "req-1",
    "snapshot_id": "snap_test_1",
    "evidence_set": {"document_ids": ["doc-1"]},
    "source": {"collection": "requirements", "id": "req-1"},
}


@pytest.mark.asyncio
async def test_list_decisions_bounded():
    with patch(
        "services.compliance_graph_service.service.decision_storage.list_decisions_for_scope",
        new_callable=AsyncMock,
        return_value=[SAMPLE_DECISION],
    ):
        result = await graph_service.list_decisions(
            actor=ActorContext(is_admin=True),
            client_id="client-1",
            limit=10,
        )
        assert result["service"] == "list_decisions"
        assert result["payload"]["count"] == 1
        assert result["payload"]["decisions"][0]["decision_id"] == "dec_test_1"


@pytest.mark.asyncio
async def test_trace_requirement_returns_decisions():
    with patch(
        "services.compliance_graph_service.service.decision_storage.list_decisions_for_scope",
        new_callable=AsyncMock,
        return_value=[SAMPLE_DECISION],
    ):
        result = await graph_service.trace_requirement(
            "req-1",
            actor=ActorContext(is_admin=True, client_id="client-1"),
            client_id="client-1",
        )
        assert result["service"] == "trace_requirement"
        assert len(result["payload"]["decisions"]) == 1


@pytest.mark.asyncio
async def test_find_decision_dependencies_includes_edges():
    with patch(
        "services.compliance_graph_service.service.decision_storage.get_decision",
        new_callable=AsyncMock,
        return_value=SAMPLE_DECISION,
    ), patch(
        "services.compliance_graph_service.service.snapshot_storage.get_snapshot_by_decision",
        new_callable=AsyncMock,
        return_value={"decision_reasoning_inputs": {}},
    ), patch(
        "services.compliance_graph_service.service.edge_storage.list_edges_for_decision",
        new_callable=AsyncMock,
        return_value=[{"edge_id": "e1", "edge_type": "SUPPORTS"}],
    ):
        result = await graph_service.find_decision_dependencies(
            "dec_test_1", actor=ActorContext(is_admin=True)
        )
        assert result["payload"]["edges"][0]["edge_id"] == "e1"


@pytest.mark.asyncio
async def test_trace_operational_impact():
    with patch(
        "services.compliance_graph_service.service.decision_storage.get_decision",
        new_callable=AsyncMock,
        return_value={**SAMPLE_DECISION, "operational_correlation_id": "corr-1"},
    ), patch(
        "services.compliance_graph_service.service.snapshot_storage.get_snapshot_by_decision",
        new_callable=AsyncMock,
        return_value={"operational_context": {"operational_event_ids": ["oe-1"]}},
    ):
        result = await graph_service.trace_operational_impact(
            "dec_test_1", actor=ActorContext(is_admin=True)
        )
        assert result["payload"]["correlation_id"] == "corr-1"
        assert result["operational_references"]["operational_event_ids"] == ["oe-1"]


@pytest.mark.asyncio
async def test_explain_for_scope_requirement(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "shadow")
    with patch(
        "services.compliance_evidence_graph.storage.decisions.list_decisions_for_scope",
        new_callable=AsyncMock,
        return_value=[SAMPLE_DECISION],
    ), patch(
        "services.compliance_graph_service.service.explain_decision",
        new_callable=AsyncMock,
        return_value={"service": "explain_decision", "insufficient_evidence": False},
    ):
        result = await consumer_adapter.explain_for_scope(
            scope_type="requirement",
            scope_id="req-1",
            client_id="client-1",
            actor=ActorContext(is_admin=True),
        )
        assert result["service"] == "explain_decision"


@pytest.mark.asyncio
async def test_explain_for_scope_disabled(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "disabled")
    result = await consumer_adapter.explain_for_scope(
        scope_type="requirement",
        scope_id="req-1",
        client_id="client-1",
        actor=ActorContext(is_admin=True),
    )
    assert result["insufficient_evidence"] is True
