"""
Build and compare commercial intake snapshots for agreement acceptance vs checkout.

Used to block checkout if plan, amounts, or client identity changed after acceptance.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from database import database
from services.plan_registry import PlanCode, plan_registry

logger = logging.getLogger(__name__)


def _format_address_from_property(prop: Dict[str, Any]) -> str:
    parts: List[str] = []
    a1 = (prop.get("address_line_1") or "").strip()
    a2 = (prop.get("address_line_2") or "").strip()
    pc = (prop.get("postcode") or "").strip()
    city = (prop.get("city") or prop.get("town") or "").strip()
    if a1:
        parts.append(a1)
    if a2:
        parts.append(a2)
    if city:
        parts.append(city)
    if pc:
        parts.append(pc)
    return ", ".join(parts) if parts else ""


async def build_commercial_snapshot(
    *,
    client_id: str,
    template_id: str,
    template_version_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Authoritative snapshot of what the user is committing to pay for at this moment.
    Must stay aligned with acceptance record validation.
    """
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        return None

    plan_str = str(client.get("billing_plan") or "PLAN_1_SOLO")
    try:
        plan_code = PlanCode(plan_str)
    except ValueError:
        legacy_mapping = {
            "PLAN_1": PlanCode.PLAN_1_SOLO,
            "PLAN_2_5": PlanCode.PLAN_2_PORTFOLIO,
            "PLAN_6_15": PlanCode.PLAN_3_PRO,
        }
        plan_code = legacy_mapping.get(plan_str, PlanCode.PLAN_1_SOLO)

    plan_def = plan_registry.get_plan(plan_code)
    plan_label = str(plan_def.get("name") or plan_code.value)

    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0, "onboarding_fee_paid": 1}) or {}
    onboarding_already_paid = bool(billing.get("onboarding_fee_paid"))

    monthly_gbp = float(plan_def.get("monthly_price") or 0)
    onboarding_gbp = float(plan_def.get("onboarding_fee") or 0)
    monthly_minor = int(round(monthly_gbp * 100))
    onboarding_minor = 0 if onboarding_already_paid else int(round(onboarding_gbp * 100))

    props = (
        await db.properties.find({"client_id": client_id}, {"_id": 0, "address_line_1": 1, "address_line_2": 1, "postcode": 1, "city": 1, "town": 1})
        .sort([("created_at", 1)])
        .to_list(50)
    )
    client_address = ""
    if props:
        client_address = _format_address_from_property(props[0])

    contact_email = (client.get("contact_email") or client.get("email") or "").strip()
    full_name = (client.get("full_name") or "").strip()
    company = (client.get("company_name") or "").strip()

    return {
        "client_full_name": full_name,
        "client_company_name": company,
        "client_address": client_address,
        "client_email": contact_email,
        "client_phone": (client.get("phone") or "").strip() or None,
        "selected_plan_code": plan_code.value,
        "plan_label": plan_label,
        "billing_amount_minor": monthly_minor,
        "billing_interval": "month",
        "onboarding_fee_minor": onboarding_minor,
        "currency": "GBP",
        "agreement_template_id": template_id,
        "agreement_template_version_id": template_version_id,
    }


def commercial_snapshots_match(
    accepted: Dict[str, Any],
    current: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Return (ok, mismatch_field_messages)."""
    keys = [
        "client_full_name",
        "client_company_name",
        "client_address",
        "client_email",
        "selected_plan_code",
        "plan_label",
        "billing_amount_minor",
        "billing_interval",
        "onboarding_fee_minor",
        "currency",
        "agreement_template_id",
        "agreement_template_version_id",
    ]
    def norm(v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()

    mismatches: List[str] = []
    for k in keys:
        if norm(accepted.get(k)) != norm(current.get(k)):
            mismatches.append(k)
    return (len(mismatches) == 0, mismatches)
