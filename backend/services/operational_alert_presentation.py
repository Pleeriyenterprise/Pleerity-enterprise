"""
Operational alert presentation layer (Phase 2 + 2.5).

Transforms stored incident fields and SLA email inputs into operator-facing
structures only. Does not persist, dedupe, change severities in the database,
or alter incident/recovery semantics.

Phase 2.5 adds optional context adapters for admin-manual–rendered operational
templates (e.g. OPS_ALERT_NOTIFICATION_SPIKE) and minimal INTERNAL_ALERT sends,
without changing template_key routing or orchestrator semantics.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from utils.app_urls import get_app_base_url

from services.incident_service import (
    SOURCE_DELIVERY_UNKNOWN,
    SOURCE_HEARTBEAT,
    SOURCE_JOB_MONITOR,
    SOURCE_RISK_REGEN_QUEUE,
)
from services.internal_alert_registry import (
    DELIVERY_UNKNOWN_STALE,
    EMAIL_DELIVERY_FAILURE_SPIKE,
    JOB_DEGRADED,
    JOB_MISSED_SLA,
    PROVISIONING_FAILED,
    RISK_REGEN_QUEUE_ATTENTION,
    SCHEDULER_HEARTBEAT_STALE,
    STRIPE_WEBHOOK_FAILURE,
    get_alert_config,
)

# Human-readable email/incident titles for scheduled job monitor (technical id in technical_details only).
JOB_MONITOR_EMAIL_TITLES: Dict[str, Dict[str, str]] = {
    "risk_signal_regen_worker": {
        "missed": "Compliance risk updates are delayed",
        "degraded": "Compliance risk updates may be incomplete",
        "never": "Compliance risk updates have not completed successfully",
    },
    "compliance_recalc_worker": {
        "missed": "Property compliance recalculation is behind schedule",
        "degraded": "Compliance recalculation finished with partial errors",
        "never": "Compliance recalculation has not completed successfully",
    },
    "compliance_recalc_sla_monitor": {
        "missed": "Compliance SLA monitoring has not run on schedule",
        "degraded": "Compliance SLA monitoring completed with warnings",
        "never": "Compliance SLA monitoring has not completed successfully",
    },
    "sla_monitoring": {
        "missed": "Order SLA checks are delayed",
        "degraded": "Order SLA checks completed with degraded outcome",
        "never": "Order SLA checks have not completed successfully",
    },
    "sla_watchdog": {
        "missed": "Platform SLA watchdog has not run on schedule",
        "degraded": "SLA watchdog completed with degraded outcome",
        "never": "SLA watchdog has not completed successfully",
    },
    "lead_followup_processing": {
        "missed": "Lead follow-up automation is delayed",
        "degraded": "Lead follow-up automation completed with partial errors",
        "never": "Lead follow-up automation has not completed successfully",
    },
    "abandoned_intake_detection": {
        "missed": "Abandoned intake detection is delayed",
        "degraded": "Abandoned intake detection completed with partial errors",
        "never": "Abandoned intake detection has not completed successfully",
    },
    "daily_reminders": {
        "missed": "Daily compliance reminders are delayed",
        "degraded": "Daily reminders ran with some sends skipped or failed",
        "never": "Daily compliance reminders have not completed successfully",
    },
    "notification_failure_spike_monitor": {
        "missed": "Notification failure spike monitor is delayed",
        "degraded": "Notification failure spike monitor completed with degraded outcome",
        "never": "Notification failure spike monitor has not completed successfully",
    },
    "scheduler_heartbeat": {
        "missed": "Scheduler heartbeat job is delayed",
        "degraded": "Scheduler heartbeat job degraded",
        "never": "Scheduler heartbeat job has not completed",
    },
    "delivery_reconciliation": {
        "missed": "Delivery reconciliation is delayed",
        "degraded": "Delivery reconciliation completed with degraded outcome",
        "never": "Delivery reconciliation has not completed successfully",
    },
    "work_order_contractor_confirmation_timeout_job": {
        "missed": "Contractor confirmation timeout sweep is delayed",
        "degraded": "Contractor confirmation timeout sweep degraded",
        "never": "Contractor confirmation timeout sweep has not completed",
    },
    "compliance_check_morning": {
        "missed": "Morning compliance status check is delayed",
        "degraded": "Morning compliance check completed with partial errors",
        "never": "Morning compliance check has not completed successfully",
    },
    "compliance_check_evening": {
        "missed": "Evening compliance status check is delayed",
        "degraded": "Evening compliance check completed with partial errors",
        "never": "Evening compliance check has not completed successfully",
    },
    "notification_retry_worker": {
        "missed": "Notification retry worker is delayed",
        "degraded": "Notification retry worker completed with degraded outcome",
        "never": "Notification retry worker has not completed successfully",
    },
    "risk_signal_regen_alert_monitor": {
        "missed": "Risk regeneration health monitor is delayed",
        "degraded": "Risk regeneration health monitor degraded",
        "never": "Risk regeneration health monitor has not completed",
    },
}


def _job_monitor_title_kind(raw_title: str, metadata: Dict[str, Any]) -> str:
    t = (raw_title or "").lower()
    meta = metadata or {}
    if meta.get("degraded_run") or "degraded" in t:
        return "degraded"
    if "not succeeded" in t or "never" in t or "no successful" in t:
        return "never"
    return "missed"


def human_job_monitor_email_title(
    *,
    related_job_name: Optional[str],
    raw_title: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Operator-facing primary title for job monitor incidents (not persisted)."""
    job = (related_job_name or "").strip()
    meta = metadata or {}
    kind = _job_monitor_title_kind(raw_title, meta)
    by_job = JOB_MONITOR_EMAIL_TITLES.get(job) or {}
    explicit = (by_job.get(kind) or "").strip()
    if explicit:
        return explicit
    if kind == "degraded":
        return "A scheduled background task completed with a degraded outcome"
    if kind == "never":
        return "A scheduled background task has not completed successfully yet"
    return "A scheduled background task has missed its expected run window"


