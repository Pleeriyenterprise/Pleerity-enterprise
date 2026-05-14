"""
Shared job runner for scheduled background jobs.
Used by server (scheduler) and admin (manual run).
Each run_* returns a dict with "message" (and optionally "count") for admin toast.
Job execution is persisted via job_run_service for observability and SLA watchdog.
"""
import asyncio
import inspect
import logging
import os
import traceback
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def _filter_kwargs_for_callable(fn: Callable[..., Any], kw: Dict[str, Any]) -> Dict[str, Any]:
    """Pass only parameters the job runner function declares (plus optional **kwargs)."""
    if not kw:
        return {}
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return {}
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return dict(kw)
    return {k: v for k, v in kw.items() if k in sig.parameters}


async def run_instrumented(
    job_id: str,
    run_type: str,
    triggered_by: Optional[str] = None,
    *,
    job_kwargs: Optional[Dict[str, Any]] = None,
    start_metadata: Optional[Dict[str, Any]] = None,
) -> dict:
    """
    Run a job by id with start/finish persistence. Used by scheduler and admin.
    run_type: "schedule" | "manual" | "webhook"
    """
    from job_runner import JOB_RUNNERS
    from services.job_run_service import (
        start_job_run,
        finish_job_run_success,
        finish_job_run_failure,
        finish_job_run_degraded,
        OUTCOME_SUCCESS,
        OUTCOME_DEGRADED,
        OUTCOME_FAILED,
        STATUS_SUCCESS,
        STATUS_DEGRADED,
    )
    fn = JOB_RUNNERS.get(job_id)
    if not fn:
        logger.error("run_instrumented: unknown job_id=%s (not in JOB_RUNNERS); no job_runs row will be created", job_id)
        raise ValueError(f"Unknown job_id: {job_id}")
    logger.info("run_instrumented: starting job_id=%s run_type=%s (will call start_job_run)", job_id, run_type)
    meta = dict(start_metadata or {})
    kw = {k: v for k, v in dict(job_kwargs or {}).items() if v is not None}
    if job_id == "monthly_digest" and triggered_by:
        kw.setdefault("triggered_by_admin_id", triggered_by)
    job_run_id = await start_job_run(
        job_id, run_type, triggered_by=triggered_by, metadata=meta if meta else None
    )
    logger.info("run_instrumented: start_job_run returned job_run_id=%s for job_id=%s", job_run_id, job_id)
    try:
        call_kw = _filter_kwargs_for_callable(fn, kw)
        if call_kw:
            result = await fn(**call_kw)
        else:
            result = await fn()
        if not isinstance(result, dict):
            result = {"message": str(result), "count": result if isinstance(result, (int, float)) else None}
        count = result.get("count")
        outcome_status = result.get("outcome_status", OUTCOME_SUCCESS)
        outcome_metrics = result.get("outcome_metrics") or {}

        if outcome_status == OUTCOME_FAILED:
            await finish_job_run_failure(
                job_run_id,
                error_code=result.get("error_code", "JobReportedFailed"),
                error_message=result.get("error_message", "Job completed with outcome_status=failed"),
                stack_trace=result.get("stack_trace"),
                outcome_metrics=outcome_metrics if outcome_metrics else None,
            )
            return result
        if outcome_status == OUTCOME_DEGRADED:
            await finish_job_run_degraded(
                job_run_id,
                affected_clients_count=count,
                outcome_metrics=outcome_metrics,
                error_message=result.get("error_message"),
            )
            now_iso = datetime.now(timezone.utc).isoformat()
            try:
                from services.incident_recovery import resolve_recovered_incidents_for_job
                n = await resolve_recovered_incidents_for_job(job_id, now_iso, STATUS_DEGRADED, job_run_id)
                if n:
                    logger.info("Incident recovery: resolved %s incident(s) for job %s after degraded run", n, job_id)
            except Exception as rec_err:
                logger.warning("Incident recovery after degraded run failed: %s", rec_err)
            return result
        await finish_job_run_success(
            job_run_id,
            affected_clients_count=count,
            outcome_status=outcome_status,
            outcome_metrics=outcome_metrics if outcome_metrics else None,
        )
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            from services.incident_recovery import resolve_recovered_incidents_for_job
            n = await resolve_recovered_incidents_for_job(job_id, now_iso, STATUS_SUCCESS, job_run_id)
            if n:
                logger.info("Incident recovery: resolved %s incident(s) for job %s after success", n, job_id)
        except Exception as rec_err:
            logger.warning("Incident recovery after success failed: %s", rec_err)
        return result
    except Exception as e:
        await finish_job_run_failure(
            job_run_id,
            error_code=type(e).__name__,
            error_message=str(e),
            stack_trace=traceback.format_exc(),
        )
        raise


def make_instrumented(job_id: str, run_type: str = "schedule"):
    """Return an async callable that runs the job with instrumentation (for scheduler).
    Note: When using a persistent job store (e.g. MongoDB), do NOT pass this callable to
    add_job—it cannot be pickled. Use run_scheduled_job with a string reference instead.
    """
    async def _run():
        return await run_instrumented(job_id, run_type, triggered_by=None)
    return _run


async def run_scheduled_job(job_id: str, run_type: str = "schedule"):
    """
    Top-level entry point for the scheduler. Must be a module-level function so that
    APScheduler can store jobs in MongoDB (pickle requires a resolvable module:func reference).
    Use in server.py as: add_job("job_runner:run_scheduled_job", ..., args=[job_id], kwargs={"run_type": "schedule"}).
    """
    return await run_instrumented(job_id, run_type, triggered_by=None)


async def run_daily_reminders(client_id: Optional[str] = None):
    try:
        from services.jobs import JobScheduler
        job_scheduler = JobScheduler()
        await job_scheduler.connect()
        result = await job_scheduler.send_daily_reminders(
            client_id=str(client_id).strip() if client_id and str(client_id).strip() else None
        )
        await job_scheduler.close()
        if isinstance(result, dict):
            logger.info("Daily reminders job completed: %s", result.get("message", result))
            return result
        return {"message": f"Daily reminders sent: {result}", "count": result}
    except Exception as e:
        logger.error("Daily reminders job failed: %s", e)
        raise


async def run_pending_verification_digest():
    try:
        from services.jobs import JobScheduler
        job_scheduler = JobScheduler()
        await job_scheduler.connect()
        result = await job_scheduler.send_pending_verification_digest()
        await job_scheduler.close()
        if isinstance(result, dict):
            logger.info("Pending verification digest job completed: %s", result.get("message", result))
            return result
        return {"message": f"Pending verification digest sent: {result} emails", "count": result}
    except Exception as e:
        logger.error("Pending verification digest job failed: %s", e)
        raise


async def run_monthly_digests(
    client_id=None,
    triggered_by_admin_id=None,
    property_ids=None,
    **__,
):
    try:
        from services.jobs import JobScheduler
        job_scheduler = JobScheduler()
        await job_scheduler.connect()
        if client_id and str(client_id).strip():
            pids = None
            if property_ids:
                pids = [str(p).strip() for p in property_ids if p and str(p).strip()]
                if not pids:
                    pids = None
            result = await job_scheduler.send_monthly_digest_for_client(
                str(client_id).strip(),
                force=True,
                triggered_by_admin_id=triggered_by_admin_id,
                property_ids=pids,
            )
        else:
            result = await job_scheduler.send_monthly_digests()
        await job_scheduler.close()
        if isinstance(result, dict):
            logger.info("Monthly digest job completed: %s", result.get("message", result))
            return result
        return {"message": f"Monthly digests sent: {result}", "count": result}
    except Exception as e:
        logger.error("Monthly digest job failed: %s", e)
        raise


async def run_compliance_status_check(client_id: Optional[str] = None):
    try:
        from services.jobs import JobScheduler
        job_scheduler = JobScheduler()
        await job_scheduler.connect()
        result = await job_scheduler.check_compliance_status_changes(
            client_id=str(client_id).strip() if client_id and str(client_id).strip() else None
        )
        await job_scheduler.close()
        if isinstance(result, dict):
            logger.info("Compliance status check completed: %s", result.get("message", result))
            return result
        return {"message": f"Compliance alerts sent: {result}", "count": result}
    except Exception as e:
        logger.error("Compliance status check failed: %s", e)
        raise


async def run_scheduled_reports():
    try:
        from services.jobs import run_scheduled_reports as process_reports
        result = await process_reports()
        if isinstance(result, dict):
            logger.info("Scheduled reports job completed: %s", result.get("message", result))
            return result
        return {"message": f"Scheduled reports sent: {result}", "count": result}
    except Exception as e:
        logger.error("Scheduled reports job failed: %s", e)
        raise


async def run_compliance_score_snapshots(client_id: Optional[str] = None):
    try:
        from services.compliance_trending import capture_all_client_snapshots
        from services.compliance_snapshot_job_outcomes import build_compliance_score_snapshots_run_result

        result = await capture_all_client_snapshots(
            client_id=str(client_id).strip() if client_id and str(client_id).strip() else None
        )
        out = build_compliance_score_snapshots_run_result(result)
        logger.info("Compliance score snapshots job outcome: %s", out.get("message"))
        return out
    except Exception as e:
        logger.error(f"Compliance score snapshots job failed: {e}")
        raise


# Backoff seconds: attempt 1 => +10s, 2 => +30s, 3 => +2m, 4 => +10m, >=5 => DEAD
COMPLIANCE_RECALC_BACKOFF = [10, 30, 120, 600]


async def run_compliance_recalc_worker():
    """
    Process compliance_recalc_queue: claim PENDING jobs, run recalculate_and_persist,
    optional drift audit, retry with backoff or mark DEAD.
    """
    try:
        from database import database
        from services.compliance_recalc_queue import (
            STATUS_PENDING,
            STATUS_RUNNING,
            STATUS_DONE,
            STATUS_FAILED,
            STATUS_DEAD,
        )
        from services.compliance_recalc_correlation import normalize_recalc_job_context
        from services.compliance_recalc_running_reclaim import reclaim_stale_running_compliance_recalc_jobs
        from services.compliance_recalc_worker_job_outcomes import build_compliance_recalc_worker_run_result
        from services.compliance_scoring_service import recalculate_and_persist
        from models import AuditAction
        from utils.audit import create_audit_log

        db = database.get_db()
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        reclaim_stats = await reclaim_stale_running_compliance_recalc_jobs(db, now=now)
        reclaimed_to_pending = int(reclaim_stats.get("reclaimed_to_pending") or 0)
        reclaimed_to_dead = int(reclaim_stats.get("reclaimed_to_dead") or 0)

        async def _heartbeat_while_running(job_id: Any) -> None:
            try:
                interval = max(20, int(os.getenv("COMPLIANCE_RECALC_HEARTBEAT_SECONDS", "45")))
            except (TypeError, ValueError):
                interval = 45
            while True:
                await asyncio.sleep(interval)
                hb = datetime.now(timezone.utc).isoformat()
                r = await db.compliance_recalc_queue.update_one(
                    {"_id": job_id, "status": STATUS_RUNNING},
                    {"$set": {"heartbeat_at": hb}},
                )
                if r.matched_count == 0:
                    break

        cursor = db.compliance_recalc_queue.find(
            {"status": STATUS_PENDING, "next_run_at": {"$lte": now_iso}}
        ).sort("next_run_at", 1).limit(10)
        jobs = await cursor.to_list(10)
        batch_size = len(jobs)
        claim_skipped = 0
        processed = 0
        failed_retry = 0
        dead_count = 0
        for job in jobs:
            jid = job["_id"]
            property_id = job["property_id"]
            client_id = job.get("client_id")
            trigger_reason = job.get("trigger_reason", "")
            correlation_id = job.get("correlation_id", "")
            actor_type = job.get("actor_type", "SYSTEM")
            actor_id = job.get("actor_id")
            attempts = job.get("attempts", 0)
            claim_iso = datetime.now(timezone.utc).isoformat()
            # Atomic claim + initial lease heartbeat (RUNNING_STUCK / reclaim use liveness)
            r = await db.compliance_recalc_queue.update_one(
                {"_id": jid, "status": STATUS_PENDING},
                {"$set": {"status": STATUS_RUNNING, "updated_at": claim_iso, "heartbeat_at": claim_iso}},
            )
            if r.modified_count == 0:
                claim_skipped += 1
                continue
            actor = {"id": actor_id or "system", "role": actor_type}
            _nctx = normalize_recalc_job_context(job)
            context = {
                "correlation_id": (_nctx.get("correlation_id") or correlation_id or ""),
                "trigger_reason": (_nctx.get("trigger_reason") or trigger_reason or ""),
            }
            old_prop = await db.properties.find_one(
                {"property_id": property_id},
                {"_id": 0, "compliance_score": 1, "compliance_version": 1},
            )
            old_score = old_prop.get("compliance_score") if old_prop else None
            hb_task = asyncio.create_task(_heartbeat_while_running(jid))
            try:
                await recalculate_and_persist(property_id, trigger_reason, actor, context)
                prop_after = await db.properties.find_one(
                    {"property_id": property_id},
                    {"_id": 0, "compliance_score": 1},
                )
                new_score = prop_after.get("compliance_score") if prop_after else None
                if old_score is not None and new_score is not None and old_score != new_score:
                    await create_audit_log(
                        action=AuditAction.COMPLIANCE_SCORE_DRIFT_DETECTED,
                        actor_id=actor_id,
                        client_id=client_id,
                        resource_type="property",
                        resource_id=property_id,
                        before_state={"compliance_score": old_score},
                        after_state={"compliance_score": new_score},
                        metadata={
                            "correlation_id": correlation_id,
                            "trigger_reason": trigger_reason,
                        },
                    )
                # Score events: record SCORE_RECALCULATED for client-level trend and "What Changed"
                try:
                    from services.compliance_score import calculate_compliance_score
                    from services.score_events_service import (
                        write_score_event,
                        EVENT_SCORE_RECALCULATED,
                        ACTOR_ROLE_SYSTEM,
                        ACTOR_ROLE_CLIENT,
                        ACTOR_ROLE_ADMIN,
                    )
                    client_score_data = await calculate_compliance_score(client_id)
                    score_after = client_score_data.get("score")
                    if score_after is not None:
                        last_recalc = await db.score_events.find_one(
                            {"client_id": client_id, "event_type": EVENT_SCORE_RECALCULATED},
                            {"_id": 0, "score_after": 1},
                            sort=[("created_at", -1)],
                        )
                        score_before = last_recalc.get("score_after") if last_recalc else None
                        delta = (score_after - score_before) if score_before is not None else None
                        actor_role = ACTOR_ROLE_SYSTEM
                        if actor_type == "CLIENT":
                            actor_role = ACTOR_ROLE_CLIENT
                        elif actor_type == "ADMIN":
                            actor_role = ACTOR_ROLE_ADMIN
                        await write_score_event(
                            client_id=client_id,
                            event_type=EVENT_SCORE_RECALCULATED,
                            actor_user_id=actor_id,
                            actor_role=actor_role,
                            property_id=property_id,
                            metadata={"trigger_reason": trigger_reason, "correlation_id": correlation_id},
                            score_before=int(score_before) if score_before is not None else None,
                            score_after=int(score_after),
                            delta=int(delta) if delta is not None else None,
                        )
                except Exception as ev_err:
                    logger.warning("Score event write failed after recalc: %s", ev_err)
                try:
                    from services.automation_status_service import record_score_recalc

                    await record_score_recalc(client_id)
                except Exception as auto_err:
                    logger.debug("automation_status score recalc stamp skipped: %s", auto_err)
                done_iso = datetime.now(timezone.utc).isoformat()
                await db.compliance_recalc_queue.update_one(
                    {"_id": jid},
                    {
                        "$set": {
                            "status": STATUS_DONE,
                            "updated_at": done_iso,
                            "recalc_execution_signals": {
                                "degraded_execution": False,
                                "partial_recovery": False,
                                "retry_pending": False,
                                "reconciliation_recommended": False,
                            },
                        },
                        "$unset": {"heartbeat_at": ""},
                    },
                )
                processed += 1
            except Exception as e:
                next_attempts = attempts + 1
                if next_attempts >= 5:
                    new_status = STATUS_DEAD
                    next_run_at = now_iso
                    dead_count += 1
                else:
                    new_status = STATUS_FAILED
                    delta = COMPLIANCE_RECALC_BACKOFF[min(next_attempts - 1, len(COMPLIANCE_RECALC_BACKOFF) - 1)]
                    next_run_at = (now + timedelta(seconds=delta)).isoformat()
                    failed_retry += 1
                err_str = str(e)
                upd_iso = datetime.now(timezone.utc).isoformat()
                failure_stage = "recalculate_and_persist"
                retry_exhausted = new_status == STATUS_DEAD
                signals = {
                    "degraded_execution": bool(retry_exhausted),
                    "partial_recovery": False,
                    "retry_pending": new_status == STATUS_FAILED,
                    "reconciliation_recommended": retry_exhausted,
                }
                fail_fields: Dict[str, Any] = {
                    "status": new_status,
                    "attempts": next_attempts,
                    "retry_count": next_attempts,
                    "next_run_at": next_run_at,
                    "last_error": err_str,
                    "updated_at": upd_iso,
                    "failure_stage": failure_stage,
                    "retry_exhausted": retry_exhausted,
                    "recalc_execution_signals": signals,
                    "last_retry_at": upd_iso,
                }
                if new_status == STATUS_DEAD:
                    fail_fields["dead_state_at"] = upd_iso
                    fail_fields["dead_state_reason"] = err_str[:4000] if err_str else None
                await db.compliance_recalc_queue.update_one(
                    {"_id": jid},
                    {"$set": fail_fields, "$unset": {"heartbeat_at": ""}},
                )
                audit_meta: Dict[str, Any] = {
                    "attempts": next_attempts,
                    "retry_count": next_attempts,
                    "error": err_str,
                    "correlation_id": correlation_id,
                    "trigger_reason": trigger_reason,
                    "failure_stage": failure_stage,
                    "retry_exhausted": retry_exhausted,
                    "last_retry_at": upd_iso,
                }
                if new_status == STATUS_DEAD:
                    audit_meta["dead_state_at"] = upd_iso
                    audit_meta["dead_state_reason"] = (err_str[:2000] if err_str else None)
                await create_audit_log(
                    action=AuditAction.COMPLIANCE_RECALC_FAILED,
                    actor_id=actor_id,
                    client_id=client_id,
                    resource_type="property",
                    resource_id=property_id,
                    metadata=audit_meta,
                )
                logger.warning(
                    "Compliance recalc failed property_id=%s correlation_id=%s attempts=%s failure_stage=%s err=%s",
                    property_id,
                    correlation_id,
                    next_attempts,
                    failure_stage,
                    err_str,
                )
            finally:
                hb_task.cancel()
                try:
                    await hb_task
                except asyncio.CancelledError:
                    pass
        return build_compliance_recalc_worker_run_result(
            {
                "batch_size": batch_size,
                "claim_skipped": claim_skipped,
                "processed": processed,
                "failed_retry": failed_retry,
                "dead": dead_count,
                "stale_running_reclaimed_to_pending": reclaimed_to_pending,
                "stale_running_reclaimed_to_dead": reclaimed_to_dead,
            }
        )
    except Exception as e:
        logger.error(f"Compliance recalc worker failed: {e}")
        raise


