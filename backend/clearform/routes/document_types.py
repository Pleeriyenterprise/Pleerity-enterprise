"""ClearForm Document Types & Templates Routes

Endpoints for:
- Document type listing (public)
- Document type admin management
- User templates CRUD
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import logging

from clearform.routes.auth import get_current_clearform_user
from clearform.services.document_type_service import document_type_service
from clearform.models.document_types import DocumentTypeConfig, DocumentCategory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clearform/document-types", tags=["ClearForm Document Types"])
templates_router = APIRouter(prefix="/api/clearform/templates", tags=["ClearForm Templates"])


# ============================================================================
# Document Types (Public + Admin)
# ============================================================================

@router.get("")
async def get_document_types(
    category: Optional[str] = None,
    active_only: bool = True,
):
    """Get all document types.
    
    Public endpoint - no auth required.
    Returns types grouped by category with full field definitions.
    """
    try:
        if category:
            try:
                cat = DocumentCategory(category)
                types = await document_type_service.get_types_by_category(cat, active_only)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
        else:
            types = await document_type_service.get_all_types(active_only)
        
        return {"types": types, "total": len(types)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document types: {e}")
        raise HTTPException(status_code=500, detail="Failed to get document types")


@router.get("/categories")
async def get_categories():
    """Get all document categories."""
    try:
        categories = await document_type_service.get_all_categories()
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Failed to get categories: {e}")
        raise HTTPException(status_code=500, detail="Failed to get categories")


@router.get("/{code}")
async def get_document_type(code: str):
    """Get a specific document type by code."""
    try:
        doc_type = await document_type_service.get_type_by_code(code)
        if not doc_type:
            raise HTTPException(status_code=404, detail="Document type not found")
        return doc_type
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document type: {e}")
        raise HTTPException(status_code=500, detail="Failed to get document type")


# ============================================================================
# Document Types Admin Management
# ============================================================================

class CreateDocumentTypeRequest(BaseModel):
    code: str
    name: str
    category: str
    description: str
    credit_cost: int = 1
    icon: str = "file-text"
    required_fields: List[Dict[str, Any]] = []
    optional_fields: List[Dict[str, Any]] = []
    examples: List[str] = []
    system_prompt: Optional[str] = None
    is_featured: bool = False


class UpdateDocumentTypeRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    credit_cost: Optional[int] = None
    icon: Optional[str] = None
    required_fields: Optional[List[Dict[str, Any]]] = None
    optional_fields: Optional[List[Dict[str, Any]]] = None
    examples: Optional[List[str]] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    display_order: Optional[int] = None


@router.post("/admin/create")
async def admin_create_document_type(
    request: CreateDocumentTypeRequest,
    user = Depends(get_current_clearform_user),
):
    """Create a new document type (admin only).
    
    Note: In production, add admin role check.
    """
    try:
        # Validate category
        try:
            category = DocumentCategory(request.category)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category: {request.category}")
        
        from clearform.models.document_types import DocumentTypeField
        
        config = DocumentTypeConfig(
            code=request.code,
            name=request.name,
            category=category,
            description=request.description,
            credit_cost=request.credit_cost,
            icon=request.icon,
            required_fields=[DocumentTypeField(**f) for f in request.required_fields],
            optional_fields=[DocumentTypeField(**f) for f in request.optional_fields],
            examples=request.examples,
            system_prompt=request.system_prompt,
            is_featured=request.is_featured,
        )
        
        result = await document_type_service.create_type(config, user.user_id)
        
        return {"message": "Document type created", "type": result.model_dump()}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create document type: {e}")
        raise HTTPException(status_code=500, detail="Failed to create document type")


@router.put("/admin/{code}")
async def admin_update_document_type(
    code: str,
    request: UpdateDocumentTypeRequest,
    user = Depends(get_current_clearform_user),
):
    """Update a document type (admin only)."""
    try:
        updates = request.model_dump(exclude_none=True)
        
        # Convert fields if present
        if "required_fields" in updates:
            from clearform.models.document_types import DocumentTypeField
            updates["required_fields"] = [DocumentTypeField(**f).model_dump() for f in updates["required_fields"]]
        if "optional_fields" in updates:
            from clearform.models.document_types import DocumentTypeField
            updates["optional_fields"] = [DocumentTypeField(**f).model_dump() for f in updates["optional_fields"]]
        
        result = await document_type_service.update_type(code, updates, user.user_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Document type not found")
        
        return {"message": "Document type updated", "type": result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update document type: {e}")
        raise HTTPException(status_code=500, detail="Failed to update document type")


@router.post("/admin/{code}/toggle")
async def admin_toggle_document_type(
    code: str,
    is_active: bool,
    user = Depends(get_current_clearform_user),
):
    """Enable/disable a document type (admin only)."""
    try:
        success = await document_type_service.toggle_type_active(code, is_active, user.user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document type not found")
        return {"message": f"Document type {'enabled' if is_active else 'disabled'}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle document type: {e}")
        raise HTTPException(status_code=500, detail="Failed to toggle document type")


@router.post("/admin/initialize")
async def admin_initialize_defaults(user = Depends(get_current_clearform_user)):
    """Initialize default document types and categories."""
    try:
        result = await document_type_service.initialize_defaults()
        return {"message": "Defaults initialized", **result}
    except Exception as e:
        logger.error(f"Failed to initialize defaults: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize defaults")


# ============================================================================
# User Templates
# ============================================================================

class CreateTemplateRequest(BaseModel):
    name: str
    document_type_code: str
    saved_fields: Dict[str, Any]
    saved_intent: Optional[str] = None
    description: Optional[str] = None
    workspace_id: Optional[str] = None


class UpdateTemplateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    saved_fields: Optional[Dict[str, Any]] = None
    saved_intent: Optional[str] = None
    tags: Optional[List[str]] = None


@templates_router.get("")
async def get_templates(
    workspace_id: Optional[str] = None,
    document_type_code: Optional[str] = None,
    user = Depends(get_current_clearform_user),
):
    """Get user's saved templates."""
    try:
        templates = await document_type_service.get_user_templates(
            user_id=user.user_id,
            workspace_id=workspace_id,
            document_type_code=document_type_code,
        )
        return {"templates": templates, "total": len(templates)}
    except Exception as e:
        logger.error(f"Failed to get templates: {e}")
        raise HTTPException(status_code=500, detail="Failed to get templates")


