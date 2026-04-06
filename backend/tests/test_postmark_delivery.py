"""Postmark delivery: retries, logging hooks, failed_notifications."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.asyncio


async def test_deliver_succeeds_first_attempt():
    from services import postmark_delivery as pd

    client = MagicMock()
    client.emails.send = MagicMock(return_value={"MessageID": "abc"})
    db = MagicMock()
    db.failed_notifications = MagicMock()
    db.failed_notifications.insert_one = AsyncMock()

    with patch.object(pd, "POSTMARK_SEND_MAX_ATTEMPTS", 3):
        with patch.object(pd, "POSTMARK_RETRY_DELAYS_SEC", [0.01, 0.01]):
            resp, err, n = await pd.deliver_postmark_email(
                client,
                {"From": "a@b.c", "To": "u@test.com", "Subject": "S", "HtmlBody": "h", "TextBody": "t"},
                template_name="T1",
                recipient="u@test.com",
                message_id="mid-1",
                client_id="c1",
                db=db,
            )
    assert resp == {"MessageID": "abc"}
    assert err is None
    assert n == 1
    client.emails.send.assert_called_once()
    db.failed_notifications.insert_one.assert_not_called()


async def test_deliver_retries_transient_then_succeeds():
    from services import postmark_delivery as pd

    client = MagicMock()
    calls = {"n": 0}

    def boom_then_ok(**kw):
        calls["n"] += 1
        if calls["n"] < 2:
            raise TimeoutError("timeout")
        return {"MessageID": "ok"}

    client.emails.send = MagicMock(side_effect=boom_then_ok)
    db = MagicMock()
    db.failed_notifications = MagicMock()
    db.failed_notifications.insert_one = AsyncMock()

    with patch.object(pd, "POSTMARK_SEND_MAX_ATTEMPTS", 3):
        with patch.object(pd, "POSTMARK_RETRY_DELAYS_SEC", [0.01, 0.01]):
            resp, err, n = await pd.deliver_postmark_email(
                client,
                {"From": "a@b.c", "To": "u@test.com", "Subject": "S", "HtmlBody": "h", "TextBody": "t"},
                template_name="T2",
                recipient="u@test.com",
                message_id="mid-2",
                client_id=None,
                db=db,
            )
    assert resp["MessageID"] == "ok"
    assert err is None
    assert n == 2
    assert client.emails.send.call_count == 2
    db.failed_notifications.insert_one.assert_not_called()


async def test_deliver_exhausted_writes_failed_notifications():
    from services import postmark_delivery as pd

    client = MagicMock()
    client.emails.send = MagicMock(side_effect=TimeoutError("always"))
    db = MagicMock()
    db.failed_notifications = MagicMock()
    db.failed_notifications.insert_one = AsyncMock()

    with patch.object(pd, "POSTMARK_SEND_MAX_ATTEMPTS", 2):
        with patch.object(pd, "POSTMARK_RETRY_DELAYS_SEC", [0.01]):
            resp, err, n = await pd.deliver_postmark_email(
                client,
                {"From": "a@b.c", "To": "u@test.com", "Subject": "S", "HtmlBody": "h", "TextBody": "t"},
                template_name="T3",
                recipient="u@test.com",
                message_id="mid-3",
                client_id="c9",
                db=db,
            )
    assert resp is None
    assert err
    assert n == 2
    assert client.emails.send.call_count == 2
    db.failed_notifications.insert_one.assert_called_once()
    doc = db.failed_notifications.insert_one.call_args[0][0]
    assert doc["template_name"] == "T3"
    assert doc["message_id"] == "mid-3"
    assert "@" in doc["recipient_masked"] or doc["recipient_masked"] == "***"


async def test_non_transient_no_retry():
    from services import postmark_delivery as pd

    class Boom(Exception):
        code = 422

    client = MagicMock()
    client.emails.send = MagicMock(side_effect=Boom("bad"))
    db = MagicMock()
    db.failed_notifications = MagicMock()
    db.failed_notifications.insert_one = AsyncMock()

    with patch.object(pd, "POSTMARK_SEND_MAX_ATTEMPTS", 3):
        resp, err, n = await pd.deliver_postmark_email(
            client,
            {"From": "a@b.c", "To": "u@test.com", "Subject": "S", "HtmlBody": "h", "TextBody": "t"},
            template_name="T4",
            recipient="u@test.com",
            message_id="mid-4",
            client_id=None,
            db=db,
        )
    assert resp is None
    assert n == 1
    client.emails.send.assert_called_once()
