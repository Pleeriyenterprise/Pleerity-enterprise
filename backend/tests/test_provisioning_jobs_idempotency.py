"""
Minimal tests for provisioning_jobs idempotency and hardening.

- Duplicate webhook with existing PAYMENT_CONFIRMED job sets needs_run=True (re-dispatch for poller).
- Lock prevents two runners from executing the same job simultaneously.
- Runner does not duplicate portal users.
"""
import pytest
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.asyncio

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

CHECKOUT_SESSION_ID = "cs_test_abc123"
CLIENT_ID = "test-client-456"
JOB_ID = "job-uuid-789"


class TestWebhookIdempotencyByCheckoutSession:
    """Duplicate webhook with same checkout_session_id: existing PAYMENT_CONFIRMED/FAILED gets needs_run=True."""

    @pytest.mark.asyncio
    async def test_duplicate_webhook_with_existing_payment_confirmed_sets_needs_run(self):
        from services.stripe_webhook_service import StripeWebhookService
        from models import ProvisioningJobStatus

        db = MagicMock()
        existing_job = {"job_id": JOB_ID, "status": ProvisioningJobStatus.PAYMENT_CONFIRMED.value}
        db.provisioning_jobs = MagicMock()
        db.provisioning_jobs.find_one = AsyncMock(return_value=existing_job)
        db.provisioning_jobs.update_one = AsyncMock()
        db.clients = MagicMock()
        db.clients.find_one = AsyncMock()
        db.clients.update_one = AsyncMock()
        db.client_billing = MagicMock()
        db.client_billing.update_one = AsyncMock()

        session = {
            "id": CHECKOUT_SESSION_ID,
            "customer": "cus_xxx",
            "subscription": "sub_xxx",
            "metadata": {"client_id": CLIENT_ID},
        }
        subscription = {
            "status": "active",
            "current_period_end": 9999999999,
            "cancel_at_period_end": False,
            "latest_invoice": "in_xxx",
            "items": {"data": [{"price": {"id": "price_xxx"}}]},
        }
        from services.plan_registry import PlanCode, EntitlementStatus
        with patch("services.stripe_webhook_service.database.get_db", return_value=db), \
             patch("services.stripe_webhook_service.stripe.Subscription.retrieve", return_value=subscription), \
             patch("services.stripe_webhook_service.plan_registry.get_plan_from_subscription_price_id", return_value=PlanCode.PLAN_1_SOLO), \
             patch("services.stripe_webhook_service.plan_registry.get_stripe_price_ids", return_value={"onboarding_price_id": "price_onboard"}), \
             patch("services.stripe_webhook_service.plan_registry.get_entitlement_status_from_subscription", return_value=EntitlementStatus.ENABLED), \
             patch("services.stripe_webhook_service.create_audit_log", new_callable=AsyncMock):
            svc = StripeWebhookService()
            await svc._handle_subscription_checkout(session, {})
        db.provisioning_jobs.update_one.assert_called()
        call = db.provisioning_jobs.update_one.call_args
        assert call[0][0] == {"checkout_session_id": CHECKOUT_SESSION_ID}
        assert call[1]["$set"].get("needs_run") is True
        db.provisioning_jobs.insert_one.assert_not_called()


class TestRunnerIdempotency:
    """Running the runner for same job (PAYMENT_CONFIRMED) twice must not duplicate portal user."""

    @pytest.mark.asyncio
    async def test_runner_core_does_not_duplicate_portal_user(self):
        from services.provisioning import provisioning_service

        db = MagicMock()
        client = {
            "client_id": CLIENT_ID,
            "email": "c@ex.com",
            "full_name": "Test",
            "onboarding_status": "PROVISIONED",  # Already provisioned
            "subscription_status": "ACTIVE",
            "billing_plan": "PLAN_1",
        }
        existing_user = {"portal_user_id": "pu-1", "client_id": CLIENT_ID, "role": "ROLE_CLIENT_ADMIN"}
        db.clients = MagicMock()
        db.clients.find_one = AsyncMock(return_value=client)
        db.clients.update_one = AsyncMock()
        db.portal_users = MagicMock()
        db.portal_users.find_one = AsyncMock(return_value=existing_user)
        db.portal_users.insert_one = AsyncMock()
        db.properties = MagicMock()
        db.properties.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
        db.requirements = MagicMock()
        db.requirements.find_one = AsyncMock(return_value=None)
        db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
        db.requirements.insert_one = AsyncMock()
        db.requirement_rules = MagicMock()
        db.requirement_rules.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
        db.password_tokens = MagicMock()
        db.password_tokens.insert_one = AsyncMock()

        with patch("services.provisioning.database.get_db", return_value=db), \
             patch("services.provisioning.create_audit_log", new_callable=AsyncMock):
            success, message, user_id = await provisioning_service.provision_client_portal_core(CLIENT_ID)
        assert success is True
        assert user_id == "pu-1"
        db.portal_users.insert_one.assert_not_called()


class TestRunnerLock:
    """Lock prevents two runners from executing the same job simultaneously."""

    @pytest.mark.asyncio
    async def test_second_runner_skips_when_lock_not_acquired(self):
        from services.provisioning_runner import run_provisioning_job, _acquire_lock

        db = MagicMock()
        job = {
            "job_id": JOB_ID,
            "client_id": CLIENT_ID,
            "status": "PAYMENT_CONFIRMED",
        }
        db.provisioning_jobs = MagicMock()
        db.provisioning_jobs.find_one = AsyncMock(return_value=job)
        db.provisioning_jobs.find_one_and_update = AsyncMock(return_value=None)
        db.provisioning_jobs.update_one = AsyncMock()
        with patch("services.provisioning_runner.database.get_db", return_value=db):
            acquired = await _acquire_lock(JOB_ID)
        assert acquired is False
        with patch("services.provisioning_runner.database.get_db", return_value=db), \
             patch("services.provisioning_runner.provisioning_service") as mock_svc:
            mock_svc.provision_client_portal_core = AsyncMock()
            run_result = await run_provisioning_job(JOB_ID)
        assert run_result is False
        db.provisioning_jobs.find_one_and_update.assert_called()
        mock_svc.provision_client_portal_core.assert_not_called()
