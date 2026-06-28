"""Tests for Compliance Evidence Graph — emit, immutability, idempotency."""
from __future__ import annotations

import os

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.compliance_evidence_graph.constants import (
    COLLECTION_DECISIONS,
    COLLECTION_EDGES,
    COLLECTION_NODES,
    COLLECTION_SNAPSHOTS,
    DECISION_COMPLIANCE_ASSESSMENT,
    EDGE_SNAPSHOT_OF,
)
from services.compliance_evidence_graph.emit_service import emit_compliance_decision


@pytest.fixture(autouse=True)
def _enable_graph_emit(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "phase1_validation")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")


@pytest.mark.asyncio
async def test_emit_rejected_without_source_pointer():
    with patch("services.compliance_evidence_graph.emit_service.graph_emit_allowed", return_value=True):
        result = await emit_compliance_decision(
            decision_type=DECISION_COMPLIANCE_ASSESSMENT,
            decision_outcome="VALID",
            summary="test",
            source_collection="",
            source_id="",
            dedupe_key="dup-empty",
            client_id="client-1",
            decision_authority={"service": "test", "component": "test"},
            snapshot_payload={},
        )
        assert result is None


@pytest.mark.asyncio
async def test_emit_idempotent_by_dedupe_key():
    existing = {"decision_id": "dec_existing", "dedupe_key": "dup-1"}
    with patch("services.compliance_evidence_graph.emit_service.graph_emit_allowed", return_value=True), patch(
        "services.compliance_evidence_graph.emit_service.decision_storage.get_decision_by_dedupe",
        new_callable=AsyncMock,
        return_value=existing,
    ):
        result = await emit_compliance_decision(
            decision_type=DECISION_COMPLIANCE_ASSESSMENT,
            decision_outcome="VALID",
            summary="test",
            source_collection="requirements",
            source_id="req-1",
            dedupe_key="dup-1",
            client_id="client-1",
            decision_authority={"service": "test", "component": "test"},
            snapshot_payload={"applicable_legislation": []},
        )
        assert result == "dec_existing"


@pytest.mark.asyncio
async def test_emit_creates_decision_snapshot_nodes_and_provenanced_edge():
    decision_col = AsyncMock()
    decision_col.insert_one = AsyncMock()
    snapshot_col = AsyncMock()
    snapshot_col.insert_one = AsyncMock()
    node_col = AsyncMock()
    node_col.insert_one = AsyncMock()
    edge_col = AsyncMock()
    edge_col.insert_one = AsyncMock()

    async def get_edge_dedupe(_):
        return None

    with patch("services.compliance_evidence_graph.emit_service.graph_emit_allowed", return_value=True), patch(
        "services.compliance_evidence_graph.emit_service.decision_storage.get_decision_by_dedupe",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "services.compliance_evidence_graph.emit_service.decision_storage.insert_decision",
        new_callable=AsyncMock,
    ) as ins_dec, patch(
        "services.compliance_evidence_graph.emit_service.snapshot_storage.insert_snapshot",
        new_callable=AsyncMock,
    ) as ins_snap, patch(
        "services.compliance_evidence_graph.emit_service.node_storage.insert_node",
        new_callable=AsyncMock,
    ) as ins_node, patch(
        "services.compliance_evidence_graph.emit_service.edge_storage.insert_edge",
        new_callable=AsyncMock,
    ) as ins_edge, patch(
        "services.compliance_evidence_graph.emit_service.edge_storage.get_edge_by_dedupe",
        new_callable=AsyncMock,
        side_effect=get_edge_dedupe,
    ):
        decision_id = await emit_compliance_decision(
            decision_type=DECISION_COMPLIANCE_ASSESSMENT,
            decision_outcome="VALID",
            summary="Requirement assessed VALID",
            source_collection="requirements",
            source_id="req-abc",
            dedupe_key="dup-new-1",
            client_id="client-1",
            property_id="prop-1",
            requirement_id="req-abc",
            decision_authority={"service": "test_svc", "component": "test_cmp"},
            snapshot_payload={"applicable_legislation": [{"legislation_id": "x"}]},
        )
        assert decision_id is not None
        assert decision_id.startswith("dec_")
        ins_dec.assert_called_once()
        ins_snap.assert_called_once()
        assert ins_node.await_count == 2
        ins_edge.assert_called_once()
        edge_doc = ins_edge.call_args[0][0]
        assert edge_doc["edge_type"] == EDGE_SNAPSHOT_OF
        assert edge_doc["provenance"]["why_exists"]
        assert edge_doc["provenance"]["created_by_component"] == "test_cmp"
        assert edge_doc["provenance"]["decision_id"] == decision_id
        assert edge_doc["provenance"]["is_active"] is True


@pytest.mark.asyncio
async def test_emit_disallowed_when_mode_disabled(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "disabled")
    result = await emit_compliance_decision(
        decision_type=DECISION_COMPLIANCE_ASSESSMENT,
        decision_outcome="VALID",
        summary="test",
        source_collection="requirements",
        source_id="req-1",
        dedupe_key="dup-off",
        client_id="client-1",
        decision_authority={"service": "test", "component": "test"},
        snapshot_payload={},
    )
    assert result is None


def test_graph_emit_allowed_under_phase1_validation():
    from services.compliance_evidence_graph.config import graph_emit_allowed, graph_producers_enabled

    os.environ["COMPLIANCE_EVIDENCE_GRAPH_MODE"] = "disabled"
    assert graph_producers_enabled() is False
    os.environ["COMPLIANCE_EVIDENCE_GRAPH_MODE"] = "phase1_validation"
    assert graph_emit_allowed() is True
