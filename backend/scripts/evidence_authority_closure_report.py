"""
Staging / ops closure report: mirror drift + backfill dry-run plan (no writes).

Run from backend with MONGO_URL and DB_NAME set (e.g. staging):

  python -m scripts.evidence_authority_closure_report
  python -m scripts.evidence_authority_closure_report --json

Notes:
- With --dry-run semantics only, drift_count_after equals drift_count_before (no DB mutations).
- After a real backfill (without --dry-run on backfill), re-run drift to obtain "after apply" numbers.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Align with tests/conftest defaults so local runs work without a .env (override for staging).
os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017/?serverSelectionTimeoutMS=5000")
os.environ.setdefault("DB_NAME", "compliance_vault_pro_test")


async def _run(*, json_out: bool) -> Dict[str, Any]:
    from database import database
    from scripts.backfill_evidence_authority import gather_backfill_plan
    from services.requirement_evidence_authority import count_mirror_drift_rows

    await database.connect()
    db = database.get_db()

    drift_before = await count_mirror_drift_rows(db)
    plan = await gather_backfill_plan(db, apply_writes=False)
    drift_after = await count_mirror_drift_rows(db)

    out: Dict[str, Any] = {
        "drift_count_before": drift_before,
        "drift_count_after": drift_after,
        "backfill_dry_run": {
            "documents_matched_unscoped": plan.get("documents_matched_unscoped"),
            "document_scope_plan": plan.get("document_scope_plan"),
            "documents_planned_unresolved": plan.get("document_unresolved_planned"),
            "requirements_to_sync_if_applied": plan.get("requirements_synced"),
        },
        "note": (
            "No writes performed. drift_count_after matches drift_count_before. "
            "Run `python -m scripts.backfill_evidence_authority` without --dry-run on staging, "
            "then `python -m scripts.detect_evidence_authority_drift --json` for post-apply drift."
        ),
    }

    await database.close()

    if json_out:
        print(json.dumps(out, indent=2))
    else:
        print("--- evidence_authority_closure_report ---")
        print(f"drift_count_before={drift_before}")
        print(f"drift_count_after={drift_after}")
        br = out["backfill_dry_run"]
        print(f"documents_matched_unscoped={br.get('documents_matched_unscoped')}")
        print(f"documents_planned_unresolved={br.get('documents_planned_unresolved')}")
        print(f"requirements_to_sync_if_applied={br.get('requirements_to_sync_if_applied')}")
        for k, v in sorted((br.get("document_scope_plan") or {}).items(), key=lambda x: -x[1]):
            print(f"  document_scope_plan[{k}]={v}")
        print(out["note"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    asyncio.run(_run(json_out=bool(args.json)))


if __name__ == "__main__":
    main()
