"""
D1 preflight: fanout baseline + control selection (read-only).

  python -m scripts.d1_preflight_capture \\
    --client-id CID --property-id PID --out-dir docs/audit
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.d1_snapshot import (  # noqa: E402
    select_control_entity,
    unrelated_fingerprints,
)
from scripts.c2_snapshot import fp32  # noqa: E402

CID_DEFAULT = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID_DEFAULT = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="D1 preflight capture (read-only)")
    p.add_argument("--client-id", default=CID_DEFAULT)
    p.add_argument("--property-id", default=PID_DEFAULT)
    p.add_argument("--out-dir", default="docs/audit")
    p.add_argument("--slug-suffix", default="6fd5ac4c_d35a58ae")
    p.add_argument("--control-client-id", default=None)
    p.add_argument("--control-property-id", default=None)
    return p.parse_args()


async def _fanout_baseline(db, *, cid: str, pid: str) -> Dict[str, Any]:
    from services.workflow_runtime_activation_registry import resolve_requirement_state_transition_core_backbone_gate

    stable_corr = f"REQUIREMENTS_SYNC:{pid}"
    queue_rows = await db.compliance_recalc_queue.find(
        {"property_id": pid},
        {"_id": 0, "correlation_id": 1, "status": 1, "updated_at": 1},
    ).sort("updated_at", -1).limit(8).to_list(8)
    regen_pending = await db.risk_signal_regen_queue.count_documents({"property_id": pid, "status": "PENDING"})
    gate = resolve_requirement_state_transition_core_backbone_gate()
    return {
        "stable_correlation_id": stable_corr,
        "queue_recent": queue_rows,
        "risk_regen_pending": regen_pending,
        "rst_core_backbone_activation": {
            "permitted": gate.get("permitted"),
            "activation_reason": gate.get("activation_reason"),
            "activation_state": gate.get("activation_state"),
        },
        "fingerprint": fp32({"queue": queue_rows, "regen_pending": regen_pending, "gate": gate.get("permitted")}),
    }


async def main() -> None:
    from database import database

    await database.connect()
    args = _parse_args()
    cid = args.client_id.strip()
    pid = args.property_id.strip()
    slug = args.slug_suffix
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    db = database.get_db()
    run_at = datetime.now(timezone.utc).isoformat()

    if args.control_client_id and args.control_property_id:
        ctrl_cid = args.control_client_id.strip()
        ctrl_pid = args.control_property_id.strip()
        ctrl_reason = "cli_override"
    else:
        ctrl_cid, ctrl_pid, ctrl_reason = await select_control_entity(db, pilot_cid=cid, pilot_pid=pid)

    fanout_before = await _fanout_baseline(db, cid=cid, pid=pid)
    fanout_before["phase"] = "D1_fanout_before"
    fanout_before["captured_at_utc"] = run_at
    fanout_before["client_id"] = cid
    fanout_before["property_id"] = pid

    unrelated_before = {
        "captured_at_utc": run_at,
        "phase": "before",
        "pilot": {"client_id": cid, "property_id": pid},
        "control": {
            "client_id": ctrl_cid,
            "property_id": ctrl_pid,
            "selection_reason": ctrl_reason,
        },
        "control_fingerprints": await unrelated_fingerprints(db, cid=ctrl_cid, pid=ctrl_pid),
        "baseline_note": "run-start normalized fingerprints; compare at verification end only",
    }

    meta = {
        "pilot_client_id": cid,
        "pilot_property_id": pid,
        "control_client_id": ctrl_cid,
        "control_property_id": ctrl_pid,
        "control_selection_reason": ctrl_reason,
        "governed_mutations": ["D1-M1", "D1-M2 (once)"],
    }

    (out_dir / f"d1_fanout_before_{slug}.json").write_text(
        json.dumps(fanout_before, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / f"d1_unrelated_surface_integrity_{slug}.json").write_text(
        json.dumps(unrelated_before, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / f"d1_control_selection_{slug}.json").write_text(
        json.dumps(meta, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps({"ok": True, "meta": meta, "artifacts": {
        "fanout_before": str(out_dir / f"d1_fanout_before_{slug}.json"),
        "control_selection": str(out_dir / f"d1_control_selection_{slug}.json"),
    }}, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
