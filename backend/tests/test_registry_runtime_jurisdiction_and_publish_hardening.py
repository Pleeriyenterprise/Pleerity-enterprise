"""
Runtime hardening for published registry merge + UK jurisdiction applicability.

Covers: portfolio-specific requirement rows, display_jurisdictions gating, action-link jurisdiction
filtering, draft-vs-published isolation (draft Mongo never merged here), and condition-driven rows.
"""
from __future__ import annotations

from services.compliance_requirement_registry import (
    build_requirement_plan_for_property,
    published_registry_entry_eligible_for_runtime,
)
from services.compliance_registry_admin_service import merge_draft_overlay_onto_plan_row


def _england_residential(**kwargs):
    base = {
        "property_id": "p1",
        "client_id": "c1",
        "jurisdiction": "England",
        "property_type": "residential",
        "tenancy_active": True,
        "has_gas_supply": True,
        "deposit_taken": True,
        "furnished": False,
        "is_hmo": False,
    }
    base.update(kwargs)
    return base


def _client_england():
    return {"default_jurisdiction": "England"}


def test_england_sees_right_to_rent_not_wales_or_scotland_rows():
    plan = build_requirement_plan_for_property(_england_residential(), _client_england())
    types = {x.requirement_type for x in plan}
    assert "right_to_rent" in types
    assert "wales_occupation_contract" not in types
    assert "scotland_landlord_registration" not in types
    assert "rent_smart_wales" not in types


def test_wales_sees_written_occupation_contract_and_rent_smart_not_right_to_rent():
    prop = _england_residential()
    prop["jurisdiction"] = "Wales"
    plan = build_requirement_plan_for_property(prop, {"default_jurisdiction": "Wales"})
    types = {x.requirement_type for x in plan}
    assert "wales_occupation_contract" in types
    assert "rent_smart_wales" in types
    assert "right_to_rent" not in types
    assert "scotland_landlord_registration" not in types


def test_scotland_sees_scotland_landlord_registration_not_right_to_rent_or_wales():
    prop = _england_residential()
    prop["jurisdiction"] = "Scotland"
    plan = build_requirement_plan_for_property(prop, {"default_jurisdiction": "Scotland"})
    types = {x.requirement_type for x in plan}
    assert "scotland_landlord_registration" in types
    assert "right_to_rent" not in types
    assert "rent_smart_wales" not in types
    assert "wales_occupation_contract" not in types


def test_northern_ireland_sees_ni_landlord_registration_not_wales_contract():
    prop = _england_residential()
    prop["jurisdiction"] = "Northern Ireland"
    plan = build_requirement_plan_for_property(prop, {"default_jurisdiction": "Northern Ireland"})
    types = {x.requirement_type for x in plan}
    assert "landlord_registration_ni" in types
    assert "wales_occupation_contract" not in types
    assert "scotland_landlord_registration" not in types
    assert "rent_smart_wales" not in types


def test_gas_safety_only_when_has_gas_supply():
    prop = _england_residential(has_gas_supply=False)
    plan = build_requirement_plan_for_property(prop, _client_england())
    assert "gas_safety" not in {x.requirement_type for x in plan}


def test_deposit_pi_only_when_deposit_taken():
    prop = _england_residential(deposit_taken=False)
    plan = build_requirement_plan_for_property(prop, _client_england())
    assert "deposit_pi" not in {x.requirement_type for x in plan}


def test_pat_only_when_furnished_and_tenancy_active():
    prop = _england_residential(furnished=True, tenancy_active=True)
    plan = build_requirement_plan_for_property(prop, _client_england())
    assert "portable_appliance_test" in {x.requirement_type for x in plan}

    prop2 = _england_residential(furnished=True, tenancy_active=False)
    plan2 = build_requirement_plan_for_property(prop2, _client_england())
    assert "portable_appliance_test" not in {x.requirement_type for x in plan2}


def test_hmo_licence_only_when_hmo():
    prop = _england_residential(is_hmo=True, hmo_license_required=True)
    plan = build_requirement_plan_for_property(prop, _client_england())
    assert "hmo_license" in {x.requirement_type for x in plan}


def test_published_overlay_skipped_when_display_jurisdictions_exclude_region():
    prop = _england_residential()
    pub = {
        "GAS_SAFETY|DEFAULT": {
            "canonical_code": "GAS_SAFETY",
            "scope_key": "DEFAULT",
            "jurisdiction": {"display_jurisdictions": ["SCOTLAND"]},
            "identity": {"name": "Scotland-only gas overlay"},
            "classification": {"requirement_type": "DOCUMENT"},
            "frequency": {"frequency_days": 400, "reminder_lead_days": 40},
        }
    }
    plan = build_requirement_plan_for_property(prop, _client_england(), published_registry_entries=pub)
    g = next(x for x in plan if x.requirement_type == "gas_safety")
    assert "Scotland-only" not in g.description


def test_published_overlay_skipped_when_entry_archived():
    prop = _england_residential()
    pub = {
        "GAS_SAFETY|DEFAULT": {
            "canonical_code": "GAS_SAFETY",
            "scope_key": "DEFAULT",
            "lifecycle": {"status": "archived"},
            "jurisdiction": {"display_jurisdictions": ["ENGLAND"]},
            "identity": {"name": "Archived gas"},
            "classification": {"requirement_type": "DOCUMENT"},
            "frequency": {"frequency_days": 400, "reminder_lead_days": 40},
        }
    }
    plan = build_requirement_plan_for_property(prop, _client_england(), published_registry_entries=pub)
    g = next(x for x in plan if x.requirement_type == "gas_safety")
    assert "Archived" not in g.description
    assert not published_registry_entry_eligible_for_runtime(pub["GAS_SAFETY|DEFAULT"])


def test_merge_filters_action_links_by_portfolio_region():
    draft = {
        "identity": {"name": "Linked gas"},
        "classification": {"requirement_type": "DOCUMENT"},
        "frequency": {"frequency_days": 365, "reminder_lead_days": 30},
        "action_links": [
            {
                "key": "eng",
                "label": "England gov",
                "url": "https://www.gov.uk/gas",
                "kind": "official",
                "jurisdictions": ["ENGLAND"],
                "priority": 10,
            },
            {
                "key": "sct",
                "label": "Scotland gov",
                "url": "https://www.mygov.scot/",
                "kind": "official",
                "jurisdictions": ["SCOTLAND"],
                "priority": 10,
            },
        ],
    }
    prod = {
        "description": "Gas",
        "frequency_days": 365,
        "warning_days": 30,
        "compliance_requirement_class": "DOCUMENT",
        "client_surface_visible": True,
        "action_links": [],
    }
    merged = merge_draft_overlay_onto_plan_row(prod, draft, portfolio_label="England")
    labels = {x["label"] for x in merged.get("action_links", [])}
    assert "England gov" in labels
    assert "Scotland gov" not in labels