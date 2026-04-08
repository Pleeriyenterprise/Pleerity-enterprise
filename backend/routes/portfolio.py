"""
Portfolio compliance summary for Audit Intelligence Platform.
GET /api/portfolio/compliance-summary: catalog-driven when catalog present, else legacy.
GET /api/portfolio/properties/{id}/compliance-detail: matrix, score, risk (catalog-driven).
"""
from fastapi import APIRouter, Request, Depends, status, HTTPException
from fastapi import Query
from database import database
from middleware import client_route_guard
from utils.risk_bands import score_to_risk_level
from services.catalog_compliance import (
    get_property_compliance_detail,
    get_portfolio_compliance_from_catalog,
)
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"], dependencies=[Depends(client_route_guard)])

REQUIREMENT_POINTS = {
    "VALID": 100,
    "COMPLIANT": 100,
    "EXPIRING_SOON": 70,
    "PENDING": 30,
    "MISSING": 30,
    "OVERDUE": 0,
    "EXPIRED": 0,
}


@router.get("/compliance-summary")
async def get_compliance_summary(request: Request):
    """
    Portfolio compliance summary. Uses catalog-driven scoring when requirements_catalog is populated;
    otherwise falls back to legacy (equal weight, fixed points). Returns portfolio_score, risk_level,
    and when catalog-driven: updated_at, kpis, properties with name, score, risk_level, overdue_count,
    expiring_30_count, missing_count.
    """
    user = await client_route_guard(request)
    client_id = user["client_id"]
    catalog_result = await get_portfolio_compliance_from_catalog(client_id)
    if catalog_result:
        return {
            "portfolio_score": catalog_result["portfolio_score"],
            "risk_level": catalog_result["risk_level"],
            "portfolio_risk_level": catalog_result.get("portfolio_risk_level", catalog_result["risk_level"]),
            "updated_at": catalog_result.get("updated_at", datetime.now(timezone.utc).isoformat()),
            "kpis": catalog_result.get("kpis", {}),
            "properties": [
                {
                    "property_id": p["property_id"],
                    "name": p.get("name"),
                    "nickname": p.get("nickname"),
                    "address_line_1": p.get("address_line_1"),
                    "postcode": p.get("postcode"),
                    "property_score": p.get("score"),
                    "score": p.get("score"),
                    "risk_level": p["risk_level"],
                    "overdue_count": p.get("overdue_count", 0),
                    "expiring_soon_count": p.get("expiring_30_count", 0),
                    "expiring_30_count": p.get("expiring_30_count", 0),
                    "missing_count": p.get("missing_count", 0),
                }
                for p in catalog_result.get("properties", [])
            ],
        }
    # Legacy path
    db = database.get_db()
    properties = await db.properties.find(
        {"client_id": client_id},
        {"_id": 0, "property_id": 1, "address_line_1": 1, "postcode": 1, "nickname": 1},
    ).to_list(100)
    if not properties:
        return {
            "portfolio_score": 100,
            "risk_level": "Low Risk",
            "properties": [],
        }
    requirements = await db.requirements.find(
        {"client_id": client_id},
        {"_id": 0, "property_id": 1, "status": 1},
    ).to_list(1000)
    total_weighted_score = 0.0
    total_requirements = 0
    property_summaries = []
    for prop in properties:
        pid = prop["property_id"]
        prop_reqs = [r for r in requirements if r.get("property_id") == pid]
        overdue_count = sum(1 for r in prop_reqs if r.get("status") in ("OVERDUE", "EXPIRED"))
        expiring_soon_count = sum(1 for r in prop_reqs if r.get("status") == "EXPIRING_SOON")
        if not prop_reqs:
            property_score = 100
        else:
            points = []
            for r in prop_reqs:
                status_val = (r.get("status") or "PENDING").upper().strip()
                pt = REQUIREMENT_POINTS.get(status_val, REQUIREMENT_POINTS["PENDING"])
                points.append(pt)
            property_score = round(sum(points) / len(points))
            property_score = max(0, min(100, property_score))
        risk_level = score_to_risk_level(property_score)
        total_weighted_score += property_score * len(prop_reqs)
        total_requirements += len(prop_reqs)
        name = prop.get("nickname") or prop.get("address_line_1") or pid
        property_summaries.append({
            "property_id": pid,
            "name": name,
            "nickname": prop.get("nickname"),
            "address_line_1": prop.get("address_line_1"),
            "postcode": prop.get("postcode"),
            "property_score": property_score,
            "risk_level": risk_level,
            "overdue_count": overdue_count,
            "expiring_soon_count": expiring_soon_count,
        })
    if total_requirements == 0:
        portfolio_score = 100
    else:
        portfolio_score = round(total_weighted_score / total_requirements)
        portfolio_score = max(0, min(100, portfolio_score))
    portfolio_risk = score_to_risk_level(portfolio_score)
    return {
        "portfolio_score": portfolio_score,
        "risk_level": portfolio_risk,
        "properties": property_summaries,
    }


