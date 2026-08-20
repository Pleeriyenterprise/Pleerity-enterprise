"""Inbox count vs list authority — NOTIFICATION-BELL-AUTHORITY-DRIFT-01."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.order_service import (
    get_unread_count,
    inbox_unread_query,
    inbox_visibility_query,
    list_inbox_notifications,
)


def _match(query, doc):
    if not isinstance(query, dict):
        return query == doc
    if "$and" in query:
        return all(_match(p, doc) for p in query["$and"])
    if "$or" in query:
        return any(_match(p, doc) for p in query["$or"])
    for k, v in query.items():
        if k.startswith("$"):
            continue
        if isinstance(v, dict):
            if "$exists" in v:
                exists = k in doc
                if bool(v["$exists"]) != exists:
                    return False
                continue
            if "$in" in v:
                if doc.get(k) not in v["$in"]:
                    return False
                continue
            if "$ne" in v:
                if doc.get(k) == v["$ne"]:
                    return False
                continue
            return False
        if v is None:
            if k in doc and doc.get(k) is not None:
                return False
            continue
        if doc.get(k) != v:
            return False
    return True


class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, spec):
        for field, direction in reversed(spec):
            rev = direction == -1
            self._docs.sort(key=lambda d: (d.get(field) is None, d.get(field)), reverse=rev)
        return self

    async def to_list(self, length):
        return self._docs[:length]


class _FakeColl:
    def __init__(self, docs):
        self.docs = list(docs)

    def find(self, query, _proj=None):
        return _FakeCursor([d for d in self.docs if _match(query, d)])

    async def count_documents(self, query):
        return sum(1 for d in self.docs if _match(query, d))

    async def update_many(self, query, update):
        n = 0
        sets = (update or {}).get("$set") or {}
        for d in self.docs:
            if _match(query, d):
                d.update(sets)
                n += 1
        return SimpleNamespace(modified_count=n)


def _db(docs):
    return SimpleNamespace(in_app_notifications=_FakeColl(docs))


def _n(i, **over):
    now = datetime.now(timezone.utc)
    row = {
        "notification_id": f"N{i}",
        "recipient_id": "user-a",
        "title": f"Title {i}",
        "message": f"Body {i}",
        "is_read": False,
        "created_at": now - timedelta(minutes=i),
        "notification_type": "system",
        "severity": "medium",
        "notification_category": "system",
    }
    row.update(over)
    return row


@pytest.mark.asyncio
async def test_one_unread_visible_record_count_and_list_agree():
    db = _db([_n(1)])
    with patch("services.order_service.database.get_db", return_value=db):
        assert await get_unread_count("user-a") == 1
        items = await list_inbox_notifications("user-a", limit=30, inbox_filter="all")
        assert len(items) == 1
        assert items[0]["notification_id"] == "N1"


@pytest.mark.asyncio
async def test_dismissed_unread_not_counted_or_listed():
    db = _db(
        [
            _n(1, dismissed_at=datetime.now(timezone.utc)),
            _n(2, dismissed=True, is_read=False),
        ]
    )
    with patch("services.order_service.database.get_db", return_value=db):
        assert await get_unread_count("user-a") == 0
        assert await list_inbox_notifications("user-a", limit=30) == []


@pytest.mark.asyncio
async def test_expired_field_does_not_hide_from_one_side_only():
    """No expiry filter in inbox authority — both sides still see the row."""
    db = _db([_n(1, expires_at=datetime.now(timezone.utc) - timedelta(days=1))])
    with patch("services.order_service.database.get_db", return_value=db):
        assert await get_unread_count("user-a") == 1
        items = await list_inbox_notifications("user-a", limit=30)
        assert len(items) == 1


@pytest.mark.asyncio
async def test_wrong_user_excluded_from_count_and_list():
    db = _db([_n(1, recipient_id="user-b")])
    with patch("services.order_service.database.get_db", return_value=db):
        assert await get_unread_count("user-a") == 0
        assert await list_inbox_notifications("user-a", limit=30) == []
        assert await get_unread_count("user-b") == 1


@pytest.mark.asyncio
async def test_read_record_not_in_unread_count_but_in_all_list():
    db = _db([_n(1, is_read=True)])
    with patch("services.order_service.database.get_db", return_value=db):
        assert await get_unread_count("user-a") == 0
        items = await list_inbox_notifications("user-a", limit=30, inbox_filter="all")
        assert len(items) == 1
        unread = await list_inbox_notifications("user-a", limit=30, inbox_filter="unread")
        assert unread == []


@pytest.mark.asyncio
async def test_mixed_visible_and_hidden():
    db = _db(
        [
            _n(1),
            _n(2, is_read=True),
            _n(3, dismissed_at=datetime.now(timezone.utc)),
            _n(4, recipient_id="other"),
        ]
    )
    with patch("services.order_service.database.get_db", return_value=db):
        assert await get_unread_count("user-a") == 1
        items = await list_inbox_notifications("user-a", limit=30)
        ids = {x["notification_id"] for x in items}
        assert ids == {"N1", "N2"}


@pytest.mark.asyncio
async def test_more_than_list_limit_does_not_hide_unread():
    docs = [_n(i, is_read=True) for i in range(50)]
    docs.append(_n(99, is_read=False, created_at=datetime.now(timezone.utc) - timedelta(days=30)))
    db = _db(docs)
    with patch("services.order_service.database.get_db", return_value=db):
        assert await get_unread_count("user-a") == 1
        items = await list_inbox_notifications("user-a", limit=10, inbox_filter="all")
        assert items[0]["notification_id"] == "N99"
        assert len(items) == 10


@pytest.mark.asyncio
async def test_malformed_missing_title_still_listed_and_counted():
    db = _db([_n(1, title=None, message=None)])
    with patch("services.order_service.database.get_db", return_value=db):
        assert await get_unread_count("user-a") == 1
        items = await list_inbox_notifications("user-a", limit=30)
        assert len(items) == 1


@pytest.mark.asyncio
async def test_visibility_and_unread_queries_share_recipient_and_dismissed():
    vis = inbox_visibility_query("user-a")
    unread = inbox_unread_query("user-a")
    assert vis["$and"][0] == {"recipient_id": "user-a"}
    assert unread["$and"][0]["$and"][0] == {"recipient_id": "user-a"}
