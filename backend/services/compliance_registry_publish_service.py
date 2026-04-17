"""
Publish queue + active published snapshot for the compliance requirement registry.

Drafts remain in ``compliance_requirement_registry_drafts`` until a queue item is **published**;
``materialize_requirements_for_property`` and plan preview load the active snapshot and pass it into
``build_requirement_plan_for_property(..., published_registry_entries=...)``.

**Published history (append-only):** Each activation (queue publish or Owner revert) appends a row to
``compliance_requirement_registry_published_history`` with ``published_line_version`` matching the
singleton ``version`` at that moment and a full ``entries`` snapshot.

**Revert:** Owner may ``revert_active_published_to_line_version`` to copy a prior history row's
``entries`` onto the active singleton; ``version`` increments again and a new **revert** history row
is appended (audit chain stays linear).

**Rematerialisation:** Changing the active snapshot (publish or revert) does **not** enqueue a global
re-materialise of all properties. Rows refresh when ``materialize_requirements_for_property`` (or the
client ``requirements/sync`` path you use operationally) runs per property — same as a normal publish.
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.compliance_registry_admin_service import COLLECTION as DRAFTS_COLLECTION

COLLECTION_QUEUE = "compliance_registry_publish_queue"
COLLECTION_PUBLISHED = "compliance_requirement_registry_published"
COLLECTION_PUBLISHED_HISTORY = "compliance_requirement_registry_published_history"
SINGLETON_KEY = "active_registry"

REMATERIALISATION_INFO: Dict[str, Any] = {
    "automatic_for_all_properties": False,
    "detail": (
        "The active singleton updates immediately for planner, admin plan-preview, and the next "
        "per-property materialise/sync. There is no fleet-wide automatic re-materialise job after "
        "publish or revert."
    ),
}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _audit_append(doc: Dict[str, Any], action: str, actor: Dict[str, str], note: Optional[str] = None) -> None:
    log = doc.setdefault("audit_log", [])
    if not isinstance(log, list):
        log = []
        doc["audit_log"] = log
    entry: Dict[str, Any] = {"at": _utc_iso(), "action": action, "actor": actor}
    if note:
        entry["note"] = note
    log.append(entry)


async def fetch_active_published_registry_entries(db) -> Optional[Dict[str, Any]]:
    """Return the ``entries`` map for the active published snapshot, or ``None`` if none."""
    doc = await db[COLLECTION_PUBLISHED].find_one({"singleton_key": SINGLETON_KEY}, {"_id": 0, "entries": 1})
    if not doc:
        return None
    ent = doc.get("entries")
    return ent if isinstance(ent, dict) else None


async def fetch_published_metadata(db) -> Optional[Dict[str, Any]]:
    doc = await db[COLLECTION_PUBLISHED].find_one(
        {"singleton_key": SINGLETON_KEY},
        {"_id": 0, "entries": 0},
    )
    return doc


async def append_published_history_record(
    db,
    *,
    published_line_version: int,
    entries: Dict[str, Any],
    recorded_at: str,
    last_queue_id: Optional[str],
    activated_by: Dict[str, str],
    activation_kind: str,
    reverted_from_published_line_version: Optional[int] = None,
) -> None:
    """Append-only snapshot row (full ``entries`` copy)."""
    ent = copy.deepcopy(entries) if isinstance(entries, dict) else {}
    doc: Dict[str, Any] = {
        "history_id": str(uuid.uuid4()),
        "published_line_version": int(published_line_version),
        "activation_kind": str(activation_kind),
        "entry_count": len(ent),
        "entries": ent,
        "recorded_at": recorded_at,
        "last_queue_id": last_queue_id,
        "activated_by": activated_by,
        "reverted_from_published_line_version": reverted_from_published_line_version,
    }
    await db[COLLECTION_PUBLISHED_HISTORY].insert_one(doc)


async def list_published_history(
    db,
    *,
    skip: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Summary rows without ``entries`` (use ``get_published_history_record`` for payloads)."""
    lim = max(1, min(int(limit), 200))
    sk = max(0, int(skip))
    cur = (
        db[COLLECTION_PUBLISHED_HISTORY]
        .find({}, {"_id": 0, "entries": 0})
        .sort([("published_line_version", -1)])
        .skip(sk)
        .limit(lim)
    )
    return await cur.to_list(lim)


