"""
F1 preflight: notification baseline + fixture classification + control selection (read-only).

  python -m scripts.f1_preflight_capture --client-id CID --property-id PID --out-dir docs/audit
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

from scripts.c2_snapshot import select_control_entity, unrelated_fingerprints  # noqa: E402
from scripts.f1_snapshot import (  # noqa: E402
    FIXTURE_NOTIFICATION_INCAPABLE,
    activation_blocked_snapshot,
    load_notification_governance_inventory,
    resolve_f1_fixture,
    unrelated_message_logs_fingerprints,
)

CID_DEFAULT = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID_DEFAULT = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CTRL_CID_DEFAULT = "04ceda9f-dd72-4b70-a6f5-809bef1b7b6a"
CTRL_PID_DEFAULT = "6d939c70-06ab-4dc8-8b36-204958d2cdb3"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="F1 preflight capture (read-only)")
    p.add_argument("--client-id", default=CID_DEFAULT)
    p.add_argument("--property-id", default=PID_DEFAULT)
    p.add_argument("--out-dir", default="docs/audit")
    p.add_argument("--slug-suffix", default="6fd5ac4c_d35a58ae")
    p.add_argument("--control-client-id", default=CTRL_CID_DEFAULT)
    p.add_argument("--control-property-id", default=CTRL_PID_DEFAULT)
    return p.parse_args()


async def _notification_before(db, *, cid: str, pid: str) -> Dict[str, Any]:
    pilot_logs = await unrelated_message_logs_fingerprints(db, cid=cid)
    property_scoped = await db.message_logs.count_documents(
        {"client_id": cid, "metadata.property_id": pid}
    )
    return {
        "client_id": cid,
        "property_id": pid,
        "pilot_message_logs": pilot_logs,
        "property_scoped_message_log_count": property_scoped,
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

    resolved = await resolve_f1_fixture(db, cid=cid, pid=pid)
    ctrl_cid = args.control_client_id.strip()
    ctrl_pid = args.control_property_id.strip()
    ctrl_reason = "explicit_cli_default"

    if not args.control_client_id or not args.control_property_id:
        ctrl_cid, ctrl_pid, ctrl_reason = await select_control_entity(db, pilot_cid=cid, pilot_pid=pid)

    notification_before = await _notification_before(db, cid=cid, pid=pid)
    notification_before["captured_at_utc"] = run_at

    ctrl_msg = await unrelated_message_logs_fingerprints(db, cid=ctrl_cid)
    ctrl_surface = await unrelated_fingerprints(db, cid=ctrl_cid, pid=ctrl_pid)

    fixture_payload: Dict[str, Any] = {
        "captured_at_utc": run_at,
        "micro_unit": "F1",
        "harness_phase": "IN_PROGRESS",
        "pilot_client_id": cid,
        "pilot_property_id": pid,
        "control_client_id": ctrl_cid,
        "control_property_id": ctrl_pid,
        "control_selection_reason": ctrl_reason,
        **resolved,
        "activation_blocked": activation_blocked_snapshot(),
        "governance_inventory_policy": load_notification_governance_inventory().get("policy"),
        "upstream_precondition": {"E1": "VERIFIED", "e1b_authoritative": "e1b_verification_report_6fd5ac4c_d35a58ae.json"},
    }
    fixture_payload["control_message_logs_fingerprint"] = ctrl_msg

    control_payload = {
        "captured_at_utc": run_at,
        "micro_unit": "F1",
        "pilot_client_id": cid,
        "pilot_property_id": pid,
        "control_client_id": ctrl_cid,
        "control_property_id": ctrl_pid,
        "selection_reason": ctrl_reason,
        "fixture_classification": resolved["fixture_classification"],
        "proof_eligible": resolved["proof_eligible"],
        "control_fingerprints": ctrl_surface,
        "control_message_logs": ctrl_msg,
    }

    _write(out_dir / f"f1_fixture_classification_{slug}.json", fixture_payload)
    _write(out_dir / f"f1_notification_before_{slug}.json", notification_before)
    _write(out_dir / f"f1_control_selection_{slug}.json", control_payload)

    exit_code = 0 if resolved["fixture_classification"] != FIXTURE_NOTIFICATION_INCAPABLE else 2
    print(
        json.dumps(
            {
                "fixture_classification": resolved["fixture_classification"],
                "proof_eligible": resolved["proof_eligible"],
                "fail_fast_reasons": resolved["fail_fast_reasons"],
                "m1_probe_sample": resolved.get("m1_probe_sample"),
                "exit_code": exit_code,
            },
            indent=2,
        )
    )
    if exit_code:
        raise SystemExit(exit_code)


def _write(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
