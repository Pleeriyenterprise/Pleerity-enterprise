"""Operational-truth copy for billing UI (S3–S5): renewal wording, Active disambiguation, stale sync, narrative."""
from __future__ import annotations

from services.billing_presentation import (
    billing_sync_visibility_note,
    build_client_billing_payload,
    build_operational_billing_narrative_lines,
    lifecycle_status_label,
    plan_status_display,
    renewal_customer_copy,
)


def test_cancel_at_period_end_renewal_copy_no_false_auto_renewal():
    s = renewal_customer_copy(
        has_subscription=True,
        subscription_status="ACTIVE",
        cancel_at_period_end=True,
        next_renewal_display="15 May 2026",
        billing_sync_state="ok",
        billing_lifecycle_state="active",
        open_invoice_status=None,
    )
    assert "Access continues until" in s
    assert "will not renew automatically" in s
    assert "Renews until" not in s


def test_open_invoice_does_not_imply_successful_renewal():
    s = renewal_customer_copy(
        has_subscription=True,
        subscription_status="ACTIVE",
        cancel_at_period_end=False,
        next_renewal_display="15 May 2026",
        billing_sync_state="ok",
        billing_lifecycle_state="active",
        open_invoice_status="open",
        stripe_next_payment_attempt_iso="2026-05-01T12:00:00+00:00",
    )
    assert "retry" in s.lower() or "invoice" in s.lower()
    assert "renewed" not in s.lower()


def test_grace_period_copy_and_plan_status_not_generic_active():
    ps = plan_status_display(
        has_subscription=True,
        subscription_status="ACTIVE",
        billing_lifecycle_state="grace_period",
        cancel_at_period_end=False,
        open_invoice_status=None,
    )
    assert ps == "Grace-period access"
    assert ps != "Active"
    rc = renewal_customer_copy(
        has_subscription=True,
        subscription_status="ACTIVE",
        cancel_at_period_end=False,
        next_renewal_display="1 June 2026",
        billing_sync_state="ok",
        billing_lifecycle_state="grace_period",
        open_invoice_status=None,
    )
    assert "grace" in rc.lower()


def test_stripe_error_sync_visibility_note():
    n = billing_sync_visibility_note(
        billing_sync_state="stripe_error",
        billing_last_synced_at_iso="2026-04-01T10:00:00+00:00",
    )
    assert n is not None
    assert "incomplete" in n.lower() or "stripe_error" in n.lower()


def test_plan_status_payment_retry_pending_overrides_active():
    ps = plan_status_display(
        has_subscription=True,
        subscription_status="ACTIVE",
        billing_lifecycle_state="active",
        cancel_at_period_end=False,
        open_invoice_status="open",
    )
    assert "Payment retry pending" in ps or "retry" in ps.lower()
    assert ps != "Active"


def test_lifecycle_label_grace_not_active():
    lab = lifecycle_status_label(
        has_subscription=True,
        cancel_at_period_end=False,
        billing_lifecycle_state="grace_period",
    )
    assert "grace" in lab.lower() or "retry" in lab.lower()
    assert lab != "Active"


def test_operational_narrative_ordering_and_sync_tail():
    lines = build_operational_billing_narrative_lines(
        lifecycle_status_label="Paid subscription active",
        plan_status_display_str="Paid subscription active",
        billing_status_display_str="Paid subscription active",
        billing_lifecycle_state="active",
        last_payment_summary="1 Apr 2026 · £19.00",
        open_invoice_status=None,
        stripe_next_payment_attempt_iso=None,
        cancel_at_period_end=False,
        next_renewal_date_display="15 May 2026",
        grace_period_summary=None,
        billing_last_synced_at_iso="2026-04-01T10:00:00+00:00",
        billing_sync_state="ok",
    )
    assert lines[0].startswith("Access:")
    assert any("Last successful payment" in x for x in lines)
    assert lines[-1].startswith("Last billing refresh") or "sync" in lines[-1].lower()


def test_build_client_payload_includes_narrative_and_no_contradictory_active_for_grace():
    p = build_client_billing_payload(
        has_subscription=True,
        current_plan_code="PLAN_1_SOLO",
        plan_name="Solo",
        plan_display_name="Solo",
        subscription_status="ACTIVE",
        billing_lifecycle_state="grace_period",
        cancel_at_period_end=False,
        next_renewal_date_iso="2026-06-01T00:00:00+00:00",
        current_period_start_iso="2026-05-01T00:00:00+00:00",
        current_period_end_iso="2026-06-01T00:00:00+00:00",
        monthly_price_pence=1900,
        setup_fee_pence=None,
        setup_fee_paid=True,
        first_billing_cycle=False,
        properties_used=1,
        properties_limit=2,
        grace_period_ends_at_iso="2026-05-10T23:59:59+00:00",
        payment_failed_at_iso=None,
        charge_automatically=True,
        billing_last_synced_at_iso="2026-04-01T10:00:00+00:00",
        billing_sync_state="ok",
        currency="gbp",
        canonical_entitlement_state="GRACE",
        last_payment_at_iso=None,
        last_payment_amount_pence=None,
        last_payment_stripe_invoice_id=None,
        last_payment_invoice_number=None,
        last_payment_status=None,
        open_invoice_status=None,
        stripe_next_payment_attempt_iso=None,
        last_invoice_failure_message=None,
    )
    assert p["plan_status_display"] == "Grace-period access"
    assert isinstance(p.get("billing_operational_narrative_lines"), list)
    assert len(p["billing_operational_narrative_lines"]) >= 1
    assert p.get("billing_sync_visibility_note")
