"""
Today inbox projection: attach business_actions vs visibility_actions to unified task DTOs.

Keep this split aligned with docs/CLIENT_PORTAL_WORKFLOW_MATRIX.md (Today page).

Business actions (build_business_actions_for_task):
    Domain CTAs only: navigate to real workflows or carry IDs for POSTs the UI performs elsewhere
    (e.g. upload deep-link to /documents?…&focus=upload, create compliance job, view requirement/issue/job).
    These may open flows that eventually change compliance/operations data; they are not “inbox-only”.

Visibility actions (build_visibility_actions_for_task):
    Snooze 1d / 7d, mark reviewed, dismiss — each maps to POST /api/today/items/{id}/snooze|mark-reviewed|dismiss
    and apply_task_action on client_task_overrides. They do not alter requirement status, jobs, or documents.

Restore:
    Dismissed/hidden tasks appear under the hidden bucket with a synthetic visibility action "restore"
    (build_today_payload_from_unified). POST /api/today/items/{id}/restore clears the override so the task
    can surface again in active sections. Same non-mutation rule as other visibility actions.

Quality (Today-only extensions on enriched copies):
    - urgency: overdue | due_soon | on_track (calendar / overdue_days / cert-expiring / SLA-style action_types;
      not inferred from generic urgency_level alone — avoids over-classifying “due soon”).
    - title: action-oriented where we can derive it (esp. requirement_action_phrase).
    - business_actions: capped (max 2), ordered with the first marked primary: true.
    - Open sections: dedupe by (property_id, requirement_id); drop tasks with no workflow affordance.

See also: services/client_task_state_service.apply_task_action (snooze | dismiss | reviewed | restore).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

from presentation.label_service import requirement_action_phrase, today_inbox_action_title
from services.client_priority_stream import (
    ACTION_CERT_EXPIRING_SOON,
    ACTION_PENDING_APPROVAL,
    ACTION_WORK_ORDER_BREACHED,
    ACTION_WORK_ORDER_NEAR_BREACH,
)

logger = logging.getLogger(__name__)


def _documents_upload_path(property_id: Optional[str], requirement_id: Optional[str]) -> str:
    q = {}
    if property_id:
        q["property_id"] = property_id
    if requirement_id:
        q["requirement_id"] = requirement_id
    q["focus"] = "upload"
    return f"/documents?{urlencode(q)}" if q else "/documents?focus=upload"


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def build_visibility_actions_for_task(task: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Inbox-only actions; delegated to POST /api/today/items/{id}/…"""
    tid = task.get("id") or ""
    return [
        {"id": "snooze_1", "label": "Snooze 1 day", "task_id": tid, "snooze_days": 1},
        {"id": "snooze_7", "label": "Snooze 7 days", "task_id": tid, "snooze_days": 7},
        {"id": "mark_reviewed", "label": "Mark reviewed", "task_id": tid},
        {"id": "dismiss", "label": "Dismiss from inbox", "task_id": tid, "requires_reason": True},
    ]


