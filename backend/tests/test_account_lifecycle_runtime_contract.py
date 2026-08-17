"""Unit tests for Account Lifecycle Runtime Contract (ILP-2)."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from services.account_lifecycle_runtime_contract import (
    CONTRACT_VERSION,
    RUNTIME_BUILD_ID,
    build_runtime_contract,
    compare_runtime_with_legacy,
    get_cached_runtime_contract,
    resolve_capabilities,
    resolve_portal_mode,
    runtime_contract_to_dict,
)

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
GRACE_END = datetime(2026, 6, 20, 0, 0, 0, tzinfo=timezone.utc)


def _build(client=None, billing=None, **kwargs):
    return build_runtime_contract(client=client, billing=billing, now=NOW, **kwargs)


def _dict(contract):
    return runtime_contract_to_dict(contract)


def _required_fields(payload):
    for field in (
        "contract_version",
        "runtime_version",
        "client_id",
        "resolved_at",
        "lifecycle_state",
        "portal_mode",
        "capabilities",
        "plan",
        "customer_experience",
        "background_policy",
        "communication_policy",
        "session_policy",
        "polling_policy",
    ):
        assert field in payload, field


def test_runtime_generation_active():
    client = {"client_id": "c1", "billing_plan": "PLAN_2_PORTFOLIO", "client_lifecycle_status": "ACTIVE"}
    billing = {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}
    payload = _dict(_build(client=client, billing=billing))
    _required_fields(payload)
    assert payload["lifecycle_state"] == "ACTIVE"
    assert payload["portal_mode"] == "FULL_ACCESS"
    assert payload["contract_version"] == CONTRACT_VERSION


def test_portal_mode_trialing():
    billing = {"subscription_status": "TRIALING", "billing_lifecycle_state": "active"}
    assert resolve_portal_mode("TRIAL") == "FULL_ACCESS"
    payload = _dict(_build(billing=billing))
    assert payload["portal_mode"] == "FULL_ACCESS"
    assert payload["lifecycle_state"] == "TRIAL"


def test_portal_mode_cancelled():
    billing = {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"}
    payload = _dict(_build(billing=billing))
    assert payload["portal_mode"] == "BILLING_RECOVERY"
    assert payload["lifecycle_state"] == "CANCELLED_IMMEDIATE"


def test_capability_generation_active():
    caps = resolve_capabilities("ACTIVE", "FULL_ACCESS", {"reports_pdf": True, "scheduled_reports": True})
    assert caps["CAP_PROP_VIEW"] == "ALLOW"
    assert caps["CAP_REPORT_GENERATE_PDF"] == "ALLOW"


def test_capability_plan_gated_denied():
    caps = resolve_capabilities("ACTIVE", "FULL_ACCESS", {"reports_pdf": False})
    assert caps["CAP_REPORT_GENERATE_PDF"] == "DENY"


def test_policy_generation_background():
    payload = _dict(_build(billing={"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"}))
    assert payload["background_policy"]["scheduled_reports"] == "REVOKE"
    assert payload["communication_policy"]["email_billing"] is True
    assert payload["navigation_policy"]["landing_route"] == "/settings/billing"


def test_version_metadata():
    payload = _dict(_build(billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}))
    assert payload["contract_version"] == CONTRACT_VERSION
    assert isinstance(payload["runtime_version"], int)
    assert payload["runtime_version"] >= 1
    assert payload["policy_pins"]["lifecycle_policy"] == "account_lifecycle_policy_v1"
    assert payload["resolver_metadata"]["runtime_build_id"] == RUNTIME_BUILD_ID


def test_unknown_state():
    billing = {"subscription_status": "WEIRD", "billing_lifecycle_state": "active"}
    payload = _dict(_build(billing=billing))
    assert payload["lifecycle_state"] == "UNKNOWN"
    assert payload["portal_mode"] == "BILLING_RECOVERY"


def test_legacy_state():
    client = {"lifecycle_status": "abandoned", "onboarding_status": "INTAKE_PENDING"}
    payload = _dict(_build(client=client))
    assert payload["lifecycle_state"] == "LEGACY"
    assert payload["portal_mode"] == "READ_ONLY"


def test_read_only_state():
    billing = {"subscription_status": "UNPAID", "billing_lifecycle_state": "expired", "read_only_retention": True}
    payload = _dict(_build(billing=billing))
    assert payload["lifecycle_state"] == "READ_ONLY"
    assert payload["portal_mode"] == "READ_ONLY"
    assert payload["capabilities"]["CAP_PROP_VIEW"] == "READ"


def test_deleted_account():
    client = {"client_id": "c-del", "purged_at": NOW.isoformat()}
    payload = _dict(_build(client=client))
    assert payload["lifecycle_state"] == "ACCOUNT_DELETED"
    assert payload["portal_mode"] == "ACCOUNT_DELETED"
    assert payload["capabilities"]["CAP_AUTH_LOGIN"] == "DENY"


def test_archived_account():
    client = {"is_deleted": True, "client_lifecycle_status": "ARCHIVED"}
    billing = {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}
    payload = _dict(_build(client=client, billing=billing))
    assert payload["lifecycle_state"] == "ARCHIVED"
    assert payload["portal_mode"] == "ARCHIVED"


def test_suspended_account():
    client = {"client_lifecycle_status": "SUSPENDED"}
    billing = {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}
    payload = _dict(_build(client=client, billing=billing))
    assert payload["lifecycle_state"] == "SUSPENDED"
    assert payload["portal_mode"] == "SUSPENDED"


def test_grace_period():
    billing = {
        "subscription_status": "PAST_DUE",
        "billing_lifecycle_state": "grace_period",
        "grace_period_ends_at": GRACE_END.isoformat(),
    }
    payload = _dict(_build(billing=billing))
    assert payload["lifecycle_state"] == "GRACE_PERIOD"
    assert payload["portal_mode"] == "GRACE"
    assert payload["background_policy"]["scheduled_reports"] == "CONTINUE"


def test_cancellation_scheduled():
    billing = {
        "subscription_status": "ACTIVE",
        "billing_lifecycle_state": "cancel_at_period_end",
        "cancel_at_period_end": True,
        "current_period_end": PERIOD_END.isoformat(),
    }
    payload = _dict(_build(billing=billing))
    assert payload["lifecycle_state"] == "CANCELLATION_SCHEDULED"
    assert payload["portal_mode"] == "FULL_ACCESS"
    assert "Cancellation scheduled" in payload["customer_experience"]["heading"]


def test_immediate_cancellation():
    billing = {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"}
    payload = _dict(_build(billing=billing))
    assert payload["lifecycle_state"] == "CANCELLED_IMMEDIATE"
    assert payload["reactivation_policy"]["eligible"] is True


def test_trial_expired():
    billing = {"subscription_status": "INCOMPLETE_EXPIRED", "billing_lifecycle_state": "expired"}
    payload = _dict(_build(billing=billing))
    assert payload["lifecycle_state"] == "TRIAL_EXPIRED"
    assert payload["portal_mode"] == "PAYMENT_REQUIRED"


def test_capability_overlays_billing_recovery():
    billing = {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"}
    payload = _dict(_build(billing=billing))
    assert payload["capabilities"]["CAP_BILLING_VIEW"] == "ALLOW"
    assert payload["capabilities"]["CAP_PROP_VIEW"] == "READ"
    assert payload["capabilities"]["CAP_PROP_EDIT"] == "DENY"


def test_plan_overlay():
    client = {"billing_plan": "PLAN_1_SOLO"}
    billing = {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}
    payload = _dict(_build(client=client, billing=billing))
    assert "plan_code" in payload["plan"]
    assert isinstance(payload["plan"]["plan_features"], dict)


def test_missing_billing_record():
    client = {"client_id": "c1", "subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}
    payload = _dict(_build(client=client))
    assert payload["lifecycle_state"] == "ACTIVE"
    assert "missing_billing_record" in payload["warnings"]


def test_conflicting_billing_facts():
    billing = {
        "subscription_status": "ACTIVE",
        "billing_lifecycle_state": "cancelled",
        "canonical_entitlement_state": "CANCELLED",
    }
    payload = _dict(_build(billing=billing))
    assert payload["lifecycle_state"] == "UNKNOWN"


def test_runtime_immutability():
    contract = _build(billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"})
    assert isinstance(contract, MappingProxyType)
    with pytest.raises(TypeError):
        contract["lifecycle_state"] = "SUSPENDED"  # type: ignore[index]


def test_runtime_idempotency():
    client = {"client_id": "c1", "billing_plan": "PLAN_2_PORTFOLIO"}
    billing = {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}
    a = _dict(_build(client=copy.deepcopy(client), billing=copy.deepcopy(billing)))
    b = _dict(_build(client=copy.deepcopy(client), billing=copy.deepcopy(billing)))
    assert a["runtime_version"] == b["runtime_version"]
    assert a["lifecycle_state"] == b["lifecycle_state"]
    assert a["capabilities"] == b["capabilities"]


def test_json_serialization():
    payload = _dict(_build(billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}))
    text = json.dumps(payload)
    roundtrip = json.loads(text)
    assert roundtrip["contract_version"] == CONTRACT_VERSION


def test_cache_safety():
    client = {"client_id": "cache-c", "billing_plan": "PLAN_1_SOLO"}
    billing = {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}
    contract = _build(client=client, billing=billing)
    from services.account_lifecycle_runtime_contract import _runtime_cache

    _runtime_cache["cache-c"] = (9999999999.0, contract["runtime_version"], contract)
    cached = get_cached_runtime_contract("cache-c", contract["runtime_version"])
    assert cached is not None
    assert get_cached_runtime_contract("cache-c", contract["runtime_version"] + 1) is None


def test_schema_validation_required_enums():
    payload = _dict(_build(billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}))
    assert payload["portal_mode"] in (
        "FULL_ACCESS",
        "READ_ONLY",
        "BILLING_RECOVERY",
        "PAYMENT_REQUIRED",
        "GRACE",
        "SUSPENDED",
        "ARCHIVED",
        "ACCOUNT_DELETED",
    )
    for grant in payload["capabilities"].values():
        assert grant in ("ALLOW", "READ", "DENY", "HIDDEN", "PLAN_GATED", "LIMITED")


def test_read_only_diagnostics():
    billing = {
        "subscription_status": "UNPAID",
        "billing_lifecycle_state": "expired",
        "canonical_entitlement_state": "ENABLED",
    }
    contract = _build(billing=billing)
    drift = compare_runtime_with_legacy(contract)
    assert drift["drift_flags"]


def test_polling_disabled_terminal_modes():
    billing = {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"}
    payload = _dict(_build(billing=billing))
    assert payload["polling_policy"]["enabled"] is False


def test_regression_no_middleware_import_in_service():
    import services.account_lifecycle_runtime_contract as mod

    source = open(mod.__file__, encoding="utf-8").read()
    assert "from middleware" not in source
    assert "import middleware" not in source
    assert "hasFeature" not in source
    assert "FEATURE_MATRIX" not in source


def test_api_route_module_exists():
    from routes import client_lifecycle_runtime

    paths = [getattr(r, "path", "") for r in client_lifecycle_runtime.router.routes]
    assert "/api/client/lifecycle-runtime" in paths
    assert "/api/client/lifecycle-contract" in paths


def test_cancelled_with_commercial_overlay_preserves_lifecycle_and_grants_plan_access():
    client = {
        "client_id": "c-cancel-overlay",
        "billing_plan": "PLAN_3_PRO",
        "commercial_effective_entitlement_state": "ENABLED",
        "commercial_restored_plan_code": "PLAN_3_PRO",
        "commercial_governance_id": "gov-suspend-1",
        "commercial_governance_state": "BILLING_SUSPENDED",
    }
    billing = {
        "subscription_status": "CANCELED",
        "billing_lifecycle_state": "cancelled",
        "canonical_entitlement_state": "CANCELLED",
        "commercial_effective_entitlement_state": "ENABLED",
        "commercial_restored_plan_code": "PLAN_3_PRO",
    }
    payload = _dict(_build(client=client, billing=billing))
    assert payload["lifecycle_state"] == "CANCELLED_IMMEDIATE"
    assert payload["portal_mode"] == "FULL_ACCESS"
    assert payload["commercial_exception"]["active"] is True
    assert payload["commercial_exception"]["restored_plan_code"] == "PLAN_3_PRO"
    assert payload["commercial_exception"]["underlying_lifecycle_state"] == "CANCELLED_IMMEDIATE"
    assert payload["plan"]["plan_code"] == "PLAN_3_PRO"
    assert payload["capabilities"].get("CAP_PROP_VIEW") != "DENY"
