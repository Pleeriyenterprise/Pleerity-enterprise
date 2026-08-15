"""Canonical entitlement helpers and client billing payload fields."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.billing_presentation import build_client_billing_payload
from services.entitlement_access import compute_canonical_entitlement_state, evaluate_subscription_feature_access
from services.stripe_webhook_service import _extract_successful_invoice_payment_fields


def test_compute_canonical_maps_stripe_states():
    assert compute_canonical_entitlement_state(billing_lifecycle_state="active", subscription_status_upper="ACTIVE") == "ENABLED"
    assert compute_canonical_entitlement_state(billing_lifecycle_state="active", subscription_status_upper="PAST_DUE") == "GRACE"
    assert compute_canonical_entitlement_state(billing_lifecycle_state="limited", subscription_status_upper="PAST_DUE") == "SUSPENDED"
    assert compute_canonical_entitlement_state(billing_lifecycle_state="cancelled", subscription_status_upper="ACTIVE") == "CANCELLED"
    assert compute_canonical_entitlement_state(billing_lifecycle_state="active", subscription_status_upper="UNPAID") == "SUSPENDED"


def test_evaluate_grace_blocks_csv_not_dashboard():
    client = {"client_id": "c1", "billing_plan": "PLAN_3_PRO", "subscription_status": "PAST_DUE"}
    billing = {"subscription_status": "PAST_DUE", "billing_lifecycle_state": "grace_period"}
    d1 = evaluate_subscription_feature_access(client=client, billing=billing, feature_key="reports_csv")
    assert d1 is not None
    assert d1[1].get("error_code") == "SUBSCRIPTION_GRACE_PAYMENT"
    d2 = evaluate_subscription_feature_access(client=client, billing=billing, feature_key="compliance_dashboard")
    assert d2 is None


def test_evaluate_suspended_blocks_scheduled_reports():
    client = {"client_id": "c1", "billing_plan": "PLAN_3_PRO", "subscription_status": "UNPAID"}
    billing = {"subscription_status": "UNPAID", "billing_lifecycle_state": "active", "canonical_entitlement_state": "SUSPENDED"}
    d = evaluate_subscription_feature_access(client=client, billing=billing, feature_key="scheduled_reports")
    assert d is not None
    assert d[1].get("error_code") == "SUBSCRIPTION_SUSPENDED"


def test_build_client_billing_payload_includes_last_payment_when_set():
    p = build_client_billing_payload(
        has_subscription=True,
        current_plan_code="PLAN_1_SOLO",
        plan_name="Solo",
        plan_display_name="Solo",
        subscription_status="ACTIVE",
        billing_lifecycle_state="active",
        cancel_at_period_end=False,
        next_renewal_date_iso="2026-12-01T00:00:00+00:00",
        current_period_start_iso="2026-11-01T00:00:00+00:00",
        current_period_end_iso="2026-12-01T00:00:00+00:00",
        monthly_price_pence=1900,
        setup_fee_pence=None,
        setup_fee_paid=True,
        first_billing_cycle=False,
        properties_used=1,
        properties_limit=2,
        grace_period_ends_at_iso=None,
        payment_failed_at_iso=None,
        charge_automatically=True,
        billing_last_synced_at_iso="2026-04-01T10:00:00+00:00",
        billing_sync_state="ok",
        currency="gbp",
        canonical_entitlement_state="ENABLED",
        last_payment_at_iso="2026-04-01T09:00:00+00:00",
        last_payment_amount_pence=1900,
        last_payment_stripe_invoice_id="in_abc",
        last_payment_invoice_number="PLE-1001",
        last_payment_status="paid",
        open_invoice_status=None,
        stripe_next_payment_attempt_iso=None,
        last_invoice_failure_message=None,
    )
    assert p.get("last_payment_status") == "paid"
    assert p.get("last_payment_display")
    assert "2026" in p.get("last_payment_display")
    assert p.get("last_payment_amount_pence") == 1900
    assert p.get("last_payment_stripe_invoice_id") == "in_abc"
    assert p.get("last_payment_invoice_number") == "PLE-1001"


def test_extract_successful_invoice_payment_fields_from_stripe_shape():
    inv = {
        "id": "in_123",
        "number": "ST-500",
        "amount_paid": 2500,
        "currency": "gbp",
        "status_transitions": {"paid_at": int(datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc).timestamp())},
    }
    fields = _extract_successful_invoice_payment_fields(inv)
    assert fields.get("last_payment_stripe_invoice_id") == "in_123"
    assert fields.get("last_payment_amount_pence") == 2500
    assert fields.get("last_payment_invoice_number") == "ST-500"
    assert fields.get("last_payment_status") == "paid"
    assert fields.get("last_payment_at") is not None


def test_commercial_overlay_on_cancelled_uses_restored_plan_gates():
    cancelled = {
        "client_id": "c1",
        "billing_plan": "PLAN_1_SOLO",
        "subscription_status": "CANCELED",
        "canonical_entitlement_state": "CANCELLED",
        "commercial_effective_entitlement_state": "ENABLED",
        "commercial_restored_plan_code": "PLAN_1_SOLO",
    }
    billing = {
        "subscription_status": "CANCELED",
        "billing_lifecycle_state": "cancelled",
        "canonical_entitlement_state": "CANCELLED",
        "commercial_effective_entitlement_state": "ENABLED",
        "commercial_restored_plan_code": "PLAN_1_SOLO",
    }
    allowed = evaluate_subscription_feature_access(
        client=cancelled, billing=billing, feature_key="compliance_dashboard"
    )
    assert allowed is None
    denied = evaluate_subscription_feature_access(
        client=cancelled, billing=billing, feature_key="predictive_maintenance"
    )
    assert denied is not None
    assert denied[1].get("error_code") == "PLAN_NOT_ELIGIBLE"

    pro = dict(cancelled)
    pro["commercial_restored_plan_code"] = "PLAN_3_PRO"
    pro_billing = dict(billing)
    pro_billing["commercial_restored_plan_code"] = "PLAN_3_PRO"
    pro_ok = evaluate_subscription_feature_access(
        client=pro, billing=pro_billing, feature_key="predictive_maintenance"
    )
    assert pro_ok is None


def test_cancelled_without_overlay_still_denied():
    client = {"client_id": "c1", "billing_plan": "PLAN_3_PRO", "canonical_entitlement_state": "CANCELLED"}
    billing = {"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"}
    d = evaluate_subscription_feature_access(client=client, billing=billing, feature_key="compliance_dashboard")
    assert d is not None
    assert d[1].get("error_code") == "SUBSCRIPTION_CANCELLED"
