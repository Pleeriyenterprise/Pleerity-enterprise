"""Integration-specific audit logging."""
from __future__ import annotations

from typing import Any, Dict, Optional

from models import AuditAction, UserRole
from utils.audit import create_audit_log


async def log_zoho_sync_event(
    *,
    integration: str,
    operation: str,
    sync_id: str,
    status: str,
    actor_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    meta = {
        "action_type": "ZOHO_SYNC",
        "integration": integration,
        "operation": operation,
        "sync_id": sync_id,
        "status": status,
        **(metadata or {}),
    }
    return await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ADMIN if actor_id else None,
        actor_id=actor_id,
        resource_type="zoho_sync",
        resource_id=resource_id or sync_id,
        metadata=meta,
    )


async def log_zoho_webhook_event(
    *,
    integration: str,
    event_type: str,
    status: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    meta = {
        "action_type": "ZOHO_WEBHOOK",
        "integration": integration,
        "event_type": event_type,
        "status": status,
        **(metadata or {}),
    }
    return await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        resource_type="zoho_webhook",
        resource_id=event_type,
        metadata=meta,
    )
