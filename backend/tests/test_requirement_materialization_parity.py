"""Preview vs materialize: same plan builder (no duplicate planning logic)."""
from services.compliance_requirement_registry import build_requirement_plan_for_property
from services.requirement_materialization_service import generate_requirements


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
