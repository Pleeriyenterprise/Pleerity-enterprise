"""
Score Ledger Service - Enterprise-grade log of every score change.

Each recalc writes one immutable ledger entry with before/after, delta,
trigger_type, trigger_label, driver breakdown, and rule_version.
Used by GET /api/client/ledger and GET /api/admin/ledger.
"""
from database import database
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

COLLECTION = "score_ledger_events"

# Map internal trigger_reason (from queue) to task-style trigger_type + human label
TRIGGER_MAP = {
    "DOC_UPLOADED": ("DOCUMENT_UPLOADED", "Document uploaded"),
    "DOCUMENT_UPLOADED": ("DOCUMENT_UPLOADED", "Document uploaded"),
    "DOC_DELETED": ("DOCUMENT_REMOVED", "Document removed"),
    "DOC_STATUS_CHANGED": ("DOCUMENT_STATUS_CHANGED", "Document status updated"),
    "AI_APPLIED": ("CERT_DETAILS_CONFIRMED", "Certificate details confirmed"),
    "ADMIN_UPLOAD": ("DOCUMENT_UPLOADED", "Document uploaded (admin)"),
    "ADMIN_DELETE": ("DOCUMENT_REMOVED", "Document removed (admin)"),
    "EXPIRY_JOB": ("SCHEDULED_RECALC", "Expiry rollover"),
    "EXPIRY_ROLLOVER": ("SCHEDULED_RECALC", "Expiry rollover"),
    "PROVISIONING": ("PROPERTY_ADDED", "Portfolio updated"),
    "PROPERTY_CREATED": ("PROPERTY_ADDED", "Property added"),
    "PROPERTY_UPDATED": ("PROPERTY_UPDATED", "Property updated"),
    "LAZY_BACKFILL": ("SCHEDULED_RECALC", "Score refreshed"),
    "REQUIREMENT_CHANGED": ("REQUIREMENT_STATUS_CHANGED", "Requirement updated"),
}

ACTOR_MAP = {"CLIENT": "user", "ADMIN": "admin", "SYSTEM": "system"}
DEFAULT_TRIGGER_TYPE = "SCHEDULED_RECALC"
DEFAULT_TRIGGER_LABEL = "Score recalculated"


