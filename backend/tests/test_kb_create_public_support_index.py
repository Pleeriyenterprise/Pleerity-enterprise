"""Public support index sync on KB article create (USER published only via strict filter)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routes.knowledge_base import (
    ArticleAudience,
    ArticleCreate,
    ArticleStatus,
    admin_create_article,
)


def _valid_create_request(
    *,
    status: ArticleStatus = ArticleStatus.PUBLISHED,
    audience: ArticleAudience = ArticleAudience.USER,
) -> ArticleCreate:
    return ArticleCreate(
        title="Test Published Article Title",
        category_id="getting-started",
        excerpt="Excerpt long enough for validation rules in the test case here.",
        content="Content body long enough for validation. " * 5,
        status=status,
        audience=audience,
    )


@pytest.mark.asyncio
async def test_admin_create_article_calls_sync():
    """POST create must invoke the same sync hook as update/publish."""
    inserted: dict = {}

    class Articles:
        async def find_one(self, q):
            return None

        async def insert_one(self, doc):
            inserted.update(doc)
            return MagicMock(inserted_id="oid")

    class Db:
        def __getitem__(self, name):
            return Articles()

    sync = AsyncMock()
    with patch("routes.knowledge_base.database.get_db", return_value=Db()):
        with patch("routes.knowledge_base.log_kb_action", new_callable=AsyncMock):
            with patch("routes.knowledge_base.generate_article_id", return_value="art-create-1"):
                with patch(
                    "routes.knowledge_base.sync_public_support_index_for_kb_article",
                    sync,
                ):
                    out = await admin_create_article(
                        _valid_create_request(),
                        {"email": "admin@test.com"},
                    )

    assert out["success"] is True
    sync.assert_awaited_once_with("art-create-1")
    assert inserted["status"] == "published"
    assert inserted["audience"] == "USER"
    assert inserted["is_active"] is True


@pytest.mark.asyncio
async def test_admin_create_draft_still_calls_sync():
    """Draft create calls sync; reindex_kb_article_by_id purges safely (no index)."""
    sync = AsyncMock()

    class Articles:
        async def find_one(self, q):
            return None

        async def insert_one(self, doc):
            return MagicMock(inserted_id="oid")

    class Db:
        def __getitem__(self, name):
            return Articles()

    with patch("routes.knowledge_base.database.get_db", return_value=Db()):
        with patch("routes.knowledge_base.log_kb_action", new_callable=AsyncMock):
            with patch("routes.knowledge_base.generate_article_id", return_value="art-draft-1"):
                with patch(
                    "routes.knowledge_base.sync_public_support_index_for_kb_article",
                    sync,
                ):
                    await admin_create_article(
                        _valid_create_request(status=ArticleStatus.DRAFT),
                        {"email": "admin@test.com"},
                    )

    sync.assert_awaited_once_with("art-draft-1")


@pytest.mark.asyncio
async def test_reindex_after_create_user_published_indexes():
    """Simulate post-create sync: USER published active article produces chunks."""
    from services.support_public_content_index_service import reindex_kb_article_by_id

    article = {
        "article_id": "u-create-1",
        "slug": "user-create-slug",
        "title": "Gas safety reminders",
        "excerpt": "About reminders",
        "content": "Paragraph one. " * 40,
        "tags": ["gas"],
        "status": "published",
        "audience": "USER",
        "is_active": True,
        "published_at": "2026-02-01T00:00:00+00:00",
    }

    replace_one = AsyncMock()

    class Articles:
        async def find_one(self, q, projection=None):
            if q.get("article_id") == "u-create-1":
                return article
            return None

    class Chunks:
        async def replace_one(self, *a, **k):
            await replace_one(*a, **k)

        async def delete_many(self, q):
            return MagicMock(deleted_count=0)

    colls = {"kb_articles": Articles(), "support_public_content_chunks": Chunks()}

    class Db:
        def __getitem__(self, name):
            return colls[name]

    with patch("services.support_public_content_index_service.database.get_db", return_value=Db()):
        result = await reindex_kb_article_by_id("u-create-1")

    assert result["indexed"] is True
    assert result["chunks"] >= 1
    assert replace_one.called


@pytest.mark.asyncio
async def test_reindex_after_create_user_draft_purges():
    from services.support_public_content_index_service import reindex_kb_article_by_id

    class Articles:
        async def find_one(self, q, projection=None):
            return None

    class Chunks:
        async def delete_many(self, q):
            assert q == {"source_type": "kb_article", "source_id": "u-draft-1"}
            return MagicMock(deleted_count=2)

    colls = {"kb_articles": Articles(), "support_public_content_chunks": Chunks()}

    class Db:
        def __getitem__(self, name):
            return colls[name]

    with patch("services.support_public_content_index_service.database.get_db", return_value=Db()):
        result = await reindex_kb_article_by_id("u-draft-1")

    assert result["indexed"] is False
    assert result["chunks"] == 0
    assert result["removed_chunks"] == 2


@pytest.mark.asyncio
async def test_reindex_staff_published_not_indexed():
    from services.support_public_content_index_service import reindex_kb_article_by_id

    class Articles:
        async def find_one(self, q, projection=None):
            assert q.get("audience") == "USER"
            return None

    class Chunks:
        async def delete_many(self, q):
            return MagicMock(deleted_count=0)

    colls = {"kb_articles": Articles(), "support_public_content_chunks": Chunks()}

    class Db:
        def __getitem__(self, name):
            return colls[name]

    with patch("services.support_public_content_index_service.database.get_db", return_value=Db()):
        for aid in ("staff-1", "admin-1"):
            result = await reindex_kb_article_by_id(aid)
            assert result["indexed"] is False
            assert result["chunks"] == 0
