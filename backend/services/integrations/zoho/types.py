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
    DUPLICATE_PERIOD = "period_already_exported"
    PAYLOAD_INVALID = "payload_validation_failed"
    CONFIG_INVALID = "config_validation_failed"
    RUN_LOCK_HELD = "run_lock_held"


ZOHO_SYNC_RUNS_COLLECTION = "zoho_sync_runs"
ZOHO_SYNC_DEAD_LETTER_COLLECTION = "zoho_sync_dead_letter"
ZOHO_SYNC_QUEUE_COLLECTION = "zoho_sync_queue"
ZOHO_OAUTH_TOKENS_COLLECTION = "zoho_oauth_tokens"
ZOHO_EXTERNAL_KEYS_COLLECTION = "zoho_external_keys"
ZOHO_ANALYTICS_EXPORT_LOCKS_COLLECTION = "zoho_analytics_export_locks"
# CRM / shared queue claim lease (seconds). Abandoned processing rows become reclaimable.
ZOHO_QUEUE_LEASE_SECONDS = 120
ANALYTICS_EXPORT_JOB_ID = "zoho_analytics_export"
ANALYTICS_EXPORT_SCHEDULE_CADENCE = "Daily 02:15 UTC"
ANALYTICS_EXPORT_LOCK_ID = "zoho_analytics_export_active"

CRM_EVENT_CREATED = "lead.created"
CRM_EVENT_UPDATED = "lead.updated"
CRM_EVENT_STAGE_CHANGED = "lead.stage_changed"
CRM_EVENT_CONVERTED = "lead.converted"
CRM_EVENT_LOST = "lead.lost"
CRM_OPERATION_UPSERT = "upsert_lead"

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
