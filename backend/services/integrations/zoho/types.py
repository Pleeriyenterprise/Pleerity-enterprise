"""Zoho integration types and constants."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class SyncDirection(str, Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class SyncStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    DEAD_LETTER = "dead_letter"


class SyncSkipReason(str, Enum):
    DISABLED = "integration_disabled"
    KILL_SWITCH = "kill_switch_active"
    NO_CREDENTIALS = "no_credentials"
    CIRCUIT_OPEN = "circuit_breaker_open"
    PII_BLOCKED = "pii_minimisation_blocked"
    AUTHORITY_DENIED = "authority_boundary_denied"
    NOT_CONFIRMED = "business_confirmation_missing"


ZOHO_SYNC_RUNS_COLLECTION = "zoho_sync_runs"
ZOHO_SYNC_DEAD_LETTER_COLLECTION = "zoho_sync_dead_letter"
ZOHO_SYNC_QUEUE_COLLECTION = "zoho_sync_queue"
ZOHO_OAUTH_TOKENS_COLLECTION = "zoho_oauth_tokens"
ZOHO_EXTERNAL_KEYS_COLLECTION = "zoho_external_keys"

CRM_EVENT_CREATED = "lead.created"
CRM_EVENT_UPDATED = "lead.updated"
CRM_EVENT_STAGE_CHANGED = "lead.stage_changed"
CRM_EVENT_CONVERTED = "lead.converted"

AUTHORITY_DENIED_RESOURCE_PREFIXES = (
    "compliance_evidence",
    "requirement_evidence",
    "client_billing",
    "portal_users",
    "properties/",
)


@dataclass
class SyncResult:
    success: bool
    sync_id: str
    integration: str
    operation: str
    status: SyncStatus
    message: str = ""
    external_id: Optional[str] = None
    skip_reason: Optional[SyncSkipReason] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
