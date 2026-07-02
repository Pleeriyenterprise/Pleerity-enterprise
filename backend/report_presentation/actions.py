"""Recommended next actions presentation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

_PRIORITY_ORDER = ("Critical", "High", "Medium", "Informational")


def present_recommended_actions(
    matrix_rows: List[Dict[str, Any]],
    *,
    max_actions: int = 12,
    property_map: Optional[Dict[str, str]] = None,
) -> List[Dict[str, str]]:
    """
    Structured recommended actions for report closing sections.
    Consumes matrix row presentation data — does not determine obligation status.
    """
    property_map = property_map or {}
    actions: List[Dict[str, str]] = []

    def _sort_key(row: Dict[str, Any]) -> int:
        pri = str(row.get("priority") or "Informational")
        try:
            return _PRIORITY_ORDER.index(pri)
        except ValueError:
            return len(_PRIORITY_ORDER)

    sorted_rows = sorted(matrix_rows, key=_sort_key)

    for row in sorted_rows:
        if len(actions) >= max_actions:
            break
        pri = str(row.get("priority") or "Medium")
        if pri == "Informational" and len(actions) >= max_actions // 2:
            continue
        name = str(row.get("obligation") or row.get("requirement_name") or "Obligation").strip()
        prop_id = str(row.get("property_id") or "")
        prop = row.get("property") or property_map.get(prop_id) or ""
        status = str(row.get("status") or "").replace("_", " ").title()
        action = str(row.get("action") or row.get("recommended_action") or "Review and remediate").strip()
        expiry = str(row.get("expiry") or "")
        timeframe = f"Before {expiry}" if expiry and expiry not in ("—", "No date on file") else "As soon as practicable"

        actions.append(
            {
                "priority": pri,
                "required_action": action,
                "reason": f"{name} is {status.lower()} and requires attention.",
                "expected_outcome": f"{name} brought to a satisfactory compliance position.",
                "evidence_required": _evidence_hint(name, row),
                "timeframe": timeframe,
                "property": str(prop)[:80],
                "authority_source": "requirement_authority",
            }
        )

    return actions


def _evidence_hint(name: str, row: Dict[str, Any]) -> str:
    lower = name.lower()
    if "gas" in lower:
        return "Valid Gas Safety Certificate (CP12)"
    if "electric" in lower or "eicr" in lower:
        return "Electrical Installation Condition Report"
    if "epc" in lower or "energy" in lower:
        return "Energy Performance Certificate"
    if row.get("evidence_file"):
        return "Verified supporting document"
    return "Appropriate statutory or supporting evidence"


def format_actions_closing_lines(actions: List[Dict[str, str]], *, detail: str = "full") -> List[str]:
    """Render actions as report closing bullet lines."""
    lines: List[str] = []
    for i, act in enumerate(actions[:8], 1):
        if detail == "summary":
            lines.append(f"{i}. [{act['priority']}] {act['required_action']} — {act['property']}")
        else:
            lines.append(
                f"{i}. [{act['priority']}] {act['required_action']}. "
                f"{act['reason']} Evidence: {act['evidence_required']}. "
                f"Timeframe: {act['timeframe']}."
            )
    if not lines:
        lines.append("No immediate remediation actions identified within export scope.")
    return lines