@router.get("/properties/{property_id}/compliance-detail")
async def get_property_compliance_detail_route(request: Request, property_id: str):
    """
    Property-level compliance detail: requirement matrix (from catalog + state), property_score,
    risk_index, risk_level, score_delta, score_change_summary, last_updated_at. Evidence-based status only; not legal advice.
    """
    user = await client_route_guard(request)
    client_id = user["client_id"]
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0, "property_id": 1, "nickname": 1, "address_line_1": 1, "compliance_score": 1, "risk_level": 1, "compliance_last_calculated_at": 1},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    detail = await get_property_compliance_detail(client_id, property_id)
    if detail is not None:
        response = dict(detail)
        # Prefer matrix-computed score/risk so property detail matches the requirements matrix (no stale stored values)
        if response.get("property_score") is not None:
            response["score"] = response["property_score"]
        if response.get("risk_level") is not None:
            response["risk_level"] = response["risk_level"]
    else:
        # Fallback: no catalog or no applicable; return minimal from requirements
        requirements = await db.requirements.find(
            {"client_id": client_id, "property_id": property_id},
            {"_id": 0, "requirement_id": 1, "requirement_type": 1, "status": 1, "due_date": 1, "description": 1},
        ).to_list(200)
        from services.catalog_compliance import _days_to_expiry, _requirement_numeric_score
        matrix = []
        for r in requirements:
            due = r.get("due_date")
            days = _days_to_expiry(due)
            matrix.append({
                "requirement_code": r.get("requirement_type"),
                "title": r.get("description") or r.get("requirement_type"),
                "status": r.get("status") or "PENDING",
                "numeric_score": _requirement_numeric_score(r.get("status"), due),
                "criticality": "MED",
                "weight": 1,
                "expiry_date": due.isoformat() if hasattr(due, "isoformat") else due,
                "days_to_expiry": days,
                "evidence_doc_id": None,
                "requirement_id": r.get("requirement_id"),
            })
        if not matrix:
            property_score = 100
        else:
            property_score = round(sum(m["numeric_score"] for m in matrix) / len(matrix))
        kpis = {"overdue": 0, "expiring_30": 0, "missing": 0, "compliant": 0}
        for m in matrix:
            s = (m.get("status") or "PENDING").upper()
            if s in ("OVERDUE", "EXPIRED"):
                kpis["overdue"] += 1
            elif s == "EXPIRING_SOON" and (m.get("days_to_expiry") or 0) <= 30:
                kpis["expiring_30"] += 1
            elif s in ("PENDING", "MISSING"):
                kpis["missing"] += 1
            else:
                kpis["compliant"] += 1
        response = {
            "property_id": property_id,
            "property_name": prop.get("nickname") or prop.get("address_line_1") or property_id,
            "matrix": matrix,
            "property_score": property_score,
            "risk_index": 0.0,
            "risk_level": score_to_risk_level(property_score),
            "kpis": kpis,
        }
    # Enrich with score change tracking and last updated (score/risk already set from detail when available)
    response.setdefault("score", prop.get("compliance_score"))
    response.setdefault("risk_level", prop.get("risk_level"))
    response["last_updated_at"] = response.get("last_updated_at") or prop.get("compliance_last_calculated_at")
    latest_log = await db.score_change_log.find_one(
        {"property_id": property_id, "client_id": client_id},
        sort=[("created_at", -1)],
        projection={"_id": 0, "delta": 1, "changed_requirements": 1, "created_at": 1},
    )
    if latest_log and latest_log.get("delta") is not None:
        response["score_delta"] = latest_log["delta"]
        changed = latest_log.get("changed_requirements") or []
        if changed:
            response["score_change_summary"] = f"{'Up' if latest_log['delta'] and latest_log['delta'] > 0 else 'Down'} {abs(latest_log['delta'])} pts; {len(changed)} requirement(s) changed"
        else:
            response["score_change_summary"] = f"{'Up' if latest_log['delta'] > 0 else 'Down'} {abs(latest_log['delta'])} pts" if latest_log["delta"] else "No change"
    else:
        response["score_delta"] = None
        response["score_change_summary"] = None
    prop_full = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0, "jurisdiction": 1},
    ) or {}
    client_doc = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "default_jurisdiction": 1},
    ) or {}
    from services.compliance_rules_registry import (
        jurisdiction_attribution_for_property,
        log_jurisdiction_resolution_debug,
        resolve_portfolio_jurisdiction,
    )

    _jr = resolve_portfolio_jurisdiction(prop_full, client_doc)
    log_jurisdiction_resolution_debug(
        context="portfolio.compliance-detail",
        property_id=property_id,
        raw_property_jurisdiction=prop_full.get("jurisdiction"),
        raw_client_default_jurisdiction=client_doc.get("default_jurisdiction"),
        resolution=_jr,
    )
    _att = jurisdiction_attribution_for_property(prop_full, client_doc, _resolution=_jr)
    response["compliance_basis"] = _att["compliance_basis"]
    response["effective_jurisdiction_label"] = _att["effective_jurisdiction_label"]
    response["jurisdiction_source"] = _att["jurisdiction_source"]
    response["client_default_jurisdiction"] = client_doc.get("default_jurisdiction")
    return response


