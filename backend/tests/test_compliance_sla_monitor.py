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


def _actionable_eligibility(client_id="c1", lifecycle="ACTIVE"):
    from services.compliance_recalc_sla_eligibility import (
        ComplianceRecalcSlaClass,
        ComplianceRecalcSlaEligibility,
    )

    return ComplianceRecalcSlaEligibility(
        sla_class=ComplianceRecalcSlaClass.ACTIONABLE,
        lifecycle_state=lifecycle,
        decision="CONTINUE",
        reason="test_actionable",
    )


def _eligibility(sla_class, lifecycle, decision, reason="test"):
    from services.compliance_recalc_sla_eligibility import ComplianceRecalcSlaEligibility

    return ComplianceRecalcSlaEligibility(
        sla_class=sla_class,
        lifecycle_state=lifecycle,
        decision=decision,
        reason=reason,
    )


class TestComplianceRecalcSlaMonitor:
    """SLA monitor creates alerts + audit, dedupes within cooldown, resolves when condition clears."""

    @pytest.fixture(autouse=True)
    def _actionable_by_default(self):
        """Existing tests model ACTIVE-eligible work; lifecycle gating is covered separately."""

        async def _fake(db, client_id, cache=None):
            return _actionable_eligibility(client_id)

        with patch(
            "services.compliance_sla_monitor.resolve_compliance_recalc_sla_eligibility",
            side_effect=_fake,
        ):
            yield

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
        fail_items = [
            {"_id": "j3", "property_id": "p3", "client_id": "c3", "status": STATUS_FAILED, "attempts": 3, "updated_at": mock_now.isoformat(), "last_error": "err"},
            {"_id": "j4", "property_id": "p4", "client_id": "c4", "status": STATUS_DEAD, "attempts": 5, "updated_at": mock_now.isoformat(), "last_error": "dead"},
        ]

        def queue_find_return(filter, *args, **kwargs):
            st = filter.get("status")
            if st == "PENDING":
                return AsyncCursor([])
            if st == "RUNNING":
                return AsyncCursor([])
            if isinstance(st, dict) and "$in" in st:
                return AsyncCursor(list(fail_items))
            return AsyncCursor([])

        db.compliance_recalc_queue.find = MagicMock(side_effect=queue_find_return)
        db.compliance_recalc_queue.find_one = AsyncMock(return_value=None)
        db.properties.find = MagicMock(return_value=AsyncCursor([]))
        db.compliance_sla_alerts.find_one = AsyncMock(return_value=None)
        db.compliance_sla_alerts.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
        db.compliance_sla_alerts.update_one = AsyncMock()

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
    async def test_running_stale_query_uses_liveness_expr(self, mock_now):
        """RUNNING breach scan must use $expr liveness (heartbeat_at vs updated_at)."""
        from services.compliance_sla_monitor import run_compliance_recalc_sla_monitor

        filters_seen = []

        def queue_find(filt, *args, **kwargs):
            filters_seen.append(filt)
            st = filt.get("status")
            if st == "PENDING":
                return AsyncCursor([])
            if st == "RUNNING" or (isinstance(st, str) and st == "RUNNING"):
                return AsyncCursor([])
            if isinstance(st, dict) and "$in" in st:
                return AsyncCursor([])
            return AsyncCursor([])

        db = MagicMock()
        db.compliance_recalc_queue.find = MagicMock(side_effect=queue_find)
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
                    await run_compliance_recalc_sla_monitor()

        running_filters = [f for f in filters_seen if f.get("status") == "RUNNING"]
        assert running_filters, "expected a RUNNING-status scan"
        assert "$expr" in running_filters[0]

    @pytest.mark.asyncio
    async def test_grouped_pending_and_property_single_email(self, mock_now):
        """PENDING_STUCK + PROPERTY_PENDING_TOO_LONG same property → one composite email."""
        from services.compliance_sla_monitor import (
            run_compliance_recalc_sla_monitor,
            ALERT_QUEUE_PROPERTY_COMPOSITE,
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
        prop_doc = {
            "property_id": "p1",
            "client_id": "c1",
            "compliance_last_calculated_at": None,
        }

        def queue_find(filt, *args, **kwargs):
            st = filt.get("status")
            if st == "PENDING":
                return AsyncCursor([dict(pending_job)])
            if st == "RUNNING":
                return AsyncCursor([])
            if isinstance(st, dict) and "$in" in st:
                return AsyncCursor([])
            return AsyncCursor([])

        db = MagicMock()
        db.compliance_recalc_queue.find = MagicMock(side_effect=queue_find)
        db.compliance_recalc_queue.find_one = AsyncMock(return_value=None)

        def properties_find(filter, *args, **kwargs):
            if filter.get("compliance_score_pending") is True:
                return AsyncCursor([prop_doc])
            return AsyncCursor([])

        db.properties.find = MagicMock(side_effect=properties_find)
        db.compliance_sla_alerts.find_one = AsyncMock(return_value=None)
        db.compliance_sla_alerts.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
        db.compliance_sla_alerts.update_one = AsyncMock()

        with patch("services.compliance_sla_monitor.database.get_db", return_value=db):
            with patch("services.compliance_sla_monitor.datetime") as m_dt:
                m_dt.now.return_value = mock_now
                m_dt.side_effect = lambda *a, **k: datetime(*a, **k) if a else mock_now
                with patch("services.compliance_sla_monitor.create_audit_log", new_callable=AsyncMock):
                    with patch("services.compliance_sla_monitor._send_alert_email", new_callable=AsyncMock) as send:
                        await run_compliance_recalc_sla_monitor()

        assert send.call_count == 1
        args, kwargs = send.call_args
        assert args[0] == ALERT_QUEUE_PROPERTY_COMPOSITE
        assert "grouped_signals" in (args[4] or {})

    @pytest.mark.asyncio
    async def test_job_done_resolves_alert(self, mock_now):
        from services.compliance_sla_monitor import run_compliance_recalc_sla_monitor, ALERT_PENDING_STUCK
        from services.compliance_recalc_queue import STATUS_DONE

        db = MagicMock()

        def queue_find_return(filter, *args, **kwargs):
            return AsyncCursor([])

        db.compliance_recalc_queue.find = MagicMock(side_effect=queue_find_return)
        db.compliance_recalc_queue.find_one = AsyncMock(return_value=None)
        db.properties.find = MagicMock(return_value=AsyncCursor([]))
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

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "last_calculated_at",
        [None, "stale_iso"],
        ids=["missing_last_calculated", "stale_last_calculated"],
    )
    async def test_property_pending_too_long_creates_warn_alert_and_breach_audit(
        self, mock_now, last_calculated_at
    ):
        from services.compliance_sla_monitor import (
            run_compliance_recalc_sla_monitor,
            ALERT_PROPERTY_PENDING_TOO_LONG,
            SLA_PENDING_SECONDS,
            SEVERITY_WARN,
        )

        stale_iso = (mock_now - timedelta(seconds=SLA_PENDING_SECONDS + 60)).isoformat()
        prop_doc = {
            "property_id": "p_pending_long",
            "client_id": "c_pending",
            "compliance_last_calculated_at": stale_iso if last_calculated_at == "stale_iso" else last_calculated_at,
        }

        db = MagicMock()
        db.compliance_recalc_queue.find = MagicMock(side_effect=lambda *a, **k: AsyncCursor([]))
        db.compliance_recalc_queue.find_one = AsyncMock(return_value=None)

        def properties_find(filter, *args, **kwargs):
            if filter.get("compliance_score_pending") is True:
                return AsyncCursor([prop_doc])
            return AsyncCursor([])

        db.properties.find = MagicMock(side_effect=properties_find)
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
        breach_calls = [
            c
            for c in audit.call_args_list
            if getattr(c[1]["action"], "value", str(c[1]["action"])) == "COMPLIANCE_RECALC_SLA_BREACH"
        ]
        assert len(breach_calls) >= 1
        meta = breach_calls[0][1]["metadata"]
        assert meta.get("alert_type") == ALERT_PROPERTY_PENDING_TOO_LONG
        assert meta.get("severity") == SEVERITY_WARN
        assert meta.get("property_id") == "p_pending_long"

        upserts = [
            c
            for c in db.compliance_sla_alerts.update_one.call_args_list
            if c[0] and len(c[0]) >= 2 and isinstance(c[0][1], dict) and c[0][1].get("$set")
        ]
        assert any(
            c[0][1]["$set"].get("alert_type") == ALERT_PROPERTY_PENDING_TOO_LONG
            and c[0][1]["$set"].get("severity") == SEVERITY_WARN
            for c in upserts
        )

    @pytest.mark.asyncio
    async def test_outcome_metrics_include_evaluated_breaches_resolved(self, mock_now):
        from services.compliance_sla_monitor import run_compliance_recalc_sla_monitor

        db = MagicMock()
        db.compliance_recalc_queue.find = MagicMock(side_effect=lambda *a, **k: AsyncCursor([]))
        db.compliance_recalc_queue.find_one = AsyncMock(return_value=None)
        db.properties.find = MagicMock(return_value=AsyncCursor([]))
        db.compliance_sla_alerts.find_one = AsyncMock(return_value=None)
        db.compliance_sla_alerts.find = MagicMock(
            return_value=MagicMock(to_list=AsyncMock(return_value=[]))
        )
        db.compliance_sla_alerts.update_one = AsyncMock()

        with patch("services.compliance_sla_monitor.database.get_db", return_value=db):
            with patch("services.compliance_sla_monitor.datetime") as m_dt:
                m_dt.now.return_value = mock_now
                m_dt.side_effect = lambda *a, **k: datetime(*a, **k) if a else mock_now
                with patch("services.compliance_sla_monitor.create_audit_log", new_callable=AsyncMock):
                    result = await run_compliance_recalc_sla_monitor()

        om = result.get("outcome_metrics") or {}
        assert result.get("outcome_status") == "success"
        assert om.get("outcome_kind") == "SLA_CHECK_COMPLETED"
        assert "evaluated" in om
        assert "lifecycle_suppressed" in om
        assert "breaches" in om
        assert "resolved" in om
        assert om["breaches"] == result["breaches"]
        assert om["resolved"] == result["resolved"]


