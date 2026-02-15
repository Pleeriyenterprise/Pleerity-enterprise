"""
Enterprise compliance scoring: single source of truth for property-level score.
Deterministic, event-driven recalculation, persisted on Property + history + audit.

All score changes must go through recalculate_and_persist(); no route implements
its own scoring. Dashboard and GET /compliance-score read stored property scores.
"""
from database import database
from datetime import datetime, timezone, date, timedelta
from typing import Dict, Any, Optional, List
import logging

from services.compliance_score import (
    get_requirement_weight,
    REQUIREMENT_TYPE_WEIGHTS,
    DEFAULT_REQUIREMENT_WEIGHT,
)

logger = logging.getLogger(__name__)

WEIGHTS_VERSION = "v1"

# Reasons for score change (used in history and audit)
REASON_DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
REASON_DOCUMENT_DELETED = "DOCUMENT_DELETED"
REASON_AI_APPLIED = "AI_APPLIED"
REASON_REQUIREMENT_CHANGED = "REQUIREMENT_CHANGED"
REASON_EXPIRY_ROLLOVER = "EXPIRY_ROLLOVER"
REASON_PROPERTY_CREATED = "PROPERTY_CREATED"
REASON_LAZY_BACKFILL = "LAZY_BACKFILL"


def _parse_due_date(due_date_str) -> Optional[datetime]:
    if not due_date_str:
        return None
    try:
        if isinstance(due_date_str, datetime):
            return due_date_str.replace(tzinfo=timezone.utc) if due_date_str.tzinfo is None else due_date_str
        s = due_date_str.replace("Z", "+00:00") if isinstance(due_date_str, str) else str(due_date_str)
        return datetime.fromisoformat(s)
    except Exception:
        return None


