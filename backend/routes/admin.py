from fastapi import APIRouter, HTTPException, Request, Depends, status, Query, Body
from pydantic import BaseModel, EmailStr
from typing import Optional
from database import database
from middleware import admin_route_guard, require_owner, require_owner_or_admin
from models import AuditAction, EmailTemplateAlias, PasswordToken, UserRole, UserStatus, PasswordStatus, ProvisioningJobStatus
from utils.audit import create_audit_log
from datetime import datetime, timezone, timedelta
import logging
import uuid
import json
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(admin_route_guard)])


# Request models for admin invite
class AdminInviteRequest(BaseModel):
    email: EmailStr
    full_name: str


class ValidateComplianceScoreRequest(BaseModel):
    """Optional body for validate-compliance-score: fix=true to repair stored score."""
    fix: bool = False


@router.get("/dashboard", dependencies=[Depends(require_owner_or_admin)])
async def get_admin_dashboard(request: Request):
    """Get admin dashboard data with enhanced statistics."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Basic stats
        total_clients = await db.clients.count_documents({})
        active_clients = await db.clients.count_documents({"subscription_status": "ACTIVE"})
        pending_clients = await db.clients.count_documents({"subscription_status": "PENDING"})
        
        # Enhanced stats
        provisioned_clients = await db.clients.count_documents({"onboarding_status": "PROVISIONED"})
        failed_provisioning = await db.clients.count_documents({"onboarding_status": "FAILED"})
        
        # Property stats
        total_properties = await db.properties.count_documents({})
        
        # Compliance overview
        properties = await db.properties.find({}, {"_id": 0, "compliance_status": 1}).to_list(10000)
        compliance_breakdown = {
            "GREEN": sum(1 for p in properties if p.get("compliance_status") == "GREEN"),
            "AMBER": sum(1 for p in properties if p.get("compliance_status") == "AMBER"),
            "RED": sum(1 for p in properties if p.get("compliance_status") == "RED")
        }
        
        # Recent activity (last 7 days)
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        recent_signups = await db.clients.count_documents({
            "created_at": {"$gte": seven_days_ago}
        })
        
        # Unverified documents (UPLOADED status) for admin verification workflow badge
        unverified_documents_count = await db.documents.count_documents({"status": "UPLOADED"})
        
        return {
            "stats": {
                "total_clients": total_clients,
                "active_clients": active_clients,
                "pending_clients": pending_clients,
                "provisioned_clients": provisioned_clients,
                "failed_provisioning": failed_provisioning,
                "total_properties": total_properties,
                "recent_signups_7d": recent_signups,
                "unverified_documents_count": unverified_documents_count,
            },
            "compliance_overview": compliance_breakdown
        }
    
    except Exception as e:
        logger.error(f"Admin dashboard error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load admin dashboard"
        )


@router.get("/documents/pending-verification", dependencies=[Depends(require_owner_or_admin)])
async def list_pending_verification_documents(
    request: Request,
    hours: int = Query(24, ge=1, le=720),
    client_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """List documents with status UPLOADED older than X hours (default 24), filterable by client_id. Paginated."""
    await admin_route_guard(request)
    db = database.get_db()
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        query = {"status": "UPLOADED", "uploaded_at": {"$lte": cutoff}}
        if client_id:
            query["client_id"] = client_id
        total = await db.documents.count_documents(query)
        cursor = db.documents.find(
            query,
            {"_id": 0, "document_id": 1, "client_id": 1, "property_id": 1, "requirement_id": 1, "uploaded_at": 1}
        ).sort("uploaded_at", 1).skip(skip).limit(limit)
        items = await cursor.to_list(limit)
        returned = len(items)
        return {
            "documents": items,
            "total": total,
            "returned": returned,
            "has_more": skip + returned < total,
            "hours": hours,
            "client_id_filter": client_id,
        }
    except Exception as e:
        logger.error(f"Pending verification list error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list pending verification documents"
        )


@router.get("/email-delivery", dependencies=[Depends(require_owner_or_admin)])
async def get_email_delivery(
    request: Request,
    template_alias: Optional[str] = Query(None),
    status: Optional[str] = Query(None, regex="^(sent|failed|skipped)$"),
    client_id: Optional[str] = Query(None),
    since_hours: int = Query(72, ge=1, le=720),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """Read-only email delivery view (message_logs + EMAIL_SKIPPED_NO_RECIPIENT audit). No recipient in response."""
    await admin_route_guard(request)
    db = database.get_db()
    try:
        since = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()
        status_order = {"failed": 0, "skipped": 1, "sent": 2}

        items_from_msg = []
        count_msg = 0
        if status is None or status in ("sent", "failed"):
            q = {"created_at": {"$gte": since}, "status": {"$in": ["sent", "failed"]}}
            if status:
                q["status"] = status
            if template_alias:
                q["template_alias"] = template_alias
            if client_id:
                q["client_id"] = client_id
            count_msg = await db.message_logs.count_documents(q)
            cursor = (
                db.message_logs.find(
                    q,
                    {
                        "_id": 0,
                        "created_at": 1,
                        "template_alias": 1,
                        "status": 1,
                        "client_id": 1,
                        "message_id": 1,
                        "provider_error_type": 1,
                        "provider_error_code": 1,
                    },
                )
                .sort("created_at", -1)
                .limit(2000)
            )
            raw = await cursor.to_list(2000)
            for r in raw:
                items_from_msg.append({
                    "created_at": r.get("created_at"),
                    "template_alias": r.get("template_alias"),
                    "status": r.get("status"),
                    "client_id": r.get("client_id"),
                    "message_id": r.get("message_id"),
                    "provider_error_type": r.get("provider_error_type"),
                    "provider_error_code": r.get("provider_error_code"),
                })

        items_from_audit = []
        count_audit = 0
        if status is None or status == "skipped":
            q = {"action": AuditAction.EMAIL_SKIPPED_NO_RECIPIENT.value, "timestamp": {"$gte": since}}
            if client_id:
                q["client_id"] = client_id
            if template_alias:
                q["metadata.template"] = template_alias
            count_audit = await db.audit_logs.count_documents(q)
            cursor = (
                db.audit_logs.find(
                    q,
                    {"_id": 0, "timestamp": 1, "client_id": 1, "metadata": 1},
                )
                .sort("timestamp", -1)
                .limit(2000)
            )
            raw = await cursor.to_list(2000)
            for r in raw:
                meta = r.get("metadata") or {}
                template = meta.get("template")
                items_from_audit.append({
                    "created_at": r.get("timestamp"),
                    "template_alias": template,
                    "status": "skipped",
                    "client_id": r.get("client_id"),
                    "message_id": None,
                    "provider_error_type": None,
                    "provider_error_code": None,
                })

        total = count_msg + count_audit
        merged = items_from_msg + items_from_audit
        def _sort_key(x):
            ts = x.get("created_at")
            if ts is None:
                return (status_order.get(x.get("status"), 3), 0.0)
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            else:
                ts = getattr(ts, "timestamp", lambda: 0)() if hasattr(ts, "timestamp") else 0
            return (status_order.get(x.get("status"), 3), -ts)
        merged.sort(key=_sort_key)
        page = merged[skip : skip + limit]
        returned = len(page)
        return {
            "total": total,
            "returned": returned,
            "has_more": skip + returned < total,
            "items": page,
        }
    except Exception as e:
        logger.error(f"Email delivery list error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load email delivery list",
        )


@router.get("/search")
async def global_search(request: Request, q: str = "", limit: int = 20):
    """
    Global search across clients by CRN, email, name, or postcode.
    Returns matching clients with their key details.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    if not q or len(q.strip()) < 2:
        return {"results": [], "query": q, "total": 0}
    
    search_term = q.strip()
    
    try:
        # Build search conditions
        # 1. Exact CRN match (case-insensitive)
        # 2. Email contains (case-insensitive)
        # 3. Name contains (case-insensitive)
        # 4. Company name contains
        search_regex = {"$regex": search_term, "$options": "i"}
        
        # Search clients
        client_query = {
            "$or": [
                {"customer_reference": search_regex},
                {"email": search_regex},
                {"full_name": search_regex},
                {"company_name": search_regex}
            ]
        }
        
        clients_cursor = db.clients.find(
            client_query,
            {"_id": 0, "client_id": 1, "customer_reference": 1, "full_name": 1, 
             "email": 1, "company_name": 1, "subscription_status": 1, 
             "onboarding_status": 1, "billing_plan": 1, "created_at": 1}
        ).limit(limit)
        
        clients = await clients_cursor.to_list(limit)
        
        # Also search by postcode in properties and return linked clients
        postcode_search = search_term.upper().replace(" ", "")
        properties_with_postcode = await db.properties.find(
            {"postcode": {"$regex": postcode_search, "$options": "i"}},
            {"_id": 0, "client_id": 1, "postcode": 1, "address_line_1": 1}
        ).to_list(50)
        
        # Get unique client IDs from postcode search
        postcode_client_ids = list(set(p["client_id"] for p in properties_with_postcode))
        existing_client_ids = [c["client_id"] for c in clients]
        
        # Fetch additional clients found via postcode
        new_client_ids = [cid for cid in postcode_client_ids if cid not in existing_client_ids]
        if new_client_ids:
            additional_clients = await db.clients.find(
                {"client_id": {"$in": new_client_ids}},
                {"_id": 0, "client_id": 1, "customer_reference": 1, "full_name": 1,
                 "email": 1, "company_name": 1, "subscription_status": 1,
                 "onboarding_status": 1, "billing_plan": 1, "created_at": 1}
            ).to_list(limit)
            
            # Mark these as found via postcode
            for c in additional_clients:
                matched_props = [p for p in properties_with_postcode if p["client_id"] == c["client_id"]]
                c["matched_via"] = "postcode"
                c["matched_postcode"] = matched_props[0]["postcode"] if matched_props else None
            
            clients.extend(additional_clients)
        
        # Log the search for audit trail
        await create_audit_log(
            action=AuditAction.ADMIN_SEARCH_PERFORMED,
            actor_id=user.get("portal_user_id"),
            actor_role=UserRole.ROLE_ADMIN,
            metadata={
                "search_query": search_term,
                "results_count": len(clients)
            }
        )
        
        return {
            "results": clients[:limit],
            "query": search_term,
            "total": len(clients)
        }
        
    except Exception as e:
        logger.error(f"Global search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )


@router.get("/statistics")
async def get_system_statistics(request: Request):
    """Get comprehensive system-wide compliance statistics."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Time periods
        now = datetime.now(timezone.utc)
        seven_days_ago = (now - timedelta(days=7)).isoformat()
        thirty_days_ago = (now - timedelta(days=30)).isoformat()
        ninety_days_ago = (now - timedelta(days=90)).isoformat()
        
        # === CLIENT STATISTICS ===
        total_clients = await db.clients.count_documents({})
        clients_by_status = {}
        for status in ["ACTIVE", "PENDING", "CANCELLED", "SUSPENDED"]:
            clients_by_status[status] = await db.clients.count_documents({"subscription_status": status})
        
        clients_by_onboarding = {}
        for status in ["PROVISIONED", "PENDING_PAYMENT", "INTAKE_COMPLETE", "FAILED"]:
            clients_by_onboarding[status] = await db.clients.count_documents({"onboarding_status": status})
        
        # New clients over time
        new_clients_7d = await db.clients.count_documents({"created_at": {"$gte": seven_days_ago}})
        new_clients_30d = await db.clients.count_documents({"created_at": {"$gte": thirty_days_ago}})
        new_clients_90d = await db.clients.count_documents({"created_at": {"$gte": ninety_days_ago}})
        
        # === PROPERTY STATISTICS ===
        total_properties = await db.properties.count_documents({})
        
        # Properties by type
        property_types = await db.properties.aggregate([
            {"$group": {"_id": "$property_type", "count": {"$sum": 1}}}
        ]).to_list(20)
        properties_by_type = {p["_id"]: p["count"] for p in property_types if p["_id"]}
        
        # Properties by compliance status
        compliance_statuses = await db.properties.aggregate([
            {"$group": {"_id": "$compliance_status", "count": {"$sum": 1}}}
        ]).to_list(10)
        properties_by_compliance = {c["_id"]: c["count"] for c in compliance_statuses if c["_id"]}
        
        # === REQUIREMENT STATISTICS ===
        total_requirements = await db.requirements.count_documents({})
        
        # Requirements by status
        req_statuses = await db.requirements.aggregate([
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]).to_list(10)
        requirements_by_status = {r["_id"]: r["count"] for r in req_statuses if r["_id"]}
        
        # Requirements by type
        req_types = await db.requirements.aggregate([
            {"$group": {"_id": "$requirement_type", "count": {"$sum": 1}}}
        ]).to_list(50)
        requirements_by_type = {r["_id"]: r["count"] for r in req_types if r["_id"]}
        
        # Upcoming expirations (next 30, 60, 90 days)
        thirty_days = (now + timedelta(days=30)).isoformat()
        sixty_days = (now + timedelta(days=60)).isoformat()
        ninety_days = (now + timedelta(days=90)).isoformat()
        
        expiring_30d = await db.requirements.count_documents({
            "due_date": {"$lte": thirty_days, "$gte": now.isoformat()},
            "status": {"$ne": "COMPLIANT"}
        })
        expiring_60d = await db.requirements.count_documents({
            "due_date": {"$lte": sixty_days, "$gte": now.isoformat()},
            "status": {"$ne": "COMPLIANT"}
        })
        expiring_90d = await db.requirements.count_documents({
            "due_date": {"$lte": ninety_days, "$gte": now.isoformat()},
            "status": {"$ne": "COMPLIANT"}
        })
        
        # Overdue requirements
        overdue_count = await db.requirements.count_documents({
            "due_date": {"$lt": now.isoformat()},
            "status": {"$in": ["PENDING", "EXPIRING_SOON"]}
        })
        
        # === DOCUMENT STATISTICS ===
        total_documents = await db.documents.count_documents({})
        
        # Documents by status
        doc_statuses = await db.documents.aggregate([
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]).to_list(10)
        documents_by_status = {d["_id"]: d["count"] for d in doc_statuses if d["_id"]}
        
        # AI analyzed documents
        ai_analyzed = await db.documents.count_documents({"ai_extraction.status": "completed"})
        
        # === EMAIL STATISTICS ===
        total_emails = await db.message_logs.count_documents({})
        emails_sent = await db.message_logs.count_documents({"status": "sent"})
        emails_failed = await db.message_logs.count_documents({"status": "failed"})
        
        # === RULE STATISTICS ===
        total_rules = await db.requirement_rules.count_documents({})
        active_rules = await db.requirement_rules.count_documents({"is_active": True})
        
        # === COMPLIANCE RATE ===
        if total_requirements > 0:
            compliant_count = requirements_by_status.get("COMPLIANT", 0)
            compliance_rate = round((compliant_count / total_requirements) * 100, 1)
        else:
            compliance_rate = 0
        
        return {
            "generated_at": now.isoformat(),
            "clients": {
                "total": total_clients,
                "by_subscription_status": clients_by_status,
                "by_onboarding_status": clients_by_onboarding,
                "new_last_7_days": new_clients_7d,
                "new_last_30_days": new_clients_30d,
                "new_last_90_days": new_clients_90d
            },
            "properties": {
                "total": total_properties,
                "by_type": properties_by_type,
                "by_compliance_status": properties_by_compliance
            },
            "requirements": {
                "total": total_requirements,
                "by_status": requirements_by_status,
                "by_type": requirements_by_type,
                "expiring_next_30_days": expiring_30d,
                "expiring_next_60_days": expiring_60d,
                "expiring_next_90_days": expiring_90d,
                "overdue": overdue_count,
                "compliance_rate_percent": compliance_rate
            },
            "documents": {
                "total": total_documents,
                "by_status": documents_by_status,
                "ai_analyzed": ai_analyzed
            },
            "emails": {
                "total": total_emails,
                "sent": emails_sent,
                "failed": emails_failed,
                "delivery_rate": round((emails_sent / total_emails * 100), 1) if total_emails > 0 else 0
            },
            "rules": {
                "total": total_rules,
                "active": active_rules
            }
        }
    
    except Exception as e:
        logger.error(f"Statistics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate statistics"
        )


@router.get("/clients")
async def get_clients(
    request: Request, 
    skip: int = 0, 
    limit: int = 50,
    subscription_status: str = None,
    onboarding_status: str = None
):
    """Get all clients (admin only). Supports filtering by subscription_status and onboarding_status."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Build query with optional filters
        query = {}
        if subscription_status:
            query["subscription_status"] = subscription_status.upper()
        if onboarding_status:
            query["onboarding_status"] = onboarding_status.upper()
        
        clients = await db.clients.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
        total = await db.clients.count_documents(query)
        
        return {
            "clients": clients,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    
    except Exception as e:
        logger.error(f"Get clients error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load clients"
        )


@router.get("/clients/by-crn/{crn}")
async def get_client_by_crn(request: Request, crn: str):
    """
    Get client by Customer Reference Number (CRN). Single source of truth: clients.customer_reference.
    Returns 404 with clear message if not found. Admin only.
    """
    await admin_route_guard(request)
    db = database.get_db()
    if not crn or len(crn.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid CRN required (format: PLE-CVP-YYYY-XXXXX)"
        )
    crn_upper = crn.strip().upper()
    client = await db.clients.find_one(
        {"customer_reference": crn_upper},
        {"_id": 0}
    )
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No client found with CRN: {crn_upper}"
        )
    return client


@router.get("/clients/{client_id}")
async def get_client_detail(request: Request, client_id: str):
    """Get client details (admin only)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        properties = await db.properties.find({"client_id": client_id}, {"_id": 0}).to_list(100)
        portal_users = await db.portal_users.find({"client_id": client_id}, {"_id": 0}).to_list(10)
        requirements = await db.requirements.find({"client_id": client_id}, {"_id": 0}).to_list(1000)
        documents = await db.documents.find({"client_id": client_id}, {"_id": 0}).to_list(1000)
        
        # Calculate compliance summary
        compliant = sum(1 for r in requirements if r["status"] == "COMPLIANT")
        overdue = sum(1 for r in requirements if r["status"] == "OVERDUE")
        expiring = sum(1 for r in requirements if r["status"] == "EXPIRING_SOON")
        
        return {
            "client": client,
            "properties": properties,
            "portal_users": portal_users,
            "requirements": requirements,
            "documents": documents,
            "compliance_summary": {
                "total": len(requirements),
                "compliant": compliant,
                "overdue": overdue,
                "expiring_soon": expiring
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get client detail error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load client details"
        )

@router.get("/audit-logs")
async def get_audit_logs(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    client_id: str = None,
    action: str = None,
    start_date: str = None,
    end_date: str = None
):
    """Get audit logs with enhanced filtering (admin only)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Build query with filters
        query = {}
        if client_id:
            query["client_id"] = client_id
        if action:
            query["action"] = action
        
        # Date range filter
        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = start_date
            if end_date:
                query["timestamp"]["$lte"] = end_date
        
        logs = await db.audit_logs.find(
            query,
            {"_id": 0}
        ).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
        
        total = await db.audit_logs.count_documents(query)
        
        # Get unique actions for filter dropdown
        unique_actions = await db.audit_logs.distinct("action")
        
        return {
            "logs": logs,
            "total": total,
            "skip": skip,
            "limit": limit,
            "filters": {
                "available_actions": unique_actions
            }
        }
    
    except Exception as e:
        logger.error(f"Get audit logs error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load audit logs"
        )


@router.get("/properties/{property_id}/compliance-score-history")
async def get_property_compliance_score_history(
    request: Request,
    property_id: str,
    limit: int = Query(50, ge=1, le=200),
):
    """Get compliance score history timeline for a property (admin observability, read-only).
    
    Returns last N snapshots from property_compliance_score_history. No score computation.
    """
    await admin_route_guard(request)
    db = database.get_db()
    try:
        prop = await db.properties.find_one(
            {"property_id": property_id},
            {"_id": 0, "property_id": 1, "client_id": 1, "compliance_score": 1, "compliance_breakdown": 1, "compliance_last_calculated_at": 1, "compliance_version": 1},
        )
        if not prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found",
            )
        snapshots = await db.property_compliance_score_history.find(
            {"property_id": property_id},
            {"_id": 0},
        ).sort("created_at", -1).limit(limit).to_list(limit)
        return {
            "property_id": property_id,
            "client_id": prop.get("client_id"),
            "current_score": prop.get("compliance_score"),
            "current_breakdown": prop.get("compliance_breakdown"),
            "last_calculated_at": prop.get("compliance_last_calculated_at"),
            "compliance_version": prop.get("compliance_version"),
            "history": snapshots,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Property compliance score history error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load compliance score history",
        )


