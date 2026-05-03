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
        return f"Critical job: {related_job_name}"
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
    `customer_impact` is only set when explicitly configured on the alert registry entry (never fabricated).
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
    presentation_title = str(title).strip() or "Operational incident"
    operational_summary = first_meaningful_summary_line(description) or presentation_title

    if config:
        business_impact = (config.get("business_impact") or config.get("description") or description).strip()
        affected_component = str(config.get("component") or "").strip() or "Operations"
        recommended_actions = str(config.get("suggested_action") or "").strip()
    else:
        business_impact = (first_meaningful_summary_line(description, max_len=600) or operational_summary).strip()
        affected_component = (str(related_job_name).strip() if related_job_name else "") or "Operations"
        recommended_actions = "Review the incident in Admin → Incidents and related observability views."

    customer_impact_raw = (config or {}).get("customer_impact")
    customer_impact = (str(customer_impact_raw).strip() if customer_impact_raw else None) or None

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


def enrich_minimal_internal_alert_context(
    context: Dict[str, Any],
    *,
    default_title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Merge additive fields for INTERNAL_ALERT sends that only pass subject/message.
    Does not set severity_label (avoids switching to structured internal layout).
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
    return out
