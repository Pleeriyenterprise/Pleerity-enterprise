"""Jurisdiction-specific SLA for compliance execution work orders."""
from services.compliance_rules_registry import compliance_execution_sla_policy
from services.compliance_workflow_service import client_job_sla_policy


def test_client_job_sla_policy_stamped_uses_registry_source():
    wo = {
        "work_order_kind": "COMPLIANCE",
        "jurisdiction": "Scotland",
        "requirement_code": "gas_safety",
        "compliance_sla_complete_days": 7,
        "compliance_sla_respond_hours": 24,
        "compliance_sla_risk_days_before_complete": 2,
        "compliance_sla_risk_hours_before_respond": 4,
    }
    p = client_job_sla_policy(wo)
    assert p["policy_source"] == "compliance_registry"
    assert p["jurisdiction"] == "Scotland"
    assert p["requirement_code"] == "gas_safety"
    assert p["compliance_sla_complete_days"] == 7


def test_client_job_sla_policy_legacy_defaults():
    wo = {
        "work_order_kind": "COMPLIANCE",
        "jurisdiction": "England",
        "requirement_code": "gas_safety",
    }
    p = client_job_sla_policy(wo)
    assert p["policy_source"] == "default"
    assert p["compliance_sla_complete_days"] == 5


def test_client_job_sla_policy_maintenance_is_none():
    assert client_job_sla_policy({"work_order_kind": "MAINTENANCE"}) is None


def test_gas_sla_scotland_vs_england_wales():
    ew = compliance_execution_sla_policy("England", "gas_safety")
    sc = compliance_execution_sla_policy("Scotland", "gas_safety")
    assert ew["complete_days"] == 10
    assert sc["complete_days"] == 7
    assert ew["complete_days"] != sc["complete_days"]


def test_legionella_scotland_risk_window_wider_than_ew():
    ew = compliance_execution_sla_policy("Wales", "legionella")
    sc = compliance_execution_sla_policy("Scotland", "legionella")
    assert sc["risk_days_before_complete"] >= ew["risk_days_before_complete"]


def test_unknown_requirement_code_uses_defaults():
    pol = compliance_execution_sla_policy("England", "smoke_alarms")
    assert pol["complete_days"] == 5
    assert pol["risk_days_before_complete"] == 1
