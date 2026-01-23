"""
Knowledge Base / FAQ System Routes

Public endpoints for searching and viewing KB articles.
Admin endpoints for managing articles and categories.

Features:
- Full CRUD for articles with rich text
- Category management
- Draft/publish workflow
- Search with analytics (top searches, no results)
- View tracking
- Soft delete
- Full audit logging
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from middleware import admin_route_guard
from database import database
import logging
import uuid
import json
import re

logger = logging.getLogger(__name__)

# Routers
public_router = APIRouter(prefix="/api/kb", tags=["knowledge-base-public"])
admin_router = APIRouter(prefix="/api/admin/kb", tags=["admin-knowledge-base"])

# Collections
ARTICLES_COLLECTION = "kb_articles"
CATEGORIES_COLLECTION = "kb_categories"
SEARCH_ANALYTICS_COLLECTION = "kb_search_analytics"


# ============================================================================
# ENUMS
# ============================================================================

class ArticleStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# ============================================================================
# DEFAULT CATEGORIES
# ============================================================================

DEFAULT_CATEGORIES = [
    {"id": "getting-started", "name": "Getting Started", "icon": "🚀", "order": 1},
    {"id": "billing-subscriptions", "name": "Billing & Subscriptions", "icon": "💳", "order": 2},
    {"id": "account-login", "name": "Account & Login", "icon": "🔑", "order": 3},
    {"id": "cvp", "name": "Compliance Vault Pro (CVP)", "icon": "🏠", "order": 4},
    {"id": "documents-uploads", "name": "Documents & Uploads", "icon": "📄", "order": 5},
    {"id": "orders-delivery", "name": "Orders & Delivery", "icon": "📦", "order": 6},
    {"id": "reports-calendar", "name": "Reports & Calendar", "icon": "📊", "order": 7},
    {"id": "integrations", "name": "Integrations (Webhooks, WhatsApp)", "icon": "🔗", "order": 8},
    {"id": "troubleshooting", "name": "Troubleshooting", "icon": "🔧", "order": 9},
]


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ArticleCreate(BaseModel):
    """Request to create a KB article."""
    title: str = Field(..., min_length=5, max_length=200)
    slug: Optional[str] = None  # Auto-generated if not provided
    category_id: str
    excerpt: str = Field(..., min_length=10, max_length=500)
    content: str = Field(..., min_length=50)  # Rich text content
    tags: Optional[List[str]] = None
    status: ArticleStatus = ArticleStatus.DRAFT
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


class ArticleUpdate(BaseModel):
    """Request to update a KB article."""
    title: Optional[str] = Field(None, min_length=5, max_length=200)
    category_id: Optional[str] = None
    excerpt: Optional[str] = Field(None, min_length=10, max_length=500)
    content: Optional[str] = Field(None, min_length=50)
    tags: Optional[List[str]] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    # Note: slug is NOT updatable for URL stability


class CategoryCreate(BaseModel):
    """Request to create a category."""
    name: str = Field(..., min_length=2, max_length=100)
    icon: str = "📁"
    description: Optional[str] = None
    order: int = 0


class CategoryUpdate(BaseModel):
    """Request to update a category."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    icon: Optional[str] = None
    description: Optional[str] = None
    order: Optional[int] = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_article_id() -> str:
    """Generate unique article ID."""
    return f"kb-{uuid.uuid4().hex[:12]}"


def generate_slug(title: str) -> str:
    """Generate URL-safe slug from title."""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug[:100]


async def log_kb_action(
    action: str,
    resource_type: str,
    resource_id: str,
    actor_email: str,
    before_state: Optional[Dict] = None,
    after_state: Optional[Dict] = None,
    details: Optional[Dict] = None
):
    """Create audit log entry for KB actions."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    await db["audit_logs"].insert_one({
        "action": action,
        "actor_type": "admin",
        "actor_id": actor_email,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": {
            **(details or {}),
            "before_state": json.dumps(before_state, default=str)[:5000] if before_state else None,
            "after_state": json.dumps(after_state, default=str)[:5000] if after_state else None,
        },
        "created_at": now,
    })


async def ensure_default_categories():
    """Ensure default categories exist."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    for cat in DEFAULT_CATEGORIES:
        existing = await db[CATEGORIES_COLLECTION].find_one({"category_id": cat["id"]})
        if not existing:
            await db[CATEGORIES_COLLECTION].insert_one({
                "category_id": cat["id"],
                "name": cat["name"],
                "icon": cat["icon"],
                "order": cat["order"],
                "description": None,
                "is_active": True,
                "article_count": 0,
                "created_at": now,
            })


