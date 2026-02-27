"""Reporting Routes - Generate and download compliance reports."""
import asyncio
import csv
import io
import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from database import database
from middleware import client_route_guard, admin_route_guard
from models import AuditAction
from utils.audit import create_audit_log
from services.reporting_service import reporting_service
from services.pdf_report_builder import build_portfolio_report, build_property_report, build_score_explanation_report
from services.report_service import load_evidence_readiness_data
from services.compliance_score import calculate_compliance_score

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["reports"])


class ReportRequest(BaseModel):
    report_type: str  # compliance_summary, requirements, audit_logs
    format: str = "csv"  # csv or pdf
    property_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    actions: Optional[List[str]] = None


class GenerateReportRequest(BaseModel):
    """Evidence Readiness PDF: scope portfolio or single property."""
    scope: str  # "portfolio" | "property"
    property_id: Optional[str] = None


def _score_and_risk_from_report_data(report_data: dict) -> tuple:
    """Extract portfolio score and risk level for reports collection metadata."""
    properties = report_data.get("properties") or []
    scores = [p.get("compliance_score") for p in properties if p.get("compliance_score") is not None]
    score_at_time = round(sum(scores) / len(scores)) if scores else None
    risk_levels = [p.get("risk_level") for p in properties if p.get("risk_level")]
    risk_level_at_time = risk_levels[0] if risk_levels else None
    return score_at_time, risk_level_at_time


@router.post("/generate")
async def generate_evidence_readiness_report(request: Request, body: GenerateReportRequest):
    """
    Generate Evidence Readiness PDF report (deterministic template).
    Body: { scope: "portfolio" | "property", property_id?: string }.
    Returns application/pdf. Stores metadata in reports collection. Plan-gated by reports_pdf.
    """
    from services.plan_registry import plan_registry

    user = await client_route_guard(request)
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "reports_pdf")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "reports_pdf", "upgrade_required": True},
        )
    if body.scope == "property" and not body.property_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="property_id required when scope is property")
    try:
        report_data = await load_evidence_readiness_data(
            client_id=user["client_id"],
            scope=body.scope,
            property_id=body.property_id,
        )
        if body.scope == "portfolio":
            pdf_bytes = await asyncio.to_thread(build_portfolio_report, user["client_id"], report_data)
        else:
            pdf_bytes = await asyncio.to_thread(
                build_property_report, user["client_id"], body.property_id, report_data
            )
        score_at_time, risk_level_at_time = _score_and_risk_from_report_data(report_data)
        now = datetime.now(timezone.utc)
        db = database.get_db()
        doc = {
            "client_id": user["client_id"],
            "scope": body.scope,
            "property_id": body.property_id,
            "created_at": now,
            "score_at_time": score_at_time,
            "risk_level_at_time": risk_level_at_time,
            "storage_url": None,
        }
        ins = await db.reports.insert_one(doc)
        report_id = str(ins.inserted_id)
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user.get("portal_user_id"),
            client_id=user["client_id"],
            resource_type="report",
            metadata={
                "report_type": "evidence_readiness",
                "scope": body.scope,
                "property_id": body.property_id,
                "report_id": report_id,
            },
        )
        filename = f"evidence_readiness_{body.scope}_{now.strftime('%Y%m%d_%H%M')}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Evidence Readiness PDF error: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate report")


@router.get("")
@router.get("/list")
async def list_reports(request: Request):
    """List previous Evidence Readiness report runs for the client (metadata only)."""
    user = await client_route_guard(request)
    db = database.get_db()
    cursor = db.reports.find(
        {"client_id": user["client_id"]},
        {"_id": 1, "scope": 1, "property_id": 1, "created_at": 1, "score_at_time": 1, "risk_level_at_time": 1},
    ).sort("created_at", -1).limit(100)
    items = []
    async for row in cursor:
        items.append({
            "report_id": str(row["_id"]),
            "scope": row.get("scope"),
            "property_id": row.get("property_id"),
            "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
            "score_at_time": row.get("score_at_time"),
            "risk_level_at_time": row.get("risk_level_at_time"),
        })
    return {"reports": items}


