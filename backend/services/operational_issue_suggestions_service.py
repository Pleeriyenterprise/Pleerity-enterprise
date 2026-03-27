"""
Operational issue suggestions (tier B: suggest only): list, dismiss, convert to linked issue.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import database
from models import AuditAction
from utils.audit import create_audit_log

from services import maintenance_issues_service
from services.operational_automation_service import (
    SUGGESTION_STATUS_PENDING,
    SUGGESTION_STATUS_DISMISSED,
    SUGGESTION_STATUS_CONVERTED,
)


async def list_pending_issue_suggestions(
    client_id: str,
    property_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Dict[str, Any]:
    """Pending suggestions for the client, optionally scoped to one property."""
    db = database.get_db()
    q: Dict[str, Any] = {"client_id": client_id, "status": SUGGESTION_STATUS_PENDING}
    if property_id:
        q["property_id"] = property_id
    total = await db.operational_issue_suggestions.count_documents(q)
    lim = max(1, min(200, limit))
    sk = max(0, skip)
    cursor = (
        db.operational_issue_suggestions.find(q, {"_id": 0})
        .sort("updated_at", -1)
        .skip(sk)
        .limit(lim)
    )
    items = await cursor.to_list(lim)
    return {"suggestions": items, "total": total, "skip": sk, "limit": lim}


async def dismiss_issue_suggestion(
    client_id: str,
    suggestion_id: str,
    actor_id: Optional[str],
    note: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Mark a pending suggestion dismissed. Returns updated doc or None if not found."""
    db = database.get_db()
    doc = await db.operational_issue_suggestions.find_one(
        {"suggestion_id": suggestion_id, "client_id": client_id},
        {"_id": 0},
    )
    if not doc:
        return None
    if doc.get("status") != SUGGESTION_STATUS_PENDING:
        raise ValueError("Suggestion is not pending")

    now = datetime.now(timezone.utc).isoformat()
    r = await db.operational_issue_suggestions.update_one(
        {
            "suggestion_id": suggestion_id,
            "client_id": client_id,
            "status": SUGGESTION_STATUS_PENDING,
        },
        {
            "$set": {
                "status": SUGGESTION_STATUS_DISMISSED,
                "dismissed_at": now,
                "dismissed_by": actor_id,
                "dismiss_note": (note or "").strip() or None,
                "updated_at": now,
            }
        },
    )
    if r.modified_count == 0:
        return None

    await create_audit_log(
        action=AuditAction.OPERATIONAL_ISSUE_SUGGESTION_DISMISSED,
        actor_id=actor_id,
        client_id=client_id,
        resource_type="operational_issue_suggestion",
        resource_id=suggestion_id,
        metadata={
            "property_id": doc.get("property_id"),
            "operational_root_key": doc.get("operational_root_key"),
            "rule_id": doc.get("rule_id"),
        },
    )
    return await db.operational_issue_suggestions.find_one(
        {"suggestion_id": suggestion_id, "client_id": client_id},
        {"_id": 0},
    )


async def convert_issue_suggestion(
    client_id: str,
    suggestion_id: str,
    issue_id: str,
    actor_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Link a pending suggestion to an issue the user created (same property)."""
    db = database.get_db()
    sug = await db.operational_issue_suggestions.find_one(
        {"suggestion_id": suggestion_id, "client_id": client_id},
        {"_id": 0},
    )
    if not sug:
        return None
    if sug.get("status") != SUGGESTION_STATUS_PENDING:
        raise ValueError("Suggestion is not pending")

    issue = await maintenance_issues_service.get_issue(issue_id.strip(), client_id=client_id)
    if not issue:
        raise ValueError("Issue not found")
    if issue.get("property_id") != sug.get("property_id"):
        raise ValueError("Issue belongs to a different property than this suggestion")

    now = datetime.now(timezone.utc).isoformat()
    r = await db.operational_issue_suggestions.update_one(
        {
            "suggestion_id": suggestion_id,
            "client_id": client_id,
            "status": SUGGESTION_STATUS_PENDING,
        },
        {
            "$set": {
                "status": SUGGESTION_STATUS_CONVERTED,
                "converted_at": now,
                "converted_by": actor_id,
                "converted_issue_id": issue_id.strip(),
                "updated_at": now,
            }
        },
    )
    if r.modified_count == 0:
        return None

    await create_audit_log(
        action=AuditAction.OPERATIONAL_ISSUE_SUGGESTION_CONVERTED,
        actor_id=actor_id,
        client_id=client_id,
        resource_type="operational_issue_suggestion",
        resource_id=suggestion_id,
        metadata={
            "property_id": sug.get("property_id"),
            "issue_id": issue_id.strip(),
            "operational_root_key": sug.get("operational_root_key"),
            "rule_id": sug.get("rule_id"),
        },
    )
    return await db.operational_issue_suggestions.find_one(
        {"suggestion_id": suggestion_id, "client_id": client_id},
        {"_id": 0},
    )
