"""
Strict public-safe filters and field extraction for the public support assistant
Knowledge Centre pipeline. No STAFF/ADMIN; no legacy articles with missing audience.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# Must match kb_articles collection usage in routes/knowledge_base.py
KB_ARTICLES_COLLECTION = "kb_articles"

# Public support indexing + retrieval: USER only (explicit; no $exists fallback).
STRICT_USER_PUBLISHED_ACTIVE_FILTER: Dict[str, Any] = {
    "status": "published",
    "is_active": True,
    "audience": "USER",
}


def strip_html_to_text(raw: Optional[str]) -> str:
    """Remove script/style/tags; collapse whitespace. For chunking only."""
    if not raw:
        return ""
    text = str(raw)
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def public_safe_article_payload(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fields allowed into support_public_content_chunks for kb_article sources.
    No draft/status/version/admin metadata.
    """
    tags = article.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    return {
        "article_id": article.get("article_id"),
        "slug": article.get("slug"),
        "title": (article.get("title") or "").strip(),
        "excerpt": (article.get("excerpt") or "").strip(),
        "content": strip_html_to_text(article.get("content") or ""),
        "tags": [str(t).strip() for t in tags if str(t).strip()],
        "published_at": article.get("published_at"),
    }


def split_into_chunks(text: str, max_len: int = 900, overlap: int = 80) -> List[str]:
    """Greedy character windows with overlap for long articles."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_len:
        return [text]
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_len, len(text))
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks
