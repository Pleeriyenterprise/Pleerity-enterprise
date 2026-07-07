"""
P0-PROFESSIONAL-PLAN-CAPABILITY-MAPPING-01 — plan registry → Runtime Contract authority.

Proves every subscription tier generates globally correct capability grants for ACTIVE accounts.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.account_lifecycle_runtime_contract import (
    GRANT_ALLOW,
    GRANT_DENY,
    build_runtime_contract,
    resolve_capabilities,
)
from services.plan_registry import PlanCode, plan_registry

UTC = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)

OPS_CAPS_SOLO_DENY = (
    "CAP_OPS_MAINTENANCE",
    "CAP_OPS_ISSUES_VIEW",
    "CAP_OPS_CONTRACTORS",
    "CAP_OPS_PREDICTIVE",
    "CAP_RISK_VIEW",
    "CAP_OPS_RENT",
)

OPS_CAPS_ALL = OPS_CAPS_SOLO_DENY + (
    "CAP_OPS_APPROVALS",
    "CAP_OPS_COMPLIANCE_REVIEW",
)

PLAN_CODES = (
    (PlanCode.PLAN_1_SOLO, "PLAN_1_SOLO"),
    (PlanCode.PLAN_2_PORTFOLIO, "PLAN_2_PORTFOLIO"),
    (PlanCode.PLAN_3_PRO, "PLAN_3_PRO"),
)


def _contract(plan: str, lifecycle: str = "ACTIVE"):
    return build_runtime_contract(
        client={
            "client_id": f"plan-test-{plan}",
            "billing_plan": plan,
            "onboarding_status": "PROVISIONED",
        },
        billing={
            "client_id": f"plan-test-{plan}",
            "subscription_status": "ACTIVE",
            "billing_lifecycle_state": "active",
        },
        now=UTC,
    )


def _caps(plan: str) -> dict:
    return dict(_contract(plan)["capabilities"])


@pytest.mark.parametrize(
    "legacy,canonical",
    [
        ("PLAN_1", "PLAN_1_SOLO"),
        ("PLAN_2_5", "PLAN_2_PORTFOLIO"),
        ("PLAN_6_15", "PLAN_3_PRO"),
        ("SOLO", "PLAN_1_SOLO"),
        ("PORTFOLIO", "PLAN_2_PORTFOLIO"),
        ("PROFESSIONAL", "PLAN_3_PRO"),
    ],
)
def test_plan_alias_resolves_to_canonical(legacy: str, canonical: str):
    assert plan_registry.resolve_plan_code(legacy).value == canonical


def test_feature_matrix_includes_ops_keys_for_all_plans():
    from services.plan_registry import all_feature_matrix_keys

    keys = all_feature_matrix_keys()
    for key in (
        "maintenance_workflows",
        "predictive_maintenance",
        "contractor_network",
        "compliance_engine",
        "rent_operations",
        "ai_assistant",
    ):
        assert key in keys


def test_ops_defaults_derived_from_plan_registry():
    from services.ops_compliance_feature_flags import DEFAULTS_BY_PLAN, MAINTENANCE_WORKFLOWS

    assert DEFAULTS_BY_PLAN["PLAN_3_PRO"][MAINTENANCE_WORKFLOWS] is True
    assert DEFAULTS_BY_PLAN["PLAN_1_SOLO"][MAINTENANCE_WORKFLOWS] is False


class TestSoloPlanCapabilities:
    def test_solo_active_denies_premium_operational_caps(self):
        caps = _caps("PLAN_1_SOLO")
        for cap in OPS_CAPS_SOLO_DENY:
            assert caps[cap] == GRANT_DENY, cap
        assert caps["CAP_AI_ASSISTANT"] == GRANT_DENY
        # Compliance engine is included on all tiers
        assert caps["CAP_OPS_APPROVALS"] == GRANT_ALLOW
        assert caps["CAP_OPS_COMPLIANCE_REVIEW"] == GRANT_ALLOW

    def test_solo_allows_core_compliance(self):
        caps = _caps("PLAN_1_SOLO")
        for cap in ("CAP_DASHBOARD_VIEW", "CAP_PROP_VIEW", "CAP_REQ_VIEW", "CAP_DOC_VIEW"):
            assert caps[cap] == GRANT_ALLOW, cap


class TestPortfolioPlanCapabilities:
    def test_portfolio_active_allows_maintenance_not_contractors(self):
        caps = _caps("PLAN_2_PORTFOLIO")
        assert caps["CAP_OPS_MAINTENANCE"] == GRANT_ALLOW
        assert caps["CAP_OPS_ISSUES_VIEW"] == GRANT_ALLOW
        assert caps["CAP_OPS_PREDICTIVE"] == GRANT_ALLOW
        assert caps["CAP_OPS_RENT"] == GRANT_ALLOW
        assert caps["CAP_OPS_CONTRACTORS"] == GRANT_DENY
        assert caps["CAP_AI_ASSISTANT"] == GRANT_ALLOW

    def test_portfolio_denies_pro_only_integrations(self):
        caps = _caps("PLAN_2_PORTFOLIO")
        assert caps["CAP_INTEGRATION_WEBHOOKS"] == GRANT_DENY
        assert caps["CAP_TENANT_PORTAL"] == GRANT_DENY


class TestProfessionalPlanCapabilities:
    def test_professional_active_allows_full_operations(self):
        caps = _caps("PLAN_3_PRO")
        for cap in OPS_CAPS_ALL:
            assert caps[cap] == GRANT_ALLOW, cap

    def test_professional_active_allows_pro_integrations(self):
        caps = _caps("PLAN_3_PRO")
        assert caps["CAP_INTEGRATION_WEBHOOKS"] == GRANT_ALLOW
        assert caps["CAP_TENANT_PORTAL"] == GRANT_ALLOW
        assert caps["CAP_AI_ASSISTANT"] == GRANT_ALLOW

    def test_professional_legacy_alias_plan_6_15(self):
        caps = _caps("PLAN_6_15")
        assert caps["CAP_OPS_MAINTENANCE"] == GRANT_ALLOW
        assert caps["CAP_OPS_CONTRACTORS"] == GRANT_ALLOW


def test_plan_features_flow_through_resolve_capabilities():
    features = plan_registry.get_features(PlanCode.PLAN_3_PRO)
    caps = resolve_capabilities("ACTIVE", "FULL_ACCESS", {k: bool(v) for k, v in features.items()})
    assert caps["CAP_OPS_MAINTENANCE"] == GRANT_ALLOW


def test_plan_matrix_key_parity_across_tiers():
    solo = set(plan_registry.get_features(PlanCode.PLAN_1_SOLO).keys())
    port = set(plan_registry.get_features(PlanCode.PLAN_2_PORTFOLIO).keys())
    pro = set(plan_registry.get_features(PlanCode.PLAN_3_PRO).keys())
    assert solo == port == pro


@pytest.mark.parametrize("plan_enum,plan_str", PLAN_CODES)
def test_active_full_access_portal_mode(plan_enum, plan_str: str):
    contract = _contract(plan_str)
    assert contract["lifecycle_state"] == "ACTIVE"
    assert contract["portal_mode"] == "FULL_ACCESS"


def test_no_hand_built_contract_needed_for_maintenance_route_gate():
    """Regression: PLAN_3_PRO must not require synthetic ALLOW in tests."""
    caps = _caps("PLAN_3_PRO")
    assert caps["CAP_OPS_MAINTENANCE"] == GRANT_ALLOW
