"""
Blog/Insights Routes - Admin management and public viewing of blog posts.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId
import re
import logging

from database import database
from utils.auth import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/blog", tags=["blog"])


# =========================
# MODELS
# =========================

class BlogPostCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    slug: Optional[str] = None
    excerpt: Optional[str] = Field(None, max_length=500)
    content: str = Field(..., min_length=10)
    featured_image: Optional[str] = None
    category: str = Field(default="General")
    tags: List[str] = Field(default_factory=list)
    status: str = Field(default="draft")  # draft, published, archived
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    

class BlogPostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    slug: Optional[str] = None
    excerpt: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = Field(None, min_length=10)
    featured_image: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


# =========================
# HELPER FUNCTIONS
# =========================

def generate_slug(title: str) -> str:
    """Generate URL-friendly slug from title."""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug


def serialize_post(post: dict) -> dict:
    """Serialize MongoDB document for API response."""
    return {
        "id": str(post["_id"]),
        "title": post.get("title"),
        "slug": post.get("slug"),
        "excerpt": post.get("excerpt"),
        "content": post.get("content"),
        "featured_image": post.get("featured_image"),
        "category": post.get("category", "General"),
        "tags": post.get("tags", []),
        "status": post.get("status", "draft"),
        "author_id": post.get("author_id"),
        "author_name": post.get("author_name"),
        "meta_title": post.get("meta_title"),
        "meta_description": post.get("meta_description"),
        "view_count": post.get("view_count", 0),
        "created_at": post.get("created_at").isoformat() if post.get("created_at") else None,
        "updated_at": post.get("updated_at").isoformat() if post.get("updated_at") else None,
        "published_at": post.get("published_at").isoformat() if post.get("published_at") else None,
    }


# =========================
# ADMIN ENDPOINTS
# =========================

@router.get("/admin/posts")
async def list_admin_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(require_admin),
):
    """List all blog posts (admin view)."""
    db = database.get_db()
    
    query = {}
    
    if status:
        query["status"] = status
    
    if category:
        query["category"] = category
    
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"content": {"$regex": search, "$options": "i"}},
            {"tags": {"$in": [search.lower()]}},
        ]
    
    total = await db.blog_posts.count_documents(query)
    
    cursor = db.blog_posts.find(query).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
    posts = await cursor.to_list(length=page_size)
    
    return {
        "posts": [serialize_post(p) for p in posts],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.post("/admin/posts")
async def create_post(
    post: BlogPostCreate,
    current_user: dict = Depends(require_admin),
):
    """Create a new blog post."""
    db = database.get_db()
    
    # Generate slug if not provided
    slug = post.slug or generate_slug(post.title)
    
    # Ensure slug is unique
    existing = await db.blog_posts.find_one({"slug": slug})
    if existing:
        # Append timestamp to make unique
        slug = f"{slug}-{int(datetime.now(timezone.utc).timestamp())}"
    
    now = datetime.now(timezone.utc)
    
    post_doc = {
        "title": post.title,
        "slug": slug,
        "excerpt": post.excerpt,
        "content": post.content,
        "featured_image": post.featured_image,
        "category": post.category,
        "tags": [t.lower() for t in post.tags],
        "status": post.status,
        "author_id": current_user.get("portal_user_id"),
        "author_name": current_user.get("email", "Admin"),
        "meta_title": post.meta_title or post.title,
        "meta_description": post.meta_description or post.excerpt,
        "view_count": 0,
        "created_at": now,
        "updated_at": now,
        "published_at": now if post.status == "published" else None,
    }
    
    result = await db.blog_posts.insert_one(post_doc)
    post_doc["_id"] = result.inserted_id
    
    logger.info(f"Blog post created: {post.title} by {current_user.get('email')}")
    
    return {
        "success": True,
        "message": "Blog post created successfully",
        "post": serialize_post(post_doc),
    }


@router.get("/admin/posts/{post_id}")
async def get_admin_post(
    post_id: str,
    current_user: dict = Depends(require_admin),
):
    """Get a single blog post (admin view)."""
    db = database.get_db()
    
    try:
        post = await db.blog_posts.find_one({"_id": ObjectId(post_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid post ID")
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return {"post": serialize_post(post)}


@router.put("/admin/posts/{post_id}")
async def update_post(
    post_id: str,
    updates: BlogPostUpdate,
    current_user: dict = Depends(require_admin),
):
    """Update a blog post."""
    db = database.get_db()
    
    try:
        post = await db.blog_posts.find_one({"_id": ObjectId(post_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid post ID")
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    update_data = {}
    
    if updates.title is not None:
        update_data["title"] = updates.title
    
    if updates.slug is not None:
        # Check slug uniqueness
        existing = await db.blog_posts.find_one({
            "slug": updates.slug,
            "_id": {"$ne": ObjectId(post_id)}
        })
        if existing:
            raise HTTPException(status_code=400, detail="Slug already exists")
        update_data["slug"] = updates.slug
    
    if updates.excerpt is not None:
        update_data["excerpt"] = updates.excerpt
    
    if updates.content is not None:
        update_data["content"] = updates.content
    
    if updates.featured_image is not None:
        update_data["featured_image"] = updates.featured_image
    
    if updates.category is not None:
        update_data["category"] = updates.category
    
    if updates.tags is not None:
        update_data["tags"] = [t.lower() for t in updates.tags]
    
    if updates.status is not None:
        update_data["status"] = updates.status
        # Set published_at when publishing
        if updates.status == "published" and post.get("status") != "published":
            update_data["published_at"] = datetime.now(timezone.utc)
    
    if updates.meta_title is not None:
        update_data["meta_title"] = updates.meta_title
    
    if updates.meta_description is not None:
        update_data["meta_description"] = updates.meta_description
    
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc)
        
        await db.blog_posts.update_one(
            {"_id": ObjectId(post_id)},
            {"$set": update_data}
        )
    
    updated_post = await db.blog_posts.find_one({"_id": ObjectId(post_id)})
    
    logger.info(f"Blog post updated: {post_id} by {current_user.get('email')}")
    
    return {
        "success": True,
        "message": "Blog post updated successfully",
        "post": serialize_post(updated_post),
    }


@router.delete("/admin/posts/{post_id}")
async def delete_post(
    post_id: str,
    current_user: dict = Depends(require_admin),
):
    """Delete a blog post."""
    db = database.get_db()
    
    try:
        result = await db.blog_posts.delete_one({"_id": ObjectId(post_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid post ID")
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Post not found")
    
    logger.info(f"Blog post deleted: {post_id} by {current_user.get('email')}")
    
    return {
        "success": True,
        "message": "Blog post deleted successfully",
    }


@router.post("/admin/posts/{post_id}/publish")
async def publish_post(
    post_id: str,
    current_user: dict = Depends(require_admin),
):
    """Publish a draft post."""
    db = database.get_db()
    
    try:
        post = await db.blog_posts.find_one({"_id": ObjectId(post_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid post ID")
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    now = datetime.now(timezone.utc)
    
    await db.blog_posts.update_one(
        {"_id": ObjectId(post_id)},
        {
            "$set": {
                "status": "published",
                "published_at": now,
                "updated_at": now,
            }
        }
    )
    
    logger.info(f"Blog post published: {post_id} by {current_user.get('email')}")
    
    return {
        "success": True,
        "message": "Blog post published successfully",
    }


@router.post("/admin/posts/{post_id}/unpublish")
async def unpublish_post(
    post_id: str,
    current_user: dict = Depends(require_admin),
):
    """Unpublish a post (set to draft)."""
    db = database.get_db()
    
    try:
        post = await db.blog_posts.find_one({"_id": ObjectId(post_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid post ID")
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    await db.blog_posts.update_one(
        {"_id": ObjectId(post_id)},
        {
            "$set": {
                "status": "draft",
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )
    
    logger.info(f"Blog post unpublished: {post_id} by {current_user.get('email')}")
    
    return {
        "success": True,
        "message": "Blog post unpublished successfully",
    }


@router.get("/admin/categories")
async def get_categories(
    current_user: dict = Depends(require_admin),
):
    """Get all unique categories."""
    db = database.get_db()
    
    categories = await db.blog_posts.distinct("category")
    
    # Add default categories if none exist
    default_categories = [
        "Property Management",
        "Compliance",
        "Investment",
        "Legal Updates",
        "Market Insights",
        "Tips & Guides",
        "Company News",
    ]
    
    all_categories = list(set(categories + default_categories))
    all_categories.sort()
    
    return {"categories": all_categories}


@router.get("/admin/tags")
async def get_tags(
    current_user: dict = Depends(require_admin),
):
    """Get all unique tags."""
    db = database.get_db()
    
    # Aggregate unique tags
    pipeline = [
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags"}},
        {"$sort": {"_id": 1}},
    ]
    
    cursor = db.blog_posts.aggregate(pipeline)
    tags = [doc["_id"] async for doc in cursor]
    
    return {"tags": tags}


# =========================
# PUBLIC ENDPOINTS
# =========================

@router.get("/posts")
async def list_public_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    category: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
):
    """List published blog posts (public view)."""
    db = database.get_db()
    
    query = {"status": "published"}
    
    if category:
        query["category"] = category
    
    if tag:
        query["tags"] = tag.lower()
    
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"excerpt": {"$regex": search, "$options": "i"}},
            {"tags": {"$in": [search.lower()]}},
        ]
    
    total = await db.blog_posts.count_documents(query)
    
    cursor = db.blog_posts.find(
        query,
        {"content": 0}  # Exclude full content in list view
    ).sort("published_at", -1).skip((page - 1) * page_size).limit(page_size)
    
    posts = await cursor.to_list(length=page_size)
    
    return {
        "posts": [serialize_post(p) for p in posts],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/posts/{slug}")
async def get_public_post(slug: str):
    """Get a single published blog post by slug."""
    db = database.get_db()
    
    post = await db.blog_posts.find_one({
        "slug": slug,
        "status": "published",
    })
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Increment view count
    await db.blog_posts.update_one(
        {"_id": post["_id"]},
        {"$inc": {"view_count": 1}}
    )
    
    return {"post": serialize_post(post)}


@router.get("/categories")
async def get_public_categories():
    """Get categories with post counts."""
    db = database.get_db()
    
    pipeline = [
        {"$match": {"status": "published"}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    
    cursor = db.blog_posts.aggregate(pipeline)
    categories = [{"name": doc["_id"], "count": doc["count"]} async for doc in cursor]
    
    return {"categories": categories}


@router.get("/tags/popular")
async def get_popular_tags(limit: int = Query(20, ge=1, le=50)):
    """Get popular tags with post counts."""
    db = database.get_db()
    
    pipeline = [
        {"$match": {"status": "published"}},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    
    cursor = db.blog_posts.aggregate(pipeline)
    tags = [{"name": doc["_id"], "count": doc["count"]} async for doc in cursor]
    
    return {"tags": tags}


@router.get("/featured")
async def get_featured_posts(limit: int = Query(3, ge=1, le=10)):
    """Get featured/recent published posts."""
    db = database.get_db()
    
    cursor = db.blog_posts.find(
        {"status": "published"},
        {"content": 0}
    ).sort("published_at", -1).limit(limit)
    
    posts = await cursor.to_list(length=limit)
    
    return {"posts": [serialize_post(p) for p in posts]}