@router.get("/properties/{property_id}/score-history")
async def get_property_score_history_route(request: Request, property_id: str, limit: int = 20):
    """Return last N score change log entries for this property (client-scoped)."""
    user = await client_route_guard(request)
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0, "property_id": 1},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    limit = min(max(1, limit), 50)
    entries = await db.score_change_log.find(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0, "previous_score": 1, "new_score": 1, "delta": 1, "reason": 1, "changed_requirements": 1, "created_at": 1},
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return {"property_id": property_id, "entries": entries}


@router.get("/properties/{property_id}/timeline")
async def get_property_timeline_route(
    request: Request,
    property_id: str,
    category: Optional[str] = Query(None, description="Filter by category: EVIDENCE, COMPLIANCE, MAINTENANCE, SCORE_RISK, SYSTEM"),
    actor_type: Optional[str] = Query(None, description="Filter by actor: user, admin, system"),
    from_date: Optional[str] = Query(None, description="From date YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="To date YYYY-MM-DD"),
    limit: int = Query(50, ge=1, le=100),
    cursor: Optional[str] = Query(None, description="Pagination cursor (last timestamp)"),
):
    """Unified property timeline: evidence, compliance, maintenance, score events. Chronological, newest first."""
    user = await client_route_guard(request)
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0, "property_id": 1},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    try:
        from services.property_timeline_service import get_property_timeline
        data = await get_property_timeline(
            client_id=user["client_id"],
            property_id=property_id,
            category=category,
            actor_type=actor_type,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            cursor=cursor,
        )
        return data
    except Exception as e:
        logger.exception("Property timeline error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load timeline",
        )


