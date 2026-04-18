"""
Registry draft ``conditions`` shape: ``{ "logic": "ALL"|"ANY", "rules": [ { "field", "op", "value"? } ] }``.

Validation and human summaries for admin; :func:`property_matches_registry_conditions` evaluates the
same shape at runtime for planner / preview overlay matching (see ``matching_drafts_for_plan_row``,
``apply_published_registry_entries_to_plan``).
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Optional, Tuple

# Must stay aligned with historical registry drafts and admin validation.
REGISTRY_CONDITION_OPS: FrozenSet[str] = frozenset({"==", "!=", "in", "not_in", "true", "false", "gt", "lt"})

VALID_REGISTRY_CONDITION_FIELDS: FrozenSet[str] = frozenset(
    {
        "is_hmo",
        "has_gas_supply",
        "tenancy_active",
        "furnished",
        "deposit_taken",
        "has_communal_areas",
        "local_authority",
        "property_type",
        "building_age_years",
        "licence_required",
        "cert_gas_safety",
        "cert_licence",
        "licence_type",
    }
)

_BOOL_FIELDS = frozenset(
    {
        "is_hmo",
        "has_gas_supply",
        "tenancy_active",
        "furnished",
        "deposit_taken",
        "has_communal_areas",
        "licence_required",
        "cert_gas_safety",
        "cert_licence",
    }
)
_NUMBER_FIELDS = frozenset({"building_age_years"})
_STRING_FIELDS = frozenset({"local_authority", "property_type", "licence_type"})


def _field_label(field: str) -> str:
    return {
        "is_hmo": "Is HMO",
        "has_gas_supply": "Has gas supply",
        "tenancy_active": "Tenancy active",
        "furnished": "Furnished",
        "deposit_taken": "Deposit taken",
        "has_communal_areas": "Has communal areas",
        "local_authority": "Local authority",
        "property_type": "Property type",
        "building_age_years": "Building age (years)",
        "licence_required": "Licence required",
        "cert_gas_safety": "Gas safety certificate",
        "cert_licence": "Licence certificate",
        "licence_type": "Licence type",
    }.get(field, field.replace("_", " ").title())


def _ops_for_field(field: str) -> FrozenSet[str]:
    if field in _BOOL_FIELDS:
        return frozenset({"true", "false", "==", "!="})
    if field in _NUMBER_FIELDS:
        return frozenset({"==", "!=", "gt", "lt"})
    if field in _STRING_FIELDS:
        return frozenset({"==", "!=", "in", "not_in"})
    return frozenset()


def _format_value(val: Any) -> str:
    if isinstance(val, bool):
        return "Yes" if val else "No"
    if val is None:
        return "—"
    if isinstance(val, list):
        return ", ".join(str(x) for x in val if x is not None and str(x).strip() != "")
    return str(val)


def human_summary_registry_conditions(cond: Optional[Dict[str, Any]]) -> str:
    if not isinstance(cond, dict):
        return ""
    rules = cond.get("rules")
    if not isinstance(rules, list) or not rules:
        return "Applies to all properties (no rules)."
    logic = str(cond.get("logic") or "ALL").upper()
    joiner = "all of the following are true" if logic == "ALL" else "any of the following are true"
    lines: List[str] = []
    for r in rules:
        if not isinstance(r, dict):
            continue
        f = str(r.get("field") or "").strip()
        if not f:
            continue
        op = str(r.get("op") or "").strip()
        val = r.get("value", None)
        label = _field_label(f)
        if op == "true":
            lines.append(f"{label} is Yes")
        elif op == "false":
            lines.append(f"{label} is No")
        elif op == "==":
            lines.append(f"{label} equals {_format_value(val)}")
        elif op == "!=":
            lines.append(f"{label} is not {_format_value(val)}")
        elif op == "in":
            lines.append(f"{label} is one of: {_format_value(val)}")
        elif op == "not_in":
            lines.append(f"{label} is not one of: {_format_value(val)}")
        elif op == "gt":
            lines.append(f"{label} is greater than {_format_value(val)}")
        elif op == "lt":
            lines.append(f"{label} is less than {_format_value(val)}")
        else:
            lines.append(f"{label} ({op})")
    if not lines:
        return "Applies to all properties (no rules)."
    return f"Applies when {joiner}:\n" + "\n".join(f"  • {x}" for x in lines)


def _boolish(val: Any, default: bool = False) -> bool:
    """Align with ``compliance_requirement_registry._boolish`` for consistent applicability."""
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    s = str(val).strip().upper()
    if s in ("NO", "FALSE", "0", ""):
        return False
    if s in ("YES", "TRUE", "1"):
        return True
    return bool(s)


def _norm_property_type(property_doc: Dict[str, Any]) -> str:
    return (property_doc.get("property_type") or "residential").strip().upper()


def _effective_bool_for_field(property_doc: Dict[str, Any], field: str) -> bool:
    if field == "is_hmo":
        return _boolish(property_doc.get("is_hmo"), False) or _norm_property_type(property_doc) == "HMO"
    if field == "has_gas_supply":
        return _boolish(property_doc.get("has_gas_supply"), True)
    return _boolish(property_doc.get(field), False)


def _property_scalar_for_rule(property_doc: Dict[str, Any], field: str) -> Any:
    if field in _BOOL_FIELDS:
        return _effective_bool_for_field(property_doc, field)
    if field == "building_age_years":
        v = property_doc.get("building_age_years")
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
    if field == "property_type":
        return _norm_property_type(property_doc)
    if field == "local_authority":
        return (property_doc.get("local_authority") or "").strip().upper()
    if field == "licence_type":
        return str(property_doc.get("licence_type") or "").strip()
    return None


def _rule_matches_property(property_doc: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    f = str(rule.get("field") or "").strip()
    op = str(rule.get("op") or "").strip()
    if f not in VALID_REGISTRY_CONDITION_FIELDS or op not in REGISTRY_CONDITION_OPS:
        return False
    if op not in _ops_for_field(f):
        return False

    if op == "true":
        return bool(_effective_bool_for_field(property_doc, f)) if f in _BOOL_FIELDS else False
    if op == "false":
        return not bool(_effective_bool_for_field(property_doc, f)) if f in _BOOL_FIELDS else False

    val = rule.get("value")

    if f in _BOOL_FIELDS:
        actual = _effective_bool_for_field(property_doc, f)
        if not isinstance(val, bool):
            return False
        if op == "==":
            return actual == val
        if op == "!=":
            return actual != val
        return False

    if f in _NUMBER_FIELDS:
        actual = _property_scalar_for_rule(property_doc, f)
        if actual is None or isinstance(val, bool):
            return False
        try:
            rhs = int(val) if not isinstance(val, (int, float)) else int(val)
        except (TypeError, ValueError):
            return False
        act = int(actual)
        if op == "==":
            return act == rhs
        if op == "!=":
            return act != rhs
        if op == "gt":
            return act > rhs
        if op == "lt":
            return act < rhs
        return False

    if f in _STRING_FIELDS:
        actual = _property_scalar_for_rule(property_doc, f)
        act_u = str(actual or "").strip().upper()
        if op in ("==", "!=") and isinstance(val, str):
            rhs = str(val).strip().upper()
            if op == "==":
                return act_u == rhs
            return act_u != rhs
        if op in ("in", "not_in") and isinstance(val, list):
            allowed = {str(x).strip().upper() for x in val if isinstance(x, str) and str(x).strip()}
            if not allowed:
                return False
            if op == "in":
                return act_u in allowed
            return act_u not in allowed
        return False

    return False


def property_matches_registry_conditions(
    property_doc: Optional[Dict[str, Any]],
    conditions: Optional[Dict[str, Any]],
) -> bool:
    """
    True when ``property_doc`` satisfies ``conditions`` (AND/OR over rules).

    * ``property_doc is None`` → True (caller has no snapshot; preserve legacy behaviour).
    * Empty or missing ``rules`` → True (applies to all properties).
    """
    if property_doc is None:
        return True
    if not isinstance(conditions, dict):
        return True
    rules = conditions.get("rules")
    if not isinstance(rules, list) or not rules:
        return True
    logic = str(conditions.get("logic") or "ALL").upper()
    results: List[bool] = []
    for r in rules:
        if not isinstance(r, dict):
            results.append(False)
            continue
        results.append(_rule_matches_property(property_doc, r))
    if not results:
        return True
    if logic == "ANY":
        return any(results)
    return all(results)


def validate_registry_conditions(cond: Dict[str, Any]) -> List[str]:
    """Structural and semantic validation for ``conditions`` (registry drafts)."""
    errs: List[str] = []
    if not isinstance(cond, dict):
        errs.append("conditions must be an object")
        return errs
    logic = str(cond.get("logic") or "ALL").upper()
    if logic not in ("ALL", "ANY"):
        errs.append("conditions.logic must be ALL or ANY")
    rules = cond.get("rules")
    if rules is None:
        return errs
    if not isinstance(rules, list):
        errs.append("conditions.rules must be a list")
        return errs

    for i, r in enumerate(rules):
        if not isinstance(r, dict):
            errs.append(f"conditions.rules[{i}] must be an object")
            continue
        f = str(r.get("field") or "").strip()
        if not f:
            errs.append(f"conditions.rules[{i}].field is required")
            continue
        if f not in VALID_REGISTRY_CONDITION_FIELDS:
            errs.append(f"conditions.rules[{i}].field is not an allowed controlled field: {f}")
            continue
        op = str(r.get("op") or "").strip()
        if not op:
            errs.append(f"conditions.rules[{i}].op is required")
            continue
        if op not in REGISTRY_CONDITION_OPS:
            errs.append(f"conditions.rules[{i}].op is not allowed: {op}")
            continue
        allowed = _ops_for_field(f)
        if op not in allowed:
            errs.append(
                f"conditions.rules[{i}]: operator {op!r} is not valid for field {f!r}; "
                f"allowed: {', '.join(sorted(allowed))}",
            )
        if op in ("true", "false"):
            if "value" in r and r.get("value") is not None and str(r.get("value")).strip() != "":
                errs.append(f"conditions.rules[{i}]: op {op!r} must not carry a value")
            continue

        if op in ("==", "!=", "gt", "lt"):
            if "value" not in r:
                errs.append(f"conditions.rules[{i}]: op {op!r} requires a value")
                continue
            val = r["value"]
            if f in _BOOL_FIELDS:
                if not isinstance(val, bool):
                    errs.append(f"conditions.rules[{i}]: value must be boolean for field {f!r}")
            elif f in _NUMBER_FIELDS:
                if isinstance(val, bool):
                    errs.append(f"conditions.rules[{i}]: value must be a number for field {f!r}")
                elif not isinstance(val, (int, float)):
                    try:
                        int(str(val).strip())
                    except (TypeError, ValueError):
                        errs.append(f"conditions.rules[{i}]: value must be a number for field {f!r}")
            elif f in _STRING_FIELDS:
                if not isinstance(val, str) or not str(val).strip():
                    errs.append(f"conditions.rules[{i}]: value must be a non-empty string for field {f!r}")
            continue

        if op in ("in", "not_in"):
            val = r.get("value")
            if not isinstance(val, list) or not val:
                errs.append(f"conditions.rules[{i}]: op {op!r} requires a non-empty list value")
            else:
                for j, item in enumerate(val):
                    if not isinstance(item, str) or not str(item).strip():
                        errs.append(f"conditions.rules[{i}].value[{j}] must be a non-empty string")
    return errs


def condition_builder_options_payload() -> Dict[str, Any]:
    """Merged into GET /controlled-field-options for the visual condition builder."""
    fields_out: List[Dict[str, Any]] = []
    for fid in sorted(VALID_REGISTRY_CONDITION_FIELDS):
        kind = "boolean" if fid in _BOOL_FIELDS else "number" if fid in _NUMBER_FIELDS else "string"
        ops = sorted(_ops_for_field(fid))
        fields_out.append(
            {
                "value": fid,
                "label": _field_label(fid),
                "kind": kind,
                "operators": [
                    {
                        "storage": o,
                        "label": {
                            "true": "Is true (yes)",
                            "false": "Is false (no)",
                            "==": "Equals",
                            "!=": "Does not equal",
                            "in": "Is one of",
                            "not_in": "Is not one of",
                            "gt": "Greater than",
                            "lt": "Less than",
                        }.get(o, o),
                    }
                    for o in ops
                ],
            }
        )
    return {
        "condition_fields": fields_out,
        "condition_logic_options": [
            {"value": "ALL", "label": "All rules must match (AND)"},
            {"value": "ANY", "label": "Any rule may match (OR)"},
        ],
        "condition_templates": [
            {"id": "gas", "label": "Gas properties only", "conditions": {"logic": "ALL", "rules": [{"field": "has_gas_supply", "op": "true"}]}},
            {"id": "hmo", "label": "HMO only", "conditions": {"logic": "ALL", "rules": [{"field": "is_hmo", "op": "true"}]}},
            {"id": "tenancy", "label": "Active tenancy only", "conditions": {"logic": "ALL", "rules": [{"field": "tenancy_active", "op": "true"}]}},
            {"id": "deposit", "label": "Deposit taken only", "conditions": {"logic": "ALL", "rules": [{"field": "deposit_taken", "op": "true"}]}},
            {"id": "communal", "label": "Communal areas only", "conditions": {"logic": "ALL", "rules": [{"field": "has_communal_areas", "op": "true"}]}},
            {"id": "clear", "label": "Clear all rules", "conditions": {"logic": "ALL", "rules": []}},
        ],
    }
