"""Phase 4 S4.1 — lifecycle-aware reminder flag infrastructure tests."""

from __future__ import annotations

import logging

from scripts.deployment_governance_ci_gate import check_production_blueprints_lifecycle_active
from services.lifecycle_aware_reminders_config import (
    get_effective_reminder_mode,
    get_lifecycle_aware_reminder_mode,
    is_lifecycle_aware_reminder_active,
    is_lifecycle_aware_reminder_off,
    is_lifecycle_aware_reminder_shadow,
    validate_lifecycle_reminder_boot,
)


class TestReminderModeConfig:
    def test_default_off(self, monkeypatch):
        monkeypatch.delenv("LIFECYCLE_AWARE_REMINDERS", raising=False)
        assert get_effective_reminder_mode() == "off"
        assert get_lifecycle_aware_reminder_mode() == "off"
        assert is_lifecycle_aware_reminder_off() is True

    def test_shadow_on_staging(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        assert get_effective_reminder_mode() == "shadow"
        assert is_lifecycle_aware_reminder_shadow() is True

    def test_preview_active_allowed(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")
        assert get_effective_reminder_mode() == "active"
        assert is_lifecycle_aware_reminder_active() is True

    def test_preview_override_allows_active_on_staging(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDER_PREVIEW_OVERRIDE", "1")
        assert get_effective_reminder_mode() == "active"

    def test_production_preview_override_never_active(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "production")
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDER_PREVIEW_OVERRIDE", "1")
        assert get_effective_reminder_mode() == "off"
        assert is_lifecycle_aware_reminder_active() is False

    def test_staging_active_downgrades_to_shadow(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        assert get_effective_reminder_mode() == "shadow"
        assert is_lifecycle_aware_reminder_active() is False

    def test_production_active_downgrades_to_off(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "production")
        assert get_effective_reminder_mode() == "off"

    def test_production_boot_guard_never_active(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "production")
        monkeypatch.delenv("PYTEST_RUNNING", raising=False)
        with caplog.at_level(logging.CRITICAL):
            effective = validate_lifecycle_reminder_boot()
        assert effective == "off"
        assert is_lifecycle_aware_reminder_active() is False
        assert "lifecycle_reminder_boot_guard" in caplog.text

    def test_unknown_mode_treated_as_off(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "bogus")
        assert get_effective_reminder_mode() == "off"

    def test_rollback_to_off_restores_legacy_authority(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        assert get_effective_reminder_mode() == "shadow"
        monkeypatch.setenv("LIFECYCLE_AWARE_REMINDERS", "off")
        assert get_effective_reminder_mode() == "off"
        assert is_lifecycle_aware_reminder_off() is True


class TestCiGovernanceReminderActive:
    def test_production_blueprint_rejects_reminders_active(self):
        errors = check_production_blueprints_lifecycle_active()
        assert errors == []
