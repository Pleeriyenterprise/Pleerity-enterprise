"""Published registry coverage patches resolve core types under strict resolver rules."""
from __future__ import annotations

import copy

from services.compliance_registry_admin_service import validate_registry_draft
from services.compliance_requirement_registry import resolve_published_entry_for_requirement
from services.published_registry_coverage_patch_specs import merge_coverage_into_published_entries


def _prop(jurisdiction: str, **kwargs):
    p = {
        "jurisdiction": jurisdiction,
        "property_type": "residential",
        "is_hmo": False,
        "has_gas_supply": True,
        "tenancy_active": True,
        "deposit_taken": True,
        "furnished": False,
    }
    p.update(kwargs)
    return p


def test_coverage_merged_snapshot_validates_and_resolves_core_slugs():
    merged, _log = merge_coverage_into_published_entries({})
    assert len(merged) >= 10
    for key, ent in merged.items():
        errs = validate_registry_draft(copy.deepcopy(ent))
        assert not errs, (key, errs)

    assert resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="eicr",
        portfolio_label="England",
        property_doc=_prop("England"),
        enforce_conditions=True,
    )
    assert resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="gas_safety",
        portfolio_label="Northern Ireland",
        property_doc=_prop("Northern Ireland"),
        enforce_conditions=True,
    )
    assert resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="right_to_rent",
        portfolio_label="England",
        property_doc=_prop("England"),
        enforce_conditions=True,
    )
    assert (
        resolve_published_entry_for_requirement(
            published_registry_entries=merged,
            requirement_type="right_to_rent",
            portfolio_label="Scotland",
            property_doc=_prop("Scotland"),
            enforce_conditions=True,
        )
        is None
    )
    assert resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="scotland_landlord_registration",
        portfolio_label="Scotland",
        property_doc=_prop("Scotland"),
        enforce_conditions=True,
    )
    assert resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="landlord_registration_ni",
        portfolio_label="Northern Ireland",
        property_doc=_prop("Northern Ireland"),
        enforce_conditions=True,
    )
    assert resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="occupation_contract",
        portfolio_label="Wales",
        property_doc=_prop("Wales"),
        enforce_conditions=True,
    )
    assert resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="wales_occupation_contract",
        portfolio_label="Wales",
        property_doc=_prop("Wales"),
        enforce_conditions=True,
    )
    assert resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="tenancy_agreement",
        portfolio_label="Wales",
        property_doc=_prop("Wales"),
        enforce_conditions=True,
    )
    assert resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="how_to_rent",
        portfolio_label="England",
        property_doc=_prop("England"),
        enforce_conditions=True,
    )
    assert resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="deposit_pi",
        portfolio_label="England",
        property_doc=_prop("England", deposit_taken=True),
        enforce_conditions=True,
    )
    assert resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="deposit_pi",
        portfolio_label="Scotland",
        property_doc=_prop("Scotland", deposit_taken=True),
        enforce_conditions=True,
    )
    w_dep = resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="deposit_pi",
        portfolio_label="Wales",
        property_doc=_prop("Wales", deposit_taken=True),
        enforce_conditions=True,
    )
    assert w_dep and str(w_dep.get("scope_key")).upper() == "WALES"
    ni_dep = resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="deposit_pi",
        portfolio_label="Northern Ireland",
        property_doc=_prop("Northern Ireland", deposit_taken=True),
        enforce_conditions=True,
    )
    assert ni_dep and str(ni_dep.get("scope_key")).upper() == "NORTHERN_IRELAND"
    assert (
        resolve_published_entry_for_requirement(
            published_registry_entries=merged,
            requirement_type="deposit_pi",
            portfolio_label="England",
            property_doc=_prop("England", deposit_taken=False),
            enforce_conditions=True,
        )
        is None
    )
    assert resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="right_to_rent_checks",
        portfolio_label="England",
        property_doc=_prop("England"),
        enforce_conditions=True,
    )
    fd = resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="fire_detection",
        portfolio_label="England",
        property_doc=_prop("England"),
        enforce_conditions=True,
    )
    assert fd and str(fd.get("canonical_code")).upper() == "SMOKE_HEAT_ALARMS"
    assert resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="hmo_fire_risk",
        portfolio_label="England",
        property_doc=_prop("England", is_hmo=True),
        enforce_conditions=True,
    )
    assert resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="fire_risk_assessment",
        portfolio_label="England",
        property_doc=_prop("England", is_hmo=True),
        enforce_conditions=True,
    )
    assert resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="portable_appliance_test",
        portfolio_label="England",
        property_doc=_prop("England"),
        enforce_conditions=True,
    )