async def log_search_analytics(query: str, results_count: int, ip_address: str = None):
    """Log search query for analytics."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    await db[SEARCH_ANALYTICS_COLLECTION].insert_one({
        "query": query.lower().strip(),
        "results_count": results_count,
        "has_results": results_count > 0,
        "ip_address": ip_address,
        "searched_at": now,
    })


# ============================================================================
# PUBLIC ENDPOINTS
# ============================================================================

@public_router.get("/articles")
async def list_public_articles(
    category: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(20, le=100),
    skip: int = Query(0, ge=0),
    request: Request = None,
):
    """List published KB articles."""
    db = database.get_db()
    
    # Build filter - only published and active
    filter_query = {
        "status": ArticleStatus.PUBLISHED.value,
        "is_active": True,
    }
    
    if category:
        filter_query["category_id"] = category
    if tag:
        filter_query["tags"] = tag
    if search:
        filter_query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"excerpt": {"$regex": search, "$options": "i"}},
            {"content": {"$regex": search, "$options": "i"}},
            {"tags": {"$regex": search, "$options": "i"}},
        ]
    
    # Get articles
    cursor = db[ARTICLES_COLLECTION].find(
        filter_query,
        {"_id": 0, "content": 0}  # Exclude full content for list view
    ).sort([("order", 1), ("published_at", -1)]).skip(skip).limit(limit)
    
    articles = await cursor.to_list(length=limit)
    total = await db[ARTICLES_COLLECTION].count_documents(filter_query)
    
    # Log search if query provided
    if search:
        ip = request.client.host if request and request.client else None
        await log_search_analytics(search, len(articles), ip)
    
    return {
        "articles": articles,
        "total": total,
    }


@public_router.get("/articles/{slug}")
async def get_public_article(
    slug: str,
    request: Request = None,
):
    """Get a single published article by slug (increments view count)."""
    db = database.get_db()
    
    article = await db[ARTICLES_COLLECTION].find_one(
        {"slug": slug, "status": ArticleStatus.PUBLISHED.value, "is_active": True},
        {"_id": 0}
    )
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # Increment view count
    await db[ARTICLES_COLLECTION].update_one(
        {"slug": slug},
        {"$inc": {"view_count": 1}}
    )
    
    # Get related articles (same category, limit 3)
    related_cursor = db[ARTICLES_COLLECTION].find(
        {
            "category_id": article["category_id"],
            "slug": {"$ne": slug},
            "status": ArticleStatus.PUBLISHED.value,
            "is_active": True,
        },
        {"_id": 0, "content": 0}
    ).limit(3)
    related = await related_cursor.to_list(length=3)
    
    return {
        **article,
        "related_articles": related,
    }


@public_router.get("/categories")
async def list_public_categories():
    """List all active categories with article counts."""
    db = database.get_db()
    await ensure_default_categories()
    
    cursor = db[CATEGORIES_COLLECTION].find(
        {"is_active": True},
        {"_id": 0}
    ).sort("order", 1)
    
    categories = await cursor.to_list(length=50)
    
    # Get article counts per category
    pipeline = [
        {"$match": {"status": ArticleStatus.PUBLISHED.value, "is_active": True}},
        {"$group": {"_id": "$category_id", "count": {"$sum": 1}}},
    ]
    counts = {}
    async for doc in db[ARTICLES_COLLECTION].aggregate(pipeline):
        counts[doc["_id"]] = doc["count"]
    
    for cat in categories:
        cat["article_count"] = counts.get(cat["category_id"], 0)
    
    return {"categories": categories}


@public_router.get("/featured")
async def get_featured_articles():
    """Get featured/popular articles for homepage."""
    db = database.get_db()
    
    # Get top viewed articles
    popular_cursor = db[ARTICLES_COLLECTION].find(
        {"status": ArticleStatus.PUBLISHED.value, "is_active": True},
        {"_id": 0, "content": 0}
    ).sort("view_count", -1).limit(5)
    popular = await popular_cursor.to_list(length=5)
    
    # Get recent articles
    recent_cursor = db[ARTICLES_COLLECTION].find(
        {"status": ArticleStatus.PUBLISHED.value, "is_active": True},
        {"_id": 0, "content": 0}
    ).sort("published_at", -1).limit(5)
    recent = await recent_cursor.to_list(length=5)
    
    return {
        "popular": popular,
        "recent": recent,
    }


@public_router.get("/tags/popular")
async def get_popular_tags():
    """Get most used tags."""
    db = database.get_db()
    
    pipeline = [
        {"$match": {"status": ArticleStatus.PUBLISHED.value, "is_active": True}},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 20},
    ]
    
    tags = []
    async for doc in db[ARTICLES_COLLECTION].aggregate(pipeline):
        tags.append({"tag": doc["_id"], "count": doc["count"]})
    
    return {"tags": tags}


# ============================================================================
# ADMIN ENDPOINTS - ARTICLES
# ============================================================================

@admin_router.get("/articles")
async def admin_list_articles(
    status: Optional[ArticleStatus] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    include_inactive: bool = False,
    limit: int = Query(50, le=200),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(admin_route_guard)
):
    """List all articles for admin (includes drafts)."""
    db = database.get_db()
    
    filter_query = {}
    if not include_inactive:
        filter_query["is_active"] = True
    if status:
        filter_query["status"] = status.value
    if category:
        filter_query["category_id"] = category
    if search:
        filter_query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"excerpt": {"$regex": search, "$options": "i"}},
        ]
    
    cursor = db[ARTICLES_COLLECTION].find(
        filter_query,
        {"_id": 0, "content": 0}
    ).sort([("status", 1), ("updated_at", -1)]).skip(skip).limit(limit)
    
    articles = await cursor.to_list(length=limit)
    total = await db[ARTICLES_COLLECTION].count_documents(filter_query)
    
    # Get stats
    total_published = await db[ARTICLES_COLLECTION].count_documents({"status": "published", "is_active": True})
    total_draft = await db[ARTICLES_COLLECTION].count_documents({"status": "draft", "is_active": True})
    
    return {
        "articles": articles,
        "total": total,
        "stats": {
            "published": total_published,
            "draft": total_draft,
        },
    }


@admin_router.get("/articles/{article_id}")
async def admin_get_article(
    article_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Get full article for editing."""
    db = database.get_db()
    
    article = await db[ARTICLES_COLLECTION].find_one(
        {"article_id": article_id},
        {"_id": 0}
    )
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    return article


