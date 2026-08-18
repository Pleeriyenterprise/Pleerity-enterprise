"""Classification for admin email template runtime metadata (Phase 2)."""

import pytest

from services.email_template_runtime_metadata import (
    get_email_alias_runtime_metadata,
    is_admin_template_content_editable,
    preview_disclaimer_for_alias,
    template_keys_by_alias,
)


def test_monthly_digest_code_built_and_not_editable():
    m = get_email_alias_runtime_metadata("monthly-digest")
    assert m["runtime_source"] == "code_built"
    assert m["admin_editable"] is False
    assert m["edit_risk_level"] == "immutable"
    assert m["db_visible_at_runtime"] is False
    assert is_admin_template_content_editable("monthly-digest") is False


@pytest.mark.parametrize(
    "alias",
    [
        "client-quote-review-required",
        "contractor-invoice-ready",
        "activation-reminder",
    ],
)
def test_bypass_aliases_code_built(alias: str):
    m = get_email_alias_runtime_metadata(alias)
    assert m["runtime_source"] == "code_built"
    assert m["admin_editable"] is False


def test_password_setup_db_backed_editable():
    m = get_email_alias_runtime_metadata("password-setup")
    assert m["runtime_source"] == "db_template"
    assert m["admin_editable"] is True
    assert is_admin_template_content_editable("password-setup") is True


def test_payment_receipt_hybrid_locked():
    m = get_email_alias_runtime_metadata("payment-receipt")
    assert m["runtime_source"] == "hybrid"
    assert m["legal_or_financial_flow"] is True
    assert m["admin_editable"] is False
    assert m["edit_risk_level"] == "high"


def test_subscription_canceled_code_built_locked():
    m = get_email_alias_runtime_metadata("subscription-canceled")
    assert m["runtime_source"] == "code_built"
    assert m["legal_or_financial_flow"] is True
    assert m["edit_risk_level"] == "immutable"
    assert m["admin_editable"] is False


def test_payment_failed_code_built_locked():
    m = get_email_alias_runtime_metadata("payment-failed")
    assert m["runtime_source"] == "code_built"
    assert m["legal_or_financial_flow"] is True
    assert m["admin_editable"] is False


def test_portal_ready_hybrid_editable():
    m = get_email_alias_runtime_metadata("portal-ready")
    assert m["runtime_source"] == "hybrid"
    assert m["admin_editable"] is True


def test_welcome_fallback_only():
    m = get_email_alias_runtime_metadata("welcome")
    assert m["runtime_source"] == "fallback_only"
    assert m["admin_editable"] is True


def test_payment_received_financial_high_editable():
    m = get_email_alias_runtime_metadata("payment-received")
    assert m["runtime_source"] == "db_template"
    assert m["legal_or_financial_flow"] is True
    assert m["edit_risk_level"] == "high"
    assert m["admin_editable"] is True


def test_template_keys_invert_pairs():
    keys = template_keys_by_alias()
    assert "WELCOME_EMAIL" in keys["password-setup"]
    assert "ORDER_CONFIRMATION" in keys["order-intake-confirmation"]
    assert "ADMIN_MANUAL" in keys["admin-manual"]


def test_preview_disclaimer_code_built():
    d = preview_disclaimer_for_alias("monthly-digest")
    assert "not rendered from the database" in d.lower() or "does not guarantee" in d.lower()


def test_preview_disclaimer_hybrid():
    d = preview_disclaimer_for_alias("payment-receipt")
    assert "preview" in d.lower()
