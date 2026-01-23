"""
Full Reporting System - Export & Scheduling
Provides PDF, CSV, Excel exports and scheduled report delivery
"""
import io
import csv
import json
import uuid
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Literal
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, EmailStr

from middleware import admin_route_guard
from database import database
from models.core import AuditAction, UserRole
from utils.audit import create_audit_log
import logging

# Excel support
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

# PDF support
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/reports", tags=["Reports"])


# ============================================
# Report Types
# ============================================

class ReportType(str):
    REVENUE = "revenue"
    ORDERS = "orders"
    CLIENTS = "clients"
    LEADS = "leads"
    COMPLIANCE = "compliance"
    SLA = "sla"
    ENABLEMENT = "enablement"
    CONSENT = "consent"


class ExportFormat(str):
    CSV = "csv"
    JSON = "json"
    PDF = "pdf"
    XLSX = "xlsx"


# ============================================
# Request/Response Models
# ============================================

class ReportRequest(BaseModel):
    report_type: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    period: str = "30d"
    format: str = "csv"
    filters: Dict[str, Any] = {}


class ScheduledReportCreate(BaseModel):
    name: str = Field(..., max_length=100)
    report_type: str
    frequency: Literal["daily", "weekly", "monthly"]
    recipients: List[EmailStr]
    format: str = "csv"
    filters: Dict[str, Any] = {}
    enabled: bool = True


class ScheduledReportResponse(BaseModel):
    schedule_id: str
    name: str
    report_type: str
    frequency: str
    recipients: List[str]
    format: str
    filters: Dict[str, Any]
    enabled: bool
    last_run: Optional[datetime]
    next_run: Optional[datetime]
    created_at: datetime
    created_by: str


# ============================================
# Helper Functions
# ============================================

def generate_schedule_id() -> str:
    return f"SCHED-{uuid.uuid4().hex[:12].upper()}"


def generate_report_id() -> str:
    return f"RPT-{uuid.uuid4().hex[:12].upper()}"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_date(date_str: str) -> datetime:
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def get_date_range(period: str) -> tuple:
    """Get start and end dates for a period."""
    end = now_utc()
    
    if period == "today":
        start = end.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "7d":
        start = end - timedelta(days=7)
    elif period == "30d":
        start = end - timedelta(days=30)
    elif period == "90d":
        start = end - timedelta(days=90)
    elif period == "ytd":
        start = end.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = end - timedelta(days=30)
    
    return start, end


# ============================================
# Data Fetchers
# ============================================

async def fetch_revenue_data(start: datetime, end: datetime, filters: dict) -> List[dict]:
    """Fetch revenue report data."""
    db = database.get_db()
    
    query = {
        "created_at": {"$gte": start.isoformat(), "$lte": end.isoformat()},
        "stripe_payment_status": "paid"
    }
    
    if filters.get("service_code"):
        query["service_code"] = filters["service_code"]
    
    cursor = db.orders.find(query, {"_id": 0}).sort("created_at", -1)
    orders = await cursor.to_list(10000)
    
    data = []
    for order in orders:
        data.append({
            "Order ID": order.get("order_id"),
            "Date": order.get("created_at", "")[:10],
            "Client ID": order.get("client_id"),
            "Service": order.get("service_name", order.get("service_code")),
            "Amount (£)": (order.get("pricing", {}).get("total_pence", 0) or 0) / 100,
            "Status": order.get("status"),
            "Payment Status": order.get("stripe_payment_status"),
        })
    
    return data


async def fetch_orders_data(start: datetime, end: datetime, filters: dict) -> List[dict]:
    """Fetch orders report data."""
    db = database.get_db()
    
    query = {"created_at": {"$gte": start.isoformat(), "$lte": end.isoformat()}}
    
    if filters.get("status"):
        query["status"] = filters["status"]
    
    cursor = db.orders.find(query, {"_id": 0}).sort("created_at", -1)
    orders = await cursor.to_list(10000)
    
    data = []
    for order in orders:
        data.append({
            "Order ID": order.get("order_id"),
            "Date": order.get("created_at", "")[:10],
            "Client ID": order.get("client_id"),
            "Service": order.get("service_name"),
            "Status": order.get("status"),
            "Amount (£)": (order.get("pricing", {}).get("total_pence", 0) or 0) / 100,
            "Fast Track": "Yes" if order.get("fast_track") else "No",
            "Printed Copy": "Yes" if order.get("printed_copy") else "No",
        })
    
    return data


