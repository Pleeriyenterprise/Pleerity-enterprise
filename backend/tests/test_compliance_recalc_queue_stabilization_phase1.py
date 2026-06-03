"""Recalc queue reference-pattern hardening (correlation, visibility, ops snapshots)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pymongo.errors import DuplicateKeyError

from services.compliance_recalc_correlation import (
    classify_duplicate_suppression_reason,
    ensure_correlation_id,
    normalize_recalc_job_context,
)
from services.compliance_recalc_operational_snapshot import (
    build_recalc_queue_health_summary,
    build_recalc_reconciliation_marker_view,
)
from services.compliance_recalc_queue import (
    EnqueueComplianceRecalcResult,
    STATUS_DEAD,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    enqueue_compliance_recalc,
)


def test_ensure_correlation_id_preserves_explicit():
    cid = ensure_correlation_id(trigger_reason="T", property_id="p1", correlation_id="  my-id  ")
    assert cid == "my-id"


def test_ensure_correlation_id_generates_when_blank():
    cid = ensure_correlation_id(trigger_reason="T", property_id="p1", correlation_id=None)
    assert cid.startswith("T:p1:")
    assert len(cid) > len("T:p1:")


def test_normalize_recalc_job_context_shape():
    ctx = normalize_recalc_job_context(
        {
            "property_id": "a",
            "client_id": "c",
            "trigger_reason": "TR",
            "actor_type": "SYSTEM",
            "correlation_id": " x ",
            "status": "PENDING",
            "attempts": 2,
        }
    )
    assert ctx["correlation_id"] == "x"
    assert ctx["retry_count"] == 2


@pytest.mark.parametrize(
    "status,expected",
    [
        ("RUNNING", "already_running"),
        ("PENDING", "duplicate_pending"),
        ("FAILED", "retry_requeued"),
        ("DONE", "duplicate_pending"),
        ("DEAD", "duplicate_pending"),
        (None, "duplicate_pending"),
    ],
)
def test_classify_duplicate_suppression_reason(status, expected):
    assert classify_duplicate_suppression_reason(existing_status=status) == expected


def test_enqueue_result_bool_backward_compat():
    assert bool(EnqueueComplianceRecalcResult(True, "c1")) is True
    assert bool(EnqueueComplianceRecalcResult(False, "c1", duplicate_suppression_reason="duplicate_pending")) is False


@pytest.mark.asyncio
async def test_enqueue_compliance_recalc_success(monkeypatch):
    import services.compliance_recalc_queue as qmod

    db = MagicMock()
    db.compliance_recalc_queue = MagicMock()
    db.compliance_recalc_queue.insert_one = AsyncMock()
    db.properties = MagicMock()
    db.properties.update_one = AsyncMock()

    monkeypatch.setattr(qmod.database, "get_db", lambda: db)

    async def _regen(*_a, **_k):
        return {}

    monkeypatch.setattr("services.risk_signal_regen_queue.enqueue_risk_signal_regen", _regen)

    res = await enqueue_compliance_recalc(
        property_id="p1",
        client_id="c1",
        trigger_reason="TRIGGER_TEST",
        actor_type="SYSTEM",
        correlation_id="fixed-corr",
    )
    assert res.enqueued is True
    assert res.correlation_id == "fixed-corr"
    assert res.duplicate_suppression_reason is None
    assert res.regeneration_requeued is True
    assert bool(res) is True
    db.compliance_recalc_queue.insert_one.assert_awaited_once()
    ins = db.compliance_recalc_queue.insert_one.await_args[0][0]
    assert ins["correlation_id"] == "fixed-corr"
    assert ins["retry_count"] == 0
    assert ins["retry_exhausted"] is False


@pytest.mark.asyncio
async def test_enqueue_compliance_recalc_duplicate_pending(monkeypatch):
    import services.compliance_recalc_queue as qmod

    db = MagicMock()
    db.compliance_recalc_queue = MagicMock()
    db.compliance_recalc_queue.insert_one = AsyncMock(side_effect=DuplicateKeyError("E11000"))
    db.compliance_recalc_queue.find_one = AsyncMock(return_value={"status": STATUS_PENDING})
    db.compliance_recalc_queue.update_one = AsyncMock()
    db.properties = MagicMock()
    db.properties.update_one = AsyncMock()

    monkeypatch.setattr(qmod.database, "get_db", lambda: db)

    async def _regen(*_a, **_k):
        return {}

    monkeypatch.setattr("services.risk_signal_regen_queue.enqueue_risk_signal_regen", _regen)

    res = await enqueue_compliance_recalc(
        property_id="p1",
        client_id="c1",
        trigger_reason="TRIGGER_TEST",
        actor_type="SYSTEM",
        correlation_id="dup-corr",
    )
    assert res.enqueued is False
    assert res.duplicate_suppression_reason == "duplicate_pending"
    assert res.correlation_id == "dup-corr"
    assert bool(res) is False
    db.compliance_recalc_queue.update_one.assert_awaited()
    db.properties.update_one.assert_awaited()


@pytest.mark.asyncio
async def test_enqueue_compliance_recalc_duplicate_running(monkeypatch):
    import services.compliance_recalc_queue as qmod

    db = MagicMock()
    db.compliance_recalc_queue = MagicMock()
    db.compliance_recalc_queue.insert_one = AsyncMock(side_effect=DuplicateKeyError("E11000"))
    db.compliance_recalc_queue.find_one = AsyncMock(return_value={"status": STATUS_RUNNING})
    db.compliance_recalc_queue.update_one = AsyncMock()
    db.properties = MagicMock()
    db.properties.update_one = AsyncMock()

    monkeypatch.setattr(qmod.database, "get_db", lambda: db)
    monkeypatch.setattr("services.risk_signal_regen_queue.enqueue_risk_signal_regen", AsyncMock())

    res = await enqueue_compliance_recalc("p1", "c1", "T", "SYSTEM", correlation_id="x")
    assert res.duplicate_suppression_reason == "already_running"
    db.properties.update_one.assert_awaited()


@pytest.mark.asyncio
async def test_enqueue_compliance_recalc_duplicate_failed_retry(monkeypatch):
    import services.compliance_recalc_queue as qmod

    db = MagicMock()
    db.compliance_recalc_queue = MagicMock()
    db.compliance_recalc_queue.insert_one = AsyncMock(side_effect=DuplicateKeyError("E11000"))
    db.compliance_recalc_queue.find_one = AsyncMock(return_value={"status": STATUS_FAILED})
    db.compliance_recalc_queue.update_one = AsyncMock()
    db.properties = MagicMock()
    db.properties.update_one = AsyncMock()

    monkeypatch.setattr(qmod.database, "get_db", lambda: db)
    monkeypatch.setattr("services.risk_signal_regen_queue.enqueue_risk_signal_regen", AsyncMock())

    res = await enqueue_compliance_recalc("p1", "c1", "T", "SYSTEM", correlation_id="x")
    assert res.duplicate_suppression_reason == "retry_requeued"
    db.properties.update_one.assert_awaited()


@pytest.mark.asyncio
async def test_enqueue_compliance_recalc_duplicate_done_regenerates(monkeypatch):
    import services.compliance_recalc_queue as qmod

    db = MagicMock()
    db.compliance_recalc_queue = MagicMock()
    db.compliance_recalc_queue.insert_one = AsyncMock(side_effect=DuplicateKeyError("E11000"))
    db.compliance_recalc_queue.find_one = AsyncMock(return_value={"status": STATUS_DONE})
    db.compliance_recalc_queue.update_one = AsyncMock()
    db.properties = MagicMock()
    db.properties.update_one = AsyncMock()

    monkeypatch.setattr(qmod.database, "get_db", lambda: db)
    monkeypatch.setattr("services.risk_signal_regen_queue.enqueue_risk_signal_regen", AsyncMock())

    res = await enqueue_compliance_recalc("p1", "c1", "T", "SYSTEM", correlation_id="done-corr")
    assert res.enqueued is True
    assert res.duplicate_suppression_reason == "regenerated_from_done_duplicate"
    db.properties.update_one.assert_awaited()


def test_health_summary_determinism():
    snap = {
        "pending_job_count": 3,
        "running_job_count": 1,
        "failed_retry_job_count": 2,
        "dead_job_count": 0,
        "missing_correlation_job_count": 1,
        "duplicate_suppression_enqueue_total": 9,
        "reconciliation_observability": {
            "stale_pending_recalc_count": 1,
            "stuck_running_count": 0,
            "regeneration_pending_backlog": 4,
        },
    }
    a = build_recalc_queue_health_summary(snap)
    b = build_recalc_queue_health_summary(snap)
    assert a == b
    assert a["duplicate_suppression_observed_total"] == 9
    assert a["health_posture"] == "NON_BLOCKING_OBSERVABILITY_ONLY"


def test_reconciliation_marker_view_sorted():
    view = build_recalc_reconciliation_marker_view(
        [
            {"property_id": "b", "status": STATUS_PENDING, "created_at": "2020-01-01"},
            {"property_id": "a", "status": STATUS_DEAD},
        ]
    )
    assert view["non_blocking"] is True
    codes = [m["code"] for m in view["markers"]]
    assert codes == ["DEAD_LETTER_PRESENT", "PENDING_ROW_PRESENT"]