async def run_expiry_rollover_recalc():
    """Daily job: enqueue compliance recalc for properties whose requirements' due_date
    crossed expiry/expiring_soon thresholds. Worker will run recalc.
    """
    try:
        from database import database
        from datetime import timedelta
        from services.compliance_recalc_queue import (
            enqueue_compliance_recalc,
            TRIGGER_EXPIRY_JOB,
            ACTOR_SYSTEM,
        )

        db = database.get_db()
        now = datetime.now(timezone.utc)
        window_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        window_end = (now + timedelta(days=31)).replace(hour=23, minute=59, second=59, microsecond=999000)
        window_start_iso = window_start.isoformat()
        window_end_iso = window_end.isoformat()
        date_str = now.strftime("%Y-%m-%d")

        cursor = db.requirements.find(
            {"due_date": {"$gte": window_start_iso, "$lte": window_end_iso}},
            {"property_id": 1}
        )
        property_ids = set()
        async for doc in cursor:
            property_ids.add(doc["property_id"])

        count = 0
        for property_id in property_ids:
            prop = await db.properties.find_one({"property_id": property_id}, {"client_id": 1})
            if not prop:
                continue
            correlation_id = f"EXPIRY_JOB:{property_id}:{date_str}"
            enqueued = await enqueue_compliance_recalc(
                property_id=property_id,
                client_id=prop["client_id"],
                trigger_reason=TRIGGER_EXPIRY_JOB,
                actor_type=ACTOR_SYSTEM,
                actor_id=None,
                correlation_id=correlation_id,
            )
            if enqueued:
                count += 1

        logger.info(f"Expiry rollover enqueued: {count} properties")
        n_considered = len(property_ids)
        om: Dict[str, Any] = {
            "properties_considered": n_considered,
            "properties_enqueued": count,
            "attempted_count": 1,
            "success_count": 1,
            "failed_count": 0,
            "outcome_kind": "NO_WORK_ELIGIBLE" if n_considered == 0 and count == 0 else "WORK_PERFORMED",
        }
        if n_considered == 0 and count == 0:
            from services.job_run_service import OUTCOME_CONDITIONAL_NO_OUTPUT

            return {
                "message": "Expiry rollover: no properties in due-date window; nothing enqueued.",
                "count": 0,
                "outcome_status": OUTCOME_CONDITIONAL_NO_OUTPUT,
                "outcome_metrics": om,
            }
        return {
            "message": f"Expiry rollover: {count} properties enqueued",
            "count": count,
            "outcome_metrics": om,
        }
    except Exception as e:
        logger.error(f"Expiry rollover job failed: {e}")
        raise


async def run_order_delivery_processing():
    try:
        from services.order_delivery_service import order_delivery_service
        result = await order_delivery_service.process_finalising_orders()
        if result.get("processed", 0) > 0:
            logger.info(
                f"Order delivery job: {result['processed']} processed, "
                f"{result['delivered']} delivered, {result['failed']} failed"
            )
            return {"message": f"Order delivery: {result['processed']} processed, {result['delivered']} delivered"}
        logger.debug("Order delivery job: No orders to process")
        return {"message": "Order delivery: no orders to process"}
    except Exception as e:
        logger.error(f"Order delivery job failed: {e}")
        raise


