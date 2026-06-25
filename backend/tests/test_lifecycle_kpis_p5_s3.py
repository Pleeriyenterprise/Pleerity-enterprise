"""Phase 5 P5-S3 — lifecycle-aware KPI active authority (preview only)."""

from __future__ import annotations

import logging

import pytest

from services.lifecycle_aware_kpis_config import get_effective_kpi_mode
from services.lifecycle_kpi_gates import (
    attention_kind_for_kpi_bucket,
    build_kpi_lifecycle_context,
    compute_lifecycle_kpi_stats,
    lifecycle_stats_authoritative_payload,
)
from services.requirement_client_runtime_surface import (
    _compute_legacy_portal_requirement_stats,
    compute_client_portal_requirement_stats,
)

_AUTHORITATIVE_KEYS = frozenset(
    {
        "total_requirements",
        "compliant",
        "satisfied",
        "status_valid",
        "pending",
        "missing_evidence",
        "expiring_soon",
        "overdue",
    }
)

_SEMANTIC_BUCKET_CASES = [
    ("gas_safety", "EXPIRY_BASED", "CERTIFICATE_EXPIRING", 1),
    ("legionella", "REVIEW_BASED", "REVIEW_DUE", 0),
    ("smoke_alarms", "EVENT_BASED", "EVENT_ACTION_REQUIRED", 0),
    ("deposit_pi", "DECLARATION_BASED", "EVENT_ACTION_REQUIRED", 0),
    ("tenancy_agreement", "TENANCY_LIFECYCLE", "TENANCY_TERM_ENDING", 0),
    ("right_to_rent", "OCCUPANCY_LIFECYCLE", "OCCUPANCY_REVIEW_DUE", 0),
    ("fitness_for_human_habitation", "OPERATIONAL", "OPERATIONAL_ACTION_REQUIRED", 0),
]


def _expiring_soon_row(requirement_code: str) -> dict:
    return {
        "requirement_code": requirement_code,
        "status": "EXPIRING_SOON",
        "requirement_satisfied": False,
    }


class TestLegacyAuthorityUnchanged:
    def test_off_mode_matches_legacy_helper(self, monkeypatch):
        monkeypatch.delenv("LIFECYCLE_AWARE_KPIS", raising=False)
        rows = [
            {"status": "COMPLIANT"},
            {"status": "VALID"},
            {"status": "PENDING"},
            {"status": "MISSING"},
            {"status": "EXPIRING_SOON", "requirement_code": "gas_safety"},
            {"status": "OVERDUE"},
            {"status": "EXPIRED"},
        ]
        legacy = _compute_legacy_portal_requirement_stats(rows)
        stats = compute_client_portal_requirement_stats(rows)
        assert stats == legacy

    def test_off_mode_no_extra_keys(self, monkeypatch):
        monkeypatch.delenv("LIFECYCLE_AWARE_KPIS", raising=False)
        stats = compute_client_portal_requirement_stats([_expiring_soon_row("legionella")])
        assert set(stats.keys()) == _AUTHORITATIVE_KEYS


