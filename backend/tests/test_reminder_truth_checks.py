import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch


def _iso_in_days(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


class _AsyncCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def __aiter__(self):
        self._idx = 0
        return self

    async def __anext__(self):
        if self._idx >= len(self._rows):
            raise StopAsyncIteration
        row = self._rows[self._idx]
        self._idx += 1
        return row


def test_daily_reminder_suppresses_already_compliant_requirement():
    async def _run():
        import os
        from services.jobs import JobScheduler
        with patch.dict(os.environ, {"MONGO_URL": "mongodb://localhost:27017", "DB_NAME": "test"}):
            scheduler = JobScheduler()
        scheduler.db = MagicMock()
        scheduler.db.clients.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[
            {"client_id": "c1", "email": "c1@test.com", "subscription_status": "ACTIVE", "entitlement_status": "ENABLED"},
        ])))
        scheduler.db.clients.find_one = AsyncMock(
            return_value={"client_id": "c1", "default_jurisdiction": "England"}
        )
        scheduler.db.notification_preferences.find_one = AsyncMock(return_value={
            "expiry_reminders": True,
            "reminder_days_before": 30,
            "daily_reminder_enabled": True,
            "quiet_hours_enabled": False,
        })
        scheduler.db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[
            {
                "requirement_id": "r1",
                "client_id": "c1",
                "property_id": "p1",
                "requirement_type": "gas_safety",
                "due_date": _iso_in_days(10),
                "status": "PENDING",
                "applicability": "REQUIRED",
                "client_surface_visible": True,
            },
        ])))
        scheduler.db.requirements.find_one = AsyncMock(return_value={
            "requirement_id": "r1",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_type": "gas_safety",
            "due_date": _iso_in_days(10),
            "status": "COMPLIANT",
            "applicability": "REQUIRED",
            "client_surface_visible": True,
        })
        scheduler.db.requirements.update_one = AsyncMock()
        scheduler.db.properties.find = MagicMock(
            return_value=_AsyncCursor(
                [
                    {
                        "property_id": "p1",
                        "client_id": "c1",
                        "jurisdiction": "England",
                        "property_type": "house",
                        "has_gas_supply": True,
                    }
                ]
            )
        )
        scheduler.db.properties.find_one = AsyncMock(
            return_value={
                "property_id": "p1",
                "client_id": "c1",
                "jurisdiction": "England",
                "property_type": "house",
                "has_gas_supply": True,
            }
        )
        scheduler.db.reminder_item_state.find_one = AsyncMock(return_value=None)
        scheduler.db.reminder_item_state.update_one = AsyncMock()
        scheduler.db.reminder_evaluation_log.insert_one = AsyncMock()
        scheduler._send_reminder_email = AsyncMock(return_value=True)
        scheduler._maybe_send_reminder_sms = AsyncMock()
        with patch("services.plan_registry.plan_registry.enforce_feature", new_callable=AsyncMock, return_value=(False, None, None)):
            result = await scheduler.send_daily_reminders()
        assert result["count"] == 0
        scheduler._send_reminder_email.assert_not_called()
        assert result["outcome_metrics"]["suppressed_items_count"] >= 1
    asyncio.run(_run())


def test_pending_verification_digest_suppressed_when_zero_pending():
    async def _run():
        import os
        from services.jobs import JobScheduler
        with patch.dict(os.environ, {"MONGO_URL": "mongodb://localhost:27017", "DB_NAME": "test"}):
            scheduler = JobScheduler()
        scheduler.db = MagicMock()
        scheduler.db.documents.count_documents = AsyncMock(side_effect=[0, 0])
        scheduler.db.portal_users.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[
            {"auth_email": "admin@example.com"},
        ])))
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock) as audit_mock:
            result = await scheduler.send_pending_verification_digest()
        assert result["count"] == 0
        assert result["outcome_metrics"]["suppression_reason"] == "ZERO_PENDING_ITEMS"
        audit_mock.assert_called_once()
    asyncio.run(_run())


def test_reminder_cooldown_env_override_matrix():
    import os
    from services.reminder_truth_service import get_reminder_cooldown_hours

    with patch.dict(os.environ, {"REMINDER_COOLDOWN_HOURS_DAILY_COMPLIANCE_EXPIRY_EMAIL": "72"}):
        assert get_reminder_cooldown_hours("DAILY_COMPLIANCE_EXPIRY_EMAIL") == 72
    with patch.dict(os.environ, {"REMINDER_COOLDOWN_HOURS_DAILY_COMPLIANCE_EXPIRY_EMAIL": "invalid"}):
        assert get_reminder_cooldown_hours("DAILY_COMPLIANCE_EXPIRY_EMAIL") == 24
