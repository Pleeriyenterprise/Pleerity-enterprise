from fastapi import APIRouter, HTTPException, Request, Depends, status, File, UploadFile, Query, Body, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from database import database
from middleware import client_route_guard
from services.compliance_score import calculate_compliance_score
from services.scoring_semantics_v1 import SCORE_AUTHORITY_UNAVAILABLE, SCORE_STATUS_UNAVAILABLE
from services.compliance_scoring_service import get_authoritative_property_compliance_for_client
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import asyncio
from pathlib import Path
import logging
import io
import os
import uuid

from utils.api_errors import log_api_error, structured_error
from utils.storage_paths import resolve_data_dir

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/client", tags=["client"], dependencies=[Depends(client_route_guard)])

# Controlled reason list for "Mark as not applicable" (must match properties.PATCH requirement)
NOT_REQUIRED_REASONS = ["no_gas_supply", "exempt", "not_applicable", "other"]


async def _resolved_jurisdiction_settings_for_client(db, client_id: str) -> Dict[str, Any]:
    """
    Return default_jurisdiction + enabled_jurisdictions for Settings UI.

    Order: persisted ``clients`` fields; else union of ``properties.jurisdiction`` (intake / explicit records).
    Last resort only (no properties, no stored row): Scotland singleton — never all four regions unless stored.
    """
    from services.compliance_rules_registry import (
        canonicalize_uk_portfolio_label,
        derive_account_jurisdiction_fields_from_property_labels,
    )

    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "default_jurisdiction": 1, "enabled_jurisdictions": 1},
    ) or {}
    stored_def = canonicalize_uk_portfolio_label(client.get("default_jurisdiction"))
    raw_en = client.get("enabled_jurisdictions")
    stored_en = [canonicalize_uk_portfolio_label(x) for x in (raw_en or []) if canonicalize_uk_portfolio_label(x)]
    if stored_def and stored_en:
        return {"default_jurisdiction": stored_def, "enabled_jurisdictions": stored_en}
    rows = await db.properties.find({"client_id": client_id}, {"_id": 0, "jurisdiction": 1}).to_list(10000)
    dd, dlist = derive_account_jurisdiction_fields_from_property_labels([p.get("jurisdiction") for p in rows])
    if dd and dlist:
        return {"default_jurisdiction": dd, "enabled_jurisdictions": dlist}
    return {"default_jurisdiction": "Scotland", "enabled_jurisdictions": ["Scotland"]}


def _compute_property_compliance_status(requirements: List[Dict[str, Any]]) -> str:
    """Compute property-level compliance status from **projected** portal-visible requirement rows.

    Uses the same effective status semantics as ``calculate_compliance_score`` (authority, else legacy
    ``status``). OVERDUE/EXPIRED → RED; EXPIRING_SOON or PENDING with due within 30 days → AMBER;
    PENDING without near-term due → AMBER (missing evidence attention); else GREEN.
    Calendar-overdue while still ``PENDING`` is not treated as RED here so property cards match
    score/header overdue counts (single source of truth).
    """
    if not requirements:
        return "GREEN"
    now = datetime.now(timezone.utc)
    has_overdue = False
    has_expiring_soon = False
    has_pending = False
    for req in requirements:
        status = (req.get("status") or "PENDING").strip().upper()
        if status in ("OVERDUE", "EXPIRED"):
            has_overdue = True
        elif status == "EXPIRING_SOON":
            has_expiring_soon = True
        elif status == "PENDING":
            has_pending = True
            due_date_str = req.get("due_date")
            if due_date_str:
                try:
                    due_date = datetime.fromisoformat(due_date_str.replace("Z", "+00:00")) if isinstance(due_date_str, str) else due_date_str
                    if due_date.tzinfo is None:
                        due_date = due_date.replace(tzinfo=timezone.utc)
                    days_until_due = (due_date - now).days
                    if days_until_due <= 30:
                        has_expiring_soon = True
                except Exception:
                    pass
    if has_overdue:
        return "RED"
    if has_expiring_soon or has_pending:
        return "AMBER"
    return "GREEN"

@router.get("/compliance-score")
async def get_compliance_score(request: Request):
    """Get the client's overall compliance score. Headline ``score`` is the persisted portfolio aggregate; optional ``catalog_portfolio_view`` is a non-authoritative matrix preview."""
    user = await client_route_guard(request)
    client_id = user["client_id"]

    try:
        score_data = await calculate_compliance_score(client_id)
        return score_data
    except Exception as e:
        logger.error(f"Compliance score error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate compliance score"
        )


@router.get("/properties/{property_id}/compliance-score/explanation")
async def get_property_compliance_score_explanation(request: Request, property_id: str):
    """
    Property-level compliance explainability payload for v2 scoring.
    Returns score, jurisdiction, bucket breakdown, requirement breakdown, deficits, and next actions.
    """
    user = await client_route_guard(request)
    db = database.get_db()

    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0, "property_id": 1, "client_id": 1},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    try:
        data = await get_authoritative_property_compliance_for_client(property_id, user["client_id"])
        if data.get("error") == "property_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Property compliance explainability error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load property compliance explainability",
        )


@router.get("/compliance-score/trend")
async def get_compliance_score_trend(
    request: Request,
    days: int = 30,
    include_breakdown: bool = False
):
    """Get compliance score trend data for trend visualization.
    
    Returns sparkline data and change analysis for the dashboard.
    
    Args:
        days: Number of days of history (default 30, max 90)
        include_breakdown: Include detailed breakdown per day
    """
    user = await client_route_guard(request)
    
    try:
        from services.compliance_trending import get_score_trend
        
        # Cap at 90 days
        days = min(days, 90)
        
        trend_data = await get_score_trend(
            client_id=user["client_id"],
            days=days,
            include_breakdown=include_breakdown
        )
        return trend_data
    except Exception as e:
        logger.error(f"Compliance score trend error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get compliance score trend"
        )


@router.get("/score/timeline")
async def get_score_timeline(
    request: Request,
    days: int = 90,
    interval: str = "week",
):
    """Score trend (90 days): points from SCORE_RECALCULATED events, latest per bucket. Fallback: current score flat line."""
    user = await client_route_guard(request)
    try:
        from services.score_events_service import get_timeline
        days = min(max(1, days), 90)
        data = await get_timeline(client_id=user["client_id"], days=days, interval=interval)
        return data
    except Exception as e:
        logger.error(f"Score timeline error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get score timeline"
        )


@router.get("/score-trend/portfolio")
async def get_score_trend_portfolio(
    request: Request,
    days: int = 90,
):
    """Portfolio score trend for last N days (daily snapshots) with summary stats for Score Trend card."""
    user = await client_route_guard(request)
    try:
        from services.compliance_trending import get_portfolio_trend_with_summary
        days = min(max(1, days), 90)
        data = await get_portfolio_trend_with_summary(client_id=user["client_id"], days=days)
        return data
    except Exception as e:
        logger.error(f"Score trend portfolio error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get portfolio score trend"
        )


@router.get("/score-trend/property/{property_id}")
async def get_score_trend_property(
    request: Request,
    property_id: str,
    days: int = 90,
):
    """Property score trend for last N days (daily snapshots) with summary stats. Property must belong to client."""
    user = await client_route_guard(request)
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0, "property_id": 1},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    try:
        from services.compliance_trending import get_property_trend_with_summary
        days = min(max(1, days), 90)
        data = await get_property_trend_with_summary(
            client_id=user["client_id"],
            property_id=property_id,
            days=days,
        )
        return data
    except Exception as e:
        logger.error(f"Score trend property error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get property score trend"
        )


@router.get("/score/changes")
async def get_score_changes(
    request: Request,
    limit: int = 20,
):
    """What Changed: recent score-affecting events with title, details, delta, deep-link ids."""
    user = await client_route_guard(request)
    try:
        from services.score_events_service import get_changes
        data = await get_changes(client_id=user["client_id"], limit=min(max(1, limit), 100))
        return data
    except Exception as e:
        logger.error(f"Score changes error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get score changes"
        )


@router.get("/compliance/activity")
async def get_compliance_activity(
    request: Request,
    property_id: Optional[str] = None,
    limit: int = 50,
):
    """Action -> Outcome activity timeline for client-visible UX feedback."""
    user = await client_route_guard(request)
    try:
        from services.compliance_outcome_engine import list_activity
        return await list_activity(
            client_id=user["client_id"],
            property_id=property_id,
            limit=min(max(1, limit), 200),
        )
    except Exception as e:
        logger.error(f"Compliance activity error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get compliance activity"
        )


@router.get("/ledger")
async def get_ledger(
    request: Request,
    property_id: Optional[str] = None,
    trigger_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 50,
    cursor: Optional[str] = None,
):
    """Score ledger: paginated list of score change events (before/after, delta, trigger, drivers)."""
    user = await client_route_guard(request)
    try:
        from services.score_ledger_service import list_ledger
        data = await list_ledger(
            client_id=user["client_id"],
            property_id=property_id,
            trigger_type=trigger_type,
            from_date=from_date,
            to_date=to_date,
            limit=min(max(1, limit), 200),
            cursor=cursor,
        )
        return data
    except Exception as e:
        logger.error(f"Ledger error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load score ledger"
        )


@router.get("/ledger/export.csv")
async def export_ledger_csv(
    request: Request,
    property_id: Optional[str] = None,
    trigger_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
):
    """Export score ledger as CSV (current filters; max 5000 rows)."""
    user = await client_route_guard(request)
    try:
        from services.score_ledger_service import list_ledger_export
        import csv as csv_module
        items = await list_ledger_export(
            client_id=user["client_id"],
            property_id=property_id,
            trigger_type=trigger_type,
            from_date=from_date,
            to_date=to_date,
            limit=5000,
        )
        out = io.StringIO()
        w = csv_module.writer(out)
        w.writerow([
            "created_at", "property_id", "trigger_type", "trigger_label", "actor_type",
            "before_score", "after_score", "delta", "before_grade", "after_grade",
            "drivers_before_status", "drivers_before_timeline", "drivers_before_documents", "drivers_before_overdue_penalty",
            "drivers_after_status", "drivers_after_timeline", "drivers_after_documents", "drivers_after_overdue_penalty",
            "rule_version",
        ])
        for r in items:
            db = r.get("drivers_before") or {}
            da = r.get("drivers_after") or {}
            w.writerow([
                r.get("created_at", ""),
                r.get("property_id", ""),
                r.get("trigger_type", ""),
                r.get("trigger_label", ""),
                r.get("actor_type", ""),
                r.get("before_score", ""),
                r.get("after_score", ""),
                r.get("delta", ""),
                r.get("before_grade", ""),
                r.get("after_grade", ""),
                db.get("status"), db.get("timeline"), db.get("documents"), db.get("overdue_penalty"),
                da.get("status"), da.get("timeline"), da.get("documents"), da.get("overdue_penalty"),
                r.get("rule_version", ""),
            ])
        out.seek(0)
        return StreamingResponse(
            iter([out.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=score_ledger_export.csv"},
        )
    except Exception as e:
        logger.error(f"Ledger export error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export score ledger"
        )


@router.get("/score-trend/portfolio")
async def get_score_trend_portfolio(request: Request, days: int = 90):
    """Portfolio score trend for last N days (snapshot-based). Returns points + summary stats for Score Trend card."""
    user = await client_route_guard(request)
    try:
        from services.compliance_trending import get_portfolio_trend_with_summary
        days = min(max(1, days), 90)
        data = await get_portfolio_trend_with_summary(user["client_id"], days=days)
        return data
    except Exception as e:
        logger.error(f"Score trend portfolio error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get portfolio score trend"
        )


@router.get("/score-trend/property/{property_id}")
async def get_score_trend_property(request: Request, property_id: str, days: int = 90):
    """Property score trend for last N days (snapshot-based). Returns points + summary stats. Property must belong to client."""
    user = await client_route_guard(request)
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0, "property_id": 1},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    try:
        from services.compliance_trending import get_property_trend_with_summary
        days = min(max(1, days), 90)
        data = await get_property_trend_with_summary(user["client_id"], property_id, days=days)
        return data
    except Exception as e:
        logger.error(f"Score trend property error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get property score trend"
        )


@router.get("/compliance-score/explanation")
async def get_compliance_score_explanation(
    request: Request,
    compare_days: int = 7,
    property_id: Optional[str] = None
):
    """Get explanation of compliance score: per-property (stored breakdown) or client-level trend.
    
    If property_id is set: returns stored score, breakdown summary, and key reasons for that property
    (no recompute; reads Property.compliance_score / compliance_breakdown).
    If property_id is omitted: compares client score to N days ago (trend explanation).
    
    Args:
        compare_days: Days back to compare for client-level trend (default 7, max 30)
        property_id: Optional; when set, return property-level explanation from stored data
    """
    user = await client_route_guard(request)
    
    try:
        if property_id:
            db = database.get_db()
            prop = await db.properties.find_one(
                {"property_id": property_id, "client_id": user["client_id"]},
                {"_id": 0, "property_id": 1, "compliance_score": 1, "compliance_breakdown": 1, "compliance_last_calculated_at": 1}
            )
            if not prop:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
            score = prop.get("compliance_score")
            breakdown = prop.get("compliance_breakdown") or {}
            reasons = []
            if breakdown.get("status_score") is not None and breakdown.get("status_score") < 100:
                reasons.append("Some requirements are not yet compliant (status score {:.0f}%)".format(breakdown["status_score"]))
            if breakdown.get("expiry_score") is not None and breakdown.get("expiry_score") < 100:
                reasons.append("Upcoming or past expiries affecting score (expiry score {:.0f}%)".format(breakdown["expiry_score"]))
            if breakdown.get("document_score") is not None and breakdown.get("document_score") < 100:
                reasons.append("Document coverage below 100% (document score {:.0f}%)".format(breakdown["document_score"]))
            if breakdown.get("overdue_penalty_score") is not None and breakdown.get("overdue_penalty_score") < 100:
                reasons.append("Overdue items are reducing the score")
            return {
                "property_id": property_id,
                "score": score,
                "breakdown_summary": breakdown,
                "compliance_last_calculated_at": prop.get("compliance_last_calculated_at"),
                "key_reasons": reasons if reasons else ["Score is based on stored compliance breakdown for this property."],
            }
        from services.compliance_trending import get_score_change_explanation
        compare_days = min(compare_days, 30)
        explanation = await get_score_change_explanation(
            client_id=user["client_id"],
            compare_days=compare_days
        )
        return explanation
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Compliance score explanation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get compliance score explanation"
        )


