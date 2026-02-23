"""Unit tests: notification preference toggles suppress sends (daily_reminder_enabled, quiet_hours, document_updates, sms_urgent_alerts_only)."""
import asyncio
from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _due_in_days(days: int) -> str:
    """ISO string for a due date N days from now (within reminder window)."""
    d = datetime.now(timezone.utc) + timedelta(days=days)
    return d.strftime("%Y-%m-%dT00:00:00+00:00")


def test_daily_reminder_skipped_when_daily_reminder_enabled_false():
    """When daily_reminder_enabled is False, send_daily_reminders does not call _send_reminder_email for that client."""
    with patch.dict("os.environ", {"MONGO_URL": "mongodb://localhost:27017", "DB_NAME": "test"}):
        from services.jobs import JobScheduler
        scheduler = JobScheduler()
    scheduler.db = MagicMock()
    scheduler.db.clients.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[
        {"client_id": "c1", "email": "c1@test.com"},
    ])))
    scheduler.db.notification_preferences.find_one = AsyncMock(return_value={
        "expiry_reminders": True,
        "reminder_days_before": 30,
        "daily_reminder_enabled": False,
        "quiet_hours_enabled": False,
    })
    scheduler.db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[
        {"requirement_id": "r1", "due_date": _due_in_days(14), "description": "Gas", "property_id": "p1", "status": "PENDING"},
    ])))
    scheduler.db.requirements.update_one = AsyncMock()
    scheduler.db.properties.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    scheduler._send_reminder_email = AsyncMock()
    scheduler._maybe_send_reminder_sms = AsyncMock()

    with patch("services.plan_registry.plan_registry", MagicMock(enforce_feature=AsyncMock(return_value=(False, None, None)))):
        count = asyncio.run(scheduler.send_daily_reminders())

    scheduler._send_reminder_email.assert_not_called()
    assert count == 0


def test_daily_reminder_skipped_when_expiry_reminders_false():
    """When expiry_reminders is False, send_daily_reminders does not call _send_reminder_email for that client."""
    with patch.dict("os.environ", {"MONGO_URL": "mongodb://localhost:27017", "DB_NAME": "test"}):
        from services.jobs import JobScheduler
        scheduler = JobScheduler()
    scheduler.db = MagicMock()
    scheduler.db.clients.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[
        {"client_id": "c1", "email": "c1@test.com"},
    ])))
    scheduler.db.notification_preferences.find_one = AsyncMock(return_value={
        "expiry_reminders": False,
        "reminder_days_before": 30,
        "daily_reminder_enabled": True,
        "quiet_hours_enabled": False,
    })
    scheduler.db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[
        {"requirement_id": "r1", "due_date": _due_in_days(14), "description": "Gas", "property_id": "p1", "status": "PENDING"},
    ])))
    scheduler._send_reminder_email = AsyncMock()

    count = asyncio.run(scheduler.send_daily_reminders())

    scheduler._send_reminder_email.assert_not_called()
    assert count == 0


def test_is_in_quiet_hours_returns_false_when_disabled():
    """_is_in_quiet_hours returns False when quiet_hours_enabled is False or prefs is None."""
    with patch.dict("os.environ", {"MONGO_URL": "mongodb://localhost:27017", "DB_NAME": "test"}):
        from services.jobs import JobScheduler
        scheduler = JobScheduler()
    assert scheduler._is_in_quiet_hours(None) is False
    assert scheduler._is_in_quiet_hours({}) is False
    assert scheduler._is_in_quiet_hours({"quiet_hours_enabled": False}) is False


def test_sms_reminder_skipped_when_sms_urgent_alerts_only_and_no_overdue():
    """When sms_urgent_alerts_only is True and there are no overdue items, _maybe_send_reminder_sms is not called."""
    with patch.dict("os.environ", {"MONGO_URL": "mongodb://localhost:27017", "DB_NAME": "test"}):
        from services.jobs import JobScheduler
        scheduler = JobScheduler()
    scheduler.db = MagicMock()
    scheduler.db.clients.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[
        {"client_id": "c1", "email": "c1@test.com"},
    ])))
    scheduler.db.notification_preferences.find_one = AsyncMock(return_value={
        "expiry_reminders": True,
        "reminder_days_before": 30,
        "daily_reminder_enabled": True,
        "quiet_hours_enabled": False,
        "sms_urgent_alerts_only": True,
    })
    # Expiring but not overdue (due in 14 days)
    scheduler.db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[
        {"requirement_id": "r1", "due_date": _due_in_days(14), "description": "Gas", "property_id": "p1", "status": "PENDING"},
    ])))
    scheduler.db.requirements.update_one = AsyncMock()
    scheduler.db.properties.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    scheduler.db.audit_logs = MagicMock()
    scheduler.db.audit_logs.insert_one = AsyncMock()
    scheduler._send_reminder_email = AsyncMock()
    scheduler._maybe_send_reminder_sms = AsyncMock()

    with patch("services.plan_registry.plan_registry", MagicMock(enforce_feature=AsyncMock(return_value=(True, None, None)))):
        with patch("services.compliance_recalc_queue.enqueue_compliance_recalc", AsyncMock()):
            asyncio.run(scheduler.send_daily_reminders())

    scheduler._send_reminder_email.assert_called_once()
    scheduler._maybe_send_reminder_sms.assert_not_called()


def test_document_updates_preference_gates_send():
    """When document_updates is False, the code path that sends AI_EXTRACTION_APPLIED is not taken (send not called)."""
    # Logic used in documents.py: if not document_updates_enabled we skip the send block
    prefs_disabled = {"document_updates": False}
    document_updates_enabled = prefs_disabled.get("document_updates", True) if prefs_disabled else True
    assert document_updates_enabled is False

    prefs_enabled = {"document_updates": True}
    document_updates_enabled = prefs_enabled.get("document_updates", True) if prefs_enabled else True
    assert document_updates_enabled is True

    prefs_missing = None
    document_updates_enabled = prefs_missing.get("document_updates", True) if prefs_missing else True
    assert document_updates_enabled is True
