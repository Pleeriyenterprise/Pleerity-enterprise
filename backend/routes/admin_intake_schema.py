"""
Admin Intake Schema Management Routes

Provides APIs for admins to customize intake wizard form fields:
- Edit field labels, helper text, placeholders
- Modify validation rules
- Reorder fields
- Toggle field visibility/required status
- Draft/Publish workflow
- Version history and rollback

Schema customizations are stored in MongoDB and merged with base schemas.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from middleware import admin_route_guard
from database import database
import logging
import json
import copy

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/intake-schema", tags=["admin-intake-schema"])

# Collections
COLLECTION = "intake_schema_customizations"
VERSIONS_COLLECTION = "intake_schema_versions"

from services.intake_schema_registry import (
    get_service_schema,
    SERVICE_INTAKE_SCHEMAS,
    IntakeFieldType,
)


# ============================================================================
# REQUEST MODELS
# ============================================================================

class FieldOverrideRequest(BaseModel):
    """Override settings for a single field."""
    field_key: str
    label: Optional[str] = None
    helper_text: Optional[str] = None
    placeholder: Optional[str] = None
    required: Optional[bool] = None
    order: Optional[int] = None
    hidden: bool = False  # Soft-hide field from form
    validation: Optional[Dict[str, Any]] = None
    options: Optional[List[str]] = None  # For select/multi-select


class SaveSchemaOverridesRequest(BaseModel):
    """Request to save schema customizations for a service."""
    service_code: str
    field_overrides: List[FieldOverrideRequest]
    is_draft: bool = True  # Save as draft by default


class PublishSchemaRequest(BaseModel):
    """Request to publish draft schema to live."""
    service_code: str


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def get_customizations(service_code: str, draft: bool = False) -> Dict[str, Any]:
    """Get stored customizations for a service (live or draft)."""
    db = database.get_db()
    doc = await db[COLLECTION].find_one(
        {"service_code": service_code},
        {"_id": 0}
    )
    if not doc:
        return {}
    
    # Return draft or live overrides based on flag
    if draft:
        return {
            **doc,
            "field_overrides": doc.get("draft_overrides", doc.get("field_overrides", [])),
            "is_draft": True,
        }
    return doc


async def get_live_customizations(service_code: str) -> Dict[str, Any]:
    """Get only published/live customizations."""
    db = database.get_db()
    doc = await db[COLLECTION].find_one(
        {"service_code": service_code},
        {"_id": 0}
    )
    return doc or {}


async def save_customizations(
    service_code: str,
    overrides: List[Dict],
    updated_by: str,
    is_draft: bool = True
):
    """Save schema customizations for a service (draft or live)."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    # Get current state for audit
    current = await db[COLLECTION].find_one({"service_code": service_code}, {"_id": 0})
    before_state = current.get("field_overrides", []) if current else []
    before_draft = current.get("draft_overrides", []) if current else []
    
    if is_draft:
        # Save to draft_overrides only
        update_data = {
            "service_code": service_code,
            "draft_overrides": overrides,
            "draft_updated_at": now,
            "draft_updated_by": updated_by,
            "has_draft": True,
        }
    else:
        # Save directly to live (publish)
        update_data = {
            "service_code": service_code,
            "field_overrides": overrides,
            "updated_at": now,
            "updated_by": updated_by,
        }
    
    await db[COLLECTION].update_one(
        {"service_code": service_code},
        {
            "$set": update_data,
            "$setOnInsert": {
                "created_at": now,
            },
            "$inc": {"schema_version": 1}
        },
        upsert=True
    )
    
    # Get new version number
    updated = await db[COLLECTION].find_one({"service_code": service_code}, {"_id": 0})
    new_version = updated.get("schema_version", 1)
    
    # Create version history entry with audit log
    await db[VERSIONS_COLLECTION].insert_one({
        "service_code": service_code,
        "version": new_version,
        "is_draft": is_draft,
        "field_overrides": overrides,
        "before_state": before_draft if is_draft else before_state,
        "after_state": overrides,
        "created_at": now,
        "created_by": updated_by,
        "action": "draft_saved" if is_draft else "published",
    })
    
    # Create audit log entry
    await db["audit_logs"].insert_one({
        "action": "INTAKE_SCHEMA_UPDATED",
        "actor_type": "admin",
        "actor_id": updated_by,
        "resource_type": "intake_schema",
        "resource_id": service_code,
        "details": {
            "is_draft": is_draft,
            "schema_version": new_version,
            "before_state": json.dumps(before_draft if is_draft else before_state, default=str)[:5000],
            "after_state": json.dumps(overrides, default=str)[:5000],
            "overrides_count": len(overrides),
        },
        "created_at": now,
    })
    
    return new_version


