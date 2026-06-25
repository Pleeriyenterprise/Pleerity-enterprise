"""Phase 5 P5-S2 — lifecycle-aware KPI shadow telemetry."""

from __future__ import annotations

import logging

from services.lifecycle_aware_kpis_config import get_effective_kpi_mode
from services.lifecycle_kpi_gates import (
    build_kpi_lifecycle_context,
    compute_lifecycle_kpi_stats,
    lifecycle_kpi_monolithic_expiring_soon_allowed,
)
from services.requirement_client_runtime_surface import compute_client_portal_requirement_stats


class TestLifecycleKpiGatesUnit:
    def test_review_based_excludes_monolithic_expiring_soon(self):
        ctx = build_kpi_lifecycle_context(
            {"requirement_code": "legionella", "status": "EXPIRING_SOON"},
        )
        assert ctx.lifecycle_semantics == "REVIEW_BASED"
        assert lifecycle_kpi_monolithic_expiring_soon_allowed(ctx) is False

    def test_expiry_based_requires_expiry_date_for_monolithic_bucket(self):
        ctx = build_kpi_lifecycle_context(
            {"requirement_code": "gas_safety", "status": "EXPIRING_SOON"},
        )
        assert ctx.lifecycle_semantics == "EXPIRY_BASED"
        assert lifecycle_kpi_monolithic_expiring_soon_allowed(ctx) is True


class TestLifecycleKpiShadow:
    def test_shadow_logs_divergence_for_review_based_expiring_soon(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        rows = [
            {
                "requirement_code": "legionella",
                "status": "EXPIRING_SOON",
                "requirement_satisfied": False,
            }
        ]
        with caplog.at_level(logging.INFO):
            stats = compute_client_portal_requirement_stats(rows)
        assert stats["expiring_soon"] == 1
        assert get_effective_kpi_mode() == "shadow"
        assert "lifecycle_kpi_shadow_complete" in caplog.text
        assert "lifecycle_kpi_shadow_divergence" in caplog.text

    def test_shadow_keeps_legacy_stats_authoritative(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        rows = [
            {
                "requirement_code": "legionella",
                "status": "EXPIRING_SOON",
                "requirement_satisfied": False,
            }
        ]
        stats = compute_client_portal_requirement_stats(rows)
        lifecycle = compute_lifecycle_kpi_stats(rows)
        assert stats["expiring_soon"] == 1
        assert lifecycle["expiring_soon"] == 0
        assert lifecycle["attention_kind_buckets"]["REVIEW_DUE"] == 1

    def test_off_mode_emits_no_shadow_logs(self, monkeypatch, caplog):
        monkeypatch.delenv("LIFECYCLE_AWARE_KPIS", raising=False)
        rows = [
            {
                "requirement_code": "legionella",
                "status": "EXPIRING_SOON",
                "requirement_satisfied": False,
            }
        ]
        with caplog.at_level(logging.INFO):
            stats = compute_client_portal_requirement_stats(rows)
        assert stats["expiring_soon"] == 1
        assert "lifecycle_kpi_shadow_complete" not in caplog.text