@router.post("/compliance-score/snapshot")
async def trigger_compliance_snapshot(request: Request):
    """Manually trigger a compliance score snapshot (for testing/admin).
    
    Creates an immediate snapshot of the current compliance score.
    Useful for manual updates or debugging.
    """
    user = await client_route_guard(request)
    
    try:
        from services.compliance_trending import capture_daily_snapshot
        
        result = await capture_daily_snapshot(user["client_id"])
        return result
    except Exception as e:
        logger.error(f"Compliance snapshot trigger error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to capture compliance snapshot"
        )

@router.get("/dashboard")
async def get_dashboard(request: Request):
    """Get client dashboard data."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one({"client_id": user["client_id"]}, {"_id": 0})
        
        # Get properties
        properties = await db.properties.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(100)
        
        # Get requirements summary
        requirements = await db.requirements.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(1000)
        from services.requirement_client_runtime_surface import (
            filter_requirement_rows_for_client_runtime_surfaces,
            client_portal_surface_visible_row,
            project_requirement_row_client_runtime,
        )

        requirements = await filter_requirement_rows_for_client_runtime_surfaces(
            db,
            client_id=user["client_id"],
            requirements=requirements,
            client_doc=client or {},
            properties=properties,
        )
        projected = [project_requirement_row_client_runtime(r) for r in requirements]
        visible_reqs = [r for r in projected if client_portal_surface_visible_row(r)]

        # Calculate compliance summary (portal-visible rows only; aligns with /client/compliance-score stats)
        total_requirements = len(visible_reqs)
        compliant = sum(1 for r in visible_reqs if (r.get("status") or "") == "COMPLIANT")
        overdue = sum(1 for r in visible_reqs if (r.get("status") or "") in ("OVERDUE", "EXPIRED"))
        expiring = sum(1 for r in visible_reqs if (r.get("status") or "") == "EXPIRING_SOON")

        # Group requirements by property so Properties page status matches Compliance Score
        reqs_by_property = {}
        for r in visible_reqs:
            pid = r.get("property_id")
            if pid:
                reqs_by_property.setdefault(pid, []).append(r)
        from services.compliance_rules_registry import (
            jurisdiction_attribution_for_property,
            property_jurisdiction_requirement_flags,
        )

        client_doc = client or {}
        # Override each property's compliance_status with live-computed value (RED/AMBER/GREEN)
        properties_out = []
        for prop in properties:
            p = dict(prop)
            p["compliance_status"] = _compute_property_compliance_status(
                reqs_by_property.get(p.get("property_id"), [])
            )
            att = jurisdiction_attribution_for_property(p, client_doc)
            p["compliance_basis"] = att["compliance_basis"]
            p["effective_jurisdiction_label"] = att["effective_jurisdiction_label"]
            p["jurisdiction_source"] = att["jurisdiction_source"]
            p.update(property_jurisdiction_requirement_flags(p))
            properties_out.append(p)
        
        # Onboarding checklist (server-driven; for banner and deep-links)
        from services.onboarding_checklist_service import get_checklist_for_client
        checklist = await get_checklist_for_client(user["client_id"])
        if checklist.get("error"):
            checklist = {"items": [], "completed_at": None, "all_required_complete": False}

        compliance_score_headline = None
        try:
            cs = await calculate_compliance_score(user["client_id"])
            compliance_score_headline = {
                "score": cs.get("score"),
                "grade": cs.get("grade"),
                "color": cs.get("color"),
                "message": cs.get("message"),
                "score_authority": cs.get("score_authority"),
                "score_status": cs.get("score_status"),
                "last_calculated_at": cs.get("last_calculated_at") or cs.get("portfolio_last_calculated_at"),
                "score_coverage": cs.get("score_coverage"),
                "score_status_message": cs.get("score_status_message"),
                "scoring_semantics_version": cs.get("scoring_semantics_version"),
                "properties_count": cs.get("properties_count"),
            }
        except Exception as headline_err:
            logger.warning("dashboard compliance headline unavailable: %s", headline_err)
            compliance_score_headline = {
                "score": None,
                "grade": None,
                "color": "gray",
                "message": "Compliance score summary unavailable.",
                "score_authority": SCORE_AUTHORITY_UNAVAILABLE,
                "score_status": SCORE_STATUS_UNAVAILABLE,
                "last_calculated_at": None,
                "score_coverage": None,
                "score_status_message": None,
                "scoring_semantics_version": None,
                "properties_count": None,
            }

        return {
            "client": client,
            "properties": properties_out,
            "compliance_summary": {
                "total_requirements": total_requirements,
                "compliant": compliant,
                "overdue": overdue,
                "expiring_soon": expiring
            },
            "onboarding_checklist": checklist,
            "compliance_score_headline": compliance_score_headline,
        }
    
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load dashboard"
        )


@router.get("/dashboard/roi-summary")
async def get_dashboard_roi_summary(request: Request):
    """
    Month-to-date ROI-style metrics (v1 approximations). Separate from /dashboard so the main
    dashboard load stays fast; clients may fetch this after first paint.
    """
    user = await client_route_guard(request)
    db = database.get_db()
    try:
        from services.client_roi_summary_service import get_roi_summary_month_to_date

        return await get_roi_summary_month_to_date(user["client_id"], db)
    except Exception:
        # Full failure (e.g. import error): still return a safe payload for the UI, but never silently —
        # ops and log aggregators need the stack trace.
        logger.exception(
            "ROI summary endpoint failed client_id=%s",
            user.get("client_id"),
        )
        return {
            "period_label": "This month",
            "compliance_items_up_to_date": 0,
            "compliance_basis": "portfolio_snapshot",
            "jobs_completed_on_time": 0,
            "jobs_completed_in_period": 0,
            "sla_breaches_avoided": 0,
            "approximate": True,
            "unavailable": True,
            "diagnostics": {
                "requirements_scan_ok": False,
                "work_orders_scan_ok": False,
                "endpoint_error": True,
            },
        }


@router.get("/priority-actions")
async def get_client_priority_actions(
    request: Request,
    property_id: Optional[str] = Query(None, description="Filter by property"),
    limit: int = Query(20, ge=1, le=50),
):
    """Compatibility endpoint: routes through command center urgent actions only."""
    user = await client_route_guard(request)
    try:
        from services.command_center_service import get_command_center_bundle
        from services.ops_compliance_feature_flags import get_effective_flags, PREDICTIVE_MAINTENANCE

        flags = await get_effective_flags(
            client_id=user["client_id"],
        )
        result = await get_command_center_bundle(
            client_id=user["client_id"],
            property_id_filter=property_id,
            predictive_enabled=bool(flags.get(PREDICTIVE_MAINTENANCE)),
            portal_user_id=user.get("portal_user_id"),
        )
        actions = (result.get("urgent_actions") or [])[:limit]
        return {"actions": actions, "total": len(actions), "source": "command_center"}
    except Exception as e:
        logger.error("Priority actions error for client %s: %s", user.get("client_id"), e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load priority actions",
        )


@router.get("/tasks/digest")
async def get_client_tasks_digest(
    request: Request,
    property_id: Optional[str] = Query(None, description="Filter by property"),
    activity_limit: int = Query(8, ge=1, le=25),
):
    """Dashboard-sized snapshot: task counts, freshness, short activity feed (no full task lists)."""
    user = await client_route_guard(request)
    try:
        from services.unified_tasks_service import get_unified_tasks_digest

        return await get_unified_tasks_digest(
            user["client_id"],
            property_id_filter=property_id,
            activity_limit=activity_limit,
            portal_user_id=user.get("portal_user_id"),
        )
    except Exception as e:
        logger.error("Tasks digest error for client %s: %s", user.get("client_id"), e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load tasks digest",
        )


@router.get("/command-center")
async def get_client_command_center(
    request: Request,
    property_id: Optional[str] = Query(None, description="Optional filter by property"),
):
    """
    Composed operations + compliance snapshot: urgent task rows, active risk signals,
    recent inbox activity, compliance summary. Reuses unified tasks, risk signals, and score services.
    """
    user = await client_route_guard(request)
    try:
        from services.ops_compliance_feature_flags import get_effective_flags, PREDICTIVE_MAINTENANCE
        from services.command_center_service import get_command_center_bundle

        flags = await get_effective_flags(user["client_id"])
        return await get_command_center_bundle(
            user["client_id"],
            predictive_enabled=bool(flags.get(PREDICTIVE_MAINTENANCE)),
            property_id_filter=property_id,
            portal_user_id=user.get("portal_user_id"),
        )
    except Exception as e:
        logger.error("Command center error for client %s: %s", user.get("client_id"), e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load command center",
        )


def _portal_locked_until_active(locked_until: Any) -> bool:
    if locked_until is None:
        return False
    try:
        if isinstance(locked_until, datetime):
            dt = locked_until
        else:
            dt = datetime.fromisoformat(str(locked_until).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt > datetime.now(timezone.utc)
    except Exception:
        return False


@router.get("/protection-snapshot")
async def get_protection_snapshot(
    request: Request,
    property_id: Optional[str] = Query(None, description="Optional filter for open issues and risk counts"),
):
    """
    Read-only aggregate for security/value surfaces: account sign-in hints, compliance requirement counts,
    open maintenance issues (when enabled), active risk signals (when predictive is enabled).
    """
    user = await client_route_guard(request)
    client_id = user["client_id"]
    portal_user_id = user.get("portal_user_id")
    db = database.get_db()

    if property_id:
        prop = await db.properties.find_one(
            {"property_id": property_id, "client_id": client_id},
            {"_id": 1},
        )
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    from services.ops_compliance_feature_flags import get_effective_flags, MAINTENANCE_WORKFLOWS, PREDICTIVE_MAINTENANCE
    from services import maintenance_issues_service
    from services.risk_signal_service import (
        STATUS_ACTIVE,
        RISK_LEVEL_HIGH,
        RISK_LEVEL_CRITICAL,
    )

    flags = await get_effective_flags(client_id)
    maintenance_on = bool(flags.get(MAINTENANCE_WORKFLOWS))
    predictive_on = bool(flags.get(PREDICTIVE_MAINTENANCE))

    async def load_portal_row():
        if not portal_user_id:
            return None
        return await db.portal_users.find_one(
            {"portal_user_id": portal_user_id},
            {"_id": 0, "last_login": 1, "failed_login_attempts": 1, "locked_until": 1, "lock_reason": 1},
        )

    async def load_compliance():
        return await calculate_compliance_score(client_id)

    async def load_open_issues():
        if not maintenance_on:
            return None
        n = await maintenance_issues_service.count_open_issues(
            client_id, property_id if property_id else None
        )
        return n

    async def load_risk_counts():
        if not predictive_on:
            return None
        q: Dict[str, Any] = {
            "client_id": client_id,
            "status": STATUS_ACTIVE,
        }
        if property_id:
            q["property_id"] = property_id
        active_total = await db.risk_signals.count_documents(q)
        q_high = {
            **q,
            "risk_level": {"$in": [RISK_LEVEL_HIGH, RISK_LEVEL_CRITICAL]},
        }
        high_crit = await db.risk_signals.count_documents(q_high)
        return active_total, high_crit

    portal_row, score_data, open_n, risk_counts = await asyncio.gather(
        load_portal_row(),
        load_compliance(),
        load_open_issues(),
        load_risk_counts(),
    )
    if risk_counts is None:
        active_risk_total, high_critical_risk = None, None
    else:
        active_risk_total, high_critical_risk = risk_counts

    stats = (score_data or {}).get("stats") or {}
    last_login = (portal_row or {}).get("last_login")
    if hasattr(last_login, "isoformat"):
        last_login = last_login.isoformat()

    return {
        "property_id_filter": property_id,
        "account": {
            "last_login_at": last_login,
            "failed_login_attempts": int((portal_row or {}).get("failed_login_attempts") or 0),
            "account_locked": _portal_locked_until_active((portal_row or {}).get("locked_until")),
            "lock_reason": (portal_row or {}).get("lock_reason"),
        },
        "compliance": {
            "score": score_data.get("score"),
            "grade": score_data.get("grade"),
            "requirements_overdue": int(stats.get("overdue") or 0),
            "requirements_expiring_soon": int(stats.get("expiring_soon") or 0),
            "requirements_pending": int(stats.get("pending") or 0),
        },
        "operations": {
            "open_maintenance_issues": open_n,
            "maintenance_workflows_enabled": maintenance_on,
        },
        "risk": {
            "predictive_enabled": predictive_on,
            "active_risk_signals_count": active_risk_total,
            "high_or_critical_active_count": high_critical_risk,
        },
    }


@router.get(
    "/tasks",
    summary="Unified tasks (Command Centre)",
    response_description=(
        "Unified inbox: `tasks` (sectioned lists), `summary`, `freshness`, optional `spend_this_month`, "
        "`activity_feed`. Same shape as GET /api/client/priorities."
    ),
)
async def get_client_unified_tasks(
    request: Request,
    property_id: Optional[str] = Query(None, description="Filter by property"),
    limit: int = Query(120, ge=1, le=200, description="Max raw priority rows pulled before sectioning"),
):
    """
    Unified Command Centre tasks: aggregated open work from compliance, maintenance, approvals,
    and risk signals; sections, freshness, and optional spend summary. Server-side prioritization.
    """
    user = await client_route_guard(request)
    try:
        from services.unified_tasks_service import get_unified_tasks_for_client

        return await get_unified_tasks_for_client(
            client_id=user["client_id"],
            property_id_filter=property_id,
            raw_limit=limit,
            portal_user_id=user.get("portal_user_id"),
        )
    except Exception as e:
        logger.error("Unified tasks error for client %s: %s", user.get("client_id"), e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load tasks",
        )


@router.get(
    "/priorities",
    summary="Priorities / Today inbox",
    description=(
        "Returns the **same JSON** as `GET /api/client/tasks`: unified prioritized work "
        "(`tasks`, `summary`, `freshness`, optional `spend_this_month`, `activity_feed`). "
        "Use this path when your integration or product copy uses “priorities” or “Today”; query parameters and "
        "server-side limits match `/tasks` (e.g. `property_id`, `limit` 1–200 for raw row cap)."
    ),
    response_description="Identical to GET /api/client/tasks.",
    openapi_extra={
        "x-equivalent-path": "/api/client/tasks",
    },
)
async def get_client_priorities(
    request: Request,
    property_id: Optional[str] = Query(None, description="Filter by property"),
    limit: int = Query(120, ge=1, le=200, description="Max raw priority rows pulled before sectioning"),
):
    """
    Same payload as GET /api/client/tasks — canonical “priorities / Today” inbox for API clients and integrations.
    """
    user = await client_route_guard(request)
    try:
        from services.unified_tasks_service import get_unified_tasks_for_client

        return await get_unified_tasks_for_client(
            client_id=user["client_id"],
            property_id_filter=property_id,
            raw_limit=limit,
            portal_user_id=user.get("portal_user_id"),
        )
    except Exception as e:
        logger.error("Priorities (unified tasks) error for client %s: %s", user.get("client_id"), e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load priorities",
        )


class ClientAnalyticsEventBody(BaseModel):
    """Allowed event names are enforced server-side (product_analytics_service.ALLOWED_EVENTS)."""

    event: str
    properties: Optional[Dict[str, Any]] = None
    path: Optional[str] = None


class EvidencePackJobCreateBody(BaseModel):
    """Optional UTC date range (YYYY-MM-DD, inclusive). Both required together; filters CSV tables except full properties list."""

    period_start: Optional[str] = None
    period_end: Optional[str] = None
    background: bool = False


@router.get("/analytics/summary")
async def get_client_analytics_summary(request: Request, days: int = Query(30, ge=7, le=90)):
    """First-party event totals by name for this client (Mongo aggregates; not a full warehouse)."""
    user = await client_route_guard(request)
    try:
        from services.product_analytics_service import summarize_client_events

        return await summarize_client_events(user["client_id"], days=days)
    except Exception as e:
        logger.error("analytics summary error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load analytics summary",
        )


@router.get("/activity-since")
async def get_client_activity_since(request: Request):
    """
    Structured deltas since this user's last acknowledged visit (or last login / 30 days).
    Does not advance the cursor; POST /activity-since/acknowledge after the user marks the feed as seen.
    """
    user = await client_route_guard(request)
    portal_user_id = user.get("portal_user_id")
    if not portal_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portal user session required",
        )
    try:
        from services.portal_activity_service import peek_activity_since_for_portal_user

        return await peek_activity_since_for_portal_user(portal_user_id, user["client_id"])
    except Exception as e:
        logger.error("activity-since error for client %s: %s", user.get("client_id"), e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load activity since last visit",
        )


@router.post("/activity-since/acknowledge")
async def post_client_activity_since_acknowledge(request: Request):
    """Advance the 'since last visit' cursor to now."""
    user = await client_route_guard(request)
    portal_user_id = user.get("portal_user_id")
    if not portal_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portal user session required",
        )
    try:
        from services.portal_activity_service import acknowledge_activity_cursor

        at = await acknowledge_activity_cursor(portal_user_id)
        return {"acknowledged_at": at}
    except Exception as e:
        logger.error("activity-since acknowledge error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to acknowledge activity feed",
        )


@router.post("/analytics/events")
async def post_client_analytics_event(request: Request, body: ClientAnalyticsEventBody):
    """First-party product analytics (Mongo). Unknown event names are ignored."""
    user = await client_route_guard(request)
    try:
        from utils.analytics_event_logger import record_portal_analytics_event

        await record_portal_analytics_event(
            client_id=user["client_id"],
            portal_user_id=user.get("portal_user_id"),
            jwt_role=user.get("role"),
            event=body.event.strip(),
            properties=body.properties,
            path=body.path,
        )
        return {"recorded": True}
    except Exception as e:
        logger.error("analytics event error: %s", e)
        return {"recorded": False}


@router.post("/evidence-pack/jobs")
async def post_client_evidence_pack_job(
    request: Request,
    background_tasks: BackgroundTasks,
    body: Optional[EvidencePackJobCreateBody] = Body(default=None),
):
    """
    Build a ZIP evidence pack (CSVs + manifest) and store in GridFS.
    Plan: requires audit_log_export (Pro). Rate: max 5 jobs per client per rolling 24h.
    Optional `period_start` / `period_end` (YYYY-MM-DD): filter requirements, documents, scores, work orders to that range; properties remain full portfolio.
    Set `background: true` to enqueue generation and poll GET /evidence-pack/jobs until status is completed.

    For a single governed **per-property** audit bundle (PDF report + verified certs + timeline +
    delivery proof + checksum manifest), use ``POST /api/client/compliance/audit-pack/generate`` instead.
    """
    from services.plan_registry import plan_registry
    from models import AuditAction
    from utils.audit import create_audit_log
    from services.evidence_pack_service import parse_export_period

    user = await client_route_guard(request)
    b = body or EvidencePackJobCreateBody()
    client_id = user["client_id"]
    allowed, error_msg, error_details = await plan_registry.enforce_feature(client_id, "audit_log_export")
    if not allowed:
        detail = {
            "error_code": (error_details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
            "message": error_msg,
            "upgrade_required": True,
            **(error_details or {}),
        }
        detail["feature"] = "audit_log_export"
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    db = database.get_db()
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=24)).isoformat()
    recent = await db.compliance_evidence_pack_jobs.count_documents(
        {"client_id": client_id, "created_at": {"$gte": cutoff}}
    )
    if recent >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Evidence pack rate limit: maximum 5 exports per 24 hours.",
        )

    cl = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "customer_reference": 1})
    crn = (cl or {}).get("customer_reference")

    try:
        parse_export_period(b.period_start, b.period_end)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    try:
        from services.evidence_pack_service import (
            create_evidence_pack_job,
            create_processing_evidence_pack_job,
            run_evidence_pack_job_in_background,
        )

        if b.background:
            job = await create_processing_evidence_pack_job(
                client_id,
                user.get("portal_user_id") or "",
                crn,
                period_start=b.period_start,
                period_end=b.period_end,
            )
            background_tasks.add_task(run_evidence_pack_job_in_background, job["job_id"])
            return job

        job = await create_evidence_pack_job(
            client_id,
            user.get("portal_user_id") or "",
            crn,
            period_start=b.period_start,
            period_end=b.period_end,
        )
        await create_audit_log(
            action=AuditAction.REPORT_EXPORTED,
            client_id=client_id,
            actor_id=user.get("portal_user_id"),
            metadata={
                "export_kind": "compliance_evidence_pack_v1",
                "job_id": job.get("job_id"),
                "period_start": job.get("period_start"),
                "period_end": job.get("period_end"),
            },
        )
        return job
    except Exception as e:
        logger.error("evidence pack job error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate evidence pack",
        )


@router.get("/evidence-pack/jobs")
async def list_client_evidence_pack_jobs(request: Request, limit: int = Query(10, ge=1, le=30)):
    from services.plan_registry import plan_registry
    from services.evidence_pack_service import recent_jobs

    user = await client_route_guard(request)
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "audit_log_export")
    if not allowed:
        detail = {
            "error_code": (error_details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
            "message": error_msg,
            "upgrade_required": True,
            **(error_details or {}),
        }
        detail["feature"] = "audit_log_export"
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    items = await recent_jobs(user["client_id"], limit=limit)
    return {"jobs": items}


@router.get("/evidence-pack/jobs/{job_id}/file")
async def download_client_evidence_pack_file(request: Request, job_id: str):
    from services.plan_registry import plan_registry
    from services.evidence_pack_service import get_job, read_pack_bytes

    user = await client_route_guard(request)
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "audit_log_export")
    if not allowed:
        detail = {
            "error_code": (error_details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
            "message": error_msg,
            "upgrade_required": True,
            **(error_details or {}),
        }
        detail["feature"] = "audit_log_export"
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    job = await get_job(user["client_id"], job_id.strip())
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job not found")
    st = job.get("status")
    if st == "processing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EXPORT_PROCESSING", "message": "Evidence pack is still being generated. Try again shortly."},
        )
    if st == "failed":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=job.get("error") or "Export job failed",
        )
    if st != "completed":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job not found")
    gid = job.get("gridfs_id")
    if not gid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export file missing")
    data = await read_pack_bytes(str(gid))
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export file unavailable")

    try:
        from services.product_analytics_service import record_event
        from utils.analytics_event_logger import analytics_role_from_jwt_role

        await record_event(
            user["client_id"],
            user.get("portal_user_id"),
            "evidence_pack_downloaded",
            {"job_id": job_id},
            "/evidence-pack",
            role=analytics_role_from_jwt_role(user.get("role")),
        )
    except Exception:
        pass

    fname = job.get("filename") or "evidence-pack.zip"
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


class ClientTaskOverrideBody(BaseModel):
    """Today inbox visibility: snooze | dismiss (reason) | reviewed | done (legacy) | restore. Does not satisfy requirements or close jobs."""

    task_id: str
    action: str
    snooze_days: Optional[int] = None
    title: Optional[str] = None
    source_type: Optional[str] = None
    property_id: Optional[str] = None
    dismiss_reason: Optional[str] = None
    business_outcome: Optional[str] = None


class ClientTaskNavigationIntentBody(BaseModel):
    """Audited server-side record of a Today / Command Centre navigation (before client-side route change)."""

    task_id: str
    intent_kind: str = "primary"
    target_path: str = ""
    source_type: Optional[str] = None
    action_context_type: Optional[str] = None


@router.post("/tasks/record-intent")
async def post_client_task_navigation_intent(request: Request, body: ClientTaskNavigationIntentBody):
    """Persist an audit trail row when the user follows a task deep-link from Today (analytics complement)."""
    user = await client_route_guard(request)
    from services.client_task_state_service import is_valid_task_id
    from utils.audit import create_audit_log
    from models import AuditAction

    tid = (body.task_id or "").strip()
    if not is_valid_task_id(tid):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid task_id")
    kind = (body.intent_kind or "primary").strip().lower()
    if kind not in ("primary", "secondary"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="intent_kind must be primary or secondary")
    try:
        await create_audit_log(
            action=AuditAction.CLIENT_PORTAL_TODAY_NAVIGATION_INTENT,
            actor_id=user.get("portal_user_id"),
            actor_role=user.get("role"),
            client_id=user.get("client_id"),
            resource_type="client_task",
            resource_id=tid,
            metadata={
                "task_id": tid,
                "intent_kind": kind,
                "target_path": (body.target_path or "")[:500],
                "source_type": body.source_type,
                "action_context_type": body.action_context_type,
            },
        )
    except Exception as e:
        logger.warning("Today navigation intent audit failed: %s", e)
    return {"ok": True}


@router.post("/tasks/override")
async def post_client_task_override(request: Request, body: ClientTaskOverrideBody):
    """Apply or clear a personal task override (snooze, dismiss, done, restore). Audited."""
    user = await client_route_guard(request)
    try:
        from services.client_task_state_service import apply_task_action

        return await apply_task_action(
            user["client_id"],
            body.task_id.strip(),
            body.action.strip().lower(),
            portal_user_id=user.get("portal_user_id"),
            snooze_days=body.snooze_days,
            title_snapshot=body.title,
            source_type_snapshot=body.source_type,
            property_id_snapshot=body.property_id,
            dismiss_reason=body.dismiss_reason,
            business_outcome=body.business_outcome,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Task override error for client %s: %s", user.get("client_id"), e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update task",
        )


@router.get("/tasks/activity")
async def get_client_task_activity(
    request: Request,
    limit: int = Query(30, ge=1, le=100),
):
    """Recent Today inbox visibility actions (snooze, dismiss, reviewed, done, restore)—not domain completion."""
    user = await client_route_guard(request)
    from services.client_task_state_service import list_recent_activity

    items = await list_recent_activity(
        user["client_id"],
        limit=limit,
        portal_user_id=user.get("portal_user_id"),
    )
    return {"items": items}


@router.get("/onboarding/checklist")
async def get_onboarding_checklist(request: Request):
    """Get server-driven onboarding checklist (items + completion)."""
    user = await client_route_guard(request)
    from services.onboarding_checklist_service import get_checklist_state
    return await get_checklist_state(user["client_id"], portal_user_id=user.get("portal_user_id"))


@router.get("/value-insights")
async def get_client_value_insights(request: Request):
    """Plan-aware achievements, risk snapshot, and upgrade unlock copy (entitlements from billing plan)."""
    user = await client_route_guard(request)
    from services.client_value_insights_service import get_value_insights

    return await get_value_insights(user["client_id"])


@router.get("/portal-context")
async def get_portal_context(request: Request):
    """Server time + last recorded client audit activity (trust / freshness signals for the portal shell)."""
    user = await client_route_guard(request)
    try:
        db = database.get_db()
        last = await db.audit_logs.find_one(
            {"client_id": user["client_id"]},
            {"_id": 0, "timestamp": 1},
            sort=[("timestamp", -1)],
        )
        last_ts = None
        if last:
            raw = last.get("timestamp")
            if hasattr(raw, "isoformat"):
                last_ts = raw.isoformat()
            else:
                last_ts = str(raw) if raw is not None else None
        return {
            "server_time": datetime.now(timezone.utc).isoformat(),
            "last_recorded_activity_at": last_ts,
        }
    except Exception as e:
        log_api_error(
            logger,
            endpoint="/client/portal-context",
            error_type=type(e).__name__,
            message=str(e),
            user_id=user.get("portal_user_id"),
            exc=e,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=structured_error(
                "PORTAL_CONTEXT_UNAVAILABLE",
                "Could not load portal status. Please try again.",
                retry_suggested=True,
            ),
        )


class JurisdictionFallbackAcknowledgementBody(BaseModel):
    """Phase-1 portfolio acknowledgement; property records remain authoritative for scoring accuracy."""

    confirm: bool = False


@router.post("/onboarding/jurisdiction-fallback-acknowledgement")
async def acknowledge_jurisdiction_fallback_assumptions(
    request: Request,
    body: JurisdictionFallbackAcknowledgementBody,
):
    """
    Record explicit consent to continue while some properties lack jurisdiction on the property record.
    Does not change scoring; enables onboarding checklist completion when defaults apply.
    """
    user = await client_route_guard(request)
    if not body.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=structured_error(
                "CONFIRMATION_REQUIRED",
                "Use the in-app confirmation step: you must acknowledge that scores and rules may be wrong for properties without a saved jurisdiction.",
                retry_suggested=False,
            ),
        )
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.clients.update_one(
        {"client_id": user["client_id"]},
        {"$set": {"jurisdiction_fallback_acknowledged_at": now}},
    )
    from services.onboarding_checklist_service import get_checklist_state, sync_auto_completed_items
    from models import AuditAction
    from utils.audit import create_audit_log

    await sync_auto_completed_items(user["client_id"], portal_user_id=user.get("portal_user_id"))
    await create_audit_log(
        action=AuditAction.JURISDICTION_FALLBACK_ASSUMPTIONS_ACKNOWLEDGED,
        actor_id=user.get("portal_user_id"),
        client_id=user["client_id"],
        resource_type="client",
        resource_id=user["client_id"],
        metadata={"acknowledged_at": now},
    )
    return await get_checklist_state(user["client_id"], portal_user_id=user.get("portal_user_id"))


@router.post("/onboarding/checklist/items/{item_id}/complete")
async def complete_onboarding_item(request: Request, item_id: str):
    """Mark one checklist item complete. Server-validates before accepting."""
    user = await client_route_guard(request)
    from services.onboarding_checklist_service import mark_item_complete
    from models import AuditAction
    from utils.audit import create_audit_log
    result = await mark_item_complete(user["client_id"], item_id, actor_id=user.get("portal_user_id"))
    if not result.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=structured_error(
                "ONBOARDING_ITEM_NOT_READY",
                str(result.get("error") or "Cannot complete this item until the step is done in the app."),
                retry_suggested=False,
            ),
        )
    await create_audit_log(
        action=AuditAction.ONBOARDING_CHECKLIST_ITEM_COMPLETED,
        actor_id=user.get("portal_user_id"),
        client_id=user["client_id"],
        resource_type="onboarding_checklist",
        resource_id=item_id,
        metadata={"item_id": item_id, "checklist_completed": result.get("checklist_completed")},
    )
    if result.get("checklist_completed"):
        await create_audit_log(
            action=AuditAction.ONBOARDING_CHECKLIST_COMPLETED,
            actor_id=user.get("portal_user_id"),
            client_id=user["client_id"],
            resource_type="onboarding_checklist",
            resource_id="checklist",
            metadata={"completed_at": result.get("completed_at")},
        )
    return result


@router.get("/settings/jurisdiction")
async def get_jurisdiction_settings(request: Request):
    """Get client jurisdiction settings (default_jurisdiction, enabled_jurisdictions)."""
    user = await client_route_guard(request)
    db = database.get_db()
    return await _resolved_jurisdiction_settings_for_client(db, user["client_id"])


class JurisdictionSettingsBody(BaseModel):
    default_jurisdiction: Optional[str] = None
    enabled_jurisdictions: Optional[List[str]] = None


@router.patch("/settings/jurisdiction")
async def update_jurisdiction_settings(request: Request, body: JurisdictionSettingsBody):
    """Update client jurisdiction settings. Valid: Scotland, England, Wales, Northern Ireland."""
    user = await client_route_guard(request)
    valid = {"Scotland", "England", "Wales", "Northern Ireland"}
    updates = {}
    if body.default_jurisdiction is not None:
        if body.default_jurisdiction not in valid:
            raise HTTPException(status_code=400, detail="Invalid default_jurisdiction")
        updates["default_jurisdiction"] = body.default_jurisdiction
    if body.enabled_jurisdictions is not None:
        if not isinstance(body.enabled_jurisdictions, list) or not all(j in valid for j in body.enabled_jurisdictions):
            raise HTTPException(status_code=400, detail="enabled_jurisdictions must be a list of Scotland, England, Wales, Northern Ireland")
        updates["enabled_jurisdictions"] = body.enabled_jurisdictions
    if not updates:
        return {"ok": True, "recalc_enqueued": 0}
    db = database.get_db()
    await db.clients.update_one(
        {"client_id": user["client_id"]},
        {"$set": updates},
    )
    # Re-score every property so jurisdiction profile, weights, and downstream risk regen stay aligned.
    from services.compliance_recalc_queue import (
        enqueue_compliance_recalc,
        TRIGGER_CLIENT_JURISDICTION_UPDATED,
        ACTOR_CLIENT,
    )

    prop_rows = await db.properties.find(
        {"client_id": user["client_id"]},
        {"_id": 0, "property_id": 1},
    ).to_list(10000)
    enq = 0
    for row in prop_rows:
        pid = row.get("property_id")
        if not pid:
            continue
        if await enqueue_compliance_recalc(
            property_id=pid,
            client_id=user["client_id"],
            trigger_reason=TRIGGER_CLIENT_JURISDICTION_UPDATED,
            actor_type=ACTOR_CLIENT,
            actor_id=user.get("portal_user_id"),
            correlation_id=f"JURISDICTION_UPDATED:{pid}",
        ):
            enq += 1
    return {"ok": True, "recalc_enqueued": enq}


@router.post("/settings/jurisdiction/apply-to-missing-properties")
async def apply_default_jurisdiction_to_missing_properties(request: Request):
    """
    Set property.jurisdiction to the client's saved default only where the property has no explicit
    UK portfolio label yet. Does not overwrite properties that already have a jurisdiction on record
    (supports mixed-jurisdiction portfolios).
    """
    user = await client_route_guard(request)
    db = database.get_db()
    from services.compliance_rules_registry import (
        canonicalize_uk_portfolio_label,
        property_has_explicit_portfolio_jurisdiction,
    )
    from services.compliance_recalc_queue import (
        ACTOR_CLIENT,
        TRIGGER_PROPERTY_UPDATED,
        enqueue_compliance_recalc,
    )

    client = await db.clients.find_one(
        {"client_id": user["client_id"]},
        {"_id": 0, "default_jurisdiction": 1},
    ) or {}
    default_label = canonicalize_uk_portfolio_label(client.get("default_jurisdiction"))
    if not default_label:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Save a valid account default jurisdiction first, then run this action.",
        )
    props = await db.properties.find(
        {"client_id": user["client_id"]},
        {"_id": 0, "property_id": 1, "jurisdiction": 1},
    ).to_list(10000)
    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    updated_property_ids = []
    enq = 0
    for p in props:
        pid = p.get("property_id")
        if not pid or property_has_explicit_portfolio_jurisdiction(p):
            continue
        await db.properties.update_one(
            {"property_id": pid, "client_id": user["client_id"]},
            {"$set": {"jurisdiction": default_label, "updated_at": now}},
        )
        updated += 1
        updated_property_ids.append(pid)
        if await enqueue_compliance_recalc(
            property_id=pid,
            client_id=user["client_id"],
            trigger_reason=TRIGGER_PROPERTY_UPDATED,
            actor_type=ACTOR_CLIENT,
            actor_id=user.get("portal_user_id"),
            correlation_id=f"JURISDICTION_APPLY_MISSING:{pid}",
        ):
            enq += 1
    return {
        "ok": True,
        "properties_updated": updated,
        "updated_property_ids": updated_property_ids,
        "recalc_enqueued": enq,
    }


@router.get("/properties")
async def get_properties(request: Request):
    """Get client properties."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        properties = await db.properties.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(100)
        from services.compliance_rules_registry import (
            build_jurisdiction_compliance_notice,
            jurisdiction_attribution_for_property,
            property_jurisdiction_requirement_flags,
        )

        client_doc = await db.clients.find_one(
            {"client_id": user["client_id"]},
            {"_id": 0, "default_jurisdiction": 1},
        ) or {}
        for p in properties:
            att = jurisdiction_attribution_for_property(p, client_doc)
            p["compliance_basis"] = att["compliance_basis"]
            p["effective_jurisdiction_label"] = att["effective_jurisdiction_label"]
            p["jurisdiction_source"] = att["jurisdiction_source"]
            p.update(property_jurisdiction_requirement_flags(p))

        return {
            "properties": properties,
            "jurisdiction_compliance_notice": build_jurisdiction_compliance_notice(client_doc, properties),
            "client_default_jurisdiction": client_doc.get("default_jurisdiction"),
        }
    
    except Exception as e:
        logger.error(f"Properties error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load properties"
        )

