from services.compliance_registry_conditions import (
    human_summary_registry_conditions,
    property_matches_registry_conditions,
    validate_registry_conditions,
)


def test_validate_conditions_rejects_bad_field():
    cond = {"logic": "ALL", "rules": [{"field": "not_a_field", "op": "true"}]}
    errs = validate_registry_conditions(cond)
    assert any("not an allowed" in e for e in errs)


def test_validate_conditions_rejects_bad_op_for_boolean_field():
    cond = {"logic": "ALL", "rules": [{"field": "is_hmo", "op": "gt", "value": 1}]}
    errs = validate_registry_conditions(cond)
    assert any("not valid for field" in e for e in errs)


def test_validate_conditions_gas_style_rule():
    cond = {"logic": "ALL", "rules": [{"field": "has_gas_supply", "op": "true"}]}
    assert validate_registry_conditions(cond) == []


def test_human_summary_multiline():
    s = human_summary_registry_conditions({"logic": "ALL", "rules": [{"field": "is_hmo", "op": "true"}]})
    assert "HMO" in s
    assert "•" in s


def test_property_matches_none_true_when_no_rules():
    assert property_matches_registry_conditions(None, {}) is True
    assert property_matches_registry_conditions(None, {"logic": "ALL", "rules": []}) is True


def test_property_matches_none_fails_closed_when_rules_require_evaluation():
    cond = {"logic": "ALL", "rules": [{"field": "has_gas_supply", "op": "false"}]}
    assert property_matches_registry_conditions(None, cond) is False


def test_property_matches_has_gas_true_false():
    prop = {"has_gas_supply": True}
    assert property_matches_registry_conditions(prop, {"logic": "ALL", "rules": [{"field": "has_gas_supply", "op": "true"}]})
    assert not property_matches_registry_conditions(
        prop,
        {"logic": "ALL", "rules": [{"field": "has_gas_supply", "op": "false"}]},
    )


def test_property_matches_is_hmo_via_property_type():
    prop = {"property_type": "HMO", "is_hmo": False}
    assert property_matches_registry_conditions(prop, {"logic": "ALL", "rules": [{"field": "is_hmo", "op": "true"}]})


def test_property_matches_any_logic():
    prop = {"has_gas_supply": True, "is_hmo": False}
    cond = {
        "logic": "ANY",
        "rules": [
            {"field": "is_hmo", "op": "true"},
            {"field": "has_gas_supply", "op": "true"},
        ],
    }
    assert property_matches_registry_conditions(prop, cond)
