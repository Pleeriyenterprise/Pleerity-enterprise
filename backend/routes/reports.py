"""Reporting Routes - Generate and download compliance reports."""
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from database import database
from middleware import client_route_guard, admin_route_guard
from models import AuditAction
from utils.audit import create_audit_log
from services.reporting_service import reporting_service
from typing import Optional, List
from pydantic import BaseModel
import io
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["reports"])


class ReportRequest(BaseModel):
    report_type: str  # compliance_summary, requirements, audit_logs
    format: str = "csv"  # csv or pdf
    property_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    actions: Optional[List[str]] = None


@router.get("/compliance-summary")
async def get_compliance_summary_report(
    request: Request,
    format: str = "csv",
    include_details: bool = True
):
    """
    Generate compliance status summary report for the client.
    
    Formats: csv, pdf (pdf returns JSON data for client-side rendering)
    """
    user = await client_route_guard(request)
    
    try:
        result = await reporting_service.generate_compliance_summary_report(
            client_id=user["client_id"],
            format=format,
            include_details=include_details
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="report",
            metadata={
                "report_type": "compliance_summary",
                "format": format
            }
        )
        
        if format == "csv":
            # Return as downloadable file
            return StreamingResponse(
                io.StringIO(result["content"]),
                media_type=result["content_type"],
                headers={
                    "Content-Disposition": f"attachment; filename={result['filename']}"
                }
            )
        else:
            # Return JSON for client-side PDF generation
            return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Compliance summary report error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report"
        )


@router.get("/requirements")
async def get_requirements_report(
    request: Request,
    format: str = "csv",
    property_id: Optional[str] = None
):
    """
    Generate detailed requirements report for the client.
    
    Optionally filter by property_id.
    Formats: csv, pdf
    """
    user = await client_route_guard(request)
    
    try:
        result = await reporting_service.generate_requirements_report(
            client_id=user["client_id"],
            property_id=property_id,
            format=format
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="report",
            metadata={
                "report_type": "requirements",
                "format": format,
                "property_id": property_id
            }
        )
        
        if format == "csv":
            return StreamingResponse(
                io.StringIO(result["content"]),
                media_type=result["content_type"],
                headers={
                    "Content-Disposition": f"attachment; filename={result['filename']}"
                }
            )
        else:
            return result
    
    except Exception as e:
        logger.error(f"Requirements report error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report"
        )


@router.get("/audit-logs")
async def get_audit_logs_report(
    request: Request,
    format: str = "csv",
    client_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    actions: Optional[str] = None,  # Comma-separated
    limit: int = 1000
):
    """
    Generate audit log extract report (Admin only).
    
    Filters:
    - client_id: Filter by specific client
    - start_date: ISO date string (inclusive)
    - end_date: ISO date string (inclusive)
    - actions: Comma-separated list of action types
    - limit: Max records (default 1000)
    
    Formats: csv, pdf
    """
    user = await admin_route_guard(request)
    
    try:
        # Parse actions if provided
        action_list = actions.split(",") if actions else None
        
        result = await reporting_service.generate_audit_log_report(
            client_id=client_id,
            start_date=start_date,
            end_date=end_date,
            actions=action_list,
            format=format,
            limit=limit
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            resource_type="report",
            metadata={
                "report_type": "audit_logs",
                "format": format,
                "filters": {
                    "client_id": client_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "actions": action_list
                }
            }
        )
        
        if format == "csv":
            return StreamingResponse(
                io.StringIO(result["content"]),
                media_type=result["content_type"],
                headers={
                    "Content-Disposition": f"attachment; filename={result['filename']}"
                }
            )
        else:
            return result
    
    except Exception as e:
        logger.error(f"Audit logs report error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report"
        )


