"""
Property Timeline Service - Unified chronological event stream for a property.

Merges: score_ledger_events, score_change_log, work_orders (synthetic "created" events).
Used by GET /api/portfolio/properties/:propertyId/timeline.
"""
from database import database
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import logging
import re

from services.scoring_explanation_copy import score_change_narrative

logger = logging.getLogger(__name__)

# Ledger trigger_type -> timeline category
TRIGGER_TO_CATEGORY = {
    "DOCUMENT_UPLOADED": "EVIDENCE",
    "DOCUMENT_REMOVED": "EVIDENCE",
    "DOCUMENT_STATUS_CHANGED": "EVIDENCE",
    "CERT_DETAILS_CONFIRMED": "EVIDENCE",
    "REQUIREMENT_STATUS_CHANGED": "COMPLIANCE",
    "SCHEDULED_RECALC": "COMPLIANCE",
    "PROPERTY_ADDED": "SYSTEM",
    "PROPERTY_UPDATED": "SYSTEM",
}
DEFAULT_CATEGORY = "SCORE_RISK"

# Categories that can be filtered
VALID_CATEGORIES = {"EVIDENCE", "COMPLIANCE", "MAINTENANCE", "SCORE_RISK", "SYSTEM"}
VALID_ACTORS = {"user", "admin", "system"}


# score_change_log.reason and similar — short titles (property timeline + API)
_SCORE_CHANGE_REASON_LABELS = {
    "CLIENT_JURISDICTION_UPDATED": "Jurisdiction updated",
    "EXPIRY_RULE": "Certificate expiry checked",
    "EXPIRY_JOB": "Certificate expiry checked",
    "PROPERTY_UPDATED": "Property details updated",
    "SCORE_RECALCULATED": "Compliance score updated",
    "SCHEDULED_PROPERTY_BATCH": "System update completed",
    "DOCUMENT_UPLOADED": "Document uploaded",
    "DOCUMENT_DELETED": "Document removed",
    "DOCUMENT_REMOVED": "Document removed",
    "REQUIREMENT_CHANGED": "Requirement updated",
    "EXPIRY_ROLLOVER": "Certificate rollover",
    "LAZY_BACKFILL": "Compliance score refreshed",
    "PROVISIONING": "Account provisioning",
    "PROPERTY_ADDED": "Property added",
    "TRIGGER_PROVISIONING": "Account provisioning",
}

_ACTION_OUTCOME_TITLES = {
    "CERTIFICATE_UPLOADED": "Certificate uploaded",
    "CERTIFICATE_VERIFIED": "Certificate verified",
    "ISSUE_CREATED": "Issue logged",
    "ISSUE_RESOLVED": "Issue resolved",
    "WORK_ORDER_COMPLETED": "Job completed",
    "REQUIREMENT_COMPLETED": "Requirement completed",
    "RISK_SIGNAL_ACKNOWLEDGED": "Risk signal acknowledged",
    "RISK_SIGNAL_RESOLVED": "Risk signal resolved",
}

_ACTION_OUTCOME_NARRATIVES = {
    "CERTIFICATE_UPLOADED": "A certificate was added; the compliance score was refreshed.",
    "CERTIFICATE_VERIFIED": "Certificate evidence was verified and the score was updated.",
    "ISSUE_CREATED": "A maintenance or compliance issue was recorded.",
    "ISSUE_RESOLVED": "An issue was resolved and scoring was recalculated.",
    "WORK_ORDER_COMPLETED": "A work order was marked complete and the score was updated.",
    "REQUIREMENT_COMPLETED": "A compliance requirement was satisfied.",
    "RISK_SIGNAL_ACKNOWLEDGED": "A risk signal was acknowledged.",
    "RISK_SIGNAL_RESOLVED": "A risk signal was closed out.",
}

_FALLBACK_SCORE_REASON_TITLE = "System update"
_FALLBACK_SCORE_REASON_BODY = (
    "Your compliance position was updated based on the latest data we hold for this property."
)


