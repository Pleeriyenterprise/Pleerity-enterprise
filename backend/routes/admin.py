from fastapi import APIRouter, HTTPException, Request, Depends, status, Query, Body
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from database import database
from middleware import (
    admin_route_guard,
    require_owner,
    require_owner_or_admin,
    require_support_or_above,
)
from middleware.step_up_auth import require_recent_step_up
from models import (
    AuditAction,
    EmailTemplateAlias,
    PasswordToken,
    UserRole,
    UserStatus,
    PasswordStatus,
    ProvisioningJobStatus,
    OnboardingStatus,
    SubscriptionStatus,
)
from utils.audit import create_audit_log
from datetime import datetime, timezone, timedelta
from pathlib import Path
import logging
import uuid
import json
import os
from urllib.parse import urlparse
from fastapi.responses import FileResponse
from auth import create_access_token
from config.security_limits import security_limits
from utils.rate_limiter import rate_limiter, log_rate_limit_event
from utils.portal_user_scope import merge_active_portal_user
from services.portal_user_lifecycle_service import (
    archive_portal_user,
    restore_portal_user,
    permanent_delete_portal_user,
    permanent_delete_preflight,
    set_portal_user_test_like_flag,
)
from services.client_lifecycle_service import default_active_client_match, derive_client_lifecycle_status
from services.compliance_rules_registry import (
    jurisdiction_attribution_for_property,
    portfolio_jurisdiction_label,
    scoring_jurisdiction_for_property,
)
from models import ClientLifecycleStatus
from pymongo.errors import DuplicateKeyError
from utils.client_email import (
    canonical_client_email,
    client_email_taken,
    classify_clients_duplicate_key_error,
)
from utils.storage_paths import resolve_data_dir
from services.billing_presentation import lifecycle_status_label
from services.admin_client_support_search import run_admin_client_support_search
from services.admin_action_governance import (
    enforce_step_up_if_required,
    ensure_action_reason,
    normalized_admin_action_metadata,
)

logger = logging.getLogger(__name__)


async def _enqueue_recalc_after_standalone_authority_sync(
    *,
    property_id: Optional[str],
    client_id: Optional[str],
    portal_user_id: Optional[str],
    correlation_id: str,
    transition_fanout: Optional[Dict[str, Any]] = None,
    trigger_origin: str = "routes.admin._enqueue_recalc_after_standalone_authority_sync",
    propagation_stage: str = "post_admin_authority_sync",
    broadcast_traces: Optional[List[Optional[Dict[str, Any]]]] = None,
) -> None:
    """Stream B straggler: queue property score after sync_requirement_evidence_authority (no sync recalc here)."""
    pid = (property_id or "").strip()
    cid = (client_id or "").strip()
    if not pid or not cid:
        return
    from services.compliance_recalc_queue import (
        ACTOR_ADMIN,
        TRIGGER_DOC_STATUS_CHANGED,
        enqueue_compliance_recalc,
    )
    from services.authority_mutation_fanout import enqueue_compliance_recalc_with_fanout

    if transition_fanout is None and not broadcast_traces:
        await enqueue_compliance_recalc(
            property_id=pid,
            client_id=cid,
            trigger_reason=TRIGGER_DOC_STATUS_CHANGED,
            actor_type=ACTOR_ADMIN,
            actor_id=str(portal_user_id or "") or None,
            correlation_id=correlation_id,
        )
        return

    await enqueue_compliance_recalc_with_fanout(
        transition_fanout,
        property_id=pid,
        client_id=cid,
        trigger_reason=TRIGGER_DOC_STATUS_CHANGED,
        actor_type=ACTOR_ADMIN,
        actor_id=str(portal_user_id or "") or None,
        correlation_id=correlation_id,
        trigger_origin=trigger_origin,
        propagation_stage=propagation_stage,
        fanout_op="admin_transition_fanout",
        broadcast_traces=broadcast_traces,
    )


def _portal_user_role_for_audit(user: Dict[str, Any]) -> Optional[UserRole]:
    try:
        return UserRole(str(user.get("role") or ""))
    except ValueError:
        return None


def _portal_lifecycle_http(exc: ValueError) -> HTTPException:
    key = str(exc)
    if key.startswith("preflight_failed:"):
        blockers = [b for b in key.split(":", 1)[1].split(",") if b]
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Permanent delete not allowed", "blockers": blockers},
        )
    static = {
        "cannot_archive_self": (status.HTTP_400_BAD_REQUEST, "You cannot archive your own account"),
        "cannot_delete_self": (status.HTTP_400_BAD_REQUEST, "You cannot delete your own account permanently"),
        "user_not_found": (status.HTTP_404_NOT_FOUND, "User not found"),
        "already_archived": (status.HTTP_400_BAD_REQUEST, "User is already archived"),
        "not_archived": (status.HTTP_400_BAD_REQUEST, "User is not archived"),
        "owner_cannot_be_archived": (status.HTTP_403_FORBIDDEN, "OWNER cannot be archived"),
        "owner_cannot_be_deleted": (status.HTTP_403_FORBIDDEN, "OWNER cannot be permanently deleted"),
        "owner_cannot_be_flagged_test_like": (
            status.HTTP_403_FORBIDDEN,
            "Owner accounts cannot be marked as test or dummy",
        ),
        "last_active_admin": (
            status.HTTP_400_BAD_REQUEST,
            "Cannot archive the last active admin. Add another admin first.",
        ),
    }
    if key in static:
        code, detail = static[key]
        return HTTPException(status_code=code, detail=detail)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=key)
router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(admin_route_guard)])
LEGACY_JOBS_ENDPOINT_SUNSET = "2026-06-30T00:00:00Z"


class SupportDangerousActionReasonBody(BaseModel):
    """Reason captured for audited high-impact admin actions (support tooling)."""

    reason: str = Field(..., min_length=10, max_length=2000)


async def _enforce_admin_job_run_rate(portal_user_id: str) -> None:
    """Cap manual job / provisioning runner triggers per staff user per hour."""
    ok, msg = await rate_limiter.check_rate_limit(
        f"admin_job_run:{portal_user_id}",
        security_limits.admin_job_run_per_staff_per_hour,
        60,
    )
    if not ok:
        log_rate_limit_event("admin_job_run", portal_user_id, None)
        await create_audit_log(
            action=AuditAction.RATE_LIMIT_EXCEEDED,
            actor_id=portal_user_id,
            metadata={"scope": "admin_job_run", "portal_user_id": portal_user_id},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=msg or "Job run limit reached for this hour. Try again later.",
        )


def _iso_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _iso_or_none_billing_period(value: Any) -> Optional[str]:
    """Next renewal / period end: never expose invalid or epoch timestamps to the UI."""
    from services.billing_period_utils import normalize_stored_period_end_for_api

    dt = normalize_stored_period_end_for_api(value)
    return dt.isoformat() if dt else None


# Request models for admin invite
class AdminInviteRequest(BaseModel):
    email: EmailStr
    full_name: str


class PortalUserTestLikeBody(BaseModel):
    is_test_like: bool = Field(..., description="Mark account as test/dummy for narrowed permanent-delete policy")


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

        from services.job_run_service import STATUS_FAILED

        since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        failed_job_runs_24h = await db.job_runs.count_documents(
            {"status": STATUS_FAILED, "finished_at": {"$gte": since_24h}}
        )
        stuck_onboarding_active = await db.clients.count_documents(
            {
                "subscription_status": "ACTIVE",
                "onboarding_status": {
                    "$in": [OnboardingStatus.INTAKE_PENDING.value, OnboardingStatus.PROVISIONING.value]
                },
            }
        )
        provisioning_failed_recent = await db.provisioning_jobs.count_documents(
            {"status": ProvisioningJobStatus.FAILED.value}
        )
        total_overdue_requirements = await db.requirements.count_documents({"status": "OVERDUE"})
        high_risk_properties = await db.properties.count_documents({"compliance_status": "RED"})

        operational_alerts: List[Dict[str, Any]] = []
        if stuck_onboarding_active > 0:
            operational_alerts.append(
                {
                    "level": "warning",
                    "code": "STUCK_ONBOARDING",
                    "count": stuck_onboarding_active,
                    "message": f"{stuck_onboarding_active} active subscription(s) still in intake or provisioning onboarding.",
                    "hint": "Review clients list and control panel for activation and provisioning steps.",
                }
            )
        if failed_job_runs_24h > 0:
            operational_alerts.append(
                {
                    "level": "warning",
                    "code": "FAILED_AUTOMATION_RUNS",
                    "count": failed_job_runs_24h,
                    "message": f"{failed_job_runs_24h} automation job run(s) failed in the last 24 hours.",
                    "hint": "Check System Health / job runs and logs for recurring failures.",
                }
            )
        if provisioning_failed_recent > 0:
            operational_alerts.append(
                {
                    "level": "high",
                    "code": "PROVISIONING_FAILURES",
                    "count": provisioning_failed_recent,
                    "message": f"{provisioning_failed_recent} provisioning job(s) in FAILED state (open backlog).",
                    "hint": "Investigate provisioning_jobs and client intake records.",
                }
            )
        if total_overdue_requirements >= 50 or high_risk_properties >= 20:
            operational_alerts.append(
                {
                    "level": "info",
                    "code": "PORTFOLIO_RISK_ACCUMULATION",
                    "count": total_overdue_requirements,
                    "message": f"Portfolio load: {total_overdue_requirements} overdue requirement(s), {high_risk_properties} RED property/propert(ies).",
                    "hint": "High backlog may indicate clients needing outreach or bulk remediation.",
                }
            )
        
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
                "failed_job_runs_24h": failed_job_runs_24h,
                "stuck_onboarding_active": stuck_onboarding_active,
                "provisioning_failed_open": provisioning_failed_recent,
                "total_overdue_requirements": total_overdue_requirements,
                "high_risk_properties_red": high_risk_properties,
            },
            "compliance_overview": compliance_breakdown,
            "recent_activity": [],
            "operational_alerts": operational_alerts,
        }
    
    except Exception as e:
        import traceback
        logger.error("Admin dashboard error: %s\n%s", e, traceback.format_exc())
        detail = "Failed to load admin dashboard"
        err_str = str(e).strip()
        if err_str and len(err_str) < 200:
            detail = f"{detail}: {err_str}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        )


@router.get("/email/health", dependencies=[Depends(require_owner_or_admin)])
async def get_email_health(request: Request):
    """
    Admin-only: verify email delivery config (Postmark).
    Returns configured, provider, from_address, templates_present.
    """
    await admin_route_guard(request)
    postmark_token = (os.getenv("POSTMARK_SERVER_TOKEN") or "").strip()
    from_address = (os.getenv("EMAIL_SENDER") or "info@pleerityenterprise.co.uk").strip()
    configured = bool(postmark_token)
    provider = "postmark" if configured else "none"
    db = database.get_db()
    welcome = await db.notification_templates.find_one(
        {"template_key": "WELCOME_EMAIL", "is_active": True},
        {"_id": 1},
    )
    templates_present = welcome is not None
    return {
        "configured": configured,
        "provider": provider,
        "from_address": from_address,
        "templates_present": templates_present,
    }


