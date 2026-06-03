"""
Score cognition lines for dashboard / portfolio surfaces.

Aligns headline score presentation with authoritative requirement truth:
blocker KPIs first, then assurance-confidence explanations when score is low
but no operational gaps remain.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

_ASSURANCE_DEFICIT_STATUSES = frozenset(
    {"SATISFIED_UNVERIFIED", "ASSURANCE_PENDING", "NEEDS_REVIEW"}
)
_BLOCKER_DEFICIT_STATUSES = frozenset({"MISSING", "MISSING_EVIDENCE", "EXPIRED"})


def _int_field(row: Dict[str, Any], *keys: str) -> int:
    for key in keys:
        val = row.get(key)
        if val is not None:
            try:
                return int(val)
            except (TypeError, ValueError):
                continue
    return 0


def _headline_score(row: Dict[str, Any]) -> Optional[int]:
    raw = row.get("property_score")
    if raw is None:
        raw = row.get("score")
    if raw is None:
        return None
    try:
        return int(round(float(raw)))
    except (TypeError, ValueError):
        return None


def build_score_risk_explanation(property_row: Dict[str, Any]) -> Optional[str]:
    """Explain elevated score/risk when no blocker KPIs are open."""
    if property_row.get("compliance_score_pending"):
        return None
    overdue = _int_field(property_row, "overdue_count")
    exp = _int_field(property_row, "expiring_30_count", "expiring_soon_count")
    missing = _int_field(property_row, "missing_count")
    if overdue or exp or missing:
        return None

    score = _headline_score(property_row)
    if score is None or score >= 80:
        return None

    deficits: List[Dict[str, Any]] = property_row.get("compliance_top_deficits") or []
    if not deficits:
        return "Score reflects assurance confidence, not active legal breaches"

    statuses = {str(d.get("status") or "").upper() for d in deficits}
    if statuses & _BLOCKER_DEFICIT_STATUSES:
        return None
    if "ASSURANCE_PENDING" in statuses or "NEEDS_REVIEW" in statuses:
        return "Score reflects assurance confidence — some evidence is awaiting verification"
    if "SATISFIED_UNVERIFIED" in statuses:
        return "Score reflects assurance confidence — several requirements rely on self-recorded declarations"
    if statuses <= _ASSURANCE_DEFICIT_STATUSES:
        return "Score reflects assurance confidence, not active legal breaches"
    return "Score reflects assurance confidence, not active legal breaches"


def build_property_score_cognition_line(
    property_row: Dict[str, Any],
    *,
    open_jobs: int = 0,
    show_open_jobs: bool = False,
) -> str:
    """
    Single-line dashboard / portfolio cognition aligned with requirement truth.
    Never returns bare 'No open gaps' when score is low without explanation.
    """
    if property_row.get("compliance_score_pending"):
        return "Score updating — recent compliance changes are being processed"

    overdue = _int_field(property_row, "overdue_count")
    exp = _int_field(property_row, "expiring_30_count", "expiring_soon_count")
    missing = _int_field(property_row, "missing_count")
    parts: List[str] = []
    if overdue > 0:
        parts.append(f"{overdue} overdue")
    if exp > 0:
        parts.append(f"{exp} expiring soon")
    if missing > 0:
        parts.append(f"{missing} missing documents")
    if show_open_jobs and open_jobs > 0:
        parts.append(f"{open_jobs} open jobs")
    if parts:
        return " · ".join(parts)

    explanation = build_score_risk_explanation(property_row)
    if explanation:
        return explanation

    score = _headline_score(property_row)
    if score is not None and score >= 80:
        return "No open gaps in this snapshot"
    if score is not None:
        return "No open blockers — score reflects assurance confidence"
    return "No open gaps in this snapshot"


def portfolio_property_cognition_fields(
    persisted_row: Dict[str, Any],
    catalog_kpis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge persisted score metadata with catalog KPIs for API payloads."""
    catalog_kpis = catalog_kpis or {}
    cognition_input = {
        "property_score": persisted_row.get("compliance_score"),
        "score": persisted_row.get("compliance_score"),
        "compliance_score_pending": persisted_row.get("compliance_score_pending"),
        "compliance_top_deficits": persisted_row.get("compliance_top_deficits") or [],
        "overdue_count": catalog_kpis.get("overdue_count", 0),
        "expiring_30_count": catalog_kpis.get("expiring_30_count", catalog_kpis.get("expiring_soon_count", 0)),
        "missing_count": catalog_kpis.get("missing_count", 0),
    }
    return {
        "compliance_score_pending": bool(persisted_row.get("compliance_score_pending")),
        "compliance_top_deficits": persisted_row.get("compliance_top_deficits") or [],
        "compliance_top_next_actions": persisted_row.get("compliance_top_next_actions") or [],
        "score_cognition_line": build_property_score_cognition_line(cognition_input),
        "score_risk_explanation": build_score_risk_explanation(cognition_input),
    }
