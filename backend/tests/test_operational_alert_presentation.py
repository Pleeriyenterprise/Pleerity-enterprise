"""Tests for Phase 2 operational alert presentation layer (no persistence / trigger changes)."""
from unittest.mock import patch

from services.internal_alert_registry import JOB_DEGRADED, JOB_MISSED_SLA, SCHEDULER_HEARTBEAT_STALE
from services.operational_alert_presentation import (
    build_internal_alert_email_context,
    build_operational_presentation_for_incident,
    format_severity_label_for_subject,
    infer_alert_type_from_incident,
    translate_stored_severity_to_label,
)


def test_translate_stored_severity_to_label():
    assert translate_stored_severity_to_label("P0") == "CRITICAL"
    assert translate_stored_severity_to_label("P1") == "ACTION_REQUIRED"
    assert translate_stored_severity_to_label("P2") == "WARNING"
    assert translate_stored_severity_to_label(None) == "WARNING"


def test_format_severity_label_for_subject():
    assert format_severity_label_for_subject("ACTION_REQUIRED") == "ACTION REQUIRED"
    assert format_severity_label_for_subject("CRITICAL") == "CRITICAL"


def test_infer_alert_type_degraded_metadata():
    inc = {
        "id": "507f1f77bcf86cd799439011",
        "source": "job_monitor",
        "title": "Job foo missed SLA",
        "metadata": {"degraded_run": True},
    }
    assert infer_alert_type_from_incident(inc) == JOB_DEGRADED


def test_infer_alert_type_missed_sla():
    inc = {
        "id": "507f1f77bcf86cd799439011",
        "source": "job_monitor",
        "title": "Job foo missed SLA",
        "metadata": {},
    }
    assert infer_alert_type_from_incident(inc) == JOB_MISSED_SLA


def test_infer_alert_type_heartbeat():
    inc = {
        "id": "507f1f77bcf86cd799439011",
        "source": "heartbeat",
        "title": "Scheduler heartbeat stale",
        "metadata": {},
    }
    assert infer_alert_type_from_incident(inc) == SCHEDULER_HEARTBEAT_STALE


def test_build_operational_presentation_resolution_paths():
    inc = {
        "id": "507f1f77bcf86cd799439011",
        "severity": "P1",
        "title": "Scheduler heartbeat stale",
        "description": "The background scheduler has not updated the heartbeat.\nSecond line ignored for summary.",
        "source": "heartbeat",
        "metadata": {"last_heartbeat_at": "2024-01-01T00:00:00Z"},
        "related_job_name": None,
    }
    with patch("services.operational_alert_presentation.get_app_base_url", return_value="https://app.example"):
        pr = build_operational_presentation_for_incident(inc, for_email_links=True)
    assert pr["severity_label"] == "ACTION_REQUIRED"
    assert pr["resolution_links"]["incident"] == "https://app.example/admin/incidents?highlight=507f1f77bcf86cd799439011"
    assert pr["resolution_links"]["system_health"].startswith("https://app.example/admin/system-health")
    assert "Stored severity" in pr["technical_details"]
    assert pr["operational_summary"].startswith("The background scheduler")


def test_build_operational_presentation_spa_paths_without_email_flag():
    inc = {
        "id": "507f1f77bcf86cd799439011",
        "severity": "P2",
        "title": "Delivery unknown unresolved",
        "description": "Runs still have delivery_unknown.",
        "source": "delivery_unknown",
        "metadata": {"stale_run_count": 3},
    }
    pr = build_operational_presentation_for_incident(inc, for_email_links=False)
    assert pr["resolution_links"]["incident"] == "/admin/incidents?highlight=507f1f77bcf86cd799439011"
    assert pr["resolution_links"]["observability"] == "/admin/observability"


def test_build_internal_alert_email_context_structured_fields():
    with patch("services.operational_alert_presentation.get_app_base_url", return_value="https://app.example"):
        ctx = build_internal_alert_email_context(
            incident_id="507f1f77bcf86cd799439011",
            stored_severity="P0",
            title="Job risk_signal_regen_worker missed SLA",
            description="Job overdue.\nDetails here.",
            source="job_monitor",
            metadata={"max_delay_minutes": 10, "delay_minutes": 15},
            related_job_name="risk_signal_regen_worker",
            related_job_run_id=None,
            last_finished_at="2024-01-01T00:00:00Z",
            last_successful_at=None,
            is_degraded_alert=False,
            expected_interval="every 10 min",
            current_status="Job overdue.",
            suggested_action="Check Automation Centre.",
            component="Job Monitor",
            possible_impact="SLA miss",
            timestamp="2024-01-02 12:00:00 UTC",
        )
    assert ctx["severity"] == "P0"
    assert ctx["severity_label"] == "CRITICAL"
    assert "[CRITICAL]" in ctx["subject"]
    assert ctx["operational_summary"].startswith("Job overdue")
    assert ctx["resolution_link"].startswith("https://app.example/admin/incidents")
    assert "Technical details" not in ctx  # layout responsibility; raw block:
    assert "max_delay_minutes" in ctx["technical_details"]
    assert ctx["business_impact"]


def test_internal_alert_html_structured_contains_collapsed_technical():
    from email_templates.internal_alert_layout import build_internal_alert_html

    html = build_internal_alert_html(
        {
            "severity_label": "WARNING",
            "severity": "P2",
            "presentation_title": "Delivery unknown unresolved",
            "operational_summary": "First line summary.",
            "business_impact": "Impact text.",
            "recommended_actions": "Check logs.",
            "resolution_link": "https://app.example/admin/incidents?highlight=1",
            "dashboard_link": "https://app.example/admin/observability",
            "technical_details": "k: v",
            "timestamp": "2024-01-01 00:00:00 UTC",
        }
    )
    assert "Technical details" in html
    assert "Open incident" in html
    assert "(reference: P2)" in html


def test_email_service_internal_alert_plain_structured():
    from models.core import EmailTemplateAlias
    from services.email_service import EmailService

    svc = EmailService()
    model = {
        "severity_label": "ACTION_REQUIRED",
        "presentation_title": "Test",
        "operational_summary": "Summary line.",
        "business_impact": "Different impact text.",
        "recommended_actions": "Do the thing.",
        "resolution_link": "https://app.example/admin/incidents?highlight=1",
        "dashboard_link": "https://app.example/admin/observability",
        "technical_details": "meta: 1",
        "severity": "P1",
        "timestamp": "t",
    }
    text = svc._build_text_body(EmailTemplateAlias.INTERNAL_ALERT, model)
    assert "ACTION REQUIRED" in text
    assert "Summary line." in text
    assert "Technical details" in text
    assert "Stored severity reference: P1" in text
