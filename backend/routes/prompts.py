"""
Enterprise Prompt Manager API Routes

Admin endpoints for managing AI document generation prompts.
Access restricted to Super Admin only (least privilege).

Features:
- CRUD operations for prompt templates
- Prompt Playground for testing
- Version history and audit log
- Activation workflow
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from datetime import datetime, timezone

from middleware import admin_route_guard
from models.prompts import (
    PromptStatus, PromptTemplateCreate, PromptTemplateUpdate,
    PromptTemplateResponse, PromptTestRequest, PromptTestResult,
    PromptActivationRequest, PromptListResponse,
)
from models.permissions import BUILT_IN_ROLES, has_permission
from services.prompt_service import prompt_service
from database import database
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/prompts", tags=["prompt-manager"])


# ============================================
# Permission Check - Super Admin Only
# ============================================

async def require_super_admin(current_user: dict = Depends(admin_route_guard)):
    """
    Enforce Super Admin only access.
    
    Per user requirements: Only Super Admin can create/edit/activate prompts.
    
    Checks:
    1. role_id == "super_admin" (team permissions system)
    2. role == "ROLE_ADMIN" (legacy admin check - existing admins are considered super admins)
    3. team.manage permission (full team control implies super admin level)
    """
    # Check legacy admin role - existing ROLE_ADMIN users are super admins
    if current_user.get("role") == "ROLE_ADMIN":
        return current_user
    
    # Check new team permissions role_id
    role_id = current_user.get("role_id", "")
    if role_id == "super_admin":
        return current_user
    
    # Check if user has full team.manage permission (which implies super admin level)
    user_permissions = current_user.get("permissions", {})
    if has_permission(user_permissions, "team", "manage"):
        return current_user
    
    raise HTTPException(
        status_code=403,
        detail="Access denied. Prompt Manager requires Super Admin privileges."
    )


# ============================================
# CRUD Endpoints
# ============================================

@router.post("", response_model=PromptTemplateResponse)
async def create_prompt_template(
    data: PromptTemplateCreate,
    current_user: dict = Depends(require_super_admin),
):
    """
    Create a new prompt template in DRAFT status.
    
    The template uses the {{INPUT_DATA_JSON}} injection pattern.
    Scattered placeholders are not allowed.
    """
    try:
        result = await prompt_service.create_template(
            data=data,
            created_by=current_user.get("email", "admin"),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=PromptListResponse)
async def list_prompt_templates(
    service_code: Optional[str] = Query(None, description="Filter by service code"),
    doc_type: Optional[str] = Query(None, description="Filter by document type"),
    status: Optional[str] = Query(None, description="Filter by status (comma-separated)"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    search: Optional[str] = Query(None, description="Search in name/description"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_super_admin),
):
    """List prompt templates with filters and pagination."""
    # Parse status filter
    status_list = None
    if status:
        try:
            status_list = [PromptStatus(s.strip()) for s in status.split(",")]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid status: {e}")
    
    # Parse tags filter
    tags_list = None
    if tags:
        tags_list = [t.strip() for t in tags.split(",")]
    
    prompts, total = await prompt_service.list_templates(
        service_code=service_code,
        doc_type=doc_type,
        status=status_list,
        tags=tags_list,
        search=search,
        page=page,
        page_size=page_size,
    )
    
    return PromptListResponse(
        prompts=prompts,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/active/{service_code}/{doc_type}", response_model=PromptTemplateResponse)
async def get_active_prompt(
    service_code: str,
    doc_type: str,
    current_user: dict = Depends(require_super_admin),
):
    """Get the currently ACTIVE prompt for a service/doc_type combination."""
    result = await prompt_service.get_active_template(service_code, doc_type)
    
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No active prompt found for {service_code}/{doc_type}"
        )
    
    return result


@router.get("/history/{service_code}/{doc_type}")
async def get_version_history(
    service_code: str,
    doc_type: str,
    current_user: dict = Depends(require_super_admin),
):
    """Get version history for a service/doc_type combination."""
    versions = await prompt_service.get_version_history(service_code, doc_type)
    
    # Find current active version
    active_version = None
    for v in versions:
        if v["status"] == PromptStatus.ACTIVE.value:
            active_version = v["version"]
            break
    
    return {
        "service_code": service_code,
        "doc_type": doc_type,
        "current_active_version": active_version,
        "versions": versions,
        "total_versions": len(versions),
    }


@router.get("/{template_id}", response_model=PromptTemplateResponse)
async def get_prompt_template(
    template_id: str,
    current_user: dict = Depends(require_super_admin),
):
    """Get a specific prompt template by ID."""
    result = await prompt_service.get_template(template_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return result


@router.put("/{template_id}", response_model=PromptTemplateResponse)
async def update_prompt_template(
    template_id: str,
    data: PromptTemplateUpdate,
    current_user: dict = Depends(require_super_admin),
):
    """
    Update a prompt template.
    
    RULES:
    - DRAFT templates: Updated in place
    - TESTED/ACTIVE templates: Creates NEW VERSION
    - DEPRECATED/ARCHIVED: Cannot be updated
    """
    try:
        result = await prompt_service.update_template(
            template_id=template_id,
            data=data,
            updated_by=current_user.get("email", "admin"),
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Template not found")
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{template_id}")
async def archive_prompt_template(
    template_id: str,
    current_user: dict = Depends(require_super_admin),
):
    """
    Archive a prompt template (soft delete).
    
    Active templates cannot be archived - deprecate them first.
    """
    success = await prompt_service.archive_template(
        template_id=template_id,
        archived_by=current_user.get("email", "admin"),
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot archive. Template not found or is currently ACTIVE."
        )
    
    return {"success": True, "message": "Template archived"}


# ============================================
# Testing Endpoints (Prompt Playground)
# ============================================

@router.post("/test", response_model=PromptTestResult)
async def test_prompt(
    request: PromptTestRequest,
    current_user: dict = Depends(require_super_admin),
):
    """
    Execute a test in the Prompt Playground.
    
    This tests the prompt with sample input data and validates
    the output against the defined schema.
    
    Required before:
    - Marking as TESTED
    - Activating the prompt
    """
    try:
        result = await prompt_service.execute_test(
            request=request,
            executed_by=current_user.get("email", "admin"),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Test execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Test execution failed: {str(e)}")


@router.get("/test/{template_id}/results")
async def get_test_results(
    template_id: str,
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_super_admin),
):
    """Get test results history for a template."""
    results = await prompt_service.get_test_results(template_id, limit)
    
    return {
        "template_id": template_id,
        "results": [r.model_dump() for r in results],
        "total": len(results),
    }


# ============================================
# Lifecycle Management
# ============================================

@router.post("/{template_id}/mark-tested")
async def mark_template_as_tested(
    template_id: str,
    current_user: dict = Depends(require_super_admin),
):
    """
    Mark a DRAFT template as TESTED.
    
    REQUIREMENT: Template must have a passing test result.
    """
    try:
        await prompt_service.mark_as_tested(
            template_id=template_id,
            marked_by=current_user.get("email", "admin"),
        )
        return {"success": True, "message": "Template marked as TESTED"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{template_id}/activate")
async def activate_prompt_template(
    template_id: str,
    request: PromptActivationRequest,
    current_user: dict = Depends(require_super_admin),
):
    """
    Activate a TESTED prompt template.
    
    RULES:
    - Only TESTED templates can be activated
    - Must have passed schema validation
    - Previous ACTIVE version becomes DEPRECATED
    - Activation is logged with evidence
    """
    try:
        result = await prompt_service.activate_template(
            template_id=template_id,
            activation_reason=request.activation_reason,
            activated_by=current_user.get("email", "admin"),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# Audit Log
# ============================================

@router.get("/audit/log")
async def get_audit_log(
    template_id: Optional[str] = Query(None, description="Filter by template ID"),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_super_admin),
):
    """Get prompt audit log entries."""
    entries = await prompt_service.get_audit_log(
        template_id=template_id,
        limit=limit,
    )
    
    return {
        "entries": entries,
        "total": len(entries),
    }


# ============================================
# Service Code & Doc Type Reference
# ============================================

@router.get("/reference/service-codes")
async def get_service_codes(
    current_user: dict = Depends(require_super_admin),
):
    """
    Get available service codes from the service catalogue.
    
    AUTHORITATIVE SOURCE: service_catalogue_v2 collection
    Only services from the catalogue can be used in prompts.
    """
    db = database.get_db()
    
    # Get service codes from service_catalogue_v2 (AUTHORITATIVE)
    cursor = db.service_catalogue_v2.find(
        {"active": True},
        {"service_code": 1, "service_name": 1, "category": 1, "_id": 0}
    ).sort("service_code", 1)
    
    services = await cursor.to_list(length=100)
    
    service_codes = [
        {
            "code": s["service_code"],
            "name": s.get("service_name", s["service_code"]),
            "category": s.get("category", "other"),
            # Canonical doc_type equals service_code
            "canonical_doc_type": s["service_code"],
        }
        for s in services if s.get("service_code")
    ]
    
    return {
        "service_codes": service_codes,
        "note": "Service Code MUST match catalogue. Document Type should be canonical (same as Service Code)."
    }


@router.get("/reference/doc-types")
async def get_doc_types(
    service_code: Optional[str] = Query(None, description="Get doc types for specific service"),
    current_user: dict = Depends(require_super_admin),
):
    """
    Get available document types.
    
    CANONICAL RULE: doc_type should equal service_code for service-specific documents.
    This endpoint returns allowed doc_types per service from SERVICE_DOC_TYPE_MAP.
    """
    # Service-specific document type mapping
    SERVICE_DOC_TYPE_MAP = {
        "AI_WF_BLUEPRINT": [
            {"code": "AI_WF_BLUEPRINT", "name": "AI Workflow Blueprint", "canonical": True},
            {"code": "AI_WORKFLOW_BLUEPRINT", "name": "AI Workflow Blueprint (Alias)", "canonical": False},
        ],
        "AI_PROC_MAP": [
            {"code": "AI_PROC_MAP", "name": "Business Process Map", "canonical": True},
        ],
        "AI_TOOLS_REC": [
            {"code": "AI_TOOLS_REC", "name": "AI Tool Recommendations", "canonical": True},
        ],
        "MR_BASIC": [
            {"code": "MR_BASIC", "name": "Basic Market Research", "canonical": True},
        ],
        "MR_ADV": [
            {"code": "MR_ADV", "name": "Advanced Market Research", "canonical": True},
        ],
        "HMO_AUDIT": [
            {"code": "HMO_AUDIT", "name": "HMO Compliance Audit", "canonical": True},
        ],
        "FULL_AUDIT": [
            {"code": "FULL_AUDIT", "name": "Full Property Audit", "canonical": True},
        ],
        "DOC_PACK_ESSENTIAL": [
            {"code": "DOC_PACK_ESSENTIAL", "name": "Essential Document Pack", "canonical": True},
        ],
        "DOC_PACK_TENANCY": [
            {"code": "DOC_PACK_TENANCY", "name": "Tenancy Document Pack", "canonical": True},
        ],
        "DOC_PACK_ULTIMATE": [
            {"code": "DOC_PACK_ULTIMATE", "name": "Ultimate Document Pack", "canonical": True},
        ],
    }
    
    if service_code:
        # Return doc types allowed for specific service
        doc_types = SERVICE_DOC_TYPE_MAP.get(service_code, [
            {"code": service_code, "name": service_code.replace("_", " ").title(), "canonical": True}
        ])
        return {
            "service_code": service_code,
            "doc_types": doc_types,
            "note": "Use canonical doc_type (same as service_code) for new prompts."
        }
    
    # Return all canonical doc types
    all_doc_types = []
    for svc_code, types in SERVICE_DOC_TYPE_MAP.items():
        for t in types:
            if t.get("canonical", False):
                all_doc_types.append({
                    "code": t["code"],
                    "name": t["name"],
                    "service_code": svc_code,
                })
    
    return {
        "doc_types": all_doc_types,
        "note": "Document Type should be canonical (same as Service Code) for service-specific documents."
    }


# ============================================
# Statistics
# ============================================

@router.get("/stats/overview")
async def get_prompt_stats(
    current_user: dict = Depends(require_super_admin),
):
    """Get prompt manager statistics."""
    db = database.get_db()
    
    # Count by status
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    status_cursor = db[prompt_service.COLLECTION].aggregate(pipeline)
    status_results = await status_cursor.to_list(length=10)
    
    status_counts = {r["_id"]: r["count"] for r in status_results}
    
    # Total templates
    total = await db[prompt_service.COLLECTION].count_documents({})
    
    # Total tests in last 24h
    from datetime import timedelta
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    recent_tests = await db[prompt_service.TEST_COLLECTION].count_documents({
        "executed_at": {"$gte": yesterday.isoformat()}
    })
    
    # Recent audit entries
    recent_audits = await db[prompt_service.AUDIT_COLLECTION].count_documents({
        "performed_at": {"$gte": yesterday}
    })
    
    return {
        "total_templates": total,
        "by_status": {
            "draft": status_counts.get(PromptStatus.DRAFT.value, 0),
            "tested": status_counts.get(PromptStatus.TESTED.value, 0),
            "active": status_counts.get(PromptStatus.ACTIVE.value, 0),
            "deprecated": status_counts.get(PromptStatus.DEPRECATED.value, 0),
            "archived": status_counts.get(PromptStatus.ARCHIVED.value, 0),
        },
        "tests_last_24h": recent_tests,
        "audit_entries_last_24h": recent_audits,
    }


# ============================================
# Prompt Performance Analytics
# ============================================

@router.get("/analytics/performance")
async def get_prompt_performance_analytics(
    template_id: Optional[str] = Query(None, description="Filter by template ID"),
    service_code: Optional[str] = Query(None, description="Filter by service code"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: dict = Depends(require_super_admin),
):
    """
    Get prompt performance analytics.
    
    Returns:
    - Total executions
    - Success rate
    - Average execution time
    - Token usage
    - Performance by prompt
    """
    from services.prompt_manager_bridge import prompt_manager_bridge
    
    analytics = await prompt_manager_bridge.get_prompt_analytics(
        template_id=template_id,
        service_code=service_code,
        days=days,
    )
    
    return analytics


@router.get("/analytics/execution-timeline")
async def get_execution_timeline(
    days: int = Query(7, ge=1, le=90, description="Number of days"),
    current_user: dict = Depends(require_super_admin),
):
    """
    Get execution timeline data for charts.
    
    Returns daily execution counts and success rates.
    """
    db = database.get_db()
    
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    pipeline = [
        {"$match": {"executed_at": {"$gte": cutoff}}},
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": "$executed_at"
                    }
                },
                "total": {"$sum": 1},
                "successful": {"$sum": {"$cond": ["$success", 1, 0]}},
                "total_tokens": {"$sum": "$total_tokens"},
                "avg_time_ms": {"$avg": "$execution_time_ms"},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    
    cursor = db.prompt_execution_metrics.aggregate(pipeline)
    results = await cursor.to_list(length=90)
    
    return {
        "period_days": days,
        "timeline": [
            {
                "date": r["_id"],
                "total_executions": r["total"],
                "successful_executions": r["successful"],
                "success_rate": round(r["successful"] / r["total"] * 100, 1) if r["total"] > 0 else 0,
                "total_tokens": r["total_tokens"],
                "avg_execution_time_ms": round(r["avg_time_ms"], 0) if r["avg_time_ms"] else 0,
            }
            for r in results
        ],
    }


@router.get("/analytics/top-prompts")
async def get_top_prompts(
    limit: int = Query(10, ge=1, le=50, description="Number of top prompts to return"),
    sort_by: str = Query("executions", description="Sort by: executions, success_rate, tokens"),
    current_user: dict = Depends(require_super_admin),
):
    """
    Get top performing prompts by various metrics.
    """
    db = database.get_db()
    
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    
    # Sort field mapping
    sort_fields = {
        "executions": "total_executions",
        "success_rate": "success_rate",
        "tokens": "total_tokens",
    }
    sort_field = sort_fields.get(sort_by, "total_executions")
    
    pipeline = [
        {"$match": {"executed_at": {"$gte": cutoff}}},
        {
            "$group": {
                "_id": {
                    "template_id": "$template_id",
                    "version": "$version",
                },
                "service_code": {"$first": "$service_code"},
                "source": {"$first": "$source"},
                "total_executions": {"$sum": 1},
                "successful": {"$sum": {"$cond": ["$success", 1, 0]}},
                "total_tokens": {"$sum": "$total_tokens"},
                "avg_time_ms": {"$avg": "$execution_time_ms"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "template_id": "$_id.template_id",
                "version": "$_id.version",
                "service_code": 1,
                "source": 1,
                "total_executions": 1,
                "successful_executions": "$successful",
                "success_rate": {
                    "$round": [
                        {"$multiply": [{"$divide": ["$successful", "$total_executions"]}, 100]},
                        1
                    ]
                },
                "total_tokens": 1,
                "avg_execution_time_ms": {"$round": ["$avg_time_ms", 0]},
            }
        },
        {"$sort": {sort_field: -1}},
        {"$limit": limit},
    ]
    
    cursor = db.prompt_execution_metrics.aggregate(pipeline)
    results = await cursor.to_list(length=limit)
    
    # Enrich with template names
    for r in results:
        if r["template_id"].startswith("PT-"):
            template = await db.prompt_templates.find_one(
                {"template_id": r["template_id"]},
                {"name": 1}
            )
            r["name"] = template["name"] if template else r["template_id"]
        else:
            r["name"] = r["template_id"].replace("LEGACY_", "")
    
    return {
        "sort_by": sort_by,
        "limit": limit,
        "prompts": results,
    }
