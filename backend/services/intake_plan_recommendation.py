"""
Intake plan recommendation (UX guidance only).

Billing, entitlements, and Stripe remain authoritative on the server; this module only
derives a suggested plan for pre-filling the CVP intake wizard from risk-check context.

V1 uses property count only; additional signals (agent profile, HMO mix, etc.) can be
folded into recommend_plan_for_intake() later without changing call sites.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, TypedDict

from services.risk_check_scoring import recommended_plan_from_property_count

# Canonical codes returned to the portal (aligned with plan_registry / intake).
_CANONICAL = frozenset({"PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO"})


class IntakePlanRecommendation(TypedDict, total=False):
    recommended_plan_code: Optional[str]
    recommendation_basis: Optional[str]
    recommendation_property_count: Optional[int]


def parse_risk_lead_property_count(raw: Any) -> Optional[int]:
    """
    Return an integer property count suitable for recommendation, or None if unusable.

    Defensive: rejects non-numeric, <1, >100 (aligned with risk check clamping).
    """
    if raw is None:
        return None
    try:
        n = int(float(raw))
    except (TypeError, ValueError):
        return None
    if n < 1 or n > 100:
        return None
    return n


def recommend_plan_from_property_count_only(property_count: int) -> str:
    """
    Map portfolio size to a suggested plan code.

    Delegates to risk_check_scoring so funnel + intake stay aligned.
    """
    pc = max(1, min(100, int(property_count)))
    code = recommended_plan_from_property_count(pc)
    return code if code in _CANONICAL else "PLAN_1_SOLO"


def recommend_plan_for_intake(*, property_count: Optional[int], **_: Any) -> IntakePlanRecommendation:
    """
    Primary entry point for intake prefill. Extra kwargs reserved for future signals.

    Returns recommended_plan_code=None when no qualifying property count exists.
    """
    if property_count is None:
        return {
            "recommended_plan_code": None,
            "recommendation_basis": None,
            "recommendation_property_count": None,
        }
    code = recommend_plan_from_property_count_only(property_count)
    return {
        "recommended_plan_code": code,
        "recommendation_basis": "property_count",
        "recommendation_property_count": property_count,
    }


def build_intake_plan_recommendation_from_risk_lead(lead: Dict[str, Any]) -> IntakePlanRecommendation:
    """Build recommendation dict for GET /risk-check/lead-from-token (sanitized lead row)."""
    n = parse_risk_lead_property_count(lead.get("property_count"))
    if n is None:
        return {
            "recommended_plan_code": None,
            "recommendation_basis": None,
            "recommendation_property_count": None,
        }
    return recommend_plan_for_intake(property_count=n)
