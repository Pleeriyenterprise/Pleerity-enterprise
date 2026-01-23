"""
CMS API Routes for Admin Site Builder
All routes require ROLE_ADMIN
"""
import os
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from pydantic import BaseModel, Field

from auth import get_current_admin
from models.cms import (
    BlockType, PageStatus, MediaType,
    CMSPageCreate, CMSPageUpdate, CMSPageResponse,
    CMSRevisionResponse, CMSMediaResponse,
    BlockCreateRequest, BlockUpdateRequest, ReorderBlocksRequest,
    PublishPageRequest, RollbackRequest, ContentBlock
)
from services import cms_service
from services.storage_adapter import upload_file_to_storage

router = APIRouter(prefix="/cms", tags=["CMS"])


# ============================================
# Page Management Routes
# ============================================

class PageListResponse(BaseModel):
    pages: List[CMSPageResponse]
    total: int
    limit: int
    offset: int


@router.get("/pages", response_model=PageListResponse)
async def list_pages(
    status: Optional[PageStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    admin = Depends(get_current_admin)
):
    """List all CMS pages (Admin only)"""
    pages, total = await cms_service.list_pages(status=status, limit=limit, offset=offset)
    return PageListResponse(pages=pages, total=total, limit=limit, offset=offset)


@router.post("/pages", response_model=CMSPageResponse, status_code=201)
async def create_page(
    data: CMSPageCreate,
    admin = Depends(get_current_admin)
):
    """Create a new CMS page (Admin only)"""
    try:
        page = await cms_service.create_page(
            slug=data.slug,
            title=data.title,
            description=data.description,
            admin_id=admin["user_id"],
            admin_email=admin["email"]
        )
        return page
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pages/{page_id}", response_model=CMSPageResponse)
async def get_page(
    page_id: str,
    admin = Depends(get_current_admin)
):
    """Get a CMS page by ID (Admin only)"""
    page = await cms_service.get_page(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.put("/pages/{page_id}", response_model=CMSPageResponse)
async def update_page(
    page_id: str,
    data: CMSPageUpdate,
    admin = Depends(get_current_admin)
):
    """Update a CMS page (Admin only)"""
    try:
        page = await cms_service.update_page(
            page_id=page_id,
            title=data.title,
            description=data.description,
            blocks=[b.dict() for b in data.blocks] if data.blocks else None,
            seo=data.seo.dict() if data.seo else None,
            admin_id=admin["user_id"],
            admin_email=admin["email"]
        )
        return page
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/pages/{page_id}")
async def delete_page(
    page_id: str,
    admin = Depends(get_current_admin)
):
    """Archive a CMS page (Admin only)"""
    success = await cms_service.delete_page(
        page_id=page_id,
        admin_id=admin["user_id"],
        admin_email=admin["email"]
    )
    if not success:
        raise HTTPException(status_code=404, detail="Page not found")
    return {"success": True, "message": "Page archived"}


# ============================================
# Block Management Routes
# ============================================

@router.post("/pages/{page_id}/blocks", response_model=ContentBlock, status_code=201)
async def add_block(
    page_id: str,
    data: BlockCreateRequest,
    admin = Depends(get_current_admin)
):
    """Add a block to a page (Admin only)"""
    try:
        block = await cms_service.add_block(
            page_id=page_id,
            block_type=data.block_type,
            content=data.content,
            position=data.position,
            admin_id=admin["user_id"],
            admin_email=admin["email"]
        )
        return block
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/pages/{page_id}/blocks/{block_id}", response_model=ContentBlock)
async def update_block(
    page_id: str,
    block_id: str,
    data: BlockUpdateRequest,
    admin = Depends(get_current_admin)
):
    """Update a block (Admin only)"""
    try:
        block = await cms_service.update_block(
            page_id=page_id,
            block_id=block_id,
            content=data.content,
            visible=data.visible,
            admin_id=admin["user_id"],
            admin_email=admin["email"]
        )
        return block
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/pages/{page_id}/blocks/{block_id}")
async def delete_block(
    page_id: str,
    block_id: str,
    admin = Depends(get_current_admin)
):
    """Delete a block (Admin only)"""
    try:
        success = await cms_service.delete_block(
            page_id=page_id,
            block_id=block_id,
            admin_id=admin["user_id"],
            admin_email=admin["email"]
        )
        if not success:
            raise HTTPException(status_code=404, detail="Block not found")
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/pages/{page_id}/blocks/reorder", response_model=List[ContentBlock])
async def reorder_blocks(
    page_id: str,
    data: ReorderBlocksRequest,
    admin = Depends(get_current_admin)
):
    """Reorder blocks on a page (Admin only)"""
    try:
        blocks = await cms_service.reorder_blocks(
            page_id=page_id,
            block_order=data.block_order,
            admin_id=admin["user_id"],
            admin_email=admin["email"]
        )
        return blocks
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# Publishing & Revision Routes
# ============================================

@router.post("/pages/{page_id}/publish", response_model=CMSPageResponse)
async def publish_page(
    page_id: str,
    data: PublishPageRequest = PublishPageRequest(),
    admin = Depends(get_current_admin)
):
    """Publish a page (Admin only)"""
    try:
        page = await cms_service.publish_page(
            page_id=page_id,
            notes=data.notes,
            admin_id=admin["user_id"],
            admin_email=admin["email"]
        )
        return page
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class RevisionListResponse(BaseModel):
    revisions: List[CMSRevisionResponse]


@router.get("/pages/{page_id}/revisions", response_model=RevisionListResponse)
async def get_revisions(
    page_id: str,
    limit: int = Query(20, ge=1, le=50),
    admin = Depends(get_current_admin)
):
    """Get revision history for a page (Admin only)"""
    revisions = await cms_service.get_revisions(page_id=page_id, limit=limit)
    return RevisionListResponse(revisions=revisions)


@router.get("/revisions/{revision_id}", response_model=CMSRevisionResponse)
async def get_revision(
    revision_id: str,
    admin = Depends(get_current_admin)
):
    """Get a specific revision (Admin only)"""
    revision = await cms_service.get_revision(revision_id)
    if not revision:
        raise HTTPException(status_code=404, detail="Revision not found")
    return revision


@router.post("/pages/{page_id}/rollback", response_model=CMSPageResponse)
async def rollback_page(
    page_id: str,
    data: RollbackRequest,
    admin = Depends(get_current_admin)
):
    """Rollback page to a previous revision (Admin only)"""
    try:
        page = await cms_service.rollback_page(
            page_id=page_id,
            revision_id=data.revision_id,
            notes=data.notes,
            admin_id=admin["user_id"],
            admin_email=admin["email"]
        )
        return page
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# Media Library Routes
# ============================================

class MediaListResponse(BaseModel):
    media: List[CMSMediaResponse]
    total: int
    limit: int
    offset: int


@router.get("/media", response_model=MediaListResponse)
async def list_media(
    media_type: Optional[MediaType] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    admin = Depends(get_current_admin)
):
    """List media library items (Admin only)"""
    items, total = await cms_service.list_media(
        media_type=media_type,
        search=search,
        limit=limit,
        offset=offset
    )
    return MediaListResponse(media=items, total=total, limit=limit, offset=offset)


@router.post("/media/upload", response_model=CMSMediaResponse, status_code=201)
async def upload_media(
    file: UploadFile = File(...),
    alt_text: Optional[str] = None,
    tags: str = "",  # Comma-separated tags
    admin = Depends(get_current_admin)
):
    """Upload a media file (Admin only)"""
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/gif", "image/svg+xml"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )
    
    # Size limit: 10MB
    max_size = 10 * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail="File too large. Max 10MB")
    
    # Upload to storage
    try:
        file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        unique_name = f"cms/{uuid.uuid4().hex}.{file_ext}"
        file_url = await upload_file_to_storage(content, unique_name, file.content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    # Parse tags
    tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
    
    # Record in database
    media = await cms_service.upload_media(
        file_name=file.filename,
        file_url=file_url,
        file_type=file.content_type,
        file_size=len(content),
        alt_text=alt_text,
        tags=tag_list,
        admin_id=admin["user_id"],
        admin_email=admin["email"]
    )
    
    return media


@router.get("/media/{media_id}", response_model=CMSMediaResponse)
async def get_media(
    media_id: str,
    admin = Depends(get_current_admin)
):
    """Get a media item (Admin only)"""
    media = await cms_service.get_media(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    return media


@router.delete("/media/{media_id}")
async def delete_media(
    media_id: str,
    admin = Depends(get_current_admin)
):
    """Delete a media item (Admin only)"""
    success = await cms_service.delete_media(
        media_id=media_id,
        admin_id=admin["user_id"],
        admin_email=admin["email"]
    )
    if not success:
        raise HTTPException(status_code=404, detail="Media not found")
    return {"success": True}


# ============================================
# Block Type Reference
# ============================================

@router.get("/block-types")
async def get_block_types(admin = Depends(get_current_admin)):
    """Get available block types with their schemas (Admin only)"""
    from models.cms import BLOCK_CONTENT_SCHEMAS
    
    block_types = []
    for bt in BlockType:
        schema_class = BLOCK_CONTENT_SCHEMAS.get(bt)
        schema_fields = {}
        if schema_class:
            for field_name, field_info in schema_class.model_fields.items():
                schema_fields[field_name] = {
                    "type": str(field_info.annotation),
                    "required": field_info.is_required(),
                    "description": field_info.description,
                }
        
        block_types.append({
            "type": bt.value,
            "label": bt.value.replace("_", " ").title(),
            "schema": schema_fields,
        })
    
    return {"block_types": block_types}


# ============================================
# Public Page Rendering Route (No Auth)
# ============================================

public_router = APIRouter(prefix="/public/cms", tags=["Public CMS"])


class PublicPageResponse(BaseModel):
    slug: str
    title: str
    description: Optional[str]
    blocks: list
    seo: Optional[dict]


@public_router.get("/pages/{slug}", response_model=PublicPageResponse)
async def get_public_page(slug: str):
    """Get published page content for public rendering"""
    page = await cms_service.get_published_page(slug)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return page
