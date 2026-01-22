"""
Admin Service Catalogue V2 Routes - Enterprise-grade CRUD operations.

This is the admin API for managing the authoritative Service Catalogue.
All services MUST be defined in the catalogue - if not here, not executable.

HARD RULE: CVP BOUNDARY
- CVP remains isolated - no changes to CVP collections
- CVP documents = reports only
- Legal/operational documents flow through Orders only
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from middleware import admin_route_guard
from services.service_catalogue_v2 import (
    service_catalogue_v2,
    ServiceCatalogueEntryV2,
    ServiceCategory,
    PricingModel,
    ProductType,
    DeliveryType,
    GenerationMode,
    PackTier,
    PricingVariant,
    DocumentTemplate,
    IntakeFieldSchema,
    IntakeFieldType,
)
from services.service_definitions_v2 import (
    seed_service_catalogue_v2,
    clear_and_reseed_catalogue,
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/services/v2", tags=["admin-services-v2"])


# ============================================================================
# REQUEST MODELS
# ============================================================================

class PricingVariantRequest(BaseModel):
    """Pricing variant for create/update requests."""
    variant_code: str
    variant_name: str
    price_amount: int
    stripe_price_id: str
    target_due_hours: int = 72
    is_addon: bool = False
    addon_type: Optional[str] = None


class DocumentTemplateRequest(BaseModel):
    """Document template for create/update requests."""
    template_code: str
    template_name: str
    format: str = "docx"
    generation_order: int = 0
    gpt_sections: List[str] = []
    is_optional: bool = False


class IntakeFieldRequest(BaseModel):
    """Intake field for create/update requests."""
    field_id: str
    label: str
    field_type: str  # IntakeFieldType value
    required: bool = True
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    options: Optional[List[str]] = None
    validation_regex: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    default_value: Optional[Any] = None
    order: int = 0
    conditional_on: Optional[str] = None
    conditional_value: Optional[Any] = None


class CreateServiceRequest(BaseModel):
    """Request model for creating a service."""
    service_code: str = Field(..., min_length=3, max_length=50)
    service_name: str = Field(..., min_length=3, max_length=100)
    description: str
    long_description: Optional[str] = None
    icon: Optional[str] = None
    
    category: str  # ServiceCategory value
    tags: List[str] = []
    
    website_preview: Optional[str] = None
    learn_more_slug: Optional[str] = None
    
    pricing_model: str  # PricingModel value
    base_price: int = 0
    price_currency: str = "gbp"
    vat_rate: float = 0.20
    
    pricing_variants: List[PricingVariantRequest] = []
    
    fast_track_available: bool = False
    fast_track_price: int = 2000
    fast_track_hours: int = 24
    
    printed_copy_available: bool = False
    printed_copy_price: int = 2500
    
    delivery_type: str = "digital"  # DeliveryType value
    standard_turnaround_hours: int = 72
    delivery_format: str = "digital"
    
    workflow_name: str
    product_type: str = "one_time"  # ProductType value
    
    documents_generated: List[DocumentTemplateRequest] = []
    
    pack_tier: Optional[str] = None  # PackTier value
    includes_lower_tiers: bool = False
    parent_pack_code: Optional[str] = None
    
    intake_fields: List[IntakeFieldRequest] = []
    
    generation_mode: str = "TEMPLATE_MERGE"  # GenerationMode value
    master_prompt_id: Optional[str] = None
    gpt_sections: List[str] = []
    
    review_required: bool = True
    
    requires_cvp_subscription: bool = False
    is_cvp_feature: bool = False
    allowed_plans: List[str] = []
    
    active: bool = True
    display_order: int = 0


class UpdateServiceRequest(BaseModel):
    """Request model for updating a service."""
    service_name: Optional[str] = None
    description: Optional[str] = None
    long_description: Optional[str] = None
    icon: Optional[str] = None
    
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    
    website_preview: Optional[str] = None
    learn_more_slug: Optional[str] = None
    
    pricing_model: Optional[str] = None
    base_price: Optional[int] = None
    price_currency: Optional[str] = None
    vat_rate: Optional[float] = None
    
    pricing_variants: Optional[List[PricingVariantRequest]] = None
    
    fast_track_available: Optional[bool] = None
    fast_track_price: Optional[int] = None
    fast_track_hours: Optional[int] = None
    
    printed_copy_available: Optional[bool] = None
    printed_copy_price: Optional[int] = None
    
    delivery_type: Optional[str] = None
    standard_turnaround_hours: Optional[int] = None
    delivery_format: Optional[str] = None
    
    workflow_name: Optional[str] = None
    product_type: Optional[str] = None
    
    documents_generated: Optional[List[DocumentTemplateRequest]] = None
    
    pack_tier: Optional[str] = None
    includes_lower_tiers: Optional[bool] = None
    parent_pack_code: Optional[str] = None
    
    intake_fields: Optional[List[IntakeFieldRequest]] = None
    
    generation_mode: Optional[str] = None
    master_prompt_id: Optional[str] = None
    gpt_sections: Optional[List[str]] = None
    
    review_required: Optional[bool] = None
    
    requires_cvp_subscription: Optional[bool] = None
    is_cvp_feature: Optional[bool] = None
    allowed_plans: Optional[List[str]] = None
    
    active: Optional[bool] = None
    display_order: Optional[int] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/")
async def list_services(
    category: Optional[str] = None,
    include_inactive: bool = False,
    current_user: dict = Depends(admin_route_guard),
):
    """List all services in the catalogue V2."""
    cat = ServiceCategory(category) if category else None
    services = await service_catalogue_v2.list_services(
        category=cat,
        active_only=not include_inactive,
    )
    
    return {
        "services": [s.to_dict() for s in services],
        "total": len(services),
    }


@router.get("/categories")
async def get_categories(
    current_user: dict = Depends(admin_route_guard),
):
    """Get available enums for service configuration."""
    return {
        "categories": [
            {"value": c.value, "label": c.value.replace("_", " ").title()}
            for c in ServiceCategory
        ],
        "pricing_models": [
            {"value": p.value, "label": p.value.replace("_", " ").title()}
            for p in PricingModel
        ],
        "delivery_types": [
            {"value": d.value, "label": d.value.replace("+", " & ").replace("_", " ").title()}
            for d in DeliveryType
        ],
        "generation_modes": [
            {"value": g.value, "label": g.value.replace("_", " ").title()}
            for g in GenerationMode
        ],
        "pack_tiers": [
            {"value": t.value, "label": t.value}
            for t in PackTier
        ],
        "product_types": [
            {"value": t.value, "label": t.value.replace("_", " ").title()}
            for t in ProductType
        ],
        "intake_field_types": [
            {"value": t.value, "label": t.value.replace("_", " ").title()}
            for t in IntakeFieldType
        ],
    }


@router.get("/stats")
async def get_catalogue_stats(
    current_user: dict = Depends(admin_route_guard),
):
    """Get service catalogue statistics."""
    stats = {}
    
    for cat in ServiceCategory:
        count = await service_catalogue_v2.count_services(category=cat, active_only=True)
        stats[cat.value] = count
    
    total = await service_catalogue_v2.count_services(active_only=True)
    inactive = await service_catalogue_v2.count_services(active_only=False) - total
    
    return {
        "total_active": total,
        "total_inactive": inactive,
        "by_category": stats,
    }


@router.get("/document-packs")
async def list_document_packs(
    current_user: dict = Depends(admin_route_guard),
):
    """List document packs in tier order (Essential → Plus → Pro)."""
    packs = await service_catalogue_v2.list_document_packs(active_only=False)
    
    return {
        "packs": [p.to_dict() for p in packs],
        "total": len(packs),
    }


@router.get("/{service_code}")
async def get_service(
    service_code: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Get a single service by code."""
    service = await service_catalogue_v2.get_service(service_code)
    
    if not service:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    return service.to_dict()