@router.get("/compliance/sla-alerts")
async def get_compliance_sla_alerts(
    request: Request,
    status: str = Query("active", description="active | all"),
    severity: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List compliance recalc SLA alerts (admin observability). Filters: status (active/all), severity, alert_type."""
    await admin_route_guard(request)
    db = database.get_db()
    try:
        q = {}
        if status == "active":
            q["active"] = True
        if severity:
            q["severity"] = severity
        if alert_type:
            q["alert_type"] = alert_type
        cursor = db.compliance_sla_alerts.find(
            q,
            {"_id": 0, "property_id": 1, "client_id": 1, "alert_type": 1, "severity": 1, "active": 1, "last_detected_at": 1, "last_sent_at": 1, "count": 1, "details": 1},
        ).sort("last_detected_at", -1).skip(offset).limit(limit)
        items = await cursor.to_list(limit)
        return {"alerts": items, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error(f"Compliance SLA alerts list error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load compliance SLA alerts",
        )


@router.get("/properties/{property_id}/compliance-recalc-status")
async def get_property_compliance_recalc_status(
    request: Request,
    property_id: str,
    limit: int = Query(20, ge=1, le=50),
):
    """Get compliance recalc queue status for a property (admin observability, read-only).
    
    Returns compliance_score_pending, last_calculated_at, and recent queue jobs.
    """
    await admin_route_guard(request)
    db = database.get_db()
    try:
        prop = await db.properties.find_one(
            {"property_id": property_id},
            {"_id": 0, "property_id": 1, "client_id": 1, "compliance_score_pending": 1, "compliance_last_calculated_at": 1},
        )
        if not prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found",
            )
        queue_recent = await db.compliance_recalc_queue.find(
            {"property_id": property_id},
            {"_id": 0, "status": 1, "trigger_reason": 1, "attempts": 1, "updated_at": 1, "last_error": 1, "correlation_id": 1},
        ).sort("updated_at", -1).limit(limit).to_list(limit)
        return {
            "property_id": property_id,
            "compliance_score_pending": prop.get("compliance_score_pending", False),
            "compliance_last_calculated_at": prop.get("compliance_last_calculated_at"),
            "queue_recent": queue_recent,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Property compliance recalc status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load compliance recalc status",
        )


@router.get("/properties/{property_id}/compliance-sla")
async def get_property_compliance_sla(
    request: Request,
    property_id: str,
    limit: int = Query(20, ge=1, le=50),
):
    """Property-level compliance SLA view: pending status, last calculated, active alerts, recent recalc jobs."""
    await admin_route_guard(request)
    db = database.get_db()
    try:
        prop = await db.properties.find_one(
            {"property_id": property_id},
            {"_id": 0, "property_id": 1, "client_id": 1, "compliance_score_pending": 1, "compliance_last_calculated_at": 1, "compliance_score": 1},
        )
        if not prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found",
            )
        active_alerts = await db.compliance_sla_alerts.find(
            {"property_id": property_id, "active": True},
            {"_id": 0},
        ).sort("last_detected_at", -1).to_list(20)
        queue_recent = await db.compliance_recalc_queue.find(
            {"property_id": property_id},
            {"_id": 0, "status": 1, "trigger_reason": 1, "attempts": 1, "updated_at": 1, "last_error": 1, "correlation_id": 1, "created_at": 1},
        ).sort("updated_at", -1).limit(limit).to_list(limit)
        return {
            "property_id": property_id,
            "client_id": prop.get("client_id"),
            "compliance_score_pending": prop.get("compliance_score_pending", False),
            "compliance_last_calculated_at": prop.get("compliance_last_calculated_at"),
            "compliance_score": prop.get("compliance_score"),
            "active_alerts": active_alerts,
            "recalc_jobs_recent": queue_recent,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Property compliance SLA error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load property compliance SLA",
        )


@router.get("/provisioning/{client_id}")
async def get_provisioning_status(request: Request, client_id: str):
    """Admin observability: client provisioning state (read-only). No override ability."""
    await admin_route_guard(request)
    db = database.get_db()
    try:
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "client_id": 1, "customer_reference": 1, "billing_plan": 1, "subscription_status": 1,
             "onboarding_status": 1, "stripe_customer_id": 1, "stripe_subscription_id": 1},
        )
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found",
            )
        job = await db.provisioning_jobs.find_one(
            {"client_id": client_id},
            {"_id": 0, "job_id": 1, "status": 1, "attempt_count": 1, "last_error": 1, "created_at": 1, "updated_at": 1},
            sort=[("created_at", -1)],
        )
        provisioning_job = None
        if job:
            provisioning_job = dict(job)
            for k in ("created_at", "updated_at"):
                if provisioning_job.get(k) and hasattr(provisioning_job[k], "isoformat"):
                    provisioning_job[k] = provisioning_job[k].isoformat()
        prov_actions = [
            "PROVISIONING_STARTED", "PROVISIONING_COMPLETE", "CRN_ASSIGNED", "ADMIN_PROVISIONING_TRIGGERED",
            "ADMIN_ACTION",
        ]
        cursor = db.audit_logs.find(
            {"client_id": client_id, "action": {"$in": prov_actions}},
            {"_id": 0, "action": 1, "timestamp": 1, "metadata": 1},
        ).sort("timestamp", -1).limit(10)
        audit_events = await cursor.to_list(10)
        for ev in audit_events:
            if ev.get("timestamp") and hasattr(ev["timestamp"], "isoformat"):
                ev["timestamp"] = ev["timestamp"].isoformat()
        return {
            "client_id": client_id,
            "crn": client.get("customer_reference"),
            "billing_plan": client.get("billing_plan"),
            "subscription_status": client.get("subscription_status"),
            "onboarding_status": client.get("onboarding_status"),
            "provisioning_job": provisioning_job,
            "stripe_customer_id": client.get("stripe_customer_id"),
            "stripe_subscription_id": client.get("stripe_subscription_id"),
            "audit_events": audit_events,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Provisioning status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load provisioning status",
        )


@router.post("/properties/{property_id}/validate-compliance-score")
async def validate_compliance_score(
    request: Request,
    property_id: str,
    body: ValidateComplianceScoreRequest = Body(default=ValidateComplianceScoreRequest()),
):
    """Admin-only: verify stored compliance score matches freshly computed score.
    Optionally fix=true updates stored score to computed and writes snapshot + COMPLIANCE_SCORE_REPAIRED audit.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    try:
        prop = await db.properties.find_one(
            {"property_id": property_id},
            {"_id": 0, "property_id": 1, "client_id": 1, "compliance_score": 1, "compliance_breakdown": 1},
        )
        if not prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found",
            )
        from services.compliance_scoring_service import calculate_property_compliance, WEIGHTS_VERSION

        result = await calculate_property_compliance(property_id)
        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Score computation failed: {result.get('error')}",
            )
        stored_score = prop.get("compliance_score")
        computed_score = result["score"]
        stored_breakdown = prop.get("compliance_breakdown") or {}
        computed_breakdown = result.get("breakdown") or {}
        score_match = (
            stored_score is not None
            and computed_score is not None
            and stored_score == computed_score
        )
        breakdown_diffs = {}
        for key in ("status_score", "expiry_score", "document_score", "overdue_penalty_score", "risk_score"):
            s = stored_breakdown.get(key)
            c = computed_breakdown.get(key)
            if s != c:
                breakdown_diffs[key] = {"stored": s, "computed": c}
        match = score_match and len(breakdown_diffs) == 0
        diff_summary = {
            "score_delta": (computed_score - stored_score) if stored_score is not None else None,
            "breakdown_diffs": breakdown_diffs if breakdown_diffs else None,
        }

        if not match:
            await create_audit_log(
                action=AuditAction.COMPLIANCE_SCORE_MISMATCH_DETECTED,
                actor_id=user.get("portal_user_id"),
                client_id=prop["client_id"],
                resource_type="property",
                resource_id=property_id,
                metadata={
                    "property_id": property_id,
                    "stored_score": stored_score,
                    "computed_score": computed_score,
                    "diff_summary": diff_summary,
                },
            )
            if body.fix:
                now = datetime.now(timezone.utc)
                new_breakdown = result.get("breakdown", {})
                await db.properties.update_one(
                    {"property_id": property_id},
                    {"$set": {
                        "compliance_score": computed_score,
                        "compliance_breakdown": new_breakdown,
                        "compliance_last_calculated_at": now.isoformat(),
                        "compliance_version": result.get("weights_version", WEIGHTS_VERSION),
                        "compliance_score_pending": False,
                    }},
                )
                breakdown_summary = {
                    "status_score": new_breakdown.get("status_score"),
                    "expiry_score": new_breakdown.get("expiry_score"),
                    "document_score": new_breakdown.get("document_score"),
                    "overdue_penalty_score": new_breakdown.get("overdue_penalty_score"),
                    "risk_score": new_breakdown.get("risk_score"),
                }
                history_doc = {
                    "property_id": property_id,
                    "client_id": prop["client_id"],
                    "score": computed_score,
                    "breakdown_summary": breakdown_summary,
                    "created_at": now.isoformat(),
                    "reason": "VALIDATOR_REPAIR",
                    "actor": {"id": user.get("portal_user_id"), "role": "ADMIN"},
                }
                await db.property_compliance_score_history.insert_one(history_doc)
                await create_audit_log(
                    action=AuditAction.COMPLIANCE_SCORE_REPAIRED,
                    actor_id=user.get("portal_user_id"),
                    client_id=prop["client_id"],
                    resource_type="property",
                    resource_id=property_id,
                    before_state={"compliance_score": stored_score},
                    after_state={"compliance_score": computed_score},
                    metadata={
                        "property_id": property_id,
                        "previous_score": stored_score,
                        "new_score": computed_score,
                    },
                )

        return {
            "property_id": property_id,
            "stored_score": stored_score,
            "computed_score": computed_score,
            "match": match,
            "diff_summary": diff_summary,
            "repaired": bool(not match and body.fix),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validate compliance score error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate compliance score",
        )


