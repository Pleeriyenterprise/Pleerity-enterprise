"""
Materialise compliance requirement rows in Mongo from the catalog registry plan.

- Idempotent per (client_id, property_id, requirement_type)
- Upserts cadence / jurisdiction / class / visibility flags when the plan changes
- Reconciles obsolete registry-generated rows (no longer in plan) without deleting audit history
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from database import database
from models import Requirement, RequirementStatus
from services.compliance_requirement_registry import (
    REQUIREMENT_GENERATION_SOURCE_REGISTRY,
    RequirementPlanItem,
    build_requirement_plan_for_property,
)

logger = logging.getLogger(__name__)


def _client_surface_visible_for_class(cls: str) -> bool:
    return str(cls or "").upper() not in ("SYSTEM",)


def _requires_document_for_class(cls: str) -> bool:
    return str(cls or "").upper() == "DOCUMENT"


def _requires_job_for_class(cls: str) -> bool:
    return str(cls or "").upper() == "JOB"


def _registry_metadata(item) -> Dict[str, Any]:
    if not item.catalog_keys:
        return {"catalog_keys": []}
    return {"catalog_keys": list(item.catalog_keys)}


async def materialize_requirements_for_property(
    client_id: str,
    property_id: str,
    *,
    reconcile_obsolete: bool = True,
) -> Dict[str, Any]:
    """
    Load the latest property + client docs, build the registry plan, upsert all rows,
    optionally mark registry-sourced rows not in the plan as NOT_REQUIRED (scoring-neutral).

    Plan rows come **only** from ``build_requirement_plan_for_property(property_doc, client_doc)`` — the
    same function used by ``generate_requirements`` / plan-preview serialization. Preview cannot drift
    from what would be written on the next materialise for the same documents (aside from Mongo
    reconcile / user NOT_REQUIRED rows).
    """
    db = database.get_db()
    property_doc = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0},
    )
    if not property_doc:
        logger.warning("materialize: property not found client_id=%s property_id=%s", client_id, property_id)
        return {"ok": False, "reason": "property_not_found"}

    client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1}) or {}
    plan = build_requirement_plan_for_property(property_doc, client_doc)
    planned_types: Set[str] = {p.requirement_type for p in plan}
    now = datetime.now(timezone.utc)
    upserted = 0

    for item in plan:
        existing = await db.requirements.find_one(
            {
                "client_id": client_id,
                "property_id": property_id,
                "requirement_type": item.requirement_type,
            },
            {"_id": 0},
        )
        csv = _client_surface_visible_for_class(item.compliance_requirement_class)
        meta = _registry_metadata(item)
        patch: Dict[str, Any] = {
            "jurisdiction": item.portfolio_jurisdiction_label,
            "description": item.description,
            "frequency_days": item.frequency_days,
            "requirement_code": item.requirement_code,
            "compliance_requirement_class": item.compliance_requirement_class,
            "is_tracked": item.is_tracked,
            "client_surface_visible": csv,
            "requires_document": _requires_document_for_class(item.compliance_requirement_class),
            "requires_job": _requires_job_for_class(item.compliance_requirement_class),
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_REGISTRY,
            "registry_metadata": meta,
            "updated_at": now.isoformat(),
        }
        if existing:
            rid = existing.get("requirement_id")
            if not rid:
                continue
            if (existing.get("applicability") or "").upper() == "NOT_REQUIRED" and existing.get("not_required_reason"):
                continue
            if (existing.get("applicability") or "").upper() == "NOT_REQUIRED" and not existing.get("not_required_reason"):
                patch["applicability"] = "UNKNOWN"
                patch["status"] = RequirementStatus.PENDING.value
                patch["not_required_reason"] = None
            await db.requirements.update_one({"requirement_id": rid}, {"$set": patch})
        else:
            due = now + timedelta(days=int(item.warning_days))
            req = Requirement(
                client_id=client_id,
                property_id=property_id,
                requirement_type=item.requirement_type,
                requirement_code=item.requirement_code,
                jurisdiction=item.portfolio_jurisdiction_label,
                description=item.description,
                frequency_days=item.frequency_days,
                due_date=due,
                status=RequirementStatus.PENDING,
                compliance_requirement_class=item.compliance_requirement_class,
                is_tracked=item.is_tracked,
                client_surface_visible=csv,
                requires_document=_requires_document_for_class(item.compliance_requirement_class),
                requires_job=_requires_job_for_class(item.compliance_requirement_class),
                requirement_generation_source=REQUIREMENT_GENERATION_SOURCE_REGISTRY,
                registry_metadata=meta,
            )
            doc = req.model_dump()
            for key in ("due_date", "created_at", "updated_at"):
                if doc.get(key):
                    doc[key] = doc[key].isoformat()
            doc["date_source"] = "SYSTEM_ESTIMATED"
            doc["evidence_state"] = "MISSING"
            doc["confidence_state"] = "ESTIMATED"
            await db.requirements.insert_one(doc)
        upserted += 1

    reconciled = 0
    if reconcile_obsolete:
        cursor = db.requirements.find(
            {
                "client_id": client_id,
                "property_id": property_id,
                "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_REGISTRY,
            },
            {"_id": 0},
        )
        async for row in cursor:
            rtype = row.get("requirement_type")
            if not rtype or rtype in planned_types:
                continue
            if row.get("evidence_doc_id"):
                continue
            if row.get("not_required_reason"):
                continue
            st = (row.get("status") or "").upper()
            if st in ("COMPLIANT", "VERIFIED"):
                continue
            await db.requirements.update_one(
                {"requirement_id": row.get("requirement_id")},
                {
                    "$set": {
                        "applicability": "NOT_REQUIRED",
                        "status": RequirementStatus.NOT_REQUIRED.value,
                        "is_tracked": False,
                        "client_surface_visible": False,
                        "requires_document": False,
                        "requires_job": False,
                        "updated_at": now.isoformat(),
                        "registry_metadata": {
                            **(row.get("registry_metadata") or {}),
                            "reconciled_obsolete": True,
                            "reconciled_at": now.isoformat(),
                        },
                    }
                },
            )
            reconciled += 1

    return {
        "ok": True,
        "property_id": property_id,
        "planned_types": sorted(planned_types),
        "upsert_passes": upserted,
        "reconciled_obsolete": reconciled,
    }


def serialize_registry_plan_items(
    items: List[RequirementPlanItem],
    *,
    include_explanations: bool = False,
    property_doc: Optional[Dict[str, Any]] = None,
    client_doc: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Single JSON-shaped serializer for ``RequirementPlanItem`` (admin plan-preview).
    Keep keys aligned with persisted Mongo fields where they overlap (type, code, cadence, class, tracked).
    """
    from services.compliance_rules_registry import scoring_jurisdiction_for_property
    from services.requirement_plan_explain import explain_registry_plan_row

    sj = ""
    if property_doc is not None:
        sj = scoring_jurisdiction_for_property(property_doc, client_doc or {})

    out: List[Dict[str, Any]] = []
    for i in items:
        row: Dict[str, Any] = {
            "requirement_type": i.requirement_type,
            "requirement_code": i.requirement_code,
            "frequency_days": i.frequency_days,
            "warning_days": i.warning_days,
            "jurisdiction": i.portfolio_jurisdiction_label,
            "compliance_requirement_class": i.compliance_requirement_class,
            "is_tracked": i.is_tracked,
            "catalog_keys": list(i.catalog_keys),
        }
        if include_explanations and property_doc is not None:
            row["explanation"] = explain_registry_plan_row(
                i, property_doc, client_doc, scoring_jurisdiction=sj
            )
        out.append(row)
    return out


def generate_requirements(
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]],
    *,
    include_explanations: bool = False,
) -> List[Dict[str, Any]]:
    """
    Pure plan preview (no I/O): same ``(property_doc, client_doc) -> plan`` as
    ``materialize_requirements_for_property`` before persistence. Output is
    ``serialize_registry_plan_items(build_requirement_plan_for_property(...))`` only.
    """
    items = build_requirement_plan_for_property(property_doc, client_doc)
    return serialize_registry_plan_items(
        items,
        include_explanations=include_explanations,
        property_doc=property_doc,
        client_doc=client_doc,
    )
