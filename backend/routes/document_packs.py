"""
Document Pack Orchestrator API Routes

Admin endpoints for managing document pack generation, review, and delivery.
Implements the orchestration flow:
1. Create document items from order
2. Generate documents in canonical order
3. Review and approve/reject individual documents
4. Regenerate as needed
5. Deliver bundle

Access restricted to Admin roles.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime, timezone

from middleware import admin_route_guard
from services.document_pack_orchestrator import (
    document_pack_orchestrator,
    PackTier,
    DOCUMENT_REGISTRY,
    CANONICAL_ORDER,
)
from database import database
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/document-packs", tags=["document-pack-orchestrator"])


# ============================================
# Request/Response Models
# ============================================

class CreateDocumentItemsRequest(BaseModel):
    """Request to create document items for an order."""
    order_id: str = Field(..., description="Parent order ID")
    service_code: str = Field(..., description="Pack service code (DOC_PACK_ESSENTIAL, DOC_PACK_PLUS, DOC_PACK_PRO)")
    selected_docs: List[str] = Field(..., description="List of doc_keys selected by client")
    input_data: dict = Field(..., description="Intake data for generation")


class GenerateDocumentRequest(BaseModel):
    """Request to generate a single document."""
    input_data: dict = Field(..., description="Input data for generation")


class GenerateAllDocumentsRequest(BaseModel):
    """Request to generate all pending documents for an order."""
    input_data: dict = Field(..., description="Input data for generation")


class RegenerateDocumentRequest(BaseModel):
    """Request to regenerate a document."""
    input_data: dict = Field(..., description="Input data for regeneration")
    regen_reason: str = Field(..., min_length=5, max_length=500, description="Reason for regeneration (required)")
    regen_notes: Optional[str] = Field(None, max_length=1000, description="Optional notes")


class ApproveDocumentRequest(BaseModel):
    """Request to approve a document."""
    pass  # No additional data needed


class RejectDocumentRequest(BaseModel):
    """Request to reject a document."""
    rejection_reason: str = Field(..., min_length=5, max_length=500, description="Reason for rejection")


# ============================================
# Registry & Pack Info Endpoints
# ============================================

@router.get("/registry")
async def get_document_registry(
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get the full document registry.
    
    Returns all document types with their doc_keys, pack tiers, and output schemas.
    """
    return {
        "registry": document_pack_orchestrator.get_registry(),
        "total_documents": len(DOCUMENT_REGISTRY),
    }