@router.get("/documents/pending-verification", dependencies=[Depends(require_owner_or_admin)])
async def list_pending_verification_documents(
    request: Request,
    hours: int = Query(0, ge=0, le=720),
    client_id: Optional[str] = Query(None),
    property_id: Optional[str] = Query(None, description="Filter to PROPERTY-scoped evidence for this property"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """List documents with status UPLOADED. When hours > 0, only include rows with uploaded_at at least that many hours ago (staleness filter). Default hours=0 lists all pending uploads so new files appear immediately."""
    await admin_route_guard(request)
    db = database.get_db()
    try:
        query: Dict[str, Any] = {"status": "UPLOADED"}
        if hours and hours > 0:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            query["uploaded_at"] = {"$lte": cutoff}
        if client_id:
            query["client_id"] = client_id
        if property_id:
            query["$or"] = [
                {"property_id": property_id},
                {"authoritative_property_id": property_id},
            ]
            query["evidence_scope_type"] = {"$nin": ["INTAKE_STAGING", "PORTFOLIO", "UNRESOLVED"]}
        total = await db.documents.count_documents(query)
        cursor = db.documents.find(
            query,
            {
                "_id": 0,
                "document_id": 1,
                "client_id": 1,
                "property_id": 1,
                "authoritative_property_id": 1,
                "evidence_scope_type": 1,
                "evidence_scope_id": 1,
                "requirement_id": 1,
                "uploaded_at": 1,
                "file_name": 1,
                "document_type": 1,
                "match_outcome": 1,
                "match_confidence": 1,
                "predicted_document_type": 1,
                "mismatch_reason_code": 1,
                "mismatch_reason_text": 1,
                "detection_signals": 1,
                "evidence_satisfies_requirement": 1,
                "manual_review_flag": 1,
                "requirement_evidence_mismatch": 1,
                "evidence_match_legacy_state": 1,
                "evidence_review_state": 1,
                "assurance_tier": 1,
                "latest_validation_snapshot": 1,
                "review_required": 1,
                "review_decision_at": 1,
                "review_decision_by": 1,
                "external_verification_method": 1,
                "external_verification_reference": 1,
                "ai_assistance": 1,
            },
        ).sort("uploaded_at", 1).skip(skip).limit(limit)
        items = await cursor.to_list(limit)
        from services.evidence_review_migration import effective_assurance_tier, effective_evidence_review_state
        # Enrich with client display name and CRN for admin table
        client_ids = list({d.get("client_id") for d in items if d.get("client_id")})
        clients_map = {}
        if client_ids:
            clients_cursor = db.clients.find(
                {"client_id": {"$in": client_ids}},
                {"_id": 0, "client_id": 1, "full_name": 1, "customer_reference": 1}
            )
            for c in await clients_cursor.to_list(len(client_ids)):
                clients_map[c["client_id"]] = {
                        "client_name": c.get("full_name") or "-",
                        "crn": c.get("customer_reference") or "-",
                }
        req_ids = list({d.get("requirement_id") for d in items if d.get("requirement_id")})
        req_map: Dict[str, Dict[str, Any]] = {}
        if req_ids:
            rc = db.requirements.find(
                {"requirement_id": {"$in": req_ids}},
                {"_id": 0, "requirement_id": 1, "description": 1, "requirement_type": 1, "requirement_code": 1},
            )
            for r in await rc.to_list(len(req_ids)):
                rid = r.get("requirement_id")
                if rid:
                    req_map[str(rid)] = r
        for d in items:
            info = clients_map.get(d.get("client_id"), {})
            d["client_name"] = info.get("client_name", "-")
            d["crn"] = info.get("crn", "-")
            d["evidence_review_state"] = effective_evidence_review_state(d)
            d["assurance_tier"] = effective_assurance_tier(d)
            d.setdefault("latest_validation_snapshot", None)
            d.setdefault("review_required", None)
            d.setdefault("review_decision_at", None)
            d.setdefault("review_decision_by", None)
            d.setdefault("external_verification_method", None)
            d.setdefault("external_verification_reference", None)
            d.setdefault("ai_assistance", None)
            rr = req_map.get(str(d.get("requirement_id") or ""))
            if rr:
                d["requirement_label"] = (rr.get("description") or rr.get("requirement_type") or rr.get("requirement_code") or d.get("requirement_id"))
            else:
                d["requirement_label"] = None
        returned = len(items)
        return {
            "documents": items,
            "total": total,
            "returned": returned,
            "has_more": skip + returned < total,
            "hours": hours,
            "client_id_filter": client_id,
            "property_id_filter": property_id,
        }
    except Exception as e:
        logger.error(f"Pending verification list error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list pending verification documents"
        )


@router.get("/documents/unresolved", dependencies=[Depends(require_owner_or_admin)])
async def list_unresolved_evidence_documents(
    request: Request,
    client_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
):
    """Queue for UNRESOLVED evidence ownership documents requiring admin disposition."""
    await admin_route_guard(request)
    db = database.get_db()
    query: Dict[str, Any] = {"evidence_scope_type": "UNRESOLVED"}
    if client_id:
        query["client_id"] = client_id
    total = await db.documents.count_documents(query)
    rows = await db.documents.find(
        query,
        {
            "_id": 0,
            "document_id": 1,
            "client_id": 1,
            "property_id": 1,
            "authoritative_property_id": 1,
            "evidence_scope_type": 1,
            "evidence_scope_id": 1,
            "requirement_id": 1,
            "status": 1,
            "file_name": 1,
            "source": 1,
            "intake_session_id": 1,
            "manual_review_flag": 1,
            "uploaded_at": 1,
            "evidence_review_state": 1,
            "assurance_tier": 1,
            "latest_validation_snapshot": 1,
            "review_required": 1,
            "review_decision_at": 1,
            "review_decision_by": 1,
            "external_verification_method": 1,
            "external_verification_reference": 1,
            "ai_assistance": 1,
        },
    ).sort("uploaded_at", -1).skip(skip).limit(limit).to_list(limit)
    from services.evidence_review_migration import effective_assurance_tier, effective_evidence_review_state
    for r in rows:
        r["evidence_review_state"] = effective_evidence_review_state(r)
        r["assurance_tier"] = effective_assurance_tier(r)
        r.setdefault("latest_validation_snapshot", None)
        r.setdefault("review_required", None)
        r.setdefault("review_decision_at", None)
        r.setdefault("review_decision_by", None)
        r.setdefault("external_verification_method", None)
        r.setdefault("external_verification_reference", None)
        r.setdefault("ai_assistance", None)
    return {
        "documents": rows,
        "total": total,
        "returned": len(rows),
        "has_more": skip + len(rows) < total,
    }


class ResolveUnresolvedScopeRequest(BaseModel):
    scope_type: str  # PROPERTY | PORTFOLIO
    property_id: Optional[str] = None
    requirement_id: Optional[str] = None


@router.post("/documents/{document_id}/resolve-scope", dependencies=[Depends(require_owner_or_admin)])
async def resolve_unresolved_document_scope(
    request: Request,
    document_id: str,
    body: ResolveUnresolvedScopeRequest,
):
    """Resolve UNRESOLVED evidence to PROPERTY or PORTFOLIO scope with validation and audit."""
    user = await admin_route_guard(request)
    db = database.get_db()
    from services.authority_mutation_fanout import authority_sync_with_transition_observability
    from services.requirement_evidence_authority import normalize_document_evidence_scope
    from services.requirement_transition_observability import merge_document_path_lineage_flags, merge_review_admin_lineage_flags

    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if (doc.get("evidence_scope_type") or "").upper() != "UNRESOLVED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document is not UNRESOLVED")
    scope_type = (body.scope_type or "").strip().upper()
    if scope_type not in {"PROPERTY", "PORTFOLIO"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scope_type must be PROPERTY or PORTFOLIO")
    if scope_type == "PORTFOLIO":
        # Policy: explicit block in user/admin operational flows for now.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PORTFOLIO evidence uploads/resolution are not enabled in operational flows.",
        )
    if not (body.property_id or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PROPERTY resolution requires property_id")
    prop = await db.properties.find_one(
        {"property_id": body.property_id.strip(), "client_id": doc.get("client_id")},
        {"_id": 0, "property_id": 1},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found for this client")
    scope_patch = normalize_document_evidence_scope(
        property_id=body.property_id.strip(),
        client_id=doc.get("client_id") or "",
        evidence_scope_type="PROPERTY",
    )
    update_payload: Dict[str, Any] = {**scope_patch, "manual_review_flag": False}
    if (body.requirement_id or "").strip():
        req = await db.requirements.find_one(
            {
                "requirement_id": body.requirement_id.strip(),
                "client_id": doc.get("client_id"),
                "property_id": body.property_id.strip(),
            },
            {"_id": 0, "requirement_id": 1},
        )
        if not req:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requirement not found for property/client")
        update_payload["requirement_id"] = body.requirement_id.strip()
    await db.documents.update_one({"document_id": document_id}, {"$set": update_payload})
    if update_payload.get("requirement_id"):
        scope_fanout: Dict[str, Any] = {}
        await authority_sync_with_transition_observability(
            db,
            update_payload["requirement_id"],
            property_id=body.property_id.strip(),
            client_id=str(doc.get("client_id") or ""),
            correlation_base=f"AUTHORITY_SYNC:RESOLVE_UNRESOLVED_SCOPE:{document_id}",
            transition_origin="routes.admin.resolve_unresolved_document_scope",
            transition_fanout=scope_fanout,
        )
        merge_document_path_lineage_flags(scope_fanout, document_id=document_id)
        merge_review_admin_lineage_flags(scope_fanout, review_id=f"RESOLVE_SCOPE:{document_id}")
        await _enqueue_recalc_after_standalone_authority_sync(
            property_id=body.property_id.strip(),
            client_id=str(doc.get("client_id") or ""),
            portal_user_id=user.get("portal_user_id"),
            correlation_id=f"AUTHORITY_SYNC:RESOLVE_UNRESOLVED_SCOPE:{document_id}",
            transition_fanout=scope_fanout,
            trigger_origin="routes.admin.resolve_unresolved_document_scope",
            propagation_stage="post_resolve_unresolved_scope",
        )
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=user.get("portal_user_id"),
        client_id=doc.get("client_id"),
        resource_type="document",
        resource_id=document_id,
        metadata={
            "action_type": "UNRESOLVED_SCOPE_RESOLVED",
            "resolved_scope_type": "PROPERTY",
            "property_id": body.property_id.strip(),
            "requirement_id": update_payload.get("requirement_id"),
        },
    )
    return {"message": "Document scope resolved", "document_id": document_id, "resolved_scope_type": "PROPERTY"}


class AdminDocumentRequirementLinkRequest(BaseModel):
    requirement_id: str


@router.post("/documents/{document_id}/link-requirement", dependencies=[Depends(require_owner_or_admin)])
async def admin_link_document_requirement(request: Request, document_id: str, body: AdminDocumentRequirementLinkRequest):
    user = await admin_route_guard(request)
    db = database.get_db()
    from services.requirement_evidence_authority import document_evidence_compatible_with_requirement

    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    req = await db.requirements.find_one(
        {"requirement_id": body.requirement_id, "client_id": doc.get("client_id")},
        {"_id": 0},
    )
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    candidate = {**doc, "requirement_id": body.requirement_id}
    if not document_evidence_compatible_with_requirement(candidate, req):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document scope is incompatible with requirement scope")
    await db.documents.update_one(
        {"document_id": document_id},
        {"$set": {"requirement_id": body.requirement_id, "manual_review_flag": False}},
    )
    from services.compliance_evidence_record_service import safe_upsert_document_upload_evidence_for_linked_document

    await safe_upsert_document_upload_evidence_for_linked_document(
        db,
        client_id=str(doc.get("client_id") or ""),
        property_id=str(req.get("property_id") or doc.get("property_id") or ""),
        requirement_id=body.requirement_id,
        document_id=document_id,
        actor_user_id=user.get("portal_user_id"),
        filename=doc.get("file_name"),
        context="admin_link_requirement",
    )
    link_fanout: Dict[str, Any] = {}
    await authority_sync_with_transition_observability(
        db,
        body.requirement_id,
        property_id=str(req.get("property_id") or "") or None,
        client_id=str(doc.get("client_id") or ""),
        correlation_base=f"AUTHORITY_SYNC:ADMIN_LINK_REQUIREMENT:{document_id}",
        transition_origin="routes.admin.admin_link_document_requirement",
        transition_fanout=link_fanout,
    )
    merge_document_path_lineage_flags(link_fanout, document_id=document_id)
    merge_review_admin_lineage_flags(link_fanout, reviewer_retrigger_possible=True)
    await _enqueue_recalc_after_standalone_authority_sync(
        property_id=str(req.get("property_id") or ""),
        client_id=str(doc.get("client_id") or ""),
        portal_user_id=user.get("portal_user_id"),
        correlation_id=f"AUTHORITY_SYNC:ADMIN_LINK_REQUIREMENT:{document_id}",
        transition_fanout=link_fanout,
        trigger_origin="routes.admin.admin_link_document_requirement",
        propagation_stage="post_admin_link_requirement",
    )
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=user.get("portal_user_id"),
        client_id=doc.get("client_id"),
        resource_type="document",
        resource_id=document_id,
        metadata={"action_type": "DOCUMENT_REQUIREMENT_LINKED", "requirement_id": body.requirement_id},
    )
    return {"message": "Requirement linked", "document_id": document_id, "requirement_id": body.requirement_id}


@router.post("/documents/{document_id}/unlink-requirement", dependencies=[Depends(require_owner_or_admin)])
async def admin_unlink_document_requirement(request: Request, document_id: str):
    user = await admin_route_guard(request)
    db = database.get_db()
    from services.authority_mutation_fanout import authority_sync_with_transition_observability
    from services.requirement_transition_observability import merge_document_path_lineage_flags, merge_review_admin_lineage_flags

    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    prior_requirement_id = doc.get("requirement_id")
    await db.documents.update_one({"document_id": document_id}, {"$set": {"requirement_id": None}})
    if prior_requirement_id:
        unlink_fanout: Dict[str, Any] = {}
        await authority_sync_with_transition_observability(
            db,
            str(prior_requirement_id),
            property_id=str(doc.get("property_id") or "") or None,
            client_id=str(doc.get("client_id") or ""),
            correlation_base=f"AUTHORITY_SYNC:ADMIN_UNLINK_REQUIREMENT:{document_id}",
            transition_origin="routes.admin.admin_unlink_document_requirement",
            transition_fanout=unlink_fanout,
        )
        merge_document_path_lineage_flags(unlink_fanout, document_id=document_id)
        merge_review_admin_lineage_flags(unlink_fanout, reassignment_replay_possible=True)
        await _enqueue_recalc_after_standalone_authority_sync(
            property_id=str(doc.get("property_id") or ""),
            client_id=str(doc.get("client_id") or ""),
            portal_user_id=user.get("portal_user_id"),
            correlation_id=f"AUTHORITY_SYNC:ADMIN_UNLINK_REQUIREMENT:{document_id}",
            transition_fanout=unlink_fanout,
            trigger_origin="routes.admin.admin_unlink_document_requirement",
            propagation_stage="post_admin_unlink_requirement",
        )
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=user.get("portal_user_id"),
        client_id=doc.get("client_id"),
        resource_type="document",
        resource_id=document_id,
        metadata={"action_type": "DOCUMENT_REQUIREMENT_UNLINKED", "prior_requirement_id": prior_requirement_id},
    )
    return {"message": "Requirement unlinked", "document_id": document_id}


@router.post("/documents/{document_id}/reject-unresolved", dependencies=[Depends(require_owner_or_admin)])
async def admin_reject_unresolved_document(request: Request, document_id: str):
    user = await admin_route_guard(request)
    db = database.get_db()
    from services.authority_mutation_fanout import authority_sync_with_transition_observability
    from services.requirement_transition_observability import merge_document_path_lineage_flags, merge_review_admin_lineage_flags

    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    prior_requirement_id = doc.get("requirement_id")
    await db.documents.update_one(
        {"document_id": document_id},
        {"$set": {"status": "REJECTED", "manual_review_flag": True}},
    )
    if prior_requirement_id:
        rej_fanout: Dict[str, Any] = {}
        await authority_sync_with_transition_observability(
            db,
            str(prior_requirement_id),
            property_id=str(doc.get("property_id") or "") or None,
            client_id=str(doc.get("client_id") or ""),
            correlation_base=f"AUTHORITY_SYNC:ADMIN_REJECT_UNRESOLVED:{document_id}",
            transition_origin="routes.admin.admin_reject_unresolved_document",
            transition_fanout=rej_fanout,
        )
        merge_document_path_lineage_flags(rej_fanout, document_id=document_id)
        merge_review_admin_lineage_flags(rej_fanout, review_reversal_possible=True)
        await _enqueue_recalc_after_standalone_authority_sync(
            property_id=str(doc.get("property_id") or ""),
            client_id=str(doc.get("client_id") or ""),
            portal_user_id=user.get("portal_user_id"),
            correlation_id=f"AUTHORITY_SYNC:ADMIN_REJECT_UNRESOLVED:{document_id}",
            transition_fanout=rej_fanout,
            trigger_origin="routes.admin.admin_reject_unresolved_document",
            propagation_stage="post_admin_reject_unresolved",
        )
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=user.get("portal_user_id"),
        client_id=doc.get("client_id"),
        resource_type="document",
        resource_id=document_id,
        metadata={"action_type": "UNRESOLVED_DOCUMENT_REJECTED"},
    )
    return {"message": "Unresolved document rejected", "document_id": document_id}


class AdminEvidenceMatchResolutionBody(BaseModel):
    """Governed admin resolution for evidence document matching (audited)."""

    action: str = Field(
        ...,
        description="approve_override | reject_evidence | relink_requirement",
    )
    reason: Optional[str] = Field(None, max_length=2000)
    relink_requirement_id: Optional[str] = Field(None, description="When action=relink_requirement")


@router.post(
    "/documents/{document_id}/resolve-evidence-match",
    dependencies=[Depends(require_owner_or_admin)],
)
async def admin_resolve_evidence_match(
    request: Request,
    document_id: str,
    body: AdminEvidenceMatchResolutionBody,
):
    """Approve, relink, or reject evidence after automated mismatch / unknown-type detection."""
    user = await admin_route_guard(request)
    db = database.get_db()
    from services.authority_mutation_fanout import authority_sync_with_transition_observability
    from services.requirement_evidence_authority import document_evidence_compatible_with_requirement
    from services.requirement_transition_observability import merge_document_path_lineage_flags, merge_review_admin_lineage_flags
    from services.evidence_document_taxonomy import MATCH_OUTCOME_MATCH_CONFIRMED
    from services.evidence_document_match_engine import persist_document_evidence_match_after_extraction

    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    action = (body.action or "").strip().lower()
    cid = doc.get("client_id")
    prior_rid = doc.get("requirement_id")

    if action == "approve_override":
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.documents.update_one(
            {"document_id": document_id},
            {
                "$set": {
                    "reviewed_match_outcome": MATCH_OUTCOME_MATCH_CONFIRMED,
                    "reviewed_match_actor_id": user.get("portal_user_id"),
                    "reviewed_match_at": now_iso,
                    "evidence_satisfies_requirement": True,
                    "match_outcome": MATCH_OUTCOME_MATCH_CONFIRMED,
                    "requirement_evidence_mismatch": False,
                    "requirement_evidence_mismatch_reason": None,
                    "manual_review_flag": False,
                }
            },
        )
        if prior_rid:
            ov_fanout: Dict[str, Any] = {}
            await authority_sync_with_transition_observability(
                db,
                str(prior_rid),
                property_id=str(doc.get("property_id") or "") or None,
                client_id=str(cid or ""),
                correlation_base=f"AUTHORITY_SYNC:EVIDENCE_MATCH_APPROVE_OVERRIDE:{document_id}",
                transition_origin="routes.admin.admin_resolve_evidence_match",
                transition_fanout=ov_fanout,
            )
            merge_document_path_lineage_flags(ov_fanout, document_id=document_id)
            merge_review_admin_lineage_flags(
                ov_fanout,
                admin_override_possible=True,
                authority_override_replay_possible=True,
            )
            await _enqueue_recalc_after_standalone_authority_sync(
                property_id=str(doc.get("property_id") or ""),
                client_id=str(cid or ""),
                portal_user_id=user.get("portal_user_id"),
                correlation_id=f"AUTHORITY_SYNC:EVIDENCE_MATCH_APPROVE_OVERRIDE:{document_id}",
                transition_fanout=ov_fanout,
                trigger_origin="routes.admin.admin_resolve_evidence_match",
                propagation_stage="post_evidence_match_approve_override",
            )
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user.get("portal_user_id"),
            client_id=cid,
            resource_type="document",
            resource_id=document_id,
            metadata={
                "action_type": "EVIDENCE_MATCH_ADMIN_APPROVE_OVERRIDE",
                "reason": (body.reason or "")[:2000],
            },
        )
        return {"message": "Evidence match approved (override)", "document_id": document_id}

    if action == "reject_evidence":
        await db.documents.update_one(
            {"document_id": document_id},
            {"$set": {"status": "REJECTED", "manual_review_flag": True}},
        )
        if prior_rid:
            rej_match_fanout: Dict[str, Any] = {}
            await authority_sync_with_transition_observability(
                db,
                str(prior_rid),
                property_id=str(doc.get("property_id") or "") or None,
                client_id=str(cid or ""),
                correlation_base=f"AUTHORITY_SYNC:EVIDENCE_MATCH_REJECT:{document_id}",
                transition_origin="routes.admin.admin_resolve_evidence_match",
                transition_fanout=rej_match_fanout,
            )
            merge_document_path_lineage_flags(rej_match_fanout, document_id=document_id)
            merge_review_admin_lineage_flags(rej_match_fanout, review_reversal_possible=True)
            await _enqueue_recalc_after_standalone_authority_sync(
                property_id=str(doc.get("property_id") or ""),
                client_id=str(cid or ""),
                portal_user_id=user.get("portal_user_id"),
                correlation_id=f"AUTHORITY_SYNC:EVIDENCE_MATCH_REJECT:{document_id}",
                transition_fanout=rej_match_fanout,
                trigger_origin="routes.admin.admin_resolve_evidence_match",
                propagation_stage="post_evidence_match_reject",
            )
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user.get("portal_user_id"),
            client_id=cid,
            resource_type="document",
            resource_id=document_id,
            metadata={
                "action_type": "EVIDENCE_MATCH_ADMIN_REJECT",
                "reason": (body.reason or "")[:2000],
            },
        )
        return {"message": "Evidence rejected", "document_id": document_id}

    if action == "relink_requirement":
        rid = (body.relink_requirement_id or "").strip()
        if not rid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="relink_requirement_id required")
        req = await db.requirements.find_one(
            {"requirement_id": rid, "client_id": cid},
            {"_id": 0},
        )
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
        candidate = {**doc, "requirement_id": rid}
        if not document_evidence_compatible_with_requirement(candidate, req):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document scope is incompatible with requirement scope",
            )
        await db.documents.update_one(
            {"document_id": document_id},
            {"$set": {"requirement_id": rid, "manual_review_flag": True}},
        )
        from services.compliance_evidence_record_service import safe_upsert_document_upload_evidence_for_linked_document

        await safe_upsert_document_upload_evidence_for_linked_document(
            db,
            client_id=str(cid or ""),
            property_id=str(req.get("property_id") or doc.get("property_id") or ""),
            requirement_id=rid,
            document_id=document_id,
            actor_user_id=user.get("portal_user_id"),
            filename=doc.get("file_name"),
            context="admin_relink_requirement",
        )
        touched_property_ids: List[str] = []
        fanout_prior: Dict[str, Any] = {}
        fanout_new: Dict[str, Any] = {}
        pp = ""
        np = ""
        if prior_rid and str(prior_rid) != rid:
            await authority_sync_with_transition_observability(
                db,
                str(prior_rid),
                property_id=str(doc.get("property_id") or "") or None,
                client_id=str(cid or ""),
                correlation_base=f"AUTHORITY_SYNC:EVIDENCE_MATCH_RELINK:{document_id}:prior",
                transition_origin="routes.admin.admin_resolve_evidence_match",
                transition_fanout=fanout_prior,
            )
            merge_document_path_lineage_flags(fanout_prior, document_id=document_id)
            merge_review_admin_lineage_flags(
                fanout_prior,
                reassignment_replay_possible=True,
                review_chain_reentry_detected=True,
            )
            prior_req_row = await db.requirements.find_one(
                {"requirement_id": str(prior_rid), "client_id": cid},
                {"_id": 0, "property_id": 1},
            )
            pp = str((prior_req_row or {}).get("property_id") or doc.get("property_id") or "").strip()
            if pp:
                touched_property_ids.append(pp)
        await authority_sync_with_transition_observability(
            db,
            rid,
            property_id=str(req.get("property_id") or "") or None,
            client_id=str(cid or ""),
            correlation_base=f"AUTHORITY_SYNC:EVIDENCE_MATCH_RELINK:{document_id}:new",
            transition_origin="routes.admin.admin_resolve_evidence_match",
            transition_fanout=fanout_new,
        )
        merge_document_path_lineage_flags(fanout_new, document_id=document_id)
        merge_review_admin_lineage_flags(
            fanout_new,
            reassignment_replay_possible=True,
            review_chain_reentry_detected=bool(prior_rid and str(prior_rid) != rid),
        )
        np = str(req.get("property_id") or doc.get("property_id") or "").strip()
        if np and np not in touched_property_ids:
            touched_property_ids.append(np)
        try:
            await persist_document_evidence_match_after_extraction(db, document_id)
        except Exception:
            logger.exception("persist_document_evidence_match_after_extraction failed after relink document_id=%s", document_id)
        seen_enqueue_props = set()
        for prop_id in touched_property_ids:
            if not prop_id or prop_id in seen_enqueue_props:
                continue
            seen_enqueue_props.add(prop_id)
            primary = fanout_new if prop_id == np else fanout_prior if prop_id == pp else fanout_new
            broadcast: Optional[List[Optional[Dict[str, Any]]]] = None
            if (
                pp
                and np
                and pp == np == prop_id
                and fanout_prior.get("transition_id")
                and fanout_new.get("transition_id")
            ):
                broadcast = [fanout_prior, fanout_new]
            await _enqueue_recalc_after_standalone_authority_sync(
                property_id=prop_id,
                client_id=str(cid or ""),
                portal_user_id=user.get("portal_user_id"),
                correlation_id=f"AUTHORITY_SYNC:EVIDENCE_MATCH_RELINK:{document_id}:{prop_id}",
                transition_fanout=primary,
                broadcast_traces=broadcast,
                trigger_origin="routes.admin.admin_resolve_evidence_match",
                propagation_stage="post_evidence_match_relink",
            )
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user.get("portal_user_id"),
            client_id=cid,
            resource_type="document",
            resource_id=document_id,
            metadata={
                "action_type": "EVIDENCE_MATCH_ADMIN_RELINK",
                "prior_requirement_id": prior_rid,
                "new_requirement_id": rid,
                "reason": (body.reason or "")[:2000],
            },
        )
        return {"message": "Requirement relinked; match re-evaluated from extraction where available.", "document_id": document_id}

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown action")


