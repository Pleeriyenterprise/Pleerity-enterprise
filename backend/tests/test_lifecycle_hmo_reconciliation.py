"""Phase 2 S2 — HMO licensing reconciliation tests."""

from __future__ import annotations

from services.compliance_rules_registry import (
    expects_expiry_for_requirement,
    get_rule,
    work_order_requirement_code_to_registry_key,
)
from services.lifecycle_extraction_profile_resolver import resolve_extraction_profile
from services.lifecycle_semantics_resolver import resolve_lifecycle_semantics
from services.lifecycle_semantics_shadow import build_shadow_payload
from services.published_registry_coverage_patch_specs import (
    _COVERAGE_PATCHES,
    _EXTRACTION_PROFILE_BY_CANONICAL,
)


class TestHMOComplianceRuleSpec:
    def test_hmo_licensing_spec_exists_ew(self):
        spec = get_rule("ENGLAND_WALES", "HMO_LICENSING")
        assert spec is not None
        assert spec.expects_expiry is True
        assert spec.storage_type == "hmo_license"

    def test_hmo_licensing_spec_exists_scotland(self):
        spec = get_rule("SCOTLAND", "HMO_LICENSING")
        assert spec is not None
        assert spec.expects_expiry is True

    def test_expects_expiry_for_hmo_license_aliases(self):
        assert expects_expiry_for_requirement("ENGLAND_WALES", "HMO_LICENSING") is True
        assert expects_expiry_for_requirement("ENGLAND_WALES", "HMO_LICENSE") is True
        assert expects_expiry_for_requirement("ENGLAND_WALES", "HMO_LICENCE") is True


class TestHMOLifecycleResolver:
    def test_hmo_license_resolves_expiry_based(self):
        resolved = resolve_lifecycle_semantics({"requirement_code": "hmo_license"})
        assert resolved.lifecycle_semantics == "EXPIRY_BASED"
        assert resolved.field_contract.requires_expiry_date is True

    def test_hmo_canonical_registry_key(self):
        assert work_order_requirement_code_to_registry_key("hmo_license") == "HMO_LICENSE"


class TestHMOShadowParity:
    def test_no_expects_expiry_conflict_for_hmo(self):
        requirement = {"requirement_id": "req-hmo-1", "requirement_code": "hmo_license"}
        payload = build_shadow_payload(requirement)
        divergence = payload.get("divergence")
        if divergence:
            assert divergence.get("type") != "semantics_mismatch"
        legacy = payload["legacy_authority"]
        assert legacy.get("expects_expiry") is True
        assert payload["lifecycle_semantics"] == "EXPIRY_BASED"


class TestHMORegistryPatch:
    def test_hmo_lifecycle_block_is_expiry_based(self):
        hmo_patch = next(p for p in _COVERAGE_PATCHES if p[0] == "HMO_LICENSING")
        lifecycle = hmo_patch[2].get("lifecycle") or {}
        assert lifecycle.get("semantics") == "EXPIRY_BASED"
        fc = lifecycle.get("field_contract") or {}
        assert fc.get("requires_expiry_date") is True

    def test_hmo_extraction_profile_id_in_canonical_map(self):
        assert _EXTRACTION_PROFILE_BY_CANONICAL["HMO_LICENSING"] == "hmo_licence_v1"

    def test_hmo_profile_resolver_alignment(self):
        registry_row = {
            "lifecycle": {
                "semantics": "EXPIRY_BASED",
                "extraction_profile_id": "hmo_licence_v1",
                "field_contract": {"requires_expiry_date": True, "requires_issue_date": True},
            }
        }
        resolved = resolve_extraction_profile(
            {"requirement_code": "hmo_license"},
            registry_row=registry_row,
        )
        assert resolved.profile_id == "hmo_licence_v1"
        assert resolved.lifecycle_semantics == "EXPIRY_BASED"