async def run_sla_monitoring():
    try:
        from services.workflow_automation_service import workflow_automation_service
        result = await workflow_automation_service.wf9_sla_check()
        results = result.get("results", {})
        checked = results.get("checked", 0)
        warnings = results.get("warnings_sent", 0)
        breaches = results.get("breaches_sent", 0)
        if warnings > 0 or breaches > 0:
            return {"message": f"SLA monitoring: {checked} checked, {warnings} warnings, {breaches} breaches"}
        return {"message": f"SLA monitoring completed: {checked} orders checked"}
    except Exception as e:
        logger.error(f"SLA monitoring job failed: {e}")
        raise


async def run_stuck_order_detection():
    try:
        from services.order_workflow import OrderStatus
        from database import database
        db = database.get_db()
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        stuck_orders = await db.orders.find({
            "status": OrderStatus.FINALISING.value,
            "updated_at": {"$lt": one_hour_ago},
            "$or": [
                {"document_versions": {"$size": 0}},
                {"version_locked": {"$ne": True}},
                {"approved_document_version": {"$exists": False}},
                {"approved_document_version": None}
            ]
        }, {"_id": 0, "order_id": 1}).to_list(100)
        if stuck_orders:
            logger.warning(f"STUCK ORDER ALERT: {len(stuck_orders)} orders")
            return {"message": f"Stuck order detection: {len(stuck_orders)} orders need attention"}
        return {"message": "Stuck order detection: no stuck orders found"}
    except Exception as e:
        logger.error(f"Stuck order detection job failed: {e}")
        raise


async def run_queued_order_processing():
    try:
        from services.workflow_automation_service import workflow_automation_service
        result = await workflow_automation_service.process_queued_orders(limit=5)
        results = result.get("results", {})
        processed = results.get("processed", 0)
        if processed > 0:
            return {"message": f"Queued order processing: {processed} processed"}
        return {"message": "Queued order processing: no orders to process"}
    except Exception as e:
        logger.error(f"Queue processing job failed: {e}")
        raise


async def run_abandoned_intake_detection():
    try:
        from services.lead_service import AbandonedIntakeService
        created = await AbandonedIntakeService.detect_abandoned_intakes(timeout_hours=1.0)
        n = len(created) if created else 0
        logger.info(f"Created {n} leads from abandoned intakes")
        return {"message": f"Abandoned intake detection: {n} leads created"}
    except Exception as e:
        logger.error(f"Abandoned intake detection failed: {e}")
        raise


async def run_lead_followup_processing():
    try:
        from services.lead_followup_service import LeadFollowUpService
        from services.lead_automation_service import process_due_sequences
        await LeadFollowUpService.process_followup_queue()
        sequence_result = await process_due_sequences(limit=100)
        return {
            "message": (
                "Lead follow-up processing completed "
                f"(sequence sent={sequence_result.get('sent', 0)} "
                f"skipped={sequence_result.get('skipped', 0)} failed={sequence_result.get('failed', 0)})"
            ),
            "count": int(sequence_result.get("sent", 0)),
            "outcome_metrics": sequence_result,
        }
    except Exception as e:
        logger.error(f"Lead follow-up processing failed: {e}")
        raise


async def run_lead_compliance_gap_detection():
    try:
        from services.lead_automation_service import detect_compliance_gap_and_trigger
        triggered = await detect_compliance_gap_and_trigger()
        return {"message": f"Lead automation compliance-gap detection: {triggered} trigger(s)", "count": int(triggered)}
    except Exception as e:
        logger.error("Lead compliance gap detection failed: %s", e)
        raise


async def run_lead_inactive_reactivation_detection():
    try:
        from services.lead_automation_service import detect_inactive_users_and_trigger
        triggered = await detect_inactive_users_and_trigger()
        return {"message": f"Lead automation inactivity detection: {triggered} trigger(s)", "count": int(triggered)}
    except Exception as e:
        logger.error("Lead inactivity reactivation detection failed: %s", e)
        raise


async def run_lead_sla_check():
    try:
        from services.lead_followup_service import LeadSLAService
        breaches = await LeadSLAService.check_sla_breaches(sla_hours=24)
        n = breaches or 0
        if n:
            logger.warning(f"Detected {n} lead SLA breaches")
        return {"message": f"Lead SLA check: {n} breaches detected"}
    except Exception as e:
        logger.error(f"Lead SLA check failed: {e}")
        raise


async def run_checklist_nurture_processing():
    """Daily: send next checklist nurture email (2–5) to COMPLIANCE_CHECKLIST leads when due."""
    from services.job_run_service import OUTCOME_FAILED

    try:
        from services.lead_nurture_service import process_checklist_nurture_queue
        sent = await process_checklist_nurture_queue()
        return {"message": f"Checklist nurture: {sent} email(s) sent", "count": sent}
    except Exception as e:
        logger.exception(
            "checklist_nurture_processing failed: structured_error job_id=checklist_nurture_processing error=%s",
            e,
        )
        return {
            "message": f"Checklist nurture failed: {e}",
            "count": 0,
            "outcome_status": OUTCOME_FAILED,
            "error_message": str(e),
            "error_code": type(e).__name__,
        }


async def run_onboarding_sequence_processing():
    """Process due landlord onboarding sequence emails (queue-based, behaviour-aware)."""
    try:
        from services.onboarding_sequence_service import process_onboarding_email_queue
        result = await process_onboarding_email_queue()
        sent = result.get("sent", 0)
        cancelled = result.get("cancelled", 0)
        skipped = result.get("skipped", 0)
        return {
            "message": f"Onboarding sequence: {sent} sent, {cancelled} cancelled, {skipped} skipped",
            "sent": sent,
            "cancelled": cancelled,
            "skipped": skipped,
        }
    except Exception as e:
        logger.error("Onboarding sequence processing failed: %s", e)
        raise


async def run_activation_reminder_processing():
    """Remind subscribers who paid but have not set their portal password (first + final)."""
    try:
        from services.onboarding_lifecycle_service import process_activation_reminders

        r = await process_activation_reminders()
        return {
            "message": f"Activation reminders: first={r.get('first', 0)} final={r.get('final', 0)}",
            **r,
        }
    except Exception as e:
        logger.error("Activation reminder processing failed: %s", e)
        raise


async def run_compliance_recalc_sla_monitor():
    """Compliance recalc SLA: detect stuck PENDING/RUNNING, repeated failures, property pending too long; dedupe alerts, audit, optional email."""
    try:
        from services.compliance_sla_monitor import run_compliance_recalc_sla_monitor as _run
        result = await _run()
        logger.info(f"Compliance recalc SLA monitor: {result.get('breaches', 0)} breaches, {result.get('resolved', 0)} resolved")
        return result
    except Exception as e:
        logger.error(f"Compliance recalc SLA monitor failed: {e}")
        raise


async def run_notification_failure_spike_monitor():
    """Notification failure spike: count FAILED in last 15 min; if >= WARN/CRIT threshold, send OPS alert (cooldown applied)."""
    try:
        from services.notification_failure_spike_monitor import run_notification_failure_spike_monitor as _run
        result = await _run()
        if result.get("breached"):
            logger.info(
                f"Notification failure spike: {result.get('severity')} ({result.get('failed_count')} failures), alert_sent={result.get('alert_sent')}"
            )
        return result
    except Exception as e:
        logger.error(f"Notification failure spike monitor failed: {e}")
        raise