@router.post("/clients/{client_id}/resend-password-setup")
async def resend_password_setup(request: Request, client_id: str):
    """Resend password setup link (admin only)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Rate limiting
        from utils.rate_limiter import rate_limiter
        
        allowed, error_msg = await rate_limiter.check_rate_limit(
            key=f"password_resend_{client_id}",
            max_attempts=3,
            window_minutes=60
        )
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )
        
        from services.provisioning import provisioning_service
        from auth import generate_secure_token, hash_token
        from models import PasswordToken
        import os
        
        # Get client and portal user
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        if client.get("onboarding_status") != "PROVISIONED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "ACCOUNT_NOT_READY", "message": "Provisioning not completed."}
            )

        portal_user = await db.portal_users.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        if not portal_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portal user not found"
            )
        
        # Revoke old tokens
        await db.password_tokens.update_many(
            {"portal_user_id": portal_user["portal_user_id"], "used_at": None, "revoked_at": None},
            {"$set": {"revoked_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        # Generate new token
        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        
        password_token = PasswordToken(
            token_hash=token_hash,
            portal_user_id=portal_user["portal_user_id"],
            client_id=client_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            created_by="ADMIN",
            send_count=1
        )
        
        doc = password_token.model_dump()
        for key in ["expires_at", "used_at", "revoked_at", "created_at"]:
            if doc.get(key) and isinstance(doc[key], datetime):
                doc[key] = doc[key].isoformat()
        
        await db.password_tokens.insert_one(doc)
        
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        setup_link = f"{frontend_url}/set-password?token={raw_token}"
        if not setup_link:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "EMAIL_INPUT_INVALID", "message": "Missing setup link"},
            )
        from services.notification_orchestrator import notification_orchestrator
        try:
            result = await notification_orchestrator.send(
                template_key="WELCOME_EMAIL",
                client_id=client_id,
                context={
                    "setup_link": setup_link,
                    "client_name": client.get("full_name") or "Customer",
                    "company_name": "Pleerity Enterprise Ltd",
                    "tagline": "AI-Driven Solutions & Compliance",
                },
                idempotency_key=None,
                event_type="admin_resend",
            )
        except Exception as e:
            logger.error(f"Resend password setup send error: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error_code": "EMAIL_SEND_FAILED", "template": EmailTemplateAlias.PASSWORD_SETUP.value},
            )
        if result.status_code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=result.details or {"error_code": "ACCOUNT_NOT_READY", "message": result.block_reason or "Blocked"},
            )
        if result.outcome == "failed":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "error_code": "EMAIL_SEND_FAILED",
                    "template": EmailTemplateAlias.PASSWORD_SETUP.value,
                    "message_id": result.message_id,
                },
            )
        
        await create_audit_log(
            action=AuditAction.PORTAL_INVITE_RESENT,
            actor_id=user["portal_user_id"],
            client_id=client_id,
            metadata={"admin_email": user["email"]}
        )
        
        return {"message": "Password setup link resent"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend password setup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error_code": "EMAIL_SEND_FAILED", "template": EmailTemplateAlias.PASSWORD_SETUP.value},
        )


# ============================================================================
# CLIENT PROFILE MANAGEMENT (Admin)
# ============================================================================

class ClientProfileUpdate(BaseModel):
    """Safe profile fields that admin can update."""
    full_name: str = None
    phone: str = None
    company_name: str = None
    preferred_contact: str = None  # EMAIL, SMS, BOTH


@router.patch("/clients/{client_id}/profile")
async def update_client_profile(
    request: Request, 
    client_id: str, 
    profile_data: ClientProfileUpdate
):
    """
    Update safe client profile fields (admin only).
    Logs before/after state for audit compliance.
    Does NOT allow subscription or billing changes.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get current client state
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Build update dict with only provided fields
        update_data = {}
        before_state = {}
        after_state = {}
        
        # Safe fields only - no subscription/billing fields
        safe_fields = ["full_name", "phone", "company_name", "preferred_contact"]
        
        for field in safe_fields:
            new_value = getattr(profile_data, field, None)
            if new_value is not None:
                old_value = client.get(field)
                if old_value != new_value:
                    before_state[field] = old_value
                    after_state[field] = new_value
                    update_data[field] = new_value
        
        if not update_data:
            return {"message": "No changes detected", "client_id": client_id}
        
        # Add timestamp
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Perform update
        await db.clients.update_one(
            {"client_id": client_id},
            {"$set": update_data}
        )
        
        # Audit log with before/after state
        await create_audit_log(
            action=AuditAction.ADMIN_PROFILE_UPDATED,
            client_id=client_id,
            actor_id=user.get("portal_user_id"),
            actor_role=UserRole.ROLE_ADMIN,
            before_state=before_state,
            after_state=after_state,
            metadata={
                "fields_changed": list(update_data.keys()),
                "admin_email": user.get("auth_email")
            }
        )
        
        logger.info(f"Admin {user.get('auth_email')} updated client {client_id} profile")
        
        return {
            "message": "Profile updated successfully",
            "client_id": client_id,
            "changes": after_state
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update client profile error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update client profile"
        )