async def get_published_history_record(
    db,
    published_line_version: int,
    *,
    include_entries: bool = False,
) -> Optional[Dict[str, Any]]:
    filt = {"published_line_version": int(published_line_version)}
    if include_entries:
        doc = await db[COLLECTION_PUBLISHED_HISTORY].find_one(filt, {"_id": 0})
    else:
        doc = await db[COLLECTION_PUBLISHED_HISTORY].find_one(filt, {"_id": 0, "entries": 0})
    if not doc:
        return None
    return {k: v for k, v in doc.items() if k != "_id"}


async def revert_active_published_to_line_version(
    db,
    target_published_line_version: int,
    actor: Dict[str, str],
) -> Dict[str, Any]:
    """
    Owner-only path (enforced in routes): restore ``entries`` from an append-only history row.

    Raises ``ValueError`` with codes: ``history_not_found``, ``invalid_history_entries``,
    ``already_active_line_version``.
    """
    tv = int(target_published_line_version)
    if tv < 1:
        raise ValueError("invalid_version")
    hist = await db[COLLECTION_PUBLISHED_HISTORY].find_one({"published_line_version": tv}, {"_id": 0})
    if not hist:
        raise ValueError("history_not_found")
    entries = hist.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("invalid_history_entries")

    prev = await db[COLLECTION_PUBLISHED].find_one({"singleton_key": SINGLETON_KEY}, {"_id": 0, "version": 1})
    current_v = int((prev or {}).get("version") or 0)
    if current_v == tv:
        raise ValueError("already_active_line_version")
    next_v = current_v + 1
    now = _utc_iso()
    ent_copy = copy.deepcopy(entries)

    await db[COLLECTION_PUBLISHED].update_one(
        {"singleton_key": SINGLETON_KEY},
        {
            "$set": {
                "singleton_key": SINGLETON_KEY,
                "version": next_v,
                "entries": ent_copy,
                "updated_at": now,
                "last_queue_id": None,
                "last_published_by": actor,
                "last_activation_kind": "revert",
                "reverted_from_published_line_version": tv,
            }
        },
        upsert=True,
    )

    await append_published_history_record(
        db,
        published_line_version=next_v,
        entries=ent_copy,
        recorded_at=now,
        last_queue_id=None,
        activated_by=actor,
        activation_kind="revert",
        reverted_from_published_line_version=tv,
    )

    return {
        "published_version": next_v,
        "reverted_from_published_line_version": tv,
        "entry_count": len(ent_copy),
    }


def _snapshot_entries_from_drafts(draft_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    entries: Dict[str, Any] = {}
    for doc in draft_docs:
        cc = str(doc.get("canonical_code") or "").strip().upper()
        sk = str(doc.get("scope_key") or "DEFAULT").strip() or "DEFAULT"
        key = f"{cc}|{sk}"
        if key in entries:
            raise ValueError(f"duplicate_publish_key:{key}")
        snap = {k: v for k, v in doc.items() if k != "_id"}
        entries[key] = snap
    return entries


async def create_publish_queue_item(
    db,
    *,
    title: str,
    draft_entry_ids: List[str],
    actor: Dict[str, str],
) -> Dict[str, Any]:
    ids = [str(x).strip() for x in (draft_entry_ids or []) if str(x).strip()]
    if not ids:
        raise ValueError("draft_entry_ids_required")
    qid = str(uuid.uuid4())
    now = _utc_iso()
    doc: Dict[str, Any] = {
        "queue_id": qid,
        "status": "draft",
        "title": (title or "").strip() or "Registry publish",
        "draft_entry_ids": ids,
        "audit_log": [],
        "created_at": now,
        "updated_at": now,
    }
    _audit_append(doc, "created", actor)
    await db[COLLECTION_QUEUE].insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}


async def get_publish_queue_item(db, queue_id: str) -> Optional[Dict[str, Any]]:
    doc = await db[COLLECTION_QUEUE].find_one({"queue_id": queue_id}, {"_id": 0})
    return doc


async def list_publish_queue_items(db, *, limit: int = 100) -> List[Dict[str, Any]]:
    cur = db[COLLECTION_QUEUE].find({}, {"_id": 0}).sort([("updated_at", -1)]).limit(max(1, min(limit, 500)))
    return await cur.to_list(limit)


