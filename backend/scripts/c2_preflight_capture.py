"""
C2 preflight: convergence before + unrelated control fingerprints (read-only).

  python -m scripts.c2_preflight_capture \\
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

from scripts.c2_snapshot import (  # noqa: E402
    full_convergence_snapshot,
    select_control_entity,
    unrelated_fingerprints,
)

CID_DEFAULT = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID_DEFAULT = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="C2 preflight capture (read-only)")
    p.add_argument("--client-id", default=CID_DEFAULT)
    p.add_argument("--property-id", default=PID_DEFAULT)
    p.add_argument("--out-dir", default="docs/audit")
    p.add_argument("--slug-suffix", default="6fd5ac4c_d35a58ae")
    p.add_argument("--control-client-id", default=None)
    p.add_argument("--control-property-id", default=None)
    return p.parse_args()


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

    pilot_before = await full_convergence_snapshot(db, cid=cid, pid=pid)
    pilot_before["phase"] = "C2_convergence_before"
    pilot_before["captured_at_utc"] = run_at

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
    }

    meta = {
        "pilot_client_id": cid,
        "pilot_property_id": pid,
        "control_client_id": ctrl_cid,
        "control_property_id": ctrl_pid,
        "control_selection_reason": ctrl_reason,
    }

    (out_dir / f"c2_convergence_before_{slug}.json").write_text(
        json.dumps(pilot_before, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / f"c2_unrelated_surface_integrity_{slug}.json").write_text(
        json.dumps(unrelated_before, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / f"c2_control_selection_{slug}.json").write_text(
        json.dumps(meta, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps({"ok": True, "meta": meta}, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
