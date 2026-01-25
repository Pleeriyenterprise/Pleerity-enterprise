"""
Marketing Website Routes - Public API for CMS-driven marketing pages

Handles:
- Services hub page
- Category pages
- Individual service pages
- URL redirects
- SEO metadata

All content is CMS-driven with Service Catalogue integration.
"""

import os
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
from typing import Optional, Dict, Any, List

from services import cms_service
from models.cms import CATEGORY_CONFIG, PageStatus

router = APIRouter(prefix="/marketing", tags=["Marketing Website"])

# Environment check for preview banner
IS_PRODUCTION = os.environ.get("ENVIRONMENT", "preview") == "production"


def add_environment_metadata(response: Dict[str, Any]) -> Dict[str, Any]:
    """Add environment metadata for frontend to render preview banner."""
    response["_meta"] = {
        "is_production": IS_PRODUCTION,
        "show_preview_banner": not IS_PRODUCTION,
        "robots_directive": "index,follow" if IS_PRODUCTION else "noindex,nofollow",
    }
    return response


# ============================================================================
# Services Hub
# ============================================================================

@router.get("/services")
async def get_services_hub():
    """
    Get the services hub page with all categories.
    
    Returns the hub page content and a list of all service categories
    with their basic info for navigation.
    """
    try:
        hub_data = await cms_service.get_services_hub()
        return add_environment_metadata({
            "success": True,
            "data": hub_data,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Category Pages
# ============================================================================

@router.get("/services/categories")
async def list_categories():
    """List all service categories."""
    categories = []
    for slug, config in CATEGORY_CONFIG.items():
        categories.append({
            "slug": slug,
            "name": config["name"],
            "tagline": config["tagline"],
            "description": config["description"],
            "icon": config["icon"],
            "display_order": config["display_order"],
            "path": f"/services/{slug}",
        })
    
    return add_environment_metadata({
        "success": True,
        "categories": sorted(categories, key=lambda x: x["display_order"]),
    })


@router.get("/services/category/{category_slug}")
async def get_category(category_slug: str):
    """
    Get a category page with all its services.
    
    Returns category info and list of services with pricing/availability.
    """
    # Validate category exists
    if category_slug not in CATEGORY_CONFIG:
        raise HTTPException(status_code=404, detail="Category not found")
    
    try:
        category_data = await cms_service.get_category_page(category_slug)
        
        if not category_data:
            raise HTTPException(status_code=404, detail="Category page not found")
        
        return add_environment_metadata({
            "success": True,
            "data": category_data,
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Individual Service Pages
# ============================================================================

@router.get("/services/{category_slug}/{service_slug}")
async def get_service(category_slug: str, service_slug: str):
    """
    Get an individual service page.
    
    Returns full service page content with:
    - CMS blocks
    - Service catalogue data (pricing, turnaround, etc.)
    - CTA configuration based on purchase mode
    """
    # Validate category
    if category_slug not in CATEGORY_CONFIG:
        raise HTTPException(status_code=404, detail="Category not found")
    
    try:
        service_data = await cms_service.get_service_page(category_slug, service_slug)
        
        if not service_data:
            # Check for redirect
            full_path = f"/services/{category_slug}/{service_slug}"
            redirect = await cms_service.check_redirect(full_path)
            if redirect:
                return add_environment_metadata({
                    "success": False,
                    "redirect": True,
                    "redirect_to": redirect["to_path"],
                    "redirect_type": redirect["redirect_type"],
                })
            
            raise HTTPException(status_code=404, detail="Service page not found")
        
        return add_environment_metadata({
            "success": True,
            "data": service_data,
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Generic Page Lookup (for any CMS page)
# ============================================================================

@router.get("/page")
async def get_page_by_path(path: str = Query(..., description="Full URL path")):
    """
    Get any CMS page by its full path.
    
    Handles redirects automatically.
    """
    try:
        # Check for redirect first
        redirect = await cms_service.check_redirect(path)
        if redirect:
            return add_environment_metadata({
                "success": False,
                "redirect": True,
                "redirect_to": redirect["to_path"],
                "redirect_type": redirect["redirect_type"],
            })
        
        # Get page
        page = await cms_service.get_page_for_public(full_path=path)
        
        if not page:
            raise HTTPException(status_code=404, detail="Page not found")
        
        return add_environment_metadata({
            "success": True,
            "page": page,
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Service Catalogue Integration
# ============================================================================

@router.get("/services/{category_slug}/list")
async def list_services_in_category(category_slug: str):
    """
    List all services in a category with basic info.
    
    Lighter endpoint for navigation/listing purposes.
    """
    if category_slug not in CATEGORY_CONFIG:
        raise HTTPException(status_code=404, detail="Category not found")
    
    try:
        services = await cms_service.list_category_services(category_slug)
        
        # Add basic catalogue info
        from database import database
        db = database.get_db()
        
        enriched = []
        for svc in services:
            service_code = svc.get("service_code")
            if service_code:
                catalogue = await db.service_catalogue_v2.find_one(
                    {"service_code": service_code},
                    {"_id": 0, "base_price": 1, "website_preview": 1}
                )
                if catalogue:
                    svc["price"] = catalogue.get("base_price", 0)
                    svc["preview"] = catalogue.get("website_preview")
            
            enriched.append({
                "slug": svc["slug"],
                "title": svc["title"],
                "description": svc.get("description") or svc.get("preview"),
                "service_code": svc.get("service_code"),
                "price": svc.get("price", 0),
                "full_path": svc.get("full_path"),
            })
        
        return add_environment_metadata({
            "success": True,
            "category": CATEGORY_CONFIG[category_slug]["name"],
            "services": enriched,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SEO Helpers
# ============================================================================

@router.get("/sitemap")
async def get_sitemap_data():
    """
    Get sitemap data for all published pages.
    
    Returns list of URLs for sitemap.xml generation.
    """
    from database import database
    db = database.get_db()
    
    try:
        # Get all published pages
        pages = await db.cms_pages.find(
            {"status": PageStatus.PUBLISHED.value},
            {"_id": 0, "full_path": 1, "updated_at": 1, "page_type": 1}
        ).to_list(length=500)
        
        urls = []
        for page in pages:
            priority = "0.8"
            if page["page_type"] == "HUB":
                priority = "1.0"
            elif page["page_type"] == "CATEGORY":
                priority = "0.9"
            elif page["page_type"] == "SERVICE":
                priority = "0.8"
            
            urls.append({
                "loc": page["full_path"],
                "lastmod": page["updated_at"].isoformat() if page.get("updated_at") else None,
                "priority": priority,
            })
        
        return {
            "success": True,
            "urls": urls,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
