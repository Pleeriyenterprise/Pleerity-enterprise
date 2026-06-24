"""Phase 1 lifecycle semantics resolver tests."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from services.lifecycle_semantics_config import get_lifecycle_semantics_mode
from services.lifecycle_semantics_resolver import resolve_lifecycle_semantics
from services.lifecycle_semantics_shadow import (
    build_shadow_payload,
    observe_lifecycle_semantics_shadow_if_enabled,
    reset_shadow_counters,
    shadow_divergence_count,
)
from services.lifecycle_semantics_validation import (
    build_classification_report_for_codes,
    documented_fallback_coverage_report,
    validate_registry_row_lifecycle_block,
)
from services.lifecycle_semantics_registry_loader import lifecycle_block_for_registry
from services.lifecycle_semantics_types import FieldContract
from services.requirement_client_runtime_surface import project_requirement_row_client_runtime


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "lifecycle_semantics_golden.json"


def _load_golden():
    with FIXTURES.open(encoding="utf-8") as f:
        return json.load(f)


class TestLifecycleSemanticsConfig:
    def test_active_mode_treated_as_disabled(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_SEMANTICS_MODE", "active")
        assert get_lifecycle_semantics_mode() == "disabled"

    def test_shadow_mode(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_SEMANTICS_MODE", "shadow")
        assert get_lifecycle_semantics_mode() == "shadow"


class TestResolverGoldenMappings:
    @pytest.mark.parametrize(
        "slug,expected_semantics,requires_expiry",
        [
            ("gas_safety", "EXPIRY_BASED", True),
            ("eicr", "EXPIRY_BASED", True),
            ("epc", "EXPIRY_BASED", True),
            ("hmo_license", "EXPIRY_BASED", True),
            ("legionella", "REVIEW_BASED", False),
            ("deposit_pi", "DECLARATION_BASED", False),
            ("right_to_rent", "OCCUPANCY_LIFECYCLE", False),
            ("tenancy_agreement", "TENANCY_LIFECYCLE", False),
            ("smoke_heat_alarms", "EVENT_BASED", False),
            ("fitness_for_human_habitation", "OPERATIONAL", False),
        ],
    )
    def test_fallback_map(self, slug, expected_semantics, requires_expiry):
        resolved = resolve_lifecycle_semantics({"requirement_code": slug})
        assert resolved.lifecycle_semantics == expected_semantics
        assert resolved.field_contract.requires_expiry_date is requires_expiry

    def test_golden_fixture_alignment(self):
        golden = _load_golden()
        for slug, expected in golden.items():
            resolved = resolve_lifecycle_semantics({"requirement_code": slug})
            assert resolved.lifecycle_semantics == expected["lifecycle_semantics"]
            assert (
                resolved.field_contract.requires_expiry_date
                is expected["requires_expiry_date"]
            )


class TestRegistryLifecycleBlock:
    def test_registry_row_takes_precedence(self):
        registry_row = {
            "lifecycle": lifecycle_block_for_registry(
                "REVIEW_BASED",
                FieldContract(requires_review_date=True, does_not_expire=True),
                vocabulary_family="compliance_review",
            )
        }
        resolved = resolve_lifecycle_semantics(
            {"requirement_code": "gas_safety"},
            registry_row=registry_row,
        )
        assert resolved.lifecycle_semantics == "REVIEW_BASED"
        assert resolved.resolution_source == "registry"

    def test_validate_registry_lifecycle_block(self):
        assert not validate_registry_row_lifecycle_block({})
        errs = validate_registry_row_lifecycle_block(
            {"lifecycle": {"semantics": "NOT_A_REAL_SEMANTICS"}}
        )
        assert any("unsupported" in e for e in errs)


class TestAttentionKindInformational:
    def test_certificate_expiring_when_near_expiry(self):
        soon = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
        resolved = resolve_lifecycle_semantics(
            {
                "requirement_code": "gas_safety",
                "confirmed_expiry_date": soon,
            }
        )
        assert resolved.attention_kind == "CERTIFICATE_EXPIRING"

    def test_tenancy_term_ending(self):
        soon = (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat()
        resolved = resolve_lifecycle_semantics(
            {
                "requirement_code": "tenancy_agreement",
                "structured_declaration": {"fixed_term_end_date": soon},
            }
        )
        assert resolved.attention_kind == "TENANCY_TERM_ENDING"


class TestShadowMode:
    def test_shadow_does_not_mutate_projected_row(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_SEMANTICS_MODE", "shadow")
        reset_shadow_counters()
        req = {
            "requirement_code": "gas_safety",
            "status": "PENDING",
            "confirmed_expiry_date": "2030-01-01T00:00:00+00:00",
        }
        before_keys = set(req.keys())
        out = project_requirement_row_client_runtime(req)
        assert "_lifecycle_semantics_shadow" not in out
        assert set(req.keys()) == before_keys
        payload = build_shadow_payload(req)
        assert payload["lifecycle_semantics"] == "EXPIRY_BASED"
        observe_lifecycle_semantics_shadow_if_enabled(req)

    def test_disabled_mode_no_shadow_side_effects(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_SEMANTICS_MODE", "disabled")
        reset_shadow_counters()
        observe_lifecycle_semantics_shadow_if_enabled({"requirement_code": "eicr"})
        assert shadow_divergence_count() == 0


class TestClassificationReports:
    def test_coverage_report_for_staging_codes(self):
        codes = [
            "gas_safety",
            "eicr",
            "epc",
            "hmo_license",
            "legionella",
            "deposit_pi",
            "right_to_rent",
            "tenancy_agreement",
            "smoke_heat_alarms",
            "fitness_for_human_habitation",
        ]
        report = build_classification_report_for_codes(codes)
        assert report.total == len(codes)
        assert len(report.unresolved) == 0
        assert report.by_semantics.get("EXPIRY_BASED", 0) >= 4

    def test_documented_fallback_coverage(self):
        doc = documented_fallback_coverage_report()
        assert doc["documented_canonical_codes"] >= 10
        assert doc["missing_canonical_resolution"] == []


class TestBackwardCompatibility:
    def test_project_requirement_row_unchanged_without_shadow(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_SEMANTICS_MODE", "disabled")
        req = {
            "requirement_code": "gas_safety",
            "status": "VALID",
            "confirmed_expiry_date": "2030-06-01T00:00:00+00:00",
        }
        out = project_requirement_row_client_runtime(req)
        assert out["status"] == "VALID"
        assert out["due_date"] is not None

    @patch("services.lifecycle_semantics_shadow.observe_lifecycle_semantics_shadow_if_enabled")
    def test_shadow_hook_does_not_change_output(self, mock_observe):
        req = {"requirement_code": "epc", "status": "PENDING"}
        out = project_requirement_row_client_runtime(req)
        mock_observe.assert_called_once()
        assert out["requirement_code"] == "epc"
