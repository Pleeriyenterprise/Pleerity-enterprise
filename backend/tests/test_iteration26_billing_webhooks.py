"""
Iteration 26 — Billing API and Stripe webhooks (in-process TestClient).

Mounted Stripe webhook routes (see routes/webhooks.py):
  POST /api/webhook/stripe   — primary
  POST /api/webhooks/stripe  — alias (same handler)

Previously tests under Pleerity-enterprise/tests/ used requests + REACT_APP_BACKEND_URL
(defaulting to a dead preview URL), which produced 404 for every call.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Optional, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

from services.billing_presentation import build_client_billing_payload
from services.stripe_webhook_service import stripe_webhook_service

# Documented contract for operators / Stripe dashboard configuration.
STRIPE_WEBHOOK_PATH_PRIMARY = "/api/webhook/stripe"
STRIPE_WEBHOOK_PATH_ALIAS = "/api/webhooks/stripe"


@pytest.fixture(scope="module")
def mongodb_reachable() -> None:
    """Stripe webhooks persist to ``stripe_events`` / ``client_billing`` — require Mongo like CI."""
    url = os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017/?serverSelectionTimeoutMS=3000")
    mc = MongoClient(url, serverSelectionTimeoutMS=3000)
    try:
        mc.admin.command("ping")
    except Exception as exc:
        mc.close()
        pytest.skip(f"MongoDB not reachable (webhook integration tests require it): {exc}")
    mc.close()


def _solo_monthly_price_id() -> str:
    return os.environ.get("STRIPE_TEST_PRICE_PLAN_1_SOLO_MONTHLY", "price_test_plan1_solo_monthly")


@pytest.fixture(scope="module")
def sync_db() -> Iterator[Any]:
    url = os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017/?serverSelectionTimeoutMS=5000")
    db_name = os.environ.get("DB_NAME", "compliance_vault_pro_test")
    mc = MongoClient(url, serverSelectionTimeoutMS=5000)
    try:
        mc.admin.command("ping")
    except ServerSelectionTimeoutError:
        pytest.skip("MongoDB not reachable for billing webhook integration tests")
    yield cast(Any, mc[db_name])
    mc.close()


def _evt(prefix: str = "evt_iter26") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def _fake_subscription_dict(
    *,
    subscription_id: str,
    customer_id: str,
    status: str = "active",
    price_id: Optional[str] = None,
) -> Dict[str, Any]:
    pid = price_id or _solo_monthly_price_id()
    now_ts = int(datetime.now(timezone.utc).timestamp())
    end_ts = now_ts + 86400 * 35
    return {
        "id": subscription_id,
        "customer": customer_id,
        "status": status,
        "current_period_end": end_ts,
        "current_period_start": now_ts,
        "billing_cycle_anchor": now_ts,
        "cancel_at_period_end": False,
        "latest_invoice": "in_iter26_latest",
        "items": {
            "data": [
                {
                    "price": {
                        "id": pid,
                        "recurring": {"interval": "month"},
                        "unit_amount": 1900,
                    }
                }
            ]
        },
    }


@pytest.fixture
def iter26_ids() -> Dict[str, str]:
    u = uuid.uuid4().hex[:10]
    return {
        "client_id": f"iter26_client_{u}",
        "cus": f"cus_iter26_{u}",
        "sub": f"sub_iter26_{u}",
    }


@pytest.fixture
def cleanup_iter26(sync_db, iter26_ids) -> Iterator[None]:
    cid = iter26_ids["client_id"]
    yield
    sync_db.stripe_events.delete_many({"event_id": {"$regex": "^evt_iter26_"}})
    sync_db.client_billing.delete_many({"client_id": cid})
    sync_db.clients.delete_many({"client_id": cid})
    sync_db.cvp_subscription_renewal_receipts.delete_many({"client_id": cid})
    sync_db.message_logs.delete_many({"client_id": cid, "template_key": "SUBSCRIPTION_RENEWAL_PAID"})


def _seed_client_and_billing(sync_db, ids: Dict[str, str], **billing_extra: Any) -> None:
    cid = ids["client_id"]
    now = datetime.now(timezone.utc)
    sync_db.clients.insert_one(
        {
            "client_id": cid,
            "billing_plan": "PLAN_1_SOLO",
            "onboarding_status": "PROVISIONED",
            "subscription_status": "ACTIVE",
            "entitlement_status": "ENABLED",
            "canonical_entitlement_state": "ENABLED",
            "billing_lifecycle_state": "active",
            "is_deleted": False,
            "client_lifecycle_status": "ACTIVE",
            "stripe_customer_id": ids["cus"],
            "stripe_subscription_id": ids["sub"],
            "created_at": now,
            "updated_at": now,
        }
    )
    row: Dict[str, Any] = {
        "client_id": cid,
        "stripe_customer_id": ids["cus"],
        "stripe_subscription_id": ids["sub"],
        "current_plan_code": "PLAN_1_SOLO",
        "subscription_status": "ACTIVE",
        "entitlement_status": "ENABLED",
        "canonical_entitlement_state": "ENABLED",
        "billing_lifecycle_state": "active",
        "current_period_end": now,
        "entitlements_version": 1,
        "created_at": now,
        "updated_at": now,
    }
    row.update(billing_extra)
    sync_db.client_billing.insert_one(row)


@pytest.fixture
def no_notifications():
    with patch(
        "services.notification_orchestrator.notification_orchestrator.send",
        new_callable=AsyncMock,
        return_value=MagicMock(outcome="duplicate_ignored"),
    ):
        yield


def test_stripe_webhook_paths_documented():
    assert STRIPE_WEBHOOK_PATH_PRIMARY == "/api/webhook/stripe"
    assert STRIPE_WEBHOOK_PATH_ALIAS == "/api/webhooks/stripe"


def test_webhook_primary_and_alias_return_200_for_unhandled_event(client, no_notifications, mongodb_reachable):
    r1 = client.post(
        STRIPE_WEBHOOK_PATH_PRIMARY,
        json={"id": _evt(), "type": "customer.created", "data": {"object": {"id": "cus_x"}}},
    )
    r2 = client.post(
        STRIPE_WEBHOOK_PATH_ALIAS,
        json={"id": _evt(), "type": "customer.created", "data": {"object": {"id": "cus_y"}}},
    )
    assert r1.status_code == 200 and r2.status_code == 200
    for r in (r1, r2):
        data = r.json()
        assert data.get("status") == "received"


def test_webhook_accepts_minimal_unknown_type(client, no_notifications, mongodb_reachable):
    body = {"id": _evt(), "type": "unknown.event.type", "data": {"object": {"id": "obj_x"}}}
    r = client.post(STRIPE_WEBHOOK_PATH_PRIMARY, json=body)
    assert r.status_code == 200
    assert r.json().get("status") == "received"


def test_customer_subscription_deleted_sets_cancelled_canonical(
    client, mongodb_reachable, sync_db, iter26_ids, cleanup_iter26, no_notifications
):
    _seed_client_and_billing(sync_db, iter26_ids)
    body = {
        "id": _evt(),
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": iter26_ids["sub"], "customer": iter26_ids["cus"]}},
    }
    r = client.post(STRIPE_WEBHOOK_PATH_PRIMARY, json=body)
    assert r.status_code == 200
    row = sync_db.client_billing.find_one({"client_id": iter26_ids["client_id"]}, {"_id": 0})
    assert row is not None
    assert row.get("subscription_status") == "CANCELED"
    assert row.get("canonical_entitlement_state") == "CANCELLED"
    crow = sync_db.clients.find_one({"client_id": iter26_ids["client_id"]}, {"_id": 0})
    assert crow.get("canonical_entitlement_state") == "CANCELLED"


def test_invoice_payment_failed_sets_grace_and_open_invoice(
    client, mongodb_reachable, sync_db, iter26_ids, cleanup_iter26, no_notifications
):
    _seed_client_and_billing(sync_db, iter26_ids)
    inv_id = f"in_iter26_pf_{uuid.uuid4().hex[:8]}"
    npt = int(datetime.now(timezone.utc).timestamp()) + 86400
    body = {
        "id": _evt(),
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "id": inv_id,
                "customer": iter26_ids["cus"],
                "subscription": iter26_ids["sub"],
                "amount_due": 1900,
                "currency": "gbp",
                "status": "open",
                "next_payment_attempt": npt,
                "last_finalization_error": {"message": "card_declined"},
            }
        },
    }
    with patch(
        "services.stripe_webhook_service.stripe.Subscription.retrieve",
        return_value={"id": iter26_ids["sub"], "status": "past_due", "customer": iter26_ids["cus"]},
    ):
        r = client.post(STRIPE_WEBHOOK_PATH_PRIMARY, json=body)
    assert r.status_code == 200
    row = sync_db.client_billing.find_one({"client_id": iter26_ids["client_id"]}, {"_id": 0})
    assert row.get("subscription_status") == "PAST_DUE"
    assert row.get("open_invoice_id") == inv_id
    assert row.get("open_invoice_status") == "open"
    assert row.get("stripe_next_payment_attempt_at") is not None
    assert row.get("grace_period_ends_at") is not None
    # Lifecycle + canonical after sync
    assert row.get("billing_lifecycle_state") in ("grace_period", "past_due", "limited")
    assert row.get("canonical_entitlement_state") in ("GRACE", "SUSPENDED")


def test_invoice_payment_failed_basil_parent_subscription_is_handled(
    client, mongodb_reachable, sync_db, iter26_ids, cleanup_iter26, no_notifications
):
    """2025-06-30.basil webhooks nest subscription under parent, not invoice.subscription."""
    _seed_client_and_billing(sync_db, iter26_ids)
    inv_id = f"in_iter26_basil_pf_{uuid.uuid4().hex[:8]}"
    npt = int(datetime.now(timezone.utc).timestamp()) + 86400
    body = {
        "id": _evt(),
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "id": inv_id,
                "customer": iter26_ids["cus"],
                "amount_due": 1900,
                "currency": "gbp",
                "status": "open",
                "next_payment_attempt": npt,
                "parent": {
                    "type": "subscription_details",
                    "subscription_details": {"subscription": iter26_ids["sub"]},
                },
            }
        },
    }
    with patch(
        "services.stripe_webhook_service.stripe.Subscription.retrieve",
        return_value={"id": iter26_ids["sub"], "status": "past_due", "customer": iter26_ids["cus"]},
    ):
        r = client.post(STRIPE_WEBHOOK_PATH_PRIMARY, json=body)
    assert r.status_code == 200
    row = sync_db.client_billing.find_one({"client_id": iter26_ids["client_id"]}, {"_id": 0})
    assert row.get("subscription_status") == "PAST_DUE"
    assert row.get("open_invoice_id") == inv_id
    assert row.get("stripe_next_payment_attempt_at") is not None


def test_invoice_paid_updates_last_payment_and_enabled_canonical(
    client, sync_db, iter26_ids, cleanup_iter26, no_notifications
):
    _seed_client_and_billing(
        sync_db,
        iter26_ids,
        payment_failed_at=datetime.now(timezone.utc),
        grace_period_ends_at=datetime.now(timezone.utc),
        dunning_stripe_invoice_id="in_old",
    )
    inv_id = f"in_iter26_paid_{uuid.uuid4().hex[:8]}"
    paid_at = int(datetime.now(timezone.utc).timestamp())
    period_start = paid_at - 86400 * 28
    period_end = paid_at + 86400 * 3
    body = {
        "id": _evt(),
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": inv_id,
                "customer": iter26_ids["cus"],
                "subscription": iter26_ids["sub"],
                "amount_paid": 1900,
                "currency": "gbp",
                "status": "paid",
                "billing_reason": "subscription_cycle",
                "number": "ITER26-0001",
                "hosted_invoice_url": "https://invoice.stripe.com/i/acct_test/test",
                "status_transitions": {"paid_at": paid_at},
            }
        },
    }
    sub_d = _fake_subscription_dict(
        subscription_id=iter26_ids["sub"],
        customer_id=iter26_ids["cus"],
        status="active",
    )
    inv_obj = MagicMock()

    def _to_dict():
        return {
            "id": inv_id,
            "number": "ITER26-0001",
            "hosted_invoice_url": "https://invoice.stripe.com/i/acct_test/test",
            "status_transitions": {"paid_at": paid_at},
            "total_details": {"amount_tax": 0},
            "lines": {
                "data": [
                    {
                        "amount": 1900,
                        "description": "Subscription",
                        "period": {"start": period_start, "end": period_end},
                    }
                ]
            },
        }

    inv_obj.to_dict = _to_dict
    with (
        patch(
            "services.stripe_webhook_service.retrieve_stripe_subscription_dict",
            new=AsyncMock(return_value=sub_d),
        ),
        patch("services.stripe_webhook_service.stripe.Invoice.retrieve", return_value=inv_obj),
    ):
        r = client.post(STRIPE_WEBHOOK_PATH_PRIMARY, json=body)
    assert r.status_code == 200
    row = sync_db.client_billing.find_one({"client_id": iter26_ids["client_id"]}, {"_id": 0})
    assert row.get("last_payment_at") is not None
    assert row.get("last_payment_amount_pence") == 1900
    assert row.get("last_payment_invoice_number") == "ITER26-0001"
    assert row.get("subscription_status") == "ACTIVE"
    assert row.get("canonical_entitlement_state") == "ENABLED"
    assert not row.get("open_invoice_id") and not row.get("open_invoice_status")
    ren = sync_db.cvp_subscription_renewal_receipts.find_one({"_id": inv_id}, {"_id": 0})
    assert ren is not None
    assert ren.get("client_id") == iter26_ids["client_id"]
    assert ren.get("amount_total_pence") == 1900
    assert ren.get("invoice_number", "").startswith("INV-")

    led = sync_db.subscription_payment_ledger.find_one({"stripe_invoice_id": inv_id}, {"_id": 0})
    assert led is not None
    assert led.get("amount_paid") == 1900
    assert led.get("currency") == "gbp"
    assert led.get("source_event_type") == "invoice.paid"
def test_customer_subscription_updated_persists_stripe_truth(
    client, mongodb_reachable, sync_db, iter26_ids, cleanup_iter26, no_notifications
):
    _seed_client_and_billing(sync_db, iter26_ids)
    body = {
        "id": _evt(),
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": iter26_ids["sub"],
                "customer": iter26_ids["cus"],
                "status": "past_due",
                "items": {"data": [{"price": {"id": _solo_monthly_price_id()}}]},
                "current_period_end": int(datetime.now(timezone.utc).timestamp()) + 86400 * 10,
            }
        },
    }
    sub_d = _fake_subscription_dict(
        subscription_id=iter26_ids["sub"],
        customer_id=iter26_ids["cus"],
        status="past_due",
    )
    with patch(
        "services.stripe_webhook_service.retrieve_stripe_subscription_dict",
        new=AsyncMock(return_value=sub_d),
    ):
        r = client.post(STRIPE_WEBHOOK_PATH_PRIMARY, json=body)
    assert r.status_code == 200
    row = sync_db.client_billing.find_one({"client_id": iter26_ids["client_id"]}, {"_id": 0})
    assert row.get("subscription_status") == "PAST_DUE"
    assert row.get("canonical_entitlement_state") in ("GRACE", "SUSPENDED", "ENABLED")
    assert sync_db.subscription_payment_ledger.count_documents({"client_id": iter26_ids["client_id"]}) == 0
@pytest.mark.asyncio
async def test_stale_subscription_reconcile_skips_without_stripe_key(mongodb_reachable):
    from services.stripe_subscription_reconcile_job import reconcile_all_stripe_subscriptions

    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "", "STRIPE_API_KEY": ""}, clear=False):
        out = await reconcile_all_stripe_subscriptions()
    assert out.get("skipped") == "no_stripe_key"


def test_build_client_billing_payload_includes_portal_contract_fields():
    """Portal-facing payload: renewal + payment copy + canonical (amount via last_payment_display)."""
    end_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    pay_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload = build_client_billing_payload(
        has_subscription=True,
        current_plan_code="PLAN_1_SOLO",
        plan_name="Solo",
        plan_display_name="Solo",
        subscription_status="ACTIVE",
        billing_lifecycle_state="active",
        cancel_at_period_end=False,
        next_renewal_date_iso=end_iso,
        current_period_start_iso=end_iso,
        current_period_end_iso=end_iso,
        monthly_price_pence=1900,
        setup_fee_pence=None,
        setup_fee_paid=True,
        first_billing_cycle=False,
        properties_used=1,
        properties_limit=2,
        grace_period_ends_at_iso=None,
        payment_failed_at_iso=None,
        charge_automatically=True,
        billing_last_synced_at_iso=end_iso,
        billing_sync_state="ok",
        currency="gbp",
        canonical_entitlement_state="ENABLED",
        last_payment_at_iso=pay_iso,
        last_payment_amount_pence=1900,
        last_payment_status="paid",
        open_invoice_status=None,
        stripe_next_payment_attempt_iso=None,
        last_invoice_failure_message=None,
    )
    assert payload.get("last_payment_at") == pay_iso
    assert payload.get("last_payment_display") and "£19.00" in (payload.get("last_payment_display") or "")
    assert payload.get("last_payment_status") == "paid"
    assert payload.get("subscription_status") == "ACTIVE"
    assert payload.get("next_renewal_date") == end_iso
    assert payload.get("canonical_entitlement_state") == "ENABLED"
    assert payload.get("last_payment_amount_pence") == 1900


def test_invoice_paid_renewal_email_context_duplicate_idempotency(
    client, sync_db, iter26_ids, cleanup_iter26
):
    """Same Stripe invoice id: one SUBSCRIPTION_RENEWAL_PAID send; second webhook is duplicate_ignored."""
    _seed_client_and_billing(sync_db, iter26_ids)
    inv_id = f"in_iter26_ren_{uuid.uuid4().hex[:8]}"
    paid_at = int(datetime.now(timezone.utc).timestamp())
    period_start = paid_at - 86400 * 30
    period_end = paid_at + 86400 * 2

    def _make_body(evt: str) -> Dict[str, Any]:
        return {
            "id": evt,
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": inv_id,
                    "customer": iter26_ids["cus"],
                    "subscription": iter26_ids["sub"],
                    "amount_paid": 1900,
                    "currency": "gbp",
                    "status": "paid",
                    "billing_reason": "subscription_cycle",
                    "number": "REN-001",
                    "hosted_invoice_url": "https://invoice.stripe.com/i/test_renewal",
                    "status_transitions": {"paid_at": paid_at},
                }
            },
        }

    inv_obj = MagicMock()

    def _to_dict():
        return {
            "id": inv_id,
            "number": "REN-001",
            "hosted_invoice_url": "https://invoice.stripe.com/i/test_renewal",
            "status_transitions": {"paid_at": paid_at},
            "total_details": {"amount_tax": 0},
            "lines": {
                "data": [
                    {
                        "amount": 1900,
                        "description": "1 × Solo (at £19.00 / month)",
                        "period": {"start": period_start, "end": period_end},
                    }
                ]
            },
        }

    inv_obj.to_dict = _to_dict
    sub_d = _fake_subscription_dict(
        subscription_id=iter26_ids["sub"],
        customer_id=iter26_ids["cus"],
        status="active",
    )

    sent_contexts: list = []
    seen_idem: set = set()

    async def cap_send(**kwargs):
        ik = (kwargs.get("idempotency_key") or "").strip()
        if ik in seen_idem:
            return MagicMock(outcome="duplicate_ignored")
        seen_idem.add(ik)
        sent_contexts.append(kwargs.get("context") or {})
        return MagicMock(outcome="sent")

    with (
        patch(
            "services.stripe_webhook_service.retrieve_stripe_subscription_dict",
            new=AsyncMock(return_value=sub_d),
        ),
        patch("services.stripe_webhook_service.stripe.Invoice.retrieve", return_value=inv_obj),
        patch(
            "services.notification_orchestrator.notification_orchestrator.send",
            new_callable=AsyncMock,
            side_effect=cap_send,
        ),
    ):
        r1 = client.post(STRIPE_WEBHOOK_PATH_PRIMARY, json=_make_body(_evt()))
        r2 = client.post(STRIPE_WEBHOOK_PATH_PRIMARY, json=_make_body(_evt()))
    assert r1.status_code == 200 and r2.status_code == 200
    assert len(sent_contexts) == 1
    c0 = sent_contexts[0]
    assert c0.get("payment_receipt_layout") == "structured"
    assert c0.get("receipt_kind") == "subscription_renewal"
    assert c0.get("hosted_invoice_url") == "https://invoice.stripe.com/i/test_renewal"
    assert c0.get("stripe_invoice_id_display") == inv_id
    assert c0.get("stripe_invoice_number_display") == "REN-001"
    assert "£19.00" in (c0.get("amount_display") or "")
    assert c0.get("billing_period_display")
    assert sync_db.cvp_subscription_renewal_receipts.count_documents({"client_id": iter26_ids["client_id"]}) == 1


def test_duplicate_webhook_delivery_same_event_id_is_idempotent(
    client, sync_db, iter26_ids, cleanup_iter26, no_notifications
):
    _seed_client_and_billing(sync_db, iter26_ids)
    inv_id = f"in_iter26_dup_{uuid.uuid4().hex[:8]}"
    evt_id = _evt()
    paid_at = int(datetime.now(timezone.utc).timestamp())
    body = {
        "id": evt_id,
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": inv_id,
                "customer": iter26_ids["cus"],
                "subscription": iter26_ids["sub"],
                "amount_paid": 1900,
                "currency": "gbp",
                "status": "paid",
                "billing_reason": "subscription_cycle",
                "status_transitions": {"paid_at": paid_at},
            }
        },
    }
    sub_d = _fake_subscription_dict(
        subscription_id=iter26_ids["sub"], customer_id=iter26_ids["cus"], status="active"
    )
    inv_obj = MagicMock()
    inv_obj.to_dict = lambda: {"id": inv_id, "lines": {"data": []}, "status_transitions": {"paid_at": paid_at}}
    with (
        patch("services.stripe_webhook_service.retrieve_stripe_subscription_dict", new=AsyncMock(return_value=sub_d)),
        patch("services.stripe_webhook_service.stripe.Invoice.retrieve", return_value=inv_obj),
    ):
        r1 = client.post(STRIPE_WEBHOOK_PATH_PRIMARY, json=body)
        r2 = client.post(STRIPE_WEBHOOK_PATH_PRIMARY, json=body)
    assert r1.status_code == 200 and r2.status_code == 200
    assert sync_db.stripe_events.count_documents({"event_id": evt_id}) == 1
    assert sync_db.payments.count_documents({"stripe_event_id": f"stripe_invoice:{inv_id}:paid"}) == 1


def test_sibling_invoice_events_do_not_duplicate_transition_side_effects(
    client, sync_db, iter26_ids, cleanup_iter26, no_notifications
):
    _seed_client_and_billing(sync_db, iter26_ids)
    inv_id = f"in_iter26_sib_{uuid.uuid4().hex[:8]}"
    paid_at = int(datetime.now(timezone.utc).timestamp())
    sub_d = _fake_subscription_dict(
        subscription_id=iter26_ids["sub"], customer_id=iter26_ids["cus"], status="active"
    )
    inv_obj = MagicMock()
    inv_obj.to_dict = lambda: {"id": inv_id, "lines": {"data": []}, "status_transitions": {"paid_at": paid_at}}
    body_paid = {
        "id": _evt(),
        "type": "invoice.paid",
        "data": {"object": {"id": inv_id, "customer": iter26_ids["cus"], "subscription": iter26_ids["sub"], "amount_paid": 1900, "currency": "gbp", "status": "paid", "billing_reason": "subscription_cycle", "status_transitions": {"paid_at": paid_at}}},
    }
    body_sibling = {
        "id": _evt(),
        "type": "invoice.payment_succeeded",
        "data": {"object": {"id": inv_id, "customer": iter26_ids["cus"], "subscription": iter26_ids["sub"], "amount_paid": 1900, "currency": "gbp", "status": "paid", "billing_reason": "subscription_cycle", "status_transitions": {"paid_at": paid_at}}},
    }
    with (
        patch("services.stripe_webhook_service.retrieve_stripe_subscription_dict", new=AsyncMock(return_value=sub_d)),
        patch("services.stripe_webhook_service.stripe.Invoice.retrieve", return_value=inv_obj),
    ):
        r1 = client.post(STRIPE_WEBHOOK_PATH_PRIMARY, json=body_paid)
        r2 = client.post(STRIPE_WEBHOOK_PATH_PRIMARY, json=body_sibling)
    assert r1.status_code == 200 and r2.status_code == 200
    assert sync_db.payments.count_documents({"stripe_event_id": f"stripe_invoice:{inv_id}:paid"}) == 1
    assert sync_db.cvp_subscription_renewal_receipts.count_documents({"_id": inv_id}) == 1


def test_out_of_order_payment_failed_after_paid_is_ignored_for_same_invoice(
    client, sync_db, iter26_ids, cleanup_iter26, no_notifications
):
    _seed_client_and_billing(sync_db, iter26_ids)
    inv_id = f"in_iter26_ooo_{uuid.uuid4().hex[:8]}"
    paid_at = int(datetime.now(timezone.utc).timestamp())
    sub_d = _fake_subscription_dict(
        subscription_id=iter26_ids["sub"], customer_id=iter26_ids["cus"], status="active"
    )
    inv_obj = MagicMock()
    inv_obj.to_dict = lambda: {"id": inv_id, "lines": {"data": []}, "status_transitions": {"paid_at": paid_at}}
    with (
        patch("services.stripe_webhook_service.retrieve_stripe_subscription_dict", new=AsyncMock(return_value=sub_d)),
        patch("services.stripe_webhook_service.stripe.Invoice.retrieve", return_value=inv_obj),
    ):
        rp = client.post(
            STRIPE_WEBHOOK_PATH_PRIMARY,
            json={
                "id": _evt(),
                "type": "invoice.paid",
                "data": {"object": {"id": inv_id, "customer": iter26_ids["cus"], "subscription": iter26_ids["sub"], "amount_paid": 1900, "currency": "gbp", "status": "paid", "billing_reason": "subscription_cycle", "status_transitions": {"paid_at": paid_at}}},
            },
        )
    assert rp.status_code == 200
    with patch(
        "services.stripe_webhook_service.stripe.Subscription.retrieve",
        return_value={"id": iter26_ids["sub"], "status": "past_due", "customer": iter26_ids["cus"]},
    ):
        rf = client.post(
            STRIPE_WEBHOOK_PATH_PRIMARY,
            json={
                "id": _evt(),
                "type": "invoice.payment_failed",
                "data": {"object": {"id": inv_id, "customer": iter26_ids["cus"], "subscription": iter26_ids["sub"], "amount_due": 1900, "currency": "gbp", "status": "open"}},
            },
        )
    assert rf.status_code == 200
    row = sync_db.client_billing.find_one({"client_id": iter26_ids["client_id"]}, {"_id": 0})
    assert row.get("subscription_status") == "ACTIVE"
    assert not row.get("open_invoice_id")


def test_payment_failed_reconciles_by_subscription_when_customer_lookup_missing(
    client, sync_db, iter26_ids, cleanup_iter26, no_notifications
):
    _seed_client_and_billing(sync_db, iter26_ids)
    with patch(
        "services.stripe_webhook_service.stripe.Subscription.retrieve",
        return_value={"id": iter26_ids["sub"], "status": "past_due", "customer": iter26_ids["cus"]},
    ):
        r = client.post(
            STRIPE_WEBHOOK_PATH_PRIMARY,
            json={
                "id": _evt(),
                "type": "invoice.payment_failed",
                "data": {
                    "object": {
                        "id": f"in_iter26_recon_{uuid.uuid4().hex[:8]}",
                        "customer": "cus_non_matching",
                        "subscription": iter26_ids["sub"],
                        "amount_due": 1900,
                        "currency": "gbp",
                        "status": "open",
                    }
                },
            },
        )
    assert r.status_code == 200
    row = sync_db.client_billing.find_one({"client_id": iter26_ids["client_id"]}, {"_id": 0})
    assert row.get("subscription_status") == "PAST_DUE"


@pytest.mark.asyncio
async def test_transition_guard_concurrent_duplicate_claimed_once(
    client, sync_db, iter26_ids, cleanup_iter26, no_notifications
):
    class _AsyncCollectionAdapter:
        def __init__(self, collection):
            self._collection = collection

        async def update_one(self, *args, **kwargs):
            return self._collection.update_one(*args, **kwargs)

        async def find_one(self, *args, **kwargs):
            return self._collection.find_one(*args, **kwargs)

    class _AsyncDbAdapter:
        def __init__(self, db):
            self.client_billing = _AsyncCollectionAdapter(db.client_billing)

    _seed_client_and_billing(sync_db, iter26_ids)
    db_adapter = _AsyncDbAdapter(sync_db)
    transition_key = f"invoice_paid:{iter26_ids['sub']}:in_concurrent_case"
    event_created = datetime.now(timezone.utc)

    with patch("services.stripe_webhook_service.database.get_db", return_value=db_adapter):
        r1, r2 = await asyncio.gather(
            stripe_webhook_service._claim_transition_guard(
                client_id=iter26_ids["client_id"],
                transition_key=transition_key,
                event_id=_evt("evt_iter26_concurrent"),
                event_type="invoice.paid",
                event_created=event_created,
                skip_if_seen=True,
            ),
            stripe_webhook_service._claim_transition_guard(
                client_id=iter26_ids["client_id"],
                transition_key=transition_key,
                event_id=_evt("evt_iter26_concurrent"),
                event_type="invoice.paid",
                event_created=event_created,
                skip_if_seen=True,
            ),
        )

    claimed_count = int(bool(r1.get("claimed"))) + int(bool(r2.get("claimed")))
    assert claimed_count == 1


@pytest.mark.asyncio
async def test_subscription_transition_key_allows_same_status_period_plan_change(
    client, sync_db, iter26_ids, cleanup_iter26, no_notifications
):
    class _AsyncCollectionAdapter:
        def __init__(self, collection):
            self._collection = collection

        async def update_one(self, *args, **kwargs):
            return self._collection.update_one(*args, **kwargs)

        async def find_one(self, *args, **kwargs):
            return self._collection.find_one(*args, **kwargs)

    class _AsyncDbAdapter:
        def __init__(self, db):
            self.client_billing = _AsyncCollectionAdapter(db.client_billing)

    _seed_client_and_billing(sync_db, iter26_ids)
    db_adapter = _AsyncDbAdapter(sync_db)
    sub_plan_a = {
        "id": iter26_ids["sub"],
        "status": "active",
        "current_period_end": 1893456000,
        "items": {"data": [{"price": {"id": "price_plan_a"}}]},
    }
    sub_plan_b = {
        "id": iter26_ids["sub"],
        "status": "active",
        "current_period_end": 1893456000,
        "items": {"data": [{"price": {"id": "price_plan_b"}}]},
    }
    key_a = stripe_webhook_service._subscription_transition_key(sub_plan_a)
    key_b = stripe_webhook_service._subscription_transition_key(sub_plan_b)
    assert key_a != key_b

    with patch("services.stripe_webhook_service.database.get_db", return_value=db_adapter):
        first = await stripe_webhook_service._claim_transition_guard(
            client_id=iter26_ids["client_id"],
            transition_key=key_a,
            event_id=_evt("evt_iter26_plan"),
            event_type="customer.subscription.updated",
            event_created=datetime.now(timezone.utc),
            skip_if_seen=True,
        )
        second = await stripe_webhook_service._claim_transition_guard(
            client_id=iter26_ids["client_id"],
            transition_key=key_b,
            event_id=_evt("evt_iter26_plan"),
            event_type="customer.subscription.updated",
            event_created=datetime.now(timezone.utc),
            skip_if_seen=True,
        )
    assert first.get("claimed") is True
    assert second.get("claimed") is True


@pytest.mark.asyncio
async def test_transition_guard_skips_stale_older_and_accepts_newer_event(
    client, sync_db, iter26_ids, cleanup_iter26, no_notifications
):
    class _AsyncCollectionAdapter:
        def __init__(self, collection):
            self._collection = collection

        async def update_one(self, *args, **kwargs):
            return self._collection.update_one(*args, **kwargs)

        async def find_one(self, *args, **kwargs):
            return self._collection.find_one(*args, **kwargs)

    class _AsyncDbAdapter:
        def __init__(self, db):
            self.client_billing = _AsyncCollectionAdapter(db.client_billing)

    _seed_client_and_billing(sync_db, iter26_ids)
    db_adapter = _AsyncDbAdapter(sync_db)
    transition_key = f"subscription_change:{iter26_ids['sub']}:ordering"
    base = datetime.now(timezone.utc)
    older = datetime.fromtimestamp(base.timestamp() - 300, tz=timezone.utc)
    newer = datetime.fromtimestamp(base.timestamp() + 300, tz=timezone.utc)

    with patch("services.stripe_webhook_service.database.get_db", return_value=db_adapter):
        first = await stripe_webhook_service._claim_transition_guard(
            client_id=iter26_ids["client_id"],
            transition_key=transition_key,
            event_id=_evt("evt_iter26_first"),
            event_type="customer.subscription.updated",
            event_created=base,
            skip_if_seen=True,
        )
        stale = await stripe_webhook_service._claim_transition_guard(
            client_id=iter26_ids["client_id"],
            transition_key=transition_key,
            event_id=_evt("evt_iter26_old"),
            event_type="customer.subscription.updated",
            event_created=older,
            skip_if_seen=True,
        )
        latest = await stripe_webhook_service._claim_transition_guard(
            client_id=iter26_ids["client_id"],
            transition_key=transition_key,
            event_id=_evt("evt_iter26_new"),
            event_type="customer.subscription.updated",
            event_created=newer,
            skip_if_seen=True,
        )
    assert first.get("claimed") is True
    assert stale.get("claimed") is False
    assert stale.get("reason") == "older_event"
    assert latest.get("claimed") is True


def test_admin_list_receipts_includes_subscription_renewals(client, sync_db, iter26_ids, cleanup_iter26):
    """Use TestClient + admin_route_guard override (same Motor loop as app); avoids async loop mismatch."""
    from middleware import admin_route_guard
    from server import app

    _seed_client_and_billing(sync_db, iter26_ids)
    now = datetime.now(timezone.utc)
    inv_id = f"in_iter26_admin_{uuid.uuid4().hex[:8]}"
    sync_db.cvp_subscription_renewal_receipts.insert_one(
        {
            "_id": inv_id,
            "client_id": iter26_ids["client_id"],
            "invoice_number": "INV-2099-000099",
            "stripe_invoice_id": inv_id,
            "stripe_invoice_number": "ADM-9",
            "paid_at": now,
            "created_at": now,
            "amount_total_pence": 1900,
            "currency": "gbp",
            "payment_status": "PAID",
            "billing_reason": "subscription_cycle",
            "billing_breakdown": [],
            "hosted_invoice_url": "https://invoice.stripe.com/i/admin_row",
        }
    )

    async def admin_override():
        return {
            "portal_user_id": "admin-test",
            "role": "ROLE_ADMIN",
            "email": "admin@test.local",
        }

    app.dependency_overrides[admin_route_guard] = admin_override
    try:
        r = client.get(
            f"/api/admin/billing/clients/{iter26_ids['client_id']}/receipts",
            params={"type": "all"},
        )
    finally:
        app.dependency_overrides.pop(admin_route_guard, None)

    assert r.status_code == 200, r.text
    data = r.json()
    meta = data.get("meta") or {}
    assert meta.get("client_id") == iter26_ids["client_id"]
    rows = data.get("receipts") or []
    details = {row.get("source_detail") for row in rows}
    assert "subscription_renewal" in details
    ren_row = next(row for row in rows if row.get("source_detail") == "subscription_renewal")
    assert ren_row.get("stripe_invoice_id") == inv_id
    assert ren_row.get("hosted_invoice_url")


def test_billing_plans_endpoint_returns_three_plans(client):
    r = client.get("/api/billing/plans")
    assert r.status_code == 200
    data = r.json()
    codes = [p["code"] for p in data["plans"]]
    assert set(codes) >= {"PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO"}
    solo = next(p for p in data["plans"] if p["code"] == "PLAN_1_SOLO")
    assert solo.get("stripe_subscription_price_id") == os.environ.get(
        "STRIPE_TEST_PRICE_PLAN_1_SOLO_MONTHLY"
    )
    assert isinstance(solo.get("features_count"), int)


def test_billing_status_requires_auth(client):
    r = client.get("/api/billing/status")
    assert r.status_code == 401


def test_checkout_requires_auth_and_step_up(client, mongodb_reachable):
    r = client.post("/api/billing/checkout", json={"plan_code": "PLAN_1_SOLO"})
    assert r.status_code == 401
    login = client.post(
        "/api/auth/login",
        json={"email": "test@pleerity.com", "password": "TestClient123!"},
    )
    if login.status_code != 200:
        pytest.skip("Seed client login not available in this database")
    token = login.json()["access_token"]
    r2 = client.post(
        "/api/billing/checkout",
        json={"plan_code": "PLAN_1_SOLO"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 403
    detail = r2.json().get("detail")
    if isinstance(detail, dict):
        assert detail.get("error_code") == "STEP_UP_REQUIRED"


def test_suspended_user_blocked_on_client_api_but_billing_ok(client, mongodb_reachable, sync_db):
    login = client.post(
        "/api/auth/login",
        json={"email": "test@pleerity.com", "password": "TestClient123!"},
    )
    if login.status_code != 200:
        pytest.skip("Seed client login not available in this database")
    token = login.json()["access_token"]
    user = login.json().get("user") or {}
    cid = user.get("client_id")
    if not cid:
        pytest.skip("Login payload missing client_id")
    hdrs = {"Authorization": f"Bearer {token}"}
    before = sync_db.client_billing.find_one({"client_id": cid}, {"_id": 0})
    if not before:
        pytest.skip("No client_billing row for seed user — cannot assert subscription guard")
    try:
        sync_db.client_billing.update_one(
            {"client_id": cid},
            {"$set": {"canonical_entitlement_state": "SUSPENDED", "billing_lifecycle_state": "limited"}},
        )
        blocked = client.get("/api/client/entitlements", headers=hdrs)
        assert blocked.status_code == 403
        det = blocked.json().get("detail")
        if isinstance(det, dict):
            assert det.get("error_code") == "SUBSCRIPTION_ACCESS_BLOCKED"
            assert det.get("canonical_entitlement_state") == "SUSPENDED"
        billing_ok = client.get("/api/billing/status", headers=hdrs)
        assert billing_ok.status_code == 200
    finally:
        sync_db.client_billing.update_one(
            {"client_id": cid},
            {
                "$set": {
                    "canonical_entitlement_state": before.get("canonical_entitlement_state"),
                    "billing_lifecycle_state": before.get("billing_lifecycle_state"),
                }
            },
        )


def test_cancelled_user_blocked_on_client_api_but_billing_ok(client, sync_db):
    login = client.post(
        "/api/auth/login",
        json={"email": "test@pleerity.com", "password": "TestClient123!"},
    )
    if login.status_code != 200:
        pytest.skip("Seed client login not available in this database")
    token = login.json()["access_token"]
    user = login.json().get("user") or {}
    cid = user.get("client_id")
    if not cid:
        pytest.skip("Login payload missing client_id")
    hdrs = {"Authorization": f"Bearer {token}"}
    before = sync_db.client_billing.find_one({"client_id": cid}, {"_id": 0})
    if not before:
        pytest.skip("No client_billing row for seed user — cannot assert subscription guard")
    try:
        sync_db.client_billing.update_one(
            {"client_id": cid},
            {"$set": {"canonical_entitlement_state": "CANCELLED", "billing_lifecycle_state": "cancelled"}},
        )
        blocked = client.get("/api/client/entitlements", headers=hdrs)
        assert blocked.status_code == 403
        billing_ok = client.get("/api/billing/status", headers=hdrs)
        assert billing_ok.status_code == 200
    finally:
        sync_db.client_billing.update_one(
            {"client_id": cid},
            {
                "$set": {
                    "canonical_entitlement_state": before.get("canonical_entitlement_state"),
                    "billing_lifecycle_state": before.get("billing_lifecycle_state"),
                }
            },
        )


def test_checkout_session_completed_mock_still_returns_200(client, no_notifications, mongodb_reachable, sync_db):
    """Minimal subscription checkout event — Stripe Session/Subscription mocked; price id matches plan_registry."""
    from services.plan_registry import PlanCode, plan_registry

    sub_id = f"sub_iter26_ck_{uuid.uuid4().hex[:8]}"
    cs_id = f"cs_iter26_{uuid.uuid4().hex[:8]}"
    cid_checkout = "nonexistent_client_iter26"
    try:
        price_row = plan_registry.get_stripe_price_ids(PlanCode.PLAN_1_SOLO)
        pid = (price_row.get("subscription_price_id") or "").strip()
    except Exception as exc:
        pytest.skip(f"Stripe price mapping not available for checkout webhook test: {exc}")
    if not pid:
        pytest.skip("subscription_price_id missing in plan_registry for PLAN_1_SOLO")

    # Minimal client row so checkout CRN + client updates match production expectations.
    now = datetime.now(timezone.utc)
    sync_db.clients.replace_one(
        {"client_id": cid_checkout},
        {
            "client_id": cid_checkout,
            "email": "checkout-mock@pleerity.test",
            "full_name": "Checkout Mock",
            "onboarding_status": "PROVISIONED",
            "subscription_status": "ACTIVE",
            "billing_plan": "PLAN_1_SOLO",
            "created_at": now,
            "updated_at": now,
        },
        upsert=True,
    )
    try:
        now_ts = int(now.timestamp())
        session_dict = {
            "id": cs_id,
            "mode": "subscription",
            "customer": "cus_nonexistent_iter26",
            "subscription": sub_id,
            "metadata": {"client_id": cid_checkout, "plan_code": PlanCode.PLAN_1_SOLO.value},
            "line_items": {
                "data": [
                    {
                        "amount": 1900,
                        "price": {"id": pid},
                        "description": "Solo monthly",
                    }
                ]
            },
        }
        sub_dict = {
            "id": sub_id,
            "status": "active",
            "customer": "cus_nonexistent_iter26",
            "cancel_at_period_end": False,
            "latest_invoice": "in_iter26_ck_inv",
            "current_period_start": now_ts,
            "current_period_end": now_ts + 86400 * 30,
            "billing_cycle_anchor": now_ts,
            "items": {"data": [{"price": {"id": pid}}]},
        }
        body = {
            "id": _evt(),
            "type": "checkout.session.completed",
            "data": {"object": dict(session_dict)},
        }
        with (
            patch(
                "services.stripe_webhook_service.stripe.checkout.Session.retrieve",
                return_value=session_dict,
            ),
            patch(
                "services.stripe_webhook_service.stripe.Subscription.retrieve",
                return_value=sub_dict,
            ),
        ):
            r = client.post(STRIPE_WEBHOOK_PATH_PRIMARY, json=body)
        assert r.status_code == 200
        assert r.json().get("status") == "received"
    finally:
        sync_db.clients.delete_many({"client_id": cid_checkout})
        sync_db.client_billing.delete_many({"client_id": cid_checkout})
        sync_db.provisioning_jobs.delete_many({"client_id": cid_checkout})


def test_checkout_session_completed_paid_creates_ledger(client, sync_db, no_notifications, mongodb_reachable):
    from services.plan_registry import PlanCode, plan_registry

    sub_id = f"sub_iter26_ckp_{uuid.uuid4().hex[:8]}"
    cs_id = f"cs_iter26_ckp_{uuid.uuid4().hex[:8]}"
    inv_id = f"in_iter26_ckp_{uuid.uuid4().hex[:8]}"
    cid = f"client_iter26_ckp_{uuid.uuid4().hex[:8]}"
    try:
        price_row = plan_registry.get_stripe_price_ids(PlanCode.PLAN_1_SOLO)
        pid = (price_row.get("subscription_price_id") or "").strip()
    except Exception as exc:
        pytest.skip(f"{exc}")
    if not pid:
        pytest.skip("subscription_price_id missing in plan_registry for PLAN_1_SOLO")

    now = datetime.now(timezone.utc)
    paid_raw = int(now.timestamp())
    sync_db.clients.replace_one(
        {"client_id": cid},
        {
            "client_id": cid,
            "email": "ckpledger@pleerity.test",
            "full_name": "Checkout Ledger Client",
            "onboarding_status": "PROVISIONED",
            "subscription_status": "ACTIVE",
            "billing_plan": "PLAN_1_SOLO",
            "created_at": now,
            "updated_at": now,
        },
        upsert=True,
    )
    now_ts = int(now.timestamp())
    session_dict = {
        "id": cs_id,
        "mode": "subscription",
        "customer": "cus_iter26_ckp",
        "subscription": sub_id,
        "payment_status": "paid",
        "invoice": inv_id,
        "metadata": {"client_id": cid, "plan_code": PlanCode.PLAN_1_SOLO.value},
        "line_items": {
            "data": [{"amount": 1900, "price": {"id": pid}, "description": "Solo monthly"}]
        },
    }
    sub_dict = {
        "id": sub_id,
        "status": "active",
        "customer": "cus_iter26_ckp",
        "cancel_at_period_end": False,
        "latest_invoice": inv_id,
        "current_period_start": now_ts,
        "current_period_end": now_ts + 86400 * 30,
        "billing_cycle_anchor": now_ts,
        "items": {"data": [{"price": {"id": pid}}]},
    }
    inv_payload = {
        "id": inv_id,
        "customer": "cus_iter26_ckp",
        "subscription": sub_id,
        "status": "paid",
        "amount_paid": 1900,
        "currency": "gbp",
        "number": "CKPLY-0099",
        "hosted_invoice_url": "https://invoice.stripe.com/i/test_ckp",
        "status_transitions": {"paid_at": paid_raw},
    }
    inv_obj = MagicMock()
    inv_obj.to_dict = lambda: dict(inv_payload)
    body = {"id": _evt(), "type": "checkout.session.completed", "data": {"object": dict(session_dict)}}
    try:
        with (
            patch(
                "services.stripe_webhook_service.stripe.checkout.Session.retrieve",
                return_value=session_dict,
            ),
            patch(
                "services.stripe_webhook_service.stripe.Subscription.retrieve",
                return_value=sub_dict,
            ),
            patch(
                "services.stripe_webhook_service.stripe.Invoice.retrieve",
                return_value=inv_obj,
            ),
        ):
            r = client.post(STRIPE_WEBHOOK_PATH_PRIMARY, json=body)
        assert r.status_code == 200
        ledger = sync_db.subscription_payment_ledger.find_one({"stripe_invoice_id": inv_id}, {"_id": 0})
        assert ledger is not None and ledger.get("client_id") == cid
        assert ledger.get("source_event_type") == "checkout.session.completed"
        prow = sync_db.client_billing.find_one({"client_id": cid}, {"_id": 0})
        assert prow and prow.get("last_payment_amount_pence") == 1900
        assert prow.get("last_payment_stripe_invoice_id") == inv_id
    finally:
        sync_db.clients.delete_many({"client_id": cid})
        sync_db.client_billing.delete_many({"client_id": cid})
        sync_db.provisioning_jobs.delete_many({"client_id": cid})
        sync_db.subscription_payment_ledger.delete_many({"client_id": cid})

