"""Phase 5 P5-S1 — lifecycle-aware KPI flag infrastructure tests."""

from __future__ import annotations

import logging

from scripts.deployment_governance_ci_gate import check_production_blueprints_lifecycle_active
from services.lifecycle_aware_kpis_config import (
    get_effective_kpi_mode,
    get_lifecycle_aware_kpi_mode,
    is_lifecycle_aware_kpi_active,
    is_lifecycle_aware_kpi_off,
    is_lifecycle_aware_kpi_shadow,
    validate_lifecycle_kpi_boot,
)


class TestKpiModeConfig:
    def test_default_off(self, monkeypatch):
        monkeypatch.delenv("LIFECYCLE_AWARE_KPIS", raising=False)
        assert get_effective_kpi_mode() == "off"
        assert get_lifecycle_aware_kpi_mode() == "off"
        assert is_lifecycle_aware_kpi_off() is True

    def test_shadow_on_staging(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        assert get_effective_kpi_mode() == "shadow"
        assert is_lifecycle_aware_kpi_shadow() is True

    def test_preview_active_allowed(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")
        assert get_effective_kpi_mode() == "active"
        assert is_lifecycle_aware_kpi_active() is True

    def test_preview_override_allows_active_on_staging(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS_PREVIEW_OVERRIDE", "1")
        assert get_effective_kpi_mode() == "active"

    def test_production_preview_override_never_active(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "production")
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS_PREVIEW_OVERRIDE", "1")
        assert get_effective_kpi_mode() == "off"
        assert is_lifecycle_aware_kpi_active() is False

    def test_staging_active_downgrades_to_shadow(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        assert get_effective_kpi_mode() == "shadow"
        assert is_lifecycle_aware_kpi_active() is False

    def test_production_active_downgrades_to_off(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "production")
        assert get_effective_kpi_mode() == "off"

    def test_production_boot_guard_never_active(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "production")
        monkeypatch.delenv("PYTEST_RUNNING", raising=False)
        with caplog.at_level(logging.CRITICAL):
            effective = validate_lifecycle_kpi_boot()
        assert effective == "off"
        assert is_lifecycle_aware_kpi_active() is False
        assert "lifecycle_kpi_boot_guard" in caplog.text

    def test_unknown_mode_treated_as_off(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "bogus")
        assert get_effective_kpi_mode() == "off"

    def test_rollback_to_off_restores_legacy_authority(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        assert get_effective_kpi_mode() == "shadow"
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "off")
        assert get_effective_kpi_mode() == "off"
        assert is_lifecycle_aware_kpi_off() is True


class TestCiGovernanceKpiActive:
    def test_production_blueprint_rejects_kpis_active(self):
        errors = check_production_blueprints_lifecycle_active()
        assert errors == []
