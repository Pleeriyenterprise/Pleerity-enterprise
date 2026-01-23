"""
Admin Intake Schema Management Routes

Provides APIs for admins to customize intake wizard form fields:
- Edit field labels, helper text, placeholders
- Modify validation rules
- Reorder fields
- Toggle field visibility/required status

Schema customizations are stored in MongoDB and merged with base schemas.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from middleware import admin_route_guard
from database import db
from services.intake_schema_registry import (
    get_service_schema,
    SERVICE_INTAKE_SCHEMAS,
    IntakeFieldType,
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/intake-schema", tags=["admin-intake-schema"])

# Collection for custom field overrides
COLLECTION = "intake_schema_customizations"


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


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def get_customizations(service_code: str) -> Dict[str, Any]:
    """Get stored customizations for a service."""
    doc = await db[COLLECTION].find_one(
        {"service_code": service_code},
        {"_id": 0}
    )
    return doc or {}


async def save_customizations(
    service_code: str,
    overrides: List[Dict],
    updated_by: str
):
    """Save schema customizations for a service."""
    now = datetime.now(timezone.utc).isoformat()
    
    await db[COLLECTION].update_one(
        {"service_code": service_code},
        {
            "$set": {
                "service_code": service_code,
                "field_overrides": overrides,
                "updated_at": now,
                "updated_by": updated_by,
            },
            "$setOnInsert": {
                "created_at": now,
            }
        },
        upsert=True
    )


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
        customizations = await get_customizations(service_code)
        has_customizations = bool(customizations.get("field_overrides"))
        
        base_schema = get_service_schema(service_code)
        field_count = len(base_schema.get("fields", []))
        
        services.append({
            "service_code": service_code,
            "field_count": field_count,
            "has_customizations": has_customizations,
            "customized_at": customizations.get("updated_at"),
            "customized_by": customizations.get("updated_by"),
        })
    
    return {
        "services": services,
        "total": len(services)
    }


@router.get("/{service_code}")
async def get_schema_editor(
    service_code: str,
    current_user: dict = Depends(admin_route_guard)
):
    """
    Get complete schema for editing.
    Returns both base schema and any customizations.
    """
    if service_code not in SERVICE_INTAKE_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    base_schema = get_service_schema(service_code)
    customizations = await get_customizations(service_code)
    
    # Build editor view with override status per field
    editor_fields = []
    override_map = {
        o["field_key"]: o 
        for o in customizations.get("field_overrides", [])
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
        "schema_version": base_schema.get("schema_version", "1.0"),
        "fields": editor_fields,
        "field_groups": base_schema.get("field_groups", {}),
        "supports_uploads": base_schema.get("supports_uploads", False),
        "supports_fast_track": base_schema.get("supports_fast_track", False),
        "supports_printed_copy": base_schema.get("supports_printed_copy", False),
        "customizations_meta": {
            "has_customizations": bool(customizations.get("field_overrides")),
            "updated_at": customizations.get("updated_at"),
            "updated_by": customizations.get("updated_by"),
        },
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
    Only fields with actual overrides should be included.
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
    
    await save_customizations(
        service_code=service_code,
        overrides=valid_overrides,
        updated_by=current_user.get("email", "admin")
    )
    
    logger.info(f"Schema overrides saved for {service_code} by {current_user.get('email')}")
    
    return {
        "success": True,
        "message": f"Schema customizations saved for {service_code}",
        "overrides_count": len(valid_overrides)
    }


@router.post("/{service_code}/reset")
async def reset_schema(
    service_code: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Reset a service schema to defaults (remove all customizations)."""
    if service_code not in SERVICE_INTAKE_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    result = await db[COLLECTION].delete_one({"service_code": service_code})
    
    if result.deleted_count > 0:
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
    current_user: dict = Depends(admin_route_guard)
):
    """Preview the merged schema with customizations applied."""
    if service_code not in SERVICE_INTAKE_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    base_schema = get_service_schema(service_code)
    customizations = await get_customizations(service_code)
    merged = merge_schema_with_overrides(base_schema, customizations)
    
    return merged


# ============================================================================
# PUBLIC ENDPOINT (for intake wizard to fetch customized schema)
# ============================================================================

async def get_customized_schema(service_code: str) -> Dict[str, Any]:
    """
    Public function to get schema with customizations applied.
    Used by the intake wizard routes.
    """
    if service_code not in SERVICE_INTAKE_SCHEMAS:
        return None
    
    base_schema = get_service_schema(service_code)
    customizations = await get_customizations(service_code)
    
    return merge_schema_with_overrides(base_schema, customizations)
