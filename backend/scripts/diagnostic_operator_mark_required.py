"""
Post-MARK_REQUIRED (or post-operator) live diagnostic for one requirement on staging / non-prod.

Uses MONGO_URL + DB_NAME (see database.py). Read-only by default.

  python -m scripts.diagnostic_operator_mark_required --client-id CID --requirement-id RID

Checks:
  1) requirement effective_applicability_state (expected REQUIRED after MARK_REQUIRED)
  2) open compliance_gaps snapshots vs requirement read model
  3) HIUA: derive_hiua_signal_for_open_gap false for each open gap
  4) latest applicability_resolution_audit row for OPERATOR_MARK_REQUIRED (or NOT_REQUIRED / REVOKE)
  5) queue membership: pipeline UNKNOWN + source OPERATOR_OVERRIDE still lists row
  6) recent audit_logs: no COMPLIANCE_GAP_OPENED / COMPLIANCE_GAP_ISSUE_CREATED in a short window
     (heuristic; gap sync uses audit_lifecycle=False for operator path)

Does not execute MARK_REQUIRED unless you pass --apply (use only on disposable staging rows).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def _run(
    *,
    client_id: str,
    requirement_id: str,
    apply_mark_required: bool,
    json_out: bool,
) -> Dict[str, Any]:
    from database import database
    from services.applicability_effective_resolver import resolve_applicability_read_model
    from services.applicability_resolution_queue import build_queue_mongo_filter
    from services.hiua_operational_uncertainty import derive_hiua_signal_for_open_gap
    from services.applicability_operator_actions import MARK_REQUIRED, execute_applicability_operator_command

    await database.connect()
    db = database.get_db()
    cid, rid = str(client_id).strip(), str(requirement_id).strip()

    if apply_mark_required:
        await execute_applicability_operator_command(
            db,
            client_id=cid,
            requirement_id=rid,
            command=MARK_REQUIRED,
            resolution_reason_code="MANUAL_LEGAL_REVIEW",
            actor={"type": "service", "id": "diagnostic_operator_mark_required", "email": None},
            notes="scripts.diagnostic_operator_mark_required --apply",
        )

    req = await db.requirements.find_one(
        {"client_id": cid, "requirement_id": rid},
        {"_id": 0},
    )
    if not req:
        out = {"ok": False, "error": "requirement not found"}
        await database.close()
        return out

    read = resolve_applicability_read_model(req)
    gaps: List[Dict[str, Any]] = await db.compliance_gaps.find(
        {"client_id": cid, "requirement_id": rid, "status": "open"},
        {"_id": 0},
    ).to_list(500)

    gap_snapshots: List[Dict[str, Any]] = []
    hiua_flags: List[bool] = []
    for g in gaps:
        gap_snapshots.append(
            {
                "gap_key": g.get("gap_key"),
                "effective_applicability_state": g.get("effective_applicability_state"),
                "applicability_resolution_source": g.get("applicability_resolution_source"),
                "pipeline_applicability_state": g.get("pipeline_applicability_state"),
            }
        )
        hiua_flags.append(derive_hiua_signal_for_open_gap(g))

    since = datetime.now(timezone.utc) - timedelta(minutes=30)
    since_iso = since.isoformat()
    ar_audit = await db.applicability_resolution_audit.find(
        {"client_id": cid, "requirement_id": rid, "created_at": {"$gte": since}},
        {"_id": 0},
    ).sort("created_at", -1).limit(5).to_list(5)

    gap_lifecycle = await db.audit_logs.find(
        {
            "client_id": cid,
            "timestamp": {"$gte": since_iso},
            "action": {"$in": ["COMPLIANCE_GAP_OPENED", "COMPLIANCE_GAP_RESOLVED", "COMPLIANCE_GAP_ISSUE_CREATED"]},
            "$or": [
                {"metadata.requirement_id": rid},
                {"resource_id": rid},
            ],
        },
        {"_id": 0, "action": 1, "timestamp": 1, "metadata": 1, "resource_id": 1},
    ).limit(50).to_list(50)

    qflt = build_queue_mongo_filter(client_id=cid)
    qflt["requirement_id"] = rid
    in_queue = await db.requirements.count_documents(qflt) >= 1

    has_operator_mark_audit = any(str(e.get("event_type") or "") == "OPERATOR_MARK_REQUIRED" for e in ar_audit)

    checks = {
        "1_effective_applicability_REQUIRED": str(read.get("effective_applicability_state") or "").upper() == "REQUIRED",
        "2_gap_snapshots_align_with_effective": all(
            str(g.get("effective_applicability_state") or "").upper()
            == str(read["effective_applicability_state"] or "").upper()
            for g in gaps
        )
        if gaps
        else True,
        "3_hiua_false_for_all_open_gaps": not any(hiua_flags),
        "4_applicability_resolution_audit_has_operator_mark": has_operator_mark_audit,
        "5_queue_row_pipeline_unknown_operator_override": bool(in_queue)
        and str(read["pipeline_applicability_state"] or "").upper() == "UNKNOWN"
        and str(read["applicability_resolution_source"] or "").upper() == "OPERATOR_OVERRIDE",
        "6_no_gap_lifecycle_audit_for_requirement_in_window": len(gap_lifecycle) == 0,
    }

    out: Dict[str, Any] = {
        "ok": all(checks.values()),
        "client_id": cid,
        "requirement_id": rid,
        "apply_mark_required": apply_mark_required,
        "requirement_read_model": read,
        "open_gap_count": len(gaps),
        "gap_snapshots": gap_snapshots,
        "hiua_per_open_gap": hiua_flags,
        "applicability_resolution_audit_recent": ar_audit,
        "in_applicability_resolution_queue": in_queue,
        "gap_lifecycle_audit_hits_last_30m": gap_lifecycle,
        "checks": checks,
        "note": (
            "Check 6 is heuristic (audit_logs gap lifecycle). Operator gap sync uses audit_lifecycle=False; "
            "COMPLIANCE_GAP_* should not fire from that path. If other jobs wrote gap audits, hits may appear."
        ),
    }
    await database.close()
    if json_out:
        print(json.dumps(out, indent=2, default=str))
    else:
        print("--- diagnostic_operator_mark_required ---")
        for k, v in checks.items():
            print(f"{k}: {v}")
        print(f"read_model: {read}")
        print(f"open_gaps: {len(gaps)} hiua_any={any(hiua_flags)}")
        if ar_audit:
            print(f"latest_ar_audit event_type={ar_audit[0].get('event_type')}")
        if gap_lifecycle:
            print(f"WARNING gap_lifecycle_hits={len(gap_lifecycle)} sample={gap_lifecycle[0]}")
        print(f"overall_ok={out['ok']}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-id", required=True)
    ap.add_argument("--requirement-id", required=True)
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Execute MARK_REQUIRED before checks (staging only; mutates requirement + gaps + audit).",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    asyncio.run(
        _run(
            client_id=args.client_id,
            requirement_id=args.requirement_id,
            apply_mark_required=bool(args.apply),
            json_out=bool(args.json),
        )
    )


if __name__ == "__main__":
    main()
