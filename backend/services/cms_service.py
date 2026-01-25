"""
CMS Service for Admin Site Builder
Handles page management, revisions, media, and auditing
"""
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from pydantic import ValidationError

from database import database
from models.cms import (
    BlockType, ContentBlock, PageStatus, PageType, SEOMetadata,
    CMSPageResponse, CMSRevisionResponse, CMSMediaResponse,
    MediaType, BLOCK_CONTENT_SCHEMAS, CATEGORY_CONFIG, PurchaseMode
)
from utils.audit import create_audit_log
from models.core import AuditAction, UserRole


def get_db():
    return database.get_db()


async def log_audit(action: str, entity_type: str, entity_id: str, user_id: str, user_email: str, changes: dict):
    """Simple audit logging wrapper for CMS operations"""
    # Map action string to AuditAction enum
    action_map = {
        "cms_page_create": AuditAction.CMS_PAGE_CREATE,
        "cms_page_update": AuditAction.CMS_PAGE_UPDATE,
        "cms_page_archive": AuditAction.CMS_PAGE_ARCHIVE,
        "cms_page_publish": AuditAction.CMS_PAGE_PUBLISH,
        "cms_page_rollback": AuditAction.CMS_PAGE_ROLLBACK,
        "cms_block_add": AuditAction.CMS_BLOCK_ADD,
        "cms_block_update": AuditAction.CMS_BLOCK_UPDATE,
        "cms_block_delete": AuditAction.CMS_BLOCK_DELETE,
        "cms_blocks_reorder": AuditAction.CMS_BLOCKS_REORDER,
        "cms_media_upload": AuditAction.CMS_MEDIA_UPLOAD,
        "cms_media_delete": AuditAction.CMS_MEDIA_DELETE,
    }
    
    audit_action = action_map.get(action, AuditAction.CMS_PAGE_UPDATE)
    
    await create_audit_log(
        action=audit_action,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=user_id,
        resource_type=entity_type,
        resource_id=entity_id,
        metadata={
            "actor_email": user_email,
            "changes": changes
        }
    )


# ============================================
# Helper Functions
# ============================================

def generate_page_id() -> str:
    return f"PG-{uuid.uuid4().hex[:12].upper()}"

def generate_revision_id() -> str:
    return f"REV-{uuid.uuid4().hex[:12].upper()}"

def generate_block_id() -> str:
    return f"BLK-{uuid.uuid4().hex[:8].upper()}"

def generate_media_id() -> str:
    return f"MED-{uuid.uuid4().hex[:12].upper()}"

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ============================================
# Block Validation
# ============================================

