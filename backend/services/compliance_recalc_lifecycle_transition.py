"""
Phase 2B: park / restore compliance recalc work on canonical lifecycle transitions.

Does not invent a second lifecycle engine. Uses runtime authority + queue PARKED status.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.account_background_runtime_authority import (
    BackgroundJobDecision,
    BackgroundRuntimeDecision,
    evaluate_background_runtime,
    queue_runtime_action,
)
from services.account_lifecycle_event_authority import (
    LifecycleEventCategory,
    LifecycleEventType,
    register_lifecycle_event_consumer,
)
from services.compliance_recalc_queue import (
    STATUS_DEAD,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PARKED,
    STATUS_PENDING,
    STATUS_RUNNING,
    TRIGGER_LIFECYCLE_RESTORED,
    ACTOR_SYSTEM,
    enqueue_compliance_recalc,
)
from services.compliance_recalc_sla_eligibility import (
    ComplianceRecalcSlaClass,
    resolve_compliance_recalc_sla_eligibility,
)
from services.compliance_recalc_state import (
    RECALC_STATE_ACTIVE_PENDING,
    RECALC_STATE_PARKED,
    property_recalc_set_fields,
)

logger = logging.getLogger(__name__)

COMPLIANCE_RECALC_QUEUE_JOB_TYPE = "compliance_recalc_queue"


@dataclass
class GovernedRecalcEnqueueResult:
    """Customer/system enqueue: executable PENDING or PARKED/terminal debt. ``bool`` is True only if executable work was created/restored."""

    enqueued: bool
    parked: bool = False
    terminalized: bool = False
    outcome: str = ""
    correlation_id: str = ""
    sla_class: Optional[str] = None
    duplicate_suppression_reason: Optional[str] = None

    def __bool__(self) -> bool:
        return self.enqueued

_TRANSITION_EVENT_TYPES = frozenset(
    {
        LifecycleEventType.LIFECYCLE_STATE_CHANGED.value,
        LifecycleEventType.BACKGROUND_POLICY_CHANGED.value,
        LifecycleEventType.RUNTIME_CONTRACT_CHANGED.value,
        LifecycleEventType.ACCOUNT_ACTIVATED.value,
        LifecycleEventType.ACCOUNT_SUSPENDED.value,
        LifecycleEventType.ACCOUNT_ARCHIVED.value,
        LifecycleEventType.ACCOUNT_DELETED.value,
        LifecycleEventType.PAYMENT_RECOVERED.value,
        LifecycleEventType.SUBSCRIPTION_REACTIVATED.value,
        LifecycleEventType.GRACE_PERIOD_STARTED.value,
        LifecycleEventType.TRIAL_EXPIRED.value,
        LifecycleEventType.SUBSCRIPTION_EXPIRED.value,
    }
)

EXECUTABLE_STATUSES = frozenset({STATUS_PENDING, STATUS_RUNNING})
RESTORABLE_PARKED_STATUSES = frozenset({STATUS_PARKED})
TERMINAL_QUEUE_STATUSES = frozenset({STATUS_DEAD})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pause_meta(decision: BackgroundRuntimeDecision) -> Dict[str, Any]:
    return {
        "runtime_pause_reason": decision.reason,
        "runtime_pause_decision": decision.decision.value,
        "runtime_version": decision.runtime_version,
        "lifecycle_state": decision.lifecycle_state,
        "background_policy_key": decision.background_policy_key,
    }


async def set_property_recalc_projection(db, property_id: str, state: str) -> None:
    fields = property_recalc_set_fields(state)
    await db.properties.update_one({"property_id": property_id}, {"$set": fields})


async def park_queue_row(
    db,
    job: Dict[str, Any],
    decision: BackgroundRuntimeDecision,
    *,
    now_iso: Optional[str] = None,
    allow_running: bool = False,
) -> str:
    """PENDING/FAILED → PARKED. RUNNING drains unless allow_running (just-claimed worker). PARKED is idempotent."""
    now_iso = now_iso or _now_iso()
    status = str(job.get("status") or "")
    jid = job.get("_id")
    if status == STATUS_RUNNING and not allow_running:
        return "drain_running"
    if status == STATUS_DEAD:
        return "already_terminal"
    if status == STATUS_DONE:
        return "done_skip"
    meta = _pause_meta(decision)
    if status == STATUS_PARKED:
        await db.compliance_recalc_queue.update_one(
            {"_id": jid, "status": STATUS_PARKED},
            {"$set": {**meta, "updated_at": now_iso}},
        )
        pid = job.get("property_id")
        if pid:
            await set_property_recalc_projection(db, str(pid), RECALC_STATE_PARKED)
        return "already_parked"

    # FAILED retains last_error / attempts; only status and pause metadata change.
    set_fields = {
        **meta,
        "status": STATUS_PARKED,
        "runtime_paused_at": now_iso,
        "parked_from_status": status,
        "updated_at": now_iso,
    }
    match_statuses = [STATUS_PENDING, STATUS_FAILED, STATUS_PARKED]
    if allow_running:
        match_statuses.append(STATUS_RUNNING)
    await db.compliance_recalc_queue.update_one(
        {"_id": jid, "status": {"$in": match_statuses}},
        {"$set": set_fields},
    )
    pid = job.get("property_id")
    if pid:
        await set_property_recalc_projection(db, str(pid), RECALC_STATE_PARKED)
    return "parked"


async def terminalize_queue_row(
    db,
    job: Dict[str, Any],
    decision: BackgroundRuntimeDecision,
    *,
    now_iso: Optional[str] = None,
    allow_running: bool = False,
) -> str:
    now_iso = now_iso or _now_iso()
    status = str(job.get("status") or "")
    if status == STATUS_RUNNING and not allow_running:
        return "drain_running"
    if status == STATUS_DONE:
        return "done_skip"
    meta = _pause_meta(decision)
    await db.compliance_recalc_queue.update_one(
        {"_id": job["_id"]},
        {
            "$set": {
                **meta,
                "status": STATUS_DEAD,
                "runtime_terminated_at": now_iso,
                "updated_at": now_iso,
                "parked_from_status": status if status != STATUS_DEAD else job.get("parked_from_status"),
            }
        },
    )
    pid = job.get("property_id")
    if pid:
        await set_property_recalc_projection(db, str(pid), RECALC_STATE_PARKED)
    return "terminalized"


async def insert_parked_debt_row(
    db,
    *,
    property_id: str,
    client_id: str,
    trigger_reason: str,
    actor_type: str,
    actor_id: Optional[str],
    correlation_id: str,
    decision: BackgroundRuntimeDecision,
) -> str:
    """Insert or keep a PARKED row for ineligible mutation/backfill debt."""
    now_iso = _now_iso()
    meta = _pause_meta(decision)
    existing = await db.compliance_recalc_queue.find_one(
        {"property_id": property_id, "correlation_id": correlation_id},
    )
    if existing:
        st = existing.get("status")
        if st == STATUS_RUNNING:
            await set_property_recalc_projection(db, property_id, RECALC_STATE_PARKED)
            return "drain_running"
        if st == STATUS_DEAD:
            await set_property_recalc_projection(db, property_id, RECALC_STATE_PARKED)
            return "already_terminal"
        await park_queue_row(db, existing, decision, now_iso=now_iso)
        return "already_parked" if st == STATUS_PARKED else "parked"

    doc = {
        "property_id": property_id,
        "client_id": client_id,
        "trigger_reason": trigger_reason,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "correlation_id": correlation_id,
        "status": STATUS_PARKED,
        "attempts": 0,
        "retry_count": 0,
        "retry_exhausted": False,
        "next_run_at": now_iso,
        "last_error": None,
        "created_at": now_iso,
        "updated_at": now_iso,
        "runtime_paused_at": now_iso,
        **meta,
    }
    try:
        await db.compliance_recalc_queue.insert_one(doc)
    except Exception:
        existing = await db.compliance_recalc_queue.find_one(
            {"property_id": property_id, "correlation_id": correlation_id},
        )
        if existing:
            await park_queue_row(db, existing, decision, now_iso=now_iso)
            return "already_parked"
        raise
    await set_property_recalc_projection(db, property_id, RECALC_STATE_PARKED)
    return "parked"


async def enqueue_governed_compliance_recalc(
    property_id: str,
    client_id: str,
    trigger_reason: str,
    actor_type: str,
    actor_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> GovernedRecalcEnqueueResult:
    """Drop-in signature matching enqueue_compliance_recalc for customer/system mutation paths."""
    from database import database

    return await enqueue_or_park_compliance_recalc(
        database.get_db(),
        property_id=property_id,
        client_id=client_id,
        trigger_reason=trigger_reason,
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
    )


async def enqueue_or_park_compliance_recalc(
    db,
    *,
    property_id: str,
    client_id: str,
    trigger_reason: str,
    actor_type: str,
    actor_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    cache: Optional[Dict[str, Any]] = None,
) -> GovernedRecalcEnqueueResult:
    """
    Customer/system path: enqueue executable work only when CONTINUE.
    Otherwise record PARKED (or terminal) debt (no Updating…, no worker claim).
    """
    from services.compliance_recalc_correlation import ensure_correlation_id

    correlation_id = ensure_correlation_id(
        trigger_reason=trigger_reason,
        property_id=property_id,
        correlation_id=correlation_id,
    )
    eligibility = await resolve_compliance_recalc_sla_eligibility(db, client_id, cache=cache)
    if not eligibility.operationally_actionable:
        bg = await evaluate_background_runtime(db, client_id, COMPLIANCE_RECALC_QUEUE_JOB_TYPE)
        if eligibility.sla_class == ComplianceRecalcSlaClass.TERMINATED:
            existing = await db.compliance_recalc_queue.find_one(
                {"property_id": property_id, "correlation_id": correlation_id},
            )
            if existing:
                outcome = await terminalize_queue_row(db, existing, bg)
            else:
                now_iso = _now_iso()
                await db.compliance_recalc_queue.insert_one(
                    {
                        "property_id": property_id,
                        "client_id": client_id,
                        "trigger_reason": trigger_reason,
                        "actor_type": actor_type,
                        "actor_id": actor_id,
                        "correlation_id": correlation_id,
                        "status": STATUS_DEAD,
                        "attempts": 0,
                        "retry_count": 0,
                        "retry_exhausted": True,
                        "next_run_at": now_iso,
                        "last_error": None,
                        "created_at": now_iso,
                        "updated_at": now_iso,
                        "runtime_terminated_at": now_iso,
                        **_pause_meta(bg),
                    }
                )
                await set_property_recalc_projection(db, property_id, RECALC_STATE_PARKED)
                outcome = "terminalized"
            return GovernedRecalcEnqueueResult(
                enqueued=False,
                parked=False,
                terminalized=True,
                outcome=outcome,
                correlation_id=correlation_id,
                sla_class=eligibility.sla_class.value,
            )
        outcome = await insert_parked_debt_row(
            db,
            property_id=property_id,
            client_id=client_id,
            trigger_reason=trigger_reason,
            actor_type=actor_type,
            actor_id=actor_id,
            correlation_id=correlation_id,
            decision=bg,
        )
        logger.info(
            "compliance_recalc debt parked property_id=%s client_id=%s sla_class=%s outcome=%s",
            property_id,
            client_id,
            eligibility.sla_class.value,
            outcome,
        )
        return GovernedRecalcEnqueueResult(
            enqueued=False,
            parked=True,
            outcome=outcome,
            correlation_id=correlation_id,
            sla_class=eligibility.sla_class.value,
        )
    result = await enqueue_compliance_recalc(
        property_id=property_id,
        client_id=client_id,
        trigger_reason=trigger_reason,
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
    )
    return GovernedRecalcEnqueueResult(
        enqueued=bool(result),
        parked=False,
        outcome="enqueued" if result else "deduplicated",
        correlation_id=correlation_id,
        sla_class=eligibility.sla_class.value,
        duplicate_suppression_reason=getattr(result, "duplicate_suppression_reason", None),
    )


async def enqueue_compliance_recalc_admin_override(
    *,
    property_id: str,
    client_id: str,
    trigger_reason: str,
    actor_id: Optional[str],
    correlation_id: Optional[str] = None,
    override_reason: Optional[str] = None,
) -> Any:
    """Privileged admin/manual enqueue: executable even when lifecycle would park."""
    db = None
    from database import database
    from models import AuditAction
    from utils.audit import create_audit_log

    db = database.get_db()
    bg = await evaluate_background_runtime(db, client_id, COMPLIANCE_RECALC_QUEUE_JOB_TYPE)
    eligibility = await resolve_compliance_recalc_sla_eligibility(db, client_id)
    try:
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=actor_id,
            client_id=client_id,
            resource_type="property",
            resource_id=property_id,
            metadata={
                "kind": "compliance_recalc_admin_override",
                "trigger_reason": trigger_reason,
                "override_reason": override_reason,
                "lifecycle_state": bg.lifecycle_state,
                "background_decision": bg.decision.value,
                "background_reason": bg.reason,
                "sla_class": eligibility.sla_class.value,
                "would_suppress": not eligibility.operationally_actionable,
            },
        )
    except Exception as exc:
        logger.warning("compliance_recalc admin override audit skipped: %s", exc)
    result = await enqueue_compliance_recalc(
        property_id=property_id,
        client_id=client_id,
        trigger_reason=trigger_reason,
        actor_type="ADMIN",
        actor_id=actor_id,
        correlation_id=correlation_id,
    )
    await set_property_recalc_projection(db, property_id, RECALC_STATE_ACTIVE_PENDING)
    return result


async def park_claimed_ineligible_job(
    db,
    job: Dict[str, Any],
    decision: BackgroundRuntimeDecision,
) -> str:
    """Worker path: claimed PENDING that is ineligible → PARKED or DEAD. No PENDING reschedule."""
    action = queue_runtime_action(decision)
    if action == "terminate" or decision.decision == BackgroundJobDecision.TERMINATE:
        return await terminalize_queue_row(db, job, decision, allow_running=True)
    return await park_queue_row(db, job, decision, allow_running=True)


async def restore_parked_row(db, job: Dict[str, Any], *, now_iso: Optional[str] = None) -> str:
    now_iso = now_iso or _now_iso()
    if str(job.get("status") or "") != STATUS_PARKED:
        return "not_parked"
    await db.compliance_recalc_queue.update_one(
        {"_id": job["_id"], "status": STATUS_PARKED},
        {
            "$set": {
                "status": STATUS_PENDING,
                "next_run_at": now_iso,
                "updated_at": now_iso,
                "restored_at": now_iso,
            }
        },
    )
    pid = job.get("property_id")
    if pid:
        await set_property_recalc_projection(db, str(pid), RECALC_STATE_ACTIVE_PENDING)
    return "restored"


async def restore_client_compliance_recalc(
    db,
    client_id: str,
) -> Dict[str, int]:
    """Deterministic restoration when policy is CONTINUE."""
    stats = {
        "restored": 0,
        "restoration_enqueued": 0,
        "restoration_deduplicated": 0,
        "skipped_running": 0,
        "errors": 0,
    }
    bg = await evaluate_background_runtime(db, client_id, COMPLIANCE_RECALC_QUEUE_JOB_TYPE)
    if not bg.allowed:
        return stats

    parked_rows = await db.compliance_recalc_queue.find(
        {"client_id": client_id, "status": STATUS_PARKED}
    ).to_list(500)
    restored_pids = set()
    dead_rows = await db.compliance_recalc_queue.find(
        {"client_id": client_id, "status": STATUS_DEAD}
    ).to_list(500)
    dead_only_pids = {str(j.get("property_id") or "") for j in dead_rows}
    for job in parked_rows:
        try:
            outcome = await restore_parked_row(db, job)
            if outcome == "restored":
                stats["restored"] += 1
                restored_pids.add(str(job.get("property_id") or ""))
        except Exception:
            stats["errors"] += 1
            logger.exception("restore_parked_row failed client_id=%s", client_id)

    executable = await db.compliance_recalc_queue.find(
        {"client_id": client_id, "status": {"$in": [STATUS_PENDING, STATUS_RUNNING]}}
    ).to_list(500)
    executable_pids = {str(j.get("property_id") or "") for j in executable}

    props = await db.properties.find(
        {"client_id": client_id},
        {"_id": 0, "property_id": 1, "compliance_score_pending": 1, "compliance_score_recalc_state": 1},
    ).to_list(500)
    for prop in props:
        pid = str(prop.get("property_id") or "")
        if not pid or pid in restored_pids or pid in executable_pids:
            continue
        if pid in dead_only_pids:
            continue
        pending = bool(prop.get("compliance_score_pending"))
        parked_state = str(prop.get("compliance_score_recalc_state") or "") == RECALC_STATE_PARKED
        if not pending and not parked_state:
            continue
        corr = f"{TRIGGER_LIFECYCLE_RESTORED}:{pid}"
        try:
            result = await enqueue_compliance_recalc(
                property_id=pid,
                client_id=client_id,
                trigger_reason=TRIGGER_LIFECYCLE_RESTORED,
                actor_type=ACTOR_SYSTEM,
                actor_id=None,
                correlation_id=corr,
            )
            if result:
                stats["restoration_enqueued"] += 1
            else:
                stats["restoration_deduplicated"] += 1
        except Exception:
            stats["errors"] += 1
            logger.exception("restoration enqueue failed property_id=%s", pid)
    return stats


async def restore_parked_debt_for_eligible_clients(
    db,
    *,
    limit_clients: int = 25,
) -> Dict[str, int]:
    """
    Lost-event safety net.

    Event publication only fires when a contract *changes*. If a PAYMENT_PENDING→ACTIVE
    (or SUSPENDED→ACTIVE) event is lost and the client is already CONTINUE, later
    reconciliation jobs that only emit on state change will never restore PARKED rows.

    This scan does not require a lifecycle delta: it discovers
    ``eligible CONTINUE client + PARKED compliance recalc debt`` and restores it.
    Invoked from the existing ``compliance_recalc_worker`` (every 15s); no new scheduler.
    """
    totals = {
        "clients_scanned": 0,
        "clients_restored": 0,
        "rows_restored": 0,
        "restoration_enqueued": 0,
        "skipped_ineligible": 0,
        "errors": 0,
    }
    try:
        rows = await db.compliance_recalc_queue.find(
            {"status": STATUS_PARKED},
            {"_id": 0, "client_id": 1},
        ).to_list(500)
    except Exception:
        logger.exception("parked-debt safety-net scan failed")
        totals["errors"] += 1
        return totals
    seen: List[str] = []
    seen_set = set()
    for row in rows or []:
        cid = str((row or {}).get("client_id") or "").strip()
        if not cid or cid in seen_set:
            continue
        seen_set.add(cid)
        seen.append(cid)
        if len(seen) >= limit_clients:
            break
    for cid in seen:
        totals["clients_scanned"] += 1
        try:
            eligibility = await resolve_compliance_recalc_sla_eligibility(db, cid)
            if not eligibility.operationally_actionable:
                totals["skipped_ineligible"] += 1
                continue
            stats = await restore_client_compliance_recalc(db, cid)
            restored = int(stats.get("restored") or 0)
            enqueued = int(stats.get("restoration_enqueued") or 0)
            totals["rows_restored"] += restored
            totals["restoration_enqueued"] += enqueued
            if restored or enqueued:
                totals["clients_restored"] += 1
        except Exception:
            totals["errors"] += 1
            logger.exception("parked-debt safety-net restore failed client_id=%s", cid)
    return totals


async def apply_lifecycle_to_client_recalc_queue(db, client_id: str) -> Dict[str, int]:
    stats = {
        "parked": 0,
        "already_parked": 0,
        "terminalized": 0,
        "drain_running": 0,
        "restored": 0,
        "restoration_enqueued": 0,
        "restoration_deduplicated": 0,
        "errors": 0,
    }
    if not client_id:
        return stats
    bg = await evaluate_background_runtime(db, client_id, COMPLIANCE_RECALC_QUEUE_JOB_TYPE)
    eligibility = await resolve_compliance_recalc_sla_eligibility(db, client_id)
    if bg.allowed and eligibility.operationally_actionable:
        restored = await restore_client_compliance_recalc(db, client_id)
        stats.update({k: stats.get(k, 0) + restored.get(k, 0) for k in restored})
        return stats

    terminate = (
        eligibility.sla_class == ComplianceRecalcSlaClass.TERMINATED
        or queue_runtime_action(bg) == "terminate"
        or bg.decision == BackgroundJobDecision.TERMINATE
    )
    rows = await db.compliance_recalc_queue.find({"client_id": client_id}).to_list(1000)
    for job in rows:
        try:
            if terminate:
                outcome = await terminalize_queue_row(db, job, bg)
            else:
                outcome = await park_queue_row(db, job, bg)
            if outcome in stats:
                stats[outcome] += 1
            elif outcome == "parked":
                stats["parked"] += 1
        except Exception:
            stats["errors"] += 1
            logger.exception("lifecycle park/terminalize failed client_id=%s", client_id)

    props = await db.properties.find(
        {"client_id": client_id, "compliance_score_pending": True},
        {"_id": 0, "property_id": 1},
    ).to_list(500)
    for prop in props:
        pid = prop.get("property_id")
        if pid:
            await set_property_recalc_projection(db, str(pid), RECALC_STATE_PARKED)
    return stats


async def on_lifecycle_event_compliance_recalc(event_doc: Dict[str, Any]) -> None:
    event_type = str(event_doc.get("event_type") or "")
    if event_type not in _TRANSITION_EVENT_TYPES:
        return
    client_id = str(event_doc.get("client_id") or "").strip()
    if not client_id:
        return
    from database import database

    db = database.get_db()
    try:
        await apply_lifecycle_to_client_recalc_queue(db, client_id)
    except Exception:
        logger.exception(
            "compliance_recalc lifecycle consumer failed client_id=%s event_type=%s",
            client_id,
            event_type,
        )


def register_compliance_recalc_lifecycle_consumers() -> None:
    """Register via account_lifecycle_event_authority builtin consumers (once at import)."""
    register_lifecycle_event_consumer(
        LifecycleEventCategory.LIFECYCLE, on_lifecycle_event_compliance_recalc
    )
    register_lifecycle_event_consumer(
        LifecycleEventCategory.BACKGROUND, on_lifecycle_event_compliance_recalc
    )
    register_lifecycle_event_consumer(
        LifecycleEventCategory.RUNTIME, on_lifecycle_event_compliance_recalc
    )
    register_lifecycle_event_consumer(
        LifecycleEventCategory.REACTIVATION, on_lifecycle_event_compliance_recalc
    )
