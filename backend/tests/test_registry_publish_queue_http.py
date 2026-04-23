"""HTTP tests: compliance registry publish-queue transitions and RBAC (Owner-only approve/publish)."""
from __future__ import annotations

import copy
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from models import UserRole
from server import app
from services.compliance_registry_publish_service import (
    COLLECTION_PUBLISHED as PUB_COLL,
    COLLECTION_PUBLISHED_HISTORY as HIST_COLL,
    COLLECTION_QUEUE as QUEUE_COLL,
)
from services.compliance_registry_admin_service import COLLECTION as DRAFTS_COLL


@pytest.fixture(scope="module")
def client():
    """Module-scoped client: one app lifespan for this file (avoids repeated Mongo connect timeouts)."""
    with TestClient(app) as c:
        yield c


_ADMIN_USER = {"role": UserRole.ROLE_ADMIN.value, "portal_user_id": "admin-1", "email": "admin@example.com"}
_OWNER_USER = {"role": UserRole.ROLE_OWNER.value, "portal_user_id": "owner-1", "email": "owner@example.com"}
_AUDITOR_USER = {"role": UserRole.ROLE_AUDITOR.value, "portal_user_id": "aud-1", "email": "auditor@example.com"}


def _patch_auth(user_dict: dict):
    """``admin_route_guard`` and role deps call ``middleware.require_auth`` directly; patch that symbol."""
    return patch("middleware.require_auth", new_callable=AsyncMock, return_value=user_dict)


