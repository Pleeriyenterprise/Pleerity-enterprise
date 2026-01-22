"""
Public Services V2 Routes - For public website service ordering.

This is the public-facing API for the Service Catalogue V2.
No authentication required for browsing services.

All services shown here come from the authoritative catalogue.
If a service is not in the catalogue, it cannot be displayed or ordered.
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from services.service_catalogue_v2 import (
    service_catalogue_v2,
    ServiceCategory,
)

router = APIRouter(prefix="/api/public/v2", tags=["public-services-v2"])


@router.get("/services")
async def list_public_services(
    category: Optional[str] = None,
):
    """
    List active services for public display.
    Groups by category for website sections.
    """
    cat = ServiceCategory(category) if category else None
    services = await service_catalogue_v2.list_services(
        category=cat,
        active_only=True,
        is_cvp_feature=False,  # Exclude CVP-only features
    )
    
    # Return public-safe fields
    public_services = []
    for s in services:
        public_services.append({
            "service_code": s.service_code,
            "service_name": s.service_name,
            "description": s.description,
            "website_preview": s.website_preview or s.description,
            "learn_more_slug": s.learn_more_slug,
            "category": s.category.value,
            "pricing_model": s.pricing_model.value,
            "base_price": s.base_price,
            "price_currency": s.price_currency,
            "vat_rate": s.vat_rate,
            "delivery_type": s.delivery_type.value,
            "turnaround_hours": s.standard_turnaround_hours,
            "fast_track_available": s.fast_track_available,
            "fast_track_price": s.fast_track_price,
            "fast_track_hours": s.fast_track_hours,
            "printed_copy_available": s.printed_copy_available,
            "printed_copy_price": s.printed_copy_price,
            "review_required": s.review_required,
            "display_order": s.display_order,
            "tags": s.tags,
            "document_count": len(s.documents_generated) if s.documents_generated else 0,
        })
    
    return {
        "services": public_services,
        "total": len(public_services),
    }


@router.get("/services/by-category")
async def list_services_by_category():
    """
    List all active services grouped by category.
    Ideal for website service catalogue page.
    """
    result = {}
    
    category_info = {
        ServiceCategory.AI_AUTOMATION: {
            "label": "Automation Services",
            "description": "AI-powered workflow and process automation",
            "icon": "sparkles",
        },
        ServiceCategory.MARKET_RESEARCH: {
            "label": "Market Research",
            "description": "Market analysis and competitor insights",
            "icon": "search",
        },
        ServiceCategory.COMPLIANCE: {
            "label": "Compliance Services",
            "description": "Property compliance audits and documentation",
            "icon": "shield",
        },
        ServiceCategory.DOCUMENT_PACK: {
            "label": "Document Packs",
            "description": "Professional landlord document bundles",
            "icon": "file-text",
        },
        ServiceCategory.SUBSCRIPTION: {
            "label": "Subscriptions",
            "description": "Ongoing compliance management",
            "icon": "repeat",
        },
    }
    
    for cat in ServiceCategory:
        if cat == ServiceCategory.SUBSCRIPTION:
            continue  # Handle subscriptions separately
        
        services = await service_catalogue_v2.list_by_category(cat, active_only=True)
        
        result[cat.value] = {
            "info": category_info.get(cat, {"label": cat.value, "description": "", "icon": "package"}),
            "services": [
                {
                    "service_code": s.service_code,
                    "service_name": s.service_name,
                    "description": s.description,
                    "website_preview": s.website_preview or s.description,
                    "learn_more_slug": s.learn_more_slug,
                    "base_price": s.base_price,
                    "fast_track_available": s.fast_track_available,
                    "fast_track_price": s.fast_track_price,
                    "printed_copy_available": s.printed_copy_available,
                    "printed_copy_price": s.printed_copy_price,
                    "turnaround_hours": s.standard_turnaround_hours,
                    "display_order": s.display_order,
                }
                for s in services
                if not s.is_cvp_feature
            ],
            "count": len([s for s in services if not s.is_cvp_feature]),
        }
    
    return result


@router.get("/services/document-packs")
async def list_document_packs():
    """
    List document packs in tier order (Essential → Plus → Pro).
    Shows pack hierarchy and included documents.
    """
    packs = await service_catalogue_v2.list_document_packs(active_only=True)
    
    result = []
    for pack in packs:
        # Get all documents including inherited
        all_docs = await service_catalogue_v2.get_pack_documents(pack.service_code)
        
        result.append({
            "service_code": pack.service_code,
            "service_name": pack.service_name,
            "description": pack.description,
            "long_description": pack.long_description,
            "website_preview": pack.website_preview or pack.description,
            "learn_more_slug": pack.learn_more_slug,
            "base_price": pack.base_price,
            "pack_tier": pack.pack_tier.value if pack.pack_tier else None,
            "includes_lower_tiers": pack.includes_lower_tiers,
            "fast_track_available": pack.fast_track_available,
            "fast_track_price": pack.fast_track_price,
            "printed_copy_available": pack.printed_copy_available,
            "printed_copy_price": pack.printed_copy_price,
            "documents": [
                {
                    "template_code": d.template_code,
                    "template_name": d.template_name,
                    "format": d.format,
                }
                for d in all_docs
            ],
            "document_count": len(all_docs),
            "display_order": pack.display_order,
        })
    
    return {
        "packs": result,
        "total": len(result),
    }


@router.get("/services/{service_code}")
async def get_public_service(service_code: str):
    """
    Get service details for public display and Learn More page.
    """
    service = await service_catalogue_v2.get_active_service(service_code)
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Don't expose CVP-only features publicly
    if service.is_cvp_feature and not service.service_code == "CVP_SUBSCRIPTION":
        raise HTTPException(status_code=404, detail="Service not found")
    
    return {
        "service_code": service.service_code,
        "service_name": service.service_name,
        "description": service.description,
        "long_description": service.long_description,
        "website_preview": service.website_preview or service.description,
        "learn_more_slug": service.learn_more_slug,
        "category": service.category.value,
        "pricing_model": service.pricing_model.value,
        "base_price": service.base_price,
        "price_currency": service.price_currency,
        "vat_rate": service.vat_rate,
        "pricing_variants": [
            {
                "variant_code": v.variant_code,
                "variant_name": v.variant_name,
                "price_amount": v.price_amount,
                "is_addon": v.is_addon,
                "addon_type": v.addon_type,
            }
            for v in service.pricing_variants
        ],
        "fast_track_available": service.fast_track_available,
        "fast_track_price": service.fast_track_price,
        "fast_track_hours": service.fast_track_hours,
        "printed_copy_available": service.printed_copy_available,
        "printed_copy_price": service.printed_copy_price,
        "delivery_type": service.delivery_type.value,
        "turnaround_hours": service.standard_turnaround_hours,
        "documents_generated": [
            {
                "template_code": d.template_code,
                "template_name": d.template_name,
                "format": d.format,
            }
            for d in service.documents_generated
        ] if service.documents_generated else [],
        "pack_tier": service.pack_tier.value if service.pack_tier else None,
        "review_required": service.review_required,
        "tags": service.tags,
    }


@router.get("/services/{service_code}/intake")
async def get_service_intake(service_code: str):
    """
    Get intake form fields for a service.
    Used to render the order form on the website.
    """
    service = await service_catalogue_v2.get_active_service(service_code)
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    intake_fields = await service_catalogue_v2.get_intake_fields(service_code)
    
    return {
        "service_code": service.service_code,
        "service_name": service.service_name,
        "intake_fields": [
            {
                "field_id": f.field_id,
                "label": f.label,
                "field_type": f.field_type.value,
                "required": f.required,
                "placeholder": f.placeholder,
                "help_text": f.help_text,
                "options": f.options,
                "min_value": f.min_value,
                "max_value": f.max_value,
                "default_value": f.default_value,
                "order": f.order,
                "conditional_on": f.conditional_on,
                "conditional_value": f.conditional_value,
            }
            for f in intake_fields
        ],
        "total_fields": len(intake_fields),
    }


@router.get("/services/{service_code}/price")
async def calculate_public_price(
    service_code: str,
    fast_track: bool = False,
    printed_copy: bool = False,
):
    """
    Calculate total price with add-ons.
    Returns breakdown for checkout display.
    """
    price = await service_catalogue_v2.calculate_order_price(
        service_code=service_code,
        fast_track=fast_track,
        printed_copy=printed_copy,
    )
    
    if not price:
        raise HTTPException(status_code=404, detail="Service not found")
    
    return price


@router.get("/cvp/plans")
async def get_cvp_plans():
    """
    Get CVP subscription plans and pricing.
    """
    cvp = await service_catalogue_v2.get_active_service("CVP_SUBSCRIPTION")
    
    if not cvp:
        return {"plans": [], "available": False}
    
    # Group variants by tier
    tiers = {
        "solo": {
            "name": "Solo Landlord",
            "description": "Up to 2 properties",
            "monthly": None,
            "setup": None,
        },
        "portfolio": {
            "name": "Portfolio",
            "description": "Up to 10 properties",
            "monthly": None,
            "setup": None,
        },
        "professional": {
            "name": "Professional",
            "description": "Up to 25 properties",
            "monthly": None,
            "setup": None,
        },
    }
    
    for v in cvp.pricing_variants:
        if "solo" in v.variant_code:
            if "monthly" in v.variant_code:
                tiers["solo"]["monthly"] = v.price_amount
            elif "setup" in v.variant_code:
                tiers["solo"]["setup"] = v.price_amount
        elif "portfolio" in v.variant_code:
            if "monthly" in v.variant_code:
                tiers["portfolio"]["monthly"] = v.price_amount
            elif "setup" in v.variant_code:
                tiers["portfolio"]["setup"] = v.price_amount
        elif "professional" in v.variant_code:
            if "monthly" in v.variant_code:
                tiers["professional"]["monthly"] = v.price_amount
            elif "setup" in v.variant_code:
                tiers["professional"]["setup"] = v.price_amount
    
    return {
        "available": True,
        "description": cvp.description,
        "long_description": cvp.long_description,
        "plans": [
            {
                "tier": k,
                "name": v["name"],
                "description": v["description"],
                "monthly_price": v["monthly"],
                "setup_fee": v["setup"],
            }
            for k, v in tiers.items()
            if v["monthly"] is not None
        ],
    }
