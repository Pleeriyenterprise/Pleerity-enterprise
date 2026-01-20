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
            "endpoint": "/api/reports/compliance-summary"
        },
        {
            "id": "requirements",
            "name": "Requirements Report",
            "description": "Detailed list of all requirements with status and due dates",
            "formats": ["csv", "pdf"],
            "endpoint": "/api/reports/requirements"
        }
    ]
    
    # Add audit logs report for admins
    if user.get("role") == "ROLE_ADMIN":
        reports.append({
            "id": "audit_logs",
            "name": "Audit Log Extract",
            "description": "System audit trail with filters (Admin only)",
            "formats": ["csv", "pdf"],
            "endpoint": "/api/reports/audit-logs"
        })
    
    return {
        "reports": reports,
        "user_role": user.get("role")
    }