@router.get("/clients/{client_id}/readiness")
async def get_client_readiness(request: Request, client_id: str):
    """
    Get client readiness checklist for provisioning.
    Returns checklist items, their status, and last failure reason if any.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        portal_user = await db.portal_users.find_one(
            {"client_id": client_id, "role": "ROLE_CLIENT"},
            {"_id": 0}
        )
        
        properties_count = await db.properties.count_documents({"client_id": client_id})
        
        # Get provisioning audit logs for failure reasons
        provisioning_logs = await db.audit_logs.find(
            {
                "client_id": client_id,
                "action": {"$in": [
                    "PROVISIONING_STARTED", 
                    "PROVISIONING_COMPLETE", 
                    "PROVISIONING_FAILED"
                ]}
            },
            {"_id": 0}
        ).sort("timestamp", -1).limit(5).to_list(5)
        
        last_failure = None
        for log in provisioning_logs:
            if log.get("action") == "PROVISIONING_FAILED":
                last_failure = {
                    "timestamp": log.get("timestamp"),
                    "reason": log.get("metadata", {}).get("error", "Unknown error")
                }
                break
        
        # Build readiness checklist
        checklist = [
            {
                "item": "intake_completed",
                "label": "Intake Form Submitted",
                "status": "complete" if client.get("onboarding_status") != "INTAKE_PENDING" else "pending",
                "required": True
            },
            {
                "item": "payment_complete",
                "label": "Stripe Payment Active",
                "status": "complete" if client.get("stripe_subscription_id") and client.get("subscription_status") == "ACTIVE" else "pending",
                "required": True,
                "details": {
                    "stripe_customer_id": client.get("stripe_customer_id"),
                    "stripe_subscription_id": client.get("stripe_subscription_id"),
                    "subscription_status": client.get("subscription_status")
                }
            },
            {
                "item": "properties_added",
                "label": "At Least One Property",
                "status": "complete" if properties_count > 0 else "pending",
                "required": True,
                "details": {"count": properties_count}
            },
            {
                "item": "portal_user_created",
                "label": "Portal User Account Created",
                "status": "complete" if portal_user else "pending",
                "required": True
            },
            {
                "item": "password_set",
                "label": "Password Set by Client",
                "status": "complete" if portal_user and portal_user.get("password_status") == "SET" else "pending",
                "required": False,
                "details": {
                    "password_status": portal_user.get("password_status") if portal_user else "N/A"
                }
            },
            {
                "item": "provisioned",
                "label": "Fully Provisioned",
                "status": "complete" if client.get("onboarding_status") == "PROVISIONED" else (
                    "failed" if client.get("onboarding_status") == "FAILED" else "pending"
                ),
                "required": True
            }
        ]
        
        # Calculate overall readiness
        required_items = [c for c in checklist if c["required"]]
        complete_required = [c for c in required_items if c["status"] == "complete"]
        ready_to_provision = len(complete_required) >= len(required_items) - 1  # All except "provisioned" itself
        
        return {
            "client_id": client_id,
            "customer_reference": client.get("customer_reference"),
            "onboarding_status": client.get("onboarding_status"),
            "checklist": checklist,
            "ready_to_provision": ready_to_provision,
            "last_failure": last_failure,
            "recent_provisioning_logs": provisioning_logs
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get client readiness error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get client readiness"
        )


@router.get("/clients/{client_id}/audit-timeline")
async def get_client_audit_timeline(request: Request, client_id: str, limit: int = 50):
    """
    Get client audit timeline - key events for admin visibility.
    Shows: intake, payment, provisioning, password setup, login, documents, 
    reminders, assistant usage, webhook events.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "client_id": 1})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Key event types for timeline
        timeline_actions = [
            "INTAKE_SUBMITTED",
            "INTAKE_PROPERTY_ADDED",
            "INTAKE_DOCUMENT_UPLOADED",
            "PROVISIONING_STARTED",
            "PROVISIONING_COMPLETE",
            "PROVISIONING_FAILED",
            "PASSWORD_TOKEN_GENERATED",
            "PASSWORD_SET_SUCCESS",
            "PASSWORD_SETUP_LINK_RESENT",
            "PORTAL_INVITE_RESENT",
            "PORTAL_INVITE_EMAIL_FAILED",
            "USER_LOGIN_SUCCESS",
            "USER_LOGIN_FAILED",
            "DOCUMENT_UPLOADED",
            "DOCUMENT_VERIFIED",
            "DOCUMENT_REJECTED",
            "DOCUMENT_AI_ANALYZED",
            "EMAIL_SENT",
            "REMINDER_SENT",
            "DIGEST_SENT",
            "COMPLIANCE_STATUS_UPDATED",
            "ADMIN_PROFILE_UPDATED",
            "ADMIN_MESSAGE_SENT",
            "ADMIN_PROVISIONING_TRIGGERED"
        ]
        
        logs = await db.audit_logs.find(
            {
                "client_id": client_id,
                "action": {"$in": timeline_actions}
            },
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        # Categorize events for UI grouping
        categorized = {
            "intake": [],
            "provisioning": [],
            "authentication": [],
            "documents": [],
            "notifications": [],
            "compliance": [],
            "admin_actions": []
        }
        
        for log in logs:
            action = log.get("action", "")
            if action.startswith("INTAKE_"):
                categorized["intake"].append(log)
            elif action.startswith("PROVISIONING_"):
                categorized["provisioning"].append(log)
            elif action in ["PASSWORD_TOKEN_GENERATED", "PASSWORD_SET_SUCCESS", "PASSWORD_SETUP_LINK_RESENT", "PORTAL_INVITE_RESENT", "PORTAL_INVITE_EMAIL_FAILED", "USER_LOGIN_SUCCESS", "USER_LOGIN_FAILED"]:
                categorized["authentication"].append(log)
            elif action.startswith("DOCUMENT_"):
                categorized["documents"].append(log)
            elif action in ["EMAIL_SENT", "REMINDER_SENT", "DIGEST_SENT"]:
                categorized["notifications"].append(log)
            elif action.startswith("COMPLIANCE_"):
                categorized["compliance"].append(log)
            elif action.startswith("ADMIN_"):
                categorized["admin_actions"].append(log)
        
        return {
            "client_id": client_id,
            "timeline": logs,
            "categorized": categorized,
            "total_events": len(logs)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get client audit timeline error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get audit timeline"
        )


# ============================================================================
# KPI DRILL-DOWN ENDPOINTS
# ============================================================================

@router.get("/kpi/properties")
async def get_kpi_properties(
    request: Request,
    status_filter: str = None,  # GREEN, AMBER, RED
    expiring_within_days: int = None,
    skip: int = 0,
    limit: int = 50
):
    """
    KPI drill-down: Get properties filtered by compliance status.
    Used when admin clicks on KPI tiles.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        query = {}
        
        if status_filter:
            query["compliance_status"] = status_filter.upper()
        
        # For "expiring soon" filter
        if expiring_within_days:
            from datetime import timedelta
            cutoff_date = (datetime.now(timezone.utc) + timedelta(days=expiring_within_days)).isoformat()
            # This would need to check requirements with expiry dates
            # For now, we'll filter properties with expiring requirements
            expiring_reqs = await db.requirements.find(
                {
                    "status": "EXPIRING_SOON",
                    "expiry_date": {"$lte": cutoff_date}
                },
                {"_id": 0, "property_id": 1}
            ).to_list(1000)
            property_ids = list(set(r["property_id"] for r in expiring_reqs))
            query["property_id"] = {"$in": property_ids}
        
        properties = await db.properties.find(
            query,
            {"_id": 0}
        ).skip(skip).limit(limit).to_list(limit)
        
        total = await db.properties.count_documents(query)
        
        # Enrich with client info
        for prop in properties:
            client = await db.clients.find_one(
                {"client_id": prop.get("client_id")},
                {"_id": 0, "full_name": 1, "email": 1, "customer_reference": 1}
            )
            prop["client"] = client
        
        return {
            "properties": properties,
            "total": total,
            "skip": skip,
            "limit": limit,
            "filter": {
                "status": status_filter,
                "expiring_within_days": expiring_within_days
            }
        }
        
    except Exception as e:
        logger.error(f"KPI properties drill-down error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load properties"
        )


@router.get("/kpi/requirements")
async def get_kpi_requirements(
    request: Request,
    status_filter: str = None,  # COMPLIANT, OVERDUE, EXPIRING_SOON, PENDING
    category: str = None,
    skip: int = 0,
    limit: int = 50
):
    """
    KPI drill-down: Get requirements filtered by status.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        query = {}
        
        if status_filter:
            query["status"] = status_filter.upper()
        if category:
            query["category"] = category.upper()
        
        requirements = await db.requirements.find(
            query,
            {"_id": 0}
        ).sort("expiry_date", 1).skip(skip).limit(limit).to_list(limit)
        
        total = await db.requirements.count_documents(query)
        
        # Enrich with property and client info
        for req in requirements:
            prop = await db.properties.find_one(
                {"property_id": req.get("property_id")},
                {"_id": 0, "nickname": 1, "address_line_1": 1, "postcode": 1, "client_id": 1}
            )
            if prop:
                req["property"] = prop
                client = await db.clients.find_one(
                    {"client_id": prop.get("client_id")},
                    {"_id": 0, "full_name": 1, "customer_reference": 1}
                )
                req["client"] = client
        
        return {
            "requirements": requirements,
            "total": total,
            "skip": skip,
            "limit": limit,
            "filter": {
                "status": status_filter,
                "category": category
            }
        }
        
    except Exception as e:
        logger.error(f"KPI requirements drill-down error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load requirements"
        )


# ============================================================================
# ADMIN MESSAGING TO CLIENT
# ============================================================================

class AdminMessageRequest(BaseModel):
    subject: str
    message: str  # Plain text or HTML
    send_copy_to_admin: bool = False


@router.post("/clients/{client_id}/message")
async def send_message_to_client(
    request: Request,
    client_id: str,
    message_data: AdminMessageRequest
):
    """
    Send email message from admin to client.
    Logs to MessageLog + AuditLog.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        from services.notification_orchestrator import notification_orchestrator
        import uuid
        req_id = str(uuid.uuid4())
        idempotency_key = f"{client_id}_ADMIN_MANUAL_{req_id}"
        result = await notification_orchestrator.send(
            template_key="ADMIN_MANUAL",
            client_id=client_id,
            context={
                "client_name": client.get("full_name", "Client"),
                "message": message_data.message.replace(chr(10), '<br>'),
                "subject": message_data.subject,
                "customer_reference": client.get("customer_reference", "N/A"),
                "company_name": "Pleerity Enterprise Ltd",
                "tagline": "AI-Driven Solutions & Compliance",
            },
            idempotency_key=idempotency_key,
            event_type="admin_send_message",
        )
        success = result.outcome in ("sent", "duplicate_ignored")
        message_id = result.message_id or req_id
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email"
            )
        await create_audit_log(
            action=AuditAction.ADMIN_MESSAGE_SENT,
            client_id=client_id,
            actor_id=user.get("portal_user_id"),
            actor_role=UserRole.ROLE_ADMIN,
            metadata={
                "message_id": message_id,
                "subject": message_data.subject,
                "recipient": client.get("email"),
                "admin_email": user.get("auth_email")
            }
        )
        if message_data.send_copy_to_admin:
            copy_key = f"{client_id}_ADMIN_MANUAL_copy_{user.get('auth_email')}_{req_id}"
            await notification_orchestrator.send(
                template_key="ADMIN_MANUAL",
                client_id=None,
                context={
                    "recipient": user.get("auth_email"),
                    "client_name": "Admin",
                    "message": f"[Copy of message sent to {client.get('email')}]<br><br>{message_data.message.replace(chr(10), '<br>')}",
                    "subject": f"[Copy] {message_data.subject}",
                    "customer_reference": client.get("customer_reference", "N/A"),
                    "company_name": "Pleerity Enterprise Ltd",
                    "tagline": "AI-Driven Solutions & Compliance",
                },
                idempotency_key=copy_key,
                event_type="admin_send_message_copy",
            )
        logger.info(f"Admin {user.get('auth_email')} sent message to client {client_id}")
        return {
            "success": True,
            "message_id": message_id,
            "recipient": client.get("email"),
            "subject": message_data.subject
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send message to client error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message"
        )


@router.get("/messages")
async def get_message_logs(request: Request, skip: int = 0, limit: int = 100, client_id: str = None):
    """Get email message logs (admin only)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        query = {}
        if client_id:
            query["client_id"] = client_id
        
        messages = await db.message_logs.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        total = await db.message_logs.count_documents(query)
        
        return {
            "messages": messages,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    
    except Exception as e:
        logger.error(f"Get message logs error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load message logs"
        )


def _parse_iso_datetime(s: Optional[str]):
    """Parse ISO datetime string to timezone-aware datetime for DB query. Returns None if invalid."""
    if not s or not s.strip():
        return None
    try:
        dt = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


@router.get("/message-logs")
async def list_message_logs_delivery(
    request: Request,
    client_id: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    template_key: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    status_prefix: Optional[str] = Query(None, description="e.g. BLOCKED for any BLOCKED_*"),
    from_: Optional[str] = Query(None, alias="from", description="ISO datetime (created_at >= from)"),
    to: Optional[str] = Query(None, description="ISO datetime (created_at <= to)"),
    recipient: Optional[str] = Query(None, description="Substring match on recipient"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Admin observability: list message_logs with filters. Read-only."""
    await admin_route_guard(request)
    db = database.get_db()
    try:
        q = {}
        if client_id:
            q["client_id"] = client_id
        if channel:
            q["channel"] = channel
        if template_key:
            q["template_key"] = template_key
        if status_filter:
            if "," in status_filter:
                q["status"] = {"$in": [s.strip() for s in status_filter.split(",") if s.strip()]}
            else:
                q["status"] = status_filter.strip()
        if status_prefix:
            q["status"] = {"$regex": f"^{status_prefix.strip()}"}
        from_dt = _parse_iso_datetime(from_)
        to_dt = _parse_iso_datetime(to)
        if from_dt is not None:
            q.setdefault("created_at", {})["$gte"] = from_dt
        if to_dt is not None:
            q.setdefault("created_at", {})["$lte"] = to_dt
        if recipient and recipient.strip():
            q["recipient"] = {"$regex": recipient.strip(), "$options": "i"}
        projection = {
            "_id": 0,
            "message_id": 1,
            "client_id": 1,
            "template_key": 1,
            "template_alias": 1,
            "channel": 1,
            "status": 1,
            "attempt_count": 1,
            "created_at": 1,
            "sent_at": 1,
            "delivered_at": 1,
            "bounced_at": 1,
            "provider_message_id": 1,
            "postmark_message_id": 1,
            "error_message": 1,
            "recipient": 1,
        }
        cursor = db.message_logs.find(q, projection).sort("created_at", -1).skip(offset).limit(limit)
        items = await cursor.to_list(limit)
        for it in items:
            for k in ("created_at", "sent_at", "delivered_at", "bounced_at"):
                if it.get(k) and hasattr(it[k], "isoformat"):
                    it[k] = it[k].isoformat()
        total = await db.message_logs.count_documents(q)
        return {"items": items, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error(f"Message logs list error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load message logs",
        )


@router.get("/message-logs/{message_id}")
async def get_message_log_by_id(request: Request, message_id: str):
    """Admin observability: single message_log by message_id. Read-only."""
    await admin_route_guard(request)
    db = database.get_db()
    try:
        log = await db.message_logs.find_one(
            {"message_id": message_id},
            {"_id": 0},
        )
        if not log:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        for k in ("created_at", "sent_at", "delivered_at", "bounced_at", "opened_at"):
            if log.get(k) and hasattr(log[k], "isoformat"):
                log[k] = log[k].isoformat()
        return log
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Message log get error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load message log",
        )


@router.post("/send-manual-email")
async def send_manual_email(
    request: Request,
    client_id: str,
    subject: str,
    message: str
):
    """Send manual email to client (admin only)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        from services.notification_orchestrator import notification_orchestrator
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        idempotency_key = f"{client_id}_ADMIN_MANUAL_{ts}"
        await notification_orchestrator.send(
            template_key="ADMIN_MANUAL",
            client_id=client_id,
            context={
                "client_name": client.get("full_name", "Client"),
                "message": message,
                "subject": subject,
                "company_name": "Pleerity Enterprise Ltd",
                "tagline": "AI-Driven Solutions & Compliance",
            },
            idempotency_key=idempotency_key,
            event_type="manual_email_sent",
        )
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=client_id,
            metadata={
                "action": "manual_email_sent",
                "subject": subject,
                "admin_email": user.get("email") or user.get("auth_email")
            }
        )
        return {"message": "Email sent successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send manual email error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send email"
        )

@router.get("/clients/{client_id}/compliance-pack")
async def generate_compliance_pack(request: Request, client_id: str):
    """Generate compliance pack for client (PLAN_6_15 only)."""
    user = await admin_route_guard(request)
    
    try:
        from services.compliance_pack import compliance_pack_generator
        
        pack_data = await compliance_pack_generator.generate_pack(client_id)
        
        return pack_data
    
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Compliance pack generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate compliance pack"
        )

@router.get("/jobs/status")
async def get_jobs_status(request: Request):
    """Get background jobs status (read-only monitoring)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get last reminder job run from audit logs
        last_reminder = await db.audit_logs.find_one(
            {"action": "REMINDER_SENT"},
            {"_id": 0},
            sort=[("timestamp", -1)]
        )
        
        # Get last digest job run
        last_digest = await db.digest_logs.find_one(
            {},
            {"_id": 0},
            sort=[("sent_at", -1)]
        )
        
        # Count pending reminders (requirements expiring in 30 days)
        thirty_days = datetime.now(timezone.utc) + timedelta(days=30)
        
        requirements = await db.requirements.find(
            {"status": {"$in": ["PENDING", "EXPIRING_SOON"]}},
            {"_id": 0}
        ).to_list(10000)
        
        pending_reminders = 0
        for r in requirements:
            try:
                due_date_str = r.get("due_date")
                if due_date_str:
                    due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00')) if isinstance(due_date_str, str) else due_date_str
                    if due_date <= thirty_days:
                        pending_reminders += 1
            except Exception:
                pass
        
        # Get scheduler status
        from server import scheduler
        scheduler_jobs = []
        for job in scheduler.get_jobs():
            scheduler_jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            })
        
        return {
            "daily_reminders": {
                "last_run": last_reminder["timestamp"] if last_reminder else None,
                "pending_count": pending_reminders
            },
            "monthly_digest": {
                "last_run": last_digest["sent_at"] if last_digest else None,
                "total_sent": await db.digest_logs.count_documents({})
            },
            "scheduled_jobs": scheduler_jobs,
            "system_status": "operational"
        }
    
    except Exception as e:
        logger.error(f"Jobs status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load jobs status"
        )


@router.get("/system/feature-matrix")
async def get_feature_matrix(request: Request):
    """Get the complete feature entitlement matrix.
    
    Returns all features with their availability across all plans.
    Useful for documentation, auditing, and admin review.
    Uses plan_registry as single source of truth.
    """
    user = await admin_route_guard(request)
    
    try:
        from services.plan_registry import plan_registry
        
        matrix = plan_registry.get_entitlement_matrix()
        
        return {
            **matrix,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        logger.error(f"Feature matrix error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load feature matrix"
        )

class RunJobRequest(BaseModel):
    job: str


@router.post("/jobs/run")
async def run_job_now(request: Request, body: RunJobRequest):
    """Run a single background job by id (admin only). Returns job-specific message for toast."""
    user = await admin_route_guard(request)
    from job_runner import JOB_RUNNERS

    job_id = (body.job or "").strip()
    if not job_id or job_id not in JOB_RUNNERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid job. Use one of: {', '.join(sorted(JOB_RUNNERS.keys()))}"
        )
    try:
        result = await JOB_RUNNERS[job_id]()
        message = (result.get("message") if result else None) or f"Job {job_id} completed"
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=None,
            metadata={
                "action": "manual_job_run",
                "job_id": job_id,
                "admin_email": user["email"],
            },
        )
        return {"success": True, "job": job_id, "message": message}
    except Exception as e:
        logger.error(f"Manual job run error ({job_id}): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run job: {job_id}"
        )


@router.post("/jobs/trigger/{job_type}")
async def trigger_job(request: Request, job_type: str):
    """Legacy: manually trigger daily/monthly/compliance (admin only). Prefer POST /jobs/run with body { job: '<id>' }."""
    user = await admin_route_guard(request)
    if job_type not in ["daily", "monthly", "compliance"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job type. Use 'daily', 'monthly', or 'compliance'"
        )
    job_id = {"daily": "daily_reminders", "monthly": "monthly_digest", "compliance": "compliance_check_morning"}[job_type]
    from job_runner import JOB_RUNNERS
    try:
        result = await JOB_RUNNERS[job_id]()
        message = (result.get("message") if result else None) or f"{job_type} job completed"
        count = result.get("count") if result else None
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=None,
            metadata={
                "action": f"manual_job_trigger_{job_type}",
                "result_count": count,
                "admin_email": user["email"]
            }
        )
        return {"message": message, "count": count}
    except Exception as e:
        logger.error(f"Manual job trigger error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger {job_type} job"
        )

@router.post("/clients/invite")
async def admin_invite_client(
    request: Request,
    full_name: str,
    email: str,
    billing_plan: str = "PLAN_1"
):
    """Admin-initiated client invitation.
    
    Creates client record in INVITED state. Admin must manually trigger
    provisioning after payment is arranged separately.
    
    IMPORTANT: This does NOT bypass the normal flow. It simply pre-creates
    the client record. Provisioning must still be triggered manually.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        from models import Client, BillingPlan, ClientType, PreferredContact, ServiceCode
        
        # Check if email already exists
        existing = await db.clients.find_one({"email": email}, {"_id": 0})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A client with this email already exists"
            )
        
        # Create client in INVITED state (not yet provisioned)
        client = Client(
            full_name=full_name,
            email=email,
            client_type=ClientType.INDIVIDUAL,
            preferred_contact=PreferredContact.EMAIL,
            billing_plan=BillingPlan(billing_plan),
            service_code=ServiceCode.VAULT_PRO,
            subscription_status="PENDING",  # Admin must activate
            onboarding_status="INTAKE_PENDING"  # Not provisioned yet
        )
        
        client_doc = client.model_dump()
        for key in ["created_at", "updated_at"]:
            if client_doc.get(key):
                client_doc[key] = client_doc[key].isoformat()
        
        await db.clients.insert_one(client_doc)
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=client.client_id,
            metadata={
                "action": "admin_client_invited",
                "email": email,
                "billing_plan": billing_plan,
                "admin_email": user["email"]
            }
        )
        
        logger.info(f"Admin invited client: {email}")
        
        return {
            "message": "Client invited successfully",
            "client_id": client.client_id,
            "next_steps": [
                "Add property details for the client",
                "Arrange payment separately",
                "Manually trigger provisioning via /admin/clients/{client_id}/provision"
            ]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin invite client error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invite client"
        )

