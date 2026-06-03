"""
Async compliance recalculation queue (Option B).
Single enqueue function; worker in job_runner processes jobs.
Reuses compliance_scoring_service.recalculate_and_persist — no duplicate scoring logic.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

from pymongo.errors import DuplicateKeyError

from database import database
from services.compliance_recalc_correlation import (
    classify_duplicate_suppression_reason,
    ensure_correlation_id,
)
from utils.compliance_fanout_log import compliance_fanout_extra

logger = logging.getLogger(__name__)

# Trigger reasons (match task correlation_id rules)
TRIGGER_DOC_UPLOADED = "DOC_UPLOADED"
TRIGGER_DOC_DELETED = "DOC_DELETED"
TRIGGER_DOC_STATUS_CHANGED = "DOC_STATUS_CHANGED"
TRIGGER_AI_APPLIED = "AI_APPLIED"
TRIGGER_ADMIN_UPLOAD = "ADMIN_UPLOAD"
TRIGGER_ADMIN_DELETE = "ADMIN_DELETE"
TRIGGER_EXPIRY_JOB = "EXPIRY_JOB"
TRIGGER_PROVISIONING = "PROVISIONING"
TRIGGER_PROPERTY_CREATED = "PROPERTY_CREATED"
TRIGGER_PROPERTY_UPDATED = "PROPERTY_UPDATED"
TRIGGER_ADMIN_MANUAL_JOB = "ADMIN_MANUAL_JOB"
TRIGGER_LAZY_BACKFILL = "LAZY_BACKFILL"
# Daily scheduled sweep: enqueue recalc per property with date-scoped correlation (deduped).
TRIGGER_SCHEDULED_PROPERTY_BATCH = "SCHEDULED_PROPERTY_BATCH"
TRIGGER_CLIENT_JURISDICTION_UPDATED = "CLIENT_JURISDICTION_UPDATED"
# Idempotent batch: enqueue reconciliation for properties that need persisted scores aligned.
TRIGGER_RECONCILIATION_BATCH = "RECONCILIATION_BATCH"

STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_DONE = "DONE"
STATUS_FAILED = "FAILED"
STATUS_DEAD = "DEAD"

# Duplicate enqueue: still mark property pending while worker has not finished.
_DUPLICATE_PENDING_MARK_STATUSES = frozenset({STATUS_PENDING, STATUS_RUNNING, STATUS_FAILED})

ACTOR_CLIENT = "CLIENT"
ACTOR_ADMIN = "ADMIN"
ACTOR_SYSTEM = "SYSTEM"


@dataclass
class EnqueueComplianceRecalcResult:
    """Structured enqueue outcome; ``bool(result)`` == ``result.enqueued`` for backward compatibility."""

    enqueued: bool
    correlation_id: str
    duplicate_suppression_reason: Optional[str] = None
    regeneration_requeued: bool = False
    regeneration_error: Optional[str] = None
    activation_skipped: bool = False
    activation_state: Optional[str] = None
    activation_reason: Optional[str] = None
    activation_scope: Optional[str] = None
    activation_family: Optional[str] = None
    activation_guard_result: Optional[str] = None
    activation_governance_version: Optional[str] = None

    def __bool__(self) -> bool:  # pragma: no cover - thin delegate
        return self.enqueued


async def enqueue_compliance_recalc(
    property_id: str,
    client_id: str,
    trigger_reason: str,
    actor_type: str,
    actor_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> EnqueueComplianceRecalcResult:
    """
    Enqueue a compliance recalc for a property. Idempotent by (property_id, correlation_id).
    Sets compliance_score_pending=true on the property.

    Returns EnqueueComplianceRecalcResult: ``bool(result)`` is True iff a new job row was inserted.
    """
    correlation_id = ensure_correlation_id(
        trigger_reason=trigger_reason,
        property_id=property_id,
        correlation_id=correlation_id,
    )
    from services.workflow_runtime_activation_registry import resolve_compliance_recalc_activation_gate

    activation_ctx = resolve_compliance_recalc_activation_gate()

    db = database.get_db()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    doc = {
        "property_id": property_id,
        "client_id": client_id,
        "trigger_reason": trigger_reason,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "correlation_id": correlation_id,
        "status": STATUS_PENDING,
        "attempts": 0,
        "retry_count": 0,
        "retry_exhausted": False,
        "next_run_at": now_iso,
        "last_error": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    branch: Optional[Tuple[bool, Optional[str]]] = None  # (enqueued, duplicate_reason)
    regen_ok = False
    regen_err: Optional[str] = None

    try:
        if not activation_ctx.get("permitted"):
            branch = (False, None)
            logger.info(
                "compliance_fanout: recalc_enqueue skipped by_activation_gate property_id=%s correlation_id=%s",
                property_id,
                correlation_id,
                extra=compliance_fanout_extra(
                    op="recalc_enqueue",
                    stage="activation_gate",
                    client_id=client_id,
                    property_id=property_id,
                    correlation_id=correlation_id,
                    trigger_reason=trigger_reason,
                    activation_state=str(activation_ctx.get("activation_state") or ""),
                    activation_guard_result=str(activation_ctx.get("activation_guard_result") or ""),
                    activation_governance_version=str(activation_ctx.get("activation_governance_version") or ""),
                ),
            )
        else:
            try:
                await db.compliance_recalc_queue.insert_one(doc)
            except DuplicateKeyError:
                existing = await db.compliance_recalc_queue.find_one(
                    {"property_id": property_id, "correlation_id": correlation_id},
                    {"status": 1},
                )
                reason = classify_duplicate_suppression_reason(existing_status=existing.get("status") if existing else None)
                try:
                    await db.compliance_recalc_queue.update_one(
                        {"property_id": property_id, "correlation_id": correlation_id},
                        {
                            "$inc": {"suppressed_duplicate_enqueue_count": 1},
                            "$set": {
                                "last_duplicate_enqueue_at": now_iso,
                                "last_duplicate_enqueue_trigger": trigger_reason,
                                "last_duplicate_suppression_reason": reason,
                            },
                        },
                    )
                except Exception as counter_err:
                    logger.debug(
                        "compliance_recalc_queue: duplicate visibility counter skipped: %s",
                        counter_err,
                        extra=compliance_fanout_extra(
                            op="recalc_enqueue",
                            stage="duplicate_counter",
                            client_id=client_id,
                            property_id=property_id,
                            correlation_id=correlation_id,
                            trigger_reason=trigger_reason,
                            exc_type=type(counter_err).__name__,
                        ),
                    )
                logger.info(
                    "compliance_fanout: recalc_enqueue duplicate suppressed",
                    extra=compliance_fanout_extra(
                        op="recalc_enqueue",
                        stage="dedupe",
                        client_id=client_id,
                        property_id=property_id,
                        correlation_id=correlation_id,
                        trigger_reason=trigger_reason,
                        dedupe=True,
                        duplicate_suppression_reason=reason,
                    ),
                )
                existing_status = (existing or {}).get("status")
                if existing_status in _DUPLICATE_PENDING_MARK_STATUSES:
                    await db.properties.update_one(
                        {"property_id": property_id},
                        {"$set": {"compliance_score_pending": True}},
                    )
                branch = (False, reason)
            else:
                await db.properties.update_one(
                    {"property_id": property_id},
                    {"$set": {"compliance_score_pending": True}},
                )
                logger.info(
                    "Enqueued compliance recalc property_id=%s correlation_id=%s trigger_reason=%s",
                    property_id,
                    correlation_id,
                    trigger_reason,
                    extra=compliance_fanout_extra(
                        op="recalc_enqueue",
                        stage="inserted",
                        client_id=client_id,
                        property_id=property_id,
                        correlation_id=correlation_id,
                        trigger_reason=trigger_reason,
                    ),
                )
                branch = (True, None)
    finally:
        try:
            from services.risk_signal_regen_queue import enqueue_risk_signal_regen

            await enqueue_risk_signal_regen(
                property_id,
                client_id,
                f"COMPLIANCE_ENQUEUE:{trigger_reason}",
            )
            regen_ok = True
        except Exception as regen_err_exc:
            regen_err = str(regen_err_exc)
            logger.warning(
                "enqueue_compliance_recalc: risk regen schedule failed property_id=%s: %s",
                property_id,
                regen_err_exc,
                extra=compliance_fanout_extra(
                    op="recalc_enqueue",
                    stage="failed",
                    client_id=client_id,
                    property_id=property_id,
                    correlation_id=correlation_id,
                    trigger_reason=trigger_reason,
                    exc_type=type(regen_err_exc).__name__,
                ),
            )

    assert branch is not None
    enq, dup_reason = branch
    skipped = not bool(activation_ctx.get("permitted"))
    return EnqueueComplianceRecalcResult(
        enqueued=enq,
        correlation_id=correlation_id,
        duplicate_suppression_reason=dup_reason,
        regeneration_requeued=regen_ok,
        regeneration_error=regen_err,
        activation_skipped=skipped,
        activation_state=str(activation_ctx.get("activation_state") or "") or None,
        activation_reason=str(activation_ctx.get("activation_reason") or "") or None,
        activation_scope=str(activation_ctx.get("activation_scope") or "") or None,
        activation_family=str(activation_ctx.get("activation_family") or "") or None,
        activation_guard_result=str(activation_ctx.get("activation_guard_result") or "") or None,
        activation_governance_version=str(activation_ctx.get("activation_governance_version") or "") or None,
    )
