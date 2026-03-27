from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import asyncio
from unittest.mock import AsyncMock

from services import client_task_state_service as svc


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_nested(row, dotted_key):
    cur = row
    for part in dotted_key.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _matches(row, query):
    for key, expected in (query or {}).items():
        actual = _get_nested(row, key)
        if isinstance(expected, dict):
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$gte" in expected:
                if actual is None or actual < expected["$gte"]:
                    return False
        else:
            if actual != expected:
                return False
    return True


class _Cursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def sort(self, key, direction):
        reverse = int(direction) < 0
        self._rows.sort(key=lambda r: _get_nested(r, key), reverse=reverse)
        return self

    def limit(self, n):
        self._rows = self._rows[: int(n)]
        return self

    async def to_list(self, length=None):
        if length is None:
            return list(self._rows)
        return list(self._rows)[: int(length)]


class _Collection:
    def __init__(self):
        self.rows = []

    async def insert_one(self, doc):
        self.rows.append(dict(doc))
        return SimpleNamespace(inserted_id=len(self.rows))

    async def update_one(self, query, update, upsert=False):
        for idx, row in enumerate(self.rows):
            if _matches(row, query):
                patched = dict(row)
                patched.update((update or {}).get("$set") or {})
                self.rows[idx] = patched
                return SimpleNamespace(matched_count=1, modified_count=1, upserted_id=None)
        if upsert:
            new_row = dict((update or {}).get("$set") or {})
            self.rows.append(new_row)
            return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=len(self.rows))
        return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=None)

    async def delete_one(self, query):
        for idx, row in enumerate(self.rows):
            if _matches(row, query):
                self.rows.pop(idx)
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    def find(self, query=None, projection=None):
        matched = [r for r in self.rows if _matches(r, query or {})]
        if projection:
            out = []
            include_keys = [k for k, v in projection.items() if v and k != "_id"]
            for row in matched:
                slim = {k: _get_nested(row, k) for k in include_keys}
                out.append(slim)
            matched = out
        return _Cursor(matched)

    async def count_documents(self, query):
        return len([r for r in self.rows if _matches(r, query or {})])


class _FakeDb:
    def __init__(self):
        self.client_task_overrides = _Collection()
        self.client_task_activity_log = _Collection()

    def __getitem__(self, name):
        return getattr(self, name)


def test_task_overrides_are_isolated_per_portal_user(monkeypatch):
    fake_db = _FakeDb()
    monkeypatch.setattr(svc.database, "get_db", lambda: fake_db)
    monkeypatch.setattr(svc, "create_audit_log", AsyncMock(return_value=None))

    asyncio.run(
        svc.apply_task_action(
            "c1",
            "requirement:req-1",
            "dismiss",
            portal_user_id="pu-1",
            title_snapshot="Task 1",
        )
    )

    u1 = asyncio.run(svc.load_active_overrides("c1", portal_user_id="pu-1"))
    u2 = asyncio.run(svc.load_active_overrides("c1", portal_user_id="pu-2"))

    assert "requirement:req-1" in u1
    assert u1["requirement:req-1"]["override"] == svc.OVERRIDE_DISMISS
    assert u2 == {}


def test_restore_only_clears_current_user_override(monkeypatch):
    fake_db = _FakeDb()
    monkeypatch.setattr(svc.database, "get_db", lambda: fake_db)
    monkeypatch.setattr(svc, "create_audit_log", AsyncMock(return_value=None))

    asyncio.run(svc.apply_task_action("c1", "issue:iss-1", "done", portal_user_id="pu-1"))
    asyncio.run(svc.apply_task_action("c1", "issue:iss-1", "dismiss", portal_user_id="pu-2"))
    asyncio.run(svc.apply_task_action("c1", "issue:iss-1", "restore", portal_user_id="pu-1"))

    u1 = asyncio.run(svc.load_active_overrides("c1", portal_user_id="pu-1"))
    u2 = asyncio.run(svc.load_active_overrides("c1", portal_user_id="pu-2"))

    assert "issue:iss-1" not in u1
    assert "issue:iss-1" in u2
    assert u2["issue:iss-1"]["override"] == svc.OVERRIDE_DISMISS


def test_hidden_and_activity_views_are_user_scoped(monkeypatch):
    fake_db = _FakeDb()
    monkeypatch.setattr(svc.database, "get_db", lambda: fake_db)
    monkeypatch.setattr(svc, "create_audit_log", AsyncMock(return_value=None))

    asyncio.run(svc.apply_task_action("c1", "work_order:wo-1", "done", portal_user_id="pu-1"))
    asyncio.run(svc.apply_task_action("c1", "work_order:wo-2", "dismiss", portal_user_id="pu-2"))

    since = _now() - timedelta(days=1)
    u1_ack = asyncio.run(
        svc.count_activity_since("c1", since, [svc.ACTION_DISMISS, svc.ACTION_DONE], portal_user_id="pu-1")
    )
    u2_ack = asyncio.run(
        svc.count_activity_since("c1", since, [svc.ACTION_DISMISS, svc.ACTION_DONE], portal_user_id="pu-2")
    )
    all_ack = asyncio.run(
        svc.count_activity_since("c1", since, [svc.ACTION_DISMISS, svc.ACTION_DONE], portal_user_id=None)
    )
    u1_hidden = asyncio.run(svc.list_hidden_inbox_items("c1", portal_user_id="pu-1"))
    u2_hidden = asyncio.run(svc.list_hidden_inbox_items("c1", portal_user_id="pu-2"))

    assert u1_ack == 1
    assert u2_ack == 1
    assert all_ack == 2
    assert [r["task_id"] for r in u1_hidden] == ["work_order:wo-1"]
    assert [r["task_id"] for r in u2_hidden] == ["work_order:wo-2"]
