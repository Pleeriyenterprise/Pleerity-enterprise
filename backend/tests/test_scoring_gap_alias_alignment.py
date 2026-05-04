"""Phase-1 alias alignment: scoring keys, gap policy facts, and legacy weights."""

from services.compliance_score import get_requirement_weight
from services.compliance_scoring_v2 import compute_property_score_v2, normalize_requirement_code
from services.policy_field_normalizer import normalize_requirement_code as policy_normalize_requirement_code
from services.requirement_code_registry import normalize_requirement_code as registry_normalize_requirement_code


def _breakdown_by_code(score: dict) -> dict:
    return {row["requirement_code"]: row for row in score["requirement_breakdown"]}


def test_scoring_normalize_maps_phase1_aliases_to_canonical_keys():
    assert normalize_requirement_code("gas_safety_certificate") == normalize_requirement_code("gas_safety") == "GAS_SAFETY"
    # Domestic alarm family: scoring bucket remains FIRE_DETECTION for all legacy slugs + canonical registry slug.
    assert normalize_requirement_code("fire_alarm") == normalize_requirement_code("fire_detection") == "FIRE_DETECTION"
    assert normalize_requirement_code("smoke_heat_alarms") == normalize_requirement_code("smoke_alarms") == "FIRE_DETECTION"
    assert (
        normalize_requirement_code("right_to_rent_checks")
        == normalize_requirement_code("right_to_rent")
        == "RIGHT_TO_RENT"
    )


def test_registry_domestic_alarm_aliases_normalize_to_smoke_heat_alarms():
    for raw in ("fire_alarm", "fire_detection", "smoke_alarms", "co_alarms", "smoke_heat_alarms"):
        assert registry_normalize_requirement_code(raw) == "smoke_heat_alarms"


def test_emergency_lighting_scoring_alias_unchanged():
    assert normalize_requirement_code("emergency_lighting") == "FIRE_DETECTION"


def test_compute_property_score_v2_joins_alias_requirements_to_canonical_profile():
    property_doc = {
        "jurisdiction": "England",
        "property_id": "p-alias-align",
        "has_gas_supply": True,
        "tenancy_active": True,
        "property_type": "RESIDENTIAL",
    }
    client_doc = {"default_jurisdiction": "England"}
    empty_docs: list = []
    zero_counts = (0, 0, 0)

    cases = [
        (
            {"requirement_code": "gas_safety_certificate", "requirement_type": "gas_safety_certificate"},
            {"requirement_code": "gas_safety", "requirement_type": "gas_safety"},
            "GAS_SAFETY",
        ),
        (
            {"requirement_code": "smoke_alarms", "requirement_type": "smoke_alarms"},
            {"requirement_code": "smoke_heat_alarms", "requirement_type": "smoke_heat_alarms"},
            "FIRE_DETECTION",
        ),
        (
            {"requirement_code": "right_to_rent_checks", "requirement_type": "right_to_rent_checks"},
            {"requirement_code": "right_to_rent", "requirement_type": "right_to_rent"},
            "RIGHT_TO_RENT",
        ),
    ]
    for req_a, req_b, code in cases:
        sa = compute_property_score_v2(
            property_doc=property_doc,
            client_doc=client_doc,
            requirements=[req_a],
            documents=empty_docs,
            open_issues_count=zero_counts[0],
            overdue_work_orders_count=zero_counts[1],
            open_risks_count=zero_counts[2],
        )
        sb = compute_property_score_v2(
            property_doc=property_doc,
            client_doc=client_doc,
            requirements=[req_b],
            documents=empty_docs,
            open_issues_count=zero_counts[0],
            overdue_work_orders_count=zero_counts[1],
            open_risks_count=zero_counts[2],
        )
        ra = _breakdown_by_code(sa)[code]
        rb = _breakdown_by_code(sb)[code]
        assert ra["applies_if"] is rb["applies_if"] is True
        for k in ("status", "earned_points", "applicable_points", "weight"):
            assert ra[k] == rb[k], f"mismatch for {code} on {k}"


def test_policy_field_normalizer_returns_registry_canonical_for_phase1_aliases():
    assert policy_normalize_requirement_code({"requirement_code": "gas_safety_certificate"}) == "gas_safety"
    assert policy_normalize_requirement_code({"requirement_code": "fire_alarm"}) == "smoke_heat_alarms"
    assert policy_normalize_requirement_code({"requirement_code": "right_to_rent_checks"}) == "right_to_rent"


def test_get_requirement_weight_alias_matches_canonical():
    assert get_requirement_weight("gas_safety_certificate") == get_requirement_weight("gas_safety") == 1.5
    assert get_requirement_weight("right_to_rent_checks") == get_requirement_weight("right_to_rent") == 1.2
    assert get_requirement_weight("fire_alarm") == get_requirement_weight("fire_detection")


def test_get_requirement_weight_smoke_co_emergency_deferred_unchanged():
    """Legacy weight keys still apply; do not regress smoke / CO / emergency paths."""
    assert get_requirement_weight("smoke_alarm") == 1.3
    assert get_requirement_weight("co_alarm") == 1.3
    assert get_requirement_weight("emergency_lighting") == 1.3
