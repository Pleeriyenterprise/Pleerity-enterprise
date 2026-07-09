"""Tests for Compliance Graph Service — explain, replay, compare, historical."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from services.compliance_graph_service.access import ActorContext
from services.compliance_graph_service import service as graph_service


def _admin_actor() -> ActorContext:
    return ActorContext(is_admin=True, client_id="admin-client")


def _tenant_actor(client_id: str = "client-1") -> ActorContext:
    return ActorContext(is_admin=False, client_id=client_id)


SAMPLE_DECISION = {
    "decision_id": "dec_test_1",
    "decision_type": "compliance_assessment",
    "decision_outcome": "VALID",
    "decision_timestamp": "2026-06-01T10:00:00+00:00",
    "summary": "Test decision summary",
    "client_id": "client-1",
    "property_id": "prop-1",
    "requirement_id": "req-1",
    "snapshot_id": "snap_test_1",
    "decision_confidence": {"score": 100, "label": "runtime_confirmed"},
    "rules_version": {"governed_rule_version_id": "gov_v1"},
    "legislation_version": {"refs": []},
    "evidence_set": {"evidence_node_ids": [], "document_ids": ["doc-1"]},
    "operational_correlation_id": "corr-1",
    "source": {"collection": "requirements", "id": "req-1"},
    "previous_decision_id": None,
}

SAMPLE_SNAPSHOT = {
    "snapshot_id": "snap_test_1",
    "decision_id": "dec_test_1",
    "snapshot_timestamp": "2026-06-01T10:00:00+00:00",
    "snapshot_hash": "abc123",
    "client_id": "client-1",
    "applicable_legislation": [{"legislation_id": "gas_safety"}],
    "evidence_version": {"document_versions": [{"document_id": "doc-1"}]},
    "decision_reasoning_inputs": {"authority_sync_outcome": {"semantic_state": "VALID"}},
    "operational_context": {"correlation_id": "corr-1", "operational_event_ids": []},
    "timeline_references": [],
}


@pytest.mark.asyncio
async def test_explain_decision_returns_structured_payload():
    with patch(
        "services.compliance_graph_service.service.decision_storage.get_decision",
        new_callable=AsyncMock,
        return_value=SAMPLE_DECISION,
    ), patch(
        "services.compliance_graph_service.service.snapshot_storage.get_snapshot_by_decision",
        new_callable=AsyncMock,
        return_value=SAMPLE_SNAPSHOT,
    ):
        result = await graph_service.explain_decision("dec_test_1", actor=_admin_actor())
        assert result["service"] == "explain_decision"
        assert result["insufficient_evidence"] is False
        assert result["payload"]["executive_summary"] == "Test decision summary"
        assert result["authoritative_references"]["decision_id"] == "dec_test_1"
        assert result["historical_references"]["snapshot_id"] == "snap_test_1"


@pytest.mark.asyncio
async def test_explain_decision_insufficient_when_missing():
    with patch(
        "services.compliance_graph_service.service.decision_storage.get_decision",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await graph_service.explain_decision("dec_missing", actor=_admin_actor())
        assert result["insufficient_evidence"] is True


@pytest.mark.asyncio
async def test_replay_decision_chronological_phases():
    with patch(
        "services.compliance_graph_service.service.decision_storage.get_decision",
        new_callable=AsyncMock,
        return_value=SAMPLE_DECISION,
    ), patch(
        "services.compliance_graph_service.service.snapshot_storage.get_snapshot_by_decision",
        new_callable=AsyncMock,
        return_value={**SAMPLE_SNAPSHOT, "rules_version": {}, "compliance_score": {"score_after": 80}},
    ), patch(
        "services.compliance_graph_service.service.node_storage.list_nodes_for_decision",
        new_callable=AsyncMock,
        return_value=[{"node_id": "n1", "occurred_at": "2026-06-01T09:00:00+00:00", "summary": "node"}],
    ), patch(
        "services.compliance_graph_service.service.edge_storage.list_edges_for_decision",
        new_callable=AsyncMock,
        return_value=[{"edge_id": "e1", "provenance": {"decision_id": "dec_test_1"}}],
    ):
        result = await graph_service.replay_decision("dec_test_1", actor=_admin_actor())
        assert result["service"] == "replay_decision"
        phases = [p["phase"] for p in result["payload"]["phases"]]
        assert "decision_recorded" in phases
        assert result["payload"]["graph_edges"][0]["provenance"]["decision_id"] == "dec_test_1"


@pytest.mark.asyncio
async def test_compare_decision_structured_diff():
    left = {**SAMPLE_DECISION, "decision_id": "dec_a", "decision_outcome": "PENDING", "snapshot_id": "snap_a"}
    right = {**SAMPLE_DECISION, "decision_id": "dec_b", "decision_outcome": "VALID", "snapshot_id": "snap_b"}
    snap_a = {**SAMPLE_SNAPSHOT, "snapshot_id": "snap_a", "compliance_score": {"score_after": 70}}
    snap_b = {**SAMPLE_SNAPSHOT, "snapshot_id": "snap_b", "compliance_score": {"score_after": 80}}
    with patch(
        "services.compliance_graph_service.service.decision_storage.get_decision",
        new_callable=AsyncMock,
        side_effect=[left, right],
    ), patch(
        "services.compliance_graph_service.service.snapshot_storage.get_snapshot_by_decision",
        new_callable=AsyncMock,
        side_effect=[snap_a, snap_b],
    ):
        result = await graph_service.compare_decision("dec_a", "dec_b", actor=_admin_actor())
        assert result["payload"]["outcome_changed"] is True
        assert "decision_outcome" in result["payload"]["diff"]


@pytest.mark.asyncio
async def test_find_historical_decision_uses_as_of():
    with patch(
        "services.compliance_graph_service.service.decision_storage.find_decision_at_or_before",
        new_callable=AsyncMock,
        return_value=SAMPLE_DECISION,
    ), patch(
        "services.compliance_graph_service.service.snapshot_storage.get_snapshot_by_decision",
        new_callable=AsyncMock,
        return_value=SAMPLE_SNAPSHOT,
    ):
        result = await graph_service.find_historical_decision(
            client_id="client-1",
            as_of="2026-06-15T00:00:00+00:00",
            actor=_tenant_actor("client-1"),
        )
        assert result["payload"]["decision_id"] == "dec_test_1"
        assert result["historical_references"]["as_of"] == "2026-06-15T00:00:00+00:00"


@pytest.mark.asyncio
async def test_tenant_isolation_denies_other_client():
    with patch(
        "services.compliance_graph_service.service.decision_storage.get_decision",
        new_callable=AsyncMock,
        return_value=SAMPLE_DECISION,
    ):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await graph_service.explain_decision("dec_test_1", actor=_tenant_actor("other-client"))
        assert exc.value.status_code == 403
