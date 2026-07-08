"""P0 lifecycle recovery UX — governed customer copy (no CAP_* in customer messages)."""
from __future__ import annotations

import pytest

from services.account_capability_enforcement import CapabilityEnforcementService
from services.account_lifecycle_runtime_contract import GRANT_DENY, build_runtime_contract
from services.lifecycle_recovery_customer_copy import (
    capability_denial_customer_message,
    contains_internal_capability_language,
    is_lifecycle_restricted_portal_mode,
)
from tests.test_account_capability_enforcement import NOW, _billing, _client


class TestLifecycleRecoveryCustomerCopy:
    def test_suspended_portal_mode_message_has_no_cap_ids(self):
        msg = capability_denial_customer_message(portal_mode="SUSPENDED", grant=GRANT_DENY, action="read")
        assert "CAP_" not in msg
        assert "suspended" in msg.lower()
        assert "resolve payment" in msg.lower()

    def test_plan_gated_full_access_message_has_no_cap_ids(self):
        msg = capability_denial_customer_message(portal_mode="FULL_ACCESS", grant="PLAN_GATED", action="read")
        assert "CAP_" not in msg
        assert "plan" in msg.lower()

    @pytest.mark.parametrize(
        "portal_mode",
        ["SUSPENDED", "BILLING_RECOVERY", "PAYMENT_REQUIRED", "GRACE", "READ_ONLY", "ARCHIVED", "ACCOUNT_DELETED"],
    )
    def test_restricted_portal_modes_are_lifecycle_restricted(self, portal_mode):
        assert is_lifecycle_restricted_portal_mode(portal_mode) is True

    def test_full_access_is_not_lifecycle_restricted(self):
        assert is_lifecycle_restricted_portal_mode("FULL_ACCESS") is False

    def test_internal_capability_language_detector(self):
        assert contains_internal_capability_language("CAP_PROP_VIEW is not permitted for your account status.")
        assert contains_internal_capability_language("Access requires CAP_TODAY_VIEW on your account.")
        assert not contains_internal_capability_language("Resolve payment in Billing to restore access.")


class TestCapabilityEnforcementCustomerMessages:
    def test_suspended_contract_denial_uses_customer_copy(self):
        contract = build_runtime_contract(
            client=_client(client_lifecycle_status="SUSPENDED"),
            billing=_billing(subscription_status="ACTIVE", billing_lifecycle_state="active"),
            now=NOW,
        )
        decision = CapabilityEnforcementService(None).evaluate_from_contract(contract, "CAP_PROP_VIEW", "read")
        assert decision.allowed is False
        assert "CAP_" not in decision.reason
        assert "suspended" in decision.reason.lower()

    def test_suspended_customer_experience_has_no_duplicate_support_lines(self):
        contract = build_runtime_contract(
            client=_client(client_lifecycle_status="SUSPENDED"),
            billing=_billing(subscription_status="ACTIVE", billing_lifecycle_state="active"),
            now=NOW,
        )
        cx = contract["customer_experience"]
        assert cx["recovery_guidance"]
        assert cx["support_guidance"] == ""
        assert cx["secondary_cta"]["label"] == "Contact support"
