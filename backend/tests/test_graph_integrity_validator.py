"""Tests for Graph Integrity Validator."""
from __future__ import annotations

import os

import pytest
from unittest.mock import AsyncMock, patch

from services.compliance_evidence_graph.constants import (
    DECISION_COMPLIANCE_ASSESSMENT,
    EDGE_SNAPSHOT_OF,
)
from services.compliance_evidence_graph.validation.integrity_validator import (
    validate_decision,
    validate_graph,
    validate_relationships,
    validate_snapshot,
)


@pytest.fixture(autouse=True)
def _enable_graph_emit(monkeypatch):
    monkeypatch.setenv("COMPLIANCE_EVIDENCE_GRAPH_MODE", "phase1_validation")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")


@pytest.mark.asyncio
async def test_validate_decision_detects_missing_snapshot():
    dec = {
        "decision_id": "dec_bad",
        "decision_type": DECISION_COMPLIANCE_ASSESSMENT,
        "snapshot_id": "snap_missing",
        "client_id": "c1",
        "source": {"collection": "requirements", "id": "r1"},
        "dedupe_key": "dup-bad",
    }
    with patch(
        "services.compliance_evidence_graph.validation.integrity_validator.decision_storage.get_decision",
        new_callable=AsyncMock,
        return_value=dec,
    ), patch(
        "services.compliance_evidence_graph.validation.integrity_validator.snapshot_storage.get_snapshot_by_decision",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await validate_decision("dec_bad")
        assert result.valid is False
        assert any("snapshot not found" in f.message for f in result.failures)


@pytest.mark.asyncio
async def test_validate_snapshot_detects_hash_missing():
    snap = {"snapshot_id": "snap_1", "decision_id": "dec_1"}
    with patch(
        "services.compliance_evidence_graph.validation.integrity_validator.snapshot_storage.get_snapshot",
        new_callable=AsyncMock,
        return_value=snap,
    ), patch(
        "services.compliance_evidence_graph.validation.integrity_validator.decision_storage.get_decision",
        new_callable=AsyncMock,
        return_value={"decision_id": "dec_1", "snapshot_id": "snap_1"},
    ):
        result = await validate_snapshot("snap_1")
        assert result.valid is False
        assert any("snapshot_hash" in f.message for f in result.failures)


@pytest.mark.asyncio
async def test_validate_relationships_detects_broken_node_ref():
    edges = [
        {
            "edge_id": "e1",
            "edge_type": EDGE_SNAPSHOT_OF,
            "from_node_id": "missing_from",
            "to_node_id": "missing_to",
            "provenance": {
                "why_exists": "test",
                "created_by_component": "test",
                "created_by_authority": "test",
                "created_at": "2026-01-01T00:00:00+00:00",
                "is_active": True,
            },
        }
    ]
    with patch(
        "services.compliance_evidence_graph.validation.integrity_validator.edge_storage.list_edges_for_decision",
        new_callable=AsyncMock,
        return_value=edges,
    ), patch(
        "services.compliance_evidence_graph.validation.integrity_validator.node_storage.get_node",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await validate_relationships(decision_id="dec_1")
        assert result.valid is False
        assert len(result.failures) >= 2


@pytest.mark.asyncio
async def test_validate_graph_empty_scope_is_valid():
    with patch(
        "services.compliance_evidence_graph.validation.integrity_validator.decision_storage.list_decisions_for_scope",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "services.compliance_evidence_graph.validation.integrity_validator.validate_tenant_isolation",
        new_callable=AsyncMock,
        return_value=__import__(
            "services.compliance_evidence_graph.validation.result", fromlist=["ValidationResult"]
        ).ValidationResult(valid=True, checks_run=1),
    ):
        result = await validate_graph(client_id="c1")
        assert result.valid is True
        assert result.stats.get("decisions_examined") == 0
