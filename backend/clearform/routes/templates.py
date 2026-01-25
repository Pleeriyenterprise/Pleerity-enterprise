"""ClearForm Template Routes

API endpoints for templates, rule packs, and template-based generation.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging

from clearform.services.clearform_auth import get_current_clearform_user
from clearform.services.template_service import template_service
from clearform.models.rule_packs import GenerationMode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["ClearForm Templates"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class TemplateGenerationRequest(BaseModel):
    """Request to generate document from template."""
    template_id: str
    data: Dict[str, Any]
    profile_id: Optional[str] = None


class PreFillRequest(BaseModel):
    """Request to get pre-filled data for a template."""
    template_id: str
    profile_id: Optional[str] = None


# ============================================================================
# TEMPLATE ENDPOINTS
# ============================================================================

@router.get("")
async def list_templates(
    document_type: Optional[str] = None,
    current_user: dict = Depends(get_current_clearform_user),
):
    """List available document templates."""
    templates = await template_service.get_available_templates(document_type)
    return {"templates": templates}


@router.get("/{template_id}")
async def get_template(
    template_id: str,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get template details including sections and placeholders."""
    details = await template_service.get_template_details(template_id)
    if not details:
        raise HTTPException(status_code=404, detail="Template not found")
    return details


@router.post("/generate")
async def generate_from_template(
    request: TemplateGenerationRequest,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Generate a document using a template.
    
    This uses deterministic or hybrid generation based on template settings.
    """
    try:
        document = await template_service.generate_from_template(
            user_id=current_user["user_id"],
            template_id=request.template_id,
            data=request.data,
            profile_id=request.profile_id,
        )
        
        return {
            "document_id": document.document_id,
            "title": document.title,
            "status": document.status.value,
            "credits_used": document.credits_used,
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Template generation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate document")


@router.post("/prefill")
async def get_prefilled_data(
    request: PreFillRequest,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get pre-filled placeholder values for a template.
    
    Uses the specified profile (or default profile) to pre-fill
    template placeholders.
    """
    from clearform.models.rule_packs import get_template
    
    template = get_template(request.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    prefilled = {}
    
    # Get profile
    if request.profile_id:
        profile = await template_service._get_profile(
            current_user["user_id"],
            request.profile_id
        )
    else:
        profile = await template_service.get_default_profile(current_user["user_id"])
    
    if profile:
        prefilled = template_service.apply_profile_to_template(template, profile)
    
    # Return template sections with prefilled values
    sections_with_prefill = []
    for section in template.sections:
        section_data = {
            "section_id": section.section_id,
            "section_type": section.section_type.value,
            "name": section.name,
            "order": section.order,
            "is_ai_enhanced": section.is_ai_enhanced,
            "placeholders": [],
        }
        
        for placeholder in section.placeholders:
            section_data["placeholders"].append({
                "key": placeholder.key,
                "label": placeholder.label,
                "field_type": placeholder.field_type,
                "required": placeholder.required,
                "default_value": placeholder.default_value,
                "prefilled_value": prefilled.get(placeholder.key),
            })
        
        sections_with_prefill.append(section_data)
    
    return {
        "template_id": template.template_id,
        "template_name": template.name,
        "generation_mode": template.generation_mode.value,
        "sections": sections_with_prefill,
        "profile_used": profile.profile_id if profile else None,
    }


# ============================================================================
# RULE PACK ENDPOINTS
# ============================================================================

@router.get("/rule-packs")
async def list_rule_packs(
    document_type: Optional[str] = None,
    current_user: dict = Depends(get_current_clearform_user),
):
    """List available compliance rule packs."""
    packs = await template_service.get_rule_packs(document_type)
    return {"rule_packs": packs}


@router.get("/rule-packs/{pack_id}")
async def get_rule_pack(
    pack_id: str,
    current_user: dict = Depends(get_current_clearform_user),
):
    """Get rule pack details including sections and validation rules."""
    from clearform.models.rule_packs import get_rule_pack as get_pack
    
    pack = get_pack(pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Rule pack not found")
    
    return {
        "pack_id": pack.pack_id,
        "name": pack.name,
        "description": pack.description,
        "category": pack.category.value,
        "document_types": pack.document_types,
        "compliance_standard": pack.compliance_standard,
        "legal_disclaimer": pack.legal_disclaimer,
        "required_sections": [s.model_dump() for s in pack.required_sections],
        "validation_rules": [r.model_dump() for r in pack.validation_rules],
    }


# ============================================================================
# PROFILE ENDPOINTS (for document creation)
# ============================================================================

@router.get("/profiles")
async def list_profiles(
    current_user: dict = Depends(get_current_clearform_user),
):
    """List user's smart profiles for auto-fill."""
    profiles = await template_service.get_user_profiles(current_user["user_id"])
    
    return {
        "profiles": [
            {
                "profile_id": p.profile_id,
                "name": p.name,
                "profile_type": p.profile_type,
                "is_default": p.is_default,
                "full_name": p.full_name,
                "email": p.email,
            }
            for p in profiles
        ]
    }