def _sla_db(*, pending_jobs=None, running_jobs=None, failed_jobs=None, pending_props=None, active_alerts=None):
    pending_jobs = list(pending_jobs or [])
    running_jobs = list(running_jobs or [])
    failed_jobs = list(failed_jobs or [])
    pending_props = list(pending_props or [])
    active_alerts = list(active_alerts or [])

    def queue_find(filt, *args, **kwargs):
        st = filt.get("status")
        if st == "PENDING":
            return AsyncCursor([dict(j) for j in pending_jobs])
        if st == "RUNNING":
            return AsyncCursor([dict(j) for j in running_jobs])
        if isinstance(st, dict) and "$in" in st:
            return AsyncCursor([dict(j) for j in failed_jobs])
        return AsyncCursor([])

    db = MagicMock()
    db.compliance_recalc_queue.find = MagicMock(side_effect=queue_find)
    db.compliance_recalc_queue.find_one = AsyncMock(return_value=None)
    db.properties.find = MagicMock(
        side_effect=lambda filt, *a, **k: AsyncCursor([dict(p) for p in pending_props])
        if filt.get("compliance_score_pending") is True
        else AsyncCursor([])
    )
    db.properties.find_one = AsyncMock(return_value=None)
    db.compliance_sla_alerts.find_one = AsyncMock(return_value=None)
    db.compliance_sla_alerts.find = MagicMock(
        return_value=MagicMock(to_list=AsyncMock(return_value=active_alerts))
    )
    db.compliance_sla_alerts.update_one = AsyncMock()
    return db


