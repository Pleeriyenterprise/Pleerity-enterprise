import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from models.enablement import (
    DeliveryChannel,
    EnablementActionStatus,
    EnablementCategory,
    EnablementEventPayload,
    EnablementEventType,
    EnablementTemplate,
)
from services import enablement_service as es


class _AsyncCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def __aiter__(self):
        self._iter = iter(self._rows)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class _Collection:
    def __init__(self, rows=None):
        self._rows = list(rows or [])
        self.find_one = AsyncMock(return_value=None)

    def find(self, *_args, **_kwargs):
        return _AsyncCursor(self._rows)


class _FakeDb:
    def __init__(self, template_doc):
        self.enablement_templates = _Collection([template_doc])
        self.clients = _Collection([])
        self.portal_users = _Collection([])


def _dashboard_ready_template_doc():
    now = datetime.now(timezone.utc)
    tpl = EnablementTemplate(
        template_id="TPL-TEST-1",
        template_code="dashboard_ready",
        category=EnablementCategory.ONBOARDING_GUIDANCE,
        event_triggers=[EnablementEventType.PROVISIONING_COMPLETED],
        title="Your Dashboard is Ready",
        body="Provisioning complete.",
        email_subject="Your Compliance Dashboard is Ready",
        email_body_html="<p>ready</p>",
        assistant_context=None,
        channels=[DeliveryChannel.EMAIL],
        delay_minutes=0,
        plan_codes=None,
        version=1,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    return tpl.model_dump(mode="json")


def test_dashboard_ready_email_suppressed_until_password_set(monkeypatch):
    fake_db = _FakeDb(_dashboard_ready_template_doc())
    fake_db.clients.find_one = AsyncMock(return_value={"name": "Acme", "email": "owner@acme.test"})
    fake_db.portal_users.find_one = AsyncMock(return_value={"password_status": "NOT_SET"})

    monkeypatch.setattr(es, "get_db", lambda: fake_db)
    monkeypatch.setattr(es, "check_suppression", AsyncMock(return_value=(False, None)))
    monkeypatch.setattr(es, "is_channel_enabled", AsyncMock(return_value=True))
    monkeypatch.setattr(es, "deliver_email", AsyncMock(return_value=True))
    monkeypatch.setattr(es, "log_enablement_action", AsyncMock(return_value=None))

    event = EnablementEventPayload(
        event_id="EVT-1",
        event_type=EnablementEventType.PROVISIONING_COMPLETED,
        client_id="c1",
        plan_code=None,
        timestamp=datetime.now(timezone.utc),
        context_payload={},
    )

    asyncio.run(es.process_enablement_event(event))

    es.deliver_email.assert_not_called()
    # Suppressed log recorded for the EMAIL channel.
    suppressed_calls = [
        c for c in es.log_enablement_action.await_args_list
        if c.kwargs.get("channel") == DeliveryChannel.EMAIL and c.kwargs.get("status") == EnablementActionStatus.SUPPRESSED
    ]
    assert suppressed_calls, "Expected suppressed action log for dashboard_ready email before password is set"


def test_dashboard_ready_email_sends_after_password_set(monkeypatch):
    fake_db = _FakeDb(_dashboard_ready_template_doc())
    fake_db.clients.find_one = AsyncMock(return_value={"name": "Acme", "email": "owner@acme.test"})
    fake_db.portal_users.find_one = AsyncMock(return_value={"password_status": "SET"})

    monkeypatch.setattr(es, "get_db", lambda: fake_db)
    monkeypatch.setattr(es, "check_suppression", AsyncMock(return_value=(False, None)))
    monkeypatch.setattr(es, "is_channel_enabled", AsyncMock(return_value=True))
    monkeypatch.setattr(es, "deliver_email", AsyncMock(return_value=True))
    monkeypatch.setattr(es, "log_enablement_action", AsyncMock(return_value=None))

    event = EnablementEventPayload(
        event_id="EVT-2",
        event_type=EnablementEventType.PROVISIONING_COMPLETED,
        client_id="c1",
        plan_code=None,
        timestamp=datetime.now(timezone.utc),
        context_payload={},
    )

    asyncio.run(es.process_enablement_event(event))

    es.deliver_email.assert_called_once()
