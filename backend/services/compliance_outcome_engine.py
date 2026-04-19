"""
Compliance Action -> Outcome Engine.

Converts concrete user/system actions into deterministic, auditable outcomes:
- score recalculation delta
- risk signal reduction/resolution signals
- property compliance status movement
- user-facing outcome message
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import database
from services.compliance_scoring_service import recalculate_and_persist


EVENT_CERTIFICATE_UPLOADED = "certificate_uploaded"
EVENT_CERTIFICATE_VERIFIED = "certificate_verified"
EVENT_ISSUE_CREATED = "issue_created"
EVENT_ISSUE_RESOLVED = "issue_resolved"
EVENT_WORK_ORDER_COMPLETED = "work_order_completed"
EVENT_REQUIREMENT_COMPLETED = "requirement_completed"
EVENT_RISK_SIGNAL_ACKNOWLEDGED = "risk_signal_acknowledged"
EVENT_RISK_SIGNAL_RESOLVED = "risk_signal_resolved"

ALL_EVENTS = {
    EVENT_CERTIFICATE_UPLOADED,
    EVENT_CERTIFICATE_VERIFIED,
    EVENT_ISSUE_CREATED,
    EVENT_ISSUE_RESOLVED,
    EVENT_WORK_ORDER_COMPLETED,
    EVENT_REQUIREMENT_COMPLETED,
    EVENT_RISK_SIGNAL_ACKNOWLEDGED,
    EVENT_RISK_SIGNAL_RESOLVED,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_from_score(score: int) -> str:
    if score >= 80:
        return "GREEN"
    if score >= 60:
        return "AMBER"
    return "RED"


def _event_label(event_type: str, requirement_type: Optional[str]) -> str:
    req = (requirement_type or "").strip().upper()
    if event_type == EVENT_CERTIFICATE_UPLOADED:
        return f"{req} certificate uploaded" if req else "Certificate uploaded"
    if event_type == EVENT_CERTIFICATE_VERIFIED:
        return f"{req} certificate verified" if req else "Certificate verified"
    if event_type == EVENT_ISSUE_CREATED:
        return "Issue created"
    if event_type == EVENT_ISSUE_RESOLVED:
        return "Issue resolved"
    if event_type == EVENT_WORK_ORDER_COMPLETED:
        return "Work order completed"
    if event_type == EVENT_REQUIREMENT_COMPLETED:
        return f"{req} requirement completed" if req else "Requirement completed"
    if event_type == EVENT_RISK_SIGNAL_ACKNOWLEDGED:
        return "Risk signal acknowledged"
    if event_type == EVENT_RISK_SIGNAL_RESOLVED:
        return "Risk signal resolved"
    return event_type.replace("_", " ").title()


def _build_dedupe_key(event: Dict[str, Any]) -> str:
    if (event.get("dedupe_key") or "").strip():
        return event["dedupe_key"].strip()
    return ":".join(
        [
            str(event.get("event_type") or ""),
            str(event.get("client_id") or ""),
            str(event.get("property_id") or ""),
            str(event.get("asset_id") or ""),
            str(event.get("requirement_type") or ""),
            str(event.get("source_id") or ""),
        ]
    )


async def _count_active_risk_signals(client_id: str, property_id: str) -> int:
    db = database.get_db()
    return await db.risk_signals.count_documents(
        {
            "client_id": client_id,
            "property_id": property_id,
            "status": {"$nin": ["resolved"]},
        }
    )


async def _mark_related_risk_resolved(event: Dict[str, Any]) -> None:
    db = database.get_db()
    client_id = event["client_id"]
    property_id = event["property_id"]
    requirement_type = (event.get("requirement_type") or "").strip().lower()
    query: Dict[str, Any] = {
        "client_id": client_id,
        "property_id": property_id,
        "status": {"$nin": ["resolved"]},
    }
    if event.get("asset_id"):
        query["asset_id"] = event.get("asset_id")
    if requirement_type:
        query["$or"] = [
            {"risk_type": {"$regex": requirement_type, "$options": "i"}},
            {"recommended_action": {"$regex": requirement_type, "$options": "i"}},
        ]
    await db.risk_signals.update_many(
        query,
        {"$set": {"status": "resolved", "updated_at": _now_iso()}},
    )


async def _mark_related_risk_acknowledged(event: Dict[str, Any]) -> None:
    db = database.get_db()
    query: Dict[str, Any] = {
        "client_id": event["client_id"],
        "property_id": event["property_id"],
        "status": "active",
    }
    if event.get("asset_id"):
        query["asset_id"] = event.get("asset_id")
    await db.risk_signals.update_many(
        query,
        {"$set": {"status": "acknowledged", "updated_at": _now_iso()}},
    )


async def _sync_regenerate_risks_and_operational(client_id: str, property_id: str) -> None:
    """After compliance recalc from an outcome event: refresh heuristic signals + automation (same worker, no extra queue)."""
    from services.ops_compliance_feature_flags import get_effective_flags, PREDICTIVE_MAINTENANCE

    db = database.get_db()
    client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "billing_plan": 1})
    billing = (client_doc or {}).get("billing_plan")
    flags = await get_effective_flags(client_id, billing)
    if not flags.get(PREDICTIVE_MAINTENANCE):
        return
    from services import risk_signal_service
    from services.operational_automation_service import evaluate_operational_automation_after_risk_refresh

    await risk_signal_service.generate_risk_signals_for_property(property_id, client_id)
    await evaluate_operational_automation_after_risk_refresh(property_id, client_id)


async def _set_requirement_compliant(event: Dict[str, Any]) -> None:
    req_type = (event.get("requirement_type") or "").strip()
    if not req_type:
        return
    db = database.get_db()
    await db.requirements.update_many(
        {
            "client_id": event["client_id"],
            "property_id": event["property_id"],
            "$or": [{"requirement_type": req_type}, {"requirement_code": req_type}],
        },
        {"$set": {"status": "COMPLIANT", "updated_at": _now_iso()}},
    )


async def apply_action_outcome(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply a compliance action outcome and return a UX payload.
    Idempotent by compliance_activity_log.dedupe_key.
    """
    event_type = (event.get("event_type") or "").strip().lower()
    if event_type not in ALL_EVENTS:
        raise ValueError(f"Unsupported event_type: {event_type}")
    if not (event.get("client_id") and event.get("property_id")):
        raise ValueError("client_id and property_id are required")

    db = database.get_db()
    dedupe_key = _build_dedupe_key({**event, "event_type": event_type})
    existing = await db.compliance_activity_log.find_one(
        {"dedupe_key": dedupe_key},
        {"_id": 0},
    )
    if existing:
        return {
            "score_change": existing.get("score_change", 0),
            "new_score": existing.get("new_score"),
            "risk_change": existing.get("risk_change", "unchanged"),
            "status_change": existing.get("status_change", "unchanged"),
            "message": existing.get("message", "No new change"),
            "idempotent": True,
        }

    property_before = await db.properties.find_one(
        {"property_id": event["property_id"], "client_id": event["client_id"]},
        {"_id": 0, "compliance_score": 1, "compliance_status": 1},
    ) or {}
    score_before = int(property_before.get("compliance_score") or 0)
    status_before = (property_before.get("compliance_status") or _status_from_score(score_before)).upper()
    risk_before = await _count_active_risk_signals(event["client_id"], event["property_id"])

    # Apply deterministic state effects before recalculation.
    if event_type in (EVENT_CERTIFICATE_VERIFIED, EVENT_REQUIREMENT_COMPLETED):
        await _set_requirement_compliant(event)
        await _mark_related_risk_resolved(event)
    elif event_type == EVENT_WORK_ORDER_COMPLETED:
        meta = event.get("metadata") or {}
        if meta.get("resolve_linked_compliance_risks"):
            await _mark_related_risk_resolved(event)
    elif event_type == EVENT_ISSUE_RESOLVED:
        await _mark_related_risk_acknowledged(event)
    elif event_type == EVENT_RISK_SIGNAL_ACKNOWLEDGED:
        await _mark_related_risk_acknowledged(event)
    elif event_type == EVENT_RISK_SIGNAL_RESOLVED:
        await _mark_related_risk_resolved(event)

    rctx: Dict[str, Any] = {
        "outcome_event_type": event_type,
        "source_id": event.get("source_id"),
        "skip_risk_regen_enqueue": True,
    }
    if event.get("metadata"):
        rctx["outcome_metadata"] = event.get("metadata")
    await recalculate_and_persist(
        property_id=event["property_id"],
        reason=f"ACTION_OUTCOME:{event_type.upper()}",
        actor={"id": event.get("actor_id"), "role": event.get("actor_role") or "SYSTEM"},
        context=rctx,
    )
    await _sync_regenerate_risks_and_operational(event["client_id"], event["property_id"])
    property_after = await db.properties.find_one(
        {"property_id": event["property_id"], "client_id": event["client_id"]},
        {"_id": 0, "compliance_score": 1, "compliance_status": 1},
    ) or {}
    new_score = int(property_after.get("compliance_score") or score_before)
    score_change = int(new_score - score_before)
    status_after = _status_from_score(new_score)
    await db.properties.update_one(
        {"property_id": event["property_id"], "client_id": event["client_id"]},
        {"$set": {"compliance_status": status_after, "updated_at": _now_iso()}},
    )
    risk_after = await _count_active_risk_signals(event["client_id"], event["property_id"])

    risk_change = "reduced" if risk_after < risk_before else ("increased" if risk_after > risk_before else "unchanged")
    status_change = "improved" if status_after != status_before and status_after in ("AMBER", "GREEN") else "unchanged"
    label = _event_label(event_type, event.get("requirement_type"))
    score_part = f"Compliance score {'+' if score_change >= 0 else ''}{score_change}"
    meta = event.get("metadata") or {}
    if event_type == EVENT_CERTIFICATE_UPLOADED and meta.get("evidence_pending_user_confirmation"):
        req_t = (event.get("requirement_type") or "").strip()
        req_part = f"{req_t} evidence uploaded — file saved. " if req_t else "Evidence uploaded — file saved. "
        message = (
            f"{req_part}"
            "Confirm extracted dates in Documents before this fully satisfies the requirement. "
            f"({score_part}; risk {risk_change})"
        )
    else:
        message = f"{label} -> {score_part} -> Risk {risk_change}"

    created_at = event.get("timestamp") or _now_iso()
    activity_doc = {
        "client_id": event["client_id"],
        "property_id": event["property_id"],
        "asset_id": event.get("asset_id"),
        "requirement_type": event.get("requirement_type"),
        "action_type": event_type,
        "score_change": score_change,
        "previous_score": score_before,
        "new_score": new_score,
        "risk_change": risk_change,
        "status_change": status_change,
        "message": message,
        "changed_requirement": (event.get("requirement_type") or "").strip().upper() or None,
        "reason": f"ACTION_OUTCOME:{event_type.upper()}",
        "created_at": created_at,
        "dedupe_key": dedupe_key,
        "source_id": event.get("source_id"),
        "metadata": event.get("metadata") or {},
    }
    await db.compliance_activity_log.insert_one(activity_doc)

    return {
        "score_change": score_change,
        "new_score": new_score,
        "risk_change": risk_change,
        "status_change": status_change,
        "message": message,
        "idempotent": False,
    }


async def list_activity(client_id: str, property_id: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    db = database.get_db()
    q: Dict[str, Any] = {"client_id": client_id}
    if property_id:
        q["property_id"] = property_id
    items = await db.compliance_activity_log.find(q, {"_id": 0}).sort("created_at", -1).limit(max(1, min(limit, 200))).to_list(max(1, min(limit, 200)))
    return {"items": items}