@router.get("/available")
async def get_available_reports(request: Request):
    """Get list of available reports for the user."""
    user = await client_route_guard(request)
    
    reports = [
        {
            "id": "compliance_summary",
            "name": "Compliance Status Summary",
            "description": "Overview of property compliance including statistics and breakdown",
            "formats": ["csv", "pdf"],
            "endpoint": "/reports/compliance-summary"
        },
        {
            "id": "requirements",
            "name": "Requirements Report",
            "description": "Detailed list of all requirements with status and due dates",
            "formats": ["csv", "pdf"],
            "endpoint": "/reports/requirements"
        }
    ]
    
    # Add audit logs report for admins
    if user.get("role") == "ROLE_ADMIN":
        reports.append({
            "id": "audit_logs",
            "name": "Audit Log Extract",
            "description": "System audit trail with filters (Admin only)",
            "formats": ["csv", "pdf"],
            "endpoint": "/reports/audit-logs"
        })
    
    return {
        "reports": reports,
        "user_role": user.get("role")
    }



# ============================================================================
# Scheduled Reports API
# ============================================================================

class CreateScheduleRequest(BaseModel):
    report_type: str  # compliance_summary, requirements
    frequency: str  # daily, weekly, monthly
    recipients: Optional[List[str]] = None
    include_details: bool = True


@router.post("/schedules")
async def create_report_schedule(request: Request, data: CreateScheduleRequest):
    """Create a scheduled report for automatic email delivery.
    
    Schedules:
    - daily: Sent every day at 8 AM
    - weekly: Sent every Monday at 8 AM
    - monthly: Sent on the 1st of each month
    """
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        from datetime import datetime, timezone, timedelta
        import uuid
        
        # Validate report type
        if data.report_type not in ["compliance_summary", "requirements"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid report type"
            )
        
        # Validate frequency
        if data.frequency not in ["daily", "weekly", "monthly"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid frequency. Must be: daily, weekly, or monthly"
            )
        
        # Get client info for default recipient
        client = await db.clients.find_one(
            {"client_id": user["client_id"]},
            {"_id": 0}
        )
        
        # Default recipients to client email if not provided
        recipients = data.recipients if data.recipients else [client.get("email", user.get("email"))]
        
        # Calculate next scheduled time
        now = datetime.now(timezone.utc)
        if data.frequency == "daily":
            next_scheduled = now + timedelta(days=1)
        elif data.frequency == "weekly":
            next_scheduled = now + timedelta(weeks=1)
        else:  # monthly
            next_scheduled = now + timedelta(days=30)
        
        # Create schedule
        schedule = {
            "schedule_id": str(uuid.uuid4()),
            "client_id": user["client_id"],
            "report_type": data.report_type,
            "frequency": data.frequency,
            "recipients": recipients,
            "include_details": data.include_details,
            "is_active": True,
            "last_sent": None,
            "next_scheduled": next_scheduled.isoformat(),
            "created_at": now.isoformat(),
            "created_by": user["portal_user_id"]
        }
        
        await db.report_schedules.insert_one(schedule)
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="report_schedule",
            resource_id=schedule["schedule_id"],
            metadata={
                "action": "schedule_created",
                "report_type": data.report_type,
                "frequency": data.frequency
            }
        )
        
        return {
            "message": "Report schedule created",
            "schedule_id": schedule["schedule_id"],
            "next_scheduled": schedule["next_scheduled"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create schedule error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create schedule"
        )


@router.get("/schedules")
async def list_report_schedules(request: Request):
    """List all scheduled reports for the client."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        schedules = await db.report_schedules.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(100)
        
        return {"schedules": schedules}
    
    except Exception as e:
        logger.error(f"List schedules error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list schedules"
        )


@router.delete("/schedules/{schedule_id}")
async def delete_report_schedule(request: Request, schedule_id: str):
    """Delete a scheduled report."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Verify ownership
        schedule = await db.report_schedules.find_one(
            {"schedule_id": schedule_id, "client_id": user["client_id"]}
        )
        
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule not found"
            )
        
        await db.report_schedules.delete_one({"schedule_id": schedule_id})
        
        return {"message": "Schedule deleted"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete schedule error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete schedule"
        )


