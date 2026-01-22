"""
Public Services Routes - For public website service ordering.
No authentication required.
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
from services.service_catalogue import service_catalogue, ServiceCategory

router = APIRouter(prefix="/api/public", tags=["public-services"])


@router.get("/services")
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
    
    # Return public-safe fields
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
            "turnaround_hours": s.estimated_turnaround_hours,
            "requires_cvp_subscription": s.requires_cvp_subscription,
            "display_order": s.display_order,
            "review_required": s.review_required,
            "documents_generated": [
                {
                    "document_code": d.document_code,
                    "document_name": d.document_name,
                    "format": d.format,
                    "is_primary": d.is_primary,
                }
                for d in s.documents_generated
            ] if s.documents_generated else [],
        })
    
    return {
        "services": public_services,
        "total": len(public_services),
    }


@router.get("/services/{service_code}")
async def get_public_service(
    service_code: str,
):
    """
    Get service details for public display and ordering.
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
        "turnaround_hours": service.estimated_turnaround_hours,
        "intake_fields": [f.model_dump() for f in service.intake_fields] if service.intake_fields else [],
        "documents_generated": [
            {
                "document_code": d.document_code,
                "document_name": d.document_name,
                "format": d.format,
                "is_primary": d.is_primary,
            }
            for d in service.documents_generated
        ] if service.documents_generated else [],
        "review_required": service.review_required,
        "requires_cvp_subscription": service.requires_cvp_subscription,
    }