@router.post("/clients/{client_id}/properties")
async def admin_add_property(
    request: Request,
    client_id: str,
    address_line_1: str,
    city: str,
    postcode: str,
    property_type: str = "residential",
    number_of_units: int = 1
):
    """Add a property for a client (admin only).
    
    Used when setting up a client before provisioning.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        from models import Property, ComplianceStatus
        
        # Verify client exists
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Create property
        property_obj = Property(
            client_id=client_id,
            address_line_1=address_line_1,
            city=city,
            postcode=postcode,
            property_type=property_type,
            number_of_units=number_of_units,
            compliance_status=ComplianceStatus.RED
        )
        
        prop_doc = property_obj.model_dump()
        for key in ["created_at", "updated_at"]:
            if prop_doc.get(key):
                prop_doc[key] = prop_doc[key].isoformat()
        
        await db.properties.insert_one(prop_doc)
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=client_id,
            metadata={
                "action": "admin_property_added",
                "property_id": property_obj.property_id,
                "address": address_line_1,
                "admin_email": user["email"]
            }
        )
        
        logger.info(f"Admin added property for client {client_id}: {address_line_1}")
        
        return {
            "message": "Property added successfully",
            "property_id": property_obj.property_id,
            "client_id": client_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin add property error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add property"
        )

@router.post("/clients/{client_id}/provision")
async def admin_trigger_provision(request: Request, client_id: str):
    """Manually trigger provisioning for a client (admin only).
    
    Uses the existing provisioning engine. This is for admin-invited clients
    where payment was arranged separately.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Verify client has at least one property
        property_count = await db.properties.count_documents({"client_id": client_id})
        if property_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client must have at least one property before provisioning"
            )
        
        # Set subscription active (manual approval by admin)
        await db.clients.update_one(
            {"client_id": client_id},
            {"$set": {"subscription_status": "ACTIVE"}}
        )
        
        # Trigger existing provisioning engine
        from services.provisioning import provisioning_service
        success, message = await provisioning_service.provision_client_portal(client_id)
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=client_id,
            metadata={
                "action": "admin_manual_provision",
                "success": success,
                "message": message,
                "admin_email": user["email"]
            }
        )
        
        if success:
            return {
                "message": "Provisioning triggered successfully",
                "status": "provisioned"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Provisioning failed: {message}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin provision error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger provisioning"
        )


