"""Calendar Routes - Compliance Expiry Calendar View
Provides calendar data for visualizing certificate expirations.
Uses deterministic expiry: confirmed_expiry_date else extracted_expiry_date else due_date.
Excludes applicability=NOT_REQUIRED from events.
"""
from fastapi import APIRouter, HTTPException, Request, status, Query
from fastapi.responses import JSONResponse, Response
from database import database
from middleware import client_route_guard
from middleware.capability_gating import capability_denied_http_detail, enforce_route_capability
from services.account_capability_enforcement import CapabilityEnforcementService
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
import logging

from utils.expiry_utils import get_effective_expiry_date, get_computed_status, is_included_for_calendar

from services.client_calendar_timeline_service import (
    build_ical_from_timeline_events,
    filter_timeline_events,
    get_timeline_events_for_range,
    group_events_by_date,
    summarize_events,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/calendar", tags=["calendar"])

_FILTER_ALIASES = {
    "requirements": "requirement",
    "scheduled_jobs": "scheduled_job",
    "compliance_jobs": "compliance_job",
    "compliance": "compliance_job",
}


async def _enforce_capability(
    user: Dict[str, Any],
    capability_id: str,
    action: str,
    *,
    request: Request | None = None,
) -> None:
    await enforce_route_capability(user, capability_id, action, request=request)


async def _require_calendar_view(request: Request) -> Dict[str, Any]:
    user = await client_route_guard(request)
    await _enforce_capability(user, "CAP_CALENDAR_VIEW", "read", request=request)
    return user


def _parse_filter_categories(filters: Optional[str]) -> Optional[set]:
    if not filters or not str(filters).strip():
        return None
    out = set()
    for part in str(filters).split(","):
        key = part.strip().lower()
        if key in _FILTER_ALIASES:
            out.add(_FILTER_ALIASES[key])
    return out or None


@router.get("/events")
async def get_calendar_events(
    request: Request,
    year: Optional[int] = Query(default=None),
    month: Optional[int] = Query(default=None, ge=1, le=12),
    filters: Optional[str] = Query(default=None, description="Comma-separated: requirements,scheduled_jobs,compliance_jobs"),
    urgent_only: bool = Query(default=False),
):
    """
    Unified timeline events for the month (requirements + scheduled work orders + compliance milestones).
    Obligation dates use requirement truth (effective expiry); visits use work_orders.scheduled_at + schedule_status.
    """
    user = await _require_calendar_view(request)
    now = datetime.now(timezone.utc)
    year = year or now.year
    if month:
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc) if month < 12 else datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)

    raw = await get_timeline_events_for_range(user["client_id"], start, end, include_work_orders=True)
    cats = _parse_filter_categories(filters)
    events = filter_timeline_events(raw, categories=cats, urgent_only=urgent_only)
    events_by_date = group_events_by_date(events)
    summary = summarize_events(events)

    return {
        "model_version": 2,
        "events_by_date": events_by_date,
        "summary": summary,
        "year": year,
        "month": month,
    }


