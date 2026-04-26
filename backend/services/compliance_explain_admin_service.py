"""
Admin-only explainability for client compliance KPIs (canonical runtime projection).

Builds on the same filter + projection path as ``calculate_compliance_score`` stats.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from database import database
from services.compliance_rules_registry import jurisdiction_attribution_for_property
from services.requirement_client_runtime_surface import (
    filter_requirement_rows_for_client_runtime_surfaces,
    client_portal_surface_visible_row,
    project_requirement_row_client_runtime,
    compute_client_portal_requirement_stats,
)


def _overdue_reason(row: Dict[str, Any]) -> str:
    st = (str(row.get("status") or "")).upper()
    if st in ("OVERDUE", "EXPIRED"):
        return f"status={st}"
    return ""


def _visibility_reason(row: Dict[str, Any]) -> str:
    if row.get("client_surface_visible") is False:
        return "client_surface_visible=false (excluded from portal KPIs)"
    return "visible"


async def build_admin_client_compliance_explain(client_id: str) -> Dict[str, Any]:
    db = database.get_db()
    client_row = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}
    properties = await db.properties.find({"client_id": client_id}, {"_id": 0}).to_list(500)
    raw = await db.requirements.find({"client_id": client_id}, {"_id": 0}).to_list(5000)
    filtered = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=raw,
        client_doc=client_row,
        properties=properties,
    )
    projected_all = [project_requirement_row_client_runtime(r) for r in filtered]
    portal_rows = [r for r in projected_all if client_portal_surface_visible_row(r)]
    counts = compute_client_portal_requirement_stats(portal_rows)

    prop_by_id = {p["property_id"]: p for p in properties if p.get("property_id")}
    explain_rows: List[Dict[str, Any]] = []
    for r in projected_all:
        pid = r.get("property_id")
        prop = prop_by_id.get(pid or "", {}) or {}
        att = jurisdiction_attribution_for_property(prop, client_row) if pid else {}
        visible = client_portal_surface_visible_row(r)
        st = (str(r.get("status") or "PENDING")).upper()
        explain_rows.append(
            {
                "requirement_id": r.get("requirement_id"),
                "property_id": pid,
                "requirement_type": r.get("requirement_type"),
                "canonical_status": st,
                "due_date": r.get("due_date"),
                "evidence_state": r.get("evidence_state"),
                "client_surface_visible": visible,
                "visibility_reason": _visibility_reason(r),
                "jurisdiction_basis": {
                    "effective_jurisdiction_label": att.get("effective_jurisdiction_label"),
                    "jurisdiction_source": att.get("jurisdiction_source"),
                    "compliance_basis": att.get("compliance_basis"),
                },
                "overdue_reason": _overdue_reason(r) if visible else "",
                "included_in_portal_kpis": visible,
                "scoring_contribution_note": "Persisted property score uses compliance_scoring_service with the same portal-filtered + projected requirement rows as KPI counts.",
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "client_id": client_id,
        "authority": "project_requirement_row_client_runtime + filter_requirement_rows_for_client_runtime_surfaces + client_portal_surface_visible_row",
        "portfolio_counts": counts,
        "rows": explain_rows,
    }
