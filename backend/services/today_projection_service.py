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

See also: services/client_task_state_service.apply_task_action (snooze | dismiss | reviewed | restore).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

def _documents_upload_path(property_id: Optional[str], requirement_id: Optional[str]) -> str:
    q = {}
    if property_id:
        q["property_id"] = property_id
    if requirement_id:
        q["requirement_id"] = requirement_id
    q["focus"] = "upload"
    return f"/documents?{urlencode(q)}" if q else "/documents?focus=upload"


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
    action_type = (meta.get("action_type") or "").strip()
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
                "id": "view_issue",
                "label": "View issue",
                "navigate": f"/operations/issues/{iid}",
            }
        )
        out.append(
            {
                "id": "create_maintenance_job",
                "label": "Create maintenance job",
                "issue_id": iid,
                "hint": "From issue detail you can open a work order when ready.",
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


def enrich_task_for_today(task: Dict[str, Any]) -> Dict[str, Any]:
    """Mutates a shallow copy: adds business_actions + visibility_actions."""
    t = dict(task)
    t["business_actions"] = build_business_actions_for_task(task)
    t["visibility_actions"] = build_visibility_actions_for_task(task)
    return t


def enrich_task_bucket(tasks: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not tasks:
        return []
    return [enrich_task_for_today(t) for t in tasks]


def build_today_payload_from_unified(full: Dict[str, Any]) -> Dict[str, Any]:
    """Same shape as GET /client/tasks with enriched tasks + flat items list."""
    tasks_root = full.get("tasks") or {}
    enriched_tasks = {
        "urgent": enrich_task_bucket(tasks_root.get("urgent")),
        "upcoming": enrich_task_bucket(tasks_root.get("upcoming")),
        "in_progress": enrich_task_bucket(tasks_root.get("in_progress")),
        "recently_completed": enrich_task_bucket(tasks_root.get("recently_completed")),
        "snoozed": enrich_task_bucket(tasks_root.get("snoozed")),
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
    return {
        "tasks": enriched_tasks,
        "summary": full.get("summary") or {},
        "freshness": full.get("freshness") or {},
        "activity_feed": full.get("activity_feed") or [],
        "spend_this_month": full.get("spend_this_month"),
        "items": flat,
    }
