"""
Build and compare commercial intake snapshots for agreement acceptance vs checkout.

Used to block checkout if plan, amounts, or client identity changed after acceptance.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from database import database
from models.core import IntakeFormData
from services.plan_registry import PlanCode, plan_registry
from utils.client_email import canonical_client_email

logger = logging.getLogger(__name__)


def build_commercial_snapshot_from_intake_form(
    data: IntakeFormData,
    template_id: str,
    template_version_id: str,
    *,
    pilot_invite_doc: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Same commercial fields as ``build_commercial_snapshot`` but from wizard payload before/during intake.
    Onboarding fee assumes not yet paid (new signup).
    """
    plan_str = data.billing_plan.value
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

    monthly_gbp = float(plan_def.get("monthly_price") or 0)
    onboarding_gbp = float(plan_def.get("onboarding_fee") or 0)
    monthly_minor = int(round(monthly_gbp * 100))
    onboarding_minor = int(round(onboarding_gbp * 100))

    snap = {
        "client_full_name": "",
        "client_company_name": "",
        "client_address": "",
        "client_address_raw": "",
        "client_postcode": "",
        "client_email": "",
        "client_phone": None,
        "selected_plan_code": plan_code.value,
        "plan_label": plan_label,
        "billing_amount_minor": monthly_minor,
        "billing_interval": "month",
        "onboarding_fee_minor": onboarding_minor,
        "currency": "GBP",
        "agreement_template_id": template_id,
        "agreement_template_version_id": template_version_id,
    }

    props = list(getattr(data, "properties", None) or [])
    client_address = ""
    client_address_raw = ""
    client_postcode = ""
    if props:
        p0 = props[0].model_dump() if hasattr(props[0], "model_dump") else props[0]
        client_address = _format_address_from_property(p0)
        client_address_raw = _raw_address_from_property(p0)
        client_postcode = _normalize_uk_postcode(p0.get("postcode"))

    contact_email = canonical_client_email(str(getattr(data, "email", "") or ""))
    full_name = (str(getattr(data, "full_name", "") or "")).strip()
    company = (str(getattr(data, "company_name", "") or "")).strip() if getattr(data, "company_name", None) else ""

    snap.update(
        {
            "client_full_name": full_name,
            "client_company_name": company,
            "client_address": client_address,
            "client_address_raw": client_address_raw,
            "client_postcode": client_postcode,
            "client_email": contact_email,
            "client_phone": (str(getattr(data, "phone", "") or "").strip() or None),
        }
    )
    if pilot_invite_doc:
        from services.pilot_commercial_truth import apply_pilot_to_commercial_snapshot, commercial_context_from_invite

        ctx = commercial_context_from_invite(pilot_invite_doc, plan_code=plan_code.value)
        snap = apply_pilot_to_commercial_snapshot(snap, ctx)
    return snap


def _format_address_from_property(prop: Dict[str, Any]) -> str:
    parts: List[str] = []
    a1 = (prop.get("address_line_1") or "").strip()
    a2 = (prop.get("address_line_2") or "").strip()
    pc = _normalize_uk_postcode(prop.get("postcode"))
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


def _raw_address_from_property(prop: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("address_line_1", "address_line_2", "city", "town", "postcode"):
        val = str(prop.get(key) or "").strip()
        if val:
            parts.append(val)
    return "\n".join(parts) if parts else ""


def _normalize_uk_postcode(v: Any) -> str:
    s = str(v or "").strip().upper()
    if not s:
        return ""
    s = " ".join(s.split())
    if len(s.replace(" ", "")) > 3 and " " not in s:
        s = s[:-3] + " " + s[-3:]
    return s


async def build_commercial_snapshot(
    *,
    client_id: str,
    template_id: str,
    template_version_id: str,
    pilot_invite_doc: Optional[Dict[str, Any]] = None,
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

    billing = await db.client_billing.find_one(
        {"client_id": client_id},
        {"_id": 0, "onboarding_fee_paid": 1, "onboarding_fee_waived": 1},
    ) or {}
    onboarding_already_paid = bool(billing.get("onboarding_fee_paid") or billing.get("onboarding_fee_waived"))

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
    client_address_raw = ""
    client_postcode = ""
    if props:
        client_address = _format_address_from_property(props[0])
        client_address_raw = _raw_address_from_property(props[0])
        client_postcode = _normalize_uk_postcode(props[0].get("postcode"))

    contact_email = (client.get("contact_email") or client.get("email") or "").strip()
    full_name = (client.get("full_name") or "").strip()
    company = (client.get("company_name") or "").strip()

    snap = {
        "client_full_name": full_name,
        "client_company_name": company,
        "client_address": client_address,
        "client_address_raw": client_address_raw,
        "client_postcode": client_postcode,
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
    if pilot_invite_doc:
        from services.pilot_commercial_truth import apply_pilot_to_commercial_snapshot, commercial_context_from_invite

        ctx = commercial_context_from_invite(pilot_invite_doc, plan_code=plan_code.value)
        snap = apply_pilot_to_commercial_snapshot(snap, ctx)
    elif client.get("pilot_program_type") or client.get("pilot_status"):
        from services.pilot_commercial_truth import apply_pilot_to_commercial_snapshot, commercial_context_from_client

        ctx = commercial_context_from_client(client, plan_code=plan_code.value)
        if ctx:
            snap = apply_pilot_to_commercial_snapshot(snap, ctx)
    return snap


def commercial_snapshots_match(
    accepted: Dict[str, Any],
    current: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Return (ok, mismatch_field_messages)."""
    keys = [
        "client_full_name",
        "client_company_name",
        "client_address",
        "client_address_raw",
        "client_postcode",
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
