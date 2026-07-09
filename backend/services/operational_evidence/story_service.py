"""
Operational Evidence Platform — Operational Story abstraction.

Stories are computed views over execution chains — not a separate authority.
Default investigation experience; raw evidence always available.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.operational_evidence.constants import (
    EVT_JOB_RUN_COMPLETED,
    EVT_JOB_RUN_DEGRADED,
    EVT_JOB_RUN_FAILED,
    EVT_JOB_RUN_STARTED,
    EVT_QUEUE_ITEM_CLAIMED,
    EVT_QUEUE_ITEM_COMPLETED,
    EVT_QUEUE_ITEM_CREATED,
    IMPACT_NONE,
)
from services.operational_evidence.query_service import get_execution_chain


_STORY_STEP_LABELS = {
    EVT_JOB_RUN_STARTED: "Started",
    EVT_JOB_RUN_COMPLETED: "Completed successfully",
    EVT_JOB_RUN_FAILED: "Failed",
    EVT_JOB_RUN_DEGRADED: "Completed with degradation",
    EVT_QUEUE_ITEM_CREATED: "Queue item created",
    EVT_QUEUE_ITEM_CLAIMED: "Worker claimed item",
    EVT_QUEUE_ITEM_COMPLETED: "Queue processing completed",
    "INCIDENT_OPENED": "Incident opened",
    "INCIDENT_RESOLVED": "Incident resolved",
    "NOTIFICATION_SENT": "Notification sent",
    "COMPLIANCE_SCORE_CHANGED": "Compliance recalculated",
}


def _humanize_event_type(event_type: str) -> str:
    if event_type in _STORY_STEP_LABELS:
        return _STORY_STEP_LABELS[event_type]
    return event_type.replace("_", " ").title()


def _derive_story_title(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "Operational execution"
    types = {it.get("event_type") for it in items}
    if EVT_QUEUE_ITEM_CREATED in types or "COMPLIANCE_SCORE_CHANGED" in types:
        return "Compliance recalculation"
    if any(t and t.startswith("JOB_RUN") for t in types):
        job_name = None
        for it in items:
            meta = it.get("metadata") or {}
            if meta.get("job_name"):
                job_name = meta["job_name"]
                break
        return f"Job execution{f' ({job_name})' if job_name else ''}"
    if any(t and t.startswith("INCIDENT") for t in types):
        return "Incident lifecycle"
    if any(t and t.startswith("NOTIFICATION") for t in types):
        return "Notification delivery"
    first = items[0]
    return _humanize_event_type(first.get("event_type") or "Operational execution")


def _summarize_customer_impact(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    worst = IMPACT_NONE
    rank = {
        IMPACT_NONE: 0,
        "operational_only": 1,
        "delayed": 2,
        "temporarily_stale": 3,
        "property_affected": 4,
        "portfolio_affected": 5,
        "partial_customer_impact": 6,
        "incorrect_output": 7,
        "manual_intervention_required": 8,
    }
    summary_text = "No customer impact"
    for it in items:
        ci = it.get("customer_impact") or {}
        cls = ci.get("classification") or IMPACT_NONE
        if rank.get(cls, 0) >= rank.get(worst, 0):
            worst = cls
            if ci.get("summary"):
                summary_text = ci["summary"]
    return {"classification": worst, "summary": summary_text}


def build_operational_story(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build story steps from ordered execution chain items."""
    if not items:
        return {
            "title": "Empty execution",
            "status": "unknown",
            "steps": [],
            "customer_impact": {"classification": IMPACT_NONE, "summary": "No customer impact"},
            "event_count": 0,
        }

    steps = []
    for it in items:
        rel = it.get("relationships") or {}
        steps.append(
            {
                "event_id": it.get("event_id"),
                "occurred_at": it.get("occurred_at"),
                "label": _humanize_event_type(it.get("event_type") or ""),
                "event_type": it.get("event_type"),
                "status": it.get("status"),
                "severity": it.get("severity"),
                "summary": (it.get("evidence") or {}).get("summary"),
                "deep_link": (it.get("evidence") or {}).get("deep_link"),
                "caused_by_event_id": rel.get("caused_by_event_id"),
                "relationship_type": rel.get("relationship_type"),
                "confidence": (it.get("confidence") or {}).get("score"),
            }
        )

    terminal = items[-1]
    terminal_status = terminal.get("status") or "unknown"
    if terminal_status == "failed":
        overall = "failed"
    elif terminal_status == "degraded":
        overall = "degraded"
    elif terminal_status in ("success", "recovered", "resolved"):
        overall = "success"
    else:
        overall = terminal_status

    return {
        "title": _derive_story_title(items),
        "status": overall,
        "started_at": items[0].get("occurred_at"),
        "finished_at": items[-1].get("occurred_at"),
        "root_execution_id": items[0].get("root_execution_id"),
        "correlation_id": items[0].get("correlation_id"),
        "steps": steps,
        "step_count": len(steps),
        "customer_impact": _summarize_customer_impact(items),
        "event_count": len(items),
        "raw_evidence_available": True,
    }


async def get_operational_story(
    *,
    root_execution_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    chain = await get_execution_chain(
        root_execution_id=root_execution_id,
        correlation_id=correlation_id,
    )
    story = build_operational_story(chain.get("items") or [])
    story["tree"] = chain.get("tree")
    story["items"] = chain.get("items")
    return story
