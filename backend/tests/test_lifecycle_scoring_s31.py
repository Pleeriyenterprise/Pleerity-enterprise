"""Phase 3 S3.1 — lifecycle-aware scoring flag infrastructure tests."""

from __future__ import annotations

import logging

from scripts.deployment_governance_ci_gate import check_production_blueprints_lifecycle_active
from services.lifecycle_aware_scoring_config import (
    get_effective_scoring_mode,
    is_lifecycle_aware_scoring_active,
    is_lifecycle_aware_scoring_off,
    is_lifecycle_aware_scoring_shadow,
    validate_lifecycle_scoring_boot,
)


class TestScoringModeConfig:
    def test_default_off(self, monkeypatch):
        monkeypatch.delenv("LIFECYCLE_AWARE_SCORING", raising=False)
        assert get_effective_scoring_mode() == "off"
        assert is_lifecycle_aware_scoring_off() is True

    def test_shadow_on_staging(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_SCORING", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        assert get_effective_scoring_mode() == "shadow"
        assert is_lifecycle_aware_scoring_shadow() is True

    def test_preview_active_allowed(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_SCORING", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")
        assert get_effective_scoring_mode() == "active"
        assert is_lifecycle_aware_scoring_active() is True

    def test_preview_override_allows_active(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_SCORING", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        monkeypatch.setenv("LIFECYCLE_AWARE_SCORING_PREVIEW_OVERRIDE", "1")
        assert get_effective_scoring_mode() == "active"

    def test_staging_active_downgrades_to_shadow(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_SCORING", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        assert get_effective_scoring_mode() == "shadow"
        assert is_lifecycle_aware_scoring_active() is False

    def test_production_active_downgrades_to_off(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_SCORING", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "production")
        assert get_effective_scoring_mode() == "off"

    def test_production_boot_guard_never_active(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_SCORING", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "production")
        monkeypatch.delenv("PYTEST_RUNNING", raising=False)
        with caplog.at_level(logging.CRITICAL):
            effective = validate_lifecycle_scoring_boot()
        assert effective == "off"
        assert is_lifecycle_aware_scoring_active() is False
        assert "lifecycle_scoring_boot_guard" in caplog.text

    def test_unknown_mode_treated_as_off(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_SCORING", "bogus")
        assert get_effective_scoring_mode() == "off"


class TestCiGovernanceScoringActive:
    def test_production_blueprint_rejects_scoring_active(self):
        errors = check_production_blueprints_lifecycle_active()
        assert errors == []
