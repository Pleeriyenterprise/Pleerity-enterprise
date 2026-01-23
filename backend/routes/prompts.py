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
    Useful for the template creation form.
    """
    db = database.get_db()
    
    # Get unique service codes from services_v2
    pipeline = [
        {"$match": {"status": "active"}},
        {"$group": {"_id": "$service_code", "name": {"$first": "$name"}}},
        {"$sort": {"_id": 1}},
    ]
    
    cursor = db.services_v2.aggregate(pipeline)
    results = await cursor.to_list(length=100)
    
    service_codes = [
        {"code": r["_id"], "name": r.get("name", r["_id"])}
        for r in results if r["_id"]
    ]
    
    # If no services in DB, provide common defaults for prompt templates
    if not service_codes:
        service_codes = [
            {"code": "AI_WF_BLUEPRINT", "name": "AI Workflow Blueprint"},
            {"code": "COMPLIANCE_AUDIT", "name": "Compliance Audit"},
            {"code": "DOCUMENT_ANALYSIS", "name": "Document Analysis"},
            {"code": "RISK_ASSESSMENT", "name": "Risk Assessment"},
            {"code": "REPORT_GENERATION", "name": "Report Generation"},
            {"code": "DATA_EXTRACTION", "name": "Data Extraction"},
        ]
    
    return {
        "service_codes": service_codes
    }


@router.get("/reference/doc-types")
async def get_doc_types(
    current_user: dict = Depends(require_super_admin),
):
    """
    Get available document types.
    """
    from services.document_generator import DocumentType
    
    return {
        "doc_types": [
            {"code": dt.value, "name": dt.value.replace("_", " ").title()}
            for dt in DocumentType
        ]
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