@router.get("/score-drivers.csv")
async def get_score_drivers_csv(request: Request):
    """
    Export score drivers as CSV (portfolio scope).
    Columns: CRN, Property name, Postcode, Requirement, Status, Date used, Date confidence,
    Evidence uploaded, Next step label, Last updated.
    Plan-gated by reports_pdf (Portfolio and Professional only). Audit logged.
    """
    from services.plan_registry import plan_registry

    user = await client_route_guard(request)
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "reports_pdf")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "reports_pdf", "upgrade_required": True},
        )
    try:
        db = database.get_db()
        client = await db.clients.find_one(
            {"client_id": user["client_id"]},
            {"_id": 0, "customer_reference": 1},
        )
        crn = (client or {}).get("customer_reference") or user["client_id"]
        score_data = await calculate_compliance_score(user["client_id"])
        drivers = score_data.get("drivers") or []
        data_as_of = score_data.get("score_last_calculated_at") or datetime.now(timezone.utc).isoformat()
        if isinstance(data_as_of, datetime):
            data_as_of = data_as_of.isoformat()

        def _next_step_label(actions):
            if not actions:
                return "—"
            if "UPLOAD" in actions:
                return "Upload document"
            if "CONFIRM" in actions:
                return "Confirm details"
            if "VIEW" in actions:
                return "View requirement"
            return "—"

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "CRN", "Property name", "Postcode", "Requirement", "Status", "Date used",
            "Date confidence", "Evidence uploaded", "Next step label", "Last updated",
        ])
        for d in drivers:
            postcode = ""
            if score_data.get("property_breakdown"):
                for pb in score_data["property_breakdown"]:
                    if pb.get("property_id") == d.get("property_id"):
                        postcode = pb.get("postcode") or ""
                        break
            date_used = d.get("date_used")
            if date_used:
                try:
                    date_used = date_used[:10] if isinstance(date_used, str) else str(date_used)[:10]
                except Exception:
                    date_used = str(date_used) if date_used else "—"
            else:
                date_used = "—"
            writer.writerow([
                crn,
                (d.get("property_name") or d.get("property_id") or "—"),
                postcode,
                (d.get("requirement_name") or "—"),
                (d.get("status") or "—"),
                date_used,
                (d.get("date_confidence") or "UNKNOWN"),
                "Y" if d.get("evidence_uploaded") else "N",
                _next_step_label(d.get("actions") or []),
                data_as_of[:19] if isinstance(data_as_of, str) and len(data_as_of) > 19 else data_as_of,
            ])

        await create_audit_log(
            action=AuditAction.REPORT_EXPORTED,
            actor_id=user.get("portal_user_id"),
            client_id=user["client_id"],
            resource_type="report",
            metadata={"report_type": "score_drivers_csv", "scope": "portfolio"},
        )

        filename = f"score_drivers_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.csv"
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        logger.exception("Score drivers CSV error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate score drivers export",
        )


@router.get("/score-explanation.pdf")
async def get_score_explanation_pdf(
    request: Request,
    scope: str = "portfolio",
    property_id: Optional[str] = None,
):
    """
    Download Compliance Score Summary (Informational) PDF.
    Branded, audit-style report. Plan-gated by reports_pdf. Audit logged.
    """
    from services.plan_registry import plan_registry

    user = await client_route_guard(request)
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "reports_pdf")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "reports_pdf", "upgrade_required": True},
        )
    try:
        score_data = await calculate_compliance_score(user["client_id"])
        db = database.get_db()
        client = await db.clients.find_one(
            {"client_id": user["client_id"]},
            {"_id": 0, "full_name": 1, "company_name": 1, "customer_reference": 1},
        )
        client_doc = client or {}
        try:
            from services.professional_reports import professional_report_generator
            branding = await professional_report_generator.get_branding(user["client_id"])
        except Exception:
            branding = {
                "primary_color": "#0B1D3A",
                "secondary_color": "#00B8A9",
                "company_name": client_doc.get("company_name") or client_doc.get("full_name") or "Client",
            }

        pdf_bytes = await asyncio.to_thread(
            build_score_explanation_report,
            user["client_id"],
            score_data,
            client_doc,
            branding,
        )

        await create_audit_log(
            action=AuditAction.REPORT_EXPORTED,
            actor_id=user.get("portal_user_id"),
            client_id=user["client_id"],
            resource_type="report",
            metadata={
                "report_type": "score_explanation_pdf",
                "scope": scope,
                "property_id": property_id,
            },
        )

        filename = f"compliance_score_summary_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        logger.exception("Score explanation PDF error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate score explanation PDF",
        )