@router.get("/properties/{property_id}/requirements")
async def get_property_requirements(request: Request, property_id: str):
    """Get requirements for a property."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Verify property belongs to client
        prop = await db.properties.find_one(
            {"property_id": property_id, "client_id": user["client_id"]},
            {"_id": 0}
        )
        
        if not prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found"
            )
        
        requirements = await db.requirements.find(
            {"property_id": property_id, "client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(100)
        from services.requirement_client_runtime_surface import (
            filter_requirement_rows_for_client_runtime_surfaces,
        )

        requirements = await filter_requirement_rows_for_client_runtime_surfaces(
            db,
            client_id=user["client_id"],
            requirements=requirements,
            client_doc=await db.clients.find_one({"client_id": user["client_id"]}, {"_id": 0}) or {},
            properties=[prop],
        )

        from services.requirement_truth import enrich_requirements_for_client

        enriched, presentation = await enrich_requirements_for_client(db, user["client_id"], requirements)
        enriched = [r for r in enriched if r.get("client_surface_visible", True)]
        return {"requirements": enriched, "presentation": presentation}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Requirements error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load requirements"
        )


@router.get("/properties/{property_id}/requirements/explanation")
async def get_requirement_explanation(
    request: Request,
    property_id: str,
    requirement_code: Optional[str] = Query(None, description="Requirement code (e.g. gas_safety, eicr)"),
    requirement_id: Optional[str] = Query(None, description="Requirement row id if used by client"),
):
    """Get contextual explanation for a compliance requirement (why it matters, legal context, recommended action)."""
    user = await client_route_guard(request)
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0},
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    query = {"property_id": property_id, "client_id": user["client_id"]}
    if requirement_code:
        query["$or"] = [
            {"requirement_code": requirement_code},
            {"requirement_type": requirement_code},
        ]
    elif requirement_id:
        query["requirement_id"] = requirement_id
    else:
        raise HTTPException(status_code=400, detail="Provide requirement_code or requirement_id")
    req = await db.requirements.find_one(query, {"_id": 0})
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    from services.requirement_client_runtime_surface import requirement_row_eligible_on_client_runtime_surfaces

    if not await requirement_row_eligible_on_client_runtime_surfaces(
        db,
        client_id=user["client_id"],
        row=req,
        property_doc=prop,
    ):
        raise HTTPException(status_code=404, detail="Requirement not found")
    code = req.get("requirement_code") or req.get("requirement_type")
    catalog = await db.requirements_catalog.find_one({"code": code}, {"_id": 0}) if code else None
    from services.explanation_engine import explain_compliance_alert
    return explain_compliance_alert(req, catalog)


@router.post("/properties/{property_id}/requirements/mark-not-applicable")
async def mark_requirement_not_applicable(request: Request, property_id: str):
    """Create or update a requirement row as NOT_APPLICABLE for a catalog item (e.g. from Property detail).
    Used when the item appears as 'Missing evidence' on the property tab but does not apply to this property.
    After this, the catalog matrix excludes it and the item disappears from the property requirements list."""
    user = await client_route_guard(request)
    db = database.get_db()
    client_id = user["client_id"]
    try:
        body = await request.json()
    except Exception:
        body = {}
    requirement_code = (body.get("requirement_code") or "").strip()
    not_required_reason = (body.get("not_required_reason") or "").strip()
    if not requirement_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="requirement_code is required")
    if not not_required_reason or not_required_reason not in NOT_REQUIRED_REASONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"not_required_reason is required and must be one of: {NOT_REQUIRED_REASONS}",
        )
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    catalog_doc = await db.requirements_catalog.find_one(
        {"code": requirement_code},
        {"_id": 0, "code": 1, "title": 1},
    )
    if not catalog_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown requirement_code: {requirement_code}",
        )
    code = catalog_doc.get("code", requirement_code)
    title = catalog_doc.get("title") or code

    def _matches(r):
        rt = (r.get("requirement_type") or "").strip().lower()
        rc = (r.get("requirement_code") or "").strip().lower()
        c = code.strip().lower()
        return rt == c or rc == c

    reqs = await db.requirements.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0, "requirement_id": 1, "requirement_type": 1, "requirement_code": 1},
    ).to_list(200)
    existing_row = next((r for r in reqs if _matches(r)), None)
    now = datetime.now(timezone.utc)
    client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1})
    from services.compliance_rules_registry import portfolio_jurisdiction_label

    portfolio_juris = portfolio_jurisdiction_label(prop, client_doc or {})

    if existing_row:
        update = {
            "applicability": "NOT_REQUIRED",
            "not_required_reason": not_required_reason or None,
            "status": "NOT_REQUIRED",
            "jurisdiction": portfolio_juris,
            "updated_at": now.isoformat(),
        }
        await db.requirements.update_one(
            {"requirement_id": existing_row["requirement_id"], "property_id": property_id, "client_id": client_id},
            {"$set": update},
        )
        requirement_id = existing_row["requirement_id"]
    else:
        requirement_id = str(uuid.uuid4())
        due_far = now + timedelta(days=365 * 10)
        doc = {
            "requirement_id": requirement_id,
            "client_id": client_id,
            "property_id": property_id,
            "requirement_type": code,
            "requirement_code": code,
            "jurisdiction": portfolio_juris,
            "description": title,
            "frequency_days": 0,
            "due_date": due_far.isoformat(),
            "status": "NOT_REQUIRED",
            "applicability": "NOT_REQUIRED",
            "not_required_reason": not_required_reason or None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        await db.requirements.insert_one(doc)
    from services.compliance_recalc_queue import enqueue_compliance_recalc, TRIGGER_PROPERTY_UPDATED, ACTOR_CLIENT
    await enqueue_compliance_recalc(
        property_id=property_id,
        client_id=client_id,
        trigger_reason=TRIGGER_PROPERTY_UPDATED,
        actor_type=ACTOR_CLIENT,
        actor_id=user.get("portal_user_id"),
        correlation_id=f"MARK_NOT_APPLICABLE:{requirement_id}",
    )
    return {"message": "Requirement marked as not applicable", "requirement_id": requirement_id}


@router.get("/requirements")
async def get_all_requirements(request: Request):
    """Get all requirements for the client."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        requirements = await db.requirements.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(1000)
        from services.requirement_client_runtime_surface import (
            filter_requirement_rows_for_client_runtime_surfaces,
        )

        props_all = await db.properties.find(
            {"client_id": user["client_id"]},
            {"_id": 0},
        ).to_list(1000)
        requirements = await filter_requirement_rows_for_client_runtime_surfaces(
            db,
            client_id=user["client_id"],
            requirements=requirements,
            client_doc=await db.clients.find_one({"client_id": user["client_id"]}, {"_id": 0}) or {},
            properties=props_all,
        )

        from services.requirement_truth import enrich_requirements_for_client

        enriched, presentation = await enrich_requirements_for_client(db, user["client_id"], requirements)
        enriched = [r for r in enriched if r.get("client_surface_visible", True)]
        return {"requirements": enriched, "presentation": presentation}
    
    except Exception as e:
        logger.error(f"Requirements error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load requirements"
        )