@router.get("/properties/{property_id}/evidence")
async def get_property_evidence(request: Request, property_id: str):
    """
    Evidence vault data for the Property Evidence tab: summary, documents, recent events.
    Composes existing documents list + requirements + timeline (EVIDENCE category).
    Additive; does not replace GET /documents.
    """
    user = await client_route_guard(request)
    client_id = user["client_id"]
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0, "property_id": 1},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    # Documents for this property (exclude file_path)
    documents = await db.documents.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0, "file_path": 0},
    ).sort("uploaded_at", -1).to_list(500)

    # Requirements for this property (for missing-critical count)
    requirements = await db.requirements.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0, "requirement_id": 1, "status": 1, "applicability": 1},
    ).to_list(200)

    # Linked: documents that have a requirement linked
    linked = sum(1 for d in documents if d.get("requirement_id"))
    # Requirement IDs that have at least one document linked
    linked_req_ids = {d.get("requirement_id") for d in documents if d.get("requirement_id")}
    need_evidence_statuses = {"MISSING", "PENDING", "OVERDUE", "EXPIRING_SOON"}
    missing_critical = sum(
        1 for r in requirements
        if (r.get("status") or "").upper() in need_evidence_statuses
        and (r.get("applicability") or "").upper() != "NOT_REQUIRED"
        and r.get("requirement_id") not in linked_req_ids
    )

    # Pending confirmation: has extraction but status != VERIFIED
    def _has_extraction(doc):
        if doc.get("extraction_id"):
            return True
        ai = doc.get("ai_extraction") or {}
        return ai.get("status") == "completed" and ai.get("data")
    pending_confirmation = sum(
        1 for d in documents
        if _has_extraction(d) and (d.get("status") or "").upper() != "VERIFIED"
    )

    last_uploaded_at = None
    for d in documents:
        u = d.get("uploaded_at")
        if u:
            last_uploaded_at = u
            break

    summary = {
        "totalDocuments": len(documents),
        "linked": linked,
        "pendingConfirmation": pending_confirmation,
        "missingCriticalEvidence": missing_critical,
        "lastUploadedAt": last_uploaded_at,
    }

    # Recent evidence events from timeline
    try:
        from services.property_timeline_service import get_property_timeline
        timeline_data = await get_property_timeline(
            client_id=client_id,
            property_id=property_id,
            category="EVIDENCE",
            limit=20,
        )
        recent_events = (timeline_data.get("items") or [])[:20]
    except Exception as e:
        logger.warning("Evidence timeline fallback: %s", e)
        recent_events = []

    return {
        "summary": summary,
        "documents": documents,
        "recentEvents": recent_events,
    }


# Client-visible audit timeline (same event types as admin timeline, excluding admin-only actions)
_TIMELINE_ACTIONS = [
    "INTAKE_SUBMITTED",
    "INTAKE_PROPERTY_ADDED",
    "INTAKE_DOCUMENT_UPLOADED",
    "PROVISIONING_STARTED",
    "PROVISIONING_COMPLETE",
    "PROVISIONING_FAILED",
    "PASSWORD_TOKEN_GENERATED",
    "PASSWORD_SET_SUCCESS",
    "PASSWORD_SETUP_LINK_RESENT",
    "PORTAL_INVITE_RESENT",
    "PORTAL_INVITE_EMAIL_FAILED",
    "USER_LOGIN_SUCCESS",
    "USER_LOGIN_FAILED",
    "DOCUMENT_UPLOADED",
    "DOCUMENT_VERIFIED",
    "DOCUMENT_REJECTED",
    "DOCUMENT_AI_ANALYZED",
    "EMAIL_SENT",
    "REMINDER_SENT",
    "DIGEST_SENT",
    "COMPLIANCE_STATUS_UPDATED",
]


@router.get("/audit-timeline")
async def get_portfolio_audit_timeline(request: Request, limit: int = 50):
    """
    Get audit timeline for the authenticated client (read-only).
    Key events: intake, provisioning, auth, documents, notifications, compliance.
    Does not include admin-only actions.
    """
    user = await client_route_guard(request)
    client_id = user["client_id"]
    db = database.get_db()
    limit = max(1, min(100, limit))
    logs = await db.audit_logs.find(
        {"client_id": client_id, "action": {"$in": _TIMELINE_ACTIONS}},
        {"_id": 0},
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    categorized = {
        "intake": [],
        "provisioning": [],
        "authentication": [],
        "documents": [],
        "notifications": [],
        "compliance": [],
    }
    for log in logs:
        action = log.get("action", "")
        if action.startswith("INTAKE_"):
            categorized["intake"].append(log)
        elif action.startswith("PROVISIONING_"):
            categorized["provisioning"].append(log)
        elif action in [
            "PASSWORD_TOKEN_GENERATED", "PASSWORD_SET_SUCCESS", "PASSWORD_SETUP_LINK_RESENT",
            "PORTAL_INVITE_RESENT", "PORTAL_INVITE_EMAIL_FAILED", "USER_LOGIN_SUCCESS", "USER_LOGIN_FAILED",
        ]:
            categorized["authentication"].append(log)
        elif action.startswith("DOCUMENT_"):
            categorized["documents"].append(log)
        elif action in ["EMAIL_SENT", "REMINDER_SENT", "DIGEST_SENT"]:
            categorized["notifications"].append(log)
        elif action.startswith("COMPLIANCE_"):
            categorized["compliance"].append(log)
    return {
        "client_id": client_id,
        "timeline": logs,
        "categorized": categorized,
        "total_events": len(logs),
    }