@router.post("/provisioning-jobs/{job_id}/retry")
async def retry_provisioning_job(request: Request, job_id: str):
    """Retry a failed or stuck provisioning job (admin only). Runs the job runner once."""
    await admin_route_guard(request)
    from services.provisioning_runner import run_provisioning_job
    try:
        ok = await run_provisioning_job(job_id)
        job = await database.get_db().provisioning_jobs.find_one({"job_id": job_id}, {"_id": 0, "status": 1, "client_id": 1})
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            client_id=job.get("client_id"),
            metadata={"action": "provisioning_job_retry", "job_id": job_id, "runner_returned": ok}
        )
        return {"message": "Retry triggered", "job_id": job_id, "status": job.get("status")}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retry provisioning job error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retry job")


@router.post("/provisioning-jobs/{job_id}/resend-invite")
async def resend_provisioning_invite(request: Request, job_id: str):
    """Resend welcome (password setup) email for a job in PROVISIONING_COMPLETED (admin only)."""
    await admin_route_guard(request)
    db = database.get_db()
    job = await db.provisioning_jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.get("status") != ProvisioningJobStatus.PROVISIONING_COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job status is {job.get('status')}; resend-invite only for PROVISIONING_COMPLETED"
        )
    from services.provisioning_runner import run_provisioning_job
    ok = await run_provisioning_job(job_id)  # Runner will do email-only retry for this status
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        client_id=job.get("client_id"),
        metadata={"action": "provisioning_job_resend_invite", "job_id": job_id, "success": ok}
    )
    return {"message": "Resend invite triggered", "job_id": job_id, "success": ok}


