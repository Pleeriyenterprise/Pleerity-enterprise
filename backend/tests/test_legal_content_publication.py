"""Tests for governed legal content publication (CMS → public API)."""
from __future__ import annotations

import pytest

from services.legal_content_defaults import CANONICAL_DEFAULTS, LEGAL_SLUGS, PROVENANCE
from services.legal_content_service import (
    get_reset_default,
    render_legal_markdown_html,
    sanitize_legal_markdown,
    seed_canonical_content,
)


def test_sanitize_strips_script_and_html():
    dirty = "# Title\n\n**bold**\n\n<script>alert(1)</script>\n\n<p onclick=\"x\">hi</p>"
    clean = sanitize_legal_markdown(dirty)
    assert "<script>" not in clean.lower()
    assert "onclick" not in clean.lower()
    assert "**bold**" in clean


def test_render_markdown_headings_and_lists():
    md = "# H1\n\n## H2\n\n- one\n- two\n\n1. a\n2. b\n\n[link](https://example.com)"
    html = render_legal_markdown_html(md)
    assert "<h1>" in html
    assert "<h2>" in html
    assert "<ul>" in html
    assert "<ol>" in html
    assert "<a href=\"https://example.com\"" in html
    assert "<script>" not in html


def test_render_blocks_injected_script():
    html = render_legal_markdown_html("<script>alert('x')</script>\n\n# Safe")
    assert "<script>" not in html.lower()
    assert "<h1>" in html


def test_all_slugs_have_canonical_defaults():
    for slug in LEGAL_SLUGS:
        assert slug in CANONICAL_DEFAULTS
        assert CANONICAL_DEFAULTS[slug]["content"].strip()
        assert CANONICAL_DEFAULTS[slug]["title"].strip()


def test_reset_default_covers_all_slugs():
    for slug in LEGAL_SLUGS:
        row = get_reset_default(slug)
        assert row is not None
        assert row["content"].strip()


def test_terms_include_subscription_language():
    terms = CANONICAL_DEFAULTS["terms"]["content"].lower()
    assert "subscription" in terms
    assert "recurring" in terms
    assert "stripe" in terms
    assert "not legal advice" in terms or "does not constitute legal advice" in terms


@pytest.mark.asyncio
async def test_seed_idempotent_skips_seeded():
    class FakeCol:
        def __init__(self):
            self.docs = {}

        async def find_one(self, query, projection=None):
            return self.docs.get(query.get("slug"))

        async def update_one(self, query, update, upsert=False):
            slug = query["slug"]
            self.docs[slug] = {**self.docs.get(slug, {}), **update["$set"]}

        async def insert_one(self, doc):
            return None

    class FakeDb:
        def __init__(self):
            self.legal_content = FakeCol()
            self.legal_content_versions = FakeCol()

    db = FakeDb()
    first = await seed_canonical_content(db, actor_email="test@example.com")
    seeded = [r for r in first["results"] if r["action"] == "seeded"]
    assert len(seeded) == len(LEGAL_SLUGS)

    second = await seed_canonical_content(db, actor_email="test@example.com")
    skipped = [r for r in second["results"] if r["action"] == "skipped"]
    assert len(skipped) == len(LEGAL_SLUGS)
    assert all(r.get("reason") == "already_seeded" for r in skipped)


@pytest.mark.asyncio
async def test_get_published_content_uses_cms_when_present():
    from services.legal_content_service import get_published_content

    class FakeCol:
        async def find_one(self, query, projection=None):
            if query.get("slug") == "privacy":
                return {
                    "slug": "privacy",
                    "title": "Privacy Policy",
                    "content": "# CMS Privacy\n\nCustom body.",
                    "version": 2,
                    "updated_at": None,
                }
            return None

    class FakeDb:
        legal_content = FakeCol()

    payload = await get_published_content(FakeDb(), "privacy")
    assert payload["source"] == "cms"
    assert payload["version"] == 2
    assert "CMS Privacy" in payload["content"]
    assert payload["fallback_used"] is False


@pytest.mark.asyncio
async def test_get_published_content_falls_back_when_empty():
    from services.legal_content_service import get_published_content

    class FakeCol:
        async def find_one(self, query, projection=None):
            return {"slug": "privacy", "title": "", "content": "", "version": 0}

    class FakeDb:
        legal_content = FakeCol()

    payload = await get_published_content(FakeDb(), "privacy")
    assert payload["source"] == "canonical_fallback"
    assert payload["fallback_used"] is True
    assert "Privacy Policy" in payload["content"] or "GDPR" in payload["content"]
