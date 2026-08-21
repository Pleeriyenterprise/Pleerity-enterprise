"""
Outcome metrics on execution/monitor jobs + Control Centre no-expected-outcome heuristic.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.control_centre_no_expected_outcome_flag import (
    should_flag_no_expected_outcome_control_centre,
)
from services.job_schedule_registry import JOB_STATE_HEALTHY


def _flag(jid, detail):
    return should_flag_no_expected_outcome_control_centre(
        jid,
        zero_output_ok=False,
        job_state=JOB_STATE_HEALTHY,
        detail=detail,
    )


@pytest.mark.asyncio
async def test_scheduler_heartbeat_return_has_metrics_and_not_flagged():
    from job_runner import run_scheduler_heartbeat, HEARTBEAT_COLLECTION

    coll = MagicMock()
    coll.update_one = AsyncMock()

    class _FakeDb:
        def __getitem__(self, key):
            if key == HEARTBEAT_COLLECTION:
                return coll
            raise KeyError(key)

    with patch("database.database.get_db", return_value=_FakeDb()):
        result = await run_scheduler_heartbeat()
    om = result.get("outcome_metrics") or {}
    assert om.get("attempted_count") == 1
    assert om.get("success_count") == 1
    assert om.get("heartbeat_written") is True
    assert om.get("outcome_kind") == "WORK_PERFORMED"
    detail = {
        "last_run_status": "success",
        "last_outcome_status": "success",
        "outcome_metrics": om,
    }
    assert _flag("scheduler_heartbeat", detail) is False


@pytest.mark.asyncio
async def test_notification_spike_monitor_no_spike_metrics_not_flagged():
    from services.notification_failure_spike_monitor import run_notification_failure_spike_monitor

    class _EmptyAgg:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    db = MagicMock()
    db.message_logs.count_documents = AsyncMock(return_value=0)
    db.message_logs.aggregate = MagicMock(side_effect=[_EmptyAgg(), _EmptyAgg()])

    with patch("services.notification_failure_spike_monitor.database.get_db", return_value=db):
        result = await run_notification_failure_spike_monitor()
    assert result.get("breached") is False
    om = result["outcome_metrics"]
    assert om["outcome_kind"] == "NO_SPIKE_DETECTED"
    assert om["attempted_count"] == 1
    assert om["success_count"] == 1
    detail = {"last_run_status": "success", "last_outcome_status": "success", "outcome_metrics": om}
    assert _flag("notification_failure_spike_monitor", detail) is False


@pytest.mark.asyncio
async def test_notification_spike_monitor_breach_metrics_visible_not_no_outcome_flag():
    from services.notification_failure_spike_monitor import run_notification_failure_spike_monitor

    class _EmptyAgg:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    db = MagicMock()
    db.message_logs.count_documents = AsyncMock(return_value=30)
    db.message_logs.aggregate = MagicMock(side_effect=[_EmptyAgg(), _EmptyAgg()])
    db.notification_spike_cooldown.find_one = AsyncMock(return_value=None)
    db.notification_spike_cooldown.update_one = AsyncMock()

    with patch("services.notification_failure_spike_monitor.database.get_db", return_value=db):
        with patch("services.notification_failure_spike_monitor.create_audit_log", new_callable=AsyncMock):
            with patch("services.notification_failure_spike_monitor._admin_recipients", return_value=[]):
                result = await run_notification_failure_spike_monitor()
    assert result.get("breached") is True
    om = result["outcome_metrics"]
    assert om["outcome_kind"] == "SPIKE_DETECTED"
    assert om["failed_count"] == 30
    assert om["breached"] is True
    detail = {"last_run_status": "success", "last_outcome_status": "success", "outcome_metrics": om}
    assert _flag("notification_failure_spike_monitor", detail) is False


def test_sla_watchdog_all_clear_detail_not_flagged():
    om = {
        "checks_run": 1,
        "incidents_created": 0,
        "alerts_sent": 0,
        "recovered": 0,
        "attempted_count": 1,
        "success_count": 1,
        "failed_count": 0,
        "outcome_kind": "SLA_CHECK_COMPLETED",
    }
    detail = {"last_run_status": "success", "last_outcome_status": "success", "outcome_metrics": om}
    assert _flag("sla_watchdog", detail) is False


def test_sla_watchdog_incidents_created_still_not_false_positive_no_outcome():
    om = {
        "checks_run": 1,
        "incidents_created": 2,
        "alerts_sent": 1,
        "recovered": 0,
        "attempted_count": 1,
        "success_count": 1,
        "failed_count": 0,
        "outcome_kind": "SLA_CHECK_COMPLETED",
    }
    detail = {"last_run_status": "success", "last_outcome_status": "success", "outcome_metrics": om}
    assert _flag("sla_watchdog", detail) is False


@pytest.mark.asyncio
async def test_expiry_rollover_no_properties_conditional_no_output_not_flagged():
    from job_runner import run_expiry_rollover_recalc

    class _EmptyCursor:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    db = MagicMock()
    db.requirements.find = MagicMock(return_value=_EmptyCursor())

    with patch("database.database.get_db", return_value=db):
        result = await run_expiry_rollover_recalc()
    assert result.get("count") == 0
    assert result.get("outcome_status") == "conditional_no_output"
    om = result["outcome_metrics"]
    assert om["properties_considered"] == 0
    assert om["properties_enqueued"] == 0
    assert om["outcome_kind"] == "NO_WORK_ELIGIBLE"
    detail = {
        "last_run_status": "success",
        "last_outcome_status": result["outcome_status"],
        "outcome_metrics": om,
    }
    assert _flag("expiry_rollover_recalc", detail) is False


@pytest.mark.asyncio
async def test_expiry_rollover_enqueued_work_not_flagged():
    from job_runner import run_expiry_rollover_recalc
    from services.compliance_recalc_sla_eligibility import (
        ComplianceRecalcSlaClass,
        ComplianceRecalcSlaEligibility,
    )

    items = [{"property_id": "p1"}]

    class _OneRowCursor:
        def __aiter__(self):
            return self

        def __init__(self):
            self._i = 0

        async def __anext__(self):
            if self._i >= len(items):
                raise StopAsyncIteration
            v = items[self._i]
            self._i += 1
            return v

    db = MagicMock()
    db.requirements.find = MagicMock(return_value=_OneRowCursor())
    db.properties.find_one = AsyncMock(return_value={"client_id": "c1"})
    actionable = ComplianceRecalcSlaEligibility(
        sla_class=ComplianceRecalcSlaClass.ACTIONABLE,
        lifecycle_state="ACTIVE",
        decision="CONTINUE",
        reason="test",
    )

    with patch("database.database.get_db", return_value=db):
        with patch(
            "services.compliance_recalc_queue.enqueue_compliance_recalc",
            new_callable=AsyncMock,
            return_value=True,
        ):
            with patch(
                "services.compliance_recalc_sla_eligibility.resolve_compliance_recalc_sla_eligibility",
                new_callable=AsyncMock,
                return_value=actionable,
            ):
                result = await run_expiry_rollover_recalc()
    assert result.get("count") == 1
    om = result["outcome_metrics"]
    assert om["properties_considered"] == 1
    assert om["properties_enqueued"] == 1
    assert om["outcome_kind"] == "WORK_PERFORMED"
    detail = {"last_run_status": "success", "last_outcome_status": "success", "outcome_metrics": om}
    assert _flag("expiry_rollover_recalc", detail) is False


def test_structured_zero_attempt_still_flags_expiry_not_broad_suppression():
    """Narrow telemetry gate must not hide a genuinely anomalous structured row."""
    detail = {
        "last_run_status": "success",
        "last_outcome_status": "success",
        "outcome_metrics": {
            "attempted_count": 0,
            "success_count": 0,
            "properties_considered": 5,
            "properties_enqueued": 0,
            "failed_count": 0,
            "outcome_kind": "WORK_PERFORMED",
        },
    }
    assert _flag("expiry_rollover_recalc", detail) is True


def test_compliance_recalc_sla_monitor_metrics_are_structured_and_not_false_positive():
    from services.compliance_sla_monitor import build_compliance_recalc_sla_monitor_run_result

    result = build_compliance_recalc_sla_monitor_run_result(
        {
            "evaluated": 10,
            "actionable": 1,
            "lifecycle_suppressed": 8,
            "terminal": 1,
            "unknown_safe_skip": 0,
            "breaches": 1,
            "resolved": 2,
        }
    )
    om = result["outcome_metrics"]
    assert om["outcome_kind"] == "SLA_CHECK_COMPLETED"
    assert om["evaluated"] == 10
    assert om["lifecycle_suppressed"] == 8
    assert om["breaches"] == 1
    assert om["resolved"] == 2
    detail = {
        "last_run_status": "success",
        "last_outcome_status": result["outcome_status"],
        "outcome_metrics": om,
    }
    assert _flag("compliance_recalc_sla_monitor", detail) is False
