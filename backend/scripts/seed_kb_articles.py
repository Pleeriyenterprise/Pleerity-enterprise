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
    {
        "slug": "command-centre-tasks-inbox",
        "title": "Tasks (Command Centre): Snooze, Dismiss, and Done",
        "category_id": "dashboard-guide",
        "excerpt": "What the Tasks inbox does when you snooze, dismiss, or mark an item done—and what it does not change elsewhere in Pleerity.",
        "content": """## What the Tasks inbox is for

**Tasks** (also labelled **Command Centre** on the page) brings overdue compliance items, expiring requirements, risk signals, work orders, approvals, and open issues into one place so you can see what needs attention and open the right screen.

## Snooze

**Snooze** hides a task from your open lists for the number of days you choose (for example 1 day or 7 days). When the snooze period ends, the task can appear again if the underlying issue still exists.

- Snooze only changes how the item appears in **your** inbox. It does not renew certificates, upload evidence, approve invoices, or close work orders.

## Dismiss

**Dismiss** hides a task from your open lists until you **Restore** it from the **Hidden (dismiss or done)** section.

- Dismiss does **not** fix compliance, cancel an obligation, or complete operational work. Use the primary action (for example **Open** or **Review approval**) to take real action on the underlying record.

## Done

**Done** marks the item as handled **in your inbox** and moves it to the hidden list until you restore it.

- **Done** does **not** mark a work order complete, approve an invoice, or resolve a maintenance issue in the Operations area. Use the linked work order, approval, or issue screens for those outcomes.

## Restore

Use **Restore** on items under **Snoozed** or **Hidden (dismiss or done)** to show them again in your open lists.

## Recently completed

Items under **Recently completed** may include real milestones (for example requirements satisfied or invoices paid) as well as inbox actions you took (dismiss or done). Check the labels to see which is which.

If something still needs doing in the real world, always follow the **Open** / **Review** actions and complete the work in the relevant property or Operations screen.""",
        "tags": ["tasks", "command centre", "inbox", "snooze", "dashboard", "getting organized"],
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
