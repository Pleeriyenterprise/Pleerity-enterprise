"""
Legal Content Management - Admin Interface
Allows admins to edit legal pages (Privacy, Terms, Cookies, Accessibility)
with full audit trail and version control
"""
from fastapi import APIRouter, HTTPException, Depends
from database import database
from middleware import admin_route_guard
from models import AuditAction
from utils.audit import create_audit_log
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional
import logging

from services.legal_content_defaults import LEGAL_SLUGS
from services.legal_content_service import (
    get_reset_default,
    preview_legal_draft,
    sanitize_legal_markdown,
    seed_canonical_content,
    serialize_legal_admin_row,
)

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


class LegalContentPreviewRequest(BaseModel):
    title: str = ""
    content: str = ""


@router.post("/{slug}/preview")
async def preview_legal_content(
    slug: str,
    data: LegalContentPreviewRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """Preview draft markdown after governed sanitisation (no save, no audit)."""
    if slug not in LEGAL_SLUGS:
        raise HTTPException(status_code=400, detail="Invalid slug")
    return preview_legal_draft(slug, data.title, data.content)


@router.get("/{slug}")
async def get_legal_content(slug: str, current_user: dict = Depends(admin_route_guard)):
    """Get current legal/marketing content by slug."""
    db = database.get_db()

    legal_content = await db.legal_content.find_one(
        {"slug": slug},
        {"_id": 0}
    )

    return serialize_legal_admin_row(legal_content, slug)


@router.get("")
async def list_legal_content(current_user: dict = Depends(admin_route_guard)):
    """List all legal/marketing content pages."""
    db = database.get_db()

    content_list = await db.legal_content.find(
        {},
        {"_id": 0}
    ).to_list(100)

    by_slug = {item["slug"]: item for item in content_list if item.get("slug")}

    return [serialize_legal_admin_row(by_slug.get(slug), slug) for slug in LEGAL_SLUGS]


async def _persist_legal_update(
    slug: str,
    title: str,
    content: str,
    current_user: dict,
    *,
    audit_action_type: str = "LEGAL_CONTENT_UPDATED",
    extra_metadata: Optional[dict] = None,
) -> dict:
    db = database.get_db()
    clean_content = sanitize_legal_markdown(content)
    current = await db.legal_content.find_one({"slug": slug}, {"_id": 0})
    current_version = current.get("version", 0) if current else 0
    new_version = current_version + 1

    updated_content = {
        "slug": slug,
        "title": title,
        "content": clean_content,
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

    version_record = {
        **updated_content,
        "version_id": f"{slug}_v{new_version}",
        "previous_content": current.get("content") if current else None,
        "previous_version": current_version,
        "created_at": datetime.now(timezone.utc),
    }
    await db.legal_content_versions.insert_one(version_record)

    metadata = {
        "action_type": audit_action_type,
        "slug": slug,
        "title": title,
        "version": new_version,
        "content_length": len(clean_content),
        "previous_version": current_version,
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role="ROLE_ADMIN",
        actor_id=current_user.get("user_id"),
        metadata=metadata,
    )

    return updated_content


@router.put("/{slug}")
async def update_legal_content(
    slug: str,
    data: LegalContentUpdate,
    current_user: dict = Depends(admin_route_guard)
):
    """Update legal content with full audit trail."""
    if slug not in LEGAL_SLUGS:
        raise HTTPException(status_code=400, detail="Invalid slug")

    updated_content = await _persist_legal_update(
        slug, data.title, data.content, current_user
    )

    logger.info(f"Legal content updated: {slug} v{updated_content['version']} by {current_user.get('email')}")

    return {
        "success": True,
        "content": updated_content,
        "message": f"Legal content '{slug}' updated to version {updated_content['version']}"
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


@router.post("/{slug}/restore/{version}")
async def restore_legal_content_version(
    slug: str,
    version: int,
    current_user: dict = Depends(admin_route_guard),
):
    """Restore a prior version as a new published version (non-destructive)."""
    if slug not in LEGAL_SLUGS:
        raise HTTPException(status_code=400, detail="Invalid slug")
    db = database.get_db()
    row = await db.legal_content_versions.find_one(
        {"slug": slug, "version": version},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Version not found")

    updated = await _persist_legal_update(
        slug,
        row.get("title") or slug.title(),
        row.get("content") or "",
        current_user,
        audit_action_type="LEGAL_CONTENT_RESTORED",
        extra_metadata={"restored_from_version": version},
    )
    return {
        "success": True,
        "content": updated,
        "message": f"Restored version {version} as new version {updated['version']}",
    }


@router.post("/{slug}/reset-default")
async def reset_to_default(slug: str, current_user: dict = Depends(admin_route_guard)):
    """Reset legal content to canonical default baseline."""
    default_data = get_reset_default(slug)
    if not default_data:
        raise HTTPException(status_code=400, detail="Invalid slug")

    updated = await _persist_legal_update(
        slug,
        default_data["title"],
        default_data["content"],
        current_user,
        audit_action_type="LEGAL_CONTENT_RESET_DEFAULT",
        extra_metadata={"reset_to": "canonical_default"},
    )
    serialized = serialize_legal_admin_row(updated, slug)
    return {
        "success": True,
        "content": serialized,
        "message": f"Legal content '{slug}' reset to canonical default (v{serialized['version']})",
    }


@router.post("/seed-canonical")
async def seed_canonical(current_user: dict = Depends(admin_route_guard)):
    """Idempotent seed of canonical public copy into legal_content."""
    db = database.get_db()
    result = await seed_canonical_content(
        db,
        actor_email=current_user.get("email"),
        actor_user_id=current_user.get("user_id"),
    )
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role="ROLE_ADMIN",
        actor_id=current_user.get("user_id"),
        metadata={
            "action_type": "LEGAL_CONTENT_SEED_CANONICAL",
            "provenance": result.get("provenance"),
            "results": result.get("results"),
        },
    )
    return {"success": True, **result}
