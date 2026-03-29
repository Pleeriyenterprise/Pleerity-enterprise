"""Declared vs verified contractor capabilities: compliance routing must not trust self-declaration alone."""

from services.compliance_contractor_capability import (
    contractor_qualifies_for_requirement,
    contractor_verified_qualifies_for_requirement,
    parse_verified_execution_capabilities,
)
from services.contractor_recommendation import recommend_contractors
from services.contractor_service import SOURCE_SELF_REGISTERED, contractor_passes_work_order_execution_gate
from services.work_order_execution_constants import (
    EXECUTION_CAPABILITY_COMPLIANCE,
    WORK_ORDER_KIND_COMPLIANCE,
)


def test_self_registered_fuzzy_declared_does_not_pass_compliance_gate():
    """Legacy execution_capabilities + credential hints must not authorize compliance for self_registered."""
    wo = {"work_order_kind": WORK_ORDER_KIND_COMPLIANCE, "requirement_code": "eicr"}
    c = {
        "source_type": SOURCE_SELF_REGISTERED,
        "execution_capabilities": "both",
        "supported_requirement_codes": [],
        "trade_types": ["electrical"],
        "credentials": ["niceic", "eicr"],
        "declared_execution_capabilities": "compliance",
        "declared_supported_requirement_codes": ["eicr"],
    }
    assert contractor_qualifies_for_requirement(c, "eicr") is True
    assert contractor_verified_qualifies_for_requirement(c, "eicr") is False
    assert EXECUTION_CAPABILITY_COMPLIANCE not in parse_verified_execution_capabilities(c)
    assert contractor_passes_work_order_execution_gate(c, wo) is False


def test_self_registered_verified_passes_compliance_gate():
    wo = {"work_order_kind": WORK_ORDER_KIND_COMPLIANCE, "requirement_code": "eicr"}
    c = {
        "source_type": SOURCE_SELF_REGISTERED,
        "execution_capabilities": "maintenance",
        "supported_requirement_codes": [],
        "verified_execution_capabilities": "compliance",
        "verified_supported_requirement_codes": ["eicr"],
    }
    assert contractor_passes_work_order_execution_gate(c, wo) is True


def test_recommendation_compliance_uses_verified_not_fuzzy():
    wo_c = {
        "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
        "requirement_code": "eicr",
        "work_order_id": "wo-v",
    }
    prop = {"postcode": "SW1A 1AA"}
    c_fuzzy_only = {
        "contractor_id": "sr1",
        "status": "active",
        "source_type": SOURCE_SELF_REGISTERED,
        "trade_types": ["electrical"],
        "credentials": ["eicr"],
        "execution_capabilities": "maintenance",
        "areas_served": ["sw1a1aa"],
        "region": "sw1a",
    }
    r = recommend_contractors(wo_c, prop, [c_fuzzy_only], eligible_only=False)
    assert r["total"] == 0

    c_verified = {
        **c_fuzzy_only,
        "contractor_id": "sr2",
        "verified_execution_capabilities": "compliance",
        "verified_supported_requirement_codes": ["eicr"],
    }
    r2 = recommend_contractors(wo_c, prop, [c_verified], eligible_only=False)
    assert r2["total"] == 1