@router.get("/plan-features")
async def get_plan_features(request: Request):
    """Get the current client's plan features and limits.
    
    Returns feature availability for UI gating.
    Uses plan_registry (2/10/25 caps); response shape preserved for compatibility.
    """
    user = await client_route_guard(request)
    try:
        from services.plan_registry import plan_registry, subscription_allows_feature_access

        client_id = user["client_id"]
        db = database.get_db()
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "billing_plan": 1, "subscription_status": 1}
        )
        if not client:
            plan_code = plan_registry.resolve_plan_code("PLAN_1_SOLO")
            plan_def = plan_registry.get_plan(plan_code)
            features = plan_registry.get_features(plan_code)
            features["max_properties"] = plan_registry.get_property_limit(plan_code)
            return {
                "plan": plan_code.value,
                "plan_name": plan_def["name"],
                "subscription_status": "UNKNOWN",
                "features": features,
                "is_active": False,
            }
        plan_str = client.get("billing_plan", "PLAN_1_SOLO")
        plan_code = plan_registry.resolve_plan_code(plan_str)
        plan_def = plan_registry.get_plan(plan_code)
        subscription_status = client.get("subscription_status", "PENDING")
        is_active = subscription_allows_feature_access(subscription_status)
        features = plan_registry.get_features(plan_code)
        features["max_properties"] = plan_registry.get_property_limit(plan_code)
        return {
            "plan": plan_code.value,
            "plan_name": plan_def["name"],
            "subscription_status": subscription_status,
            "features": features,
            "is_active": is_active,
        }
    except Exception as e:
        logger.error(f"Plan features error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load plan features"
        )