@admin_router.post("/articles")
async def admin_create_article(
    request: ArticleCreate,
    current_user: dict = Depends(admin_route_guard)
):
    """Create a new KB article."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    article_id = generate_article_id()
    slug = request.slug or generate_slug(request.title)
    
    # Check slug uniqueness
    existing = await db[ARTICLES_COLLECTION].find_one({"slug": slug})
    if existing:
        # Append ID to make unique
        slug = f"{slug}-{article_id[-6:]}"
    
    doc = {
        "article_id": article_id,
        "title": request.title,
        "slug": slug,
        "category_id": request.category_id,
        "excerpt": request.excerpt,
        "content": request.content,
        "tags": request.tags or [],
        "status": request.status.value,
        "meta_title": request.meta_title or request.title,
        "meta_description": request.meta_description or request.excerpt,
        "view_count": 0,
        "is_active": True,
        "created_at": now,
        "created_by": current_user.get("email"),
        "updated_at": now,
        "updated_by": current_user.get("email"),
        "published_at": now if request.status == ArticleStatus.PUBLISHED else None,
    }
    
    await db[ARTICLES_COLLECTION].insert_one(doc)
    doc.pop("_id", None)
    
    # Audit log
    await log_kb_action(
        action="KB_ARTICLE_CREATED",
        resource_type="kb_article",
        resource_id=article_id,
        actor_email=current_user.get("email"),
        after_state=doc,
    )
    
    logger.info(f"KB article created: {article_id} by {current_user.get('email')}")
    
    return {
        "success": True,
        "article_id": article_id,
        "slug": slug,
        "article": doc,
    }


@admin_router.put("/articles/{article_id}")
async def admin_update_article(
    article_id: str,
    request: ArticleUpdate,
    current_user: dict = Depends(admin_route_guard)
):
    """Update an existing KB article."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    # Get current state
    current = await db[ARTICLES_COLLECTION].find_one({"article_id": article_id})
    if not current:
        raise HTTPException(status_code=404, detail="Article not found")
    
    before_state = {k: v for k, v in current.items() if k != "_id"}
    
    # Build update
    update_data = {"updated_at": now, "updated_by": current_user.get("email")}
    
    if request.title is not None:
        update_data["title"] = request.title
    if request.category_id is not None:
        update_data["category_id"] = request.category_id
    if request.excerpt is not None:
        update_data["excerpt"] = request.excerpt
    if request.content is not None:
        update_data["content"] = request.content
    if request.tags is not None:
        update_data["tags"] = request.tags
    if request.meta_title is not None:
        update_data["meta_title"] = request.meta_title
    if request.meta_description is not None:
        update_data["meta_description"] = request.meta_description
    
    await db[ARTICLES_COLLECTION].update_one(
        {"article_id": article_id},
        {"$set": update_data}
    )
    
    updated = await db[ARTICLES_COLLECTION].find_one({"article_id": article_id}, {"_id": 0})
    
    # Audit log
    await log_kb_action(
        action="KB_ARTICLE_UPDATED",
        resource_type="kb_article",
        resource_id=article_id,
        actor_email=current_user.get("email"),
        before_state=before_state,
        after_state=updated,
    )
    
    return {"success": True, "article": updated}