class _FakeQueueCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def sort(self, *_args, **_kwargs):
        return self

    def skip(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    async def to_list(self, length=None):
        del length
        return list(self._rows)


class _FakeHistCursor:
    def __init__(self, rows):
        self._rows = list(rows)
        self._skip = 0
        self._lim = 50

    def sort(self, *_args, **_kwargs):
        return self

    def skip(self, n: int):
        self._skip = int(n)
        return self

    def limit(self, n: int):
        self._lim = int(n)
        return self

    async def to_list(self, length=None):
        del length
        return self._rows[self._skip : self._skip + self._lim]


class FakeRegistryMongo:
    """Minimal in-memory Mongo behaviour for publish-queue + published + one draft."""

    def __init__(self, draft_entry_id: str):
        self._queues: dict[str, dict] = {}
        self._drafts: dict[str, dict] = {
            draft_entry_id: {
                "entry_id": draft_entry_id,
                "canonical_code": "GAS_SAFETY",
                "scope_key": "DEFAULT",
                "jurisdiction": {"display_jurisdictions": ["England", "Wales", "Scotland", "Northern Ireland"]},
                "identity": {"name": "Draft gas", "category": "SAFETY"},
                "classification": {
                    "requirement_type": "DOCUMENT",
                    "requires_document": True,
                    "criticality": "HIGH",
                    "client_surface_visible": True,
                },
                "action_behaviour": {"primary_action_mode": "upload_document"},
                "conditions": {"logic": "ALL", "rules": []},
                "governance": {"needs_review_fields": []},
                "action_links": [],
                "why_it_matters_short": "Statutory gas safety compliance for this property.",
                "why_it_matters_long": "",
                "why_it_matters_by_jurisdiction": {},
                "frequency": {"frequency_days": 365, "reminder_lead_days": 30},
            }
        }
        self._published: dict | None = None
        self._history_docs: list[dict] = []

    def __getitem__(self, name: str):
        if name == QUEUE_COLL:
            return self
        if name == DRAFTS_COLL:
            return _DraftsSub(self)
        if name == PUB_COLL:
            return _PublishedSub(self)
        if name == HIST_COLL:
            return _HistorySub(self)
        raise KeyError(name)

    async def find_one(self, filt: dict, projection=None):
        del projection
        qid = filt.get("queue_id")
        if qid:
            return self._queues.get(qid)
        return None

    async def insert_one(self, doc: dict):
        qid = doc["queue_id"]
        self._queues[qid] = {**doc}

    async def update_one(self, filt: dict, update: dict, upsert: bool = False):
        del upsert
        qid = filt.get("queue_id")
        if not qid:
            return
        doc = self._queues.get(qid)
        if not doc:
            return
        if "$set" in update:
            doc.update(update["$set"])

    def find(self, *_args, **_kwargs):
        rows = sorted(self._queues.values(), key=lambda d: d.get("updated_at", ""), reverse=True)
        return _FakeQueueCursor(rows)


class _DraftsSub:
    def __init__(self, parent: FakeRegistryMongo):
        self._p = parent

    async def find_one(self, filt: dict, projection=None):
        del projection
        eid = filt.get("entry_id")
        if not eid:
            return None
        return self._p._drafts.get(eid)


class _HistorySub:
    def __init__(self, parent: FakeRegistryMongo):
        self._p = parent

    async def insert_one(self, doc: dict):
        self._p._history_docs.append({**doc})

    async def find_one(self, filt: dict, projection=None):
        pv = filt.get("published_line_version")
        if pv is None:
            return None
        for h in self._p._history_docs:
            if h.get("published_line_version") == pv:
                if projection and projection.get("entries") == 0:
                    return {k: v for k, v in h.items() if k not in ("entries", "_id")}
                return {k: v for k, v in h.items() if k != "_id"}
        return None

    def find(self, filt, projection=None):
        del filt
        base = sorted(self._p._history_docs, key=lambda x: -int(x.get("published_line_version") or 0))
        rows = []
        for h in base:
            if projection and projection.get("entries") == 0:
                rows.append({k: v for k, v in h.items() if k not in ("entries", "_id")})
            else:
                rows.append({k: v for k, v in h.items() if k != "_id"})
        return _FakeHistCursor(rows)


class _PublishedSub:
    def __init__(self, parent: FakeRegistryMongo):
        self._p = parent

    async def find_one(self, filt: dict, projection=None):
        if not filt.get("singleton_key"):
            return None
        pub = self._p._published
        if pub is None:
            return None
        doc = dict(pub)
        if projection:
            if projection.get("entries") == 1 and projection.get("version") == 1:
                return {"version": doc.get("version"), "entries": doc.get("entries")}
            if projection.get("entries") == 1:
                return {"entries": doc.get("entries")}
            if projection.get("entries") == 0:
                return {k: v for k, v in doc.items() if k != "entries"}
            if projection.get("version") == 1 and projection.get("entries") != 1:
                return {"version": doc.get("version")}
        return doc

    async def update_one(self, filt: dict, update: dict, upsert: bool = False):
        del filt, upsert
        s = update.get("$set", {})
        if self._p._published is None:
            self._p._published = {}
        self._p._published.update(s)


@contextmanager
def _patch_registry_http(fake_db: FakeRegistryMongo):
    with patch("routes.admin_compliance_registry.database.get_db", return_value=fake_db):
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            yield


def test_approve_returns_403_for_admin_not_owner(client):
    with _patch_auth(_ADMIN_USER):
        r = client.post("/api/admin/compliance/registry/publish-queue/q-1/approve")
    assert r.status_code == 403
    assert "Insufficient" in (r.json().get("detail") or "")


def test_publish_returns_403_for_admin_not_owner(client):
    with _patch_auth(_ADMIN_USER):
        r = client.post("/api/admin/compliance/registry/publish-queue/q-1/publish")
    assert r.status_code == 403


def test_submit_still_allowed_for_admin(client):
    fake = FakeRegistryMongo("e-submit-1")
    qid = "queue-submit-test"
    fake._queues[qid] = {
        "queue_id": qid,
        "status": "draft",
        "title": "t",
        "draft_entry_ids": ["e-submit-1"],
        "audit_log": [],
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    with _patch_auth(_ADMIN_USER), _patch_registry_http(fake):
        r = client.post(f"/api/admin/compliance/registry/publish-queue/{qid}/submit")
    assert r.status_code == 200, r.text
    assert r.json()["queue"]["status"] == "submitted"


def test_publish_merge_preserves_prior_snapshot_keys(client):
    """Publishing a queue overlays keys onto the existing snapshot; other keys remain."""
    e_gas = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
    e_eicr = "ffffffff-ffff-4fff-8fff-ffffffffffff"
    fake = FakeRegistryMongo(e_gas)
    fake._drafts[e_eicr] = copy.deepcopy(fake._drafts[e_gas])
    fake._drafts[e_eicr]["entry_id"] = e_eicr
    fake._drafts[e_eicr]["canonical_code"] = "EICR"
    fake._drafts[e_eicr]["identity"] = {**fake._drafts[e_gas]["identity"], "name": "Draft EICR"}
    with _patch_auth(_OWNER_USER), _patch_registry_http(fake):
        r0 = client.post(
            "/api/admin/compliance/registry/publish-queue",
            json={"title": "Gas only", "draft_entry_ids": [e_gas]},
        )
        assert r0.status_code == 200, r0.text
        q0 = r0.json()["queue"]["queue_id"]
        client.post(f"/api/admin/compliance/registry/publish-queue/{q0}/submit")
        client.post(f"/api/admin/compliance/registry/publish-queue/{q0}/approve")
        r_pub = client.post(f"/api/admin/compliance/registry/publish-queue/{q0}/publish")
        assert r_pub.status_code == 200, r_pub.text
        assert "GAS_SAFETY|DEFAULT" in (fake._published.get("entries") or {})

        r1 = client.post(
            "/api/admin/compliance/registry/publish-queue",
            json={"title": "EICR overlay", "draft_entry_ids": [e_eicr]},
        )
        q1 = r1.json()["queue"]["queue_id"]
        client.post(f"/api/admin/compliance/registry/publish-queue/{q1}/submit")
        client.post(f"/api/admin/compliance/registry/publish-queue/{q1}/approve")
        r_pub2 = client.post(f"/api/admin/compliance/registry/publish-queue/{q1}/publish")
        assert r_pub2.status_code == 200, r_pub2.text
        ent = fake._published.get("entries") or {}
        assert "GAS_SAFETY|DEFAULT" in ent and "EICR|DEFAULT" in ent
        assert r_pub2.json().get("entry_count") == 2


def test_owner_full_transition_create_through_publish(client):
    eid = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
    fake = FakeRegistryMongo(eid)
    with _patch_auth(_OWNER_USER), _patch_registry_http(fake):
        r0 = client.post(
            "/api/admin/compliance/registry/publish-queue",
            json={"title": "Milestone publish", "draft_entry_ids": [eid]},
        )
        assert r0.status_code == 200, r0.text
        qid = r0.json()["queue"]["queue_id"]

        r1 = client.post(f"/api/admin/compliance/registry/publish-queue/{qid}/submit")
        assert r1.status_code == 200, r1.text
        assert r1.json()["queue"]["status"] == "submitted"

        r2 = client.post(f"/api/admin/compliance/registry/publish-queue/{qid}/approve")
        assert r2.status_code == 200, r2.text
        assert r2.json()["queue"]["status"] == "approved"

        r3 = client.post(f"/api/admin/compliance/registry/publish-queue/{qid}/publish")
        assert r3.status_code == 200, r3.text
        assert r3.json()["status"] == "published"
        assert r3.json()["published_version"] == 1
        assert r3.json()["entry_count"] == 1

        assert fake._published is not None
        assert fake._published.get("version") == 1
        assert "GAS_SAFETY|DEFAULT" in (fake._published.get("entries") or {})
        assert len(fake._history_docs) == 1
        assert fake._history_docs[0].get("published_line_version") == 1
        assert fake._history_docs[0].get("activation_kind") == "publish"


def test_reject_submitted_allowed_for_admin(client):
    fake = FakeRegistryMongo("e-rej-1")
    qid = "queue-reject-test"
    fake._queues[qid] = {
        "queue_id": qid,
        "status": "submitted",
        "title": "t",
        "draft_entry_ids": ["e-rej-1"],
        "audit_log": [],
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    with _patch_auth(_ADMIN_USER), _patch_registry_http(fake):
        r = client.post(
            f"/api/admin/compliance/registry/publish-queue/{qid}/reject",
            json={"reason": "needs more review"},
        )
    assert r.status_code == 200, r.text
    assert r.json()["queue"]["status"] == "rejected"
    assert r.json()["queue"]["rejection_reason"] == "needs more review"


def test_auditor_cannot_create_publish_queue(client):
    fake = FakeRegistryMongo("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
    with _patch_auth(_AUDITOR_USER), _patch_registry_http(fake):
        r = client.post(
            "/api/admin/compliance/registry/publish-queue",
            json={"title": "x", "draft_entry_ids": ["eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"]},
        )
    assert r.status_code == 403


def test_list_publish_queue_requires_admin_capable_user(client):
    """Router admin_route_guard + require_admin on list — with auth override succeeds."""
    fake = FakeRegistryMongo("x")
    fake._queues["q1"] = {
        "queue_id": "q1",
        "status": "draft",
        "title": "only",
        "draft_entry_ids": ["x"],
        "audit_log": [],
        "created_at": "2026-01-02T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
    }
    with _patch_auth(_ADMIN_USER), _patch_registry_http(fake):
        r = client.get("/api/admin/compliance/registry/publish-queue")
    assert r.status_code == 200, r.text
    assert len(r.json().get("items") or []) == 1


def _sample_entry(name: str) -> dict:
    return {
        "canonical_code": "GAS_SAFETY",
        "scope_key": "DEFAULT",
        "jurisdiction": {"display_jurisdictions": ["England", "Wales", "Scotland", "Northern Ireland"]},
        "identity": {"name": name},
        "classification": {"requirement_type": "DOCUMENT"},
        "frequency": {"frequency_days": 365, "reminder_lead_days": 30},
    }


def test_published_history_list_and_detail(client):
    fake = FakeRegistryMongo("e-hist-1")
    fake._history_docs = [
        {
            "history_id": "h1",
            "published_line_version": 2,
            "activation_kind": "publish",
            "entry_count": 1,
            "entries": {"GAS_SAFETY|DEFAULT": _sample_entry("V2")},
            "recorded_at": "2026-01-03T00:00:00Z",
            "last_queue_id": "q2",
            "activated_by": {"portal_user_id": "o", "email": "o@e.com"},
            "reverted_from_published_line_version": None,
        },
        {
            "history_id": "h0",
            "published_line_version": 1,
            "activation_kind": "publish",
            "entry_count": 1,
            "entries": {"GAS_SAFETY|DEFAULT": _sample_entry("V1")},
            "recorded_at": "2026-01-02T00:00:00Z",
            "last_queue_id": "q1",
            "activated_by": {"portal_user_id": "o", "email": "o@e.com"},
            "reverted_from_published_line_version": None,
        },
    ]
    with _patch_auth(_ADMIN_USER), _patch_registry_http(fake):
        r = client.get("/api/admin/compliance/registry/published/history")
        assert r.status_code == 200, r.text
        items = r.json().get("items") or []
        assert len(items) == 2
        assert items[0].get("published_line_version") == 2
        assert "entries" not in items[0]
        r2 = client.get("/api/admin/compliance/registry/published/history/1?include_entries=true")
        assert r2.status_code == 200, r2.text
        rec = r2.json().get("record") or {}
        assert rec.get("published_line_version") == 1
        assert "entries" in rec


def test_revert_owner_advances_version_and_admin_forbidden(client):
    fake = FakeRegistryMongo("e-rev-1")
    fake._history_docs = [
        {
            "history_id": "h1",
            "published_line_version": 1,
            "activation_kind": "publish",
            "entry_count": 1,
            "entries": {"GAS_SAFETY|DEFAULT": _sample_entry("V1")},
            "recorded_at": "2026-01-02T00:00:00Z",
            "last_queue_id": "q1",
            "activated_by": {"portal_user_id": "o", "email": "o@e.com"},
            "reverted_from_published_line_version": None,
        },
        {
            "history_id": "h2",
            "published_line_version": 2,
            "activation_kind": "publish",
            "entry_count": 1,
            "entries": {"GAS_SAFETY|DEFAULT": _sample_entry("V2")},
            "recorded_at": "2026-01-03T00:00:00Z",
            "last_queue_id": "q2",
            "activated_by": {"portal_user_id": "o", "email": "o@e.com"},
            "reverted_from_published_line_version": None,
        },
    ]
    fake._published = {
        "singleton_key": "active_registry",
        "version": 2,
        "entries": copy.deepcopy(fake._history_docs[1]["entries"]),
        "updated_at": "2026-01-03T00:00:00Z",
        "last_queue_id": "q2",
    }

    with _patch_auth(_ADMIN_USER), _patch_registry_http(fake):
        r403 = client.post("/api/admin/compliance/registry/published/revert-to/1")
    assert r403.status_code == 403

    with _patch_auth(_OWNER_USER), _patch_registry_http(fake):
        r = client.post("/api/admin/compliance/registry/published/revert-to/1")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("published_version") == 3
    assert body.get("reverted_from_published_line_version") == 1
    assert body.get("rematerialisation", {}).get("automatic_for_all_properties") is False
    assert fake._published.get("version") == 3
    assert fake._published["entries"]["GAS_SAFETY|DEFAULT"]["identity"]["name"] == "V1"
    assert len(fake._history_docs) == 3
    assert fake._history_docs[-1].get("activation_kind") == "revert"