@router.get("/canonical-order")
async def get_canonical_order(
    pack_tier: Optional[str] = Query(None, description="Filter by pack tier (ESSENTIAL, PLUS, PRO)"),
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get canonical order lists for pack tiers.
    """
    if pack_tier:
        try:
            tier = PackTier(pack_tier)
            order = CANONICAL_ORDER.get(tier, [])
            return {
                "pack_tier": pack_tier,
                "canonical_order": order,
                "total": len(order),
            }
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid pack tier: {pack_tier}")
    
    # Return all
    return {
        "canonical_orders": {
            tier.value: order for tier, order in CANONICAL_ORDER.items()
        }
    }


@router.get("/pack-info/{service_code}")
async def get_pack_info(
    service_code: str,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get information about a pack including allowed documents.
    
    Shows pack tier, inheritance, and all available documents in canonical order.
    """
    try:
        return document_pack_orchestrator.get_pack_info(service_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# Document Item Management
# ============================================

@router.post("/items")
async def create_document_items(
    request: CreateDocumentItemsRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Create document items for an order.
    
    Applies entitlement and selection filters, then creates items in canonical order.
    """
    try:
        items = await document_pack_orchestrator.create_document_items(
            order_id=request.order_id,
            service_code=request.service_code,
            selected_docs=request.selected_docs,
            input_data=request.input_data,
        )
        
        return {
            "success": True,
            "order_id": request.order_id,
            "service_code": request.service_code,
            "items_created": len(items),
            "items": [item.to_dict() for item in items],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/items/order/{order_id}")
async def get_document_items_for_order(
    order_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get all document items for an order, sorted by canonical order.
    """
    items = await document_pack_orchestrator.get_document_items(order_id)
    
    # Calculate stats
    status_counts = {}
    for item in items:
        status = item.get("status", "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1
    
    return {
        "order_id": order_id,
        "total_items": len(items),
        "status_summary": status_counts,
        "items": items,
    }


@router.get("/items/{item_id}")
async def get_document_item(
    item_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get a single document item by ID.
    """
    item = await document_pack_orchestrator.get_document_item(item_id)
    
    if not item:
        raise HTTPException(status_code=404, detail="Document item not found")
    
    return item


# ============================================
# Generation Endpoints
# ============================================

@router.post("/items/{item_id}/generate")
async def generate_document(
    item_id: str,
    request: GenerateDocumentRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Generate a single document.
    
    Uses the Prompt Manager to generate content based on the active prompt template.
    """
    try:
        result = await document_pack_orchestrator.generate_document(
            item_id=item_id,
            input_data=request.input_data,
            generated_by=current_user.get("email", "admin"),
        )
        
        return {
            "success": True,
            "item": result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.post("/order/{order_id}/generate-all")
async def generate_all_documents(
    order_id: str,
    request: GenerateAllDocumentsRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Generate all pending documents for an order in canonical order.
    """
    try:
        results = await document_pack_orchestrator.generate_all_documents(
            order_id=order_id,
            input_data=request.input_data,
            generated_by=current_user.get("email", "admin"),
        )
        
        # Calculate success/failure counts
        success_count = sum(1 for r in results if r.get("status") == "COMPLETED")
        failed_count = sum(1 for r in results if r.get("status") == "FAILED")
        
        return {
            "success": True,
            "order_id": order_id,
            "total_generated": len(results),
            "successful": success_count,
            "failed": failed_count,
            "items": results,
        }
    except Exception as e:
        logger.error(f"Batch generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


# ============================================
# Regeneration Endpoint
# ============================================

@router.post("/items/{item_id}/regenerate")
async def regenerate_document(
    item_id: str,
    request: RegenerateDocumentRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Regenerate a document, creating a new version.
    
    Requires a reason for audit trail. Previous versions are preserved.
    """
    try:
        result = await document_pack_orchestrator.regenerate_document(
            item_id=item_id,
            input_data=request.input_data,
            regen_reason=request.regen_reason,
            regen_notes=request.regen_notes,
            regenerated_by=current_user.get("email", "admin"),
        )
        
        return {
            "success": True,
            "message": f"Document regenerated to version {result.get('version')}",
            "item": result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Regeneration failed: {e}")
        raise HTTPException(status_code=500, detail=f"Regeneration failed: {str(e)}")


# ============================================
# Review & Approval Endpoints
# ============================================

@router.post("/items/{item_id}/approve")
async def approve_document(
    item_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Approve a completed document.
    
    Only documents in COMPLETED status can be approved.
    """
    try:
        result = await document_pack_orchestrator.approve_document(
            item_id=item_id,
            approved_by=current_user.get("email", "admin"),
        )
        
        return {
            "success": True,
            "message": "Document approved",
            "item": result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/items/{item_id}/reject")
async def reject_document(
    item_id: str,
    request: RejectDocumentRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Reject a document, requiring regeneration.
    """
    try:
        result = await document_pack_orchestrator.reject_document(
            item_id=item_id,
            rejection_reason=request.rejection_reason,
            rejected_by=current_user.get("email", "admin"),
        )
        
        return {
            "success": True,
            "message": "Document rejected",
            "item": result,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# Delivery Bundle Endpoint
# ============================================

@router.get("/order/{order_id}/bundle")
async def get_delivery_bundle(
    order_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get the delivery bundle for an order.
    
    Returns all approved documents in canonical order, ready for delivery.
    """
    items = await document_pack_orchestrator.get_document_items(order_id)
    
    # Filter to approved items only
    approved_items = [
        item for item in items
        if item.get("status") == "APPROVED"
    ]
    
    # Check if all items are ready
    all_items_count = len(items)
    approved_count = len(approved_items)
    pending_count = sum(1 for item in items if item.get("status") in ["PENDING", "GENERATING"])
    
    bundle_ready = approved_count == all_items_count and all_items_count > 0
    
    return {
        "order_id": order_id,
        "bundle_ready": bundle_ready,
        "total_documents": all_items_count,
        "approved_documents": approved_count,
        "pending_documents": pending_count,
        "bundle": [
            {
                "item_id": item["item_id"],
                "doc_key": item["doc_key"],
                "display_name": item["display_name"],
                "canonical_index": item["canonical_index"],
                "version": item["version"],
                "files": item.get("files", []),
                "generated_output": item.get("generated_output"),
            }
            for item in approved_items
        ],
    }


# ============================================
# Statistics Endpoint
# ============================================

@router.get("/stats")
async def get_document_pack_stats(
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get document pack orchestration statistics.
    """
    db = database.get_db()
    
    # Count by status
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    status_cursor = db.document_pack_items.aggregate(pipeline)
    status_results = await status_cursor.to_list(length=20)
    status_counts = {r["_id"]: r["count"] for r in status_results}
    
    # Count by doc_type
    pipeline = [
        {"$group": {"_id": "$doc_type", "count": {"$sum": 1}}}
    ]
    type_cursor = db.document_pack_items.aggregate(pipeline)
    type_results = await type_cursor.to_list(length=50)
    type_counts = {r["_id"]: r["count"] for r in type_results}
    
    # Total items
    total = await db.document_pack_items.count_documents({})
    
    # Recent regenerations
    regen_count = await db.document_pack_items.count_documents({
        "regenerated_from_version": {"$exists": True, "$ne": None}
    })
    
    return {
        "total_document_items": total,
        "by_status": status_counts,
        "by_doc_type": type_counts,
        "regenerations": regen_count,
        "registry_size": len(DOCUMENT_REGISTRY),
    }