@router.get("/{service_code}/documents")
async def get_service_documents(
    service_code: str,
    include_inherited: bool = True,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Get documents for a service.
    For document packs, optionally includes documents from lower tiers.
    """
    if include_inherited:
        documents = await service_catalogue_v2.get_pack_documents(service_code)
    else:
        service = await service_catalogue_v2.get_service(service_code)
        if not service:
            raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
        documents = service.documents_generated
    
    return {
        "service_code": service_code,
        "documents": [d.model_dump() for d in documents],
        "total": len(documents),
        "includes_inherited": include_inherited,
    }


@router.get("/{service_code}/price")
async def calculate_price(
    service_code: str,
    fast_track: bool = False,
    printed_copy: bool = False,
    current_user: dict = Depends(admin_route_guard),
):
    """Calculate price for a service with add-ons."""
    price = await service_catalogue_v2.calculate_order_price(
        service_code=service_code,
        fast_track=fast_track,
        printed_copy=printed_copy,
    )
    
    if not price:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    return price


@router.post("/")
async def create_service(
    request: CreateServiceRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """Create a new service in the catalogue."""
    try:
        # Convert request to entry
        entry = ServiceCatalogueEntryV2(
            service_code=request.service_code.upper(),
            service_name=request.service_name,
            description=request.description,
            long_description=request.long_description,
            icon=request.icon,
            category=ServiceCategory(request.category),
            tags=request.tags,
            website_preview=request.website_preview,
            learn_more_slug=request.learn_more_slug,
            pricing_model=PricingModel(request.pricing_model),
            base_price=request.base_price,
            price_currency=request.price_currency,
            vat_rate=request.vat_rate,
            pricing_variants=[PricingVariant(**v.model_dump()) for v in request.pricing_variants],
            fast_track_available=request.fast_track_available,
            fast_track_price=request.fast_track_price,
            fast_track_hours=request.fast_track_hours,
            printed_copy_available=request.printed_copy_available,
            printed_copy_price=request.printed_copy_price,
            delivery_type=DeliveryType(request.delivery_type),
            standard_turnaround_hours=request.standard_turnaround_hours,
            delivery_format=request.delivery_format,
            workflow_name=request.workflow_name,
            product_type=ProductType(request.product_type),
            documents_generated=[DocumentTemplate(**d.model_dump()) for d in request.documents_generated],
            pack_tier=PackTier(request.pack_tier) if request.pack_tier else None,
            includes_lower_tiers=request.includes_lower_tiers,
            parent_pack_code=request.parent_pack_code,
            intake_fields=[
                IntakeFieldSchema(
                    field_id=f.field_id,
                    label=f.label,
                    field_type=IntakeFieldType(f.field_type),
                    required=f.required,
                    placeholder=f.placeholder,
                    help_text=f.help_text,
                    options=f.options,
                    validation_regex=f.validation_regex,
                    min_value=f.min_value,
                    max_value=f.max_value,
                    default_value=f.default_value,
                    order=f.order,
                    conditional_on=f.conditional_on,
                    conditional_value=f.conditional_value,
                )
                for f in request.intake_fields
            ],
            generation_mode=GenerationMode(request.generation_mode),
            master_prompt_id=request.master_prompt_id,
            gpt_sections=request.gpt_sections,
            review_required=request.review_required,
            requires_cvp_subscription=request.requires_cvp_subscription,
            is_cvp_feature=request.is_cvp_feature,
            allowed_plans=request.allowed_plans,
            active=request.active,
            display_order=request.display_order,
        )
        
        created = await service_catalogue_v2.create_service(
            entry=entry,
            created_by=current_user.get("email"),
        )
        
        return {
            "success": True,
            "service": created.to_dict(),
            "message": f"Service {request.service_code} created successfully",
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{service_code}")
async def update_service(
    service_code: str,
    request: UpdateServiceRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """Update a service. service_code cannot be changed."""
    # Build updates dict, excluding None values
    updates = {}
    for field, value in request.model_dump().items():
        if value is not None:
            updates[field] = value
    
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    # Convert nested models if present
    if "pricing_variants" in updates:
        updates["pricing_variants"] = [
            v if isinstance(v, dict) else v.model_dump()
            for v in updates["pricing_variants"]
        ]
    if "documents_generated" in updates:
        updates["documents_generated"] = [
            d if isinstance(d, dict) else d.model_dump()
            for d in updates["documents_generated"]
        ]
    if "intake_fields" in updates:
        updates["intake_fields"] = [
            f if isinstance(f, dict) else f.model_dump()
            for f in updates["intake_fields"]
        ]
    
    updated = await service_catalogue_v2.update_service(
        service_code=service_code,
        updates=updates,
        updated_by=current_user.get("email"),
    )
    
    if not updated:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    return {
        "success": True,
        "service": updated.to_dict(),
        "message": f"Service {service_code} updated successfully",
    }


@router.post("/{service_code}/activate")
async def activate_service(
    service_code: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Activate a service."""
    success = await service_catalogue_v2.activate_service(
        service_code=service_code,
        updated_by=current_user.get("email"),
    )
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    return {
        "success": True,
        "message": f"Service {service_code} activated",
    }


@router.post("/{service_code}/deactivate")
async def deactivate_service(
    service_code: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Deactivate a service (soft delete)."""
    success = await service_catalogue_v2.deactivate_service(
        service_code=service_code,
        updated_by=current_user.get("email"),
    )
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    return {
        "success": True,
        "message": f"Service {service_code} deactivated",
    }


@router.post("/seed")
async def seed_services(
    current_user: dict = Depends(admin_route_guard),
):
    """Seed the service catalogue with authoritative service definitions."""
    result = await seed_service_catalogue_v2()
    
    return {
        "success": True,
        "message": "Service catalogue V2 seeded successfully",
        "created": result["created"],
        "skipped": result["skipped"],
    }


@router.post("/reseed")
async def reseed_services(
    confirm: bool = Query(False, description="Must be true to confirm destructive action"),
    current_user: dict = Depends(admin_route_guard),
):
    """
    Clear and reseed the entire catalogue.
    DESTRUCTIVE - use with caution! Requires confirm=true.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="This is a destructive action. Pass confirm=true to proceed."
        )
    
    result = await clear_and_reseed_catalogue()
    
    return {
        "success": True,
        "message": "Service catalogue V2 cleared and reseeded",
        "created": result["created"],
        "skipped": result["skipped"],
    }