@router.get("/expiries", deprecated=True)
async def get_expiry_calendar(
    request: Request,
    year: int = Query(default=None, description="Year to fetch (defaults to current year)"),
    month: Optional[int] = Query(default=None, ge=1, le=12, description="Month to fetch (1-12, optional)")
):
    """**Deprecated** — legacy requirement-only calendar JSON (status_color, no work orders).

    Use ``GET /api/calendar/events`` for the unified timeline (requirements + scheduled visits + compliance milestones).

    **Differs from unified model:** no ``event_id`` / ``event_type``; no work-order schedule overlay;
    same underlying requirement *dates* as unified (effective expiry via ``get_effective_expiry_date``).

    Remaining consumers: external/integration tests and docs; do not add new client-portal usage.
    """
    user = await _require_calendar_view(request)
    db = database.get_db()
    
    try:
        client_id = user["client_id"]
        
        # Default to current year if not specified
        now = datetime.now(timezone.utc)
        if year is None:
            year = now.year
        
        # Build date range
        if month:
            # Specific month
            start_date = datetime(year, month, 1, tzinfo=timezone.utc)
            if month == 12:
                end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        else:
            # Entire year
            start_date = datetime(year, 1, 1, tzinfo=timezone.utc)
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        
        client_row = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "default_jurisdiction": 1},
        ) or {}

        # Get all properties for this client (full docs for planner-aligned requirement filtering)
        properties = await db.properties.find(
            {"client_id": client_id},
            {"_id": 0},
        ).to_list(100)
        
        property_map = {p["property_id"]: p for p in properties}
        property_ids = list(property_map.keys())
        if not property_ids:
            requirements = []
        else:
            requirements = await db.requirements.find(
                {"property_id": {"$in": property_ids}, "client_id": client_id},
                {"_id": 0},
            ).to_list(500)
            from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

            requirements = await filter_requirement_rows_for_client_runtime_surfaces(
                db,
                client_id=client_id,
                requirements=requirements,
                client_doc=client_row,
                properties=properties,
            )

        events_by_date = {}
        for req in requirements:
            if not is_included_for_calendar(req):
                continue
            due_date = get_effective_expiry_date(req)
            if due_date is None or not (start_date <= due_date < end_date):
                continue
            date_key = due_date.strftime("%Y-%m-%d")
            if date_key not in events_by_date:
                events_by_date[date_key] = []
            property_info = property_map.get(req["property_id"], {})
            status = get_computed_status(req, property_doc=property_info, client_doc=client_row)
            status_color = "red" if status in ["OVERDUE"] else "amber" if status == "EXPIRING_SOON" else "green" if status == "COMPLIANT" else "blue"
            events_by_date[date_key].append({
                "requirement_id": req["requirement_id"],
                "requirement_type": req["requirement_type"],
                "description": req.get("description", ""),
                "status": status,
                "status_color": status_color,
                "property_id": req["property_id"],
                "property_address": property_info.get("address_line_1", "Unknown"),
                "property_city": property_info.get("city", ""),
                "due_date": date_key
            })

        status_priority = {"OVERDUE": 0, "EXPIRING_SOON": 1, "PENDING": 2, "COMPLIANT": 3, "UNKNOWN_DATE": 4}
        for date_key in events_by_date:
            events_by_date[date_key].sort(key=lambda x: status_priority.get(x["status"], 4))
        
        # Calculate summary statistics
        total_events = sum(len(events) for events in events_by_date.values())
        overdue_count = sum(
            1 for events in events_by_date.values() 
            for e in events if e["status"] in ["OVERDUE", "EXPIRED"]
        )
        expiring_soon_count = sum(
            1 for events in events_by_date.values()
            for e in events if e["status"] == "EXPIRING_SOON"
        )
        
        payload = {
            "year": year,
            "month": month,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "events_by_date": events_by_date,
            "summary": {
                "total_events": total_events,
                "overdue_count": overdue_count,
                "expiring_soon_count": expiring_soon_count,
                "dates_with_events": len(events_by_date),
            },
            "deprecated": True,
            "successor": "/api/calendar/events",
        }
        return JSONResponse(
            content=payload,
            headers={
                "Deprecation": "true",
                "Link": "</api/calendar/events>; rel=\"successor-version\"",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Calendar expiries error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load calendar data"
        )


@router.get("/upcoming")
async def get_upcoming_expiries(
    request: Request,
    days: int = Query(default=90, ge=7, le=365, description="Number of days to look ahead"),
    filters: Optional[str] = Query(default=None, description="Comma-separated: requirements,scheduled_jobs,compliance_jobs"),
    urgent_only: bool = Query(default=False),
):
    """Unified timeline for list/agenda view: obligations + visits in range (includes overdue obligations)."""
    user = await _require_calendar_view(request)
    try:
        now = datetime.now(timezone.utc)
        lookback_days = 730
        start = now - timedelta(days=lookback_days)
        end = now + timedelta(days=days)

        raw = await get_timeline_events_for_range(user["client_id"], start, end, include_work_orders=True)
        cats = _parse_filter_categories(filters)
        events = filter_timeline_events(raw, categories=cats, urgent_only=urgent_only)
        events.sort(key=lambda e: (e.get("date") or "", e.get("datetime_utc") or "", e.get("title") or ""))

        # Legacy shape for consumers that still expect requirement-only rows
        upcoming_legacy = []
        for e in events:
            if e.get("event_category") != "requirement":
                continue
            rid = (e.get("metadata") or {}).get("requirement_id")
            if not rid:
                continue
            try:
                due_dt = datetime.fromisoformat(str(e.get("datetime_utc") or "").replace("Z", "+00:00"))
            except Exception:
                due_dt = now
            days_until = (due_dt - now).days
            upcoming_legacy.append(
                {
                    "requirement_id": rid,
                    "requirement_type": e.get("requirement_type") or "",
                    "description": e.get("title") or "",
                    "status": e.get("status"),
                    "due_date": due_dt.isoformat(),
                    "days_until_due": days_until,
                    "property_id": e.get("property_id"),
                    "property_address": e.get("property_name") or "",
                    "property_city": "",
                    "urgency": e.get("urgency")
                    or ("high" if days_until <= 7 else "medium" if days_until <= 30 else "low"),
                }
            )

        return {
            "model_version": 2,
            "days_ahead": days,
            "count": len(events),
            "timeline_events": events,
            "summary": summarize_events(events),
            "upcoming": upcoming_legacy,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upcoming expiries error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load upcoming expiries"
        )


@router.get("/export.ics")
async def export_ical_calendar(
    request: Request,
    days: int = Query(default=365, ge=30, le=730, description="Days of events to include"),
    lookback_days: int = Query(
        default=365,
        ge=0,
        le=1095,
        description="Days before today to include (obligations and visits in the past window)",
    ),
    filters: Optional[str] = Query(
        default=None,
        description="Same as /calendar/events: comma-separated requirements,scheduled_jobs,compliance_jobs",
    ),
    urgent_only: bool = Query(default=False, description="Same as /calendar/events: only overdue / expiring-soon requirements"),
):
    """Export unified timeline as iCal (.ics): same pipeline as ``/calendar/events`` (including filters).

    Uses ``get_timeline_events_for_range`` then ``filter_timeline_events`` so exports match the client
    calendar when the same ``filters`` and ``urgent_only`` query params are used.
    """
    user = await _require_calendar_view(request)
    try:
        db = database.get_db()
        client_id = user["client_id"]
        
        # Get client info for calendar name
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "full_name": 1, "company_name": 1, "customer_reference": 1}
        ) or {}

        calendar_name = client.get("company_name") or client.get("full_name") or "Compliance"
        crn = client.get("customer_reference", "")

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=lookback_days)
        end = now + timedelta(days=days)

        raw_timeline = await get_timeline_events_for_range(client_id, start, end, include_work_orders=True)
        cats = _parse_filter_categories(filters)
        timeline_events = filter_timeline_events(
            raw_timeline,
            categories=cats,
            urgent_only=urgent_only,
        )
        ical_content = build_ical_from_timeline_events(
            timeline_events,
            calendar_name=str(calendar_name),
            client_ref=str(crn or client_id or ""),
            now_utc=now,
        )

        filename = f"compliance_timeline_{crn or client_id}.ics"
        
        return Response(
            content=ical_content,
            media_type="text/calendar",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"iCal export error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate iCal calendar"
        )


