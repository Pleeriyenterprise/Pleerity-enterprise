"""
Acceptance tests for provisioning enterprise hardening.

- Duplicate Stripe webhook → one stripe_event, one job, one CRN
- CRN assignment writes CRN_ASSIGNED audit exactly once
- Admin resend before PROVISIONED → 403 ACCOUNT_NOT_READY
- Login before PROVISIONED → 403 ACCOUNT_NOT_READY
- Observability endpoint returns correct provisioning job state
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


@pytest.mark.asyncio
async def test_duplicate_stripe_webhook_only_one_processing():
    """Duplicate Stripe event: only one stripe_event record, no second processing."""
    from services.stripe_webhook_service import StripeWebhookService
    import json

    payload = json.dumps({
        "id": "ev_dup_123",
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_1", "customer": "cus_1", "subscription": "sub_1", "metadata": {"client_id": "c1"}}},
    }).encode()
    event_id = "ev_dup_123"
    db = MagicMock()
    # First call: no existing. Second call: existing with PROCESSED.
    db.stripe_events.find_one = AsyncMock(side_effect=[
        None,
        {"event_id": event_id, "status": "PROCESSED"},
    ])
    db.stripe_events.insert_one = AsyncMock()
    db.stripe_events.update_one = AsyncMock()

    with patch("services.stripe_webhook_service.stripe.Webhook.construct_event") as construct:
        construct.return_value = json.loads(payload.decode())
    with patch("services.stripe_webhook_service.database.get_db", return_value=db):
        svc = StripeWebhookService()
        with patch.object(svc, "_handle_event", new_callable=AsyncMock) as handle:
            handle.return_value = {}
            ok1, msg1, _ = await svc.process_webhook(payload, "sig")
            ok2, msg2, _ = await svc.process_webhook(payload, "sig")
    assert ok1 is True and ok2 is True
    assert "Already processed" in msg2
    assert handle.await_count == 1


@pytest.mark.asyncio
async def test_duplicate_stripe_webhook_duplicate_insert_returns_already_processed():
    """When insert_one raises E11000 (race), webhook returns Already processed and does not run _handle_event."""
    from services.stripe_webhook_service import StripeWebhookService
    import json

    payload = json.dumps({
        "id": "ev_race_456",
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_1", "customer": "cus_1", "subscription": "sub_1", "metadata": {"client_id": "c1"}}},
    }).encode()
    db = MagicMock()
    db.stripe_events.find_one = AsyncMock(return_value=None)
    db.stripe_events.update_one = AsyncMock()
    db.stripe_events.insert_one = AsyncMock(side_effect=Exception("E11000 duplicate key error"))

    with patch("services.stripe_webhook_service.stripe.Webhook.construct_event") as construct:
        construct.return_value = json.loads(payload.decode())
    with patch("services.stripe_webhook_service.database.get_db", return_value=db):
        svc = StripeWebhookService()
        with patch.object(svc, "_handle_event", new_callable=AsyncMock) as handle:
            ok, msg, _ = await svc.process_webhook(payload, "sig")
    assert ok is True
    assert "Already processed" in msg
    handle.assert_not_called()


@pytest.mark.asyncio
async def test_crn_assignment_writes_audit_exactly_once():
    """CRN assignment writes CRN_ASSIGNED audit only when newly assigned; not when CRN already exists."""
    from services.crn_service import ensure_client_crn
    from models import AuditAction

    db = MagicMock()
    db.clients.find_one = AsyncMock(side_effect=[
        {"client_id": "c1", "customer_reference": None},
        {"client_id": "c1", "customer_reference": "PLE-CVP-2026-000001"},
    ])
    db.clients.update_one = AsyncMock()

    with patch("services.crn_service.database.get_db", return_value=db):
        with patch("services.crn_service.get_next_crn", new_callable=AsyncMock, return_value="PLE-CVP-2026-000001"):
            with patch("services.crn_service.create_audit_log", new_callable=AsyncMock) as audit:
                out = await ensure_client_crn("c1")
    assert out == "PLE-CVP-2026-000001"
    assert audit.await_count == 1
    assert getattr(audit.call_args[1]["action"], "value", str(audit.call_args[1]["action"])) == "CRN_ASSIGNED"

    # Second call: client already has CRN -> no audit
    db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "customer_reference": "PLE-CVP-2026-000001"})
    with patch("services.crn_service.database.get_db", return_value=db):
        with patch("services.crn_service.create_audit_log", new_callable=AsyncMock) as audit2:
            out2 = await ensure_client_crn("c1")
    assert out2 == "PLE-CVP-2026-000001"
    audit2.assert_not_called()


@pytest.mark.asyncio
async def test_admin_resend_before_provisioned_returns_403_account_not_ready():
    """Admin resend-password-setup when onboarding_status != PROVISIONED → 403 ACCOUNT_NOT_READY."""
    from fastapi import Request
    from routes.admin import resend_password_setup

    request = MagicMock(spec=Request)
    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "onboarding_status": "PROVISIONING"})

    with patch("routes.admin.admin_route_guard", new_callable=AsyncMock, return_value={"portal_user_id": "admin1"}):
        with patch("routes.admin.database.get_db", return_value=db):
            with patch("routes.admin.rate_limiter") as rl:
                rl.check_rate_limit = AsyncMock(return_value=(True, None))
                from fastapi import HTTPException
                try:
                    await resend_password_setup(request, "c1")
                except HTTPException as e:
                    assert e.status_code == 403
                    assert e.detail.get("error_code") == "ACCOUNT_NOT_READY"
                    assert "Provisioning" in e.detail.get("message", "")
                    return
    pytest.fail("Expected HTTPException 403")


@pytest.mark.asyncio
async def test_login_before_provisioned_returns_403_account_not_ready():
    """Login when onboarding_status != PROVISIONED → 403 with ACCOUNT_NOT_READY."""
    from fastapi import Request
    from routes.auth import login
    from models import OnboardingStatus, UserStatus, PasswordStatus, UserRole

    request = MagicMock(spec=Request)
    db = MagicMock()
    portal_user = {
        "portal_user_id": "u1",
        "client_id": "c1",
        "auth_email": "client@test.com",
        "role": UserRole.ROLE_CLIENT_ADMIN.value,
        "password_hash": "hashed",
        "status": UserStatus.ACTIVE.value,
        "password_status": PasswordStatus.SET.value,
        "session_version": 0,
    }
    client = {"client_id": "c1", "onboarding_status": OnboardingStatus.INTAKE_PENDING.value}
    db.portal_users.find_one = AsyncMock(return_value=portal_user)
    db.clients.find_one = AsyncMock(return_value=client)

    with patch("routes.auth.database.get_db", return_value=db):
        with patch("routes.auth.verify_password", return_value=True):
            with patch("routes.auth.create_audit_log", new_callable=AsyncMock):
                from fastapi import HTTPException
                try:
                    await login(request, type("C", (), {"email": "client@test.com", "password": "x"})())
                except HTTPException as e:
                    assert e.status_code == 403
                    assert e.detail.get("error_code") == "ACCOUNT_NOT_READY"
                    assert "provisioned" in e.detail.get("message", "").lower()
                    return
    pytest.fail("Expected HTTPException 403")


@pytest.mark.asyncio
async def test_observability_endpoint_returns_provisioning_job_state():
    """GET /api/admin/provisioning/{client_id} returns correct provisioning job and state."""
    from fastapi import Request
    from routes.admin import get_provisioning_status

    request = MagicMock(spec=Request)
    db = MagicMock()
    client = {
        "client_id": "c1",
        "customer_reference": "PLE-CVP-2026-000001",
        "billing_plan": "PLAN_1_SOLO",
        "subscription_status": "ACTIVE",
        "onboarding_status": "PROVISIONED",
        "stripe_customer_id": "cus_1",
        "stripe_subscription_id": "sub_1",
    }
    job = {
        "job_id": "job_1",
        "status": "WELCOME_EMAIL_SENT",
        "attempt_count": 1,
        "last_error": None,
        "created_at": "2026-02-12T10:00:00",
        "updated_at": "2026-02-12T10:05:00",
    }
    db.clients.find_one = AsyncMock(return_value=client)
    db.provisioning_jobs.find_one = AsyncMock(return_value=job)
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=[])
    db.audit_logs.find = MagicMock(return_value=cursor)

    with patch("routes.admin.admin_route_guard", new_callable=AsyncMock):
        with patch("routes.admin.database.get_db", return_value=db):
            result = await get_provisioning_status(request, "c1")
    assert result["client_id"] == "c1"
    assert result["crn"] == "PLE-CVP-2026-000001"
    assert result["onboarding_status"] == "PROVISIONED"
    assert result["provisioning_job"]["job_id"] == "job_1"
    assert result["provisioning_job"]["status"] == "WELCOME_EMAIL_SENT"
    assert result["provisioning_job"]["attempt_count"] == 1
    assert result["stripe_customer_id"] == "cus_1"
