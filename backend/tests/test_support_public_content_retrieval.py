"""Public support content index + retrieval (Knowledge Centre USER, allowlisted site)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.kb_public_support_utils import (
    STRICT_USER_PUBLISHED_ACTIVE_FILTER,
    public_safe_article_payload,
    strip_html_to_text,
)


def test_strip_html_removes_tags():
    raw = "<p>Hello <b>world</b></p><script>x</script>"
    assert strip_html_to_text(raw) == "Hello world"


def test_public_safe_payload_no_internal_fields():
    article = {
        "article_id": "a1",
        "slug": "s1",
        "title": "T",
        "excerpt": "E",
        "content": "<p>Body</p>",
        "tags": ["x"],
        "published_at": "2026-01-01",
        "version": "99",
        "status": "published",
        "published_by": "admin@x.com",
    }
    safe = public_safe_article_payload(article)
    assert safe["article_id"] == "a1"
    assert "version" not in safe
    assert "published_by" not in safe
    assert "Body" in safe["content"]


def test_strict_user_filter_requires_explicit_user():
    assert STRICT_USER_PUBLISHED_ACTIVE_FILTER["audience"] == "USER"
    assert STRICT_USER_PUBLISHED_ACTIVE_FILTER["status"] == "published"
    assert STRICT_USER_PUBLISHED_ACTIVE_FILTER["is_active"] is True


@pytest.mark.asyncio
async def test_reindex_kb_article_find_uses_strict_filter():
    """STAFF/ADMIN documents must not be returned by the find_one used for indexing."""
    from services.support_public_content_index_service import reindex_kb_article_by_id

    class Articles:
        async def find_one(self, q, projection=None):
            assert q.get("audience") == "USER"
            assert q.get("status") == "published"
            assert q.get("is_active") is True
            assert q.get("article_id") == "art-1"
            return None

    class Chunks:
        async def delete_many(self, q):
            return MagicMock(deleted_count=0)

    colls = {"kb_articles": Articles(), "support_public_content_chunks": Chunks()}

    class Db:
        def __getitem__(self, name):
            return colls[name]

    with patch("services.support_public_content_index_service.database.get_db", return_value=Db()):
        await reindex_kb_article_by_id("art-1")


@pytest.mark.asyncio
async def test_published_user_article_produces_chunks():
    from services.support_public_content_index_service import index_kb_article_from_doc

    replace_one = AsyncMock()

    class Chunks:
        async def replace_one(self, *a, **k):
            await replace_one(*a, **k)

        async def delete_many(self, q):
            return MagicMock(deleted_count=0)

    class Db:
        def __getitem__(self, name):
            assert name == "support_public_content_chunks"
            return Chunks()

    article = {
        "article_id": "u1",
        "slug": "user-slug",
        "title": "Gas safety reminders",
        "excerpt": "About reminders",
        "content": "Paragraph one. " * 40,
        "tags": ["gas", "reminders"],
        "published_at": "2026-02-01T00:00:00+00:00",
    }

    with patch("services.support_public_content_index_service.database.get_db", return_value=Db()):
        n = await index_kb_article_from_doc(article)
    assert n >= 1
    assert replace_one.called


@pytest.mark.asyncio
async def test_chunk_doc_has_no_internal_metadata():
    from services.support_public_content_index_service import index_kb_article_from_doc

    stored = []

    class Chunks:
        async def replace_one(self, filt, doc, upsert=False):
            stored.append(doc)

        async def delete_many(self, q):
            return MagicMock(deleted_count=0)

    class Db:
        def __getitem__(self, name):
            return Chunks()

    article = {
        "article_id": "z1",
        "slug": "z-slug",
        "title": "T",
        "excerpt": "E",
        "content": "Hello world content here.",
        "tags": ["t"],
        "published_at": "2026-01-01",
    }

    with patch("services.support_public_content_index_service.database.get_db", return_value=Db()):
        await index_kb_article_from_doc(article)

    assert stored
    doc = stored[0]
    for bad in ("version", "published_by", "meta_title", "related_feature_flags"):
        assert bad not in doc


@pytest.mark.asyncio
async def test_kc_preferred_over_site_when_both_match():
    """If KC clears threshold, site_page must not be selected."""
    from services.support_public_content_retrieval import try_public_support_content_answer

    kb_doc = {
        "source_type": "kb_article",
        "source_id": "k1",
        "title": "Upload evidence guide",
        "slug": "upload-evidence",
        "url": None,
        "audience": "USER",
        "status": "published",
        "chunk_text": "upload evidence documents compliance vault property evidence queue",
        "chunk_index": 0,
        "content_hash": "x",
        "topic_tags": ["documents"],
        "indexed_at": "2026-01-02",
        "published_at": "2026-01-01",
    }
    site_doc = {
        "source_type": "site_page",
        "source_id": "/services",
        "title": "Services",
        "slug": None,
        "url": "https://example.com/services",
        "audience": "PUBLIC",
        "status": "published",
        "chunk_text": "upload evidence services marketplace order",
        "chunk_index": 0,
        "content_hash": "y",
        "topic_tags": ["services"],
        "indexed_at": "2026-01-02",
        "published_at": "2026-01-02",
    }

    class CursorKb:
        def __init__(self, docs):
            self._docs = docs
            self._i = 0

        def sort(self, *a, **k):
            return self

        def limit(self, n):
            return self

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._i >= len(self._docs):
                raise StopAsyncIteration
            d = self._docs[self._i]
            self._i += 1
            return d

    class Coll:
        def find(self, q, projection=None):
            st = q.get("source_type")
            docs = [kb_doc] if st == "kb_article" else [site_doc]
            return CursorKb(docs)

    class Db:
        def __getitem__(self, name):
            assert name == "support_public_content_chunks"
            return Coll()

    with patch("services.support_public_content_retrieval.database.get_db", return_value=Db()):
        with patch("services.support_public_content_retrieval.get_app_base_url", return_value="https://example.com"):
            out = await try_public_support_content_answer(
                "how do I upload evidence for my property",
                None,
            )
    assert out is not None
    assert out["metadata"]["retrieval_path"] == ["kc_article"]
    assert out["metadata"]["sources"][0]["source_type"] == "kb_article"
    assert out["metadata"].get("conversational_synthesis") is True
    assert "gist" in out["response"].lower() or "walkthrough" in out["response"].lower()
