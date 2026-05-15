"""Incident lifecycle: fingerprint, suppression, deployment awareness."""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from services.incident_lifecycle_service import (
    LIFECYCLE_DEGRADED,
    LIFECYCLE_OPEN,
    compute_incident_fingerprint,
    is_deployment_suppression_active,
    record_operational_detection,
    suppression_window_seconds,
    try_transition_to_recovered,
)
from services.incident_service import SEVERITY_P0, SEVERITY_P1, SEVERITY_P2


def test_fingerprint_stable_for_same_condition():
    a = compute_incident_fingerprint(
        "job_monitor",
        related_job_name="sla_watchdog",
        triggering_reason="missed_sla",
    )
    b = compute_incident_fingerprint(
        "job_monitor",
        related_job_name="sla_watchdog",
        triggering_reason="missed_sla",
    )
    assert a == b
    c = compute_incident_fingerprint(
        "job_monitor",
        related_job_name="sla_watchdog",
        triggering_reason="degraded_run",
    )
    assert c != a


def test_suppression_windows_ordered_by_severity():
    assert suppression_window_seconds(SEVERITY_P0) <= suppression_window_seconds(SEVERITY_P1)
    assert suppression_window_seconds(SEVERITY_P1) <= suppression_window_seconds(SEVERITY_P2)


def test_deployment_suppression_from_env(monkeypatch):
    future = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    monkeypatch.setenv("PLATFORM_DEPLOY_SUPPRESSION_UNTIL", future)
    active, note = is_deployment_suppression_active()
    assert active is True
    assert note


@pytest.mark.asyncio
async def test_record_operational_detection_creates_with_lifecycle_fields(monkeypatch):
    oid = ObjectId()
    incidents = MagicMock()
    incidents.find_one = AsyncMock(return_value=None)
    incidents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=incidents)
    db.incidents = incidents
    db.portal_users = MagicMock()
    db.portal_users.find = MagicMock(
        return_value=MagicMock(to_list=AsyncMock(return_value=[]))
    )

    monkeypatch.setattr(
        "services.incident_lifecycle_service.database",
        MagicMock(get_db=lambda: db),
    )
    monkeypatch.setattr(
        "services.incident_service.database",
        MagicMock(get_db=lambda: db),
    )

    async def fake_create(*_a, **_k):
        return str(oid)

    monkeypatch.setattr(
        "services.incident_lifecycle_service.create_incident",
        fake_create,
    )

    outcome = await record_operational_detection(
        SEVERITY_P1,
        "Test incident",
        "Description",
        "job_monitor",
        related_job_name="compliance_recalc_worker",
        metadata={"triggering_reason": "missed_sla"},
    )
    assert outcome.created is True
    assert outcome.incident_id == str(oid)
    assert outcome.lifecycle_state == LIFECYCLE_OPEN
    assert incidents.update_one.await_count == 1
    set_doc = incidents.update_one.call_args[0][1]["$set"]
    assert set_doc["lifecycle_state"] == LIFECYCLE_OPEN
    assert set_doc["incident_fingerprint"]


@pytest.mark.asyncio
async def test_try_transition_to_recovered_requires_stable_window(monkeypatch):
    oid = ObjectId()
    now = datetime.now(timezone.utc)
    first_healthy = (now - timedelta(seconds=60)).isoformat()
    incidents = MagicMock()
    incidents.find_one = AsyncMock(
        return_value={
            "_id": oid,
            "status": "open",
            "lifecycle_state": LIFECYCLE_OPEN,
            "first_healthy_at": first_healthy,
            "recovery_email_sent_at": None,
            "first_detected_at": (now - timedelta(hours=1)).isoformat(),
            "created_at": (now - timedelta(hours=1)).isoformat(),
            "lifecycle_history": [],
        }
    )
    incidents.update_one = AsyncMock()
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=incidents)
    db.incidents = incidents
    monkeypatch.setattr(
        "services.incident_lifecycle_service.database",
        MagicMock(get_db=lambda: db),
    )
    monkeypatch.setattr(
        "services.incident_lifecycle_service.DEFAULT_RECOVERY_STABLE_SECONDS",
        300,
    )

    transitioned, should_send = await try_transition_to_recovered(
        str(oid),
        recovery_note="healthy again",
    )
    assert transitioned is False
    assert should_send is False


