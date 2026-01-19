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
