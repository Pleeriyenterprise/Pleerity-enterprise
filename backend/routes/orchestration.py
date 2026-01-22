"""
Document Orchestration API Routes - Endpoints for GPT-powered document generation.

These endpoints control the document generation pipeline:
- Generate documents for orders (payment-gated)
- View generation history
- Approve/reject generated content
- Regenerate with changes

All generation is payment-gated and requires human review before final delivery.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from middleware import admin_route_guard
from services.document_orchestrator import document_orchestrator, OrchestrationStatus
from services.service_catalogue_v2 import service_catalogue_v2
from services.gpt_prompt_registry import get_prompt_for_service, validate_intake_data
from database import database
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/orchestration", tags=["document-orchestration"])


# ============================================================================
# REQUEST MODELS
# ============================================================================

class GenerateDocumentRequest(BaseModel):
    """Request to generate documents for an order."""
    order_id: str = Field(..., description="Order ID to generate documents for")
    intake_data: Dict[str, Any] = Field(..., description="Intake form data")


class RegenerateDocumentRequest(BaseModel):
    """Request to regenerate documents with changes."""
    order_id: str = Field(..., description="Order ID to regenerate")
    intake_data: Dict[str, Any] = Field(..., description="Updated intake form data")
    regeneration_notes: str = Field(..., description="Notes describing requested changes")


class ReviewRequest(BaseModel):
    """Request to approve or reject generated content."""
    order_id: str = Field(..., description="Order ID to review")
    approved: bool = Field(..., description="Whether to approve or reject")
    review_notes: Optional[str] = Field(None, description="Review notes or feedback")


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@router.post("/generate")
async def generate_documents(
    request: GenerateDocumentRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Generate documents for a paid order.
    
    This endpoint executes the FULL pipeline:
    1. Validates the order has been paid
    2. Creates immutable intake snapshot
    3. Selects the appropriate prompt based on service_code
    4. Executes GPT generation
    5. Renders DOCX + PDF documents
    6. Stores with versioning and hashes
    7. Sets order status to review_pending
    
    Requires admin authentication.
    """
    logger.info(f"Document generation requested for order {request.order_id} by {current_user.get('email')}")
    
    # Execute full pipeline (generation + rendering)
    result = await document_orchestrator.execute_full_pipeline(
        order_id=request.order_id,
        intake_data=request.intake_data,
        regeneration=False,
    )
    
    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=result.error_message or "Generation failed"
        )
    
    return {
        "success": True,
        "order_id": result.order_id,
        "service_code": result.service_code,
        "version": result.version,
        "status": result.status.value,
        "structured_output": result.structured_output,
        "rendered_documents": result.rendered_documents,
        "validation_issues": result.validation_issues,
        "data_gaps": result.data_gaps,
        "execution_time_ms": result.execution_time_ms,
        "tokens": {
            "prompt": result.prompt_tokens,
            "completion": result.completion_tokens,
        },
        "message": f"Document v{result.version} generated and rendered. Ready for review.",
    }


@router.post("/regenerate")
async def regenerate_documents(
    request: RegenerateDocumentRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Regenerate documents with changes.
    
    MANDATORY: regeneration_notes must be provided.
    This is used when a reviewer requests changes to the generated content.
    The regeneration_notes are stored in the audit trail.
    """
    if not request.regeneration_notes or len(request.regeneration_notes.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="Regeneration requires detailed notes (minimum 10 characters)"
        )
    
    logger.info(f"Document regeneration requested for order {request.order_id} by {current_user.get('email')}: {request.regeneration_notes[:50]}...")
    
    result = await document_orchestrator.execute_full_pipeline(
        order_id=request.order_id,
        intake_data=request.intake_data,
        regeneration=True,
        regeneration_notes=request.regeneration_notes,
    )
    
    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=result.error_message or "Regeneration failed"
        )
    
    return {
        "success": True,
        "order_id": result.order_id,
        "service_code": result.service_code,
        "version": result.version,
        "status": result.status.value,
        "is_regeneration": True,
        "structured_output": result.structured_output,
        "rendered_documents": result.rendered_documents,
        "validation_issues": result.validation_issues,
        "data_gaps": result.data_gaps,
        "execution_time_ms": result.execution_time_ms,
        "message": f"Document v{result.version} regenerated. Ready for review.",
    }


@router.post("/review")
async def review_generated_content(
    request: ReviewRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Approve or reject generated content.
    
    This is the human review gate:
    - Approved: Document marked FINAL, triggers auto-delivery
    - Rejected: MANDATORY review_notes required for regeneration
    """
    # Rejection requires notes
    if not request.approved and (not request.review_notes or len(request.review_notes.strip()) < 10):
        raise HTTPException(
            status_code=400,
            detail="Rejection requires detailed notes for regeneration (minimum 10 characters)"
        )
    
    logger.info(f"Review submitted for order {request.order_id}: approved={request.approved} by {current_user.get('email')}")
    
    success = await document_orchestrator.mark_reviewed(
        order_id=request.order_id,
        approved=request.approved,
        reviewer_id=current_user.get("email"),
        review_notes=request.review_notes,
    )
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail="No execution found for order"
        )
    
    status = "approved" if request.approved else "changes_requested"
    
    # Mark document version as FINAL if approved
    if request.approved:
        from services.template_renderer import template_renderer
        latest = await document_orchestrator.get_latest_execution(request.order_id)
        if latest and latest.get("version"):
            await template_renderer.mark_final(
                order_id=request.order_id,
                version=latest["version"],
                approved_by=current_user.get("email"),
            )
    
    return {
        "success": True,
        "order_id": request.order_id,
        "review_status": status,
        "reviewed_by": current_user.get("email"),
        "message": f"Document {status}. {'Ready for delivery.' if request.approved else 'Regeneration required.'}",
    }


