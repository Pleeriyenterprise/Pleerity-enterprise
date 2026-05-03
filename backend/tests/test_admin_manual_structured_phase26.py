"""Phase 2.6: structured admin-manual layout; legacy compatibility."""
from unittest.mock import patch

import pytest

from email_templates.admin_manual_structured_layout import (
    build_admin_manual_structured_html,
    build_admin_manual_structured_plain_text,
)
from models.core import EmailTemplateAlias
from services.email_service import EmailService
from services.operational_alert_presentation import (
    enrich_ops_notification_spike_email_context,
    enrich_provisioning_failed_admin_context,
    enrich_stripe_webhook_failure_admin_context,
)


def test_legacy_admin_manual_html_unchanged_when_not_structured():
    svc = EmailService()
    html = svc._build_html_body(
        EmailTemplateAlias.ADMIN_MANUAL,
        {
            "client_name": "Alex",
            "message": "Short legacy staff note.\nSecond line.",
        },
    )
    assert "Compliance Vault Pro" in html
    assert "Short legacy staff note." in html
    assert "Summary" not in html
    assert "admin_manual" not in html.lower()


def test_legacy_admin_manual_plain_text_unchanged():
    svc = EmailService()
    text = svc._build_text_body(
        EmailTemplateAlias.ADMIN_MANUAL,
        {"client_name": "Alex", "message": "Plain only."},
    )
    assert "Plain only." in text
    assert "Summary" not in text


def test_structured_admin_manual_html_contains_sections():
    model = {
        "client_name": "Ops",
        "admin_manual_structured": True,
        "admin_manual_header_title": "Test header",
        "admin_manual_summary": "Something failed at the edge.",
        "admin_manual_impact": "Users may see delays.",
        "admin_manual_actions": "Check logs and retry.",
        "admin_manual_resolution_url": "https://app.example/admin/observability",
        "admin_manual_resolution_label": "Open Observability",
        "admin_manual_debug": "trace_id=abc",
    }
    html = build_admin_manual_structured_html(model)
    assert "Summary" in html
    assert "Operational impact" in html
    assert "Recommended actions" in html
    assert "Technical / debug" in html
    assert "https://app.example/admin/observability" in html


def test_structured_plain_text_includes_sections():
    model = {
        "client_name": "Ops",
        "admin_manual_header_title": "H",
        "admin_manual_summary": "S",
        "admin_manual_impact": "I",
        "admin_manual_actions": "A",
        "admin_manual_resolution_url": "https://x/y",
        "admin_manual_resolution_label": "Go",
        "admin_manual_debug": "D",
    }
    t = build_admin_manual_structured_plain_text(model, footer="\n--footer--\n")
    assert "Summary" in t
    assert "Operational impact" in t
    assert "--footer--" in t


def test_email_service_uses_structured_when_flag_and_summary():
    svc = EmailService()
    model = {
        "admin_manual_structured": True,
        "admin_manual_header_title": "Ops",
        "admin_manual_summary": "Spike detected.",
        "admin_manual_impact": "Impact line.",
        "admin_manual_actions": "Act.",
        "admin_manual_resolution_url": "https://app.example/admin/observability",
        "admin_manual_resolution_label": "Observability",
        "admin_manual_debug": "raw",
        "client_name": "there",
    }
    html = svc._build_html_body(EmailTemplateAlias.ADMIN_MANUAL, model)
    assert "Spike detected." in html
    assert "Technical / debug" in html


@pytest.mark.parametrize(
    "enrich_fn,kwargs",
    [
        (
            enrich_ops_notification_spike_email_context,
            dict(
                recipient="r@x.c",
                subject="[WARN] old",
                message="Severity: WARN\nTop: x",
                ops_severity_token="WARN",
                failed_count=5,
                lookback_minutes=15,
            ),
        ),
        (
            enrich_stripe_webhook_failure_admin_context,
            dict(recipient="r@x.c", subject="old", message="Error: boom"),
        ),
        (
            enrich_provisioning_failed_admin_context,
            dict(recipient="r@x.c", job_id="job1", client_id=None, error_message="e"),
        ),
    ],
)
def test_operational_enrichers_set_admin_manual_structured(enrich_fn, kwargs):
    with patch("services.operational_alert_presentation.get_app_base_url", return_value="https://app.example"):
        ctx = enrich_fn(**kwargs)
    assert ctx.get("admin_manual_structured") is True
    assert str(ctx.get("admin_manual_summary") or "").strip()
    assert "message" in ctx


def test_structured_without_summary_falls_back_to_legacy_in_email_service():
    """Guard: structured flag alone must not switch layout (requires summary)."""
    svc = EmailService()
    html = svc._build_html_body(
        EmailTemplateAlias.ADMIN_MANUAL,
        {"admin_manual_structured": True, "message": "Only message", "client_name": "A"},
    )
    assert "Only message" in html
    assert "Operational impact" not in html
