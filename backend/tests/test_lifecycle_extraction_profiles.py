"""Phase 2 S1 — extraction profile registry tests."""

from __future__ import annotations

import pytest

from services.lifecycle_extraction_profiles import (
    EXTRACTION_PROFILE_IDS,
    PROFILE_BY_SEMANTICS,
    PROFILE_BY_STORAGE_SLUG,
    get_extraction_profile,
    list_extraction_profiles,
    profile_for_storage_slug,
)
from services.lifecycle_extraction_profile_resolver import resolve_extraction_profile


EXPECTED_PROFILES = frozenset(
    {
        "certificate_standard_v1",
        "hmo_licence_v1",
        "tenancy_agreement_v1",
        "deposit_protection_v1",
        "prescribed_information_v1",
        "right_to_rent_v1",
        "legionella_review_v1",
        "landlord_registration_v1",
        "event_completion_v1",
        "operational_workflow_v1",
        "supporting_document_v1",
    }
)


class TestProfileRegistryCoverage:
    def test_all_profiles_registered(self):
        assert EXTRACTION_PROFILE_IDS == EXPECTED_PROFILES
        assert len(list_extraction_profiles()) == 11

    @pytest.mark.parametrize("profile_id", sorted(EXPECTED_PROFILES))
    def test_profile_has_field_contracts(self, profile_id):
        profile = get_extraction_profile(profile_id)
        assert profile is not None
        assert profile.lifecycle_semantics
        assert isinstance(profile.required_fields, tuple)
        assert isinstance(profile.optional_fields, tuple)
        assert isinstance(profile.forbidden_fields, tuple)
        assert len(profile.extracted_fields) >= 1
        assert len(profile.required_fields) >= 1


class TestProfileStorageSlugMapping:
    @pytest.mark.parametrize(
        "slug,expected_profile",
        [
            ("gas_safety", "certificate_standard_v1"),
            ("hmo_license", "hmo_licence_v1"),
            ("tenancy_agreement", "tenancy_agreement_v1"),
            ("deposit_pi", "deposit_protection_v1"),
            ("how_to_rent", "prescribed_information_v1"),
            ("right_to_rent", "right_to_rent_v1"),
            ("legionella", "legionella_review_v1"),
            ("landlord_registration", "landlord_registration_v1"),
            ("smoke_heat_alarms", "event_completion_v1"),
            ("fitness_for_human_habitation", "operational_workflow_v1"),
        ],
    )
    def test_slug_maps_to_profile(self, slug, expected_profile):
        assert profile_for_storage_slug(slug) == expected_profile
        assert PROFILE_BY_STORAGE_SLUG[slug] == expected_profile


class TestProfileResolver:
    def test_registry_extraction_profile_id_takes_precedence(self):
        registry_row = {
            "lifecycle": {
                "semantics": "EXPIRY_BASED",
                "extraction_profile_id": "hmo_licence_v1",
                "field_contract": {"requires_expiry_date": True},
            }
        }
        resolved = resolve_extraction_profile(
            {"requirement_code": "gas_safety"},
            registry_row=registry_row,
        )
        assert resolved.profile_id == "hmo_licence_v1"
        assert resolved.resolution_source == "registry"

    def test_slug_fallback_when_no_registry_profile(self):
        resolved = resolve_extraction_profile({"requirement_code": "hmo_license"})
        assert resolved.profile_id == "hmo_licence_v1"
        assert resolved.lifecycle_semantics == "EXPIRY_BASED"

    def test_semantics_default_when_unknown_slug(self):
        resolved = resolve_extraction_profile({"requirement_code": "unknown_future_type"})
        assert resolved.profile_id == PROFILE_BY_SEMANTICS["REVIEW_BASED"]

    def test_non_expiry_forbids_expiry_fields(self):
        resolved = resolve_extraction_profile({"requirement_code": "tenancy_agreement"})
        profile = resolved.profile
        assert profile.lifecycle_semantics == "TENANCY_LIFECYCLE"
        assert "expiry_date" in profile.forbidden_fields
