"""
Acceptance tests for enterprise notification orchestrator.
- Welcome blocked before PROVISIONED → 403 + audit
- Billing email allowed pre-provisioning
- Professional SMS allowed
- Solo SMS → 403 PLAN_GATE_DENIED
- Duplicate idempotency_key does not duplicate send
- Delivery webhook updates MessageLog
- Missing provider env does not crash
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


@pytest.mark.asyncio
async def test_welcome_blocked_before_provisioned_returns_403_and_audit():
    """WELCOME_EMAIL when onboarding_status != PROVISIONED → blocked, 403 ACCOUNT_NOT_READY, audit."""
    from services.notification_orchestrator import notification_orchestrator

    db = MagicMock()
    db.notification_templates.find_one = AsyncMock(return_value={
        "template_key": "WELCOME_EMAIL",
        "channel": "EMAIL",
        "requires_provisioned": True,
        "requires_active_subscription": False,
        "requires_entitlement_enabled": False,
        "plan_required_feature_key": None,
        "is_active": True,
    })
    db.clients.find_one = AsyncMock(return_value={
        "client_id": "c1",
        "email": "u@test.com",
        "onboarding_status": "PROVISIONING",
        "subscription_status": "ACTIVE",
        "entitlement_status": "ENABLED",
    })
    db.notification_preferences.find_one = AsyncMock(return_value=None)
    db.message_logs.find_one = AsyncMock(return_value=None)
    db.message_logs.insert_one = AsyncMock()

    with patch("services.notification_orchestrator.database.get_db", return_value=db):
        with patch("services.notification_orchestrator.create_audit_log", new_callable=AsyncMock) as audit:
            result = await notification_orchestrator.send(
                template_key="WELCOME_EMAIL",
                client_id="c1",
                context={"setup_link": "https://x/set-password", "client_name": "Test"},
                idempotency_key=None,
            )
    assert result.outcome == "blocked"
    assert result.block_reason == "BLOCKED_PROVISIONING_INCOMPLETE"
    assert result.status_code == 403
    assert result.details.get("error_code") == "ACCOUNT_NOT_READY"
    assert audit.await_count >= 1
    call_actions = [c.kwargs.get("action") for c in audit.call_args_list]
    assert any(
        getattr(a, "value", str(a)) == "NOTIFICATION_BLOCKED_PROVISIONING_INCOMPLETE"
        for a in call_actions
    )


@pytest.mark.asyncio
async def test_billing_email_allowed_pre_provisioning():
    """SUBSCRIPTION_CONFIRMED or PAYMENT_FAILED can be sent when client not yet PROVISIONED."""
    from services.notification_orchestrator import notification_orchestrator

    db = MagicMock()
    db.notification_templates.find_one = AsyncMock(return_value={
        "template_key": "SUBSCRIPTION_CONFIRMED",
        "channel": "EMAIL",
        "email_template_alias": "payment-receipt",
        "requires_provisioned": False,
        "requires_active_subscription": False,
        "requires_entitlement_enabled": False,
        "plan_required_feature_key": None,
        "is_active": True,
    })
    db.clients.find_one = AsyncMock(return_value={
        "client_id": "c1",
        "email": "u@test.com",
        "contact_email": "u@test.com",
        "onboarding_status": "PROVISIONING",
        "subscription_status": "ACTIVE",
        "entitlement_status": "ENABLED",
    })
    db.notification_preferences.find_one = AsyncMock(return_value=None)
    db.message_logs.find_one = AsyncMock(return_value=None)
    db.message_logs.insert_one = AsyncMock()
    db.message_logs.update_one = AsyncMock()
    db.email_templates.find_one = AsyncMock(return_value={
        "subject": "Payment received",
        "html_body": "Hi {{client_name}}",
        "text_body": "Hi {{client_name}}",
    })

    with patch("services.notification_orchestrator.database.get_db", return_value=db):
        with patch("services.notification_orchestrator.create_audit_log", new_callable=AsyncMock):
            with patch.object(notification_orchestrator, "_postmark_client", MagicMock()) as pm:
                pm.emails.send = MagicMock(return_value={"MessageID": "pm-123"})
                result = await notification_orchestrator.send(
                    template_key="SUBSCRIPTION_CONFIRMED",
                    client_id="c1",
                    context={"client_name": "Test", "plan_name": "Pro", "amount": "£79/mo"},
                    idempotency_key="ev_1_SUB",
                )
    assert result.outcome == "sent"


@pytest.mark.asyncio
async def test_professional_sms_allowed():
    """Client on PLAN_3_PRO with sms_reminders can send SMS (mock Twilio)."""
    from services.notification_orchestrator import notification_orchestrator

    db = MagicMock()
    db.notification_templates.find_one = AsyncMock(return_value={
        "template_key": "COMPLIANCE_EXPIRY_REMINDER",
        "channel": "SMS",
        "sms_body": "Reminder: {{client_name}}",
        "requires_provisioned": True,
        "requires_active_subscription": True,
        "requires_entitlement_enabled": True,
        "plan_required_feature_key": "sms_reminders",
        "is_active": True,
    })
    db.clients.find_one = AsyncMock(return_value={
        "client_id": "c1",
        "onboarding_status": "PROVISIONED",
        "subscription_status": "ACTIVE",
        "entitlement_status": "ENABLED",
    })
    db.notification_preferences.find_one = AsyncMock(return_value={"sms_enabled": True, "sms_phone_number": "+441234567890"})
    db.message_logs.find_one = AsyncMock(return_value=None)
    db.message_logs.count_documents = AsyncMock(return_value=0)
    db.message_logs.insert_one = AsyncMock()
    db.message_logs.update_one = AsyncMock()

    mock_registry = MagicMock()
    mock_registry.enforce_feature = AsyncMock(return_value=(True, None, None))
    with patch("services.notification_orchestrator.database.get_db", return_value=db):
        with patch("services.notification_orchestrator.create_audit_log", new_callable=AsyncMock):
            with patch("services.plan_registry.plan_registry", mock_registry):
                with patch.dict("os.environ", {"SMS_ENABLED": "true", "TWILIO_PHONE_NUMBER": "+44000"}):
                    with patch.object(notification_orchestrator, "_twilio_client", MagicMock()) as tw:
                        tw.messages.create = MagicMock(return_value=MagicMock(sid="SM123"))
                        result = await notification_orchestrator.send(
                            template_key="COMPLIANCE_EXPIRY_REMINDER",
                            client_id="c1",
                            context={"client_name": "Test"},
                            idempotency_key="sms_1",
                        )
    assert result.outcome == "sent"


@pytest.mark.asyncio
async def test_solo_sms_returns_403_plan_gate_denied():
    """Client on Solo plan sending SMS template with plan_required_feature_key → 403 PLAN_GATE_DENIED."""
    from services.notification_orchestrator import notification_orchestrator

    db = MagicMock()
    db.notification_templates.find_one = AsyncMock(return_value={
        "template_key": "COMPLIANCE_EXPIRY_REMINDER",
        "channel": "SMS",
        "sms_body": "Reminder",
        "requires_provisioned": True,
        "requires_active_subscription": True,
        "requires_entitlement_enabled": True,
        "plan_required_feature_key": "sms_reminders",
        "is_active": True,
    })
    db.clients.find_one = AsyncMock(return_value={
        "client_id": "c1",
        "onboarding_status": "PROVISIONED",
        "subscription_status": "ACTIVE",
        "entitlement_status": "ENABLED",
    })
    db.notification_preferences.find_one = AsyncMock(return_value={"sms_enabled": True, "sms_phone_number": "+441234567890"})

    mock_registry = MagicMock()
    mock_registry.enforce_feature = AsyncMock(return_value=(False, "SMS requires Pro plan", {"error_code": "PLAN_GATE_DENIED"}))
    with patch("services.notification_orchestrator.database.get_db", return_value=db):
        with patch("services.notification_orchestrator.create_audit_log", new_callable=AsyncMock):
            with patch("services.plan_registry.plan_registry", mock_registry):
                result = await notification_orchestrator.send(
                    template_key="COMPLIANCE_EXPIRY_REMINDER",
                    client_id="c1",
                    context={"client_name": "Test"},
                    idempotency_key="sms_solo",
                )
    assert result.outcome == "blocked"
    assert result.block_reason == "BLOCKED_PLAN_GATE"
    assert result.status_code == 403
    assert result.details.get("error_code") == "PLAN_GATE_DENIED"


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_returns_duplicate_ignored():
    """Same idempotency_key twice → second call returns duplicate_ignored, no second send."""
    from services.notification_orchestrator import notification_orchestrator

    db = MagicMock()
    db.notification_templates.find_one = AsyncMock(return_value={
        "template_key": "PAYMENT_FAILED",
        "channel": "EMAIL",
        "email_template_alias": "payment-failed",
        "requires_provisioned": False,
        "is_active": True,
    })
    db.clients.find_one = AsyncMock(return_value={
        "client_id": "c1",
        "email": "u@test.com",
        "contact_email": "u@test.com",
        "onboarding_status": "PROVISIONING",
        "subscription_status": "ACTIVE",
        "entitlement_status": "ENABLED",
    })
    db.notification_preferences.find_one = AsyncMock(return_value=None)
    db.message_logs.find_one = AsyncMock(side_effect=[None, {"message_id": "m1", "status": "SENT"}])
    db.message_logs.insert_one = AsyncMock()
    db.message_logs.update_one = AsyncMock()
    db.email_templates.find_one = AsyncMock(return_value={"subject": "Payment failed", "html_body": "Hi", "text_body": "Hi"})

    with patch("services.notification_orchestrator.database.get_db", return_value=db):
        with patch("services.notification_orchestrator.create_audit_log", new_callable=AsyncMock):
            with patch.object(notification_orchestrator, "_postmark_client", MagicMock()) as pm:
                pm.emails.send = MagicMock(return_value={"MessageID": "pm-1"})
                result1 = await notification_orchestrator.send(
                    template_key="PAYMENT_FAILED",
                    client_id="c1",
                    context={"client_name": "X", "billing_portal_link": "https://x", "retry_date": ""},
                    idempotency_key="ev_dup_PAYMENT_FAILED",
                )
    assert result1.outcome == "sent"

    with patch("services.notification_orchestrator.database.get_db", return_value=db):
        result2 = await notification_orchestrator.send(
            template_key="PAYMENT_FAILED",
            client_id="c1",
            context={"client_name": "X", "billing_portal_link": "https://x", "retry_date": ""},
            idempotency_key="ev_dup_PAYMENT_FAILED",
        )
    assert result2.outcome == "duplicate_ignored"


@pytest.mark.asyncio
async def test_delivery_webhook_updates_message_log():
    """POST /api/webhooks/postmark with Delivered updates message_logs status and writes audit."""
    from fastapi.testclient import TestClient
    from routes.webhooks import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    db = MagicMock()
    db.message_logs.find_one = AsyncMock(return_value={"message_id": "msg-1", "client_id": "c1"})
    db.message_logs.update_many = AsyncMock(return_value=MagicMock(modified_count=1))

    with patch("routes.webhooks.database.get_db", return_value=db):
        with patch("routes.webhooks.create_audit_log", new_callable=AsyncMock):
            resp = client.post(
                "/api/webhooks/postmark",
                json={"MessageID": "pm-xyz", "RecordType": "Delivery", "DeliveredAt": "2026-02-12T12:00:00Z"},
            )
    assert resp.status_code == 200
    assert resp.json().get("status") == "received"
    db.message_logs.update_many.assert_called()
    call = db.message_logs.update_many.call_args
    assert call[0][1]["$set"]["status"] == "DELIVERED"


@pytest.mark.asyncio
async def test_missing_provider_env_does_not_crash():
    """POSTMARK_SERVER_TOKEN missing → MessageLog BLOCKED_PROVIDER_NOT_CONFIGURED, no exception."""
    from services.notification_orchestrator import notification_orchestrator

    db = MagicMock()
    db.notification_templates.find_one = AsyncMock(return_value={
        "template_key": "WELCOME_EMAIL",
        "channel": "EMAIL",
        "requires_provisioned": True,
        "is_active": True,
    })
    db.clients.find_one = AsyncMock(return_value={
        "client_id": "c1",
        "email": "u@test.com",
        "onboarding_status": "PROVISIONED",
        "subscription_status": "ACTIVE",
        "entitlement_status": "ENABLED",
    })
    db.notification_preferences.find_one = AsyncMock(return_value=None)
    db.message_logs.find_one = AsyncMock(return_value=None)
    db.message_logs.insert_one = AsyncMock()
    db.message_logs.update_one = AsyncMock()

    with patch("services.notification_orchestrator.database.get_db", return_value=db):
        with patch("services.notification_orchestrator.create_audit_log", new_callable=AsyncMock):
            with patch.object(notification_orchestrator, "_postmark_client", None):
                result = await notification_orchestrator.send(
                    template_key="WELCOME_EMAIL",
                    client_id="c1",
                    context={"setup_link": "https://x", "client_name": "Test"},
                    idempotency_key="no_crash_1",
                )
    assert result.outcome == "blocked"
    assert result.block_reason == "BLOCKED_PROVIDER_NOT_CONFIGURED"
    db.message_logs.update_one.assert_called()
    sets = [c[0][1].get("$set", c[0][1]) for c in db.message_logs.update_one.call_args_list]
    assert any(s.get("status") == "BLOCKED_PROVIDER_NOT_CONFIGURED" for s in sets)
