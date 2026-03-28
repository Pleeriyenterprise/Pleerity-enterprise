"""
Map Stripe checkout session / invoice lines to CVP customer-facing descriptions and DB breakdown rows.

Amounts use Stripe's smallest currency unit (pence for GBP); field name ``amount`` matches persisted breakdown.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.plan_registry import PlanCode, plan_registry


def _cvp_tier_plan_label(plan_code: PlanCode) -> str:
    tier_labels: Dict[PlanCode, str] = {
        PlanCode.PLAN_1_SOLO: "Solo",
        PlanCode.PLAN_2_PORTFOLIO: "Portfolio",
        PlanCode.PLAN_3_PRO: "Professional",
    }
    tier = tier_labels.get(plan_code)
    if not tier:
        tier = plan_code.value.replace("PLAN_", "").replace("_", " ").title()
    return f"CVP {tier} Plan"


def subscription_line_description(plan_code: PlanCode) -> str:
    return f"{_cvp_tier_plan_label(plan_code)} — Monthly Subscription"


def setup_line_description(plan_code: PlanCode) -> str:
    return f"{_cvp_tier_plan_label(plan_code)} — Setup Fee (One-time)"


def classify_price_for_plan(price_id: Optional[str], plan_code: PlanCode) -> str:
    if not price_id:
        return "other"
    try:
        pids = plan_registry.get_stripe_price_ids(plan_code)
    except Exception:
        return "other"
    if price_id == pids.get("subscription_price_id"):
        return "subscription"
    if price_id == pids.get("onboarding_price_id"):
        return "setup_fee"
    return "other"


def _line_price_id(line_item: Dict[str, Any]) -> Optional[str]:
    price = line_item.get("price")
    if isinstance(price, str):
        return price
    if isinstance(price, dict):
        return price.get("id")
    return None


def build_checkout_pdf_lines_and_breakdown(
    session: Dict[str, Any],
    plan_code: PlanCode,
    *,
    billing_period_note: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Build ReportLab line_items rows and a normalized billing_breakdown for Mongo.

    Each PDF row: description, quantity, unit_pence, line_total_pence.
    Each breakdown row: type, description, amount (Stripe smallest currency unit).
    """
    container = session.get("line_items") or {}
    raw_lines = container.get("data") or []
    pdf_rows: List[Dict[str, Any]] = []
    breakdown: List[Dict[str, Any]] = []
    subscription_note_applied = False

    if not raw_lines:
        return pdf_rows, breakdown

    for li in raw_lines:
        if not isinstance(li, dict):
            continue
        price_id = _line_price_id(li)
        amount = int(li.get("amount_total") if li.get("amount_total") is not None else li.get("amount_subtotal") or 0)
        ltype = classify_price_for_plan(price_id, plan_code)
        if ltype == "subscription":
            desc = subscription_line_description(plan_code)
            if billing_period_note and not subscription_note_applied:
                desc = f"{desc}\n{billing_period_note}"
                subscription_note_applied = True
        elif ltype == "setup_fee":
            desc = setup_line_description(plan_code)
        else:
            price = li.get("price") if isinstance(li.get("price"), dict) else {}
            desc = (
                li.get("description")
                or (price.get("nickname") if isinstance(price, dict) else None)
                or "Billing line"
            )
            ltype = "other"

        qty = int(li.get("quantity") or 1)
        unit_pence = amount // max(qty, 1) if qty else amount
        pdf_rows.append(
            {
                "description": desc,
                "quantity": max(qty, 1),
                "unit_pence": unit_pence,
                "line_total_pence": amount,
            }
        )
        breakdown.append({"type": ltype, "description": desc.split("\n")[0], "amount": amount})

    return pdf_rows, breakdown


def normalize_stripe_invoice_lines(
    invoice: Dict[str, Any],
    plan_code: Optional[PlanCode],
) -> List[Dict[str, Any]]:
    """
    Client/API-facing line rows: description, amount_cents, type.
    type in: subscription | setup_fee | proration | other
    """
    out: List[Dict[str, Any]] = []
    lines = (invoice.get("lines") or {}).get("data") or []
    for line in lines:
        if not isinstance(line, dict):
            continue
        amount = int(line.get("amount") or 0)
        price = line.get("price")
        if isinstance(price, str):
            price_id = price
        elif isinstance(price, dict):
            price_id = price.get("id")
        else:
            price_id = None

        if line.get("proration"):
            desc = line.get("description") or "Proration adjustment"
            out.append({"description": desc, "amount_cents": amount, "type": "proration"})
            continue

        ltype = "other"
        desc = line.get("description") or ""
        if plan_code:
            cls = classify_price_for_plan(price_id, plan_code)
            if cls == "subscription":
                ltype = "subscription"
                desc = subscription_line_description(plan_code)
            elif cls == "setup_fee":
                ltype = "setup_fee"
                desc = setup_line_description(plan_code)
        if ltype == "other" and not desc:
            if isinstance(price, dict):
                desc = price.get("nickname") or str(price.get("product") or "") or "Line item"
            else:
                desc = "Line item"
        out.append({"description": desc, "amount_cents": amount, "type": ltype})
    return out


def breakdown_from_invoice_lines(invoice: Dict[str, Any], plan_code: Optional[PlanCode]) -> List[Dict[str, Any]]:
    """Persisted shape: type, description, amount (pence/cents)."""
    rows = normalize_stripe_invoice_lines(invoice, plan_code)
    return [
        {"type": r["type"], "description": r["description"], "amount": r["amount_cents"]}
        for r in rows
    ]
