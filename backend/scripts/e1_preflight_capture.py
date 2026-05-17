"""
E1 preflight: authority baseline + control selection (read-only).

  python -m scripts.e1_preflight_capture \\
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

from scripts.c2_snapshot import unrelated_fingerprints  # noqa: E402
from scripts.e1_snapshot import (  # noqa: E402
    authority_snapshot_bundle,
    gather_document_requirement_context,
    select_control_entity,
)

CID_DEFAULT = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID_DEFAULT = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="E1 preflight capture (read-only)")
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

    ctx = await gather_document_requirement_context(db, cid=cid, pid=pid)
    rid = ctx["requirement_id"]
    doc_id = ctx.get("document_id")

    if args.control_client_id and args.control_property_id:
        ctrl_cid, ctrl_pid = args.control_client_id.strip(), args.control_property_id.strip()
        reason = "explicit_cli"
    else:
        ctrl_cid, ctrl_pid, reason = await select_control_entity(db, pilot_cid=cid, pilot_pid=pid)

    authority_before = await authority_snapshot_bundle(
        db, cid=cid, pid=pid, requirement_id=rid, document_id=doc_id
    )
    authority_before["captured_at_utc"] = run_at

    control_payload = {
        "captured_at_utc": run_at,
        "pilot_client_id": cid,
        "pilot_property_id": pid,
        "control_client_id": ctrl_cid,
        "control_property_id": ctrl_pid,
        "selection_reason": reason,
        "pilot_requirement_id": rid,
        "pilot_document_id": doc_id,
    }

    ctrl_fp = await unrelated_fingerprints(db, cid=ctrl_cid, pid=ctrl_pid)
    control_payload["control_fingerprints"] = ctrl_fp

    _write(out_dir / f"e1_authority_before_{slug}.json", authority_before)
    _write(out_dir / f"e1_control_selection_{slug}.json", control_payload)

    print(
        json.dumps(
            {
                "authority_before": f"e1_authority_before_{slug}.json",
                "control_selection": f"e1_control_selection_{slug}.json",
                "requirement_id": rid,
                "document_id": doc_id,
            },
            indent=2,
        )
    )


def _write(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