class AdminEvidenceMatchBackfillBody(BaseModel):
    limit: int = Field(50, ge=1, le=500)
    dry_run: bool = False
    reason: str = Field(..., min_length=10, max_length=2000)


@router.post(
    "/documents/backfill-evidence-match",
    dependencies=[Depends(require_owner_or_admin)],
)
async def admin_backfill_evidence_match(request: Request, body: AdminEvidenceMatchBackfillBody):
    """
    Safe batch: persist match fields from existing extraction when possible; otherwise tag legacy
    unclassified (never silently as strong match). Re-syncs affected requirement authority.
    """
    user = await admin_route_guard(request)
    support_reason = ensure_action_reason("backfill_evidence_match_batch", body.reason)
    db = database.get_db()
    from services.authority_mutation_fanout import authority_sync_with_transition_observability
    from services.evidence_document_match_engine import persist_document_evidence_match_after_extraction
    from services.evidence_document_taxonomy import (
        EVIDENCE_MATCH_LEGACY_STATE_UNCLASSIFIED_PRE_ENGINE,
        MATCH_OUTCOME_NEEDS_ADMIN_REVIEW,
        REASON_CODE_LEGACY_UNCLASSIFIED,
    )
    from services.requirement_transition_observability import merge_document_path_lineage_flags

    q: Dict[str, Any] = {
        "$and": [
            {"deleted": {"$ne": True}},
            {"$or": [{"match_outcome": {"$exists": False}}, {"match_outcome": None}]},
        ]
    }
    rows = await db.documents.find(q, {"_id": 0}).limit(body.limit).to_list(body.limit)
    updated = 0
    preview: List[Dict[str, Any]] = []
    backfill_batch_tag = uuid.uuid4().hex[:16] if not body.dry_run else ""
    for doc in rows:
        did = doc.get("document_id")
        if not did:
            continue
        st = (doc.get("status") or "").upper()
        ai = doc.get("ai_extraction") if isinstance(doc.get("ai_extraction"), dict) else {}
        has_ext = (
            str(ai.get("status") or "").lower() == "completed"
            and isinstance(ai.get("data"), dict)
            and bool(doc.get("client_id"))
            and bool(doc.get("requirement_id"))
        )
        if has_ext:
            if body.dry_run:
                preview.append({"document_id": did, "action": "would_persist_from_extraction"})
                continue
            await persist_document_evidence_match_after_extraction(db, str(did))
            pid_bf = str(doc.get("property_id") or "").strip()
            cid_bf = str(doc.get("client_id") or "").strip()
            if pid_bf and cid_bf and backfill_batch_tag:
                await _enqueue_recalc_after_standalone_authority_sync(
                    property_id=pid_bf,
                    client_id=cid_bf,
                    portal_user_id=user.get("portal_user_id"),
                    correlation_id=f"AUTHORITY_SYNC:EVIDENCE_MATCH_BACKFILL:{backfill_batch_tag}:{pid_bf}",
                )
            updated += 1
            continue

        if st == "VERIFIED":
            patch = {"evidence_match_legacy_state": EVIDENCE_MATCH_LEGACY_STATE_UNCLASSIFIED_PRE_ENGINE}
        elif st in ("PENDING", "UPLOADED", ""):
            patch = {
                "evidence_match_legacy_state": EVIDENCE_MATCH_LEGACY_STATE_UNCLASSIFIED_PRE_ENGINE,
                "match_outcome": MATCH_OUTCOME_NEEDS_ADMIN_REVIEW,
                "predicted_document_type": "UNKNOWN",
                "mismatch_reason_code": REASON_CODE_LEGACY_UNCLASSIFIED,
                "mismatch_reason_text": "Legacy document before evidence match engine; needs review or re-analysis.",
                "evidence_satisfies_requirement": False,
                "manual_review_flag": True,
            }
        else:
            patch = {"evidence_match_legacy_state": EVIDENCE_MATCH_LEGACY_STATE_UNCLASSIFIED_PRE_ENGINE}

        if body.dry_run:
            preview.append({"document_id": did, "action": "would_tag_legacy", "status": st})
            continue
        await db.documents.update_one({"document_id": did}, {"$set": patch})
        rid = doc.get("requirement_id")
        if rid:
            pid_bf = str(doc.get("property_id") or "").strip()
            cid_bf = str(doc.get("client_id") or "").strip()
            bf_fanout: Dict[str, Any] = {}
            await authority_sync_with_transition_observability(
                db,
                str(rid),
                property_id=str(doc.get("property_id") or "") or None,
                client_id=str(doc.get("client_id") or ""),
                correlation_base=f"AUTHORITY_SYNC:EVIDENCE_MATCH_BACKFILL:{backfill_batch_tag}:{pid_bf}",
                transition_origin="routes.admin.admin_backfill_evidence_match",
                transition_fanout=bf_fanout,
            )
            merge_document_path_lineage_flags(bf_fanout, document_id=str(did))
            if pid_bf and cid_bf and backfill_batch_tag:
                await _enqueue_recalc_after_standalone_authority_sync(
                    property_id=pid_bf,
                    client_id=cid_bf,
                    portal_user_id=user.get("portal_user_id"),
                    correlation_id=f"AUTHORITY_SYNC:EVIDENCE_MATCH_BACKFILL:{backfill_batch_tag}:{pid_bf}",
                    transition_fanout=bf_fanout,
                    trigger_origin="routes.admin.admin_backfill_evidence_match",
                    propagation_stage="post_evidence_match_backfill",
                )
        updated += 1

    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=user.get("portal_user_id"),
        client_id=None,
        resource_type="document",
        resource_id="batch",
        metadata={
            "action_type": "EVIDENCE_MATCH_BACKFILL",
            **normalized_admin_action_metadata(
                "backfill_evidence_match_batch",
                support_reason,
                {"requested_limit": body.limit, "dry_run": body.dry_run},
            ),
            "updated": updated,
            "dry_run": body.dry_run,
            "limit": body.limit,
        },
    )
    return {"updated": updated, "dry_run": body.dry_run, "preview": preview[:25], "scanned": len(rows)}


class AdminEvidenceReviewBackfillBody(BaseModel):
    limit: int = Field(500, ge=1, le=5000)
    dry_run: bool = True
    force: bool = False


@router.post(
    "/documents/backfill-evidence-review-v2",
    dependencies=[Depends(require_owner_or_admin)],
)
async def admin_backfill_evidence_review_v2(request: Request, body: AdminEvidenceReviewBackfillBody):
    """Backfill evidence_review_state + assurance_tier from legacy status mapping (safe/idempotent)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    from services.evidence_review_backfill import scan_evidence_review_backfill

    result = await scan_evidence_review_backfill(
        db,
        limit=body.limit,
        force=body.force,
        dry_run=body.dry_run,
    )

    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=user.get("portal_user_id"),
        client_id=None,
        resource_type="document",
        resource_id="batch",
        metadata={
            "action_type": "EVIDENCE_REVIEW_V2_BACKFILL",
            "dry_run": body.dry_run,
            "force": body.force,
            "limit": body.limit,
            "scanned": result.get("scanned"),
            "updated": result.get("updated"),
            "planned_updates": result.get("planned_updates"),
        },
    )
    return result


@router.get("/requirements/authority-drift", dependencies=[Depends(require_owner_or_admin)])
async def list_requirement_authority_drift(
    request: Request,
    client_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
):
    """Detect requirement mirror drift where legacy mirrored fields diverge from evidence_authority."""
    await admin_route_guard(request)
    db = database.get_db()
    from services.requirement_evidence_authority import detect_requirement_mirror_drift

    q: Dict[str, Any] = {"evidence_authority_synced_at": {"$ne": None}, "evidence_authority.version": {"$gte": 1}}
    if client_id:
        q["client_id"] = client_id
    rows = await db.requirements.find(q, {"_id": 0}).limit(limit).to_list(limit)
    drifts = []
    for r in rows:
        d = detect_requirement_mirror_drift(r)
        if d.get("drift"):
            drifts.append(
                {
                    "requirement_id": r.get("requirement_id"),
                    "client_id": r.get("client_id"),
                    "property_id": r.get("property_id"),
                    "reasons": d.get("reasons"),
                    "expected": d.get("expected"),
                    "actual": {
                        "status": r.get("status"),
                        "evidence_state": r.get("evidence_state"),
                        "due_date": r.get("due_date"),
                    },
                }
            )
    return {"checked": len(rows), "drift_count": len(drifts), "drifts": drifts}


@router.get("/documents/{document_id}/file", dependencies=[Depends(require_owner_or_admin)])
async def get_admin_document_file(
    request: Request,
    document_id: str,
    download: bool = Query(False, description="If true, return as attachment"),
):
    """Admin view or download any document by ID (e.g. for pending verification review)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    from routes.documents import _resolve_document_file_path
    document, file_path, media_type, filename = await _resolve_document_file_path(db, document_id)
    await create_audit_log(
        action=AuditAction.DOCUMENT_VIEWED,
        actor_id=user.get("portal_user_id") or user.get("user_id") or "admin",
        client_id=document.get("client_id"),
        resource_type="document",
        resource_id=document_id,
        metadata={"file_name": filename, "download": download, "admin": True},
    )
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@router.get("/extraction-queue", dependencies=[Depends(require_owner_or_admin)])
async def list_extraction_queue(
    request: Request,
    status_filter: Optional[List[str]] = Query(None, alias="status"),
    client_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
):
    """List extracted_documents for review: NEEDS_REVIEW and/or FAILED. Admin can confirm/reject via document apply/reject endpoints."""
    await admin_route_guard(request)
    db = database.get_db()
    try:
        query = {}
        if status_filter:
            query["status"] = {"$in": status_filter}
        else:
            query["status"] = {"$in": ["NEEDS_REVIEW", "FAILED"]}
        if client_id:
            query["client_id"] = client_id
        total = await db.extracted_documents.count_documents(query)
        cursor = db.extracted_documents.find(
            query,
            {"_id": 0, "extraction_id": 1, "document_id": 1, "client_id": 1, "file_name": 1, "status": 1, "extracted": 1, "errors": 1, "source": 1}
        ).sort("audit.created_at", -1).skip(skip).limit(limit)
        items = []
        async for row in cursor:
            items.append({
                "extraction_id": row.get("extraction_id"),
                "document_id": row.get("document_id"),
                "client_id": row.get("client_id"),
                "file_name": row.get("file_name"),
                "status": row.get("status"),
                "extracted": row.get("extracted"),
                "errors": row.get("errors"),
                "source": row.get("source"),
            })
        return {"items": items, "total": total, "returned": len(items)}
    except Exception as e:
        logger.error("Extraction queue list error: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list extraction queue")


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
        since_dt = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        status_order = {"failed": 0, "skipped": 1, "sent": 2}

        items_from_msg = []
        count_msg = 0
        if status is None or status in ("sent", "failed"):
            # Accept both orchestrator (SENT/FAILED, template_key) and legacy (sent/failed, template_alias)
            q = {
                "created_at": {"$gte": since_dt},
                "status": {"$in": ["sent", "failed", "SENT", "FAILED"]},
                "$or": [{"channel": {"$exists": False}}, {"channel": "EMAIL"}],
            }
            if status:
                q["status"] = {"$in": [status, status.upper()]}
            if template_alias:
                q["$and"] = [
                    {"$or": [{"template_alias": template_alias}, {"template_key": template_alias}]},
                ]
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
                        "template_key": 1,
                        "status": 1,
                        "client_id": 1,
                        "message_id": 1,
                        "provider_error_type": 1,
                        "provider_error_code": 1,
                        "error_message": 1,
                    },
                )
                .sort("created_at", -1)
                .limit(2000)
            )
            raw = await cursor.to_list(2000)
            for r in raw:
                st = r.get("status") or ""
                status_normalized = st.lower() if st in ("SENT", "FAILED", "sent", "failed") else st
                items_from_msg.append({
                    "created_at": r.get("created_at"),
                    "template_alias": r.get("template_alias") or r.get("template_key"),
                    "status": status_normalized,
                    "client_id": r.get("client_id"),
                    "message_id": r.get("message_id"),
                    "provider_error_type": r.get("provider_error_type"),
                    "provider_error_code": r.get("provider_error_code"),
                    "error_message": r.get("error_message"),
                })

        items_from_audit = []
        count_audit = 0
        if status is None or status == "skipped":
            q = {"action": AuditAction.EMAIL_SKIPPED_NO_RECIPIENT.value, "timestamp": {"$gte": since_dt}}
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
        # Diagnostic empty reason (Priority 5: make empty states diagnostic)
        empty_reason = None
        if total == 0:
            if template_alias or client_id or status:
                empty_reason = "template_or_filter_excluded_all"
            else:
                empty_reason = "no_sends_attempted"
        return {
            "total": total,
            "returned": returned,
            "has_more": skip + returned < total,
            "items": page,
            "empty_reason": empty_reason,
        }
    except Exception as e:
        logger.error(f"Email delivery list error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load email delivery list",
        )


