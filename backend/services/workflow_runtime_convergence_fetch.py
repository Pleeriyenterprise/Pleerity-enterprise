"""
Read-only fetch helpers for compliance_recalc_queue rows used in convergence joins.

Phase 3 — observability only; no writes, no route wiring, bounded deterministic reads.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence

from database import database

from services.workflow_runtime_convergence_observability import (
    build_recalc_joined_convergence_snapshot,
    deterministic_recalc_job_sort_key,
)

logger = logging.getLogger(__name__)

DEFAULT_FETCH_LIMIT = 100
MAX_FETCH_LIMIT_CAP = 500
MAX_CORRELATION_HINTS = 32


def normalize_correlation_hints(
    correlation_hints: Optional[Sequence[str]],
    *,
    max_hints: int = MAX_CORRELATION_HINTS,
) -> List[str]:
    """Trim, dedupe (preserve order), cap length. No DB substring logic."""
    if not correlation_hints:
        return []
    seen: set[str] = set()
    out: List[str] = []
    for raw in correlation_hints:
        h = str(raw or "").strip()
        if not h or h in seen:
            continue
        seen.add(h)
        out.append(h)
        if len(out) >= max_hints:
            break
    return out


def _filters_meaningful(
    *,
    property_id: Optional[str],
    client_id: Optional[str],
    correlation_hints: Sequence[str],
    created_at_min: Optional[str],
    created_at_max: Optional[str],
    updated_at_min: Optional[str],
    updated_at_max: Optional[str],
) -> bool:
    """
    Require tenant scope, exact correlation list, or a fully bounded time window.
    Prevents collection-wide scans from status-only or open-ended queries.
    """
    if (property_id or "").strip():
        return True
    if (client_id or "").strip():
        return True
    if correlation_hints:
        return True
    if created_at_min and created_at_max:
        return True
    if updated_at_min and updated_at_max:
        return True
    return False


def _build_mongo_query(
    *,
    property_id: Optional[str],
    client_id: Optional[str],
    correlation_hints: Sequence[str],
    status_in: Optional[Sequence[str]],
    created_at_min: Optional[str],
    created_at_max: Optional[str],
    updated_at_min: Optional[str],
    updated_at_max: Optional[str],
) -> Dict[str, Any]:
    parts: List[Dict[str, Any]] = []
    pid = (property_id or "").strip()
    cid = (client_id or "").strip()
    if pid:
        parts.append({"property_id": pid})
    if cid:
        parts.append({"client_id": cid})
    if correlation_hints:
        parts.append({"correlation_id": {"$in": list(correlation_hints)}})
    if status_in:
        statuses = [str(s or "").strip().upper() for s in status_in if str(s or "").strip()]
        if statuses:
            parts.append({"status": {"$in": statuses}})

    ca: Dict[str, Any] = {}
    if created_at_min:
        ca["$gte"] = created_at_min
    if created_at_max:
        ca["$lte"] = created_at_max
    if ca:
        parts.append({"created_at": ca})

    ua: Dict[str, Any] = {}
    if updated_at_min:
        ua["$gte"] = updated_at_min
    if updated_at_max:
        ua["$lte"] = updated_at_max
    if ua:
        parts.append({"updated_at": ua})

    if not parts:
        return {}
    if len(parts) == 1:
        return parts[0]
    return {"$and": parts}


def _serialize_job(doc: Mapping[str, Any]) -> Dict[str, Any]:
    """Plain dict copy; stringify ObjectId for stable snapshots."""
    out: Dict[str, Any] = dict(doc)
    _id = out.get("_id")
    if _id is not None and not isinstance(_id, (str, int, float, bool)):
        out["_id"] = str(_id)
    return out


async def fetch_recalc_jobs_for_convergence_join(
    db=None,
    *,
    property_id: Optional[str] = None,
    client_id: Optional[str] = None,
    correlation_hints: Optional[Sequence[str]] = None,
    status_in: Optional[Sequence[str]] = None,
    created_at_min: Optional[str] = None,
    created_at_max: Optional[str] = None,
    updated_at_min: Optional[str] = None,
    updated_at_max: Optional[str] = None,
    limit: int = DEFAULT_FETCH_LIMIT,
    max_limit_cap: int = MAX_FETCH_LIMIT_CAP,
) -> Dict[str, Any]:
    """
    Bounded read of ``compliance_recalc_queue`` rows for Phase 2 join helpers.

    Returns ``{"jobs": [...], "diagnostics": {...}}``. No writes.
    If filters are insufficient for a safe bounded query, returns empty jobs and diagnostics flag.
    """
    hints = normalize_correlation_hints(correlation_hints)
    meaningful = _filters_meaningful(
        property_id=property_id,
        client_id=client_id,
        correlation_hints=hints,
        created_at_min=created_at_min,
        created_at_max=created_at_max,
        updated_at_min=updated_at_min,
        updated_at_max=updated_at_max,
    )

    cap_ceiling = min(MAX_FETCH_LIMIT_CAP, max(1, int(max_limit_cap or MAX_FETCH_LIMIT_CAP)))
    requested = int(limit) if limit is not None else DEFAULT_FETCH_LIMIT
    effective_limit = max(1, min(requested, cap_ceiling))

    query_filters = _build_mongo_query(
        property_id=property_id,
        client_id=client_id,
        correlation_hints=hints,
        status_in=status_in,
        created_at_min=created_at_min,
        created_at_max=created_at_max,
        updated_at_min=updated_at_min,
        updated_at_max=updated_at_max,
    )

    if not meaningful:
        logger.info(
            "fetch_recalc_jobs_for_convergence_join: skipped unbounded scan (insufficient filters)",
            extra={"query_filters": query_filters},
        )
        return {
            "jobs": [],
            "diagnostics": {
                "query_filters": query_filters,
                "limit": effective_limit,
                "bounded": True,
                "skipped_unbounded_scan": True,
                "matched_count": 0,
                "returned_count": 0,
                "truncated": False,
                "warning": "insufficient_filters_for_safe_query",
            },
        }

    mongo = db if db is not None else database.get_db()
    fetch_n = effective_limit + 1
    cursor = mongo.compliance_recalc_queue.find(query_filters)
    raw: List[Mapping[str, Any]] = await cursor.to_list(length=fetch_n)

    truncated = len(raw) > effective_limit
    slice_docs = raw[:effective_limit]
    jobs = sorted((_serialize_job(d) for d in slice_docs), key=deterministic_recalc_job_sort_key)

    returned_count = len(jobs)
    diagnostics: Dict[str, Any] = {
        "query_filters": query_filters,
        "limit": effective_limit,
        "bounded": True,
        "skipped_unbounded_scan": False,
        "returned_count": returned_count,
        "truncated": truncated,
    }
    if truncated:
        diagnostics["matched_count"] = None
        diagnostics["matched_lower_bound"] = effective_limit + 1
    else:
        diagnostics["matched_count"] = returned_count

    return {"jobs": jobs, "diagnostics": diagnostics}


async def build_recalc_joined_convergence_snapshot_from_db(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    generated_at_iso: str,
    db=None,
    max_jobs_scanned: Optional[int] = None,
    fetch_result: Optional[MutableMapping[str, Any]] = None,
    **fetch_kwargs: Any,
) -> Dict[str, Any]:
    """
    Read-only integration: bounded fetch + ``build_recalc_joined_convergence_snapshot``.

    ``fetch_kwargs`` are passed to ``fetch_recalc_jobs_for_convergence_join`` (e.g. property_id).
    If ``fetch_result`` is provided (e.g. from a prior ``fetch_recalc_jobs_for_convergence_join`` call),
    the helper reuses it and does not query Mongo again.
    """
    if fetch_result is None:
        fetch_result = await fetch_recalc_jobs_for_convergence_join(db=db, **fetch_kwargs)
    jobs = fetch_result.get("jobs") or []
    eff_scan = max_jobs_scanned if max_jobs_scanned is not None else len(jobs)
    snap = build_recalc_joined_convergence_snapshot(
        transition_traces=transition_traces,
        recalc_queue_jobs=jobs,
        generated_at_iso=generated_at_iso,
        max_jobs_scanned=eff_scan,
    )
    snap["fetch_diagnostics"] = dict(fetch_result.get("diagnostics") or {})
    snap["fetch_diagnostics"]["jobs_fetched"] = len(jobs)
    return snap
