"""
Governed purge of aged operational telemetry (not authoritative SoR).

Feature-flagged. Default dry behaviour when flag off.
Never targets protected collections.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from database import database

logger = logging.getLogger(__name__)

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
    }
)

# days retention → collection + timestamp field
DEFAULT_POLICIES = (
    ("job_runs", "created_at", 90),
    ("operational_evidence_events", "occurred_at", 90),
    ("operational_evidence_executions", "started_at", 90),
    ("message_logs", "created_at", 180),
    ("reminder_evaluation_log", "created_at", 90),
    ("workflow_nudge_audit", "created_at", 90),
    ("workflow_recovery_audit", "created_at", 90),
)


def retention_purge_enabled() -> bool:
    return (os.getenv("MONGO_OPERATIONAL_RETENTION_PURGE_ENABLED") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _cutoff_iso(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=max(1, days))).isoformat()


async def purge_aged_operational_telemetry(
    *,
    batch_limit: int = 2000,
    dry_run: bool | None = None,
) -> Dict[str, Any]:
    """
    Delete aged rows from operational collections per DEFAULT_POLICIES.
    dry_run defaults to True when purge flag is off; when flag on, dry_run=False unless forced.
    """
    db = database.get_db()
    if db is None:
        return {"ok": False, "reason": "database_unavailable"}

    if dry_run is None:
        dry_run = not retention_purge_enabled()

    results: List[Dict[str, Any]] = []
    for coll_name, ts_field, days in DEFAULT_POLICIES:
        if coll_name in PROTECTED:
            results.append({"collection": coll_name, "skipped": True, "reason": "protected"})
            continue
        cutoff = _cutoff_iso(days)
        filt = {ts_field: {"$lt": cutoff}}
        try:
            match = await db[coll_name].count_documents(filt)
        except Exception as exc:
            results.append({"collection": coll_name, "error": str(exc)[:160]})
            continue
        deleted = 0
        if not dry_run and match:
            # batch by _id
            remaining = match
            while remaining > 0:
                docs = (
                    await db[coll_name]
                    .find(filt, {"_id": 1})
                    .limit(batch_limit)
                    .to_list(batch_limit)
                )
                if not docs:
                    break
                res = await db[coll_name].delete_many({"_id": {"$in": [d["_id"] for d in docs]}})
                deleted += int(res.deleted_count or 0)
                remaining = await db[coll_name].count_documents(filt)
                if int(res.deleted_count or 0) == 0:
                    break
        results.append(
            {
                "collection": coll_name,
                "timestamp_field": ts_field,
                "retention_days": days,
                "cutoff": cutoff,
                "matched": match,
                "deleted": deleted,
                "dry_run": dry_run,
            }
        )

    logger.info(
        "operational retention purge dry_run=%s results=%s",
        dry_run,
        [(r.get("collection"), r.get("matched"), r.get("deleted")) for r in results],
    )
    return {
        "ok": True,
        "dry_run": dry_run,
        "enabled_flag": retention_purge_enabled(),
        "collections": results,
    }