class TestShadowAuthorityUnchanged:
    def test_shadow_returns_legacy_not_lifecycle(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        rows = [_expiring_soon_row("legionella")]
        stats = compute_client_portal_requirement_stats(rows)
        lifecycle = compute_lifecycle_kpi_stats(rows)
        assert stats["expiring_soon"] == 1
        assert lifecycle["expiring_soon"] == 0
        assert set(stats.keys()) == _AUTHORITATIVE_KEYS

    def test_shadow_still_logs(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        rows = [_expiring_soon_row("legionella")]
        with caplog.at_level(logging.INFO):
            compute_client_portal_requirement_stats(rows)
        assert "lifecycle_kpi_shadow_complete" in caplog.text


class TestActiveAuthorityPreview:
    def test_preview_active_returns_lifecycle_stats(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")
        rows = [_expiring_soon_row("legionella")]
        stats = compute_client_portal_requirement_stats(rows)
        lifecycle = lifecycle_stats_authoritative_payload(compute_lifecycle_kpi_stats(rows))
        assert get_effective_kpi_mode() == "active"
        assert stats == lifecycle
        assert stats["expiring_soon"] == 0
        assert stats["expiring_soon"] != _compute_legacy_portal_requirement_stats(rows)["expiring_soon"]

    def test_active_payload_shape_unchanged(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")
        stats = compute_client_portal_requirement_stats([_expiring_soon_row("gas_safety")])
        assert set(stats.keys()) == _AUTHORITATIVE_KEYS
        assert "attention_kind_buckets" not in stats

    def test_active_skips_shadow_logs(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")
        with caplog.at_level(logging.INFO):
            compute_client_portal_requirement_stats([_expiring_soon_row("legionella")])
        assert "lifecycle_kpi_shadow_complete" not in caplog.text


class TestActiveTierGuards:
    def test_staging_active_downgrades_to_shadow_legacy_returned(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        rows = [_expiring_soon_row("legionella")]
        stats = compute_client_portal_requirement_stats(rows)
        assert get_effective_kpi_mode() == "shadow"
        assert stats["expiring_soon"] == 1

    def test_production_active_downgrades_to_off_legacy_returned(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "production")
        rows = [_expiring_soon_row("legionella")]
        stats = compute_client_portal_requirement_stats(rows)
        assert get_effective_kpi_mode() == "off"
        assert stats["expiring_soon"] == 1


class TestRollback:
    def test_flag_off_restores_legacy_authority(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")
        rows = [_expiring_soon_row("legionella")]
        active_stats = compute_client_portal_requirement_stats(rows)
        assert active_stats["expiring_soon"] == 0

        monkeypatch.setenv("LIFECYCLE_AWARE_KPIS", "off")
        off_stats = compute_client_portal_requirement_stats(rows)
        assert off_stats["expiring_soon"] == 1
        assert off_stats == _compute_legacy_portal_requirement_stats(rows)


class TestSemanticBucketMapping:
    @pytest.mark.parametrize(
        "requirement_code,expected_semantics,expected_bucket,expected_expiring_soon",
        _SEMANTIC_BUCKET_CASES,
    )
    def test_each_semantic_routes_to_correct_bucket(
        self,
        requirement_code,
        expected_semantics,
        expected_bucket,
        expected_expiring_soon,
    ):
        row = _expiring_soon_row(requirement_code)
        ctx = build_kpi_lifecycle_context(row)
        assert ctx.lifecycle_semantics == expected_semantics
        assert attention_kind_for_kpi_bucket(ctx) == expected_bucket

        stats = compute_lifecycle_kpi_stats([row])
        assert stats["expiring_soon"] == expected_expiring_soon
        assert stats["attention_kind_buckets"][expected_bucket] == 1
        for kind, count in stats["attention_kind_buckets"].items():
            if kind == expected_bucket:
                assert count == 1
            else:
                assert count == 0

    def test_no_certificate_fallback_for_review_based(self):
        ctx = build_kpi_lifecycle_context(_expiring_soon_row("legionella"))
        assert attention_kind_for_kpi_bucket(ctx) == "REVIEW_DUE"
        assert attention_kind_for_kpi_bucket(ctx) != "CERTIFICATE_EXPIRING"

    def test_unsupported_semantics_raises(self):
        from services.lifecycle_kpi_gates import KpiLifecycleContext

        ctx = KpiLifecycleContext(
            requirement_code="bogus",
            lifecycle_semantics="NOT_A_REAL_SEMANTIC",  # type: ignore[arg-type]
            requires_expiry_date=False,
            attention_kind=None,
            resolution_source="test",
        )
        with pytest.raises(ValueError, match="unsupported lifecycle_semantics"):
            attention_kind_for_kpi_bucket(ctx)
