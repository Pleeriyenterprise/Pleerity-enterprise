"""Phase 2 S5-extract — profile-aware extraction tests."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest

from scripts.deployment_governance_ci_gate import check_production_blueprints_lifecycle_active
from services.lifecycle_aware_extraction_config import (
    get_effective_extraction_mode,
    is_lifecycle_aware_extraction_active,
    is_lifecycle_aware_extraction_off,
    validate_lifecycle_extraction_boot,
)
from services.lifecycle_extraction_profile_resolver import resolve_extraction_profile
from services.lifecycle_extraction_profiles import (
    EXTRACTION_PROFILE_IDS,
    get_extraction_profile,
)
from services.lifecycle_profile_extraction import (
    build_profile_system_prompt,
    legacy_extraction_status,
    maybe_run_profile_extraction_observe,
    normalize_profile_extraction,
    observe_extraction_shadow,
    profile_extraction_status,
    resolve_profile_for_extraction,
)


def _req(code: str) -> dict:
    return {"requirement_id": "req-extract", "requirement_code": code}


def _confidence(overall: float = 0.9) -> dict:
    return {"overall": overall, "dates": overall, "fields": overall}


PROFILE_EXTRACTED_RULES = [
    ("certificate_standard_v1", "expiry_date", {"expiry_date": "2027-01-01"}),
    ("hmo_licence_v1", "expiry_date", {"expiry_date": "2027-06-01"}),
    ("tenancy_agreement_v1", "tenancy_start_date", {"tenancy_start_date": "2025-01-01"}),
    ("deposit_protection_v1", "protection_date", {"protection_date": "2025-03-01"}),
    ("prescribed_information_v1", "served_date", {"served_date": "2025-02-01"}),
    ("right_to_rent_v1", "check_date", {"check_date": "2025-04-01"}),
    ("legionella_review_v1", "assessment_date", {"assessment_date": "2025-05-01"}),
    ("landlord_registration_v1", "registration_number", {"registration_number": "REG-1"}),
    ("event_completion_v1", "event_date", {"event_date": "2025-06-01"}),
    ("operational_workflow_v1", "completion_date", {"completion_date": "2025-07-01"}),
    ("supporting_document_v1", "document_date", {"document_date": "2025-08-01"}),
]


class TestExtractionModeConfig:
    def test_default_off(self, monkeypatch):
        monkeypatch.delenv("LIFECYCLE_AWARE_EXTRACTION", raising=False)
        assert get_effective_extraction_mode() == "off"
        assert is_lifecycle_aware_extraction_off() is True

    def test_shadow_on_staging(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_EXTRACTION", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        assert get_effective_extraction_mode() == "shadow"

    def test_preview_active_allowed(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_EXTRACTION", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "preview")
        assert get_effective_extraction_mode() == "active"
        assert is_lifecycle_aware_extraction_active() is True

    def test_staging_active_downgrades_to_shadow(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_EXTRACTION", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        assert get_effective_extraction_mode() == "shadow"
        assert is_lifecycle_aware_extraction_active() is False

    def test_production_active_downgrades_to_off(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_EXTRACTION", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "production")
        assert get_effective_extraction_mode() == "off"

    def test_production_boot_guard_never_active(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_EXTRACTION", "active")
        monkeypatch.setenv("DEPLOYMENT_TIER", "production")
        monkeypatch.delenv("PYTEST_RUNNING", raising=False)
        with caplog.at_level(logging.CRITICAL):
            effective = validate_lifecycle_extraction_boot()
        assert effective == "off"
        assert is_lifecycle_aware_extraction_active() is False
        assert "lifecycle_extract_boot_guard" in caplog.text


class TestCiGovernanceExtractionActive:
    def test_production_blueprint_rejects_extraction_active(self):
        errors = check_production_blueprints_lifecycle_active()
        assert errors == []


class TestProfileCoverage:
    def test_all_profiles_have_prompt_and_rules(self):
        assert len(EXTRACTION_PROFILE_IDS) == 11
        for profile_id in sorted(EXTRACTION_PROFILE_IDS):
            profile = get_extraction_profile(profile_id)
            assert profile is not None
            prompt = build_profile_system_prompt(profile)
            assert profile.profile_id in prompt
            for field in profile.required_fields:
                assert field in prompt


class TestProfileSelection:
    def test_gas_safety_certificate_profile(self):
        resolved = resolve_profile_for_extraction(_req("gas_safety"))
        assert resolved.profile_id == "certificate_standard_v1"

    def test_registry_precedence(self):
        registry_row = {
            "lifecycle": {
                "semantics": "EXPIRY_BASED",
                "extraction_profile_id": "hmo_licence_v1",
            }
        }
        resolved = resolve_profile_for_extraction(
            _req("gas_safety"),
            registry_row=registry_row,
        )
        assert resolved.profile_id == "hmo_licence_v1"
        assert resolved.resolution_source == "registry"

    def test_deposit_pi_routes_to_protection(self):
        resolved = resolve_profile_for_extraction(_req("deposit_pi"))
        assert resolved.profile_id == "deposit_protection_v1"

    def test_document_context_pi_override(self):
        resolved = resolve_extraction_profile(
            _req("deposit_pi"),
            document={"document_type": "how_to_rent"},
        )
        assert resolved.profile_id == "prescribed_information_v1"
        assert resolved.resolution_source == "document_context"

    def test_semantics_fallback_supporting_document(self):
        resolved = resolve_profile_for_extraction(_req("unknown_future_type_xyz"))
        assert resolved.profile_id in ("legionella_review_v1", "supporting_document_v1")


class TestExtractedCompletionRules:
    def test_legacy_requires_expiry_date(self):
        assert legacy_extraction_status({"confidence": _confidence(0.9)}) == "NEEDS_REVIEW"
        assert (
            legacy_extraction_status(
                {"confidence": _confidence(0.9), "expiry_date": "2027-01-01"}
            )
            == "EXTRACTED"
        )
        assert (
            legacy_extraction_status(
                {"confidence": _confidence(0.5), "expiry_date": "2027-01-01"}
            )
            == "NEEDS_REVIEW"
        )

    @pytest.mark.parametrize("profile_id,required_field,fields", PROFILE_EXTRACTED_RULES)
    def test_profile_extracted_when_required_present(
        self, profile_id, required_field, fields
    ):
        profile = get_extraction_profile(profile_id)
        assert profile is not None
        extracted = {**fields, "confidence": _confidence(0.9)}
        assert profile_extraction_status(profile, extracted) == "EXTRACTED"

    @pytest.mark.parametrize("profile_id,required_field,fields", PROFILE_EXTRACTED_RULES)
    def test_profile_needs_review_without_required(
        self, profile_id, required_field, fields
    ):
        profile = get_extraction_profile(profile_id)
        assert profile is not None
        incomplete = {k: v for k, v in fields.items() if k != required_field}
        incomplete["confidence"] = _confidence(0.9)
        assert profile_extraction_status(profile, incomplete) == "NEEDS_REVIEW"

    def test_legionella_does_not_need_expiry_date(self):
        profile = get_extraction_profile("legionella_review_v1")
        assert profile is not None
        extracted = {
            "assessment_date": "2025-01-01",
            "confidence": _confidence(0.9),
        }
        assert profile_extraction_status(profile, extracted) == "EXTRACTED"
        assert legacy_extraction_status(extracted) == "NEEDS_REVIEW"

    def test_forbidden_field_blocks_extracted(self):
        profile = get_extraction_profile("tenancy_agreement_v1")
        assert profile is not None
        extracted = {
            "tenancy_start_date": "2025-01-01",
            "expiry_date": "2027-01-01",
            "confidence": _confidence(0.9),
        }
        assert profile_extraction_status(profile, extracted) == "NEEDS_REVIEW"


class TestNormalizeProfileExtraction:
    def test_date_normalization(self):
        profile = get_extraction_profile("deposit_protection_v1")
        assert profile is not None
        out = normalize_profile_extraction(
            {"protection_date": "2025-03-15T00:00:00", "confidence": _confidence()},
            profile,
        )
        assert out["protection_date"] == "2025-03-15"


class TestShadowObservation:
    def test_off_mode_skips_shadow_logs(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_EXTRACTION", "off")
        profile = get_extraction_profile("legionella_review_v1")
        resolved = resolve_profile_for_extraction(_req("legionella"))
        assert profile is not None
        with caplog.at_level(logging.INFO):
            observe_extraction_shadow(
                legacy_extracted={"confidence": _confidence(0.5)},
                profile_extracted={"assessment_date": "2025-01-01", "confidence": _confidence(0.9)},
                profile=profile,
                resolved=resolved,
            )
        assert "lifecycle_extract_shadow_complete" not in caplog.text

    def test_shadow_logs_complete_and_divergence(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_EXTRACTION", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        profile = get_extraction_profile("legionella_review_v1")
        resolved = resolve_profile_for_extraction(_req("legionella"))
        assert profile is not None
        legacy = {"confidence": _confidence(0.9)}
        profile_data = {"assessment_date": "2025-01-01", "confidence": _confidence(0.9)}
        with caplog.at_level(logging.INFO):
            observe_extraction_shadow(
                legacy_extracted=legacy,
                profile_extracted=profile_data,
                profile=profile,
                resolved=resolved,
                document_id="doc-1",
            )
        assert "lifecycle_extract_shadow_complete" in caplog.text
        assert "lifecycle_extract_shadow_status_divergence" in caplog.text

    def test_shadow_logs_profile_selected(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_EXTRACTION", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        from services.lifecycle_profile_extraction import log_profile_selected

        resolved = resolve_profile_for_extraction(_req("legionella"))
        with caplog.at_level(logging.INFO):
            log_profile_selected(resolved, document_id="doc-2")
        assert "lifecycle_extract_profile_selected" in caplog.text

    @pytest.mark.asyncio
    async def test_maybe_run_off_returns_none(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_EXTRACTION", "off")
        profile_extracted, resolved = await maybe_run_profile_extraction_observe(
            "text",
            "file.pdf",
            legacy_extracted={"confidence": _confidence()},
        )
        assert profile_extracted is None
        assert resolved is None

    @pytest.mark.asyncio
    async def test_maybe_run_shadow_invokes_profile_llm(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_EXTRACTION", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        mock_extract = AsyncMock(
            return_value={
                "success": True,
                "extracted": {
                    "assessment_date": "2025-01-01",
                    "confidence": _confidence(0.9),
                },
            }
        )
        with patch(
            "services.ai_provider.extract_profile_aware_fields_async",
            mock_extract,
        ):
            profile_extracted, resolved = await maybe_run_profile_extraction_observe(
                "legionella assessment 2025-01-01",
                "legionella.pdf",
                legacy_extracted={"confidence": _confidence(0.9)},
                requirement=_req("legionella"),
            )
        assert resolved is not None
        assert resolved.profile_id == "legionella_review_v1"
        assert profile_extracted is not None
        mock_extract.assert_awaited_once()


class TestLegacyCompatibility:
    def test_off_mode_legacy_status_unchanged(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_EXTRACTION", "off")
        legacy = {"confidence": _confidence(0.9), "expiry_date": "2027-01-01"}
        assert legacy_extraction_status(legacy) == "EXTRACTED"

    def test_shadow_mode_legacy_authoritative(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_EXTRACTION", "shadow")
        monkeypatch.setenv("DEPLOYMENT_TIER", "staging")
        legacy = {"confidence": _confidence(0.9), "expiry_date": "2027-01-01"}
        profile = get_extraction_profile("legionella_review_v1")
        assert profile is not None
        profile_data = {"assessment_date": "2025-01-01", "confidence": _confidence(0.9)}
        assert legacy_extraction_status(legacy) == "EXTRACTED"
        assert profile_extraction_status(profile, profile_data) == "EXTRACTED"
        assert get_effective_extraction_mode() == "shadow"