@router.get("/versions/{order_id}")
async def get_document_versions(
    order_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get all document versions for an order.
    Returns full audit trail with hashes for integrity verification.
    """
    from services.template_renderer import template_renderer
    versions = await template_renderer.get_all_versions(order_id)
    
    return {
        "order_id": order_id,
        "versions": [
            {
                "version": v.get("version"),
                "status": v.get("status"),
                "is_regeneration": v.get("is_regeneration", False),
                "regeneration_notes": v.get("regeneration_notes"),
                "docx": v.get("docx"),
                "pdf": v.get("pdf"),
                "intake_snapshot_hash": v.get("intake_snapshot_hash"),
                "json_output_hash": v.get("json_output_hash"),
                "created_at": v.get("created_at"),
                "approved_at": v.get("approved_at"),
                "approved_by": v.get("approved_by"),
            }
            for v in versions
        ],
        "total": len(versions),
    }


@router.get("/versions/{order_id}/{version}")
async def get_document_version(
    order_id: str,
    version: int,
    current_user: dict = Depends(admin_route_guard),
):
    """Get a specific document version with full audit data."""
    from services.template_renderer import template_renderer
    version_data = await template_renderer.get_version(order_id, version)
    
    if not version_data:
        raise HTTPException(
            status_code=404,
            detail=f"Version {version} not found for order {order_id}"
        )
    
    return version_data


@router.get("/history/{order_id}")
async def get_generation_history(
    order_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Get the generation history for an order."""
    history = await document_orchestrator.get_execution_history(order_id)
    
    return {
        "order_id": order_id,
        "executions": history,
        "total": len(history),
    }


@router.get("/latest/{order_id}")
async def get_latest_generation(
    order_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Get the latest generation for an order."""
    execution = await document_orchestrator.get_latest_execution(order_id)
    
    if not execution:
        raise HTTPException(
            status_code=404,
            detail="No generation found for order"
        )
    
    return execution


@router.get("/validate/{service_code}")
async def validate_service_intake(
    service_code: str,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get the prompt definition and required fields for a service.
    Useful for building intake forms.
    """
    # First check service exists
    service = await service_catalogue_v2.get_service(service_code)
    if not service:
        raise HTTPException(
            status_code=404,
            detail=f"Service not found: {service_code}"
        )
    
    # Get prompt definition
    prompt_def = get_prompt_for_service(service_code)
    
    # For document packs, use orchestrator
    if not prompt_def and service_code.startswith("DOC_PACK_"):
        prompt_def = get_prompt_for_service("DOC_PACK_ORCHESTRATOR")
    
    if not prompt_def:
        return {
            "service_code": service_code,
            "has_prompt": False,
            "message": "No GPT prompt defined for this service. Uses template-only generation.",
        }
    
    return {
        "service_code": service_code,
        "has_prompt": True,
        "prompt_id": prompt_def.prompt_id,
        "prompt_name": prompt_def.name,
        "description": prompt_def.description,
        "required_fields": prompt_def.required_fields,
        "gpt_sections": prompt_def.gpt_sections,
        "temperature": prompt_def.temperature,
        "max_tokens": prompt_def.max_tokens,
    }


@router.post("/validate-data")
async def validate_intake_data_endpoint(
    service_code: str,
    intake_data: Dict[str, Any],
    current_user: dict = Depends(admin_route_guard),
):
    """
    Validate intake data against prompt requirements.
    Returns list of missing required fields.
    """
    # For document packs, use orchestrator
    check_code = service_code
    if service_code.startswith("DOC_PACK_"):
        check_code = "DOC_PACK_ORCHESTRATOR"
    
    is_valid, missing_fields = validate_intake_data(check_code, intake_data)
    
    return {
        "service_code": service_code,
        "is_valid": is_valid,
        "missing_fields": missing_fields,
        "message": "All required fields present" if is_valid else f"Missing {len(missing_fields)} required fields",
    }


@router.get("/stats")
async def get_orchestration_stats(
    current_user: dict = Depends(admin_route_guard),
):
    """Get orchestration execution statistics."""
    db = database.get_db()
    
    # Count by status
    pipeline = [
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1}
        }}
    ]
    
    status_counts = {}
    async for doc in db[document_orchestrator.COLLECTION].aggregate(pipeline):
        status_counts[doc["_id"]] = doc["count"]
    
    # Count by service
    service_pipeline = [
        {"$group": {
            "_id": "$service_code",
            "count": {"$sum": 1},
            "avg_time_ms": {"$avg": "$execution_time_ms"}
        }}
    ]
    
    service_stats = []
    async for doc in db[document_orchestrator.COLLECTION].aggregate(service_pipeline):
        service_stats.append({
            "service_code": doc["_id"],
            "count": doc["count"],
            "avg_time_ms": int(doc.get("avg_time_ms", 0) or 0),
        })
    
    # Total executions
    total = await db[document_orchestrator.COLLECTION].count_documents({})
    
    # Recent executions (last 24h)
    from datetime import timedelta
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    recent = await db[document_orchestrator.COLLECTION].count_documents({
        "created_at": {"$gte": yesterday}
    })
    
    return {
        "total_executions": total,
        "last_24h": recent,
        "by_status": status_counts,
        "by_service": service_stats,
    }
