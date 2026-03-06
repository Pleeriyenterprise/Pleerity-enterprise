"""
One-time migration: set default_jurisdiction, enabled_jurisdictions, and onboarding_checklist
for existing clients (Operations & Compliance / Senior Product Engineer spec).

- default_jurisdiction: "Scotland"
- enabled_jurisdictions: ["Scotland", "England", "Wales", "Northern Ireland"]
- onboarding_checklist: for clients with >= 1 property, mark "add_properties" complete and set completed_at

Run from backend dir: python -m scripts.migrate_ops_compliance_client_defaults
Uses MONGO_URL and DB_NAME from env (or .env).
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent so we can import database
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

UK_JURISDICTIONS = ["Scotland", "England", "Wales", "Northern Ireland"]


async def run():
    from database import database
    await database.connect()
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()

    clients = await db.clients.find({}, {"_id": 0, "client_id": 1}).to_list(100_000)
    updated_jurisdiction = 0
    updated_checklist = 0

    for c in clients:
        client_id = c["client_id"]
        updates = {}

        # Set jurisdiction defaults if missing
        doc = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "default_jurisdiction": 1, "enabled_jurisdictions": 1, "onboarding_checklist": 1},
        )
        if not doc.get("default_jurisdiction"):
            updates["default_jurisdiction"] = "Scotland"
        if not doc.get("enabled_jurisdictions"):
            updates["enabled_jurisdictions"] = UK_JURISDICTIONS.copy()

        if updates:
            await db.clients.update_one(
                {"client_id": client_id},
                {"$set": updates},
            )
            updated_jurisdiction += 1

        # Checklist: if client has >= 1 property, mark add_properties complete
        if doc.get("onboarding_checklist"):
            continue
        prop_count = await db.properties.count_documents({"client_id": client_id})
        if prop_count >= 1:
            items = [{"id": "add_properties", "completed_at": now}]
            await db.clients.update_one(
                {"client_id": client_id},
                {
                    "$set": {
                        "onboarding_checklist.items": items,
                        "onboarding_checklist.updated_at": now,
                    }
                },
            )
            updated_checklist += 1

    await database.close()
    print(f"Migration done. Clients updated (jurisdiction): {updated_jurisdiction}. Clients with checklist backfill: {updated_checklist}.")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    asyncio.run(run())
