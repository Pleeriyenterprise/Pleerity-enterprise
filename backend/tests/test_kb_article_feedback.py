"""
KB article helpful / not helpful feedback API and public article serialization.

Seeds/cleans test rows with synchronous PyMongo so Motor (TestClient lifespan loop)
is never used from a different asyncio loop.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
from pymongo import MongoClient

from middleware import admin_route_guard


def _sync_db():
    url = os.environ.get("MONGO_URL")
    name = os.environ.get("DB_NAME", "compliance_vault_pro_test")
    if not url:
        pytest.skip("MONGO_URL not set")
    try:
        client = MongoClient(url, serverSelectionTimeoutMS=8000)
        client.admin.command("ping")
        return client[name]
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"MongoDB not reachable: {exc}")


def _cleanup_sync(db, article_id: str):
    db["kb_article_feedback"].delete_many({"article_id": article_id})
    db["kb_articles"].delete_many({"article_id": article_id})


def _seed_published_user_article_sync(db):
    aid = f"kb-testfeed-{uuid.uuid4().hex[:10]}"
    slug = f"kb-testfeed-{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()
    db["kb_articles"].insert_one(
        {
            "article_id": aid,
            "slug": slug,
            "title": "Test feedback article",
            "category_id": "getting-started",
            "excerpt": "Short excerpt for tests that meets minimum length requirements here.",
            "content": "Body content " * 20,
            "tags": ["test", "feedback"],
            "status": "published",
            "audience": "USER",
            "version": "9.9.9",
            "view_count": 0,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "published_at": now,
        }
    )
    return aid, slug


@pytest.mark.integration
def test_kb_public_anonymous_feedback_inserts_and_duplicate_no_second_row(client):
    """Items 1–2: insert one row; duplicate response; DB still has exactly one row for that dedupe."""
    sdb = _sync_db()
    aid, slug = _seed_published_user_article_sync(sdb)
    session_id = f"pytest-sess-{uuid.uuid4().hex[:16]}"
    try:
        assert sdb["kb_article_feedback"].count_documents({"article_id": aid}) == 0

        r1 = client.post(
            f"/api/kb/articles/{aid}/feedback",
            json={"feedback_type": "helpful", "session_id": session_id},
        )
        assert r1.status_code == 200, r1.text
        b1 = r1.json()
        assert b1["ok"] is True
        assert b1["duplicate"] is False
        assert b1["totals"]["total"] == 1
        assert sdb["kb_article_feedback"].count_documents({"article_id": aid}) == 1
        row = sdb["kb_article_feedback"].find_one({"article_id": aid})
        assert row["dedupe_key"] == f"session:{session_id}"
        assert row["feedback_type"] == "helpful"
        assert row["source_surface"] == "public_kb"

        r2 = client.post(
            f"/api/kb/articles/{aid}/feedback",
            json={"feedback_type": "not_helpful", "session_id": session_id},
        )
        assert r2.status_code == 200
        b2 = r2.json()
        assert b2["duplicate"] is True
        assert b2["totals"]["helpful"] == 1
        assert sdb["kb_article_feedback"].count_documents({"article_id": aid}) == 1

        g = client.get(f"/api/kb/articles/{slug}")
        assert g.status_code == 200
        data = g.json()
        assert "status" not in data
        assert "audience" not in data
        assert "version" not in data
        assert data.get("article_id") == aid
        assert "category_name" in data
    finally:
        _cleanup_sync(sdb, aid)


@pytest.mark.integration
def test_kb_public_feedback_requires_session_when_anonymous(client):
    sdb = _sync_db()
    aid, _slug = _seed_published_user_article_sync(sdb)
    try:
        r = client.post(
            f"/api/kb/articles/{aid}/feedback",
            json={"feedback_type": "helpful"},
        )
        assert r.status_code == 400
    finally:
        _cleanup_sync(sdb, aid)


@pytest.mark.integration
def test_kb_public_feedback_invalid_session_id_rejected(client):
    """Item 9: invalid session_id must not be accepted for anonymous voters."""
    sdb = _sync_db()
    aid, _slug = _seed_published_user_article_sync(sdb)
    try:
        r_short = client.post(
            f"/api/kb/articles/{aid}/feedback",
            json={"feedback_type": "helpful", "session_id": "short"},
        )
        assert r_short.status_code == 400

        r_bad = client.post(
            f"/api/kb/articles/{aid}/feedback",
            json={"feedback_type": "helpful", "session_id": "bad!@#chars"},
        )
        assert r_bad.status_code == 400
    finally:
        _cleanup_sync(sdb, aid)


@pytest.mark.integration
def test_kb_public_feedback_unknown_article(client):
    _sync_db()
    r = client.post(
        "/api/kb/articles/kb-nonexistent-zzzzzzzz/feedback",
        json={"feedback_type": "helpful", "session_id": f"pytest-sess-{uuid.uuid4().hex[:16]}"},
    )
    assert r.status_code == 404


@pytest.mark.integration
def test_kb_client_help_feedback_uses_authenticated_dedupe_key(client):
    """Item 3: client path dedupes on user:* not session:*."""
    from middleware import client_route_guard

    sdb = _sync_db()
    aid, _slug = _seed_published_user_article_sync(sdb)
    portal_user_id = f"pytest-portal-{uuid.uuid4().hex[:12]}"

    async def _fake_client_user():
        return {
            "portal_user_id": portal_user_id,
            "client_id": "pytest-client-ignored",
            "role": "USER",
        }

    app = __import__("server", fromlist=["app"]).app
    app.dependency_overrides[client_route_guard] = _fake_client_user
    try:
        assert sdb["kb_article_feedback"].count_documents({"article_id": aid}) == 0

        r1 = client.post(
            f"/api/client/help/articles/{aid}/feedback",
            json={"feedback_type": "helpful"},
        )
        assert r1.status_code == 200, r1.text
        assert r1.json()["duplicate"] is False
        row = sdb["kb_article_feedback"].find_one({"article_id": aid})
        assert row["dedupe_key"] == f"user:{portal_user_id}"
        assert row["source_surface"] == "client_help"

        r2 = client.post(
            f"/api/client/help/articles/{aid}/feedback",
            json={"feedback_type": "not_helpful"},
        )
        assert r2.status_code == 200
        assert r2.json()["duplicate"] is True
        assert sdb["kb_article_feedback"].count_documents({"article_id": aid}) == 1
    finally:
        app.dependency_overrides.pop(client_route_guard, None)
        _cleanup_sync(sdb, aid)


@pytest.mark.integration
def test_kb_client_help_article_get_excludes_internal_metadata(client):
    """Item 5: client Help article JSON must not leak status / audience / version."""
    from middleware import client_route_guard

    sdb = _sync_db()
    aid, slug = _seed_published_user_article_sync(sdb)

    async def _fake_client_user():
        return {"portal_user_id": f"pytest-{uuid.uuid4().hex[:8]}", "role": "USER"}

    app = __import__("server", fromlist=["app"]).app
    app.dependency_overrides[client_route_guard] = _fake_client_user
    try:
        r = client.get(f"/api/client/help/articles/{slug}")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "status" not in data
        assert "audience" not in data
        assert "version" not in data
        assert data.get("article_id") == aid
    finally:
        app.dependency_overrides.pop(client_route_guard, None)
        _cleanup_sync(sdb, aid)


@pytest.mark.integration
def test_kb_admin_feedback_summary_totals_and_pct(client):
    """Item 6: seeded rows in-window appear in aggregates with expected helpful_pct."""
    sdb = _sync_db()
    aid = f"kb-analytics-{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()
    docs = [
        {
            "feedback_id": f"kbf-{uuid.uuid4().hex[:12]}",
            "article_id": aid,
            "article_slug": "x",
            "article_title_snapshot": "Analytics seed",
            "article_audience_snapshot": "USER",
            "article_category_id": "getting-started",
            "feedback_type": "helpful",
            "user_id": None,
            "session_fingerprint": "s1",
            "dedupe_key": f"session:{uuid.uuid4().hex}",
            "voter_kind": "anonymous",
            "source_surface": "public_kb",
            "created_at": now,
        },
        {
            "feedback_id": f"kbf-{uuid.uuid4().hex[:12]}",
            "article_id": aid,
            "article_slug": "x",
            "article_title_snapshot": "Analytics seed",
            "article_audience_snapshot": "USER",
            "article_category_id": "getting-started",
            "feedback_type": "helpful",
            "user_id": None,
            "session_fingerprint": "s2",
            "dedupe_key": f"session:{uuid.uuid4().hex}",
            "voter_kind": "anonymous",
            "source_surface": "public_kb",
            "created_at": now,
        },
        {
            "feedback_id": f"kbf-{uuid.uuid4().hex[:12]}",
            "article_id": aid,
            "article_slug": "x",
            "article_title_snapshot": "Analytics seed",
            "article_audience_snapshot": "USER",
            "article_category_id": "getting-started",
            "feedback_type": "not_helpful",
            "user_id": None,
            "session_fingerprint": "s3",
            "dedupe_key": f"session:{uuid.uuid4().hex}",
            "voter_kind": "anonymous",
            "source_surface": "public_kb",
            "created_at": now,
        },
    ]
    for d in docs:
        d["dedupe_key"] = f"session:pytest-analytics-{uuid.uuid4().hex[:20]}"
    try:
        sdb["kb_article_feedback"].insert_many(docs)

        app = __import__("server", fromlist=["app"]).app

        async def _override_admin():
            return {"email": "admin@test.com"}

        app.dependency_overrides[admin_route_guard] = _override_admin
        try:
            r = client.get("/api/admin/kb/feedback-summary?days=30&limit=200")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["totals"]["votes"] >= 3
            row = next((a for a in body["articles"] if a.get("article_id") == aid), None)
            assert row is not None, body["articles"]
            assert row["votes"] == 3
            assert row["helpful"] == 2
            assert row["not_helpful"] == 1
            assert row["helpful_pct"] == pytest.approx(66.67, rel=1e-3)
        finally:
            app.dependency_overrides.pop(admin_route_guard, None)
    finally:
        sdb["kb_article_feedback"].delete_many({"article_id": aid})


@pytest.mark.integration
def test_kb_article_feedback_indexes_idempotent_pymongo():
    """Item 10: Mongo accepts repeated create_index on same keys (idempotent, non-destructive)."""
    sdb = _sync_db()
    coll = sdb["kb_article_feedback"]
    coll.create_index([("article_id", 1), ("dedupe_key", 1)], unique=True)
    coll.create_index([("article_id", 1), ("dedupe_key", 1)], unique=True)
    info = coll.index_information()
    keys = set()
    for v in info.values():
        raw = v.get("key")
        if raw is None:
            continue
        if isinstance(raw, dict):
            keys.add(tuple(raw.items()))
        else:
            keys.add(tuple(raw))
    assert (("article_id", 1), ("dedupe_key", 1)) in keys, keys


@pytest.mark.integration
def test_admin_kb_feedback_summary_smoke(client):
    _sync_db()
    from server import app

    async def _override_admin():
        return {"email": "admin@test.com"}

    app.dependency_overrides[admin_route_guard] = _override_admin
    try:
        r = client.get("/api/admin/kb/feedback-summary?days=30&limit=10")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "period_days" in body
        assert "totals" in body
        assert "articles" in body
        assert "lowest_helpful_pct_articles" in body
    finally:
        app.dependency_overrides.pop(admin_route_guard, None)
