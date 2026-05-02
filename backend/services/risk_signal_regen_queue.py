"""
Debounced, idempotent queue for near–real-time risk signal regeneration per property.
Coalesces bursts (document uploads, recalcs) into one run per debounce window.
Worker claims PENDING jobs atomically; no concurrent regeneration for the same property.
Does not enqueue compliance recalc (breaks recalc↔risk loops).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from database import database

logger = logging.getLogger(__name__)

STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_DONE = "DONE"
STATUS_FAILED = "FAILED"
STATUS_DEAD = "DEAD"

# Triggers (for audit / debugging)
TRIGGER_COMPLIANCE_RECALC = "COMPLIANCE_RECALC"
TRIGGER_DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
TRIGGER_DOCUMENT_DELETE = "DOCUMENT_DELETE"
TRIGGER_DOCUMENT_STATUS = "DOCUMENT_STATUS"
TRIGGER_PROPERTY_SETTINGS = "PROPERTY_SETTINGS"
TRIGGER_MANUAL = "MANUAL"
TRIGGER_OUTCOME_SYNC = "OUTCOME_SYNC_COMPLETED"  # immediate path already ran; queue should merge only

RISK_REGEN_BACKOFF_SEC = [15, 45, 120, 600]
MAX_TRIGGER_HISTORY = 25


def _debounce_seconds() -> int:
    try:
        return max(15, min(600, int(os.environ.get("RISK_REGEN_DEBOUNCE_SECONDS", "45"))))
    except ValueError:
        return 45


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def enqueue_risk_signal_regen(
    property_id: str,
    client_id: str,
    trigger_reason: str,
    *,
    debounce_override: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Ensure a risk regeneration will run after debounce. At most one PENDING row per property
    (partial unique index). Extends next_run_at on repeat enqueue (debounce coalescing).
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    debounce = debounce_override if debounce_override is not None else _debounce_seconds()
    next_run = (now + timedelta(seconds=debounce)).isoformat()

    existing = await db.risk_signal_regen_queue.find_one(
        {"property_id": property_id, "status": STATUS_PENDING},
    )
    if existing:
        await db.risk_signal_regen_queue.update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "next_run_at": next_run,
                    "updated_at": now.isoformat(),
                    "client_id": client_id,
                },
                "$push": {
                    "trigger_reasons": {
                        "$each": [f"{trigger_reason}@{now.isoformat()}"],
                        "$slice": -MAX_TRIGGER_HISTORY,
                    }
                },
            },
        )
        logger.info(
            "risk_regen_queue merged property_id=%s next_run_at=%s trigger=%s",
            property_id,
            next_run,
            trigger_reason,
        )
        return {"queued": True, "merged": True, "property_id": property_id, "next_run_at": next_run}

    doc = {
        "property_id": property_id,
        "client_id": client_id,
        "status": STATUS_PENDING,
        "next_run_at": next_run,
        "trigger_reasons": [f"{trigger_reason}@{now.isoformat()}"],
        "attempts": 0,
        "last_error": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    try:
        await db.risk_signal_regen_queue.insert_one(doc)
        logger.info(
            "risk_regen_queue enqueued property_id=%s next_run_at=%s trigger=%s",
            property_id,
            next_run,
            trigger_reason,
        )
        return {"queued": True, "merged": False, "property_id": property_id, "next_run_at": next_run}
    except Exception as e:
        if "duplicate key" in str(e).lower() or "E11000" in str(e):
            return await enqueue_risk_signal_regen(
                property_id, client_id, trigger_reason, debounce_override=debounce
            )
        raise


async def run_risk_signal_regen_worker(batch_limit: int = 15) -> Dict[str, Any]:
    """
    Claim PENDING jobs due now, run generate_risk_signals_for_property + operational automation.

    Returns dict consumed by ``run_instrumented`` including ``outcome_status`` and ``outcome_metrics``
    so ``job_runs`` distinguish queue-empty / flag-skips / regenerations / failures without
    treating feature-flag skips as regenerated work.
    """
    from services import risk_signal_service
    from services.job_run_service import (
        OUTCOME_CONDITIONAL_NO_OUTPUT,
        OUTCOME_DEGRADED,
        OUTCOME_FAILED,
        OUTCOME_SUCCESS,
    )
    from services.ops_compliance_feature_flags import get_effective_flags, PREDICTIVE_MAINTENANCE
    from services.operational_automation_service import evaluate_operational_automation_after_risk_refresh
    from models import AuditAction
    from utils.audit import create_audit_log

    db = database.get_db()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    attempted_count = 0
    regenerated_count = 0
    skipped_feature_flag_count = 0
    failed_count = 0

    stale_cutoff = (now - timedelta(minutes=30)).isoformat()
    await db.risk_signal_regen_queue.update_many(
        {"status": STATUS_RUNNING, "updated_at": {"$lt": stale_cutoff}},
        {"$set": {"status": STATUS_PENDING, "updated_at": now_iso}},
    )
    await db.risk_signal_regen_queue.update_many(
        {"status": STATUS_FAILED, "next_run_at": {"$lte": now_iso}},
        {"$set": {"status": STATUS_PENDING, "updated_at": now_iso}},
    )

    for _ in range(max(1, batch_limit)):
        job = await db.risk_signal_regen_queue.find_one_and_update(
            {
                "status": STATUS_PENDING,
                "next_run_at": {"$lte": now_iso},
            },
            {"$set": {"status": STATUS_RUNNING, "updated_at": now_iso}},
            sort=[("next_run_at", 1)],
        )
        if not job:
            break

        attempted_count += 1
        jid = job["_id"]
        property_id = job["property_id"]
        client_id = job.get("client_id") or ""
        attempts = int(job.get("attempts") or 0)

        try:
            if not client_id:
                prop = await db.properties.find_one(
                    {"property_id": property_id},
                    {"_id": 0, "client_id": 1, "billing_plan": 1},
                )
                client_id = (prop or {}).get("client_id") or ""
            client_doc = await db.clients.find_one(
                {"client_id": client_id},
                {"_id": 0, "billing_plan": 1},
            )
            billing = (client_doc or {}).get("billing_plan")
            flags = await get_effective_flags(client_id, billing)
            if not flags.get(PREDICTIVE_MAINTENANCE):
                await db.risk_signal_regen_queue.delete_one({"_id": jid})
                logger.info(
                    "risk_regen_worker skip (no PREDICTIVE_MAINTENANCE) property_id=%s",
                    property_id,
                )
                skipped_feature_flag_count += 1
                continue

            logger.info("risk_regen_worker start property_id=%s client_id=%s", property_id, client_id)
            out = await risk_signal_service.generate_risk_signals_for_property(property_id, client_id)
            await evaluate_operational_automation_after_risk_refresh(property_id, client_id)

            await db.risk_signal_regen_queue.delete_one({"_id": jid})
            await create_audit_log(
                action=AuditAction.RISK_SIGNAL_REGEN_COMPLETED,
                client_id=client_id,
                resource_type="property",
                resource_id=property_id,
                metadata={
                    "generated": out.get("generated"),
                    "previous_active_removed": out.get("previous_active_removed"),
                    "triggers": job.get("trigger_reasons") or [],
                },
            )
            logger.info(
                "risk_regen_worker done property_id=%s generated=%s",
                property_id,
                out.get("generated"),
            )
            regenerated_count += 1
        except Exception as e:
            failed_count += 1
            err_str = str(e)
            next_attempts = attempts + 1
            if next_attempts >= 5:
                await db.risk_signal_regen_queue.update_one(
                    {"_id": jid},
                    {
                        "$set": {
                            "status": STATUS_DEAD,
                            "attempts": next_attempts,
                            "last_error": err_str,
                            "updated_at": _now_iso(),
                        }
                    },
                )
                await create_audit_log(
                    action=AuditAction.RISK_SIGNAL_REGEN_FAILED,
                    client_id=client_id,
                    resource_type="property",
                    resource_id=property_id,
                    metadata={"attempts": next_attempts, "error": err_str, "terminal": True},
                )
                logger.error(
                    "risk_regen_worker DEAD property_id=%s attempts=%s err=%s",
                    property_id,
                    next_attempts,
                    err_str,
                )
            else:
                delta = RISK_REGEN_BACKOFF_SEC[min(next_attempts - 1, len(RISK_REGEN_BACKOFF_SEC) - 1)]
                next_run = (now + timedelta(seconds=delta)).isoformat()
                await db.risk_signal_regen_queue.update_one(
                    {"_id": jid},
                    {
                        "$set": {
                            "status": STATUS_FAILED,
                            "attempts": next_attempts,
                            "last_error": err_str,
                            "next_run_at": next_run,
                            "updated_at": _now_iso(),
                        }
                    },
                )
                await create_audit_log(
                    action=AuditAction.RISK_SIGNAL_REGEN_FAILED,
                    client_id=client_id,
                    resource_type="property",
                    resource_id=property_id,
                    metadata={"attempts": next_attempts, "error": err_str, "next_run_at": next_run},
                )
                logger.warning(
                    "risk_regen_worker retry property_id=%s attempts=%s err=%s",
                    property_id,
                    next_attempts,
                    err_str,
                )

    queue_empty = attempted_count == 0
    outcome_metrics: Dict[str, Any] = {
        "attempted_count": attempted_count,
        "regenerated_count": regenerated_count,
        "skipped_feature_flag_count": skipped_feature_flag_count,
        "failed_count": failed_count,
        "queue_empty": queue_empty,
    }

    if queue_empty:
        outcome_kind = "NO_WORK_ELIGIBLE"
        outcome_status = OUTCOME_CONDITIONAL_NO_OUTPUT
        message = "Risk signal regen worker: no pending jobs (queue empty)"
    elif failed_count > 0 and regenerated_count > 0:
        outcome_kind = "DEGRADED"
        outcome_status = OUTCOME_DEGRADED
        message = (
            f"Risk signal regen worker: {regenerated_count} regenerated, "
            f"{failed_count} failed this batch, {skipped_feature_flag_count} skipped (feature flag)"
        )
    elif failed_count > 0:
        outcome_kind = "FAILED"
        outcome_status = OUTCOME_FAILED
        message = (
            f"Risk signal regen worker: {failed_count} failed, {regenerated_count} regenerated, "
            f"{skipped_feature_flag_count} skipped (feature flag)"
        )
    elif regenerated_count > 0:
        outcome_kind = "WORK_PERFORMED"
        outcome_status = OUTCOME_SUCCESS
        message = (
            f"Risk signal regen worker: {regenerated_count} property/properties regenerated"
            + (
                f", {skipped_feature_flag_count} skipped (predictive maintenance off)"
                if skipped_feature_flag_count
                else ""
            )
        )
    else:
        # attempted > 0 but only feature-flag skips (no regen, no failures)
        outcome_kind = "BLOCKED"
        outcome_status = OUTCOME_CONDITIONAL_NO_OUTPUT
        message = (
            f"Risk signal regen worker: {skipped_feature_flag_count} job(s) cleared "
            f"(predictive maintenance disabled); 0 risk regenerations run"
        )

    outcome_metrics["outcome_kind"] = outcome_kind

    result: Dict[str, Any] = {
        "message": message,
        "count": regenerated_count,
        "outcome_status": outcome_status,
        "outcome_metrics": outcome_metrics,
        # Back-compat for callers that still read ``errors``:
        "errors": failed_count,
    }
    if outcome_status == OUTCOME_DEGRADED:
        result["error_message"] = (
            f"{failed_count} regeneration failure(s) in this run; {regenerated_count} succeeded"
        )
    if outcome_status == OUTCOME_FAILED:
        result["error_code"] = "RISK_SIGNAL_REGEN_BATCH_FAILED"
        result["error_message"] = f"All {failed_count} attempted regeneration(s) failed in this run"
        result["stack_trace"] = None

    return result


async def get_regen_queue_summary(sample_limit: int = 25) -> Dict[str, Any]:
    """
    Admin/ops snapshot: counts by status, oldest pending, recent DEAD/FAILED samples.
    `attention_required` hints dashboards or alerting (not a substitute for full APM).
    """
    db = database.get_db()
    coll = db.risk_signal_regen_queue
    lim = max(1, min(100, int(sample_limit)))
    counts: Dict[str, int] = {}
    for st in (STATUS_PENDING, STATUS_RUNNING, STATUS_FAILED, STATUS_DEAD):
        counts[st] = await coll.count_documents({"status": st})

    oldest_pending = await coll.find_one(
        {"status": STATUS_PENDING},
        {
            "_id": 0,
            "property_id": 1,
            "client_id": 1,
            "next_run_at": 1,
            "trigger_reasons": 1,
            "created_at": 1,
            "attempts": 1,
        },
        sort=[("next_run_at", 1)],
    )
    dead = await coll.find(
        {"status": STATUS_DEAD},
        {
            "_id": 0,
            "property_id": 1,
            "client_id": 1,
            "last_error": 1,
            "attempts": 1,
            "updated_at": 1,
        },
    ).sort("updated_at", -1).limit(lim).to_list(lim)
    failed = await coll.find(
        {"status": STATUS_FAILED},
        {
            "_id": 0,
            "property_id": 1,
            "client_id": 1,
            "last_error": 1,
            "attempts": 1,
            "next_run_at": 1,
            "updated_at": 1,
        },
    ).sort("updated_at", -1).limit(lim).to_list(lim)

    dead_n = counts.get(STATUS_DEAD, 0)
    failed_n = counts.get(STATUS_FAILED, 0)
    attention = dead_n > 0 or failed_n > 5

    return {
        "counts_by_status": counts,
        "oldest_pending_job": oldest_pending,
        "recent_dead": dead,
        "recent_failed": failed,
        "attention_required": attention,
        "sample_limit": lim,
    }
