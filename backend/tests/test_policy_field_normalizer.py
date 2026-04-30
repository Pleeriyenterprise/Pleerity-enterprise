from services.policy_field_normalizer import (
    normalize_applicability_state,
    normalize_policy_criticality,
    normalize_requirement_code,
    resolve_policy_facts,
)


def test_normalize_requirement_code_precedence():
    assert normalize_requirement_code({"requirement_code": " GAS_SAFETY "}) == "gas_safety"
    assert normalize_requirement_code({"code": "EICR"}) == "eicr"
    assert normalize_requirement_code({"requirement_type": "epc"}) == "epc"


def test_normalize_applicability_state_with_status_fallback():
    assert normalize_applicability_state({"applicability": "required"}) == "REQUIRED"
    assert normalize_applicability_state({"status": "NOT_REQUIRED"}) == "NOT_REQUIRED"
    assert normalize_applicability_state({}) == "UNKNOWN"


def test_normalize_policy_criticality_defaults_medium():
    assert normalize_policy_criticality("high") == "HIGH"
    assert normalize_policy_criticality("bad") == "MEDIUM"


def test_resolve_policy_facts_uses_requirement_row_authority_then_fallbacks():
    out = resolve_policy_facts(
        {
            "requirement_code_normalized": "gas_safety",
            "applicability_state": "REQUIRED",
            "is_mandatory": True,
            "policy_criticality": "HIGH",
            "evidence_authority": {"state": "VERIFIED_EXPIRED"},
        },
        registry_metadata={"is_mandatory": False, "criticality": "LOW"},
        catalog_defaults={"is_mandatory": False, "criticality": "LOW"},
    )
    assert out["requirement_code_normalized"] == "gas_safety"
    assert out["applicability_state"] == "REQUIRED"
    assert out["is_mandatory"] is True
    assert out["policy_criticality"] == "HIGH"
    assert out["mandatory_source"] == "requirement_row"
    assert out["criticality_source"] == "requirement_row"
    assert out["evidence_state_normalized"] == "VERIFIED_EXPIRED"