@router.patch("/schedules/{schedule_id}/toggle")
async def toggle_report_schedule(request: Request, schedule_id: str):
    """Toggle a scheduled report on/off."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Verify ownership
        schedule = await db.report_schedules.find_one(
            {"schedule_id": schedule_id, "client_id": user["client_id"]}
        )
        
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule not found"
            )
        
        new_status = not schedule.get("is_active", True)
        
        await db.report_schedules.update_one(
            {"schedule_id": schedule_id},
            {"$set": {"is_active": new_status}}
        )
        
        return {
            "message": f"Schedule {'enabled' if new_status else 'disabled'}",
            "is_active": new_status
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Toggle schedule error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle schedule"
        )


# ============================================================================
# Professional PDF Reports (Plan Gated)
# ============================================================================

@router.get("/professional/compliance-summary")
async def download_compliance_summary_pdf(request: Request):
    """Download professionally formatted compliance summary PDF.
    
    Plan gating: Requires Growth plan (PLAN_2_5) or higher.
    Uses client branding settings for white-label customization.
    """
    from services.feature_entitlement import feature_entitlement_service
    from services.professional_reports import professional_report_generator
    
    user = await client_route_guard(request)
    
    try:
        # Enforce feature access
        allowed, error_msg, error_details = await feature_entitlement_service.enforce_feature(
            user["client_id"],
            "reports_pdf"
        )
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": error_details.get("error_code", "PLAN_NOT_ELIGIBLE"),
                    "message": error_msg,
                    "feature": "reports_pdf",
                    "upgrade_required": True
                }
            )
        
        # Generate PDF
        pdf_buffer = await professional_report_generator.generate_compliance_summary_pdf(
            client_id=user["client_id"],
            include_details=True
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="report",
            metadata={
                "report_type": "professional_compliance_summary",
                "format": "pdf"
            }
        )
        
        filename = f"compliance_summary_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Professional compliance summary PDF error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report"
        )


@router.get("/professional/expiry-schedule")
async def download_expiry_schedule_pdf(
    request: Request,
    days: int = 90
):
    """Download professionally formatted expiry schedule PDF.
    
    Plan gating: Requires Growth plan (PLAN_2_5) or higher.
    """
    from services.feature_entitlement import feature_entitlement_service
    from services.professional_reports import professional_report_generator
    
    user = await client_route_guard(request)
    
    try:
        # Enforce feature access
        allowed, error_msg, error_details = await feature_entitlement_service.enforce_feature(
            user["client_id"],
            "reports_pdf"
        )
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": error_details.get("error_code", "PLAN_NOT_ELIGIBLE"),
                    "message": error_msg,
                    "feature": "reports_pdf",
                    "upgrade_required": True
                }
            )
        
        # Limit days
        days = min(days, 365)
        
        # Generate PDF
        pdf_buffer = await professional_report_generator.generate_expiry_schedule_pdf(
            client_id=user["client_id"],
            days=days
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="report",
            metadata={
                "report_type": "professional_expiry_schedule",
                "format": "pdf",
                "days": days
            }
        )
        
        filename = f"expiry_schedule_{days}days_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Professional expiry schedule PDF error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report"
        )


@router.get("/professional/audit-log")
async def download_audit_log_pdf(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    actions: Optional[str] = None
):
    """Download professionally formatted audit log PDF.
    
    Plan gating: Requires Portfolio plan (PLAN_6_15) or higher.
    """
    from services.feature_entitlement import feature_entitlement_service
    from services.professional_reports import professional_report_generator
    
    user = await client_route_guard(request)
    
    try:
        # Enforce feature access
        allowed, error_msg, error_details = await feature_entitlement_service.enforce_feature(
            user["client_id"],
            "audit_exports"
        )
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": error_details.get("error_code", "PLAN_NOT_ELIGIBLE"),
                    "message": error_msg,
                    "feature": "audit_exports",
                    "upgrade_required": True
                }
            )
        
        # Parse actions filter
        action_list = actions.split(",") if actions else None
        
        # Generate PDF
        pdf_buffer = await professional_report_generator.generate_audit_log_pdf(
            client_id=user["client_id"],
            start_date=start_date,
            end_date=end_date,
            actions=action_list
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="report",
            metadata={
                "report_type": "professional_audit_log",
                "format": "pdf",
                "filters": {"start_date": start_date, "end_date": end_date}
            }
        )
        
        filename = f"audit_log_{datetime.now().strftime('%Y%m%d')}.pdf"
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Professional audit log PDF error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report"
        )
