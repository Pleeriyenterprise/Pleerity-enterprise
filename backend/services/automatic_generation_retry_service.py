"""
One delayed automatic retry (10 minutes) for FAILED orders when failure looks retryable
and both LLM providers were exhausted due to transient-class errors.

Uses order flags (no dynamic APScheduler job serialization).
Processed by periodic job `generation_auto_retry_processing`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from database import database
from services.admin_failure_summary import classify_generation_error, order_failure_fields_from_message
from services.order_service import transition_order_state, get_order
from services.order_workflow import (
    OrderStatus,
    AUTOMATIC_GENERATION_RETRY_METADATA_KEY,
    AUTOMATIC_GENERATION_RETRY_METADATA_VALUE,
)

logger = logging.getLogger(__name__)


async def persist_generation_failure_on_order(
    order_id: str,
    failure_message: str,
    *,
    both_providers_exhausted: bool = False,
) -> None:
    """Update orders with admin-safe error fields (does not schedule retry)."""
    fields = order_failure_fields_from_message(
        failure_message,
        both_providers_exhausted=both_providers_exhausted,
    )
    db = database.get_db()
    await db.orders.update_one(
        {"order_id": order_id},
        {"$set": fields},
    )


async def maybe_schedule_automatic_generation_retry(
    order_id: str,
    failure_message: str,
    *,
    both_providers_exhausted: bool = False,
) -> None:
    """
    If eligible, mark automatic_retry_attempted and pending retry window.
    Manual admin retry remains allowed afterward (separate guard only while pending).
    """
    if not both_providers_exhausted:
        return

    et, retryable = classify_generation_error(
        failure_message,
        both_providers_exhausted=both_providers_exhausted,
    )
    if not retryable:
        return

    db = database.get_db()
    order = await get_order(order_id)
    if not order:
        return
    if order.get("automatic_retry_attempted"):
        return

    now = datetime.now(timezone.utc)
    due = now + timedelta(minutes=10)
    extra = order_failure_fields_from_message(
        failure_message,
        both_providers_exhausted=both_providers_exhausted,
    )
    res = await db.orders.update_one(
        {
            "order_id": order_id,
            "status": OrderStatus.FAILED.value,
            "automatic_retry_attempted": {"$ne": True},
        },
        {
            "$set": {
                **extra,
                "automatic_retry_attempted": True,
                "retryable_failure": True,
                "automatic_retry_pending": True,
                "scheduled_automatic_retry_at": due,
            }
        },
    )
    if res.modified_count:
        logger.info(
            "Scheduled automatic generation retry for %s at %s (retryable=%s type=%s)",
            order_id,
            due.isoformat(),
            retryable,
            et,
        )


async def process_due_automatic_generation_retries() -> Dict[str, Any]:
    """Pick up orders past scheduled_automatic_retry_at; FAILED→QUEUED; run WF2+WF3."""
    from services.workflow_automation_service import workflow_automation_service

    db = database.get_db()
    now = datetime.now(timezone.utc)
    cursor = db.orders.find(
        {
            "status": OrderStatus.FAILED.value,
            "automatic_retry_pending": True,
            "scheduled_automatic_retry_at": {"$lte": now},
        },
        {"_id": 0, "order_id": 1},
    ).limit(25)
    orders = await cursor.to_list(length=25)
    processed = 0
    errors = 0
    for row in orders:
        oid = row.get("order_id")
        if not oid:
            continue
        lock = await db.orders.update_one(
            {"order_id": oid, "automatic_retry_pending": True},
            {"$set": {"automatic_retry_pending": False}},
        )
        if lock.modified_count == 0:
            continue
        try:
            await transition_order_state(
                order_id=oid,
                new_status=OrderStatus.QUEUED,
                triggered_by_type="system",
                reason="Automatic delayed retry (generation)",
                metadata={
                    AUTOMATIC_GENERATION_RETRY_METADATA_KEY: AUTOMATIC_GENERATION_RETRY_METADATA_VALUE,
                    "workflow_event_code": "AUTOMATIC_RETRY_TRIGGERED",
                },
            )
            gen = await workflow_automation_service.wf2_queue_to_generation(oid, force_retry=True)
            if gen.get("success"):
                await workflow_automation_service.wf3_draft_to_review(oid)
            processed += 1
        except Exception as e:
            errors += 1
            logger.exception("Automatic generation retry failed for %s: %s", oid, e)
            try:
                await db.orders.update_one(
                    {"order_id": oid},
                    {"$set": {"automatic_retry_pending": False}},
                )
            except Exception:
                pass

    return {
        "message": f"auto generation retries: processed={processed} errors={errors}",
        "count": processed,
    }
