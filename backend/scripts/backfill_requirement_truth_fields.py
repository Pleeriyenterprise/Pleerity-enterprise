"""
Backfill date_source, evidence_state, confidence_state on requirements collection.

Assumptions (idempotent — safe to re-run):
- Rows with expiry_source CONFIRMED → USER_PROVIDED + PARTIALLY_CONFIRMED unless a VERIFIED
  document exists for that requirement_id, in which case VERIFIED_DOCUMENT + VERIFIED.
- Rows with expiry_source EXTRACTED (and no verified doc) → USER_PROVIDED + PARTIALLY_CONFIRMED.
- All other rows (NONE/missing) → SYSTEM_ESTIMATED + ESTIMATED + evidence from documents.
- NOT_REQUIRED status rows: evidence/date truth set for consistency; UI excludes them from notices.

Run from backend dir: python -m scripts.backfill_requirement_truth_fields
Requires: MONGO_URL, DB_NAME (same as main app).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def run() -> None:
    from database import database
    from services.requirement_truth import (
        EVIDENCE_MISSING,
        evidence_state_from_document_statuses,
        infer_confidence_state,
        infer_date_source,
    )

    await database.connect()
    db = database.get_db()
    reqs = await db.requirements.find({}, {"_id": 0}).to_list(200_000)
    ids = [r["requirement_id"] for r in reqs if r.get("requirement_id")]
    evidence_map: dict[str, str] = {rid: EVIDENCE_MISSING for rid in ids}
    if ids:
        cursor = db.documents.aggregate(
            [
                {"$match": {"requirement_id": {"$in": ids}}},
                {"$group": {"_id": "$requirement_id", "statuses": {"$push": "$status"}}},
            ]
        )
        async for row in cursor:
            rid = row.get("_id")
            if not rid:
                continue
            evidence_map[str(rid)] = evidence_state_from_document_statuses(
                [str(s) for s in (row.get("statuses") or [])]
            )

    updated = 0
    for r in reqs:
        rid = r.get("requirement_id")
        if not rid:
            continue
        ev = evidence_map.get(rid, EVIDENCE_MISSING)
        ds = infer_date_source(r, ev)
        conf = infer_confidence_state(ds, ev)
        patch = {"date_source": ds, "evidence_state": ev, "confidence_state": conf}
        await db.requirements.update_one({"requirement_id": rid}, {"$set": patch})
        updated += 1

    print(f"Backfilled truth fields on {updated} requirement rows.")
    await database.close()


if __name__ == "__main__":
    asyncio.run(run())
