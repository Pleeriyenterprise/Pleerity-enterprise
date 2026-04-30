"""
Remove overlapping snapshot keys from the active published registry singleton.

Default: dry-run (print changelog). ``--apply`` persists (increments version, appends history).

Does not run coverage repair or legacy client-truth migration.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import database  # noqa: E402
from services.compliance_registry_admin_service import validate_registry_draft  # noqa: E402
from services.compliance_registry_publish_service import (  # noqa: E402
    COLLECTION_PUBLISHED,
    SINGLETON_KEY,
    append_published_history_record,
)
from services.registry_overlap_correction import (  # noqa: E402
    OVERLAP_SNAPSHOT_KEYS_TO_REMOVE,
    apply_registry_overlap_correction,
)


def _utc_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


async def _run(*, apply: bool) -> int:
    await database.connect()
    try:
        db = database.get_db()
        prev = await db[COLLECTION_PUBLISHED].find_one({"singleton_key": SINGLETON_KEY}, {"_id": 0})
        prev_entries = (prev or {}).get("entries") if isinstance((prev or {}).get("entries"), dict) else {}
        merged, changelog = apply_registry_overlap_correction(prev_entries)

        validation_errors: dict = {}
        for k, ent in merged.items():
            if not isinstance(ent, dict):
                validation_errors[k] = ["entry_not_a_dict"]
                continue
            doc = json.loads(json.dumps(ent))
            errs = validate_registry_draft(doc)
            if errs:
                validation_errors[k] = errs

        out = {
            "dry_run": not apply,
            "keys_removed": OVERLAP_SNAPSHOT_KEYS_TO_REMOVE,
            "changelog": changelog,
            "removed_found": [x["registry_key"] for x in changelog],
            "previous_version": (prev or {}).get("version"),
            "previous_entry_count": len(prev_entries),
            "merged_entry_count": len(merged),
            "validation_error_keys": sorted(validation_errors.keys()),
            "validation_errors": validation_errors,
        }
        print(json.dumps(out, indent=2, default=str))
        if validation_errors:
            return 2
        if not apply:
            return 0

        next_v = int((prev or {}).get("version") or 0) + 1
        now = _utc_iso()
        actor = {"portal_user_id": "apply_registry_overlap_correction", "email": "system@local"}
        await db[COLLECTION_PUBLISHED].update_one(
            {"singleton_key": SINGLETON_KEY},
            {
                "$set": {
                    "singleton_key": SINGLETON_KEY,
                    "version": next_v,
                    "entries": merged,
                    "updated_at": now,
                    "last_queue_id": None,
                    "last_published_by": actor,
                    "last_activation_kind": "overlap_correction",
                    "reverted_from_published_line_version": None,
                }
            },
            upsert=True,
        )
        await append_published_history_record(
            db,
            published_line_version=next_v,
            entries=merged,
            recorded_at=now,
            last_queue_id=None,
            activated_by=actor,
            activation_kind="overlap_correction",
            reverted_from_published_line_version=None,
        )
        print(json.dumps({"applied": True, "published_version": next_v}, indent=2))
        return 0
    finally:
        await database.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="Persist overlap-corrected entries to Mongo.")
    args = p.parse_args()
    raise SystemExit(asyncio.run(_run(apply=bool(args.apply))))


if __name__ == "__main__":
    main()
