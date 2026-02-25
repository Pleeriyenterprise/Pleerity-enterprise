"""
Export published CMS pages to the assistant knowledge base (assistant_kb).

Published page content is written as markdown files so the Pleerity Assistant
can answer questions using the marketing/website content. Run after meaningful
CMS publishes or on a schedule.

Run from repo root: python backend/scripts/export_cms_to_kb.py
Or from backend: python scripts/export_cms_to_kb.py (with PYTHONPATH=.)
"""

import asyncio
import re
import sys
from pathlib import Path

# Allow importing backend modules when run from repo root or backend
_backend = Path(__file__).resolve().parent.parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from database import database
from models.cms import PageStatus


KB_DIR = _backend / "docs" / "assistant_kb"
WEBSITE_PREFIX = "website_"
MAX_PAGE_CHARS = 12000  # Trim very long pages so KB stays usable


def _extract_text_from_value(val):
    """Recursively extract strings from block content (dict/list)."""
    if isinstance(val, str) and val.strip():
        return [val.strip()]
    if isinstance(val, dict):
        out = []
        for k, v in val.items():
            if k in ("block_id", "block_type", "order", "visible", "image_id", "background_image_id", "cta_link", "button_link"):
                continue
            out.extend(_extract_text_from_value(v))
        return out
    if isinstance(val, list):
        out = []
        for item in val:
            out.extend(_extract_text_from_value(item))
        return out
    return []


def _blocks_to_markdown(blocks):
    """Convert CMS blocks to a single markdown string."""
    if not blocks:
        return ""
    visible = [b for b in blocks if b.get("visible", True)]
    visible.sort(key=lambda x: x.get("order", 0))
    parts = []
    for block in visible:
        content = block.get("content") or {}
        bits = _extract_text_from_value(content)
        text = " ".join(bits)
        if text:
            parts.append(text)
    return "\n\n".join(parts)


async def export_cms_to_kb():
    """Export all published CMS pages to assistant_kb as website_<slug>.md."""
    await database.connect()
    db = database.get_db()

    cursor = db.cms_pages.find(
        {"status": PageStatus.PUBLISHED.value},
        {"_id": 0, "slug": 1, "title": 1, "description": 1, "blocks": 1},
    )
    pages = await cursor.to_list(length=500)

    KB_DIR.mkdir(parents=True, exist_ok=True)

    # Remove old website_*.md so unpublished pages are dropped
    for old in KB_DIR.glob(f"{WEBSITE_PREFIX}*.md"):
        old.unlink()

    exported = 0
    for page in pages:
        slug = (page.get("slug") or "").strip() or "page"
        title = (page.get("title") or slug).strip()
        description = (page.get("description") or "").strip()
        blocks = page.get("blocks") or []
        body = _blocks_to_markdown(blocks)
        if description and description not in body:
            body = f"{description}\n\n{body}" if body else description
        if len(body) > MAX_PAGE_CHARS:
            body = body[:MAX_PAGE_CHARS] + "\n\n[... content trimmed for KB ...]"
        # Safe filename: only alphanumeric, dash, underscore
        safe_slug = re.sub(r"[^a-z0-9_-]", "-", slug.lower()).strip("-") or "page"
        filename = f"{WEBSITE_PREFIX}{safe_slug}.md"
        filepath = KB_DIR / filename
        content = f"# {title}\n\nSource: website page /{slug}\n\n{body}".strip()
        filepath.write_text(content, encoding="utf-8")
        exported += 1
        print(f"  {filename}")

    print(f"Exported {exported} published CMS pages to {KB_DIR}")
    return exported


if __name__ == "__main__":
    asyncio.run(export_cms_to_kb())
