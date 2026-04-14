"""Per-property requirement plan from compliance_requirement_registry."""
from services.compliance_requirement_registry import (
    REQUIREMENT_CLASS_DOCUMENT,
    REQUIREMENT_CLASS_JOB,
    REQUIREMENT_CLASS_OBLIGATION,
    build_requirement_plan_for_property,
)
from services.requirement_catalog import (
    GAS_SAFETY_CERT,
    HMO_FIRE_RISK,
    HMO_FIRE_RISK_EVIDENCE,
    SCOTLAND_LANDLORD_REGISTRATION,
    WALES_OCCUPATION_CONTRACT,
)


def test_plan_is_per_property_types_no_cross_merge():
    p1 = {"property_id": "a", "jurisdiction": "England", "cert_gas_safety": "YES"}
    p2 = {"property_id": "b", "jurisdiction": "Scotland", "cert_gas_safety": "YES", "is_hmo": True}
    c = {}
    plan1 = build_requirement_plan_for_property(p1, c)
    plan2 = build_requirement_plan_for_property(p2, c)
    t1 = {x.requirement_type for x in plan1}
    t2 = {x.requirement_type for x in plan2}
    assert "gas_safety" in t1 and "gas_safety" in t2
    assert "scotland_landlord_registration" in t2
    assert "scotland_landlord_registration" not in t1


def test_obligation_types_not_tracked():
    prop = {
        "jurisdiction": "Wales",
        "property_type": "house",
        "tenancy_active": True,
    }
    plan = build_requirement_plan_for_property(prop, {})
    wales_contract = next((x for x in plan if x.requirement_type == "wales_occupation_contract"), None)
    assert wales_contract is not None
    assert wales_contract.compliance_requirement_class == REQUIREMENT_CLASS_OBLIGATION
    assert wales_contract.is_tracked is False


def test_hmo_job_rows_tracked():
    prop = {"jurisdiction": "England", "is_hmo": True, "cert_gas_safety": "YES"}
    plan = build_requirement_plan_for_property(prop, {})
    em = next((x for x in plan if x.requirement_type == "emergency_lighting"), None)
    assert em is not None
    assert em.compliance_requirement_class == REQUIREMENT_CLASS_JOB
    assert em.is_tracked is True


def test_core_pack_document_class():
    prop = {"jurisdiction": "England", "cert_gas_safety": "YES"}
    plan = build_requirement_plan_for_property(prop, {})
    gas = next((x for x in plan if x.requirement_type == "gas_safety"), None)
    assert gas is not None
    assert gas.compliance_requirement_class == REQUIREMENT_CLASS_DOCUMENT


def test_scenario_england_non_hmo_gas_supply_no_hmo_pack():
    """England residential, not HMO, gas supply on — gas row present; no HMO-only jobs."""
    prop = {
        "property_id": "p-eng-1",
        "jurisdiction": "England",
        "property_type": "house",
        "is_hmo": False,
        "has_gas_supply": True,
    }
    plan = build_requirement_plan_for_property(prop, {})
    types = {x.requirement_type for x in plan}
    assert "gas_safety" in types
    assert "emergency_lighting" not in types
    assert "hmo_fire_risk_evidence" not in types
    gas = next(x for x in plan if x.requirement_type == "gas_safety")
    assert GAS_SAFETY_CERT in gas.catalog_keys


def test_scenario_scotland_landlord_registration_present():
    prop = {"property_id": "p-sct-1", "jurisdiction": "Scotland", "property_type": "flat"}
    plan = build_requirement_plan_for_property(prop, {})
    reg = next((x for x in plan if x.requirement_type == "scotland_landlord_registration"), None)
    assert reg is not None
    assert reg.catalog_keys == (SCOTLAND_LANDLORD_REGISTRATION,)
    assert reg.compliance_requirement_class == REQUIREMENT_CLASS_DOCUMENT


def test_scenario_wales_no_active_tenancy_excludes_occupation_contract():
    prop = {
        "property_id": "p-wls-1",
        "jurisdiction": "Wales",
        "property_type": "house",
        "tenancy_active": False,
    }
    plan = build_requirement_plan_for_property(prop, {})
    assert all(x.requirement_type != "wales_occupation_contract" for x in plan)
    assert WALES_OCCUPATION_CONTRACT not in {k for x in plan for k in x.catalog_keys}


def test_scenario_northern_ireland_hmo_fire_and_jobs():
    prop = {
        "property_id": "p-ni-1",
        "jurisdiction": "Northern Ireland",
        "property_type": "house",
        "is_hmo": True,
        "has_gas_supply": True,
    }
    plan = build_requirement_plan_for_property(prop, {})
    types = {x.requirement_type for x in plan}
    assert "hmo_fire_risk_evidence" in types
    assert "emergency_lighting" in types
    fra = next(x for x in plan if x.requirement_type == "hmo_fire_risk_evidence")
    assert HMO_FIRE_RISK_EVIDENCE in fra.catalog_keys and HMO_FIRE_RISK in fra.catalog_keys