async def run_sla_watchdog():
    """Enterprise observability: detect missed job SLAs and create incidents + admin alert."""
    try:
        from services.sla_watchdog import run_sla_watchdog as _run
        result = await _run()
        if result.get("incidents_created", 0) > 0:
            logger.info("SLA watchdog: %s incident(s) created", result["incidents_created"])
        return result
    except Exception as e:
        logger.error("SLA watchdog failed: %s", e)
        raise


async def run_notification_retry_worker():
    """Process notification retry queue (outbox pattern). Picks items with next_run_at <= now and re-attempts send."""
    from database import database
    from datetime import datetime, timezone
    try:
        db = database.get_db()
        now = datetime.now(timezone.utc)
        cursor = db.notification_retry_queue.find(
            {"status": "PENDING", "next_run_at": {"$lte": now}},
        ).limit(50)
        items = await cursor.to_list(50)
        from services.notification_orchestrator import notification_orchestrator
        processed = 0
        for item in items:
            try:
                await notification_orchestrator.process_retry(item["message_id"])
                processed += 1
            except Exception as e:
                logger.warning(f"Notification retry for {item.get('message_id')} failed: {e}")
        return {"message": f"Processed {processed} notification retries", "count": processed}
    except Exception as e:
        logger.error(f"Notification retry worker failed: {e}")
        raise


async def run_pending_payment_lifecycle():
    """
    Daily task: mark lifecycle_status pending_payment -> abandoned if created_at older than 14 days
    and still no active subscription. Optionally abandoned -> archived after 90 days.
    No deletions. No PII wiping.
    """
    try:
        from database import database
        db = database.get_db()
        now = datetime.now(timezone.utc)
        cutoff_14d = now - timedelta(days=14)
        cutoff_90d = now - timedelta(days=90)

        # pending_payment -> abandoned: created_at older than 14 days, no active subscription
        r1 = await db.clients.update_many(
            {
                "lifecycle_status": "pending_payment",
                "created_at": {"$lt": cutoff_14d},
                "$or": [
                    {"subscription_status": {"$nin": ["active", "trialing", "ACTIVE", "TRIALING"]}},
                    {"subscription_status": {"$exists": False}},
                    {"stripe_subscription_id": {"$in": [None, ""]}},
                ],
            },
            {"$set": {"lifecycle_status": "abandoned", "updated_at": now}},
        )

        # abandoned -> archived: optional, after 90 days (using checkout_link_sent_at or created_at as proxy for "abandoned since")
        r2 = await db.clients.update_many(
            {
                "lifecycle_status": "abandoned",
                "$or": [
                    {"checkout_link_sent_at": {"$lt": cutoff_90d}},
                    {"checkout_link_sent_at": {"$exists": False}, "created_at": {"$lt": cutoff_90d}},
                ],
            },
            {"$set": {"lifecycle_status": "archived", "updated_at": now}},
        )

        logger.info("Pending payment lifecycle: %s -> abandoned, %s -> archived", r1.modified_count, r2.modified_count)
        return {"message": f"Lifecycle: {r1.modified_count} abandoned, {r2.modified_count} archived", "abandoned": r1.modified_count, "archived": r2.modified_count}
    except Exception as e:
        logger.error("Pending payment lifecycle job failed: %s", e)
        raise


async def run_client_lifecycle_stale_archive():
    """Archive stale LEAD/PENDING_SETUP-style clients with no Stripe, properties, or portal users."""
    try:
        from database import database
        from services.client_lifecycle_service import job_archive_stale_pending_clients

        db = database.get_db()
        return await job_archive_stale_pending_clients(db, stale_days=45, dry_run=False)
    except Exception as e:
        logger.error("client_lifecycle_stale_archive failed: %s", e)
        raise


async def run_client_purge_eligibility_scan():
    """Mark archived clients as PURGE_ELIGIBLE when safe (preflight passes)."""
    try:
        from database import database
        from services.client_lifecycle_service import job_evaluate_purge_eligibility

        db = database.get_db()
        return await job_evaluate_purge_eligibility(db, archived_min_days=60, dry_run=False)
    except Exception as e:
        logger.error("client_purge_eligibility_scan failed: %s", e)
        raise


async def run_client_test_like_flag_job():
    """Heuristic test-like client flagging; never deletes."""
    try:
        from database import database
        from services.client_lifecycle_service import job_flag_test_like_records

        db = database.get_db()
        return await job_flag_test_like_records(db, limit=500, dry_run=False)
    except Exception as e:
        logger.error("client_test_like_flag_job failed: %s", e)
        raise


async def run_risk_lead_nurture_processing():
    """Daily: send risk-check nurture emails 2–5 when due (day 2, 4, 6, 10 since created). Idempotent, no deletes."""
    from database import database
    db = database.get_db()
    now = datetime.now(timezone.utc)
    cursor = db.risk_leads.find(
        {"status": {"$ne": "converted"}, "email_sequence_step": {"$gte": 1}},
        {"_id": 0, "lead_id": 1, "created_at": 1, "email_sequence_step": 1, "first_name": 1, "email": 1, "computed_score": 1, "risk_band": 1}
    )
    leads = await cursor.to_list(length=500)
    sent = 0
    for lead in leads:
        try:
            created_at = lead.get("created_at")
            if not created_at:
                continue
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if getattr(created_at, "tzinfo", None) is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            days_since = (now - created_at).days
            current_step = lead.get("email_sequence_step") or 0
            next_step = None
            if current_step < 2 and days_since >= 2:
                next_step = 2
            elif current_step < 3 and days_since >= 4:
                next_step = 3
            elif current_step < 4 and days_since >= 6:
                next_step = 4
            elif current_step < 5 and days_since >= 10:
                next_step = 5
            if next_step is None:
                continue
            full_lead = await db.risk_leads.find_one({"lead_id": lead["lead_id"]}, {"_id": 0})
            if not full_lead:
                continue
            from services.risk_lead_email_service import send_risk_lead_email
            ok, _ = await send_risk_lead_email(full_lead, next_step)
            if ok:
                await db.risk_leads.update_one(
                    {"lead_id": lead["lead_id"]},
                    {"$set": {"email_sequence_step": next_step, "last_email_sent_at": now.isoformat()}},
                )
                sent += 1
        except Exception as e:
            logger.warning("Risk lead nurture skip %s: %s", lead.get("lead_id"), e)
    logger.info("Risk lead nurture: %s email(s) sent", sent)
    return {"message": f"Risk lead nurture: {sent} email(s) sent", "count": sent}


async def run_predictive_insights_job():
    """Precompute predictive maintenance insights for all clients with PREDICTIVE_MAINTENANCE. Writes to cache."""
    from database import database
    from services.ops_compliance_feature_flags import get_effective_flags, PREDICTIVE_MAINTENANCE
    from services.predictive_service import get_insights_for_client

    db = database.get_db()
    clients = await db.clients.find({}, {"_id": 0, "client_id": 1, "billing_plan": 1}).to_list(10000)
    count = 0
    for c in clients:
        try:
            flags = await get_effective_flags(c["client_id"], c.get("billing_plan"))
            if not flags.get(PREDICTIVE_MAINTENANCE):
                continue
            await get_insights_for_client(c["client_id"])
            count += 1
        except Exception as e:
            logger.warning("Predictive insights skip client %s: %s", c.get("client_id"), e)
    return {"message": f"Predictive insights precomputed for {count} client(s)", "count": count}


async def run_risk_signal_regen_worker():
    """Process debounced risk_signal_regen_queue: regenerate heuristic signals + operational automation."""
    try:
        from services.risk_signal_regen_queue import run_risk_signal_regen_worker as _run

        return await _run(batch_limit=20)
    except Exception as e:
        logger.error("Risk signal regen worker failed: %s", e)
        raise