def build_business_actions_for_task(task: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Domain actions that navigate or trigger real workflows.
    Each item: id, label, and one of: navigate, requirement_id, risk_signal_id, issue_id, work_order_id, approval.
    """
    meta = task.get("metadata") or {}
    source_type = (task.get("source_type") or "").strip()
    prop_id = task.get("property_id")
    source_entity_id = task.get("source_entity_id") or task.get("source_id")

    out: List[Dict[str, Any]] = []

    if source_type == "requirement" and source_entity_id:
        rid = str(source_entity_id)
        out.append(
            {
                "id": "upload_certificate",
                "label": "Upload certificate",
                "navigate": _documents_upload_path(prop_id, rid),
            }
        )
        ce = meta.get("compliance_execution_booking") or {}
        if ce.get("eligible"):
            out.append(
                {
                    "id": "create_compliance_work_order",
                    "label": "Create compliance job",
                    "requirement_id": rid,
                    "property_id": ce.get("property_id") or prop_id,
                    "requirement_code": ce.get("requirement_code"),
                    "compliance_purpose": ce.get("compliance_purpose") or "inspection",
                    "compliance_generated_from": ce.get("compliance_generated_from") or "requirement",
                }
            )
        out.append(
            {
                "id": "view_requirement",
                "label": "View requirement",
                "navigate": f"/requirements?view_requirement={rid}",
            }
        )

    if source_type == "risk_signal" and source_entity_id:
        sid = str(source_entity_id)
        out.append(
            {
                "id": "review_risk_signal",
                "label": "Review risk signal",
                "navigate": f"/operations/risk-signals?signal_id={sid}",
            }
        )

    if source_type == "issue" and source_entity_id:
        iid = str(source_entity_id)
        out.append(
            {
                "id": "create_maintenance_job",
                "label": "Create maintenance job",
                "issue_id": iid,
                "hint": "From issue detail you can open a work order when ready.",
            }
        )
        out.append(
            {
                "id": "view_issue",
                "label": "View issue",
                "navigate": f"/operations/issues/{iid}",
            }
        )

    if source_type == "work_order" and source_entity_id:
        wid = str(source_entity_id)
        out.append(
            {
                "id": "view_job",
                "label": "View job",
                "navigate": f"/operations/jobs/{wid}",
            }
        )

    if source_type == "approval" and source_entity_id:
        inv = str(source_entity_id)
        out.append(
            {
                "id": "view_approval",
                "label": "View approval",
                "navigate": f"/operations/approvals?invoice_id={inv}",
            }
        )

    # Fallback: primary URL from engine
    if not out and task.get("primary_action_url"):
        out.append(
            {
                "id": "open_primary",
                "label": task.get("primary_action_label") or "Open",
                "navigate": task.get("primary_action_url"),
            }
        )

    return out


# Lower = earlier in list (more “primary” workflow). view_* / review-only last.
_BUSINESS_ACTION_ORDER: Dict[str, int] = {
    "create_compliance_work_order": 0,
    "upload_certificate": 1,
    "create_maintenance_job": 2,
    "open_primary": 3,
    "review_risk_signal": 4,
    "view_job": 8,
    "view_issue": 8,
    "view_approval": 8,
    "view_requirement": 20,
}


def cap_and_order_business_actions(actions: List[Dict[str, Any]], max_actions: int = 2) -> List[Dict[str, Any]]:
    """Keep at most max_actions, prefer workflow-first CTAs; first item gets primary: True."""
    if not actions:
        return []
    ranked = sorted(
        actions,
        key=lambda a: (_BUSINESS_ACTION_ORDER.get(str(a.get("id") or ""), 6), a.get("label") or ""),
    )
    capped = ranked[: max(1, min(int(max_actions), 2))]
    out: List[Dict[str, Any]] = []
    for i, raw in enumerate(capped):
        a = dict(raw)
        a["primary"] = i == 0
        out.append(a)
    return out


def derive_today_urgency(task: Dict[str, Any], now: datetime) -> str:
    """
    Coarse band for Today UI: overdue | due_soon | on_track.

    due_soon requires a calendar horizon (due within 7d), explicit cert-expiring-soon, or an SLA/billing
    action_type — not bare urgency_level (critical/high), so open jobs and risks are not all “due soon”.
    """
    od = task.get("overdue_days")
    try:
        if od is not None and int(od) > 0:
            return "overdue"
    except (TypeError, ValueError):
        pass

    due_at = task.get("due_date")
    d = _parse_dt(due_at)
    if d:
        today = now.date()
        due_date = d.date()
        if due_date < today:
            return "overdue"
        if due_date >= today:
            if (due_date - today).days <= 7:
                return "due_soon"
        # Future due beyond 7d
        if due_date > today + timedelta(days=7):
            return "on_track"

    meta = task.get("metadata") or {}
    at = (meta.get("action_type") or "").strip()
    if at == ACTION_CERT_EXPIRING_SOON:
        return "due_soon"

    # Operational / billing time pressure without a parsed due_date (do not use urgency_level alone).
    if at in (
        ACTION_WORK_ORDER_BREACHED,
        ACTION_WORK_ORDER_NEAR_BREACH,
        ACTION_PENDING_APPROVAL,
    ):
        return "due_soon"

    return "on_track"


_PASSIVE_HINTS = (
    "missing",
    " not ",
    "no certificate",
    "no document",
    "expired",
    "required:",
    "non-compliant",
    "non compliant",
    "breach",
    "overdue —",
    "overdue -",
)


def _title_looks_problem_focused(title: str) -> bool:
    low = (title or "").strip().lower()
    if not low:
        return False
    return any(h in low for h in _PASSIVE_HINTS)


def today_action_oriented_title(task: Dict[str, Any]) -> Tuple[Optional[str], bool]:
    """
    Returns (new_title_or_none, set_today_action_flag).
    When flag True, clients should prefer title verbatim (see metadata.today_action_title).
    """
    meta = task.get("metadata") or {}
    st = (task.get("source_type") or "").strip()
    code = meta.get("requirement_code")

    if st == "requirement" and code:
        phrase = requirement_action_phrase(code)
        if phrase:
            return phrase, True

    if st == "requirement":
        pl = (task.get("primary_action_label") or "").strip()
        raw = (task.get("title") or "").strip()
        if pl and pl.lower() not in ("view", "open") and len(pl) > 3:
            return pl, True
        if raw and not _title_looks_problem_focused(raw):
            return None, False
        if pl:
            return pl, True
        return None, False

    inbox_title = today_inbox_action_title(st)
    if inbox_title:
        return inbox_title, True

    if st == "tenant_request":
        return None, False

    if st == "priority_action":
        raw = (task.get("title") or "").strip()
        if _title_looks_problem_focused(raw):
            alt = (task.get("primary_action_label") or task.get("primary_recommended_action") or "").strip()
            if alt:
                return alt, True
        return None, False

    raw = (task.get("title") or "").strip()
    if _title_looks_problem_focused(raw):
        alt = (task.get("primary_action_label") or "").strip()
        if alt:
            return alt, True

    return None, False


def _requirement_dedupe_key(task: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """(property_id, requirement_id) when task ties to a requirement row; else None."""
    st = (task.get("source_type") or "").strip()
    pid = str(task.get("property_id") or "").strip()
    if st == "requirement" and task.get("source_entity_id"):
        return (pid, str(task["source_entity_id"]))
    if st == "tenant_request" and task.get("requirement_id"):
        return (pid, str(task["requirement_id"]))
    return None


def dedupe_tasks_by_requirement(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep the highest impact_score task per (property_id, requirement_id)."""
    best: Dict[Tuple[str, str], Dict[str, Any]] = {}
    other: List[Dict[str, Any]] = []
    for t in tasks:
        k = _requirement_dedupe_key(t)
        if k is None:
            other.append(t)
            continue
        cur = best.get(k)
        if cur is None or int(t.get("impact_score") or 0) > int(cur.get("impact_score") or 0):
            best[k] = t
    return other + list(best.values())


def today_task_is_actionable(task: Dict[str, Any]) -> bool:
    """Has at least one business action or a primary deep link from the unified engine."""
    acts = task.get("business_actions") or []
    if acts:
        return True
    return bool((task.get("primary_action_url") or "").strip())


def enrich_task_for_today(task: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    """Shallow copy: business_actions (capped), visibility_actions, urgency, title polish, metadata flag."""
    t = dict(task)
    meta = dict(t.get("metadata") or {})

    raw_actions = build_business_actions_for_task(t)
    t["business_actions"] = cap_and_order_business_actions(raw_actions, max_actions=2)
    t["visibility_actions"] = build_visibility_actions_for_task(t)
    t["urgency"] = derive_today_urgency(t, now)

    new_title, action_flag = today_action_oriented_title(t)
    if new_title:
        t["title"] = new_title
    if action_flag:
        meta["today_action_title"] = True

    t["metadata"] = meta
    return t


def enrich_task_bucket(
    tasks: Optional[List[Dict[str, Any]]],
    now: datetime,
    *,
    filter_non_actionable: bool = False,
) -> List[Dict[str, Any]]:
    if not tasks:
        return []
    enriched = [enrich_task_for_today(dict(x), now) for x in tasks]
    enriched = dedupe_tasks_by_requirement(enriched)
    if filter_non_actionable:
        before = len(enriched)
        enriched = [x for x in enriched if today_task_is_actionable(x)]
        dropped = before - len(enriched)
        if dropped:
            logger.debug("today_projection: dropped %s non-actionable tasks from open bucket", dropped)
    enriched.sort(
        key=lambda x: (
            -int(x.get("impact_score") or 0),
            (x.get("urgency_level") or "") not in ("critical", "high"),
            x.get("title") or "",
        )
    )
    return enriched


def build_today_payload_from_unified(full: Dict[str, Any]) -> Dict[str, Any]:
    """Same shape as GET /client/tasks with enriched tasks + flat items list."""
    now = datetime.now(timezone.utc)
    tasks_root = full.get("tasks") or {}
    enriched_tasks = {
        "urgent": enrich_task_bucket(tasks_root.get("urgent"), now, filter_non_actionable=True),
        "upcoming": enrich_task_bucket(tasks_root.get("upcoming"), now, filter_non_actionable=True),
        "in_progress": enrich_task_bucket(tasks_root.get("in_progress"), now, filter_non_actionable=True),
        "recently_completed": enrich_task_bucket(tasks_root.get("recently_completed"), now, filter_non_actionable=False),
        "snoozed": enrich_task_bucket(tasks_root.get("snoozed"), now, filter_non_actionable=False),
        "hidden": tasks_root.get("hidden") or [],
    }
    flat: List[Dict[str, Any]] = []
    for section, key in (
        ("urgent", "urgent"),
        ("upcoming", "upcoming"),
        ("in_progress", "in_progress"),
        ("snoozed", "snoozed"),
    ):
        for t in enriched_tasks.get(key) or []:
            tid = t.get("id")
            if not tid:
                continue
            entry = {
                "id": tid,
                "section": section,
                "title": t.get("title"),
                "description": t.get("description"),
                "property_id": t.get("property_id"),
                "task": t,
                "business_actions": t.get("business_actions") or [],
                "visibility_actions": t.get("visibility_actions") or [],
            }
            flat.append(entry)
    for h in enriched_tasks.get("hidden") or []:
        tid = h.get("task_id") or h.get("id")
        if not tid:
            continue
        flat.append(
            {
                "id": tid,
                "section": "hidden",
                "title": h.get("title"),
                "description": None,
                "property_id": h.get("property_id"),
                "task": h,
                "business_actions": [],
                "visibility_actions": [
                    {"id": "restore", "label": "Restore to inbox", "task_id": tid},
                ],
            }
        )
    summary = dict(full.get("summary") or {})
    summary["urgent_count"] = len(enriched_tasks["urgent"])
    summary["upcoming_count"] = len(enriched_tasks["upcoming"])
    summary["in_progress_count"] = len(enriched_tasks["in_progress"])
    summary["recently_completed_count"] = len(enriched_tasks["recently_completed"])
    summary["snoozed_count"] = len(enriched_tasks["snoozed"])
    summary["hidden_count"] = len(enriched_tasks["hidden"])
    habit = dict(summary.get("habit") or {})
    habit["urgent_open_total"] = len(enriched_tasks["urgent"])
    summary["habit"] = habit

    return {
        "tasks": enriched_tasks,
        "summary": summary,
        "freshness": full.get("freshness") or {},
        "activity_feed": full.get("activity_feed") or [],
        "spend_this_month": full.get("spend_this_month"),
        "items": flat,
    }
