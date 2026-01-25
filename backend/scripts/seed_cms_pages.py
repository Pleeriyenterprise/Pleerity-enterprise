"""
CMS Service Page Seeder

Seeds CMS pages from the Service Catalogue.
Creates category and service pages with default content.

Run with: python scripts/seed_cms_pages.py
"""

import asyncio
import sys
sys.path.insert(0, '/app/backend')

from database import database
from models.cms import PageStatus, PageType, CATEGORY_CONFIG
from datetime import datetime, timezone
from bson import ObjectId
import re


def generate_slug(text: str) -> str:
    """Generate URL-safe slug from text."""
    slug = text.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug


async def seed_cms_pages():
    """Seed CMS pages from Service Catalogue."""
    await database.connect()
    db = database.get_db()
    
    print("=" * 60)
    print("CMS Page Seeder")
    print("=" * 60)
    
    # 1. Create Services Hub page
    print("\n1. Creating Services Hub page...")
    hub_exists = await db.cms_pages.find_one({"page_type": "HUB", "slug": "services"})
    if not hub_exists:
        hub_page = {
            "page_id": f"CMS-HUB-{ObjectId()}",
            "page_type": "HUB",
            "status": PageStatus.PUBLISHED.value,
            "slug": "services",
            "category_slug": None,
            "service_code": None,
            "full_path": "/services",
            "title": "Our Services",
            "subtitle": "Professional business services to help you grow and succeed",
            "hero_image": None,
            "blocks": [],
            "seo": {
                "meta_title": "Services | Pleerity Enterprise",
                "meta_description": "Explore our professional services: AI automation, market research, compliance audits, and document packs.",
                "no_index": False,
            },
            "display_order": 0,
            "visible_in_nav": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "published_at": datetime.now(timezone.utc),
            "created_by": "system",
            "updated_by": "system",
            "published_by": "system",
        }
        await db.cms_pages.insert_one(hub_page)
        print("   ✓ Created Services Hub page")
    else:
        print("   • Hub page already exists")
    
    # 2. Create Category pages
    print("\n2. Creating Category pages...")
    for cat_slug, config in CATEGORY_CONFIG.items():
        cat_exists = await db.cms_pages.find_one({
            "page_type": "CATEGORY",
            "slug": cat_slug
        })
        
        if not cat_exists:
            cat_page = {
                "page_id": f"CMS-CAT-{ObjectId()}",
                "page_type": "CATEGORY",
                "status": PageStatus.PUBLISHED.value,
                "slug": cat_slug,
                "category_slug": None,
                "service_code": None,
                "full_path": f"/services/{cat_slug}",
                "title": config["name"],
                "subtitle": config["tagline"],
                "description": config["description"],
                "hero_image": None,
                "blocks": [],
                "seo": {
                    "meta_title": f"{config['name']} | Pleerity Enterprise",
                    "meta_description": config["description"],
                    "no_index": False,
                },
                "display_order": config["display_order"],
                "visible_in_nav": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "published_at": datetime.now(timezone.utc),
                "created_by": "system",
                "updated_by": "system",
                "published_by": "system",
            }
            await db.cms_pages.insert_one(cat_page)
            print(f"   ✓ Created: {config['name']}")
        else:
            print(f"   • Already exists: {config['name']}")
    
    # 3. Create Service pages from catalogue
    print("\n3. Creating Service pages from catalogue...")
    
    # Map catalogue category to CMS category slug
    category_map = {
        config["service_catalogue_category"]: cat_slug
        for cat_slug, config in CATEGORY_CONFIG.items()
    }
    
    services = await db.service_catalogue_v2.find({"active": True}).to_list(100)
    
    for service in services:
        service_code = service.get("service_code")
        service_name = service.get("service_name") or service.get("name")
        catalogue_category = service.get("category")
        
        # Skip if no category mapping
        cms_category = category_map.get(catalogue_category)
        if not cms_category:
            print(f"   ! Skipping {service_code}: No category mapping for '{catalogue_category}'")
            continue
        
        # Generate slug
        slug = service.get("learn_more_slug") or generate_slug(service_name)
        
        # Check if page exists
        page_exists = await db.cms_pages.find_one({
            "page_type": "SERVICE",
            "service_code": service_code
        })
        
        if not page_exists:
            # Build default content from catalogue
            description = service.get("description") or service.get("long_description") or ""
            base_price = service.get("base_price", 0)
            turnaround = service.get("standard_turnaround_hours", 48)
            fast_track = service.get("fast_track_available", False)
            
            service_page = {
                "page_id": f"CMS-SVC-{ObjectId()}",
                "page_type": "SERVICE",
                "status": PageStatus.PUBLISHED.value,
                "slug": slug,
                "category_slug": cms_category,
                "service_code": service_code,
                "full_path": f"/services/{cms_category}/{slug}",
                "title": service_name,
                "subtitle": description[:200] if description else None,
                "description": description,
                "hero_image": None,
                "blocks": [],
                "seo": {
                    "meta_title": f"{service_name} | Pleerity Enterprise",
                    "meta_description": description[:160] if description else service_name,
                    "no_index": False,
                },
                "display_order": service.get("display_order", 0),
                "visible_in_nav": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "published_at": datetime.now(timezone.utc),
                "created_by": "system",
                "updated_by": "system",
                "published_by": "system",
            }
            await db.cms_pages.insert_one(service_page)
            print(f"   ✓ Created: {service_name} ({service_code}) -> /services/{cms_category}/{slug}")
        else:
            print(f"   • Already exists: {service_name}")
    
    # Summary
    print("\n" + "=" * 60)
    print("Seeding Complete!")
    print("=" * 60)
    
    hub_count = await db.cms_pages.count_documents({"page_type": "HUB"})
    cat_count = await db.cms_pages.count_documents({"page_type": "CATEGORY"})
    svc_count = await db.cms_pages.count_documents({"page_type": "SERVICE"})
    
    print(f"\nCMS Pages Summary:")
    print(f"  Hub pages:      {hub_count}")
    print(f"  Category pages: {cat_count}")
    print(f"  Service pages:  {svc_count}")
    print(f"  Total:          {hub_count + cat_count + svc_count}")


if __name__ == "__main__":
    asyncio.run(seed_cms_pages())
