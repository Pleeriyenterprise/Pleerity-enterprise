"""
Integrated exercise: subscription checkout webhook path with agreement metadata,
CRN, issuance mocks, notification with PDF attachment, and issued-row email_delivery update.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.agreements import COL_ISSUED_AGREEMENTS

pytestmark = pytest.mark.asyncio

CHECKOUT_SESSION_ID = "cs_integ_agreement_001"
CLIENT_ID = "client-integ-agreement"
EVT_ID = "evt_integ_agreement_001"


@pytest.fixture
def subscription_dict():
    return {
        "id": "sub_integ_1",
        "status": "active",
        "current_period_end": 9999999999,
        "current_period_start": 1000000000,
        "cancel_at_period_end": False,
        "latest_invoice": "in_xxx",
        "items": {"data": [{"price": {"id": "price_plan1"}}]},
    }


@pytest.fixture
def session_with_agreement_metadata(subscription_dict):
    return {
        "id": CHECKOUT_SESSION_ID,
        "mode": "subscription",
        "customer": "cus_integ",
        "subscription": subscription_dict["id"],
        "amount_total": 5000,
        "currency": "gbp",
        "metadata": {
            "client_id": CLIENT_ID,
            "plan_code": "PLAN_1_SOLO",
            "acceptance_id": "acc-integ-1",
            "agreement_template_version_id": "ver-integ-1",
        },
        "line_items": {
            "data": [
                {"price": {"id": "price_plan1"}, "amount_total": 1900, "description": "Monthly"},
                {"price": {"id": "price_onboard"}, "amount_total": 4900, "description": "Setup"},
            ]
        },
    }


async def test_subscription_checkout_attaches_agreement_pdf_and_marks_email_delivered(
    session_with_agreement_metadata, subscription_dict
):
    import database as db_module

    from services.order_receipt_service import STRIPE_CHECKOUT_INVOICES
    from services.plan_registry import PlanCode, EntitlementStatus
    from services.stripe_webhook_service import StripeWebhookService

    issued_coll = MagicMock()
    issued_coll.update_one = AsyncMock()

    class MergedDb:
        """Single get_db() return value: Motor-style attributes + __getitem__ for dynamic collections."""

        def __init__(self):
            self.client_billing = MagicMock()
            self.client_billing.find_one = AsyncMock(return_value={"entitlements_version": 1})
            self.client_billing.update_one = AsyncMock()
            self.clients = MagicMock()

            async def clients_find_one(q, projection=None, **kw):
                if projection and "intake_session_id" in projection:
                    return {"intake_session_id": "sess-1"}
                return {
                    "full_name": "Pat",
                    "email": "pat@example.com",
                    "customer_reference": "CRN-INT-1",
                }

            self.clients.find_one = AsyncMock(side_effect=clients_find_one)
            self.clients.update_one = AsyncMock()
            self.provisioning_jobs = MagicMock()
            self.provisioning_jobs.find_one = AsyncMock(return_value=None)
            self.provisioning_jobs.insert_one = AsyncMock()
            self.checkout_sessions = MagicMock()
            self.checkout_sessions.update_one = AsyncMock()
            self.issued_agreements = issued_coll

        def __getitem__(self, name):
            if name == STRIPE_CHECKOUT_INVOICES:
                m = MagicMock()
                m.update_one = AsyncMock()
                return m
            if name == COL_ISSUED_AGREEMENTS:
                return issued_coll
            m = MagicMock()
            m.update_one = AsyncMock()
            m.find_one = AsyncMock(return_value=None)
            return m

    merged_db = MergedDb()

    sent_calls = []

    async def capture_send(**kwargs):
        sent_calls.append(kwargs)
        return SimpleNamespace(outcome="sent", message_id="msg-integ-1")

    issued_summary = {
        "issued_id": "issued-integ-1",
        "document_files": {"pdf_filename": "agreement_issued-inte_client-inte.pdf"},
    }

    with patch.object(db_module.database, "get_db", return_value=merged_db), \
         patch("services.stripe_webhook_service.stripe.Subscription.retrieve", return_value=subscription_dict), \
         patch(
             "services.stripe_webhook_service.plan_registry.get_plan_from_subscription_price_id",
             return_value=PlanCode.PLAN_1_SOLO,
         ), \
         patch(
             "services.stripe_webhook_service.plan_registry.get_stripe_price_ids",
             return_value={"onboarding_price_id": "price_onboard"},
         ), \
         patch(
             "services.stripe_webhook_service.plan_registry.get_entitlement_status_from_subscription",
             return_value=EntitlementStatus.ENABLED,
         ), \
         patch("services.stripe_webhook_service.create_audit_log", new_callable=AsyncMock), \
         patch("services.stripe_webhook_service.sync_subscription_lifecycle", new_callable=AsyncMock), \
         patch("services.crn_service.ensure_client_crn", new_callable=AsyncMock, return_value="CRN-INT-1"), \
         patch(
             "services.agreement_issuance_service.issue_agreement_for_subscription_payment",
             new_callable=AsyncMock,
             return_value=(True, None, issued_summary),
         ), \
         patch(
             "services.agreement_issuance_service.load_issued_pdf_bytes",
             new_callable=AsyncMock,
             return_value=b"%PDF-1.4 integration",
         ), \
         patch(
             "services.order_receipt_service.ensure_subscription_checkout_invoice_pdf",
             new_callable=AsyncMock,
             return_value=(False, None, None, "skipped for test"),
         ), \
         patch(
             "services.notification_orchestrator.notification_orchestrator.send",
             new_callable=AsyncMock,
             side_effect=capture_send,
         ), \
         patch("services.stripe_webhook_service._run_provisioning_after_webhook", new_callable=AsyncMock):

        svc = StripeWebhookService()
        await svc._handle_subscription_checkout(
            session_with_agreement_metadata,
            {"id": EVT_ID},
        )

    assert sent_calls, "notification send should run"
    ctx = sent_calls[0].get("context") or {}
    atts = ctx.get("attachments") or []
    import base64

    assert any(
        (a.get("Name") or "").endswith(".pdf")
        and b"%PDF" in base64.b64decode(a.get("Content") or "")
        for a in atts
    ), "email context should include agreement PDF attachment"

    issued_coll.update_one.assert_awaited()
    up_filter = issued_coll.update_one.await_args[0][0]
    assert up_filter.get("issued_id") == "issued-integ-1"
    assert up_filter.get("client_id") == CLIENT_ID
    setdoc = issued_coll.update_one.await_args[0][1].get("$set", {})
    assert setdoc.get("email_delivery", {}).get("sent") is True


async def test_mark_issued_agreement_email_delivered_writes_email_delivery():
    from services.agreement_issuance_service import mark_issued_agreement_email_delivered

    coll = MagicMock()
    coll.update_one = AsyncMock()

    class D:
        def __getitem__(self, n):
            if n == COL_ISSUED_AGREEMENTS:
                return coll
            return MagicMock()

    with patch("services.agreement_issuance_service.database.get_db", return_value=D()):
        await mark_issued_agreement_email_delivered(
            issued_id="i1",
            client_id="c1",
            template_key="SUBSCRIPTION_CONFIRMED",
            stripe_event_id="evt_x",
            message_id="mid_y",
        )
    coll.update_one.assert_awaited()
    payload = coll.update_one.await_args[0][1]["$set"]["email_delivery"]
    assert payload["sent"] is True
    assert payload["template_key"] == "SUBSCRIPTION_CONFIRMED"


async def test_subscription_checkout_sends_email_when_agreement_generation_fails(
    session_with_agreement_metadata, subscription_dict
):
    import database as db_module

    from services.order_receipt_service import STRIPE_CHECKOUT_INVOICES
    from services.plan_registry import PlanCode, EntitlementStatus
    from services.stripe_webhook_service import StripeWebhookService

    class MergedDb:
        def __init__(self):
            self.client_billing = MagicMock()
            self.client_billing.find_one = AsyncMock(return_value={"entitlements_version": 1})
            self.client_billing.update_one = AsyncMock()
            self.clients = MagicMock()

            async def clients_find_one(q, projection=None, **kw):
                if projection and "intake_session_id" in projection:
                    return {"intake_session_id": "sess-1"}
                return {
                    "full_name": "Pat",
                    "email": "pat@example.com",
                    "customer_reference": "CRN-INT-1",
                }

            self.clients.find_one = AsyncMock(side_effect=clients_find_one)
            self.clients.update_one = AsyncMock()
            self.provisioning_jobs = MagicMock()
            self.provisioning_jobs.find_one = AsyncMock(return_value=None)
            self.provisioning_jobs.insert_one = AsyncMock()
            self.checkout_sessions = MagicMock()
            self.checkout_sessions.update_one = AsyncMock()

        def __getitem__(self, name):
            if name == STRIPE_CHECKOUT_INVOICES:
                m = MagicMock()
                m.update_one = AsyncMock()
                return m
            m = MagicMock()
            m.update_one = AsyncMock()
            m.find_one = AsyncMock(return_value=None)
            return m

    merged_db = MergedDb()
    sent_calls = []

    async def capture_send(**kwargs):
        sent_calls.append(kwargs)
        return SimpleNamespace(outcome="sent", message_id="msg-integ-fail-path")

    with patch.object(db_module.database, "get_db", return_value=merged_db), \
         patch("services.stripe_webhook_service.stripe.Subscription.retrieve", return_value=subscription_dict), \
         patch(
             "services.stripe_webhook_service.plan_registry.get_plan_from_subscription_price_id",
             return_value=PlanCode.PLAN_1_SOLO,
         ), \
         patch(
             "services.stripe_webhook_service.plan_registry.get_stripe_price_ids",
             return_value={"onboarding_price_id": "price_onboard"},
         ), \
         patch(
             "services.stripe_webhook_service.plan_registry.get_entitlement_status_from_subscription",
             return_value=EntitlementStatus.ENABLED,
         ), \
         patch("services.stripe_webhook_service.create_audit_log", new_callable=AsyncMock), \
         patch("services.stripe_webhook_service.sync_subscription_lifecycle", new_callable=AsyncMock), \
         patch("services.crn_service.ensure_client_crn", new_callable=AsyncMock, return_value="CRN-INT-1"), \
         patch(
             "services.agreement_issuance_service.issue_agreement_for_subscription_payment",
             new_callable=AsyncMock,
             return_value=(False, "PDF_BUILD_ERROR:test", None),
         ), \
         patch(
             "services.order_receipt_service.ensure_subscription_checkout_invoice_pdf",
             new_callable=AsyncMock,
             return_value=(True, b"%PDF-1.4 invoice", "INV-2026-000001", None),
         ), \
         patch(
             "services.notification_orchestrator.notification_orchestrator.send",
             new_callable=AsyncMock,
             side_effect=capture_send,
         ), \
         patch("services.stripe_webhook_service._run_provisioning_after_webhook", new_callable=AsyncMock):
        svc = StripeWebhookService()
        await svc._handle_subscription_checkout(
            session_with_agreement_metadata,
            {"id": EVT_ID},
        )

    assert sent_calls, "subscription confirmation email should still be sent"
    ctx = sent_calls[0].get("context") or {}
    atts = ctx.get("attachments") or []
    assert any((a.get("Name") or "").startswith("INV-2026-000001") for a in atts), "invoice PDF should be attached"
    assert not any((a.get("Name") or "").startswith("agreement_") for a in atts), "agreement PDF should be absent on failed generation"
