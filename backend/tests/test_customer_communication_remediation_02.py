"""Customer communication quality remediation 02 — P0/P1 render and authority tests."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lifecycle_communication.context import infer_communication_family
from lifecycle_communication.copy import build_reason
from lifecycle_communication.resolver import resolve_reminder_subject
from models import EmailTemplateAlias
from services.email_service import EmailService, _get_onboarding_content
from services.subscription_lifecycle_service import (
    resolve_subscription_canceled_customer_copy,
    subscription_renewal_reminder_subject,
)
from services.jobs import _workflow_aware_reminder_line
from services.maintenance_service import _contractor_assignment_message_html


def _html(alias, model):
    return EmailService()._build_html_body(alias, model)


def test_overdue_line_never_says_before_expiry():
    line = _workflow_aware_reminder_line(
        {"workflow_class": "DOCUMENT_UPLOAD"},
        classification="overdue",
        days_until_due=-29,
    )
    assert "before expiry" not in line.lower()
    assert "overdue" in line.lower()


def test_registration_reason_does_not_duplicate_noun():
    reason = build_reason(
        "REGISTRATION",
        req_name="Scottish landlord registration",
        due_date="09 June",
        is_overdue=True,
    )
    assert "registration registration" not in reason.lower()
    assert "scottish landlord registration is overdue" in reason.lower()


def test_hmo_fire_family_is_evidence_not_certificate():
    fam = infer_communication_family(
        {
            "requirement_code": "hmo_fire_risk",
            "requirement_name": "HMO fire safety evidence",
            "lifecycle_attention_kind": "CERTIFICATE_EXPIRING",
            "workflow_class": "MULTI_EVIDENCE",
        }
    )
    assert fam == "DOCUMENT_EVIDENCE"
    subj = resolve_reminder_subject(
        {
            "requirement_name": "HMO fire safety evidence",
            "requirement_code": "hmo_fire_risk",
            "lifecycle_attention_kind": "CERTIFICATE_EXPIRING",
            "workflow_class": "MULTI_EVIDENCE",
        },
        is_overdue=True,
    )
    assert "renewal" not in subj.lower()
    assert "hmo fire safety evidence is overdue" in subj.lower()


def test_review_subject_does_not_force_expiry_or_renewal():
    subj = resolve_reminder_subject(
        {
            "requirement_name": "Occupancy review",
            "lifecycle_attention_kind": "OCCUPANCY_REVIEW_DUE",
        },
        is_overdue=False,
        days_remaining=7,
    )
    assert "expir" not in subj.lower()
    assert "renewal" not in subj.lower()
    assert "due" in subj.lower()


def test_eicr_upcoming_subject_uses_calculated_days():
    subj = resolve_reminder_subject(
        {
            "requirement_name": "EICR",
            "requirement_code": "eicr",
            "lifecycle_attention_kind": "CERTIFICATE_EXPIRING",
        },
        is_overdue=False,
        days_remaining=14,
    )
    assert "14" in subj
    assert "7 days" not in subj


def test_single_requirement_render_excludes_sibling():
    html = _html(
        EmailTemplateAlias.REMINDER,
        {
            "client_name": "Alex",
            "requirement_name": "Scottish landlord registration",
            "requirement_code": "scottish_landlord_registration",
            "property_address": "12 High Street",
            "due_date": "09 June 2026",
            "is_overdue": True,
            "days_overdue": 29,
            "days_remaining": 0,
            "single_requirement_reminder": True,
            "semantic_line": "This requirement is overdue by 29 days",
            "portal_link": "https://example.test/properties/p1?requirement_id=r1",
            "cta_label": "View Scottish landlord registration",
            "lifecycle_attention_kind": "CERTIFICATE_EXPIRING",
        },
    )
    assert "Scottish landlord registration" in html
    assert "HMO fire" not in html
    assert "before expiry" not in html.lower()
    assert "29 days overdue" in html
    assert "View Scottish landlord registration" in html
    assert "12 High Street" in html
    assert "registration registration" not in html.lower()


def test_two_unrelated_requirements_render_independently():
    a = _html(
        EmailTemplateAlias.REMINDER,
        {
            "requirement_name": "Scottish landlord registration",
            "requirement_code": "scottish_landlord_registration",
            "property_address": "A Street",
            "is_overdue": True,
            "days_overdue": 10,
            "single_requirement_reminder": True,
            "subject": "Scottish landlord registration is overdue",
            "portal_link": "https://example.test/properties/p1?requirement_id=r-reg",
        },
    )
    b = _html(
        EmailTemplateAlias.REMINDER,
        {
            "requirement_name": "HMO fire safety evidence",
            "requirement_code": "hmo_fire_risk",
            "property_address": "A Street",
            "is_overdue": True,
            "days_overdue": 4,
            "single_requirement_reminder": True,
            "subject": "HMO fire safety evidence is overdue",
            "portal_link": "https://example.test/properties/p1?requirement_id=r-hmo",
            "cta_label": "Upload HMO fire safety evidence",
        },
    )
    assert "HMO fire" not in a
    assert "landlord registration" not in b.lower() or "scottish" not in b.lower()
    assert "Upload HMO fire safety evidence" in b


def test_monthly_digest_still_aggregate_shaped():
    html = _html(
        EmailTemplateAlias.MONTHLY_DIGEST,
        {
            "client_name": "Alex",
            "subject": "Your monthly compliance summary",
            "period_label": "July 2026",
            "portal_link": "https://example.test/today",
        },
    )
    assert "monthly" in html.lower() or "digest" in html.lower() or "summary" in html.lower()


def test_payment_failed_code_built_without_retry_does_not_invent_or_genericize():
    html = _html(
        EmailTemplateAlias.PAYMENT_FAILED,
        {
            "client_name": "Alex",
            "billing_portal_link": "https://example.test/settings/billing",
            "plan_code": "portfolio",
            "entitlement_status": "LIMITED",
            "access_suspended": False,
        },
    )
    low = html.lower()
    assert "unsuccessful" in low or "unable to collect" in low
    assert "you have a new notification from pleerity" not in low
    assert "has not been suspended" in low
    assert "grace-period end" not in low or "not a pleerity grace" in low
    assert "update billing" in low


def test_payment_failed_with_retry_date_labels_stripe_retry():
    html = _html(
        EmailTemplateAlias.PAYMENT_FAILED,
        {
            "client_name": "Alex",
            "billing_portal_link": "https://example.test/settings/billing",
            "retry_date": "August 20, 2026",
            "entitlement_status": "LIMITED",
        },
    )
    assert "August 20, 2026" in html
    assert "Stripe" in html
    assert "grace-period end" in html.lower()


def test_canceled_copy_uses_period_end_not_webhook_now():
    period_end = datetime(2026, 8, 1, tzinfo=timezone.utc)
    copy = resolve_subscription_canceled_customer_copy(
        stripe_subscription={
            "cancel_at_period_end": True,
            "current_period_end": int(period_end.timestamp()),
            "ended_at": int(period_end.timestamp()),
        },
        billing={"entitlement_status": "DISABLED"},
        now=datetime(2026, 8, 18, tzinfo=timezone.utc),
        effective_entitlement="DISABLED",
    )
    assert copy["access_end_date_known"] is True
    assert "August 1, 2026" in copy["access_end_date"]
    assert "August 18" not in copy["access_end_date"]
    html = _html(
        EmailTemplateAlias.SUBSCRIPTION_CANCELED,
        {
            "client_name": "Alex",
            "access_end_date": copy["access_end_date"],
            "access_body_html": copy["access_body_html"],
            "billing_portal_link": "https://example.test/settings/billing",
        },
    )
    assert "August 1, 2026" in html
    assert "cancelled" in html.lower() or "canceled" in html.lower()


def test_canceled_copy_missing_period_does_not_invent_date():
    copy = resolve_subscription_canceled_customer_copy(
        stripe_subscription={"cancel_at_period_end": False},
        billing={"entitlement_status": "DISABLED"},
        effective_entitlement="DISABLED",
    )
    assert copy["access_end_date_known"] is False
    assert copy["access_end_date"] == ""
    assert "cannot confirm" in copy["access_body_text"].lower()


def test_renewal_subject_uses_actual_days():
    assert subscription_renewal_reminder_subject(6) == "Your subscription renews in 6 days"
    assert subscription_renewal_reminder_subject(1) == "Your subscription renews tomorrow"
    assert subscription_renewal_reminder_subject(3) == "Your subscription renews in 3 days"


def test_onboarding_day0_adapts_when_property_exists():
    c = _get_onboarding_content(
        EmailTemplateAlias.ONBOARDING_DAY0_WELCOME,
        {"has_added_property": True},
    )
    assert "Add your first property" not in c["cta_label"]
    assert "first property is on the account" in c["body"].lower() or "view your properties" in c["cta_label"].lower()


def test_onboarding_day1_neutral_when_jurisdiction_unknown():
    c = _get_onboarding_content(
        EmailTemplateAlias.ONBOARDING_DAY1_SETUP_REMINDER,
        {"jurisdiction_known": False, "jurisdiction_label": ""},
    )
    assert "CP12" not in c["body"]
    assert "safety certificates, registrations and records" in c["body"]


def test_onboarding_day7_does_not_say_activate_if_monitoring_on():
    c = _get_onboarding_content(
        EmailTemplateAlias.ONBOARDING_DAY7_ACTIVATION_PUSH,
        {"monitoring_enabled": True, "has_added_property": True},
    )
    assert "Activate monitoring" not in c["cta_label"]


def test_contractor_assignment_html_contains_job_and_cta():
    html = _contractor_assignment_message_html(
        kind_label="compliance execution",
        work_order_id="WO-1",
        description="EICR inspection",
        property_address="1 Test St",
        due_date_str="20 August 2026",
        job_link="https://example.test/jobs/secure",
    )
    assert "WO-1" in html
    assert "1 Test St" in html
    assert "https://example.test/jobs/secure" in html
    assert "EICR inspection" in html


@pytest.mark.asyncio
async def test_send_daily_reminders_emits_two_independent_emails():
    from services.jobs import JobScheduler
    import os

    with patch.dict(os.environ, {"MONGO_URL": "mongodb://localhost:27017", "DB_NAME": "test"}):
        scheduler = JobScheduler()
    scheduler.db = MagicMock()
    scheduler.db.audit_logs.insert_one = AsyncMock()
    captured = []

    async def _fake_send(*, template_key, client_id, context, idempotency_key, event_type):
        captured.append(
            {
                "template_key": template_key,
                "idempotency_key": idempotency_key,
                "subject": context.get("subject"),
                "requirement_name": context.get("requirement_name"),
                "body_name": context.get("requirement_name"),
            }
        )
        return SimpleNamespace(outcome="sent")

    with patch("services.notification_orchestrator.notification_orchestrator.send", new=AsyncMock(side_effect=_fake_send)):
        with patch("services.webhook_service.fire_reminder_sent", new=AsyncMock()):
            ok1 = await scheduler._send_reminder_email(
                {"client_id": "c-1", "email": "a@test.com", "full_name": "Client"},
                expiring=[],
                overdue=[
                    {
                        "type": "Scottish landlord registration",
                        "code": "scottish_landlord_registration",
                        "requirement_id": "r-reg",
                        "property_id": "p1",
                        "property_address": "A Street",
                        "due_date": "09 June 2026",
                        "due_date_iso": "2026-06-09",
                        "days_overdue": 29,
                        "is_overdue": True,
                        "lifecycle_window": "overdue",
                        "semantic_line": "This requirement is overdue by 29 days",
                        "workflow_semantics_bucket": "REGISTRATION_TRACKING",
                        "lifecycle_attention_kind": "CERTIFICATE_EXPIRING",
                    }
                ],
                recipient_email="a@test.com",
                reminder_refs=[{"requirement_id": "r-reg", "property_id": "p1", "due_date": "2026-06-09"}],
            )
            ok2 = await scheduler._send_reminder_email(
                {"client_id": "c-1", "email": "a@test.com", "full_name": "Client"},
                expiring=[],
                overdue=[
                    {
                        "type": "HMO fire safety evidence",
                        "code": "hmo_fire_risk",
                        "requirement_id": "r-hmo",
                        "property_id": "p1",
                        "property_address": "A Street",
                        "due_date": "01 July 2026",
                        "due_date_iso": "2026-07-01",
                        "days_overdue": 4,
                        "is_overdue": True,
                        "lifecycle_window": "overdue",
                        "semantic_line": "Required evidence is overdue and incomplete",
                        "workflow_semantics_bucket": "MULTI_EVIDENCE",
                        "lifecycle_attention_kind": "CERTIFICATE_EXPIRING",
                    }
                ],
                recipient_email="a@test.com",
                reminder_refs=[{"requirement_id": "r-hmo", "property_id": "p1", "due_date": "2026-07-01"}],
            )
    assert ok1 and ok2
    assert len(captured) == 2
    assert captured[0]["idempotency_key"] != captured[1]["idempotency_key"]
    assert "registration" in (captured[0]["subject"] or "").lower()
    assert "hmo" in (captured[1]["subject"] or "").lower()
    assert "hmo" not in (captured[0]["subject"] or "").lower()
