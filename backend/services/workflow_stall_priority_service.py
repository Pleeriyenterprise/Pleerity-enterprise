"""Today / Command Centre priority boosts for stalled workflows."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import database

from services.client_priority_stream import _action
from services.workflow_timer_service import work_order_stall_context

logger = logging.getLogger(__name__)

_TERMINAL_WO = frozenset({"CANCELLED", "COMPLETED", "VERIFIED", "CLOSED"})

CONTINUATION_CTA: Dict[str, Dict[str, str]] = {
    "awaiting_contractor_quote": {
        "landlord": "Open job",
        "contractor": "Submit quote",
        "banner": "Waiting on contractor quote",
    },
    "awaiting_contractor_quote_revision": {
        "landlord": "Open job",
        "contractor": "Submit revised quote",
        "banner": "Waiting on revised contractor quote",
    },
    "awaiting_landlord_quote_response": {
        "landlord": "Review contractor quote",
        "contractor": "Open job",
        "banner": "Waiting on landlord approval",
    },
    "awaiting_visit_confirmation": {
        "landlord": "Confirm proposed visit",
        "contractor": "Confirm proposed visit",
        "banner": "Visit proposal awaiting confirmation",
    },
    "awaiting_visit_reschedule": {
        "landlord": "Open job",
        "contractor": "Propose new visit time",
        "banner": "Visit reschedule pending",
    },
    "completion_proof_pending": {
        "contractor": "Upload completion proof",
        "banner": "Completion proof pending",
    },
    "awaiting_completion_review": {
        "landlord": "Review completion proof",
        "contractor": "Awaiting review",
        "banner": "Completion proof awaiting review",
    },
    "invoice_pending": {
        "contractor": "Submit invoice",
        "banner": "Invoice pending",
    },
}


def _escalation_tier(age_hours: Optional[float]) -> Optional[str]:
    if age_hours is None:
        return None
    if age_hours >= 72:
        return "T72"
    if age_hours >= 24:
        return "T24"
    return None


def _priority_score(stall_type: str, tier: Optional[str]) -> int:
    base = {
        "awaiting_landlord_quote_response": 92,
        "awaiting_visit_confirmation": 90,
        "awaiting_contractor_quote": 88,
        "awaiting_contractor_quote_revision": 87,
        "awaiting_visit_reschedule": 85,
        "completion_proof_pending": 84,
        "awaiting_completion_review": 91,
        "invoice_pending": 82,
    }.get(stall_type, 80)
    if tier == "T72":
        return min(99, base + 4)
    if tier == "T24":
        return min(96, base + 2)
    return base


async def fetch_workflow_stall_priority_actions(
    client_id: str,
    property_id_filter: Optional[str] = None,
    limit: int = 6,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    q: Dict[str, Any] = {
        "client_id": client_id,
        "status": {"$nin": list(_TERMINAL_WO)},
    }
    if property_id_filter:
        q["property_id"] = property_id_filter
    cursor = db.work_orders.find(q, {"_id": 0}).limit(200)
    actions: List[Dict[str, Any]] = []
    async for wo in cursor:
        stall = work_order_stall_context(wo)
        if not stall:
            continue
        tier = _escalation_tier(stall.get("age_hours"))
        stype = stall.get("stall_type") or ""
        cta_map = CONTINUATION_CTA.get(stype, {})
        waiting = stall.get("waiting_on") or "landlord"
        label = cta_map.get(waiting) or cta_map.get("landlord") or "Continue"
        banner = cta_map.get("banner") or "Workflow needs attention"
        wid = wo.get("work_order_id")
        score = _priority_score(stype, tier)
        actions.append(
            _action(
                "workflow_stall_nudge",
                banner,
                f"Stalled for {int(stall.get('age_hours') or 0)}h — waiting on {waiting}.",
                score,
                "high" if tier == "T72" else "medium",
                related_work_order_id=wid,
                related_property_id=wo.get("property_id"),
                recommended_url=f"/operations/work-orders/{wid}",
                recommended_action_label=label,
                why_matters="Unresolved dependencies block work from continuing.",
                recommended_action_detail=banner,
            )
        )
    actions.sort(key=lambda a: -(a.get("priority") or 0))
    return actions[:limit]


def merge_workflow_stall_with_urgent(
    stall_actions: List[Dict[str, Any]],
    existing: List[Dict[str, Any]],
    *,
    cap: int = 24,
) -> List[Dict[str, Any]]:
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for a in stall_actions + existing:
        key = a.get("related_work_order_id") or a.get("title")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(a)
    out.sort(key=lambda x: -(x.get("priority") or 0))
    return out[:cap]


def apply_workflow_stall_escalation_to_today_payload(
    client_id: str,
    payload: Dict[str, Any],
    *,
    stalled_work_orders: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Boost urgency and attach continuation metadata for tasks linked to stalled jobs."""
    if stalled_work_orders is None:
        return payload
    stall_by_wo = {}
    for wo in stalled_work_orders:
        stall = work_order_stall_context(wo)
        if stall and wo.get("work_order_id"):
            stall_by_wo[wo["work_order_id"]] = stall
    if not stall_by_wo:
        return payload
    tasks_root = payload.get("tasks") or {}
    now = datetime.now(timezone.utc)
    for bucket in ("urgent", "upcoming", "in_progress"):
        rows = tasks_root.get(bucket) or []
        for t in rows:
            wid = (t.get("metadata") or {}).get("related_work_order_id") or t.get("related_work_order_id")
            if not wid or wid not in stall_by_wo:
                continue
            stall = stall_by_wo[wid]
            tier = _escalation_tier(stall.get("age_hours"))
            meta = dict(t.get("metadata") or {})
            meta["workflow_stall_escalation_tier"] = tier
            meta["waiting_on_party"] = stall.get("waiting_on")
            stype = stall.get("stall_type") or ""
            meta["continuation_banner"] = CONTINUATION_CTA.get(stype, {}).get("banner")
            t["metadata"] = meta
            if tier in ("T24", "T72"):
                t["urgency"] = "due_soon" if tier == "T24" else "overdue"
            if tier == "T72" and bucket != "urgent":
                tasks_root.setdefault("_promoted", []).append(t.get("id"))
    payload["tasks"] = tasks_root
    payload["workflow_stall_disclosure"] = {
        "client_id": client_id,
        "stalled_count": len(stall_by_wo),
        "captured_at": now.isoformat(),
        "has_unresolved_dependencies": len(stall_by_wo) > 0,
    }
    return payload


async def load_stalled_work_orders_for_client(
    client_id: str,
    property_id_filter: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    q: Dict[str, Any] = {"client_id": client_id, "status": {"$nin": list(_TERMINAL_WO)}}
    if property_id_filter:
        q["property_id"] = property_id_filter
    out: List[Dict[str, Any]] = []
    async for wo in db.work_orders.find(q, {"_id": 0}).limit(limit * 4):
        if work_order_stall_context(wo):
            out.append(wo)
        if len(out) >= limit:
            break
    return out
