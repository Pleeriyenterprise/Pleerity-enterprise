"""
Seed example Knowledge Base (Help Centre) articles for USER audience.

Idempotent: creates articles only if a document with the same slug does not exist.
Run from backend dir: python -m scripts.seed_kb_articles
Or: PYTHONPATH=backend python backend/scripts/seed_kb_articles.py
"""

import asyncio
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone

_backend_root = Path(__file__).resolve().parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from database import database

ARTICLES_COLLECTION = "kb_articles"
CATEGORIES_COLLECTION = "kb_categories"


def generate_article_id() -> str:
    return f"kb-{uuid.uuid4().hex[:12]}"


# Example USER-scoped articles (slug -> doc). Category IDs must exist in kb_categories
# (ensure_default_categories in knowledge_base.py creates them on first API use).
EXAMPLE_ARTICLES = [
    {
        "slug": "uploading-evidence",
        "title": "How to Upload a Gas Safety Certificate and Other Evidence",
        "category_id": "documents-uploads",
        "excerpt": "Learn how to upload gas safety certificates and other compliance evidence to your property records.",
        "content": """## Uploading evidence

1. Go to **Properties** and open the property you want to update.
2. Find the **Documents** or **Evidence** section for that property.
3. Click **Add document** or **Upload**.
4. Choose the document type (e.g. Gas Safety Certificate, EICR).
5. Select the file from your device and add any required dates or reference numbers.
6. Submit. The document will be stored against the property and used for compliance scoring.

If a document type is missing, contact your administrator. Evidence is used to calculate your compliance score and reminder dates.""",
        "tags": ["evidence", "upload", "gas safety", "certificates", "documents"],
    },
    {
        "slug": "adding-a-property",
        "title": "How to Add a Property",
        "category_id": "adding-properties",
        "excerpt": "Step-by-step guide to adding a new property to your portfolio.",
        "content": """## Adding a property

1. Go to **Properties** in the main menu.
2. Click **Add property** (or similar).
3. Enter the property address and any required details (e.g. type, number of units).
4. Save. The property will appear in your portfolio.
5. You can then add requirements, documents, and compliance evidence to the property.

Properties are the basis for compliance tracking and reminders.""",
        "tags": ["property", "add", "portfolio", "getting started"],
    },
    {
        "slug": "compliance-score-explained",
        "title": "Understanding Your Compliance Score",
        "category_id": "compliance-score",
        "excerpt": "What the compliance score means and how it is calculated.",
        "content": """## Compliance score explained

Your **compliance score** reflects how up to date your properties are with required evidence and checks.

- Evidence (e.g. gas safety, EICR) that is valid and in date improves your score.
- Missing or expired evidence lowers your score.
- The score may be shown as a percentage or level (e.g. Good, Attention needed).

Use the Dashboard and property-level views to see which items need action. Keeping evidence up to date keeps your score healthy.""",
        "tags": ["compliance", "score", "dashboard", "evidence"],
    },
    {
        "slug": "reminders-and-alerts",
        "title": "How Reminder Alerts Work",
        "category_id": "reminders",
        "excerpt": "How the system sends reminders for upcoming or overdue compliance items.",
        "content": """## Reminders and alerts

The platform sends **reminders** when compliance items are coming due or overdue.

- You may receive email (and optionally SMS) reminders for items linked to your properties.
- Reminders are typically sent in advance of expiry and again after a due date if not updated.
- Check your **Dashboard** and **Properties** to see what is due and take action (e.g. renew or upload evidence).

If you are not receiving reminders, check your notification settings and email address.""",
        "tags": ["reminders", "alerts", "notifications", "compliance"],
    },
]


async def seed_kb_articles():
    await database.connect()
    db = database.get_db()
    if db is None:
        print("ERROR: Database not connected")
        return

    now = datetime.now(timezone.utc).isoformat()
    created = 0
    skipped = 0

    for item in EXAMPLE_ARTICLES:
        slug = item["slug"]
        existing = await db[ARTICLES_COLLECTION].find_one({"slug": slug})
        if existing:
            print(f"  Skip (exists): {slug}")
            skipped += 1
            continue

        article_id = generate_article_id()
        doc = {
            "article_id": article_id,
            "title": item["title"],
            "slug": slug,
            "category_id": item["category_id"],
            "excerpt": item["excerpt"],
            "content": item["content"],
            "tags": item.get("tags", []),
            "status": "published",
            "audience": "USER",
            "version": "1.0",
            "summary": item["excerpt"][:500],
            "meta_title": item["title"],
            "meta_description": item["excerpt"],
            "view_count": 0,
            "is_active": True,
            "product_module": None,
            "related_feature_flags": [],
            "article_type": None,
            "release_version": None,
            "release_date": None,
            "changes": [],
            "affected_modules": [],
            "created_at": now,
            "created_by": "seed_kb_articles",
            "updated_at": now,
            "updated_by": "seed_kb_articles",
            "published_at": now,
        }
        await db[ARTICLES_COLLECTION].insert_one(doc)
        print(f"  Created: {slug} ({article_id})")
        created += 1

    print(f"\nDone. Created: {created}, Skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(seed_kb_articles())