@router.get("/{report_id}/download")
async def download_report_by_id(request: Request, report_id: str):
    """Re-generate and download PDF for a previous report run (same scope/property_id, current data)."""
    from services.plan_registry import plan_registry

    user = await client_route_guard(request)
    allowed, _, _ = await plan_registry.enforce_feature(user["client_id"], "reports_pdf")
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Upgrade required for PDF reports")
    db = database.get_db()
    from bson import ObjectId
    try:
        oid = ObjectId(report_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    row = await db.reports.find_one({"_id": oid, "client_id": user["client_id"]})
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    scope = row.get("scope") or "portfolio"
    property_id = row.get("property_id")
    try:
        report_data = await load_evidence_readiness_data(
            client_id=user["client_id"], scope=scope, property_id=property_id
        )
        if scope == "portfolio":
            pdf_bytes = await asyncio.to_thread(build_portfolio_report, user["client_id"], report_data)
        else:
            pdf_bytes = await asyncio.to_thread(
                build_property_report, user["client_id"], property_id, report_data
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    created = row.get("created_at") or datetime.now(timezone.utc)
    filename = f"evidence_readiness_{scope}_{created.strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/compliance-summary")
async def get_compliance_summary_report(
    request: Request,
    format: str = "csv",
    include_details: bool = True
):
    """
    Generate compliance status summary report for the client.
    
    CSV: PORTFOLIO and PROFESSIONAL only (reports_csv).
    PDF: PORTFOLIO and PROFESSIONAL only (reports_pdf).
    """
    user = await client_route_guard(request)
    
    from services.plan_registry import plan_registry
    # Feature gating: PDF and CSV both require Portfolio+ per pricing page
    if format == "pdf":
        allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "reports_pdf")
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_details or {"message": error_msg, "feature": "reports_pdf", "upgrade_required": True}
            )
    if format == "csv":
        allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "reports_csv")
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_details or {"message": error_msg, "feature": "reports_csv", "upgrade_required": True}
            )
    
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
    CSV/PDF: PORTFOLIO and PROFESSIONAL only (reports_csv / reports_pdf) per pricing page.
    """
    user = await client_route_guard(request)
    
    from services.plan_registry import plan_registry
    if format == "pdf":
        allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "reports_pdf")
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_details or {"message": error_msg, "feature": "reports_pdf", "upgrade_required": True}
            )
    if format == "csv":
        allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "reports_csv")
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_details or {"message": error_msg, "feature": "reports_csv", "upgrade_required": True}
            )
    
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
    
    Note: Scheduled reports require Portfolio plan (PLAN_2_PORTFOLIO) or higher.
    """
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Plan gating: scheduled_reports (plan_registry)
        from services.plan_registry import plan_registry

        allowed, error_msg, error_details = await plan_registry.enforce_feature(
            user["client_id"],
            "scheduled_reports"
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": (error_details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
                    "message": error_msg,
                    "feature": "scheduled_reports",
                    "upgrade_required": True,
                    **(error_details or {})
                }
            )
        
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
        
        # Normalize recipients to a list (API may receive list or comma-separated string)
        if data.recipients:
            if isinstance(data.recipients, list):
                recipients = [str(r).strip() for r in data.recipients if str(r).strip()]
            else:
                recipients = [r.strip() for r in str(data.recipients).split(",") if r.strip()]
        else:
            recipients = []
        if not recipients:
            recipients = [client.get("email") or user.get("email") or ""]
            recipients = [r for r in recipients if r]
        
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
    """List all scheduled reports for the client. Gated: Portfolio+ (scheduled_reports)."""
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry

    allowed, error_msg, error_details = await plan_registry.enforce_feature(
        user["client_id"],
        "scheduled_reports"
    )
    if not allowed:
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user.get("portal_user_id"),
            client_id=user["client_id"],
            metadata={
                "action_type": "PLAN_GATE_DENIED",
                "feature_key": "scheduled_reports",
                "endpoint": "/api/reports/schedules",
                "method": "GET",
                "reason": error_msg,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "scheduled_reports", "upgrade_required": True}
        )
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
    """Delete a scheduled report. Gated: Portfolio+ (scheduled_reports)."""
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry

    allowed, error_msg, error_details = await plan_registry.enforce_feature(
        user["client_id"],
        "scheduled_reports"
    )
    if not allowed:
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user.get("portal_user_id"),
            client_id=user["client_id"],
            metadata={
                "action_type": "PLAN_GATE_DENIED",
                "feature_key": "scheduled_reports",
                "endpoint": f"/api/reports/schedules/{schedule_id}",
                "method": "DELETE",
                "reason": error_msg,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "scheduled_reports", "upgrade_required": True}
        )
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
    
    Plan gating: Requires Portfolio plan or higher (plan_registry reports_pdf).
    Uses client branding settings for white-label customization.
    """
    from services.plan_registry import plan_registry
    from services.professional_reports import professional_report_generator

    user = await client_route_guard(request)
    try:
        allowed, error_msg, error_details = await plan_registry.enforce_feature(
            user["client_id"],
            "reports_pdf"
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": (error_details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
                    "message": error_msg,
                    "feature": "reports_pdf",
                    "upgrade_required": True,
                    **(error_details or {})
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
    
    Plan gating: Requires Portfolio plan or higher (plan_registry reports_pdf).
    """
    from services.plan_registry import plan_registry
    from services.professional_reports import professional_report_generator

    user = await client_route_guard(request)
    try:
        allowed, error_msg, error_details = await plan_registry.enforce_feature(
            user["client_id"],
            "reports_pdf"
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": (error_details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
                    "message": error_msg,
                    "feature": "reports_pdf",
                    "upgrade_required": True,
                    **(error_details or {})
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
    
    Plan gating: Requires Professional plan (plan_registry audit_log_export).
    """
    from services.plan_registry import plan_registry
    from services.professional_reports import professional_report_generator

    user = await client_route_guard(request)
    try:
        # Canonical: audit_exports -> audit_log_export (plan_registry)
        allowed, error_msg, error_details = await plan_registry.enforce_feature(
            user["client_id"],
            "audit_log_export"
        )
        if not allowed:
            detail = {
                "error_code": (error_details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
                "message": error_msg,
                "upgrade_required": True,
                **(error_details or {}),
            }
            detail["feature"] = "audit_exports"  # preserve response shape
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

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
