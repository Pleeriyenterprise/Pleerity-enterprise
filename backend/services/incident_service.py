"""
Incident management for enterprise observability.
System-wide P0/P1/P2 incidents with acknowledge/resolve workflow.
Created by SLA watchdog or other monitors; surfaced in admin UI and notifications.
"""
from database import database
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

COLLECTION = "incidents"

STATUS_OPEN = "open"
STATUS_ACKNOWLEDGED = "acknowledged"
STATUS_RESOLVED = "resolved"

SEVERITY_P0 = "P0"
SEVERITY_P1 = "P1"
SEVERITY_P2 = "P2"

SOURCE_JOB_MONITOR = "job_monitor"
SOURCE_API_ERROR = "api_error"
SOURCE_WEBHOOK = "webhook"
SOURCE_EMAIL = "email"


async def create_incident(
    severity: str,
    title: str,
    description: str,
    source: str,
    *,
    related_job_run_id: Optional[str] = None,
    related_job_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a new incident. Returns incident_id (str)."""
    db = database.get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "severity": severity,
        "title": title,
        "description": description,
        "source": source,
        "status": STATUS_OPEN,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "acknowledged_by": None,
        "acknowledged_at": None,
        "resolved_by": None,
        "resolved_at": None,
        "related_job_run_id": related_job_run_id,
        "related_job_name": related_job_name,
        "metadata": metadata or {},
    }
    result = await db[COLLECTION].insert_one(doc)
    incident_id = str(result.inserted_id)
    logger.info("Incident created incident_id=%s severity=%s title=%s", incident_id, severity, title)
    # Notify all admins (in-app notification)
    try:
        from models import UserRole
        staff_roles = (UserRole.ROLE_OWNER.value, UserRole.ROLE_ADMIN.value, UserRole.ROLE_SUPPORT.value)
        admins = await db.portal_users.find(
            {"role": {"$in": staff_roles}},
            {"_id": 0, "portal_user_id": 1, "user_id": 1},
        ).to_list(500)
        from services.order_service import create_in_app_notification
        for admin in admins:
            recipient_id = admin.get("user_id") or admin.get("portal_user_id")
            if not recipient_id:
                continue
            await create_in_app_notification(
                recipient_id=recipient_id,
                title=f"[{severity}] {title}",
                message=description[:500] if description else title,
                notification_type="incident",
                link=f"/admin/incidents?highlight={incident_id}",
                metadata={"incident_id": incident_id, "severity": severity},
            )
    except Exception as e:
        logger.warning("Failed to create incident in-app notifications: %s", e)
    return incident_id


async def list_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
) -> Dict[str, Any]:
    """List incidents with optional filters. Returns { items, total }."""
    db = database.get_db()
    query = {}
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity
    total = await db[COLLECTION].count_documents(query)
    cursor = db[COLLECTION].find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(limit)
    items = []
    for d in docs:
        oid = d.pop("_id", None)
        d["id"] = str(oid) if oid else ""
        items.append(d)
    return {"items": items, "total": total}


async def get_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    """Get a single incident by id."""
    from bson import ObjectId
    db = database.get_db()
    try:
        oid = ObjectId(incident_id)
    except Exception:
        return None
    doc = await db[COLLECTION].find_one({"_id": oid})
    if not doc:
        return None
    doc.pop("_id")
    doc["id"] = incident_id
    return doc


async def acknowledge_incident(incident_id: str, acknowledged_by: str, note: Optional[str] = None) -> bool:
    """Mark incident as acknowledged. Returns True if updated."""
    from bson import ObjectId
    db = database.get_db()
    now = datetime.now(timezone.utc)
    try:
        oid = ObjectId(incident_id)
    except Exception:
        return False
    update = {"status": STATUS_ACKNOWLEDGED, "acknowledged_by": acknowledged_by, "acknowledged_at": now.isoformat(), "updated_at": now.isoformat()}
    if note:
        update["metadata.note_ack"] = note
    result = await db[COLLECTION].update_one({"_id": oid, "status": STATUS_OPEN}, {"$set": update})
    return result.modified_count > 0


async def resolve_incident(incident_id: str, resolved_by: str, note: Optional[str] = None) -> bool:
    """Mark incident as resolved. Returns True if updated."""
    from bson import ObjectId
    db = database.get_db()
    now = datetime.now(timezone.utc)
    try:
        oid = ObjectId(incident_id)
    except Exception:
        return False
    update = {"status": STATUS_RESOLVED, "resolved_by": resolved_by, "resolved_at": now.isoformat(), "updated_at": now.isoformat()}
    if note:
        update["metadata.note_resolve"] = note
    result = await db[COLLECTION].update_one(
        {"_id": oid, "status": {"$in": [STATUS_OPEN, STATUS_ACKNOWLEDGED]}},
        {"$set": update},
    )
    return result.modified_count > 0


async def count_open_by_severity(severities: List[str]) -> int:
    """Count open incidents with severity in the given list (e.g. [P0, P1] for banner)."""
    if not severities:
        return 0
    db = database.get_db()
    return await db[COLLECTION].count_documents({"status": STATUS_OPEN, "severity": {"$in": severities}})