async def publish_schema(service_code: str, published_by: str) -> int:
    """Publish draft schema to live."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    # Get current document
    current = await db[COLLECTION].find_one({"service_code": service_code})
    if not current:
        raise HTTPException(status_code=404, detail="No schema found to publish")
    
    draft_overrides = current.get("draft_overrides", [])
    if not draft_overrides:
        raise HTTPException(status_code=400, detail="No draft changes to publish")
    
    before_state = current.get("field_overrides", [])
    
    # Update live schema with draft
    await db[COLLECTION].update_one(
        {"service_code": service_code},
        {
            "$set": {
                "field_overrides": draft_overrides,
                "updated_at": now,
                "updated_by": published_by,
                "has_draft": False,
                "published_at": now,
                "published_by": published_by,
            },
            "$unset": {"draft_overrides": 1, "draft_updated_at": 1, "draft_updated_by": 1},
            "$inc": {"schema_version": 1}
        }
    )
    
    # Get new version
    updated = await db[COLLECTION].find_one({"service_code": service_code}, {"_id": 0})
    new_version = updated.get("schema_version", 1)
    
    # Create version entry
    await db[VERSIONS_COLLECTION].insert_one({
        "service_code": service_code,
        "version": new_version,
        "is_draft": False,
        "field_overrides": draft_overrides,
        "before_state": before_state,
        "after_state": draft_overrides,
        "created_at": now,
        "created_by": published_by,
        "action": "published",
    })
    
    # Audit log
    await db["audit_logs"].insert_one({
        "action": "INTAKE_SCHEMA_PUBLISHED",
        "actor_type": "admin",
        "actor_id": published_by,
        "resource_type": "intake_schema",
        "resource_id": service_code,
        "details": {
            "schema_version": new_version,
            "before_state": json.dumps(before_state, default=str)[:5000],
            "after_state": json.dumps(draft_overrides, default=str)[:5000],
        },
        "created_at": now,
    })
    
    return new_version


def merge_schema_with_overrides(base_schema: Dict, customizations: Dict) -> Dict:
    """Merge base schema with admin customizations."""
    if not customizations or not customizations.get("field_overrides"):
        return base_schema
    
    # Create lookup of overrides by field_key
    override_map = {
        o["field_key"]: o 
        for o in customizations.get("field_overrides", [])
    }
    
    # Apply overrides to fields
    merged_fields = []
    for field in base_schema.get("fields", []):
        field_key = field["field_key"]
        override = override_map.get(field_key, {})
        
        # Skip if field is hidden
        if override.get("hidden", False):
            continue
        
        merged_field = {**field}
        
        # Apply overrides (only non-None values)
        if override.get("label"):
            merged_field["label"] = override["label"]
        if override.get("helper_text") is not None:
            merged_field["helper_text"] = override["helper_text"]
        if override.get("placeholder") is not None:
            merged_field["placeholder"] = override["placeholder"]
        if override.get("required") is not None:
            merged_field["required"] = override["required"]
        if override.get("order") is not None:
            merged_field["order"] = override["order"]
        if override.get("validation") is not None:
            merged_field["validation"] = {
                **merged_field.get("validation", {}),
                **override["validation"]
            }
        if override.get("options") is not None:
            merged_field["options"] = override["options"]
        
        merged_fields.append(merged_field)
    
    # Sort by order
    merged_fields.sort(key=lambda f: f.get("order", 0))
    
    return {
        **base_schema,
        "fields": merged_fields,
        "has_customizations": True,
        "customized_at": customizations.get("updated_at"),
        "schema_version": customizations.get("schema_version", 1),
    }


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/services")
async def list_configurable_services(
    current_user: dict = Depends(admin_route_guard)
):
    """List all services with their intake schema configuration status."""
    services = []
    
    for service_code in SERVICE_INTAKE_SCHEMAS.keys():
        customizations = await get_live_customizations(service_code)
        has_customizations = bool(customizations.get("field_overrides"))
        has_draft = bool(customizations.get("has_draft"))
        
        base_schema = get_service_schema(service_code)
        field_count = len(base_schema.get("fields", []))
        
        services.append({
            "service_code": service_code,
            "field_count": field_count,
            "has_customizations": has_customizations,
            "has_draft": has_draft,
            "schema_version": customizations.get("schema_version", 0),
            "customized_at": customizations.get("updated_at"),
            "customized_by": customizations.get("updated_by"),
            "draft_updated_at": customizations.get("draft_updated_at"),
            "published_at": customizations.get("published_at"),
        })
    
    return {
        "services": services,
        "total": len(services)
    }


@router.get("/{service_code}")
async def get_schema_editor(
    service_code: str,
    draft: bool = True,
    current_user: dict = Depends(admin_route_guard)
):
    """
    Get complete schema for editing.
    Returns both base schema and any customizations.
    """
    if service_code not in SERVICE_INTAKE_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    base_schema = get_service_schema(service_code)
    customizations = await get_customizations(service_code, draft=draft)
    
    # Build editor view with override status per field
    editor_fields = []
    
    # Get the right overrides based on draft flag
    field_overrides = customizations.get("draft_overrides", customizations.get("field_overrides", [])) if draft else customizations.get("field_overrides", [])
    override_map = {
        o["field_key"]: o 
        for o in field_overrides
    }
    
    for field in base_schema.get("fields", []):
        field_key = field["field_key"]
        override = override_map.get(field_key, {})
        
        editor_fields.append({
            "base": field,
            "override": override if override else None,
            "has_override": bool(override),
            "is_hidden": override.get("hidden", False),
        })
    
    return {
        "service_code": service_code,
        "schema_version": customizations.get("schema_version", 0),
        "fields": editor_fields,
        "field_groups": base_schema.get("field_groups", {}),
        "supports_uploads": base_schema.get("supports_uploads", False),
        "supports_fast_track": base_schema.get("supports_fast_track", False),
        "supports_printed_copy": base_schema.get("supports_printed_copy", False),
        "customizations_meta": {
            "has_customizations": bool(customizations.get("field_overrides")),
            "has_draft": bool(customizations.get("has_draft")),
            "updated_at": customizations.get("updated_at"),
            "updated_by": customizations.get("updated_by"),
            "draft_updated_at": customizations.get("draft_updated_at"),
            "draft_updated_by": customizations.get("draft_updated_by"),
            "published_at": customizations.get("published_at"),
            "published_by": customizations.get("published_by"),
        },
        "is_viewing_draft": draft,
        "available_field_types": [t.value for t in IntakeFieldType],
    }


@router.put("/{service_code}")
async def save_schema_overrides(
    service_code: str,
    request: SaveSchemaOverridesRequest,
    current_user: dict = Depends(admin_route_guard)
):
    """
    Save schema customizations for a service.
    By default saves as draft. Set is_draft=false to save directly to live.
    """
    if service_code not in SERVICE_INTAKE_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    if request.service_code != service_code:
        raise HTTPException(status_code=400, detail="Service code mismatch")
    
    # Filter out empty overrides (only save fields with actual changes)
    valid_overrides = []
    for override in request.field_overrides:
        has_changes = any([
            override.label is not None,
            override.helper_text is not None,
            override.placeholder is not None,
            override.required is not None,
            override.order is not None,
            override.hidden,
            override.validation is not None,
            override.options is not None,
        ])
        
        if has_changes:
            valid_overrides.append(override.model_dump(exclude_none=True))
    
    new_version = await save_customizations(
        service_code=service_code,
        overrides=valid_overrides,
        updated_by=current_user.get("email", "admin"),
        is_draft=request.is_draft
    )
    
    logger.info(f"Schema overrides saved for {service_code} by {current_user.get('email')} (draft={request.is_draft})")
    
    return {
        "success": True,
        "message": f"Schema {'draft ' if request.is_draft else ''}saved for {service_code}",
        "overrides_count": len(valid_overrides),
        "schema_version": new_version,
        "is_draft": request.is_draft,
    }


@router.post("/{service_code}/publish")
async def publish_schema_to_live(
    service_code: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Publish draft schema to live."""
    if service_code not in SERVICE_INTAKE_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    new_version = await publish_schema(
        service_code=service_code,
        published_by=current_user.get("email", "admin")
    )
    
    logger.info(f"Schema published for {service_code} by {current_user.get('email')}")
    
    return {
        "success": True,
        "message": f"Schema published to live for {service_code}",
        "schema_version": new_version,
    }


