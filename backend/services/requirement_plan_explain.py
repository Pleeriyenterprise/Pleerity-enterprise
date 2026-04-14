"""
Lightweight inclusion/exclusion explanations for registry plan rows (support / staging).

Uses the same property + client inputs as ``build_requirement_plan_for_property``.
Does not change planning logic — only narrates why a row appears or why catalog keys are out of scope.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from services.compliance_requirement_registry import RequirementPlanItem
from services.requirement_catalog import explain_catalog_keys_for_property


def explain_registry_plan_row(
    item: RequirementPlanItem,
    property_doc: Dict,
    client_doc: Optional[Dict],
    *,
    scoring_jurisdiction: str,
) -> str:
    """One-line human-readable reason this plan row is included."""
    pt = (property_doc.get("property_type") or "residential").strip().upper()
    is_hmo = bool(property_doc.get("is_hmo", False)) or pt == "HMO"
    la = (property_doc.get("local_authority") or "").strip().upper()

    if item.catalog_keys:
        expl = explain_catalog_keys_for_property(property_doc, client_doc)
        by_key = {e["catalog_key"]: e for e in expl}
        parts: List[str] = []
        for ck in item.catalog_keys:
            entry = by_key.get(ck)
            if entry:
                parts.append(f"{ck}: {entry['reason']}")
            else:
                parts.append(f"{ck}: linked catalog key")
        base = "; ".join(parts)
        # Core pack rows carry catalog keys for scoring alignment; add cadence note when it is a core slug.
        core_slugs = {
            "gas_safety",
            "eicr",
            "epc",
            "fire_alarm",
            "legionella",
            "hmo_fire_risk",
            "occupation_contract",
            "landlord_registration",
        }
        if item.requirement_type in core_slugs:
            return (
                f"Core cadence ({scoring_jurisdiction}): {item.requirement_type}. "
                f"Catalog mapping: {base}"
            )
        return base

    if item.requirement_type in ("emergency_lighting", "fire_extinguisher"):
        return "HMO expansion job: property is HMO (or property_type HMO)."
    if item.requirement_type == "fire_risk_assessment":
        return "HMO expansion document: fire risk assessment (no separate hmo_fire_risk_evidence row)."
    if item.requirement_type.startswith("communal_"):
        return "Communal areas: has_communal_areas is true."
    if item.requirement_type == "selective_license":
        return f"Selective licensing: local_authority {la} is in configured selective-licensing list."
    if item.requirement_type == "hmo_license":
        return "HMO licence document row (catalog PROPERTY_LICENCE applicable with is_hmo, or hmo_license_required expansion)."

    return f"Registry expansion for scoring jurisdiction {scoring_jurisdiction} (portfolio label on row)."