@router.get("/clients/{client_id}/password-setup-link")
async def get_password_setup_link(request: Request, client_id: str, generate_new: bool = False):
    """Get or generate password setup link for a client (admin only, for internal testing).
    
    This endpoint allows admins to:
    1. View the latest valid password setup link for a client
    2. Generate a new link if none exists or if generate_new=True
    
    SECURITY: This is for internal testing only. In production, consider restricting access.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Get portal user
        portal_user = await db.portal_users.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        if not portal_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portal user not found - client may not be provisioned"
            )
        
        import os
        from auth import generate_secure_token, hash_token
        from models import PasswordToken
        
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        
        # Check for existing valid token (not used, not revoked, not expired)
        existing_token = None
        if not generate_new:
            # Find valid token - we need to check expiry
            tokens = await db.password_tokens.find(
                {
                    "portal_user_id": portal_user["portal_user_id"],
                    "used_at": None,
                    "revoked_at": None
                },
                {"_id": 0}
            ).sort("created_at", -1).to_list(10)
            
            for token in tokens:
                expires_at = datetime.fromisoformat(token["expires_at"].replace('Z', '+00:00')) if isinstance(token["expires_at"], str) else token["expires_at"]
                if expires_at > datetime.now(timezone.utc):
                    existing_token = token
                    break
        
        if existing_token and not generate_new:
            # NOTE: We cannot retrieve the raw token from hash - must generate new
            return {
                "message": "Existing valid token found but raw token not retrievable",
                "token_exists": True,
                "expires_at": existing_token["expires_at"],
                "created_at": existing_token["created_at"],
                "portal_user_id": portal_user["portal_user_id"],
                "client_email": client["email"],
                "note": "Use generate_new=true to create a new link",
                "client_status": {
                    "subscription_status": client.get("subscription_status"),
                    "onboarding_status": client.get("onboarding_status")
                },
                "portal_user_status": {
                    "status": portal_user.get("status"),
                    "password_status": portal_user.get("password_status")
                }
            }
        
        # Generate new token
        # First, revoke any existing tokens
        await db.password_tokens.update_many(
            {"portal_user_id": portal_user["portal_user_id"], "used_at": None, "revoked_at": None},
            {"$set": {"revoked_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        
        password_token = PasswordToken(
            token_hash=token_hash,
            portal_user_id=portal_user["portal_user_id"],
            client_id=client_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),  # 24 hours for admin-generated
            created_by="ADMIN",
            send_count=0  # Not sent via email
        )
        
        doc = password_token.model_dump()
        for key in ["expires_at", "used_at", "revoked_at", "created_at"]:
            if doc.get(key) and isinstance(doc[key], datetime):
                doc[key] = doc[key].isoformat()
        
        await db.password_tokens.insert_one(doc)
        
        setup_link = f"{frontend_url}/set-password?token={raw_token}"
        
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=client_id,
            metadata={
                "action": "admin_generated_password_link",
                "admin_email": user["email"],
                "for_user": portal_user["portal_user_id"]
            }
        )
        if user.get("role") == UserRole.ROLE_OWNER.value:
            await create_audit_log(
                action=AuditAction.PASSWORD_RESET_BY_OWNER,
                actor_role=UserRole.ROLE_OWNER,
                actor_id=user["portal_user_id"],
                client_id=client_id,
                resource_type="portal_user",
                resource_id=portal_user["portal_user_id"],
                metadata={"for_email": portal_user.get("auth_email")}
            )
        
        return {
            "message": "Password setup link generated",
            "setup_link": setup_link,
            "raw_token": raw_token,
            "expires_at": password_token.expires_at.isoformat(),
            "client_email": client["email"],
            "client_name": client["full_name"],
            "client_status": {
                "subscription_status": client.get("subscription_status"),
                "onboarding_status": client.get("onboarding_status")
            },
            "portal_user_status": {
                "status": portal_user.get("status"),
                "password_status": portal_user.get("password_status")
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get password setup link error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get/generate password setup link"
        )

@router.get("/clients/{client_id}/full-status")
async def get_client_full_status(request: Request, client_id: str):
    """Get complete client status including all related records (admin only).
    
    Returns a comprehensive view of client state for debugging and verification.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Get portal user(s)
        portal_users = await db.portal_users.find(
            {"client_id": client_id},
            {"_id": 0, "password_hash": 0}
        ).to_list(10)
        
        # Get properties
        properties = await db.properties.find(
            {"client_id": client_id},
            {"_id": 0}
        ).to_list(100)
        
        # Get requirements count by status
        requirements = await db.requirements.find(
            {"client_id": client_id},
            {"_id": 0, "status": 1}
        ).to_list(1000)
        
        req_summary = {}
        for r in requirements:
            status = r.get("status", "UNKNOWN")
            req_summary[status] = req_summary.get(status, 0) + 1
        
        # Get password tokens
        tokens = await db.password_tokens.find(
            {"client_id": client_id},
            {"_id": 0, "token_hash": 0}  # Don't expose hash
        ).sort("created_at", -1).to_list(5)
        
        # Get recent audit logs
        audit_logs = await db.audit_logs.find(
            {"client_id": client_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(10).to_list(10)
        
        # Get message logs
        message_logs = await db.message_logs.find(
            {"client_id": client_id},
            {"_id": 0}
        ).sort("created_at", -1).limit(10).to_list(10)
        
        return {
            "client": client,
            "portal_users": portal_users,
            "properties_count": len(properties),
            "properties": properties[:5],  # First 5 only
            "requirements_summary": req_summary,
            "requirements_total": len(requirements),
            "recent_password_tokens": tokens,
            "recent_audit_logs": audit_logs,
            "recent_message_logs": message_logs,
            "readiness_check": {
                "has_properties": len(properties) > 0,
                "is_provisioned": client.get("onboarding_status") == "PROVISIONED",
                "subscription_active": client.get("subscription_status") == "ACTIVE",
                "has_portal_user": len(portal_users) > 0,
                "portal_user_active": any(u.get("status") == "ACTIVE" for u in portal_users),
                "password_set": any(u.get("password_status") == "SET" for u in portal_users)
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get client full status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get client status"
        )



# ============================================================================
# ADMIN USER MANAGEMENT
# ============================================================================

@router.get("/admins")
async def list_admins(request: Request):
    """List all staff (OWNER + ADMIN) for admin management. Excludes password hashes."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        admins = await db.portal_users.find(
            {"role": {"$in": [UserRole.ROLE_OWNER.value, UserRole.ROLE_ADMIN.value]}},
            {"_id": 0, "password_hash": 0}
        ).to_list(100)
        
        return {
            "admins": admins,
            "total": len(admins)
        }
    
    except Exception as e:
        logger.error(f"List admins error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list admins"
        )


@router.post("/admins/invite")
async def invite_admin(request: Request, invite_data: AdminInviteRequest):
    """Invite a new ADMIN user (OWNER only). Creates ROLE_ADMIN only; no second OWNER.
    
    Creates PortalUser with ROLE_ADMIN, sends password setup email, audits. Staff field created_by_owner_id set when invited by OWNER.
    """
    inviter = await require_owner(request)
    db = database.get_db()
    
    try:
        existing_user = await db.portal_users.find_one(
            {"auth_email": invite_data.email},
            {"_id": 0}
        )
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists"
            )
        
        portal_user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        is_owner = inviter.get("role") == UserRole.ROLE_OWNER.value
        
        new_admin = {
            "portal_user_id": portal_user_id,
            "client_id": None,
            "auth_email": invite_data.email,
            "password_hash": None,
            "role": UserRole.ROLE_ADMIN.value,
            "status": UserStatus.INVITED.value,
            "password_status": PasswordStatus.NOT_SET.value,
            "must_set_password": True,
            "session_version": 0,
            "last_login": None,
            "created_at": now.isoformat(),
            "full_name": invite_data.full_name,
            "invited_by": inviter["portal_user_id"],
            "created_by_owner_id": inviter["portal_user_id"] if is_owner else None,
        }
        
        await db.portal_users.insert_one(new_admin)
        logger.info(f"Created new admin user: {invite_data.email}")
        
        # Generate password setup token
        from auth import generate_secure_token, hash_token
        
        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        
        password_token = PasswordToken(
            token_hash=token_hash,
            portal_user_id=portal_user_id,
            client_id="ADMIN_INVITE",  # Special marker for admin invites
            expires_at=now + timedelta(hours=24),
            created_by=inviter["portal_user_id"],
            send_count=1
        )
        
        token_doc = password_token.model_dump()
        for key in ["expires_at", "used_at", "revoked_at", "created_at"]:
            if token_doc.get(key) and isinstance(token_doc[key], datetime):
                token_doc[key] = token_doc[key].isoformat()
        
        await db.password_tokens.insert_one(token_doc)
        logger.info(f"Generated password token for admin: {invite_data.email}")
        
        from services.notification_orchestrator import notification_orchestrator
        import os
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        setup_link = f"{frontend_url}/set-password?token={raw_token}"
        idempotency_key = f"{portal_user_id}_ADMIN_INVITE"
        await notification_orchestrator.send(
            template_key="ADMIN_INVITE",
            client_id=None,
            context={
                "recipient": invite_data.email,
                "admin_name": invite_data.full_name,
                "inviter_name": inviter.get("email", "System Administrator"),
                "setup_link": setup_link,
                "company_name": "Pleerity Enterprise Ltd",
            },
            idempotency_key=idempotency_key,
            event_type="admin_invite",
        )
        logger.info(f"Sent admin invite email to: {invite_data.email}")
        
        await create_audit_log(
            action=AuditAction.ADMIN_INVITED,
            actor_role=UserRole(inviter["role"]),
            actor_id=inviter["portal_user_id"],
            resource_type="portal_user",
            resource_id=portal_user_id,
            metadata={
                "invited_email": invite_data.email,
                "invited_name": invite_data.full_name,
                "inviter_email": inviter.get("email")
            }
        )
        
        return {
            "message": "Admin invitation sent successfully",
            "portal_user_id": portal_user_id,
            "email": invite_data.email,
            "status": "INVITED",
            "note": "The invited admin will receive an email with instructions to set up their account."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Invite admin error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invite admin"
        )


@router.delete("/admins/{portal_user_id}")
async def deactivate_admin(request: Request, portal_user_id: str):
    """Deactivate an ADMIN user (OWNER or ADMIN). OWNER cannot be deactivated or downgraded; last OWNER cannot be removed."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        if user["portal_user_id"] == portal_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own account"
            )
        
        target = await db.portal_users.find_one(
            {"portal_user_id": portal_user_id},
            {"_id": 0, "role": 1, "status": 1, "auth_email": 1}
        )
        
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # OWNER cannot be deleted, deactivated, or downgraded via API
        if target.get("role") == UserRole.ROLE_OWNER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="OWNER cannot be deactivated or removed via API"
            )
        
        # Target is ADMIN: last-active-admin protection
        active_admin_count = await db.portal_users.count_documents({
            "role": UserRole.ROLE_ADMIN.value,
            "status": UserStatus.ACTIVE.value
        })
        if active_admin_count <= 1 and target.get("status") == UserStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last active admin. Add another admin or use the recovery script to re-enable an admin by email."
            )

        await db.portal_users.update_one(
            {"portal_user_id": portal_user_id},
            {"$set": {"status": UserStatus.DISABLED.value}}
        )
        
        await create_audit_log(
            action=AuditAction.ADMIN_DISABLED,
            actor_role=UserRole(user["role"]),
            actor_id=user["portal_user_id"],
            resource_type="portal_user",
            resource_id=portal_user_id,
            metadata={
                "deactivated_email": target.get("auth_email"),
                "by": user.get("email")
            }
        )
        
        return {
            "message": "Admin deactivated successfully",
            "portal_user_id": portal_user_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Deactivate admin error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate admin"
        )