async def calculate_property_compliance(
    property_id: str,
    as_of_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Compute compliance score for a single property from current DB state.
    Deterministic: same DB state + same as_of_date -> same result.
    as_of_date defaults to today (UTC); pass explicitly for tests.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    if as_of_date is not None:
        now = datetime.combine(as_of_date, now.time(), tzinfo=timezone.utc)

    property_doc = await db.properties.find_one(
        {"property_id": property_id},
        {"_id": 0, "property_id": 1, "client_id": 1, "is_hmo": 1}
    )
    if not property_doc:
        return {
            "score": 0,
            "breakdown": {},
            "weights_version": WEIGHTS_VERSION,
            "error": "property_not_found",
        }

    requirements = await db.requirements.find(
        {"property_id": property_id},
        {"_id": 0}
    ).to_list(500)
    documents = await db.documents.find(
        {"property_id": property_id},
        {"_id": 0}
    ).to_list(500)
    verified_documents = [d for d in documents if d.get("status") == "VERIFIED"]
    is_hmo = property_doc.get("is_hmo", False)
    hmo_property_ids = [property_id] if is_hmo else []

    if not requirements:
        return {
            "score": 100,
            "grade": "A",
            "color": "green",
            "breakdown": {
                "status_score": 100.0,
                "expiry_score": 100.0,
                "document_score": 100.0,
                "overdue_penalty_score": 100.0,
                "risk_score": 95.0 if is_hmo else 100.0,
            },
            "stats": {
                "total_requirements": 0,
                "compliant": 0,
                "pending": 0,
                "expiring_soon": 0,
                "overdue": 0,
            },
            "weights_version": WEIGHTS_VERSION,
        }

    total_weight = 0
    weighted_points = 0
    status_counts = {"COMPLIANT": 0, "PENDING": 0, "EXPIRING_SOON": 0, "OVERDUE": 0, "EXPIRED": 0}
    critical_overdue = []

    for req in requirements:
        status = req.get("status", "PENDING")
        req_type = req.get("requirement_type", "UNKNOWN")
        weight = get_requirement_weight(req_type)
        if property_id in hmo_property_ids and req_type.upper() in ["HMO_LICENCE", "FIRE_RISK_ASSESSMENT", "FIRE_DOORS", "EMERGENCY_LIGHTING"]:
            weight *= 1.2
        total_weight += weight
        if status in status_counts:
            status_counts[status] += 1
        else:
            status_counts["PENDING"] += 1
        if status == "COMPLIANT":
            weighted_points += weight * 100
        elif status == "PENDING":
            weighted_points += weight * 70
        elif status == "EXPIRING_SOON":
            weighted_points += weight * 40
        else:
            weighted_points += 0
            if weight >= 1.3:
                critical_overdue.append({"type": req_type, "property_id": property_id, "weight": weight})

    status_score = (weighted_points / (total_weight * 100)) * 100 if total_weight > 0 else 100
    total_reqs = len(requirements)
    compliant_count = status_counts["COMPLIANT"]
    pending_count = status_counts["PENDING"]
    expiring_soon_count = status_counts["EXPIRING_SOON"]
    overdue_count = status_counts["OVERDUE"] + status_counts["EXPIRED"]

    min_days_until_critical = float("inf")
    min_days_until_any = float("inf")
    nearest_expiry_type = None
    for req in requirements:
        if req.get("status") in ["COMPLIANT", "PENDING", "EXPIRING_SOON"]:
            due = _parse_due_date(req.get("due_date"))
            if due:
                days_until = (due - now).days
                if days_until < min_days_until_any:
                    min_days_until_any = days_until
                    nearest_expiry_type = req.get("requirement_type")
                if get_requirement_weight(req.get("requirement_type", "UNKNOWN")) >= 1.3 and days_until < min_days_until_critical:
                    min_days_until_critical = days_until
    effective_min_days = min_days_until_critical if min_days_until_critical != float("inf") else min_days_until_any

    if effective_min_days == float("inf"):
        expiry_score = 100
    elif effective_min_days >= 90:
        expiry_score = 100
    elif effective_min_days >= 60:
        expiry_score = 90
    elif effective_min_days >= 30:
        expiry_score = 75
    elif effective_min_days >= 14:
        expiry_score = 50
    elif effective_min_days >= 7:
        expiry_score = 30
    elif effective_min_days >= 0:
        expiry_score = 15
    else:
        expiry_score = 0

    requirements_with_verified_docs = set()
    for doc in verified_documents:
        if doc.get("requirement_id"):
            requirements_with_verified_docs.add(doc["requirement_id"])
    requirements_with_any_docs = set()
    for doc in documents:
        if doc.get("requirement_id"):
            requirements_with_any_docs.add(doc["requirement_id"])
    verified_doc_rate = (len(requirements_with_verified_docs) / total_reqs * 100) if total_reqs > 0 else 0
    doc_score = min(verified_doc_rate, 100)

    overdue_penalty_base = 100 - (overdue_count / total_reqs * 100) if total_reqs > 0 else 100
    critical_penalty = len(critical_overdue) * 10
    overdue_penalty_score = max(0, overdue_penalty_base - critical_penalty)

    risk_score = 100
    if is_hmo:
        risk_score -= 5
    risk_score = max(0, risk_score)

    final_score = (
        (status_score * 0.35) +
        (expiry_score * 0.25) +
        (doc_score * 0.15) +
        (overdue_penalty_score * 0.15) +
        (risk_score * 0.10)
    )
    final_score = round(max(0, min(100, final_score)))

    if final_score >= 90:
        grade, color = "A", "green"
    elif final_score >= 80:
        grade, color = "B", "green"
    elif final_score >= 70:
        grade, color = "C", "amber"
    elif final_score >= 60:
        grade, color = "D", "amber"
    else:
        grade, color = "F", "red"

    breakdown = {
        "status_score": round(status_score, 1),
        "expiry_score": round(expiry_score, 1),
        "document_score": round(doc_score, 1),
        "overdue_penalty_score": round(overdue_penalty_score, 1),
        "risk_score": round(risk_score, 1),
    }
    stats = {
        "total_requirements": total_reqs,
        "compliant": compliant_count,
        "pending": pending_count,
        "expiring_soon": expiring_soon_count,
        "overdue": overdue_count,
    }
    return {
        "score": final_score,
        "grade": grade,
        "color": color,
        "breakdown": breakdown,
        "stats": stats,
        "weights_version": WEIGHTS_VERSION,
        "weights": {
            "status": "35%",
            "expiry": "25%",
            "documents": "15%",
            "overdue_penalty": "15%",
            "risk_factor": "10%",
        },
    }


async def recalculate_and_persist(
    property_id: str,
    reason: str,
    actor: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Load DB state, compute score, persist to Property, write history snapshot, and audit.
    Safe to call concurrently (last write wins); single atomic Property update.
    """
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id},
        {"_id": 0, "property_id": 1, "client_id": 1, "compliance_score": 1, "compliance_breakdown": 1}
    )
    if not prop:
        logger.warning(f"recalculate_and_persist: property not found {property_id}")
        return {}

    client_id = prop["client_id"]
    previous_score = prop.get("compliance_score")
    previous_breakdown = prop.get("compliance_breakdown") or {}

    result = await calculate_property_compliance(property_id)
    if result.get("error"):
        logger.warning(f"recalculate_and_persist: calculation error for {property_id}: {result.get('error')}")
        return result

    new_score = result["score"]
    new_breakdown = result.get("breakdown", {})
    now = datetime.now(timezone.utc)

    await db.properties.update_one(
        {"property_id": property_id},
        {"$set": {
            "compliance_score": new_score,
            "compliance_breakdown": new_breakdown,
            "compliance_last_calculated_at": now.isoformat(),
            "compliance_version": result.get("weights_version", WEIGHTS_VERSION),
        }}
    )

    breakdown_summary = {
        "status_score": new_breakdown.get("status_score"),
        "expiry_score": new_breakdown.get("expiry_score"),
        "document_score": new_breakdown.get("document_score"),
        "overdue_penalty_score": new_breakdown.get("overdue_penalty_score"),
        "risk_score": new_breakdown.get("risk_score"),
    }
    history_doc = {
        "property_id": property_id,
        "client_id": client_id,
        "score": new_score,
        "breakdown_summary": breakdown_summary,
        "created_at": now.isoformat(),
        "reason": reason,
        "actor": actor,
    }
    await db.property_compliance_score_history.insert_one(history_doc)

    from models import AuditAction
    from utils.audit import create_audit_log
    delta = (new_score - previous_score) if previous_score is not None else None
    await create_audit_log(
        action=AuditAction.COMPLIANCE_SCORE_UPDATED,
        actor_id=(actor or {}).get("id") or (actor or {}).get("portal_user_id"),
        client_id=client_id,
        resource_type="property",
        resource_id=property_id,
        before_state={"compliance_score": previous_score} if previous_score is not None else None,
        after_state={"compliance_score": new_score},
        metadata={
            "reason": reason,
            "previous_score": previous_score,
            "new_score": new_score,
            "delta": delta,
            "actor_role": (actor or {}).get("role"),
            **(context or {}),
        },
    )
    logger.info(f"Compliance score updated property_id={property_id} reason={reason} previous={previous_score} new={new_score}")
    return result
