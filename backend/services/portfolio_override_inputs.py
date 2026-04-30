"""
Read-only helpers to build portfolio property breakdown for risk override parity
with /api/portfolio/compliance-summary legacy matrix path (no writes).
"""
from __future__ import annotations

from typing import Any, Dict, List

from utils.risk_bands import score_to_risk_level
from services.scoring_semantics_v1 import resolve_property_score_status
from services.requirement_client_runtime_surface import (
    filter_requirement_rows_for_client_runtime_surfaces,
    project_requirement_row_client_runtime,
)

_MAX_FETCH = 500_000


async def _mongo_find_to_list(cursor: Any, cap: int = _MAX_FETCH) -> List[Dict[str, Any]]:
    if cursor is None:
        return []
    fn = getattr(cursor, "to_list", None)
    if callable(fn):
        return await fn(cap)
    out: List[Dict[str, Any]] = []
    async for doc in cursor:
        out.append(doc)
        if len(out) >= cap:
            break
    return out


def property_persisted_score_row_status(prop: Dict[str, Any]) -> str:
    return resolve_property_score_status(prop)


_REQUIREMENT_POINTS = {
    "VALID": 100,
    "COMPLIANT": 100,
    "EXPIRING_SOON": 70,
    "PENDING": 30,
    "MISSING": 30,
    "OVERDUE": 0,
    "EXPIRED": 0,
}


async def build_portfolio_legacy_property_breakdown_for_override(
    db: Any,
    *,
    client_id: str,
    properties: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Legacy matrix-style per-property rows used by portfolio override (tenant-scoped reads only)."""
    if not properties:
        return []
    client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1}) or {}
    requirements = await _mongo_find_to_list(
        db.requirements.find({"client_id": client_id}, {"_id": 0}),
        cap=_MAX_FETCH,
    )
    requirements = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=requirements,
        client_doc=client_doc,
        properties=properties,
    )
    property_summaries: List[Dict[str, Any]] = []
    for prop in properties:
        pid = prop["property_id"]
        prop_reqs = [
            project_requirement_row_client_runtime(r)
            for r in requirements
            if r.get("property_id") == pid
        ]
        overdue_count = sum(
            1
            for r in prop_reqs
            if (r.get("status") or "").upper().strip() in ("OVERDUE", "EXPIRED")
        )
        expiring_soon_count = sum(
            1
            for r in prop_reqs
            if (r.get("status") or "").upper().strip() == "EXPIRING_SOON"
        )
        if not prop_reqs:
            legacy_matrix_property_score = None
        else:
            points = []
            for r in prop_reqs:
                status_val = (r.get("status") or "PENDING").upper().strip()
                pt = _REQUIREMENT_POINTS.get(status_val, _REQUIREMENT_POINTS["PENDING"])
                points.append(pt)
            legacy_matrix_property_score = round(sum(points) / len(points))
            legacy_matrix_property_score = max(0, min(100, legacy_matrix_property_score))
        matrix_risk = (
            score_to_risk_level(legacy_matrix_property_score)
            if legacy_matrix_property_score is not None
            else None
        )
        name = prop.get("nickname") or prop.get("address_line_1") or pid
        persisted = prop.get("compliance_score")
        st = property_persisted_score_row_status(prop)
        if prop.get("risk_level") is not None:
            risk_out = prop.get("risk_level")
        elif persisted is not None:
            risk_out = score_to_risk_level(int(round(float(persisted))))
        else:
            risk_out = None
        _plc = prop.get("compliance_last_calculated_at")
        if hasattr(_plc, "isoformat"):
            _plc = _plc.isoformat()
        _plc_out = _plc if isinstance(_plc, str) else None
        property_summaries.append(
            {
                "property_id": pid,
                "name": name,
                "nickname": prop.get("nickname"),
                "address_line_1": prop.get("address_line_1"),
                "postcode": prop.get("postcode"),
                "score": persisted,
                "property_score": persisted,
                "preview_legacy_matrix_score": legacy_matrix_property_score,
                "preview_legacy_matrix_risk_level": matrix_risk,
                "risk_level": risk_out,
                "score_status": st,
                "last_calculated_at": _plc_out,
                "overdue_count": overdue_count,
                "expiring_soon_count": expiring_soon_count,
            }
        )
    return property_summaries
