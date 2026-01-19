from database import database
from models import AuditLog, AuditAction, UserRole
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

async def create_audit_log(
    action: AuditAction,
    actor_role: Optional[UserRole] = None,
    actor_id: Optional[str] = None,
    client_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    reason_code: Optional[str] = None,
    ip_address: Optional[str] = None
) -> str:
    """Create an audit log entry."""
    try:
        db = database.get_db()
        
        audit_log = AuditLog(
            action=action,
            actor_role=actor_role,
            actor_id=actor_id,
            client_id=client_id,
            resource_type=resource_type,
            resource_id=resource_id,
            before_state=before_state,
            after_state=after_state,
            metadata=metadata,
            reason_code=reason_code,
            ip_address=ip_address
        )
        
        doc = audit_log.model_dump()
        doc["timestamp"] = doc["timestamp"].isoformat() if isinstance(doc["timestamp"], datetime) else doc["timestamp"]
        
        await db.audit_logs.insert_one(doc)
        logger.info(f"Audit log created: {action.value}")
        return audit_log.audit_id
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")
        # Never fail the main operation due to audit log failure
        return ""
