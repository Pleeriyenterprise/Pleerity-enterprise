"""
Apply domestic alarm registry unification to the active published singleton:

- Removes overlapping snapshot keys (including ``FIRE_DETECTION|DEFAULT``) via overlap correction.
- Merges ``SMOKE_HEAT_ALARMS|DEFAULT`` with unified client copy (title, CTA, why).

Default: dry-run. ``--apply`` persists (version++, history). Does not run coverage repair or legacy migration.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import database  # noqa: E402
from services.compliance_registry_admin_service import (  # noqa: E402
    default_draft_shell,
    merge_partial_draft,
    validate_registry_draft,
)
from services.compliance_registry_publish_service import (  # noqa: E402
    COLLECTION_PUBLISHED,
    SINGLETON_KEY,
    append_published_history_record,
)
from services.published_registry_coverage_patch_specs import (  # noqa: E402
    SMOKE_HEAT_ALARMS_UNIFIED_CLIENT_PATCH,
    _RUNTIME_SANITY_PATCH,
)
from services.registry_overlap_correction import apply_registry_overlap_correction  # noqa: E402


def _utc_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _merge_smoke_heat_default(entries: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(entries)
    key = "SMOKE_HEAT_ALARMS|DEFAULT"
    prev = out.get(key)
    if not isinstance(prev, dict) or not prev:
        shell = default_draft_shell(canonical_code="SMOKE_HEAT_ALARMS", scope_key="DEFAULT")
        shell.pop("entry_id", None)
        shell.pop("status", None)
        prev = shell
    merged = merge_partial_draft(prev, _RUNTIME_SANITY_PATCH)
    merged = merge_partial_draft(merged, SMOKE_HEAT_ALARMS_UNIFIED_CLIENT_PATCH)
    out[key] = merged
    return out


async def _run(*, apply: bool) -> int:
    await database.connect()
    try:
        db = database.get_db()
        prev = await db[COLLECTION_PUBLISHED].find_one({"singleton_key": SINGLETON_KEY}, {"_id": 0})
        prev_entries = (prev or {}).get("entries") if isinstance((prev or {}).get("entries"), dict) else {}
        overlapped, overlap_log = apply_registry_overlap_correction(prev_entries)
        merged = _merge_smoke_heat_default(overlapped)

        validation_errors: Dict[str, List[str]] = {}
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
            "overlap_changelog": overlap_log,
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
        actor = {"portal_user_id": "apply_alarm_registry_unification", "email": "system@local"}
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
                    "last_activation_kind": "alarm_registry_unification",
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
            activation_kind="alarm_registry_unification",
            reverted_from_published_line_version=None,
        )
        print(json.dumps({"applied": True, "published_version": next_v}, indent=2))
        return 0
    finally:
        await database.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="Persist merged entries to Mongo.")
    args = p.parse_args()
    raise SystemExit(asyncio.run(_run(apply=bool(args.apply))))


if __name__ == "__main__":
    main()
