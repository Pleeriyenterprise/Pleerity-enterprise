"""
Integration tests for subscription state gating (CANCELED / PAST_DUE / UNPAID) and downgrade reconciliation.

Ensures:
- Pro client with subscription_status CANCELED/PAST_DUE/UNPAID gets 403 SUBSCRIPTION_INACTIVE on gated features.
- Plan reconciliation disables scheduled reports, SMS prefs, tenant access, white-label on downgrade/cancel.
- Job runner skips scheduled reports and SMS when plan/subscription does not allow.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


@pytest.mark.asyncio
async def test_enforce_feature_returns_subscription_inactive_when_canceled():
    """Client with billing_plan=PLAN_3_PRO but subscription_status=CANCELED → enforce_feature denies with SUBSCRIPTION_INACTIVE."""
    from services.plan_registry import plan_registry

    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value={
        "client_id": "client-pro-canceled",
        "billing_plan": "PLAN_3_PRO",
        "subscription_status": "CANCELED",
    })
    with patch("services.plan_registry.database.get_db", return_value=db):
        allowed, msg, details = await plan_registry.enforce_feature("client-pro-canceled", "reports_pdf")
    assert allowed is False
    assert details is not None
    assert details.get("error_code") == "SUBSCRIPTION_INACTIVE"
    assert "CANCELED" in (msg or "")


@pytest.mark.asyncio
async def test_enforce_feature_returns_subscription_inactive_when_past_due():
    """Client with subscription_status=PAST_DUE → enforce_feature denies."""
    from services.plan_registry import plan_registry

    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value={
        "client_id": "client-past-due",
        "billing_plan": "PLAN_3_PRO",
        "subscription_status": "PAST_DUE",
    })
    with patch("services.plan_registry.database.get_db", return_value=db):
        allowed, msg, details = await plan_registry.enforce_feature("client-past-due", "reports_csv")
    assert allowed is False
    assert details is not None
    assert details.get("error_code") == "SUBSCRIPTION_INACTIVE"


@pytest.mark.asyncio
async def test_enforce_feature_returns_subscription_inactive_when_unpaid():
    """Client with subscription_status=UNPAID → enforce_feature denies."""
    from services.plan_registry import plan_registry

    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value={
        "client_id": "client-unpaid",
        "billing_plan": "PLAN_3_PRO",
        "subscription_status": "UNPAID",
    })
    with patch("services.plan_registry.database.get_db", return_value=db):
        allowed, _, details = await plan_registry.enforce_feature("client-unpaid", "scheduled_reports")
    assert allowed is False
    assert details.get("error_code") == "SUBSCRIPTION_INACTIVE"


@pytest.mark.asyncio
async def test_reconcile_plan_change_disables_scheduled_reports_on_downgrade():
    """Reconcile when scheduled_reports no longer allowed: report_schedules set is_active=False, disabled_reason=PLAN_DOWNGRADE."""
    from services.plan_reconciliation_service import reconcile_plan_change

    db = MagicMock()
    db.report_schedules.update_many = AsyncMock(return_value=MagicMock(modified_count=2))
    db.notification_preferences.update_one = AsyncMock(return_value=MagicMock(modified_count=0))
    db.portal_users.update_many = AsyncMock(return_value=MagicMock(modified_count=0))
    db.branding_settings.update_one = AsyncMock(return_value=MagicMock(modified_count=0))
    with patch("services.plan_reconciliation_service.database.get_db", return_value=db):
        with patch("services.plan_reconciliation_service.create_audit_log", new_callable=AsyncMock):
            summary = await reconcile_plan_change(
                client_id="c1",
                old_plan="PLAN_3_PRO",
                new_plan="PLAN_1_SOLO",
                reason="stripe_webhook",
                subscription_status="ACTIVE",
            )
    assert any(a.get("feature") == "scheduled_reports" and a.get("action") == "disabled" for a in summary["actions"])
    call = db.report_schedules.update_many.call_args
    assert call[0][1]["$set"]["is_active"] is False
    assert call[0][1]["$set"]["disabled_reason"] == "PLAN_DOWNGRADE"


@pytest.mark.asyncio
async def test_reconcile_plan_change_revokes_tenant_access_on_downgrade():
    """Reconcile when tenant_portal no longer allowed: portal_users (ROLE_TENANT) set status=DISABLED."""
    from services.plan_reconciliation_service import reconcile_plan_change

    db = MagicMock()
    db.report_schedules.update_many = AsyncMock(return_value=MagicMock(modified_count=0))
    db.notification_preferences.update_one = AsyncMock(return_value=MagicMock(modified_count=0))
    db.portal_users.update_many = AsyncMock(return_value=MagicMock(modified_count=3))
    db.branding_settings.update_one = AsyncMock(return_value=MagicMock(modified_count=0))
    with patch("services.plan_reconciliation_service.database.get_db", return_value=db):
        with patch("services.plan_reconciliation_service.create_audit_log", new_callable=AsyncMock):
            summary = await reconcile_plan_change(
                client_id="c1",
                old_plan="PLAN_3_PRO",
                new_plan="PLAN_1_SOLO",
                reason="stripe_webhook",
                subscription_status="ACTIVE",
            )
    assert any(a.get("feature") == "tenant_portal" for a in summary["actions"])
    call = db.portal_users.update_many.call_args
    filter_arg = call[0][0]
    update_arg = call[0][1]
    assert filter_arg.get("role") == "ROLE_TENANT"
    assert filter_arg.get("client_id") == "c1"
    assert update_arg["$set"]["status"] == "DISABLED"
    assert update_arg["$set"]["revoked_reason"] == "PLAN_DOWNGRADE"


@pytest.mark.asyncio
async def test_reconcile_subscription_deleted_treats_no_paid_features():
    """Reconcile with new_plan=None (subscription deleted): all corrective actions applied."""
    from services.plan_reconciliation_service import reconcile_plan_change

    db = MagicMock()
    db.report_schedules.update_many = AsyncMock(return_value=MagicMock(modified_count=1))
    db.notification_preferences.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db.portal_users.update_many = AsyncMock(return_value=MagicMock(modified_count=0))
    db.branding_settings.update_one = AsyncMock(return_value=MagicMock(modified_count=0))
    with patch("services.plan_reconciliation_service.database.get_db", return_value=db):
        with patch("services.plan_reconciliation_service.create_audit_log", new_callable=AsyncMock):
            summary = await reconcile_plan_change(
                client_id="c1",
                old_plan="PLAN_3_PRO",
                new_plan=None,
                reason="stripe_webhook",
                subscription_status="CANCELED",
            )
    assert summary["new_plan"] is None
    assert summary["subscription_status"] == "CANCELED"
    assert db.report_schedules.update_many.called
    assert db.notification_preferences.update_one.called


@pytest.mark.asyncio
async def test_scheduled_report_job_skips_when_enforce_feature_denies():
    """Scheduled report job: when enforce_feature('scheduled_reports') denies, skip and do not send."""
    from services.jobs import ScheduledReportJob
    from datetime import datetime, timezone

    db = MagicMock()
    db.report_schedules.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[
        {"schedule_id": "s1", "client_id": "c1", "report_type": "compliance_summary", "frequency": "weekly",
         "recipients": ["a@b.co"], "next_scheduled": datetime.now(timezone.utc).isoformat()},
    ])))
    db.clients.find_one = AsyncMock(return_value={
        "client_id": "c1", "subscription_status": "ACTIVE", "entitlement_status": "ENABLED",
        "email": "a@b.co", "full_name": "Test",
    })
    db.message_logs.insert_one = AsyncMock()
    job = ScheduledReportJob(db)
    mock_registry = MagicMock()
    mock_registry.enforce_feature = AsyncMock(return_value=(False, "Subscription inactive", {"error_code": "SUBSCRIPTION_INACTIVE"}))
    with patch("services.plan_registry.plan_registry", mock_registry):
        with patch("services.jobs.create_audit_log", new_callable=AsyncMock):
            count = await job.process_scheduled_reports()
    assert count == 0
    mock_registry.enforce_feature.assert_called_once_with("c1", "scheduled_reports")
    db.report_schedules.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_enforce_property_limit_denies_over_cap():
    """enforce_property_limit: client on Solo with 2 properties, request 1 more → denied."""
    from services.plan_registry import plan_registry

    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "billing_plan": "PLAN_1_SOLO"})
    with patch("services.plan_registry.database.get_db", return_value=db):
        allowed, msg, details = await plan_registry.enforce_property_limit("c1", 3)
    assert allowed is False
    assert details is not None
    assert details.get("error_code") == "PROPERTY_LIMIT_EXCEEDED"
    assert details.get("current_limit") == 2
    assert details.get("requested_count") == 3


@pytest.mark.asyncio
async def test_enforce_property_limit_allows_at_cap():
    """enforce_property_limit: client on Solo with 2 requested → allowed."""
    from services.plan_registry import plan_registry

    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "billing_plan": "PLAN_1_SOLO"})
    with patch("services.plan_registry.database.get_db", return_value=db):
        allowed, _, _ = await plan_registry.enforce_property_limit("c1", 2)
    assert allowed is True