@templates_router.post("")
async def create_template(
    request: CreateTemplateRequest,
    user = Depends(get_current_clearform_user),
):
    """Create a new template."""
    try:
        template = await document_type_service.create_template(
            user_id=user.user_id,
            name=request.name,
            document_type_code=request.document_type_code,
            saved_fields=request.saved_fields,
            saved_intent=request.saved_intent,
            description=request.description,
            workspace_id=request.workspace_id,
        )
        return {"message": "Template created", "template": template.model_dump()}
    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        raise HTTPException(status_code=500, detail="Failed to create template")


@templates_router.get("/{template_id}")
async def get_template(
    template_id: str,
    user = Depends(get_current_clearform_user),
):
    """Get a specific template."""
    try:
        template = await document_type_service.get_template(user.user_id, template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return template
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get template: {e}")
        raise HTTPException(status_code=500, detail="Failed to get template")


@templates_router.put("/{template_id}")
async def update_template(
    template_id: str,
    request: UpdateTemplateRequest,
    user = Depends(get_current_clearform_user),
):
    """Update a template."""
    try:
        updates = request.model_dump(exclude_none=True)
        result = await document_type_service.update_template(user.user_id, template_id, updates)
        if not result:
            raise HTTPException(status_code=404, detail="Template not found")
        return {"message": "Template updated", "template": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update template: {e}")
        raise HTTPException(status_code=500, detail="Failed to update template")


@templates_router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    user = Depends(get_current_clearform_user),
):
    """Delete a template."""
    try:
        success = await document_type_service.delete_template(user.user_id, template_id)
        if not success:
            raise HTTPException(status_code=404, detail="Template not found")
        return {"message": "Template deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete template: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete template")


@templates_router.post("/{template_id}/use")
async def use_template(
    template_id: str,
    user = Depends(get_current_clearform_user),
):
    """Mark template as used (for usage tracking)."""
    try:
        template = await document_type_service.use_template(user.user_id, template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return {"message": "Template used", "template": template}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to use template: {e}")
        raise HTTPException(status_code=500, detail="Failed to use template")


@templates_router.post("/{template_id}/favorite")
async def toggle_template_favorite(
    template_id: str,
    user = Depends(get_current_clearform_user),
):
    """Toggle template favorite status."""
    try:
        template = await document_type_service.toggle_favorite(user.user_id, template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return {"message": f"Template {'favorited' if template['is_favorite'] else 'unfavorited'}", "template": template}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle favorite: {e}")
        raise HTTPException(status_code=500, detail="Failed to toggle favorite")
