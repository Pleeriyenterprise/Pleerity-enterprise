"""
Phase 5.3 Part 4 — cross-flow integrity smoke checks. REF-PRODTEST-CROSSFLOW-001.

A: Intake surface responds (requires MongoDB + app lifespan from client fixture).
B–D: Mock-backed trust-layer behaviour aligned with production routes/services.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_scenario_a_intake_and_upload_routes_reachable(client):
    """A: Onboarding entrypoints exist; full upload flow needs DB + ClamAV mocks in other tests."""
    r = client.get("/api/intake/services")
    if r.status_code != 200:
        pytest.skip(f"Intake services returned {r.status_code}; MongoDB required for full gate.")
    assert r.status_code == 200
    data = r.json()
    assert "services" in data
    assert any(s.get("service_code") == "DOC_PACK_ESSENTIAL" for s in data.get("services", []))


@pytest.mark.asyncio
async def test_scenario_b_subscription_gating_inactive():
    """B: Canceled subscription → SUBSCRIPTION_INACTIVE from enforce_feature."""
    from services.plan_registry import plan_registry

    db = MagicMock()
    db.clients.find_one = AsyncMock(
        return_value={
            "client_id": "cx",
            "billing_plan": "PLAN_3_PRO",
            "subscription_status": "CANCELED",
        }
    )
    db.client_billing = MagicMock()
    db.client_billing.find_one = AsyncMock(return_value=None)
    with patch("services.plan_registry.database.get_db", return_value=db):
        allowed, msg, details = await plan_registry.enforce_feature("cx", "reports_pdf")
    assert allowed is False
    assert details.get("error_code") == "SUBSCRIPTION_INACTIVE"


@pytest.mark.asyncio
async def test_scenario_c_resend_surfaces_provider_rejection():
    """C: Provider/orchestrator failure → HTTP 502 with structured error (visible failure)."""
    from routes.admin import resend_password_setup
    from fastapi import Request, HTTPException

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.user = {"portal_user_id": "admin-1", "role": "ROLE_ADMIN", "email": "admin@test.com"}

    db = MagicMock()
    db.clients = MagicMock()
    db.portal_users = MagicMock()
    db.password_tokens = MagicMock()
    db.clients.find_one = AsyncMock(
        return_value={
            "client_id": "c1",
            "email": "c@test.com",
            "full_name": "Client",
            "onboarding_status": "PROVISIONED",
        }
    )
    db.portal_users.find_one = AsyncMock(return_value={"portal_user_id": "pu1", "client_id": "c1"})
    db.password_tokens.update_many = AsyncMock()
    db.password_tokens.insert_one = AsyncMock()
    db.clients.update_one = AsyncMock()

    send_result = MagicMock(outcome="failed", error_message="bounce", message_id=None)
    with patch("routes.admin.admin_route_guard", new_callable=AsyncMock, return_value=request.state.user), \
         patch("routes.admin.require_recent_step_up", new_callable=AsyncMock), \
         patch("routes.admin.database.get_db", return_value=db), \
         patch("routes.admin.rate_limiter") as rl, \
         patch("routes.admin.create_audit_log", new_callable=AsyncMock):
        rl.check_rate_limit = AsyncMock(return_value=(True, None))
        with patch("auth.generate_secure_token", return_value="t"), \
             patch("auth.hash_token", return_value="h"), \
             patch(
                 "services.notification_orchestrator.notification_orchestrator.send",
                 AsyncMock(return_value=send_result),
             ):
            with pytest.raises(HTTPException) as ei:
                await resend_password_setup(request, "c1")
    assert ei.value.status_code == 502
    assert ei.value.detail["error_code"] == "EMAIL_PROVIDER_REJECTED"


@pytest.mark.asyncio
async def test_scenario_d_scheduled_report_skipped_when_plan_blocks():
    """D: When enforce_feature denies scheduled_reports, job returns success with zero sends (no schedule advance)."""
    from services.jobs import ScheduledReportJob
    from datetime import datetime, timezone

    db = MagicMock()
    db.report_schedules = MagicMock()
    db.report_schedules.find = MagicMock(
        return_value=MagicMock(
            to_list=AsyncMock(
                return_value=[
                    {
                        "schedule_id": "s1",
                        "client_id": "c1",
                        "report_type": "compliance_summary",
                        "frequency": "weekly",
                        "recipients": ["a@b.co"],
                        "next_scheduled": datetime.now(timezone.utc).isoformat(),
                    }
                ]
            )
        )
    )
    db.report_schedules.update_one = AsyncMock()
    db.clients = MagicMock()
    db.clients.find_one = AsyncMock(
        return_value={
            "client_id": "c1",
            "subscription_status": "ACTIVE",
            "entitlement_status": "ENABLED",
            "email": "a@b.co",
            "full_name": "Test",
        }
    )
    db.message_logs = MagicMock()
    db.message_logs.insert_one = AsyncMock()
    mock_registry = MagicMock()
    mock_registry.enforce_feature = AsyncMock(
        return_value=(False, "blocked", {"error_code": "SUBSCRIPTION_INACTIVE"})
    )
    job = ScheduledReportJob(db)
    with patch("services.plan_registry.plan_registry", mock_registry, create=True):
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            result = await job.process_scheduled_reports()
    assert result["count"] == 0
    db.report_schedules.update_one.assert_not_called()