@pytest.mark.asyncio
async def test_repeat_missing_last_alert_retries_when_deploy_inactive(monkeypatch):
    """If initial email was suppressed and last_alert_email_at absent, retries when deploy window off."""
    oid = ObjectId()
    fingerprint = compute_incident_fingerprint(
        "job_monitor",
        related_job_name="x",
        triggering_reason="missed_sla",
    )
    now = datetime.now(timezone.utc)

    doc = {
        "_id": oid,
        "id": str(oid),
        "status": "open",
        "severity": SEVERITY_P2,
        "lifecycle_state": LIFECYCLE_OPEN,
        "repeat_count": 1,
        "first_detected_at": (now - timedelta(minutes=2)).isoformat(),
        "created_at": (now - timedelta(minutes=2)).isoformat(),
        "incident_fingerprint": fingerprint,
        "last_repeat_at": (now - timedelta(minutes=1)).isoformat(),
        "lifecycle_history": [],
        "health_transitions": [],
        "deployment_related_possible": True,
        "metadata": {"triggering_reason": "missed_sla"},
    }

    monkeypatch.delenv("PLATFORM_DEPLOY_SUPPRESSION_UNTIL", raising=False)

    incidents = MagicMock()
    incidents.find_one = AsyncMock(return_value=doc.copy())
    incidents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=incidents)
    db.incidents = incidents

    monkeypatch.setattr(
        "services.incident_lifecycle_service.database",
        MagicMock(get_db=lambda: db),
    )

    out = await record_operational_detection(
        SEVERITY_P2,
        "t",
        "d",
        "job_monitor",
        related_job_name="x",
        metadata={"triggering_reason": "missed_sla"},
    )
    assert out.created is False
    assert out.should_send_open_alert is True


@pytest.mark.asyncio
async def test_repeat_missing_last_alert_still_suppressed_during_deploy_p2(monkeypatch):
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    monkeypatch.setenv("PLATFORM_DEPLOY_SUPPRESSION_UNTIL", future)

    oid = ObjectId()
    fingerprint = compute_incident_fingerprint(
        "job_monitor",
        related_job_name="x",
        triggering_reason="missed_sla",
    )
    now = datetime.now(timezone.utc)

    doc = {
        "_id": oid,
        "id": str(oid),
        "status": "open",
        "severity": SEVERITY_P2,
        "lifecycle_state": LIFECYCLE_OPEN,
        "repeat_count": 1,
        "first_detected_at": (now - timedelta(minutes=5)).isoformat(),
        "created_at": (now - timedelta(minutes=5)).isoformat(),
        "incident_fingerprint": fingerprint,
        "metadata": {"triggering_reason": "missed_sla"},
        "lifecycle_history": [],
        "health_transitions": [],
    }

    incidents = MagicMock()
    incidents.find_one = AsyncMock(return_value=doc.copy())
    incidents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=incidents)
    db.incidents = incidents

    monkeypatch.setattr(
        "services.incident_lifecycle_service.database",
        MagicMock(get_db=lambda: db),
    )

    out = await record_operational_detection(
        SEVERITY_P2,
        "t",
        "d",
        "job_monitor",
        related_job_name="x",
        metadata={"triggering_reason": "missed_sla"},
    )
    assert out.created is False
    assert out.should_send_open_alert is False
    assert out.suppressed_reason == "deployment_window_p2_transient"


@pytest.mark.asyncio
async def test_severity_escalation_sends_even_when_deploy_suppressed_p2(monkeypatch):
    """P0 repeat should notify even inside deploy suppression window."""
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    monkeypatch.setenv("PLATFORM_DEPLOY_SUPPRESSION_UNTIL", future)

    oid = ObjectId()
    fingerprint = compute_incident_fingerprint(
        "job_monitor",
        related_job_name="x",
        triggering_reason="missed_sla",
    )
    now = datetime.now(timezone.utc)

    doc = {
        "_id": oid,
        "id": str(oid),
        "status": "open",
        "severity": SEVERITY_P2,
        "lifecycle_state": LIFECYCLE_OPEN,
        "repeat_count": 5,
        "first_detected_at": (now - timedelta(minutes=30)).isoformat(),
        "created_at": (now - timedelta(minutes=30)).isoformat(),
        "incident_fingerprint": fingerprint,
        "last_alert_email_at": now.isoformat(),
        "metadata": {"triggering_reason": "missed_sla"},
        "lifecycle_history": [],
        "health_transitions": [],
    }

    incidents = MagicMock()
    incidents.find_one = AsyncMock(return_value=doc.copy())
    incidents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=incidents)
    db.incidents = incidents

    monkeypatch.setattr(
        "services.incident_lifecycle_service.database",
        MagicMock(get_db=lambda: db),
    )

    out = await record_operational_detection(
        SEVERITY_P0,
        "Critical",
        "d",
        "job_monitor",
        related_job_name="x",
        metadata={"triggering_reason": "missed_sla"},
    )
    assert out.created is False
    assert out.should_send_open_alert is True
    assert out.escalation_level_changed is True
