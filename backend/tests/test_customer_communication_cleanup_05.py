"""Cleanup 05 — residual customer communication quality."""
from __future__ import annotations

import pytest

from models.core import EmailTemplateAlias
from services.email_event_registry import EMAIL_EVENTS
from services.email_service import EmailService, _get_onboarding_content
from services.notification_send_idempotency import should_suppress_compliance_alert_for_property
from services.branding_resolver_service import finalize_db_email_html


def test_should_suppress_single_requirement_when_daily_reminders_enabled():
    assert should_suppress_compliance_alert_for_property(
        contributing_requirement_ids=["req-gas"],
        daily_reminders_enabled=True,
    )
    assert not should_suppress_compliance_alert_for_property(
        contributing_requirement_ids=["req-gas"],
        daily_reminders_enabled=False,
    )


def test_should_not_suppress_multi_requirement_or_unknown_degradation():
    assert not should_suppress_compliance_alert_for_property(
        contributing_requirement_ids=["req-gas", "req-eicr"],
        daily_reminders_enabled=True,
    )
    assert not should_suppress_compliance_alert_for_property(
        contributing_requirement_ids=[],
        daily_reminders_enabled=True,
    )


def test_finalize_db_email_html_uses_canonical_greeting():
    html, text = finalize_db_email_html(
        "<p>Please review the attached details.</p>",
        "Please review the attached details.",
        {
            "client_name": "Ada Lovelace",
            "first_name": "Ada",
            "_email_branding": {"company_name": "Pleerity"},
        },
        "reminder",
        "client-cleanup-05",
    )
    assert "Hello Ada," in html
    assert "Please review the attached details." in html
    assert "name 'resolve_greeting'" not in html


def test_tenant_invite_omits_raw_rag_labels():
    svc = EmailService()
    html = svc._build_html_body(
        EmailTemplateAlias.TENANT_INVITE,
        {
            "tenant_name": "Jordan Tenant",
            "setup_link": "https://pleerityenterprise.co.uk/setup?token=test",
            "login_url": "https://pleerityenterprise.co.uk/login",
        },
    )
    lowered = html.lower()
    assert "green/amber/red" not in lowered
    assert " rag" not in lowered
    assert "in order" in lowered or "need a review" in lowered or "need action" in lowered


@pytest.mark.asyncio
async def test_support_confirmation_has_no_invented_sla(monkeypatch):
    captured = {}

    class _Result:
        outcome = "sent"

    async def _fake_send(**kwargs):
        captured.update(kwargs)
        return _Result()

    import services.support_email_service as svc

    monkeypatch.setattr(
        "services.notification_orchestrator.notification_orchestrator.send",
        _fake_send,
    )

    ok = await svc.send_ticket_confirmation_email(
        ticket_id="TCK-1",
        customer_email="jordan@yopmail.com",
        subject="Help with a document",
        description="I cannot upload a file",
        category="documents",
        priority="medium",
    )
    assert ok is True
    message = captured["context"]["message"]
    assert "24 hours" not in message.lower()
    assert "TCK-1" in message
    assert "received your request" in message.lower()
    assert "no guaranteed response time" in message.lower()
    assert "You have a new notification from Pleerity" not in message
    assert "/help" in captured["context"]["message"]
    assert "/support\"" not in captured["context"]["message"]


def test_onboarding_day2_adapts_when_property_exists():
    empty = _get_onboarding_content(
        EmailTemplateAlias.ONBOARDING_DAY2_COMPLIANCE_EDUCATION,
        {"has_added_property": False},
    )
    ready = _get_onboarding_content(
        EmailTemplateAlias.ONBOARDING_DAY2_COMPLIANCE_EDUCATION,
        {"has_added_property": True},
    )
    assert "Add a property" in empty["cta_label"]
    assert "Review your requirements" in ready["cta_label"]
    assert "legal penalties" not in ready["body"].lower()


def test_onboarding_day5_not_fear_based():
    copy = _get_onboarding_content(
        EmailTemplateAlias.ONBOARDING_DAY5_RISK_AWARENESS,
        {"has_added_property": True, "monitoring_enabled": False},
    )
    assert "legal penalties" not in copy["body"].lower()
    assert "insurance issues" not in copy["body"].lower()


def test_compliance_alert_subject_omits_rag_jargon():
    from email_presentation.status_colors import customer_facing_compliance_alert_subject

    red = customer_facing_compliance_alert_subject(
        [{"new_status": "RED"}, {"new_status": "AMBER"}]
    )
    amber = customer_facing_compliance_alert_subject([{"new_status": "AMBER"}])
    assert "RED" not in red and "AMBER" not in red and "RAG" not in red
    assert red == "A property needs attention"
    assert amber == "A property needs review"


def test_registry_marks_unimplemented_without_renaming_live_keys():
    assert EMAIL_EVENTS["PAYMENT_FAILED"]["template_key"] == "PAYMENT_FAILED"
    assert EMAIL_EVENTS["SUBSCRIPTION_RENEWAL_REMINDER_7D"]["template_key"] == (
        "SUBSCRIPTION_RENEWAL_REMINDER_7D"
    )
    assert EMAIL_EVENTS["INVOICE_AVAILABLE"].get("lifecycle_status") == "NOT_IMPLEMENTED"
    assert EMAIL_EVENTS["DOCUMENT_PACK_DELIVERY"].get("lifecycle_status") == "SUPERSEDED"
    assert EMAIL_EVENTS["RENEWAL_REMINDER"].get("lifecycle_status") == "LEGACY_ALIAS"
