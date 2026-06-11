"""Manual job execution scope governance."""
import pytest

from services.job_execution_governance import (
    ExecutionRequest,
    ExecutionScopeType,
    build_job_kwargs_for_run,
    get_allowed_scopes,
    get_governance_matrix,
    infer_scope_type,
    ResolvedExecution,
    validate_execution_request,
    validate_scope_for_job,
)


def test_monthly_digest_allowed_scopes():
    scopes = get_allowed_scopes("monthly_digest")
    assert ExecutionScopeType.CLIENT in scopes
    assert ExecutionScopeType.PORTFOLIO_WIDE in scopes
    assert ExecutionScopeType.PROPERTY not in scopes


def test_risk_signals_job_property_and_client_only():
    scopes = get_allowed_scopes("risk_signals_job")
    assert scopes == [ExecutionScopeType.CLIENT, ExecutionScopeType.PROPERTY]


def test_global_only_job_portfolio_wide_only():
    scopes = get_allowed_scopes("pending_verification_digest")
    assert scopes == [ExecutionScopeType.PORTFOLIO_WIDE]


def test_validate_rejects_unsupported_scope():
    req = ExecutionRequest(
        scope_type=ExecutionScopeType.PROPERTY,
        property_id="p1",
        reason="support reason text",
    )
    err = validate_execution_request("monthly_digest", req)
    assert err is not None
    assert "does not support scope" in err


def test_validate_portfolio_wide_requires_confirmation():
    req = ExecutionRequest(
        scope_type=ExecutionScopeType.PORTFOLIO_WIDE,
        portfolio_wide=True,
        portfolio_wide_confirmed=False,
        reason="support reason text",
    )
    err = validate_execution_request("monthly_digest", req)
    assert err is not None
    assert "portfolio_wide_confirmed" in err


def test_validate_client_scope_ok():
    req = ExecutionRequest(
        scope_type=ExecutionScopeType.CLIENT,
        client_id="c1",
        reason="support reason text",
    )
    assert validate_execution_request("monthly_digest", req) is None


def test_infer_scope_from_client_id():
    assert infer_scope_type(
        scope_type=None,
        client_id="c1",
        property_id=None,
        client_ids=None,
        plan_code=None,
        jurisdiction=None,
        cohort_filter=None,
        portfolio_wide=False,
    ) == ExecutionScopeType.CLIENT


def test_build_job_kwargs_single_client():
    resolved = ResolvedExecution(
        scope_type=ExecutionScopeType.CLIENT,
        client_ids=["c1"],
    )
    kw = build_job_kwargs_for_run("daily_reminders", resolved)
    assert kw == {"client_id": "c1"}


def test_build_job_kwargs_property_recalc():
    resolved = ResolvedExecution(
        scope_type=ExecutionScopeType.PROPERTY,
        property_id="p1",
    )
    kw = build_job_kwargs_for_run("compliance_recalc_enqueue_property", resolved)
    assert kw == {"property_id": "p1"}


def test_governance_matrix_classification():
    matrix = get_governance_matrix()
    assert matrix["classification"] == "MANUAL_JOB_GOVERNANCE_CONVERGED"
    job_ids = {row["job_id"] for row in matrix["jobs"]}
    assert "monthly_digest" in job_ids
    assert "daily_reminders" in job_ids
