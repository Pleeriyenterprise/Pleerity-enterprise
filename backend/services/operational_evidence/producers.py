"""
Operational Evidence Platform — thin producers at instrumentation boundaries.

Each producer emits with evidence pointers to authoritative collections only.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.operational_evidence.constants import (
    CATEGORY_COMPLIANCE,
    CATEGORY_EMAIL,
    CATEGORY_EVIDENCE,
    CATEGORY_INCIDENT,
    CATEGORY_NOTIFICATION,
    CATEGORY_QUEUE,
    CATEGORY_RISK,
    CATEGORY_SCHEDULER,
    CATEGORY_SMS,
    CATEGORY_WORKER,
    CONFIDENCE_PROVIDER_PENDING,
    CONFIDENCE_RUNTIME_CONFIRMED,
    EVT_COMPLIANCE_BECAME_NON_COMPLIANT,
    EVT_COMPLIANCE_BECAME_VALID,
    EVT_COMPLIANCE_SCORE_CHANGED,
    EVT_EVIDENCE_APPROVED,
    EVT_EVIDENCE_REJECTED,
    EVT_INCIDENT_DEGRADED,
    EVT_INCIDENT_OPENED,
    EVT_INCIDENT_RECOVERED,
    EVT_INCIDENT_REPEAT_DETECTED,
    EVT_INCIDENT_RESOLVED,
    EVT_JOB_RUN_COMPLETED,
    EVT_JOB_RUN_DEGRADED,
    EVT_JOB_RUN_FAILED,
    EVT_JOB_RUN_STARTED,
    EVT_NOTIFICATION_FAILED,
    EVT_NOTIFICATION_QUEUED,
    EVT_NOTIFICATION_RETRY_SCHEDULED,
    EVT_NOTIFICATION_SENT,
    EVT_PORTFOLIO_RISK_DECREASED,
    EVT_PORTFOLIO_RISK_INCREASED,
    EVT_QUEUE_ITEM_CLAIMED,
    EVT_QUEUE_ITEM_COMPLETED,
    EVT_QUEUE_ITEM_CREATED,
    EVT_QUEUE_ITEM_DEAD,
    EVT_QUEUE_ITEM_FAILED,
    IMPACT_DELAYED,
    IMPACT_NONE,
    IMPACT_OPERATIONAL_ONLY,
    IMPACT_PROPERTY,
    IMPACT_RECOVERED_AUTO,
    REL_CAUSED,
    REL_CONTINUATION,
    REL_RETRY_OF,
    REL_TRIGGERED,
)
from services.operational_evidence.context import OperationalContext, merge_context, set_operational_context
from services.operational_evidence.emit_service import emit_operational_evidence


def _job_deep_link(job_run_id: str) -> str:
    return f"/admin/automation?job_run_id={job_run_id}"


def _incident_deep_link(incident_id: str) -> str:
    return f"/admin/incidents?highlight={incident_id}"


def _timeline_deep_link(root_execution_id: str) -> str:
    return f"/admin/ops/evidence-timeline?root_execution_id={root_execution_id}"


async def emit_job_run_started(
    *,
    job_run_id: str,
    job_name: str,
    run_type: str,
    correlation_id: Optional[str] = None,
    triggered_by: Optional[str] = None,
    caused_by_event_id: Optional[str] = None,
) -> Optional[str]:
    ctx = merge_context(
        job_run_id=job_run_id,
        correlation_id=correlation_id,
    ).ensure_execution()
    set_operational_context(ctx)
    return await emit_operational_evidence(
        category=CATEGORY_SCHEDULER,
        event_type=EVT_JOB_RUN_STARTED,
        severity="info",
        status="started",
        summary=f"Scheduler triggered {job_name}",
        source_service="job_runner",
        source_component="run_instrumented",
        trigger={"type": run_type, "ref": job_name},
        actor={"type": "system", "id": triggered_by},
        relationship_type=REL_TRIGGERED if caused_by_event_id else REL_CONTINUATION,
        caused_by_event_id=caused_by_event_id,
        customer_impact={
            "classification": IMPACT_OPERATIONAL_ONLY,
            "scope": "none",
            "affected_count": 0,
            "summary": "Automation execution started",
        },
        evidence={
            "source_collection": "job_runs",
            "source_id": job_run_id,
            "deep_link": _job_deep_link(job_run_id),
        },
        metadata={"job_name": job_name, "run_type": run_type},
        context=ctx,
    )


async def emit_job_run_finished(
    *,
    job_run_id: str,
    job_name: str,
    status: str,
    duration_ms: Optional[int] = None,
    error_message: Optional[str] = None,
    outcome_status: Optional[str] = None,
) -> Optional[str]:
    ctx = merge_context(job_run_id=job_run_id)
    if status == "failed":
        evt = EVT_JOB_RUN_FAILED
        sev = "error"
    elif status == "degraded":
        evt = EVT_JOB_RUN_DEGRADED
        sev = "warning"
    else:
        evt = EVT_JOB_RUN_COMPLETED
        sev = "info"
    summary = f"Job {job_name} {status}"
    if error_message:
        summary = f"{summary}: {error_message[:200]}"
    return await emit_operational_evidence(
        category=CATEGORY_SCHEDULER,
        event_type=evt,
        severity=sev,
        status=status,
        summary=summary,
        source_service="job_run_service",
        source_component="finish_job_run",
        duration_ms=duration_ms,
        new_state=status,
        customer_impact={
            "classification": IMPACT_NONE if status == "success" else IMPACT_OPERATIONAL_ONLY,
            "scope": "none",
            "affected_count": 0,
            "summary": "No direct customer impact" if status == "success" else "Operational degradation",
        },
        evidence={
            "source_collection": "job_runs",
            "source_id": job_run_id,
            "deep_link": _job_deep_link(job_run_id),
        },
        metadata={"job_name": job_name, "outcome_status": outcome_status},
        context=ctx,
    )


async def emit_queue_item_created(
    *,
    queue_item_id: str,
    queue_collection: str,
    property_id: str,
    client_id: str,
    correlation_id: str,
    trigger_reason: str,
    caused_by_event_id: Optional[str] = None,
) -> Optional[str]:
    ctx = merge_context(
        queue_item_id=queue_item_id,
        property_id=property_id,
        client_id=client_id,
        correlation_id=correlation_id,
    ).fork_execution()
    return await emit_operational_evidence(
        category=CATEGORY_QUEUE,
        event_type=EVT_QUEUE_ITEM_CREATED,
        severity="info",
        status="success",
        summary=f"Queue item created ({trigger_reason}) for property {property_id}",
        source_service="compliance_recalc_queue",
        source_component="enqueue_compliance_recalc",
        trigger={"type": "enqueue", "ref": trigger_reason},
        relationship_type=REL_CAUSED,
        caused_by_event_id=caused_by_event_id,
        customer_impact={
            "classification": IMPACT_OPERATIONAL_ONLY,
            "scope": "property",
            "affected_count": 1,
            "summary": "Compliance recalculation queued",
        },
        evidence={
            "source_collection": queue_collection,
            "source_id": queue_item_id,
            "deep_link": f"/admin/ops/evidence-timeline?property_id={property_id}",
        },
        metadata={"trigger_reason": trigger_reason},
        context=ctx,
    )


async def emit_incident_lifecycle(
    *,
    incident_id: str,
    event_type: str,
    title: str,
    severity: str,
    lifecycle_state: str,
    related_job_name: Optional[str] = None,
    related_job_run_id: Optional[str] = None,
    repeat_count: int = 1,
    caused_by_event_id: Optional[str] = None,
) -> Optional[str]:
    ctx = merge_context(
        incident_id=incident_id,
        job_run_id=related_job_run_id,
    )
    if event_type == EVT_INCIDENT_OPENED:
        status = "open"
    elif event_type == EVT_INCIDENT_RESOLVED:
        status = "resolved"
    elif event_type == EVT_INCIDENT_DEGRADED:
        status = "degraded"
    elif event_type == EVT_INCIDENT_RECOVERED:
        status = "recovered"
    else:
        status = "detected"

    actual_type = event_type
    if repeat_count > 1 and event_type == EVT_INCIDENT_OPENED:
        actual_type = EVT_INCIDENT_REPEAT_DETECTED

    return await emit_operational_evidence(
        category=CATEGORY_INCIDENT,
        event_type=actual_type,
        severity="critical" if severity == "P0" else "error" if severity == "P1" else "warning",
        status=status,
        summary=title,
        source_service="incident_lifecycle_service",
        source_component="record_operational_detection",
        new_state=lifecycle_state,
        relationship_type=REL_CAUSED if caused_by_event_id else None,
        caused_by_event_id=caused_by_event_id,
        customer_impact={
            "classification": IMPACT_OPERATIONAL_ONLY,
            "scope": "platform",
            "affected_count": 0,
            "summary": "Operational incident — investigate automation impact",
        },
        recovery_status="none" if status in ("open", "degraded", "detected") else "recovered",
        evidence={
            "source_collection": "incidents",
            "source_id": incident_id,
            "deep_link": _incident_deep_link(incident_id),
        },
        metadata={
            "related_job_name": related_job_name,
            "repeat_count": repeat_count,
            "presentation_severity": severity,
        },
        context=ctx,
    )


def _queue_deep_link(property_id: str, queue_item_id: str) -> str:
    return f"/admin/ops/evidence-timeline?property_id={property_id}"


def _notification_deep_link(message_id: str) -> str:
    return f"/admin/ops/evidence-timeline?notification_id={message_id}"


def _score_deep_link(client_id: str, property_id: str) -> str:
    return f"/admin/observability/score-events?client_id={client_id}&property_id={property_id}"


async def emit_queue_item_claimed(
    *,
    queue_item_id: str,
    queue_collection: str,
    property_id: str,
    client_id: str,
    correlation_id: str,
    job_run_id: Optional[str] = None,
) -> Optional[str]:
    ctx = merge_context(
        queue_item_id=queue_item_id,
        property_id=property_id,
        client_id=client_id,
        correlation_id=correlation_id,
        job_run_id=job_run_id,
    ).fork_execution()
    return await emit_operational_evidence(
        category=CATEGORY_WORKER,
        event_type=EVT_QUEUE_ITEM_CLAIMED,
        severity="info",
        status="started",
        summary=f"Worker claimed queue item for property {property_id}",
        source_service="job_runner",
        source_component="run_compliance_recalc_worker",
        relationship_type=REL_CAUSED,
        customer_impact={
            "classification": IMPACT_OPERATIONAL_ONLY,
            "scope": "property",
            "affected_count": 1,
            "summary": "Compliance recalculation in progress",
        },
        evidence={
            "source_collection": queue_collection,
            "source_id": queue_item_id,
            "deep_link": _queue_deep_link(property_id, queue_item_id),
        },
        context=ctx,
    )


async def emit_queue_item_completed(
    *,
    queue_item_id: str,
    queue_collection: str,
    property_id: str,
    client_id: str,
    correlation_id: str,
) -> Optional[str]:
    ctx = merge_context(
        queue_item_id=queue_item_id,
        property_id=property_id,
        client_id=client_id,
        correlation_id=correlation_id,
    )
    return await emit_operational_evidence(
        category=CATEGORY_QUEUE,
        event_type=EVT_QUEUE_ITEM_COMPLETED,
        severity="info",
        status="success",
        summary=f"Queue item completed for property {property_id}",
        source_service="job_runner",
        source_component="run_compliance_recalc_worker",
        customer_impact={
            "classification": IMPACT_PROPERTY,
            "scope": "property",
            "affected_count": 1,
            "summary": "Property compliance score updated",
        },
        evidence={
            "source_collection": queue_collection,
            "source_id": queue_item_id,
            "deep_link": _queue_deep_link(property_id, queue_item_id),
        },
        context=ctx,
    )


async def emit_queue_item_failed(
    *,
    queue_item_id: str,
    queue_collection: str,
    property_id: str,
    client_id: str,
    correlation_id: str,
    error_message: str,
    will_retry: bool,
) -> Optional[str]:
    ctx = merge_context(
        queue_item_id=queue_item_id,
        property_id=property_id,
        client_id=client_id,
        correlation_id=correlation_id,
    )
    return await emit_operational_evidence(
        category=CATEGORY_QUEUE,
        event_type=EVT_QUEUE_ITEM_FAILED,
        severity="error",
        status="failed",
        summary=f"Queue processing failed: {error_message[:200]}",
        source_service="job_runner",
        source_component="run_compliance_recalc_worker",
        recovery_status="in_progress" if will_retry else "failed",
        customer_impact={
            "classification": IMPACT_DELAYED if will_retry else IMPACT_PROPERTY,
            "scope": "property",
            "affected_count": 1,
            "summary": "Compliance recalculation delayed" if will_retry else "Compliance recalculation failed",
        },
        evidence={
            "source_collection": queue_collection,
            "source_id": queue_item_id,
            "deep_link": _queue_deep_link(property_id, queue_item_id),
        },
        metadata={"will_retry": will_retry},
        context=ctx,
    )


async def emit_queue_item_dead(
    *,
    queue_item_id: str,
    queue_collection: str,
    property_id: str,
    client_id: str,
    correlation_id: str,
    error_message: str,
) -> Optional[str]:
    ctx = merge_context(
        queue_item_id=queue_item_id,
        property_id=property_id,
        client_id=client_id,
        correlation_id=correlation_id,
    )
    return await emit_operational_evidence(
        category=CATEGORY_QUEUE,
        event_type=EVT_QUEUE_ITEM_DEAD,
        severity="critical",
        status="failed",
        summary=f"Queue item dead-lettered: {error_message[:200]}",
        source_service="job_runner",
        source_component="run_compliance_recalc_worker",
        recovery_status="failed",
        customer_impact={
            "classification": IMPACT_PROPERTY,
            "scope": "property",
            "affected_count": 1,
            "summary": "Compliance recalculation exhausted retries",
        },
        evidence={
            "source_collection": queue_collection,
            "source_id": queue_item_id,
            "deep_link": _queue_deep_link(property_id, queue_item_id),
        },
        context=ctx,
    )


async def emit_score_ledger_change(
    *,
    ledger_id: str,
    client_id: str,
    property_id: str,
    correlation_id: Optional[str],
    before_score: Optional[float],
    after_score: float,
    trigger_label: Optional[str] = None,
    requirement_id: Optional[str] = None,
) -> Optional[str]:
    ctx = merge_context(
        client_id=client_id,
        property_id=property_id,
        requirement_id=requirement_id,
        correlation_id=correlation_id,
    )
    delta = (after_score - before_score) if before_score is not None else None
    event_type = EVT_COMPLIANCE_SCORE_CHANGED
    impact_summary = f"Compliance score changed to {after_score}"
    threshold = 70.0
    if before_score is not None:
        if before_score < threshold <= after_score:
            event_type = EVT_COMPLIANCE_BECAME_VALID
            impact_summary = f"Property became compliant (score {after_score})"
        elif before_score >= threshold > after_score:
            event_type = EVT_COMPLIANCE_BECAME_NON_COMPLIANT
            impact_summary = f"Property became non-compliant (score {after_score})"

    primary_id = await emit_operational_evidence(
        category=CATEGORY_COMPLIANCE,
        event_type=event_type,
        severity="info",
        status="success",
        summary=impact_summary,
        source_service="score_ledger_service",
        source_component="log_score_change",
        previous_state=str(before_score) if before_score is not None else None,
        new_state=str(after_score),
        customer_impact={
            "classification": IMPACT_PROPERTY,
            "scope": "property",
            "affected_count": 1,
            "summary": impact_summary,
        },
        evidence={
            "source_collection": "score_ledger_events",
            "source_id": ledger_id,
            "deep_link": _score_deep_link(client_id, property_id),
        },
        metadata={"trigger_label": trigger_label, "delta": delta},
        context=ctx,
    )
    if delta is not None and abs(delta) >= 1:
        risk_evt = EVT_PORTFOLIO_RISK_DECREASED if delta > 0 else EVT_PORTFOLIO_RISK_INCREASED
        await emit_operational_evidence(
            category=CATEGORY_RISK,
            event_type=risk_evt,
            severity="warning" if delta < 0 else "info",
            status="success",
            summary=f"Portfolio risk {'increased' if delta < 0 else 'decreased'} (Δ{delta:+.1f})",
            source_service="score_ledger_service",
            source_component="log_score_change",
            relationship_type=REL_CAUSED,
            caused_by_event_id=primary_id,
            customer_impact={
                "classification": IMPACT_PROPERTY,
                "scope": "portfolio",
                "affected_count": 1,
                "summary": "Portfolio risk signal updated",
            },
            evidence={
                "source_collection": "score_ledger_events",
                "source_id": ledger_id,
                "deep_link": _score_deep_link(client_id, property_id),
            },
            context=ctx,
        )
    return primary_id


async def emit_notification_queued(
    *,
    message_id: str,
    client_id: Optional[str],
    channel: str,
    template_key: str,
) -> Optional[str]:
    category = CATEGORY_SMS if channel == "SMS" else CATEGORY_EMAIL if channel == "EMAIL" else CATEGORY_NOTIFICATION
    ctx = merge_context(notification_id=message_id, client_id=client_id)
    return await emit_operational_evidence(
        category=category,
        event_type=EVT_NOTIFICATION_QUEUED,
        severity="info",
        status="started",
        summary=f"Notification queued ({template_key}) via {channel}",
        source_service="notification_orchestrator",
        source_component="send",
        customer_impact={
            "classification": IMPACT_OPERATIONAL_ONLY,
            "scope": "tenant" if client_id else "none",
            "affected_count": 1 if client_id else 0,
            "summary": "Notification entered delivery pipeline",
        },
        evidence={
            "source_collection": "message_logs",
            "source_id": message_id,
            "deep_link": _notification_deep_link(message_id),
        },
        metadata={"template_key": template_key, "channel": channel},
        context=ctx,
    )


async def emit_notification_outcome(
    *,
    message_id: str,
    client_id: Optional[str],
    channel: str,
    template_key: str,
    outcome: str,
    error_message: Optional[str] = None,
    transient: bool = False,
    attempt_count: Optional[int] = None,
) -> None:
    try:
        if outcome == "sent":
            await emit_notification_sent(
                message_id=message_id,
                client_id=client_id,
                channel=channel,
                template_key=template_key,
            )
        elif outcome == "failed":
            failed_id = await emit_notification_failed(
                message_id=message_id,
                client_id=client_id,
                channel=channel,
                template_key=template_key,
                error_message=error_message,
                transient=transient,
            )
            if transient and attempt_count:
                await emit_notification_retry_scheduled(
                    message_id=message_id,
                    client_id=client_id,
                    channel=channel,
                    template_key=template_key,
                    attempt_count=attempt_count,
                    caused_by_event_id=failed_id,
                )
    except Exception:
        pass


async def emit_notification_sent(
    *,
    message_id: str,
    client_id: Optional[str],
    channel: str,
    template_key: str,
) -> Optional[str]:
    category = CATEGORY_SMS if channel == "SMS" else CATEGORY_EMAIL if channel == "EMAIL" else CATEGORY_NOTIFICATION
    ctx = merge_context(notification_id=message_id, client_id=client_id)
    return await emit_operational_evidence(
        category=category,
        event_type=EVT_NOTIFICATION_SENT,
        severity="info",
        status="success",
        summary=f"Notification sent ({template_key})",
        source_service="notification_orchestrator",
        source_component="send",
        confidence=CONFIDENCE_PROVIDER_PENDING,
        confidence_reason="Provider accepted; delivery confirmation may be pending",
        customer_impact={
            "classification": IMPACT_OPERATIONAL_ONLY,
            "scope": "tenant" if client_id else "none",
            "affected_count": 1 if client_id else 0,
            "summary": "Customer notification dispatched",
        },
        evidence={
            "source_collection": "message_logs",
            "source_id": message_id,
            "deep_link": _notification_deep_link(message_id),
        },
        metadata={"template_key": template_key, "channel": channel},
        context=ctx,
    )


async def emit_notification_failed(
    *,
    message_id: str,
    client_id: Optional[str],
    channel: str,
    template_key: str,
    error_message: Optional[str] = None,
    transient: bool = False,
) -> Optional[str]:
    category = CATEGORY_SMS if channel == "SMS" else CATEGORY_EMAIL if channel == "EMAIL" else CATEGORY_NOTIFICATION
    ctx = merge_context(notification_id=message_id, client_id=client_id)
    return await emit_operational_evidence(
        category=category,
        event_type=EVT_NOTIFICATION_FAILED,
        severity="error",
        status="failed",
        summary=f"Notification failed ({template_key}): {(error_message or 'unknown')[:200]}",
        source_service="notification_orchestrator",
        source_component="send",
        recovery_status="in_progress" if transient else "failed",
        customer_impact={
            "classification": IMPACT_DELAYED if transient else IMPACT_PROPERTY,
            "scope": "tenant" if client_id else "none",
            "affected_count": 1 if client_id else 0,
            "summary": "Notification delivery failed",
        },
        evidence={
            "source_collection": "message_logs",
            "source_id": message_id,
            "deep_link": _notification_deep_link(message_id),
        },
        metadata={"template_key": template_key, "channel": channel, "transient": transient},
        context=ctx,
    )


async def emit_notification_retry_scheduled(
    *,
    message_id: str,
    client_id: Optional[str],
    channel: str,
    template_key: str,
    attempt_count: int,
    caused_by_event_id: Optional[str] = None,
) -> Optional[str]:
    ctx = merge_context(notification_id=message_id, client_id=client_id)
    return await emit_operational_evidence(
        category=CATEGORY_NOTIFICATION,
        event_type=EVT_NOTIFICATION_RETRY_SCHEDULED,
        severity="warning",
        status="started",
        summary=f"Notification retry scheduled (attempt {attempt_count}) for {template_key}",
        source_service="notification_orchestrator",
        source_component="notification_retry_queue",
        relationship_type=REL_RETRY_OF,
        caused_by_event_id=caused_by_event_id,
        customer_impact={
            "classification": IMPACT_DELAYED,
            "scope": "tenant" if client_id else "none",
            "affected_count": 1 if client_id else 0,
            "summary": "Notification delivery delayed — retry scheduled",
        },
        evidence={
            "source_collection": "message_logs",
            "source_id": message_id,
            "deep_link": _notification_deep_link(message_id),
        },
        metadata={"template_key": template_key, "channel": channel, "attempt_count": attempt_count},
        context=ctx,
    )


async def emit_evidence_review_transition(
    *,
    event_id: str,
    document_id: str,
    client_id: Optional[str],
    property_id: Optional[str],
    requirement_id: Optional[str],
    correlation_id: str,
    to_state: str,
) -> Optional[str]:
    approved_states = frozenset({"APPROVED", "ACCEPTED", "VERIFIED"})
    rejected_states = frozenset({"REJECTED", "DECLINED"})
    upper = to_state.upper()
    if upper in approved_states:
        evt = EVT_EVIDENCE_APPROVED
        summary = f"Evidence approved for document {document_id}"
        st = "success"
    elif upper in rejected_states:
        evt = EVT_EVIDENCE_REJECTED
        summary = f"Evidence rejected for document {document_id}"
        st = "failed"
    else:
        evt = EVT_EVIDENCE_APPROVED
        summary = f"Evidence review: {to_state}"
        st = "success"
    ctx = merge_context(
        document_id=document_id,
        client_id=client_id,
        property_id=property_id,
        requirement_id=requirement_id,
        correlation_id=correlation_id,
    )
    return await emit_operational_evidence(
        category=CATEGORY_EVIDENCE,
        event_type=evt,
        severity="info" if st == "success" else "warning",
        status=st,
        summary=summary,
        source_service="evidence_review_audit",
        source_component="append_evidence_review_event",
        new_state=to_state,
        customer_impact={
            "classification": IMPACT_PROPERTY,
            "scope": "property" if property_id else "tenant",
            "affected_count": 1,
            "summary": summary,
        },
        evidence={
            "source_collection": "evidence_review_events",
            "source_id": event_id,
            "deep_link": f"/admin/ops/evidence-timeline?document_id={document_id}",
        },
        context=ctx,
    )


async def emit_incident_recovered(
    *,
    incident_id: str,
    title: str,
    severity: str,
    recovery_note: str,
    related_job_name: Optional[str] = None,
) -> Optional[str]:
    return await emit_incident_lifecycle(
        incident_id=incident_id,
        event_type=EVT_INCIDENT_RECOVERED,
        title=title or recovery_note,
        severity=severity,
        lifecycle_state="RECOVERED",
        related_job_name=related_job_name,
    )


async def emit_incident_resolved_auto(
    *,
    incident_id: str,
    title: str,
    severity: str,
    resolution_note: str,
) -> Optional[str]:
    ctx = merge_context(incident_id=incident_id)
    return await emit_operational_evidence(
        category=CATEGORY_INCIDENT,
        event_type=EVT_INCIDENT_RESOLVED,
        severity="info",
        status="resolved",
        summary=title or resolution_note,
        source_service="incident_lifecycle_service",
        source_component="try_auto_resolve_after_recovery",
        new_state="RESOLVED",
        recovery_status="recovered",
        customer_impact={
            "classification": IMPACT_RECOVERED_AUTO,
            "scope": "platform",
            "affected_count": 0,
            "summary": "Incident recovered automatically",
        },
        evidence={
            "source_collection": "incidents",
            "source_id": incident_id,
            "deep_link": _incident_deep_link(incident_id),
        },
        metadata={"resolution_note": resolution_note, "auto": True},
        context=ctx,
    )