def present_score_change_reason(reason: Optional[str]) -> Dict[str, str]:
    """
    Map score_change_log.reason (and similar) to user-facing title + optional description.
    Never returns raw internal codes for known patterns.
    """
    raw = (reason or "").strip()
    if not raw:
        return {"title": _FALLBACK_SCORE_REASON_TITLE, "description": ""}

    m = re.match(r"^ACTION_OUTCOME:\s*([A-Za-z0-9_]+)\s*$", raw, re.IGNORECASE)
    if m:
        suffix = m.group(1).upper()
        title = _ACTION_OUTCOME_TITLES.get(suffix)
        if title:
            return {
                "title": title,
                "description": _ACTION_OUTCOME_NARRATIVES.get(suffix, ""),
            }
        return {
            "title": _FALLBACK_SCORE_REASON_TITLE,
            "description": "Your compliance position was refreshed after a workflow outcome was recorded.",
        }

    up = raw.upper()
    slug = re.sub(r"\s+", "_", up)
    if slug in _SCORE_CHANGE_REASON_LABELS:
        return {
            "title": _SCORE_CHANGE_REASON_LABELS[slug],
            "description": _score_change_narrative(slug),
        }

    # Only treat as internal code if the stored value is already SCREAMING_SNAKE (not Title Case prose).
    if re.match(r"^[A-Z][A-Z0-9_]+$", raw):
        return {"title": _FALLBACK_SCORE_REASON_TITLE, "description": _FALLBACK_SCORE_REASON_BODY}

    return {"title": raw, "description": ""}


def _score_change_narrative(reason_key: str) -> str:
    """Full sentence for timeline body — never raw enum names."""
    k = (reason_key or "").strip().upper()
    narratives = {
        "CLIENT_JURISDICTION_UPDATED": "Your portfolio or property region changed, so scoring rules were re-applied for this property.",
        "EXPIRY_RULE": "Expiry rules were applied to obligation dates; the compliance score reflects the latest certificate timelines.",
        "EXPIRY_JOB": "A scheduled check refreshed certificate dates and the compliance score for this property.",
        "PROPERTY_UPDATED": "Property details changed; obligations and scoring were refreshed where needed.",
        "SCORE_RECALCULATED": "The compliance score was recalculated from your latest evidence and property data.",
        "SCHEDULED_PROPERTY_BATCH": "An automated compliance pass ran for this property and updated the score if anything changed.",
        "DOCUMENT_UPLOADED": "A document was added or updated and contributed to your compliance position.",
        "DOCUMENT_DELETED": "A document was removed; the score reflects what is still on file.",
        "DOCUMENT_REMOVED": "A document was removed; the score reflects what is still on file.",
        "REQUIREMENT_CHANGED": "A requirement row changed (status, dates, or evidence link).",
        "EXPIRY_ROLLOVER": "A certificate or obligation moved into a new expiry window; dates and score were updated.",
        "LAZY_BACKFILL": "Stored compliance data was refreshed to match your current portfolio records.",
        "PROVISIONING": "Initial compliance data was set up for your portfolio.",
        "PROPERTY_ADDED": "This property was added to your portfolio.",
    }
    return narratives.get(k, _FALLBACK_SCORE_REASON_BODY)


def _friendly_score_change_reason(reason: Optional[str]) -> str:
    """Map internal trigger/reason codes to short user-readable labels."""
    if not reason or not str(reason).strip():
        return "Compliance score updated"
    return present_score_change_reason(reason)["title"]


def _parse_iso(ts: Any) -> Optional[datetime]:
    if ts is None:
        return None
    if hasattr(ts, "timestamp"):
        return ts
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def _ledger_to_item(e: Dict[str, Any], index: int) -> Dict[str, Any]:
    created = e.get("created_at")
    ts = _parse_iso(created)
    ts_str = created if isinstance(created, str) else (ts.isoformat() if ts else None)
    trigger_type = e.get("trigger_type") or "SCHEDULED_RECALC"
    trigger_label = e.get("trigger_label") or "Score recalculated"
    category = TRIGGER_TO_CATEGORY.get(trigger_type, DEFAULT_CATEGORY)
    actor_type = (e.get("actor_type") or "system").lower()
    delta = e.get("delta")
    desc = _ledger_description(e)
    # Avoid title == description (reads like a log echo)
    if desc and trigger_label and desc.strip().lower() == str(trigger_label).strip().lower():
        desc = _ledger_narrative_from_trigger(trigger_type, delta)
    return {
        "id": f"ledger:{ts_str}:{index}" if ts_str else f"ledger:{index}",
        "timestamp": ts_str,
        "category": category,
        "eventType": trigger_type,
        "title": trigger_label,
        "description": desc,
        "actorType": actor_type if actor_type in VALID_ACTORS else "system",
        "actorLabel": _actor_label(actor_type),
        "linkedEntityType": _ledger_linked_type(e),
        "linkedEntityId": e.get("document_id") or e.get("requirement_id"),
        "linkedEntityLabel": trigger_label,
        "impact": {"scoreDelta": delta, "riskChange": None} if delta is not None else None,
        "source": "ledger",
    }


