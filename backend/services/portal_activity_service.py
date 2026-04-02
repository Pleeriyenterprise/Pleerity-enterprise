"""
Portal activity deltas: "since last visit" for client admins and period summaries for digests.

Uses Mongo collections only (audit_logs, compliance_score_history, work_orders, documents) — no fabricated metrics.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from database import database
from models import AuditAction

logger = logging.getLogger(__name__)

# Audit actions surfaced in product copy (counts only; no PII in aggregates)
_TRACKED_ACTIONS = frozenset(
    a.value
    for a in (
        AuditAction.DOCUMENT_VERIFIED,
        AuditAction.COMPLIANCE_SCORE_UPDATED,
        AuditAction.COMPLIANCE_STATUS_UPDATED,
        AuditAction.REMINDER_SENT,
        AuditAction.DIGEST_SENT,
        AuditAction.COMPLIANCE_RECALC_FAILED,
        AuditAction.INVOICE_APPROVED,
        AuditAction.INVOICE_REJECTED,
        AuditAction.MAINTENANCE_ISSUE_CREATED,
        AuditAction.CONTRACTOR_WORK_ORDER_STATUS_CHANGED,
        AuditAction.CLIENT_TASK_MARKED_DONE,
        AuditAction.CLIENT_TASK_MARKED_REVIEWED,
        AuditAction.CLIENT_TASK_DISMISSED,
        AuditAction.CLIENT_TASK_SNOOZED,
        AuditAction.RISK_SIGNAL_CREATED,
    )
)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        s = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except Exception:
        return None


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _default_since(portal_row: Optional[Dict[str, Any]]) -> datetime:
    """First call: cursor missing → last_login → 30 days ago."""
    now = datetime.now(timezone.utc)
    if portal_row:
        cur = _parse_iso(portal_row.get("last_activity_since_cursor_at"))
        if cur:
            return cur
        ll = _parse_iso(portal_row.get("last_login"))
        if ll:
            return ll
    return now - timedelta(days=30)


async def compute_activity_deltas(
    client_id: str,
    since_iso: str,
    until_iso: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Read-only aggregate for [since, until]. Does not mutate cursors.
    `since_iso` / `until_iso` are ISO-8601 UTC strings.
    """
    db = database.get_db()
    until_dt = _parse_iso(until_iso) if until_iso else datetime.now(timezone.utc)
    since_dt = _parse_iso(since_iso)
    if not since_dt:
        since_dt = until_dt - timedelta(days=30)
    if since_dt >= until_dt:
        return {
            "window": {"since": _iso(since_dt), "until": _iso(until_dt)},
            "empty_window": True,
            "compliance_score": None,
            "audit_counts": [],
            "work_orders_completed": 0,
            "documents_uploaded": 0,
            "lines": [],
        }

    since_s = _iso(since_dt)
    until_s = _iso(until_dt)

    # --- Portfolio score: first snapshot on/after since vs latest on/before until ---
    score_block: Optional[Dict[str, Any]] = None
    try:
        since_key = since_dt.strftime("%Y-%m-%d")
        until_key = until_dt.strftime("%Y-%m-%d")
        snap_a = await db.compliance_score_history.find_one(
            {"client_id": client_id, "date_key": {"$gte": since_key, "$lte": until_key}},
            {"_id": 0, "date_key": 1, "score": 1, "grade": 1},
            sort=[("date_key", 1)],
        )
        snap_b = await db.compliance_score_history.find_one(
            {"client_id": client_id, "date_key": {"$lte": until_key}},
            {"_id": 0, "date_key": 1, "score": 1, "grade": 1},
            sort=[("date_key", -1)],
        )
        if snap_a and snap_b and snap_a.get("date_key") != snap_b.get("date_key"):
            d = int(snap_b.get("score") or 0) - int(snap_a.get("score") or 0)
            score_block = {
                "score_at_start": snap_a.get("score"),
                "score_at_end": snap_b.get("score"),
                "delta": d,
                "grade_at_end": snap_b.get("grade"),
                "compare_from_date_key": snap_a.get("date_key"),
                "compare_to_date_key": snap_b.get("date_key"),
            }
        elif snap_b:
            score_block = {
                "score_at_start": None,
                "score_at_end": snap_b.get("score"),
                "delta": None,
                "grade_at_end": snap_b.get("grade"),
                "compare_from_date_key": None,
                "compare_to_date_key": snap_b.get("date_key"),
            }
    except Exception as e:
        logger.debug("activity deltas: score history failed: %s", e)

    # --- Audit log counts (string timestamp range; stored as ISO strings) ---
    audit_counts: List[Dict[str, Any]] = []
    try:
        match = {
            "client_id": client_id,
            "timestamp": {"$gte": since_s, "$lte": until_s},
            "action": {"$in": list(_TRACKED_ACTIONS)},
        }
        cursor = db.audit_logs.aggregate(
            [
                {"$match": match},
                {"$group": {"_id": "$action", "n": {"$sum": 1}}},
                {"$sort": {"n": -1}},
            ]
        )
        audit_counts = []
        async for r in cursor:
            audit_counts.append({"action": r["_id"], "count": r["n"]})
    except Exception as e:
        logger.warning("activity deltas: audit aggregation failed: %s", e)

    # --- Work orders marked completed in window (completed_at ISO) ---
    wo_completed = 0
    try:
        wo_completed = await db.work_orders.count_documents(
            {
                "client_id": client_id,
                "completed_at": {"$gte": since_s, "$lte": until_s},
            }
        )
    except Exception as e:
        logger.debug("activity deltas: work_orders count failed: %s", e)

    # --- Documents uploaded in window ---
    docs_up = 0
    try:
        docs_up = await db.documents.count_documents(
            {
                "client_id": client_id,
                "uploaded_at": {"$gte": since_s, "$lte": until_s},
            }
        )
    except Exception as e:
        logger.debug("activity deltas: documents count failed: %s", e)

    lines = _human_lines(score_block, audit_counts, wo_completed, docs_up)

    return {
        "window": {"since": since_s, "until": until_s},
        "empty_window": False,
        "compliance_score": score_block,
        "audit_counts": audit_counts,
        "work_orders_completed": wo_completed,
        "documents_uploaded": docs_up,
        "lines": lines,
    }