async def fetch_clients_data(start: datetime, end: datetime, filters: dict) -> List[dict]:
    """Fetch clients report data."""
    db = database.get_db()
    
    query = {"created_at": {"$gte": start.isoformat(), "$lte": end.isoformat()}}
    
    cursor = db.clients.find(query, {"_id": 0}).sort("created_at", -1)
    clients = await cursor.to_list(10000)
    
    data = []
    for client in clients:
        data.append({
            "Client ID": client.get("client_id"),
            "Name": client.get("name"),
            "Email": client.get("email"),
            "Phone": client.get("phone"),
            "Created": client.get("created_at", "")[:10],
            "Plan": client.get("plan_code"),
            "Status": client.get("onboarding_status"),
            "Properties": client.get("property_count", 0),
        })
    
    return data


async def fetch_leads_data(start: datetime, end: datetime, filters: dict) -> List[dict]:
    """Fetch leads report data."""
    db = database.get_db()
    
    query = {"created_at": {"$gte": start.isoformat(), "$lte": end.isoformat()}}
    
    if filters.get("stage"):
        query["stage"] = filters["stage"]
    if filters.get("intent_score"):
        query["intent_score"] = {"$gte": filters["intent_score"]}
    
    cursor = db.leads.find(query, {"_id": 0}).sort("created_at", -1)
    leads = await cursor.to_list(10000)
    
    data = []
    for lead in leads:
        data.append({
            "Lead ID": lead.get("lead_id"),
            "Email": lead.get("email"),
            "Name": lead.get("name"),
            "Created": lead.get("created_at", "")[:10],
            "Source": lead.get("source_platform"),
            "Stage": lead.get("stage"),
            "Intent Score": lead.get("intent_score"),
            "Converted": "Yes" if lead.get("converted_to_client") else "No",
        })
    
    return data


async def fetch_compliance_data(start: datetime, end: datetime, filters: dict) -> List[dict]:
    """Fetch compliance report data."""
    db = database.get_db()
    
    # Get all properties
    cursor = db.properties.find({}, {"_id": 0})
    properties = await cursor.to_list(10000)
    
    data = []
    for prop in properties:
        data.append({
            "Property ID": prop.get("property_id"),
            "Address": prop.get("address", {}).get("line1", ""),
            "Postcode": prop.get("address", {}).get("postcode", ""),
            "Client ID": prop.get("client_id"),
            "Compliance %": prop.get("compliance_score", 0),
            "Status": prop.get("compliance_status", "UNKNOWN"),
            "Total Requirements": prop.get("total_requirements", 0),
            "Met Requirements": prop.get("met_requirements", 0),
        })
    
    return data


async def fetch_enablement_data(start: datetime, end: datetime, filters: dict) -> List[dict]:
    """Fetch enablement report data."""
    db = database.get_db()
    
    query = {"created_at": {"$gte": start.isoformat(), "$lte": end.isoformat()}}
    
    if filters.get("status"):
        query["status"] = filters["status"]
    if filters.get("category"):
        query["category"] = filters["category"]
    
    cursor = db.enablement_actions.find(query, {"_id": 0}).sort("created_at", -1)
    actions = await cursor.to_list(10000)
    
    data = []
    for action in actions:
        data.append({
            "Action ID": action.get("action_id"),
            "Date": action.get("created_at", "")[:19],
            "Client ID": action.get("client_id"),
            "Event Type": action.get("event_type"),
            "Category": action.get("category"),
            "Channel": action.get("channel"),
            "Status": action.get("status"),
            "Title": action.get("rendered_title", "")[:50],
        })
    
    return data