def human_job_monitor_scope_line(related_job_name: Optional[str]) -> str:
    job = (related_job_name or "").strip()
    if not job:
        return "Critical scheduled jobs"
    return f"Background automation (internal job reference: {job})"


def format_ordered_action_lines(actions: Optional[List[str]]) -> str:
    if not actions:
        return ""
    lines = [str(x).strip() for x in actions if str(x).strip()]
    if not lines:
        return ""
    return "\n".join(f"{i + 1}. {line}" for i, line in enumerate(lines))


def _registry_recommended_actions_text(config: Optional[Dict[str, Any]]) -> str:
    if not config:
        return ""
    ordered = format_ordered_action_lines(config.get("recommended_actions_ordered"))
    if ordered:
        return ordered
    return str(config.get("suggested_action") or "").strip()


def compliance_recalc_sla_alert_copy(alert_type: str, severity: str) -> Dict[str, Any]:
    """
    Operator copy for compliance recalc queue SLA alerts (template_key COMPLIANCE_SLA_ALERT).
    Keys align with admin_manual_structured optional fields.
    """
    # Import alert type constants from monitor module would create cycle; use string keys.
    base_escalation = (
        "Escalate to platform engineering if the queue does not drain after remediation attempts, "
        "or if multiple properties show the same failure signature."
    )
    common_if_ignored = (
        "Scores, risk signals, and reminders that depend on a fresh compliance calculation may stay stale. "
        "No data-loss risk is implied by this alert alone—stale reads and delayed automation are the primary risks."
    )
    if alert_type == "PENDING_STUCK":
        return {
            "plain_title": "Compliance calculation is waiting too long in the queue",
            "summary": (
                "A property’s compliance recalculation job has stayed in the PENDING state longer than the "
                "configured threshold. The worker may be busy, the job may be blocked, or scheduling may be delayed."
            ),
            "operational_impact": (
                "Operational degradation only for this property’s recalculation pipeline until the job runs or is cleared."
            ),
            "customer_impact": (
                "Potential customer-facing impact: portal compliance scores and summaries for this property may lag."
            ),
            "likely_causes": (
                "High queue volume; worker saturation; dependency lock; invalid payload causing silent reschedule; "
                "or infrastructure pause during deploy."
            ),
            "urgency_guidance": (
                "Safe to monitor briefly (minutes) if the platform is under load; schedule investigation within one hour "
                "if the condition persists or spreads to many properties."
            ),
            "if_ignored": common_if_ignored,
            "ordered_actions": [
                "Open Automation Control Centre and locate the compliance recalculation queue for this property.",
                "Confirm whether workers are processing other jobs normally (check recent successful runs).",
                "Inspect the job’s next_run_at and attempts; look for repeated errors in technical details.",
                "If the job is wedged with no progress, follow internal runbook for clearing or requeuing (avoid duplicate manual triggers).",
                base_escalation,
            ],
            "subject_severity_token": "Operational warning" if severity == "WARN" else "Urgent operational review",
        }
    if alert_type == "RUNNING_STUCK":
        return {
            "plain_title": "Compliance calculation appears stuck while running",
            "summary": (
                "A recalculation job has remained in RUNNING longer than expected without progress updates. "
                "The worker process may be blocked, crashed mid-run, or waiting on an external dependency."
            ),
            "operational_impact": "This property’s recalculation pipeline is blocked until the job completes or is recovered.",
            "customer_impact": "Potential customer-facing impact: scores and dependent views may be frozen for this property.",
            "likely_causes": (
                "Long-running dependency; deadlock; worker killed mid-job; database latency spike; or unhandled stall in processing."
            ),
            "urgency_guidance": "Immediate investigation recommended: stuck RUNNING jobs can hold resources and block follow-on work.",
            "if_ignored": common_if_ignored,
            "ordered_actions": [
                "Open Automation Control Centre and confirm whether workers are healthy.",
                "Identify the stuck job id (technical details) and correlate with worker logs around updated_at.",
                "Check database and external service health for the time window shown.",
                "If safe per runbook, cancel or requeue the stuck job after capturing diagnostics.",
                base_escalation,
            ],
            "subject_severity_token": "Urgent operational review" if severity == "CRIT" else "Operational warning",
        }
    if alert_type in ("FAILING_REPEATEDLY", "DEAD_JOB"):
        dead = alert_type == "DEAD_JOB"
        return {
            "plain_title": "Compliance recalculation is failing repeatedly" + (" (dead letter)" if dead else ""),
            "summary": (
                "The compliance recalculation queue reports repeated failures or a dead-letter state for this property. "
                "Each failure may leave compliance_score_pending or related flags set."
            ),
            "operational_impact": "Automated recalculation will not succeed until the underlying error is fixed.",
            "customer_impact": "Potential customer-facing impact: incorrect or stale compliance presentation until fixed.",
            "likely_causes": (
                "Data validation error; missing requirement linkage; upstream API failure; resource timeout; or corrupt input document."
            ),
            "urgency_guidance": "Immediate investigation recommended after two or more failures; dead-letter states require review before retry.",
            "if_ignored": common_if_ignored + " Repeated failures may increase support tickets for the same property.",
            "ordered_actions": [
                "Open Automation Control Centre and capture last_error from the failing job (technical details).",
                "Open the tenant in Admin → Client control panel and reproduce in a safe sandbox if available.",
                "Fix data or configuration root cause before manual retry.",
                "Retry the job only once the error condition is cleared; document the change in audit notes.",
                base_escalation,
            ],
            "subject_severity_token": "Urgent operational review" if severity == "CRIT" else "Operational warning",
        }
    if alert_type == "PROPERTY_PENDING_TOO_LONG":
        return {
            "plain_title": "Property compliance score has been pending too long",
            "summary": (
                "The property is flagged with compliance_score_pending for longer than the configured window, "
                "or the last successful calculation is older than expected while pending remains set."
            ),
            "operational_impact": "Downstream dashboards and automations that trust a fresh score may be using stale indicators.",
            "customer_impact": "Potential customer-facing impact: the portal may show an outdated or interim compliance picture.",
            "likely_causes": (
                "Queue starvation for this property; worker errors; manual flags; or a completed job that did not clear pending."
            ),
            "urgency_guidance": (
                "Safe to monitor briefly if a deploy just finished; otherwise schedule investigation within one business hour."
            ),
            "if_ignored": common_if_ignored,
            "ordered_actions": [
                "Open Automation Control Centre and search for queue rows for this property_id.",
                "Open Admin → Client control panel for the client_id and review property compliance flags.",
                "If the queue is empty but pending remains, consider a controlled score validation or recalculation trigger per runbook.",
                base_escalation,
            ],
            "subject_severity_token": "Operational warning",
        }
    return {
        "plain_title": "Compliance recalculation SLA attention required",
        "summary": "The compliance recalculation SLA monitor raised an alert for this property.",
        "operational_impact": "Recalculation or score freshness may be impaired until triaged.",
        "customer_impact": "Potential customer-facing impact: stale compliance presentation.",
        "likely_causes": "See technical details for alert-specific context.",
        "urgency_guidance": "Begin triage using Automation Centre and client admin views.",
        "if_ignored": common_if_ignored,
        "ordered_actions": [
            "Review technical details for raw alert_type and timestamps.",
            "Open Automation Control Centre.",
            base_escalation,
        ],
        "subject_severity_token": "Operational notice",
    }