def validate_block_content(block_type: BlockType, content: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate block content against its schema"""
    schema_class = BLOCK_CONTENT_SCHEMAS.get(block_type)
    if not schema_class:
        return False, f"Unknown block type: {block_type}"
    
    try:
        schema_class(**content)
        return True, None
    except ValidationError as e:
        return False, str(e)


def validate_video_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Only allow YouTube and Vimeo embeds for safety
    Returns (is_valid, error_message)
    """
    youtube_patterns = [
        r'(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(https?://)?(www\.)?youtube\.com/embed/[\w-]+',
        r'(https?://)?(www\.)?youtu\.be/[\w-]+',
    ]
    vimeo_patterns = [
        r'(https?://)?(www\.)?vimeo\.com/\d+',
        r'(https?://)?(player\.)?vimeo\.com/video/\d+',
    ]
    
    for pattern in youtube_patterns + vimeo_patterns:
        if re.match(pattern, url, re.IGNORECASE):
            return True, None
    
    return False, "Only YouTube and Vimeo URLs are allowed for security"


# ============================================
# Page Management
# ============================================

def build_full_path(page_type: str, slug: str, category_slug: Optional[str] = None) -> str:
    """Build the full URL path for a page based on its type."""
    if page_type == "HUB":
        return "/services"
    elif page_type == "CATEGORY":
        return f"/services/{slug}"
    elif page_type == "SERVICE":
        if not category_slug:
            raise ValueError("SERVICE pages require a category_slug")
        return f"/services/{category_slug}/{slug}"
    elif page_type == "LEGAL":
        return f"/legal/{slug}"
    else:
        return f"/{slug}"


async def create_page(
    slug: str,
    title: str,
    description: Optional[str],
    admin_id: str,
    admin_email: str,
    page_type: str = "GENERIC",
    category_slug: Optional[str] = None,
    service_code: Optional[str] = None,
    subtitle: Optional[str] = None,
    display_order: int = 0
) -> CMSPageResponse:
    """Create a new CMS page with support for marketing website page types."""
    
    # Check slug uniqueness within category
    query = {"slug": slug}
    if category_slug:
        query["category_slug"] = category_slug
    
    existing = await get_db().cms_pages.find_one(query)
    if existing:
        return False, f"Page with slug '{slug}' already exists in this category", None
    
    # Validate slug format
    if not re.match(r'^[a-z0-9-]+$', slug):
        raise ValueError("Slug must contain only lowercase letters, numbers, and hyphens")
    
    # Validate service code exists (for SERVICE pages)
    if page_type == "SERVICE" and service_code:
        service = await get_db().service_catalogue_v2.find_one({"service_code": service_code})
        if not service:
            raise ValueError(f"Service code '{service_code}' not found in catalogue")
    
    # Build full path
    full_path = build_full_path(page_type, slug, category_slug)
    
    page_id = generate_page_id()
    now = now_utc()
    
    page_doc = {
        "page_id": page_id,
        "slug": slug,
        "title": title,
        "description": description,
        "page_type": page_type,
        "category_slug": category_slug,
        "service_code": service_code,
        "full_path": full_path,
        "subtitle": subtitle,
        "hero_image": None,
        "status": PageStatus.DRAFT.value,
        "blocks": [],
        "seo": None,
        "display_order": display_order,
        "visible_in_nav": True,
        "current_version": 0,
        "created_at": now,
        "updated_at": now,
        "published_at": None,
        "created_by": admin_id,
        "updated_by": admin_id,
    }
    
    await get_db().cms_pages.insert_one(page_doc)
    
    # Audit log
    await log_audit(
        action="cms_page_create",
        entity_type="cms_page",
        entity_id=page_id,
        user_id=admin_id,
        user_email=admin_email,
        changes={"slug": slug, "title": title, "page_type": page_type, "full_path": full_path}
    )
    
    return CMSPageResponse(
        page_id=page_id,
        slug=slug,
        title=title,
        description=description,
        page_type=page_type,
        category_slug=category_slug,
        service_code=service_code,
        full_path=full_path,
        subtitle=subtitle,
        status=PageStatus.DRAFT,
        blocks=[],
        seo=None,
        display_order=display_order,
        visible_in_nav=True,
        current_version=0,
        created_at=now,
        updated_at=now,
        published_at=None,
        created_by=admin_id,
        updated_by=admin_id
    )


async def get_page(page_id: str) -> Optional[CMSPageResponse]:
    """Get a page by ID"""
    doc = await get_db().cms_pages.find_one({"page_id": page_id})
    if not doc:
        return None
    return _doc_to_page_response(doc)


async def get_page_by_slug(slug: str) -> Optional[CMSPageResponse]:
    """Get a page by slug"""
    doc = await get_db().cms_pages.find_one({"slug": slug})
    if not doc:
        return None
    return _doc_to_page_response(doc)


async def list_pages(
    status: Optional[PageStatus] = None,
    limit: int = 50,
    offset: int = 0
) -> Tuple[List[CMSPageResponse], int]:
    """List all CMS pages with optional status filter"""
    query = {}
    if status:
        query["status"] = status.value
    
    total = await get_db().cms_pages.count_documents(query)
    cursor = get_db().cms_pages.find(query).sort("updated_at", -1).skip(offset).limit(limit)
    
    pages = []
    async for doc in cursor:
        pages.append(_doc_to_page_response(doc))
    
    return pages, total


async def update_page(
    page_id: str,
    title: Optional[str],
    description: Optional[str],
    blocks: Optional[List[Dict]],
    seo: Optional[Dict],
    admin_id: str,
    admin_email: str
) -> CMSPageResponse:
    """Update page content (creates draft state)"""
    
    page = await get_db().cms_pages.find_one({"page_id": page_id})
    if not page:
        raise ValueError(f"Page {page_id} not found")
    
    update_fields = {
        "updated_at": now_utc(),
        "updated_by": admin_id,
    }
    
    changes = {}
    
    if title is not None:
        update_fields["title"] = title
        changes["title"] = title
    
    if description is not None:
        update_fields["description"] = description
        changes["description"] = description
    
    if blocks is not None:
        # Validate all blocks
        for block in blocks:
            block_type = BlockType(block.get("block_type"))
            is_valid, error = validate_block_content(block_type, block.get("content", {}))
            if not is_valid:
                raise ValueError(f"Invalid block content: {error}")
            
            # Validate video URLs specifically
            if block_type == BlockType.VIDEO_EMBED:
                video_url = block.get("content", {}).get("video_url", "")
                is_valid, error = validate_video_url(video_url)
                if not is_valid:
                    raise ValueError(error)
        
        update_fields["blocks"] = blocks
        changes["blocks_updated"] = True
    
    if seo is not None:
        update_fields["seo"] = seo
        changes["seo_updated"] = True
    
    # If published, revert to draft
    if page.get("status") == PageStatus.PUBLISHED.value:
        update_fields["status"] = PageStatus.DRAFT.value
        changes["status"] = "DRAFT (modified)"
    
    await get_db().cms_pages.update_one(
        {"page_id": page_id},
        {"$set": update_fields}
    )
    
    # Audit log
    await log_audit(
        action="cms_page_update",
        entity_type="cms_page",
        entity_id=page_id,
        user_id=admin_id,
        user_email=admin_email,
        changes=changes
    )
    
    return await get_page(page_id)


async def delete_page(page_id: str, admin_id: str, admin_email: str) -> bool:
    """Delete (archive) a page"""
    page = await get_db().cms_pages.find_one({"page_id": page_id})
    if not page:
        return False
    
    await get_db().cms_pages.update_one(
        {"page_id": page_id},
        {"$set": {
            "status": PageStatus.ARCHIVED.value,
            "updated_at": now_utc(),
            "updated_by": admin_id
        }}
    )
    
    await log_audit(
        action="cms_page_archive",
        entity_type="cms_page",
        entity_id=page_id,
        user_id=admin_id,
        user_email=admin_email,
        changes={"status": "ARCHIVED"}
    )
    
    return True


# ============================================
# Block Management
# ============================================

async def add_block(
    page_id: str,
    block_type: BlockType,
    content: Dict[str, Any],
    position: Optional[int],
    admin_id: str,
    admin_email: str
) -> ContentBlock:
    """Add a block to a page"""
    
    # Validate content
    is_valid, error = validate_block_content(block_type, content)
    if not is_valid:
        raise ValueError(f"Invalid block content: {error}")
    
    # Validate video URL if applicable
    if block_type == BlockType.VIDEO_EMBED:
        video_url = content.get("video_url", "")
        is_valid, error = validate_video_url(video_url)
        if not is_valid:
            raise ValueError(error)
    
    page = await get_db().cms_pages.find_one({"page_id": page_id})
    if not page:
        raise ValueError(f"Page {page_id} not found")
    
    block_id = generate_block_id()
    blocks = page.get("blocks", [])
    
    # Determine order
    if position is not None and 0 <= position <= len(blocks):
        order = position
        # Shift existing blocks
        for b in blocks:
            if b["order"] >= position:
                b["order"] += 1
    else:
        order = len(blocks)
    
    new_block = {
        "block_id": block_id,
        "block_type": block_type.value,
        "content": content,
        "visible": True,
        "order": order,
    }
    
    blocks.append(new_block)
    blocks.sort(key=lambda x: x["order"])
    
    # Update page
    await get_db().cms_pages.update_one(
        {"page_id": page_id},
        {"$set": {
            "blocks": blocks,
            "updated_at": now_utc(),
            "updated_by": admin_id,
            "status": PageStatus.DRAFT.value if page.get("status") == PageStatus.PUBLISHED.value else page.get("status")
        }}
    )
    
    await log_audit(
        action="cms_block_add",
        entity_type="cms_page",
        entity_id=page_id,
        user_id=admin_id,
        user_email=admin_email,
        changes={"block_id": block_id, "block_type": block_type.value}
    )
    
    return ContentBlock(**new_block)


async def update_block(
    page_id: str,
    block_id: str,
    content: Optional[Dict[str, Any]],
    visible: Optional[bool],
    admin_id: str,
    admin_email: str
) -> ContentBlock:
    """Update a block's content or visibility"""
    
    page = await get_db().cms_pages.find_one({"page_id": page_id})
    if not page:
        raise ValueError(f"Page {page_id} not found")
    
    blocks = page.get("blocks", [])
    block_index = next((i for i, b in enumerate(blocks) if b["block_id"] == block_id), None)
    
    if block_index is None:
        raise ValueError(f"Block {block_id} not found")
    
    block = blocks[block_index]
    changes = {}
    
    if content is not None:
        block_type = BlockType(block["block_type"])
        is_valid, error = validate_block_content(block_type, content)
        if not is_valid:
            raise ValueError(f"Invalid block content: {error}")
        
        if block_type == BlockType.VIDEO_EMBED:
            video_url = content.get("video_url", "")
            is_valid, error = validate_video_url(video_url)
            if not is_valid:
                raise ValueError(error)
        
        block["content"] = content
        changes["content_updated"] = True
    
    if visible is not None:
        block["visible"] = visible
        changes["visible"] = visible
    
    blocks[block_index] = block
    
    await get_db().cms_pages.update_one(
        {"page_id": page_id},
        {"$set": {
            "blocks": blocks,
            "updated_at": now_utc(),
            "updated_by": admin_id,
            "status": PageStatus.DRAFT.value if page.get("status") == PageStatus.PUBLISHED.value else page.get("status")
        }}
    )
    
    await log_audit(
        action="cms_block_update",
        entity_type="cms_page",
        entity_id=page_id,
        user_id=admin_id,
        user_email=admin_email,
        changes={"block_id": block_id, **changes}
    )
    
    return ContentBlock(**block)


async def delete_block(
    page_id: str,
    block_id: str,
    admin_id: str,
    admin_email: str
) -> bool:
    """Delete a block from a page"""
    
    page = await get_db().cms_pages.find_one({"page_id": page_id})
    if not page:
        raise ValueError(f"Page {page_id} not found")
    
    blocks = page.get("blocks", [])
    new_blocks = [b for b in blocks if b["block_id"] != block_id]
    
    if len(new_blocks) == len(blocks):
        return False  # Block not found
    
    # Reorder
    for i, b in enumerate(new_blocks):
        b["order"] = i
    
    await get_db().cms_pages.update_one(
        {"page_id": page_id},
        {"$set": {
            "blocks": new_blocks,
            "updated_at": now_utc(),
            "updated_by": admin_id,
            "status": PageStatus.DRAFT.value if page.get("status") == PageStatus.PUBLISHED.value else page.get("status")
        }}
    )
    
    await log_audit(
        action="cms_block_delete",
        entity_type="cms_page",
        entity_id=page_id,
        user_id=admin_id,
        user_email=admin_email,
        changes={"block_id": block_id}
    )
    
    return True


async def reorder_blocks(
    page_id: str,
    block_order: List[str],
    admin_id: str,
    admin_email: str
) -> List[ContentBlock]:
    """Reorder blocks on a page"""
    
    page = await get_db().cms_pages.find_one({"page_id": page_id})
    if not page:
        raise ValueError(f"Page {page_id} not found")
    
    blocks = page.get("blocks", [])
    block_map = {b["block_id"]: b for b in blocks}
    
    # Validate all block IDs exist
    for bid in block_order:
        if bid not in block_map:
            raise ValueError(f"Block {bid} not found on page")
    
    # Reorder
    new_blocks = []
    for i, bid in enumerate(block_order):
        block = block_map[bid]
        block["order"] = i
        new_blocks.append(block)
    
    # Add any blocks not in the order list (keep at end)
    remaining = [b for b in blocks if b["block_id"] not in block_order]
    for b in remaining:
        b["order"] = len(new_blocks)
        new_blocks.append(b)
    
    await get_db().cms_pages.update_one(
        {"page_id": page_id},
        {"$set": {
            "blocks": new_blocks,
            "updated_at": now_utc(),
            "updated_by": admin_id,
            "status": PageStatus.DRAFT.value if page.get("status") == PageStatus.PUBLISHED.value else page.get("status")
        }}
    )
    
    await log_audit(
        action="cms_blocks_reorder",
        entity_type="cms_page",
        entity_id=page_id,
        user_id=admin_id,
        user_email=admin_email,
        changes={"new_order": block_order}
    )
    
    return [ContentBlock(**b) for b in new_blocks]


# ============================================
# Publishing & Revisions
# ============================================

async def publish_page(
    page_id: str,
    notes: Optional[str],
    admin_id: str,
    admin_email: str
) -> CMSPageResponse:
    """Publish page and create revision snapshot"""
    
    page = await get_db().cms_pages.find_one({"page_id": page_id})
    if not page:
        raise ValueError(f"Page {page_id} not found")
    
    now = now_utc()
    new_version = page.get("current_version", 0) + 1
    
    # Create revision snapshot
    revision_id = generate_revision_id()
    revision_doc = {
        "revision_id": revision_id,
        "page_id": page_id,
        "version": new_version,
        "title": page["title"],
        "description": page.get("description"),
        "blocks": page.get("blocks", []),
        "seo": page.get("seo"),
        "published_at": now,
        "published_by": admin_id,
        "notes": notes,
    }
    
    await get_db().cms_revisions.insert_one(revision_doc)
    
    # Update page status
    await get_db().cms_pages.update_one(
        {"page_id": page_id},
        {"$set": {
            "status": PageStatus.PUBLISHED.value,
            "current_version": new_version,
            "published_at": now,
            "updated_at": now,
            "updated_by": admin_id,
        }}
    )
    
    await log_audit(
        action="cms_page_publish",
        entity_type="cms_page",
        entity_id=page_id,
        user_id=admin_id,
        user_email=admin_email,
        changes={"version": new_version, "notes": notes}
    )
    
    return await get_page(page_id)


async def get_revisions(page_id: str, limit: int = 20) -> List[CMSRevisionResponse]:
    """Get revision history for a page"""
    cursor = get_db().cms_revisions.find({"page_id": page_id}).sort("version", -1).limit(limit)
    
    revisions = []
    async for doc in cursor:
        revisions.append(_doc_to_revision_response(doc))
    
    return revisions


async def get_revision(revision_id: str) -> Optional[CMSRevisionResponse]:
    """Get a specific revision"""
    doc = await get_db().cms_revisions.find_one({"revision_id": revision_id})
    if not doc:
        return None
    return _doc_to_revision_response(doc)


async def rollback_page(
    page_id: str,
    revision_id: str,
    notes: Optional[str],
    admin_id: str,
    admin_email: str
) -> CMSPageResponse:
    """Rollback page to a previous revision"""
    
    page = await get_db().cms_pages.find_one({"page_id": page_id})
    if not page:
        raise ValueError(f"Page {page_id} not found")
    
    revision = await get_db().cms_revisions.find_one({"revision_id": revision_id, "page_id": page_id})
    if not revision:
        raise ValueError(f"Revision {revision_id} not found for page {page_id}")
    
    # Restore content from revision
    await get_db().cms_pages.update_one(
        {"page_id": page_id},
        {"$set": {
            "title": revision["title"],
            "description": revision.get("description"),
            "blocks": revision.get("blocks", []),
            "seo": revision.get("seo"),
            "status": PageStatus.DRAFT.value,
            "updated_at": now_utc(),
            "updated_by": admin_id,
        }}
    )
    
    await log_audit(
        action="cms_page_rollback",
        entity_type="cms_page",
        entity_id=page_id,
        user_id=admin_id,
        user_email=admin_email,
        changes={
            "rolled_back_to_version": revision["version"],
            "revision_id": revision_id,
            "notes": notes
        }
    )
    
    return await get_page(page_id)


# ============================================
# Media Library
# ============================================

async def upload_media(
    file_name: str,
    file_url: str,
    file_type: str,
    file_size: int,
    alt_text: Optional[str],
    tags: List[str],
    admin_id: str,
    admin_email: str
) -> CMSMediaResponse:
    """Record a media upload"""
    
    media_id = generate_media_id()
    now = now_utc()
    
    # Determine media type
    media_type = MediaType.IMAGE if file_type.startswith("image/") else MediaType.VIDEO_EMBED
    
    media_doc = {
        "media_id": media_id,
        "media_type": media_type.value,
        "file_name": file_name,
        "file_url": file_url,
        "file_type": file_type,
        "file_size": file_size,
        "alt_text": alt_text,
        "tags": tags,
        "uploaded_at": now,
        "uploaded_by": admin_id,
    }
    
    await get_db().cms_media.insert_one(media_doc)
    
    await log_audit(
        action="cms_media_upload",
        entity_type="cms_media",
        entity_id=media_id,
        user_id=admin_id,
        user_email=admin_email,
        changes={"file_name": file_name, "media_type": media_type.value}
    )
    
    return CMSMediaResponse(
        media_id=media_id,
        media_type=media_type,
        file_name=file_name,
        file_url=file_url,
        file_size=file_size,
        alt_text=alt_text,
        tags=tags,
        uploaded_at=now,
        uploaded_by=admin_id
    )


async def list_media(
    media_type: Optional[MediaType] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> Tuple[List[CMSMediaResponse], int]:
    """List media library items"""
    
    query = {}
    if media_type:
        query["media_type"] = media_type.value
    if search:
        query["$or"] = [
            {"file_name": {"$regex": search, "$options": "i"}},
            {"alt_text": {"$regex": search, "$options": "i"}},
            {"tags": {"$in": [search.lower()]}},
        ]
    
    total = await get_db().cms_media.count_documents(query)
    cursor = get_db().cms_media.find(query).sort("uploaded_at", -1).skip(offset).limit(limit)
    
    media_items = []
    async for doc in cursor:
        media_items.append(_doc_to_media_response(doc))
    
    return media_items, total


async def get_media(media_id: str) -> Optional[CMSMediaResponse]:
    """Get a media item by ID"""
    doc = await get_db().cms_media.find_one({"media_id": media_id})
    if not doc:
        return None
    return _doc_to_media_response(doc)


async def delete_media(media_id: str, admin_id: str, admin_email: str) -> bool:
    """Delete a media item"""
    result = await get_db().cms_media.delete_one({"media_id": media_id})
    
    if result.deleted_count > 0:
        await log_audit(
            action="cms_media_delete",
            entity_type="cms_media",
            entity_id=media_id,
            user_id=admin_id,
            user_email=admin_email,
            changes={}
        )
        return True
    return False


# ============================================
# Public Rendering
# ============================================

async def get_published_page(slug: str) -> Optional[Dict[str, Any]]:
    """Get published page content for public rendering"""
    page = await get_db().cms_pages.find_one({
        "slug": slug,
        "status": PageStatus.PUBLISHED.value
    })
    
    if not page:
        return None
    
    # Return only published content (visible blocks)
    visible_blocks = [b for b in page.get("blocks", []) if b.get("visible", True)]
    visible_blocks.sort(key=lambda x: x.get("order", 0))
    
    return {
        "slug": page["slug"],
        "title": page["title"],
        "description": page.get("description"),
        "blocks": visible_blocks,
        "seo": page.get("seo"),
    }


async def get_page_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """Get page by slug (any status)"""
    page = await get_db().cms_pages.find_one({"slug": slug}, {"_id": 0})
    return page


async def clear_page_blocks(page_id: str, admin_id: str, admin_email: str):
    """Clear all blocks from a page (for template replacement)"""
    page = await get_db().cms_pages.find_one({"page_id": page_id})
    if not page:
        raise ValueError(f"Page {page_id} not found")
    
    await get_db().cms_pages.update_one(
        {"page_id": page_id},
        {"$set": {
            "blocks": [],
            "updated_at": now_utc(),
            "updated_by": admin_id,
            "status": PageStatus.DRAFT.value
        }}
    )
    
    await log_audit(
        action="cms_page_update",
        entity_type="cms_page",
        entity_id=page_id,
        user_id=admin_id,
        user_email=admin_email,
        changes={"action": "clear_blocks_for_template"}
    )


# ============================================
# Helpers
# ============================================

def _doc_to_page_response(doc: Dict) -> CMSPageResponse:
    """Convert MongoDB document to CMSPageResponse"""
    blocks = [ContentBlock(**b) for b in doc.get("blocks", [])]
    seo = SEOMetadata(**doc["seo"]) if doc.get("seo") else None
    
    return CMSPageResponse(
        page_id=doc["page_id"],
        slug=doc["slug"],
        title=doc["title"],
        description=doc.get("description"),
        status=PageStatus(doc["status"]),
        blocks=blocks,
        seo=seo,
        current_version=doc.get("current_version", 0),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        published_at=doc.get("published_at"),
        created_by=doc["created_by"],
        updated_by=doc["updated_by"]
    )


def _doc_to_revision_response(doc: Dict) -> CMSRevisionResponse:
    """Convert MongoDB document to CMSRevisionResponse"""
    blocks = [ContentBlock(**b) for b in doc.get("blocks", [])]
    seo = SEOMetadata(**doc["seo"]) if doc.get("seo") else None
    
    return CMSRevisionResponse(
        revision_id=doc["revision_id"],
        page_id=doc["page_id"],
        version=doc["version"],
        title=doc["title"],
        blocks=blocks,
        seo=seo,
        published_at=doc["published_at"],
        published_by=doc["published_by"],
        notes=doc.get("notes")
    )


def _doc_to_media_response(doc: Dict) -> CMSMediaResponse:
    """Convert MongoDB document to CMSMediaResponse"""
    return CMSMediaResponse(
        media_id=doc["media_id"],
        media_type=MediaType(doc["media_type"]),
        file_name=doc["file_name"],
        file_url=doc["file_url"],
        file_size=doc.get("file_size"),
        alt_text=doc.get("alt_text"),
        tags=doc.get("tags", []),
        uploaded_at=doc["uploaded_at"],
        uploaded_by=doc["uploaded_by"]
    )
