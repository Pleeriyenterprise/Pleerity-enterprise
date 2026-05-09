"""
Ops-only read-only runtime convergence diagnostic (Phase 4).

Run from backend directory (requires MONGO_URL, DB_NAME like the main app):

  python -m scripts.runtime_convergence_diagnostic --property-id PID --limit 50
  python -m scripts.runtime_convergence_diagnostic --client-id CID --correlation-id X --output-format summary

No routes, no UI, no writes, no enqueue, no worker triggers.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CLI_HARD_MAX_LIMIT = 500
DEFAULT_LIMIT = 100
MAX_TIME_WINDOW_HOURS = 168  # 7 days


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Read-only convergence diagnostic (ops). Bounded queue reads only.",
    )
    p.add_argument("--property-id", dest="property_id", default=None, help="Filter by property_id")
    p.add_argument("--client-id", dest="client_id", default=None, help="Filter by client_id")
    p.add_argument(
        "--correlation-id",
        dest="correlation_ids",
        action="append",
        default=None,
        help="Exact correlation_id (repeatable)",
    )
    p.add_argument(
        "--status",
        dest="statuses",
        action="append",
        default=None,
        help="Queue status filter e.g. PENDING (repeatable)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Max jobs to return (cap {CLI_HARD_MAX_LIMIT}, default {DEFAULT_LIMIT})",
    )
    p.add_argument(
        "--time-window-hours",
        type=int,
        default=None,
        help=f"Optional: restrict updated_at to [now-hours, now] (max {MAX_TIME_WINDOW_HOURS}h); requires property, client, or correlation scope",
    )
    p.add_argument(
        "--traces-json",
        dest="traces_json",
        default=None,
        help="Optional JSON file: array of transition trace dicts for join diagnostics",
    )
    p.add_argument(
        "--output-format",
        choices=("json", "summary"),
        default="json",
        help="json: full snapshot; summary: concise deterministic text",
    )
    p.add_argument(
        "--skip-connect",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return p.parse_args(argv)


def _cli_scope_meaningful(
    *,
    property_id: Optional[str],
    client_id: Optional[str],
    correlation_ids: Optional[Sequence[str]],
) -> bool:
    if (property_id or "").strip():
        return True
    if (client_id or "").strip():
        return True
    if correlation_ids:
        for c in correlation_ids:
            if str(c or "").strip():
                return True
    return False


def _normalize_statuses(statuses: Optional[Sequence[str]]) -> List[str]:
    if not statuses:
        return []
    out: List[str] = []
    for s in statuses:
        for part in str(s or "").split(","):
            t = part.strip().upper()
            if t:
                out.append(t)
    return out


def _load_traces(path: Optional[str]) -> List[Dict[str, Any]]:
    if not path:
        return []
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("traces-json must be a JSON array")
    return [dict(x) for x in data if isinstance(x, Mapping)]


async def _freshness_enrichment(
    db,
    *,
    property_id: Optional[str],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Read-only property freshness fields when property_id is set."""
    if not (property_id or "").strip():
        return {}, {"available": False, "reason": "property_id_not_provided"}
    doc = await db.properties.find_one(
        {"property_id": property_id.strip()},
        {"_id": 0, "compliance_last_calculated_at": 1, "compliance_score_pending": 1, "property_id": 1, "client_id": 1},
    )
    if not doc:
        return {}, {"available": False, "reason": "property_not_found"}
    blob = {
        "property_id": doc.get("property_id"),
        "client_id": doc.get("client_id"),
        "compliance_last_calculated_at": doc.get("compliance_last_calculated_at"),
        "compliance_score_pending": doc.get("compliance_score_pending"),
    }
    vis = {
        "available": True,
        "score_pending_visible": bool(doc.get("compliance_score_pending")),
        "last_calculated_visible": doc.get("compliance_last_calculated_at") is not None,
    }
    return blob, vis


