"""Invoice/receipt PDF: CVP product line, order add-on rows, totals, header visibility."""
from __future__ import annotations

from datetime import datetime, timezone

from services.invoice_pdf_builder import build_branded_invoice_pdf_bytes, _normalize_line_items
from services.order_receipt_service import (
    _build_order_line_items_for_pdf,
    order_to_invoice_data,
    subscription_session_to_invoice_data,
)
from services.plan_registry import PlanCode, plan_registry
from utils.branding import get_branding_logo_path


def test_cvp_plan_registry_professional_label():
    line = plan_registry.format_cvp_invoice_product_line(PlanCode.PLAN_3_PRO)
    assert line == "Compliance Vault Pro — Professional Plan"


def test_cvp_subscription_invoice_data_includes_billing_period():
    data = subscription_session_to_invoice_data(
        invoice_number="INV-TEST-1",
        order_reference="cs_test_abc",
        customer_name="Test User",
        customer_email="t@example.com",
        primary_line_description=plan_registry.format_cvp_invoice_product_line(PlanCode.PLAN_3_PRO),
        amount_total_pence=22800,
        currency="gbp",
        billing_period_start=datetime(2026, 3, 19, tzinfo=timezone.utc),
        billing_period_end=datetime(2026, 4, 18, tzinfo=timezone.utc),
    )
    desc = data["line_items"][0]["description"]
    assert "Compliance Vault Pro — Professional Plan" in desc
    assert "Billing period: 19 Mar 2026 to 18 Apr 2026" in desc
    assert data["subtotal_pence"] == data["line_items"][0]["line_total_pence"]


def test_cvp_pdf_generates_bytes():
    data = subscription_session_to_invoice_data(
        invoice_number="INV-TEST-2",
        order_reference="cs_x",
        customer_name="A",
        customer_email="a@a.a",
        primary_line_description=plan_registry.format_cvp_invoice_product_line(PlanCode.PLAN_3_PRO),
        amount_total_pence=1000,
        currency="gbp",
    )
    pdf = build_branded_invoice_pdf_bytes(data)
    assert isinstance(pdf, bytes) and len(pdf) > 1500


def test_pdf_logo_path_resolves_default_branding_asset():
    logo = get_branding_logo_path()
    assert logo is not None
    assert logo.replace("\\", "/").endswith("/static/branding/logo.png")


def test_non_cvp_order_with_addons_line_items():
    order = {
        "order_id": "oid-1",
        "order_ref": "PLE-20260319-0002",
        "invoice_number": "INV-2026-000001",
        "customer": {"full_name": "Mr. Thomas Wright", "email": "tw@example.com"},
        "service_code": "DOC_PACK_ESSENTIAL",
        "service_name": "Essential Landlord Document Pack",
        "paid_at": datetime(2026, 3, 19, 17, 16, tzinfo=timezone.utc),
        "pricing_snapshot": {
            "base_price_pence": 7400,
            "addon_total_pence": 4500,
            "total_price_pence": 11900,
            "currency": "gbp",
            "addons": [
                {"code": "FAST_TRACK", "name": "Fast Track Delivery", "price_pence": 2000},
                {"code": "PRINTED_COPY", "name": "Printed Copy", "price_pence": 2500},
            ],
        },
        "pricing": {"total_amount": 11900, "currency": "gbp"},
    }
    items = _build_order_line_items_for_pdf(order)
    assert len(items) == 3
    assert items[0]["description"] == "Essential Landlord Document Pack"
    assert items[1]["description"] == "Fast Track Delivery"
    assert items[2]["description"] == "Printed Copy"
    assert sum(i["line_total_pence"] for i in items) == 11900


def test_order_to_invoice_data_subtotal_matches_line_sum():
    order = {
        "order_id": "oid-2",
        "order_ref": "PLE-1",
        "invoice_number": "INV-9",
        "customer": {"full_name": "A", "email": "a@a.a"},
        "service_name": "Essential Landlord Document Pack",
        "paid_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "pricing_snapshot": {
            "base_price_pence": 7400,
            "total_price_pence": 11900,
            "addons": [
                {"name": "Fast Track Delivery", "price_pence": 2000},
                {"name": "Printed Copy", "price_pence": 2500},
            ],
        },
        "pricing": {"total_amount": 11900},
    }
    data = order_to_invoice_data(order)
    s = sum(li["line_total_pence"] for li in data["line_items"])
    assert s == data["subtotal_pence"] == 11900
    pdf = build_branded_invoice_pdf_bytes(data)
    assert len(pdf) > 1500


def test_normalize_line_items_multi_row():
    data = {
        "line_items": [
            {"description": "A", "quantity": 1, "unit_pence": 100, "line_total_pence": 100},
            {"description": "B", "quantity": 2, "unit_pence": 50, "line_total_pence": 100},
        ],
        "subtotal_pence": 200,
        "total_pence": 200,
        "currency": "gbp",
        "invoice_number": "1",
        "order_reference": "r",
        "date_issued": "d",
        "customer_name": "n",
        "customer_email": "e",
        "payment_status": "PAID",
        "payment_method": "Card",
    }
    rows = _normalize_line_items(data)
    assert len(rows) == 2
    assert _sum_lines(rows) == 200


def _sum_lines(rows):
    return sum(int(x["line_total_pence"]) for x in rows)
