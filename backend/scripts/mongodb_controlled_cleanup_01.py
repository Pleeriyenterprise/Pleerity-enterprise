"""
Controlled MongoDB cleanup for Atlas Flex storage remediation.

Default: dry-run only. Refuses pleerity_production.
Deletes require --execute-deletes YES_I_APPROVED_STAGING_PURGE
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

ALLOWED_DBS = frozenset({"pleerity_staging"})
REFUSED_DBS = frozenset({"pleerity_production"})
EXECUTE_TOKEN = "YES_I_APPROVED_STAGING_PURGE"

TIER1_COLLECTIONS = (
    "job_runs",
    "operational_evidence_events",
    "operational_evidence_executions",
)

TIER2_COLLECTIONS = (
    "message_logs",
    "workflow_nudge_audit",
    "workflow_recovery_audit",
    "reminder_evaluation_log",
)

PROTECTED = frozenset(
    {
        "audit_logs",
        "compliance_decisions",
        "compliance_decision_snapshots",
        "compliance_evidence_nodes",
        "compliance_evidence_edges",
        "requirements",
        "clients",
        "consent_events",
        "consent_state",
        "score_ledger_events",
        "users",
        "properties",
        "documents",
        "order_files.chunks",
        "order_files.files",
        "compliance_audit_packs.chunks",
        "compliance_audit_packs.files",
    }
)

TIMESTAMP_FIELDS = (
    "created_at",
    "occurred_at",
    "recorded_at",
    "started_at",
    "finished_at",
    "updated_at",
)

REASON = {
    "job_runs": "operational_telemetry_unbounded_no_ttl",
    "operational_evidence_events": "derived_oep_index_unbounded_retention",
    "operational_evidence_executions": "derived_execution_registry",
    "message_logs": "operational_delivery_log_age_based",
    "workflow_nudge_audit": "operational_workflow_audit_age_based",
    "workflow_recovery_audit": "operational_workflow_audit_age_based",
    "reminder_evaluation_log": "operational_reminder_log_age_based",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(uri: str, db_name: str) -> Tuple[MongoClient, Database]:
    if db_name in REFUSED_DBS:
        raise SystemExit(f"REFUSED: cleanup must never target {db_name}")
    if db_name not in ALLOWED_DBS:
        raise SystemExit(f"REFUSED: db {db_name!r} not in allowlist {sorted(ALLOWED_DBS)}")
    client = MongoClient(uri, serverSelectionTimeoutMS=20000)
    client.admin.command("ping")
    return client, client[db_name]


def _stats(coll: Collection) -> Dict[str, Any]:
    try:
        s = coll.database.command("collStats", coll.name)
    except Exception as exc:
        return {"error": str(exc)[:200]}
    return {
        "count": int(s.get("count") or 0),
        "size_bytes": int(s.get("size") or 0),
        "storage_size_bytes": int(s.get("storageSize") or 0),
        "total_index_size_bytes": int(s.get("totalIndexSize") or 0),
        "nindexes": int(s.get("nindexes") or 0),
    }


def _date_range(coll: Collection) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {"oldest": None, "newest": None, "field": None}
    for field in TIMESTAMP_FIELDS:
        try:
            oldest = coll.find_one({field: {"$exists": True}}, sort=[(field, 1)], projection={field: 1})
            newest = coll.find_one({field: {"$exists": True}}, sort=[(field, -1)], projection={field: 1})
        except Exception:
            continue
        if oldest and newest and oldest.get(field) is not None:
            out["oldest"] = str(oldest.get(field))
            out["newest"] = str(newest.get(field))
            out["field"] = field
            break
    return out


def _sample_ids(coll: Collection, n: int = 5) -> List[str]:
    ids: List[str] = []
    for doc in coll.find({}, {"_id": 1, "event_id": 1, "job_name": 1}).limit(n):
        if doc.get("event_id"):
            ids.append(str(doc["event_id"]))
        else:
            ids.append(str(doc.get("_id")))
    return ids


def _age_filter(days: Optional[int], ts_field: str) -> Dict[str, Any]:
    if not days or days <= 0:
        return {}
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    # ISO strings compare lexicographically for zero-padded UTC timestamps
    cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()
    return {ts_field: {"$lt": cutoff_iso}}


def report_collection(
    db: Database,
    name: str,
    *,
    tier: str,
    age_days: Optional[int] = None,
) -> Dict[str, Any]:
    if name in PROTECTED:
        return {
            "collection": name,
            "tier": tier,
            "protected": True,
            "would_delete": False,
            "reason": "protected_collection",
        }
    coll = db[name]
    stats = _stats(coll)
    dr = _date_range(coll)
    filt = _age_filter(age_days, dr.get("field") or "created_at") if age_days else {}
    match_count = coll.count_documents(filt) if filt else int(stats.get("count") or 0)
    # proportional reclaim estimate
    total = max(int(stats.get("count") or 0), 1)
    ratio = match_count / total
    size_b = int(stats.get("size_bytes") or 0)
    idx_b = int(stats.get("total_index_size_bytes") or 0)
    return {
        "collection": name,
        "tier": tier,
        "protected": False,
        "document_count": int(stats.get("count") or 0),
        "match_count": match_count,
        "filter": filt or {"_all": True},
        "age_days": age_days,
        "reclaim_estimate_bytes": int(size_b * ratio),
        "index_reclaim_estimate_bytes": int(idx_b * ratio),
        "oldest_timestamp": dr.get("oldest"),
        "newest_timestamp": dr.get("newest"),
        "timestamp_field": dr.get("field"),
        "sample_ids": _sample_ids(coll),
        "deletion_reason": REASON.get(name, "operational_telemetry"),
        "would_delete": match_count > 0,
        "stats": stats,
    }


def delete_batches(
    coll: Collection,
    filt: Dict[str, Any],
    *,
    batch_size: int,
    checkpoint_path: Path,
    label: str,
) -> Dict[str, Any]:
    deleted_total = 0
    batch_no = 0
    started = time.time()
    while True:
        batch_no += 1
        ids = [d["_id"] for d in coll.find(filt, {"_id": 1}).limit(batch_size)]
        if not ids:
            break
        t0 = time.time()
        res = coll.delete_many({"_id": {"$in": ids}})
        deleted = int(res.deleted_count or 0)
        deleted_total += deleted
        remaining = coll.count_documents(filt)
        cp = {
            "collection": coll.name,
            "label": label,
            "batch_number": batch_no,
            "deleted_this_batch": deleted,
            "deleted_total": deleted_total,
            "remaining_estimate": remaining,
            "elapsed_ms_batch": int((time.time() - t0) * 1000),
            "elapsed_ms_total": int((time.time() - started) * 1000),
            "updated_at": _now(),
        }
        checkpoint_path.write_text(json.dumps(cp, indent=2), encoding="utf-8")
        print(json.dumps({"checkpoint": cp}))
        if deleted == 0:
            break
    return {
        "collection": coll.name,
        "batches": batch_no,
        "deleted_total": deleted_total,
        "elapsed_ms": int((time.time() - started) * 1000),
    }


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Controlled MongoDB staging cleanup")
    p.add_argument("--environment", default="staging", choices=["staging"])
    p.add_argument("--db-name", default="pleerity_staging")
    p.add_argument("--tier", choices=["1", "2", "1+2"], default="1")
    p.add_argument("--tier2-age-days", type=int, default=30)
    p.add_argument("--batch-size", type=int, default=2000)
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    p.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    p.add_argument(
        "--execute-deletes",
        default="",
        help=f"Must equal {EXECUTE_TOKEN} to delete",
    )
    p.add_argument(
        "--output",
        default=str(ROOT / "docs" / "audit" / "mongodb_cleanup_execution_01.json"),
    )
    args = p.parse_args(argv)

    uri = os.environ.get("MONGO_URL") or os.environ.get("MONGO_URI")
    if not uri:
        print("MONGO_URL/MONGO_URI required", file=sys.stderr)
        return 2

    execute = (not args.dry_run) and args.execute_deletes == EXECUTE_TOKEN
    if not args.dry_run and args.execute_deletes != EXECUTE_TOKEN:
        print(
            f"REFUSED: --no-dry-run requires --execute-deletes {EXECUTE_TOKEN}",
            file=sys.stderr,
        )
        return 3

    client, db = _connect(uri, args.db_name)
    before_db = {
        "database": args.db_name,
        "ping_ok": True,
        "captured_at": _now(),
    }

    reports: List[Dict[str, Any]] = []
    if args.tier in ("1", "1+2"):
        for name in TIER1_COLLECTIONS:
            reports.append(report_collection(db, name, tier="1", age_days=None))
    if args.tier in ("2", "1+2"):
        for name in TIER2_COLLECTIONS:
            reports.append(
                report_collection(db, name, tier="2", age_days=args.tier2_age_days)
            )

    delete_results: List[Dict[str, Any]] = []
    if execute:
        cp_dir = ROOT / "docs" / "audit" / "mongodb_cleanup_checkpoints"
        cp_dir.mkdir(parents=True, exist_ok=True)
        for rep in reports:
            if rep.get("protected") or not rep.get("would_delete"):
                continue
            name = rep["collection"]
            filt = rep.get("filter") or {}
            if filt.get("_all"):
                filt = {}
            try:
                delete_results.append(
                    delete_batches(
                        db[name],
                        filt,
                        batch_size=max(100, min(args.batch_size, 5000)),
                        checkpoint_path=cp_dir / f"{name}.json",
                        label=f"tier{rep['tier']}",
                    )
                )
            except Exception as exc:
                delete_results.append(
                    {
                        "collection": name,
                        "aborted": True,
                        "error": str(exc)[:500],
                    }
                )
                break

    after_reports = []
    if execute:
        for rep in reports:
            name = rep["collection"]
            if name in PROTECTED:
                continue
            after_reports.append({"collection": name, "stats": _stats(db[name])})

    out = {
        "audit_id": "MONGODB-STORAGE-REMEDIATION-AND-LIFECYCLE-GOVERNANCE-01",
        "mode": "execute" if execute else "dry_run",
        "environment": args.environment,
        "database": args.db_name,
        "tier": args.tier,
        "generated_at": _now(),
        "before": before_db,
        "collections": reports,
        "delete_results": delete_results,
        "after": after_reports,
        "totals": {
            "reclaim_estimate_bytes": sum(
                int(r.get("reclaim_estimate_bytes") or 0) for r in reports
            ),
            "index_reclaim_estimate_bytes": sum(
                int(r.get("index_reclaim_estimate_bytes") or 0) for r in reports
            ),
            "deleted_total": sum(int(r.get("deleted_total") or 0) for r in delete_results),
        },
        "production_touched": False,
        "protected_blocklist": sorted(PROTECTED),
    }
    Path(args.output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"wrote": args.output, "mode": out["mode"], "totals": out["totals"]}, indent=2))
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
