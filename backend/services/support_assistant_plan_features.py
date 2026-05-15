"""
Registry-backed CVP plan feature matrix for public support grounding.

Source of truth: plan_registry.FEATURE_MATRIX + FEATURE_METADATA + PLAN_DEFINITIONS.
Used by the AI brain only — not a permission system.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Support-facing grouping (workflow language, not internal feature keys)
_WORKFLOW_GROUPS = (
    ("core", "Core compliance & portfolio"),
    ("documents", "Documents & evidence"),
    ("ai", "AI document handling"),
    ("reporting", "Reports & audit prep"),
    ("communication", "Reminders & notifications"),
    ("portal", "Tenant access"),
    ("integration", "Integrations"),
)


def _category_for_key(feature_key: str, meta: Dict[str, Any]) -> str:
    return (meta.get("category") or "other").strip().lower()


def build_cvp_plan_features_for_support() -> Dict[str, Any]:
    """
    Structured plan capabilities from the live registry — safe for support prompts.
    """
    try:
        from services.plan_registry import (
            FEATURE_MATRIX,
            FEATURE_METADATA,
            PLAN_DEFINITIONS,
            PlanCode,
        )
    except Exception as e:
        logger.warning("support plan features: plan_registry unavailable: %s", e)
        return {"available": False, "plans": [], "note": "Plan feature matrix unavailable."}

    plans_out: List[Dict[str, Any]] = []
    for code in (PlanCode.PLAN_1_SOLO, PlanCode.PLAN_2_PORTFOLIO, PlanCode.PLAN_3_PRO):
        plan_def = PLAN_DEFINITIONS.get(code, {}) or {}
        matrix = FEATURE_MATRIX.get(code, {}) or {}
        enabled_by_category: Dict[str, List[str]] = {}
        for feature_key, is_on in sorted(matrix.items()):
            if not is_on:
                continue
            meta = FEATURE_METADATA.get(feature_key, {}) or {}
            cat = _category_for_key(feature_key, meta)
            label = (meta.get("name") or feature_key).strip()
            enabled_by_category.setdefault(cat, []).append(label)

        plans_out.append(
            {
                "code": code.value,
                "name": plan_def.get("name") or code.value,
                "max_properties": plan_def.get("max_properties"),
                "monthly_price_gbp": plan_def.get("monthly_price"),
                "onboarding_fee_gbp": plan_def.get("onboarding_fee"),
                "enabled_features_by_category": enabled_by_category,
            }
        )

    return {
        "available": True,
        "source": "plan_registry",
        "plans": plans_out,
        "grounding_rule": (
            "State plan inclusion only when listed under enabled_features for that plan. "
            "Do not infer features from plan name or tier."
        ),
    }


def format_plan_features_for_prompt(snapshot: Dict[str, Any]) -> str:
    """Compact text block for the support planner (registry-backed features only)."""
    if not snapshot.get("available"):
        return snapshot.get("note") or "(Plan features unavailable — do not guess plan inclusions.)"

    lines: List[str] = [
        "CVP PLAN FEATURES (registry-backed — only assert inclusions listed here):",
        snapshot.get("grounding_rule", ""),
    ]
    for plan in snapshot.get("plans") or []:
        name = plan.get("name") or plan.get("code")
        props = plan.get("max_properties")
        monthly = plan.get("monthly_price_gbp")
        header = f"- {name}"
        if props is not None:
            header += f" (up to {props} properties"
            if monthly is not None:
                header += f", £{float(monthly):.0f}/mo registry price"
            header += ")"
        lines.append(header)
        by_cat = plan.get("enabled_features_by_category") or {}
        for cat_key, _label in _WORKFLOW_GROUPS:
            items = by_cat.get(cat_key)
            if items:
                lines.append(f"  {cat_key}: {', '.join(items[:12])}")
        # any uncategorised
        for cat_key, items in sorted(by_cat.items()):
            if cat_key in {c[0] for c in _WORKFLOW_GROUPS}:
                continue
            if items:
                lines.append(f"  {cat_key}: {', '.join(items[:8])}")
    return "\n".join(lines)[:12000]