@admin_router.post("/articles/{article_id}/publish")
async def admin_publish_article(
    article_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Publish a draft article."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    current = await db[ARTICLES_COLLECTION].find_one({"article_id": article_id})
    if not current:
        raise HTTPException(status_code=404, detail="Article not found")
    
    before_status = current.get("status")
    
    await db[ARTICLES_COLLECTION].update_one(
        {"article_id": article_id},
        {
            "$set": {
                "status": ArticleStatus.PUBLISHED.value,
                "published_at": now,
                "published_by": current_user.get("email"),
                "updated_at": now,
            }
        }
    )
    
    # Audit log
    await log_kb_action(
        action="KB_ARTICLE_PUBLISHED",
        resource_type="kb_article",
        resource_id=article_id,
        actor_email=current_user.get("email"),
        details={"before_status": before_status},
    )
    
    return {"success": True, "status": "published"}


@admin_router.post("/articles/{article_id}/unpublish")
async def admin_unpublish_article(
    article_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Unpublish an article back to draft."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    await db[ARTICLES_COLLECTION].update_one(
        {"article_id": article_id},
        {
            "$set": {
                "status": ArticleStatus.DRAFT.value,
                "unpublished_at": now,
                "unpublished_by": current_user.get("email"),
                "updated_at": now,
            }
        }
    )
    
    # Audit log
    await log_kb_action(
        action="KB_ARTICLE_UNPUBLISHED",
        resource_type="kb_article",
        resource_id=article_id,
        actor_email=current_user.get("email"),
    )
    
    return {"success": True, "status": "draft"}


@admin_router.delete("/articles/{article_id}")
async def admin_deactivate_article(
    article_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Soft delete (deactivate) an article."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    result = await db[ARTICLES_COLLECTION].update_one(
        {"article_id": article_id},
        {
            "$set": {
                "is_active": False,
                "deactivated_at": now,
                "deactivated_by": current_user.get("email"),
            }
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # Audit log
    await log_kb_action(
        action="KB_ARTICLE_DEACTIVATED",
        resource_type="kb_article",
        resource_id=article_id,
        actor_email=current_user.get("email"),
    )
    
    return {"success": True, "message": "Article deactivated"}


# ============================================================================
# ADMIN ENDPOINTS - CATEGORIES
# ============================================================================

@admin_router.get("/categories")
async def admin_list_categories(
    include_inactive: bool = False,
    current_user: dict = Depends(admin_route_guard)
):
    """List all categories for admin."""
    db = database.get_db()
    await ensure_default_categories()
    
    filter_query = {}
    if not include_inactive:
        filter_query["is_active"] = True
    
    cursor = db[CATEGORIES_COLLECTION].find(
        filter_query,
        {"_id": 0}
    ).sort("order", 1)
    
    categories = await cursor.to_list(length=100)
    
    return {"categories": categories}


@admin_router.post("/categories")
async def admin_create_category(
    request: CategoryCreate,
    current_user: dict = Depends(admin_route_guard)
):
    """Create a new category."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    category_id = generate_slug(request.name)
    
    # Check uniqueness
    existing = await db[CATEGORIES_COLLECTION].find_one({"category_id": category_id})
    if existing:
        category_id = f"{category_id}-{uuid.uuid4().hex[:6]}"
    
    doc = {
        "category_id": category_id,
        "name": request.name,
        "icon": request.icon,
        "description": request.description,
        "order": request.order,
        "is_active": True,
        "article_count": 0,
        "created_at": now,
        "created_by": current_user.get("email"),
    }
    
    await db[CATEGORIES_COLLECTION].insert_one(doc)
    doc.pop("_id", None)
    
    return {"success": True, "category": doc}


@admin_router.put("/categories/{category_id}")
async def admin_update_category(
    category_id: str,
    request: CategoryUpdate,
    current_user: dict = Depends(admin_route_guard)
):
    """Update a category."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    update_data = {"updated_at": now}
    if request.name is not None:
        update_data["name"] = request.name
    if request.icon is not None:
        update_data["icon"] = request.icon
    if request.description is not None:
        update_data["description"] = request.description
    if request.order is not None:
        update_data["order"] = request.order
    
    result = await db[CATEGORIES_COLLECTION].update_one(
        {"category_id": category_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    
    updated = await db[CATEGORIES_COLLECTION].find_one({"category_id": category_id}, {"_id": 0})
    
    return {"success": True, "category": updated}


@admin_router.delete("/categories/{category_id}")
async def admin_deactivate_category(
    category_id: str,
    current_user: dict = Depends(admin_route_guard)
):
    """Soft delete a category."""
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    result = await db[CATEGORIES_COLLECTION].update_one(
        {"category_id": category_id},
        {"$set": {"is_active": False, "deactivated_at": now}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    
    return {"success": True, "message": "Category deactivated"}


# ============================================================================
# ADMIN ENDPOINTS - ANALYTICS
# ============================================================================

@admin_router.get("/analytics")
async def admin_get_analytics(
    days: int = Query(30, le=90),
    current_user: dict = Depends(admin_route_guard)
):
    """Get KB search and view analytics."""
    db = database.get_db()
    
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    # Top viewed articles
    top_viewed_cursor = db[ARTICLES_COLLECTION].find(
        {"status": ArticleStatus.PUBLISHED.value, "is_active": True},
        {"_id": 0, "article_id": 1, "title": 1, "view_count": 1, "category_id": 1}
    ).sort("view_count", -1).limit(10)
    top_viewed = await top_viewed_cursor.to_list(length=10)
    
    # Top searches
    pipeline = [
        {"$match": {"searched_at": {"$gte": cutoff}}},
        {"$group": {"_id": "$query", "count": {"$sum": 1}, "has_results": {"$first": "$has_results"}}},
        {"$sort": {"count": -1}},
        {"$limit": 20},
    ]
    top_searches = []
    async for doc in db[SEARCH_ANALYTICS_COLLECTION].aggregate(pipeline):
        top_searches.append({
            "query": doc["_id"],
            "count": doc["count"],
            "has_results": doc.get("has_results", True),
        })
    
    # Searches with no results
    no_results_pipeline = [
        {"$match": {"searched_at": {"$gte": cutoff}, "has_results": False}},
        {"$group": {"_id": "$query", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    no_results = []
    async for doc in db[SEARCH_ANALYTICS_COLLECTION].aggregate(no_results_pipeline):
        no_results.append({"query": doc["_id"], "count": doc["count"]})
    
    # Total stats
    total_articles = await db[ARTICLES_COLLECTION].count_documents({"is_active": True})
    total_published = await db[ARTICLES_COLLECTION].count_documents({"status": "published", "is_active": True})
    total_searches = await db[SEARCH_ANALYTICS_COLLECTION].count_documents({"searched_at": {"$gte": cutoff}})
    
    return {
        "period_days": days,
        "stats": {
            "total_articles": total_articles,
            "total_published": total_published,
            "total_searches": total_searches,
        },
        "top_viewed_articles": top_viewed,
        "top_searches": top_searches,
        "searches_with_no_results": no_results,
    }
