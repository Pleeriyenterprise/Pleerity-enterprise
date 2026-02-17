"""
Enterprise notification tests: throttling, failure spike monitor, health APIs, plan gate SMS.
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


@pytest.mark.asyncio
async def test_global_throttle_exceeded_defers_and_enqueues_retry():
    """When per-minute limit is reached, send returns DEFERRED_THROTTLED, MessageLog updated, retry enqueued, no provider call."""
    from services.notification_orchestrator import notification_orchestrator, NotificationResult

    db = MagicMock()
    db.notification_templates.find_one = AsyncMock(return_value={
        "template_key": "OTP_CODE_SMS",
        "channel": "SMS",
        "sms_body": "{{body}}",
        "requires_provisioned": False,
        "is_active": True,
    })
    db.message_logs.find_one = AsyncMock(return_value=None)
    db.message_logs.insert_one = AsyncMock()
    db.message_logs.count_documents = AsyncMock(return_value=30)
    db.message_logs.update_one = AsyncMock()
    db.notification_retry_queue.insert_one = AsyncMock()

    with patch("services.notification_orchestrator.database.get_db", return_value=db):
        with patch("services.notification_orchestrator.NOTIFICATION_SMS_PER_MINUTE_LIMIT", 30):
            with patch("services.notification_orchestrator.create_audit_log", new_callable=AsyncMock) as audit:
                result = await notification_orchestrator.send(
                    template_key="OTP_CODE_SMS",
                    client_id=None,
                    context={"recipient": "+447700900123", "body": "Code 123456"},
                    idempotency_key="test-otp-1",
                )
    assert result.outcome == "blocked"
    assert result.block_reason == "DEFERRED_THROTTLED"
    db.message_logs.update_one.assert_called_once()
    update_call = db.message_logs.update_one.call_args[0]
    assert update_call[1]["$set"]["status"] == "DEFERRED_THROTTLED"
    db.notification_retry_queue.insert_one.assert_called_once()
    audit_calls = [c.kwargs.get("action") for c in audit.call_args_list]
    assert any(getattr(a, "value", str(a)) == "NOTIFICATION_THROTTLED" for a in audit_calls)


@pytest.mark.asyncio
async def test_failure_spike_monitor_breach_sends_audit_and_alert_respects_cooldown():
    """When failed_count >= WARN threshold, NOTIFICATION_FAILURE_SPIKE_DETECTED audit; when within cooldown, no duplicate alert."""
    from services.notification_failure_spike_monitor import run_notification_failure_spike_monitor

    db = MagicMock()
    since = datetime.now(timezone.utc) - timedelta(minutes=15)
    db.message_logs.count_documents = AsyncMock(return_value=12)
    db.message_logs.aggregate = lambda *a, **kw: _AsyncAggregateCursor([])
    db.notification_spike_cooldown.find_one = AsyncMock(return_value=None)
    db.notification_spike_cooldown.update_one = AsyncMock()

    with patch("services.notification_failure_spike_monitor.database.get_db", return_value=db):
        with patch("services.notification_failure_spike_monitor.create_audit_log", new_callable=AsyncMock) as audit:
            with patch("services.notification_failure_spike_monitor._admin_recipients", return_value=["ops@test.com"]):
                with patch("services.notification_failure_spike_monitor.notification_orchestrator.send", new_callable=AsyncMock) as orch_send:
                    from services.notification_orchestrator import NotificationResult
                    orch_send.return_value = NotificationResult(outcome="sent", message_id="m1")
                    result = await run_notification_failure_spike_monitor()
    assert result.get("breached") is True
    assert result.get("severity") == "WARN"
    assert result.get("failed_count") == 12
    audit_calls = [c.kwargs.get("action") for c in audit.call_args_list]
    assert any(getattr(a, "value", str(a)) == "NOTIFICATION_FAILURE_SPIKE_DETECTED" for a in audit_calls)
    orch_send.assert_called()

    db.notification_spike_cooldown.find_one = AsyncMock(return_value={
        "last_sent_at": datetime.now(timezone.utc),
        "severity": "WARN",
    })
    with patch("services.notification_failure_spike_monitor.database.get_db", return_value=db):
        with patch("services.notification_failure_spike_monitor.NOTIFICATION_SPIKE_COOLDOWN_SECONDS", 3600):
            with patch("services.notification_failure_spike_monitor.create_audit_log", new_callable=AsyncMock) as audit2:
                with patch("services.notification_failure_spike_monitor._admin_recipients", return_value=["ops@test.com"]):
                    with patch("services.notification_failure_spike_monitor.notification_orchestrator.send", new_callable=AsyncMock) as orch_send2:
                        result2 = await run_notification_failure_spike_monitor()
    assert result2.get("breached") is True
    assert result2.get("cooldown") is True
    assert result2.get("alert_sent") is False
    orch_send2.assert_not_called()


class _AsyncAggregateCursor:
    def __init__(self, items):
        self._items = list(items)
        self._i = 0
    def __aiter__(self):
        return self
    async def __anext__(self):
        if self._i >= len(self._items):
            raise StopAsyncIteration
        self._i += 1
        return self._items[self._i - 1]


@pytest.mark.asyncio
async def test_notification_health_summary_returns_aggregates():
    """GET notification-health/summary returns sent/failed counts, throttled_count, top_failed_templates (mock DB)."""
    from routes.admin import get_notification_health_summary

    db = MagicMock()
    db.message_logs.count_documents = AsyncMock(side_effect=[10, 2, 5, 1, 3])
    top_templates = [{"_id": "PAYMENT_FAILED", "count": 2}, {"_id": "OTP_CODE_SMS", "count": 1}]
    top_reasons = [{"_id": "timeout", "count": 2}]
    n = [0]
    def agg_mock(*args, **kwargs):
        n[0] += 1
        return _AsyncAggregateCursor(top_templates if n[0] == 1 else top_reasons)
    db.message_logs.aggregate = agg_mock

    req = MagicMock()
    req.state = MagicMock()
    req.state.user = {"role": "admin"}

    with patch("routes.admin.database.get_db", return_value=db):
        with patch("routes.admin.admin_route_guard", new_callable=AsyncMock):
            response = await get_notification_health_summary(req, window_minutes=60)
    assert "sent_email_count" in response
    assert "failed_email_count" in response
    assert "sent_sms_count" in response
    assert "failed_sms_count" in response
    assert "throttled_count" in response
    assert "top_failed_templates" in response
    assert "top_failure_reasons" in response
    assert response["window_minutes"] == 60


@pytest.mark.asyncio
async def test_compliance_expiry_reminder_sms_pro_allowed_solo_denied():
    """COMPLIANCE_EXPIRY_REMINDER_SMS: plan_registry enforce_feature sms_reminders allowed for Pro, denied for Solo."""
    from services.notification_orchestrator import notification_orchestrator

    db = MagicMock()
    db.notification_templates.find_one = AsyncMock(return_value={
        "template_key": "COMPLIANCE_EXPIRY_REMINDER_SMS",
        "channel": "SMS",
        "sms_body": "{{count}} items",
        "requires_provisioned": True,
        "requires_active_subscription": True,
        "requires_entitlement_enabled": True,
        "plan_required_feature_key": "sms_reminders",
        "is_active": True,
    })
    db.clients.find_one = AsyncMock(return_value={
        "client_id": "c1",
        "email": "u@test.com",
        "onboarding_status": "PROVISIONED",
        "subscription_status": "ACTIVE",
        "entitlement_status": "ENABLED",
    })
    db.notification_preferences.find_one = AsyncMock(return_value={"sms_enabled": True, "sms_phone_number": "+447700900111"})
    db.message_logs.find_one = AsyncMock(return_value=None)
    db.message_logs.insert_one = AsyncMock()
    db.message_logs.count_documents = AsyncMock(return_value=0)

    with patch("services.notification_orchestrator.database.get_db", return_value=db):
        with patch("services.notification_orchestrator.plan_registry.enforce_feature", new_callable=AsyncMock) as enforce:
            enforce.return_value = (False, "SMS reminders not available on your plan", None)
            result = await notification_orchestrator.send(
                template_key="COMPLIANCE_EXPIRY_REMINDER_SMS",
                client_id="c1",
                context={"count": 2, "portal_link": "https://x/portal"},
                idempotency_key="c1_sms_reminder_1",
            )
    assert result.outcome == "blocked"
    assert result.block_reason == "BLOCKED_PLAN_GATE"

    with patch("services.notification_orchestrator.database.get_db", return_value=db):
        with patch("services.notification_orchestrator.plan_registry.enforce_feature", new_callable=AsyncMock) as enforce2:
            enforce2.return_value = (True, None, None)
            db.message_logs.count_documents = AsyncMock(return_value=0)
            result2 = await notification_orchestrator.send(
                template_key="COMPLIANCE_EXPIRY_REMINDER_SMS",
                client_id="c1",
                context={"count": 2, "portal_link": "https://x/portal"},
                idempotency_key="c1_sms_reminder_2",
            )
    assert result2.outcome != "blocked" or result2.block_reason != "BLOCKED_PLAN_GATE"
