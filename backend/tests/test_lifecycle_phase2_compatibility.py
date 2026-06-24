"""Phase 2 S1–S3 compatibility tests — no behaviour change when flags off."""

from __future__ import annotations

import pytest

from services.compliance_rules_registry import expects_expiry_for_requirement
from services.lifecycle_confirm_contract import maybe_attach_lifecycle_confirm_contract
from services.lifecycle_semantics_config import get_lifecycle_semantics_mode
from services.lifecycle_semantics_resolver import resolve_lifecycle_semantics
from services.lifecycle_semantics_shadow import build_shadow_payload


@pytest.fixture(autouse=True)
def _flags_off(monkeypatch):
    monkeypatch.setenv("LIFECYCLE_AWARE_CONFIRM", "off")
    monkeypatch.setenv("LIFECYCLE_SEMANTICS_MODE", "disabled")


class TestBaselineCompatibility:
    def test_lifecycle_semantics_mode_default_disabled(self):
        assert get_lifecycle_semantics_mode() == "disabled"

    def test_confirm_contract_not_attached_when_off(self):
        payload = {"requirement_id": "r1", "policy": {}}
        out = maybe_attach_lifecycle_confirm_contract(
            payload,
            requirement={"requirement_code": "gas_safety"},
            surface="evidence_resolution",
        )
        assert out is payload or out == payload
        assert "lifecycle_confirm_contract" not in out

    def test_existing_resolver_mappings_unchanged(self):
        for slug in ("gas_safety", "eicr", "epc", "hmo_license", "legionella"):
            resolved = resolve_lifecycle_semantics({"requirement_code": slug})
            assert resolved.lifecycle_semantics
            assert resolved.resolution_source in (
                "registry",
                "governance_fallback",
                "legacy_map",
                "default",
            )

    def test_hmo_expects_expiry_aligned_without_changing_scoring_surface(self):
        assert expects_expiry_for_requirement("ENGLAND_WALES", "HMO_LICENSING") is True
        shadow = build_shadow_payload({"requirement_code": "hmo_license"})
        assert shadow["lifecycle_semantics"] == "EXPIRY_BASED"
        legacy = shadow["legacy_authority"]
        assert legacy.get("expects_expiry") is True
