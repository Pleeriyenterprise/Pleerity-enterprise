"""
Live property compliance RAG (GREEN / AMBER / RED) from enriched requirement truth.

Single authority for property cards on GET /client/properties, GET /client/dashboard,
and scheduled compliance_status persistence alignment.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.requirement_attention_eligibility_service import (
    OPERATIONAL_PROPERTY_ATTENTION_REASONS,
    is_requirement_attention_eligible,
)

# Reasons that indicate legal/operational deficiency on a property card.
RED_ATTENTION_REASONS = frozenset({"expired", "rejected", "escalation_review"})


def compute_property_compliance_rag(requirements: List[Dict[str, Any]]) -> str:
    """
    Property-level RAG from enriched, portal-visible requirement rows.

    GREEN — no operational deficiencies (assurance-only review states excluded).
    AMBER — operational action warranted (missing evidence, renewal due, follow-up).
    RED — expired/rejected/escalation legal risk.
    """
    if not requirements:
        return "GREEN"
    has_red = False
    has_amber = False
    for req in requirements:
        eligible, reason, _ = is_requirement_attention_eligible(req)
        if not eligible or not reason:
            continue
        if reason in RED_ATTENTION_REASONS:
            has_red = True
            continue
        if reason in OPERATIONAL_PROPERTY_ATTENTION_REASONS:
            has_amber = True
    if has_red:
        return "RED"
    if has_amber:
        return "AMBER"
    return "GREEN"


async def attach_live_compliance_status_to_properties(
    db,
    *,
    client_id: str,
    client_doc: Optional[Dict[str, Any]],
    properties: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Enrich requirements and attach live ``compliance_status`` to each property dict."""
    from services.requirement_client_runtime_surface import (
        client_portal_surface_visible_row,
        filter_requirement_rows_for_client_runtime_surfaces,
        project_requirement_row_client_runtime,
    )
    from services.requirement_truth import enrich_requirements_for_client

    if not properties:
        return []

    raw_requirements = await db.requirements.find({"client_id": client_id}, {"_id": 0}).to_list(2000)
    raw_requirements = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=raw_requirements,
        client_doc=client_doc or {},
        properties=properties,
    )
    enriched, _ = await enrich_requirements_for_client(db, client_id, list(raw_requirements))
    projected = [project_requirement_row_client_runtime(r) for r in enriched]
    visible = [r for r in projected if client_portal_surface_visible_row(r)]

    reqs_by_property: Dict[str, List[Dict[str, Any]]] = {}
    for r in visible:
        pid = r.get("property_id")
        if pid:
            reqs_by_property.setdefault(str(pid), []).append(r)

    out: List[Dict[str, Any]] = []
    for prop in properties:
        p = dict(prop)
        p["compliance_status"] = compute_property_compliance_rag(
            reqs_by_property.get(str(p.get("property_id")), [])
        )
        out.append(p)
    return out