def _ledger_narrative_from_trigger(trigger_type: Optional[str], delta: Any) -> str:
    """When ledger label is generic, use a property-history sentence."""
    t = (trigger_type or "").strip().upper()
    if t in ("SCHEDULED_RECALC",):
        return "Scheduled processing updated compliance scoring for this property."
    if t in ("REQUIREMENT_STATUS_CHANGED",):
        return "An obligation’s status or dates changed; your compliance picture was refreshed."
    if t in ("CERT_DETAILS_CONFIRMED", "DOCUMENT_UPLOADED", "DOCUMENT_STATUS_CHANGED", "DOCUMENT_REMOVED"):
        if delta is not None and delta != 0:
            return score_change_narrative(delta)
        return "Evidence or certificate details were updated on file."
    if t in ("PROPERTY_ADDED", "PROPERTY_UPDATED"):
        return "Property information was updated."
    if delta is not None and delta != 0:
        return score_change_narrative(delta)
    return "Activity was recorded for this property."


def _ledger_description(e: Dict[str, Any]) -> str:
    trigger_type = e.get("trigger_type")
    if trigger_type in ("CERT_DETAILS_CONFIRMED", "DOCUMENT_UPLOADED", "DOCUMENT_REMOVED", "DOCUMENT_STATUS_CHANGED"):
        delta = e.get("delta")
        if delta is not None and delta != 0:
            return score_change_narrative(delta)
        return e.get("trigger_label") or "Evidence or certificate updated."
    if trigger_type in ("REQUIREMENT_STATUS_CHANGED", "SCHEDULED_RECALC"):
        return e.get("trigger_label") or "Compliance status or expiry updated."
    if trigger_type in ("PROPERTY_ADDED", "PROPERTY_UPDATED"):
        return e.get("trigger_label") or "Property updated."
    delta = e.get("delta")
    if delta is not None and delta != 0:
        return score_change_narrative(delta)
    return e.get("trigger_label") or "Compliance records were refreshed."


def _actor_label(actor_type: str) -> str:
    if actor_type == "user":
        return "You"
    if actor_type == "admin":
        return "Admin"
    return "System"


def _ledger_linked_type(e: Dict[str, Any]) -> Optional[str]:
    if e.get("document_id"):
        return "DOCUMENT"
    if e.get("requirement_id"):
        return "REQUIREMENT"
    return None


def _score_change_to_item(e: Dict[str, Any], index: int) -> Dict[str, Any]:
    created = e.get("created_at")
    ts = _parse_iso(created)
    ts_str = created if isinstance(created, str) else (ts.isoformat() if ts else None)
    reason_raw = e.get("reason") or ""
    delta = e.get("delta")
    presented = present_score_change_reason(reason_raw)
    title = presented["title"]
    r_up = (reason_raw or "").strip().upper()
    m_ao = re.match(r"^ACTION_OUTCOME:\s*([A-Za-z0-9_]+)\s*$", reason_raw or "", re.IGNORECASE)
    if m_ao:
        event_type = f"ACTION_OUTCOME:{m_ao.group(1).upper()}"
    elif re.match(r"^[A-Z][A-Z0-9_]+$", r_up):
        event_type = r_up or "SCORE_RECALCULATED"
    else:
        event_type = re.sub(r"\s+", "_", r_up) or "SCORE_RECALCULATED"
    body = presented.get("description") or ""
    if delta is not None and delta != 0 and not body:
        body = score_change_narrative(delta)
    if not body:
        narr_key = (
            event_type.split(":", 1)[1]
            if event_type.startswith("ACTION_OUTCOME:")
            else event_type
        )
        body = presented.get("description") or _score_change_narrative(narr_key)
    return {
        "id": f"score_log:{ts_str}:{index}" if ts_str else f"score_log:{index}",
        "timestamp": ts_str,
        "category": "SCORE_RISK",
        "eventType": event_type,
        "title": title,
        "description": body,
        "actorType": "system",
        "actorLabel": "System",
        "linkedEntityType": None,
        "linkedEntityId": None,
        "linkedEntityLabel": None,
        "impact": {"scoreDelta": delta, "riskChange": None} if delta is not None else None,
        "source": "score_change_log",
    }


