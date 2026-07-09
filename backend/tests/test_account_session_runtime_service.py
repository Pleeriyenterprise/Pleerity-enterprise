"""Tests for ILP-5 session runtime authority service."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.account_lifecycle_runtime_contract import build_runtime_contract
from services.account_session_runtime_service import (
    SessionRefreshAction,
    SessionRuntimeState,
    build_client_auth_claims,
    validate_session_against_contract,
)

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _contract(lifecycle="ACTIVE", billing=None, client=None, entitlements_version=3):
    client = client or {
        "client_id": "c-sess",
        "billing_plan": "PLAN_3_PRO",
        "entitlements_version": entitlements_version,
    }
    billing = billing or {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}
    return build_runtime_contract(
        client=client,
        billing=billing,
        now=NOW,
        entitlements_version=entitlements_version,
    )


def test_build_client_auth_claims_contains_version_hints_not_capabilities():
    contract = _contract()
    portal_user = {
        "portal_user_id": "pu-1",
        "client_id": "c-sess",
        "auth_email": "a@example.com",
        "role": "ROLE_CLIENT",
        "session_version": 2,
    }
    claims = build_client_auth_claims(portal_user, contract, session_id="sess-abc")
    assert claims["session_id"] == "sess-abc"
    assert claims["runtime_version"] == contract["runtime_version"]
    assert claims["entitlements_version"] == 3
    assert "capabilities" not in claims
    assert "CAP_" not in str(claims)


def test_validate_continue_when_versions_match():
    contract = _contract()
    jwt = {
        "runtime_version": contract["runtime_version"],
        "entitlements_version": 3,
        "contract_version": contract["contract_version"],
        "session_id": "sess-1",
    }
    session_record = {
        "session_id": "sess-1",
        "runtime_version": contract["runtime_version"],
        "entitlements_version": 3,
        "lifecycle_state": contract["lifecycle_state"],
        "portal_mode": contract["portal_mode"],
    }
    result = validate_session_against_contract(jwt, contract, session_record=session_record)
    assert result.action == SessionRefreshAction.CONTINUE
    assert result.session_state == SessionRuntimeState.ACTIVE
    assert result.force_refresh is False


def test_validate_refresh_when_runtime_version_changed():
    contract = _contract()
    jwt = {"runtime_version": 1, "entitlements_version": 3, "contract_version": contract["contract_version"]}
    result = validate_session_against_contract(jwt, contract)
    assert result.action == SessionRefreshAction.REFRESH_RUNTIME
    assert "runtime_version_changed" in result.reasons
    assert result.force_refresh is True


def test_validate_refresh_token_when_entitlements_changed():
    contract = _contract()
    jwt = {
        "runtime_version": contract["runtime_version"],
        "entitlements_version": 1,
        "contract_version": contract["contract_version"],
    }
    result = validate_session_against_contract(jwt, contract)
    assert result.action == SessionRefreshAction.REFRESH_TOKEN
    assert "entitlements_version_changed" in result.reasons


def test_validate_force_reauth_on_account_deleted():
    contract = _contract(
        client={
            "client_id": "c-sess",
            "billing_plan": "PLAN_3_PRO",
            "purged_at": NOW.isoformat(),
        },
    )
    result = validate_session_against_contract({}, contract)
    assert result.action == SessionRefreshAction.FORCE_REAUTH
    assert result.session_state == SessionRuntimeState.FORCE_REAUTH


@pytest.mark.parametrize(
    "lifecycle,billing,client_extra",
    [
        ("ACTIVE", {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}, {}),
        (
            "CANCELLED_IMMEDIATE",
            {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"},
            {},
        ),
        (
            "READ_ONLY",
            {"subscription_status": "UNPAID", "billing_lifecycle_state": "expired", "read_only_retention": True},
            {"read_only_retention": True},
        ),
        ("SUSPENDED", {"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"}, {"client_lifecycle_status": "SUSPENDED"}),
    ],
)
def test_lifecycle_transition_version_hints_change_without_capability_in_jwt(lifecycle, billing, client_extra):
    client = {"client_id": "c-sess", "billing_plan": "PLAN_3_PRO", "entitlements_version": 5, **client_extra}
    contract = build_runtime_contract(
        client=client,
        billing=billing,
        now=NOW,
        entitlements_version=5,
    )
    claims = build_client_auth_claims(
        {"portal_user_id": "pu", "client_id": "c-sess", "auth_email": "x@y.com", "role": "ROLE_CLIENT"},
        contract,
        session_id="s1",
    )
    assert claims["runtime_version"] == contract["runtime_version"]
    assert contract["lifecycle_state"] == lifecycle
    assert "capabilities" not in claims
