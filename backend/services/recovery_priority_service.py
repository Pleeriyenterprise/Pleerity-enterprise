"""Today / Command Centre recovery priority integration."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.client_priority_stream import _action
from services.operational_recovery_service import (
    build_operational_recovery_summary,
    detect_workflow_recovery_candidates,
)
from services.recovery_constants import (
    RECOVERY_OPERATIONAL_DEAD_END,
    RECOVERY_QUOTE_NEGOTIATION_LOOP,
    RECOVERY_VISIT_RESCHEDULE_LOOP,
    RECOVERY_EVIDENCE_REJECTION_LOOP,
    RECOVERY_WORK_ORDER_ABANDONMENT_RISK,
)

logger = logging.getLogger(__name__)

_RECOVERY_PRIORITY = {
    RECOVERY_WORK_ORDER_ABANDONMENT_RISK: 100,
    RECOVERY_OPERATIONAL_DEAD_END: 99,
    RECOVERY_EVIDENCE_REJECTION_LOOP: 98,
    RECOVERY_QUOTE_NEGOTIATION_LOOP: 98,
    RECOVERY_VISIT_RESCHEDULE_LOOP: 97,
    RECOVERY_CONTRACTOR_NON_RESPONSE: 97,
}


def _is_blocked(recovery_type: str) -> bool:
    return recovery_type in (
        RECOVERY_OPERATIONAL_DEAD_END,
        RECOVERY_WORK_ORDER_ABANDONMENT_RISK,
        RECOVERY_QUOTE_NEGOTIATION_LOOP,
        RECOVERY_VISIT_RESCHEDULE_LOOP,
        RECOVERY_EVIDENCE_REJECTION_LOOP,
    )


async def fetch_operational_recovery_priority_actions(
    client_id: str,
    property_id_filter: Optional[str] = None,
    limit: int = 6,
) -> List[Dict[str, Any]]:
    candidates = await detect_workflow_recovery_candidates(
        client_id,
        property_id_filter=property_id_filter,
        limit=limit * 3,
    )
    actions: List[Dict[str, Any]] = []
    for rec in candidates:
        if rec.get("suppressed"):
            continue
        rtype = rec.get("recovery_type") or ""
        score = _RECOVERY_PRIORITY.get(rtype, 95 if _is_blocked(rtype) else 93)
        if rec.get("severity") == "high":
            score = min(99, score + 2)
        et = rec.get("entity_type") or ""
        eid = rec.get("entity_id") or ""
        url = f"/operations/work-orders/{eid}" if et == "work_order" else f"/compliance/requirements/{eid}"
        first_action = (rec.get("suggested_actions") or [{}])[0]
        label = first_action.get("label") if isinstance(first_action, dict) else "Review"
        actions.append(
            _action(
                "operational_recovery",
                rec.get("recovery_summary") or "Recovery needed",
                rec.get("recovery_explanation") or "",
                score,
                "high" if rec.get("severity") == "high" else "medium",
                related_work_order_id=eid if et == "work_order" else None,
                related_property_id=rec.get("property_id"),
                recommended_url=url,
                recommended_action_label=label,
                why_matters=rec.get("operational_risk") or "",
                recommended_action_detail=rec.get("recovery_summary"),
            )
        )
    actions.sort(key=lambda a: -(a.get("priority") or 0))
    return actions[:limit]


def merge_recovery_with_urgent(
    recovery_actions: List[Dict[str, Any]],
    existing: List[Dict[str, Any]],
    *,
    cap: int = 24,
) -> List[Dict[str, Any]]:
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for a in recovery_actions + existing:
        key = a.get("related_work_order_id") or a.get("title")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(a)
    out.sort(key=lambda x: -(x.get("priority") or 0))
    return out[:cap]


async def apply_operational_recovery_to_today_payload(
    client_id: str,
    payload: Dict[str, Any],
    *,
    property_id_filter: Optional[str] = None,
) -> Dict[str, Any]:
    candidates = await detect_workflow_recovery_candidates(
        client_id,
        property_id_filter=property_id_filter,
        limit=50,
    )
    summary = build_operational_recovery_summary(candidates)
    now = datetime.now(timezone.utc)
    blocked = [c for c in candidates if _is_blocked(c.get("recovery_type") or "")]
    waiting = [c for c in candidates if c not in blocked]

    payload["recovery_disclosure"] = {
        "client_id": client_id,
        "recovery_count": len(candidates),
        "blocked_count": len(blocked),
        "waiting_count": len(waiting),
        "has_recovery_attention": summary.get("has_recovery_attention"),
        "high_risk_count": summary.get("high_risk_count"),
        "captured_at": now.isoformat(),
    }
    payload["recovery_risk"] = {
        "high_risk_count": summary.get("high_risk_count"),
        "blocked_count": summary.get("blocked_count"),
        "by_recovery_type": summary.get("by_recovery_type"),
    }

    tasks_root = payload.get("tasks") or {}
    recovery_by_wo = {
        c["entity_id"]: c for c in candidates if c.get("entity_type") == "work_order" and c.get("entity_id")
    }
    for bucket in ("urgent", "upcoming", "in_progress"):
        for t in tasks_root.get(bucket) or []:
            wid = (t.get("metadata") or {}).get("related_work_order_id") or t.get("related_work_order_id")
            rec = recovery_by_wo.get(wid)
            if not rec:
                continue
            meta = dict(t.get("metadata") or {})
            meta["recovery_type"] = rec.get("recovery_type")
            meta["waiting_on_summary"] = rec.get("waiting_on_party")
            meta["stalled_reason"] = rec.get("recovery_summary")
            meta["recovery_actions"] = rec.get("suggested_actions")
            meta["is_blocked"] = _is_blocked(rec.get("recovery_type") or "")
            t["metadata"] = meta
            if meta["is_blocked"] and bucket != "urgent":
                t["urgency"] = "overdue"
                tasks_root.setdefault("_recovery_promoted", []).append(t.get("id"))

    payload["tasks"] = tasks_root
    if candidates:
        top = candidates[0]
        payload["waiting_on_summary"] = top.get("waiting_on_party")
        payload["stalled_reason"] = top.get("recovery_summary")
        payload["recovery_actions"] = top.get("suggested_actions")
    return payload
