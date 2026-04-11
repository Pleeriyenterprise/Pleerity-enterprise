"""
Client Command Centre — persistent per-user task overrides (snooze, dismiss, mark done) and
append-only activity for history / habit metrics. Does not mutate underlying compliance or
operations entities; overlays only affect inbox presentation until restore or snooze expiry.
"""
from __future__ import annotations

import re
import uuid
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from database import database
from models import AuditAction
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

COLLECTION_OVERRIDES = "client_task_overrides"
COLLECTION_ACTIVITY = "client_task_activity_log"

OVERRIDE_SNOOZE = "snooze"
OVERRIDE_DISMISS = "dismiss"
OVERRIDE_DONE = "done"
OVERRIDE_REVIEWED = "reviewed"

ACTION_SNOOZE = "snooze"
ACTION_DISMISS = "dismiss"
ACTION_DONE = "done"
ACTION_REVIEWED = "reviewed"
ACTION_RESTORE = "restore"

# Stable ids from unified_tasks_service: "requirement:uuid", "risk_signal:...", etc.
_TASK_ID_RE = re.compile(r"^[a-z_]+:[A-Za-z0-9_-]{1,128}$")


def is_valid_task_id(task_id: str) -> bool:
    if not task_id or len(task_id) > 180:
        return False
    return bool(_TASK_ID_RE.match(task_id.strip()))


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


