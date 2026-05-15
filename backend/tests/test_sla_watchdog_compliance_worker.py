"""SLA watchdog still flags genuinely missed compliance_recalc_worker runs (job_runs)."""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


@pytest.mark.asyncio
async def test_watchdog_creates_incident_when_compliance_worker_overdue():
    from services.sla_watchdog import run_sla_watchdog
    from services.incident_lifecycle_service import DetectionOutcome, LIFECYCLE_OPEN

    real_now = datetime.now(timezone.utc)
    old_finish = (real_now - timedelta(days=1)).isoformat()

    mock_db = MagicMock()
    mock_db.scheduler_heartbeat = MagicMock()
    mock_db.scheduler_heartbeat.find_one = AsyncMock(return_value={"last_heartbeat_at": real_now.isoformat()})

    jr = MagicMock()

    async def job_runs_find_one(filter, *args, **kwargs):
        if filter.get("job_name") == "compliance_recalc_worker":
            return {"finished_at": old_finish, "status": "success"}
        return None

    jr.find_one = AsyncMock(side_effect=job_runs_find_one)
    jr.count_documents = AsyncMock(return_value=0)
    mock_db.job_runs = jr

    def _coll(name):
        if name == "job_runs":
            return jr
        if name == "scheduler_heartbeat":
            return mock_db.scheduler_heartbeat
        if name == "incidents":
            return mock_db.incidents
        return MagicMock(find_one=AsyncMock(return_value=None), count_documents=AsyncMock(return_value=0))

    mock_db.__getitem__.side_effect = _coll

    mock_db.incidents = MagicMock()
    mock_db.incidents.find_one = AsyncMock(return_value=None)
    mock_db.incidents.update_one = AsyncMock()

    fake_config = [("compliance_recalc_worker", 1, 10, "P2", "compliance worker must run")]

    from bson import ObjectId

    oid_inc = ObjectId()

    async def fake_record_detection(*args, **kwargs):
        # Only count the missed-SLA path for compliance_recalc_worker
        if kwargs.get("related_job_name") == "compliance_recalc_worker":
            return DetectionOutcome(
                incident_id=str(oid_inc),
                created=True,
                should_send_open_alert=True,
                lifecycle_state=LIFECYCLE_OPEN,
                repeat_count=1,
            )
        return DetectionOutcome(
            incident_id="ffffffffffffffffffffffff",
            created=False,
            should_send_open_alert=False,
            lifecycle_state=LIFECYCLE_OPEN,
            repeat_count=0,
        )

    with patch("services.sla_watchdog.database.get_db", return_value=mock_db):
        with patch(
            "services.incident_recovery.check_and_resolve_heartbeat_incidents",
            new_callable=AsyncMock,
            return_value=0,
        ):
            with patch(
                "services.incident_recovery.check_and_resolve_delivery_unknown_incidents",
                new_callable=AsyncMock,
                return_value=0,
            ):
                with patch(
                    "services.incident_recovery.check_and_resolve_risk_regen_queue_incidents",
                    new_callable=AsyncMock,
                    return_value=0,
                ):
                    with patch("services.sla_watchdog._get_scheduler_next_runs", return_value={}):
                        with patch("services.sla_watchdog.DEFAULT_SLA_CONFIG", fake_config):
                            with patch(
                                "services.sla_watchdog.record_operational_detection",
                                new_callable=AsyncMock,
                                side_effect=fake_record_detection,
                            ):
                                with patch(
                                    "services.sla_watchdog._send_incident_alert_email",
                                    new_callable=AsyncMock,
                                    return_value=True,
                                ):
                                    out = await run_sla_watchdog()

    assert out.get("incidents_created", 0) >= 1


@pytest.mark.asyncio
async def test_run_sla_watchdog_stale_heartbeat_queries_incidents_with_open_status_no_nameerror():
    """Regression: module-level STATUS_OPEN for heartbeat dedupe (fixes prod NameError)."""
    from services.incident_service import SOURCE_HEARTBEAT, STATUS_OPEN
    from services.sla_watchdog import run_sla_watchdog

    real_now = datetime.now(timezone.utc)
    stale_hb = (real_now - timedelta(seconds=400)).isoformat()

    mock_db = MagicMock()
    mock_db.scheduler_heartbeat = MagicMock()
    mock_db.scheduler_heartbeat.find_one = AsyncMock(return_value={"last_heartbeat_at": stale_hb})

    mock_incidents = MagicMock()
    mock_incidents.find_one = AsyncMock(return_value=None)
    mock_incidents.update_one = AsyncMock()

    jr = MagicMock()
    jr.find_one = AsyncMock(return_value=None)
    jr.count_documents = AsyncMock(return_value=0)
    mock_db.job_runs = jr
    mock_db.incidents = mock_incidents

    def _coll(name):
        if name == "job_runs":
            return jr
        if name == "scheduler_heartbeat":
            return mock_db.scheduler_heartbeat
        if name == "incidents":
            return mock_db.incidents
        return MagicMock(find_one=AsyncMock(return_value=None), count_documents=AsyncMock(return_value=0))

    mock_db.__getitem__.side_effect = _coll

    with patch("services.sla_watchdog.database.get_db", return_value=mock_db):
        with patch(
            "services.incident_recovery.check_and_resolve_heartbeat_incidents",
            new_callable=AsyncMock,
            return_value=0,
        ):
            with patch(
                "services.incident_recovery.check_and_resolve_delivery_unknown_incidents",
                new_callable=AsyncMock,
                return_value=0,
            ):
                with patch(
                    "services.incident_recovery.check_and_resolve_risk_regen_queue_incidents",
                    new_callable=AsyncMock,
                    return_value=0,
                ):
                    with patch("services.sla_watchdog._get_scheduler_next_runs", return_value={}):
                        with patch("services.sla_watchdog.DEFAULT_SLA_CONFIG", []):
                            with patch(
                                "services.sla_watchdog.create_incident",
                                new_callable=AsyncMock,
                                return_value="inc_test_hb",
                            ):
                                with patch(
                                    "services.sla_watchdog._send_incident_alert_email",
                                    new_callable=AsyncMock,
                                    return_value=False,
                                ):
                                    out = await run_sla_watchdog()

    assert out.get("incidents_created") == 1
    mock_incidents.find_one.assert_called()
    filt = mock_incidents.find_one.call_args[0][0]
    assert filt["status"] == STATUS_OPEN
    assert filt["source"] == SOURCE_HEARTBEAT