def enrich_compliance_sla_alert_email_context(
    *,
    recipient: str,
    alert_type: str,
    severity: str,
    property_id: str,
    client_id: str,
    details: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Structured admin-manual context for COMPLIANCE_SLA_ALERT (routing unchanged).
    Preserves full diagnostics in admin_manual_debug.
    """
    copy = compliance_recalc_sla_alert_copy(alert_type, severity)
    base = _app_base(for_email=True)
    auto_url = f"{base}/admin/automation" if base else ""
    client_url = f"{base}/admin/clients/{client_id}" if (base and client_id) else ""
    secondary: List[Dict[str, str]] = []
    if client_url:
        secondary.append({"label": "Client control panel", "url": client_url})
    if auto_url and auto_url != client_url:
        secondary.append({"label": "Automation Control Centre", "url": auto_url})
    try:
        raw_debug = json.dumps(details, indent=2, default=str)[:12000]
    except Exception:
        raw_debug = str(details)[:12000]
    meta_lines = [f"alert_type: {alert_type}", f"severity: {severity}", f"property_id: {property_id}", f"client_id: {client_id or 'N/A'}"]
    full_debug = "\n".join(meta_lines) + "\n\n" + raw_debug
    actions_text = format_ordered_action_lines(copy.get("ordered_actions"))
    subject = f"[{copy['subject_severity_token']}] {copy['plain_title']}"
    summary = copy["summary"]
    lines_plain = [
        "What happened",
        summary,
        "",
        "Operational impact",
        copy["operational_impact"],
        "",
        "Customer impact",
        copy["customer_impact"],
        "",
        "Likely causes",
        copy["likely_causes"],
        "",
        "Urgency",
        copy["urgency_guidance"],
        "",
        "If left unresolved",
        copy["if_ignored"],
        "",
        "Recommended actions",
        actions_text,
    ]
    if auto_url:
        lines_plain.extend(["", "Where to investigate", auto_url])
    if client_url:
        lines_plain.append(client_url)
    lines_plain.extend(["", "--- Technical / debug ---", full_debug])
    full_plain = "\n".join(lines_plain)
    out = _admin_manual_structured_payload(
        header_title="Compliance recalculation health",
        summary=summary,
        impact=copy["operational_impact"],
        actions=actions_text,
        resolution_url=auto_url or client_url,
        resolution_label="Open Automation Control Centre" if auto_url else "Open client control panel",
        secondary_links=secondary or None,
        raw_debug=full_debug,
        full_plaintext=full_plain,
        recipient=recipient,
        subject=subject,
        presentation_adapter="compliance_sla_alert_v2",
        extra_meta={
            "admin_manual_customer_impact": copy["customer_impact"],
            "admin_manual_urgency_guidance": copy["urgency_guidance"],
            "admin_manual_if_ignored": copy["if_ignored"],
            "admin_manual_likely_causes": copy["likely_causes"],
            "_compliance_sla_alert_type": alert_type,
        },
    )
    return out

STORED_SEVERITY_TO_LABEL = {
    "P0": "CRITICAL",
    "P1": "ACTION_REQUIRED",
    "P2": "WARNING",
}


def translate_stored_severity_to_label(stored: Optional[str]) -> str:
    s = (stored or "").strip().upper()
    return STORED_SEVERITY_TO_LABEL.get(s, "WARNING")


def format_severity_label_for_subject(severity_label: str) -> str:
    """Human-readable subject line token (stored mapping stays underscore form)."""
    sl = (severity_label or "").strip().upper()
    if sl == "ACTION_REQUIRED":
        return "ACTION REQUIRED"
    return sl.replace("_", " ")


def infer_alert_type_from_incident(incident: Dict[str, Any]) -> Optional[str]:
    meta = incident.get("metadata") if isinstance(incident.get("metadata"), dict) else {}
    explicit = meta.get("alert_type")
    if explicit:
        return str(explicit)
    source = (incident.get("source") or "").strip()
    title = (incident.get("title") or "").lower()
    if source == SOURCE_HEARTBEAT:
        return SCHEDULER_HEARTBEAT_STALE
    if source == SOURCE_DELIVERY_UNKNOWN:
        return DELIVERY_UNKNOWN_STALE
    if source == SOURCE_RISK_REGEN_QUEUE:
        return RISK_REGEN_QUEUE_ATTENTION
    if source == SOURCE_JOB_MONITOR:
        if meta.get("degraded_run") or "degraded" in title:
            return JOB_DEGRADED
        return JOB_MISSED_SLA
    return None


def infer_alert_type_from_watchdog_email(source: str, title: str, metadata: Optional[Dict[str, Any]]) -> Optional[str]:
    meta = metadata or {}
    if meta.get("alert_type"):
        return str(meta["alert_type"])
    fake = {"source": source, "title": title, "metadata": meta}
    return infer_alert_type_from_incident(fake)


def _app_base(*, for_email: bool) -> str:
    return (get_app_base_url(for_email_links=for_email) or "").strip().rstrip("/")


def build_resolution_links(
    *,
    incident_id: str,
    source: str,
    related_job_name: Optional[str],
    related_job_run_id: Optional[str],
    for_email: bool = False,
) -> Dict[str, str]:
    """
    Deep admin targets. When for_email is True, links are absolute (email clients).
    When False, paths are SPA-relative (/admin/...) for use with in-app routers.
    """
    out: Dict[str, str] = {}
    if not incident_id:
        return out
    incident_path = f"/admin/incidents?highlight={incident_id}"
    obs_path = "/admin/observability"
    auto_path = "/admin/automation"
    health_path = "/admin/system-health"

    base = _app_base(for_email=for_email) if for_email else ""

    def href(path: str) -> str:
        if base:
            return f"{base}{path}"
        return path

    if for_email:
        out["incident"] = href(incident_path)
        out["observability"] = href(obs_path)
        out["automation_centre"] = href(auto_path)
        out["system_health"] = href(health_path)
    else:
        out["incident"] = incident_path
        out["observability"] = obs_path
        out["automation_centre"] = auto_path
        out["system_health"] = health_path

    if related_job_run_id:
        out["job_run_message_logs"] = href(auto_path)

    if source == SOURCE_JOB_MONITOR:
        out["primary_resolution"] = out["automation_centre"]
    elif source == SOURCE_HEARTBEAT:
        out["primary_resolution"] = out["system_health"]
    elif source == SOURCE_DELIVERY_UNKNOWN:
        out["primary_resolution"] = out["observability"]
    elif source == SOURCE_RISK_REGEN_QUEUE:
        out["primary_resolution"] = out["automation_centre"]
    else:
        out["primary_resolution"] = out["incident"]
    return out


def build_technical_details_text(
    *,
    stored_severity: str,
    metadata: Optional[Dict[str, Any]],
    related_job_name: Optional[str],
    related_job_run_id: Optional[str],
    extra_context: Optional[Dict[str, Any]] = None,
) -> str:
    lines: List[str] = []
    lines.append(f"Stored severity (audit reference): {stored_severity}")
    if related_job_name:
        lines.append(f"Related job name: {related_job_name}")
    if related_job_run_id:
        lines.append(f"Related job run id: {related_job_run_id}")
    merged: Dict[str, Any] = {}
    if metadata:
        merged.update(metadata)
    if extra_context:
        for k, v in extra_context.items():
            if v is not None and v != "":
                merged[k] = v
    if merged:
        lines.append("Context / metadata:")
        try:
            lines.append(json.dumps(merged, indent=2, default=str)[:8000])
        except Exception:
            lines.append(str(merged)[:8000])
    return "\n".join(lines)


def first_meaningful_summary_line(description: str, *, max_len: int = 400) -> str:
    text = (description or "").strip()
    if not text:
        return ""
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:max_len]
    return text[:max_len]


def _affected_scope_for(source: str, related_job_name: Optional[str]) -> str:
    if source == SOURCE_HEARTBEAT:
        return "Platform-wide background scheduler"
    if source == SOURCE_DELIVERY_UNKNOWN:
        return "Outbound notification delivery confirmation pipeline"
    if source == SOURCE_RISK_REGEN_QUEUE:
        return "Risk signal regeneration queue"
    if source == SOURCE_JOB_MONITOR and related_job_name:
        return human_job_monitor_scope_line(related_job_name)
    if source == SOURCE_JOB_MONITOR:
        return "Critical scheduled jobs"
    return "Platform operations"


def build_operational_presentation_for_incident(
    incident: Dict[str, Any],
    *,
    for_email_links: bool = False,
) -> Dict[str, Any]:
    """
    Return a normalized presentation dict for API/UI/email enrichment.
    customer_impact, urgency_guidance, and if_ignored are populated only from the
    internal alert registry when an alert_type is inferred (never fabricated).
    """
    incident_id = str(incident.get("id") or incident.get("_id") or "").strip()
    stored = (incident.get("severity") or "P2").strip()
    title = incident.get("title") or "Operational incident"
    description = incident.get("description") or ""
    source = incident.get("source") or ""
    metadata = incident.get("metadata") if isinstance(incident.get("metadata"), dict) else {}
    related_job_name = incident.get("related_job_name")
    related_job_run_id = incident.get("related_job_run_id")

    alert_type = infer_alert_type_from_incident(incident)
    config = get_alert_config(alert_type) if alert_type else None

    severity_label = translate_stored_severity_to_label(stored)
    raw_title = str(title).strip() or "Operational incident"
    presentation_title = raw_title
    if source == SOURCE_JOB_MONITOR:
        presentation_title = human_job_monitor_email_title(
            related_job_name=related_job_name if isinstance(related_job_name, str) else None,
            raw_title=raw_title,
            metadata=metadata,
        )
    operational_summary = first_meaningful_summary_line(description) or presentation_title

    if config:
        business_impact = (config.get("business_impact") or config.get("description") or description).strip()
        affected_component = str(config.get("component") or "").strip() or "Operations"
        recommended_actions = _registry_recommended_actions_text(config) or str(
            config.get("suggested_action") or ""
        ).strip()
    else:
        business_impact = (first_meaningful_summary_line(description, max_len=600) or operational_summary).strip()
        affected_component = (str(related_job_name).strip() if related_job_name else "") or "Operations"
        recommended_actions = "Review the incident in Admin → Incidents and related observability views."

    customer_impact_raw = (config or {}).get("customer_impact")
    customer_impact = (str(customer_impact_raw).strip() if customer_impact_raw else None) or None

    urgency_guidance_raw = (config or {}).get("urgency_guidance")
    urgency_guidance = (str(urgency_guidance_raw).strip() if urgency_guidance_raw else None) or None

    if_ignored_raw = (config or {}).get("if_ignored")
    if_ignored_guidance = (str(if_ignored_raw).strip() if if_ignored_raw else None) or None

    affected_scope = _affected_scope_for(source, related_job_name)

    links: Dict[str, str] = {}
    if incident_id:
        links = build_resolution_links(
            incident_id=incident_id,
            source=source,
            related_job_name=related_job_name,
            related_job_run_id=related_job_run_id,
            for_email=for_email_links,
        )

    primary = links.get("incident") or links.get("primary_resolution") or ""

    technical_details = build_technical_details_text(
        stored_severity=stored,
        metadata=metadata,
        related_job_name=related_job_name,
        related_job_run_id=related_job_run_id,
    )

    return {
        "presentation_title": presentation_title,
        "operational_summary": operational_summary,
        "business_impact": business_impact,
        "severity_label": severity_label,
        "stored_severity": stored,
        "recommended_actions": recommended_actions,
        "resolution_link": primary,
        "resolution_links": links,
        "technical_details": technical_details,
        "affected_component": affected_component,
        "affected_scope": affected_scope,
        "customer_impact": customer_impact,
        "urgency_guidance": urgency_guidance,
        "if_ignored_guidance": if_ignored_guidance,
        "alert_type": alert_type,
    }


def build_internal_alert_email_context(
    *,
    incident_id: str,
    stored_severity: str,
    title: str,
    description: str,
    source: str,
    metadata: Optional[Dict[str, Any]],
    related_job_name: Optional[str],
    related_job_run_id: Optional[str],
    last_finished_at: Optional[Any],
    last_successful_at: Optional[Any],
    is_degraded_alert: bool,
    expected_interval: Optional[str],
    current_status: str,
    suggested_action: str,
    component: str,
    possible_impact: str,
    timestamp: str,
) -> Dict[str, Any]:
    """
    Build orchestrator context for INTERNAL_ALERT emails: presentation fields plus
    legacy keys expected by EmailService / templates for backward compatibility.
    """
    meta = metadata or {}
    incident_like = {
        "id": incident_id,
        "severity": stored_severity,
        "title": title,
        "description": description,
        "source": source,
        "metadata": meta,
        "related_job_name": related_job_name,
        "related_job_run_id": related_job_run_id,
    }
    pres = build_operational_presentation_for_incident(incident_like, for_email_links=True)

    observability_link = (pres["resolution_links"] or {}).get("observability") or ""
    if not observability_link:
        base = _app_base(for_email=True)
        if base:
            observability_link = f"{base}/admin/observability"

    incident_link = (pres["resolution_links"] or {}).get("incident") or ""
    primary = incident_link or (pres["resolution_links"] or {}).get("primary_resolution") or pres["resolution_link"]

    extra_ctx = {
        "last_finished_at": last_finished_at,
        "last_successful_at_context": last_successful_at,
        "expected_interval": expected_interval,
        "degraded_run": is_degraded_alert,
        "current_status": current_status,
        "possible_impact": possible_impact,
    }
    technical = build_technical_details_text(
        stored_severity=stored_severity,
        metadata=meta,
        related_job_name=related_job_name,
        related_job_run_id=related_job_run_id,
        extra_context=extra_ctx,
    )

    subj_label = format_severity_label_for_subject(pres["severity_label"])

    return {
        "recipient": "",
        "subject": f"[{subj_label}] {pres['presentation_title']}",
        "severity": stored_severity,
        "severity_label": pres["severity_label"],
        "title": pres["presentation_title"],
        "presentation_title": pres["presentation_title"],
        "operational_summary": pres["operational_summary"],
        "business_impact": pres["business_impact"],
        "customer_impact": pres.get("customer_impact") or "",
        "operator_urgency_note": pres.get("urgency_guidance") or "",
        "if_ignored_guidance": pres.get("if_ignored_guidance") or "",
        "affected_component": pres["affected_component"],
        "affected_scope": pres["affected_scope"],
        "description": description,
        "component": component or pres["affected_component"],
        "last_successful_run": (last_successful_at if is_degraded_alert else last_finished_at),
        "last_run_at": last_finished_at,
        "degraded_run": is_degraded_alert,
        "expected_interval": expected_interval,
        "current_status": current_status,
        "possible_impact": possible_impact,
        "suggested_action": (suggested_action or pres["recommended_actions"]).strip(),
        "recommended_actions": pres["recommended_actions"],
        "dashboard_link": observability_link,
        "resolution_link": primary,
        "incident_link": incident_link,
        "resolution_links": pres["resolution_links"],
        "technical_details": technical,
        "timestamp": timestamp,
    }


# --- Phase 2.5: non–INTERNAL_ALERT operational email context adapters ---
# --- Phase 2.6: optional admin_manual_structured fields for EmailService ---


def _admin_manual_structured_payload(
    *,
    header_title: str,
    summary: str,
    impact: str,
    actions: str,
    resolution_url: str,
    resolution_label: str,
    secondary_links: Optional[List[Dict[str, str]]],
    raw_debug: str,
    full_plaintext: str,
    recipient: str,
    subject: str,
    presentation_adapter: str,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "recipient": recipient,
        "subject": subject,
        "message": full_plaintext,
        "admin_manual_structured": True,
        "admin_manual_header_title": header_title,
        "admin_manual_summary": summary,
        "admin_manual_impact": impact,
        "admin_manual_actions": actions,
        "admin_manual_resolution_url": resolution_url,
        "admin_manual_resolution_label": resolution_label,
        "admin_manual_debug": raw_debug.strip(),
        "_presentation_adapter": presentation_adapter,
    }
    if secondary_links:
        out["admin_manual_secondary_links"] = secondary_links
    if extra_meta:
        for k, v in extra_meta.items():
            if v is not None:
                out[k] = v
    return out


def enrich_ops_notification_spike_email_context(
    *,
    recipient: str,
    subject: str,
    message: str,
    ops_severity_token: str,
    failed_count: int,
    lookback_minutes: int,
) -> Dict[str, Any]:
    """
    Enrich OPS_ALERT_NOTIFICATION_SPIKE (admin-manual) sends with operator-first copy.
    Preserves raw telemetry at the end; does not change template_key or routing.
    """
    cfg = get_alert_config(EMAIL_DELIVERY_FAILURE_SPIKE) or {}
    pres_sev_label = "CRITICAL" if (ops_severity_token or "").upper() == "CRIT" else "WARNING"
    subj_display = format_severity_label_for_subject(pres_sev_label)
    base = _app_base(for_email=True)
    obs = f"{base}/admin/observability" if base else ""
    biz = (cfg.get("business_impact") or cfg.get("description") or "").strip()
    action = (cfg.get("suggested_action") or "").strip()
    summary = (
        f"Outbound notification failures have spiked: {failed_count} failed sends recorded in the last "
        f"{lookback_minutes} minutes (operational threshold crossed)."
    )
    lines = [
        "What happened",
        summary,
        "",
        "Why it matters",
        biz or "Delivery health may affect tenant and staff communications.",
        "",
        "What to do next",
        action or "Review Message logs, provider dashboards, and recent failing template_keys.",
    ]
    if obs:
        lines.extend(["", "Where to investigate", obs])
    lines.extend(["", "--- Raw telemetry (debug) ---", message])
    new_subject = f"[{subj_display}] Notification failure spike - {failed_count} failures ({lookback_minutes} min window)"
    full_plain = "\n".join(lines)
    return _admin_manual_structured_payload(
        header_title="Notification delivery health",
        summary=summary,
        impact=biz or "Delivery health may affect tenant and staff communications.",
        actions=action or "Review Message logs, provider dashboards, and recent failing template_keys.",
        resolution_url=obs,
        resolution_label="Open Observability",
        secondary_links=None,
        raw_debug=message,
        full_plaintext=full_plain,
        recipient=recipient,
        subject=new_subject,
        presentation_adapter="ops_notification_spike_v1",
        extra_meta={
            "_original_ops_subject": subject,
            "_original_ops_severity_token": ops_severity_token,
        },
    )


def enrich_risk_regen_queue_ops_email_context(
    *,
    recipient: str,
    subject: str,
    message: str,
    incident_id: str,
) -> Dict[str, Any]:
    """
    Enrich risk regen queue OPS_ALERT_NOTIFICATION_SPIKE emails using registry copy
    and deep admin links. Raw queue dump remains in the debug section.
    """
    cfg = get_alert_config(RISK_REGEN_QUEUE_ATTENTION) or {}
    base = _app_base(for_email=True)
    incident_url = f"{base}/admin/incidents?highlight={incident_id}" if base else ""
    auto_url = f"{base}/admin/automation" if base else ""
    title = str(cfg.get("default_title") or "Risk signal regeneration queue needs attention").strip()
    biz = (cfg.get("business_impact") or cfg.get("description") or "").strip()
    action = (cfg.get("suggested_action") or "").strip()
    subj_display = format_severity_label_for_subject("WARNING")
    lines = [
        "What happened",
        title + ".",
        "",
        "Why it matters",
        biz,
        "",
        "What to do next",
        action,
    ]
    if incident_url:
        lines.extend(["", "Where to resolve", f"Open incident: {incident_url}"])
    if auto_url:
        lines.append(f"Automation Control Centre: {auto_url}")
    lines.extend(["", "--- Raw telemetry (debug) ---", message])
    full_plain = "\n".join(lines)
    secondary: List[Dict[str, str]] = []
    if auto_url and auto_url != incident_url:
        secondary.append({"label": "Automation Control Centre", "url": auto_url})
    return _admin_manual_structured_payload(
        header_title="Risk automation health",
        summary=title + ".",
        impact=biz,
        actions=action,
        resolution_url=incident_url or auto_url,
        resolution_label="Open incident" if incident_url else "Open Automation Centre",
        secondary_links=secondary or None,
        raw_debug=message,
        full_plaintext=full_plain,
        recipient=recipient,
        subject=f"[{subj_display}] {title}",
        presentation_adapter="risk_regen_queue_ops_v1",
        extra_meta={"_original_ops_subject": subject},
    )


def enrich_stripe_webhook_failure_admin_context(
    *,
    recipient: str,
    subject: str,
    message: str,
) -> Dict[str, Any]:
    """Structured admin-manual context for STRIPE_WEBHOOK_FAILURE_ADMIN (routing unchanged)."""
    cfg = get_alert_config(STRIPE_WEBHOOK_FAILURE) or {}
    base = _app_base(for_email=True)
    billing_url = f"{base}/admin/billing" if base else ""
    stored = (cfg.get("severity") or "P1").strip()
    subj_disp = format_severity_label_for_subject(translate_stored_severity_to_label(stored))
    biz = (cfg.get("business_impact") or cfg.get("description") or "").strip()
    action = (cfg.get("suggested_action") or "").strip()
    summary = "Stripe webhook processing failed with an exception while handling a billing event."
    lines = [
        "What happened",
        summary,
        "",
        "Why it matters",
        biz or "Subscription and payment state may drift from Stripe until webhooks recover.",
        "",
        "What to do next",
        action or "Check webhook endpoint logs and Stripe dashboard; retry failed events if needed.",
    ]
    if billing_url:
        lines.extend(["", "Where to resolve", billing_url])
    lines.extend(["", "--- Technical / debug ---", message])
    full_plain = "\n".join(lines)
    return _admin_manual_structured_payload(
        header_title="Billing / webhooks",
        summary=summary,
        impact=biz or "Subscription and payment state may drift from Stripe until webhooks recover.",
        actions=action or "Check webhook endpoint logs and Stripe dashboard; retry failed events if needed.",
        resolution_url=billing_url,
        resolution_label="Open Billing (admin)",
        secondary_links=None,
        raw_debug=message.strip(),
        full_plaintext=full_plain,
        recipient=recipient,
        subject=f"[{subj_disp}] Stripe webhook processing failure",
        presentation_adapter="stripe_webhook_failure_admin_v1",
        extra_meta={"_original_ops_subject": subject},
    )


def enrich_provisioning_failed_admin_context(
    *,
    recipient: str,
    job_id: str,
    client_id: Optional[str],
    error_message: str,
) -> Dict[str, Any]:
    """Structured admin-manual context for PROVISIONING_FAILED_ADMIN (routing unchanged)."""
    cfg = get_alert_config(PROVISIONING_FAILED) or {}
    base = _app_base(for_email=True)
    dash_url = f"{base}/admin/dashboard" if base else ""
    stored = (cfg.get("severity") or "P1").strip()
    subj_disp = format_severity_label_for_subject(translate_stored_severity_to_label(stored))
    biz = (cfg.get("business_impact") or cfg.get("description") or "").strip()
    action = (cfg.get("suggested_action") or "").strip()
    summary = (
        f"Tenant or channel provisioning failed for job {job_id}"
        + (f" (client {client_id})" if client_id else "")
        + "."
    )
    msg = f"Job ID: {job_id}\nClient ID: {client_id or 'N/A'}\nError: {error_message[:500]}"
    lines = [
        "What happened",
        summary,
        "",
        "Why it matters",
        biz or "Tenant messaging or telephony channels may be incomplete until provisioning succeeds.",
        "",
        "What to do next",
        action or "Check provisioning logs and provider API status; retry or fix configuration.",
        "",
        "--- Technical / debug ---",
        msg,
    ]
    full_plain = "\n".join(lines)
    new_subject = f"[{subj_disp}] Provisioning failed: job {job_id}" + (f" (client {client_id})" if client_id else "")
    return _admin_manual_structured_payload(
        header_title="Provisioning",
        summary=summary,
        impact=biz or "Tenant messaging or telephony channels may be incomplete until provisioning succeeds.",
        actions=action or "Check provisioning logs and provider API status; retry or fix configuration.",
        resolution_url=dash_url,
        resolution_label="Open Admin dashboard",
        secondary_links=None,
        raw_debug=msg.strip(),
        full_plaintext=full_plain,
        recipient=recipient,
        subject=new_subject,
        presentation_adapter="provisioning_failed_admin_v1",
    )


def enrich_order_notification_staff_context(
    *,
    recipient: str,
    event_type: str,
    order_id: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None,
    admin_display_name: str = "Admin",
) -> Dict[str, Any]:
    """
    Structured staff context for ORDER_NOTIFICATION when used for SLA / operations (alias: compliance-alert).
    Preserves template_key; adds admin_manual_structured for EmailService branch.
    """
    base = _app_base(for_email=True)
    order_url = f"{base}/admin/orders?order={order_id}" if base else ""
    meta = metadata or {}
    et = (event_type or "").strip().lower()
    is_breach = et == "sla_breach" or et.endswith("_sla_breach")
    is_warn = et == "sla_warning" or et.endswith("_sla_warning")
    if is_breach:
        header = "Order processing SLA"
        summary = (
            f"An active order has exceeded its internal processing SLA window. "
            f"Order reference: {order_id}. {message.strip()}"
        )
        urgency = "Immediate investigation recommended: clients may be waiting on deliverables tied to this order."
        subj_tok = "Urgent operational review"
    elif is_warn:
        header = "Order processing SLA"
        summary = (
            f"An active order is approaching its internal processing SLA deadline. "
            f"Order reference: {order_id}. {message.strip()}"
        )
        urgency = "Safe to monitor briefly if capacity is constrained; plan same-day follow-up if no movement."
        subj_tok = "Operational warning"
    else:
        header = "Order operations"
        summary = f"Order {order_id}: {message.strip()}"
        urgency = "Review during the next business window unless paired with a critical incident."
        subj_tok = "Operational notice"
    hours_line = ""
    if meta.get("hours_remaining") is not None:
        hours_line = f"Hours remaining (approx): {meta.get('hours_remaining')}\n"
    if meta.get("hours_overdue") is not None:
        hours_line = f"Hours overdue (approx): {meta.get('hours_overdue')}\n"
    debug = f"event_type: {event_type}\norder_id: {order_id}\n{hours_line}metadata: {json.dumps(meta, default=str)[:4000]}"
    actions = format_ordered_action_lines(
        [
            f"Open the order in Admin: {order_url}" if order_url else "Open Admin → Orders and search for the order reference.",
            "Confirm current workflow status and whether generation or review is blocked.",
            "Check Automation Centre and Observability for correlated failures.",
            "Update the customer or internal owner if the timeline will slip.",
        ]
    )
    lines = [
        "What happened",
        summary,
        "",
        "Operational impact",
        "Internal fulfilment timelines may slip; customer-visible dates on documents or deliverables may be affected.",
        "",
        "Customer impact",
        "Potential customer-facing impact: slower document turnaround or delayed communications about this order.",
        "",
        "Urgency",
        urgency,
        "",
        "If left unresolved",
        "SLA clocks continue; backlog may grow and support load may increase for the same order.",
        "",
        "Recommended actions",
        actions,
    ]
    if order_url:
        lines.extend(["", "Where to investigate", order_url])
    lines.extend(["", "--- Technical / debug ---", debug])
    full_plain = "\n".join(lines)
    return _admin_manual_structured_payload(
        header_title=header,
        summary=summary,
        impact="Order fulfilment and internal SLA tracking for this reference.",
        actions=actions,
        resolution_url=order_url,
        resolution_label="Open order in Admin",
        secondary_links=None,
        raw_debug=debug,
        full_plaintext=full_plain,
        recipient=recipient,
        subject=f"[{subj_tok}] {header} — order {order_id}",
        presentation_adapter="order_notification_staff_v1",
        extra_meta={
            "client_name": admin_display_name,
            "admin_manual_customer_impact": "Potential customer-facing impact: slower turnaround for this order until cleared.",
            "admin_manual_urgency_guidance": urgency,
            "admin_manual_if_ignored": "SLA drift and customer expectations may diverge; audit trail becomes harder to reconstruct.",
            "admin_manual_likely_causes": "Capacity limits, blocked client inputs, provider issues, or workflow exceptions.",
        },
    )


def enrich_lead_sla_breach_admin_context(
    *,
    recipient: str,
    lead_id: str,
    name: str,
    email: str,
    created_at: str,
    admin_dashboard_url: str,
) -> Dict[str, Any]:
    """Structured admin-manual context for LEAD_SLA_BREACH_ADMIN (routing unchanged)."""
    summary = (
        f"A new sales lead has not received first contact within the configured SLA window. "
        f"Lead name on file: {name or 'Unknown'}."
    )
    actions = format_ordered_action_lines(
        [
            "Open the Leads board and claim or assign this lead.",
            "Attempt first contact via the channel appropriate to consent (email or phone).",
            "Log the touchpoint in your CRM discipline so SLA metrics stay accurate.",
            "If the lead is a duplicate or spam, mark per sales runbook rather than ignoring silently.",
        ]
    )
    debug = f"lead_id: {lead_id}\nemail: {email}\ncreated_at: {created_at}"
    lines = [
        "What happened",
        summary,
        "",
        "Operational impact",
        "Sales response metrics degrade; warm leads may cool.",
        "",
        "Customer impact",
        "Potential customer-facing impact: the prospect may perceive slow response from your organisation.",
        "",
        "Urgency",
        "Timely action recommended within the same business day for high-intent services.",
        "",
        "Recommended actions",
        actions,
        "",
        "Where to investigate",
        admin_dashboard_url,
        "",
        "--- Technical / debug ---",
        debug,
    ]
    full_plain = "\n".join(lines)
    return _admin_manual_structured_payload(
        header_title="Lead response SLA",
        summary=summary,
        impact="Lead handling SLA breach for a NEW lead without first contact.",
        actions=actions,
        resolution_url=admin_dashboard_url,
        resolution_label="Open Leads",
        secondary_links=None,
        raw_debug=debug,
        full_plaintext=full_plain,
        recipient=recipient,
        subject="[Operational notice] Lead awaiting first contact",
        presentation_adapter="lead_sla_breach_admin_v1",
        extra_meta={
            "client_name": "there",
            "admin_manual_customer_impact": "Prospect experience may suffer if no timely outreach.",
            "admin_manual_urgency_guidance": "Timely action recommended within the same business day.",
            "admin_manual_if_ignored": "Lead temperature drops; conversion probability typically falls.",
            "admin_manual_likely_causes": "Inbox volume; missing assignment; weekend/holiday coverage gaps.",
        },
    )


def enrich_submission_internal_notification_context(
    *,
    recipient: str,
    submission_type: str,
    submission_id: str,
    summary: str,
    detail_url: str,
) -> Dict[str, Any]:
    """
    Structured SUPPORT_INTERNAL_NOTIFICATION for known operational submission types.
    Falls back to minimal structured copy for unknown types (no snake_case titles in subject).
    """
    st = (submission_type or "").strip().lower().replace(" ", "_")
    friendly = {
        "work_order_contractor_routing_timeout": (
            "Work order — contractor confirmation overdue",
            "A client did not confirm a recommended contractor before the deadline. The work order may need staff routing.",
        ),
    }.get(st, ("Internal admin notification", summary))
    title, desc = friendly if isinstance(friendly, tuple) else ("Internal admin notification", summary)
    actions = format_ordered_action_lines(
        [
            "Open the linked admin view and review the record.",
            "Decide whether to re-engage the client, assign manually, or close per policy.",
            "Document the decision in audit notes if your process requires it.",
        ]
    )
    debug = f"submission_type: {submission_type}\nsubmission_id: {submission_id}\nraw_summary: {summary}"
    lines = [
        "What happened",
        desc,
        "",
        "Operational impact",
        "Staff attention may be required to unblock a workflow.",
        "",
        "Urgency",
        "Timely action recommended within business hours unless tagged critical elsewhere.",
        "",
        "Recommended actions",
        actions,
        "",
        "Where to investigate",
        detail_url,
        "",
        "--- Technical / debug ---",
        debug,
    ]
    full_plain = "\n".join(lines)
    return _admin_manual_structured_payload(
        header_title="Admin operations",
        summary=desc,
        impact="Operational item requires triage in the admin console.",
        actions=actions,
        resolution_url=detail_url,
        resolution_label="Open admin record",
        secondary_links=None,
        raw_debug=debug,
        full_plaintext=full_plain,
        recipient=recipient,
        subject=f"[Operational notice] {title}",
        presentation_adapter="support_internal_notification_v1",
        extra_meta={
            "client_name": "there",
            "admin_manual_urgency_guidance": "Timely review recommended; not every item is customer-critical.",
            "admin_manual_if_ignored": "The underlying workflow may remain blocked until reviewed.",
        },
    )


def enrich_minimal_internal_alert_context(
    context: Dict[str, Any],
    *,
    default_title: Optional[str] = None,
    use_structured_operator_layout: bool = False,
) -> Dict[str, Any]:
    """
    Merge additive fields for INTERNAL_ALERT sends that only pass subject/message.
    When use_structured_operator_layout is True, also sets severity_label and summary fields
    so EmailService uses the operator-first internal layout (Phase 2).
    """
    out = dict(context)
    if out.get("message") and not out.get("description"):
        out["description"] = out["message"]
    if not out.get("title"):
        if default_title:
            out["title"] = default_title
        elif out.get("subject"):
            sub = str(out["subject"]).strip()
            out["title"] = sub[:120] + ("..." if len(sub) > 120 else "")
        else:
            out["title"] = "Internal alert"
    out.setdefault("_presentation_adapter", "minimal_internal_alert_v1")
    if use_structured_operator_layout:
        out["severity_label"] = "WARNING"
        desc = str(out.get("description") or "").strip()
        out["operational_summary"] = first_meaningful_summary_line(desc, max_len=500) or out.get("title", "")
        out["presentation_title"] = out.get("title") or default_title or "Internal alert"
        out.setdefault("business_impact", "An operational item needs staff review in the admin console.")
        out.setdefault(
            "operator_urgency_note",
            "Timely review recommended during business hours unless the subject indicates a critical incident.",
        )
        out.setdefault(
            "if_ignored_guidance",
            "The related workflow may remain paused until an admin picks it up.",
        )
        out.setdefault("recommended_actions", out.get("suggested_action") or "Open the linked admin view and continue processing.")
    return out