def _human_lines(
    score_block: Optional[Dict[str, Any]],
    audit_counts: List[Dict[str, Any]],
    wo_completed: int,
    docs_up: int,
) -> List[str]:
    out: List[str] = []
    if score_block and score_block.get("delta") is not None:
        d = score_block["delta"]
        if d > 0:
            out.append(f"Portfolio compliance score increased by {d} points (snapshot comparison).")
        elif d < 0:
            out.append(f"Portfolio compliance score decreased by {abs(d)} points (snapshot comparison).")
        else:
            out.append("Portfolio compliance score unchanged between compared snapshots.")
    ac_map = {x["action"]: x["count"] for x in audit_counts}
    v = ac_map.get(AuditAction.DOCUMENT_VERIFIED.value, 0)
    if v:
        out.append(f"{v} document(s) verified by your team.")
    r = ac_map.get(AuditAction.REMINDER_SENT.value, 0)
    if r:
        out.append(f"{r} compliance reminder(s) sent.")
    g = ac_map.get(AuditAction.DIGEST_SENT.value, 0)
    if g:
        out.append(f"{g} digest email(s) sent.")
    f = ac_map.get(AuditAction.COMPLIANCE_RECALC_FAILED.value, 0)
    if f:
        out.append(f"{f} compliance recalculation issue(s) logged (review notifications or support).")
    ia = ac_map.get(AuditAction.INVOICE_APPROVED.value, 0)
    if ia:
        out.append(f"{ia} maintenance invoice approval(s) recorded.")
    if wo_completed:
        out.append(f"{wo_completed} work order(s) marked completed.")
    if docs_up:
        out.append(f"{docs_up} new document upload(s).")
    return out


async def peek_activity_since_for_portal_user(
    portal_user_id: str,
    client_id: str,
) -> Dict[str, Any]:
    """Compute deltas since stored cursor (or last_login / 30d). Does not move the cursor."""
    db = database.get_db()
    row = await db.portal_users.find_one(
        {"portal_user_id": portal_user_id, "client_id": client_id},
        {"_id": 0, "last_activity_since_cursor_at": 1, "last_login": 1},
    )
    since_dt = _default_since(row)
    since_s = _iso(since_dt)
    until_s = _iso(datetime.now(timezone.utc))
    payload = await compute_activity_deltas(client_id, since_s, until_s)
    payload["cursor_mode"] = "peek"
    return payload


async def acknowledge_activity_cursor(portal_user_id: str) -> str:
    """Advance cursor to now (call when user marks the feed as seen)."""
    db = database.get_db()
    until_s = _iso(datetime.now(timezone.utc))
    await db.portal_users.update_one(
        {"portal_user_id": portal_user_id},
        {"$set": {"last_activity_since_cursor_at": until_s}},
    )
    return until_s
