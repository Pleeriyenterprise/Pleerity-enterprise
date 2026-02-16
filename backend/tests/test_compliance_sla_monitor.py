"""
Tests for compliance recalc SLA monitor: stuck PENDING/RUNNING, failing repeatedly, resolution.
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


class AsyncCursor:
    """Async iterator over a list (for mocking Motor find() cursor)."""
    def __init__(self, items):
        self._items = list(items)
    def __aiter__(self):
        return self
    async def __anext__(self):
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


@pytest.fixture
def mock_now():
    return datetime(2026, 2, 12, 10, 0, 0, tzinfo=timezone.utc)


class TestComplianceRecalcSlaMonitor:
    """SLA monitor creates alerts + audit, dedupes within cooldown, resolves when condition clears."""

    @pytest.mark.asyncio
    async def test_stuck_pending_creates_alert_and_audit(self, mock_now):
        from services.compliance_sla_monitor import (
            run_compliance_recalc_sla_monitor,
            ALERT_PENDING_STUCK,
            SLA_PENDING_SECONDS,
        )
        from models import AuditAction

        old_created = (mock_now - timedelta(seconds=SLA_PENDING_SECONDS + 60)).isoformat()
        pending_jobs = [
            {
                "_id": "j1",
                "property_id": "p1",
                "client_id": "c1",
                "status": "PENDING",
                "attempts": 0,
                "created_at": old_created,
                "next_run_at": old_created,
                "last_error": None,
            }
        ]
        db = MagicMock()
        call_idx = [0]
        def find_return(*args, **kwargs):
            call_idx[0] += 1
            if call_idx[0] == 1:
                return AsyncCursor(pending_jobs)
            if call_idx[0] == 2:
                return AsyncCursor([])
            if call_idx[0] == 3:
                return AsyncCursor([])
            if call_idx[0] == 4:
                return AsyncCursor([])
            return AsyncCursor([])
        db.compliance_recalc_queue.find = MagicMock(side_effect=find_return)
        db.compliance_recalc_queue.find_one = AsyncMock(return_value=None)
        db.properties.find = MagicMock(return_value=AsyncCursor([]))
        db.compliance_sla_alerts.find_one = AsyncMock(return_value=None)
        db.compliance_sla_alerts.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
        db.compliance_sla_alerts.update_one = AsyncMock()

        with patch("services.compliance_sla_monitor.database.get_db", return_value=db):
            with patch("services.compliance_sla_monitor.datetime") as m_dt:
                m_dt.now.return_value = mock_now
                m_dt.side_effect = lambda *a, **k: datetime(*a, **k) if a else mock_now
            with patch("services.compliance_sla_monitor.create_audit_log", new_callable=AsyncMock) as audit:
                result = await run_compliance_recalc_sla_monitor()
        assert result.get("breaches", 0) >= 1
        audit.assert_called()
        call_actions = [getattr(c[1]["action"], "value", str(c[1]["action"])) for c in audit.call_args_list]
        assert "COMPLIANCE_RECALC_SLA_BREACH" in call_actions
        db.compliance_sla_alerts.update_one.assert_called()

    @pytest.mark.asyncio
    async def test_cooldown_dedupe_no_second_audit_or_send(self, mock_now):
        """Same stuck PENDING job on two runs: second run within cooldown only updates last_detected_at + count, no duplicate BREACH audit."""
        from services.compliance_sla_monitor import (
            run_compliance_recalc_sla_monitor,
            ALERT_PENDING_STUCK,
            SLA_PENDING_SECONDS,
        )

        old_created = (mock_now - timedelta(seconds=SLA_PENDING_SECONDS + 60)).isoformat()
        pending_job = {
            "_id": "j1",
            "property_id": "p1",
            "client_id": "c1",
            "status": "PENDING",
            "attempts": 0,
            "created_at": old_created,
            "next_run_at": old_created,
            "last_error": None,
        }

        def queue_find_return(filter, *args, **kwargs):
            # Return stuck PENDING job only for PENDING-status query (fresh list each call so both runs get one)
            if filter.get("status") == "PENDING":
                return AsyncCursor([dict(pending_job)])
            return AsyncCursor([])

        db = MagicMock()
        db.compliance_recalc_queue.find = MagicMock(side_effect=queue_find_return)
        db.compliance_recalc_queue.find_one = AsyncMock(return_value=None)
        db.properties.find = MagicMock(return_value=AsyncCursor([]))
        # First run: no existing alert. Second run: existing alert within cooldown.
        last_sent_within_cooldown = (mock_now - timedelta(seconds=10)).isoformat()
        existing_alert = {
            "property_id": "p1",
            "alert_type": ALERT_PENDING_STUCK,
            "active": True,
            "last_sent_at": last_sent_within_cooldown,
            "count": 1,
        }
        db.compliance_sla_alerts.find_one = AsyncMock(side_effect=[None, existing_alert])
        db.compliance_sla_alerts.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
        db.compliance_sla_alerts.update_one = AsyncMock()

        with patch("services.compliance_sla_monitor.database.get_db", return_value=db):
            with patch("services.compliance_sla_monitor.datetime") as m_dt:
                m_dt.now.return_value = mock_now
                m_dt.side_effect = lambda *a, **k: datetime(*a, **k) if a else mock_now
            with patch("services.compliance_sla_monitor.create_audit_log", new_callable=AsyncMock) as audit:
                result1 = await run_compliance_recalc_sla_monitor()
                result2 = await run_compliance_recalc_sla_monitor()

        assert result1.get("breaches", 0) == 1
        assert result2.get("breaches", 0) == 1
        breach_calls = [c for c in audit.call_args_list if getattr(c[1].get("action"), "value", str(c[1].get("action"))) == "COMPLIANCE_RECALC_SLA_BREACH"]
        assert len(breach_calls) == 1, "BREACH audit must be emitted only once (second run within cooldown must not re-send)"
        # First run: full upsert. Second run: update with $set + $inc only (cooldown path).
        updates = db.compliance_sla_alerts.update_one.call_args_list
        assert len(updates) >= 2
        second_update = updates[1][0][1]
        assert "$inc" in second_update and second_update["$inc"].get("count") == 1
        assert "$set" in second_update and "last_detected_at" in second_update["$set"]
        assert "last_sent_at" not in second_update["$set"]

    @pytest.mark.asyncio
    async def test_stuck_running_creates_crit_alert(self, mock_now):
        from services.compliance_sla_monitor import (
            run_compliance_recalc_sla_monitor,
            ALERT_RUNNING_STUCK,
            SLA_RUNNING_SECONDS,
        )

        old_updated = (mock_now - timedelta(seconds=SLA_RUNNING_SECONDS + 60)).isoformat()
        running_jobs = [
            {
                "_id": "j2",
                "property_id": "p2",
                "client_id": "c2",
                "status": "RUNNING",
                "attempts": 1,
                "updated_at": old_updated,
                "last_error": None,
            }
        ]
        db = MagicMock()
        call_idx = [0]
        def find_return(*args, **kwargs):
            call_idx[0] += 1
            if call_idx[0] == 1:
                return AsyncCursor([])
            if call_idx[0] == 2:
                return AsyncCursor(running_jobs)
            if call_idx[0] == 3:
                return AsyncCursor([])
            if call_idx[0] == 4:
                return AsyncCursor([])
            return AsyncCursor([])
        db.compliance_recalc_queue.find = MagicMock(side_effect=find_return)
        db.compliance_recalc_queue.find_one = AsyncMock(return_value=None)
        db.properties.find = MagicMock(return_value=AsyncCursor([]))
        db.compliance_sla_alerts.find_one = AsyncMock(return_value=None)
        db.compliance_sla_alerts.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
        db.compliance_sla_alerts.update_one = AsyncMock()

        with patch("services.compliance_sla_monitor.database.get_db", return_value=db):
            with patch("services.compliance_sla_monitor.datetime") as m_dt:
                m_dt.now.return_value = mock_now
                m_dt.side_effect = lambda *a, **k: datetime(*a, **k) if a else mock_now
            with patch("services.compliance_sla_monitor.create_audit_log", new_callable=AsyncMock):
                result = await run_compliance_recalc_sla_monitor()
        assert result.get("breaches", 0) >= 1
        call = db.compliance_sla_alerts.update_one.call_args
        if call and len(call[0]) >= 2:
            doc = call[0][1]
            if isinstance(doc, dict) and doc.get("$set"):
                assert doc["$set"].get("severity") == "CRIT"
                assert doc["$set"].get("alert_type") == ALERT_RUNNING_STUCK

    @pytest.mark.asyncio
    async def test_failed_attempts_3_warn_attempts_5_or_dead_crit(self, mock_now):
        from services.compliance_sla_monitor import (
            run_compliance_recalc_sla_monitor,
            ALERT_FAILING_REPEATEDLY,
            ALERT_DEAD_JOB,
            SLA_MAX_FAILURES_WARN,
            SLA_MAX_FAILURES_CRIT,
        )
        from services.compliance_recalc_queue import STATUS_FAILED, STATUS_DEAD

        db = MagicMock()
        # No PENDING/RUNNING stuck
        async def empty_cursor(*a, **k):
            return
            yield
        db.compliance_recalc_queue.find = MagicMock(return_value=empty_cursor())
        db.compliance_recalc_queue.find_one = AsyncMock(return_value=None)
        db.properties.find = MagicMock(return_value=AsyncMock(__aiter__=lambda _: iter([])))
        db.compliance_sla_alerts.find_one = AsyncMock(return_value=None)
        db.compliance_sla_alerts.find = MagicMock(return_value=AsyncMock(to_list=AsyncMock(return_value=[])))
        db.compliance_sla_alerts.update_one = AsyncMock()

        async def failed_jobs():
            yield {"_id": "j3", "property_id": "p3", "client_id": "c3", "status": STATUS_FAILED, "attempts": 3, "updated_at": mock_now.isoformat(), "last_error": "err"}
            yield {"_id": "j4", "property_id": "p4", "client_id": "c4", "status": STATUS_DEAD, "attempts": 5, "updated_at": mock_now.isoformat(), "last_error": "dead"}
        db.compliance_recalc_queue.find = MagicMock(return_value=failed_jobs())

        with patch("services.compliance_sla_monitor.database.get_db", return_value=db):
            with patch("services.compliance_sla_monitor.create_audit_log", new_callable=AsyncMock):
                result = await run_compliance_recalc_sla_monitor()
        assert result.get("breaches", 0) >= 2
        calls = db.compliance_sla_alerts.update_one.call_args_list
        severities = []
        for c in calls:
            if c[0] and len(c[0]) >= 2 and isinstance(c[0][1], dict) and c[0][1].get("$set"):
                severities.append((c[0][1]["$set"].get("alert_type"), c[0][1]["$set"].get("severity")))
        assert any(s[1] == "WARN" for s in severities)
        assert any(s[1] == "CRIT" for s in severities)

    @pytest.mark.asyncio
    async def test_job_done_resolves_alert(self, mock_now):
        from services.compliance_sla_monitor import run_compliance_recalc_sla_monitor, ALERT_PENDING_STUCK
        from services.compliance_recalc_queue import STATUS_DONE

        db = MagicMock()
        async def empty(*a, **k):
            return
            yield
        db.compliance_recalc_queue.find = MagicMock(return_value=empty())
        db.compliance_recalc_queue.find_one = AsyncMock(return_value=None)
        db.properties.find = MagicMock(return_value=AsyncMock(__aiter__=lambda _: iter([])))
        # One active PENDING_STUCK alert - no stuck job now => resolve
        db.compliance_sla_alerts.find_one = AsyncMock(return_value=None)
        db.compliance_sla_alerts.find = MagicMock(return_value=AsyncMock(to_list=AsyncMock(return_value=[
            {"property_id": "p1", "alert_type": ALERT_PENDING_STUCK, "client_id": "c1", "active": True},
        ])))
        db.compliance_sla_alerts.update_one = AsyncMock()

        with patch("services.compliance_sla_monitor.database.get_db", return_value=db):
            with patch("services.compliance_sla_monitor.create_audit_log", new_callable=AsyncMock) as audit:
                result = await run_compliance_recalc_sla_monitor()
        assert result.get("resolved", 0) >= 1
        # Should have RESOLVED audit and update_one setting active=False
        resolved_calls = [c for c in audit.call_args_list if getattr(c[1].get("action"), "value", str(c[1].get("action"))) == "COMPLIANCE_RECALC_SLA_RESOLVED"]
        assert len(resolved_calls) >= 1
