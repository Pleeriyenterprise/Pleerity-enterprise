"""
Read-only chronological timeline for a single maintenance issue.

Merges: issue record (reported), audit_logs for resource maintenance_issue,
work_orders linked by issue_id, and asset_events with related_issue_id.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from database import database
from utils.audit import get_audit_logs_for_resource

from services import maintenance_issues_service

logger = logging.getLogger(__name__)

# Audit actions that already represent issue creation (avoid duplicate with synthetic row)
_CREATION_AUDIT_ACTIONS = frozenset(
    {
        "tenant_issue_reported",
        "issue_created_from_risk_signal",
    }
)


def _action_display(action: Optional[str]) -> str:
    if not action:
        return "Update"
    a = str(action).lower()
    mapping = {
        "issue_status_updated": "Status updated",
        "issue_closed": "Issue closed or resolved",
        "tenant_issue_reported": "Issue reported (tenant)",
        "issue_created_from_risk_signal": "Issue created from risk signal",
    }
    return mapping.get(a, a.replace("_", " ").title())


def _parse_ts(ts: Any) -> str:
    if ts is None:
        return ""
    if hasattr(ts, "isoformat"):
        return ts.isoformat()
    return str(ts)


def _sort_key(item: Dict[str, Any]) -> str:
    return item.get("timestamp") or ""


async def get_issue_timeline(client_id: str, issue_id: str, *, limit: int = 120) -> Optional[Dict[str, Any]]:
    """
    Build merged timeline for one issue. Returns None if issue not found for client.
    Items sorted by timestamp descending (newest first).
    """
    issue = await maintenance_issues_service.get_issue(issue_id, client_id=client_id)
    if not issue:
        return None

    items: List[Dict[str, Any]] = []
    cap = max(10, min(int(limit), 200))

    audits = await get_audit_logs_for_resource("maintenance_issue", issue_id, limit=cap)
    has_creation_audit = any(
        str(a.get("action") or "").lower() in _CREATION_AUDIT_ACTIONS for a in audits
    )

    if not has_creation_audit:
        created = issue.get("created_at")
        desc = (issue.get("description") or "").strip()[:280] or "Maintenance issue recorded."
        src = (issue.get("source") or "").strip().lower()
        src_note = f" Source: {src}." if src else ""
        items.append(
            {
                "id": f"issue_created:{issue_id}",
                "timestamp": _parse_ts(created),
                "category": "ISSUE",
                "event_type": "ISSUE_RECORDED",
                "title": "Issue reported",
                "description": f"{desc}{src_note}",
                "source": "issue",
                "metadata": {
                    "issue_id": issue_id,
                    "status_after": issue.get("status"),
                },
            }
        )

    for idx, a in enumerate(audits):
        ts = _parse_ts(a.get("timestamp"))
        act = str(a.get("action") or "")
        act_l = act.lower()
        meta = a.get("metadata") or {}
        old_s = meta.get("old_status")
        new_s = meta.get("new_status")
        detail_parts = []
        if old_s and new_s:
            detail_parts.append(f"Status: {old_s} → {new_s}")
        elif new_s:
            detail_parts.append(f"Status: {new_s}")
        description = ". ".join(detail_parts) if detail_parts else _action_display(act)
        items.append(
            {
                "id": a.get("audit_id") or f"audit:{issue_id}:{idx}:{ts}",
                "timestamp": ts,
                "category": "AUDIT",
                "event_type": act.upper().replace(".", "_") if act else "AUDIT",
                "title": _action_display(act),
                "description": description,
                "source": "audit_log",
                "metadata": {
                    "issue_id": issue_id,
                    "actor_id": a.get("actor_id"),
                    "old_status": old_s,
                    "new_status": new_s,
                },
            }
        )

    db = database.get_db()
    try:
        wo_list = await db.work_orders.find(
            {"client_id": client_id, "issue_id": issue_id},
            {
                "_id": 0,
                "work_order_id": 1,
                "description": 1,
                "status": 1,
                "created_at": 1,
                "completed_at": 1,
                "assigned_at": 1,
                "contractor_id": 1,
            },
        ).to_list(50)

        for wo in wo_list:
            wid = wo.get("work_order_id")
            desc = (wo.get("description") or "").strip()[:200]
            st = wo.get("status") or ""

            items.append(
                {
                    "id": f"wo_created:{wid}",
                    "timestamp": _parse_ts(wo.get("created_at")),
                    "category": "WORK_ORDER",
                    "event_type": "WORK_ORDER_CREATED",
                    "title": "Work order created",
                    "description": f"{desc or 'Work order linked to this issue.'} ({st})".strip(),
                    "source": "work_order",
                    "metadata": {"work_order_id": wid, "issue_id": issue_id, "status": st},
                }
            )

            if wo.get("assigned_at") and wo.get("contractor_id"):
                items.append(
                    {
                        "id": f"wo_assigned:{wid}",
                        "timestamp": _parse_ts(wo.get("assigned_at")),
                        "category": "WORK_ORDER",
                        "event_type": "WORK_ORDER_ASSIGNED",
                        "title": "Contractor assigned",
                        "description": f"Work order {str(wid)[:8]}… — contractor assigned.",
                        "source": "work_order",
                        "metadata": {
                            "work_order_id": wid,
                            "issue_id": issue_id,
                            "contractor_id": wo.get("contractor_id"),
                        },
                    }
                )

            if wo.get("completed_at"):
                items.append(
                    {
                        "id": f"wo_completed:{wid}",
                        "timestamp": _parse_ts(wo.get("completed_at")),
                        "category": "WORK_ORDER",
                        "event_type": "WORK_ORDER_COMPLETED",
                        "title": "Work order completed",
                        "description": desc or "Work marked complete.",
                        "source": "work_order",
                        "metadata": {"work_order_id": wid, "issue_id": issue_id},
                    }
                )
    except Exception as e:
        logger.debug("issue timeline work_orders skip: %s", e)

    try:
        ae_cursor = db.asset_events.find(
            {"client_id": client_id, "related_issue_id": issue_id},
            {"_id": 0, "event_id": 1, "event_type": 1, "timestamp": 1, "description": 1, "asset_id": 1},
        ).sort("timestamp", -1).limit(30)
        asset_events = await ae_cursor.to_list(30)
        for ev in asset_events:
            et = (ev.get("event_type") or "asset_event").replace("_", " ").title()
            items.append(
                {
                    "id": ev.get("event_id") or f"ae:{ev.get('timestamp')}:{ev.get('asset_id')}",
                    "timestamp": _parse_ts(ev.get("timestamp")),
                    "category": "ASSET",
                    "event_type": (ev.get("event_type") or "ASSET_EVENT").upper(),
                    "title": et,
                    "description": (ev.get("description") or et or "Asset activity")[:280],
                    "source": "asset_event",
                    "metadata": {
                        "issue_id": issue_id,
                        "asset_id": ev.get("asset_id"),
                    },
                }
            )
    except Exception as e:
        logger.debug("issue timeline asset_events skip: %s", e)

    items.sort(key=_sort_key, reverse=True)
    items = items[:cap]

    return {
        "issue_id": issue_id,
        "items": items,
    }
