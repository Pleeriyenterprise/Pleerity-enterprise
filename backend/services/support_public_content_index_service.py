"""
Indexed public content for the website support assistant (no per-chat HTTP crawl).

Phase 2: support_public_content_chunks — USER KC articles + allowlisted marketing pages.
Reindex on publish/update/unpublish; full rebuild for recovery.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from database import database

from services.kb_public_support_utils import (
    KB_ARTICLES_COLLECTION,
    STRICT_USER_PUBLISHED_ACTIVE_FILTER,
    public_safe_article_payload,
    split_into_chunks,
    strip_html_to_text,
)

logger = logging.getLogger(__name__)

SUPPORT_PUBLIC_CONTENT_CHUNKS = "support_public_content_chunks"

# Marketing routes only (no portal, admin, auth). Sync via reindex only — never per chat turn.
SITE_PAGE_ALLOWLIST: Sequence[str] = (
    "/",
    "/compliance-vault-pro",
    "/pricing",
    "/services",
    "/about",
    "/faq",
)


async def ensure_support_public_content_indexes() -> None:
    """Idempotent indexes for chunk collection."""
    db = database.get_db()
    coll = db[SUPPORT_PUBLIC_CONTENT_CHUNKS]
    await coll.create_index(
        [("source_type", 1), ("source_id", 1), ("chunk_index", 1)],
        unique=True,
        name="uniq_source_chunk",
    )
    await coll.create_index([("source_type", 1), ("indexed_at", -1)], name="type_indexed")
    await coll.create_index([("topic_tags", 1)], name="topic_tags")
    try:
        await coll.create_index([("chunk_text", "text"), ("title", "text")], name="chunk_text_title_text")
    except Exception as e:
        logger.warning("support_public_content: text index not created (may already exist or unsupported): %s", e)


def _chunk_doc_hash(chunk_text: str) -> str:
    return hashlib.sha256(chunk_text.encode("utf-8", errors="replace")).hexdigest()[:32]


async def delete_chunks_for_source(source_type: str, source_id: str) -> int:
    db = database.get_db()
    res = await db[SUPPORT_PUBLIC_CONTENT_CHUNKS].delete_many(
        {"source_type": source_type, "source_id": source_id}
    )
    return int(res.deleted_count or 0)


async def _upsert_chunk(doc: Dict[str, Any]) -> None:
    db = database.get_db()
    filt = {
        "source_type": doc["source_type"],
        "source_id": doc["source_id"],
        "chunk_index": doc["chunk_index"],
    }
    await db[SUPPORT_PUBLIC_CONTENT_CHUNKS].replace_one(filt, doc, upsert=True)


async def index_kb_article_from_doc(article: Dict[str, Any]) -> int:
    """
    Build chunks from a kb_articles document. Caller must ensure document matches
    STRICT_USER_PUBLISHED_ACTIVE_FILTER (strict USER only).
    """
    safe = public_safe_article_payload(article)
    aid = safe.get("article_id")
    slug = safe.get("slug")
    if not aid or not slug:
        logger.warning("support_public_content: skip article missing article_id or slug")
        return 0

    title = safe["title"]
    excerpt = safe["excerpt"]
    body = safe["content"]
    combined = f"{title}\n\n{excerpt}\n\n{body}".strip()
    if not combined:
        await delete_chunks_for_source("kb_article", aid)
        return 0

    tags = safe.get("tags") or []
    published_at = safe.get("published_at") or datetime.now(timezone.utc).isoformat()
    now = datetime.now(timezone.utc).isoformat()

    pieces = split_into_chunks(combined, max_len=900, overlap=80)
    count = 0
    for idx, chunk_text in enumerate(pieces):
        doc = {
            "source_type": "kb_article",
            "source_id": aid,
            "title": title,
            "slug": slug,
            "url": None,
            "audience": "USER",
            "status": "published",
            "chunk_text": chunk_text,
            "chunk_index": idx,
            "content_hash": _chunk_doc_hash(chunk_text),
            "topic_tags": list(tags),
            "indexed_at": now,
            "published_at": published_at,
        }
        await _upsert_chunk(doc)
        count += 1
    # Remove stale higher chunk indices if article shrank
    db = database.get_db()
    await db[SUPPORT_PUBLIC_CONTENT_CHUNKS].delete_many(
        {"source_type": "kb_article", "source_id": aid, "chunk_index": {"$gte": count}}
    )
    return count


async def reindex_kb_article_by_id(article_id: str) -> Dict[str, Any]:
    """Load article with strict USER published filter; index or purge."""
    db = database.get_db()
    q = {"article_id": article_id, **STRICT_USER_PUBLISHED_ACTIVE_FILTER}
    article = await db[KB_ARTICLES_COLLECTION].find_one(q, {"_id": 0})
    if not article:
        deleted = await delete_chunks_for_source("kb_article", article_id)
        return {"indexed": False, "chunks": 0, "removed_chunks": deleted}
    n = await index_kb_article_from_doc(article)
    return {"indexed": True, "chunks": n, "removed_chunks": 0}


async def reindex_all_published_user_kb_articles() -> Dict[str, Any]:
    """Full rebuild of all USER published active articles."""
    db = database.get_db()
    await delete_all_chunks_of_type("kb_article")
    cursor = db[KB_ARTICLES_COLLECTION].find(STRICT_USER_PUBLISHED_ACTIVE_FILTER, {"_id": 0})
    total_chunks = 0
    articles = 0
    async for article in cursor:
        total_chunks += await index_kb_article_from_doc(article)
        articles += 1
    return {"articles": articles, "chunks": total_chunks}


async def delete_all_chunks_of_type(source_type: str) -> int:
    db = database.get_db()
    res = await db[SUPPORT_PUBLIC_CONTENT_CHUNKS].delete_many({"source_type": source_type})
    return int(res.deleted_count or 0)


def _strip_boilerplate_html(html: str) -> str:
    """Nav/footer heuristics — best-effort for marketing HTML."""
    h = html or ""
    h = re.sub(r"(?is)<nav[^>]*>.*?</nav>", " ", h)
    h = re.sub(r"(?is)<footer[^>]*>.*?</footer>", " ", h)
    h = re.sub(r"(?is)<header[^>]*>.*?</header>", " ", h)
    return strip_html_to_text(h)


async def reindex_allowlisted_site_pages(
    base_url: Optional[str] = None,
    paths: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Fetch allowlisted public routes once (admin/cron/deploy hook). Not called per chat turn.
    """
    try:
        import httpx
    except ImportError as e:
        raise RuntimeError("httpx is required for site page reindex") from e

    from utils.app_urls import get_app_base_url

    base = (base_url or get_app_base_url(for_email_links=True)).rstrip("/")
    use_paths = list(paths) if paths is not None else list(SITE_PAGE_ALLOWLIST)

    await delete_all_chunks_of_type("site_page")
    now = datetime.now(timezone.utc).isoformat()
    indexed = 0
    errors: List[str] = []

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        for path in use_paths:
            url = base + (path if path.startswith("/") else "/" + path)
            sid = path or "/"
            try:
                resp = await client.get(url, headers={"User-Agent": "PleeritySupportPublicIndex/1.0"})
                if resp.status_code >= 400:
                    errors.append(f"{url} status {resp.status_code}")
                    continue
                text = _strip_boilerplate_html(resp.text)
                if len(text) < 80:
                    errors.append(f"{url} too little text after strip")
                    continue
                title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", resp.text)
                title = strip_html_to_text(title_match.group(1)) if title_match else path
                pieces = split_into_chunks(text, max_len=1200, overlap=100)
                for idx, chunk_text in enumerate(pieces):
                    doc = {
                        "source_type": "site_page",
                        "source_id": sid,
                        "title": title[:200],
                        "slug": None,
                        "url": url,
                        "audience": "PUBLIC",
                        "status": "published",
                        "chunk_text": chunk_text,
                        "chunk_index": idx,
                        "content_hash": _chunk_doc_hash(chunk_text),
                        "topic_tags": [path.strip("/") or "home"],
                        "indexed_at": now,
                        "published_at": now,
                    }
                    await _upsert_chunk(doc)
                    indexed += 1
            except Exception as ex:
                logger.warning("support_public_content: site fetch failed %s: %s", url, ex)
                errors.append(f"{url}: {ex}")

    return {"chunks": indexed, "errors": errors, "paths": use_paths}


async def full_reindex_public_support_content(
    *,
    include_site: bool = True,
    site_base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """KB full rebuild + optional allowlisted site sync."""
    await ensure_support_public_content_indexes()
    kb = await reindex_all_published_user_kb_articles()
    site: Dict[str, Any] = {"chunks": 0, "errors": []}
    if include_site:
        try:
            site = await reindex_allowlisted_site_pages(base_url=site_base_url)
        except Exception as e:
            site = {"chunks": 0, "errors": [str(e)]}
    return {"kb": kb, "site": site}
