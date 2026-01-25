"""ClearForm Document Routes

Endpoints:
- GET /api/clearform/documents/types - Get available document types
- POST /api/clearform/documents/generate - Generate a document
- GET /api/clearform/documents/vault - Get document vault
- GET /api/clearform/documents/{id} - Get document details
- GET /api/clearform/documents/{id}/download - Download document
- PUT /api/clearform/documents/{id}/tags - Update document tags
- DELETE /api/clearform/documents/{id} - Archive document
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import PlainTextResponse
from typing import Optional, List
from pydantic import BaseModel
import logging

from clearform.models.documents import (
    ClearFormDocument,
    ClearFormDocumentType,
    ClearFormDocumentStatus,
    DocumentGenerationRequest,
    DocumentVaultResponse,
    DOCUMENT_TYPE_CONFIG,
)
from clearform.services.document_service import document_service
from clearform.routes.auth import get_current_clearform_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clearform/documents", tags=["ClearForm Documents"])


class DocumentResponse(BaseModel):
    document_id: str
    document_type: str
    title: str
    status: str
    content_markdown: Optional[str] = None
    content_plain: Optional[str] = None
    credits_used: int
    created_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    tags: List[str] = []


class TagsUpdateRequest(BaseModel):
    tags: List[str]


@router.get("/types")
async def get_document_types():
    """Get available document types with configurations.
    
    No auth required - for display on landing page.
    """
    return await document_service.get_document_types()


@router.post("/generate", response_model=DocumentResponse)
async def generate_document(
    request: DocumentGenerationRequest,
    user = Depends(get_current_clearform_user),
):
    """Generate a new document.
    
    Deducts credits and starts async generation.
    Returns immediately with document ID - poll for status.
    """
    try:
        document = await document_service.create_document(
            user_id=user.user_id,
            request=request,
        )
        
        return DocumentResponse(
            document_id=document.document_id,
            document_type=document.document_type.value,
            title=document.title,
            status=document.status.value,
            content_markdown=document.content_markdown,
            content_plain=document.content_plain,
            credits_used=document.credits_used,
            created_at=document.created_at.isoformat(),
            completed_at=document.completed_at.isoformat() if document.completed_at else None,
            error_message=document.error_message,
            tags=document.tags,
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Document generation failed: {e}")
        raise HTTPException(status_code=500, detail="Document generation failed")


@router.get("/vault", response_model=DocumentVaultResponse)
async def get_vault(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    user = Depends(get_current_clearform_user),
):
    """Get user's document vault with filters."""
    try:
        doc_type = None
        if document_type:
            try:
                doc_type = ClearFormDocumentType(document_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid document type: {document_type}")
        
        doc_status = None
        if status:
            try:
                doc_status = ClearFormDocumentStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        
        return await document_service.get_vault(
            user_id=user.user_id,
            page=page,
            page_size=page_size,
            document_type=doc_type,
            status=doc_status,
            search=search,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get vault: {e}")
        raise HTTPException(status_code=500, detail="Failed to get vault")


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    user = Depends(get_current_clearform_user),
):
    """Get document details."""
    try:
        document = await document_service.get_document(user.user_id, document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return DocumentResponse(
            document_id=document.document_id,
            document_type=document.document_type.value,
            title=document.title,
            status=document.status.value,
            content_markdown=document.content_markdown,
            content_plain=document.content_plain,
            credits_used=document.credits_used,
            created_at=document.created_at.isoformat(),
            completed_at=document.completed_at.isoformat() if document.completed_at else None,
            error_message=document.error_message,
            tags=document.tags,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(status_code=500, detail="Failed to get document")


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    format: str = Query("markdown", enum=["markdown", "plain", "pdf"]),
    user = Depends(get_current_clearform_user),
):
    """Download document in specified format."""
    try:
        document = await document_service.get_document(user.user_id, document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if document.status != ClearFormDocumentStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="Document not ready for download")
        
        if format == "markdown":
            return PlainTextResponse(
                content=document.content_markdown or "",
                media_type="text/markdown",
                headers={
                    "Content-Disposition": f'attachment; filename="{document.title}.md"'
                }
            )
        elif format == "plain":
            return PlainTextResponse(
                content=document.content_plain or "",
                media_type="text/plain",
                headers={
                    "Content-Disposition": f'attachment; filename="{document.title}.txt"'
                }
            )
        elif format == "pdf":
            # PDF generation would require additional library (reportlab)
            # For MVP, return markdown with note
            raise HTTPException(
                status_code=501, 
                detail="PDF export coming soon. Please use markdown or plain text format."
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download document: {e}")
        raise HTTPException(status_code=500, detail="Failed to download document")


@router.put("/{document_id}/tags")
async def update_tags(
    document_id: str,
    request: TagsUpdateRequest,
    user = Depends(get_current_clearform_user),
):
    """Update document tags."""
    try:
        success = await document_service.update_tags(
            user_id=user.user_id,
            document_id=document_id,
            tags=request.tags,
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"message": "Tags updated", "tags": request.tags}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update tags: {e}")
        raise HTTPException(status_code=500, detail="Failed to update tags")


@router.delete("/{document_id}")
async def archive_document(
    document_id: str,
    user = Depends(get_current_clearform_user),
):
    """Archive a document (soft delete)."""
    try:
        success = await document_service.archive_document(
            user_id=user.user_id,
            document_id=document_id,
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"message": "Document archived"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to archive document: {e}")
        raise HTTPException(status_code=500, detail="Failed to archive document")