async def run_risk_signal_regen_alert_monitor():
    """Queue health: resolve incidents when healthy; create P2 + OPS email when attention_required."""
    try:
        from services.risk_signal_regen_alert_monitor import run_risk_signal_regen_alert_monitor as _run

        result = await _run()
        if result.get("incidents_created"):
            logger.info(
                "risk_signal_regen_alert_monitor: created incident incident_id=%s alert_sent=%s",
                result.get("incident_id"),
                result.get("alert_sent"),
            )
        if result.get("incidents_resolved"):
            logger.info(
                "risk_signal_regen_alert_monitor: resolved %s incident(s)",
                result["incidents_resolved"],
            )
        return {
            "message": "Risk regen queue alert monitor completed",
            "count": int(result.get("incidents_created") or 0) + int(result.get("incidents_resolved") or 0),
            "outcome_metrics": {k: v for k, v in result.items() if k not in ("message",)},
        }
    except Exception as e:
        logger.error("Risk signal regen alert monitor failed: %s", e)
        raise


async def run_risk_signals_job(client_id: Optional[str] = None):
    """Generate stored risk signals for all clients with PREDICTIVE_MAINTENANCE. Writes to risk_signals collection."""
    from database import database
    from services.ops_compliance_feature_flags import get_effective_flags, PREDICTIVE_MAINTENANCE
    from services import risk_signal_service
    from services.job_run_service import (
        OUTCOME_SUCCESS,
        OUTCOME_DEGRADED,
        OUTCOME_FAILED,
        OUTCOME_CONDITIONAL_NO_OUTPUT,
    )

    db = database.get_db()
    filter_cid = str(client_id).strip() if client_id and str(client_id).strip() else None
    clients = await db.clients.find({}, {"_id": 0, "client_id": 1, "billing_plan": 1}).to_list(10000)
    if filter_cid:
        clients = [c for c in clients if c.get("client_id") == filter_cid]
        if not clients:
            return {
                "message": f"Client not found: {filter_cid}",
                "count": 0,
                "outcome_status": OUTCOME_FAILED,
                "error_code": "UnknownClient",
                "error_message": "No client matches client_id for risk_signals_job",
                "outcome_metrics": {},
            }
    skipped_no_flag = 0
    eligible_clients = 0
    successful_clients = 0
    client_errors = 0
    properties_scanned = 0
    signals_generated = 0
    signals_cleared = 0

    for c in clients:
        cid = c.get("client_id")
        try:
            flags = await get_effective_flags(cid, c.get("billing_plan"))
            if not flags.get(PREDICTIVE_MAINTENANCE):
                skipped_no_flag += 1
                continue
            eligible_clients += 1
            out = await risk_signal_service.generate_risk_signals_for_org(cid)
            successful_clients += 1
            properties_scanned += int(out.get("properties_processed") or 0)
            signals_generated += int(out.get("total_signals") or 0)
            signals_cleared += int(out.get("previous_active_signals_cleared") or 0)
        except Exception as e:
            client_errors += 1
            logger.warning("Risk signals failed for client %s: %s", cid, e)

    if skipped_no_flag:
        logger.info(
            "risk_signals_job: skipped %s client(s) without PREDICTIVE_MAINTENANCE",
            skipped_no_flag,
        )

    outcome_metrics = {
        "clients_skipped_no_predictive_flag": skipped_no_flag,
        "clients_eligible": eligible_clients,
        "clients_processed_ok": successful_clients,
        "clients_failed": client_errors,
        "properties_processed": properties_scanned,
        "signals_generated": signals_generated,
        "signals_replaced_cleared": signals_cleared,
        # Health summary / conditional_no_output: "work units" emitted this run
        "attempted_count": signals_generated,
    }

    if eligible_clients == 0:
        return {
            "message": "Risk signals: no clients with predictive maintenance enabled",
            "count": 0,
            "outcome_status": OUTCOME_CONDITIONAL_NO_OUTPUT,
            "outcome_metrics": {**outcome_metrics, "reason_code": "no_eligible_clients"},
        }
    if client_errors > 0 and successful_clients == 0:
        return {
            "message": f"Risk signals failed for all {eligible_clients} eligible client(s)",
            "count": 0,
            "outcome_status": OUTCOME_FAILED,
            "error_code": "AllClientsFailed",
            "error_message": "Every eligible client raised an error during risk signal generation",
            "outcome_metrics": outcome_metrics,
        }
    if client_errors > 0:
        return {
            "message": (
                f"Risk signals: partial success — {successful_clients} client(s) ok, "
                f"{client_errors} failed; {signals_generated} signal(s) written, "
                f"{properties_scanned} propert(ies) scanned"
            ),
            "count": successful_clients,
            "outcome_status": OUTCOME_DEGRADED,
            "error_message": f"{client_errors} client(s) failed during generation",
            "outcome_metrics": outcome_metrics,
        }
    if properties_scanned == 0:
        return {
            "message": (
                "Risk signals: eligible clients had no active properties to scan "
                f"({successful_clients} client(s))"
            ),
            "count": successful_clients,
            "outcome_status": OUTCOME_CONDITIONAL_NO_OUTPUT,
            "outcome_metrics": {**outcome_metrics, "reason_code": "no_properties_to_scan"},
        }
    if signals_generated == 0:
        return {
            "message": (
                f"Risk signals: scanned {properties_scanned} propert(ies) across "
                f"{successful_clients} client(s); no new risk signals (rules produced empty set)"
            ),
            "count": successful_clients,
            "outcome_status": OUTCOME_CONDITIONAL_NO_OUTPUT,
            "outcome_metrics": {**outcome_metrics, "reason_code": "no_rules_triggered"},
        }

    return {
        "message": (
            f"Risk signals: {signals_generated} signal(s) for {successful_clients} client(s), "
            f"{properties_scanned} propert(ies) scanned"
        ),
        "count": successful_clients,
        "outcome_status": OUTCOME_SUCCESS,
        "outcome_metrics": outcome_metrics,
    }


