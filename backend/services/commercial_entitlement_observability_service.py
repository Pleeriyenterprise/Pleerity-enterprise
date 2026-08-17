"""Commercial entitlement audit trail and metrics (Phase 2C)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import database
from models import AuditAction
from services.commercial_entitlement_service import COL_GOVERNANCE, get_active_governance
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

COL_AUDIT = "commercial_entitlement_audit"
COL_METRICS = "commercial_entitlement_metrics"

EVENT_COMMERCIAL_GRANTED = "commercial_granted"
EVENT_COMMERCIAL_REVOKED = "commercial_revoked"
EVENT_COMMERCIAL_EXPIRED = "commercial_expired"
EVENT_COMMERCIAL_DRIFT_DETECTED = "commercial_drift_detected"
EVENT_COMMERCIAL_REVIEW_DUE = "commercial_review_due"
EVENT_COMMERCIAL_REJECTED = "commercial_rejected"

METRIC_KEYS = frozenset(
    {
        "grace_issued",
        "suspension_issued",
        "sponsorship_issued",
        "recovery_continuity",
        "retention_saves",
        "waived_revenue_exposure",
        "expiry_actions",
        "entitlement_drift",
        "commercial_revoked",
    }
)

_ACTION_METRIC_MAP = {
    "grant_grace_period": "grace_issued",
    "suspend_billing": "suspension_issued",
    "grant_sponsored_access": "sponsorship_issued",
    "apply_recovery_compensation": "recovery_continuity",
    "retention_extension": "retention_saves",
    "waive_onboarding_fee": "waived_revenue_exposure",
    "restrict_entitlement": "suspension_issued",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _increment_metric(metric_key: str, *, client_id: Optional[str] = None) -> None:
    if metric_key not in METRIC_KEYS:
        return
    db = database.get_db()
    now = _now().isoformat()
    scopes = [("global", "global")]
    if client_id:
        scopes.append((client_id, client_id))
    for scope_key, scope_val in scopes:
        await db[COL_METRICS].update_one(
            {"scope": scope_key, "client_id": scope_val},
            {
                "$inc": {metric_key: 1, "event_count": 1},
                "$set": {"last_event_at": now, "last_metric": metric_key},
            },
            upsert=True,
        )


async def record_commercial_entitlement_event(
    *,
    event_type: str,
    client_id: str,
    governance_id: Optional[str] = None,
    action: Optional[str] = None,
    actor_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    db = database.get_db()
    event_id = str(uuid.uuid4())
    now = _now().isoformat()
    meta = dict(metadata or {})
    doc = {
        "event_id": event_id,
        "event_type": event_type,
        "client_id": client_id,
        "governance_id": governance_id,
        "action": action,
        "actor_id": actor_id,
        "created_at": now,
        "metadata": meta,
    }
    await db[COL_AUDIT].insert_one(doc)

    if action and action in _ACTION_METRIC_MAP:
        await _increment_metric(_ACTION_METRIC_MAP[action], client_id=client_id)
    if event_type == EVENT_COMMERCIAL_EXPIRED:
        await _increment_metric("expiry_actions", client_id=client_id)
    if event_type == EVENT_COMMERCIAL_DRIFT_DETECTED:
        await _increment_metric("entitlement_drift", client_id=client_id)
    if event_type == EVENT_COMMERCIAL_REVOKED:
        await _increment_metric("commercial_revoked", client_id=client_id)

    audit_action = AuditAction.COMMERCIAL_ENTITLEMENT_GOVERNED
    if event_type == EVENT_COMMERCIAL_REVOKED:
        audit_action = AuditAction.COMMERCIAL_ENTITLEMENT_REVOKED
    elif event_type == EVENT_COMMERCIAL_EXPIRED:
        audit_action = AuditAction.COMMERCIAL_ENTITLEMENT_EXPIRED
    elif event_type == EVENT_COMMERCIAL_REJECTED:
        audit_action = AuditAction.COMMERCIAL_ENTITLEMENT_REJECTED

    try:
        await create_audit_log(
            action=audit_action,
            actor_id=actor_id,
            client_id=client_id,
            resource_type="commercial_entitlement",
            resource_id=governance_id or client_id,
            metadata={"event_type": event_type, "event_id": event_id, "action": action, **meta},
            reason_code="commercial_entitlement_observability",
        )
    except Exception as exc:
        logger.warning("commercial entitlement audit log failed client_id=%s: %s", client_id, exc)

    return event_id


async def get_client_commercial_entitlement_observability(client_id: str) -> Dict[str, Any]:
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "client_id": 1})
    if not client:
        return {"found": False, "client_id": client_id}

    active = await get_active_governance(client_id)
    cursor = db[COL_GOVERNANCE].find({"client_id": client_id}).sort("created_at", -1).limit(50)
    history: List[Dict[str, Any]] = []
    async for row in cursor:
        row.pop("_id", None)
        history.append(row)

    audit_cursor = db[COL_AUDIT].find({"client_id": client_id}).sort("created_at", -1).limit(30)
    audit_events: List[Dict[str, Any]] = []
    async for row in audit_cursor:
        row.pop("_id", None)
        audit_events.append(row)

    global_metrics = await db[COL_METRICS].find_one({"scope": "global"}, {"_id": 0})
    client_metrics = await db[COL_METRICS].find_one({"scope": client_id}, {"_id": 0})

    return {
        "found": True,
        "client_id": client_id,
        "active_governance": active,
        "governance_history": history,
        "audit_events": audit_events,
        "metrics": {
            "global": global_metrics or {},
            "client": client_metrics or {},
        },
    }


async def get_fleet_commercial_entitlement_metrics() -> Dict[str, Any]:
    db = database.get_db()
    doc = await db[COL_METRICS].find_one({"scope": "global"}, {"_id": 0})
    active_count = await db[COL_GOVERNANCE].count_documents({"status": "active"})
    return {
        "scope": "global",
        "active_governance_count": active_count,
        "counters": doc or {},
    }