@router.post("/admins/{portal_user_id}/reactivate")
async def reactivate_admin(request: Request, portal_user_id: str):
    """Reactivate a disabled ADMIN user. Only ADMIN can be reactivated (OWNER cannot be deactivated)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        target = await db.portal_users.find_one(
            {"portal_user_id": portal_user_id, "role": UserRole.ROLE_ADMIN.value},
            {"_id": 0}
        )
        
        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin not found"
            )
        
        if target.get("status") == UserStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin is already active"
            )
        
        await db.portal_users.update_one(
            {"portal_user_id": portal_user_id},
            {"$set": {"status": UserStatus.ACTIVE.value}}
        )
        
        await create_audit_log(
            action=AuditAction.ADMIN_ENABLED,
            actor_role=UserRole(user["role"]),
            actor_id=user["portal_user_id"],
            resource_type="portal_user",
            resource_id=portal_user_id,
            metadata={
                "reactivated_email": target.get("auth_email"),
                "by": user.get("email")
            }
        )
        
        return {
            "message": "Admin reactivated successfully",
            "portal_user_id": portal_user_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reactivate admin error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reactivate admin"
        )


@router.post("/admins/{portal_user_id}/force-logout")
async def force_logout_admin(request: Request, portal_user_id: str):
    """Force logout all sessions for a staff user by incrementing session_version (OWNER only). Audited."""
    user = await require_owner(request)
    db = database.get_db()
    
    try:
        target = await db.portal_users.find_one(
            {"portal_user_id": portal_user_id},
            {"_id": 0, "role": 1, "auth_email": 1}
        )
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        result = await db.portal_users.update_one(
            {"portal_user_id": portal_user_id},
            {"$inc": {"session_version": 1}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update session version")
        
        await create_audit_log(
            action=AuditAction.SESSION_FORCE_LOGOUT,
            actor_role=UserRole.ROLE_OWNER,
            actor_id=user["portal_user_id"],
            resource_type="portal_user",
            resource_id=portal_user_id,
            metadata={"target_email": target.get("auth_email"), "by": user.get("email")}
        )
        return {"message": "Sessions invalidated", "portal_user_id": portal_user_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Force logout error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to force logout")


@router.post("/admins/{portal_user_id}/resend-invite")
async def resend_admin_invite(request: Request, portal_user_id: str):
    """Resend invitation email to an admin who hasn't set their password yet.
    
    This revokes all existing tokens and generates a new one with fresh expiration.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Find the target admin
        target_admin = await db.portal_users.find_one(
            {"portal_user_id": portal_user_id, "role": UserRole.ROLE_ADMIN.value},
            {"_id": 0}
        )
        
        if not target_admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin not found"
            )
        
        # Check if password is already set
        if target_admin.get("password_status") == PasswordStatus.SET.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This admin has already set their password"
            )
        
        # Revoke existing tokens
        await db.password_tokens.update_many(
            {"portal_user_id": portal_user_id, "used_at": None, "revoked_at": None},
            {"$set": {"revoked_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        # Generate new token
        from auth import generate_secure_token, hash_token
        
        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        now = datetime.now(timezone.utc)
        
        password_token = PasswordToken(
            token_hash=token_hash,
            portal_user_id=portal_user_id,
            client_id="ADMIN_INVITE",
            expires_at=now + timedelta(hours=24),
            created_by=user["portal_user_id"],
            send_count=1
        )
        
        token_doc = password_token.model_dump()
        for key in ["expires_at", "used_at", "revoked_at", "created_at"]:
            if token_doc.get(key) and isinstance(token_doc[key], datetime):
                token_doc[key] = token_doc[key].isoformat()
        
        await db.password_tokens.insert_one(token_doc)
        
        import os
        from services.notification_orchestrator import notification_orchestrator
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        setup_link = f"{frontend_url}/set-password?token={raw_token}"
        admin_name = target_admin.get("full_name", target_admin.get("auth_email", "Admin"))
        idempotency_key = f"{portal_user_id}_ADMIN_INVITE"
        await notification_orchestrator.send(
            template_key="ADMIN_INVITE",
            client_id=None,
            context={
                "recipient": target_admin["auth_email"],
                "admin_name": admin_name,
                "inviter_name": user.get("email", "System Administrator"),
                "setup_link": setup_link,
                "company_name": "Pleerity Enterprise Ltd",
            },
            idempotency_key=idempotency_key,
            event_type="admin_invite_resend",
        )
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=user["portal_user_id"],
            resource_type="portal_user",
            resource_id=portal_user_id,
            metadata={
                "action": "admin_invite_resent",
                "to_email": target_admin.get("auth_email"),
                "by_admin": user.get("email")
            }
        )
        
        return {
            "message": "Invitation resent successfully",
            "portal_user_id": portal_user_id,
            "email": target_admin["auth_email"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend admin invite error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resend invitation"
        )


# ============================================================================
# ADMIN ASSISTANT - CRN Lookup with AI Analysis
# ============================================================================

@router.get("/client-lookup")
async def lookup_client_by_crn(request: Request, crn: str = None):
    """
    Look up a client by Customer Reference Number (CRN).
    Returns full client snapshot for admin assistant context.
    RBAC enforced - admin only.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    if not crn or len(crn.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid CRN required (format: PLE-CVP-YYYY-XXXXX)"
        )
    
    crn = crn.strip().upper()
    
    try:
        # Find client by CRN
        client = await db.clients.find_one(
            {"customer_reference": crn},
            {"_id": 0}
        )
        
        if not client:
            # Log failed lookup attempt
            await create_audit_log(
                action=AuditAction.ADMIN_CRN_LOOKUP,
                actor_id=user.get("portal_user_id"),
                actor_role=UserRole.ROLE_ADMIN,
                metadata={
                    "crn": crn,
                    "found": False,
                    "admin_email": user.get("auth_email")
                }
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No client found with CRN: {crn}"
            )
        
        client_id = client.get("client_id")
        
        # Get full snapshot for assistant context
        properties = await db.properties.find(
            {"client_id": client_id},
            {"_id": 0}
        ).to_list(100)
        
        requirements = await db.requirements.find(
            {"client_id": client_id},
            {"_id": 0}
        ).to_list(500)
        
        documents = await db.documents.find(
            {"client_id": client_id},
            {"_id": 0, "document_id": 1, "property_id": 1, "requirement_id": 1,
             "file_name": 1, "status": 1, "uploaded_at": 1, "category": 1}
        ).to_list(500)
        
        portal_users = await db.portal_users.find(
            {"client_id": client_id},
            {"_id": 0, "password_hash": 0}
        ).to_list(10)
        
        # Calculate compliance summary
        total_reqs = len(requirements)
        compliant = sum(1 for r in requirements if r.get("status") == "COMPLIANT")
        overdue = sum(1 for r in requirements if r.get("status") == "OVERDUE")
        expiring = sum(1 for r in requirements if r.get("status") == "EXPIRING_SOON")
        
        snapshot = {
            "client": client,
            "properties": properties,
            "requirements": requirements,
            "documents": documents,
            "portal_users": portal_users,
            "compliance_summary": {
                "total_requirements": total_reqs,
                "compliant": compliant,
                "overdue": overdue,
                "expiring_soon": expiring,
                "compliance_percentage": round((compliant / total_reqs * 100) if total_reqs > 0 else 0, 1)
            },
            "property_count": len(properties),
            "document_count": len(documents)
        }
        
        # Log successful lookup
        await create_audit_log(
            action=AuditAction.ADMIN_CRN_LOOKUP,
            client_id=client_id,
            actor_id=user.get("portal_user_id"),
            actor_role=UserRole.ROLE_ADMIN,
            metadata={
                "crn": crn,
                "found": True,
                "admin_email": user.get("auth_email"),
                "client_email": client.get("email"),
                "properties_count": len(properties),
                "requirements_count": total_reqs
            }
        )
        
        return snapshot
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CRN lookup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to lookup client by CRN"
        )


class AdminAssistantRequest(BaseModel):
    crn: str
    question: str


# Admin-specific system prompt with elevated access
ADMIN_ASSISTANT_PROMPT = """You are the Admin Assistant for Compliance Vault Pro (Pleerity Enterprise Ltd).
You are helping an ADMINISTRATOR review a client's compliance status and data.

**Your role:**
- You have READ-ONLY access to the client data snapshot provided below.
- Explain the data clearly and professionally.
- Help the admin understand compliance gaps, issues, and client status.
- Provide actionable insights based on the data.

**Rules:**
1. Use ONLY the provided snapshot data - never invent or assume data.
2. If data is missing, clearly state what is missing.
3. Do NOT provide legal advice or predictions about enforcement.
4. Do NOT suggest modifying data - explain how the admin can do it themselves in the portal.
5. Be concise but thorough in your analysis.

**Output format:**
- Start with a direct answer to the question.
- Include relevant data points and evidence from the snapshot.
- If appropriate, suggest admin actions (view property, contact client, review document, etc.).
- Keep responses professional and audit-appropriate.

**Client Data Snapshot:**
{snapshot}
"""


@router.post("/assistant/ask")
async def admin_assistant_ask(request: Request, data: AdminAssistantRequest):
    """
    Admin AI Assistant endpoint with CRN-based client context.
    
    Server-side retrieval:
    1. Validates CRN and fetches client snapshot
    2. Injects snapshot into LLM prompt
    3. LLM cannot query DB directly
    4. Logs query + answer in AuditLog
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    # Validate inputs
    if not data.crn or len(data.crn.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid CRN required"
        )
    
    if not data.question or len(data.question.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty"
        )
    
    if len(data.question) > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question too long (max 1000 characters)"
        )
    
    crn = data.crn.strip().upper()
    question = data.question.strip()
    
    try:
        # Rate limiting - 20 questions per 10 minutes per admin
        from utils.rate_limiter import rate_limiter
        allowed, error_msg = await rate_limiter.check_rate_limit(
            key=f"admin_assistant_{user['portal_user_id']}",
            max_attempts=20,
            window_minutes=10
        )
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )
        
        # Step 1: Fetch client by CRN (server-side retrieval)
        client = await db.clients.find_one(
            {"customer_reference": crn},
            {"_id": 0}
        )
        
        if not client:
            await create_audit_log(
                action=AuditAction.ADMIN_ASSISTANT_QUERY,
                actor_id=user.get("portal_user_id"),
                actor_role=UserRole.ROLE_ADMIN,
                metadata={
                    "crn": crn,
                    "question": question[:200],
                    "error": "Client not found",
                    "admin_email": user.get("auth_email")
                }
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No client found with CRN: {crn}"
            )
        
        client_id = client.get("client_id")
        
        # Step 2: Build client snapshot
        properties = await db.properties.find(
            {"client_id": client_id},
            {"_id": 0}
        ).to_list(100)
        
        requirements = await db.requirements.find(
            {"client_id": client_id},
            {"_id": 0}
        ).to_list(500)
        
        documents = await db.documents.find(
            {"client_id": client_id},
            {"_id": 0, "document_id": 1, "property_id": 1, "requirement_id": 1,
             "file_name": 1, "status": 1, "uploaded_at": 1, "category": 1}
        ).to_list(500)
        
        # Compliance summary
        total_reqs = len(requirements)
        compliant = sum(1 for r in requirements if r.get("status") == "COMPLIANT")
        overdue = sum(1 for r in requirements if r.get("status") == "OVERDUE")
        expiring = sum(1 for r in requirements if r.get("status") == "EXPIRING_SOON")
        
        snapshot_data = {
            "client": {
                "crn": crn,
                "name": client.get("full_name"),
                "email": client.get("email"),
                "company": client.get("company_name"),
                "type": client.get("client_type"),
                "plan": client.get("billing_plan"),
                "subscription_status": client.get("subscription_status"),
                "onboarding_status": client.get("onboarding_status"),
                "created_at": client.get("created_at")
            },
            "compliance_summary": {
                "total_requirements": total_reqs,
                "compliant": compliant,
                "compliant_percentage": round((compliant / total_reqs * 100) if total_reqs > 0 else 0, 1),
                "overdue": overdue,
                "expiring_soon": expiring
            },
            "properties": [
                {
                    "nickname": p.get("nickname"),
                    "address": f"{p.get('address_line_1', '')}, {p.get('postcode', '')}",
                    "council": p.get("local_authority"),
                    "type": p.get("property_type"),
                    "compliance_status": p.get("compliance_status"),
                    "is_hmo": p.get("is_hmo")
                }
                for p in properties
            ],
            "requirements_by_status": {
                "COMPLIANT": [r.get("category") for r in requirements if r.get("status") == "COMPLIANT"],
                "OVERDUE": [{"category": r.get("category"), "property": r.get("property_id")} for r in requirements if r.get("status") == "OVERDUE"],
                "EXPIRING_SOON": [{"category": r.get("category"), "expiry": r.get("expiry_date")} for r in requirements if r.get("status") == "EXPIRING_SOON"]
            },
            "documents": [
                {
                    "name": d.get("file_name"),
                    "status": d.get("status"),
                    "category": d.get("category"),
                    "uploaded": d.get("uploaded_at")
                }
                for d in documents[:50]  # Limit to recent 50
            ]
        }
        
        # Step 3: Call LLM with injected snapshot (Google Generative AI)
        try:
            from utils.llm_chat import chat, _get_api_key
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Admin assistant unavailable (LLM not configured)",
            )
        if not _get_api_key():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Admin assistant unavailable (LLM_API_KEY not set)",
            )
        system_prompt = ADMIN_ASSISTANT_PROMPT.format(
            snapshot=json.dumps(snapshot_data, indent=2, default=str)
        )
        answer = await chat(
            system_prompt=system_prompt,
            user_text=question,
            model="gemini-2.5-flash",
        )
        
        # Step 4: Save query to history collection
        query_history_entry = {
            "query_id": f"aq-{uuid.uuid4().hex[:12]}",
            "admin_id": user.get("portal_user_id"),
            "admin_email": user.get("auth_email"),
            "client_id": client_id,
            "crn": crn,
            "client_name": client.get("full_name"),
            "question": question,
            "answer": answer,
            "model": "gemini-2.5-flash",
            "snapshot_summary": {
                "properties_count": len(properties),
                "requirements_count": total_reqs,
                "compliance_percentage": round((compliant / total_reqs * 100) if total_reqs > 0 else 0, 1)
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.admin_assistant_queries.insert_one(query_history_entry)
        
        # Step 5: Audit log - query and answer
        await create_audit_log(
            action=AuditAction.ADMIN_ASSISTANT_QUERY,
            client_id=client_id,
            actor_id=user.get("portal_user_id"),
            actor_role=UserRole.ROLE_ADMIN,
            metadata={
                "crn": crn,
                "question": question,
                "answer_preview": answer[:500] if answer else None,
                "admin_email": user.get("auth_email"),
                "client_email": client.get("email"),
                "properties_in_snapshot": len(properties),
                "requirements_in_snapshot": total_reqs,
                "model": "gemini-2.5-flash",
                "query_id": query_history_entry["query_id"]
            }
        )
        
        return {
            "crn": crn,
            "client_name": client.get("full_name"),
            "question": question,
            "answer": answer,
            "compliance_summary": snapshot_data["compliance_summary"],
            "properties_count": len(properties),
            "query_id": query_history_entry["query_id"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin assistant error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process assistant query"
        )



@router.get("/assistant/history")
async def get_assistant_query_history(
    request: Request,
    crn: Optional[str] = Query(default=None, description="Filter by client CRN"),
    limit: int = Query(default=50, ge=1, le=100),
    skip: int = Query(default=0, ge=0)
):
    """Get admin assistant query history.
    
    Returns a list of past queries with their answers, optionally filtered by client CRN.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Build query filter
        query_filter = {}
        if crn:
            query_filter["crn"] = crn.upper()
        
        # Get queries (newest first)
        queries = await db.admin_assistant_queries.find(
            query_filter,
            {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        
        # Get total count for pagination
        total = await db.admin_assistant_queries.count_documents(query_filter)
        
        return {
            "queries": queries,
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": total > skip + limit
        }
    
    except Exception as e:
        logger.error(f"Query history error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load query history"
        )


@router.get("/assistant/history/{query_id}")
async def get_assistant_query_detail(
    request: Request,
    query_id: str
):
    """Get a specific query by ID."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        query = await db.admin_assistant_queries.find_one(
            {"query_id": query_id},
            {"_id": 0}
        )
        
        if not query:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Query not found"
            )
        
        return query
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query detail error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load query detail"
        )