"""ClearForm Audit Service

Comprehensive audit logging for compliance and tracking.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging

from database import database
from clearform.models.audit import AuditLog, AuditAction, AuditSeverity, AuditLogQuery

logger = logging.getLogger(__name__)


class AuditService:
    """Service for audit logging."""
    
    def __init__(self):
        self.db = None
    
    def _get_db(self):
        if self.db is None:
            self.db = database.get_db()
        return self.db
    
    async def log(
        self,
        action: AuditAction,
        description: str,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        session_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Create an audit log entry."""
        db = self._get_db()
        
        entry = AuditLog(
            action=action,
            severity=severity,
            description=description,
            user_id=user_id,
            org_id=org_id,
            session_id=session_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        await db.clearform_audit_logs.insert_one(entry.model_dump())
        
        # Log to application logger as well
        log_msg = f"[AUDIT] {action.value}: {description}"
        if user_id:
            log_msg += f" (user: {user_id})"
        if org_id:
            log_msg += f" (org: {org_id})"
        
        if severity == AuditSeverity.ERROR:
            logger.error(log_msg)
        elif severity == AuditSeverity.WARNING:
            logger.warning(log_msg)
        elif severity == AuditSeverity.CRITICAL:
            logger.critical(log_msg)
        else:
            logger.info(log_msg)
        
        return entry
    
    async def query(self, query: AuditLogQuery) -> List[Dict[str, Any]]:
        """Query audit logs."""
        db = self._get_db()
        
        mongo_query = {}
        
        if query.user_id:
            mongo_query["user_id"] = query.user_id
        if query.org_id:
            mongo_query["org_id"] = query.org_id
        if query.action:
            mongo_query["action"] = query.action.value
        if query.resource_type:
            mongo_query["resource_type"] = query.resource_type
        if query.resource_id:
            mongo_query["resource_id"] = query.resource_id
        if query.severity:
            mongo_query["severity"] = query.severity.value
        
        if query.start_date or query.end_date:
            mongo_query["created_at"] = {}
            if query.start_date:
                mongo_query["created_at"]["$gte"] = query.start_date
            if query.end_date:
                mongo_query["created_at"]["$lte"] = query.end_date
        
        cursor = db.clearform_audit_logs.find(
            mongo_query,
            {"_id": 0}
        ).sort("created_at", -1).skip(query.offset).limit(query.limit)
        
        return await cursor.to_list(query.limit)
    
    async def get_user_audit_logs(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        action: Optional[AuditAction] = None,
    ) -> List[Dict[str, Any]]:
        """Get audit logs for a user."""
        query = AuditLogQuery(
            user_id=user_id,
            action=action,
            limit=limit,
            offset=offset,
        )
        return await self.query(query)
    
    async def get_org_audit_logs(
        self,
        org_id: str,
        limit: int = 100,
        offset: int = 0,
        action: Optional[AuditAction] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get audit logs for an organization."""
        query = AuditLogQuery(
            org_id=org_id,
            action=action,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )
        return await self.query(query)
    
    async def get_document_audit_trail(
        self,
        document_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get audit trail for a specific document."""
        query = AuditLogQuery(
            resource_type="document",
            resource_id=document_id,
            limit=limit,
        )
        return await self.query(query)
    
    async def get_recent_activity(
        self,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get recent activity for dashboard."""
        query = AuditLogQuery(
            user_id=user_id,
            org_id=org_id,
            limit=limit,
        )
        return await self.query(query)
    
    async def count_by_action(
        self,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Count audit logs by action type."""
        db = self._get_db()
        
        match_stage = {}
        if user_id:
            match_stage["user_id"] = user_id
        if org_id:
            match_stage["org_id"] = org_id
        if start_date or end_date:
            match_stage["created_at"] = {}
            if start_date:
                match_stage["created_at"]["$gte"] = start_date
            if end_date:
                match_stage["created_at"]["$lte"] = end_date
        
        pipeline = [
            {"$match": match_stage} if match_stage else {"$match": {}},
            {"$group": {"_id": "$action", "count": {"$sum": 1}}},
        ]
        
        results = await db.clearform_audit_logs.aggregate(pipeline).to_list(50)
        
        return {r["_id"]: r["count"] for r in results}


# Global instance
audit_service = AuditService()
