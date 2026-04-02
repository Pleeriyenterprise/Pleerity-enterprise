"""
Unified client calendar / timeline events: requirements (obligation dates) + work order visits
(read-only lens over requirements + work_orders; no separate calendar truth).
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from database import database
from presentation.label_service import requirement_label
from services.maintenance_service import (
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    WORK_ORDER_KIND_COMPLIANCE,
    WORK_ORDER_KIND_MAINTENANCE,
)
from services.work_order_schedule_constants import (
    SCHEDULE_STATUS_CANCELLED,
    SCHEDULE_STATUS_COMPLETED,
    SCHEDULE_STATUS_CONFIRMED,
    SCHEDULE_STATUS_PROPOSED,
    SCHEDULE_STATUS_RESCHEDULE_REQUESTED,
)
from utils.expiry_utils import get_effective_expiry_date, get_computed_status, is_included_for_calendar

logger = logging.getLogger(__name__)


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    try:
        s = str(value).replace("Z", "+00:00").strip()
        if not s:
            return None
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _property_display(prop: Dict[str, Any]) -> str:
    nick = (prop.get("nickname") or "").strip()
    if nick:
        return nick
    a1 = (prop.get("address_line_1") or "").strip()
    if a1:
        return a1
    pc = (prop.get("postcode") or "").strip()
    cy = (prop.get("city") or "").strip()
    if cy and pc:
        return f"{cy}, {pc}"
    return pc or cy or str(prop.get("property_id") or "Property")


def _requirement_date_source(req: Dict[str, Any]) -> str:
    if req.get("confirmed_expiry_date"):
        return "confirmed"
    if req.get("extracted_expiry_date"):
        return "extracted"
    if req.get("due_date"):
        return "due_legacy"
    return "unknown"


def _requirement_event_type(computed_status: str) -> str:
    s = (computed_status or "").upper()
    if s == "OVERDUE" or s == "EXPIRED":
        return "requirement_overdue"
    if s == "EXPIRING_SOON":
        return "requirement_expiring_soon"
    if s == "COMPLIANT":
        return "requirement_valid"
    if s == "PENDING" or s == "MISSING":
        return "requirement_due"
    return "requirement_due"


def _visit_event_type(schedule_status: str, work_order_kind: str) -> str:
    st = (schedule_status or "").strip().lower()
    prefix = "compliance_visit" if (work_order_kind or "").strip().upper() == WORK_ORDER_KIND_COMPLIANCE else "work_order_visit"
    if st == SCHEDULE_STATUS_PROPOSED:
        return f"{prefix}_proposed"
    if st == SCHEDULE_STATUS_CONFIRMED:
        return f"{prefix}_confirmed"
    if st == SCHEDULE_STATUS_RESCHEDULE_REQUESTED:
        return f"{prefix}_reschedule_requested"
    if st == SCHEDULE_STATUS_CANCELLED:
        return f"{prefix}_cancelled"
    if st == SCHEDULE_STATUS_COMPLETED:
        return f"{prefix}_completed"
    return f"{prefix}_proposed"


def _visit_title(schedule_status: str, work_order_kind: str) -> str:
    st = (schedule_status or "").strip().lower()
    is_comp = (work_order_kind or "").strip().upper() == WORK_ORDER_KIND_COMPLIANCE
    if st == SCHEDULE_STATUS_PROPOSED:
        return "Proposed compliance inspection" if is_comp else "Proposed repair visit"
    if st == SCHEDULE_STATUS_CONFIRMED:
        return "Confirmed compliance inspection" if is_comp else "Confirmed repair visit"
    if st == SCHEDULE_STATUS_RESCHEDULE_REQUESTED:
        return "Reschedule requested (compliance inspection)" if is_comp else "Reschedule requested (repair visit)"
    if st == SCHEDULE_STATUS_CANCELLED:
        return "Compliance inspection cancelled" if is_comp else "Repair visit cancelled"
    if st == SCHEDULE_STATUS_COMPLETED:
        return "Compliance inspection visit completed" if is_comp else "Repair visit completed"
    return "Proposed compliance inspection" if is_comp else "Proposed repair visit"


def _severity_from_requirement_status(computed_status: str) -> str:
    s = (computed_status or "").upper()
    if s in ("OVERDUE", "EXPIRED"):
        return "critical"
    if s == "EXPIRING_SOON":
        return "high"
    if s == "COMPLIANT":
        return "low"
    return "medium"


def _requirement_title(req: Dict[str, Any], computed_status: str) -> str:
    code = req.get("requirement_type") or req.get("code") or ""
    label = requirement_label(code) if code else "Compliance item"
    s = (computed_status or "").upper()
    eff = get_effective_expiry_date(req)
    date_str = eff.strftime("%d %b %Y") if eff else ""

    if s in ("OVERDUE", "EXPIRED"):
        return f"Requirement overdue: {label}"
    if s == "EXPIRING_SOON":
        return f"Requirement expiring soon: {label}"
    if s == "COMPLIANT" and date_str:
        return f"Requirement valid until {date_str}: {label}"
    if date_str:
        return f"Requirement due ({date_str}): {label}"
    return f"Requirement due: {label}"


def _stable_event_id(parts: List[str]) -> str:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"evt_{h}"


async def load_client_calendar_context(client_id: str) -> Tuple[Dict[str, Any], List[str]]:
    db = database.get_db()
    properties = await db.properties.find(
        {"client_id": client_id},
        {"_id": 0, "property_id": 1, "address_line_1": 1, "city": 1, "postcode": 1, "nickname": 1},
    ).to_list(500)
    property_map = {p["property_id"]: p for p in properties}
    return property_map, list(property_map.keys())


def build_requirement_timeline_events(
    requirements: List[Dict[str, Any]],
    property_map: Dict[str, Any],
    start: datetime,
    end: datetime,
    req_to_doc: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    req_to_doc = req_to_doc or {}
    out: List[Dict[str, Any]] = []
    for req in requirements:
        if not is_included_for_calendar(req):
            continue
        effective = get_effective_expiry_date(req)
        if effective is None:
            continue
        if not (start <= effective < end):
            continue
        computed = get_computed_status(req)
        prop = property_map.get(req.get("property_id"), {})
        pid = req.get("property_id")
        rid = req.get("requirement_id")
        date_key = effective.strftime("%Y-%m-%d")
        event_type = _requirement_event_type(computed)
        title = _requirement_title(req, computed)
        route = f"/documents?property_id={pid}&requirement_id={rid}" if pid and rid else "/documents"

        out.append(
            {
                "event_id": _stable_event_id(["req", str(rid), date_key]),
                "event_type": event_type,
                "event_category": "requirement",
                "source_entity_type": "requirement",
                "source_entity_id": str(rid),
                "property_id": str(pid) if pid else "",
                "property_name": _property_display(prop) if prop else "",
                "title": title,
                "date": date_key,
                "datetime_utc": effective.replace(tzinfo=timezone.utc).isoformat(),
                "timezone": None,
                "status": computed,
                "severity": _severity_from_requirement_status(computed),
                "urgency": "high" if computed in ("OVERDUE", "EXPIRED", "EXPIRING_SOON") else "low",
                "date_source": _requirement_date_source(req),
                "requirement_type": req.get("requirement_type") or req.get("code") or "",
                "document_id": req_to_doc.get(rid),
                "primary_route": route,
                "metadata": {"requirement_id": rid, "property_id": pid},
            }
        )
    return out


def build_work_order_timeline_events(
    work_orders: List[Dict[str, Any]],
    property_map: Dict[str, Any],
    start: datetime,
    end: datetime,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for wo in work_orders:
        wid = wo.get("work_order_id")
        pid = wo.get("property_id")
        if not wid or not pid:
            continue
        prop = property_map.get(pid, {})
        kind = (wo.get("work_order_kind") or WORK_ORDER_KIND_MAINTENANCE).strip().upper()
        wo_status = (wo.get("status") or "").strip().upper()
        schedule_status = (wo.get("schedule_status") or "").strip().lower()
        scheduled_raw = wo.get("scheduled_at")
        scheduled_at = _parse_dt(scheduled_raw)
        tz_name = (wo.get("scheduled_timezone") or "").strip() or None

        # Completed jobs: single milestone row (avoid duplicate "visit completed" + "job completed").
        if wo_status == STATUS_COMPLETED:
            completed_at = _parse_dt(wo.get("completed_at"))
            if completed_at is not None:
                day_start = datetime(completed_at.year, completed_at.month, completed_at.day, tzinfo=timezone.utc)
                if start <= day_start < end:
                    date_key = day_start.strftime("%Y-%m-%d")
                    if kind == WORK_ORDER_KIND_COMPLIANCE:
                        title = "Compliance job completed"
                        et = "compliance_job_completed"
                        cat = "compliance_job"
                    else:
                        title = "Repair job completed"
                        et = "maintenance_job_completed"
                        cat = "scheduled_job"
                    out.append(
                        {
                            "event_id": _stable_event_id(["wo_done", str(wid), date_key]),
                            "event_type": et,
                            "event_category": cat,
                            "source_entity_type": "work_order",
                            "source_entity_id": str(wid),
                            "property_id": str(pid),
                            "property_name": _property_display(prop) if prop else "",
                            "title": title,
                            "date": date_key,
                            "datetime_utc": completed_at.replace(tzinfo=timezone.utc).isoformat()
                            if completed_at.tzinfo is None
                            else completed_at.isoformat(),
                            "timezone": None,
                            "status": STATUS_COMPLETED,
                            "severity": "low",
                            "urgency": "low",
                            "work_order_kind": kind,
                            "work_order_status": STATUS_COMPLETED,
                            "primary_route": f"/operations/work-orders?work_order_id={wid}",
                            "metadata": {"work_order_id": wid, "property_id": pid},
                        }
                    )
            continue

        # Visit events: only when a real scheduled_at exists (truthful scheduling)
        if scheduled_at is not None and schedule_status in (
            SCHEDULE_STATUS_PROPOSED,
            SCHEDULE_STATUS_CONFIRMED,
            SCHEDULE_STATUS_RESCHEDULE_REQUESTED,
            SCHEDULE_STATUS_CANCELLED,
            SCHEDULE_STATUS_COMPLETED,
        ):
            # Anchor to visit local calendar day in UTC for grid (same as requirement all-day style)
            day_start = datetime(scheduled_at.year, scheduled_at.month, scheduled_at.day, tzinfo=timezone.utc)
            if not (start <= day_start < end):
                continue
            date_key = day_start.strftime("%Y-%m-%d")
            et = _visit_event_type(schedule_status, kind)
            cat = "compliance_job" if kind == WORK_ORDER_KIND_COMPLIANCE else "scheduled_job"
            title = _visit_title(schedule_status, kind)
            route = f"/operations/work-orders?work_order_id={wid}"
            sev = "high" if schedule_status == SCHEDULE_STATUS_RESCHEDULE_REQUESTED else (
                "medium" if schedule_status == SCHEDULE_STATUS_PROPOSED else "low"
            )
            if schedule_status == SCHEDULE_STATUS_CANCELLED:
                sev = "medium"
            out.append(
                {
                    "event_id": _stable_event_id(["wo_visit", str(wid), date_key, schedule_status]),
                    "event_type": et,
                    "event_category": cat,
                    "source_entity_type": "work_order",
                    "source_entity_id": str(wid),
                    "property_id": str(pid),
                    "property_name": _property_display(prop) if prop else "",
                    "title": title,
                    "date": date_key,
                    "datetime_utc": scheduled_at.replace(tzinfo=timezone.utc).isoformat()
                    if scheduled_at.tzinfo is None
                    else scheduled_at.isoformat(),
                    "timezone": tz_name,
                    "status": schedule_status,
                    "severity": sev,
                    "urgency": "high" if schedule_status in (SCHEDULE_STATUS_RESCHEDULE_REQUESTED, SCHEDULE_STATUS_CANCELLED) else "medium",
                    "work_order_kind": kind,
                    "work_order_status": wo_status or None,
                    "primary_route": route,
                    "metadata": {
                        "work_order_id": wid,
                        "property_id": pid,
                        "contractor_id": wo.get("contractor_id"),
                        "schedule_status": schedule_status,
                    },
                }
            )

        # Compliance job in progress: only when status is IN_PROGRESS and there is no scheduled visit row
        # (avoids duplicating the same day as a proposed/confirmed visit).
        if kind == WORK_ORDER_KIND_COMPLIANCE and wo_status == STATUS_IN_PROGRESS:
            has_visit_row = scheduled_at is not None and schedule_status in (
                SCHEDULE_STATUS_PROPOSED,
                SCHEDULE_STATUS_CONFIRMED,
                SCHEDULE_STATUS_RESCHEDULE_REQUESTED,
                SCHEDULE_STATUS_CANCELLED,
                SCHEDULE_STATUS_COMPLETED,
            )
            if has_visit_row:
                continue
            anchor = _parse_dt(wo.get("accepted_at")) or _parse_dt(wo.get("updated_at"))
            if anchor is None:
                continue
            day_start = datetime(anchor.year, anchor.month, anchor.day, tzinfo=timezone.utc)
            if not (start <= day_start < end):
                continue
            date_key = day_start.strftime("%Y-%m-%d")
            out.append(
                {
                    "event_id": _stable_event_id(["wo_cj_prog", str(wid), date_key]),
                    "event_type": "compliance_job_started",
                    "event_category": "compliance_job",
                    "source_entity_type": "work_order",
                    "source_entity_id": str(wid),
                    "property_id": str(pid),
                    "property_name": _property_display(prop) if prop else "",
                    "title": "Compliance job in progress",
                    "date": date_key,
                    "datetime_utc": anchor.replace(tzinfo=timezone.utc).isoformat()
                    if anchor.tzinfo is None
                    else anchor.isoformat(),
                    "timezone": None,
                    "status": STATUS_IN_PROGRESS,
                    "severity": "medium",
                    "urgency": "medium",
                    "work_order_kind": kind,
                    "work_order_status": STATUS_IN_PROGRESS,
                    "primary_route": f"/operations/work-orders?work_order_id={wid}",
                    "metadata": {"work_order_id": wid, "property_id": pid},
                }
            )

    return out


def merge_and_sort_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def sort_key(e: Dict[str, Any]):
        d = e.get("date") or ""
        dt = e.get("datetime_utc") or ""
        cat = e.get("event_category") or ""
        return (d, dt, cat, e.get("title") or "")

    return sorted(events, key=sort_key)


def group_events_by_date(events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    by_date: Dict[str, List[Dict[str, Any]]] = {}
    for e in events:
        dk = e.get("date") or ""
        if not dk:
            continue
        by_date.setdefault(dk, []).append(e)
    for dk in by_date:
        by_date[dk].sort(
            key=lambda x: (
                x.get("severity") not in ("critical", "high"),
                x.get("datetime_utc") or "",
                x.get("title") or "",
            )
        )
    return by_date


def summarize_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    req = sum(1 for e in events if e.get("event_category") == "requirement")
    sj = sum(1 for e in events if e.get("event_category") == "scheduled_job")
    cj = sum(1 for e in events if e.get("event_category") == "compliance_job")
    overdue = sum(1 for e in events if e.get("event_type") == "requirement_overdue")
    expiring = sum(1 for e in events if e.get("event_type") == "requirement_expiring_soon")
    dates = len({e.get("date") for e in events if e.get("date")})
    return {
        "total_events": len(events),
        "requirement_events": req,
        "scheduled_job_events": sj,
        "compliance_job_events": cj,
        "overdue_count": overdue,
        "expiring_soon_count": expiring,
        "dates_with_events": dates,
    }


async def get_timeline_events_for_range(
    client_id: str,
    start: datetime,
    end: datetime,
    *,
    include_work_orders: bool = True,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    property_map, property_ids = await load_client_calendar_context(client_id)
    if not property_ids:
        return []

    requirements = await db.requirements.find({"property_id": {"$in": property_ids}}, {"_id": 0}).to_list(2000)
    requirement_ids = [r["requirement_id"] for r in requirements if r.get("requirement_id")]
    req_to_doc: Dict[str, str] = {}
    if requirement_ids:
        async for doc in db.documents.find(
            {"requirement_id": {"$in": requirement_ids}, "client_id": client_id},
            {"_id": 0, "requirement_id": 1, "document_id": 1},
        ).limit(2000):
            rid = doc.get("requirement_id")
            if rid and rid not in req_to_doc:
                req_to_doc[rid] = doc.get("document_id")

    ev_req = build_requirement_timeline_events(requirements, property_map, start, end, req_to_doc)
    ev_wo: List[Dict[str, Any]] = []
    if include_work_orders:
        try:
            wos = await db.work_orders.find(
                {"client_id": client_id, "property_id": {"$in": property_ids}},
                {
                    "_id": 0,
                    "work_order_id": 1,
                    "property_id": 1,
                    "client_id": 1,
                    "scheduled_at": 1,
                    "schedule_status": 1,
                    "scheduled_timezone": 1,
                    "work_order_kind": 1,
                    "status": 1,
                    "completed_at": 1,
                    "accepted_at": 1,
                    "updated_at": 1,
                    "contractor_id": 1,
                },
            ).to_list(500)
            ev_wo = build_work_order_timeline_events(wos, property_map, start, end)
        except Exception as e:
            logger.warning("calendar timeline: work_orders load failed: %s", e)

    merged = merge_and_sort_events(ev_req + ev_wo)
    # De-duplicate identical event_ids (shouldn't happen)
    seen = set()
    out: List[Dict[str, Any]] = []
    for e in merged:
        eid = e.get("event_id")
        if eid in seen:
            continue
        seen.add(eid)
        out.append(e)
    return out


def filter_timeline_events(
    events: List[Dict[str, Any]],
    *,
    categories: Optional[set] = None,
    urgent_only: bool = False,
) -> List[Dict[str, Any]]:
    if not categories and not urgent_only:
        return events
    out: List[Dict[str, Any]] = []
    for e in events:
        cat = e.get("event_category") or ""
        if categories and cat not in categories:
            continue
        if urgent_only:
            if e.get("event_type") != "requirement_overdue" and e.get("severity") != "critical":
                if e.get("event_type") != "requirement_expiring_soon":
                    continue
        out.append(e)
    return out


def ical_escape(value: Any) -> str:
    """Escape text for iCalendar SUMMARY/DESCRIPTION/LOCATION."""
    if value is None:
        return ""
    t = str(value).replace("\r", "").replace("\n", "\\n")
    return t.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")


def _ical_uid(event: Dict[str, Any]) -> str:
    eid = (event.get("event_id") or "").strip() or "unknown"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in eid)[:200]
    return f"{safe}@pleerity.timeline"


def _use_utc_datetime_for_ics(event: Dict[str, Any]) -> bool:
    """Timed visits use DTSTART in UTC; obligations and job milestones use all-day DATE."""
    et = str(event.get("event_type") or "")
    if et.startswith("work_order_visit_") or et.startswith("compliance_visit_"):
        return bool(event.get("datetime_utc"))
    return False


def _ical_alarm_days(event: Dict[str, Any]) -> Optional[int]:
    et = str(event.get("event_type") or "")
    if event.get("event_category") == "requirement":
        if "overdue" in et:
            return 1
        if "expiring" in et:
            return 7
        return 14
    if "visit" in et:
        return 1
    return None


def build_ical_from_timeline_events(
    events: List[Dict[str, Any]],
    *,
    calendar_name: str,
    client_ref: str,
    now_utc: datetime,
) -> str:
    """
    Build iCalendar (RFC 5545) document from unified timeline events (same source as /calendar/events).
    One VEVENT per timeline row; UIDs stable per event_id.
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Pleerity//Unified Timeline//EN",
        f"X-WR-CALNAME:{ical_escape(calendar_name)} - Timeline",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    stamp = now_utc.strftime("%Y%m%dT%H%M%SZ")
    seen_uid: set = set()

    for event in events:
        uid = _ical_uid(event)
        if uid in seen_uid:
            continue
        seen_uid.add(uid)

        summary = ical_escape(event.get("title") or "Event")
        loc = ical_escape(event.get("property_name") or "")
        desc_parts = [
            f"Type: {event.get('event_type')}",
            f"Category: {event.get('event_category')}",
            f"Status: {event.get('status')}",
        ]
        if event.get("date_source"):
            desc_parts.append(f"Date source: {event.get('date_source')}")
        if client_ref:
            desc_parts.append(f"Reference: {client_ref}")
        description = ical_escape("\n".join(desc_parts))

        cats = "Compliance,Obligation"
        if event.get("event_category") == "scheduled_job":
            cats = "Operations,Repair"
        elif event.get("event_category") == "compliance_job":
            cats = "Operations,Compliance"

        use_dt = _use_utc_datetime_for_ics(event)
        dt_line = ""
        if use_dt:
            dt = _parse_dt(event.get("datetime_utc"))
            if dt:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dt_utc = dt.astimezone(timezone.utc)
                dt_line = f"DTSTART:{dt_utc.strftime('%Y%m%dT%H%M%SZ')}"
        if not dt_line:
            dk = (event.get("date") or "")[:10].replace("-", "")
            if len(dk) != 8:
                continue
            dt_line = f"DTSTART;VALUE=DATE:{dk}"

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{stamp}",
                dt_line,
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{description}",
                f"LOCATION:{loc}",
                f"CATEGORIES:{cats}",
            ]
        )
        alarm = _ical_alarm_days(event)
        if alarm is not None and alarm > 0:
            lines.extend(
                [
                    "BEGIN:VALARM",
                    "ACTION:DISPLAY",
                    f"DESCRIPTION:{summary}",
                    f"TRIGGER:-P{alarm}D",
                    "END:VALARM",
                ]
            )
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)
