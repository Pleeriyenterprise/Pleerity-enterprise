"""Calendar Routes - Compliance Expiry Calendar View
Provides calendar data for visualizing certificate expirations.
"""
from fastapi import APIRouter, HTTPException, Request, status, Query
from database import database
from middleware import client_route_guard
from datetime import datetime, timezone, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/expiries")
async def get_expiry_calendar(
    request: Request,
    year: int = Query(default=None, description="Year to fetch (defaults to current year)"),
    month: Optional[int] = Query(default=None, ge=1, le=12, description="Month to fetch (1-12, optional)")
):
    """Get calendar data for certificate expirations.
    
    Returns requirements grouped by date for calendar visualization.
    Can filter by year and optionally by month.
    """
    user = await client_route_guard(request)
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
        
        # Get all properties for this client
        properties = await db.properties.find(
            {"client_id": client_id},
            {"_id": 0, "property_id": 1, "address_line_1": 1, "city": 1, "postcode": 1}
        ).to_list(100)
        
        property_map = {p["property_id"]: p for p in properties}
        property_ids = list(property_map.keys())
        
        # Get all requirements within date range
        requirements = await db.requirements.find(
            {
                "property_id": {"$in": property_ids},
                "due_date": {
                    "$gte": start_date.isoformat(),
                    "$lt": end_date.isoformat()
                }
            },
            {"_id": 0}
        ).to_list(500)
        
        # Group requirements by date
        events_by_date = {}
        
        for req in requirements:
            due_date_str = req.get("due_date", "")
            if isinstance(due_date_str, str):
                # Parse the date string
                try:
                    due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                except:
                    continue
            else:
                due_date = due_date_str
            
            date_key = due_date.strftime("%Y-%m-%d")
            
            if date_key not in events_by_date:
                events_by_date[date_key] = []
            
            property_info = property_map.get(req["property_id"], {})
            
            # Determine status color
            status = req.get("status", "PENDING")
            if status in ["OVERDUE", "EXPIRED"]:
                status_color = "red"
            elif status == "EXPIRING_SOON":
                status_color = "amber"
            elif status == "COMPLIANT":
                status_color = "green"
            else:
                status_color = "blue"
            
            events_by_date[date_key].append({
                "requirement_id": req["requirement_id"],
                "requirement_type": req["requirement_type"],
                "description": req["description"],
                "status": status,
                "status_color": status_color,
                "property_id": req["property_id"],
                "property_address": property_info.get("address_line_1", "Unknown"),
                "property_city": property_info.get("city", ""),
                "due_date": date_key
            })
        
        # Sort events within each date by status severity
        status_priority = {"OVERDUE": 0, "EXPIRED": 0, "EXPIRING_SOON": 1, "PENDING": 2, "COMPLIANT": 3}
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
        
        return {
            "year": year,
            "month": month,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "events_by_date": events_by_date,
            "summary": {
                "total_events": total_events,
                "overdue_count": overdue_count,
                "expiring_soon_count": expiring_soon_count,
                "dates_with_events": len(events_by_date)
            }
        }
    
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
    days: int = Query(default=90, ge=7, le=365, description="Number of days to look ahead")
):
    """Get upcoming certificate expirations for the next N days.
    
    Returns a list of requirements sorted by due date.
    """
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        client_id = user["client_id"]
        
        now = datetime.now(timezone.utc)
        end_date = now + timedelta(days=days)
        
        # Get all properties for this client
        properties = await db.properties.find(
            {"client_id": client_id},
            {"_id": 0, "property_id": 1, "address_line_1": 1, "city": 1}
        ).to_list(100)
        
        property_map = {p["property_id"]: p for p in properties}
        property_ids = list(property_map.keys())
        
        # Get requirements due within the time range
        requirements = await db.requirements.find(
            {
                "property_id": {"$in": property_ids},
                "due_date": {
                    "$gte": now.isoformat(),
                    "$lte": end_date.isoformat()
                }
            },
            {"_id": 0}
        ).sort("due_date", 1).to_list(100)
        
        # Enrich with property info and calculate days until due
        upcoming = []
        for req in requirements:
            property_info = property_map.get(req["property_id"], {})
            
            due_date_str = req.get("due_date", "")
            try:
                due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00')) if isinstance(due_date_str, str) else due_date_str
                days_until_due = (due_date - now).days
            except:
                days_until_due = 0
            
            upcoming.append({
                "requirement_id": req["requirement_id"],
                "requirement_type": req["requirement_type"],
                "description": req["description"],
                "status": req.get("status", "PENDING"),
                "due_date": req["due_date"],
                "days_until_due": days_until_due,
                "property_id": req["property_id"],
                "property_address": property_info.get("address_line_1", "Unknown"),
                "property_city": property_info.get("city", ""),
                "urgency": "high" if days_until_due <= 7 else ("medium" if days_until_due <= 30 else "low")
            })
        
        return {
            "days_ahead": days,
            "count": len(upcoming),
            "upcoming": upcoming
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
    days: int = Query(default=365, ge=30, le=730, description="Days of events to include")
):
    """Export compliance expiry dates as an iCal calendar file.
    
    Generates an iCal (.ics) file that can be subscribed to by external
    calendar applications (Google Calendar, Outlook, Apple Calendar).
    
    Plan gating: Requires Growth plan (PLAN_2_5) or higher.
    
    Returns:
        iCal file with VEVENT entries for each requirement expiry
    """
    from fastapi.responses import Response
    from services.plan_registry import plan_registry

    user = await client_route_guard(request)
    try:
        # TEMP Step 2: calendar_sync has no plan_registry key; gate by compliance_calendar (all plans have it)
        allowed, error_msg, error_details = await plan_registry.enforce_feature(
            user["client_id"],
            "compliance_calendar"
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": (error_details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
                    "message": error_msg,
                    "feature": "calendar_sync",
                    "upgrade_required": True,
                    **(error_details or {})
                }
            )
        
        db = database.get_db()
        client_id = user["client_id"]
        
        # Get client info for calendar name
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "full_name": 1, "company_name": 1, "customer_reference": 1}
        )
        
        calendar_name = client.get("company_name") or client.get("full_name") or "Compliance"
        crn = client.get("customer_reference", "")
        
        now = datetime.now(timezone.utc)
        end_date = now + timedelta(days=days)
        
        # Get all properties for this client
        properties = await db.properties.find(
            {"client_id": client_id},
            {"_id": 0, "property_id": 1, "address_line_1": 1, "city": 1, "postcode": 1}
        ).to_list(100)
        
        property_map = {p["property_id"]: p for p in properties}
        property_ids = list(property_map.keys())
        
        # Get requirements within date range
        requirements = await db.requirements.find(
            {
                "property_id": {"$in": property_ids},
                "due_date": {
                    "$gte": now.isoformat(),
                    "$lte": end_date.isoformat()
                }
            },
            {"_id": 0}
        ).sort("due_date", 1).to_list(500)
        
        # Build iCal content
        ical_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Compliance Vault Pro//Pleerity Enterprise Ltd//EN",
            f"X-WR-CALNAME:{calendar_name} - Compliance Expiries",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH"
        ]
        
        for req in requirements:
            property_info = property_map.get(req["property_id"], {})
            due_date_str = req.get("due_date", "")
            
            try:
                due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00')) if isinstance(due_date_str, str) else due_date_str
            except:
                continue
            
            # Create unique event ID
            event_uid = f"{req['requirement_id']}@compliance-vault-pro.pleerity.com"
            
            # Format dates for iCal (YYYYMMDD for all-day events)
            dtstart = due_date.strftime("%Y%m%d")
            
            # Build location string
            location = f"{property_info.get('address_line_1', '')}, {property_info.get('city', '')} {property_info.get('postcode', '')}".strip(", ")
            
            # Build description
            description = f"Requirement: {req.get('requirement_type', 'Unknown')}\\n"
            description += f"Property: {location}\\n"
            description += f"Status: {req.get('status', 'PENDING')}\\n"
            description += f"Description: {req.get('description', '')}\\n"
            if crn:
                description += f"CRN: {crn}"
            
            # Clean description for iCal (escape special chars)
            description = description.replace(",", "\\,").replace(";", "\\;")
            
            # Determine alarm based on status
            alarm_days = 7 if req.get("status") == "EXPIRING_SOON" else 30
            
            # Build event
            ical_lines.extend([
                "BEGIN:VEVENT",
                f"UID:{event_uid}",
                f"DTSTAMP:{now.strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART;VALUE=DATE:{dtstart}",
                f"SUMMARY:{req.get('requirement_type', 'Compliance')} Expiry - {property_info.get('address_line_1', 'Property')}",
                f"DESCRIPTION:{description}",
                f"LOCATION:{location}",
                "CATEGORIES:Compliance,Expiry",
                "STATUS:CONFIRMED",
                # Add alarm
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"DESCRIPTION:Compliance expiry reminder - {req.get('requirement_type', '')}",
                f"TRIGGER:-P{alarm_days}D",
                "END:VALARM",
                "END:VEVENT"
            ])
        
        ical_lines.append("END:VCALENDAR")
        
        # Join with CRLF as per iCal spec
        ical_content = "\r\n".join(ical_lines)
        
        # Generate filename
        filename = f"compliance_expiries_{crn or client_id}.ics"
        
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
    
    Plan gating: TEMP gated by compliance_calendar (Step 5 may introduce calendar_sync).
    """
    from services.plan_registry import plan_registry
    import os

    user = await client_route_guard(request)
    try:
        # TEMP Step 2: calendar_sync -> compliance_calendar
        allowed, error_msg, error_details = await plan_registry.enforce_feature(
            user["client_id"],
            "compliance_calendar"
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": (error_details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
                    "message": error_msg,
                    "feature": "calendar_sync",
                    "upgrade_required": True,
                    **(error_details or {})
                }
            )
        
        # Get base URL from environment
        base_url = os.environ.get("BASE_URL", request.base_url.scheme + "://" + request.base_url.netloc)
        
        # For now, return the authenticated endpoint
        # In production, you'd generate a long-lived token for calendar subscriptions
        subscription_url = f"{base_url}/api/calendar/export.ics"
        
        return {
            "subscription_url": subscription_url,
            "format": "iCal (.ics)",
            "note": "This URL requires authentication. For external calendar subscriptions, use the Download option.",
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
