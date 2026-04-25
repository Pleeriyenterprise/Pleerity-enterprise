"""compliance_gaps Mongo upsert behaviour and sync error propagation."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.compliance_gap_sync import sync_compliance_gaps_for_requirement
from services.requirement_evidence_authority import AUTHORITY_VERSION


def _requirement_missing_authority():
    return {
        "client_id": "c-sync",
        "property_id": "p-sync",
        "requirement_id": "r-sync",
        "requirement_code": "EPC",
        "applicability": "REQUIRED",
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {"version": AUTHORITY_VERSION, "state": "MISSING"},
    }


@pytest.mark.asyncio
async def test_upsert_set_excludes_created_at_set_on_insert_only():
    req = _requirement_missing_authority()
    db = MagicMock()
    captured: dict = {}

    async def capture_update_one(filter_q, update, upsert=False):
        captured["update"] = update
        r = MagicMock()
        r.upserted_id = object()
        return r

    db.compliance_gaps.update_one = AsyncMock(side_effect=capture_update_one)
    db.compliance_gaps.find = MagicMock(return_value=MagicMock())
    db.compliance_gaps.find.return_value.to_list = AsyncMock(return_value=[])
    db.compliance_gaps.update_many = AsyncMock(return_value=MagicMock(modified_count=0))

    with patch("services.compliance_gap_sync.apply_gap_operational_bridge", new=AsyncMock()):
        out = await sync_compliance_gaps_for_requirement(db, req, property_doc=None, audit_lifecycle=False)

    assert "errors" in out
    assert out["errors"] == []
    upd = captured["update"]
    assert "$set" in upd and "$setOnInsert" in upd
    assert "created_at" not in upd["$set"]
    assert "created_at" in upd["$setOnInsert"]
    assert upd["$set"].get("status") == "open"
    assert "updated_at" in upd["$set"]


@pytest.mark.asyncio
async def test_upsert_existing_document_updates_without_created_at_in_set():
    req = _requirement_missing_authority()
    db = MagicMock()

    async def second_insert_no_upsert(filter_q, update, upsert=False):
        r = MagicMock()
        r.upserted_id = None
        return r

    db.compliance_gaps.update_one = AsyncMock(side_effect=second_insert_no_upsert)
    db.compliance_gaps.find = MagicMock(return_value=MagicMock())
    db.compliance_gaps.find.return_value.to_list = AsyncMock(return_value=[])
    db.compliance_gaps.update_many = AsyncMock(return_value=MagicMock(modified_count=0))

    with patch("services.compliance_gap_sync.apply_gap_operational_bridge", new=AsyncMock()):
        await sync_compliance_gaps_for_requirement(db, req, property_doc=None, audit_lifecycle=False)

    call = db.compliance_gaps.update_one.await_args
    update = call[0][1]
    assert "created_at" not in update["$set"]
    assert "created_at" in update["$setOnInsert"]


@pytest.mark.asyncio
async def test_failed_upsert_returns_error_and_skips_resolve_when_all_fail():
    req = _requirement_missing_authority()
    db = MagicMock()
    db.compliance_gaps.update_one = AsyncMock(side_effect=RuntimeError("server error"))
    db.compliance_gaps.find = MagicMock(return_value=MagicMock())
    db.compliance_gaps.find.return_value.to_list = AsyncMock(return_value=[])
    um = AsyncMock()
    db.compliance_gaps.update_many = um

    with patch("services.compliance_gap_sync.apply_gap_operational_bridge", new=AsyncMock()):
        out = await sync_compliance_gaps_for_requirement(db, req, property_doc=None, audit_lifecycle=False)

    assert len(out["errors"]) >= 1
    assert any(e.get("stage") == "upsert" for e in out["errors"])
    um.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_failure_recorded():
    req = _requirement_missing_authority()
    db = MagicMock()
    db.compliance_gaps.update_one = AsyncMock(return_value=MagicMock(upserted_id=None))
    db.compliance_gaps.find = MagicMock(return_value=MagicMock())
    db.compliance_gaps.find.return_value.to_list = AsyncMock(return_value=[{"gap_key": "stale", "gap_kind": "EXPIRED"}])
    db.compliance_gaps.update_many = AsyncMock(side_effect=Exception("resolve failed"))

    with patch("services.compliance_gap_sync.apply_gap_operational_bridge", new=AsyncMock()):
        out = await sync_compliance_gaps_for_requirement(db, req, property_doc=None, audit_lifecycle=False)

    assert any(e.get("stage") == "resolve" for e in out["errors"])