@router.get("/entitlements")
async def get_client_entitlements(request: Request):
    """Get comprehensive feature entitlements for the client.
    
    Returns detailed feature availability with metadata for UI rendering.
    Uses plan_registry plus ops_compliance module flags (maintenance_workflows, predictive_maintenance).
    """
    user = await client_route_guard(request)
    try:
        from services.plan_registry import plan_registry
        from services.ops_compliance_feature_flags import (
            get_effective_flags,
            MAINTENANCE_WORKFLOWS,
            PREDICTIVE_MAINTENANCE,
            CONTRACTOR_NETWORK,
            INVOICING,
            COMPLIANCE_ENGINE,
        )

        entitlements = await plan_registry.get_client_entitlements(user["client_id"])
        flags = await get_effective_flags(user["client_id"])
        features = entitlements.get("features") or {}
        # Plan-based defaults + admin overrides (single source of truth for client menu)
        features["maintenance_workflows"] = {
            "enabled": bool(flags.get(MAINTENANCE_WORKFLOWS)),
            "name": "Maintenance Workflows",
            "description": "Report and track work orders; tenants can report repairs.",
            "category": "ops",
            "minimum_plan": None,
        }
        features["predictive_maintenance"] = {
            "enabled": bool(flags.get(PREDICTIVE_MAINTENANCE)),
            "name": "Predictive Maintenance",
            "description": "View predictive insights for property assets and maintenance.",
            "category": "ops",
            "minimum_plan": None,
        }
        features["contractor_network"] = {
            "enabled": bool(flags.get(CONTRACTOR_NETWORK)),
            "name": "Contractor Network",
            "description": "View vetted contractors and preferred trades for your account.",
            "category": "ops",
            "minimum_plan": None,
        }
        features["invoicing"] = {
            "enabled": bool(flags.get(INVOICING)),
            "name": "Billing & Invoicing",
            "description": "View billing history and invoices.",
            "category": "ops",
            "minimum_plan": None,
        }
        features["compliance_engine"] = {
            "enabled": bool(flags.get(COMPLIANCE_ENGINE)),
            "name": "Compliance execution",
            "description": "Book compliance inspections and renewal jobs with contractor confirmation.",
            "category": "compliance",
            "minimum_plan": None,
        }
        entitlements["features"] = features
        enabled_count = sum(1 for f in features.values() if f.get("enabled"))
        entitlements["feature_summary"] = {
            "total": len(features),
            "enabled": enabled_count,
            "disabled": len(features) - enabled_count,
        }
        return entitlements
    except Exception as e:
        logger.error(f"Entitlements error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load entitlements"
        )


