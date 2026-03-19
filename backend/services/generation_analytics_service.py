"""
Aggregation for admin generation health dashboards (MongoDB).

Reads generation_runs and orders; does not expose raw provider traces in list endpoints.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import database
from services.admin_failure_summary import classify_generation_error, summarize_generation_failure

logger = logging.getLogger(__name__)

PROVIDERS = ("openai", "gemini")


def _window_start(hours: int) -> datetime:
    h = max(1, min(int(hours or 24), 24 * 14))
    return datetime.now(timezone.utc) - timedelta(hours=h)


def _run_provider_key(doc: Dict[str, Any]) -> Optional[str]:
    """Attribute a run to a provider for health stats."""
    if doc.get("status") == "COMPLETED":
        p = (doc.get("provider_used") or doc.get("provider") or "").strip().lower()
        return p if p in PROVIDERS else None
    # FAILED: attribute to primary attempted
    p = (doc.get("primary_provider_attempted") or "").strip().lower()
    if p in PROVIDERS:
        return p
    return None


def _classify_run_errors(doc: Dict[str, Any]) -> Dict[str, int]:
    """Single run contribution to error-type counters (per provider row)."""
    err = doc.get("error_message") or ""
    ft = doc.get("final_error_type")
    both = bool(doc.get("fallback_reason") == "both_llm_providers_failed" or "both" in (err.lower()))
    if ft:
        et = str(ft)
    else:
        et, _ = classify_generation_error(
            err,
            error_code=doc.get("error_code"),
            both_providers_exhausted=both,
        )
    keys = {
        "quota_errors": 0,
        "rate_limit_errors": 0,
        "timeout_errors": 0,
        "schema_errors": 0,
    }
    if et == "quota_exceeded":
        keys["quota_errors"] = 1
    elif et == "rate_limit":
        keys["rate_limit_errors"] = 1
    elif et == "timeout":
        keys["timeout_errors"] = 1
    elif et == "schema_error":
        keys["schema_errors"] = 1
    return keys


async def get_provider_health_summary(hours: int = 24) -> Dict[str, Any]:
    db = database.get_db()
    start = _window_start(hours)
    cursor = db.generation_runs.find(
        {"created_at": {"$gte": start}},
        {
            "_id": 0,
            "status": 1,
            "provider_used": 1,
            "provider": 1,
            "primary_provider_attempted": 1,
            "fallback_used": 1,
            "error_message": 1,
            "final_error_type": 1,
            "fallback_reason": 1,
            "started_at": 1,
            "completed_at": 1,
            "created_at": 1,
            "latency_ms": 1,
        },
    )
    runs = await cursor.to_list(length=50000)

    totals = {
        "total_runs": len(runs),
        "success_runs": 0,
        "failed_runs": 0,
        "retryable_failures": 0,
        "fallback_successes": 0,
    }

    per_provider: Dict[str, Dict[str, Any]] = {
        "openai": {
            "provider": "openai",
            "total_runs": 0,
            "successes": 0,
            "failures": 0,
            "latency_sum": 0,
            "latency_n": 0,
            "fallback_used_count": 0,
            "quota_errors": 0,
            "rate_limit_errors": 0,
            "timeout_errors": 0,
            "schema_errors": 0,
        },
        "gemini": {
            "provider": "gemini",
            "total_runs": 0,
            "successes": 0,
            "failures": 0,
            "latency_sum": 0,
            "latency_n": 0,
            "fallback_used_count": 0,
            "quota_errors": 0,
            "rate_limit_errors": 0,
            "timeout_errors": 0,
            "schema_errors": 0,
        },
    }

    for doc in runs:
        st = doc.get("status")
        if st == "COMPLETED":
            totals["success_runs"] += 1
            if doc.get("fallback_used"):
                totals["fallback_successes"] += 1
        elif st == "FAILED":
            totals["failed_runs"] += 1
            msg = doc.get("error_message")
            both = "both" in (msg or "").lower() or doc.get("fallback_reason") == "both_llm_providers_failed"
            _, ryb = classify_generation_error(msg, both_providers_exhausted=both)
            if ryb:
                totals["retryable_failures"] += 1

        pk = _run_provider_key(doc)
        if not pk or pk not in per_provider:
            continue
        bucket = per_provider[pk]
        bucket["total_runs"] += 1
        if st == "COMPLETED":
            bucket["successes"] += 1
            if doc.get("fallback_used"):
                bucket["fallback_used_count"] += 1
            lat = doc.get("latency_ms")
            if lat is None and doc.get("started_at") and doc.get("completed_at"):
                try:
                    sa = doc["started_at"]
                    ca = doc["completed_at"]
                    if isinstance(sa, datetime) and isinstance(ca, datetime):
                        lat = int((ca - sa).total_seconds() * 1000)
                except Exception:
                    lat = None
            if isinstance(lat, (int, float)) and lat >= 0:
                bucket["latency_sum"] += int(lat)
                bucket["latency_n"] += 1
        elif st == "FAILED":
            bucket["failures"] += 1
            ec = _classify_run_errors(doc)
            for k, v in ec.items():
                bucket[k] += v

    providers_out: List[Dict[str, Any]] = []
    for p in PROVIDERS:
        b = per_provider[p]
        tr = b["total_runs"]
        succ = b["successes"]
        providers_out.append(
            {
                "provider": p,
                "total_runs": tr,
                "success_rate": round(succ / tr, 4) if tr else 0.0,
                "avg_latency_ms": int(b["latency_sum"] / b["latency_n"]) if b["latency_n"] else 0,
                "fallback_used_count": b["fallback_used_count"],
                "quota_errors": b["quota_errors"],
                "rate_limit_errors": b["rate_limit_errors"],
                "timeout_errors": b["timeout_errors"],
                "schema_errors": b["schema_errors"],
            }
        )

    return {
        "window_hours": max(1, min(int(hours or 24), 24 * 14)),
        "totals": totals,
        "providers": providers_out,
    }


async def get_recent_generation_runs(
    limit: int = 50,
    status: Optional[str] = None,
    provider: Optional[str] = None,
    service_code: Optional[str] = None,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    lim = max(1, min(int(limit or 50), 200))
    conds: List[Dict[str, Any]] = []
    if status:
        conds.append({"status": status.upper()})
    if service_code:
        conds.append({"service_code": service_code})
    if provider:
        pv = provider.strip().lower()
        if pv in PROVIDERS:
            conds.append(
                {
                    "$or": [
                        {"provider_used": pv},
                        {"provider": pv},
                        {"primary_provider_attempted": pv},
                    ]
                }
            )
    q: Dict[str, Any] = {"$and": conds} if len(conds) > 1 else (conds[0] if conds else {})

    cursor = (
        db.generation_runs.find(q, {"_id": 0})
        .sort("created_at", -1)
        .limit(lim)
    )
    rows = await cursor.to_list(length=lim)
    out: List[Dict[str, Any]] = []
    for doc in rows:
        err_raw = doc.get("error_message")
        ft = doc.get("final_error_type")
        if not ft and err_raw:
            both = "both" in (err_raw or "").lower()
            ft, _ = classify_generation_error(err_raw, both_providers_exhausted=both)
        # Optional: fetch order_ref
        order_ref = None
        oid = doc.get("order_id")
        if oid:
            o = await db.orders.find_one({"order_id": oid}, {"_id": 0, "order_ref": 1, "reference": 1})
            if o:
                order_ref = o.get("order_ref") or o.get("reference")
        lat = doc.get("latency_ms")
        if lat is None and doc.get("started_at") and doc.get("completed_at"):
            try:
                sa, ca = doc["started_at"], doc["completed_at"]
                if isinstance(sa, datetime) and isinstance(ca, datetime):
                    lat = int((ca - sa).total_seconds() * 1000)
            except Exception:
                lat = None
        out.append(
            {
                "run_id": doc.get("run_id"),
                "order_id": oid,
                "order_ref": order_ref,
                "service_code": doc.get("service_code"),
                "doc_type": doc.get("doc_type"),
                "provider_preferred": doc.get("primary_provider_attempted"),
                "provider_used": doc.get("provider_used") or doc.get("provider"),
                "fallback_used": bool(doc.get("fallback_used")),
                "retry_count": int(doc.get("retry_count") or 0),
                "status": doc.get("status"),
                "final_error_type": ft,
                "created_at": doc.get("created_at"),
                "latency_ms": lat,
            }
        )
    return out


async def get_failed_orders_summary(limit: int = 50) -> List[Dict[str, Any]]:
    db = database.get_db()
    lim = max(1, min(int(limit or 50), 200))
    cursor = (
        db.orders.find(
            {"status": "FAILED"},
            {
                "_id": 0,
                "order_id": 1,
                "order_ref": 1,
                "reference": 1,
                "service_code": 1,
                "status": 1,
                "failure_reason": 1,
                "last_generation_error_type": 1,
                "last_generation_error_short": 1,
                "retryable_failure": 1,
                "automatic_retry_attempted": 1,
                "automatic_retry_pending": 1,
                "scheduled_automatic_retry_at": 1,
                "created_at": 1,
                "updated_at": 1,
            },
        )
        .sort("updated_at", -1)
        .limit(lim)
    )
    rows = await cursor.to_list(length=lim)
    out: List[Dict[str, Any]] = []
    for o in rows:
        raw = o.get("failure_reason") or ""
        et = o.get("last_generation_error_type")
        if not et:
            et, _ = classify_generation_error(raw)
        summary = summarize_generation_failure(str(et), raw)
        out.append(
            {
                "order_id": o.get("order_id"),
                "order_ref": o.get("order_ref") or o.get("reference"),
                "service_code": o.get("service_code"),
                "workflow_status": o.get("status"),
                "final_error_type": et,
                "final_error_message_short": o.get("last_generation_error_short") or summary["short_message"],
                "retryable": bool(o.get("retryable_failure", summary["retryable"])),
                "automatic_retry_attempted": bool(o.get("automatic_retry_attempted")),
                "automatic_retry_pending": bool(o.get("automatic_retry_pending")),
                "scheduled_automatic_retry_at": o.get("scheduled_automatic_retry_at"),
                "created_at": o.get("created_at"),
                "updated_at": o.get("updated_at"),
            }
        )
    return out


async def get_prompt_failure_patterns(limit: int = 40) -> List[Dict[str, Any]]:
    db = database.get_db()
    lim = max(1, min(int(limit or 40), 200))
    match = {"status": "FAILED"}
    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": {
                    "service_code": {"$ifNull": ["$service_code", ""]},
                    "doc_type": {"$ifNull": ["$doc_type", ""]},
                    "prompt_template_id": {"$ifNull": ["$template_id", ""]},
                    "prompt_version_used": {"$ifNull": ["$prompt_version", None]},
                    "final_error_type": {"$ifNull": ["$final_error_type", "unknown"]},
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"count": -1}},
        {"$limit": lim},
    ]
    try:
        agg = await db.generation_runs.aggregate(pipeline).to_list(length=lim)
    except Exception as e:
        logger.warning("prompt failure aggregate failed: %s", e)
        agg = []

    out: List[Dict[str, Any]] = []
    for row in agg:
        gid = row.get("_id") or {}
        et = gid.get("final_error_type")
        if et in (None, "unknown", ""):
            # Derive from a sample run if needed — skipped for cost; UI shows unknown
            et = "unknown"
        out.append(
            {
                "service_code": gid.get("service_code") or None,
                "doc_type": gid.get("doc_type") or None,
                "prompt_template_id": gid.get("prompt_template_id") or None,
                "prompt_version_used": gid.get("prompt_version_used"),
                "final_error_type": et,
                "count": row.get("count", 0),
            }
        )
    return out
