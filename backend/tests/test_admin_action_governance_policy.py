import pytest
from fastapi.testclient import TestClient

from middleware import admin_route_guard, require_owner_or_admin
from server import app
from services.admin_action_governance import (
    _REGISTRY_PATH,
    get_admin_action_policy,
    normalized_admin_action_metadata,
)


EXPECTED_ACTIONS = {
    "start_impersonation",
    "run_subscription_lifecycle_batch",
    "run_stripe_reconcile_batch",
    "change_plan",
    "force_provision",
    "unlock_account",
    "retry_agreement_issuance",
    "backfill_evidence_match_batch",
}

# Full registry must stay in sync with frontend/src/config/adminActionPolicyRegistry.json.
# The five lifecycle_ops_* keys are intentional governed actions from
# AdminLifecycleOperationsPanel / routes/admin_lifecycle_operations.py, not accidental drift.
FULL_REGISTRY_ACTIONS = {
    "admin_cancel_subscription",
    "authority_backfill_p0_apply",
    "authority_backfill_p0_dry_run",
    "backfill_evidence_match_batch",
    "billing_recovery_admin_set_mode",
    "billing_recovery_bulk_resend",
    "billing_recovery_closeout",
    "billing_recovery_escalate",
    "billing_recovery_regenerate_checkout",
    "change_login_email",
    "change_plan",
    "commercial_entitlement_execute",
    "delete_admin_document",
    "force_provision",
    "link_unresolved_requirement",
    "onboarding_recovery_execute",
    "reconcile_subscription_payment_ledger",
    "reject_unresolved_document",
    "resolve_unresolved_scope",
    "retry_agreement_issuance",
    "retry_document_extraction",
    "run_portfolio_wide_job",
    "run_scoped_automation_job",
    "run_stripe_reconcile_batch",
    "run_subscription_lifecycle_batch",
    "seed_admin_remediation_probe",
    "start_impersonation",
    "unlock_account",
    "lifecycle_ops_refresh_runtime",
    "lifecycle_ops_reconcile_stripe",
    "lifecycle_ops_resume_subscription",
    "lifecycle_ops_mark_support_review",
    "lifecycle_ops_export_support_bundle",
}

REQUIRED_FIELDS = {
    "action_id",
    "risk_class",
    "operator_level",
    "requires_reason",
    "requires_confirmation",
    "requires_step_up",
    "affects_multiple_customers",
    "irreversible",
}


async def _override_admin_route_guard(_request):
    return {"portal_user_id": "a1", "role": "ROLE_ADMIN"}


async def _override_owner_or_admin(_request):
    return {"portal_user_id": "a1", "role": "ROLE_ADMIN"}


@pytest.fixture
def client():
    return TestClient(app)


def test_policy_registry_contains_phase1_actions():
    for action_id in EXPECTED_ACTIONS:
        policy = get_admin_action_policy(action_id)
        assert REQUIRED_FIELDS.issubset(set(policy.keys()))


def test_registry_action_ids_match_exactly_and_cannot_drift_silently():
    import json

    with _REGISTRY_PATH.open("r", encoding="utf-8") as f:
        registry = json.load(f)
    assert set(registry.keys()) == FULL_REGISTRY_ACTIONS
    assert EXPECTED_ACTIONS <= FULL_REGISTRY_ACTIONS
    for action_id, policy in registry.items():
        assert policy["action_id"] == action_id
        assert REQUIRED_FIELDS.issubset(set(policy.keys()))


def test_normalized_audit_metadata_contract_for_all_actions():
    for action_id in EXPECTED_ACTIONS:
        metadata = normalized_admin_action_metadata(action_id, "Incident verification reason")
        assert metadata["action_id"] == action_id
        assert "risk_class" in metadata
        assert "operator_level" in metadata
        assert metadata["support_reason"] == "Incident verification reason"
        assert "affects_multiple_customers" in metadata


@pytest.mark.parametrize(
    "endpoint,payload",
    [
        ("/api/admin/clients/c1/impersonation/start", {}),
        ("/api/admin/billing/jobs/subscription-lifecycle", {}),
        ("/api/admin/billing/jobs/stripe-subscription-reconcile", {}),
        (
            "/api/admin/billing/clients/c1/change-plan",
            {"plan_code": "PLAN_2_PORTFOLIO", "apply_at_period_end": True},
        ),
        ("/api/admin/billing/clients/c1/force-provision", {}),
        ("/api/admin/clients/c1/actions/unlock-account", {}),
        (
            "/api/admin/clients/c1/agreements/retry-issue",
            {"acceptance_id": "a1", "payment_reference": "pay_1"},
        ),
        ("/api/admin/documents/backfill-evidence-match", {"limit": 10, "dry_run": True}),
    ],
)
def test_governed_actions_require_reason(client, endpoint, payload):
    app.dependency_overrides[admin_route_guard] = _override_admin_route_guard
    app.dependency_overrides[require_owner_or_admin] = _override_owner_or_admin
    try:
        response = client.post(endpoint, json=payload)
    finally:
        app.dependency_overrides.pop(admin_route_guard, None)
        app.dependency_overrides.pop(require_owner_or_admin, None)
    assert response.status_code == 422