@router.get("/entitlements/context")
async def get_client_entitlements_context(request: Request):
    """
    Lightweight usage context for upsell and dashboard copy (property count vs plan cap, read API path).
    Does not replace GET /entitlements; safe to call when building contextual upgrade messaging.
    """
    user = await client_route_guard(request)
    try:
        from services.plan_registry import plan_registry

        db = database.get_db()
        client_id = user["client_id"]
        prop_count = await db.properties.count_documents({"client_id": client_id})
        ent = await plan_registry.get_client_entitlements(client_id)
        cap = int(ent.get("max_properties") or 0)
        at_limit = cap > 0 and prop_count >= cap
        return {
            "property_count": prop_count,
            "max_properties": cap,
            "at_property_limit": at_limit,
            "plan": ent.get("plan"),
            "plan_name": ent.get("plan_name"),
            "is_active": bool(ent.get("is_active")),
            "read_api_base_path": "/api/client-data/v1",
        }
    except Exception as e:
        logger.error("entitlements context error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load entitlements context",
        )


@router.get("/contractors")
async def get_client_contractors(
    request: Request,
    vetted_only: bool = False,
    skip: int = 0,
    limit: int = 100,
    source_type: Optional[str] = None,
):
    """List contractors available to this client (assigned or system-wide). Requires CONTRACTOR_NETWORK flag."""
    user = await client_route_guard(request)
    from services.ops_compliance_feature_flags import get_effective_flags, CONTRACTOR_NETWORK
    from services import contractor_service

    flags = await get_effective_flags(user["client_id"])
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Contractor network is not enabled for your account. Contact your administrator.",
        )
    result = await contractor_service.list_contractors_for_client(
        client_id=user["client_id"],
        vetted_only=vetted_only,
        skip=skip,
        limit=min(limit, 200),
        source_type=source_type,
    )
    return result


class CreateContractorBody(BaseModel):
    company_name: str
    trade_types: List[str]
    phone: Optional[str] = None
    email: Optional[str] = None
    contact_name: Optional[str] = None
    region: Optional[str] = None
    credentials: Optional[List[str]] = None
    insurance_details: Optional[str] = None
    areas_served: Optional[List[str]] = None
    notes: Optional[str] = None


@router.get("/contractors/{contractor_id}/explanation")
async def get_contractor_explanation(request: Request, contractor_id: str):
    """Get explanation for contractor reliability/performance score (why it matters, usage guidance). Requires CONTRACTOR_NETWORK."""
    user = await client_route_guard(request)
    from services.ops_compliance_feature_flags import get_effective_flags, CONTRACTOR_NETWORK
    from services import contractor_service
    from services.explanation_engine import explain_contractor_score

    flags = await get_effective_flags(user["client_id"])
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(status_code=403, detail="Contractor network not enabled")
    result = await contractor_service.list_contractors_for_client(
        client_id=user["client_id"], skip=0, limit=500,
    )
    contractors = result.get("contractors") or []
    if not any(c.get("contractor_id") == contractor_id for c in contractors):
        raise HTTPException(status_code=404, detail="Contractor not found")
    doc = await contractor_service.get_contractor(contractor_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Contractor not found")
    return explain_contractor_score(doc)


@router.post("/contractors/{contractor_id}/submit-to-network")
async def submit_contractor_to_network(request: Request, contractor_id: str):
    """Submit a private contractor for network review. Contractor remains private until admin approves. Requires CONTRACTOR_NETWORK."""
    user = await client_route_guard(request)
    from services.ops_compliance_feature_flags import get_effective_flags, CONTRACTOR_NETWORK
    from services import contractor_service

    flags = await get_effective_flags(user["client_id"])
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Contractor network is not enabled for your account.",
        )
    doc = await contractor_service.submit_contractor_to_network(contractor_id, user["client_id"])
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contractor not found or not eligible for network submission.",
        )
    from utils.audit import create_audit_log
    from models import AuditAction
    await create_audit_log(
        action=AuditAction.CONTRACTOR_SUBMITTED_TO_NETWORK,
        client_id=user["client_id"],
        resource_type="contractor",
        resource_id=contractor_id,
        metadata={"submitted_to_network_at": doc.get("submitted_to_network_at")},
    )
    return doc


@router.post("/contractors")
async def create_client_contractor(request: Request, body: CreateContractorBody):
    """Landlord adds a contractor. Requires CONTRACTOR_NETWORK. Contractor is visible only to this organisation."""
    user = await client_route_guard(request)
    from services.ops_compliance_feature_flags import get_effective_flags, CONTRACTOR_NETWORK
    from services import contractor_service

    flags = await get_effective_flags(user["client_id"])
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Contractor network is not enabled for your account.",
        )
    if not body.phone and not body.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="phone or email is required")
    doc = await contractor_service.create_contractor_landlord(
        client_id=user["client_id"],
        company_name=body.company_name.strip(),
        trade_types=[t.strip() for t in body.trade_types if t and t.strip()] or ["general"],
        phone=body.phone.strip() if body.phone else None,
        email=body.email.strip() if body.email else None,
        contact_name=body.contact_name.strip() if body.contact_name else None,
        region=body.region.strip() if body.region else None,
        credentials=body.credentials,
        insurance_details=body.insurance_details.strip() if body.insurance_details else None,
        areas_served=body.areas_served,
        notes=body.notes.strip() if body.notes else None,
    )
    from utils.audit import create_audit_log
    from models import AuditAction
    await create_audit_log(
        action=AuditAction.CONTRACTOR_CREATED,
        client_id=user["client_id"],
        resource_type="contractor",
        resource_id=doc.get("contractor_id"),
        metadata={"source_type": "landlord_added"},
    )
    return doc


class RateContractorBody(BaseModel):
    rating: int  # 1-5
    work_order_id: Optional[str] = None
    property_id: Optional[str] = None
    completion_speed: Optional[int] = None  # 1-5
    professionalism: Optional[int] = None   # 1-5
    notes: Optional[str] = None


