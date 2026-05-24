"""
Today attention authority ranking — ATTENTION_AUTHORITY_RULES (VERIFY-02 G1).

Deterministic sort keys for unified task / Today inbox ordering. Aligns with
``services.ops_runtime_verify_02.attention_authority_service.ATTENTION_PRECEDENCE``.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from services.client_priority_stream import (
    ACTION_CERT_EXPIRING_SOON,
    ACTION_MISSING_DOCUMENT,
    ACTION_OPEN_ISSUE,
    ACTION_OPEN_WORK_ORDER,
    ACTION_OVERDUE_COMPLIANCE,
    ACTION_PENDING_APPROVAL,
    ACTION_RISK_SIGNAL,
    ACTION_WORK_ORDER_BREACHED,
    ACTION_WORK_ORDER_NEAR_BREACH,
)

# Lower rank = higher attention authority (matches G1 harness + framework).
ATTENTION_PRECEDENCE: Dict[str, int] = {
    "overdue_remediation": 1,
    "active_risk": 2,
    "open_operational_debt": 3,
    "time_bound_reminder": 4,
    "informational": 5,
}


def _action_type(task: Dict[str, Any]) -> str:
    meta = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    at = str(meta.get("action_type") or task.get("primary_action_type") or "").strip()
    if at:
        return at
    st = str(task.get("source_type") or "").lower()
    return {
        "risk_signal": ACTION_RISK_SIGNAL,
        "issue": ACTION_OPEN_ISSUE,
        "work_order": ACTION_OPEN_WORK_ORDER,
        "approval": ACTION_PENDING_APPROVAL,
        "requirement": ACTION_MISSING_DOCUMENT,
    }.get(st, "")


def attention_class_for_task(task: Dict[str, Any]) -> str:
    """
    Map unified/today task DTO to ATTENTION_AUTHORITY_RULES debt class.
    Mirrors G1 harness ``_attention_class`` against enriched Today rows.
    """
    section = str(task.get("section") or task.get("_section") or "")
    source = str(task.get("source_type") or "").lower()
    u = str(task.get("urgency") or task.get("urgency_level") or "").lower()
    overdue_days = int(task.get("overdue_days") or 0)
    action_type = _action_type(task)

    if u == "overdue" or overdue_days > 0:
        return "overdue_remediation"
    if action_type == ACTION_OVERDUE_COMPLIANCE:
        return "overdue_remediation"
    if action_type == ACTION_WORK_ORDER_BREACHED:
        return "overdue_remediation"
    if source in ("risk_signal", "risk") or "risk" in source or action_type == ACTION_RISK_SIGNAL:
        return "active_risk"
    if source in ("work_order", "issue", "maintenance_issue", "requirement", "compliance_job"):
        return "open_operational_debt"
    if action_type in (ACTION_OPEN_ISSUE, ACTION_OPEN_WORK_ORDER, ACTION_MISSING_DOCUMENT, ACTION_CERT_EXPIRING_SOON):
        return "open_operational_debt"
    if u == "due_soon" or section == "upcoming":
        return "time_bound_reminder"
    if action_type == ACTION_PENDING_APPROVAL or source == "approval":
        return "time_bound_reminder"
    if section in ("snoozed", "hidden"):
        return "informational"
    return "open_operational_debt" if section in ("urgent", "in_progress") else "informational"


def _sub_rank_within_class(task: Dict[str, Any], debt_class: str) -> int:
    """Finer ordering within a precedence band (lower = higher priority)."""
    source = str(task.get("source_type") or "").lower()
    action_type = _action_type(task)
    if debt_class == "active_risk":
        sev = str((task.get("metadata") or {}).get("severity") or task.get("urgency_level") or "").lower()
        if sev == "critical":
            return 0
        if sev == "high":
            return 1
        return 2
    if debt_class == "open_operational_debt":
        if source == "issue" or action_type == ACTION_OPEN_ISSUE:
            return 0
        if action_type in (ACTION_WORK_ORDER_BREACHED, ACTION_WORK_ORDER_NEAR_BREACH):
            return 1
        if source == "work_order" or action_type == ACTION_OPEN_WORK_ORDER:
            return 2
        if source == "requirement" or action_type in (
            ACTION_MISSING_DOCUMENT,
            ACTION_OVERDUE_COMPLIANCE,
            ACTION_CERT_EXPIRING_SOON,
        ):
            return 3
        return 4
    if debt_class == "time_bound_reminder":
        if source == "approval" or action_type == ACTION_PENDING_APPROVAL:
            return 1
        return 0
    return 0


def _urgency_tier(task: Dict[str, Any]) -> int:
    u = str(task.get("urgency") or task.get("urgency_level") or "").lower()
    if u in ("critical", "overdue"):
        return 0
    if u == "high":
        return 1
    if u in ("due_soon", "medium"):
        return 2
    return 3


def attention_rank_explanation(task: Dict[str, Any]) -> Dict[str, Any]:
    debt_class = attention_class_for_task(task)
    key = today_attention_sort_key(task)
    return {
        "class": debt_class,
        "precedence_rank": ATTENTION_PRECEDENCE.get(debt_class, 99),
        "sub_rank": _sub_rank_within_class(task, debt_class),
        "urgency_tier": _urgency_tier(task),
        "impact_score": int(task.get("impact_score") or 0),
        "sort_key": list(key),
    }


def today_attention_sort_key(task: Dict[str, Any]) -> Tuple[Any, ...]:
    """
    Sort key for Today/unified task lists (lower tuple = appears earlier / higher attention).
    """
    debt_class = attention_class_for_task(task)
    precedence = ATTENTION_PRECEDENCE.get(debt_class, 99)
    sub = _sub_rank_within_class(task, debt_class)
    urgency = _urgency_tier(task)
    impact = -int(task.get("impact_score") or 0)
    title = str(task.get("title") or "")
    tid = str(task.get("id") or "")
    return (precedence, sub, urgency, impact, title, tid)
