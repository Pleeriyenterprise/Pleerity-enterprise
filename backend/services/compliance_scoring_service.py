"""
Enterprise compliance scoring: single source of truth for property-level score.
Deterministic, event-driven recalculation, persisted on Property + history + audit.
Uses Compliance Score v1 (evidence-based, no legal verdicts) from compliance_scoring module.

All score changes must go through recalculate_and_persist(); no route implements
its own scoring. Dashboard and GET /compliance-score read stored property scores.
"""
from database import database
from datetime import datetime, timezone, date, timedelta
from typing import Dict, Any, Optional, List
import logging

from services.compliance_scoring import compute_property_score as compute_property_score_v1
from utils.risk_bands import score_to_grade_color_message

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
    Compute compliance score for a single property from current DB state (Compliance Score v1).
    Deterministic: same DB state + same as_of_date -> same result.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    if as_of_date is not None:
        now = datetime.combine(as_of_date, now.time(), tzinfo=timezone.utc)

    property_doc = await db.properties.find_one(
        {"property_id": property_id},
        {"_id": 0, "property_id": 1, "client_id": 1, "is_hmo": 1, "bedrooms": 1, "occupancy": 1,
         "licence_required": 1, "has_gas_supply": 1, "has_gas": 1}
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

    result = compute_property_score_v1(property_doc, requirements, documents, as_of=now)
    score = result.get("score_0_100", 0)
    risk_level = result.get("risk_level", "Low risk")
    breakdown_v1 = result.get("breakdown", [])

    grade, color, _ = score_to_grade_color_message(score)
    status_score = score
    breakdown_legacy = {
        "status_score": float(score),
        "expiry_score": float(score),
        "document_score": float(score),
        "overdue_penalty_score": float(score),
        "risk_score": 100.0,
    }
    stats = {
        "total_requirements": len(requirements),
        "compliant": sum(1 for r in requirements if (r.get("status") or "").upper() == "COMPLIANT"),
        "pending": sum(1 for r in requirements if (r.get("status") or "").upper() == "PENDING"),
        "expiring_soon": sum(1 for r in requirements if (r.get("status") or "").upper() == "EXPIRING_SOON"),
        "overdue": sum(1 for r in requirements if (r.get("status") or "").upper() in ("OVERDUE", "EXPIRED")),
    }
    return {
        "score": score,
        "grade": grade,
        "color": color,
        "risk_level": risk_level,
        "score_breakdown": breakdown_v1,
        "breakdown": breakdown_legacy,
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
    risk_level = result.get("risk_level")
    score_breakdown = result.get("score_breakdown", [])
    now = datetime.now(timezone.utc)

    set_fields = {
        "compliance_score": new_score,
        "compliance_breakdown": new_breakdown,
        "compliance_last_calculated_at": now.isoformat(),
        "compliance_version": result.get("weights_version", WEIGHTS_VERSION),
        "compliance_score_pending": False,
    }
    if risk_level is not None:
        set_fields["risk_level"] = risk_level
    if score_breakdown is not None:
        set_fields["score_breakdown"] = score_breakdown

    await db.properties.update_one(
        {"property_id": property_id},
        {"$set": set_fields}
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
