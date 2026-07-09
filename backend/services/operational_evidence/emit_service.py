"""
Operational Evidence Platform — append-only evidence indexer.

Never replaces authoritative sources. Every event requires an evidence pointer.
Emit failures are logged and never block business logic.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import database

from services.operational_evidence.constants import (
    ALL_CATEGORIES,
    COLLECTION_EVENTS,
    COLLECTION_EXECUTIONS,
    CONFIDENCE_INFERENCE_ONLY,
    CONFIDENCE_LABELS,
    CONFIDENCE_RUNTIME_CONFIRMED,
)
from services.operational_evidence.context import (
    OperationalContext,
    get_operational_context,
    set_operational_context,
)

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_build_sha() -> str:
    for key in ("GIT_COMMIT_SHA", "BUILD_SHA", "RENDER_GIT_COMMIT", "SOURCE_VERSION", "COMMIT_SHA"):
        val = (os.getenv(key) or "").strip()
        if val and val.lower() != "unknown":
            return val
    return "unknown"


def _resolve_environment() -> str:
    return (os.getenv("ENVIRONMENT") or os.getenv("DEPLOYMENT_TIER") or "development").strip().lower()


def _payload_hash(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _validate_emit(
    *,
    category: str,
    event_type: str,
    evidence: Dict[str, Any],
    confidence: int,
) -> None:
    if category not in ALL_CATEGORIES:
        raise ValueError(f"invalid evidence category: {category}")
    if not event_type or not str(event_type).strip():
        raise ValueError("event_type required")
    if not evidence.get("source_collection") or not evidence.get("source_id"):
        raise ValueError("evidence.source_collection and evidence.source_id required")
    if confidence not in CONFIDENCE_LABELS and confidence != CONFIDENCE_INFERENCE_ONLY:
        if confidence < 0 or confidence > 100:
            raise ValueError("confidence must be 0-100")


async def emit_operational_evidence(
    *,
    category: str,
    event_type: str,
    severity: str = "info",
    status: str = "success",
    summary: str,
    evidence: Dict[str, Any],
    source_service: str,
    source_component: str,
    actor: Optional[Dict[str, Any]] = None,
    trigger: Optional[Dict[str, Any]] = None,
    occurred_at: Optional[str] = None,
    duration_ms: Optional[int] = None,
    previous_state: Optional[str] = None,
    new_state: Optional[str] = None,
    customer_impact: Optional[Dict[str, Any]] = None,
    recovery_status: str = "none",
    confidence: int = CONFIDENCE_RUNTIME_CONFIRMED,
    confidence_reason: Optional[str] = None,
    relationship_type: Optional[str] = None,
    parent_event_id: Optional[str] = None,
    caused_by_event_id: Optional[str] = None,
    context: Optional[OperationalContext] = None,
    correlation_overrides: Optional[Dict[str, Optional[str]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    temporal_snapshot: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Append one immutable evidence event. Returns event_id or None on failure.

    Relationships:
    - parent_event_id / caused_by_event_id set explicitly when causality is known
    - previous_event_id derived from context.last_event_id (continuation within execution)
    - next_event_id is never stored (immutable); computed at query time via execution_sequence
    - child_count computed at query time
    """
    try:
        _validate_emit(category=category, event_type=event_type, evidence=evidence, confidence=confidence)
    except ValueError as exc:
        logger.warning("operational_evidence emit rejected: %s", exc)
        return None

    db = database.get_db()
    if db is None:
        logger.warning("operational_evidence emit skipped: database unavailable")
        return None

    ctx = (context or get_operational_context() or OperationalContext()).ensure_execution()
    if correlation_overrides:
        ctx = ctx.with_ids(**correlation_overrides)

    ctx = ctx.next_sequence()
    event_id = str(uuid.uuid4())
    now = _now_iso()
    occurred = occurred_at or now

    previous_event_id = ctx.last_event_id
    ev_doc: Dict[str, Any] = {
        "event_id": event_id,
        "occurred_at": occurred,
        "recorded_at": now,
        "category": category,
        "event_type": event_type,
        "severity": severity,
        "status": status,
        "source_service": source_service,
        "source_component": source_component,
        "actor": actor or {"type": "system", "id": None},
        "trigger": trigger,
        "correlation_id": ctx.correlation_id,
        "execution_id": ctx.execution_id,
        "root_execution_id": ctx.root_execution_id,
        "job_run_id": ctx.job_run_id,
        "incident_id": ctx.incident_id,
        "queue_item_id": ctx.queue_item_id,
        "workflow_id": ctx.workflow_id,
        "notification_id": ctx.notification_id,
        "webhook_id": ctx.webhook_id,
        "property_id": ctx.property_id,
        "requirement_id": ctx.requirement_id,
        "client_id": ctx.client_id,
        "user_id": ctx.user_id,
        "document_id": ctx.document_id,
        "request_id": ctx.request_id,
        "relationships": {
            "parent_event_id": parent_event_id,
            "previous_event_id": previous_event_id,
            "next_event_id": None,
            "caused_by_event_id": caused_by_event_id,
            "relationship_type": relationship_type,
        },
        "execution": {
            "root_execution_id": ctx.root_execution_id,
            "execution_id": ctx.execution_id,
            "execution_depth": ctx.execution_depth,
            "execution_sequence": ctx.execution_sequence,
        },
        "previous_state": previous_state,
        "new_state": new_state,
        "duration_ms": duration_ms,
        "customer_impact": customer_impact
        or {
            "classification": "no_impact",
            "scope": "none",
            "affected_count": 0,
            "summary": "No customer impact",
        },
        "recovery_status": recovery_status,
        "confidence": {
            "score": confidence,
            "label": CONFIDENCE_LABELS.get(confidence, "custom"),
            "reason": confidence_reason or CONFIDENCE_LABELS.get(confidence, "runtime evidence"),
        },
        "evidence": {
            **evidence,
            "summary": evidence.get("summary") or summary,
            "payload_hash": _payload_hash(
                {
                    "source_collection": evidence.get("source_collection"),
                    "source_id": str(evidence.get("source_id")),
                    "event_type": event_type,
                    "occurred_at": occurred,
                }
            ),
        },
        "environment": _resolve_environment(),
        "build_sha": _resolve_build_sha(),
        "temporal_snapshot": temporal_snapshot,
        "metadata": metadata or {},
    }

    try:
        await db[COLLECTION_EVENTS].insert_one(ev_doc)
        await _upsert_execution_summary(db, ctx, event_id, occurred, event_type, summary)
        updated_ctx = ctx.with_ids(last_event_id=event_id)
        set_operational_context(updated_ctx)
        return event_id
    except Exception as exc:
        logger.warning("operational_evidence emit failed: %s", exc, exc_info=True)
        return None


async def _upsert_execution_summary(
    db,
    ctx: OperationalContext,
    event_id: str,
    occurred_at: str,
    event_type: str,
    summary: str,
) -> None:
    """Lightweight execution registry for fast story/tree roots (not authoritative)."""
    root = ctx.root_execution_id
    if not root:
        return
    await db[COLLECTION_EXECUTIONS].update_one(
        {"root_execution_id": root},
        {
            "$setOnInsert": {
                "root_execution_id": root,
                "correlation_id": ctx.correlation_id,
                "started_at": occurred_at,
                "first_event_id": event_id,
            },
            "$set": {
                "last_event_id": event_id,
                "last_occurred_at": occurred_at,
                "last_event_type": event_type,
                "last_summary": summary,
                "updated_at": _now_iso(),
            },
            "$inc": {"event_count": 1},
            "$max": {"max_execution_depth": ctx.execution_depth},
        },
        upsert=True,
    )


def emit_operational_evidence_background(**kwargs: Any) -> None:
    """Fire-and-forget emit; safe to call from sync code paths."""

    async def _run() -> None:
        await emit_operational_evidence(**kwargs)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        asyncio.run(_run())
