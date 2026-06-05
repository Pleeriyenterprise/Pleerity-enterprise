"""
Governed legal/marketing content publication service.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from markdown_it import MarkdownIt

from services.legal_content_defaults import (
    CANONICAL_DEFAULTS,
    LEGAL_SLUGS,
    PROVENANCE,
    get_canonical,
)

_MD = MarkdownIt("commonmark", {"html": False}).enable("table")

_SCRIPT_BLOCK = re.compile(
    r"<\s*(script|iframe|object|embed|form|style)\b[^>]*>.*?</\s*\1\s*>",
    re.DOTALL | re.IGNORECASE,
)
_SCRIPT_VOID = re.compile(
    r"<\s*(script|iframe|object|embed|form|style)\b[^>]*/\s*>",
    re.IGNORECASE,
)
_EVENT_HANDLER = re.compile(r"\s+on[a-z]+\s*=\s*[\"'][^\"']*[\"']", re.IGNORECASE)
_HTML_TAG = re.compile(r"<[^>]+>")


def sanitize_legal_markdown(content: str) -> str:
    """Strip unsafe HTML; legal pages are markdown-first."""
    if not content:
        return ""
    s = content.replace("\x00", "")
    s = _SCRIPT_BLOCK.sub("", s)
    s = _SCRIPT_VOID.sub("", s)
    s = _EVENT_HANDLER.sub("", s)
    s = _HTML_TAG.sub("", s)
    return s.strip()


def render_legal_markdown_html(content: str) -> str:
    """Render sanitised markdown to safe HTML (no raw HTML input)."""
    clean = sanitize_legal_markdown(content)
    if not clean:
        return ""
    return _MD.render(clean)


def _iso(dt: Any) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.astimezone(timezone.utc).isoformat()
    return str(dt)


def _published_from_doc(doc: Optional[dict], slug: str) -> Dict[str, Any]:
    canonical = get_canonical(slug)
    if doc and (doc.get("version") or 0) > 0 and (doc.get("content") or "").strip():
        content = doc.get("content") or ""
        return {
            "slug": slug,
            "title": doc.get("title") or (canonical or {}).get("title", slug.title()),
            "content": content,
            "content_html": render_legal_markdown_html(content),
            "version": doc.get("version") or 0,
            "updated_at": _iso(doc.get("updated_at")),
            "source": "cms",
            "fallback_used": False,
        }
    if canonical:
        content = canonical["content"]
        return {
            "slug": slug,
            "title": canonical["title"],
            "content": content,
            "content_html": render_legal_markdown_html(content),
            "version": 0,
            "updated_at": None,
            "source": "canonical_fallback",
            "fallback_used": True,
        }
    return {
        "slug": slug,
        "title": slug.title(),
        "content": "",
        "content_html": "",
        "version": 0,
        "updated_at": None,
        "source": "empty",
        "fallback_used": True,
    }


async def get_published_content(db, slug: str) -> Dict[str, Any]:
    if slug not in LEGAL_SLUGS:
        return {"error": "not_found", "slug": slug}
    doc = await db.legal_content.find_one({"slug": slug}, {"_id": 0})
    return _published_from_doc(doc, slug)


async def seed_canonical_content(
    db,
    *,
    actor_email: str = "system@legal-content-seed",
    actor_user_id: str = "system",
    force: bool = False,
) -> Dict[str, Any]:
    """Idempotent seed from canonical static copy. Skips slugs with custom CMS content."""
    results = []
    now = datetime.now(timezone.utc)
    for slug in LEGAL_SLUGS:
        canonical = get_canonical(slug)
        if not canonical:
            results.append({"slug": slug, "action": "skipped", "reason": "no_canonical"})
            continue
        existing = await db.legal_content.find_one({"slug": slug}, {"_id": 0})
        if existing and not force:
            if existing.get("provenance") == PROVENANCE:
                results.append({"slug": slug, "action": "skipped", "reason": "already_seeded", "version": existing.get("version")})
                continue
            if (existing.get("version") or 0) > 0 and (existing.get("content") or "").strip():
                results.append({"slug": slug, "action": "skipped", "reason": "custom_content_present", "version": existing.get("version")})
                continue
        version = 1
        record = {
            "slug": slug,
            "title": canonical["title"],
            "content": canonical["content"],
            "version": version,
            "updated_at": now,
            "updated_by": actor_email,
            "updated_by_user_id": actor_user_id,
            "provenance": PROVENANCE,
            "seeded_at": now,
        }
        await db.legal_content.update_one({"slug": slug}, {"$set": record}, upsert=True)
        await db.legal_content_versions.insert_one(
            {
                **record,
                "version_id": f"{slug}_v{version}",
                "previous_content": existing.get("content") if existing else None,
                "previous_version": existing.get("version", 0) if existing else 0,
                "created_at": now,
                "action": "SEED_CANONICAL",
            }
        )
        results.append({"slug": slug, "action": "seeded", "version": version})
    return {"results": results, "provenance": PROVENANCE, "seeded_at": _iso(now)}


def get_reset_default(slug: str) -> Optional[Dict[str, str]]:
    canonical = get_canonical(slug)
    if not canonical:
        return None
    return {"title": canonical["title"], "content": canonical["content"]}


def preview_legal_draft(slug: str, title: str, content: str) -> Dict[str, Any]:
    """Non-persistent admin preview using the same sanitisation as save."""
    raw = content or ""
    clean = sanitize_legal_markdown(raw)
    return {
        "slug": slug,
        "title": (title or "").strip() or slug.title(),
        "content": clean,
        "content_length": len(clean.strip()),
        "sanitization_applied": clean != raw.strip(),
    }


def serialize_legal_admin_row(doc: Optional[dict], slug: str) -> Dict[str, Any]:
    """Normalize Mongo legal_content for admin editor hydration."""
    if not doc:
        canonical = get_canonical(slug)
        return {
            "slug": slug,
            "title": (canonical or {}).get("title") or f"{slug.title()} Page",
            "content": "",
            "version": 0,
            "updated_at": None,
            "updated_by": None,
            "provenance": None,
            "content_length": 0,
            "is_empty": True,
        }
    content = doc.get("content") or ""
    return {
        "slug": doc.get("slug", slug),
        "title": doc.get("title") or "",
        "content": content,
        "version": int(doc.get("version") or 0),
        "updated_at": _iso(doc.get("updated_at")),
        "updated_by": doc.get("updated_by"),
        "provenance": doc.get("provenance"),
        "content_length": len(content.strip()),
        "is_empty": len(content.strip()) == 0,
    }
