"""Admin read-only diagnostics: requirement workflow class reference vs runtime (drift detection)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from database import database
from middleware import admin_route_guard
from services.compliance_registry_publish_service import fetch_active_published_registry_entries
from services.requirement_truth import enrich_requirements_for_admin
from services.requirement_workflow_audit import (
    audit_projection_from_enriched,
    list_work_order_job_class_mismatches,
)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin-requirement-workflow-audit"],
    dependencies=[Depends(admin_route_guard)],
)


@router.get("/requirement-workflow-audit")
async def get_requirement_workflow_audit(
    client_id: Optional[str] = None,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    include_work_orders: bool = Query(True),
) -> Dict[str, Any]:
    """
    Returns enriched requirement projections with decision-record reference class,
    resolver runtime summary, and mismatch flags. Optional work-order completion slice
    where reference class is not REMEDIATION_JOB.

    Read-only: does not mutate registry, resolver, evidence authority, or workflows.
    """
    db = database.get_db()
    q: Dict[str, Any] = {}
    if client_id:
        q["client_id"] = str(client_id).strip()

    cur = db.requirements.find(q, {"_id": 0}).skip(offset).limit(limit)
    rows: List[Dict[str, Any]] = await cur.to_list(length=limit)
    enriched = await enrich_requirements_for_admin(db, rows)
    items = [audit_projection_from_enriched(e) for e in enriched]

    work_order_mismatches: List[Dict[str, Any]] = []
    if include_work_orders:
        pub = await fetch_active_published_registry_entries(db)
        work_order_mismatches = await list_work_order_job_class_mismatches(
            db,
            published_entries=pub,
            limit=min(200, limit),
        )

    return {
        "items": items,
        "count": len(items),
        "offset": offset,
        "limit": limit,
        "work_order_mismatches": work_order_mismatches,
        "read_only": True,
    }
