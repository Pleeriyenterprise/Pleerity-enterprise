"""Admin legal content editor hydration tests."""
from __future__ import annotations

from services.legal_content_defaults import LEGAL_SLUGS
from services.legal_content_service import preview_legal_draft, serialize_legal_admin_row


def test_serialize_legal_admin_row_from_mongo_doc():
    doc = {
        "slug": "privacy",
        "title": "Privacy Policy",
        "content": "# Privacy\n\nBody text.",
        "version": 3,
        "updated_at": None,
        "updated_by": "admin@example.com",
        "provenance": "canonical_seed_v1",
    }
    row = serialize_legal_admin_row(doc, "privacy")
    assert row["slug"] == "privacy"
    assert row["version"] == 3
    assert row["content_length"] > 10
    assert row["is_empty"] is False
    assert row["title"] == "Privacy Policy"


def test_serialize_legal_admin_row_empty_placeholder():
    row = serialize_legal_admin_row(None, "terms")
    assert row["slug"] == "terms"
    assert row["version"] == 0
    assert row["is_empty"] is True
    assert row["content"] == ""


def test_preview_legal_draft_applies_sanitisation():
    dirty = "# Title\n\n<script>alert(1)</script>\n\nSafe **bold**"
    row = preview_legal_draft("privacy", "Privacy Policy", dirty)
    assert row["slug"] == "privacy"
    assert "<script>" not in row["content"].lower()
    assert "**bold**" in row["content"]
    assert row["sanitization_applied"] is True
    assert row["content_length"] > 0


def test_preview_legal_draft_unchanged_clean_markdown():
    md = "# Privacy\n\nParagraph one."
    row = preview_legal_draft("privacy", "Privacy Policy", md)
    assert row["content"] == md
    assert row["sanitization_applied"] is False


def test_all_slugs_have_canonical_titles_when_missing():
    for slug in LEGAL_SLUGS:
        row = serialize_legal_admin_row(None, slug)
        assert row["title"]
        assert row["slug"] == slug
