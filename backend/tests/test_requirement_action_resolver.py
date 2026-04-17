from services.requirement_action_resolver import resolve_take_action_envelope, resolve_take_action_for_priority_action


def test_resolver_includes_registry_why_it_matters():
    requirement = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "gas_safety",
        "requirement_code": "gas_safety",
        "compliance_requirement_class": "DOCUMENT",
        "registry_metadata": {
            "why_it_matters_short_published": "Gas checks reduce safety risk and support legal compliance.",
            "why_it_matters_long_published": "Longer detail text.",
        },
    }
    out = resolve_take_action_envelope(requirement, property_id="p1", property_jurisdiction="England")
    assert out.get("why_it_matters_short", "").startswith("Gas checks reduce safety risk")
    assert out.get("why_it_matters_long") == "Longer detail text."


def test_priority_action_projection_includes_why_it_matters():
    row = {
        "related_property_id": "p1",
        "related_requirement_id": "r1",
        "requirement_code": "gas_safety",
        "jurisdiction": "England",
    }
    eng = {
        "compliance_requirement_class": "DOCUMENT",
        "registry_metadata": {"why_it_matters_short_published": "Short why"},
    }
    out = resolve_take_action_for_priority_action(row, compliance_engine=eng)
    assert out.get("why_it_matters_short") == "Short why"