@router.post("/contractors/{contractor_id}/rate")
async def rate_contractor(request: Request, contractor_id: str, body: RateContractorBody):
    """Submit a rating for a contractor (e.g. after work order). Requires CONTRACTOR_NETWORK."""
    user = await client_route_guard(request)
    from services.ops_compliance_feature_flags import get_effective_flags, CONTRACTOR_NETWORK
    from services import contractor_service

    flags = await get_effective_flags(user["client_id"])
    if not flags.get(CONTRACTOR_NETWORK):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Contractor network is not enabled.")
    if not (1 <= body.rating <= 5):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="rating must be between 1 and 5")
    try:
        doc = await contractor_service.create_contractor_rating(
            contractor_id=contractor_id,
            client_id=user["client_id"],
            rating=body.rating,
            work_order_id=body.work_order_id,
            property_id=body.property_id,
            completion_speed=body.completion_speed,
            professionalism=body.professionalism,
            notes=body.notes,
        )
        return doc
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/documents")
async def get_documents(request: Request):
    """Get client documents."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        documents = await db.documents.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(1000)
        
        return {"documents": documents}
    
    except Exception as e:
        logger.error(f"Documents error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load documents"
        )


@router.get("/compliance-pack/{property_id}/preview")
async def get_compliance_pack_preview(request: Request, property_id: str):
    """Get a preview of what the compliance pack will contain."""
    user = await client_route_guard(request)
    
    try:
        from services.compliance_pack import compliance_pack_service
        
        preview = await compliance_pack_service.get_pack_preview(
            property_id=property_id,
            client_id=user["client_id"]
        )
        return preview
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Compliance pack preview error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate preview"
        )


@router.get("/compliance-pack/{property_id}/download")
async def download_compliance_pack(
    request: Request, 
    property_id: str,
    include_expired: bool = False
):
    """Download a compliance pack PDF for a property.
    
    Requires Portfolio plan or higher. TEMP: gated by reports_pdf until Step 5 canonical key.
    """
    user = await client_route_guard(request)
    try:
        # TEMP Step 2: compliance_packs has no plan_registry key; gate by reports_pdf (Portfolio+)
        from services.plan_registry import plan_registry

        allowed, error_msg, error_details = await plan_registry.enforce_feature(
            user["client_id"],
            "reports_pdf"
        )
        if not allowed:
            detail = {
                "error_code": (error_details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
                "message": error_msg,
                "upgrade_required": True,
                **(error_details or {}),
            }
            detail["feature"] = "compliance_packs"  # preserve response shape
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

        from services.compliance_pack import compliance_pack_service
        
        pdf_bytes = await compliance_pack_service.generate_compliance_pack(
            property_id=property_id,
            client_id=user["client_id"],
            include_expired=include_expired,
            requested_by=user["portal_user_id"],
            requested_by_role=user.get("role")
        )
        
        # Get property for filename
        db = database.get_db()
        property_doc = await db.properties.find_one(
            {"property_id": property_id},
            {"_id": 0, "nickname": 1, "postcode": 1}
        )
        
        filename = f"compliance_pack_{property_doc.get('postcode', property_id)}.pdf"
        if property_doc and property_doc.get('nickname'):
            filename = f"compliance_pack_{property_doc['nickname'].replace(' ', '_')}.pdf"
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Compliance pack download error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate compliance pack"
        )


@router.post("/tenants/invite")
async def invite_tenant(request: Request):
    """
    Invite a tenant to view property compliance status.
    
    Creates a ROLE_TENANT user with read-only access.
    Gated: Portfolio and Professional only (tenant_portal).
    """
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "tenant_portal")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "tenant_portal", "upgrade_required": True}
        )
    db = database.get_db()
    
    # Only CLIENT_ADMIN can invite tenants
    if user.get("role") not in ["ROLE_CLIENT_ADMIN", "ROLE_ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only client admins can invite tenants"
        )
    
    try:
        body = await request.json()
        email = body.get("email")
        full_name = body.get("full_name", "")
        property_ids = body.get("property_ids", [])  # Optional: specific properties
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required"
            )
        
        # Check if tenant already exists (auth_email is used for login)
        email_lower = email.strip().lower()
        existing = await db.portal_users.find_one({
            "$or": [{"auth_email": email_lower}, {"email": email_lower}]
        })
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        # Build tenant and token in memory; send email first so we only persist on success
        import uuid
        from datetime import datetime, timezone, timedelta
        from auth import generate_secure_token, hash_token
        
        tenant_id = str(uuid.uuid4())
        tenant_user = {
            "portal_user_id": tenant_id,
            "client_id": user["client_id"],
            "auth_email": email_lower,
            "email": email_lower,
            "full_name": full_name,
            "role": "ROLE_TENANT",
            "status": "INVITED",
            "password_status": "NOT_SET",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "invited_by": user["portal_user_id"]
        }
        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        token_doc = {
            "token_hash": token_hash,
            "portal_user_id": tenant_id,
            "client_id": user["client_id"],
            "expires_at": expires_at.isoformat(),
        }
        from utils.public_app_url import get_frontend_base_url
        base = get_frontend_base_url().rstrip("/")
        invite_url = f"{base}/set-password?token={raw_token}"
        login_url = f"{base}/login/client"
        
        from services.notification_orchestrator import notification_orchestrator
        idempotency_key = f"{tenant_id}_TENANT_INVITE"
        result = await notification_orchestrator.send(
            template_key="TENANT_INVITE",
            client_id=user["client_id"],
            context={
                "recipient": email,
                "tenant_name": full_name or "there",
                "setup_link": invite_url,
                "login_url": login_url,
                "subject": "You've been invited to view property compliance",
            },
            idempotency_key=idempotency_key,
            event_type="tenant_invite",
        )
        
        if result.outcome == "blocked":
            reason = result.block_reason or "Email provider not configured"
            if reason == "BLOCKED_PROVIDER_NOT_CONFIGURED":
                reason = "Email provider (Postmark) is not configured. Set POSTMARK_SERVER_TOKEN to send invite emails."
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Invitation email could not be sent: {reason}",
            )
        if result.outcome == "failed":
            msg = result.error_message or "Email delivery failed"
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Invitation email failed to deliver: {msg}",
            )
        if result.outcome == "duplicate_ignored":
            return {
                "message": "An invitation was already sent to this email recently. If they did not receive it, check spam or resend from Tenant Management.",
                "tenant_id": tenant_id,
                "email": email,
                "invite_sent": False,
                "duplicate": True,
            }
        if result.outcome != "sent":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invitation email could not be sent",
            )
        
        # Email sent successfully; persist tenant and token
        await db.portal_users.insert_one(tenant_user)
        await db.password_tokens.insert_one(token_doc)
        if property_ids:
            for prop_id in property_ids:
                prop = await db.properties.find_one({
                    "property_id": prop_id,
                    "client_id": user["client_id"]
                })
                if prop:
                    await db.tenant_assignments.insert_one({
                        "tenant_id": tenant_id,
                        "property_id": prop_id,
                        "assigned_at": datetime.now(timezone.utc).isoformat(),
                        "assigned_by": user["portal_user_id"]
                    })
        
        logger.info(f"Tenant invited: {email} by {user['email']}")
        return {
            "message": "Tenant invited successfully",
            "tenant_id": tenant_id,
            "email": email,
            "invite_sent": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tenant invite error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invite tenant"
        )


@router.get("/tenants")
async def list_tenants(request: Request):
    """List all tenants invited by this client. Gated: Portfolio+ (tenant_portal)."""
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "tenant_portal")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "tenant_portal", "upgrade_required": True}
        )
    db = database.get_db()
    
    try:
        tenants = await db.portal_users.find(
            {
                "client_id": user["client_id"],
                "role": "ROLE_TENANT"
            },
            {"_id": 0, "password_hash": 0}
        ).to_list(100)
        
        # Get property assignments
        tenant_ids = [t["portal_user_id"] for t in tenants]
        assignments = await db.tenant_assignments.find(
            {"tenant_id": {"$in": tenant_ids}},
            {"_id": 0}
        ).to_list(1000)
        
        # Build assignment map
        assignment_map = {}
        for a in assignments:
            if a["tenant_id"] not in assignment_map:
                assignment_map[a["tenant_id"]] = []
            assignment_map[a["tenant_id"]].append(a["property_id"])
        
        # Add assignments to tenant data
        for tenant in tenants:
            tenant["assigned_properties"] = assignment_map.get(tenant["portal_user_id"], [])
        
        return {"tenants": tenants}
    
    except Exception as e:
        logger.error(f"List tenants error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tenants"
        )


@router.get("/tenant-messages")
async def list_tenant_messages(request: Request):
    """List messages from tenants to this client (landlord). Gated: tenant_portal."""
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "tenant_portal")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "tenant_portal", "upgrade_required": True}
        )
    db = database.get_db()
    cursor = db.tenant_messages.find(
        {"client_id": user["client_id"]},
        {"_id": 0, "message_id": 1, "tenant_name": 1, "tenant_email": 1, "property_id": 1, "property_address": 1, "subject": 1, "message": 1, "created_at": 1},
    ).sort("created_at", -1)
    messages = await cursor.to_list(200)
    for m in messages:
        if m.get("created_at"):
            m["created_at"] = m["created_at"].isoformat()
    return {"messages": messages}


@router.get("/tenant-requests")
async def list_tenant_requests(request: Request):
    """List certificate requests from tenants for this client. Gated: tenant_portal."""
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "tenant_portal")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "tenant_portal", "upgrade_required": True}
        )
    db = database.get_db()
    cursor = db.tenant_requests.find(
        {"client_id": user["client_id"]},
        {
            "_id": 0,
            "request_id": 1,
            "tenant_name": 1,
            "tenant_email": 1,
            "property_id": 1,
            "property_address": 1,
            "certificate_type": 1,
            "requirement_code": 1,
            "requirement_id": 1,
            "linked_work_order_id": 1,
            "message": 1,
            "status": 1,
            "created_at": 1,
        },
    ).sort("created_at", -1)
    requests_list = await cursor.to_list(200)
    for r in requests_list:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
    return {"requests": requests_list}


class TenantRequestStartComplianceJobBody(BaseModel):
    allow_duplicate: bool = False


@router.post("/tenant-requests/{request_id}/start-compliance-job")
async def start_tenant_request_compliance_job(
    request: Request,
    request_id: str,
    body: Optional[TenantRequestStartComplianceJobBody] = None,
):
    """Create a COMPLIANCE work order directly from a tenant request (real execution, audited)."""
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry

    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "tenant_portal")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "tenant_portal", "upgrade_required": True},
        )
    if user.get("role") not in ["ROLE_CLIENT", "ROLE_CLIENT_ADMIN", "ROLE_ADMIN"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    from services import tenant_request_compliance_service as trc

    try:
        return await trc.start_compliance_job_from_tenant_request(
            client_id=user["client_id"],
            tenant_request_id=request_id,
            actor_portal_user_id=user.get("portal_user_id"),
            actor_role=user.get("role"),
            allow_duplicate=bool((body or TenantRequestStartComplianceJobBody()).allow_duplicate),
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("tenant request -> compliance job failed: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to start compliance job")


@router.patch("/tenant-requests/{request_id}")
async def update_tenant_request_status(request: Request, request_id: str):
    """Update a certificate request status (IN_PROGRESS, DONE, DECLINED). Gated: tenant_portal."""
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "tenant_portal")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "tenant_portal", "upgrade_required": True}
        )
    if user.get("role") not in ["ROLE_CLIENT", "ROLE_CLIENT_ADMIN", "ROLE_ADMIN"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    try:
        body = await request.json()
    except Exception:
        body = {}
    status_value = (body.get("status") or "").strip().upper()
    if status_value not in ("IN_PROGRESS", "DONE", "DECLINED"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status must be one of: IN_PROGRESS, DONE, DECLINED")
    db = database.get_db()
    doc = await db.tenant_requests.find_one({"request_id": request_id, "client_id": user["client_id"]})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    from datetime import datetime, timezone
    from utils.audit import create_audit_log
    from models import AuditAction
    now = datetime.now(timezone.utc)
    req_id = (doc.get("requirement_id") or "").strip()
    req_satisfied = False
    verified_evidence_exists = False
    completed_compliance_job_exists = False
    if status_value == "DONE":
        await create_audit_log(
            action=AuditAction.TENANT_REQUEST_RESOLUTION_ATTEMPT,
            client_id=user["client_id"],
            actor_id=user.get("portal_user_id"),
            resource_type="tenant_request",
            resource_id=request_id,
            metadata={"attempted_status": "DONE", "requirement_id": req_id or None},
        )
        if req_id:
            req = await db.requirements.find_one(
                {"client_id": user["client_id"], "requirement_id": req_id},
                {"_id": 0, "status": 1},
            )
            req_satisfied = ((req or {}).get("status") or "").strip().upper() in ("COMPLIANT", "VALID")
            verified_evidence_exists = (
                await db.documents.count_documents(
                    {
                        "client_id": user["client_id"],
                        "requirement_id": req_id,
                        "status": "VERIFIED",
                    }
                )
                > 0
            )
            completed_compliance_job_exists = (
                await db.work_orders.count_documents(
                    {
                        "client_id": user["client_id"],
                        "work_order_kind": "COMPLIANCE",
                        "status": {"$in": ["COMPLETED", "VERIFIED"]},
                        "$or": [
                            {"linked_property_requirement_id": req_id},
                            {"requirement_code": doc.get("requirement_code")},
                        ],
                    }
                )
                > 0
            )
        if not (req_satisfied or verified_evidence_exists or completed_compliance_job_exists):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot mark as DONE without resolving the underlying compliance requirement",
            )

    await db.tenant_requests.update_one(
        {"request_id": request_id, "client_id": user["client_id"]},
        {"$set": {"status": status_value, "updated_at": now}},
    )
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        client_id=user["client_id"],
        actor_id=user.get("portal_user_id"),
        resource_type="tenant_request",
        resource_id=request_id,
        metadata={"status": status_value, "actor_role": user.get("role"), "requirement_id": req_id or None},
    )
    if status_value == "IN_PROGRESS" and req_id:
        await create_audit_log(
            action=AuditAction.REQUIREMENT_ACTION_TRIGGERED,
            client_id=user["client_id"],
            actor_id=user.get("portal_user_id"),
            resource_type="requirement",
            resource_id=req_id,
            metadata={"source": "tenant_request", "request_id": request_id, "actor_role": user.get("role")},
        )
    if status_value == "DONE":
        await create_audit_log(
            action=AuditAction.TENANT_REQUEST_RESOLVED,
            client_id=user["client_id"],
            actor_id=user.get("portal_user_id"),
            resource_type="tenant_request",
            resource_id=request_id,
            metadata={
                "status": "DONE",
                "requirement_id": req_id or None,
                "req_satisfied": req_satisfied,
                "verified_evidence_exists": verified_evidence_exists,
                "completed_compliance_job_exists": completed_compliance_job_exists,
            },
        )
    return {"request_id": request_id, "status": status_value}


@router.post("/tenants/{tenant_id}/assign-property")
async def assign_tenant_to_property(request: Request, tenant_id: str):
    """Assign a tenant to a property. Gated: Portfolio+ (tenant_portal)."""
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "tenant_portal")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "tenant_portal", "upgrade_required": True}
        )
    db = database.get_db()
    
    if user.get("role") not in ["ROLE_CLIENT_ADMIN", "ROLE_ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only client admins can manage tenant assignments"
        )
    
    try:
        body = await request.json()
        property_id = body.get("property_id")
        
        if not property_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="property_id is required"
            )
        
        # Verify tenant belongs to this client
        tenant = await db.portal_users.find_one({
            "portal_user_id": tenant_id,
            "client_id": user["client_id"],
            "role": "ROLE_TENANT"
        })
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Verify property belongs to this client
        prop = await db.properties.find_one({
            "property_id": property_id,
            "client_id": user["client_id"]
        })
        
        if not prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found"
            )
        
        # Check if already assigned
        existing = await db.tenant_assignments.find_one({
            "tenant_id": tenant_id,
            "property_id": property_id
        })
        
        if existing:
            return {"message": "Tenant already assigned to this property"}
        
        # Create assignment
        from datetime import datetime, timezone
        await db.tenant_assignments.insert_one({
            "tenant_id": tenant_id,
            "property_id": property_id,
            "assigned_at": datetime.now(timezone.utc).isoformat(),
            "assigned_by": user["portal_user_id"]
        })
        
        logger.info(f"Tenant {tenant_id} assigned to property {property_id}")
        
        return {
            "message": "Tenant assigned to property",
            "tenant_id": tenant_id,
            "property_id": property_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Assign tenant error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign tenant"
        )


@router.delete("/tenants/{tenant_id}/unassign-property/{property_id}")
async def unassign_tenant_from_property(request: Request, tenant_id: str, property_id: str):
    """Remove a tenant's assignment to a property. Gated: Portfolio+ (tenant_portal)."""
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "tenant_portal")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "tenant_portal", "upgrade_required": True}
        )
    db = database.get_db()
    
    if user.get("role") not in ["ROLE_CLIENT_ADMIN", "ROLE_ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only client admins can manage tenant assignments"
        )
    
    try:
        # Verify tenant belongs to this client
        tenant = await db.portal_users.find_one({
            "portal_user_id": tenant_id,
            "client_id": user["client_id"],
            "role": "ROLE_TENANT"
        })
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Remove assignment
        result = await db.tenant_assignments.delete_one({
            "tenant_id": tenant_id,
            "property_id": property_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found"
            )
        
        logger.info(f"Tenant {tenant_id} unassigned from property {property_id}")
        
        return {"message": "Tenant unassigned from property"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unassign tenant error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unassign tenant"
        )


@router.delete("/tenants/{tenant_id}")
async def revoke_tenant_access(request: Request, tenant_id: str):
    """Revoke a tenant's access entirely (disable account). Gated: Portfolio+ (tenant_portal)."""
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "tenant_portal")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "tenant_portal", "upgrade_required": True}
        )
    db = database.get_db()
    
    if user.get("role") not in ["ROLE_CLIENT_ADMIN", "ROLE_ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only client admins can revoke tenant access"
        )
    
    try:
        # Verify tenant belongs to this client
        tenant = await db.portal_users.find_one({
            "portal_user_id": tenant_id,
            "client_id": user["client_id"],
            "role": "ROLE_TENANT"
        })
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Disable the tenant account
        await db.portal_users.update_one(
            {"portal_user_id": tenant_id},
            {"$set": {"status": "DISABLED"}}
        )
        
        # Remove all property assignments
        await db.tenant_assignments.delete_many({"tenant_id": tenant_id})
        
        logger.info(f"Tenant {tenant_id} access revoked by {user['email']}")
        
        return {"message": "Tenant access revoked"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Revoke tenant error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke tenant access"
        )


