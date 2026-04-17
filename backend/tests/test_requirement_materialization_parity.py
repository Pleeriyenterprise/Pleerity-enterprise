"""Preview vs materialize: same plan builder (no duplicate planning logic)."""
from services.compliance_requirement_registry import build_requirement_plan_for_property
from services.requirement_materialization_service import _effective_client_surface_visible, generate_requirements


def test_generate_requirements_types_match_build_plan_directly():
    prop = {
        "property_id": "p-parity",
        "client_id": "c1",
        "jurisdiction": "Northern Ireland",
        "property_type": "house",
        "is_hmo": True,
        "has_gas_supply": True,
    }
    direct = {x.requirement_type for x in build_requirement_plan_for_property(prop, {})}
    via_preview = {x["requirement_type"] for x in generate_requirements(prop, {})}
    assert direct == via_preview


def test_published_overlay_fields_flow_into_plan_and_preview():
    prop = {
        "property_id": "p-overlay",
        "client_id": "c1",
        "jurisdiction": "England",
        "property_type": "house",
        "has_gas_supply": True,
    }
    published = {
        "GAS_SAFETY|DEFAULT": {
            "canonical_code": "GAS_SAFETY",
            "scope_key": "DEFAULT",
            "identity": {"name": "Gas Safety (Published)"},
            "classification": {"requirement_type": "DOCUMENT", "client_surface_visible": False},
            "frequency": {"frequency_days": 400, "reminder_lead_days": 20},
            "action_links": [
                {
                    "key": "k1",
                    "label": "Published link",
                    "kind": "official",
                    "jurisdictions": ["ENGLAND"],
                    "url": "https://example.com/published",
                    "priority": 10,
                    "is_active": True,
                }
            ],
            "why_it_matters_short": "Published short reason",
            "why_it_matters_long": "Published long reason",
            "why_it_matters_by_jurisdiction": {"SCOTLAND": {"short": "Scotland short"}},
        }
    }
    items = build_requirement_plan_for_property(prop, {}, published_registry_entries=published)
    gas = next(x for x in items if x.requirement_type == "gas_safety")
    assert gas.client_surface_visible_override is False
    assert _effective_client_surface_visible(gas) is False
    assert gas.why_it_matters_short == "Published short reason"
    assert gas.why_it_matters_long == "Published long reason"
    assert len(gas.action_links) == 1
    rows = generate_requirements(prop, {}, published_registry_entries=published)
    gas_row = next(x for x in rows if x["requirement_type"] == "gas_safety")
    assert gas_row["client_surface_visible"] is False
    assert gas_row["why_it_matters_short"] == "Published short reason"
    assert gas_row["why_it_matters_long"] == "Published long reason"
    assert len(gas_row["action_links"]) == 1
