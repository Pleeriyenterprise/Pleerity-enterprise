"""
Cookie Consent API Routes

Public endpoints for consent capture.
Admin endpoints for consent dashboard (ROLE_ADMIN only).
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Query, Response
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import io
import csv
import logging

from models.consent import (
    ConsentCaptureRequest,
    ConsentPreferences,
    ConsentEventType,
)
from services.consent_service import (
    ConsentService,
    ConsentAdminService,
)
from routes.auth import admin_route_guard
import database

logger = logging.getLogger(__name__)

# Public router - no auth required
public_router = APIRouter(prefix="/consent", tags=["Consent"])

# Admin router - ROLE_ADMIN required
admin_router = APIRouter(prefix="/admin/consent", tags=["Admin Consent"])


# =============================================================================
# PUBLIC ENDPOINTS
# =============================================================================

@public_router.post("/capture")
async def capture_consent(
    request: ConsentCaptureRequest,
    req: Request,
):
    """
    Capture consent from frontend cookie banner.
    Public endpoint - no auth required.
    """
    # Get IP address (for hashing only)
    ip_address = req.headers.get("X-Forwarded-For", req.client.host if req.client else None)
    if ip_address and "," in ip_address:
        ip_address = ip_address.split(",")[0].strip()
    
    result = await ConsentService.capture_consent(
        request=request,
        ip_address=ip_address,
    )
    
    return result


@public_router.get("/state/{session_id}")
async def get_consent_state(session_id: str):
    """
    Get current consent state for a session.
    Used by frontend to restore preferences.
    """
    state = await ConsentService.get_consent_state(session_id)
    
    if not state:
        return {
            "exists": False,
            "preferences": {
                "necessary": True,
                "analytics": False,
                "marketing": False,
                "functional": False,
            },
        }
    
    return {
        "exists": True,
        "preferences": state.get("preferences", {}),
        "consent_version": state.get("consent_version"),
        "action_taken": state.get("action_taken"),
    }


@public_router.post("/withdraw")
async def withdraw_consent(
    session_id: str,
    categories: Optional[list] = None,
):
    """
    Withdraw consent for specified categories.
    """
    result = await ConsentService.withdraw_consent(
        session_id=session_id,
        categories=categories,
    )
    return result


# =============================================================================
# ADMIN ENDPOINTS - ROLE_ADMIN REQUIRED
# =============================================================================

@admin_router.get("/stats")
async def get_consent_stats(
    from_date: str = Query(None, alias="from", description="Start date YYYY-MM-DD"),
    to_date: str = Query(None, alias="to", description="End date YYYY-MM-DD"),
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get consent statistics for admin dashboard.
    Returns KPIs, category breakdowns, and trend data.
    """
    # Default to last 30 days
    if not to_date:
        to_dt = datetime.now(timezone.utc)
    else:
        to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00")) if "T" in to_date else datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    
    if not from_date:
        from_dt = to_dt - timedelta(days=30)
    else:
        from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00")) if "T" in from_date else datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    
    stats = await ConsentAdminService.get_stats(from_dt, to_dt)
    
    return stats


@admin_router.get("/logs")
async def get_consent_logs(
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    action_taken: Optional[str] = Query(None),
    marketing: Optional[str] = Query(None),
    analytics: Optional[str] = Query(None),
    user_type: Optional[str] = Query(None),
    crn: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    consent_version: Optional[str] = Query(None),
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get paginated consent logs for admin dashboard.
    """
    # Default to last 30 days
    if not to_date:
        to_dt = datetime.now(timezone.utc)
    else:
        to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00")) if "T" in to_date else datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    
    if not from_date:
        from_dt = to_dt - timedelta(days=30)
    else:
        from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00")) if "T" in from_date else datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    
    filters = {
        "action_taken": action_taken,
        "marketing": marketing,
        "analytics": analytics,
        "user_type": user_type,
        "crn": crn,
        "email": email,
        "session_id": session_id,
        "country": country,
        "consent_version": consent_version,
    }
    
    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}
    
    rows, total = await ConsentAdminService.get_logs(
        from_dt, to_dt, page, page_size, filters
    )
    
    return {
        "rows": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@admin_router.get("/logs/{event_id}")
async def get_consent_log_detail(
    event_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get detailed consent record for admin drawer view.
    """
    detail = await ConsentAdminService.get_log_detail(event_id)
    
    if not detail:
        raise HTTPException(status_code=404, detail="Consent record not found")
    
    return detail


@admin_router.get("/export.csv")
async def export_consent_csv(
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    action_taken: Optional[str] = Query(None),
    marketing: Optional[str] = Query(None),
    analytics: Optional[str] = Query(None),
    current_user: dict = Depends(admin_route_guard),
):
    """
    Export consent logs as CSV.
    """
    # Default to last 30 days
    if not to_date:
        to_dt = datetime.now(timezone.utc)
    else:
        to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00")) if "T" in to_date else datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    
    if not from_date:
        from_dt = to_dt - timedelta(days=30)
    else:
        from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00")) if "T" in from_date else datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    
    filters = {
        "action_taken": action_taken,
        "marketing": marketing,
        "analytics": analytics,
    }
    filters = {k: v for k, v in filters.items() if v is not None}
    
    # Get all logs (up to 10k for export)
    rows, _ = await ConsentAdminService.get_logs(
        from_dt, to_dt, page=1, page_size=10000, filters=filters
    )
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "Event ID",
        "Timestamp (UTC)",
        "Action",
        "Marketing",
        "Analytics",
        "Functional",
        "Session ID",
        "CRN",
        "Country",
        "Page",
        "Consent Version",
    ])
    
    for row in rows:
        prefs = row.get("preferences", {})
        writer.writerow([
            row.get("event_id"),
            row.get("created_at"),
            row.get("action_taken"),
            "Yes" if prefs.get("marketing") else "No",
            "Yes" if prefs.get("analytics") else "No",
            "Yes" if prefs.get("functional") else "No",
            row.get("session_id"),
            row.get("crn") or "",
            row.get("country") or "",
            row.get("page_path") or "",
            row.get("consent_version"),
        ])
    
    output.seek(0)
    
    filename = f"consent_export_{from_dt.strftime('%Y%m%d')}_{to_dt.strftime('%Y%m%d')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@admin_router.get("/export.pdf")
