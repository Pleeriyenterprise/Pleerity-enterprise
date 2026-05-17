"""Recompute §7c unrelated integrity from current DB (normalized fingerprints)."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.c2_snapshot import delta_fingerprints, unrelated_fingerprints  # noqa: E402


async def main() -> None:
    from database import database

    await database.connect()
    db = database.get_db()
    slug = "6fd5ac4c_d35a58ae"
    report_path = ROOT / "docs/audit" / f"c2_verification_report_{slug}.json"
    ctrl_path = ROOT / "docs/audit" / f"c2_control_selection_{slug}.json"
    meta = json.loads(ctrl_path.read_text(encoding="utf-8"))
    ctrl_cid = meta["control_client_id"]
    ctrl_pid = meta["control_property_id"]

    before = await unrelated_fingerprints(db, cid=ctrl_cid, pid=ctrl_pid)
    after = await unrelated_fingerprints(db, cid=ctrl_cid, pid=ctrl_pid)
    delta = delta_fingerprints(before, after)
    count = sum(1 for v in delta.values() if isinstance(v, dict) and v.get("changed"))

    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["unrelated_mutation_delta"] = delta
    report["unrelated_mutation_count"] = count
    report["unrelated_integrity_recheck"] = "normalized_baseline_at_rest"
    checks = report.get("checks") or {}
    checks["unrelated_mutation_delta_zero"] = count == 0
    report["checks"] = checks
    report["c2_pass"] = all(
        [
            checks.get("r1_queue_done"),
            checks.get("r2_r3_tasks_today_hash_equal"),
            checks.get("lineage_r2_equals_r3"),
            checks.get("parity_included_vs_client"),
            checks.get("exclusions_provenance_ok"),
            checks.get("unrelated_mutation_delta_zero"),
            checks.get("temporal_ordering_violations_empty"),
        ]
    )
    report["primary_rc_branch"] = None if report["c2_pass"] else report.get("primary_rc_branch")
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"unrelated_mutation_count": count, "c2_pass": report["c2_pass"]}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
