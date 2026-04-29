from services.admin_billing_receipts import _enrich_admin_payment_row


def test_enrich_admin_payment_row_subscription_pdf_available():
    row = _enrich_admin_payment_row(
        {
            "source": "subscription",
            "invoice_number": "INV-1",
            "pdf_available": True,
            "payment_status": "PAID",
        }
    )
    assert row["download_available"] is True
    assert row["resend_available"] is True
    assert row["download_unavailable_reason"] is None
    assert row["resend_unavailable_reason"] is None
    assert row["failed_attempt_marker"] is False


def test_enrich_admin_payment_row_failed_has_marker():
    row = _enrich_admin_payment_row(
        {
            "source": "subscription",
            "invoice_number": "INV-2",
            "pdf_available": False,
            "payment_status": "FAILED",
        }
    )
    assert row["failed_attempt_marker"] is True
    assert row["failed_attempt_reason"] == "Payment requires support follow-up."
    assert row["download_available"] is False
    assert row["resend_available"] is False
    assert row["download_unavailable_reason"] == "Receipt PDF is not available yet."
    assert row["retry_state_label"] == "Payment retry in progress"
    assert row["can_open_hosted_invoice"] is False


def test_enrich_admin_payment_row_adds_hosted_invoice_and_contract_fields():
    row = _enrich_admin_payment_row(
        {
            "source": "subscription",
            "invoice_number": "INV-300",
            "pdf_available": True,
            "payment_status": "PAID",
            "hosted_invoice_url": "https://stripe.test/inv_300",
        }
    )
    assert row["can_open_hosted_invoice"] is True
    assert row["hosted_invoice_unavailable_reason"] is None
    assert isinstance(row["billing_anomaly_flags"], list)