async def run_work_order_sla_breach_job():
    """
    Work order SLA: set sla_breach_risk_at when approaching respond/complete deadline,
    sla_breached_at when deadline has passed. Only for status not in (COMPLETED, CANCELLED).
    """
    from database import database
    from services.maintenance_service import STATUS_COMPLETED, STATUS_CANCELLED

    db = database.get_db()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    cursor = db.work_orders.find(
        {"status": {"$nin": [STATUS_COMPLETED, STATUS_CANCELLED]}},
        {
            "_id": 1,
            "work_order_id": 1,
            "sla_respond_by": 1,
            "sla_complete_by": 1,
            "sla_breached_at": 1,
            "sla_breach_risk_at": 1,
            "compliance_sla_risk_days_before_complete": 1,
            "compliance_sla_risk_hours_before_respond": 1,
        },
    )
    work_orders = await cursor.to_list(500)
    at_risk_updated = 0
    breached_updated = 0
    for wo in work_orders:
        risk_hours = wo.get("compliance_sla_risk_hours_before_respond")
        if risk_hours is None:
            risk_hours = 4
        risk_days = wo.get("compliance_sla_risk_days_before_complete")
        if risk_days is None:
            risk_days = 1
        try:
            risk_threshold_respond = now + timedelta(hours=float(risk_hours))
        except (TypeError, ValueError):
            risk_threshold_respond = now + timedelta(hours=4)
        try:
            risk_threshold_complete = now + timedelta(days=float(risk_days))
        except (TypeError, ValueError):
            risk_threshold_complete = now + timedelta(days=1)

        respond_by = wo.get("sla_respond_by")
        complete_by = wo.get("sla_complete_by")
        already_breached = wo.get("sla_breached_at")
        update = {}
        # Breached: respond_by or complete_by in the past
        if not already_breached:
            is_breached = False
            if respond_by:
                try:
                    r = respond_by if isinstance(respond_by, datetime) else datetime.fromisoformat(respond_by.replace("Z", "+00:00"))
                    if r.tzinfo is None:
                        r = r.replace(tzinfo=timezone.utc)
                    if r <= now:
                        is_breached = True
                except Exception:
                    pass
            if not is_breached and complete_by:
                try:
                    c = complete_by if isinstance(complete_by, datetime) else datetime.fromisoformat(complete_by.replace("Z", "+00:00"))
                    if c.tzinfo is None:
                        c = c.replace(tzinfo=timezone.utc)
                    if c <= now:
                        is_breached = True
                except Exception:
                    pass
            if is_breached:
                update["sla_breached_at"] = now_iso
                update["updated_at"] = now_iso
                breached_updated += 1
        # At risk: deadline within next 4h (respond) or 1d (complete), not yet breached
        if not update and not wo.get("sla_breach_risk_at") and not already_breached:
            at_risk = False
            if respond_by:
                try:
                    r = respond_by if isinstance(respond_by, datetime) else datetime.fromisoformat(respond_by.replace("Z", "+00:00"))
                    if r.tzinfo is None:
                        r = r.replace(tzinfo=timezone.utc)
                    if now < r <= risk_threshold_respond:
                        at_risk = True
                except Exception:
                    pass
            if not at_risk and complete_by:
                try:
                    c = complete_by if isinstance(complete_by, datetime) else datetime.fromisoformat(complete_by.replace("Z", "+00:00"))
                    if c.tzinfo is None:
                        c = c.replace(tzinfo=timezone.utc)
                    if now < c <= risk_threshold_complete:
                        at_risk = True
                except Exception:
                    pass
            if at_risk:
                update["sla_breach_risk_at"] = now_iso
                update["updated_at"] = now_iso
                at_risk_updated += 1
        if update:
            await db.work_orders.update_one(
                {"work_order_id": wo["work_order_id"]},
                {"$set": update},
            )
    msg = f"Work order SLA: {at_risk_updated} at-risk, {breached_updated} breached"
    if at_risk_updated or breached_updated:
        logger.info(msg)
    return {"message": msg, "count": at_risk_updated + breached_updated}


async def run_work_order_contractor_confirmation_timeout_job():
    """Reminder + admin escalation for pending client contractor confirmations (no default auto-assign)."""
    from services.work_order_contractor_routing_service import run_contractor_confirmation_timeout_sweep

    return await run_contractor_confirmation_timeout_sweep()


HEARTBEAT_COLLECTION = "scheduler_heartbeat"
HEARTBEAT_DOC_ID = "default"
# Round-robin cursor for scheduled compliance recalc batch (avoids always hitting the same N properties).
COMPLIANCE_BATCH_POINTER_DOC_ID = "compliance_recalc_batch_pointer"


async def _fetch_properties_batch_round_robin(db, limit: int) -> List[Dict[str, Any]]:
    """
    Return up to ``limit`` properties using a persistent cursor on ``property_id`` (lexicographic ring).
    Stores state in ``scheduler_heartbeat`` under COMPLIANCE_BATCH_POINTER_DOC_ID.
    """
    coll = db[HEARTBEAT_COLLECTION]
    ptr_doc = await coll.find_one({"_id": COMPLIANCE_BATCH_POINTER_DOC_ID}, {"_id": 0, "after_property_id": 1})
    raw_after = (ptr_doc or {}).get("after_property_id")
    after = (str(raw_after).strip() if raw_after else "") or None

    proj = {"_id": 0, "property_id": 1, "client_id": 1}
    batch: List[Dict[str, Any]] = []

    q1: Dict[str, Any] = {"property_id": {"$gt": after}} if after else {}
    async for prop in db.properties.find(q1, proj).sort("property_id", 1).limit(limit):
        batch.append(prop)

    need = limit - len(batch)
    # Wrap only when continuing from a previous cursor; if ``after`` is None, a short batch means
    # the portfolio has fewer than ``limit`` properties — do not re-query from the start (duplicates).
    if need > 0 and after:
        q2: Dict[str, Any] = {"property_id": {"$lte": after}}
        async for prop in db.properties.find(q2, proj).sort("property_id", 1).limit(need):
            batch.append(prop)

    next_after: Optional[str] = None
    if batch:
        last_id = batch[-1].get("property_id")
        next_after = str(last_id).strip() if last_id else None

    now_iso = datetime.now(timezone.utc).isoformat()
    await coll.update_one(
        {"_id": COMPLIANCE_BATCH_POINTER_DOC_ID},
        {"$set": {"after_property_id": next_after, "updated_at": now_iso}},
        upsert=True,
    )
    return batch


async def run_compliance_recalc_enqueue_property(property_id: Optional[str] = None, **_kwargs):
    """
    Enqueue compliance recalc for the worker queue.

    - Manual (admin): pass ``property_id`` — enqueues that property (admin trigger).
    - Scheduled: omit ``property_id`` — enqueues up to COMPLIANCE_RECALC_SCHEDULED_BATCH_LIMIT
      properties per run with a daily dedupe correlation. Properties are chosen in **round-robin**
      order on ``property_id`` (cursor persisted in ``scheduler_heartbeat``).
    """
    import os

    from database import database
    from services.compliance_recalc_queue import (
        ACTOR_ADMIN,
        ACTOR_SYSTEM,
        TRIGGER_ADMIN_MANUAL_JOB,
        TRIGGER_SCHEDULED_PROPERTY_BATCH,
        enqueue_compliance_recalc,
    )
    from services.job_run_service import OUTCOME_FAILED

    pid = str(property_id).strip() if property_id else ""
    db = database.get_db()

    if pid:
        prop = await db.properties.find_one({"property_id": pid}, {"_id": 0, "client_id": 1})
        if not prop or not prop.get("client_id"):
            return {
                "message": f"Property not found: {pid}",
                "count": 0,
                "outcome_status": OUTCOME_FAILED,
                "error_message": "property not found",
            }
        cid = prop["client_id"]
        corr = f"{TRIGGER_ADMIN_MANUAL_JOB}:{pid}:{uuid.uuid4().hex[:12]}"
        enq = await enqueue_compliance_recalc(
            property_id=pid,
            client_id=cid,
            trigger_reason=TRIGGER_ADMIN_MANUAL_JOB,
            actor_type=ACTOR_ADMIN,
            actor_id=None,
            correlation_id=corr,
        )
        return {
            "message": "Compliance recalc enqueued" if enq else "Recalc already queued (duplicate correlation window)",
            "count": 1 if enq else 0,
            "outcome_metrics": {"enqueued": enq, "property_id": pid, "client_id": cid},
        }

    # Scheduled batch: one enqueue per property per calendar day (unique correlation).
    try:
        limit = int(os.environ.get("COMPLIANCE_RECALC_SCHEDULED_BATCH_LIMIT", "500"))
    except ValueError:
        limit = 500
    limit = max(1, min(limit, 5000))

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    enqueued = 0
    scanned = 0
    try:
        total_props = await db.properties.count_documents({})
        props_batch = await _fetch_properties_batch_round_robin(db, limit)
        for prop in props_batch:
            scanned += 1
            pr = prop.get("property_id")
            cid = prop.get("client_id")
            if not pr or not cid:
                continue
            corr = f"{TRIGGER_SCHEDULED_PROPERTY_BATCH}:{pr}:{date_str}"
            ok = await enqueue_compliance_recalc(
                property_id=str(pr),
                client_id=str(cid),
                trigger_reason=TRIGGER_SCHEDULED_PROPERTY_BATCH,
                actor_type=ACTOR_SYSTEM,
                actor_id=None,
                correlation_id=corr,
            )
            if ok:
                enqueued += 1
        msg = (
            f"Scheduled compliance recalc enqueue: {enqueued} newly enqueued "
            f"({scanned} properties in batch, limit={limit}, portfolio={total_props}, round-robin)"
        )
        logger.info("compliance_recalc_enqueue_property: %s", msg)
        return {
            "message": msg,
            "count": enqueued,
            "outcome_metrics": {
                "enqueued": enqueued,
                "scanned": scanned,
                "limit": limit,
                "batch_date": date_str,
                "total_properties": total_props,
                "round_robin": True,
            },
        }
    except Exception as e:
        logger.exception(
            "compliance_recalc_enqueue_property batch failed: job_id=compliance_recalc_enqueue_property error=%s",
            e,
        )
        return {
            "message": f"Scheduled enqueue batch failed: {e}",
            "count": 0,
            "outcome_status": OUTCOME_FAILED,
            "error_message": str(e),
            "error_code": type(e).__name__,
        }