async def _transition(
    db,
    queue_id: str,
    *,
    from_statuses: List[str],
    to_status: str,
    actor: Dict[str, str],
    audit_action: str,
    extra_set: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    doc = await db[COLLECTION_QUEUE].find_one({"queue_id": queue_id}, {"_id": 0})
    if not doc:
        raise ValueError("queue_not_found")
    st = str(doc.get("status") or "")
    if st not in from_statuses:
        raise ValueError(f"invalid_status:{st}")
    log = list(doc.get("audit_log") or []) if isinstance(doc.get("audit_log"), list) else []
    entry: Dict[str, Any] = {"at": _utc_iso(), "action": audit_action, "actor": actor}
    log.append(entry)
    now = _utc_iso()
    patch: Dict[str, Any] = {"status": to_status, "updated_at": now, "audit_log": log}
    if extra_set:
        patch.update(extra_set)
    await db[COLLECTION_QUEUE].update_one({"queue_id": queue_id}, {"$set": patch})
    out = {**doc, **patch}
    return {k: v for k, v in out.items() if k != "_id"}


async def submit_publish_queue_item(db, queue_id: str, actor: Dict[str, str]) -> Dict[str, Any]:
    return await _transition(
        db,
        queue_id,
        from_statuses=["draft"],
        to_status="submitted",
        actor=actor,
        audit_action="submitted",
    )


async def approve_publish_queue_item(db, queue_id: str, actor: Dict[str, str]) -> Dict[str, Any]:
    return await _transition(
        db,
        queue_id,
        from_statuses=["submitted"],
        to_status="approved",
        actor=actor,
        audit_action="approved",
    )


async def reject_publish_queue_item(
    db,
    queue_id: str,
    actor: Dict[str, str],
    *,
    reason: str,
) -> Dict[str, Any]:
    r = (reason or "").strip() or "rejected"
    return await _transition(
        db,
        queue_id,
        from_statuses=["submitted", "approved"],
        to_status="rejected",
        actor=actor,
        audit_action="rejected",
        extra_set={"rejection_reason": r},
    )


async def publish_publish_queue_item(
    db,
    queue_id: str,
    actor: Dict[str, str],
) -> Dict[str, Any]:
    doc = await db[COLLECTION_QUEUE].find_one({"queue_id": queue_id}, {"_id": 0})
    if not doc:
        raise ValueError("queue_not_found")
    if str(doc.get("status") or "") != "approved":
        raise ValueError("not_approved")
    ids = doc.get("draft_entry_ids") or []
    if not isinstance(ids, list) or not ids:
        raise ValueError("draft_entry_ids_missing")

    draft_docs: List[Dict[str, Any]] = []
    for eid in ids:
        eid_s = str(eid).strip()
        d = await db[DRAFTS_COLLECTION].find_one({"entry_id": eid_s}, {"_id": 0})
        if not d:
            raise ValueError(f"missing_draft:{eid_s}")
        draft_docs.append(d)

    try:
        entries = _snapshot_entries_from_drafts(draft_docs)
    except ValueError as e:
        raise ValueError(str(e)) from e

    prev = await db[COLLECTION_PUBLISHED].find_one({"singleton_key": SINGLETON_KEY}, {"_id": 0, "version": 1})
    next_v = int((prev or {}).get("version") or 0) + 1
    now = _utc_iso()
    ent_copy = copy.deepcopy(entries)

    await db[COLLECTION_PUBLISHED].update_one(
        {"singleton_key": SINGLETON_KEY},
        {
            "$set": {
                "singleton_key": SINGLETON_KEY,
                "version": next_v,
                "entries": ent_copy,
                "updated_at": now,
                "last_queue_id": queue_id,
                "last_published_by": actor,
                "last_activation_kind": "publish",
                "reverted_from_published_line_version": None,
            }
        },
        upsert=True,
    )

    await append_published_history_record(
        db,
        published_line_version=next_v,
        entries=ent_copy,
        recorded_at=now,
        last_queue_id=queue_id,
        activated_by=actor,
        activation_kind="publish",
        reverted_from_published_line_version=None,
    )

    log = list(doc.get("audit_log") or []) if isinstance(doc.get("audit_log"), list) else []
    log.append({"at": now, "action": "published", "actor": actor, "version": next_v})
    await db[COLLECTION_QUEUE].update_one(
        {"queue_id": queue_id},
        {
            "$set": {
                "status": "published",
                "updated_at": now,
                "published_at": now,
                "published_version": next_v,
                "audit_log": log,
            }
        },
    )

    return {
        "queue_id": queue_id,
        "status": "published",
        "published_version": next_v,
        "entry_count": len(entries),
    }
