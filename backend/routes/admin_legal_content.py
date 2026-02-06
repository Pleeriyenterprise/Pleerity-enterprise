"""
Legal Content Management - Admin Interface
Allows admins to edit legal pages (Privacy, Terms, Cookies, Accessibility)
with full audit trail and version control
"""
from fastapi import APIRouter, HTTPException, Depends
from database import database
from auth_middleware import admin_route_guard
from models import AuditAction
from utils.audit import create_audit_log
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/legal-content", tags=["admin-legal"])


class LegalContentUpdate(BaseModel):
    slug: str  # privacy, terms, cookies, accessibility
    title: str
    content: str  # Markdown or HTML


class LegalContentResponse(BaseModel):
    slug: str
    title: str
    content: str
    version: int
    updated_at: str
    updated_by: Optional[str]


@router.get("/{slug}")
async def get_legal_content(slug: str, current_user: dict = Depends(admin_route_guard)):
    """Get current legal content by slug."""
    db = database.get_db()
    
    legal_content = await db.legal_content.find_one(
        {"slug": slug},
        {"_id": 0}
    )
    
    if not legal_content:
        # Return default/empty structure
        return {
            "slug": slug,
            "title": "",
            "content": "",
            "version": 0,
            "updated_at": None,
            "updated_by": None
        }
    
    return legal_content


@router.get("")
async def list_legal_content(current_user: dict = Depends(admin_route_guard)):
    """List all legal content pages."""
    db = database.get_db()
    
    content_list = await db.legal_content.find(
        {},
        {"_id": 0}
    ).to_list(100)
    
    # Ensure all required slugs exist
    required_slugs = ['privacy', 'terms', 'cookies', 'accessibility']
    existing_slugs = {item['slug'] for item in content_list}
    
    for slug in required_slugs:
        if slug not in existing_slugs:
            content_list.append({
                "slug": slug,
                "title": f"{slug.title()} Policy",
                "content": "",
                "version": 0,
                "updated_at": None,
                "updated_by": None
            })
    
    return content_list


@router.put("/{slug}")
async def update_legal_content(
    slug: str,
    data: LegalContentUpdate,
    current_user: dict = Depends(admin_route_guard)
):
    """
    Update legal content with full audit trail.
    Creates a new version and logs the change.
    """
    db = database.get_db()
    
    # Get current content for diff
    current = await db.legal_content.find_one({"slug": slug}, {"_id": 0})
    
    current_version = current.get("version", 0) if current else 0
    new_version = current_version + 1
    
    # Store new version
    updated_content = {
        "slug": slug,
        "title": data.title,
        "content": data.content,
        "version": new_version,
        "updated_at": datetime.now(timezone.utc),
        "updated_by": current_user.get("email"),
        "updated_by_user_id": current_user.get("user_id"),
    }
    
    await db.legal_content.update_one(
        {"slug": slug},
        {"$set": updated_content},
        upsert=True
    )
    
    # Store version history
    version_record = {
        **updated_content,
        "version_id": f"{slug}_v{new_version}",
        "previous_content": current.get("content") if current else None,
        "previous_version": current_version,
        "created_at": datetime.now(timezone.utc),
    }
    
    await db.legal_content_versions.insert_one(version_record)
    
    # Audit log
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role="ROLE_ADMIN",
        actor_id=current_user.get("user_id"),
        metadata={
            "action_type": "LEGAL_CONTENT_UPDATED",
            "slug": slug,
            "title": data.title,
            "version": new_version,
            "content_length": len(data.content),
            "previous_version": current_version,
        }
    )
    
    logger.info(f"Legal content updated: {slug} v{new_version} by {current_user.get('email')}")
    
    return {
        "success": True,
        "content": updated_content,
        "message": f"Legal content '{slug}' updated to version {new_version}"
    }


@router.get("/{slug}/versions")
async def get_legal_content_versions(slug: str, current_user: dict = Depends(admin_route_guard)):
    """Get version history for a legal content page."""
    db = database.get_db()
    
    versions = await db.legal_content_versions.find(
        {"slug": slug},
        {"_id": 0}
    ).sort("version", -1).to_list(100)
    
    return versions


@router.post("/{slug}/reset-default")
async def reset_to_default(slug: str, current_user: dict = Depends(admin_route_guard)):
    """
    Reset legal content to default/baseline.
    Useful if admin wants to restore original content.
    """
    db = database.get_db()
    
    # Define default content (this can be expanded)
    defaults = {
        "privacy": {
            "title": "Privacy Policy",
            "content": "# Privacy Policy\n\nPlaceholder content. Please update via admin panel."
        },
        "terms": {
            "title": "Terms of Service",
            "content": "# Terms of Service\n\nPlaceholder content. Please update via admin panel."
        },
        "cookies": {
            "title": "Cookie Policy",
            "content": "# Cookie Policy\n\nPlaceholder content. Please update via admin panel."
        },
        "accessibility": {
            "title": "Accessibility Statement",
            "content": "# Accessibility Statement\n\nPlaceholder content. Please update via admin panel."
        }
    }
    
    if slug not in defaults:
        raise HTTPException(status_code=400, detail="Invalid slug")
    
    default_data = defaults[slug]
    
    # Update using the same logic as update endpoint
    return await update_legal_content(
        slug=slug,
        data=LegalContentUpdate(
            slug=slug,
            title=default_data["title"],
            content=default_data["content"]
        ),
        current_user=current_user
    )
