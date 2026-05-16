"""C1: duplicate enqueue suppression vs legitimate new correlation (rev 2 §4c)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pymongo.errors import DuplicateKeyError

from services.compliance_recalc_queue import (
    STATUS_DONE,
    STATUS_PENDING,
    enqueue_compliance_recalc,
)


@pytest.mark.asyncio
async def test_stable_replay_suppresses_duplicate_when_done_exists(monkeypatch):
    import services.compliance_recalc_queue as qmod

    db = MagicMock()
    db.compliance_recalc_queue = MagicMock()
    db.compliance_recalc_queue.insert_one = AsyncMock(side_effect=DuplicateKeyError("dup"))
    db.compliance_recalc_queue.find_one = AsyncMock(
        return_value={"status": STATUS_DONE, "correlation_id": "REQUIREMENTS_SYNC:p1"}
    )
    db.compliance_recalc_queue.update_one = AsyncMock()
    db.properties = MagicMock()
    db.properties.update_one = AsyncMock()

    monkeypatch.setattr(qmod.database, "get_db", lambda: db)
    monkeypatch.setattr("services.risk_signal_regen_queue.enqueue_risk_signal_regen", AsyncMock(return_value={}))

    res = await enqueue_compliance_recalc(
        property_id="p1",
        client_id="c1",
        trigger_reason="TRIGGER_PROPERTY_UPDATED",
        actor_type="CLIENT",
        correlation_id="REQUIREMENTS_SYNC:p1",
    )
    assert res.enqueued is False
    assert res.duplicate_suppression_reason == "duplicate_pending"
    db.properties.update_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_meaningful_mutation_new_correlation_enqueues(monkeypatch):
    import services.compliance_recalc_queue as qmod

    db = MagicMock()
    db.compliance_recalc_queue = MagicMock()
    db.compliance_recalc_queue.insert_one = AsyncMock()
    db.properties = MagicMock()
    db.properties.update_one = AsyncMock()

    monkeypatch.setattr(qmod.database, "get_db", lambda: db)
    monkeypatch.setattr("services.risk_signal_regen_queue.enqueue_risk_signal_regen", AsyncMock(return_value={}))

    res = await enqueue_compliance_recalc(
        property_id="p1",
        client_id="c1",
        trigger_reason="ADMIN_MANUAL_JOB",
        actor_type="ADMIN",
        correlation_id="ADMIN_MANUAL_JOB:REGISTRY_SYNC:p1:abc123",
    )
    assert res.enqueued is True
    assert res.duplicate_suppression_reason is None
    db.properties.update_one.assert_awaited_once()