async def fetch_consent_data(start: datetime, end: datetime, filters: dict) -> List[dict]:
    """Fetch consent report data."""
    db = database.get_db()
    
    query = {"created_at": {"$gte": start.isoformat(), "$lte": end.isoformat()}}
    
    cursor = db.consent_events.find(query, {"_id": 0}).sort("created_at", -1)
    events = await cursor.to_list(10000)
    
    data = []
    for event in events:
        prefs = event.get("preferences", {})
        data.append({
            "Event ID": event.get("event_id"),
            "Date": event.get("created_at", "")[:19],
            "Session ID": event.get("session_id"),
            "Action": event.get("event_type"),
            "Analytics": "Yes" if prefs.get("analytics") else "No",
            "Marketing": "Yes" if prefs.get("marketing") else "No",
            "Functional": "Yes" if prefs.get("functional") else "No",
        })
    
    return data


# Data fetcher mapping
DATA_FETCHERS = {
    "revenue": fetch_revenue_data,
    "orders": fetch_orders_data,
    "clients": fetch_clients_data,
    "leads": fetch_leads_data,
    "compliance": fetch_compliance_data,
    "enablement": fetch_enablement_data,
    "consent": fetch_consent_data,
}


# ============================================
# Export Formatters
# ============================================

def format_csv(data: List[dict]) -> io.StringIO:
    """Format data as CSV."""
    output = io.StringIO()
    
    if not data:
        output.write("No data available\n")
        return output
    
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    
    output.seek(0)
    return output


def format_json(data: List[dict]) -> io.StringIO:
    """Format data as JSON."""
    output = io.StringIO()
    json.dump({"data": data, "count": len(data), "generated_at": now_utc().isoformat()}, output, indent=2, default=str)
    output.seek(0)
    return output


# ============================================
# API Endpoints
# ============================================

@router.get("/types")
async def get_report_types(admin: dict = Depends(admin_route_guard)):
    """Get available report types."""
    return {
        "types": [
            {"value": "revenue", "label": "Revenue Report", "description": "Revenue by orders and services"},
            {"value": "orders", "label": "Orders Report", "description": "All orders with status"},
            {"value": "clients", "label": "Clients Report", "description": "Client listing and details"},
            {"value": "leads", "label": "Leads Report", "description": "Lead pipeline data"},
            {"value": "compliance", "label": "Compliance Report", "description": "Property compliance status"},
            {"value": "enablement", "label": "Enablement Report", "description": "Customer enablement actions"},
            {"value": "consent", "label": "Consent Report", "description": "Cookie consent events"},
        ],
        "formats": [
            {"value": "csv", "label": "CSV"},
            {"value": "json", "label": "JSON"},
        ],
        "periods": [
            {"value": "today", "label": "Today"},
            {"value": "7d", "label": "Last 7 Days"},
            {"value": "30d", "label": "Last 30 Days"},
            {"value": "90d", "label": "Last 90 Days"},
            {"value": "ytd", "label": "Year to Date"},
            {"value": "custom", "label": "Custom Range"},
        ]
    }


@router.post("/generate")
async def generate_report(
    request: ReportRequest,
    admin: dict = Depends(admin_route_guard)
):
    """Generate a report and return as download."""
    
    if request.report_type not in DATA_FETCHERS:
        raise HTTPException(status_code=400, detail=f"Unknown report type: {request.report_type}")
    
    # Determine date range
    if request.start_date and request.end_date:
        start = parse_date(request.start_date)
        end = parse_date(request.end_date)
    else:
        start, end = get_date_range(request.period)
    
    # Fetch data
    fetcher = DATA_FETCHERS[request.report_type]
    data = await fetcher(start, end, request.filters)
    
    # Format output
    if request.format == "json":
        output = format_json(data)
        media_type = "application/json"
        extension = "json"
    else:  # Default to CSV
        output = format_csv(data)
        media_type = "text/csv"
        extension = "csv"
    
    filename = f"{request.report_type}_report_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.{extension}"
    
    # Audit log
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=admin.get("portal_user_id"),
        resource_type="report",
        resource_id=generate_report_id(),
        metadata={
            "report_type": request.report_type,
            "format": request.format,
            "period": f"{start.isoformat()} to {end.isoformat()}",
            "row_count": len(data)
        }
    )
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/preview/{report_type}")
async def preview_report(
    report_type: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: str = "30d",
    limit: int = Query(20, ge=1, le=100),
    admin: dict = Depends(admin_route_guard)
):
    """Preview report data without downloading."""
    
    if report_type not in DATA_FETCHERS:
        raise HTTPException(status_code=400, detail=f"Unknown report type: {report_type}")
    
    # Determine date range
    if start_date and end_date:
        start = parse_date(start_date)
        end = parse_date(end_date)
    else:
        start, end = get_date_range(period)
    
    # Fetch data
    fetcher = DATA_FETCHERS[report_type]
    data = await fetcher(start, end, {})
    
    return {
        "report_type": report_type,
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "total_rows": len(data),
        "preview": data[:limit],
        "columns": list(data[0].keys()) if data else []
    }