async def export_consent_pdf(
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    current_user: dict = Depends(admin_route_guard),
):
    """
    Export consent summary as PDF.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.units import inch
    except ImportError:
        raise HTTPException(status_code=500, detail="PDF generation not available")
    
    # Default to last 30 days
    if not to_date:
        to_dt = datetime.now(timezone.utc)
    else:
        to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00")) if "T" in to_date else datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    
    if not from_date:
        from_dt = to_dt - timedelta(days=30)
    else:
        from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00")) if "T" in from_date else datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    
    # Get stats
    stats = await ConsentAdminService.get_stats(from_dt, to_dt)
    
    # Get top 50 logs
    rows, total = await ConsentAdminService.get_logs(from_dt, to_dt, page=1, page_size=50)
    
    # Create PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=18, spaceAfter=12)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=14, spaceAfter=6)
    
    story = []
    
    # Title
    story.append(Paragraph("Cookie Consent Report", title_style))
    story.append(Paragraph(f"Period: {from_dt.strftime('%Y-%m-%d')} to {to_dt.strftime('%Y-%m-%d')}", styles['Normal']))
    story.append(Paragraph(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # KPIs
    story.append(Paragraph("Summary Statistics", heading_style))
    kpis = stats.get("kpis", {})
    kpi_data = [
        ["Metric", "Value"],
        ["Total Sessions (Banner Shown)", str(kpis.get("total_sessions_shown", 0))],
        ["Accept All", str(kpis.get("accept_all_count", 0))],
        ["Reject Non-Essential", str(kpis.get("reject_count", 0))],
        ["Custom Preferences", str(kpis.get("custom_count", 0))],
    ]
    kpi_table = Table(kpi_data, colWidths=[3*inch, 2*inch])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d9488')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Categories
    story.append(Paragraph("Category Breakdown", heading_style))
    cats = stats.get("categories", {})
    cat_data = [
        ["Category", "Allowed"],
        ["Analytics", str(cats.get("analytics_allowed_count", 0))],
        ["Marketing", str(cats.get("marketing_allowed_count", 0))],
        ["Functional", str(cats.get("functional_allowed_count", 0))],
    ]
    cat_table = Table(cat_data, colWidths=[3*inch, 2*inch])
    cat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d9488')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    story.append(cat_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Recent logs
    story.append(Paragraph(f"Recent Consent Events (Top 50 of {total})", heading_style))
    log_data = [["Timestamp", "Action", "Marketing", "Analytics", "Session"]]
    for row in rows[:50]:
        prefs = row.get("preferences", {})
        log_data.append([
            row.get("created_at", "")[:19],
            row.get("action_taken", ""),
            "✓" if prefs.get("marketing") else "✗",
            "✓" if prefs.get("analytics") else "✗",
            (row.get("session_id") or "")[:12] + "...",
        ])
    
    log_table = Table(log_data, colWidths=[1.5*inch, 1.5*inch, 0.8*inch, 0.8*inch, 1.5*inch])
    log_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d9488')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (2, 0), (3, -1), 'CENTER'),
    ]))
    story.append(log_table)
    
    # Footer
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("Pleerity Enterprise Ltd - Cookie Consent Evidence Report", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    
    filename = f"consent_report_{from_dt.strftime('%Y%m%d')}_{to_dt.strftime('%Y%m%d')}.pdf"
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@admin_router.get("/client/{client_id}")
async def get_client_consent(
    client_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get consent state for a specific client (for admin profile view).
    """
    db = database.get_db()
    
    state = await db["consent_state"].find_one(
        {"client_id": client_id},
        {"_id": 0}
    )
    
    if not state:
        return {
            "exists": False,
            "outreach_eligible": False,
            "preferences": None,
        }
    
    return {
        "exists": True,
        "outreach_eligible": state.get("outreach_eligible", False),
        "preferences": state.get("preferences"),
        "action_taken": state.get("action_taken"),
        "consent_version": state.get("consent_version"),
        "updated_at": state.get("updated_at"),
    }


@admin_router.get("/lead/{lead_id}")
async def get_lead_consent(
    lead_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get consent state for a specific lead (from intake session).
    """
    db = database.get_db()
    
    # First find the lead to get session info
    lead = await db["leads"].find_one(
        {"lead_id": lead_id},
        {"_id": 0, "session_id": 1, "source_metadata": 1}
    )
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    session_id = lead.get("session_id") or lead.get("source_metadata", {}).get("session_id")
    
    if not session_id:
        return {
            "exists": False,
            "outreach_eligible": lead.get("marketing_consent", False),
            "preferences": None,
            "note": "No session tracking - using lead marketing_consent field",
        }
    
    state = await db["consent_state"].find_one(
        {"session_id": session_id},
        {"_id": 0}
    )
    
    if not state:
        return {
            "exists": False,
            "outreach_eligible": lead.get("marketing_consent", False),
            "preferences": None,
        }
    
    return {
        "exists": True,
        "outreach_eligible": state.get("outreach_eligible", False),
        "preferences": state.get("preferences"),
        "action_taken": state.get("action_taken"),
        "consent_version": state.get("consent_version"),
        "updated_at": state.get("updated_at"),
    }
