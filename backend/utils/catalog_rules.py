"""
Rule evaluator for requirements_catalog applies_to.
Used only for read-side compliance (compliance-detail, compliance-summary).
Supports applies_to with keys all/any and leaf conditions {field, op, value}.
Ops: ==, !=, in, not_in, exists, true, false.
Property profile is a flat dict (e.g. from property document).
"""
from typing import Any, Dict


def _eval_leaf(profile: Dict[str, Any], condition: Dict[str, Any]) -> bool:
    """Evaluate a single leaf condition: {field, op, value}."""
    field = condition.get("field")
    op = (condition.get("op") or "==").strip().lower()
    val = condition.get("value")
    profile_val = profile.get(field) if field is not None else None

    if op == "true":
        return bool(profile_val) is True
    if op == "false":
        return bool(profile_val) is False
    if op == "exists":
        return (field in profile) == (val if val is not None else True)
    if op == "==":
        return profile_val == val
    if op == "!=":
        return profile_val != val
    if op == "in":
        if val is None or not isinstance(val, list):
            return False
        return profile_val in val
    if op == "not_in":
        if val is None or not isinstance(val, list):
            return True
        return profile_val not in val
    return False


def evaluate_applies_to(profile: Dict[str, Any], applies_to: Any) -> bool:
    """
    Given a property profile dict and applies_to (from catalog), return whether the requirement applies.
    applies_to can be:
    - None / missing: requirement applies to all.
    - Dict with "all": list of conditions (AND) or nested {all/any} dicts.
    - Dict with "any": list of conditions (OR) or nested {all/any} dicts.
    - A single leaf condition {field, op, value}.
    """
    if applies_to is None:
        return True
    if not isinstance(applies_to, dict):
        return True

    if "all" in applies_to:
        items = applies_to["all"]
        if not isinstance(items, list):
            return True
        return all(_eval_group(profile, item) for item in items)
    if "any" in applies_to:
        items = applies_to["any"]
        if not isinstance(items, list):
            return True
        return any(_eval_group(profile, item) for item in items)

    # Single leaf
    return _eval_leaf(profile, applies_to)


def _eval_group(profile: Dict[str, Any], item: Any) -> bool:
    """Evaluate one item in an all/any list (can be nested all/any or leaf)."""
    if isinstance(item, dict) and ("all" in item or "any" in item):
        return evaluate_applies_to(profile, item)
    if isinstance(item, dict) and ("field" in item or "op" in item):
        return _eval_leaf(profile, item)
    return False


def build_property_profile(property_doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a flat profile from a property document for the rule evaluator.
    Normalizes keys so applies_to can reference e.g. is_hmo, has_gas_supply, local_authority.
    """
    return {
        "property_type": (property_doc.get("property_type") or "").strip(),
        "is_hmo": bool(property_doc.get("is_hmo", False)),
        "hmo_license_required": bool(property_doc.get("hmo_license_required", False)),
        "has_gas_supply": bool(property_doc.get("has_gas_supply", True)),
        "has_gas": bool(property_doc.get("has_gas", property_doc.get("has_gas_supply", True))),
        "building_age_years": property_doc.get("building_age_years"),
        "has_communal_areas": bool(property_doc.get("has_communal_areas", False)),
        "local_authority": (property_doc.get("local_authority") or "").strip().upper(),
        "licence_required": (property_doc.get("licence_required") or "").strip().upper(),
    }