# ============================================
# Scheduled Reports
# ============================================

@router.get("/schedules")
async def list_scheduled_reports(admin: dict = Depends(admin_route_guard)):
    """List all scheduled reports."""
    db = database.get_db()
    
    cursor = db.report_schedules.find({}, {"_id": 0}).sort("created_at", -1)
    schedules = await cursor.to_list(100)
    
    return {"schedules": schedules, "total": len(schedules)}


@router.post("/schedules")
async def create_scheduled_report(
    request: ScheduledReportCreate,
    admin: dict = Depends(admin_route_guard)
):
    """Create a new scheduled report."""
    db = database.get_db()
    
    if request.report_type not in DATA_FETCHERS:
        raise HTTPException(status_code=400, detail=f"Unknown report type: {request.report_type}")
    
    schedule_id = generate_schedule_id()
    now = now_utc()
    
    # Calculate next run based on frequency
    if request.frequency == "daily":
        next_run = now.replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=1)
    elif request.frequency == "weekly":
        days_until_monday = (7 - now.weekday()) % 7
        next_run = now.replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=days_until_monday or 7)
    else:  # monthly
        if now.month == 12:
            next_run = now.replace(year=now.year + 1, month=1, day=1, hour=8, minute=0, second=0, microsecond=0)
        else:
            next_run = now.replace(month=now.month + 1, day=1, hour=8, minute=0, second=0, microsecond=0)
    
    schedule = {
        "schedule_id": schedule_id,
        "name": request.name,
        "report_type": request.report_type,
        "frequency": request.frequency,
        "recipients": request.recipients,
        "format": request.format,
        "filters": request.filters,
        "enabled": request.enabled,
        "last_run": None,
        "next_run": next_run.isoformat(),
        "created_at": now.isoformat(),
        "created_by": admin.get("portal_user_id"),
    }
    
    await db.report_schedules.insert_one(schedule)
    
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=admin.get("portal_user_id"),
        resource_type="report_schedule",
        resource_id=schedule_id,
        metadata={"action": "create", "name": request.name, "frequency": request.frequency}
    )
    
    del schedule["_id"] if "_id" in schedule else None
    return schedule


@router.put("/schedules/{schedule_id}/toggle")
async def toggle_scheduled_report(
    schedule_id: str,
    admin: dict = Depends(admin_route_guard)
):
    """Enable or disable a scheduled report."""
    db = database.get_db()
    
    schedule = await db.report_schedules.find_one({"schedule_id": schedule_id})
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    new_status = not schedule.get("enabled", True)
    
    await db.report_schedules.update_one(
        {"schedule_id": schedule_id},
        {"$set": {"enabled": new_status}}
    )
    
    return {"schedule_id": schedule_id, "enabled": new_status}


@router.delete("/schedules/{schedule_id}")
async def delete_scheduled_report(
    schedule_id: str,
    admin: dict = Depends(admin_route_guard)
):
    """Delete a scheduled report."""
    db = database.get_db()
    
    result = await db.report_schedules.delete_one({"schedule_id": schedule_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=admin.get("portal_user_id"),
        resource_type="report_schedule",
        resource_id=schedule_id,
        metadata={"action": "delete"}
    )
    
    return {"success": True}


# ============================================
# Report History
# ============================================

@router.get("/history")
async def get_report_history(
    limit: int = Query(50, ge=1, le=200),
    admin: dict = Depends(admin_route_guard)
):
    """Get report generation history from audit logs."""
    db = database.get_db()
    
    cursor = db.audit_logs.find(
        {"resource_type": "report"},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit)
    
    logs = await cursor.to_list(limit)
    
    return {"history": logs, "total": len(logs)}
