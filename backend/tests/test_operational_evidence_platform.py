"""Tests for Operational Evidence Platform — emit, relationships, stories."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.operational_evidence.constants import (
    CATEGORY_SCHEDULER,
    COLLECTION_EVENTS,
    EVT_JOB_RUN_STARTED,
)
from services.operational_evidence.context import OperationalContext, set_operational_context
from services.operational_evidence.emit_service import emit_operational_evidence
from services.operational_evidence.query_service import _build_execution_tree
from services.operational_evidence.story_service import build_operational_story


@pytest.mark.asyncio
async def test_emit_requires_evidence_pointer():
    with patch("services.operational_evidence.emit_service.database") as mock_db:
        mock_db.get_db.return_value = MagicMock()
        result = await emit_operational_evidence(
            category=CATEGORY_SCHEDULER,
            event_type=EVT_JOB_RUN_STARTED,
            summary="test",
            evidence={},
            source_service="test",
            source_component="test",
        )
        assert result is None


@pytest.mark.asyncio
async def test_emit_appends_event_with_relationships():
    mock_col = AsyncMock()
    mock_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="abc"))
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)
    mock_exec_col = AsyncMock()
    mock_exec_col.update_one = AsyncMock()
    mock_db.operational_evidence_executions = mock_exec_col

    ctx = OperationalContext(correlation_id="corr-1").ensure_execution()
    set_operational_context(ctx)

    with patch("services.operational_evidence.emit_service.database") as db_mod:
        db_mod.get_db.return_value = mock_db

        def getitem(name):
            if name == COLLECTION_EVENTS:
                return mock_col
            if name == "operational_evidence_executions":
                return mock_exec_col
            return mock_col

        mock_db.__getitem__.side_effect = getitem

        event_id = await emit_operational_evidence(
            category=CATEGORY_SCHEDULER,
            event_type=EVT_JOB_RUN_STARTED,
            summary="Job started",
            evidence={
                "source_collection": "job_runs",
                "source_id": "run123",
                "deep_link": "/admin/automation",
            },
            source_service="job_runner",
            source_component="run_instrumented",
            context=ctx,
        )

    assert event_id is not None
    inserted = mock_col.insert_one.call_args[0][0]
    assert inserted["correlation_id"] == "corr-1"
    assert inserted["evidence"]["source_collection"] == "job_runs"
    assert inserted["relationships"]["previous_event_id"] is None
    assert inserted["execution"]["execution_sequence"] == 1
    assert inserted["confidence"]["score"] == 100


def test_build_execution_tree_child_count():
    items = [
        {
            "event_id": "a",
            "event_type": "JOB_RUN_STARTED",
            "occurred_at": "2026-01-01T09:00:01",
            "relationships": {},
            "execution": {"execution_depth": 0, "execution_sequence": 1},
            "evidence": {"summary": "start"},
            "status": "started",
            "severity": "info",
        },
        {
            "event_id": "b",
            "event_type": "QUEUE_ITEM_CREATED",
            "occurred_at": "2026-01-01T09:00:02",
            "relationships": {"caused_by_event_id": "a", "parent_event_id": "a"},
            "execution": {"execution_depth": 1, "execution_sequence": 2},
            "evidence": {"summary": "queue"},
            "status": "success",
            "severity": "info",
        },
    ]
    tree = _build_execution_tree(items)
    assert tree["root_event_id"] == "a"
    assert len(tree["edges"]) >= 1
    child = next(n for n in tree["nodes"] if n["event_id"] == "a")
    assert child["child_count"] == 1


def test_score_ledger_event_type_threshold():
    from services.operational_evidence.constants import (
        EVT_COMPLIANCE_BECAME_NON_COMPLIANT,
        EVT_COMPLIANCE_BECAME_VALID,
    )

    items_before_valid = [{"event_type": EVT_COMPLIANCE_BECAME_VALID, "status": "success", "evidence": {"summary": "ok"}, "customer_impact": {}}]
    story = build_operational_story(items_before_valid)
    assert story["title"]

    items = [
        {
            "event_type": "JOB_RUN_STARTED",
            "occurred_at": "2026-01-01T09:00:01",
            "status": "started",
            "evidence": {"summary": "Started"},
            "customer_impact": {"classification": "operational_only", "summary": "Ops only"},
        },
        {
            "event_type": "JOB_RUN_COMPLETED",
            "occurred_at": "2026-01-01T09:00:10",
            "status": "success",
            "evidence": {"summary": "Done"},
            "customer_impact": {"classification": "no_impact", "summary": "No customer impact"},
        },
    ]
    story = build_operational_story(items)
    assert story["status"] == "success"
    assert len(story["steps"]) == 2
    assert story["steps"][0]["label"] == "Started"
    assert story["raw_evidence_available"] is True


@pytest.mark.asyncio
async def test_backfill_skips_already_indexed():
    from services.operational_evidence.backfill_service import _already_indexed, _emit_backfill

    mock_events = AsyncMock()
    mock_events.find_one = AsyncMock(return_value={"_id": "existing"})
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_events)

    with patch("services.operational_evidence.backfill_service.database") as db_mod:
        db_mod.get_db.return_value = mock_db
        assert await _already_indexed("job_runs", "run1", "JOB_RUN_COMPLETED") is True


@pytest.mark.asyncio
async def test_backfill_emit_sets_metadata():
    from services.operational_evidence.backfill_service import _emit_backfill

    with patch("services.operational_evidence.backfill_service.emit_operational_evidence", new_callable=AsyncMock) as emit:
        emit.return_value = "evt-1"
        ok = await _emit_backfill(
            category="scheduler",
            event_type="JOB_RUN_COMPLETED",
            summary="test",
            source_service="backfill_service",
            source_component="test",
            evidence={"source_collection": "job_runs", "source_id": "r1", "deep_link": "/"},
        )
        assert ok is True
        kwargs = emit.call_args.kwargs
        assert kwargs["metadata"]["backfill"] is True
        assert kwargs["confidence"] == 80


@pytest.mark.asyncio
async def test_risk_regen_queue_created_emit():
    from services.operational_evidence.producers import emit_risk_regen_queue_created
    from services.operational_evidence.constants import CATEGORY_RISK, EVT_QUEUE_ITEM_CREATED

    with patch("services.operational_evidence.producers.emit_operational_evidence", new_callable=AsyncMock) as emit:
        emit.return_value = "evt-risk"
        await emit_risk_regen_queue_created(
            queue_item_id="q1",
            property_id="prop-1",
            client_id="client-1",
            trigger_reason="DOCUMENT_UPLOAD",
        )
        kwargs = emit.call_args.kwargs
        assert kwargs["category"] == CATEGORY_RISK
        assert kwargs["event_type"] == EVT_QUEUE_ITEM_CREATED
        assert kwargs["evidence"]["source_collection"] == "risk_signal_regen_queue"


@pytest.mark.asyncio
async def test_retention_filter_excludes_warm_by_default():
    from services.operational_evidence.query_service import _build_filter_query

    q = _build_filter_query()
    assert q["retention.tier"]["$nin"] == ["warm", "cold"]

    q_archived = _build_filter_query(include_archived=True)
    assert "retention.tier" not in q_archived


@pytest.mark.asyncio
async def test_apply_warm_retention_tier():
    from services.operational_evidence.retention_service import apply_warm_retention_tier

    mock_col = AsyncMock()
    mock_col.count_documents = AsyncMock(return_value=5)
    mock_col.find = MagicMock(
        return_value=MagicMock(
            sort=MagicMock(
                return_value=MagicMock(
                    limit=MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[{"_id": "a"}])))
                )
            )
        )
    )
    mock_col.update_many = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_col)

    with patch("services.operational_evidence.retention_service.database") as db_mod:
        db_mod.get_db.return_value = mock_db
        result = await apply_warm_retention_tier(batch_limit=10)
    assert result["modified"] == 1


@pytest.mark.asyncio
async def test_maintenance_job_orchestrates_backfill_and_retention():
    from services.operational_evidence.maintenance_service import run_operational_evidence_maintenance

    with patch(
        "services.operational_evidence.maintenance_service.run_operational_evidence_backfill",
        new_callable=AsyncMock,
    ) as backfill:
        with patch(
            "services.operational_evidence.maintenance_service.apply_warm_retention_tier",
            new_callable=AsyncMock,
        ) as retention:
            backfill.return_value = {"totals": {"emitted": 3}}
            retention.return_value = {"modified": 2}
            result = await run_operational_evidence_maintenance()
    assert result["count"] == 5
    assert "backfill" in result and "retention" in result
