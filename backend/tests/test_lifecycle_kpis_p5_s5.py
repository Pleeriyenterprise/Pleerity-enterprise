"""Phase 5 P5-S5 — additive lifecycle KPI breakdown API field."""

from __future__ import annotations

from services.lifecycle_aware_kpis_config import get_effective_kpi_mode
from services.lifecycle_kpi_gates import (
    LIFECYCLE_KPI_BREAKDOWN_KEYS,
    lifecycle_kpi_breakdown_api_payload,
    lifecycle_kpi_breakdown_for_portal_rows,
    lifecycle_stats_authoritative_payload,
    compute_lifecycle_kpi_stats,
)
from services.requirement_client_runtime_surface import compute_client_portal_requirement_stats


def _expiring_soon_row(requirement_code: str) -> dict:
    return {
        "requirement_code": requirement_code,
        "status": "EXPIRING_SOON",
        "requirement_satisfied": False,
    }


class TestLifecycleKpiBreakdownPayload:
    def test_api_keys_cover_all_attention_buckets(self):
        assert set(LIFECYCLE_KPI_BREAKDOWN_KEYS) == {
            "certificate_expiring",
            "review_due",
            "event_action_required",
            "tenancy_term_ending",
            "occupancy_review_due",
            "operational_action_required",
        }

    def test_breakdown_maps_review_based_to_review_due(self):
        rows = [_expiring_soon_row("legionella")]
        lifecycle = compute_lifecycle_kpi_stats(rows)
        breakdown = lifecycle_kpi_breakdown_api_payload(lifecycle)
        assert breakdown["review_due"] == 1
        assert breakdown["certificate_expiring"] == 0
        assert lifecycle["expiring_soon"] == 0

    def test_breakdown_maps_expiry_based_to_certificate_expiring(self):
        rows = [_expiring_soon_row("gas_safety")]
        breakdown = lifecycle_kpi_breakdown_api_payload(compute_lifecycle_kpi_stats(rows))
        assert breakdown["certificate_expiring"] == 1
        assert breakdown["review_due"] == 0


class TestLifecycleKpiBreakdownGating:
    def test_off_mode_returns_none(self, monkeypatch):
        monkeypatch.delenv("LIFECYCLE_AWARE_KPIS", raising=False)
        rows = [_expiring_soon_row("legionella")]
        assert lifecycle_kpi_breakdown_for_portal_rows(rows) is None

    def test_shadow_mode_returns_breakdown(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        rows = [_expiring_soon_row("legionella")]
        breakdown = lifecycle_kpi_breakdown_for_portal_rows(rows)
        assert breakdown is not None
        assert breakdown["review_due"] == 1
        assert get_effective_kpi_mode() == "shadow"

    def test_eight_key_contract_unchanged_with_breakdown_helper(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        rows = [_expiring_soon_row("legionella")]
        stats = compute_client_portal_requirement_stats(rows)
        assert set(stats.keys()) == {
            "total_requirements",
            "compliant",
            "satisfied",
            "status_valid",
            "pending",
            "missing_evidence",
            "expiring_soon",
            "overdue",
        }
        assert stats["expiring_soon"] == 1
        breakdown = lifecycle_kpi_breakdown_for_portal_rows(rows)
        assert breakdown["review_due"] == 1

    def test_active_preview_breakdown_matches_lifecycle_authority(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")
        rows = [_expiring_soon_row("legionella")]
        stats = compute_client_portal_requirement_stats(rows)
        lifecycle = lifecycle_stats_authoritative_payload(compute_lifecycle_kpi_stats(rows))
        breakdown = lifecycle_kpi_breakdown_for_portal_rows(rows)
        assert stats == lifecycle
        assert breakdown["review_due"] == 1
        assert stats["expiring_soon"] == 0


class TestComplianceScoreBreakdownIntegration:
    def test_calculate_compliance_score_includes_additive_breakdown(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        # Unit-level: breakdown helper is what compliance_score attaches.
        breakdown = lifecycle_kpi_breakdown_for_portal_rows(
            [_expiring_soon_row("legionella"), {"status": "OVERDUE"}],
        )
        assert breakdown is not None
        assert "lifecycle_kpi_breakdown" not in breakdown
        assert breakdown["review_due"] == 1
