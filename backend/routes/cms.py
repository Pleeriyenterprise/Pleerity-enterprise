"""
CMS API Routes for Admin Site Builder
All routes require ROLE_ADMIN
"""
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from pydantic import BaseModel, Field

from middleware import admin_route_guard
from models.cms import (
    BlockType, PageStatus, MediaType,
    CMSPageCreate, CMSPageUpdate, CMSPageResponse,
    CMSRevisionResponse, CMSMediaResponse,
    BlockCreateRequest, BlockUpdateRequest, ReorderBlocksRequest,
    PublishPageRequest, RollbackRequest, ContentBlock
)
from services import cms_service
from services.storage_adapter import upload_file_to_storage

router = APIRouter(prefix="/api/admin/cms", tags=["CMS"])


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
    admin: dict = Depends(admin_route_guard)
):
    """List all CMS pages (Admin only)"""
    pages, total = await cms_service.list_pages(status=status, limit=limit, offset=offset)
    return PageListResponse(pages=pages, total=total, limit=limit, offset=offset)


@router.post("/pages", response_model=CMSPageResponse, status_code=201)
async def create_page(
    data: CMSPageCreate,
    admin: dict = Depends(admin_route_guard)
):
    """Create a new CMS page (Admin only)"""
    try:
        page = await cms_service.create_page(
            slug=data.slug,
            title=data.title,
            description=data.description,
            admin_id=admin["portal_user_id"],
            admin_email=admin["email"]
        )
        return page
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pages/{page_id}", response_model=CMSPageResponse)
async def get_page(
    page_id: str,
    admin: dict = Depends(admin_route_guard)
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
    admin: dict = Depends(admin_route_guard)
):
    """Update a CMS page (Admin only)"""
    try:
        page = await cms_service.update_page(
            page_id=page_id,
            title=data.title,
            description=data.description,
            blocks=[b.dict() for b in data.blocks] if data.blocks else None,
            seo=data.seo.dict() if data.seo else None,
            admin_id=admin["portal_user_id"],
            admin_email=admin["email"]
        )
        return page
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/pages/{page_id}")
async def delete_page(
    page_id: str,
    admin: dict = Depends(admin_route_guard)
):
    """Archive a CMS page (Admin only)"""
    success = await cms_service.delete_page(
        page_id=page_id,
        admin_id=admin["portal_user_id"],
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
    admin: dict = Depends(admin_route_guard)
):
    """Add a block to a page (Admin only)"""
    try:
        block = await cms_service.add_block(
            page_id=page_id,
            block_type=data.block_type,
            content=data.content,
            position=data.position,
            admin_id=admin["portal_user_id"],
            admin_email=admin["email"]
        )
        return block
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# NOTE: Reorder route MUST be defined BEFORE {block_id} routes to avoid path conflict
@router.put("/pages/{page_id}/blocks/reorder", response_model=List[ContentBlock])
async def reorder_blocks(
    page_id: str,
    data: ReorderBlocksRequest,
    admin: dict = Depends(admin_route_guard)
):
    """Reorder blocks on a page (Admin only)"""
    try:
        blocks = await cms_service.reorder_blocks(
            page_id=page_id,
            block_order=data.block_order,
            admin_id=admin["portal_user_id"],
            admin_email=admin["email"]
        )
        return blocks
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/pages/{page_id}/blocks/{block_id}", response_model=ContentBlock)
async def update_block(
    page_id: str,
    block_id: str,
    data: BlockUpdateRequest,
    admin: dict = Depends(admin_route_guard)
):
    """Update a block (Admin only)"""
    try:
        block = await cms_service.update_block(
            page_id=page_id,
            block_id=block_id,
            content=data.content,
            visible=data.visible,
            admin_id=admin["portal_user_id"],
            admin_email=admin["email"]
        )
        return block
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/pages/{page_id}/blocks/{block_id}")
async def delete_block(
    page_id: str,
    block_id: str,
    admin: dict = Depends(admin_route_guard)
):
    """Delete a block (Admin only)"""
    try:
        success = await cms_service.delete_block(
            page_id=page_id,
            block_id=block_id,
            admin_id=admin["portal_user_id"],
            admin_email=admin["email"]
        )
        if not success:
            raise HTTPException(status_code=404, detail="Block not found")
        return {"success": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# Publishing & Revision Routes
# ============================================

@router.post("/pages/{page_id}/publish", response_model=CMSPageResponse)
async def publish_page(
    page_id: str,
    data: PublishPageRequest = PublishPageRequest(),
    admin: dict = Depends(admin_route_guard)
):
    """Publish a page (Admin only)"""
    try:
        page = await cms_service.publish_page(
            page_id=page_id,
            notes=data.notes,
            admin_id=admin["portal_user_id"],
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
    admin: dict = Depends(admin_route_guard)
):
    """Get revision history for a page (Admin only)"""
    revisions = await cms_service.get_revisions(page_id=page_id, limit=limit)
    return RevisionListResponse(revisions=revisions)


@router.get("/revisions/{revision_id}", response_model=CMSRevisionResponse)
async def get_revision(
    revision_id: str,
    admin: dict = Depends(admin_route_guard)
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
    admin: dict = Depends(admin_route_guard)
):
    """Rollback page to a previous revision (Admin only)"""
    try:
        page = await cms_service.rollback_page(
            page_id=page_id,
            revision_id=data.revision_id,
            notes=data.notes,
            admin_id=admin["portal_user_id"],
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
    admin: dict = Depends(admin_route_guard)
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
    admin: dict = Depends(admin_route_guard)
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
        admin_id=admin["portal_user_id"],
        admin_email=admin["email"]
    )
    
    return media


@router.get("/media/{media_id}", response_model=CMSMediaResponse)
async def get_media(
    media_id: str,
    admin: dict = Depends(admin_route_guard)
):
    """Get a media item (Admin only)"""
    media = await cms_service.get_media(media_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    return media


@router.delete("/media/{media_id}")
async def delete_media(
    media_id: str,
    admin: dict = Depends(admin_route_guard)
):
    """Delete a media item (Admin only)"""
    success = await cms_service.delete_media(
        media_id=media_id,
        admin_id=admin["portal_user_id"],
        admin_email=admin["email"]
    )
    if not success:
        raise HTTPException(status_code=404, detail="Media not found")
    return {"success": True}


# ============================================
# Block Type Reference
# ============================================

@router.get("/block-types")
async def get_block_types(admin: dict = Depends(admin_route_guard)):
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
# Page Templates
# ============================================

from services.cms_templates import get_all_templates, get_template, CMS_TEMPLATES


@router.get("/templates")
async def list_templates(admin: dict = Depends(admin_route_guard)):
    """List all available page templates"""
    return {"templates": get_all_templates()}


@router.get("/templates/{template_id}")
async def get_template_detail(template_id: str, admin: dict = Depends(admin_route_guard)):
    """Get a specific template with full block definitions"""
    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return {
        "template_id": template_id,
        **template
    }


@router.get("/templates/{template_id}/preview")
async def preview_template(template_id: str, admin: dict = Depends(admin_route_guard)):
    """Get template preview data for rendering in UI"""
    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Return blocks formatted for preview
    preview_blocks = []
    for idx, block in enumerate(template["blocks"]):
        preview_blocks.append({
            "block_id": f"preview-{idx}",
            "block_type": block["block_type"],
            "content": block["content"],
            "visible": block.get("visible", True),
            "order": idx
        })
    
    return {
        "template_id": template_id,
        "name": template["name"],
        "description": template["description"],
        "blocks": preview_blocks
    }


class ApplyTemplateRequest(BaseModel):
    template_id: str
    page_title: str
    page_slug: str
    replace_existing: bool = False


@router.post("/templates/apply")
async def apply_template(
    request: ApplyTemplateRequest,
    admin: dict = Depends(admin_route_guard)
):
    """Apply a template to create a new page or update existing"""
    template = get_template(request.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Check if page exists
    existing_page = await cms_service.get_page_by_slug(request.page_slug)
    
    if existing_page and not request.replace_existing:
        raise HTTPException(
            status_code=400, 
            detail="Page with this slug already exists. Set replace_existing=true to overwrite."
        )
    
    if existing_page and request.replace_existing:
        # Update existing page with template blocks
        page_id = existing_page["page_id"]
        
        # Clear existing blocks
        await cms_service.clear_page_blocks(page_id, admin["portal_user_id"], admin["email"])
        
        # Add template blocks
        for idx, block in enumerate(template["blocks"]):
            await cms_service.add_block(
                page_id=page_id,
                block_type=block["block_type"],
                content=block["content"],
                admin_id=admin["portal_user_id"],
                admin_email=admin["email"]
            )
        
        # Update page title
        await cms_service.update_page(
            page_id=page_id,
            title=request.page_title,
            admin_id=admin["portal_user_id"],
            admin_email=admin["email"]
        )
        
        return {"success": True, "page_id": page_id, "action": "updated"}
    
    else:
        # Create new page with template
        try:
            page = await cms_service.create_page(
                slug=request.page_slug,
                title=request.page_title,
                description=template.get("description", ""),
                admin_id=admin["portal_user_id"],
                admin_email=admin["email"]
            )
            
            # Add template blocks
            for idx, block in enumerate(template["blocks"]):
                await cms_service.add_block(
                    page_id=page["page_id"],
                    block_type=block["block_type"],
                    content=block["content"],
                    admin_id=admin["portal_user_id"],
                    admin_email=admin["email"]
                )
            
            return {"success": True, "page_id": page["page_id"], "action": "created"}
        
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))


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


# ============================================
# Media File Serving (Public - for rendered pages)
# ============================================

from fastapi.responses import StreamingResponse
from services.storage_adapter import cms_storage_adapter

@router.get("/media/file/{file_id}")
async def serve_media_file(file_id: str):
    """Serve media file content (Public - for rendered pages)"""
    try:
        content, metadata = await cms_storage_adapter.download_file(file_id)
        return StreamingResponse(
            iter([content]),
            media_type=metadata.content_type,
            headers={
                "Content-Disposition": f"inline; filename={metadata.filename}",
                "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
            }
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Media file not found")
