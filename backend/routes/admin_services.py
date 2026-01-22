"""
Admin Service Catalogue Routes - CRUD operations for the Service Catalogue.
All services MUST be defined in the catalogue - no hard-coded service logic.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from middleware import admin_route_guard
from services.service_catalogue import (
    service_catalogue,
    ServiceCatalogueEntry,
    ServiceCategory,
    PricingModel,
    DeliveryType,
    GenerationMode,
    IntakeFieldSchema,
    DocumentDefinition,
    seed_service_catalogue,
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/services", tags=["admin-services"])


# ============================================================================
# REQUEST MODELS
# ============================================================================

class CreateServiceRequest(BaseModel):
    service_code: str = Field(..., min_length=3, max_length=50)
    service_name: str = Field(..., min_length=3, max_length=100)
    description: str
    short_description: Optional[str] = None
    icon: Optional[str] = None
    
    category: str  # ServiceCategory value
    tags: List[str] = []
    
    pricing_model: str  # PricingModel value
    price_amount: int = 0
    price_currency: str = "gbp"
    stripe_price_id: Optional[str] = None
    vat_rate: float = 0.20
    
    delivery_type: str  # DeliveryType value
    estimated_turnaround_hours: int = 24
    delivery_format: str = "single_pdf"
    
    documents_generated: List[Dict[str, Any]] = []
    intake_fields: List[Dict[str, Any]] = []
    
    review_required: bool = True
    generation_mode: str = "TEMPLATE_ONLY"
    master_prompt_version: Optional[str] = None
    
    requires_cvp_subscription: bool = False
    allowed_plans: List[str] = []
    
    active: bool = True
    display_order: int = 0


class UpdateServiceRequest(BaseModel):
    service_name: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    icon: Optional[str] = None
    
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    
    pricing_model: Optional[str] = None
    price_amount: Optional[int] = None
    price_currency: Optional[str] = None
    stripe_price_id: Optional[str] = None
    vat_rate: Optional[float] = None
    
    delivery_type: Optional[str] = None
    estimated_turnaround_hours: Optional[int] = None
    delivery_format: Optional[str] = None
    
    documents_generated: Optional[List[Dict[str, Any]]] = None
    intake_fields: Optional[List[Dict[str, Any]]] = None
    
    review_required: Optional[bool] = None
    generation_mode: Optional[str] = None
    master_prompt_version: Optional[str] = None
    
    requires_cvp_subscription: Optional[bool] = None
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
    """
    List all services in the catalogue.
    Admin can see inactive services.
    """
    cat = ServiceCategory(category) if category else None
    services = await service_catalogue.list_services(
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
    """Get available service categories."""
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
    }


@router.get("/{service_code}")
async def get_service(
    service_code: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Get a single service by code."""
    service = await service_catalogue.get_service(service_code)
    
    if not service:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    return service.to_dict()


@router.post("/")
async def create_service(
    request: CreateServiceRequest,
    current_user: dict = Depends(admin_route_guard),
):
    """
    Create a new service in the catalogue.
    service_code is immutable after creation.
    """
    try:
        # Convert to ServiceCatalogueEntry
        entry = ServiceCatalogueEntry(
            service_code=request.service_code.upper(),
            service_name=request.service_name,
            description=request.description,
            short_description=request.short_description,
            icon=request.icon,
            category=ServiceCategory(request.category),
            tags=request.tags,
            pricing_model=PricingModel(request.pricing_model),
            price_amount=request.price_amount,
            price_currency=request.price_currency,
            stripe_price_id=request.stripe_price_id,
            vat_rate=request.vat_rate,
            delivery_type=DeliveryType(request.delivery_type),
            estimated_turnaround_hours=request.estimated_turnaround_hours,
            delivery_format=request.delivery_format,
            documents_generated=[DocumentDefinition(**d) for d in request.documents_generated],
            intake_fields=[IntakeFieldSchema(**f) for f in request.intake_fields],
            review_required=request.review_required,
            generation_mode=GenerationMode(request.generation_mode),
            master_prompt_version=request.master_prompt_version,
            requires_cvp_subscription=request.requires_cvp_subscription,
            allowed_plans=request.allowed_plans,
            active=request.active,
            display_order=request.display_order,
        )
        
        created = await service_catalogue.create_service(
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
    """
    Update a service.
    Note: service_code cannot be changed (immutable).
    """
    # Build updates dict, excluding None values
    updates = {}
    for field, value in request.model_dump().items():
        if value is not None:
            updates[field] = value
    
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    # Convert documents and intake_fields if present
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
    
    updated = await service_catalogue.update_service(
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
    success = await service_catalogue.activate_service(
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
    success = await service_catalogue.deactivate_service(
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
    """Seed the service catalogue with default services."""
    await seed_service_catalogue()
    
    return {
        "success": True,
        "message": "Service catalogue seeded successfully",
    }


# ============================================================================
# PUBLIC ENDPOINTS (for service display on public pages)
# ============================================================================

@router.get("/public/list")
async def list_public_services(
    category: Optional[str] = None,
):
    """
    List active services for public display.
    No authentication required.
    """
    cat = ServiceCategory(category) if category else None
    services = await service_catalogue.list_services(
        category=cat,
        active_only=True,
    )
    
    # Return only public-safe fields
    public_services = []
    for s in services:
        public_services.append({
            "service_code": s.service_code,
            "service_name": s.service_name,
            "description": s.description,
            "short_description": s.short_description,
            "category": s.category.value,
            "pricing_model": s.pricing_model.value,
            "price_amount": s.price_amount,
            "price_currency": s.price_currency,
            "vat_rate": s.vat_rate,
            "delivery_type": s.delivery_type.value,
            "estimated_turnaround_hours": s.estimated_turnaround_hours,
            "requires_cvp_subscription": s.requires_cvp_subscription,
            "display_order": s.display_order,
        })
    
    return {
        "services": public_services,
        "total": len(public_services),
    }


@router.get("/public/{service_code}")
async def get_public_service(
    service_code: str,
):
    """
    Get service details for public display.
    No authentication required.
    """
    service = await service_catalogue.get_active_service(service_code)
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    return {
        "service_code": service.service_code,
        "service_name": service.service_name,
        "description": service.description,
        "short_description": service.short_description,
        "category": service.category.value,
        "pricing_model": service.pricing_model.value,
        "price_amount": service.price_amount,
        "price_currency": service.price_currency,
        "vat_rate": service.vat_rate,
        "delivery_type": service.delivery_type.value,
        "estimated_turnaround_hours": service.estimated_turnaround_hours,
        "intake_fields": [f.model_dump() for f in service.intake_fields],
        "requires_cvp_subscription": service.requires_cvp_subscription,
    }
