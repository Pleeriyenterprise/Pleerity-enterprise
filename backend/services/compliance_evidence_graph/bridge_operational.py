"""
Operational bridge — resolve OE correlation context for compliance decisions.

Read-only enrichment. Does not mutate operational or compliance authority state.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.operational_evidence.context import OperationalContext, get_operational_context


def resolve_operational_bridge(
    *,
    correlation_id: Optional[str] = None,
    client_id: Optional[str] = None,
    property_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build operational bridge payload from available context.
    Unknown fields remain null — never fabricated.
    """
    ctx = get_operational_context()
    resolved_cid = _first_non_empty(
        correlation_id,
        ctx.correlation_id if ctx else None,
    )

    operational_context: Dict[str, Any] = {
        "correlation_id": resolved_cid,
        "execution_id": ctx.execution_id if ctx else None,
        "root_execution_id": ctx.root_execution_id if ctx else None,
        "job_run_id": ctx.job_run_id if ctx else None,
        "incident_id": ctx.incident_id if ctx else None,
        "queue_item_id": ctx.queue_item_id if ctx else None,
        "worker": _infer_worker(ctx),
        "queue": _infer_queue(ctx),
        "recovery_event": None,
    }

    if extra:
        for key, val in extra.items():
            if val is not None and operational_context.get(key) is None:
                operational_context[key] = val

    timeline_references: List[Dict[str, Any]] = []
    if ctx and ctx.last_event_id:
        timeline_references.append(
            {
                "operational_event_id": ctx.last_event_id,
                "correlation_id": resolved_cid,
                "source": "operational_context.last_event_id",
            }
        )

    return {
        "operational_correlation_id": resolved_cid,
        "operational_context": operational_context,
        "timeline_references": timeline_references,
        "scope": {
            "client_id": _first_non_empty(client_id, ctx.client_id if ctx else None),
            "property_id": _first_non_empty(property_id, ctx.property_id if ctx else None),
            "requirement_id": _first_non_empty(requirement_id, ctx.requirement_id if ctx else None),
        },
    }


def merge_bridge_into_snapshot(snapshot_payload: Dict[str, Any], bridge: Dict[str, Any]) -> Dict[str, Any]:
    """Non-destructive merge of bridge fields into snapshot payload."""
    out = dict(snapshot_payload)
    if bridge.get("operational_context"):
        out["operational_context"] = {
            **(out.get("operational_context") or {}),
            **bridge["operational_context"],
        }
    if bridge.get("timeline_references"):
        existing = list(out.get("timeline_references") or [])
        out["timeline_references"] = existing + bridge["timeline_references"]
    return out


def _first_non_empty(*values: Optional[str]) -> Optional[str]:
    for v in values:
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def _infer_worker(ctx: Optional[OperationalContext]) -> Optional[str]:
    if not ctx or not ctx.metadata:
        return None
    return ctx.metadata.get("worker") or ctx.metadata.get("job_name")


def _infer_queue(ctx: Optional[OperationalContext]) -> Optional[str]:
    if not ctx:
        return None
    if ctx.queue_item_id:
        return "compliance_recalc_queue"
    return ctx.metadata.get("queue") if ctx.metadata else None
