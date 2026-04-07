"""
Backfill requirements.jurisdiction from property.jurisdiction and client.default_jurisdiction.

Idempotent — safe to re-run. Uses portfolio_jurisdiction_label (same as provisioning).

Run from backend dir: python -m scripts.migrate_backfill_requirement_jurisdiction

Requires: MONGO_URL, DB_NAME (same as main app).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def run() -> None:
    from database import database
    from services.compliance_rules_registry import portfolio_jurisdiction_label

    await database.connect()
    db = database.get_db()

    query = {
        "$or": [
            {"jurisdiction": {"$exists": False}},
            {"jurisdiction": None},
            {"jurisdiction": ""},
        ]
    }
    cursor = db.requirements.find(
        query,
        {"_id": 0, "requirement_id": 1, "property_id": 1, "client_id": 1},
    )
    props_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
    clients_cache: Dict[str, Dict[str, Any]] = {}
    updated = 0
    skipped = 0

    async for r in cursor:
        rid = r.get("requirement_id")
        pid = r.get("property_id")
        cid = r.get("client_id")
        if not rid or not pid or not cid:
            skipped += 1
            continue
        key = (cid, pid)
        if key not in props_cache:
            props_cache[key] = (
                await db.properties.find_one(
                    {"client_id": cid, "property_id": pid},
                    {"_id": 0, "jurisdiction": 1},
                )
                or {}
            )
        if cid not in clients_cache:
            clients_cache[cid] = (
                await db.clients.find_one(
                    {"client_id": cid},
                    {"_id": 0, "default_jurisdiction": 1},
                )
                or {}
            )
        j = portfolio_jurisdiction_label(props_cache[key], clients_cache[cid])
        await db.requirements.update_one({"requirement_id": rid}, {"$set": {"jurisdiction": j}})
        updated += 1

    print(f"Backfilled jurisdiction on {updated} requirement rows ({skipped} skipped missing ids).")
    await database.close()


if __name__ == "__main__":
    asyncio.run(run())