@router.post("/{service_code}/discard-draft")
async def discard_draft(
    service_code: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Discard draft changes without publishing."""
    if service_code not in SERVICE_INTAKE_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    await db[COLLECTION].update_one(
        {"service_code": service_code},
        {
            "$unset": {"draft_overrides": 1, "draft_updated_at": 1, "draft_updated_by": 1},
            "$set": {"has_draft": False}
        }
    )
    
    # Audit log
    await db["audit_logs"].insert_one({
        "action": "INTAKE_SCHEMA_DRAFT_DISCARDED",
        "actor_type": "admin",
        "actor_id": current_user.get("email"),
        "resource_type": "intake_schema",
        "resource_id": service_code,
        "details": {},
        "created_at": now,
    })
    
    return {"success": True, "message": "Draft discarded"}


@router.get("/{service_code}/versions")
async def get_version_history(
    service_code: str,
    limit: int = 20,
    current_user: dict = Depends(admin_route_guard)
):
    """Get version history for a schema."""
    if service_code not in SERVICE_INTAKE_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    db = database.get_db()
    cursor = db[VERSIONS_COLLECTION].find(
        {"service_code": service_code},
        {"_id": 0}
    ).sort("version", -1).limit(limit)
    
    versions = await cursor.to_list(length=limit)
    
    return {
        "service_code": service_code,
        "versions": versions,
        "total": len(versions)
    }


@router.post("/{service_code}/rollback/{version}")
async def rollback_to_version(
    service_code: str,
    version: int,
    current_user: dict = Depends(admin_route_guard)
):
    """Rollback schema to a specific version."""
    if service_code not in SERVICE_INTAKE_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    # Find the version to rollback to
    target_version = await db[VERSIONS_COLLECTION].find_one(
        {"service_code": service_code, "version": version},
        {"_id": 0}
    )
    
    if not target_version:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")
    
    # Get current state for audit
    current = await db[COLLECTION].find_one({"service_code": service_code}, {"_id": 0})
    before_state = current.get("field_overrides", []) if current else []
    
    # Apply rollback
    rollback_overrides = target_version.get("field_overrides", [])
    
    await db[COLLECTION].update_one(
        {"service_code": service_code},
        {
            "$set": {
                "field_overrides": rollback_overrides,
                "updated_at": now,
                "updated_by": current_user.get("email"),
                "has_draft": False,
                "rollback_from_version": version,
            },
            "$unset": {"draft_overrides": 1},
            "$inc": {"schema_version": 1}
        }
    )
    
    # Get new version
    updated = await db[COLLECTION].find_one({"service_code": service_code}, {"_id": 0})
    new_version = updated.get("schema_version", 1)
    
    # Create version entry
    await db[VERSIONS_COLLECTION].insert_one({
        "service_code": service_code,
        "version": new_version,
        "is_draft": False,
        "field_overrides": rollback_overrides,
        "before_state": before_state,
        "after_state": rollback_overrides,
        "created_at": now,
        "created_by": current_user.get("email"),
        "action": f"rollback_to_v{version}",
    })
    
    # Audit log
    await db["audit_logs"].insert_one({
        "action": "INTAKE_SCHEMA_ROLLBACK",
        "actor_type": "admin",
        "actor_id": current_user.get("email"),
        "resource_type": "intake_schema",
        "resource_id": service_code,
        "details": {
            "rolled_back_to_version": version,
            "new_version": new_version,
            "before_state": json.dumps(before_state, default=str)[:5000],
            "after_state": json.dumps(rollback_overrides, default=str)[:5000],
        },
        "created_at": now,
    })
    
    logger.info(f"Schema rolled back to v{version} for {service_code} by {current_user.get('email')}")
    
    return {
        "success": True,
        "message": f"Rolled back to version {version}",
        "new_version": new_version,
    }


@router.post("/{service_code}/reset")
async def reset_schema(
    service_code: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Reset a service schema to defaults (remove all customizations)."""
    if service_code not in SERVICE_INTAKE_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    # Get current for audit
    current = await db[COLLECTION].find_one({"service_code": service_code}, {"_id": 0})
    before_state = current.get("field_overrides", []) if current else []
    
    result = await db[COLLECTION].delete_one({"service_code": service_code})
    
    if result.deleted_count > 0:
        # Audit log
        await db["audit_logs"].insert_one({
            "action": "INTAKE_SCHEMA_RESET",
            "actor_type": "admin",
            "actor_id": current_user.get("email"),
            "resource_type": "intake_schema",
            "resource_id": service_code,
            "details": {
                "before_state": json.dumps(before_state, default=str)[:5000],
            },
            "created_at": now,
        })
        
        logger.info(f"Schema reset for {service_code} by {current_user.get('email')}")
        return {
            "success": True,
            "message": f"Schema reset to defaults for {service_code}"
        }
    else:
        return {
            "success": True,
            "message": "No customizations found to reset"
        }


@router.get("/{service_code}/preview")
async def preview_customized_schema(
    service_code: str,
    draft: bool = False,
    current_user: dict = Depends(admin_route_guard)
):
    """Preview the merged schema with customizations applied."""
    if service_code not in SERVICE_INTAKE_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    base_schema = get_service_schema(service_code)
    customizations = await get_customizations(service_code, draft=draft)
    merged = merge_schema_with_overrides(base_schema, customizations)
    
    return {
        **merged,
        "is_preview": True,
        "is_draft_preview": draft,
    }


# ============================================================================
# PUBLIC ENDPOINT (for intake wizard to fetch customized schema)
# ============================================================================

async def get_customized_schema(service_code: str) -> Dict[str, Any]:
    """
    Public function to get schema with LIVE customizations applied.
    Used by the intake wizard routes.
    """
    if service_code not in SERVICE_INTAKE_SCHEMAS:
        return None
    
    base_schema = get_service_schema(service_code)
    customizations = await get_live_customizations(service_code)  # Only live, not draft
    
    return merge_schema_with_overrides(base_schema, customizations)
