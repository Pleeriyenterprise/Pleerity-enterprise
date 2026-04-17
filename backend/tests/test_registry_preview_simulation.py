"""Registry preview simulation merges drafts read-only onto production plan rows."""
from __future__ import annotations

from services.compliance_registry_admin_service import (
    REGISTRY_PREVIEW_COVERAGE,
    build_registry_preview_simulation,
    matching_drafts_for_plan_row,
    plan_types_for_draft_canonical,
)


def test_plan_types_includes_wales_scotland_aliases():
    assert "gas_safety" in plan_types_for_draft_canonical("GAS_SAFETY")
    assert "scotland_landlord_registration" in plan_types_for_draft_canonical("LANDLORD_REGISTRATION")
    assert "wales_occupation_contract" in plan_types_for_draft_canonical("OCCUPATION_CONTRACT")


def test_preview_response_includes_coverage_metadata():
    prop = {"property_id": "p0", "client_id": "c1", "jurisdiction": "England", "property_type": "residential", "has_gas_supply": True}
    out = build_registry_preview_simulation(prop, {}, [], include_explanations=False)
    assert out.get("published_registry_entry_count") == 0
    cov = out.get("preview_coverage")
    assert cov is REGISTRY_PREVIEW_COVERAGE
    assert cov.get("decorates_only") is True
    assert "not_yet" in cov and isinstance(cov["not_yet"], list)


def test_preview_simulation_applies_name_overlay():
    prop = {
        "property_id": "p1",
        "client_id": "c1",
        "jurisdiction": "England",
        "property_type": "residential",
        "has_gas_supply": True,
    }
    client = {"client_id": "c1", "default_jurisdiction": "England"}
    drafts = [
        {
            "entry_id": "e1",
            "canonical_code": "GAS_SAFETY",
            "scope_key": "DEFAULT",
            "jurisdiction": {"display_jurisdictions": ["England", "Wales", "Scotland", "Northern Ireland"]},
            "identity": {"name": "Preview gas title"},
            "classification": {"requirement_type": "DOCUMENT", "client_surface_visible": True},
            "frequency": {"frequency_days": 365, "reminder_lead_days": 30},
            "why_it_matters_short": "Preview why short",
            "why_it_matters_long": "Preview why long",
            "action_links": [
                {
                    "key": "k1",
                    "label": "Help",
                    "kind": "official",
                    "jurisdictions": ["ENGLAND"],
                    "url": "https://example.com/help",
                    "priority": 10,
                    "is_active": True,
                }
            ],
        }
    ]
    out = build_registry_preview_simulation(prop, client, drafts, include_explanations=False)
    gas = next((r for r in out["rows"] if r["requirement_type"] == "gas_safety"), None)
    assert gas is not None
    assert gas["production"]["description"] != "Preview gas title" or gas["preview"]["description"] == "Preview gas title"
    assert gas["registry_preview"]["overlay_count"] >= 1
    assert gas["registry_preview"]["read_only"] is True
    assert gas["preview"].get("why_it_matters_short") == "Preview why short"
    assert gas["preview"].get("why_it_matters_long") == "Preview why long"
    assert gas["preview"].get("action_links")


def test_scotland_draft_skipped_for_england_property():
    prop = {
        "property_id": "p2",
        "client_id": "c1",
        "jurisdiction": "England",
        "property_type": "residential",
        "has_gas_supply": True,
    }
    client = {"default_jurisdiction": "England"}
    drafts = [
        {
            "entry_id": "e2",
            "canonical_code": "LANDLORD_REGISTRATION",
            "scope_key": "SCOTLAND",
            "jurisdiction": {"display_jurisdictions": ["Scotland"]},
            "identity": {"name": "Scot reg"},
        }
    ]
    matched = matching_drafts_for_plan_row(drafts, "scotland_landlord_registration", "England")
    assert matched == []
