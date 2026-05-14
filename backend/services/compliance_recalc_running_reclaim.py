"""
Stale RUNNING recovery for compliance_recalc_queue (parity with risk_signal_regen_queue).

Uses a liveness timestamp: max(heartbeat_at, updated_at) when heartbeat_at is set,
otherwise updated_at. Reclaim is atomic per document (race-safe with concurrent workers).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Tuple

from services.compliance_recalc_queue import (
    STATUS_DEAD,
    STATUS_PENDING,
    STATUS_RUNNING,
)

logger = logging.getLogger(__name__)

COMPLIANCE_RECALC_MAX_ATTEMPTS = 5
RECLAIM_REASON = "STALE_RUNNING_EXCEEDED_THRESHOLD"
RECLAIM_ERROR_PREFIX = "STALE_RUNNING_RECLAIMED:"


def compliance_recalc_running_stale_seconds() -> int:
    raw = os.getenv("COMPLIANCE_RECALC_RUNNING_STALE_SECONDS", "1800")
    try:
        sec = int(raw)
    except (TypeError, ValueError):
        sec = 1800
    return max(60, sec)


def mongo_running_liveness_stale_filter(stale_cut_iso: str) -> Dict[str, Any]:
    """
    Match RUNNING rows whose liveness (heartbeat vs claim time) is older than stale_cut_iso.

    ISO strings compared lexicographically (UTC isoformat from this codebase).
    """
    return {
        "status": STATUS_RUNNING,
        "$expr": {
            "$lt": [
                {
                    "$max": [
                        {"$ifNull": ["$heartbeat_at", "$updated_at"]},
                        "$updated_at",
                    ]
                },
                stale_cut_iso,
            ]
        },
    }


def _atomic_stale_running_filter(jid: Any, stale_cut_iso: str) -> Dict[str, Any]:
    return {"_id": jid, **mongo_running_liveness_stale_filter(stale_cut_iso)}


async def reclaim_stale_running_compliance_recalc_jobs(
    db,
    *,
    now: Optional[datetime] = None,
    max_rows: int = 200,
) -> Dict[str, Any]:
    """
    Reclaim RUNNING rows with stale liveness: increment attempts; PENDING retry or DEAD if exhausted.

    Returns counts and does not raise on partial progress.
    """
    from models import AuditAction
    from utils.audit import create_audit_log

    now_dt = now or datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    stale_sec = compliance_recalc_running_stale_seconds()
    stale_cut = (now_dt - timedelta(seconds=stale_sec)).isoformat()

    reclaimed_to_pending = 0
    reclaimed_to_dead = 0
    skipped_race = 0

    for _ in range(max(1, max_rows)):
        doc = await db.compliance_recalc_queue.find_one(
            mongo_running_liveness_stale_filter(stale_cut),
            sort=[("updated_at", 1)],
        )
        if not doc:
            break
        jid = doc["_id"]
        property_id = doc.get("property_id", "")
        client_id = doc.get("client_id", "")
        prev_attempts = int(doc.get("attempts") or 0)
        prev_updated = doc.get("updated_at")
        prev_heartbeat = doc.get("heartbeat_at")
        new_attempts = prev_attempts + 1

        reclaim_meta = {
            "reclaimed_at": now_iso,
            "reclaimed_reason": RECLAIM_REASON,
            "previous_updated_at": prev_updated,
            "previous_attempts": prev_attempts,
            "previous_heartbeat_at": prev_heartbeat,
        }
        err_msg = (
            f"{RECLAIM_ERROR_PREFIX} no terminal completion within {stale_sec}s "
            f"(liveness stale; attempts after reclaim increment={new_attempts})"
        )

        if new_attempts >= COMPLIANCE_RECALC_MAX_ATTEMPTS:
            dead_fields: Dict[str, Any] = {
                "status": STATUS_DEAD,
                "attempts": new_attempts,
                "retry_count": new_attempts,
                "retry_exhausted": True,
                "next_run_at": now_iso,
                "last_error": err_msg,
                "updated_at": now_iso,
                "failure_stage": "stale_running_reclaim",
                "last_retry_at": now_iso,
                "dead_state_at": now_iso,
                "dead_state_reason": err_msg[:4000],
                "recalc_execution_signals": {
                    "degraded_execution": True,
                    "partial_recovery": False,
                    "retry_pending": False,
                    "reconciliation_recommended": True,
                },
                **reclaim_meta,
            }
            res = await db.compliance_recalc_queue.update_one(
                _atomic_stale_running_filter(jid, stale_cut),
                {"$set": dead_fields, "$unset": {"heartbeat_at": ""}},
            )
            if res.modified_count:
                reclaimed_to_dead += 1
                await create_audit_log(
                    action=AuditAction.COMPLIANCE_RECALC_FAILED,
                    client_id=client_id,
                    resource_type="property",
                    resource_id=property_id,
                    metadata={
                        "attempts": new_attempts,
                        "error": err_msg,
                        "correlation_id": doc.get("correlation_id"),
                        "trigger_reason": doc.get("trigger_reason"),
                        "failure_stage": "stale_running_reclaim",
                        "retry_exhausted": True,
                        "dead_state_at": now_iso,
                        "dead_state_reason": err_msg[:2000],
                        "reclaimed": True,
                    },
                )
                logger.warning(
                    "compliance_recalc_queue: stale RUNNING reclaimed to DEAD queue_id=%s property_id=%s attempts=%s",
                    jid,
                    property_id,
                    new_attempts,
                )
            else:
                skipped_race += 1
        else:
            pending_fields: Dict[str, Any] = {
                "status": STATUS_PENDING,
                "attempts": new_attempts,
                "retry_count": new_attempts,
                "next_run_at": now_iso,
                "last_error": err_msg,
                "updated_at": now_iso,
                "failure_stage": "stale_running_reclaim",
                "retry_exhausted": False,
                "last_retry_at": now_iso,
                "recalc_execution_signals": {
                    "degraded_execution": False,
                    "partial_recovery": True,
                    "retry_pending": True,
                    "reconciliation_recommended": False,
                },
                **reclaim_meta,
            }
            res = await db.compliance_recalc_queue.update_one(
                _atomic_stale_running_filter(jid, stale_cut),
                {"$set": pending_fields, "$unset": {"heartbeat_at": ""}},
            )
            if res.modified_count:
                reclaimed_to_pending += 1
                await create_audit_log(
                    action=AuditAction.COMPLIANCE_RECALC_FAILED,
                    client_id=client_id,
                    resource_type="property",
                    resource_id=property_id,
                    metadata={
                        "attempts": new_attempts,
                        "error": err_msg,
                        "correlation_id": doc.get("correlation_id"),
                        "trigger_reason": doc.get("trigger_reason"),
                        "failure_stage": "stale_running_reclaim",
                        "retry_exhausted": False,
                        "reclaimed": True,
                        "next_run_at": now_iso,
                    },
                )
                logger.info(
                    "compliance_recalc_queue: stale RUNNING reclaimed to PENDING queue_id=%s property_id=%s attempts=%s",
                    jid,
                    property_id,
                    new_attempts,
                )
            else:
                skipped_race += 1

    total = reclaimed_to_pending + reclaimed_to_dead
    if total:
        logger.info(
            "compliance_recalc_queue: stale RUNNING reclaim pass complete pending=%s dead=%s skipped_race=%s stale_sec=%s",
            reclaimed_to_pending,
            reclaimed_to_dead,
            skipped_race,
            stale_sec,
        )
    return {
        "reclaimed_to_pending": reclaimed_to_pending,
        "reclaimed_to_dead": reclaimed_to_dead,
        "skipped_race": skipped_race,
        "stale_threshold_seconds": stale_sec,
    }


def outcome_metrics_reclaim_prefix() -> Tuple[str, str]:
    """Outcome metric keys for job_runs / worker summaries."""
    return ("stale_running_reclaimed_to_pending", "stale_running_reclaimed_to_dead")