async def _run_monitor(db, mock_now):
    from services.compliance_sla_monitor import run_compliance_recalc_sla_monitor

    with patch("services.compliance_sla_monitor.database.get_db", return_value=db):
        with patch("services.compliance_sla_monitor.datetime") as m_dt:
            m_dt.now.return_value = mock_now
            m_dt.side_effect = lambda *a, **k: datetime(*a, **k) if a else mock_now
            with patch("services.compliance_sla_monitor.create_audit_log", new_callable=AsyncMock) as audit:
                result = await run_compliance_recalc_sla_monitor()
    return result, audit


class TestComplianceSlaLifecycleActionability:
    """Per-client lifecycle eligibility: suppressed work must not storm; ACTIVE failures must still page."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "lifecycle,sla_class,decision,expect_breach",
        [
            ("ACTIVE", "ACTIONABLE", "CONTINUE", True),
            ("TRIAL", "ACTIONABLE", "CONTINUE", True),
            ("GRACE_PERIOD", "ACTIONABLE", "CONTINUE", True),
            ("PAYMENT_PENDING", "LIFECYCLE_SUPPRESSED", "SKIP", False),
            ("SUSPENDED", "LIFECYCLE_SUPPRESSED", "PAUSE", False),
            ("CANCELLED_IMMEDIATE", "LIFECYCLE_SUPPRESSED", "PAUSE", False),
            ("ACCOUNT_DELETED", "TERMINATED", "TERMINATE", False),
            ("ARCHIVED", "TERMINATED", "TERMINATE", False),
            ("UNKNOWN", "UNKNOWN_SAFE_SKIP", "SKIP", False),
        ],
    )
    async def test_pending_stuck_and_property_pending_by_lifecycle(
        self, mock_now, lifecycle, sla_class, decision, expect_breach
    ):
        from services.compliance_recalc_sla_eligibility import ComplianceRecalcSlaClass
        from services.compliance_sla_monitor import SLA_PENDING_SECONDS

        cls = ComplianceRecalcSlaClass(sla_class)
        old_created = (mock_now - timedelta(seconds=SLA_PENDING_SECONDS + 60)).isoformat()
        pending_job = {
            "_id": "j-life",
            "property_id": "p-life",
            "client_id": "c-life",
            "status": "PENDING",
            "attempts": 0,
            "created_at": old_created,
            "next_run_at": old_created,
            "last_error": None,
        }
        prop_doc = {
            "property_id": "p-life",
            "client_id": "c-life",
            "compliance_last_calculated_at": None,
        }
        db = _sla_db(pending_jobs=[pending_job], pending_props=[prop_doc])

        async def _fake(_db, client_id, cache=None):
            return _eligibility(cls, lifecycle, decision, reason=f"test_{lifecycle}")

        with patch(
            "services.compliance_sla_monitor.resolve_compliance_recalc_sla_eligibility",
            side_effect=_fake,
        ):
            result, audit = await _run_monitor(db, mock_now)

        om = result["outcome_metrics"]
        if expect_breach:
            assert result["breaches"] >= 2
            assert om["actionable"] >= 1
            breach_calls = [
                c
                for c in audit.call_args_list
                if getattr(c[1].get("action"), "value", str(c[1].get("action")))
                == "COMPLIANCE_RECALC_SLA_BREACH"
            ]
            assert len(breach_calls) >= 2
        else:
            assert result["breaches"] == 0
            assert db.compliance_sla_alerts.update_one.call_count == 0
            bucket = {
                "LIFECYCLE_SUPPRESSED": "lifecycle_suppressed",
                "TERMINATED": "terminal",
                "UNKNOWN_SAFE_SKIP": "unknown_safe_skip",
            }[sla_class]
            assert om[bucket] >= 1
            assert om["evaluated"] >= 1

    @pytest.mark.asyncio
    async def test_ineligible_client_does_not_skip_entire_monitor(self, mock_now):
        from services.compliance_recalc_sla_eligibility import ComplianceRecalcSlaClass
        from services.compliance_sla_monitor import SLA_PENDING_SECONDS

        old_created = (mock_now - timedelta(seconds=SLA_PENDING_SECONDS + 60)).isoformat()
        jobs = [
            {
                "_id": "j-suppressed",
                "property_id": "p-suppressed",
                "client_id": "c-suppressed",
                "status": "PENDING",
                "attempts": 0,
                "created_at": old_created,
                "next_run_at": old_created,
                "last_error": None,
            },
            {
                "_id": "j-active",
                "property_id": "p-active",
                "client_id": "c-active",
                "status": "PENDING",
                "attempts": 0,
                "created_at": old_created,
                "next_run_at": old_created,
                "last_error": None,
            },
        ]
        db = _sla_db(pending_jobs=jobs)

        async def _fake(_db, client_id, cache=None):
            if client_id == "c-suppressed":
                return _eligibility(
                    ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED,
                    "PAYMENT_PENDING",
                    "SKIP",
                )
            return _actionable_eligibility(client_id)

        with patch(
            "services.compliance_sla_monitor.resolve_compliance_recalc_sla_eligibility",
            side_effect=_fake,
        ):
            result, audit = await _run_monitor(db, mock_now)

        assert result["breaches"] == 1
        assert result["outcome_metrics"]["lifecycle_suppressed"] >= 1
        assert result["outcome_metrics"]["actionable"] >= 1
        meta_props = [
            c[1]["metadata"].get("property_id")
            for c in audit.call_args_list
            if getattr(c[1].get("action"), "value", str(c[1].get("action")))
            == "COMPLIANCE_RECALC_SLA_BREACH"
        ]
        assert "p-active" in meta_props
        assert "p-suppressed" not in meta_props

    @pytest.mark.asyncio
    async def test_active_running_stuck_still_crit(self, mock_now):
        from services.compliance_sla_monitor import ALERT_RUNNING_STUCK, SLA_RUNNING_SECONDS

        old_updated = (mock_now - timedelta(seconds=SLA_RUNNING_SECONDS + 60)).isoformat()
        running_jobs = [
            {
                "_id": "j-run",
                "property_id": "p-run",
                "client_id": "c-run",
                "status": "RUNNING",
                "attempts": 1,
                "updated_at": old_updated,
                "last_error": None,
            }
        ]
        db = _sla_db(running_jobs=running_jobs)

        async def _fake(_db, client_id, cache=None):
            return _actionable_eligibility(client_id)

        with patch(
            "services.compliance_sla_monitor.resolve_compliance_recalc_sla_eligibility",
            side_effect=_fake,
        ):
            result, _audit = await _run_monitor(db, mock_now)

        assert result["breaches"] >= 1
        call = db.compliance_sla_alerts.update_one.call_args
        doc = call[0][1]
        assert doc["$set"].get("severity") == "CRIT"
        assert doc["$set"].get("alert_type") == ALERT_RUNNING_STUCK

    @pytest.mark.asyncio
    async def test_active_failed_and_dead_remain_intact(self, mock_now):
        from services.compliance_recalc_queue import STATUS_DEAD, STATUS_FAILED

        failed_jobs = [
            {
                "_id": "j-fail",
                "property_id": "p-fail",
                "client_id": "c-fail",
                "status": STATUS_FAILED,
                "attempts": 3,
                "updated_at": mock_now.isoformat(),
                "last_error": "err",
            },
            {
                "_id": "j-dead",
                "property_id": "p-dead",
                "client_id": "c-dead",
                "status": STATUS_DEAD,
                "attempts": 5,
                "updated_at": mock_now.isoformat(),
                "last_error": "dead",
            },
        ]
        db = _sla_db(failed_jobs=failed_jobs)

        async def _fake(_db, client_id, cache=None):
            return _actionable_eligibility(client_id)

        with patch(
            "services.compliance_sla_monitor.resolve_compliance_recalc_sla_eligibility",
            side_effect=_fake,
        ):
            result, _audit = await _run_monitor(db, mock_now)

        assert result["breaches"] >= 2

    @pytest.mark.asyncio
    async def test_suppressed_failed_dead_does_not_page(self, mock_now):
        from services.compliance_recalc_queue import STATUS_DEAD, STATUS_FAILED
        from services.compliance_recalc_sla_eligibility import ComplianceRecalcSlaClass

        failed_jobs = [
            {
                "_id": "j-fail",
                "property_id": "p-fail",
                "client_id": "c-pay",
                "status": STATUS_FAILED,
                "attempts": 3,
                "updated_at": mock_now.isoformat(),
                "last_error": "err",
            },
            {
                "_id": "j-dead",
                "property_id": "p-dead",
                "client_id": "c-del",
                "status": STATUS_DEAD,
                "attempts": 5,
                "updated_at": mock_now.isoformat(),
                "last_error": "dead",
            },
        ]
        db = _sla_db(failed_jobs=failed_jobs)

        async def _fake(_db, client_id, cache=None):
            if client_id == "c-del":
                return _eligibility(ComplianceRecalcSlaClass.TERMINATED, "ACCOUNT_DELETED", "TERMINATE")
            return _eligibility(
                ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED, "PAYMENT_PENDING", "SKIP"
            )

        with patch(
            "services.compliance_sla_monitor.resolve_compliance_recalc_sla_eligibility",
            side_effect=_fake,
        ):
            result, _audit = await _run_monitor(db, mock_now)

        assert result["breaches"] == 0
        assert result["outcome_metrics"]["lifecycle_suppressed"] >= 1
        assert result["outcome_metrics"]["terminal"] >= 1

    @pytest.mark.asyncio
    async def test_lifecycle_change_resolves_prior_alert(self, mock_now):
        from services.compliance_recalc_sla_eligibility import ComplianceRecalcSlaClass
        from services.compliance_sla_monitor import ALERT_PROPERTY_PENDING_TOO_LONG, SLA_PENDING_SECONDS

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
        db = _sla_db(
            pending_jobs=[pending_job],
            active_alerts=[
                {
                    "property_id": "p1",
                    "alert_type": ALERT_PROPERTY_PENDING_TOO_LONG,
                    "client_id": "c1",
                    "active": True,
                }
            ],
        )
        db.compliance_sla_alerts.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

        async def _fake(_db, client_id, cache=None):
            return _eligibility(
                ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED, "SUSPENDED", "PAUSE"
            )

        with patch(
            "services.compliance_sla_monitor.resolve_compliance_recalc_sla_eligibility",
            side_effect=_fake,
        ):
            result, audit = await _run_monitor(db, mock_now)

        assert result["breaches"] == 0
        assert result["resolved"] >= 1
        resolved_calls = [
            c
            for c in audit.call_args_list
            if getattr(c[1].get("action"), "value", str(c[1].get("action")))
            == "COMPLIANCE_RECALC_SLA_RESOLVED"
        ]
        assert len(resolved_calls) >= 1

    @pytest.mark.asyncio
    async def test_active_property_pending_clears_resolves(self, mock_now):
        from services.compliance_sla_monitor import ALERT_PROPERTY_PENDING_TOO_LONG

        db = _sla_db(
            active_alerts=[
                {
                    "property_id": "p1",
                    "alert_type": ALERT_PROPERTY_PENDING_TOO_LONG,
                    "client_id": "c1",
                    "active": True,
                }
            ]
        )
        db.properties.find_one = AsyncMock(
            return_value={"property_id": "p1", "compliance_score_pending": False}
        )
        db.compliance_sla_alerts.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

        async def _fake(_db, client_id, cache=None):
            return _actionable_eligibility(client_id)

        with patch(
            "services.compliance_sla_monitor.resolve_compliance_recalc_sla_eligibility",
            side_effect=_fake,
        ):
            result, audit = await _run_monitor(db, mock_now)

        assert result["resolved"] >= 1
        resolved_calls = [
            c
            for c in audit.call_args_list
            if getattr(c[1].get("action"), "value", str(c[1].get("action")))
            == "COMPLIANCE_RECALC_SLA_RESOLVED"
        ]
        assert len(resolved_calls) >= 1

    @pytest.mark.asyncio
    async def test_suppressed_does_not_send_composite_email(self, mock_now):
        from services.compliance_recalc_sla_eligibility import ComplianceRecalcSlaClass
        from services.compliance_sla_monitor import SLA_PENDING_SECONDS, run_compliance_recalc_sla_monitor

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
        prop_doc = {"property_id": "p1", "client_id": "c1", "compliance_last_calculated_at": None}
        db = _sla_db(pending_jobs=[pending_job], pending_props=[prop_doc])

        async def _fake(_db, client_id, cache=None):
            return _eligibility(
                ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED, "PAYMENT_PENDING", "SKIP"
            )

        with patch("services.compliance_sla_monitor.database.get_db", return_value=db):
            with patch("services.compliance_sla_monitor.datetime") as m_dt:
                m_dt.now.return_value = mock_now
                m_dt.side_effect = lambda *a, **k: datetime(*a, **k) if a else mock_now
                with patch("services.compliance_sla_monitor.create_audit_log", new_callable=AsyncMock):
                    with patch(
                        "services.compliance_sla_monitor._send_alert_email", new_callable=AsyncMock
                    ) as send:
                        with patch(
                            "services.compliance_sla_monitor.resolve_compliance_recalc_sla_eligibility",
                            side_effect=_fake,
                        ):
                            await run_compliance_recalc_sla_monitor()

        assert send.call_count == 0