@router.get("/search")
async def global_search(
    request: Request,
    q: str = "",
    limit: int = 20,
    include_archived: bool = Query(False, description="Include archived, purge-eligible, and suspended clients"),
):
    """
    Global search across clients by CRN, email, name, phone, order reference, or postcode.
    By default excludes clients hidden from the active admin list (archived, purge queue, suspended).
    Set include_archived=true to search those as well (e.g. recovery on dormant accounts).
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    if not q or len(q.strip()) < 2:
        return {"results": [], "query": q, "total": 0, "include_archived": include_archived}

    search_term = q.strip()

    try:
        normalized_results = await run_admin_client_support_search(
            db,
            search_term=search_term,
            limit=limit,
            include_archived=include_archived,
        )

        await create_audit_log(
            action=AuditAction.ADMIN_SEARCH_PERFORMED,
            actor_id=user.get("portal_user_id"),
            actor_role=UserRole.ROLE_ADMIN,
            metadata={
                "search_query": search_term,
                "results_count": len(normalized_results),
                "include_archived": include_archived,
            },
        )

        return {
            "results": normalized_results,
            "query": search_term,
            "total": len(normalized_results),
            "include_archived": include_archived,
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


# Map plan_code query param (solo|portfolio|pro) to billing_plan value
_PLAN_CODE_TO_BILLING = {"solo": "PLAN_1_SOLO", "portfolio": "PLAN_2_PORTFOLIO", "pro": "PLAN_3_PRO"}


@router.get("/clients")
async def get_clients(
    request: Request,
    skip: int = 0,
    limit: int = 50,
    subscription_status: str = None,
    onboarding_status: str = None,
    plan_code: str = None,
    min_properties: int = None,
    max_properties: int = None,
    risk_band: str = None,
    q: str = None,
    lifecycle_bucket: str = None,
    include_archived_clients: bool = False,
    account_environment: str = None,
):
    """
    Get all clients (admin only). Supports filtering by subscription_status, onboarding_status,
    plan_code (solo|portfolio|pro), min_properties, max_properties, and q (search name/email/CRN).
    lifecycle_bucket: active (default), all, archived, purge_eligible, test_like, pending_setup, suspended.
    By default archived/purge-eligible/deleted clients are excluded unless include_archived_clients or bucket=all.
    account_environment: optional live | non_production — intersects with lifecycle_bucket (live = not is_test_like).
    """
    await admin_route_guard(request)
    db = database.get_db()

    try:
        import re
        # Base match on clients collection
        match: Dict[str, Any] = {}
        if subscription_status:
            match["subscription_status"] = subscription_status.strip().upper()
        if onboarding_status:
            match["onboarding_status"] = onboarding_status.strip().upper()
        if plan_code:
            plan_key = (plan_code or "").strip().lower()
            if plan_key in _PLAN_CODE_TO_BILLING:
                match["billing_plan"] = _PLAN_CODE_TO_BILLING[plan_key]
        if q and q.strip():
            q_esc = re.escape(q.strip())
            match["$or"] = [
                {"full_name": {"$regex": q_esc, "$options": "i"}},
                {"email": {"$regex": q_esc, "$options": "i"}},
                {"customer_reference": {"$regex": q_esc, "$options": "i"}},
            ]
        # risk_band filter reserved for future use (no-op when portfolio_score_band not stored)

        bucket = (lifecycle_bucket or "active").strip().lower()
        if bucket == "all":
            pass
        elif bucket == "active":
            if not include_archived_clients:
                match = {"$and": [match, default_active_client_match()]} if match else default_active_client_match()
        elif bucket == "archived":
            match = {"$and": [match, {"client_lifecycle_status": ClientLifecycleStatus.ARCHIVED.value}]} if match else {"client_lifecycle_status": ClientLifecycleStatus.ARCHIVED.value}
        elif bucket == "purge_eligible":
            pe = {"$or": [
                {"client_lifecycle_status": ClientLifecycleStatus.PURGE_ELIGIBLE.value},
                {"purge_eligible": True},
            ]}
            match = {"$and": [match, pe]} if match else pe
        elif bucket == "test_like":
            tl = {"is_test_like": True}
            match = {"$and": [match, tl]} if match else tl
        elif bucket == "pending_setup":
            ps = {"onboarding_status": {"$ne": OnboardingStatus.PROVISIONED.value}}
            parts = [match, ps] if match else [ps]
            if not include_archived_clients:
                parts.append(default_active_client_match())
            match = {"$and": parts}
        elif bucket == "suspended":
            sus = {
                "$or": [
                    {"client_lifecycle_status": ClientLifecycleStatus.SUSPENDED.value},
                    {"subscription_status": SubscriptionStatus.CANCELLED.value},
                ]
            }
            match = {"$and": [match, sus]} if match else sus
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid lifecycle_bucket (use active, all, archived, purge_eligible, test_like, pending_setup, suspended)",
            )

        env = (account_environment or "").strip().lower()
        if env == "live":
            live_q = {"$or": [{"is_test_like": {"$ne": True}}, {"is_test_like": {"$exists": False}}]}
            match = {"$and": [match, live_q]} if match else live_q
        elif env == "non_production":
            np = {"is_test_like": True}
            match = {"$and": [match, np]} if match else np
        elif env not in ("", "all", "none", None):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid account_environment (use live, non_production, or omit)",
            )

        pipeline = [
            {"$match": match},
            {"$lookup": {"from": "client_billing", "localField": "client_id", "foreignField": "client_id", "as": "_billing"}},
            {"$lookup": {"from": "properties", "localField": "client_id", "foreignField": "client_id", "as": "_props"}},
            {
                "$addFields": {
                    "property_count": {"$size": "$_props"},
                    "current_period_end": {"$arrayElemAt": ["$_billing.current_period_end", 0]},
                    "cancel_at_period_end": {"$arrayElemAt": ["$_billing.cancel_at_period_end", 0]},
                    "plan_code": "$billing_plan",
                }
            },
        ]
        if min_properties is not None:
            pipeline.append({"$match": {"property_count": {"$gte": min_properties}}})
        if max_properties is not None:
            pipeline.append({"$match": {"property_count": {"$lte": max_properties}}})

        # Facet: total count and paginated list
        pipeline.append({
            "$facet": {
                "total": [{"$count": "n"}],
                "clients": [
                    {"$skip": skip},
                    {"$limit": limit},
                    {"$addFields": {"portfolio_score_band": None}},
                    {
                        "$project": {
                            "_id": 0,
                            "_billing": 0,
                            "_props": 0,
                        }
                    },
                ]
            }
        })

        cursor = db.clients.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        out = result[0] if result else {}
        total = (out.get("total") or [{}])[0].get("n", 0)
        clients = out.get("clients") or []

        # Normalize datetime and bool for JSON
        for c in clients:
            val = c.get("current_period_end")
            if hasattr(val, "isoformat"):
                c["current_period_end"] = val.isoformat()
            if c.get("cancel_at_period_end") is None:
                c["cancel_at_period_end"] = False
            c["derived_client_lifecycle_status"] = derive_client_lifecycle_status(c)

        return {
            "clients": clients,
            "total": total,
            "skip": skip,
            "limit": limit,
            "lifecycle_bucket": bucket,
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error("Get clients error: %s\n%s", e, traceback.format_exc())
        detail = "Failed to load clients"
        err_str = str(e).strip()
        if err_str and len(err_str) < 200:
            detail = f"{detail}: {err_str}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
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
        from services.requirement_truth import enrich_requirements_for_admin

        requirements = await enrich_requirements_for_admin(db, requirements)
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


@router.get("/clients/{client_id}/avatar")
async def get_client_avatar(request: Request, client_id: str):
    """Return a client's profile picture (admin). 404 if none."""
    await admin_route_guard(request)
    db = database.get_db()
    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "avatar_ext": 1}
    )
    if not client or not client.get("avatar_ext"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No profile picture")
    ext = client.get("avatar_ext", ".jpg")
    avatars_dir = Path(resolve_data_dir()) / "data" / "profile_avatars"
    file_path = avatars_dir / f"{client_id}{ext}"
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No profile picture")
    media = "image/jpeg" if ext == ".jpg" else ("image/png" if ext == ".png" else "image/webp")
    return FileResponse(path=str(file_path), media_type=media)


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


@router.get("/ledger")
async def get_admin_ledger(
    request: Request,
    client_id: str = Query(..., description="Client ID to scope ledger (required)"),
    property_id: Optional[str] = Query(None),
    trigger_type: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    cursor: Optional[str] = Query(None),
):
    """Admin: paginated score ledger for a client (same shape as client ledger API)."""
    await admin_route_guard(request)
    try:
        from services.score_ledger_service import list_ledger
        data = await list_ledger(
            client_id=client_id,
            property_id=property_id,
            trigger_type=trigger_type,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            cursor=cursor,
        )
        return data
    except Exception as e:
        logger.error(f"Admin ledger error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load score ledger",
        )


@router.get("/ledger/export.csv")
async def export_admin_ledger_csv(
    request: Request,
    client_id: str = Query(..., description="Client ID to export ledger for (required)"),
    property_id: Optional[str] = Query(None),
    trigger_type: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
):
    """Admin: export score ledger as CSV for a client (max 5000 rows)."""
    await admin_route_guard(request)
    try:
        from services.score_ledger_service import list_ledger_export
        import csv as csv_module
        import io
        items = await list_ledger_export(
            client_id=client_id,
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
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            iter([out.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=score_ledger_export.csv"},
        )
    except Exception as e:
        logger.error(f"Admin ledger export error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export score ledger",
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


@router.get("/clients/{client_id}/compliance-activity")
async def get_client_compliance_activity(
    request: Request,
    client_id: str,
    property_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Admin visibility into Action -> Outcome activity log for a client/property."""
    await admin_route_guard(request)
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "client_id": 1})
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    try:
        from services.compliance_outcome_engine import list_activity
        return await list_activity(client_id=client_id, property_id=property_id, limit=limit)
    except Exception as e:
        logger.error(f"Compliance activity list error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load compliance activity",
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


@router.get("/properties/{property_id}/requirements/plan-preview")
async def get_property_requirements_plan_preview(
    request: Request,
    property_id: str,
    include_mongo_snapshot: bool = Query(
        True,
        description="Include current requirements rows + drift vs planned types (staging / debugging).",
    ),
    include_explanations: bool = Query(
        False,
        description="Include per-row plan explanations and catalog-key inclusion/exclusion reasons.",
    ),
):
    """Read-only: catalog registry plan for this property (no writes).

    Intended for staging validation and support debugging — not for portal clients.
    RBAC: same as other ``/api/admin`` routes — ``admin_route_guard`` / ``require_admin`` (Owner, Admin,
    Support, Content, Auditor). Compare ``planned_types`` to Mongo
    when ``include_mongo_snapshot`` is true; after registry publish/revert use
    ``POST /api/admin/properties/{id}/requirements/sync-from-registry`` (staff) or the client
    ``POST /api/properties/{id}/requirements/sync`` to reconcile drift.
    """
    await admin_route_guard(request)
    db = database.get_db()
    try:
        prop = await db.properties.find_one({"property_id": property_id}, {"_id": 0})
        if not prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found",
            )
        client_id = prop.get("client_id")
        client_doc = (
            await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1})
            if client_id
            else None
        ) or {}

        from services.requirement_catalog import explain_catalog_keys_for_property
        from services.compliance_registry_publish_service import fetch_active_published_registry_entries
        from services.requirement_materialization_service import generate_requirements

        published = await fetch_active_published_registry_entries(db)
        planned_items = generate_requirements(
            prop,
            client_doc,
            include_explanations=include_explanations,
            published_registry_entries=published,
        )
        planned_types = sorted({str(p["requirement_type"]) for p in planned_items})

        portfolio = portfolio_jurisdiction_label(prop, client_doc)
        scoring_j = scoring_jurisdiction_for_property(prop, client_doc)

        out: Dict[str, Any] = {
            "property_id": property_id,
            "client_id": client_id,
            "portfolio_jurisdiction_label": portfolio,
            "scoring_jurisdiction": scoring_j,
            "planned_types": planned_types,
            "planned": planned_items,
            "plan_builder": "build_requirement_plan_for_property",
            "preview_serializer": "serialize_registry_plan_items",
            "published_registry": {
                "active": bool(published),
                "entry_count": len(published) if isinstance(published, dict) else 0,
            },
        }
        if include_explanations:
            out["catalog_key_explanations"] = explain_catalog_keys_for_property(prop, client_doc)

        if include_mongo_snapshot and client_id:
            rows = await db.requirements.find(
                {"property_id": property_id, "client_id": client_id},
                {
                    "_id": 0,
                    "requirement_id": 1,
                    "requirement_type": 1,
                    "requirement_code": 1,
                    "requirement_generation_source": 1,
                    "client_surface_visible": 1,
                    "applicability": 1,
                    "status": 1,
                    "is_tracked": 1,
                },
            ).to_list(500)
            mongo_types = {str(r.get("requirement_type") or "").lower() for r in rows if r.get("requirement_type")}
            planned_lower = {t.lower() for t in planned_types}
            by_source: Dict[str, int] = {}
            visible_count = 0
            for r in rows:
                src = r.get("requirement_generation_source") or "(unset)"
                by_source[src] = by_source.get(src, 0) + 1
                if r.get("client_surface_visible") is not False:
                    visible_count += 1
            out["mongo_snapshot"] = {
                "row_count": len(rows),
                "rows": rows,
                "requirement_generation_source_counts": by_source,
                "portal_visible_row_count": visible_count,
                "types_in_mongo_not_in_plan": sorted(mongo_types - planned_lower),
                "types_in_plan_not_in_mongo": sorted(planned_lower - mongo_types),
            }
        elif include_mongo_snapshot:
            out["mongo_snapshot"] = {"error": "property_missing_client_id"}

        return out
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Admin requirements plan-preview error property_id=%s: %s", property_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to build requirements plan preview",
        )


@router.post("/properties/{property_id}/requirements/sync-from-registry")
async def admin_post_property_requirements_sync_from_registry(
    request: Request,
    property_id: str,
    user: dict = Depends(require_support_or_above),
):
    """
    Re-run catalog + published-registry materialisation for one property (any client).

    Use after **publish** or **revert** so Mongo ``requirements`` rows match the active snapshot; does not
    fan out to other properties. Same core work as ``POST /api/properties/{id}/requirements/sync`` for
    the owning client, but callable from the admin console without client portal context.
    """
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id},
        {"_id": 0, "client_id": 1, "property_id": 1},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    client_id = prop.get("client_id")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Property has no client_id",
        )

    from services.compliance_recalc_queue import (
        ACTOR_ADMIN,
        TRIGGER_ADMIN_MANUAL_JOB,
        enqueue_compliance_recalc,
    )
    from services.provisioning import provisioning_service
    from services.requirement_materialization_service import materialize_requirements_for_property

    result = await materialize_requirements_for_property(client_id, property_id, reconcile_obsolete=True)
    if not (result or {}).get("ok", True) and (result or {}).get("reason") == "property_not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    await provisioning_service._update_property_compliance(property_id)
    corr = f"{TRIGGER_ADMIN_MANUAL_JOB}:REGISTRY_SYNC:{property_id}:{uuid.uuid4().hex[:12]}"
    await enqueue_compliance_recalc(
        property_id=property_id,
        client_id=client_id,
        trigger_reason=TRIGGER_ADMIN_MANUAL_JOB,
        actor_type=ACTOR_ADMIN,
        actor_id=str(user.get("portal_user_id") or user.get("user_id") or ""),
        correlation_id=corr,
    )

    ip_address = request.client.host if request.client else None
    await create_audit_log(
        action=AuditAction.COMPLIANCE_REGISTRY_ADMIN_PROPERTY_REQUIREMENTS_SYNCED,
        actor_role=_portal_user_role_for_audit(user),
        actor_id=str(user.get("portal_user_id") or user.get("user_id") or ""),
        client_id=client_id,
        resource_type="property",
        resource_id=property_id,
        metadata={"planned_types_count": len((result or {}).get("planned_types") or [])},
        ip_address=ip_address,
    )

    return {
        "ok": True,
        "property_id": property_id,
        "client_id": client_id,
        **(result or {}),
    }


class _ActionLinksDraftBody(BaseModel):
    links: List[Dict[str, Any]] = Field(default_factory=list)


@router.get("/properties/{property_id}/requirements/{requirement_id}/action-links")
async def admin_get_requirement_action_links_preview(
    property_id: str,
    requirement_id: str,
    user: dict = Depends(require_owner_or_admin),
):
    """Effective links preview: registry defaults, overrides, jurisdiction, final client-facing links."""
    _ = user
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id}, {"_id": 0})
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    req = await db.requirements.find_one(
        {"requirement_id": requirement_id, "property_id": property_id},
        {"_id": 0},
    )
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found for this property")
    cid = prop.get("client_id")
    client_doc = (
        await db.clients.find_one({"client_id": cid}, {"_id": 0, "default_jurisdiction": 1}) if cid else None
    ) or {}
    from services.requirement_action_links_admin_service import build_action_links_admin_preview

    return build_action_links_admin_preview(requirement_row=req, property_doc=prop, client_doc=client_doc)


@router.get("/properties/{property_id}/requirements-lite")
async def admin_list_property_requirements_lite(property_id: str, user: dict = Depends(require_owner_or_admin)):
    """Minimal requirement rows for admin action-links tooling (dropdown)."""
    _ = user
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id}, {"_id": 0, "client_id": 1})
    if not prop or not prop.get("client_id"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    rows = await db.requirements.find(
        {"property_id": property_id, "client_id": prop["client_id"]},
        {"_id": 0, "requirement_id": 1, "requirement_code": 1, "requirement_type": 1, "status": 1},
    ).to_list(500)
    return {"property_id": property_id, "client_id": prop["client_id"], "items": rows}


@router.put("/properties/{property_id}/requirements/{requirement_id}/action-links/draft")
async def admin_put_requirement_action_links_draft(
    request: Request,
    property_id: str,
    requirement_id: str,
    body: _ActionLinksDraftBody,
    user: dict = Depends(require_owner_or_admin),
):
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id}, {"_id": 0})
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    req = await db.requirements.find_one(
        {"requirement_id": requirement_id, "property_id": property_id},
        {"_id": 0},
    )
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found for this property")

    from services.requirement_action_links_admin_service import (
        append_action_links_audit,
        merge_registry_metadata_for_links,
        normalize_admin_action_link_item,
        validate_action_links_override,
    )

    normalized: List[Dict[str, Any]] = []
    for raw in body.links:
        item, err = normalize_admin_action_link_item(raw if isinstance(raw, dict) else {}, generate_key_if_missing=True)
        if err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)
        normalized.append(item)

    errs = validate_action_links_override(normalized)
    if errs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"errors": errs})

    prev_meta = req.get("registry_metadata") if isinstance(req.get("registry_metadata"), dict) else {}
    prev_snap = {
        "action_links": prev_meta.get("action_links"),
        "action_links_draft": prev_meta.get("action_links_draft"),
    }
    new_meta = merge_registry_metadata_for_links(
        dict(prev_meta),
        action_links_draft=normalized if normalized else None,
        unset_draft=not normalized,
    )
    new_meta = append_action_links_audit(
        new_meta,
        actor_user_id=str(user.get("portal_user_id") or user.get("user_id") or ""),
        actor_email=str(user.get("email") or ""),
        action="save_draft",
        previous=prev_snap,
        new={"action_links": prev_meta.get("action_links"), "action_links_draft": normalized if normalized else None},
    )

    await db.requirements.update_one(
        {"requirement_id": requirement_id, "property_id": property_id},
        {"$set": {"registry_metadata": new_meta}},
    )

    from utils.audit import create_audit_log
    from models import AuditAction

    actor_role = _portal_user_role_for_audit(user)
    ip_address = request.client.host if request.client else None
    await create_audit_log(
        action=AuditAction.REQUIREMENT_ACTION_LINKS_DRAFT_SAVED,
        actor_role=actor_role,
        actor_id=str(user.get("portal_user_id") or user.get("user_id") or ""),
        client_id=req.get("client_id"),
        resource_type="requirement",
        resource_id=requirement_id,
        before_state=prev_snap,
        after_state={"action_links_draft": normalized if normalized else None},
        metadata={"property_id": property_id},
        ip_address=ip_address,
    )

    return {"ok": True, "action_links_draft": normalized if normalized else None}


@router.post("/properties/{property_id}/requirements/{requirement_id}/action-links/publish")
async def admin_post_requirement_action_links_publish(
    request: Request,
    property_id: str,
    requirement_id: str,
    user: dict = Depends(require_owner_or_admin),
):
    db = database.get_db()
    req = await db.requirements.find_one(
        {"requirement_id": requirement_id, "property_id": property_id},
        {"_id": 0},
    )
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found for this property")
    prev_meta = req.get("registry_metadata") if isinstance(req.get("registry_metadata"), dict) else {}
    draft = prev_meta.get("action_links_draft")
    if not isinstance(draft, list) or not draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No draft to publish. Save a draft first.",
        )

    from services.requirement_action_links_admin_service import (
        append_action_links_audit,
        merge_registry_metadata_for_links,
        normalize_admin_action_link_item,
        validate_action_links_override,
    )

    normalized: List[Dict[str, Any]] = []
    for raw in draft:
        item, err = normalize_admin_action_link_item(raw if isinstance(raw, dict) else {}, generate_key_if_missing=True)
        if err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)
        normalized.append(item)
    errs = validate_action_links_override(normalized)
    if errs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"errors": errs})

    prev_snap = {
        "action_links": prev_meta.get("action_links"),
        "action_links_draft": prev_meta.get("action_links_draft"),
    }
    new_meta = merge_registry_metadata_for_links(
        dict(prev_meta),
        action_links=list(normalized),
        action_links_draft=list(normalized),
    )
    new_meta = append_action_links_audit(
        new_meta,
        actor_user_id=str(user.get("portal_user_id") or user.get("user_id") or ""),
        actor_email=str(user.get("email") or ""),
        action="publish",
        previous=prev_snap,
        new={"action_links": normalized, "action_links_draft": normalized},
    )

    await db.requirements.update_one(
        {"requirement_id": requirement_id, "property_id": property_id},
        {"$set": {"registry_metadata": new_meta}},
    )

    from utils.audit import create_audit_log
    from models import AuditAction

    actor_role = _portal_user_role_for_audit(user)
    ip_address = request.client.host if request.client else None
    await create_audit_log(
        action=AuditAction.REQUIREMENT_ACTION_LINKS_PUBLISHED,
        actor_role=actor_role,
        actor_id=str(user.get("portal_user_id") or user.get("user_id") or ""),
        client_id=req.get("client_id"),
        resource_type="requirement",
        resource_id=requirement_id,
        before_state={"action_links": prev_meta.get("action_links")},
        after_state={"action_links": normalized},
        metadata={"property_id": property_id},
        ip_address=ip_address,
    )

    return {"ok": True, "action_links": normalized}


@router.post("/properties/{property_id}/requirements/{requirement_id}/action-links/revert")
async def admin_post_requirement_action_links_revert(
    request: Request,
    property_id: str,
    requirement_id: str,
    user: dict = Depends(require_owner_or_admin),
):
    db = database.get_db()
    req = await db.requirements.find_one(
        {"requirement_id": requirement_id, "property_id": property_id},
        {"_id": 0},
    )
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found for this property")
    prev_meta = req.get("registry_metadata") if isinstance(req.get("registry_metadata"), dict) else {}
    prev_snap = {
        "action_links": prev_meta.get("action_links"),
        "action_links_draft": prev_meta.get("action_links_draft"),
    }

    from services.requirement_action_links_admin_service import append_action_links_audit, merge_registry_metadata_for_links

    new_meta = merge_registry_metadata_for_links(
        dict(prev_meta),
        unset_published=True,
        unset_draft=True,
    )
    new_meta = append_action_links_audit(
        new_meta,
        actor_user_id=str(user.get("portal_user_id") or user.get("user_id") or ""),
        actor_email=str(user.get("email") or ""),
        action="revert",
        previous=prev_snap,
        new={"action_links": None, "action_links_draft": None},
    )

    await db.requirements.update_one(
        {"requirement_id": requirement_id, "property_id": property_id},
        {"$set": {"registry_metadata": new_meta}},
    )

    from utils.audit import create_audit_log
    from models import AuditAction

    actor_role = _portal_user_role_for_audit(user)
    ip_address = request.client.host if request.client else None
    await create_audit_log(
        action=AuditAction.REQUIREMENT_ACTION_LINKS_REVERTED,
        actor_role=actor_role,
        actor_id=str(user.get("portal_user_id") or user.get("user_id") or ""),
        client_id=req.get("client_id"),
        resource_type="requirement",
        resource_id=requirement_id,
        before_state=prev_snap,
        after_state={"action_links": None, "action_links_draft": None},
        metadata={"property_id": property_id},
        ip_address=ip_address,
    )

    return {"ok": True}


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

    **Stream B:** When ``fix=true`` and a mismatch exists, persistence uses only
    ``compliance_scoring_service.recalculate_and_persist`` with
    ``REASON_ADMIN_VALIDATOR_REPAIR`` (single writer). Emits
    ``COMPLIANCE_SCORE_MISMATCH_DETECTED`` (if mismatch), then canonical
    ``COMPLIANCE_SCORE_UPDATED`` from recalc, then ``COMPLIANCE_SCORE_REPAIRED``.
    Shared ``correlation_id`` links audit metadata.

    When ``fix=false``, diagnostic only (compare + optional mismatch audit).
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
        from services.compliance_scoring_service import (
            calculate_property_compliance,
            recalculate_and_persist,
            REASON_ADMIN_VALIDATOR_REPAIR,
        )

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

        repaired = False
        if not match:
            correlation_id = f"ADMIN_VALIDATOR_REPAIR:{property_id}:{uuid.uuid4().hex[:12]}"
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
                    "correlation_id": correlation_id,
                },
            )
            if body.fix:
                recalc_result = await recalculate_and_persist(
                    property_id,
                    REASON_ADMIN_VALIDATOR_REPAIR,
                    actor={"id": user.get("portal_user_id"), "role": "ADMIN"},
                    context={
                        "correlation_id": correlation_id,
                        "diff_summary": diff_summary,
                    },
                )
                if recalc_result.get("error"):
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Recalculation failed: {recalc_result.get('error')}",
                    )
                new_score = recalc_result.get("score")
                await create_audit_log(
                    action=AuditAction.COMPLIANCE_SCORE_REPAIRED,
                    actor_id=user.get("portal_user_id"),
                    client_id=prop["client_id"],
                    resource_type="property",
                    resource_id=property_id,
                    before_state={"compliance_score": stored_score},
                    after_state={"compliance_score": new_score},
                    metadata={
                        "property_id": property_id,
                        "previous_score": stored_score,
                        "new_score": new_score,
                        "correlation_id": correlation_id,
                        "diff_summary": diff_summary,
                        "canonical_reason": REASON_ADMIN_VALIDATOR_REPAIR,
                    },
                )
                repaired = True

        return {
            "property_id": property_id,
            "stored_score": stored_score,
            "computed_score": computed_score,
            "match": match,
            "diff_summary": diff_summary,
            "repaired": repaired,
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
    await require_recent_step_up(request, user)
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
        from utils.app_urls import get_app_base_url

        base_url = get_app_base_url(for_email_links=True)
        setup_link = f"{base_url}/set-password?token={raw_token}"
        activation_link_domain = urlparse(setup_link).netloc or ""
        client_email = (client.get("email") or client.get("contact_email") or portal_user.get("auth_email") or "").strip()
        if not client_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "EMAIL_INPUT_INVALID", "message": "Client has no email; add email to client or portal user."},
            )
        if not setup_link:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "EMAIL_INPUT_INVALID", "message": "Missing setup link"},
            )
        from services.notification_orchestrator import notification_orchestrator
        # Unique idempotency key per attempt so each resend creates a new message_log (avoid duplicate_ignored from null key collision)
        idempotency_key = f"admin_resend_welcome_{client_id}_{uuid.uuid4()}"
        try:
            result = await notification_orchestrator.send(
                template_key="WELCOME_EMAIL",
                client_id=client_id,
                context={
                    "recipient": client_email,
                    "setup_link": setup_link,
                    "client_name": client.get("full_name") or "Customer",
                    "company_name": "Pleerity Enterprise Ltd",
                    "tagline": "AI-Driven Solutions & Compliance",
                },
                idempotency_key=idempotency_key,
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

        now_iso = datetime.now(timezone.utc).isoformat()
        audit_meta_base = {
            "client_id": client_id,
            "portal_user_id": portal_user["portal_user_id"],
            "email": client_email[:3] + "***@***" if len(client_email) > 6 else "***",
            "activation_link_domain": activation_link_domain,
            "status": None,
        }

        if result.outcome == "blocked":
            err_msg = result.block_reason or "Email send blocked (e.g. provider not configured)."
            await db.clients.update_one(
                {"client_id": client_id},
                {
                    "$set": {
                        "activation_email_status": "FAILED",
                        "activation_email_sent_at": now_iso,
                        "activation_email_error": err_msg[:1000],
                        "activation_link_last_url": setup_link,
                    }
                },
            )
            await create_audit_log(
                action=AuditAction.ACTIVATION_EMAIL_RESEND,
                actor_id=user["portal_user_id"],
                client_id=client_id,
                metadata={**audit_meta_base, "status": "FAILED", "error": err_msg},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error_code": "EMAIL_NOT_CONFIGURED", "message": err_msg},
            )
        if result.outcome == "failed":
            err_msg = (result.error_message or "Send failed")[:1000]
            await db.clients.update_one(
                {"client_id": client_id},
                {
                    "$set": {
                        "activation_email_status": "FAILED",
                        "activation_email_sent_at": now_iso,
                        "activation_email_error": err_msg,
                        "activation_link_last_url": setup_link,
                    }
                },
            )
            await create_audit_log(
                action=AuditAction.ACTIVATION_EMAIL_RESEND,
                actor_id=user["portal_user_id"],
                client_id=client_id,
                metadata={
                    **audit_meta_base,
                    "status": "FAILED",
                    "error": err_msg,
                    "provider_message_id": result.message_id,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "error_code": "EMAIL_PROVIDER_REJECTED",
                    "message": result.error_message or err_msg,
                },
            )
        if result.outcome not in ("sent", "duplicate_ignored"):
            err_msg = "Unexpected outcome"
            await db.clients.update_one(
                {"client_id": client_id},
                {"$set": {"activation_email_status": "FAILED", "activation_email_sent_at": now_iso, "activation_email_error": err_msg, "activation_link_last_url": setup_link}},
            )
            await create_audit_log(
                action=AuditAction.ACTIVATION_EMAIL_RESEND,
                actor_id=user["portal_user_id"],
                client_id=client_id,
                metadata={**audit_meta_base, "status": "FAILED", "error": err_msg},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error_code": "EMAIL_SEND_FAILED", "message": err_msg},
            )

        # Success: only update client and set SENT when we actually sent (not duplicate_ignored)
        if result.outcome == "sent":
            await db.clients.update_one(
                {"client_id": client_id},
                {
                    "$set": {
                        "activation_email_status": "SENT",
                        "activation_email_sent_at": now_iso,
                        "activation_link_last_url": setup_link,
                    },
                    "$unset": {"activation_email_error": ""},
                },
            )
        provider_message_id = (result.details or {}).get("provider_message_id") or result.message_id
        await create_audit_log(
            action=AuditAction.ACTIVATION_EMAIL_RESEND,
            actor_id=user["portal_user_id"],
            client_id=client_id,
            metadata={
                **audit_meta_base,
                "status": "SUCCESS" if result.outcome == "sent" else "DUPLICATE_IGNORED",
                "provider_message_id": provider_message_id,
                "message_id": result.message_id,
            },
        )
        return {
            "message": "Password setup link resent" if result.outcome == "sent" else "A password link was already sent recently (request deduplicated).",
            "activation_link": setup_link if result.outcome == "sent" else None,
            "provider_message_id": provider_message_id,
            "message_id": result.message_id,
        }
    
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
            {"client_id": client_id, "role": {"$in": ["ROLE_CLIENT", "ROLE_CLIENT_ADMIN"]}},
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
                "status": "complete" if portal_user and (portal_user.get("password_status") == "SET" or portal_user.get("password_set")) else "pending",
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
            "FORGOT_PASSWORD_REQUESTED",
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
            elif action in [
                "PASSWORD_TOKEN_GENERATED",
                "PASSWORD_SET_SUCCESS",
                "PASSWORD_SETUP_LINK_RESENT",
                "FORGOT_PASSWORD_REQUESTED",
                "PORTAL_INVITE_RESENT",
                "PORTAL_INVITE_EMAIL_FAILED",
                "USER_LOGIN_SUCCESS",
                "USER_LOGIN_FAILED",
                "ONBOARDING_PAYMENT_CONFIRMATION_EMAIL_SENT",
                "ONBOARDING_DASHBOARD_READY_EMAIL_SENT",
                "ONBOARDING_ACTIVATION_REMINDER_SENT",
                "ONBOARDING_EMAIL_SEND_BLOCKED",
            ]:
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


@router.get("/clients/{client_id}/command-centre-task-activity")
async def get_client_command_centre_task_activity(
    request: Request,
    client_id: str,
    limit: int = Query(50, ge=1, le=100),
):
    """Read-only Command Centre inbox activity (snooze, dismiss, done, restore) for support visibility."""
    await admin_route_guard(request)
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "client_id": 1})
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    from services.client_task_state_service import list_recent_activity

    items = await list_recent_activity(client_id, limit=limit)
    return {"items": items, "client_id": client_id}


# ============================================================================
# KPI DRILL-DOWN ENDPOINTS
# ============================================================================

@router.get("/kpi/properties")
async def get_kpi_properties(
    request: Request,
    status_filter: str = None,  # GREEN, AMBER, RED
    expiring_within_days: int = None,
    min_due_days: int = None,
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
        
        # For "expiring soon" filter (aligned with /admin/statistics due_date logic)
        if expiring_within_days:
            from datetime import timedelta
            now_iso = datetime.now(timezone.utc).isoformat()
            cutoff_date = (datetime.now(timezone.utc) + timedelta(days=expiring_within_days)).isoformat()
            req_query = {
                "due_date": {"$lte": cutoff_date, "$gte": now_iso},
                "status": {"$ne": "COMPLIANT"},
            }
            if min_due_days and min_due_days > 0:
                req_query["due_date"]["$gte"] = (datetime.now(timezone.utc) + timedelta(days=min_due_days)).isoformat()
            expiring_reqs = await db.requirements.find(req_query, {"_id": 0, "property_id": 1}).to_list(5000)
            property_ids = list(set(r["property_id"] for r in expiring_reqs))
            query["property_id"] = {"$in": property_ids}
        
        properties = await db.properties.find(
            query,
            {"_id": 0}
        ).skip(skip).limit(limit).to_list(limit)
        
        total = await db.properties.count_documents(query)
        
        # Enrich with client info and jurisdiction attribution (display-only)
        for prop in properties:
            client_row = await db.clients.find_one(
                {"client_id": prop.get("client_id")},
                {"_id": 0, "full_name": 1, "email": 1, "customer_reference": 1, "default_jurisdiction": 1},
            )
            if client_row:
                prop["client"] = {k: v for k, v in client_row.items() if k != "default_jurisdiction"}
            else:
                prop["client"] = None
            att = jurisdiction_attribution_for_property(prop, client_row or {})
            prop["effective_jurisdiction_label"] = att.get("effective_jurisdiction_label")
            prop["jurisdiction_source"] = att.get("jurisdiction_source")

        return {
            "properties": properties,
            "total": total,
            "skip": skip,
            "limit": limit,
            "filter": {
                "status": status_filter,
                "expiring_within_days": expiring_within_days,
                "min_due_days": min_due_days,
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
    due_within_days: int = None,
    min_due_days: int = None,
    exclude_overdue: bool = False,
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
        
        now_iso = datetime.now(timezone.utc).isoformat()

        if status_filter:
            normalized_status = status_filter.upper()
            if normalized_status == "OVERDUE":
                query["due_date"] = {"$lt": now_iso}
                query["status"] = {"$in": ["PENDING", "EXPIRING_SOON"]}
            elif normalized_status == "EXPIRING_SOON":
                query["due_date"] = {"$gte": now_iso, "$lte": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}
                query["status"] = {"$ne": "COMPLIANT"}
            else:
                query["status"] = normalized_status
        if category:
            query["category"] = category.upper()

        if due_within_days and due_within_days > 0:
            due_query = query.get("due_date", {})
            if not isinstance(due_query, dict):
                due_query = {}
            due_query["$lte"] = (datetime.now(timezone.utc) + timedelta(days=due_within_days)).isoformat()
            if exclude_overdue:
                due_query["$gte"] = now_iso
            if min_due_days and min_due_days > 0:
                due_query["$gte"] = (datetime.now(timezone.utc) + timedelta(days=min_due_days)).isoformat()
            query["due_date"] = due_query
        
        requirements = await db.requirements.find(
            query,
            {"_id": 0}
        ).sort("due_date", 1).skip(skip).limit(limit).to_list(limit)
        
        total = await db.requirements.count_documents(query)
        
        # Enrich with property and client info
        for req in requirements:
            prop = await db.properties.find_one(
                {"property_id": req.get("property_id")},
                {"_id": 0, "nickname": 1, "address_line_1": 1, "postcode": 1, "client_id": 1, "jurisdiction": 1}
            )
            if prop:
                client_row = await db.clients.find_one(
                    {"client_id": prop.get("client_id")},
                    {"_id": 0, "full_name": 1, "customer_reference": 1, "default_jurisdiction": 1},
                )
                att = jurisdiction_attribution_for_property(prop, client_row or {})
                prop_out = dict(prop)
                prop_out["effective_jurisdiction_label"] = att.get("effective_jurisdiction_label")
                prop_out["jurisdiction_source"] = att.get("jurisdiction_source")
                req["property"] = prop_out
                req["client"] = (
                    {k: v for k, v in client_row.items() if k != "default_jurisdiction"}
                    if client_row
                    else None
                )

        from services.requirement_truth import enrich_requirements_for_admin

        requirements = await enrich_requirements_for_admin(db, requirements)
        
        return {
            "requirements": requirements,
            "total": total,
            "skip": skip,
            "limit": limit,
            "filter": {
                "status": status_filter,
                "category": category,
                "due_within_days": due_within_days,
                "min_due_days": min_due_days,
                "exclude_overdue": exclude_overdue,
            }
        }
        
    except Exception as e:
        logger.error(f"KPI requirements drill-down error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load requirements"
        )


@router.get("/kpi/documents")
async def get_kpi_documents(
    request: Request,
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
):
    """
    KPI drill-down: list documents with optional status filter.
    Used by statistics document tiles for actionable drill-down.
    """
    await admin_route_guard(request)
    db = database.get_db()

    try:
        query: Dict[str, Any] = {}
        if status_filter:
            query["status"] = status_filter.upper()

        cursor = (
            db.documents.find(
                query,
                {
                    "_id": 0,
                    "document_id": 1,
                    "client_id": 1,
                    "property_id": 1,
                    "file_name": 1,
                    "status": 1,
                    "uploaded_at": 1,
                    "created_at": 1,
                },
            )
            .sort("uploaded_at", -1)
            .skip(skip)
            .limit(limit)
        )
        documents = await cursor.to_list(limit)
        total = await db.documents.count_documents(query)

        client_ids = list({d.get("client_id") for d in documents if d.get("client_id")})
        property_ids = list({d.get("property_id") for d in documents if d.get("property_id")})

        client_map: Dict[str, Dict[str, Any]] = {}
        if client_ids:
            async for c in db.clients.find(
                {"client_id": {"$in": client_ids}},
                {"_id": 0, "client_id": 1, "full_name": 1, "customer_reference": 1, "default_jurisdiction": 1},
            ):
                cid = c.get("client_id")
                if cid:
                    client_map[cid] = c

        property_map: Dict[str, Dict[str, Any]] = {}
        if property_ids:
            async for p in db.properties.find(
                {"property_id": {"$in": property_ids}},
                {"_id": 0, "property_id": 1, "nickname": 1, "address_line_1": 1, "postcode": 1, "client_id": 1, "jurisdiction": 1},
            ):
                pid = p.get("property_id")
                if pid:
                    property_map[pid] = p

        for pid, p in list(property_map.items()):
            cid = p.get("client_id")
            client_row = client_map.get(cid) if cid else None
            att = jurisdiction_attribution_for_property(p, client_row or {})
            property_map[pid] = {
                **p,
                "effective_jurisdiction_label": att.get("effective_jurisdiction_label"),
                "jurisdiction_source": att.get("jurisdiction_source"),
            }

        for doc in documents:
            cid = doc.get("client_id")
            pid = doc.get("property_id")
            crow = client_map.get(cid) if cid else None
            doc["client"] = (
                {k: v for k, v in crow.items() if k != "default_jurisdiction"}
                if crow
                else None
            )
            doc["property"] = property_map.get(pid) if pid else None

        return {
            "documents": documents,
            "total": total,
            "skip": skip,
            "limit": limit,
            "filter": {"status": status_filter},
        }
    except Exception as e:
        logger.error(f"KPI documents drill-down error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load documents",
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
    status_filter: Optional[str] = Query(None, alias="status"),
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
        empty_reason = None
        if total == 0:
            if any([client_id, channel, template_key, status_filter, status_prefix, recipient]) or from_dt or to_dt:
                empty_reason = "filters_excluded_all_results"
            else:
                empty_reason = "no_message_logs_match_filters_or_time_window"
        return {"items": items, "total": total, "limit": limit, "offset": offset, "empty_reason": empty_reason}
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


def _notification_health_status(sent_total, failed_total, throttled_count, reminder_job_ran_with_attempts, has_any_logs):
    """Derive a single status so empty state is not ambiguous."""
    if sent_total > 0 and failed_total == 0 and throttled_count == 0:
        return "sent_ok"
    if sent_total > 0 and failed_total > 0:
        return "partial_failure"
    if sent_total == 0 and failed_total > 0:
        return "failed"
    if throttled_count > 0 and sent_total == 0 and failed_total == 0:
        return "notifications_queued"
    if sent_total == 0 and failed_total == 0:
        if reminder_job_ran_with_attempts and not has_any_logs:
            return "job_did_not_run"  # reliability concern: job ran but no message_logs
        if reminder_job_ran_with_attempts and has_any_logs:
            return "no_notifications_due"  # job ran, logs exist, but 0 in window
        return "no_notifications_due"
    return "cannot_verify"


@router.get("/notification-health/summary", dependencies=[Depends(require_owner_or_admin)])
async def get_notification_health_summary(
    request: Request,
    window_minutes: int = Query(60, ge=1, le=10080),
):
    """Admin notification health: aggregate counts, top failures, and explicit status (no ambiguous empty state)."""
    await admin_route_guard(request)
    db = database.get_db()
    try:
        since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        match = {"created_at": {"$gte": since}}
        # Support both "SENT"/"FAILED" and "sent"/"failed" for message_logs
        sent_email = await db.message_logs.count_documents({**match, "channel": "EMAIL", "status": {"$in": ["SENT", "sent"]}})
        failed_email = await db.message_logs.count_documents({**match, "channel": "EMAIL", "status": {"$in": ["FAILED", "failed"]}})
        sent_sms = await db.message_logs.count_documents({**match, "channel": "SMS", "status": {"$in": ["SENT", "sent"]}})
        failed_sms = await db.message_logs.count_documents({**match, "channel": "SMS", "status": {"$in": ["FAILED", "failed"]}})
        throttled_count = await db.message_logs.count_documents({**match, "status": "DEFERRED_THROTTLED"})
        sent_total = sent_email + sent_sms
        failed_total = failed_email + failed_sms
        has_any_logs = await db.message_logs.count_documents(match) > 0

        # Did a notification job run in this window with attempted sends? (so we can flag job_did_not_run)
        reminder_run = await db.job_runs.find_one(
            {"job_name": "daily_reminders", "started_at": {"$gte": since.isoformat()}},
            {"_id": 0, "outcome_metrics": 1},
            sort=[("started_at", -1)],
        )
        reminder_job_ran_with_attempts = False
        if reminder_run and reminder_run.get("outcome_metrics"):
            om = reminder_run["outcome_metrics"]
            if (om.get("attempted_count") or 0) > 0 or (om.get("expected_count") or 0) > 0:
                reminder_job_ran_with_attempts = True

        status_value = _notification_health_status(
            sent_total, failed_total, throttled_count, reminder_job_ran_with_attempts, has_any_logs,
        )

        top_failed = []
        async for doc in db.message_logs.aggregate([
            {"$match": {**match, "status": {"$in": ["FAILED", "failed"]}}},
            {"$group": {"_id": "$template_key", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]):
            top_failed.append({"template_key": doc["_id"] or "unknown", "count": doc["count"]})
        top_reasons = []
        async for doc in db.message_logs.aggregate([
            {"$match": {**match, "status": {"$in": ["FAILED", "failed"]}, "error_message": {"$exists": True, "$ne": ""}}},
            {"$group": {"_id": {"$substr": ["$error_message", 0, 120]}, "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]):
            top_reasons.append({"reason": doc["_id"], "count": doc["count"]})
        # Diagnostic empty reason when no activity in window (Priority 5)
        empty_reason = None
        if sent_total == 0 and failed_total == 0 and throttled_count == 0:
            if status_value == "job_did_not_run":
                empty_reason = "notification_jobs_ran_but_produced_no_logs"
            elif status_value == "no_notifications_due":
                empty_reason = "no_notifications_due_in_this_window"
            elif not has_any_logs:
                empty_reason = "no_message_logs_in_window_check_scheduler_and_jobs"
            else:
                empty_reason = "no_sent_or_failed_in_window"
        return {
            "window_minutes": window_minutes,
            "notification_health_status": status_value,
            "sent_email_count": sent_email,
            "failed_email_count": failed_email,
            "sent_sms_count": sent_sms,
            "failed_sms_count": failed_sms,
            "throttled_count": throttled_count,
            "top_failed_templates": top_failed,
            "top_failure_reasons": top_reasons,
            "empty_reason": empty_reason,
        }
    except Exception as e:
        logger.error("Notification health summary error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load notification health summary",
        )


@router.get("/notification-health/timeseries", dependencies=[Depends(require_owner_or_admin)])
async def get_notification_health_timeseries(
    request: Request,
    window_minutes: int = Query(240, ge=1, le=10080),
    bucket_minutes: int = Query(15, ge=1, le=120),
):
    """Admin notification health: time buckets with sent/failed per channel."""
    await admin_route_guard(request)
    db = database.get_db()
    try:
        since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        buckets = []
        bucket_sec = bucket_minutes * 60
        t = since.replace(minute=(since.minute // bucket_minutes) * bucket_minutes, second=0, microsecond=0)
        while t < datetime.now(timezone.utc):
            bucket_end = t + timedelta(minutes=bucket_minutes)
            match = {"created_at": {"$gte": t, "$lt": bucket_end}}
            sent_email = await db.message_logs.count_documents({**match, "channel": "EMAIL", "status": "SENT"})
            failed_email = await db.message_logs.count_documents({**match, "channel": "EMAIL", "status": "FAILED"})
            sent_sms = await db.message_logs.count_documents({**match, "channel": "SMS", "status": "SENT"})
            failed_sms = await db.message_logs.count_documents({**match, "channel": "SMS", "status": "FAILED"})
            buckets.append({
                "bucket_start": t.isoformat(),
                "bucket_end": bucket_end.isoformat(),
                "sent_email_count": sent_email,
                "failed_email_count": failed_email,
                "sent_sms_count": sent_sms,
                "failed_sms_count": failed_sms,
            })
            t = bucket_end
        return {"window_minutes": window_minutes, "bucket_minutes": bucket_minutes, "buckets": buckets}
    except Exception as e:
        logger.error(f"Notification health timeseries error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load notification health timeseries",
        )


@router.get("/notification-health/recent", dependencies=[Depends(require_owner_or_admin)])
async def get_notification_health_recent(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
):
    """Admin notification health: recent message_logs with status, template_key, recipient, error, timestamps."""
    await admin_route_guard(request)
    db = database.get_db()
    try:
        cursor = db.message_logs.find(
            {},
            {"_id": 0, "message_id": 1, "template_key": 1, "channel": 1, "status": 1, "recipient": 1, "error_message": 1, "created_at": 1, "sent_at": 1},
        ).sort("created_at", -1).limit(limit)
        items = await cursor.to_list(limit)
        for it in items:
            for k in ("created_at", "sent_at"):
                if it.get(k) and hasattr(it[k], "isoformat"):
                    it[k] = it[k].isoformat()
        return {"items": items, "limit": limit}
    except Exception as e:
        logger.error(f"Notification health recent error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load recent message logs",
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
    """Legacy jobs status endpoint. Prefer /api/admin/observability/framework-audit + /health-summary."""
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
        
        # Get scheduler status (use getattr for next_run_time; some APScheduler backends may not expose it on Job)
        from server import scheduler
        scheduler_jobs = []
        for job in scheduler.get_jobs():
            next_run = getattr(job, "next_run_time", None)
            scheduler_jobs.append({
                "id": getattr(job, "id", None),
                "name": getattr(job, "name", None),
                "next_run": next_run.isoformat() if next_run else None,
            })
        # If scheduler returned no jobs, treat as issues (scheduler may not be running)
        system_status = "operational" if scheduler_jobs else "issues"

        logger.warning("Deprecated endpoint used: GET /api/admin/jobs/status")
        return {
            "deprecated": True,
            "compatibility_window_ends_at": LEGACY_JOBS_ENDPOINT_SUNSET,
            "replacement_endpoints": [
                "/api/admin/observability/framework-audit",
                "/api/admin/observability/health-summary",
            ],
            "daily_reminders": {
                "last_run": last_reminder["timestamp"] if last_reminder else None,
                "pending_count": pending_reminders
            },
            "monthly_digest": {
                "last_run": last_digest["sent_at"] if last_digest else None,
                "total_sent": await db.digest_logs.count_documents({})
            },
            "scheduled_jobs": scheduler_jobs,
            "system_status": system_status,
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
    client_id: Optional[str] = None
    property_id: Optional[str] = None
    # Monthly digest: optional filter (requires client_id). See job_scope_registry.
    property_ids: Optional[List[str]] = None


class ClientMonthlyDigestActionBody(BaseModel):
    property_ids: Optional[List[str]] = None


@router.post("/jobs/run")
async def run_job_now(request: Request, body: RunJobRequest):
    """Run a single background job by id (admin only). Returns job-specific message for toast. Persists to job_runs."""
    user = await admin_route_guard(request)
    await _enforce_admin_job_run_rate(user["portal_user_id"])
    from job_runner import JOB_RUNNERS, run_instrumented

    job_id = (body.job or "").strip()
    if not job_id or job_id not in JOB_RUNNERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid job. Use one of: {', '.join(sorted(JOB_RUNNERS.keys()))}"
        )
    from services.job_scope_registry import get_job_run_scope, validate_manual_job_scope

    scope_err = validate_manual_job_scope(
        job_id,
        client_id=body.client_id,
        property_id=body.property_id,
        property_ids=body.property_ids,
    )
    if scope_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=scope_err)

    job_kwargs = None
    start_metadata = None
    if body.client_id and body.client_id.strip():
        start_metadata = {"scope": "client", "client_id": body.client_id.strip()}
    else:
        start_metadata = {"scope": "global"}
    if body.property_id and body.property_id.strip():
        start_metadata = dict(start_metadata or {})
        start_metadata["property_id"] = body.property_id.strip()
    pids_meta = [str(x).strip() for x in (body.property_ids or []) if x and str(x).strip()]
    if pids_meta:
        start_metadata = dict(start_metadata or {})
        start_metadata["property_ids"] = pids_meta

    scope = get_job_run_scope(job_id)
    job_kw: Dict[str, Any] = {}
    if scope.accepts_client_id and body.client_id and body.client_id.strip():
        job_kw["client_id"] = body.client_id.strip()
    if scope.accepts_property_id and body.property_id and body.property_id.strip():
        job_kw["property_id"] = body.property_id.strip()
    if scope.accepts_property_ids_filter and pids_meta:
        job_kw["property_ids"] = pids_meta
    job_kwargs = job_kw if job_kw else None
    try:
        result = await run_instrumented(
            job_id,
            "manual",
            triggered_by=user.get("portal_user_id"),
            job_kwargs=job_kwargs,
            start_metadata=start_metadata,
        )
        message = (result.get("message") if result else None) or f"Job {job_id} completed"
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=body.client_id.strip() if body.client_id and body.client_id.strip() else None,
            metadata={
                "action": "manual_job_run",
                "job_id": job_id,
                "run_scope": (start_metadata or {}).get("scope"),
                "target_client_id": body.client_id.strip() if body.client_id and body.client_id.strip() else None,
                "target_property_id": body.property_id.strip() if body.property_id and body.property_id.strip() else None,
                "target_property_ids": pids_meta if pids_meta else None,
                "admin_email": user["email"],
                "job_kwargs": job_kwargs,
            },
        )
        return {"success": True, "job": job_id, "message": message, "result": result}
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
    await _enforce_admin_job_run_rate(user["portal_user_id"])
    if job_type not in ["daily", "monthly", "compliance"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job type. Use 'daily', 'monthly', or 'compliance'"
        )
    job_id = {"daily": "daily_reminders", "monthly": "monthly_digest", "compliance": "compliance_check_morning"}[job_type]
    from job_runner import run_instrumented
    try:
        result = await run_instrumented(job_id, "manual", triggered_by=user.get("portal_user_id"))
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
        logger.warning("Deprecated endpoint used: POST /api/admin/jobs/trigger/%s", job_type)
        return {
            "message": message,
            "count": count,
            "deprecated": True,
            "compatibility_window_ends_at": LEGACY_JOBS_ENDPOINT_SUNSET,
            "replacement_endpoint": "/api/admin/jobs/run",
            "mapped_job_id": job_id,
        }
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

        invite_email = canonical_client_email(email)
        if not invite_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid email is required",
            )

        if await client_email_taken(db, email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A client with this email already exists",
            )

        # Create client in INVITED state (not yet provisioned)
        client = Client(
            full_name=full_name,
            email=invite_email,
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

        try:
            await db.clients.insert_one(client_doc)
        except DuplicateKeyError as dup_err:
            kind = classify_clients_duplicate_key_error(dup_err)
            if kind == "email":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A client with this email already exists",
                ) from dup_err
            logger.warning(
                "Admin invite clients.insert_one duplicate key (kind=%s): %s",
                kind,
                dup_err,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Could not create client due to a conflict; please retry or contact support.",
            ) from dup_err

        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=client.client_id,
            metadata={
                "action": "admin_client_invited",
                "email": invite_email,
                "billing_plan": billing_plan,
                "admin_email": user["email"]
            }
        )
        
        logger.info("Admin invited client: %s", invite_email)
        
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
async def retry_provisioning_job(
    request: Request,
    job_id: str,
    body: SupportDangerousActionReasonBody = Body(...),
):
    """Retry a failed or stuck provisioning job (admin only). Runs the job runner once."""
    user = await admin_route_guard(request)
    await _enforce_admin_job_run_rate(user["portal_user_id"])
    from services.provisioning_runner import run_provisioning_job
    try:
        ok = await run_provisioning_job(job_id)
        job = await database.get_db().provisioning_jobs.find_one({"job_id": job_id}, {"_id": 0, "status": 1, "client_id": 1})
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user.get("portal_user_id"),
            client_id=job.get("client_id"),
            metadata={
                "action": "provisioning_job_retry",
                "job_id": job_id,
                "runner_returned": ok,
                "support_reason": body.reason,
            },
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
    user = await admin_route_guard(request)
    await _enforce_admin_job_run_rate(user["portal_user_id"])
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
    if generate_new:
        await require_recent_step_up(request, user)
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
        
        from auth import generate_secure_token, hash_token
        from models import PasswordToken
        from utils.public_app_url import get_public_app_url
        base_url = get_public_app_url(for_email_links=False)
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
        setup_link = f"{base_url}/set-password?token={raw_token}"
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
            "derived_client_lifecycle_status": derive_client_lifecycle_status(client),
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


@router.get("/clients/{client_id}/control-panel")
async def get_client_control_panel(request: Request, client_id: str):
    """
    Unified client control panel payload for admin support workflows.
    Returns normalized, UI-safe fields only.
    """
    await admin_route_guard(request)
    db = database.get_db()

    try:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

        portal_users = await db.portal_users.find(
            {"client_id": client_id},
            {
                "_id": 0,
                "portal_user_id": 1,
                "role": 1,
                "status": 1,
                "password_status": 1,
                "last_login": 1,
                "auth_email": 1,
                "is_test_like": 1,
            },
        ).to_list(10)
        primary_user = next((u for u in portal_users if u.get("role") == UserRole.ROLE_CLIENT_ADMIN.value), None)
        if not primary_user and portal_users:
            primary_user = portal_users[0]

        billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})

        sub_status: Dict[str, Any] = {}
        try:
            from services.stripe_service import StripeService

            sub_status = await StripeService().get_subscription_status(client_id, client_facing=False) or {}
        except Exception:
            sub_status = {}

        wh_at = sub_status.get("stripe_webhook_last_received_at")
        wh_type = sub_status.get("stripe_webhook_last_event_type")
        if not wh_at and billing:
            wh_at = _iso_or_none(billing.get("stripe_webhook_last_received_at"))
        if not wh_type and billing:
            wh_type = billing.get("stripe_webhook_last_event_type")

        stripe_customer_id = sub_status.get("stripe_customer_id") or client.get("stripe_customer_id") or (
            billing.get("stripe_customer_id") if billing else None
        )
        stripe_subscription_id = sub_status.get("stripe_subscription_id") or (
            billing.get("stripe_subscription_id") if billing else None
        )
        billing_last_synced_at = sub_status.get("billing_last_synced_at") or _iso_or_none(
            (billing or {}).get("billing_last_synced_at")
        )
        billing_sync_state = sub_status.get("billing_sync_state") or (
            (billing or {}).get("billing_sync_state") if billing else None
        )
        lifecycle_from_sub = sub_status.get("lifecycle_status_label")

        unresolved_evidence_document_count = await db.documents.count_documents(
            {"client_id": client_id, "evidence_scope_type": "UNRESOLVED"}
        )

        properties_count = await db.properties.count_documents({"client_id": client_id})
        missing_docs = await db.requirements.count_documents({"client_id": client_id, "status": "PENDING"})
        overdue_items = await db.requirements.count_documents({"client_id": client_id, "status": "OVERDUE"})

        compliance_score = None
        compliance_risk_level = None
        score_data: Dict[str, Any] = {}
        try:
            from services.compliance_score import calculate_compliance_score

            score_data = await calculate_compliance_score(client_id)
            # Portfolio headline uses persisted property scores (see calculate_compliance_score).
            compliance_score = score_data.get("score")
            compliance_risk_level = score_data.get("message") or score_data.get("grade")
        except Exception:
            # Do not fail control panel if score recompute is unavailable — never substitute a legacy client row as headline.
            score_data = {
                "score_authority": "unavailable",
                "score_status": "unavailable",
                "last_calculated_at": None,
                "score_coverage": None,
            }

        issues_count = await db.maintenance_issues.count_documents({"client_id": client_id})
        work_orders_count = await db.work_orders.count_documents({"client_id": client_id})
        contractors_count = await db.contractors.count_documents(
            {"$or": [{"client_id": client_id}, {"client_id": None}]}
        )

        # Reuse existing merged receipts model from admin billing service.
        from services.admin_billing_receipts import list_receipts_for_client

        receipts, receipts_meta = await list_receipts_for_client(client_id, type_filter="all", limit=20)

        payment_events = await db.payments.find(
            {"client_id": client_id},
            {"_id": 0, "payment_id": 1, "amount": 1, "currency": 1, "status": 1, "created_at": 1},
        ).sort("created_at", -1).limit(15).to_list(15)
        login_events = await db.audit_logs.find(
            {"client_id": client_id, "action": {"$in": [AuditAction.USER_LOGIN_SUCCESS.value, AuditAction.USER_LOGIN_FAILED.value]}},
            {"_id": 0, "action": 1, "timestamp": 1, "metadata": 1},
        ).sort("timestamp", -1).limit(20).to_list(20)
        system_events = await db.audit_logs.find(
            {"client_id": client_id},
            {"_id": 0, "action": 1, "timestamp": 1, "metadata": 1},
        ).sort("timestamp", -1).limit(50).to_list(50)

        from services.onboarding_checklist_service import get_checklist_for_client

        oc_state = await get_checklist_for_client(client_id)
        onboard_snap: Dict[str, Any]
        if oc_state.get("error"):
            onboard_snap = {"unavailable": True}
        else:
            onboard_snap = {
                "onboarding_status": oc_state.get("onboarding_status"),
                "phase_status": oc_state.get("phase_status"),
                "progress": oc_state.get("progress"),
                "completed_at": oc_state.get("completed_at"),
                "next_step": oc_state.get("next_step"),
            }
        dl_rows = (
            await db.digest_logs.find({"client_id": client_id}, {"_id": 0, "digest_id": 1, "sent_at": 1})
            .sort("sent_at", -1)
            .limit(1)
            .to_list(1)
        )
        last_digest_row = dl_rows[0] if dl_rows else None
        bc_rows = (
            await db.communication_deliveries.find(
                {"client_id": client_id},
                {"_id": 0, "communication_id": 1, "created_at": 1, "email_status": 1, "in_app_status": 1},
            )
            .sort("created_at", -1)
            .limit(1)
            .to_list(1)
        )
        last_broadcast_delivery = bc_rows[0] if bc_rows else None
        recent_audit_highlights = []
        for ev in system_events[:12]:
            md = ev.get("metadata") if isinstance(ev.get("metadata"), dict) else {}
            recent_audit_highlights.append(
                {
                    "action": ev.get("action"),
                    "timestamp": ev.get("timestamp"),
                    "metadata_preview": {k: md[k] for k in list(md.keys())[:6]},
                }
            )

        onboarding_stage = client.get("onboarding_status")
        activation_email_sent = bool(client.get("activation_email_sent_at"))
        dashboard_ready_sent = bool(client.get("onboarding_dashboard_ready_email_sent_at"))

        return {
            "identity": {
                "client_id": client_id,
                "name": client.get("full_name"),
                "company_name": client.get("company_name"),
                "crn": client.get("customer_reference"),
                "email": client.get("email") or (primary_user or {}).get("auth_email"),
                "phone": client.get("phone"),
                "plan": client.get("billing_plan"),
                "status": client.get("subscription_status"),
                "is_test_like": bool(client.get("is_test_like")),
            },
            "account_state": {
                "password_set": bool(primary_user and primary_user.get("password_status") == PasswordStatus.SET.value),
                "last_login": _iso_or_none((primary_user or {}).get("last_login")),
                "onboarding_stage": onboarding_stage,
                "activation_email_sent": activation_email_sent,
                "dashboard_ready_sent": dashboard_ready_sent,
            },
            "subscription_billing": {
                "plan": client.get("billing_plan"),
                "status": client.get("subscription_status"),
                "billing_lifecycle_state": (billing or {}).get("billing_lifecycle_state"),
                "cancel_at_period_end": bool((billing or {}).get("cancel_at_period_end")),
                "lifecycle_status_label": lifecycle_from_sub
                or lifecycle_status_label(
                    has_subscription=bool((billing or {}).get("stripe_subscription_id")),
                    cancel_at_period_end=bool((billing or {}).get("cancel_at_period_end")),
                    billing_lifecycle_state=(billing or {}).get("billing_lifecycle_state"),
                ),
                "canonical_entitlement_state": (billing or {}).get("canonical_entitlement_state")
                or client.get("canonical_entitlement_state"),
                "stripe_customer_id": stripe_customer_id,
                "stripe_subscription_id": stripe_subscription_id,
                "stripe_webhook_last_received_at": wh_at,
                "stripe_webhook_last_event_type": wh_type,
                "billing_last_synced_at": billing_last_synced_at,
                "billing_sync_state": billing_sync_state,
                "last_payment": _iso_or_none((billing or {}).get("last_payment_at"))
                or _iso_or_none(client.get("last_payment_date")),
                "next_billing_date": _iso_or_none_billing_period((billing or {}).get("current_period_end")),
                "open_invoice_status": (billing or {}).get("open_invoice_status"),
                "stripe_next_payment_attempt_at": _iso_or_none((billing or {}).get("stripe_next_payment_attempt_at")),
                "retry_state_label": (
                    "Awaiting retry"
                    if str((billing or {}).get("open_invoice_status") or "").lower() in {"open", "past_due", "unpaid"}
                    else "No retry in progress"
                ),
                "next_retry_at_utc": _iso_or_none((billing or {}).get("stripe_next_payment_attempt_at")),
                "grace_period_ends_at_utc": _iso_or_none((billing or {}).get("grace_period_ends_at")),
                "billing_anomaly_flags": [],
                "stripe_sync_state_label": (
                    "Up to date" if str(billing_sync_state or "").lower() == "ok" else "Needs review"
                ),
                "stripe_sync_updated_at_utc": billing_last_synced_at,
                "billing_reconciliation_needed": bool((billing or {}).get("billing_reconciliation_needed")),
                "billing_reconciliation_reason": (billing or {}).get("billing_reconciliation_reason"),
                "billing_reconciliation_marked_at": _iso_or_none((billing or {}).get("billing_reconciliation_marked_at")),
                "receipts": receipts,
                "receipts_meta": receipts_meta,
            },
            "compliance_overview": {
                "properties_count": properties_count,
                "compliance_score": compliance_score,
                "risk_level": compliance_risk_level,
                "score_authority": score_data.get("score_authority"),
                "score_status": score_data.get("score_status"),
                "last_calculated_at": score_data.get("last_calculated_at")
                or score_data.get("portfolio_last_calculated_at"),
                "score_coverage": score_data.get("score_coverage"),
                "score_status_message": score_data.get("score_status_message"),
                "scoring_semantics_version": score_data.get("scoring_semantics_version"),
                "missing_documents": missing_docs,
                "overdue_items": overdue_items,
                "unresolved_evidence_document_count": unresolved_evidence_document_count,
            },
            "operations": {
                "issues": issues_count,
                "work_orders": work_orders_count,
                "contractors": contractors_count,
            },
            "activity_timeline": {
                "payments": payment_events,
                "login_events": login_events,
                "system_actions": system_events,
            },
            "operational_snapshot": {
                "onboarding_checklist": onboard_snap,
                "last_monthly_digest": last_digest_row,
                "last_broadcast_delivery": last_broadcast_delivery,
                "recent_audit_highlights": recent_audit_highlights,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get client control panel error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load client control panel",
        )


class RunClientJobRequest(BaseModel):
    job: str = "compliance_recalc_client"


@router.post("/clients/{client_id}/actions/resend-activation-email")
async def admin_action_resend_activation_email(request: Request, client_id: str):
    """Alias endpoint for control panel action. Reuses existing resend-password flow."""
    return await resend_password_setup(request, client_id)


@router.post("/clients/{client_id}/actions/resend-dashboard-email")
async def admin_action_resend_dashboard_email(request: Request, client_id: str):
    """Resend dashboard-ready email with explicit admin audit trail."""
    admin = await admin_route_guard(request)
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "full_name": 1, "email": 1, "contact_email": 1})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    from services.onboarding_email_governance import (
        log_onboarding_email_blocked,
        milestone_set_payload,
        primary_client_admin_password_set,
    )

    if not await primary_client_admin_password_set(client_id):
        await log_onboarding_email_blocked(
            template_key="DASHBOARD_READY",
            client_id=client_id,
            reason="admin_resend_blocked_password_not_set",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client admin has not completed password setup; dashboard-ready email cannot be sent.",
        )

    recipient = (client.get("contact_email") or client.get("email") or "").strip()
    if not recipient:
        raise HTTPException(status_code=400, detail="Client has no email address")

    from utils.app_urls import get_app_base_url
    from services.notification_orchestrator import notification_orchestrator

    portal_base = get_app_base_url(for_email_links=True).strip().rstrip("/")
    portal_link = f"{portal_base}/app/dashboard" if portal_base else "#"
    result = await notification_orchestrator.send(
        template_key="DASHBOARD_READY",
        client_id=client_id,
        context={
            "recipient": recipient,
            "client_name": (client.get("full_name") or "there"),
            "portal_link": portal_link,
            "portal_base_url": portal_base,
            "dashboard_milestone_email": True,
            "subject": "Your Compliance Vault Pro dashboard is ready",
        },
        idempotency_key=f"ADMIN_DASHBOARD_READY_{client_id}_{uuid.uuid4()}",
        event_type="admin_resend_dashboard_ready",
    )
    if result.outcome not in ("sent", "duplicate_ignored"):
        raise HTTPException(status_code=502, detail="Dashboard-ready email failed to send")

    now_d = datetime.now(timezone.utc)
    await db.clients.update_one(
        {"client_id": client_id},
        {
            "$set": {
                "onboarding_dashboard_ready_email_sent_at": now_d.isoformat(),
                **milestone_set_payload("dashboard_ready_email_sent_at", now_d),
            }
        },
    )
    logger.info(
        "onboarding_dashboard_ready_email_sent client_id=%s source=admin_resend template=DASHBOARD_READY",
        client_id,
    )
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=admin.get("portal_user_id"),
        actor_role=UserRole.ROLE_ADMIN,
        client_id=client_id,
        metadata={
            "action_type": "resend_dashboard_email",
            "message_id": result.message_id,
            "outcome": result.outcome,
        },
    )
    return {"success": True, "message": "Dashboard-ready email resent", "outcome": result.outcome}


@router.post("/clients/{client_id}/actions/recalculate-compliance")
async def admin_action_recalculate_compliance(request: Request, client_id: str):
    """Queue compliance recalculation for all client properties."""
    admin = await admin_route_guard(request)
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "client_id": 1})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    from services.compliance_recalc_queue import (
        enqueue_compliance_recalc,
        TRIGGER_ADMIN_UPLOAD,
        ACTOR_ADMIN,
    )

    props = await db.properties.find({"client_id": client_id}, {"_id": 0, "property_id": 1}).to_list(1000)
    enqueued = 0
    for prop in props:
        pid = prop.get("property_id")
        if not pid:
            continue
        ok = await enqueue_compliance_recalc(
            property_id=pid,
            client_id=client_id,
            trigger_reason=TRIGGER_ADMIN_UPLOAD,
            actor_type=ACTOR_ADMIN,
            actor_id=admin.get("portal_user_id"),
            correlation_id=f"admin_client_recalc:{client_id}:{pid}:{int(datetime.now(timezone.utc).timestamp())}",
        )
        if ok:
            enqueued += 1

    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=admin.get("portal_user_id"),
        actor_role=UserRole.ROLE_ADMIN,
        client_id=client_id,
        metadata={"action_type": "recalculate_compliance", "properties_enqueued": enqueued},
    )
    return {"success": True, "enqueued": enqueued}


@router.post("/clients/{client_id}/actions/reconcile-compliance-scores")
async def admin_action_reconcile_compliance_scores(request: Request, client_id: str):
    """Enqueue idempotent recalc jobs for properties with missing or pending persisted scores only."""
    admin = await admin_route_guard(request)
    db = database.get_db()
    if not await db.clients.find_one({"client_id": client_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Client not found")

    from services.compliance_score_reconciliation_service import enqueue_reconciliation_for_properties

    result = await enqueue_reconciliation_for_properties(client_id=client_id)
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=admin.get("portal_user_id"),
        actor_role=UserRole.ROLE_ADMIN,
        client_id=client_id,
        metadata={
            "action_type": "reconcile_compliance_scores",
            "enqueued": result.get("enqueued"),
            "skipped": result.get("skipped"),
        },
    )
    return {"success": True, **result}


@router.post("/clients/{client_id}/actions/run-job")
async def admin_action_run_client_job(request: Request, client_id: str, body: RunClientJobRequest):
    """
    Run a scoped client job action.
    Current safe job: compliance_recalc_client.
    """
    job = (body.job or "").strip() or "compliance_recalc_client"
    if job != "compliance_recalc_client":
        raise HTTPException(status_code=400, detail="Unsupported client job")
    return await admin_action_recalculate_compliance(request, client_id)


@router.post("/clients/{client_id}/actions/monthly-digest")
async def admin_action_client_monthly_digest(
    request: Request,
    client_id: str,
    body: ClientMonthlyDigestActionBody = Body(default_factory=ClientMonthlyDigestActionBody),
):
    """Send the monthly compliance digest email (and PDF) to one client. Audited; respects active subscription."""
    user = await admin_route_guard(request)
    await _enforce_admin_job_run_rate(user["portal_user_id"])
    db = database.get_db()
    exists = await db.clients.find_one({"client_id": client_id}, {"_id": 1})
    if not exists:
        raise HTTPException(status_code=404, detail="Client not found")
    from job_runner import run_instrumented

    pids = [str(x).strip() for x in (body.property_ids or []) if x and str(x).strip()]
    job_kw: Dict[str, Any] = {"client_id": client_id.strip()}
    if pids:
        job_kw["property_ids"] = pids
    meta = {"scope": "client", "client_id": client_id.strip()}
    if pids:
        meta["property_ids"] = pids

    try:
        result = await run_instrumented(
            "monthly_digest",
            "manual",
            triggered_by=user.get("portal_user_id"),
            job_kwargs=job_kw,
            start_metadata=meta,
        )
    except Exception as e:
        logger.error("admin monthly digest for client %s failed: %s", client_id, e)
        raise HTTPException(status_code=500, detail="Failed to send monthly digest")
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=user.get("portal_user_id"),
        client_id=client_id,
        metadata={
            "action_type": "client_monthly_digest",
            "outcome_status": (result or {}).get("outcome_status"),
            "message": (result or {}).get("message"),
            "property_ids": pids if pids else None,
        },
    )
    return {"success": True, "client_id": client_id, **(result or {})}


@router.post("/clients/{client_id}/actions/unlock-account")
async def admin_action_unlock_account(
    request: Request,
    client_id: str,
    body: SupportDangerousActionReasonBody = Body(...),
):
    """Unlock client portal users by re-enabling account and clearing lock flags."""
    admin = await admin_route_guard(request)
    support_reason = ensure_action_reason("unlock_account", body.reason)
    db = database.get_db()
    users = await db.portal_users.find(
        {"client_id": client_id},
        {"_id": 0, "portal_user_id": 1, "status": 1},
    ).to_list(20)
    if not users:
        raise HTTPException(status_code=404, detail="Portal user not found")

    portal_user_ids = [u.get("portal_user_id") for u in users if u.get("portal_user_id")]
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.portal_users.update_many(
        {"portal_user_id": {"$in": portal_user_ids}},
        {
            "$set": {"status": UserStatus.ACTIVE.value, "updated_at": now_iso},
            "$unset": {"locked_until": "", "lock_reason": "", "failed_login_attempts": ""},
            "$inc": {"session_version": 1},
        },
    )

    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=admin.get("portal_user_id"),
        actor_role=UserRole.ROLE_ADMIN,
        client_id=client_id,
        metadata={
            "action_type": "unlock_account",
            **normalized_admin_action_metadata("unlock_account", support_reason),
            "affected_users": len(portal_user_ids),
        },
    )
    return {"success": True, "unlocked_users": len(portal_user_ids)}


@router.post("/clients/{client_id}/impersonation/start", dependencies=[Depends(require_owner_or_admin)])
async def admin_start_impersonation(
    request: Request,
    client_id: str,
    ttl_minutes: int = Query(30, ge=5, le=120),
    body: SupportDangerousActionReasonBody = Body(...),
):
    """
    Start audited admin impersonation for a client portal user.
    Returns short-lived client token with explicit impersonation claims.
    """
    admin = await admin_route_guard(request)
    support_reason = ensure_action_reason("start_impersonation", body.reason)
    await enforce_step_up_if_required("start_impersonation", request, admin, require_recent_step_up)
    db = database.get_db()

    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "client_id": 1, "full_name": 1, "company_name": 1, "onboarding_status": 1},
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.get("onboarding_status") != OnboardingStatus.PROVISIONED.value:
        raise HTTPException(status_code=403, detail="Client is not provisioned for portal access")

    target = await db.portal_users.find_one(
        {"client_id": client_id, "role": UserRole.ROLE_CLIENT_ADMIN.value},
        {"_id": 0},
    )
    if not target:
        target = await db.portal_users.find_one(
            {"client_id": client_id, "role": {"$in": [UserRole.ROLE_CLIENT.value, UserRole.ROLE_CLIENT_ADMIN.value]}},
            {"_id": 0},
        )
    if not target:
        raise HTTPException(status_code=404, detail="No client portal user found")
    if target.get("status") != UserStatus.ACTIVE.value:
        raise HTTPException(status_code=403, detail="Target user is not active")
    if target.get("password_status") != PasswordStatus.SET.value:
        raise HTTPException(status_code=403, detail="Target user has not completed password setup")

    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=ttl_minutes)
    token_data = {
        "portal_user_id": target.get("portal_user_id"),
        "client_id": target.get("client_id"),
        "email": target.get("auth_email"),
        "role": target.get("role"),
        "session_version": target.get("session_version", 0),
        "impersonation": True,
        "impersonated_by_portal_user_id": admin.get("portal_user_id"),
        "impersonated_by_role": admin.get("role"),
        "impersonation_started_at": now.isoformat(),
    }
    access_token = create_access_token(token_data, expires_delta=timedelta(minutes=ttl_minutes))

    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=admin.get("portal_user_id"),
        actor_role=UserRole.ROLE_ADMIN,
        client_id=client_id,
        resource_type="portal_user",
        resource_id=target.get("portal_user_id"),
        metadata={
            "action_type": "impersonation_start",
            **normalized_admin_action_metadata("start_impersonation", support_reason),
            "ttl_minutes": ttl_minutes,
            "target_role": target.get("role"),
            "target_client_id": client_id,
            "target_email_masked": ((target.get("auth_email") or "")[:3] + "***"),
        },
    )
    return {
        "access_token": access_token,
        "expires_at": expires.isoformat(),
        "user": {
            "portal_user_id": target.get("portal_user_id"),
            "email": target.get("auth_email"),
            "role": target.get("role"),
            "client_id": target.get("client_id"),
            "impersonation": True,
            "impersonated_by_portal_user_id": admin.get("portal_user_id"),
        },
        "client": {
            "client_id": client_id,
            "name": client.get("full_name"),
            "company_name": client.get("company_name"),
            "target_email_masked": ((target.get("auth_email") or "")[:3] + "***"),
        },
    }

def _get_profile_avatars_path():
    return Path(resolve_data_dir()) / "data" / "profile_avatars"


@router.get("/clients/{client_id}/avatar")
async def get_client_avatar(request: Request, client_id: str):
    """Return a client's profile picture (admin). 404 if none."""
    await admin_route_guard(request)
    db = database.get_db()
    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "avatar_ext": 1}
    )
    if not client or not client.get("avatar_ext"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No profile picture")
    avatars_dir = _get_profile_avatars_path()
    ext = client.get("avatar_ext", ".jpg")
    file_path = avatars_dir / f"{client_id}{ext}"
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No profile picture")
    media = "image/jpeg" if ext == ".jpg" else ("image/png" if ext == ".png" else "image/webp")
    return FileResponse(path=str(file_path), media_type=media)


# ============================================================================
# ADMIN USER MANAGEMENT
# ============================================================================

@router.get("/admins")
async def list_admins(request: Request, include_archived: bool = Query(False)):
    """List all staff (OWNER + ADMIN) for admin management. Excludes password hashes.
    Archived (soft-deleted) users are omitted unless include_archived=true.
    """
    await admin_route_guard(request)
    db = database.get_db()

    try:
        q: Dict[str, Any] = {"role": {"$in": [UserRole.ROLE_OWNER.value, UserRole.ROLE_ADMIN.value]}}
        if not include_archived:
            q = merge_active_portal_user(q)
        admins = await db.portal_users.find(q, {"_id": 0, "password_hash": 0}).to_list(100)

        for a in admins:
            pid = a.get("portal_user_id")
            if pid:
                ok, blockers = await permanent_delete_preflight(db, str(pid))
                a["hard_delete_allowed"] = ok
                a["hard_delete_blockers"] = [] if ok else blockers
            a["is_test_like"] = bool(a.get("is_test_like"))

        return {
            "admins": admins,
            "total": len(admins),
        }

    except Exception as e:
        logger.error(f"List admins error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list admins",
        )


@router.post("/users/{portal_user_id}/archive")
async def archive_staff_user(request: Request, portal_user_id: str):
    """Soft-delete (archive) a portal user: disables login, retains billing linkage on client."""
    user = await admin_route_guard(request)
    await require_recent_step_up(request, user)
    db = database.get_db()
    try:
        await archive_portal_user(
            db,
            portal_user_id,
            user["portal_user_id"],
            actor_role=UserRole(user["role"]),
        )
        return {"message": "User archived", "portal_user_id": portal_user_id}
    except ValueError as e:
        raise _portal_lifecycle_http(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("archive user error: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to archive user")


@router.post("/users/{portal_user_id}/restore")
async def restore_staff_user(request: Request, portal_user_id: str):
    """Restore an archived portal user to active (not a substitute for reactivating legacy DISABLED-only rows)."""
    user = await admin_route_guard(request)
    await require_recent_step_up(request, user)
    db = database.get_db()
    try:
        await restore_portal_user(
            db,
            portal_user_id,
            user["portal_user_id"],
            actor_role=UserRole(user["role"]),
        )
        return {"message": "User restored", "portal_user_id": portal_user_id}
    except ValueError as e:
        raise _portal_lifecycle_http(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("restore user error: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to restore user")


@router.get("/users/{portal_user_id}/permanent-delete-check")
async def permanent_delete_check(request: Request, portal_user_id: str):
    """Return whether hard delete is allowed (billing and audit preflight)."""
    await require_owner_or_admin(request)
    db = database.get_db()
    allowed, blockers = await permanent_delete_preflight(db, portal_user_id)
    return {"allowed": allowed, "blockers": blockers}


@router.delete("/users/{portal_user_id}/permanent")
async def permanent_delete_user(request: Request, portal_user_id: str):
    """Remove portal_users row only when preflight passes; never deletes Stripe, clients, or invoice rows."""
    user = await require_owner(request)
    await require_recent_step_up(request, user)
    db = database.get_db()
    try:
        await permanent_delete_portal_user(
            db,
            portal_user_id,
            user["portal_user_id"],
            actor_role=UserRole(user["role"]),
        )
        return {"message": "User permanently deleted", "portal_user_id": portal_user_id}
    except ValueError as e:
        raise _portal_lifecycle_http(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("permanent delete user error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to permanently delete user",
        )


@router.post("/users/{portal_user_id}/test-like")
async def set_portal_user_test_like_route(
    request: Request,
    portal_user_id: str,
    body: PortalUserTestLikeBody,
):
    """Mark or unmark a portal user as test/dummy (OWNER/ADMIN, step-up). Never applies to OWNER role."""
    user = await require_owner_or_admin(request)
    await require_recent_step_up(request, user)
    db = database.get_db()
    try:
        await set_portal_user_test_like_flag(
            db,
            portal_user_id,
            body.is_test_like,
            user["portal_user_id"],
            actor_role=UserRole(user["role"]),
        )
        return {"ok": True, "portal_user_id": portal_user_id, "is_test_like": body.is_test_like}
    except ValueError as e:
        raise _portal_lifecycle_http(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("set portal user test-like error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update test flag",
        )


@router.post("/admins/invite")
async def invite_admin(request: Request, invite_data: AdminInviteRequest):
    """Invite a new ADMIN user (OWNER only). Creates ROLE_ADMIN only; no second OWNER.
    
    Creates PortalUser with ROLE_ADMIN, sends password setup email, audits. Staff field created_by_owner_id set when invited by OWNER.
    """
    inviter = await require_owner(request)
    await require_recent_step_up(request, inviter)
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
        from utils.public_app_url import get_frontend_base_url
        try:
            base_url = get_frontend_base_url()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=f"App URL not configured: {e}")
        setup_link = f"{base_url}/set-password?token={raw_token}"
        idempotency_key = f"{portal_user_id}_ADMIN_INVITE"
        result = await notification_orchestrator.send(
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
        if result.outcome != "sent":
            if result.outcome == "blocked":
                reason = result.block_reason or "email provider not configured"
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
                    "message": "An invitation was already sent to this email recently. If they did not receive it, check spam or use Resend invite later.",
                    "portal_user_id": portal_user_id,
                    "email": invite_data.email,
                    "status": "INVITED",
                    "duplicate": True,
                }
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
    """Deactivate an ADMIN user (OWNER or ADMIN). Delegates to archive (USER_ARCHIVED audit)."""
    user = await admin_route_guard(request)
    await require_recent_step_up(request, user)
    db = database.get_db()

    try:
        await archive_portal_user(
            db,
            portal_user_id,
            user["portal_user_id"],
            actor_role=UserRole(user["role"]),
        )
        return {
            "message": "Admin archived successfully",
            "portal_user_id": portal_user_id,
        }
    except ValueError as e:
        raise _portal_lifecycle_http(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Deactivate admin error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate admin",
        )


@router.post("/admins/{portal_user_id}/reactivate")
async def reactivate_admin(request: Request, portal_user_id: str):
    """Reactivate a disabled ADMIN user. Archived users are restored (USER_RESTORED); legacy DISABLED uses ADMIN_ENABLED."""
    user = await admin_route_guard(request)
    await require_recent_step_up(request, user)
    db = database.get_db()

    try:
        target = await db.portal_users.find_one(
            {"portal_user_id": portal_user_id, "role": UserRole.ROLE_ADMIN.value},
            {"_id": 0},
        )

        if not target:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Admin not found",
            )

        if target.get("is_deleted") is True:
            await restore_portal_user(
                db,
                portal_user_id,
                user["portal_user_id"],
                actor_role=UserRole(user["role"]),
            )
            return {
                "message": "Admin restored successfully",
                "portal_user_id": portal_user_id,
            }

        if target.get("status") == UserStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin is already active",
            )

        await db.portal_users.update_one(
            {"portal_user_id": portal_user_id},
            {"$set": {"status": UserStatus.ACTIVE.value}},
        )

        await create_audit_log(
            action=AuditAction.ADMIN_ENABLED,
            actor_role=UserRole(user["role"]),
            actor_id=user["portal_user_id"],
            resource_type="portal_user",
            resource_id=portal_user_id,
            metadata={
                "reactivated_email": target.get("auth_email"),
                "by": user.get("email"),
            },
        )

        return {
            "message": "Admin reactivated successfully",
            "portal_user_id": portal_user_id,
        }

    except ValueError as e:
        raise _portal_lifecycle_http(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reactivate admin error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reactivate admin",
        )


@router.post("/admins/{portal_user_id}/force-logout")
async def force_logout_admin(request: Request, portal_user_id: str):
    """Force logout all sessions for a staff user by incrementing session_version (OWNER only). Audited."""
    user = await require_owner(request)
    await require_recent_step_up(request, user)
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
    await require_recent_step_up(request, user)
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
        
        from services.notification_orchestrator import notification_orchestrator
        from utils.public_app_url import get_frontend_base_url
        try:
            base_url = get_frontend_base_url()
        except ValueError as e:
            raise HTTPException(status_code=503, detail=f"App URL not configured: {e}")
        setup_link = f"{base_url}/set-password?token={raw_token}"
        admin_name = target_admin.get("full_name", target_admin.get("auth_email", "Admin"))
        # Must differ from initial invite key ({portal_user_id}_ADMIN_INVITE) or orchestrator returns
        # duplicate_ignored and never sends — resend would silently do nothing while still returning 200.
        idempotency_key = f"{portal_user_id}_ADMIN_INVITE_RESEND_{token_hash}"
        result = await notification_orchestrator.send(
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
        if result.outcome != "sent":
            if result.outcome == "blocked":
                reason = result.block_reason or "email provider not configured"
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
                logger.warning(
                    "resend_admin_invite duplicate_ignored portal_user_id=%s idempotency_key=%s",
                    portal_user_id,
                    idempotency_key,
                )
                return {
                    "message": "An invitation was already sent recently. If the recipient did not receive it, check spam or try again in a few minutes.",
                    "portal_user_id": portal_user_id,
                    "email": target_admin["auth_email"],
                    "duplicate": True,
                }
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
        logger.info(
            "Admin invite email resent: portal_user_id=%s to=%s",
            portal_user_id,
            target_admin.get("auth_email"),
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
        from services.requirement_truth import enrich_requirements_for_admin

        requirements = await enrich_requirements_for_admin(db, requirements)
        
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


class AdminAssistantChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    crn: Optional[str] = None


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
        from services.requirement_truth import enrich_requirements_for_admin

        requirements_enriched = await enrich_requirements_for_admin(db, requirements)
        
        documents = await db.documents.find(
            {"client_id": client_id},
            {"_id": 0, "document_id": 1, "property_id": 1, "requirement_id": 1,
             "file_name": 1, "status": 1, "uploaded_at": 1, "category": 1}
        ).to_list(500)
        
        # Compliance summary
        total_reqs = len(requirements_enriched)
        compliant = sum(1 for r in requirements_enriched if r.get("status") == "COMPLIANT")
        overdue = sum(1 for r in requirements_enriched if r.get("status") == "OVERDUE")
        expiring = sum(1 for r in requirements_enriched if r.get("status") == "EXPIRING_SOON")
        
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
                "COMPLIANT": [r.get("display_label") for r in requirements_enriched if r.get("status") == "COMPLIANT"],
                "OVERDUE": [
                    {"requirement": r.get("display_label"), "property_id": r.get("property_id"), "date_label": r.get("date_label")}
                    for r in requirements_enriched
                    if r.get("status") == "OVERDUE"
                ],
                "EXPIRING_SOON": [
                    {
                        "requirement": r.get("display_label"),
                        "property_id": r.get("property_id"),
                        "date_label": r.get("date_label"),
                    }
                    for r in requirements_enriched
                    if r.get("status") == "EXPIRING_SOON"
                ],
                "PENDING": [r.get("display_label") for r in requirements_enriched if r.get("status") == "PENDING"],
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
        
        # Step 3: Call LLM (canonical config: OPENAI_API_KEY when AI_ENABLED=true)
        try:
            from utils import ai_config
            from utils.llm_chat import chat_openai
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Admin assistant unavailable (LLM not configured)",
            )
        system_prompt = ADMIN_ASSISTANT_PROMPT.format(
            snapshot=json.dumps(snapshot_data, indent=2, default=str)
        )
        if ai_config.AI_ENABLED and not ai_config.is_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Admin assistant unavailable (set OPENAI_API_KEY when AI_ENABLED=true)",
            )
        answer = await chat_openai(system_prompt=system_prompt, user_text=question)
        model_used = getattr(ai_config, "AI_MODEL", "openai")
        
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
            "model": model_used,
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
                "model": model_used,
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


@router.post("/assistant/chat", dependencies=[Depends(require_owner_or_admin)])
async def admin_assistant_chat(request: Request, data: AdminAssistantChatRequest):
    """
    Admin assistant chat with optional CRN: when CRN provided, scope to that client.
    Returns same shape as client /api/assistant/chat (conversation_id, answer, citations, safety_flags).
    """
    user = await admin_route_guard(request)
    if not data.crn or len(data.crn.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CRN required for admin assistant chat"
        )
    if not data.message or len(data.message.strip()) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty")
    if len(data.message) > 2000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message too long (max 2000 characters)")

    from utils.rate_limiter import rate_limiter
    from utils import ai_config
    from services.assistant_chat_service import chat_turn as assistant_chat_turn

    if ai_config.AI_ENABLED and not ai_config.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "AI_NOT_CONFIGURED", "detail": "AI service not configured. Set OPENAI_API_KEY when AI_ENABLED=true."},
        )

    admin_id = user.get("portal_user_id") or user.get("auth_email", "")
    allowed, err = await rate_limiter.check_rate_limit(
        key=f"admin_assistant_chat_{admin_id}",
        max_attempts=20,
        window_minutes=10,
    )
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err)

    db = database.get_db()
    client = await db.clients.find_one(
        {"customer_reference": data.crn.strip().upper()},
        {"_id": 0, "client_id": 1},
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No client found with CRN: {data.crn.strip()}")

    client_id = client["client_id"]
    result = await assistant_chat_turn(
        client_id=client_id,
        user_id=admin_id,
        message=data.message.strip(),
        conversation_id=data.conversation_id,
        property_id=None,
        is_admin=True,
    )
    return result


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




@router.get("/assistant/conversations", dependencies=[Depends(require_support_or_above)])
async def list_assistant_conversations(
    request: Request,
    client_id: Optional[str] = Query(default=None, description="Filter by client_id"),
    escalated: Optional[bool] = Query(default=None, description="Filter by escalated"),
    limit: int = Query(default=50, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
):
    """List Portal Assistant conversations. Support role can read transcripts for handover context."""
    await require_support_or_above(request)
    db = database.get_db()
    query = {}
    if client_id:
        query["client_id"] = client_id
    if escalated is not None:
        query["escalated"] = escalated
    total = await db.assistant_conversations.count_documents(query)
    cursor = db.assistant_conversations.find(
        query,
        {"_id": 0, "conversation_id": 1, "client_id": 1, "created_by_user_id": 1, "created_at": 1, "last_activity_at": 1, "escalated": 1, "escalation_reason": 1, "escalated_at": 1},
    ).sort("last_activity_at", -1).skip(skip).limit(limit)
    conversations = await cursor.to_list(length=limit)
    return {
        "conversations": conversations,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": total > skip + limit,
    }


@router.get("/assistant/conversations/{conversation_id}", dependencies=[Depends(require_support_or_above)])
async def get_assistant_conversation_with_messages(
    request: Request,
    conversation_id: str,
):
    """Get one Portal Assistant conversation with full message transcript. Support role can read."""
    await require_support_or_above(request)
    db = database.get_db()
    conv = await db.assistant_conversations.find_one(
        {"conversation_id": conversation_id},
        {"_id": 0},
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    messages = await db.assistant_messages.find(
        {"conversation_id": conversation_id},
        {"_id": 0, "message_id": 1, "role": 1, "message": 1, "created_at": 1, "citations": 1, "safety_flags": 1},
    ).sort("created_at", 1).to_list(length=500)
    return {"conversation": conv, "messages": messages}