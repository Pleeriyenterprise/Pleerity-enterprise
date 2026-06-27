"""
Operational Evidence Platform — historical backfill from authoritative sources.

Read-only on source collections. Emits with reduced confidence and metadata.backfill=true.
Skips rows that already have a matching evidence index entry.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from database import database

from services.operational_evidence.constants import (
    CATEGORY_COMPLIANCE,
    CATEGORY_INCIDENT,
    CATEGORY_NOTIFICATION,
    CATEGORY_RISK,
    CATEGORY_SCHEDULER,
    COLLECTION_EVENTS,
    CONFIDENCE_INDIRECT,
    EVT_INCIDENT_OPENED,
    EVT_JOB_RUN_COMPLETED,
    EVT_JOB_RUN_DEGRADED,
    EVT_JOB_RUN_FAILED,
    EVT_JOB_RUN_STARTED,
    EVT_NOTIFICATION_FAILED,
    EVT_NOTIFICATION_SENT,
    EVT_COMPLIANCE_SCORE_CHANGED,
    IMPACT_NONE,
    IMPACT_OPERATIONAL_ONLY,
    IMPACT_PROPERTY,
)
from services.operational_evidence.emit_service import emit_operational_evidence

logger = logging.getLogger(__name__)

BACKFILL_SOURCES = frozenset({"job_runs", "incidents", "message_logs", "score_ledger_events"})


async def _already_indexed(source_collection: str, source_id: str, event_type: str) -> bool:
    db = database.get_db()
    existing = await db[COLLECTION_EVENTS].find_one(
        {
            "evidence.source_collection": source_collection,
            "evidence.source_id": str(source_id),
            "event_type": event_type,
        },
        {"_id": 1},
    )
    return existing is not None


async def _emit_backfill(**kwargs: Any) -> bool:
    kwargs.setdefault("confidence", CONFIDENCE_INDIRECT)
    kwargs.setdefault("confidence_reason", "Historical backfill from authoritative source")
    meta = dict(kwargs.get("metadata") or {})
    meta["backfill"] = True
    kwargs["metadata"] = meta
    event_id = await emit_operational_evidence(**kwargs)
    return event_id is not None


async def backfill_job_runs(*, since_iso: str, limit: int = 500) -> Dict[str, int]:
    db = database.get_db()
    stats = {"scanned": 0, "emitted": 0, "skipped": 0}
    cursor = db.job_runs.find({"created_at": {"$gte": since_iso}}).sort("created_at", 1).limit(limit)
    rows = await cursor.to_list(limit)
    for run in rows:
        stats["scanned"] += 1
        run_id = str(run["_id"])
        job_name = run.get("job_name") or "unknown"
        status = run.get("status") or "unknown"
        corr = run.get("correlation_id")
        started = run.get("started_at") or run.get("created_at")

        if status == "running":
            evt = EVT_JOB_RUN_STARTED
            emit_status = "started"
        elif status == "failed":
            evt = EVT_JOB_RUN_FAILED
            emit_status = "failed"
        elif status == "degraded":
            evt = EVT_JOB_RUN_DEGRADED
            emit_status = "degraded"
        else:
            evt = EVT_JOB_RUN_COMPLETED
            emit_status = status if status in ("success", "degraded", "failed") else "success"

        if await _already_indexed("job_runs", run_id, evt):
            stats["skipped"] += 1
            continue

        ok = await _emit_backfill(
            category=CATEGORY_SCHEDULER,
            event_type=evt,
            severity="info" if emit_status == "success" else "warning",
            status=emit_status,
            summary=f"[backfill] Job {job_name} {emit_status}",
            source_service="backfill_service",
            source_component="backfill_job_runs",
            occurred_at=started,
            duration_ms=run.get("duration_ms"),
            correlation_overrides={"correlation_id": corr, "job_run_id": run_id},
            customer_impact={
                "classification": IMPACT_NONE,
                "scope": "none",
                "affected_count": 0,
                "summary": "Historical job run",
            },
            evidence={
                "source_collection": "job_runs",
                "source_id": run_id,
                "deep_link": f"/admin/automation?job_run_id={run_id}",
            },
            metadata={"job_name": job_name},
        )
        if ok:
            stats["emitted"] += 1
        else:
            stats["skipped"] += 1
    return stats


async def backfill_incidents(*, since_iso: str, limit: int = 200) -> Dict[str, int]:
    db = database.get_db()
    stats = {"scanned": 0, "emitted": 0, "skipped": 0}
    rows = await db.incidents.find({"created_at": {"$gte": since_iso}}).sort("created_at", 1).limit(limit).to_list(limit)
    for inc in rows:
        stats["scanned"] += 1
        inc_id = str(inc["_id"])
        if await _already_indexed("incidents", inc_id, EVT_INCIDENT_OPENED):
            stats["skipped"] += 1
            continue
        ok = await _emit_backfill(
            category=CATEGORY_INCIDENT,
            event_type=EVT_INCIDENT_OPENED,
            severity="warning",
            status=inc.get("status") or "open",
            summary=f"[backfill] {inc.get('title') or 'Incident'}",
            source_service="backfill_service",
            source_component="backfill_incidents",
            occurred_at=inc.get("created_at"),
            correlation_overrides={
                "incident_id": inc_id,
                "job_run_id": inc.get("related_job_run_id"),
            },
            customer_impact={
                "classification": IMPACT_OPERATIONAL_ONLY,
                "scope": "platform",
                "affected_count": 0,
                "summary": "Historical incident",
            },
            evidence={
                "source_collection": "incidents",
                "source_id": inc_id,
                "deep_link": f"/admin/incidents?highlight={inc_id}",
            },
            metadata={"severity": inc.get("severity"), "related_job_name": inc.get("related_job_name")},
        )
        if ok:
            stats["emitted"] += 1
        else:
            stats["skipped"] += 1
    return stats


async def backfill_message_logs(*, since_iso: str, limit: int = 500) -> Dict[str, int]:
    db = database.get_db()
    stats = {"scanned": 0, "emitted": 0, "skipped": 0}
    rows = (
        await db.message_logs.find({"created_at": {"$gte": since_iso}})
        .sort("created_at", 1)
        .limit(limit)
        .to_list(limit)
    )
    for msg in rows:
        stats["scanned"] += 1
        mid = msg.get("message_id") or str(msg.get("_id", ""))
        st = (msg.get("status") or "").upper()
        if st in ("SENT", "DELIVERED", "PROVIDER_ACCEPTED"):
            evt = EVT_NOTIFICATION_SENT
            emit_st = "success"
        elif st == "FAILED":
            evt = EVT_NOTIFICATION_FAILED
            emit_st = "failed"
        else:
            stats["skipped"] += 1
            continue
        if await _already_indexed("message_logs", mid, evt):
            stats["skipped"] += 1
            continue
        channel = msg.get("channel") or "EMAIL"
        ok = await _emit_backfill(
            category=CATEGORY_NOTIFICATION,
            event_type=evt,
            severity="info" if emit_st == "success" else "error",
            status=emit_st,
            summary=f"[backfill] Notification {msg.get('template_key') or 'message'} {emit_st}",
            source_service="backfill_service",
            source_component="backfill_message_logs",
            occurred_at=msg.get("created_at") or msg.get("sent_at"),
            correlation_overrides={"notification_id": mid, "client_id": msg.get("client_id")},
            customer_impact={
                "classification": IMPACT_OPERATIONAL_ONLY,
                "scope": "tenant" if msg.get("client_id") else "none",
                "affected_count": 1 if msg.get("client_id") else 0,
                "summary": "Historical notification",
            },
            evidence={
                "source_collection": "message_logs",
                "source_id": mid,
                "deep_link": f"/admin/ops/evidence-timeline?notification_id={mid}",
            },
            metadata={"template_key": msg.get("template_key"), "channel": channel},
        )
        if ok:
            stats["emitted"] += 1
        else:
            stats["skipped"] += 1
    return stats


async def backfill_score_ledger(*, since_iso: str, limit: int = 500) -> Dict[str, int]:
    db = database.get_db()
    stats = {"scanned": 0, "emitted": 0, "skipped": 0}
    rows = (
        await db.score_ledger_events.find({"created_at": {"$gte": since_iso}})
        .sort("created_at", 1)
        .limit(limit)
        .to_list(limit)
    )
    for row in rows:
        stats["scanned"] += 1
        lid = str(row["_id"])
        if await _already_indexed("score_ledger_events", lid, EVT_COMPLIANCE_SCORE_CHANGED):
            stats["skipped"] += 1
            continue
        client_id = row.get("client_id") or ""
        property_id = row.get("property_id") or ""
        ok = await _emit_backfill(
            category=CATEGORY_COMPLIANCE,
            event_type=EVT_COMPLIANCE_SCORE_CHANGED,
            severity="info",
            status="success",
            summary=f"[backfill] Score {row.get('before_score')} → {row.get('after_score')}",
            source_service="backfill_service",
            source_component="backfill_score_ledger",
            occurred_at=row.get("created_at"),
            correlation_overrides={
                "correlation_id": row.get("correlation_id"),
                "client_id": client_id,
                "property_id": property_id,
                "requirement_id": row.get("requirement_id"),
            },
            customer_impact={
                "classification": IMPACT_PROPERTY,
                "scope": "property",
                "affected_count": 1,
                "summary": "Historical score change",
            },
            evidence={
                "source_collection": "score_ledger_events",
                "source_id": lid,
                "deep_link": f"/admin/observability/score-events?client_id={client_id}&property_id={property_id}",
            },
            metadata={"delta": row.get("delta"), "trigger_type": row.get("trigger_type")},
        )
        if ok:
            stats["emitted"] += 1
        else:
            stats["skipped"] += 1
    return stats


async def run_operational_evidence_backfill(
    *,
    days: int = 7,
    limit_per_source: int = 500,
    sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run bounded historical backfill. Default: last 7 days, all sources."""
    since = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 90)))
    since_iso = since.isoformat()
    chosen = set(sources or BACKFILL_SOURCES) & BACKFILL_SOURCES
    result: Dict[str, Any] = {
        "since": since_iso,
        "days": days,
        "sources": sorted(chosen),
        "by_source": {},
        "totals": {"scanned": 0, "emitted": 0, "skipped": 0},
    }
    runners = {
        "job_runs": backfill_job_runs,
        "incidents": backfill_incidents,
        "message_logs": backfill_message_logs,
        "score_ledger_events": backfill_score_ledger,
    }
    for name in sorted(chosen):
        fn = runners[name]
        stats = await fn(since_iso=since_iso, limit=limit_per_source)
        result["by_source"][name] = stats
        for k in ("scanned", "emitted", "skipped"):
            result["totals"][k] += stats[k]
    logger.info("operational_evidence backfill complete: %s", result["totals"])
    return result