@router.post("/tenants/{tenant_id}/resend-invite")
async def resend_tenant_invite(request: Request, tenant_id: str):
    """Resend invitation email to a tenant. Gated: Portfolio+ (tenant_portal)."""
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "tenant_portal")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "tenant_portal", "upgrade_required": True}
        )
    db = database.get_db()
    
    if user.get("role") not in ["ROLE_CLIENT_ADMIN", "ROLE_ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only client admins can resend invites"
        )
    
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        
        # Verify tenant belongs to this client
        tenant = await db.portal_users.find_one({
            "portal_user_id": tenant_id,
            "client_id": user["client_id"],
            "role": "ROLE_TENANT"
        })
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        if tenant.get("status") == "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant has already set up their account"
            )
        
        # Create new password token (same schema as set_password: token_hash, client_id)
        from datetime import datetime, timezone, timedelta
        from auth import generate_secure_token, hash_token
        
        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        token_doc = {
            "token_hash": token_hash,
            "portal_user_id": tenant_id,
            "client_id": user["client_id"],
            "expires_at": expires_at.isoformat(),
        }
        await db.password_tokens.insert_one(token_doc)
        
        from utils.public_app_url import get_frontend_base_url
        from services.notification_orchestrator import notification_orchestrator
        base = get_frontend_base_url().rstrip("/")
        invite_url = f"{base}/set-password?token={raw_token}"
        login_url = f"{base}/login/client"
        idempotency_key = f"{tenant_id}_TENANT_INVITE_resend"
        await notification_orchestrator.send(
            template_key="TENANT_INVITE",
            client_id=user["client_id"],
            context={
                "recipient": tenant.get("auth_email") or tenant.get("email"),
                "tenant_name": tenant.get("full_name", "there"),
                "setup_link": invite_url,
                "login_url": login_url,
                "subject": "Reminder: Set up your tenant portal access",
            },
            idempotency_key=idempotency_key,
            event_type="tenant_invite_resend",
        )
        logger.info(f"Tenant invite resent to {tenant.get('auth_email') or tenant.get('email', '')}")
        
        return {"message": "Invitation resent successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend invite error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resend invitation"
        )


# ============================================================================
# BRANDING SETTINGS (White-Label)
# ============================================================================

DATA_DIR = resolve_data_dir()
BRANDING_LOGOS_PATH = Path(DATA_DIR) / "data" / "branding_logos"
BRANDING_LOGOS_PATH.mkdir(parents=True, exist_ok=True)
BRANDING_LOGO_MAX_BYTES = 2 * 1024 * 1024  # 2MB
BRANDING_LOGO_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

def _branding_logo_path(client_id: str, ext: str) -> Path:
    return BRANDING_LOGOS_PATH / f"{client_id}{ext}"

@router.get("/branding")
async def get_branding_settings(request: Request):
    """Get the client's branding settings.
    
    Returns current branding configuration for white-label customization.
    Plan gating: Requires Portfolio plan (PLAN_6_15) for full customization.
    """
    from services.plan_registry import plan_registry
    from datetime import datetime, timezone

    user = await client_route_guard(request)
    try:
        db = database.get_db()
        client_id = user["client_id"]

        # Canonical: white_label -> white_label_reports (plan_registry)
        allowed, error_msg, error_details = await plan_registry.enforce_feature(
            client_id,
            "white_label_reports"
        )
        
        # Get existing branding settings
        branding = await db.branding_settings.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        # Get client info for defaults
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "company_name": 1, "email": 1, "phone": 1}
        )
        
        # Return defaults if no branding set
        if not branding:
            branding = {
                "client_id": client_id,
                "company_name": client.get("company_name"),
                "logo_url": None,
                "favicon_url": None,
                "primary_color": "#0B1D3A",
                "secondary_color": "#00B8A9",
                "accent_color": "#FFB800",
                "text_color": "#1F2937",
                "report_header_text": None,
                "report_footer_text": None,
                "include_pleerity_branding": True,
                "white_label_enabled": False,
                "email_from_name": None,
                "email_reply_to": client.get("email"),
                "contact_email": client.get("email"),
                "contact_phone": client.get("phone"),
                "website_url": None,
                "is_default": True
            }
        else:
            branding.setdefault("white_label_enabled", False)

        from services.branding_resolver_service import resolve_branding, BrandingContext

        rb = await resolve_branding(client_id, BrandingContext.CLIENT_PORTAL_UI)
        branding["resolved_branding"] = rb.to_portal_dict()
        
        # Add feature availability info
        branding["feature_enabled"] = allowed
        if not allowed:
            branding["upgrade_message"] = error_msg
            branding["upgrade_required"] = True
        
        return branding
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get branding settings error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load branding settings"
        )


@router.put("/branding")
async def update_branding_settings(request: Request):
    """Update the client's branding settings.
    
    Plan gating: Requires Professional plan (white_label_reports).
    """
    from services.plan_registry import plan_registry
    from models import AuditAction
    from utils.audit import create_audit_log
    from datetime import datetime, timezone

    user = await client_route_guard(request)
    body = await request.json()
    try:
        db = database.get_db()
        client_id = user["client_id"]

        # Canonical: white_label -> white_label_reports (plan_registry)
        allowed, error_msg, error_details = await plan_registry.enforce_feature(
            client_id,
            "white_label_reports"
        )
        if not allowed:
            detail = {
                "error_code": (error_details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
                "message": error_msg,
                "upgrade_required": True,
                **(error_details or {}),
            }
            detail["feature"] = "white_label"  # preserve response shape
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

        # Allowed fields to update
        allowed_fields = [
            "company_name", "logo_url", "favicon_url",
            "primary_color", "secondary_color", "accent_color", "text_color",
            "report_header_text", "report_footer_text", "include_pleerity_branding",
            "white_label_enabled",
            "email_from_name", "email_reply_to",
            "contact_email", "contact_phone", "website_url"
        ]
        
        # Build update document
        update_doc = {
            "client_id": client_id,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        for field in allowed_fields:
            if field in body:
                # Validate colors
                if field.endswith("_color") and body[field]:
                    color = body[field]
                    if not (color.startswith("#") and len(color) in [4, 7]):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid color format for {field}. Use hex format (e.g., #0B1D3A)"
                        )
                update_doc[field] = body[field]

        if body.get("white_label_enabled") is True:
            existing = await db.branding_settings.find_one({"client_id": client_id}, {"_id": 0}) or {}
            merged = {**existing, **update_doc}
            client_row = await db.clients.find_one(
                {"client_id": client_id},
                {"_id": 0, "company_name": 1, "full_name": 1, "email": 1},
            )
            co = (merged.get("company_name") or (client_row or {}).get("company_name") or (client_row or {}).get("full_name") or "").strip()
            em = (merged.get("contact_email") or (client_row or {}).get("email") or "").strip()
            ext = merged.get("logo_upload_ext")
            logo_ok = False
            if ext and str(ext).startswith("."):
                p = _branding_logo_path(client_id, ext)
                logo_ok = p.is_file()
            if not co:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "INCOMPLETE_BRANDING", "message": "Company name is required to enable white-label."},
                )
            if not em:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "INCOMPLETE_BRANDING", "message": "Support contact email is required to enable white-label."},
                )
            if not logo_ok:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "INCOMPLETE_BRANDING", "message": "Upload a logo before enabling white-label."},
                )
        
        # Upsert branding settings
        await db.branding_settings.update_one(
            {"client_id": client_id},
            {"$set": update_doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.SETTINGS_UPDATED,
            client_id=client_id,
            actor_id=user.get("portal_user_id"),
            metadata={"updated_fields": [k for k in update_doc.keys() if k not in ["client_id", "updated_at"]]}
        )
        
        logger.info(f"Branding settings updated for client {client_id}")
        
        # Return updated settings
        updated = await db.branding_settings.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        updated["feature_enabled"] = True
        from services.branding_resolver_service import resolve_branding, BrandingContext

        rb = await resolve_branding(client_id, BrandingContext.CLIENT_PORTAL_UI)
        updated["resolved_branding"] = rb.to_portal_dict()
        
        return updated
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update branding settings error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update branding settings"
        )


@router.post("/branding/reset")
async def reset_branding_settings(request: Request):
    """Reset branding settings to defaults.
    
    Plan gating: Requires Professional plan (white_label_reports).
    """
    from services.plan_registry import plan_registry
    from models import AuditAction
    from utils.audit import create_audit_log

    user = await client_route_guard(request)
    try:
        db = database.get_db()
        client_id = user["client_id"]

        # Canonical: white_label -> white_label_reports (plan_registry)
        allowed, error_msg, error_details = await plan_registry.enforce_feature(
            client_id,
            "white_label_reports"
        )
        if not allowed:
            detail = {
                "error_code": (error_details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
                "message": error_msg,
                "upgrade_required": True,
                **(error_details or {}),
            }
            detail["feature"] = "white_label"  # preserve response shape
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

        # Remove uploaded logo file if any
        for ext in [".png", ".jpg", ".webp"]:
            path = _branding_logo_path(client_id, ext)
            if path.is_file():
                try:
                    path.unlink()
                except OSError:
                    pass

        # Delete branding settings
        result = await db.branding_settings.delete_one({"client_id": client_id})
        
        # Audit log
        await create_audit_log(
            action=AuditAction.SETTINGS_UPDATED,
            client_id=client_id,
            actor_id=user.get("portal_user_id"),
            metadata={"action": "branding_reset"}
        )
        
        logger.info(f"Branding settings reset for client {client_id}")
        
        return {"message": "Branding settings reset to defaults", "deleted": result.deleted_count > 0}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset branding settings error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset branding settings"
        )


@router.get("/branding/logo")
async def get_branding_logo(request: Request):
    """Serve the client's uploaded branding logo (for use in reports and preview)."""
    user = await client_route_guard(request)
    db = database.get_db()
    client_id = user["client_id"]
    branding = await db.branding_settings.find_one(
        {"client_id": client_id},
        {"_id": 0, "logo_upload_ext": 1}
    )
    exts = [branding.get("logo_upload_ext")] if branding and branding.get("logo_upload_ext") else [".png", ".jpg", ".webp"]
    for ext in exts:
        if not ext or not ext.startswith("."):
            continue
        path = _branding_logo_path(client_id, ext)
        if path.is_file():
            media = "image/jpeg" if ext == ".jpg" else ("image/png" if ext == ".png" else "image/webp")
            return FileResponse(path=str(path), media_type=media)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No logo uploaded")


@router.post("/branding/logo")
async def upload_branding_logo(request: Request, file: UploadFile = File(...)):
    """Upload a logo file for branding. Replaces existing. Returns logo_url to use in settings."""
    from services.plan_registry import plan_registry

    user = await client_route_guard(request)
    db = database.get_db()
    client_id = user["client_id"]

    allowed, error_msg, error_details = await plan_registry.enforce_feature(
        client_id,
        "white_label_reports"
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_msg or "Upgrade required for white-label branding"
        )

    if not file.content_type or file.content_type.lower() not in BRANDING_LOGO_ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Allowed types: JPEG, PNG, WebP"
        )
    content = await file.read()
    if len(content) > BRANDING_LOGO_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large (max 2MB)"
        )
    ext = ".jpg" if "jpeg" in (file.content_type or "").lower() else (".png" if "png" in (file.content_type or "").lower() else ".webp")
    # Remove any previous logo file(s)
    for e in [".png", ".jpg", ".webp"]:
        p = _branding_logo_path(client_id, e)
        if p.is_file():
            try:
                p.unlink()
            except OSError:
                pass
    path = _branding_logo_path(client_id, ext)
    path.write_bytes(content)

    base_url = str(request.base_url).rstrip("/")
    logo_url = f"{base_url}/api/client/branding/logo"
    now = datetime.now(timezone.utc).isoformat()
    await db.branding_settings.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "logo_url": logo_url,
                "logo_upload_ext": ext,
                "updated_at": now,
            },
            "$setOnInsert": {"client_id": client_id, "created_at": now},
        },
        upsert=True,
    )
    logger.info(f"Branding logo uploaded for client {client_id}")
    return {"logo_url": logo_url}


@router.get("/branding/preview")
async def get_branding_preview(request: Request):
    """Generate a sample PDF using current branding (for preview before saving)."""
    from services.plan_registry import plan_registry
    from services.professional_reports import professional_report_generator

    user = await client_route_guard(request)
    client_id = user["client_id"]

    allowed, error_msg, _ = await plan_registry.enforce_feature(
        client_id,
        "white_label_reports"
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_msg or "Upgrade required for white-label branding"
        )

    db = database.get_db()
    branding_row = await db.branding_settings.find_one(
        {"client_id": client_id},
        {"_id": 0, "logo_upload_ext": 1}
    )
    logo_path = None
    if branding_row and branding_row.get("logo_upload_ext"):
        path = _branding_logo_path(client_id, branding_row["logo_upload_ext"])
        if path.is_file():
            logo_path = str(path)

    try:
        pdf_buffer = await professional_report_generator.generate_branding_preview_pdf(
            client_id, logo_path=logo_path
        )
    except Exception as e:
        logger.error(f"Branding preview error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate preview"
        )
    pdf_buffer.seek(0)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=branding_preview.pdf"},
    )

