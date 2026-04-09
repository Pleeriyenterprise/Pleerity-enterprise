"""
One-off migration: fix properties where compliance recalc historically wrote scoring buckets into properties.jurisdiction.

Safe actions:
- SCOTLAND / scotland → canonical portfolio label "Scotland" (1:1).
- ENGLAND_WALES (and variants) → set scoring_jurisdiction_bucket to ENGLAND_WALES and clear jurisdiction
  so account default / per-property correction applies (ambiguous: could have been England, Wales, or NI).

Production workflow (recommended)
--------------------------------
1. Count only (no writes) — use this to size the change before scheduling apply:

     python -m scripts.migrate_property_jurisdiction_legacy_buckets --count

2. Review samples:

     python -m scripts.migrate_property_jurisdiction_legacy_buckets --dry-run

3. Apply during a maintenance window or low-traffic period:

     python -m scripts.migrate_property_jurisdiction_legacy_buckets --apply

4. Re-run --count; both legacy counts should be 0.

MongoDB equivalents (mongosh) for ad-hoc checks without Python:

  // Scotland bucket stored as jurisdiction (case-insensitive exact token)
  db.properties.countDocuments({ jurisdiction: /^scotland$/i })

  // England & Wales bucket strings
  db.properties.countDocuments({
    $or: [
      { jurisdiction: /^england_wales$/i },
      { jurisdiction: /^england\\/wales$/i },
      { jurisdiction: /^england wales$/i },
      { jurisdiction: "ENGLAND_WALES" },
    ],
  })

Requires MONGODB_URI (or project env) as used by database.database.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Tuple

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate_property_jurisdiction_legacy_buckets")

SCOTLAND_QUERY: Dict[str, Any] = {
    "jurisdiction": {"$regex": r"^scotland$", "$options": "i"},
}

EW_QUERY: Dict[str, Any] = {
    "$or": [
        {"jurisdiction": {"$regex": r"^(england_wales|england/wales|england wales)$", "$options": "i"}},
        {"jurisdiction": "ENGLAND_WALES"},
    ],
}


async def _legacy_counts(coll) -> Tuple[int, int]:
    sc = await coll.count_documents(SCOTLAND_QUERY)
    ew = await coll.count_documents(EW_QUERY)
    return sc, ew


async def _fetch_legacy_docs(coll) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    scotland_docs = await coll.find(
        SCOTLAND_QUERY,
        {"_id": 1, "property_id": 1, "jurisdiction": 1, "client_id": 1},
    ).to_list(500_000)
    ew_docs = await coll.find(
        EW_QUERY,
        {"_id": 1, "property_id": 1, "jurisdiction": 1, "client_id": 1},
    ).to_list(500_000)
    return scotland_docs, ew_docs


async def run_count(coll, as_json: bool) -> None:
    sc, ew = await _legacy_counts(coll)
    total = sc + ew
    if as_json:
        print(
            json.dumps(
                {
                    "legacy_jurisdiction_scotland_bucket": sc,
                    "legacy_jurisdiction_england_wales_bucket": ew,
                    "legacy_jurisdiction_total": total,
                },
                indent=2,
            )
        )
        return
    logger.info("legacy_jurisdiction_migration_counts scotland_bucket=%s england_wales_bucket=%s total=%s", sc, ew, total)


async def run_dry_run(coll) -> None:
    sc, ew = await _legacy_counts(coll)
    logger.info("Found %s properties with legacy SCOTLAND bucket in jurisdiction", sc)
    logger.info("Found %s properties with legacy ENGLAND_WALES bucket in jurisdiction", ew)
    scotland_docs, ew_docs = await _fetch_legacy_docs(coll)
    for d in scotland_docs[:20]:
        logger.info(
            "  [dry-run] SCOTLAND→Scotland property_id=%s client_id=%s raw=%r",
            d.get("property_id"),
            d.get("client_id"),
            d.get("jurisdiction"),
        )
    if len(scotland_docs) > 20:
        logger.info("  ... and %s more (Scotland bucket)", len(scotland_docs) - 20)
    for d in ew_docs[:20]:
        logger.info(
            "  [dry-run] ENGLAND_WALES→clear jurisdiction, set bucket property_id=%s client_id=%s raw=%r",
            d.get("property_id"),
            d.get("client_id"),
            d.get("jurisdiction"),
        )
    if len(ew_docs) > 20:
        logger.info("  ... and %s more (ENGLAND_WALES bucket)", len(ew_docs) - 20)


async def run_apply(coll) -> None:
    sc_before, ew_before = await _legacy_counts(coll)
    logger.info("Before apply: scotland_bucket=%s england_wales_bucket=%s", sc_before, ew_before)
    scotland_docs, ew_docs = await _fetch_legacy_docs(coll)

    for d in scotland_docs:
        pid = d.get("property_id")
        if not pid:
            logger.warning("Skipping document without property_id: %s", d.get("_id"))
            continue
        await coll.update_one(
            {"property_id": pid},
            {"$set": {"jurisdiction": "Scotland", "scoring_jurisdiction_bucket": "SCOTLAND"}},
        )
        logger.info("Updated property_id=%s: jurisdiction=Scotland, scoring_jurisdiction_bucket=SCOTLAND", pid)

    for d in ew_docs:
        pid = d.get("property_id")
        if not pid:
            logger.warning("Skipping document without property_id: %s", d.get("_id"))
            continue
        await coll.update_one(
            {"property_id": pid},
            {
                "$set": {"scoring_jurisdiction_bucket": "ENGLAND_WALES"},
                "$unset": {"jurisdiction": ""},
            },
        )
        logger.info(
            "Updated property_id=%s: unset jurisdiction (ambiguous legacy), scoring_jurisdiction_bucket=ENGLAND_WALES",
            pid,
        )

    sc_after, ew_after = await _legacy_counts(coll)
    logger.info("After apply: scotland_bucket=%s england_wales_bucket=%s (expect 0, 0)", sc_after, ew_after)


async def run(mode: Literal["count", "dry_run", "apply"], as_json: bool) -> None:
    from database import database

    db = database.get_db()
    coll = db.properties

    if mode == "count":
        await run_count(coll, as_json=as_json)
    elif mode == "dry_run":
        await run_dry_run(coll)
    else:
        await run_apply(coll)


def main() -> None:
    p = argparse.ArgumentParser(description="Migrate legacy scoring-bucket values out of properties.jurisdiction")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--count", action="store_true", help="Print legacy row counts only (use first in production)")
    g.add_argument("--dry-run", action="store_true", help="Counts + sample property rows (no writes)")
    g.add_argument("--apply", action="store_true", help="Perform updates; re-run --count after to verify zero rows")
    p.add_argument(
        "--json",
        action="store_true",
        help="With --count, print a single JSON object to stdout (for CI/monitoring)",
    )
    args = p.parse_args()
    if args.json and not args.count:
        p.error("--json is only valid with --count")
    mode = "count" if args.count else ("dry_run" if args.dry_run else "apply")
    asyncio.run(run(mode, as_json=args.json))


if __name__ == "__main__":
    main()
