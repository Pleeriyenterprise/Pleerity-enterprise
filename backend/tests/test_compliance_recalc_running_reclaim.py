"""
Tests for stale RUNNING reclaim on compliance_recalc_queue (race-safe, attempt caps).
"""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


@pytest.fixture
def frozen_now():
    return datetime(2026, 5, 8, 12, 0, 0, tzinfo=timezone.utc)


class TestMongoRunningStaleFilter:
    def test_filter_contains_expr(self):
        from services.compliance_recalc_running_reclaim import mongo_running_liveness_stale_filter

        f = mongo_running_liveness_stale_filter("2026-05-08T10:00:00+00:00")
        assert f["status"] == "RUNNING"
        assert "$expr" in f


@pytest.mark.asyncio
class TestReclaimStaleRunning:
    async def test_stale_running_becomes_pending(self, frozen_now, monkeypatch):
        from bson import ObjectId
        from services.compliance_recalc_running_reclaim import reclaim_stale_running_compliance_recalc_jobs

        monkeypatch.setenv("COMPLIANCE_RECALC_RUNNING_STALE_SECONDS", "600")
        jid = ObjectId()
        stale_iso = (frozen_now - timedelta(hours=2)).isoformat()
        doc = {
            "_id": jid,
            "status": "RUNNING",
            "property_id": "prop-a",
            "client_id": "cli-a",
            "attempts": 1,
            "updated_at": stale_iso,
            "correlation_id": "corr",
            "trigger_reason": "TEST",
        }

        db = MagicMock()
        db.compliance_recalc_queue = MagicMock()
        db.compliance_recalc_queue.find_one = AsyncMock(side_effect=[doc, None])
        db.compliance_recalc_queue.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            out = await reclaim_stale_running_compliance_recalc_jobs(db, now=frozen_now, max_rows=50)

        assert out["reclaimed_to_pending"] == 1
        assert out["reclaimed_to_dead"] == 0
        call = db.compliance_recalc_queue.update_one.call_args
        assert call[0][1]["$set"]["status"] == "PENDING"
        assert call[0][1]["$set"]["attempts"] == 2
        assert call[0][1]["$unset"] == {"heartbeat_at": ""}

    async def test_fresh_running_not_selected(self, frozen_now, monkeypatch):
        from services.compliance_recalc_running_reclaim import reclaim_stale_running_compliance_recalc_jobs

        monkeypatch.setenv("COMPLIANCE_RECALC_RUNNING_STALE_SECONDS", "600")
        db = MagicMock()
        db.compliance_recalc_queue = MagicMock()
        db.compliance_recalc_queue.find_one = AsyncMock(return_value=None)

        out = await reclaim_stale_running_compliance_recalc_jobs(db, now=frozen_now, max_rows=50)
        assert out["reclaimed_to_pending"] == 0
        assert out["reclaimed_to_dead"] == 0
        db.compliance_recalc_queue.update_one.assert_not_called()

    async def test_max_attempts_goes_dead_not_pending(self, frozen_now, monkeypatch):
        from bson import ObjectId
        from services.compliance_recalc_running_reclaim import reclaim_stale_running_compliance_recalc_jobs

        monkeypatch.setenv("COMPLIANCE_RECALC_RUNNING_STALE_SECONDS", "600")
        jid = ObjectId()
        stale_iso = (frozen_now - timedelta(hours=2)).isoformat()
        doc = {
            "_id": jid,
            "status": "RUNNING",
            "property_id": "prop-b",
            "client_id": "cli-b",
            "attempts": 4,
            "updated_at": stale_iso,
            "correlation_id": "corr",
            "trigger_reason": "TEST",
        }

        db = MagicMock()
        db.compliance_recalc_queue = MagicMock()
        db.compliance_recalc_queue.find_one = AsyncMock(side_effect=[doc, None])
        db.compliance_recalc_queue.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            out = await reclaim_stale_running_compliance_recalc_jobs(db, now=frozen_now, max_rows=50)

        assert out["reclaimed_to_dead"] == 1
        assert out["reclaimed_to_pending"] == 0
        assert db.compliance_recalc_queue.update_one.call_args[0][1]["$set"]["status"] == "DEAD"

    async def test_race_second_worker_gets_zero_modified(self, frozen_now, monkeypatch):
        from bson import ObjectId
        from services.compliance_recalc_running_reclaim import reclaim_stale_running_compliance_recalc_jobs

        monkeypatch.setenv("COMPLIANCE_RECALC_RUNNING_STALE_SECONDS", "600")
        jid = ObjectId()
        stale_iso = (frozen_now - timedelta(hours=2)).isoformat()
        doc = {
            "_id": jid,
            "status": "RUNNING",
            "property_id": "prop-c",
            "client_id": "cli-c",
            "attempts": 1,
            "updated_at": stale_iso,
            "correlation_id": "corr",
            "trigger_reason": "TEST",
        }

        db = MagicMock()
        db.compliance_recalc_queue = MagicMock()
        db.compliance_recalc_queue.find_one = AsyncMock(side_effect=[doc, None])
        db.compliance_recalc_queue.update_one = AsyncMock(return_value=MagicMock(modified_count=0))

        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            out = await reclaim_stale_running_compliance_recalc_jobs(db, now=frozen_now, max_rows=50)

        assert out["reclaimed_to_pending"] == 0
        assert out["skipped_race"] == 1