async def _log_activity(
    client_id: str,
    task_id: str,
    action: str,
    actor_id: Optional[str],
    task_scope_user_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    db = database.get_db()
    doc = {
        "event_id": str(uuid.uuid4()),
        "client_id": client_id,
        "task_id": task_id,
        "action": action,
        "created_at": _now(),
        "actor_portal_user_id": actor_id,
        "task_scope_user_id": task_scope_user_id,
        "extra": extra or {},
    }
    await db[COLLECTION_ACTIVITY].insert_one(doc)


def _scope_token(portal_user_id: Optional[str]) -> str:
    token = (portal_user_id or "").strip()
    return token or "__client__"


def _scoped_task_id(task_id: str, portal_user_id: Optional[str]) -> str:
    return f"{_scope_token(portal_user_id)}::{task_id}"


def _raw_task_id_from_doc(row: Dict[str, Any]) -> str:
    raw = (row.get("raw_task_id") or "").strip()
    if raw:
        return raw
    scoped = str(row.get("task_id") or "")
    if "::" in scoped:
        return scoped.split("::", 1)[1]
    return scoped


async def apply_task_action(
    client_id: str,
    task_id: str,
    action: str,
    *,
    portal_user_id: Optional[str] = None,
    snooze_days: Optional[int] = None,
    title_snapshot: Optional[str] = None,
    source_type_snapshot: Optional[str] = None,
    property_id_snapshot: Optional[str] = None,
    dismiss_reason: Optional[str] = None,
    business_outcome: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Apply snooze, dismiss (reason required), done (legacy inbox hide), reviewed (preferred triage hide), or restore.
    Writes override row (except restore) and activity log. Does not mutate compliance or operations truth.
    """
    if not is_valid_task_id(task_id):
        raise ValueError("Invalid task_id")
    action = (action or "").strip().lower()
    if action not in (ACTION_SNOOZE, ACTION_DISMISS, ACTION_DONE, ACTION_REVIEWED, ACTION_RESTORE):
        raise ValueError("action must be snooze, dismiss, done, reviewed, or restore")

    db = database.get_db()
    coll = db[COLLECTION_OVERRIDES]
    scope = _scope_token(portal_user_id)
    scoped_task_id = _scoped_task_id(task_id, portal_user_id)

    if action == ACTION_RESTORE:
        await coll.delete_one({"client_id": client_id, "task_id": scoped_task_id})
        await _log_activity(
            client_id, task_id, ACTION_RESTORE, portal_user_id,
            task_scope_user_id=scope,
            extra={},
        )
        await create_audit_log(
            action=AuditAction.CLIENT_TASK_RESTORED,
            actor_id=portal_user_id,
            client_id=client_id,
            resource_type="client_task",
            resource_id=task_id,
            metadata={
                "task_id": task_id,
                "task_scope_user_id": scope,
                "inbox_action_summary": "Today inbox visibility: item restored to Today lists (does not change underlying work)",
            },
        )
        return {"ok": True, "task_id": task_id, "state": None}

    now = _now()
    snap = {
        "title": (title_snapshot or "")[:500] or None,
        "source_type": source_type_snapshot,
        "property_id": property_id_snapshot,
    }

    if action == ACTION_SNOOZE:
        days = int(snooze_days) if snooze_days is not None else 1
        days = max(1, min(days, 30))
        until = now + timedelta(days=days)
        doc = {
            "client_id": client_id,
            "task_id": scoped_task_id,
            "raw_task_id": task_id,
            "task_scope_user_id": scope,
            "override": OVERRIDE_SNOOZE,
            "snoozed_until": until,
            "recorded_at": now,
            "actor_portal_user_id": portal_user_id,
            "last_user_action_at": now,
            "last_user_action_by": portal_user_id,
            "snapshot": snap,
            "dismiss_reason": None,
            "task_status": OVERRIDE_SNOOZE,
        }
        await coll.update_one(
            {"client_id": client_id, "task_id": scoped_task_id},
            {"$set": doc},
            upsert=True,
        )
        await _log_activity(
            client_id,
            task_id,
            ACTION_SNOOZE,
            portal_user_id,
            task_scope_user_id=scope,
            extra={
                "snooze_days": days,
                "snoozed_until": until.isoformat(),
                "title": (title_snapshot or "")[:500] or None,
                "source_type": source_type_snapshot,
                "business_outcome": business_outcome or "task_snoozed",
            },
        )
        await create_audit_log(
            action=AuditAction.CLIENT_TASK_SNOOZED,
            actor_id=portal_user_id,
            client_id=client_id,
            resource_type="client_task",
            resource_id=task_id,
            metadata={
                "task_id": task_id,
                "task_scope_user_id": scope,
                "snooze_days": days,
                "snoozed_until": until.isoformat(),
                "business_outcome": business_outcome or "task_snoozed",
                "inbox_action_summary": (
                    f"Today inbox visibility: hidden from Today until {until.isoformat()} "
                    f"({days} day(s)); requirements, jobs, issues, and documents unchanged"
                ),
            },
        )
        return {"ok": True, "task_id": task_id, "state": OVERRIDE_SNOOZE, "snoozed_until": until.isoformat()}

    if action == ACTION_DISMISS:
        dr = (dismiss_reason or "").strip()
        if len(dr) < 3:
            if os.getenv("CLIENT_TASK_DISMISS_ALLOW_LEGACY_EMPTY", "").strip().lower() in ("1", "true", "yes"):
                dr = (
                    os.getenv("CLIENT_TASK_DISMISS_LEGACY_DEFAULT_REASON", "").strip()
                    or "Legacy integration dismiss (no reason supplied — enable CLIENT_TASK_DISMISS_ALLOW_LEGACY_EMPTY only during migration)"
                )
            else:
                raise ValueError(
                    "Hide from Today requires a reason (at least 3 characters), stored for audit. "
                    "This does not upload documents, satisfy requirements, close jobs, or resolve issues."
                )

    # dismiss | done | reviewed
    if action == ACTION_DISMISS:
        override = OVERRIDE_DISMISS
    elif action == ACTION_REVIEWED:
        override = OVERRIDE_REVIEWED
    else:
        override = OVERRIDE_DONE
    doc = {
        "client_id": client_id,
        "task_id": scoped_task_id,
        "raw_task_id": task_id,
        "task_scope_user_id": scope,
        "override": override,
        "snoozed_until": None,
        "recorded_at": now,
        "actor_portal_user_id": portal_user_id,
        "last_user_action_at": now,
        "last_user_action_by": portal_user_id,
        "snapshot": snap,
        "dismiss_reason": (dismiss_reason or "").strip()[:2000] if action == ACTION_DISMISS else None,
        "task_status": override,
    }
    await coll.update_one(
        {"client_id": client_id, "task_id": scoped_task_id},
        {"$set": doc},
        upsert=True,
    )
    act_extra: Dict[str, Any] = {
        "title": (title_snapshot or "")[:500] or None,
        "source_type": source_type_snapshot,
        "business_outcome": business_outcome
        or (
            "task_dismissed"
            if action == ACTION_DISMISS
            else ("task_marked_reviewed" if action == ACTION_REVIEWED else "inbox_done_legacy")
        ),
    }
    if action == ACTION_DISMISS:
        act_extra["dismiss_reason"] = (dismiss_reason or "").strip()[:2000]
    await _log_activity(
        client_id,
        task_id,
        action,
        portal_user_id,
        task_scope_user_id=scope,
        extra=act_extra,
    )
    if action == ACTION_DISMISS:
        audit_action = AuditAction.CLIENT_TASK_DISMISSED
    elif action == ACTION_REVIEWED:
        audit_action = AuditAction.CLIENT_TASK_MARKED_REVIEWED
    else:
        audit_action = AuditAction.CLIENT_TASK_MARKED_DONE
    audit_meta: Dict[str, Any] = {
        "task_id": task_id,
        "task_scope_user_id": scope,
        "override": override,
        "business_outcome": act_extra.get("business_outcome"),
    }
    if action == ACTION_DISMISS:
        audit_meta["dismiss_reason"] = (dismiss_reason or "").strip()[:2000]
    if action == ACTION_DISMISS:
        audit_meta["inbox_action_summary"] = (
            "Today inbox visibility: hidden from Today with audited reason—"
            "does not upload documents, satisfy requirements, close jobs, resolve issues, or approve invoices"
        )
    elif action == ACTION_REVIEWED:
        audit_meta["inbox_action_summary"] = (
            "Today inbox visibility: marked reviewed in Today only—underlying requirement/job/issue/document unchanged"
        )
    else:
        audit_meta["inbox_action_summary"] = (
            "Today inbox visibility: legacy done flag in inbox—underlying records unchanged unless completed elsewhere"
        )
    await create_audit_log(
        action=audit_action,
        actor_id=portal_user_id,
        client_id=client_id,
        resource_type="client_task",
        resource_id=task_id,
        metadata=audit_meta,
    )
    return {"ok": True, "task_id": task_id, "state": override}


async def load_active_overrides(client_id: str, portal_user_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Return task_id -> override doc, dropping expired snoozes (and deleting them)."""
    db = database.get_db()
    coll = db[COLLECTION_OVERRIDES]
    now = _now()
    q: Dict[str, Any] = {"client_id": client_id}
    if portal_user_id is not None:
        q["task_scope_user_id"] = _scope_token(portal_user_id)
    cursor = coll.find(q)
    docs = await cursor.to_list(length=500)
    out: Dict[str, Dict[str, Any]] = {}
    for d in docs:
        d.pop("_id", None)
        tid = _raw_task_id_from_doc(d)
        if not tid:
            continue
        if d.get("override") == OVERRIDE_SNOOZE:
            until = _parse_dt(d.get("snoozed_until"))
            if until and until <= now:
                await coll.delete_one({"client_id": client_id, "task_id": d.get("task_id")})
                logger.debug("Expired snooze removed task_id=%s client=%s", tid, client_id)
                continue
        out[tid] = d
    return out


def partition_tasks_by_override(
    tasks: List[Dict[str, Any]],
    overrides: Dict[str, Dict[str, Any]],
    now: datetime,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Split into visible (for urgent/upcoming/in_progress) and snoozed (still active snooze).
    Dismissed/done tasks are omitted from both.
    """
    visible: List[Dict[str, Any]] = []
    snoozed: List[Dict[str, Any]] = []
    for t in tasks:
        tid = t.get("id")
        if not tid:
            continue
        o = overrides.get(tid)
        if not o:
            visible.append(t)
            continue
        kind = o.get("override")
        if kind == OVERRIDE_SNOOZE:
            until = _parse_dt(o.get("snoozed_until"))
            if until and until > now:
                sn = dict(t)
                sn["user_override"] = "snooze"
                sn["snoozed_until"] = until.isoformat()
                sn["section"] = "snoozed"
                snoozed.append(sn)
            else:
                visible.append(t)
        elif kind in (OVERRIDE_DISMISS, OVERRIDE_DONE, OVERRIDE_REVIEWED):
            continue
        else:
            visible.append(t)
    return visible, snoozed


async def count_activity_since(
    client_id: str,
    since: datetime,
    actions: List[str],
    portal_user_id: Optional[str] = None,
) -> int:
    db = database.get_db()
    q: Dict[str, Any] = {
        "client_id": client_id,
        "action": {"$in": actions},
        "created_at": {"$gte": since},
    }
    if portal_user_id is not None:
        q["task_scope_user_id"] = _scope_token(portal_user_id)
    # Normalize legacy action names in query
    expanded = list(actions)
    if ACTION_DONE in actions and ACTION_REVIEWED not in actions:
        expanded.append(ACTION_REVIEWED)
    if ACTION_REVIEWED in actions and ACTION_DONE not in actions:
        expanded.append(ACTION_DONE)
    q["action"] = {"$in": list(dict.fromkeys(expanded))}
    return await db[COLLECTION_ACTIVITY].count_documents(q)


async def list_hidden_inbox_items(
    client_id: str,
    limit: int = 40,
    portal_user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Dismissed or inbox-done tasks still in overrides — user can restore to open lists."""
    db = database.get_db()
    coll = db[COLLECTION_OVERRIDES]
    q: Dict[str, Any] = {
        "client_id": client_id,
        "override": {"$in": [OVERRIDE_DISMISS, OVERRIDE_DONE, OVERRIDE_REVIEWED]},
    }
    if portal_user_id is not None:
        q["task_scope_user_id"] = _scope_token(portal_user_id)
    cursor = (
        coll.find(
            q,
            {"_id": 0, "task_id": 1, "raw_task_id": 1, "override": 1, "snapshot": 1, "recorded_at": 1, "dismiss_reason": 1},
        )
        .sort("recorded_at", -1)
        .limit(min(limit, 100))
    )
    rows = await cursor.to_list(length=min(limit, 100))
    out: List[Dict[str, Any]] = []
    for r in rows:
        tid = _raw_task_id_from_doc(r)
        if not tid:
            continue
        snap = r.get("snapshot") or {}
        ra = r.get("recorded_at")
        if hasattr(ra, "isoformat"):
            ra = ra.isoformat()
        out.append(
            {
                "id": tid,
                "task_id": tid,
                "user_override": r.get("override"),
                "title": snap.get("title") or tid,
                "source_type": snap.get("source_type"),
                "property_id": snap.get("property_id"),
                "hidden_at": ra,
                "dismiss_reason": r.get("dismiss_reason"),
            }
        )
    return out


def _format_activity_action_label(action: str, extra: Optional[Dict[str, Any]] = None) -> str:
    """Human-readable Today inbox visibility label (not domain completion)."""
    a = (action or "").strip().lower()
    ex = extra or {}
    if a == ACTION_SNOOZE:
        until = ex.get("snoozed_until")
        if until:
            return f"Today item snoozed (hidden until {until})"
        return "Today item snoozed"
    if a == ACTION_DISMISS:
        return "Today item hidden from Today (dismissed)"
    if a == ACTION_REVIEWED:
        return "Today item marked reviewed in Today only"
    if a == ACTION_DONE:
        return "Today item marked done in inbox (legacy visibility)"
    if a == ACTION_RESTORE:
        return "Today item restored to Today"
    return f"Today inbox: {a or 'activity'}"


async def list_recent_activity(
    client_id: str,
    limit: int = 25,
    portal_user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Recent inbox actions for Phase 2 history strip (newest first)."""
    db = database.get_db()
    q: Dict[str, Any] = {"client_id": client_id}
    if portal_user_id is not None:
        q["task_scope_user_id"] = _scope_token(portal_user_id)
    cursor = (
        db[COLLECTION_ACTIVITY]
        .find(q, {"_id": 0})
        .sort("created_at", -1)
        .limit(min(limit, 100))
    )
    rows = await cursor.to_list(length=min(limit, 100))
    for r in rows:
        ca = r.get("created_at")
        if hasattr(ca, "isoformat"):
            r["created_at"] = ca.isoformat()
        r["action_label"] = _format_activity_action_label(r.get("action"), r.get("extra"))
    return rows


def merge_user_acknowledgements_into_recent(
    system_recent: List[Dict[str, Any]],
    activity_rows: List[Dict[str, Any]],
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Prepend synthetic 'completed' items from dismiss/done activity for the Recently completed section."""
    synthetic: List[Dict[str, Any]] = []
    for row in activity_rows:
        act = (row.get("action") or "").lower()
        if act not in (ACTION_DISMISS, ACTION_DONE, ACTION_REVIEWED):
            continue
        tid = row.get("task_id") or ""
        if not tid:
            continue
        ca = row.get("created_at")
        ca_s = ca.isoformat() if hasattr(ca, "isoformat") else str(ca)
        extra = row.get("extra") or {}
        title_from_log = extra.get("title")
        if act == ACTION_DISMISS:
            label = title_from_log or "Hidden from Today (dismissed)"
        elif act == ACTION_REVIEWED:
            label = title_from_log or "Marked reviewed in Today only"
        else:
            label = title_from_log or "Marked done in Today inbox (legacy)"
        synthetic.append({
            "id": f"user_ack:{tid}:{ca_s}",
            "source_type": "inbox_acknowledgement",
            "source_id": tid,
            "source_entity_type": "inbox_acknowledgement",
            "source_entity_id": tid,
            "action_context_type": "inbox_triage",
            "primary_recommended_action": "Restore or read help",
            "title": label,
            "description": "This was a Today visibility action only—it does not upload documents, satisfy requirements, close jobs, resolve issues, or change compliance scores. Restore from Today → Snoozed or Hidden, or open Help for how inbox visibility works.",
            "property_id": None,
            "property_label": None,
            "urgency_level": "low",
            "due_date": None,
            "overdue_days": None,
            "impact_label": "Inbox",
            "impact_score": 1,
            "status": "completed",
            "section": "recently_completed",
            "primary_action_type": "restore_hint",
            "primary_action_label": "How Today inbox visibility works",
            "primary_action_url": "/help?article=how-inbox-visibility-works-today",
            "inline_action_supported": False,
            "metadata": {"user_action": act, "task_id": tid, "business_outcome": (extra.get("business_outcome") or "inbox_triage")},
            "freshness_timestamp": ca_s,
            "created_at": ca_s,
            "updated_at": ca_s,
            "filter_tags": [],
        })
    merged = synthetic[:8] + list(system_recent)
    merged.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
    return merged[:limit]


async def ensure_client_task_indexes() -> None:
    """
    Idempotent indexes for Command Centre task overrides and activity log.
    Called from API startup and from scripts.ensure_services_indexes.
    """
    db = database.get_db()
    overrides = db[COLLECTION_OVERRIDES]
    activity = db[COLLECTION_ACTIVITY]
    await overrides.create_index(
        [("client_id", 1), ("task_id", 1)],
        unique=True,
        name="idx_client_task_overrides_client_task",
    )
    await activity.create_index(
        [("client_id", 1), ("created_at", -1)],
        name="idx_client_task_activity_client_created",
    )
    await activity.create_index("event_id", unique=True, name="idx_client_task_activity_event_id")
