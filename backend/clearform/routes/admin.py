"""ClearForm Admin Routes

Backend endpoints for ClearForm administration panel.
Requires admin authentication (from main Pleerity admin auth).
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import Optional
from datetime import datetime, timezone
import logging

from database import database
from middleware import admin_route_guard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/clearform", tags=["ClearForm Admin"], dependencies=[Depends(admin_route_guard)])


# ============================================================================
# Users Admin
# ============================================================================

@router.get("/users")
async def get_clearform_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=200),
    search: Optional[str] = None,
    
):
    """Get all ClearForm users with stats."""
    db = database.get_db()
    
    # Build query
    query = {}
    if search:
        query["$or"] = [
            {"email": {"$regex": search, "$options": "i"}},
            {"full_name": {"$regex": search, "$options": "i"}},
        ]
    
    # Get users with counts
    pipeline = [
        {"$match": query},
        {"$lookup": {
            "from": "clearform_documents",
            "localField": "user_id",
            "foreignField": "user_id",
            "as": "documents"
        }},
        {"$addFields": {
            "documents_count": {"$size": "$documents"}
        }},
        {"$project": {
            "_id": 0,
            "user_id": 1,
            "email": 1,
            "full_name": 1,
            "status": 1,
            "credit_balance": 1,
            "subscription_plan": 1,
            "documents_count": 1,
            "created_at": 1,
            "last_login_at": 1,
        }},
        {"$sort": {"created_at": -1}},
        {"$skip": (page - 1) * page_size},
        {"$limit": page_size},
    ]
    
    users = await db.clearform_users.aggregate(pipeline).to_list(length=page_size)
    total = await db.clearform_users.count_documents(query)
    
    return {
        "users": users,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": page * page_size < total,
    }


@router.get("/stats")
async def get_clearform_stats():
    """Get overall ClearForm statistics."""
    db = database.get_db()
    
    total_users = await db.clearform_users.count_documents({})
    active_users = await db.clearform_users.count_documents({"status": "ACTIVE"})
    total_documents = await db.clearform_documents.count_documents({})
    
    # Sum credits used
    pipeline = [
        {"$group": {
            "_id": None,
            "total_credits_used": {"$sum": "$lifetime_credits_used"}
        }}
    ]
    credit_result = await db.clearform_users.aggregate(pipeline).to_list(length=1)
    total_credits_used = credit_result[0]["total_credits_used"] if credit_result else 0
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_documents": total_documents,
        "total_credits_used": total_credits_used,
    }


@router.get("/users/{user_id}")
async def get_clearform_user(
    user_id: str,
    
):
    """Get detailed info for a specific ClearForm user."""
    db = database.get_db()
    
    user = await db.clearform_users.find_one(
        {"user_id": user_id},
        {"_id": 0, "hashed_password": 0}
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get user's documents
    documents = await db.clearform_documents.find(
        {"user_id": user_id},
        {"_id": 0, "content_markdown": 0}
    ).sort("created_at", -1).limit(20).to_list(length=20)
    
    # Get credit transactions
    transactions = await db.clearform_credit_transactions.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(length=20)
    
    return {
        "user": user,
        "documents": documents,
        "transactions": transactions,
    }


# ============================================================================
# Documents Admin
# ============================================================================

@router.get("/documents")
async def get_clearform_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=200),
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    
):
    """Get all ClearForm documents."""
    db = database.get_db()
    
    # Build query
    query = {}
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"document_id": {"$regex": search, "$options": "i"}},
        ]
    if status_filter:
        query["status"] = status_filter
    
    # Get documents with user email
    pipeline = [
        {"$match": query},
        {"$lookup": {
            "from": "clearform_users",
            "localField": "user_id",
            "foreignField": "user_id",
            "as": "user"
        }},
        {"$addFields": {
            "user_email": {"$arrayElemAt": ["$user.email", 0]}
        }},
        {"$project": {
            "_id": 0,
            "document_id": 1,
            "user_id": 1,
            "user_email": 1,
            "title": 1,
            "document_type": 1,
            "status": 1,
            "credits_used": 1,
            "created_at": 1,
            "completed_at": 1,
        }},
        {"$sort": {"created_at": -1}},
        {"$skip": (page - 1) * page_size},
        {"$limit": page_size},
    ]
    
    documents = await db.clearform_documents.aggregate(pipeline).to_list(length=page_size)
    total = await db.clearform_documents.count_documents(query)
    
    return {
        "documents": documents,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": page * page_size < total,
    }


@router.get("/documents/stats")
async def get_clearform_documents_stats():
    """Get document statistics."""
    db = database.get_db()
    
    total = await db.clearform_documents.count_documents({})
    completed = await db.clearform_documents.count_documents({"status": "COMPLETED"})
    failed = await db.clearform_documents.count_documents({"status": "FAILED"})
    pending = await db.clearform_documents.count_documents(
        {"status": {"$in": ["PENDING", "GENERATING"]}}
    )
    
    return {
        "total": total,
        "completed": completed,
        "failed": failed,
        "pending": pending,
    }


@router.get("/documents/{document_id}")
async def get_clearform_document(
    document_id: str,
    
):
    """Get detailed info for a specific document."""
    db = database.get_db()
    
    doc = await db.clearform_documents.find_one(
        {"document_id": document_id},
        {"_id": 0}
    )
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Get user info
    user = await db.clearform_users.find_one(
        {"user_id": doc.get("user_id")},
        {"_id": 0, "email": 1, "full_name": 1}
    )
    
    doc["user_email"] = user.get("email") if user else None
    doc["user_name"] = user.get("full_name") if user else None
    
    return doc


# ============================================================================
# Organizations Admin
# ============================================================================

@router.get("/organizations")
async def get_clearform_organizations(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=200),
    
):
    """Get all ClearForm organizations."""
    db = database.get_db()
    
    orgs = await db.clearform_organizations.find(
        {},
        {"_id": 0}
    ).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size).to_list(length=page_size)
    
    total = await db.clearform_organizations.count_documents({})
    
    return {
        "organizations": orgs,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ============================================================================
# Audit Logs Admin
# ============================================================================

@router.get("/audit")
async def get_clearform_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, le=500),
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    
):
    """Get ClearForm audit logs."""
    db = database.get_db()
    
    query = {}
    if action:
        query["action"] = action
    if user_id:
        query["user_id"] = user_id
    
    logs = await db.clearform_audit_logs.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size).to_list(length=page_size)
    
    total = await db.clearform_audit_logs.count_documents(query)
    
    return {
        "logs": logs,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ============================================================================
# Document Types Admin
# ============================================================================

@router.get("/document-types")
async def get_clearform_document_types():
    """Get all document types."""
    db = database.get_db()
    
    types = await db.clearform_document_types.find(
        {},
        {"_id": 0}
    ).to_list(length=200)
    
    categories = await db.clearform_document_categories.find(
        {},
        {"_id": 0}
    ).to_list(length=50)
    
    return {
        "document_types": types,
        "categories": categories,
    }
