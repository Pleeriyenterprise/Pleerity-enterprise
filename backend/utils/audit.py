from database import database
from models import AuditLog, AuditAction, UserRole
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

def calculate_diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate the differences between before and after states.
    
    Returns a dict with:
    - added: fields that exist in after but not in before
    - removed: fields that exist in before but not in after
    - changed: fields that exist in both but have different values
    """
    if not before and not after:
        return {}
    
    if not before:
        return {"added": after, "removed": {}, "changed": {}}
    
    if not after:
        return {"added": {}, "removed": before, "changed": {}}
    
    diff = {"added": {}, "removed": {}, "changed": {}}
    
    all_keys = set(before.keys()) | set(after.keys())
    
    for key in all_keys:
        before_val = before.get(key)
        after_val = after.get(key)
        
        if key not in before:
            diff["added"][key] = after_val
        elif key not in after:
            diff["removed"][key] = before_val
        elif before_val != after_val:
            diff["changed"][key] = {
                "from": before_val,
                "to": after_val
            }
    
    # Remove empty categories
    return {k: v for k, v in diff.items() if v}

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
    ip_address: Optional[str] = None,
    auto_diff: bool = True
) -> str:
    """Create an audit log entry with optional automatic diff calculation.
    
    Args:
        action: The audit action type
        actor_role: Role of the user performing the action
        actor_id: ID of the user performing the action
        client_id: ID of the affected client
        resource_type: Type of resource being modified (e.g., 'property', 'profile')
        resource_id: ID of the specific resource
        before_state: State before the change
        after_state: State after the change
        metadata: Additional metadata
        reason_code: Optional reason code for the action
        ip_address: IP address of the request
        auto_diff: If True, automatically calculate and store diff
    """
    try:
        db = database.get_db()
        
        # Calculate diff if both states provided and auto_diff is enabled
        diff = None
        if auto_diff and before_state and after_state:
            diff = calculate_diff(before_state, after_state)
        
        # Merge diff into metadata
        enriched_metadata = metadata.copy() if metadata else {}
        if diff:
            enriched_metadata["diff"] = diff
            enriched_metadata["changes_count"] = (
                len(diff.get("added", {})) + 
                len(diff.get("removed", {})) + 
                len(diff.get("changed", {}))
            )
        
        audit_log = AuditLog(
            action=action,
            actor_role=actor_role,
            actor_id=actor_id,
            client_id=client_id,
            resource_type=resource_type,
            resource_id=resource_id,
            before_state=before_state,
            after_state=after_state,
            metadata=enriched_metadata if enriched_metadata else None,
            reason_code=reason_code,
            ip_address=ip_address
        )
        
        doc = audit_log.model_dump()
        doc["timestamp"] = doc["timestamp"].isoformat() if isinstance(doc["timestamp"], datetime) else doc["timestamp"]
        
        await db.audit_logs.insert_one(doc)
        logger.info(f"Audit log created: {action.value}" + (f" with {enriched_metadata.get('changes_count', 0)} changes" if diff else ""))
        return audit_log.audit_id
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")
        # Never fail the main operation due to audit log failure
        return ""

async def get_audit_logs_for_resource(
    resource_type: str,
    resource_id: str,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Get audit logs for a specific resource."""
    try:
        db = database.get_db()
        cursor = db.audit_logs.find(
            {"resource_type": resource_type, "resource_id": resource_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    except Exception as e:
        logger.error(f"Failed to get audit logs for resource: {e}")
        return []