def _work_order_to_item(wo: Dict[str, Any]) -> Dict[str, Any]:
    created = wo.get("created_at")
    ts_str = created if isinstance(created, str) else None
    raw_desc = (wo.get("description") or "").strip()[:200]
    wo_id = wo.get("work_order_id")
    kind = (wo.get("work_order_kind") or "MAINTENANCE").strip().upper()
    if kind == "COMPLIANCE":
        title = "Compliance job started"
        lead = "A compliance inspection or certification job was created for this property."
    else:
        title = "Maintenance job started"
        lead = "A repair or maintenance work order was opened."
    body = f"{lead} {raw_desc}".strip() if raw_desc else lead
    return {
        "id": f"wo:{wo_id}" if wo_id else f"wo:{ts_str}",
        "timestamp": ts_str,
        "category": "MAINTENANCE",
        "eventType": "WORK_ORDER_CREATED",
        "title": title,
        "description": body,
        "actorType": "user",
        "actorLabel": "You",
        "linkedEntityType": "WORK_ORDER",
        "linkedEntityId": wo_id,
        "linkedEntityLabel": f"Work Order #{str(wo_id)[:8]}" if wo_id else "Work order",
        "impact": None,
        "source": "work_orders",
    }


def _work_order_completed_to_item(wo: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Timeline item for work order completion (when completed_at is set)."""
    completed_at = wo.get("completed_at")
    if not completed_at:
        return None
    ts_str = completed_at if isinstance(completed_at, str) else None
    wo_id = wo.get("work_order_id")
    raw_desc = (wo.get("description") or "").strip()[:200]
    kind = (wo.get("work_order_kind") or "MAINTENANCE").strip().upper()
    if kind == "COMPLIANCE":
        title = "Compliance job completed"
        lead = "The compliance job for this property is marked complete."
    else:
        title = "Maintenance job completed"
        lead = "The maintenance work order for this property is marked complete."
    body = f"{lead} {raw_desc}".strip() if raw_desc else lead
    return {
        "id": f"wo_done:{wo_id}" if wo_id else f"wo_done:{ts_str}",
        "timestamp": ts_str,
        "category": "MAINTENANCE",
        "eventType": "WORK_ORDER_COMPLETED",
        "title": title,
        "description": body,
        "actorType": "user",
        "actorLabel": "You",
        "linkedEntityType": "WORK_ORDER",
        "linkedEntityId": wo_id,
        "linkedEntityLabel": f"Work Order #{str(wo_id)[:8]}" if wo_id else "Work order",
        "impact": None,
        "source": "work_orders",
    }


def _work_order_assigned_to_item(wo: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Timeline item for contractor assigned (when contractor_id and assigned_at are set)."""
    assigned_at = wo.get("assigned_at")
    if not assigned_at or not wo.get("contractor_id"):
        return None
    ts_str = assigned_at if isinstance(assigned_at, str) else None
    wo_id = wo.get("work_order_id")
    return {
        "id": f"wo_assigned:{wo_id}" if wo_id else f"wo_assigned:{ts_str}",
        "timestamp": ts_str,
        "category": "MAINTENANCE",
        "eventType": "WORK_ORDER_ASSIGNED",
        "title": "Contractor assigned",
        "description": "A contractor was assigned to this work order.",
        "actorType": "user",
        "actorLabel": "You",
        "linkedEntityType": "WORK_ORDER",
        "linkedEntityId": wo_id,
        "linkedEntityLabel": f"Work Order #{str(wo_id)[:8]}" if wo_id else "Work order",
        "impact": None,
        "source": "work_orders",
    }


def _asset_event_to_item(ev: Dict[str, Any]) -> Dict[str, Any]:
    """Timeline item from asset_events (issue_created, repair_completed, document_linked, etc.)."""
    ts = ev.get("timestamp")
    ts_str = ts if isinstance(ts, str) else None
    event_type = (ev.get("event_type") or "").replace("_", " ").title()
    desc = (ev.get("description") or event_type or "Asset activity").strip()[:200]
    ev_id = ev.get("event_id")
    return {
        "id": f"asset_ev:{ev_id}" if ev_id else f"asset_ev:{ts_str}",
        "timestamp": ts_str,
        "category": "MAINTENANCE",
        "eventType": (ev.get("event_type") or "ASSET_EVENT").upper(),
        "title": event_type or "Asset activity",
        "description": desc or "Asset event.",
        "actorType": "system",
        "actorLabel": "System",
        "linkedEntityType": "ASSET",
        "linkedEntityId": ev.get("asset_id"),
        "linkedEntityLabel": desc or event_type,
        "impact": None,
        "source": "asset_events",
    }


async def get_property_timeline(
    client_id: str,
    property_id: str,
    *,
    category: Optional[str] = None,
    actor_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 50,
    cursor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return a unified timeline for the property: ledger + score_change_log + work_orders.
    Sorted by timestamp descending. Filters applied after merge.
    """
    from services.score_ledger_service import list_ledger_export

    def _normalize_date_range(from_d: Optional[str], to_d: Optional[str]):
        start, end = None, None
        if from_d and from_d.strip() and len(from_d.strip()) >= 10 and from_d.strip()[4] == "-":
            start = from_d.strip()[:10] + "T00:00:00.000Z"
        if to_d and to_d.strip() and len(to_d.strip()) >= 10 and to_d.strip()[4] == "-":
            end = to_d.strip()[:10] + "T23:59:59.999Z"
        return start, end

    db = database.get_db()

    # 1) Ledger entries for this property (no pagination on export; we cap limit)
    ledger_items = await list_ledger_export(
        client_id=client_id,
        property_id=property_id,
        from_date=from_date,
        to_date=to_date,
        limit=500,
    )
    # 2) Score change log (simpler entries; may overlap with ledger - we include both and sort)
    start, end = _normalize_date_range(from_date, to_date)
    score_query = {"property_id": property_id, "client_id": client_id}
    if start or end:
        score_query["created_at"] = {}
        if start:
            score_query["created_at"]["$gte"] = start
        if end:
            score_query["created_at"]["$lte"] = end
    score_log = await db.score_change_log.find(
        score_query,
        {"_id": 0, "created_at": 1, "previous_score": 1, "new_score": 1, "delta": 1, "reason": 1},
    ).sort("created_at", -1).limit(100).to_list(100)

    # 3) Work orders for this property (synthetic "created" + "completed" + "assigned" events)
    wo_list = await db.work_orders.find(
        {"property_id": property_id, "client_id": client_id},
        {
            "_id": 0,
            "work_order_id": 1,
            "description": 1,
            "created_at": 1,
            "completed_at": 1,
            "contractor_id": 1,
            "assigned_at": 1,
            "work_order_kind": 1,
        },
    ).sort("created_at", -1).limit(100).to_list(100)

    # Build normalized items
    items: List[Dict[str, Any]] = []
    for i, e in enumerate(ledger_items):
        item = _ledger_to_item(e, i)
        if category and item["category"] != category:
            continue
        if actor_type and item["actorType"] != actor_type.lower():
            continue
        items.append(item)

    for i, e in enumerate(score_log):
        item = _score_change_to_item(e, i)
        if category and item["category"] != category:
            continue
        if actor_type and item["actorType"] != actor_type.lower():
            continue
        items.append(item)

    for wo in wo_list:
        item = _work_order_to_item(wo)
        if category and item["category"] != category:
            pass
        elif actor_type and item["actorType"] != actor_type.lower():
            pass
        else:
            items.append(item)
        completed_item = _work_order_completed_to_item(wo)
        if completed_item:
            if category and completed_item["category"] != category:
                pass
            elif actor_type and completed_item["actorType"] != actor_type.lower():
                pass
            else:
                items.append(completed_item)
        assigned_item = _work_order_assigned_to_item(wo)
        if assigned_item:
            if category and assigned_item["category"] != category:
                pass
            elif actor_type and assigned_item["actorType"] != actor_type.lower():
                pass
            else:
                items.append(assigned_item)

    # 4) Asset events for this property (issue_created, repair_completed, document_linked, etc.)
    try:
        from services.property_assets_service import list_asset_events_for_property
        asset_ev_list = await list_asset_events_for_property(
            property_id=property_id,
            client_id=client_id,
            limit=100,
            from_date=start,
            to_date=end,
        )
        for ev in asset_ev_list:
            item = _asset_event_to_item(ev)
            if category and item["category"] != category:
                continue
            if actor_type and item["actorType"] != actor_type.lower():
                continue
            items.append(item)
    except Exception as e:
        logger.debug("Timeline asset_events skip: %s", e)

    # Sort by timestamp descending
    def sort_key(x):
        t = x.get("timestamp") or ""
        return t

    items.sort(key=sort_key, reverse=True)

    # Cursor pagination: cursor is the last timestamp seen
    if cursor:
        items = [x for x in items if (x.get("timestamp") or "") < cursor]
    items = items[: limit + 1]
    has_more = len(items) > limit
    if has_more:
        items = items[:limit]
    next_cursor = items[-1]["timestamp"] if items and has_more else None

    return {
        "items": items,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": len(items) if not cursor else None,
    }
