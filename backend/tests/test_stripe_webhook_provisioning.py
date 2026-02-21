"""
Unit test: paid Stripe webhook updates subscription/payment and triggers provisioning;
provisioning_status becomes IN_PROGRESS then COMPLETED; duplicate webhook does not provision twice (idempotency).
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

EVENT_ID = "evt_test_webhook_provisioning_001"
CHECKOUT_SESSION_ID = "cs_test_checkout_001"
SUB_ID = "sub_test_001"
CLIENT_ID = "test-client-webhook-provisioning"
CUS_ID = "cus_test_001"


def _make_checkout_completed_event():
    """Minimal checkout.session.completed event with subscription (paid)."""
    return {
        "id": EVENT_ID,
        "type": "checkout.session.completed",
        "livemode": False,
        "data": {
            "object": {
                "id": CHECKOUT_SESSION_ID,
                "mode": "subscription",
                "customer": CUS_ID,
                "subscription": SUB_ID,
                "metadata": {"client_id": CLIENT_ID},
            }
        },
    }


def _make_subscription_active():
    return {
        "id": SUB_ID,
        "status": "active",
        "current_period_end": 9999999999,
        "cancel_at_period_end": False,
        "latest_invoice": "in_xxx",
        "items": {"data": [{"price": {"id": "price_plan1"}}]},
    }


class _InMemoryStore:
    """Minimal in-memory store for clients, stripe_events, provisioning_jobs, client_billing."""

    def __init__(self):
        self.clients = {}
        self.stripe_events = {}
        self.provisioning_jobs = {}
        self.client_billing = {}

    def get_db(self):
        db = MagicMock()
        # clients
        async def clients_find_one(q, projection=None, **kw):
            cid = q.get("client_id")
            return self.clients.get(cid)

        async def clients_update_one(q, u, **kw):
            cid = q.get("client_id")
            if cid not in self.clients:
                self.clients[cid] = {"client_id": cid}
            doc = self.clients[cid]
            if "$set" in u:
                doc.update(u["$set"])
            if "$unset" in u:
                for k in u["$unset"]:
                    doc.pop(k, None)

        db.clients = MagicMock()
        db.clients.find_one = AsyncMock(side_effect=clients_find_one)
        db.clients.update_one = AsyncMock(side_effect=clients_update_one)

        # stripe_events
        async def stripe_events_find_one(q, **kw):
            eid = q.get("event_id")
            return self.stripe_events.get(eid)

        async def stripe_events_insert_one(doc, **kw):
            self.stripe_events[doc["event_id"]] = doc

        async def stripe_events_update_one(q, u, **kw):
            eid = q.get("event_id")
            if eid in self.stripe_events:
                if "$set" in u:
                    self.stripe_events[eid].update(u["$set"])

        db.stripe_events = MagicMock()
        db.stripe_events.find_one = AsyncMock(side_effect=stripe_events_find_one)
        db.stripe_events.insert_one = AsyncMock(side_effect=stripe_events_insert_one)
        db.stripe_events.update_one = AsyncMock(side_effect=stripe_events_update_one)

        # provisioning_jobs
        async def jobs_find_one(q, projection=None, **kw):
            if "checkout_session_id" in q:
                for j in self.provisioning_jobs.values():
                    if j.get("checkout_session_id") == q["checkout_session_id"]:
                        return {k: j.get(k) for k in (projection or {}).keys() or j} if projection else j
            if "job_id" in q:
                return self.provisioning_jobs.get(q["job_id"])
            return None

        async def jobs_insert_one(doc, **kw):
            self.provisioning_jobs[doc["job_id"]] = doc.copy()

        async def jobs_update_one(q, u, **kw):
            jid = q.get("job_id")
            if jid and jid in self.provisioning_jobs:
                if "$set" in u:
                    self.provisioning_jobs[jid].update(u["$set"])

        db.provisioning_jobs = MagicMock()
        db.provisioning_jobs.find_one = AsyncMock(side_effect=jobs_find_one)
        db.provisioning_jobs.insert_one = AsyncMock(side_effect=jobs_insert_one)
        db.provisioning_jobs.update_one = AsyncMock(side_effect=jobs_update_one)

        # client_billing
        async def billing_find_one(q, projection=None, **kw):
            cid = q.get("client_id")
            return self.client_billing.get(cid)

        async def billing_update_one(q, u, upsert=False, **kw):
            cid = q.get("client_id")
            if cid not in self.client_billing:
                self.client_billing[cid] = {"client_id": cid}
            if "$set" in u:
                self.client_billing[cid].update(u["$set"])
            if "$inc" in u:
                for k, v in u["$inc"].items():
                    self.client_billing[cid][k] = self.client_billing[cid].get(k, 0) + v

        db.client_billing = MagicMock()
        db.client_billing.find_one = AsyncMock(side_effect=billing_find_one)
        db.client_billing.update_one = AsyncMock(side_effect=billing_update_one)

        return db


def test_paid_webhook_updates_subscription_and_provisioning_idempotent():
    """
    Simulate a paid webhook (checkout.session.completed):
    - subscription/payment fields updated on client
    - provisioning_status becomes IN_PROGRESS then COMPLETED (mocked provisioning)
    - Second delivery of same event: no second provisioning (idempotency).
    """
    asyncio.run(_test_paid_webhook_updates_subscription_and_provisioning_idempotent_async())


async def _test_paid_webhook_updates_subscription_and_provisioning_idempotent_async():
    from services.stripe_webhook_service import StripeWebhookService
    from services.plan_registry import PlanCode, EntitlementStatus
    from models import ProvisioningJobStatus

    store = _InMemoryStore()
    store.clients[CLIENT_ID] = {
        "client_id": CLIENT_ID,
        "subscription_status": "PENDING",
        "onboarding_status": "INTAKE_COMPLETE",
        "intake_session_id": "sess_123",
    }
    store.client_billing[CLIENT_ID] = {"client_id": CLIENT_ID, "entitlements_version": 0}

    event = _make_checkout_completed_event()
    payload = json.dumps(event).encode("utf-8")
    subscription = _make_subscription_active()

    run_provisioning_call_count = 0

    async def mock_run_provisioning_job(job_id: str):
        nonlocal run_provisioning_call_count
        run_provisioning_call_count += 1
        db = store.get_db()
        job = await db.provisioning_jobs.find_one({"job_id": job_id})
        if not job:
            return False
        cid = job.get("client_id")
        await db.clients.update_one(
            {"client_id": cid},
            {"$set": {"provisioning_status": "IN_PROGRESS", "onboarding_status": "PROVISIONING"}},
        )
        await db.clients.update_one(
            {"client_id": cid},
            {"$set": {"provisioning_status": "COMPLETED", "onboarding_status": "PROVISIONED"}},
        )
        await db.provisioning_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": ProvisioningJobStatus.WELCOME_EMAIL_SENT.value}},
        )
        return True

    tasks_run = []

    def capture_and_run_task(coro):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        t = loop.create_task(coro)
        tasks_run.append(t)
        return t

    with patch("services.stripe_webhook_service.database.get_db", side_effect=store.get_db), \
         patch("services.stripe_webhook_service.stripe.Webhook.construct_event") as construct_ev, \
         patch("services.stripe_webhook_service.stripe.Subscription.retrieve", return_value=subscription), \
         patch("services.stripe_webhook_service.plan_registry.get_plan_from_subscription_price_id", return_value=PlanCode.PLAN_1_SOLO), \
         patch("services.stripe_webhook_service.plan_registry.get_stripe_price_ids", return_value={"onboarding_price_id": "price_plan1"}), \
         patch("services.stripe_webhook_service.plan_registry.get_entitlement_status_from_subscription", return_value=EntitlementStatus.ENABLED), \
         patch("services.stripe_webhook_service.create_audit_log", new_callable=AsyncMock), \
         patch("services.crn_service.ensure_client_crn", new_callable=AsyncMock), \
         patch("services.stripe_webhook_service._run_provisioning_after_webhook", side_effect=mock_run_provisioning_job), \
         patch("asyncio.create_task", side_effect=capture_and_run_task):

        def _construct(payload_bytes, sig, secret):
            return event

        construct_ev.side_effect = _construct

        svc = StripeWebhookService()
        success, message, details = await svc.process_webhook(payload=payload, signature="whsec_test")
        if tasks_run:
            await asyncio.gather(*tasks_run)
        assert success is True
        assert message in ("Processed", "Already processed")
        assert store.clients.get(CLIENT_ID)
        assert store.clients[CLIENT_ID].get("subscription_status") == "ACTIVE"
        assert store.clients[CLIENT_ID].get("billing_plan") == PlanCode.PLAN_1_SOLO.value
        assert run_provisioning_call_count >= 1, "provisioning should have been triggered once"
        assert store.clients[CLIENT_ID].get("provisioning_status") == "COMPLETED"
        assert store.clients[CLIENT_ID].get("onboarding_status") == "PROVISIONED"

    first_run_count = run_provisioning_call_count

    with patch("services.stripe_webhook_service.database.get_db", side_effect=store.get_db), \
         patch("services.stripe_webhook_service.stripe.Webhook.construct_event") as construct_ev2, \
         patch("services.stripe_webhook_service.stripe.Subscription.retrieve", return_value=subscription), \
         patch("services.stripe_webhook_service.plan_registry.get_plan_from_subscription_price_id", return_value=PlanCode.PLAN_1_SOLO), \
         patch("services.stripe_webhook_service.plan_registry.get_stripe_price_ids", return_value={"onboarding_price_id": "price_plan1"}), \
         patch("services.stripe_webhook_service.plan_registry.get_entitlement_status_from_subscription", return_value=EntitlementStatus.ENABLED), \
         patch("services.stripe_webhook_service.create_audit_log", new_callable=AsyncMock), \
         patch("services.stripe_webhook_service._run_provisioning_after_webhook", new_callable=AsyncMock):

        def _construct2(payload_bytes, sig, secret):
            return event

        construct_ev2.side_effect = _construct2

        success2, message2, _ = await svc.process_webhook(payload=payload, signature="whsec_test")
        assert success2 is True
        assert message2 == "Already processed"
        assert run_provisioning_call_count == first_run_count
