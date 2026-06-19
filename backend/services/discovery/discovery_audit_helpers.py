"""
Discovery audit helper scaffolding — Stage C.

Builds and validates audit payloads only. No database writes or workflow wiring.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services.discovery.discovery_models import (
    PLATFORM_TENANT_ID,
    DiscoveryAuditLogDocument,
    generate_discovery_audit_id,
    is_frozen_audit_event,
)

_EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")


class DiscoveryAuditValidationError(ValueError):
    """Raised when audit event type or payload is invalid."""


def validate_audit_event_type(event_type: str) -> str:
    """Validate event_type against frozen taxonomy. Returns normalised type."""
    if not event_type or not str(event_type).strip():
        raise DiscoveryAuditValidationError("event_type is required")
    normalised = str(event_type).strip().upper()
    if not is_frozen_audit_event(normalised):
        raise DiscoveryAuditValidationError(
            f"event_type '{normalised}' is not in frozen audit taxonomy"
        )
    return normalised


def _mask_email(value: str) -> str:
    if "@" not in value:
        return "***"
    local, domain = value.rsplit("@", 1)
    masked_local = (local[:2] + "***") if len(local) > 2 else local[0] + "***"
    return f"{masked_local}@{domain}"


def prepare_audit_payload(details: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Sanitise audit details for storage — mask emails, no raw payload blobs.
    Does not persist; callers use build_audit_event() output in later stages.
    """
    if not details:
        return {}
    clean: Dict[str, Any] = {}
    for key, value in details.items():
        if key in ("raw_payload", "raw_row", "csv_row"):
            continue
        if isinstance(value, str) and _EMAIL_RE.search(value):
            clean[key] = _mask_email(value)
        elif isinstance(value, dict):
            clean[key] = prepare_audit_payload(value)
        else:
            clean[key] = value
    return clean


def build_audit_event(
    *,
    event_type: str,
    prospect_id: Optional[str] = None,
    run_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
    job_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    provider: Optional[str] = None,
    actor_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    reason_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    tenant_id: str = PLATFORM_TENANT_ID,
    created_at: Optional[datetime] = None,
) -> DiscoveryAuditLogDocument:
    """
    Construct a validated audit document. Does not write to discovery_audit_logs.
    """
    validated_type = validate_audit_event_type(event_type)
    now = created_at or datetime.now(timezone.utc)
    return DiscoveryAuditLogDocument(
        audit_id=generate_discovery_audit_id(),
        event_type=validated_type,
        prospect_id=prospect_id,
        run_id=run_id,
        campaign_id=campaign_id,
        job_id=job_id,
        lead_id=lead_id,
        provider=provider,
        actor_id=actor_id,
        actor_email=actor_email,
        reason_code=reason_code,
        details=prepare_audit_payload(details),
        tenant_id=tenant_id,
        created_at=now,
    )
