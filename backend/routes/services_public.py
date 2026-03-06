"""
Canonical public Services API for the four services (AI automation, Market research,
Compliance services, Document packs).

Paths: GET /api/services, GET /api/services/{service_code}
Authoritative source: service_catalogue_v2 collection.
CVP-only services are excluded from listing.
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, List, Any, Dict

from services.service_catalogue_v2 import (
    service_catalogue_v2,
    ServiceCategory,
)

router = APIRouter(prefix="/api/services", tags=["services-public"])


def _service_to_public(doc: Any) -> Dict[str, Any]:
    """Map catalogue entry to task-shaped public response."""
    return {
        "service_code": doc.service_code,
        "name": doc.service_name,
        "category": doc.category.value,
        "description_preview": doc.description,
        "description_full": doc.long_description,
        "pricing": doc.pricing_model.value,
        "base_price": doc.base_price,
        "currency": doc.price_currency,
        "add_ons": [
            {"code": "FAST_TRACK", "name": "Fast Track", "price": doc.fast_track_price}
            for _ in [1] if doc.fast_track_available
        ]
        + [
            {"code": "PRINTED_COPY", "name": "Printed Copy", "price": doc.printed_copy_price}
            for _ in [1] if doc.printed_copy_available
        ],
        "requires_review": doc.review_required,
        "document_types": [d.template_code for d in (doc.documents_generated or [])],
        "is_active": doc.active,
        "sort_order": doc.display_order,
        "seo_slug": doc.learn_more_slug or doc.service_code.lower().replace("_", "-"),
        "intake_schema_id": getattr(doc, "intake_schema_id", None) or doc.service_code,
        "website_preview": doc.website_preview or doc.description,
        "turnaround_hours": doc.standard_turnaround_hours,
        "fast_track_available": doc.fast_track_available,
        "fast_track_price": doc.fast_track_price,
        "printed_copy_available": doc.printed_copy_available,
        "printed_copy_price": doc.printed_copy_price,
        "tags": doc.tags,
    }


@router.get("")
async def list_services(category: Optional[str] = None):
    """
    List active services (public). Excludes CVP-only features.
    service_code is canonical and used everywhere.
    """
    cat = None
    if category:
        try:
            cat = ServiceCategory(category)
        except ValueError:
            pass
    services = await service_catalogue_v2.list_services(
        category=cat,
        active_only=True,
        is_cvp_feature=False,
    )
    return {
        "services": [_service_to_public(s) for s in services],
        "total": len(services),
    }


@router.get("/by-slug/{slug}")
async def get_service_by_slug(slug: str):
    """
    Get a single active service by seo_slug or service_code (public).
    Enables Learn More links to /services/detail/{slug}.
    """
    # Try by seo_slug first (normalized: lowercase, underscores to hyphens)
    slug_norm = slug.strip().lower().replace("_", "-")
    services = await service_catalogue_v2.list_services(active_only=True, is_cvp_feature=False)
    for s in services:
        if s.is_cvp_feature and s.service_code != "CVP_SUBSCRIPTION":
            continue
        code_slug = s.service_code.lower().replace("_", "-")
        learn_slug = (s.learn_more_slug or code_slug).strip().lower().replace("_", "-")
        if learn_slug == slug_norm or code_slug == slug_norm:
            return _service_to_public(s)
    # Fallback: try as service_code
    service = await service_catalogue_v2.get_active_service(slug)
    if service:
        if service.is_cvp_feature and service.service_code != "CVP_SUBSCRIPTION":
            raise HTTPException(status_code=404, detail="Service not found")
        return _service_to_public(service)
    raise HTTPException(status_code=404, detail=f"Service not found: {slug}")


@router.get("/{service_code}")
async def get_service(service_code: str):
    """
    Get a single service by service_code (public). Returns 404 if not found or inactive.
    """
    service = await service_catalogue_v2.get_active_service(service_code)
    if not service:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    if service.is_cvp_feature and service.service_code != "CVP_SUBSCRIPTION":
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    return _service_to_public(service)
