"""
Restore Services (AI & Automation, Market Research, Document Packs, Compliance Audits)

1. Seeds service_catalogue_v2 with all service definitions (idempotent).
2. Seeds CMS pages (hub, category, service pages) from the catalogue.

Run from backend dir: python scripts/restore_services.py
Requires: MONGO_URL, DB_NAME in env (or .env).
"""

import asyncio
import sys
from pathlib import Path

_backend_root = Path(__file__).resolve().parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))
if Path("/app/backend").exists() and "/app/backend" not in sys.path:
    sys.path.insert(0, "/app/backend")


async def main():
    from database import database
    import os

    if not os.environ.get("MONGO_URL"):
        print("Error: MONGO_URL (and DB_NAME) must be set. Use .env or export before running.")
        print("  Example: set MONGO_URL=mongodb://... && python scripts/restore_services.py")
        sys.exit(1)

    from services.service_definitions_v2 import seed_service_catalogue_v2
    from scripts.seed_cms_pages import seed_cms_pages

    print("=" * 60)
    print("Restore Services")
    print("=" * 60)

    await database.connect()

    print("\nStep 1: Seed service catalogue V2 (idempotent)...")
    try:
        result = await seed_service_catalogue_v2()
        print(f"   Catalogue: {result.get('created', 0)} created, {result.get('skipped', 0)} already existed.")
    except Exception as e:
        print(f"   Error: {e}")
        raise

    print("\nStep 2: Seed CMS pages (hub, categories, service pages)...")
    await seed_cms_pages()

    print("\nDone. Category pages and service pages are restored.")
    print("  /services          - Hub")
    print("  /services/ai-automation")
    print("  /services/market-research")
    print("  /services/document-packs")
    print("  /services/compliance-audits")


if __name__ == "__main__":
    asyncio.run(main())
