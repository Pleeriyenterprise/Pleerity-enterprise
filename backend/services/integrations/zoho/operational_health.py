"""Zoho integration operational health — feeds System Health and Control Centre."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import database
from services.integrations.zoho.circuit_breaker import zoho_circuit_breaker
from services.integrations.zoho.config import (
    INTEGRATION_FLAG_CHECKERS,
    zoho_credentials_configured,
    zoho_integration_enabled,
    zoho_kill_switch_active,
    zoho_refresh_token,
    zoho_shared_oauth_client_configured,
)
from services.integrations.zoho.credential_resolver import resolve_oauth_credentials
from services.integrations.zoho.oauth import zoho_oauth_manager
from services.integrations.zoho.oauth_credential_registry import (
    NON_OAUTH_INTEGRATIONS,
    OAUTH_INTEGRATION_REGISTRY,
    registry_snapshot,
)
from services.integrations.zoho.types import (
    ZOHO_SYNC_DEAD_LETTER_COLLECTION,
    ZOHO_SYNC_QUEUE_COLLECTION,
    ZOHO_SYNC_RUNS_COLLECTION,
    SyncStatus,
)
from services.integrations.zoho.version import version_metadata_snapshot

ACCESS_TOKEN_BUFFER_SECONDS = 300
DEAD_LETTER_DEGRADED_THRESHOLD = 50
QUEUE_LAG_DEGRADED_THRESHOLD = 100
QUEUE_LAG_HOURS = 1


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _oauth_status_label(
    *,
    credentials_configured: bool,
    token_cached: bool,
    token_valid: bool,
    auth_failure_count: int,
) -> str:
    if not credentials_configured:
        return "not_configured"
    if auth_failure_count > 0 and not token_valid:
        return "authentication_failed"
    if token_cached and token_valid:
        return "healthy"
    if token_cached:
        return "cached_expired"
    return "awaiting_refresh"


async def _oauth_health_for_integration(integration: str) -> Dict[str, Any]:
    if integration in NON_OAUTH_INTEGRATIONS:
        return {
            "integration": integration,
            "credentials_configured": False,
            "refresh_token_configured": False,
            "refresh_token_source": "not_applicable",
            "access_token_cached": False,
            "last_successful_refresh": None,
            "token_expiry": None,
            "expires_in_seconds": None,
            "expected_scope": None,
            "oauth_status": "not_applicable",
            "authentication_failures": 0,
            "last_validation_time": None,
            "using_legacy_fallback": False,
            "requires_oauth": False,
        }

    resolved = resolve_oauth_credentials(integration)
    if not resolved:
        return {
            "integration": integration,
            "credentials_configured": False,
            "refresh_token_configured": False,
            "refresh_token_source": "none",
            "access_token_cached": False,
            "last_successful_refresh": None,
            "token_expiry": None,
            "expires_in_seconds": None,
            "expected_scope": None,
            "oauth_status": "unknown_integration",
            "authentication_failures": 0,
            "last_validation_time": None,
            "using_legacy_fallback": False,
            "requires_oauth": True,
        }

    metadata = await zoho_oauth_manager.get_token_metadata(integration)
    expires_at = float(metadata.get("expires_at") or 0)
    now = time.time()
    expires_in = max(0, int(expires_at - now)) if expires_at else None
    token_cached = bool(metadata.get("expires_at"))
    token_valid = expires_at > (now + ACCESS_TOKEN_BUFFER_SECONDS) if expires_at else False
    auth_failures = int(metadata.get("auth_failure_count") or 0)
    token_expiry_iso = (
        datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat() if expires_at else None
    )

    return {
        "integration": integration,
        "credentials_configured": resolved.credentials_configured,
        "refresh_token_configured": resolved.refresh_token_configured,
        "refresh_token_source": resolved.refresh_token_source.value,
        "access_token_cached": token_cached,
        "last_successful_refresh": metadata.get("last_successful_refresh_at"),
        "token_expiry": token_expiry_iso,
        "expires_in_seconds": expires_in,
        "expected_scope": resolved.expected_scope,
        "oauth_status": _oauth_status_label(
            credentials_configured=resolved.credentials_configured,
            token_cached=token_cached,
            token_valid=token_valid,
            auth_failure_count=auth_failures,
        ),
        "authentication_failures": auth_failures,
        "last_validation_time": metadata.get("last_validation_at"),
        "using_legacy_fallback": resolved.using_legacy_fallback,
        "requires_oauth": True,
    }


async def _oauth_health() -> Dict[str, Any]:
    by_integration = {
        name: await _oauth_health_for_integration(name)
        for name in list(OAUTH_INTEGRATION_REGISTRY.keys()) + list(NON_OAUTH_INTEGRATIONS)
    }

    any_valid = any(
        row.get("oauth_status") == "healthy" for row in by_integration.values()
    )
    any_cached = any(row.get("access_token_cached") for row in by_integration.values())

    # Aggregate fields preserved for existing observability consumers.
    return {
        "configured": zoho_credentials_configured(),
        "shared_client_configured": zoho_shared_oauth_client_configured(),
        "legacy_refresh_token_configured": bool(zoho_refresh_token()),
        "token_cached": any_cached,
        "token_valid": any_valid,
        "expires_in_seconds": _min_expires_in(by_integration),
        "by_integration": by_integration,
        "credential_registry": registry_snapshot(),
    }


def _min_expires_in(by_integration: Dict[str, Dict[str, Any]]) -> Optional[int]:
    values = [
        int(row["expires_in_seconds"])
        for row in by_integration.values()
        if row.get("expires_in_seconds") is not None
    ]
    return min(values) if values else None


async def _integration_sync_summary(integration: str, since_iso: str) -> Dict[str, Any]:
    db = database.get_db()
    filt = {"integration": integration}
    last_success = await db[ZOHO_SYNC_RUNS_COLLECTION].find_one(
        {**filt, "status": SyncStatus.SUCCESS.value},
        {"_id": 0, "completed_at": 1, "sync_id": 1, "operation": 1},
        sort=[("completed_at", -1)],
    )
    last_failure = await db[ZOHO_SYNC_RUNS_COLLECTION].find_one(
        {**filt, "status": {"$in": [SyncStatus.FAILED.value, SyncStatus.DEAD_LETTER.value]}},
        {"_id": 0, "completed_at": 1, "sync_id": 1, "operation": 1, "error": 1},
        sort=[("completed_at", -1)],
    )
    failure_count_24h = await db[ZOHO_SYNC_RUNS_COLLECTION].count_documents(
        {
            **filt,
            "status": {"$in": [SyncStatus.FAILED.value, SyncStatus.DEAD_LETTER.value]},
            "completed_at": {"$gte": since_iso},
        }
    )
    cb_open = zoho_circuit_breaker.is_open(integration)
    enabled = bool(INTEGRATION_FLAG_CHECKERS.get(integration) and INTEGRATION_FLAG_CHECKERS[integration]())
    return {
        "enabled": enabled,
        "last_success_at": (last_success or {}).get("completed_at"),
        "last_success_sync_id": (last_success or {}).get("sync_id"),
        "last_failure_at": (last_failure or {}).get("completed_at"),
        "last_failure_sync_id": (last_failure or {}).get("sync_id"),
        "last_failure_error": (last_failure or {}).get("error"),
        "failure_count_24h": failure_count_24h,
        "circuit_breaker": "open" if cb_open else "closed",
    }


async def _queue_stats(now: datetime) -> Dict[str, Any]:
    db = database.get_db()
    pending = await db[ZOHO_SYNC_QUEUE_COLLECTION].count_documents({"status": "pending"})
    processing = await db[ZOHO_SYNC_QUEUE_COLLECTION].count_documents({"status": "processing"})
    oldest = await db[ZOHO_SYNC_QUEUE_COLLECTION].find_one(
        {"status": "pending"},
        {"_id": 0, "created_at": 1},
        sort=[("created_at", 1)],
    )
    oldest_at = (oldest or {}).get("created_at")
    oldest_age_seconds: Optional[int] = None
    if oldest_at:
        parsed = _parse_iso(oldest_at)
        if parsed:
            oldest_age_seconds = int((now - parsed.astimezone(timezone.utc)).total_seconds())
    return {
        "pending": pending,
        "processing": processing,
        "oldest_pending_at": oldest_at,
        "oldest_pending_age_seconds": oldest_age_seconds,
    }


async def _dead_letter_stats() -> Dict[str, Any]:
    db = database.get_db()
    unresolved = await db[ZOHO_SYNC_DEAD_LETTER_COLLECTION].count_documents({"resolved": False})
    oldest = await db[ZOHO_SYNC_DEAD_LETTER_COLLECTION].find_one(
        {"resolved": False},
        {"_id": 0, "created_at": 1, "dead_letter_id": 1},
        sort=[("created_at", 1)],
    )
    return {
        "unresolved": unresolved,
        "oldest_unresolved_at": (oldest or {}).get("created_at"),
        "oldest_unresolved_id": (oldest or {}).get("dead_letter_id"),
    }


async def _webhook_stats_24h(since_iso: str) -> Dict[str, Any]:
    db = database.get_db()
    accepted = 0
    rejected = 0
    auth_failed = 0
    try:
        cursor = db.audit_logs.find(
            {
                "metadata.action_type": "ZOHO_WEBHOOK",
                "created_at": {"$gte": since_iso},
            },
            {"_id": 0, "metadata": 1},
        ).limit(5000)
        async for row in cursor:
            status = str((row.get("metadata") or {}).get("status") or "").lower()
            if status in ("success", "accepted"):
                accepted += 1
            elif status == "rejected":
                rejected += 1
            elif status in ("auth_failed", "unauthorized"):
                auth_failed += 1
    except Exception:
        pass
    return {
        "accepted": accepted,
        "rejected": rejected,
        "auth_failed": auth_failed,
    }


def _derive_overall_status(
    *,
    master_enabled: bool,
    kill_switch: bool,
    oauth: Dict[str, Any],
    integrations: Dict[str, Any],
    queue: Dict[str, Any],
    dead_letter: Dict[str, Any],
    circuit_breakers_open: List[str],
) -> str:
    if not master_enabled:
        return "dormant"
    if kill_switch:
        return "disabled"
    degraded = False
    oauth_by_integration = oauth.get("by_integration") or {}
    for name, row in integrations.items():
        if not row.get("enabled"):
            continue
        oauth_row = oauth_by_integration.get(name) or {}
        if oauth_row.get("requires_oauth") and oauth_row.get("credentials_configured"):
            if oauth_row.get("oauth_status") in ("authentication_failed", "cached_expired"):
                degraded = True
            if oauth_row.get("oauth_status") == "not_configured":
                degraded = True
    if master_enabled and oauth.get("configured") and not oauth.get("token_valid") and oauth.get("token_cached") is False:
        pass
    if dead_letter.get("unresolved", 0) > DEAD_LETTER_DEGRADED_THRESHOLD:
        degraded = True
    if queue.get("pending", 0) > QUEUE_LAG_DEGRADED_THRESHOLD:
        oldest_age = queue.get("oldest_pending_age_seconds")
        if oldest_age is not None and oldest_age > QUEUE_LAG_HOURS * 3600:
            degraded = True
    if circuit_breakers_open:
        degraded = True
    for row in integrations.values():
        if row.get("enabled") and row.get("circuit_breaker") == "open":
            degraded = True
        if row.get("enabled") and row.get("failure_count_24h", 0) > 10:
            degraded = True
    if degraded:
        return "degraded"
    return "healthy"


async def build_zoho_operational_snapshot() -> Dict[str, Any]:
    """Full operational snapshot for admin and platform observability."""
    now = datetime.now(timezone.utc)
    since_24h = (now - timedelta(hours=24)).isoformat()
    master_enabled = zoho_integration_enabled()
    kill_switch = zoho_kill_switch_active()
    oauth = await _oauth_health()
    integrations = {
        name: await _integration_sync_summary(name, since_24h)
        for name in INTEGRATION_FLAG_CHECKERS.keys()
    }
    queue = await _queue_stats(now)
    dead_letter = await _dead_letter_stats()
    webhooks_24h = await _webhook_stats_24h(since_24h)
    circuit_breakers = zoho_circuit_breaker.snapshot()
    circuit_open = [k for k, v in circuit_breakers.items() if v.get("open")]

    overall_status = _derive_overall_status(
        master_enabled=master_enabled,
        kill_switch=kill_switch,
        oauth=oauth,
        integrations=integrations,
        queue=queue,
        dead_letter=dead_letter,
        circuit_breakers_open=circuit_open,
    )

    return {
        "generated_at": now.isoformat(),
        "overall_status": overall_status,
        "zoho_integration_enabled": master_enabled,
        "kill_switch_active": kill_switch,
        "oauth": oauth,
        "integrations": integrations,
        "queue": queue,
        "dead_letter": dead_letter,
        "webhooks_24h": webhooks_24h,
        "circuit_breakers": circuit_breakers,
        "versions": version_metadata_snapshot(),
        "manual_jobs_only": True,
        "admin_path": "/api/admin/integrations/zoho/status",
    }


def build_zoho_operational_health_summary(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure summary over ``build_zoho_operational_snapshot`` — same pattern as recalc queue health.
    """
    queue = snapshot.get("queue") or {}
    dead_letter = snapshot.get("dead_letter") or {}
    oauth = snapshot.get("oauth") or {}
    oauth_by_integration = oauth.get("by_integration") or {}
    circuit_breakers = snapshot.get("circuit_breakers") or {}
    open_breakers = [k for k, v in circuit_breakers.items() if v.get("open")]
    oauth_integrations_healthy = [
        name
        for name, row in oauth_by_integration.items()
        if row.get("requires_oauth") and row.get("oauth_status") == "healthy"
    ]
    oauth_integrations_configured = [
        name
        for name, row in oauth_by_integration.items()
        if row.get("requires_oauth") and row.get("credentials_configured")
    ]
    return {
        "overall_status": snapshot.get("overall_status") or "dormant",
        "zoho_integration_enabled": bool(snapshot.get("zoho_integration_enabled")),
        "kill_switch_active": bool(snapshot.get("kill_switch_active")),
        "oauth_configured": bool(oauth.get("configured")),
        "oauth_shared_client_configured": bool(oauth.get("shared_client_configured")),
        "oauth_token_valid": bool(oauth.get("token_valid")),
        "oauth_integrations_configured": oauth_integrations_configured,
        "oauth_integrations_healthy": oauth_integrations_healthy,
        "queue_depth_pending": int(queue.get("pending") or 0),
        "queue_depth_processing": int(queue.get("processing") or 0),
        "dead_letter_unresolved": int(dead_letter.get("unresolved") or 0),
        "circuit_breakers_open": open_breakers,
        "circuit_breaker_open_count": len(open_breakers),
        "webhooks_accepted_24h": int((snapshot.get("webhooks_24h") or {}).get("accepted") or 0),
        "webhooks_rejected_24h": int((snapshot.get("webhooks_24h") or {}).get("rejected") or 0),
        "integration_layer_version": (snapshot.get("versions") or {}).get("integration_layer_version"),
        "manual_jobs_only": True,
        "health_posture": "INTEGRATED_WITH_PLATFORM_OBSERVABILITY",
        "admin_path": snapshot.get("admin_path"),
    }
