"""Inbound Zoho webhook handlers — governed actions only."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from database import database
from services.integrations.zoho.adapters.books import ZohoBooksAdapter
from services.integrations.zoho.adapters.crm import ZohoCrmAdapter
from services.integrations.zoho.audit_helper import log_zoho_webhook_event
from services.integrations.zoho.config import is_integration_enabled
from services.integrations.zoho.registry import validate_inbound_crm_fields
from services.integrations.zoho.service import zoho_integration_service

logger = logging.getLogger(__name__)


async def handle_sign_completion(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not is_integration_enabled("sign"):
        return {"accepted": False, "reason": "sign_sync_disabled"}

    result = await zoho_integration_service.run_sync(
        "sign",
        "process_completion",
        {
            "request_id": payload.get("request_id"),
            "document_name": payload.get("document_name"),
            "category": payload.get("category") or payload.get("document_category"),
            "completed_at": payload.get("completed_at"),
            "document_url": payload.get("document_url"),
            "business_record_id": payload.get("business_record_id"),
        },
    )
    await log_zoho_webhook_event(
        integration="sign",
        event_type="document.completed",
        status=result.status.value,
        metadata={"sync_id": result.sync_id},
    )
    return {"accepted": result.success, "sync_id": result.sync_id, "message": result.message}


async def handle_campaigns_unsubscribe(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not is_integration_enabled("campaigns"):
        return {"accepted": False, "reason": "campaigns_sync_disabled"}

    email = (payload.get("email") or payload.get("contact_email") or "").strip().lower()
    if not email:
        return {"accepted": False, "reason": "missing_email"}

    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.newsletter_subscribers.update_one(
        {"email": email},
        {"$set": {"unsubscribed": True, "marketing_consent": False, "unsubscribed_at": now, "zoho_unsubscribe_at": now}},
        upsert=False,
    )
    await db.leads.update_one(
        {"email": email},
        {"$set": {"followup_status": "opted_out", "updated_at": now}},
    )
    await log_zoho_webhook_event(
        integration="campaigns",
        event_type="unsubscribe",
        status="success",
        metadata={"email_hash_prefix": email[:3] + "***"},
    )
    return {"accepted": True, "message": "unsubscribe_recorded_in_pleerity"}


async def reject_crm_inbound(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Zoho must never create or update authoritative Pleerity leads."""
    fields = payload.get("data") or payload.get("fields") or payload
    blocked = validate_inbound_crm_fields(fields if isinstance(fields, dict) else {})
    adapter = ZohoCrmAdapter()
    result = await adapter.execute(
        "inbound_rejected",
        {"sync_id": "inbound-reject", "fields": fields},
    )
    await log_zoho_webhook_event(
        integration="crm",
        event_type="inbound_rejected",
        status="rejected",
        metadata={"blocked_fields": blocked},
    )
    return {
        "accepted": False,
        "reason": "crm_inbound_forbidden",
        "blocked_fields": blocked,
        "message": result.message,
    }


async def reject_books_inbound(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Zoho Books must never create or modify authoritative Pleerity billing data."""
    adapter = ZohoBooksAdapter()
    result = await adapter.execute("inbound_rejected", {"sync_id": "inbound-reject"})
    event = str(payload.get("event") or payload.get("type") or "unknown").lower()
    await log_zoho_webhook_event(
        integration="books",
        event_type="inbound_rejected",
        status="rejected",
        metadata={"event": event},
    )
    return {
        "accepted": False,
        "reason": "books_inbound_forbidden",
        "message": result.message,
    }
