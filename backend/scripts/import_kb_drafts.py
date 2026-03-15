"""
Import Knowledge Centre draft articles from docs/knowledge-centre-drafts/drafts/*.md.

Idempotent: inserts only if slug does not already exist. All articles are created
with status=draft. Do NOT publishes automatically.

Run from backend dir: python -m scripts.import_kb_drafts
Or: PYTHONPATH=backend python backend/scripts/import_kb_drafts.py

Requires: MongoDB reachable (same as app); PyYAML.
"""

import asyncio
import re
import sys
import uuid
import yaml
from pathlib import Path
from datetime import datetime, timezone

_backend_root = Path(__file__).resolve().parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

# Repo root (parent of backend)
_repo_root = _backend_root.parent
_drafts_dir = _repo_root / "docs" / "knowledge-centre-drafts" / "drafts"

ARTICLES_COLLECTION = "kb_articles"


def generate_article_id() -> str:
    return f"kb-{uuid.uuid4().hex[:12]}"


def parse_draft_md(filepath: Path) -> tuple[dict, str]:
    """Parse a draft .md file: frontmatter (YAML) and body. Returns (frontmatter, body)."""
    text = filepath.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not match:
        raise ValueError(f"No frontmatter in {filepath}")
    front = yaml.safe_load(match.group(1)) or {}
    body = match.group(2).strip()
    return front, body


def build_article_doc(front: dict, body: str, now: str) -> dict:
    """Build kb_articles document from frontmatter and body. status is always draft."""
    slug = front.get("slug") or ""
    title = front.get("title") or "Untitled"
    excerpt = (front.get("excerpt") or body[:500]).strip()
    if len(excerpt) < 10:
        excerpt = (body[:500] or title).strip() or "No summary."
    excerpt = excerpt[:500]
    audience = (front.get("audience") or "USER").upper()
    if audience not in ("USER", "ADMIN", "STAFF"):
        audience = "USER"
    category_id = front.get("category_id") or "getting-started"
    tags = front.get("tags")
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    elif not isinstance(tags, list):
        tags = []
    module = front.get("module") or ""
    article_type = front.get("article_type")  # e.g. release_notes

    return {
        "article_id": generate_article_id(),
        "title": title[:200],
        "slug": slug[:100],
        "category_id": category_id,
        "excerpt": excerpt,
        "content": body,
        "tags": tags,
        "status": "draft",
        "audience": audience,
        "version": "1.0",
        "summary": excerpt,
        "meta_title": title[:200],
        "meta_description": excerpt,
        "view_count": 0,
        "is_active": True,
        "product_module": module or None,
        "related_feature_flags": [],
        "article_type": article_type,
        "release_version": None,
        "release_date": None,
        "changes": [],
        "affected_modules": [],
        "created_at": now,
        "created_by": "import_kb_drafts",
        "updated_at": now,
        "updated_by": "import_kb_drafts",
        "published_at": None,
    }


async def main():
    if not _drafts_dir.exists():
        print(f"Drafts dir not found: {_drafts_dir}")
        print("Run from repo root or ensure docs/knowledge-centre-drafts/drafts/ exists.")
        return

    draft_files = sorted(_drafts_dir.glob("*.md"))
    draft_files = [f for f in draft_files if f.name != "README.md"]
    if not draft_files:
        print("No draft .md files found (excluding README.md).")
        return

    await __import__("database").database.connect()
    db = __import__("database").database.get_db()
    if db is None:
        print("Database not connected.")
        return

    # Categories are created when the app or KB API runs. If this is a fresh DB,
    # run the app once or seed_kb_articles so category_id values exist.
    now = datetime.now(timezone.utc).isoformat()
    created = 0
    skipped = 0

    for filepath in draft_files:
        try:
            front, body = parse_draft_md(filepath)
        except Exception as e:
            print(f"  Skip {filepath.name}: parse error — {e}")
            skipped += 1
            continue

        slug = front.get("slug")
        if not slug:
            print(f"  Skip {filepath.name}: no slug in frontmatter.")
            skipped += 1
            continue

        existing = await db[ARTICLES_COLLECTION].find_one({"slug": slug})
        if existing:
            print(f"  Skip (exists): {slug}")
            skipped += 1
            continue

        doc = build_article_doc(front, body, now)
        await db[ARTICLES_COLLECTION].insert_one(doc)
        print(f"  Created (draft): {slug} — {doc['title']}")
        created += 1

    print(f"\nDone. Created: {created}, Skipped: {skipped}. All new articles have status=draft.")


if __name__ == "__main__":
    asyncio.run(main())
