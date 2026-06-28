"""Tests for operational bridge — read-only context resolution."""
from __future__ import annotations

import pytest

from services.compliance_evidence_graph.bridge_operational import (
    merge_bridge_into_snapshot,
    resolve_operational_bridge,
)
from services.operational_evidence.context import OperationalContext, reset_operational_context, set_operational_context


@pytest.fixture
def _reset_ctx():
    token = set_operational_context(OperationalContext())
    yield
    reset_operational_context(token)


def test_bridge_resolves_from_operational_context(_reset_ctx):
    set_operational_context(
        OperationalContext(
            correlation_id="corr-123",
            job_run_id="run-abc",
            root_execution_id="root-xyz",
            client_id="client-1",
            metadata={"worker": "compliance_recalc_worker"},
        )
    )
    bridge = resolve_operational_bridge()
    assert bridge["operational_correlation_id"] == "corr-123"
    assert bridge["operational_context"]["job_run_id"] == "run-abc"
    assert bridge["operational_context"]["worker"] == "compliance_recalc_worker"
    assert bridge["scope"]["client_id"] == "client-1"


def test_bridge_never_fabricates_unknown_fields():
    bridge = resolve_operational_bridge()
    assert bridge["operational_correlation_id"] is None
    assert bridge["operational_context"]["incident_id"] is None
    assert bridge["operational_context"]["recovery_event"] is None


def test_bridge_explicit_correlation_overrides_context(_reset_ctx):
    set_operational_context(OperationalContext(correlation_id="ctx-corr"))
    bridge = resolve_operational_bridge(correlation_id="explicit-corr")
    assert bridge["operational_correlation_id"] == "explicit-corr"


def test_merge_bridge_into_snapshot_non_destructive():
    snap = {"compliance_score": {"score_after": 80}}
    bridge = resolve_operational_bridge(correlation_id="c1")
    merged = merge_bridge_into_snapshot(snap, bridge)
    assert merged["compliance_score"]["score_after"] == 80
    assert merged["operational_context"]["correlation_id"] == "c1"
