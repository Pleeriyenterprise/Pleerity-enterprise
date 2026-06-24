"""Phase 2 S3 — lifecycle confirm contract tests."""

from __future__ import annotations

import pytest

from services.lifecycle_aware_confirm_config import get_lifecycle_aware_confirm_mode
from services.lifecycle_confirm_contract import (
    build_contract_for_requirement,
    maybe_attach_lifecycle_confirm_contract,
    observe_confirm_payload_shadow,
)
from services.lifecycle_extraction_profiles import EXTRACTION_PROFILE_IDS


class TestLifecycleAwareConfirmConfig:
    def test_default_mode_is_off(self, monkeypatch):
        monkeypatch.delenv("LIFECYCLE_AWARE_CONFIRM", raising=False)
        assert get_lifecycle_aware_confirm_mode() == "off"

    def test_active_mode_prohibited(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "active")
        assert get_lifecycle_aware_confirm_mode() == "off"

    def test_shadow_mode(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "shadow")
        assert get_lifecycle_aware_confirm_mode() == "shadow"


class TestConfirmContractShape:
    @pytest.mark.parametrize(
        "requirement_code,expected_semantics,expected_profile",
        [
            ("gas_safety", "EXPIRY_BASED", "certificate_standard_v1"),
            ("hmo_license", "EXPIRY_BASED", "hmo_licence_v1"),
            ("tenancy_agreement", "TENANCY_LIFECYCLE", "tenancy_agreement_v1"),
            ("deposit_pi", "DECLARATION_BASED", "deposit_protection_v1"),
            ("how_to_rent", "DECLARATION_BASED", "prescribed_information_v1"),
            ("right_to_rent", "OCCUPANCY_LIFECYCLE", "right_to_rent_v1"),
            ("legionella", "REVIEW_BASED", "legionella_review_v1"),
            ("landlord_registration", "REVIEW_BASED", "landlord_registration_v1"),
            ("smoke_heat_alarms", "EVENT_BASED", "event_completion_v1"),
            ("fitness_for_human_habitation", "OPERATIONAL", "operational_workflow_v1"),
        ],
    )
    def test_contract_per_lifecycle_type(
        self, requirement_code, expected_semantics, expected_profile
    ):
        contract = build_contract_for_requirement({"requirement_code": requirement_code})
        assert contract["lifecycle_semantics"] == expected_semantics
        assert contract["extraction_profile_id"] == expected_profile
        assert isinstance(contract["confirm_fields"], list)
        assert len(contract["confirm_fields"]) >= 1
        assert isinstance(contract["optional_fields"], list)
        assert isinstance(contract["forbidden_fields"], list)
        assert isinstance(contract["validation_rules"], list)
        assert len(contract["validation_rules"]) >= 1
        assert contract["contract_version"] == "1.0.0-phase2"
        assert contract["resolver_version"] == "1.0.0-phase1"

    def test_non_expiry_forbids_expiry_in_contract(self):
        contract = build_contract_for_requirement({"requirement_code": "tenancy_agreement"})
        assert "expiry_date" in contract["forbidden_fields"]
        assert "confirmed_expiry_date" in contract["forbidden_fields"]

    def test_expiry_based_allows_expiry(self):
        contract = build_contract_for_requirement({"requirement_code": "gas_safety"})
        assert "expiry_date" in contract["confirm_fields"]
        assert "expiry_date" not in contract["forbidden_fields"]


class TestConfirmContractAttachment:
    def test_off_mode_unchanged(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "off")
        payload = {"has_extraction": True}
        out = maybe_attach_lifecycle_confirm_contract(
            payload,
            requirement={"requirement_code": "gas_safety"},
            surface="test",
        )
        assert out == payload
        assert "lifecycle_confirm_contract" not in out

    def test_shadow_mode_attaches_contract(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "shadow")
        payload = {"has_extraction": True}
        out = maybe_attach_lifecycle_confirm_contract(
            payload,
            requirement={"requirement_code": "hmo_license"},
            surface="test",
        )
        assert "lifecycle_confirm_contract" in out
        contract = out["lifecycle_confirm_contract"]
        assert contract["extraction_profile_id"] == "hmo_licence_v1"


class TestObserveOnlyValidation:
    def test_observe_does_not_mutate_payload(self, monkeypatch, caplog):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "shadow")
        contract = build_contract_for_requirement({"requirement_code": "tenancy_agreement"})
        payload = {"expiry_date": "2027-01-01"}
        observe_confirm_payload_shadow(payload, contract, surface="apply_extraction")
        assert payload["expiry_date"] == "2027-01-01"

    def test_off_mode_skips_observe(self, monkeypatch):
        monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "off")
        contract = build_contract_for_requirement({"requirement_code": "gas_safety"})
        observe_confirm_payload_shadow({"expiry_date": "2027-01-01"}, contract, surface="test")


class TestProfileCoverageForSemantics:
    @pytest.mark.parametrize(
        "requirement_code,expected_semantics",
        [
            ("gas_safety", "EXPIRY_BASED"),
            ("legionella", "REVIEW_BASED"),
            ("smoke_heat_alarms", "EVENT_BASED"),
            ("deposit_pi", "DECLARATION_BASED"),
            ("tenancy_agreement", "TENANCY_LIFECYCLE"),
            ("right_to_rent", "OCCUPANCY_LIFECYCLE"),
            ("fitness_for_human_habitation", "OPERATIONAL"),
        ],
    )
    def test_all_semantics_have_contract_path(self, requirement_code, expected_semantics):
        contract = build_contract_for_requirement({"requirement_code": requirement_code})
        assert contract["lifecycle_semantics"] == expected_semantics
        assert contract["extraction_profile_id"] in EXTRACTION_PROFILE_IDS
