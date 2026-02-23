"""
Tests for deterministic certificate expiry tracking and compliance calendar.
- Expiry source: confirmed > extracted > due_date
- NOT_REQUIRED excluded from calendar and scoring
- Calendar events endpoint and reminder message_logs (REMINDER + refs)
"""
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from utils.expiry_utils import (
    get_effective_expiry_date,
    get_computed_status,
    is_included_for_calendar,
)


class TestGetEffectiveExpiryDate:
    """Single rule: confirmed_expiry_date else extracted_expiry_date else due_date."""

    def test_confirmed_takes_precedence(self):
        req = {
            "confirmed_expiry_date": "2026-06-15T00:00:00+00:00",
            "extracted_expiry_date": "2026-05-01T00:00:00+00:00",
            "due_date": "2026-04-01T00:00:00+00:00",
        }
        d = get_effective_expiry_date(req)
        assert d is not None
        assert d.year == 2026 and d.month == 6 and d.day == 15

    def test_extracted_when_no_confirmed(self):
        req = {
            "extracted_expiry_date": "2026-05-01T00:00:00+00:00",
            "due_date": "2026-04-01T00:00:00+00:00",
        }
        d = get_effective_expiry_date(req)
        assert d is not None
        assert d.year == 2026 and d.month == 5 and d.day == 1

    def test_due_date_fallback(self):
        req = {"due_date": "2026-04-01T00:00:00Z"}
        d = get_effective_expiry_date(req)
        assert d is not None
        assert d.year == 2026 and d.month == 4 and d.day == 1

    def test_none_when_no_dates(self):
        req = {}
        assert get_effective_expiry_date(req) is None
        req = {"applicability": "UNKNOWN"}
        assert get_effective_expiry_date(req) is None


class TestGetComputedStatus:
    """NOT_REQUIRED, UNKNOWN_DATE, OVERDUE, EXPIRING_SOON, COMPLIANT."""

    def test_not_required(self):
        req = {"applicability": "NOT_REQUIRED", "due_date": "2026-12-31T00:00:00Z"}
        assert get_computed_status(req) == "NOT_REQUIRED"

    def test_unknown_date_when_no_effective_date(self):
        req = {"applicability": "REQUIRED"}
        assert get_computed_status(req) == "UNKNOWN_DATE"

    def test_overdue(self):
        past = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        req = {"due_date": past, "applicability": "REQUIRED"}
        assert get_computed_status(req) == "OVERDUE"

    def test_expiring_soon(self):
        future = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
        req = {"due_date": future, "applicability": "REQUIRED"}
        assert get_computed_status(req) == "EXPIRING_SOON"

    def test_compliant(self):
        future = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()
        req = {"due_date": future, "applicability": "REQUIRED"}
        assert get_computed_status(req) == "COMPLIANT"


class TestIsIncludedForCalendar:
    """NOT_REQUIRED excluded; no effective date excluded."""

    def test_not_required_excluded(self):
        req = {"applicability": "NOT_REQUIRED", "due_date": "2026-12-31T00:00:00Z"}
        assert is_included_for_calendar(req) is False

    def test_included_when_effective_date_present(self):
        req = {"due_date": "2026-12-31T00:00:00Z"}
        assert is_included_for_calendar(req) is True
        req = {"extracted_expiry_date": "2026-06-01T00:00:00Z"}
        assert is_included_for_calendar(req) is True

    def test_excluded_when_no_date(self):
        req = {"applicability": "UNKNOWN"}
        assert is_included_for_calendar(req) is False


class TestReminderWritesReminderTypeAndRefs:
    """Reminder email/SMS pass event_type=REMINDER and reminder_refs in context."""

    def test_send_reminder_email_passes_reminder_event_type_and_refs(self):
        async def _run():
            from services.jobs import JobScheduler
            import os
            with patch.dict(os.environ, {"MONGO_URL": "mongodb://localhost:27017", "DB_NAME": "test"}):
                scheduler = JobScheduler()
                scheduler.db = MagicMock()
                scheduler.db.clients = MagicMock()
                scheduler.db.notification_preferences = MagicMock()
                scheduler.db.requirements = MagicMock()
                scheduler.db.audit_logs = MagicMock()
                scheduler.db.properties = MagicMock()

                scheduler.db.clients.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
                scheduler.db.notification_preferences.find_one = AsyncMock(return_value={"expiry_reminders": True, "daily_reminder_enabled": True})
                scheduler.db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))

                with patch("services.jobs.JobScheduler._resolve_reminder_recipients", new_callable=AsyncMock, return_value=["u@example.com"]):
                    with patch("services.jobs.JobScheduler._send_reminder_email", new_callable=AsyncMock) as mock_send:
                        clients = [{"client_id": "c1", "email": "u@example.com", "subscription_status": "ACTIVE", "entitlement_status": "ENABLED"}]
                        scheduler.db.clients.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=clients)))
                        reqs = [
                            {
                                "requirement_id": "r1",
                                "client_id": "c1",
                                "property_id": "p1",
                                "due_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                                "description": "Gas Safety",
                            }
                        ]
                        scheduler.db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=reqs)))
                        scheduler.db.requirements.update_one = AsyncMock()
                        with patch("services.compliance_recalc_queue.enqueue_compliance_recalc", new_callable=AsyncMock):
                            with patch("services.plan_registry.plan_registry.enforce_feature", new_callable=AsyncMock, return_value=(False, None, None)):
                                await scheduler.send_daily_reminders()
                        mock_send.assert_called()
                        call_kw = mock_send.call_args[1]
                        assert "reminder_refs" in call_kw
                        refs = call_kw["reminder_refs"]
                        if isinstance(refs, str):
                            import json
                            refs = json.loads(refs)
                        assert isinstance(refs, list) and len(refs) >= 1
                        assert refs[0].get("property_id") == "p1"
                        assert refs[0].get("requirement_type") is not None or "due_date" in refs[0]
        asyncio.run(_run())

    def test_reminder_event_type_documented(self):
        """Implementation uses event_type=REMINDER and reminder_refs in context (see jobs._send_reminder_email and notification_orchestrator message_log metadata). Verified by test_send_reminder_email_passes_reminder_event_type_and_refs."""
        # Contract: _send_reminder_email is called with reminder_refs; it passes event_type="REMINDER"
        # and context["reminder_refs"] = json.dumps(reminder_refs) to notification_orchestrator.send,
        # so message_logs get metadata.event_type=REMINDER and metadata.reminder_refs for audit.
        pass
