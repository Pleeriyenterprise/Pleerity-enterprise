"""
Portfolio compliance summary for Audit Intelligence Platform.
GET /api/portfolio/compliance-summary returns portfolio_score, risk_level, and per-property summary.
Uses task-defined requirement-level points (VALID=100, EXPIRING_SOON=70, MISSING=30, OVERDUE=0)
and portfolio weighting by requirement count. Does not replace existing /client/compliance-score.
"""
from fastapi import APIRouter, Request, Depends, status
from database import database
from middleware import client_route_guard
from utils.risk_bands import score_to_risk_level
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"], dependencies=[Depends(client_route_guard)])

# Task-defined requirement status -> points (no legal certification implied)
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
    Portfolio compliance summary for Audit Intelligence views.
    Returns portfolio_score, risk_level, and per-property summary.
    Evidence-based status only; not legal advice or certification.
    """
    user = await client_route_guard(request)
    client_id = user["client_id"]
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

    # Per-property: requirement-level points -> weighted average = property score
    # (Equal weight per requirement as per task: "weighted average of requirement scores".)
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
        property_summaries.append({
            "property_id": pid,
            "property_score": property_score,
            "risk_level": risk_level,
            "overdue_count": overdue_count,
            "expiring_soon_count": expiring_soon_count,
        })

    # Portfolio score: weighted average across properties by requirement count
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
