"""
E1a preflight: fixture classification + authority baseline (read-only).

  python -m scripts.e1a_preflight_capture --client-id CID --property-id PID
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

from scripts.c2_snapshot import unrelated_fingerprints, select_control_entity  # noqa: E402
from scripts.e1_snapshot import authority_snapshot_bundle  # noqa: E402
from scripts.e1a_snapshot import (  # noqa: E402
    FIXTURE_INCAPABLE,
    resolve_e1a_fixture,
)

CID_DEFAULT = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID_DEFAULT = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="E1a preflight (fixture gate + baseline)")
    p.add_argument("--client-id", default=CID_DEFAULT)
    p.add_argument("--property-id", default=PID_DEFAULT)
    p.add_argument("--requirement-id", default=None)
    p.add_argument("--document-id", default=None)
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

    resolved = await resolve_e1a_fixture(
        db,
        cid=cid,
        pid=pid,
        requirement_id=args.requirement_id,
        document_id=args.document_id,
    )
    classification = resolved["classification"]
    rid = resolved["requirement_id"]
    doc_id = resolved["document_id"]

    if args.control_client_id and args.control_property_id:
        ctrl_cid, ctrl_pid = args.control_client_id.strip(), args.control_property_id.strip()
        reason = "explicit_cli"
    else:
        ctrl_cid, ctrl_pid, reason = await select_control_entity(db, pilot_cid=cid, pilot_pid=pid)

    authority_before = await authority_snapshot_bundle(
        db, cid=cid, pid=pid, requirement_id=rid, document_id=doc_id or None
    )
    authority_before["captured_at_utc"] = run_at

    fixture_payload: Dict[str, Any] = {
        "captured_at_utc": run_at,
        "micro_unit": "E1a",
        "pilot_client_id": cid,
        "pilot_property_id": pid,
        "control_client_id": ctrl_cid,
        "control_property_id": ctrl_pid,
        "control_selection_reason": reason,
        **classification,
        "staging_fixture_candidates": resolved.get("staging_fixture_candidates") or [],
        "prior_e1_run_reference": "e1_verification_report_6fd5ac4c_d35a58ae.json (preserved)",
    }
    ctrl_fp = await unrelated_fingerprints(db, cid=ctrl_cid, pid=ctrl_pid)
    fixture_payload["control_fingerprints"] = ctrl_fp

    control_payload = {
        "captured_at_utc": run_at,
        "micro_unit": "E1a",
        "pilot_client_id": cid,
        "pilot_property_id": pid,
        "control_client_id": ctrl_cid,
        "control_property_id": ctrl_pid,
        "selection_reason": reason,
        "pilot_requirement_id": rid,
        "pilot_document_id": doc_id,
        "fixture_classification": classification["fixture_classification"],
        "proof_eligible": classification["proof_eligible"],
    }
    control_payload["control_fingerprints"] = ctrl_fp

    _write(out_dir / f"e1a_fixture_classification_{slug}.json", fixture_payload)
    _write(out_dir / f"e1a_authority_before_{slug}.json", authority_before)
    _write(out_dir / f"e1a_control_selection_{slug}.json", control_payload)

    exit_code = 0 if classification["fixture_classification"] != FIXTURE_INCAPABLE else 2
    print(
        json.dumps(
            {
                "fixture_classification": classification["fixture_classification"],
                "proof_eligible": classification["proof_eligible"],
                "fail_fast_reasons": classification["fail_fast_reasons"],
                "fixture_classification_artifact": f"e1a_fixture_classification_{slug}.json",
                "authority_before": f"e1a_authority_before_{slug}.json",
                "staging_candidate_count": len(fixture_payload["staging_fixture_candidates"]),
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
