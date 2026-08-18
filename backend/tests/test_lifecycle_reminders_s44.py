"""Phase 4 S4.4 — dedicated attention_kind email/SMS reminder templates."""

from __future__ import annotations

import pytest

from models import EmailTemplateAlias
from notification_template_seed_definitions import (
    CORE_NOTIFICATION_TEMPLATE_SEED_DEFINITIONS,
    all_notification_template_keys_from_seed,
)
from services.email_service import EmailService, LIFECYCLE_REMINDER_ALIASES
from services.lifecycle_reminder_gates import resolve_lifecycle_reminder_template_key
from services.lifecycle_reminder_template_registry import (
    ATTENTION_KINDS,
    all_lifecycle_reminder_template_keys,
    lifecycle_reminder_email_alias,
    lifecycle_reminder_email_template_key,
    lifecycle_reminder_notification_seed_rows,
    lifecycle_reminder_sms_template_key,
    lifecycle_reminder_spec,
)


class TestLifecycleReminderTemplateRegistry:
    def test_all_attention_kinds_have_seed_rows(self):
        seed_keys = {row["template_key"] for row in lifecycle_reminder_notification_seed_rows()}
        for kind in ATTENTION_KINDS:
            assert lifecycle_reminder_email_template_key(kind) in seed_keys
            assert lifecycle_reminder_sms_template_key(kind) in seed_keys

    def test_seed_rows_registered_in_core_definitions(self):
        core_keys = {row["template_key"] for row in CORE_NOTIFICATION_TEMPLATE_SEED_DEFINITIONS}
        assert all_lifecycle_reminder_template_keys().issubset(core_keys)

    def test_review_due_copy_avoids_certificate_expiry_language(self):
        spec = lifecycle_reminder_spec("REVIEW_DUE")
        assert "expiry" not in spec["header_title"].lower()
        assert "review" in spec["intro_html"].lower()
        assert lifecycle_reminder_email_alias("REVIEW_DUE") == "lifecycle-reminder-review-due"


class TestLifecycleReminderTemplateRoutingS44:
    def test_shadow_still_authoritative_legacy(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        assert resolve_lifecycle_reminder_template_key("REVIEW_DUE") == "COMPLIANCE_EXPIRY_REMINDER"

    def test_off_still_legacy(self, monkeypatch):
        monkeypatch.delenv("LIFECYCLE_AWARE_REMINDERS", raising=False)
        assert resolve_lifecycle_reminder_template_key("REVIEW_DUE") == "COMPLIANCE_EXPIRY_REMINDER"

    def test_active_preview_resolves_lifecycle_keys(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")
        for kind in ATTENTION_KINDS:
            assert resolve_lifecycle_reminder_template_key(kind) == lifecycle_reminder_email_template_key(kind)
            assert resolve_lifecycle_reminder_template_key(kind, channel="SMS") == lifecycle_reminder_sms_template_key(
                kind
            )

    def test_shadow_logs_template_divergence(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        resolve_lifecycle_reminder_template_key("REVIEW_DUE")
        assert "lifecycle_reminder_shadow_template_routing" in caplog.text


class TestLifecycleReminderEmailCopy:
    @pytest.mark.parametrize(
        "alias,attention_kind,expected_phrase",
        [
            (EmailTemplateAlias.REMINDER, "CERTIFICATE_EXPIRING", "expires in"),
            (EmailTemplateAlias.LIFECYCLE_REMINDER_REVIEW_DUE, "REVIEW_DUE", "review due on"),
            (
                EmailTemplateAlias.LIFECYCLE_REMINDER_EVENT_ACTION_REQUIRED,
                "EVENT_ACTION_REQUIRED",
                "requires action by",
            ),
        ],
    )
    def test_lifecycle_reminder_email_body_uses_kind_specific_copy(
        self,
        alias: EmailTemplateAlias,
        attention_kind: str,
        expected_phrase: str,
    ):
        svc = EmailService()
        model = {
            "client_name": "Test Client",
            "requirement_name": "Legionella",
            "property_address": "1 Test Street",
            "due_date": "2026-07-01",
            "days_remaining": 10,
            "portal_link": "https://example.com/today",
            "lifecycle_attention_kind": attention_kind,
        }
        html = svc._build_html_body(alias, model)
        assert expected_phrase in html
        assert alias in LIFECYCLE_REMINDER_ALIASES

    def test_all_lifecycle_seed_keys_in_notification_governance_set(self):
        assert all_lifecycle_reminder_template_keys().issubset(all_notification_template_keys_from_seed())