async def run_diagnostic(
    *,
    property_id: Optional[str] = None,
    client_id: Optional[str] = None,
    correlation_ids: Optional[Sequence[str]] = None,
    statuses: Optional[Sequence[str]] = None,
    limit: int = DEFAULT_LIMIT,
    time_window_hours: Optional[int] = None,
    traces_json_path: Optional[str] = None,
    output_format: str = "json",
    db=None,
    generated_at_iso: Optional[str] = None,
    connect_database: bool = True,
) -> Tuple[int, str]:
    """
    Run bounded read-only diagnostics. Returns (exit_code, output_string).

    When connect_database is False, caller must pass db= (tests).
    """
    from services.workflow_runtime_convergence_fetch import (
        MAX_FETCH_LIMIT_CAP,
        build_recalc_joined_convergence_snapshot_from_db,
        fetch_recalc_jobs_for_convergence_join,
        normalize_correlation_hints,
    )
    from services.workflow_runtime_convergence_observability import (
        build_convergence_join_operational_summary,
        build_runtime_convergence_snapshot,
    )

    if not _cli_scope_meaningful(
        property_id=property_id,
        client_id=client_id,
        correlation_ids=correlation_ids,
    ):
        msg = (
            "Insufficient scope: provide --property-id, --client-id, and/or --correlation-id "
            "(time window alone is not allowed to avoid cross-tenant scans)."
        )
        if output_format == "summary":
            return 2, f"WARNING: {msg}\n"
        return 2, json.dumps({"warning": msg, "jobs": [], "diagnostics": {"skipped_unbounded_scan": True}}, indent=2, sort_keys=True) + "\n"

    eff_limit = max(1, min(int(limit or DEFAULT_LIMIT), CLI_HARD_MAX_LIMIT, MAX_FETCH_LIMIT_CAP))

    updated_min: Optional[str] = None
    updated_max: Optional[str] = None
    if time_window_hours is not None:
        tw = max(1, min(int(time_window_hours), MAX_TIME_WINDOW_HOURS))
        now = datetime.now(timezone.utc)
        updated_max = now.isoformat()
        updated_min = (now - timedelta(hours=tw)).isoformat()

    hints = normalize_correlation_hints(list(correlation_ids) if correlation_ids else None)
    status_in = _normalize_statuses(statuses)

    iso = generated_at_iso or datetime.now(timezone.utc).isoformat()

    if connect_database:
        from database import database

        await database.connect()
        mongo = database.get_db()
    else:
        mongo = db
        if mongo is None:
            return 2, "Internal error: db required when connect_database=False\n"

    traces = _load_traces(traces_json_path)

    fetch_kw: Dict[str, Any] = {
        "property_id": (property_id or "").strip() or None,
        "client_id": (client_id or "").strip() or None,
        "correlation_hints": hints or None,
        "status_in": status_in or None,
        "updated_at_min": updated_min,
        "updated_at_max": updated_max,
        "limit": eff_limit,
        "max_limit_cap": CLI_HARD_MAX_LIMIT,
    }

    fr = await fetch_recalc_jobs_for_convergence_join(db=mongo, **fetch_kw)

    joined = await build_recalc_joined_convergence_snapshot_from_db(
        transition_traces=traces,
        generated_at_iso=iso,
        db=mongo,
        fetch_result=fr,
        max_jobs_scanned=len(fr.get("jobs") or []),
    )

    runtime = build_runtime_convergence_snapshot(
        transition_traces=traces,
        generated_at_iso=iso,
        recalc_queue_jobs=fr.get("jobs") or [],
    )

    op = build_convergence_join_operational_summary(
        joined_rows=joined.get("joined_rows") or [],
        transition_traces=traces,
        recalc_queue_jobs=fr.get("jobs") or [],
        max_jobs_scanned=len(fr.get("jobs") or []),
    )

    fresh_blob, fresh_vis = await _freshness_enrichment(mongo, property_id=(property_id or "").strip() or None)

    payload: Dict[str, Any] = {
        "schema_version": "runtime_convergence_diagnostic_cli_v1",
        "generated_at_iso": iso,
        "cli_scope": {
            "property_id": fetch_kw["property_id"],
            "client_id": fetch_kw["client_id"],
            "correlation_hints_normalized": hints,
            "status_in": status_in,
            "limit": eff_limit,
            "time_window_hours": time_window_hours,
            "updated_at_min": updated_min,
            "updated_at_max": updated_max,
        },
        "fetch": {
            "diagnostics": fr.get("diagnostics"),
            "jobs": fr.get("jobs") or [],
        },
        "joined_convergence_snapshot": joined,
        "runtime_convergence_snapshot": runtime,
        "convergence_join_operational_summary": op,
        "freshness_enrichment": fresh_blob,
        "freshness_visibility": fresh_vis,
        "transition_trace_count": len(traces),
    }

    if output_format == "summary":
        return 0, _format_summary(payload)

    out = json.dumps(payload, indent=2, sort_keys=True, default=str)
    return 0, out + "\n"


def _format_summary(payload: Mapping[str, Any]) -> str:
    lines: List[str] = []
    fd = (payload.get("fetch") or {}).get("diagnostics") or {}
    fj = (payload.get("fetch") or {}).get("jobs") or []
    lines.append("=== runtime convergence diagnostic (summary) ===")
    lines.append(f"returned_job_count: {len(fj)}")
    lines.append(f"limit: {fd.get('limit')} truncated: {fd.get('truncated')} skipped_unbounded_scan: {fd.get('skipped_unbounded_scan')}")
    if fd.get("warning"):
        lines.append(f"fetch_warning: {fd.get('warning')}")
    lines.append(f"transition_trace_count: {payload.get('transition_trace_count')}")

    joined = payload.get("joined_convergence_snapshot") or {}
    rc = joined.get("recalc_convergence_summary") or {}
    lines.append(f"join_histogram: {rc.get('by_join_classification')}")
    lines.append(f"settlement_linkage: {rc.get('by_settlement_linkage')}")

    stale = (joined.get("joined_rows") or [])
    stale_risk = sum(1 for r in stale if r.get("stale_read_risk_visible"))
    lines.append(f"joined_rows_stale_read_risk_visible: {stale_risk}")

    op = payload.get("convergence_join_operational_summary") or {}
    lines.append(f"weakest_joined_workflows: {op.get('weakest_joined_workflows')}")
    lines.append(f"strongest_joined_workflows: {op.get('strongest_joined_workflows')}")
    lines.append(f"trace_without_queue_visibility: {op.get('trace_without_queue_visibility')}")
    lines.append(f"queue_without_trace_visibility: {op.get('queue_without_trace_visibility')}")

    rt = payload.get("runtime_convergence_snapshot") or {}
    pc = rt.get("propagation_completion") or {}
    lines.append(f"propagation_by_completion: {pc.get('by_propagation_completion')}")

    fv = payload.get("freshness_visibility") or {}
    lines.append(f"freshness_visibility: {fv}")

    return "\n".join(lines) + "\n"


async def _amain() -> int:
    args = _parse_args()
    code, text = await run_diagnostic(
        property_id=args.property_id,
        client_id=args.client_id,
        correlation_ids=args.correlation_ids,
        statuses=args.statuses,
        limit=args.limit,
        time_window_hours=args.time_window_hours,
        traces_json_path=args.traces_json,
        output_format=args.output_format,
        connect_database=not getattr(args, "skip_connect", False),
    )
    sys.stdout.write(text)
    return code


def main() -> None:
    raise SystemExit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()
