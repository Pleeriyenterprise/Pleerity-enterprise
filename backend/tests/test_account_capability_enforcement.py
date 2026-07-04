"""Unit tests for Account Capability Enforcement (ILP-4 Phase 0–1)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.account_capability_enforcement import (
    GRANT_ALLOW,
    GRANT_DENY,
    GRANT_HIDDEN,
    GRANT_LIMITED,
    GRANT_PLAN_GATED,
    GRANT_READ,
    CapabilityDeniedError,
    CapabilityEnforcementService,
    CapabilityReasonCode,
    SEMANTIC_READ_ONLY,
    is_grant_action_allowed,
    normalize_grant_semantic,
)
from services.account_lifecycle_runtime_contract import build_runtime_contract
from services.capability_compatibility import (
    evaluate_feature_via_capability,
    feature_key_to_capabilities,
    primary_capability_for_feature,
)

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _client(**overrides):
    base = {
        "client_id": "c-enf-1",
        "billing_plan": "PLAN_3_PRO",
        "subscription_status": "ACTIVE",
    }
    base.update(overrides)
    return base


def _billing(**overrides):
    base = {
        "client_id": "c-enf-1",
        "subscription_status": "ACTIVE",
        "billing_lifecycle_state": "active",
        "canonical_entitlement_state": "ENABLED",
    }
    base.update(overrides)
    return base


def _contract(**kwargs):
    return build_runtime_contract(client=_client(), billing=_billing(), now=NOW, **kwargs)


def _service():
    return CapabilityEnforcementService(db=None)


class TestGrantSemantics:
    def test_read_maps_to_read_only_semantic(self):
        assert normalize_grant_semantic(GRANT_READ) == SEMANTIC_READ_ONLY

    def test_allow_read_write(self):
        assert is_grant_action_allowed(GRANT_ALLOW, "read") is True
        assert is_grant_action_allowed(GRANT_ALLOW, "write") is True

    def test_read_only_allows_read_blocks_write(self):
        assert is_grant_action_allowed(GRANT_READ, "read") is True
        assert is_grant_action_allowed(GRANT_READ, "write") is False

    def test_deny_blocks_both(self):
        assert is_grant_action_allowed(GRANT_DENY, "read") is False
        assert is_grant_action_allowed(GRANT_DENY, "write") is False

    def test_hidden_blocks_both(self):
        assert is_grant_action_allowed(GRANT_HIDDEN, "read") is False
        assert is_grant_action_allowed(GRANT_HIDDEN, "write") is False

    def test_limited_allows_read_and_write(self):
        assert is_grant_action_allowed(GRANT_LIMITED, "read") is True
        assert is_grant_action_allowed(GRANT_LIMITED, "write") is True

    def test_unresolved_plan_gated_blocks(self):
        assert is_grant_action_allowed(GRANT_PLAN_GATED, "read") is False
        assert is_grant_action_allowed(GRANT_PLAN_GATED, "write") is False


class TestCapabilityEnforcementService:
    def test_allow_decision_active(self):
        contract = _contract()
        svc = _service()
        decision = svc.evaluate_from_contract(contract, "CAP_PROP_EDIT", "write")
        assert decision.allowed is True
        assert decision.grant == GRANT_ALLOW
        assert decision.reason_code == CapabilityReasonCode.ALLOWED.value

    def test_read_only_blocks_write_allows_read(self):
        contract = build_runtime_contract(
            client=_client(),
            billing=_billing(
                subscription_status="UNPAID",
                billing_lifecycle_state="expired",
                read_only_retention=True,
            ),
            now=NOW,
        )
        svc = _service()
        read_decision = svc.evaluate_from_contract(contract, "CAP_PROP_VIEW", "read")
        write_decision = svc.evaluate_from_contract(contract, "CAP_PROP_VIEW", "write")
        assert read_decision.allowed is True
        assert read_decision.effective_semantic == SEMANTIC_READ_ONLY
        assert write_decision.allowed is False
        assert write_decision.reason_code == CapabilityReasonCode.READ_ONLY_BLOCKED.value

    def test_deny_suspended(self):
        contract = build_runtime_contract(
            client=_client(),
            billing=_billing(
                subscription_status="SUSPENDED",
                billing_lifecycle_state="suspended",
                canonical_entitlement_state="SUSPENDED",
            ),
            now=NOW,
        )
        decision = _service().evaluate_from_contract(contract, "CAP_PROP_VIEW", "read")
        assert decision.allowed is False
        assert decision.grant == GRANT_DENY
        assert decision.reason_code == CapabilityReasonCode.DENIED.value

    def test_denied_deleted_login(self):
        contract = build_runtime_contract(
            client={"client_id": "c-enf-1", "purged_at": NOW.isoformat()},
            billing=_billing(),
            now=NOW,
        )
        decision = _service().evaluate_from_contract(contract, "CAP_AUTH_LOGIN", "read")
        assert decision.allowed is False
        assert decision.grant == GRANT_DENY

    def test_denied_archived_property_view(self):
        contract = build_runtime_contract(
            client={"client_id": "c-enf-1", "is_deleted": True, "client_lifecycle_status": "ARCHIVED"},
            billing=_billing(subscription_status="ACTIVE", billing_lifecycle_state="active"),
            now=NOW,
        )
        decision = _service().evaluate_from_contract(contract, "CAP_PROP_VIEW", "read")
        assert decision.allowed is False
        assert decision.grant == GRANT_DENY

    def test_plan_gated_resolved_deny_on_solo(self):
        contract = build_runtime_contract(
            client=_client(billing_plan="PLAN_1_SOLO"),
            billing=_billing(),
            now=NOW,
        )
        decision = _service().evaluate_from_contract(contract, "CAP_REPORT_GENERATE_PDF", "write")
        assert decision.grant == GRANT_DENY
        assert decision.allowed is False
        assert decision.reason_code == CapabilityReasonCode.DENIED.value

    def test_plan_gated_resolved_allow_on_pro(self):
        contract = _contract()
        decision = _service().evaluate_from_contract(contract, "CAP_REPORT_GENERATE_PDF", "write")
        assert decision.grant == GRANT_ALLOW
        assert decision.allowed is True

    def test_unknown_catalog_capability_missing_from_map(self):
        contract = _contract()
        decision = _service().evaluate_from_contract(contract, "CAP_INTEGRATION_READ_API", "read")
        assert decision.allowed is False
        assert decision.reason_code == CapabilityReasonCode.UNKNOWN_CAPABILITY.value

    def test_recovery_cta_from_customer_experience(self):
        contract = build_runtime_contract(
            client=_client(),
            billing=_billing(
                subscription_status="UNPAID",
                billing_lifecycle_state="expired",
                read_only_retention=True,
            ),
            now=NOW,
        )
        decision = _service().evaluate_from_contract(contract, "CAP_PROP_VIEW", "write")
        assert decision.allowed is False
        assert decision.recovery_route == "/settings/billing"

    def test_evaluate_all_from_contract(self):
        contract = _contract()
        decisions = _service().evaluate_all_from_contract(contract)
        assert len(decisions) == len(contract["capabilities"]) * 2


class TestCompatibilityMapping:
    @pytest.mark.asyncio
    async def test_feature_key_maps_to_capability(self):
        assert primary_capability_for_feature("reports_pdf") == "CAP_REPORT_GENERATE_PDF"
        assert "CAP_REPORT_DOWNLOAD" in feature_key_to_capabilities("reports_pdf")

    @pytest.mark.asyncio
    async def test_evaluate_feature_via_capability_blocks_when_cap_denied(self):
        contract = build_runtime_contract(
            client=_client(billing_plan="PLAN_1_SOLO"),
            billing=_billing(),
            now=NOW,
        )
        svc = _service()
        decision = await evaluate_feature_via_capability(svc, "c-enf-1", "reports_pdf", "write", contract=contract)
        assert decision.allowed is False


class TestCapabilityDeniedError:
    def test_to_detail_shape(self):
        contract = build_runtime_contract(
            client=_client(),
            billing=_billing(
                subscription_status="UNPAID",
                billing_lifecycle_state="expired",
                read_only_retention=True,
            ),
            now=NOW,
        )
        decision = _service().evaluate_from_contract(contract, "CAP_PROP_VIEW", "write")
        err = CapabilityDeniedError(decision)
        detail = err.to_detail()
        assert detail["error"] == "capability_denied"
        assert detail["capability_id"] == "CAP_PROP_VIEW"
        assert detail["reason_code"] == CapabilityReasonCode.READ_ONLY_BLOCKED.value
