"""
Async compliance recalculation queue (Option B).
Single enqueue function; worker in job_runner processes jobs.
Reuses compliance_scoring_service.recalculate_and_persist — no duplicate scoring logic.
"""
from database import database
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Trigger reasons (match task correlation_id rules)
TRIGGER_DOC_UPLOADED = "DOC_UPLOADED"
TRIGGER_DOC_DELETED = "DOC_DELETED"
TRIGGER_DOC_STATUS_CHANGED = "DOC_STATUS_CHANGED"
TRIGGER_AI_APPLIED = "AI_APPLIED"
TRIGGER_ADMIN_UPLOAD = "ADMIN_UPLOAD"
TRIGGER_ADMIN_DELETE = "ADMIN_DELETE"
TRIGGER_EXPIRY_JOB = "EXPIRY_JOB"
TRIGGER_PROVISIONING = "PROVISIONING"
TRIGGER_PROPERTY_CREATED = "PROPERTY_CREATED"
TRIGGER_LAZY_BACKFILL = "LAZY_BACKFILL"

STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_DONE = "DONE"
STATUS_FAILED = "FAILED"
STATUS_DEAD = "DEAD"

ACTOR_CLIENT = "CLIENT"
ACTOR_ADMIN = "ADMIN"
ACTOR_SYSTEM = "SYSTEM"


async def enqueue_compliance_recalc(
    property_id: str,
    client_id: str,
    trigger_reason: str,
    actor_type: str,
    actor_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> bool:
    """
    Enqueue a compliance recalc for a property. Idempotent by (property_id, correlation_id).
    Sets compliance_score_pending=true on the property.
    Returns True if a new job was enqueued, False if duplicate (no-op).
    """
    if not correlation_id:
        correlation_id = f"{trigger_reason}:{property_id}:{datetime.now(timezone.utc).timestamp()}"
    db = database.get_db()
    now = datetime.now(timezone.utc)
    doc = {
        "property_id": property_id,
        "client_id": client_id,
        "trigger_reason": trigger_reason,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "correlation_id": correlation_id,
        "status": STATUS_PENDING,
        "attempts": 0,
        "next_run_at": now.isoformat(),
        "last_error": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    try:
        await db.compliance_recalc_queue.insert_one(doc)
        await db.properties.update_one(
            {"property_id": property_id},
            {"$set": {"compliance_score_pending": True}},
        )
        logger.info(f"Enqueued compliance recalc property_id={property_id} correlation_id={correlation_id}")
        return True
    except Exception as e:
        if "duplicate key" in str(e).lower() or "E11000" in str(e):
            return False
        raise