def _drivers_from_breakdown(breakdown: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Map legacy breakdown keys to task driver names."""
    if not breakdown:
        return {"status": None, "timeline": None, "documents": None, "overdue_penalty": None}
    return {
        "status": breakdown.get("status_score"),
        "timeline": breakdown.get("expiry_score"),
        "documents": breakdown.get("document_score"),
        "overdue_penalty": breakdown.get("overdue_penalty_score"),
    }


def _drivers_delta(before: Dict[str, Optional[float]], after: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
    out = {}
    for k in ("status", "timeline", "documents", "overdue_penalty"):
        b, a = before.get(k), after.get(k)
        if b is not None and a is not None:
            out[k] = round(a - b, 2)
        else:
            out[k] = None
    return out


async def log_score_change(
    client_id: str,
    property_id: str,
    *,
    actor_type: str,
    actor_id: Optional[str] = None,
    trigger_reason: str,
    trigger_type: Optional[str] = None,
    trigger_label: Optional[str] = None,
    before_score: Optional[float] = None,
    after_score: float,
    before_grade: Optional[str] = None,
    after_grade: Optional[str] = None,
    drivers_before: Optional[Dict[str, Optional[float]]] = None,
    drivers_after: Optional[Dict[str, Optional[float]]] = None,
    rule_version: Optional[str] = None,
    requirement_id: Optional[str] = None,
    document_id: Optional[str] = None,
    evidence: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """
    Write one immutable score ledger entry. Call from recalculate_and_persist only.
    Computes delta and drivers_delta. Idempotency: if correlation_id is provided and
    an entry with same correlation_id already exists for this client/property, skip insert.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    delta = (after_score - before_score) if before_score is not None else None
    drivers_before_n = drivers_before or _drivers_from_breakdown({})
    drivers_after_n = drivers_after or _drivers_from_breakdown({})
    drivers_delta = _drivers_delta(drivers_before_n, drivers_after_n)
    trigger_type_final = trigger_type or TRIGGER_MAP.get(trigger_reason, (DEFAULT_TRIGGER_TYPE, DEFAULT_TRIGGER_LABEL))[0]
    trigger_label_final = trigger_label or TRIGGER_MAP.get(trigger_reason, (DEFAULT_TRIGGER_TYPE, DEFAULT_TRIGGER_LABEL))[1]
    actor_normalized = ACTOR_MAP.get((actor_type or "").upper(), "system")

    if correlation_id:
        existing = await db[COLLECTION].find_one(
            {"client_id": client_id, "property_id": property_id, "correlation_id": correlation_id},
            {"_id": 1},
        )
        if existing:
            logger.debug("Score ledger skip duplicate correlation_id=%s", correlation_id)
            return

    doc = {
        "client_id": client_id,
        "property_id": property_id,
        "requirement_id": requirement_id,
        "document_id": document_id,
        "actor_type": actor_normalized,
        "actor_id": actor_id,
        "trigger_type": trigger_type_final,
        "trigger_label": trigger_label_final,
        "before_score": round(before_score, 2) if before_score is not None else None,
        "after_score": round(after_score, 2),
        "delta": round(delta, 2) if delta is not None else None,
        "before_grade": before_grade,
        "after_grade": after_grade,
        "drivers_before": drivers_before_n,
        "drivers_after": drivers_after_n,
        "drivers_delta": drivers_delta,
        "rule_version": rule_version or "v1",
        "evidence": evidence or {},
        "created_at": now.isoformat(),
    }
    if correlation_id:
        doc["correlation_id"] = correlation_id
    await db[COLLECTION].insert_one(doc)
    logger.debug("Score ledger entry client_id=%s property_id=%s trigger=%s delta=%s", client_id, property_id, trigger_type_final, delta)


async def list_ledger(
    client_id: str,
    *,
    property_id: Optional[str] = None,
    trigger_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 50,
    cursor: Optional[str] = None,
) -> Dict[str, Any]:
    """Paginated list of ledger entries for a client, newest first."""
    db = database.get_db()
    query = {"client_id": client_id}
    if property_id:
        query["property_id"] = property_id
    if trigger_type:
        query["trigger_type"] = trigger_type
    if from_date or to_date:
        query["created_at"] = {}
        if from_date:
            query["created_at"]["$gte"] = from_date
        if to_date:
            query["created_at"]["$lte"] = to_date
    if cursor:
        try:
            query["created_at"] = query.get("created_at") or {}
            query["created_at"]["$lt"] = cursor
        except Exception:
            pass
    limit = min(max(1, limit), 200)
    cursor_cur = db[COLLECTION].find(query, {"_id": 0}).sort("created_at", -1).limit(limit + 1)
    items = await cursor_cur.to_list(limit + 1)
    has_more = len(items) > limit
    if has_more:
        items = items[:limit]
    next_cursor = items[-1]["created_at"] if items and has_more else None
    total = await db[COLLECTION].count_documents({"client_id": client_id} if not (property_id or trigger_type or from_date or to_date) else query)
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more, "total": total}


async def list_ledger_export(
    client_id: str,
    *,
    property_id: Optional[str] = None,
    trigger_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 10000,
) -> List[Dict[str, Any]]:
    """Fetch ledger entries for CSV export (no cursor; cap at limit)."""
    db = database.get_db()
    query = {"client_id": client_id}
    if property_id:
        query["property_id"] = property_id
    if trigger_type:
        query["trigger_type"] = trigger_type
    if from_date or to_date:
        query["created_at"] = {}
        if from_date:
            query["created_at"]["$gte"] = from_date
        if to_date:
            query["created_at"]["$lte"] = to_date
    limit = min(max(1, limit), 10000)
    cursor = db[COLLECTION].find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(limit)
