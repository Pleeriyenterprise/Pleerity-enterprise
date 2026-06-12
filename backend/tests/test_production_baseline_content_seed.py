"""Tests for production baseline content seed (system-owned only)."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

import pytest

from services.legal_content_defaults import LEGAL_SLUGS, PROVENANCE
from services.production_baseline_content_seed import (
    ALLOWED_WRITE_COLLECTIONS,
    BASELINE_KB_PROVENANCE,
    FORBIDDEN_TOUCH_COLLECTIONS,
    plan_production_baseline_seed,
    run_production_baseline_seed,
)
from scripts.seed_kb_articles import EXAMPLE_ARTICLES


class _FakeCol:
    def __init__(self, name: str, store: Dict[str, Dict[str, Any]]):
        self.name = name
        self.store = store
        self.writes: List[Dict[str, Any]] = []

    async def find_one(self, query: Dict[str, Any], projection=None):
        if self.name == "kb_categories":
            return self.store.get(f"cat:{query.get('category_id')}")
        if self.name == "kb_articles":
            return self.store.get(f"article:{query.get('slug')}")
        if self.name == "legal_content":
            return self.store.get(f"legal:{query.get('slug')}")
        if self.name == "compliance_requirement_registry_drafts":
            key = f"{query.get('canonical_code')}|{query.get('scope_key')}"
            return self.store.get(f"draft:{key}")
        if self.name == "compliance_requirement_registry_published":
            if query.get("singleton_key") == "active_registry":
                return self.store.get("published:active_registry")
        return None

    async def insert_one(self, doc: Dict[str, Any]):
        self.writes.append({"op": "insert_one", "doc": copy.deepcopy(doc)})
        if self.name == "kb_categories":
            self.store[f"cat:{doc['category_id']}"] = {k: v for k, v in doc.items() if k != "_id"}
        elif self.name == "kb_articles":
            self.store[f"article:{doc['slug']}"] = {k: v for k, v in doc.items() if k != "_id"}
        elif self.name == "legal_content_versions":
            pass
        elif self.name == "compliance_requirement_registry_drafts":
            key = f"{doc.get('canonical_code')}|{doc.get('scope_key')}"
            self.store[f"draft:{key}"] = {k: v for k, v in doc.items() if k != "_id"}
        elif self.name == "compliance_requirement_registry_published_history":
            pass
        return None

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        self.writes.append({"op": "update_one", "query": query, "update": update, "upsert": upsert})
        if self.name == "legal_content" and upsert:
            slug = query["slug"]
            row = self.store.get(f"legal:{slug}") or {}
            row.update(update.get("$set", {}))
            self.store[f"legal:{slug}"] = row
        elif self.name == "kb_articles":
            slug = query["slug"]
            row = self.store.get(f"article:{slug}") or {}
            row.update(update.get("$set", {}))
            self.store[f"article:{slug}"] = row
        elif self.name == "compliance_requirement_registry_drafts":
            key = f"{query.get('canonical_code')}|{query.get('scope_key')}"
            row = self.store.get(f"draft:{key}") or {}
            row.update(update.get("$set", {}))
            self.store[f"draft:{key}"] = row
        elif self.name == "compliance_requirement_registry_published" and upsert:
            self.store["published:active_registry"] = update.get("$set", {})
        return None

    def find(self, query: Dict[str, Any], projection=None):
        class _Cursor:
            def __init__(self, rows: List[Dict[str, Any]]):
                self._rows = rows

            def sort(self, *_args, **_kwargs):
                return self

            async def to_list(self, limit: int):
                return self._rows[:limit]

        if self.name == "compliance_requirement_registry_drafts":
            rows = [v for k, v in self.store.items() if k.startswith("draft:")]
            return _Cursor(rows)
        return _Cursor([])


class _FakeDb:
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}
        self.legal_content = _FakeCol("legal_content", self._store)
        self.legal_content_versions = _FakeCol("legal_content_versions", self._store)
        self.kb_articles = _FakeCol("kb_articles", self._store)
        self.kb_categories = _FakeCol("kb_categories", self._store)
        self.compliance_requirement_registry_drafts = _FakeCol(
            "compliance_requirement_registry_drafts", self._store
        )
        self.compliance_requirement_registry_published = _FakeCol(
            "compliance_requirement_registry_published", self._store
        )
        self.compliance_requirement_registry_published_history = _FakeCol(
            "compliance_requirement_registry_published_history", self._store
        )
        # Operational collections — track accidental writes
        self.clients = _FakeCol("clients", self._store)
        self.portal_users = _FakeCol("portal_users", self._store)
        self.documents = _FakeCol("documents", self._store)

    def __getitem__(self, name: str) -> _FakeCol:
        return getattr(self, name)

    def all_writes(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for attr in (
            "legal_content",
            "legal_content_versions",
            "kb_articles",
            "kb_categories",
            "compliance_requirement_registry_drafts",
            "compliance_requirement_registry_published",
            "compliance_requirement_registry_published_history",
            "clients",
            "portal_users",
            "documents",
        ):
            col = getattr(self, attr)
            out.extend([(attr, w) for w in col.writes])
        return out


@pytest.mark.asyncio
async def test_empty_baseline_dry_run_plans_creates():
    db = _FakeDb()
    plan = await plan_production_baseline_seed(db)
    assert plan["dry_run"] is True
    assert plan["counts"]["create"] > 0
    assert plan["counts"]["seed"] == len(LEGAL_SLUGS)
    collections = {a["collection"] for a in plan["actions"]}
    assert "legal_content" in collections
    assert "kb_articles" in collections
    assert "kb_categories" in collections
    assert "compliance_requirement_registry_drafts" in collections


@pytest.mark.asyncio
async def test_apply_then_rerun_is_idempotent():
    db = _FakeDb()
    first = await run_production_baseline_seed(db, dry_run=False)
    assert first["dry_run"] is False
    assert first["kb_articles"]["created"] == len(EXAMPLE_ARTICLES)
    assert first["legal"]["provenance"] == PROVENANCE

    second_plan = await plan_production_baseline_seed(db)
    assert second_plan["counts"]["skip"] >= len(EXAMPLE_ARTICLES) + len(LEGAL_SLUGS)


@pytest.mark.asyncio
async def test_no_customer_collections_touched():
    db = _FakeDb()
    await run_production_baseline_seed(db, dry_run=False)
    writes = db.all_writes()
    touched = {name for name, _ in writes}
    assert not touched.intersection(FORBIDDEN_TOUCH_COLLECTIONS)
    allowed = {name for name, _ in writes}
    assert allowed.issubset(ALLOWED_WRITE_COLLECTIONS)


@pytest.mark.asyncio
async def test_legal_pages_present_after_seed():
    db = _FakeDb()
    await run_production_baseline_seed(db, dry_run=False)
    for slug in LEGAL_SLUGS:
        row = await db.legal_content.find_one({"slug": slug})
        assert row is not None
        assert (row.get("content") or "").strip()
        assert row.get("provenance") == PROVENANCE


@pytest.mark.asyncio
async def test_kb_articles_present_after_seed():
    db = _FakeDb()
    await run_production_baseline_seed(db, dry_run=False)
    for item in EXAMPLE_ARTICLES:
        row = await db.kb_articles.find_one({"slug": item["slug"]})
        assert row is not None
        assert row.get("status") == "published"
        assert row.get("provenance") == BASELINE_KB_PROVENANCE


@pytest.mark.asyncio
async def test_registry_drafts_present_after_seed():
    db = _FakeDb()
    result = await run_production_baseline_seed(db, dry_run=False)
    assert result["registry_drafts"]["inserted"] > 0
    pub = await db.compliance_requirement_registry_published.find_one({"singleton_key": "active_registry"})
    assert pub is not None
    assert pub.get("version") == 1
    assert len(pub.get("entries") or {}) > 0


@pytest.mark.asyncio
async def test_custom_kb_article_not_overwritten():
    db = _FakeDb()
    db._store["article:uploading-evidence"] = {
        "slug": "uploading-evidence",
        "content": "CUSTOM USER EDIT",
        "created_by": "admin@example.com",
    }
    await run_production_baseline_seed(db, dry_run=False)
    row = await db.kb_articles.find_one({"slug": "uploading-evidence"})
    assert row["content"] == "CUSTOM USER EDIT"