async def run_delivery_reconciliation():
    """Enrich recent reminder/digest job runs with delivery_provider_accepted, delivery_delivered, delivery_bounced from message_logs."""
    try:
        from services.delivery_reconciliation import run_delivery_reconciliation as _run
        return await _run(hours_back=48)
    except Exception as e:
        logger.warning("Delivery reconciliation failed: %s", e)
        raise


async def run_scheduler_heartbeat():
    """Minimal heartbeat: persist current timestamp so health summary can show scheduler is alive."""
    try:
        from database import database
        db = database.get_db()
        now = datetime.now(timezone.utc)
        await db[HEARTBEAT_COLLECTION].update_one(
            {"_id": HEARTBEAT_DOC_ID},
            {"$set": {"last_heartbeat_at": now.isoformat(), "updated_at": now.isoformat()}},
            upsert=True,
        )
        return {
            "message": "Heartbeat updated",
            "count": 1,
            "outcome_metrics": {
                "attempted_count": 1,
                "success_count": 1,
                "heartbeat_written": True,
                "checks_run": 1,
                "outcome_kind": "WORK_PERFORMED",
            },
        }
    except Exception as e:
        logger.warning("Scheduler heartbeat failed: %s", e)
        raise


async def run_generation_auto_retry_processing():
    """Process FAILED orders with due scheduled automatic generation retries."""
    from services.automatic_generation_retry_service import process_due_automatic_generation_retries

    return await process_due_automatic_generation_retries()


async def run_contractor_performance_recalc():
    """Recalculate contractor performance metrics and overall score for all contractors. Runs daily and on-demand."""
    try:
        from services.contractor_intelligence_service import recalculate_all_contractors
        processed, errors = await recalculate_all_contractors(audit=True)
        msg = f"Contractor performance recalc: {processed} updated"
        if errors:
            msg += f", {errors} errors"
        logger.info("contractor_performance_recalc: %s", msg)
        return {"message": msg, "count": processed}
    except Exception as e:
        logger.error("Contractor performance recalc job failed: %s", e)
        raise


async def run_subscription_lifecycle():
    """Post-grace entitlement enforcement, mid-grace payment nudges, 7d/3d renewal emails."""
    from services.jobs import run_renewal_reminders

    return await run_renewal_reminders()


async def run_stripe_subscription_reconcile_job():
    """Batch re-sync subscription rows from Stripe (webhook safety net)."""
    from services.jobs import run_stripe_subscription_reconcile

    return await run_stripe_subscription_reconcile()


async def run_scheduled_admin_communications():
    """Deliver admin communications scheduled for now or earlier."""
    from services import admin_communications_service as acs

    return await acs.process_due_scheduled_communications()


async def run_work_order_schedule_reminders():
    """Remind client + contractor of confirmed visits starting within the next 24 hours."""
    try:
        from services.work_order_schedule_service import run_schedule_reminders_job

        return await run_schedule_reminders_job()
    except Exception as e:
        logger.error("Work order schedule reminders job failed: %s", e)
        raise


# Map scheduler job id -> run function (for admin manual run)
JOB_RUNNERS = {
    "daily_reminders": run_daily_reminders,
    "subscription_lifecycle": run_subscription_lifecycle,
    "stripe_subscription_reconcile": run_stripe_subscription_reconcile_job,
    "pending_verification_digest": run_pending_verification_digest,
    "monthly_digest": run_monthly_digests,
    "compliance_check_morning": run_compliance_status_check,
    "compliance_check_evening": run_compliance_status_check,
    "scheduled_reports": run_scheduled_reports,
    "compliance_score_snapshots": run_compliance_score_snapshots,
    "compliance_recalc_worker": run_compliance_recalc_worker,
    "compliance_recalc_enqueue_property": run_compliance_recalc_enqueue_property,
    "expiry_rollover_recalc": run_expiry_rollover_recalc,
    "order_delivery_processing": run_order_delivery_processing,
    "sla_monitoring": run_sla_monitoring,
    "stuck_order_detection": run_stuck_order_detection,
    "queued_order_processing": run_queued_order_processing,
    "generation_auto_retry_processing": run_generation_auto_retry_processing,
    "abandoned_intake_detection": run_abandoned_intake_detection,
    "lead_followup_processing": run_lead_followup_processing,
    "lead_compliance_gap_detection": run_lead_compliance_gap_detection,
    "lead_inactive_reactivation_detection": run_lead_inactive_reactivation_detection,
    "lead_sla_check": run_lead_sla_check,
    "checklist_nurture_processing": run_checklist_nurture_processing,
    "onboarding_sequence_processing": run_onboarding_sequence_processing,
    "activation_reminder_processing": run_activation_reminder_processing,
    "risk_lead_nurture_processing": run_risk_lead_nurture_processing,
    "compliance_recalc_sla_monitor": run_compliance_recalc_sla_monitor,
    "sla_watchdog": run_sla_watchdog,
    "notification_failure_spike_monitor": run_notification_failure_spike_monitor,
    "notification_retry_worker": run_notification_retry_worker,
    "pending_payment_lifecycle": run_pending_payment_lifecycle,
    "client_lifecycle_stale_archive": run_client_lifecycle_stale_archive,
    "client_purge_eligibility_scan": run_client_purge_eligibility_scan,
    "client_test_like_flag_job": run_client_test_like_flag_job,
    "predictive_insights_job": run_predictive_insights_job,
    "risk_signals_job": run_risk_signals_job,
    "risk_signal_regen_worker": run_risk_signal_regen_worker,
    "risk_signal_regen_alert_monitor": run_risk_signal_regen_alert_monitor,
    "work_order_sla_breach_job": run_work_order_sla_breach_job,
    "work_order_contractor_confirmation_timeout_job": run_work_order_contractor_confirmation_timeout_job,
    "scheduler_heartbeat": run_scheduler_heartbeat,
    "delivery_reconciliation": run_delivery_reconciliation,
    "contractor_performance_recalc": run_contractor_performance_recalc,
    "scheduled_admin_communications": run_scheduled_admin_communications,
    "work_order_schedule_reminders": run_work_order_schedule_reminders,
}