@router.get("/subscription-url")
async def get_calendar_subscription_url(request: Request):
    """Get the URL for subscribing to the compliance calendar.
    
    Returns a URL that can be used to subscribe to the calendar
    in external applications. The URL includes an authentication token.
    
    Plan gating: ``CAP_CALENDAR_VIEW`` via Runtime Contract (plan key ``compliance_calendar``).
    """
    user = await _require_calendar_view(request)
    try:
        # Get base URL from environment
        from utils.app_urls import get_api_base_url

        _fallback = request.base_url.scheme + "://" + request.base_url.netloc
        base_url = get_api_base_url() or _fallback
        
        # For now, return the authenticated endpoint
        # In production, you'd generate a long-lived token for calendar subscriptions
        subscription_url = f"{base_url}/api/calendar/export.ics"
        
        return {
            "subscription_url": subscription_url,
            "format": "iCal (.ics)",
            "note": (
                "This URL requires authentication. Default feed includes all categories; add "
                "filters=requirements,scheduled_jobs,compliance_jobs and/or urgent_only=true to match "
                "the client calendar. For a filtered export from the portal, use Download on the calendar page."
            ),
            "instructions": {
                "google_calendar": "Settings → Add calendar → From URL → Paste URL",
                "outlook": "Add calendar → Subscribe from web → Paste URL",
                "apple_calendar": "File → New Calendar Subscription → Paste URL"
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Subscription URL error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate subscription URL"
        )
