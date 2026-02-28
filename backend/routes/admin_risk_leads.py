"""
Admin: Risk Check leads – list, export CSV, resend report email.
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from database import database
from middleware import admin_route_guard
from typing import Optional
import csv
import io
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/risk-leads", tags=["admin-risk-leads"])

COLLECTION = "risk_leads"


@router.get("", dependencies=[Depends(admin_route_guard)])
async def list_risk_leads(
    current_user: dict = Depends(admin_route_guard),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    risk_band: Optional[str] = None,
    q: Optional[str] = None,
):
    """List risk_check leads with optional filters. Returns { items, total }."""
    db = database.get_db()
    filt = {}
    if risk_band:
        filt["risk_band"] = risk_band.strip().upper()
    if q and q.strip():
        s = q.strip()
        filt["$or"] = [
            {"email": {"$regex": s, "$options": "i"}},
            {"first_name": {"$regex": s, "$options": "i"}},
            {"lead_id": {"$regex": s, "$options": "i"}},
        ]
    total = await db[COLLECTION].count_documents(filt)
    cursor = db[COLLECTION].find(
        filt,
        {
            "_id": 0,
            "lead_id": 1,
            "created_at": 1,
            "first_name": 1,
            "email": 1,
            "property_count": 1,
            "risk_band": 1,
            "computed_score": 1,
            "recommended_plan_code": 1,
            "status": 1,
            "utm_source": 1,
        },
    ).sort("created_at", -1).skip(offset).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"items": items, "total": total}


@router.get("/export/csv", dependencies=[Depends(admin_route_guard)])
async def export_risk_leads_csv(
    current_user: dict = Depends(admin_route_guard),
    risk_band: Optional[str] = None,
):
    """Export risk leads as CSV."""
    db = database.get_db()
    filt = {}
    if risk_band:
        filt["risk_band"] = risk_band.strip().upper()
    cursor = db[COLLECTION].find(filt, {"_id": 0}).sort("created_at", -1)
    rows = await cursor.to_list(length=10000)

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Date", "Lead ID", "First Name", "Email", "Properties", "Risk Band", "Score", "Recommended Plan", "Status", "UTM Source"])
    for r in rows:
        w.writerow([
            r.get("created_at", ""),
            r.get("lead_id", ""),
            r.get("first_name", ""),
            r.get("email", ""),
            r.get("property_count", ""),
            r.get("risk_band", ""),
            r.get("computed_score", ""),
            r.get("recommended_plan_code", ""),
            r.get("status", ""),
            r.get("utm_source", ""),
        ])
    out.seek(0)
    return StreamingResponse(
        iter([out.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=risk_leads_export.csv"},
    )


@router.get("/{lead_id}/report", dependencies=[Depends(admin_route_guard)])
async def get_risk_lead_report(
    lead_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Return the full risk report payload for a lead (same shape as POST /api/risk-check/report). For admin view only."""
    from fastapi import HTTPException
    from services.risk_check_scoring import simulated_property_breakdown

    db = database.get_db()
    lead = await db[COLLECTION].find_one({"lead_id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Risk lead not found")

    score = lead.get("computed_score", 0)
    property_count = max(1, min(100, lead.get("property_count") or 1))
    gas_status = lead.get("gas_status") or "—"
    eicr_status = lead.get("eicr_status") or "—"
    tracking_method = lead.get("tracking_method") or "—"

    property_breakdown = simulated_property_breakdown(
        property_count, score, gas_status, eicr_status, tracking_method
    )

    return {
        "lead_id": lead.get("lead_id"),
        "score": score,
        "risk_band": lead.get("risk_band", "LOW"),
        "exposure_range_label": lead.get("exposure_range_label", ""),
        "flags": lead.get("flags", []),
        "disclaimer_text": lead.get("disclaimer_text", ""),
        "property_breakdown": property_breakdown,
        "recommended_plan_code": lead.get("recommended_plan_code", "PLAN_2_PORTFOLIO"),
    }


@router.post("/{lead_id}/resend-report", dependencies=[Depends(admin_route_guard)])
async def resend_risk_report(
    lead_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Re-send the Compliance Risk Snapshot email to the lead. Uses same template as initial report."""
    db = database.get_db()
    lead = await db[COLLECTION].find_one({"lead_id": lead_id}, {"_id": 0})
    if not lead:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Risk lead not found")

    from routes.risk_check import _send_risk_report_email
    ok = await _send_risk_report_email(lead)
    return {"ok": ok, "message": "Email sent" if ok else "Email not sent (check Postmark or duplicate)"}


@router.post("/{lead_id}/mark-converted", dependencies=[Depends(admin_route_guard)])
async def mark_risk_lead_converted(
    lead_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Set risk lead status to 'converted'. Idempotent."""
    db = database.get_db()
    result = await db[COLLECTION].update_one(
        {"lead_id": lead_id},
        {"$set": {"status": "converted"}},
    )
    if result.matched_count == 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Risk lead not found")
    return {"ok": True, "message": "Marked as converted"}
