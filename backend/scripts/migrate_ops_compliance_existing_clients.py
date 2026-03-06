"""
Migration: Add default_jurisdiction, enabled_jurisdictions, and onboarding_checklist
to existing clients (Operations & Compliance). Idempotent: skips clients that already have these set.

Run from backend dir: python -m scripts.migrate_ops_compliance_existing_clients
Requires: MONGO_URL, DB_NAME in env.
"""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend root so we can import database
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

UK_JURISDICTIONS = ["Scotland", "England", "Wales", "Northern Ireland"]


async def run():
    from database import database
    await database.connect()
    db = database.get_db()
    clients = await db.clients.find(
        {}, {"_id": 0, "client_id": 1, "default_jurisdiction": 1, "enabled_jurisdictions": 1, "onboarding_checklist": 1}
    ).to_list(10000)
    updated = 0
    now = datetime.now(timezone.utc).isoformat()
    for c in clients:
        client_id = c["client_id"]
        updates = {}
        if not c.get("default_jurisdiction"):
            updates["default_jurisdiction"] = "Scotland"
        if not c.get("enabled_jurisdictions"):
            updates["enabled_jurisdictions"] = UK_JURISDICTIONS.copy()
        if "onboarding_checklist" not in c or c.get("onboarding_checklist") is None:
            prop_count = await db.properties.count_documents({"client_id": client_id})
            items = [{"id": "add_properties", "completed_at": now if prop_count >= 1 else None}]
            updates["onboarding_checklist"] = {
                "items": items,
                "completed_at": now if prop_count >= 1 else None,
                "updated_at": now,
            }
        if updates:
            await db.clients.update_one({"client_id": client_id}, {"$set": updates})
            updated += 1
            print(f"Updated client_id={client_id}")
    print(f"Done. Updated {updated} of {len(clients)} clients.")
    await database.close()


if __name__ == "__main__":
    asyncio.run(run())
