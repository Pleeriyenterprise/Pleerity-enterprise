"""
Read-only Unified Compliance Work Queue (UCWQ) v1 projection.

Built **only** from ``get_unified_tasks_for_client`` — no direct ``compliance_gaps`` reads,
no remediation-correlation-view, no persistence (PVG-001).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from services.unified_tasks_service import get_unified_tasks_for_client

# v1 excludes tenant inbox rows (deferred in product spec).
_UCWQ_EXCLUDED_SOURCE_TYPES: Set[str] = {"tenant_message", "tenant_request"}

# Top-level JSON keys allowed on each item (contract tests).
UCWQ_V1_ITEM_TOP_LEVEL_KEYS: Set[str] = {
    "queue_item_id",
    "source_system",
    "remediation_key",
    "property_id",
    "property_label",
    "title",
    "subtitle",
    "urgency_band",
    "primary_action",
    "primary_action_authority",
    "closure_summary_user",
    "related_ids",
    "created_at",
    "updated_at",
}

UCWQ_V1_PRIMARY_ACTION_KEYS: Set[str] = {"type", "label", "url", "inline_supported", "take_action"}

UCWQ_V1_RELATED_IDS_KEYS: Set[str] = {
    "requirement_id",
    "gap_key",
    "signal_id",
    "work_order_id",
    "issue_id",
    "invoice_id",
}


def urgency_band_from_unified_urgency_level(urgency_level: Optional[str]) -> str:
    """
    Map unified task ``urgency_level`` (from ``_urgency_level``) to UCWQ v1 band labels.
    Mirrors UNIFIED_COMPLIANCE_WORK_QUEUE_DESIGN.md § Urgency mapping v1.
    """
    u = (urgency_level or "low").lower()
    if u in ("critical", "high"):
        return "Urgent"
    if u == "medium":
        return "Soon"
    return "Watch"


def _remediation_key(task: Dict[str, Any]) -> str:
    meta = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    gk = meta.get("gap_key")
    if gk:
        return str(gk)
    tid = task.get("id")
    return str(tid) if tid else ""


def _primary_action_authority(task: Dict[str, Any]) -> str:
    meta = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    if isinstance(meta.get("take_action"), dict) and meta.get("take_action"):
        return "canonical_take_action"
    if meta.get("requirement_action_type"):
        return "canonical_take_action"
    st = (task.get("source_type") or "").lower()
    if st in ("risk_signal", "work_order", "issue", "approval"):
        return "operations_constructed"
    if st == "requirement":
        return "fallback"
    return "fallback"


def _closure_summary_user(task: Dict[str, Any]) -> str:
    st = (task.get("source_type") or "").lower()
    if st == "requirement":
        return (
            "Follow up on this obligation in your compliance view—hiding it in the inbox "
            "does not clear the requirement."
        )
    if st in ("work_order", "issue"):
        return "Operational follow-up may still be needed for statutory compliance."
    if st == "risk_signal":
        return "Review the flagged signal—follow through in operations or compliance as needed."
    if st == "approval":
        return "Approve or reject to unblock invoices and spend visibility."
    return "Review and complete the next step when you are ready."


def _related_ids(task: Dict[str, Any]) -> Dict[str, str]:
    meta = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    out: Dict[str, str] = {}
    rid = task.get("requirement_id") or meta.get("requirement_id")
    if rid:
        out["requirement_id"] = str(rid)
    if meta.get("gap_key"):
        out["gap_key"] = str(meta["gap_key"])
    if meta.get("related_risk_signal_id"):
        out["signal_id"] = str(meta["related_risk_signal_id"])
    if meta.get("related_work_order_id"):
        out["work_order_id"] = str(meta["related_work_order_id"])
    if meta.get("related_issue_id"):
        out["issue_id"] = str(meta["related_issue_id"])
    if meta.get("related_invoice_id"):
        out["invoice_id"] = str(meta["related_invoice_id"])
    return out


def _subtitle(task: Dict[str, Any]) -> str:
    d = (task.get("description") or "").strip()
    if d:
        return d[:2000]
    r = (task.get("recommended_action") or "").strip()
    return r[:2000] if r else ""


def _task_to_ucwq_row(task: Dict[str, Any]) -> Dict[str, Any]:
    meta = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    primary: Dict[str, Any] = {
        "type": task.get("primary_action_type"),
        "label": task.get("primary_action_label"),
        "url": (task.get("primary_action_url") or "").strip(),
        "inline_supported": bool(task.get("inline_action_supported")),
    }
    ta = meta.get("take_action")
    if isinstance(ta, dict) and ta:
        primary["take_action"] = ta

    row: Dict[str, Any] = {
        "queue_item_id": str(task.get("id") or ""),
        "source_system": str(task.get("source_type") or ""),
        "remediation_key": _remediation_key(task),
        "property_id": task.get("property_id"),
        "property_label": task.get("property_label"),
        "title": task.get("title") or "Task",
        "subtitle": _subtitle(task),
        "urgency_band": urgency_band_from_unified_urgency_level(task.get("urgency_level")),
        "primary_action": primary,
        "primary_action_authority": _primary_action_authority(task),
        "closure_summary_user": _closure_summary_user(task),
        "related_ids": _related_ids(task),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "_sort_score": int(task.get("impact_score") or 0),
    }
    return row


async def get_unified_compliance_work_queue_v1(
    client_id: str,
    *,
    property_id_filter: Optional[str] = None,
    raw_limit: int = 120,
    portal_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    bundle = await get_unified_tasks_for_client(
        client_id,
        property_id_filter=property_id_filter,
        raw_limit=raw_limit,
        portal_user_id=portal_user_id,
    )
    sections = bundle.get("tasks") or {}
    flat: List[Dict[str, Any]] = []
    for key in ("urgent", "upcoming", "in_progress"):
        flat.extend(sections.get(key) or [])

    filtered = [
        t
        for t in flat
        if (t.get("source_type") or "") not in _UCWQ_EXCLUDED_SOURCE_TYPES
    ]
    rows = [_task_to_ucwq_row(t) for t in filtered]
    rows.sort(
        key=lambda r: (
            -int(r.get("_sort_score") or 0),
            str(r.get("queue_item_id") or ""),
            str(r.get("property_id") or ""),
        )
    )
    for r in rows:
        r.pop("_sort_score", None)

    return {
        "items": rows,
        "summary": {"count": len(rows)},
    }
