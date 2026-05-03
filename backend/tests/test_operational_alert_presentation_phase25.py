"""Phase 2.5: adapters for OPS spike, risk regen OPS email, minimal INTERNAL_ALERT compatibility."""
from unittest.mock import patch

from email_templates.internal_alert_layout import build_internal_alert_html

from services.operational_alert_presentation import (
    enrich_minimal_internal_alert_context,
    enrich_ops_notification_spike_email_context,
    enrich_risk_regen_queue_ops_email_context,
)


def test_enrich_ops_spike_includes_registry_and_debug_block():
    raw = "Severity: WARN\nFailed count: 12\nTop templates:\n  - T: 1"
    with patch("services.operational_alert_presentation.get_app_base_url", return_value="https://app.example"):
        ctx = enrich_ops_notification_spike_email_context(
            recipient="ops@test.com",
            subject="[WARN] legacy",
            message=raw,
            ops_severity_token="WARN",
            failed_count=12,
            lookback_minutes=15,
        )
    assert ctx["recipient"] == "ops@test.com"
    assert "WARNING" in ctx["subject"]
    assert "What happened" in ctx["message"]
    assert "https://app.example/admin/observability" in ctx["message"]
    assert "--- Raw telemetry (debug) ---" in ctx["message"]
    assert raw in ctx["message"]
    assert ctx.get("_presentation_adapter") == "ops_notification_spike_v1"


def test_enrich_ops_spike_crit_uses_critical_label():
    with patch("services.operational_alert_presentation.get_app_base_url", return_value="https://app.example"):
        ctx = enrich_ops_notification_spike_email_context(
            recipient="ops@test.com",
            subject="[CRIT] legacy",
            message="raw",
            ops_severity_token="CRIT",
            failed_count=99,
            lookback_minutes=15,
        )
    assert "CRITICAL" in ctx["subject"]


def test_enrich_risk_regen_includes_incident_and_debug():
    raw = "Risk signal regeneration queue reports"
    with patch("services.operational_alert_presentation.get_app_base_url", return_value="https://app.example"):
        ctx = enrich_risk_regen_queue_ops_email_context(
            recipient="ops@test.com",
            subject="[P2] legacy",
            message=raw,
            incident_id="507f1f77bcf86cd799439011",
        )
    assert "507f1f77bcf86cd799439011" in ctx["message"]
    assert "Automation Control Centre" in ctx["message"]
    assert "--- Raw telemetry (debug) ---" in ctx["message"]
    assert raw in ctx["message"]
    assert ctx.get("_presentation_adapter") == "risk_regen_queue_ops_v1"


def test_enrich_minimal_internal_alert_sets_description_and_title():
    ctx = enrich_minimal_internal_alert_context(
        {"recipient": "a@b.c", "subject": "Subj", "message": "Body text"},
        default_title="Client information submitted",
    )
    assert ctx["description"] == "Body text"
    assert ctx["title"] == "Client information submitted"


def test_internal_alert_legacy_html_includes_message_when_no_description():
    html = build_internal_alert_html(
        {
            "severity": "P2",
            "title": "Client information submitted",
            "message": "Plain body from token flow.",
            "dashboard_link": "https://app.example/admin/orders?order=123",
            "suggested_action": "Review order.",
            "component": "Orders",
        }
    )
    assert "Plain body from token flow." in html
    assert "Client information submitted" in html


def test_internal_alert_legacy_still_works_description_only():
    html = build_internal_alert_html(
        {
            "severity": "P2",
            "title": "T",
            "description": "Desc only",
        }
    )
    assert "Desc only" in html
