"""
Team Permissions & Role Management API
Provides endpoints for managing roles, permissions, and admin users
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, EmailStr

from middleware import admin_route_guard
from database import database
from models.core import AuditAction, UserRole
from models.permissions import (
    ALL_PERMISSIONS, BUILT_IN_ROLES, CustomRoleCreate, CustomRoleUpdate,
    RoleResponse, AdminUserCreate, AdminUserUpdate, AdminUserResponse,
    has_permission
)
from utils.audit import create_audit_log
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/team", tags=["Team Management"])


# ============================================
# Helper Functions
# ============================================

def generate_role_id() -> str:
    return f"ROLE-{uuid.uuid4().hex[:12].upper()}"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


async def check_team_permission(admin: dict, action: str) -> bool:
    """Check if admin has team management permission"""
    db = database.get_db()
    
    # Super admins always have access
    if admin.get("role") == UserRole.ROLE_ADMIN.value:
        admin_user = await db.portal_users.find_one(
            {"portal_user_id": admin.get("portal_user_id")},
            {"_id": 0, "role_id": 1}
        )
        if admin_user and admin_user.get("role_id") == "super_admin":
            return True
    
    # Check custom permissions
    role_id = admin.get("role_id", "super_admin")
    
    if role_id in BUILT_IN_ROLES:
        permissions = BUILT_IN_ROLES[role_id]["permissions"]
    else:
        custom_role = await db.custom_roles.find_one({"role_id": role_id}, {"_id": 0})
        permissions = custom_role.get("permissions", {}) if custom_role else {}
    
    return has_permission(permissions, "team", action)


# ============================================
# Permissions Configuration
# ============================================

@router.get("/permissions")
async def get_all_permissions(admin: dict = Depends(admin_route_guard)):
    """Get all available permissions in the system"""
    return {
        "permissions": ALL_PERMISSIONS,
        "categories": list(ALL_PERMISSIONS.keys())
    }


# ============================================
# Role Management
# ============================================

@router.get("/roles")
async def list_roles(admin: dict = Depends(admin_route_guard)):
    """List all roles (built-in and custom)"""
    db = database.get_db()
    
    # Get custom roles
    cursor = db.custom_roles.find({"is_active": True}, {"_id": 0})
    custom_roles = await cursor.to_list(100)
    
    # Count users per role
    role_user_counts = {}
    async for doc in db.portal_users.aggregate([
        {"$match": {"role": UserRole.ROLE_ADMIN.value}},
        {"$group": {"_id": "$role_id", "count": {"$sum": 1}}}
    ]):
        role_user_counts[doc["_id"]] = doc["count"]
    
    roles = []
    
    # Add built-in roles
    for role_id, role_data in BUILT_IN_ROLES.items():
        roles.append({
            "role_id": role_id,
            "name": role_data["name"],
            "description": role_data["description"],
            "is_system": role_data["is_system"],
            "is_active": True,
            "permissions": role_data["permissions"],
            "user_count": role_user_counts.get(role_id, 0),
            "created_at": "2024-01-01T00:00:00Z",
        })
    
    # Add custom roles
    for role in custom_roles:
        roles.append({
            **role,
            "user_count": role_user_counts.get(role["role_id"], 0)
        })
    
    return {"roles": roles, "total": len(roles)}


@router.get("/roles/{role_id}")
async def get_role(role_id: str, admin: dict = Depends(admin_route_guard)):
    """Get role details"""
    db = database.get_db()
    
    # Check built-in roles
    if role_id in BUILT_IN_ROLES:
        role_data = BUILT_IN_ROLES[role_id]
        return {
            "role_id": role_id,
            "name": role_data["name"],
            "description": role_data["description"],
            "is_system": role_data["is_system"],
            "is_active": True,
            "permissions": role_data["permissions"],
        }
    
    # Check custom roles
    role = await db.custom_roles.find_one({"role_id": role_id}, {"_id": 0})
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    return role


@router.post("/roles")
async def create_role(
    request: CustomRoleCreate,
    admin: dict = Depends(admin_route_guard)
):
    """Create a custom role"""
    db = database.get_db()
    
    # Check permission
    if not await check_team_permission(admin, "manage"):
        raise HTTPException(status_code=403, detail="Insufficient permissions to create roles")
    
    # Validate permissions
    for category, actions in request.permissions.items():
        if category not in ALL_PERMISSIONS:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
        valid_actions = ALL_PERMISSIONS[category]["actions"]
        for action in actions:
            if action not in valid_actions:
                raise HTTPException(status_code=400, detail=f"Invalid action '{action}' for category '{category}'")
    
    role_id = generate_role_id()
    now = now_utc()
    
    role = {
        "role_id": role_id,
        "name": request.name,
        "description": request.description,
        "is_system": False,
        "is_active": True,
        "permissions": request.permissions,
        "created_at": now,
        "updated_at": now,
        "created_by": admin.get("portal_user_id"),
    }
    
    await db.custom_roles.insert_one(role)
    
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=admin.get("portal_user_id"),
        resource_type="role",
        resource_id=role_id,
        metadata={"action": "create", "name": request.name}
    )
    
    if "_id" in role:
        del role["_id"]
    return role


@router.put("/roles/{role_id}")
async def update_role(
    role_id: str,
    request: CustomRoleUpdate,
    admin: dict = Depends(admin_route_guard)
):
    """Update a custom role"""
    db = database.get_db()
    
    # Check permission
    if not await check_team_permission(admin, "manage"):
        raise HTTPException(status_code=403, detail="Insufficient permissions to update roles")
    
    # Cannot update built-in roles
    if role_id in BUILT_IN_ROLES:
        raise HTTPException(status_code=400, detail="Cannot modify built-in roles")
    
    # Check role exists
    role = await db.custom_roles.find_one({"role_id": role_id})
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Build update
    updates = {"updated_at": now_utc()}
    
    if request.name is not None:
        updates["name"] = request.name
    if request.description is not None:
        updates["description"] = request.description
    if request.is_active is not None:
        updates["is_active"] = request.is_active
    if request.permissions is not None:
        # Validate permissions
        for category, actions in request.permissions.items():
            if category not in ALL_PERMISSIONS:
                raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
        updates["permissions"] = request.permissions
    
    await db.custom_roles.update_one(
        {"role_id": role_id},
        {"$set": updates}
    )
    
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=admin.get("portal_user_id"),
        resource_type="role",
        resource_id=role_id,
        metadata={"action": "update", "updates": list(updates.keys())}
    )
    
    return {"success": True, "role_id": role_id}


@router.delete("/roles/{role_id}")
async def delete_role(role_id: str, admin: dict = Depends(admin_route_guard)):
    """Delete a custom role (deactivate)"""
    db = database.get_db()
    
    # Check permission
    if not await check_team_permission(admin, "manage"):
        raise HTTPException(status_code=403, detail="Insufficient permissions to delete roles")
    
    # Cannot delete built-in roles
    if role_id in BUILT_IN_ROLES:
        raise HTTPException(status_code=400, detail="Cannot delete built-in roles")
    
    # Check if role has users
    user_count = await db.portal_users.count_documents({"role_id": role_id})
    if user_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete role with {user_count} assigned users. Reassign users first."
        )
    
    # Soft delete
    result = await db.custom_roles.update_one(
        {"role_id": role_id},
        {"$set": {"is_active": False, "deleted_at": now_utc()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Role not found")
    
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=admin.get("portal_user_id"),
        resource_type="role",
        resource_id=role_id,
        metadata={"action": "delete"}
    )
    
    return {"success": True}


# ============================================
# Admin User Management
# ============================================

@router.get("/users")
async def list_admin_users(
    role_id: Optional[str] = None,
    status: Optional[str] = None,
    admin: dict = Depends(admin_route_guard)
):
    """List admin users"""
    db = database.get_db()
    
    query = {"role": UserRole.ROLE_ADMIN.value}
    if role_id:
        query["role_id"] = role_id
    if status:
        query["status"] = status
    
    cursor = db.portal_users.find(query, {"_id": 0, "password_hash": 0})
    users = await cursor.to_list(500)
    
    # Enrich with role names
    for user in users:
        role_id = user.get("role_id", "super_admin")
        if role_id in BUILT_IN_ROLES:
            user["role_name"] = BUILT_IN_ROLES[role_id]["name"]
        else:
            custom_role = await db.custom_roles.find_one({"role_id": role_id}, {"_id": 0, "name": 1})
            user["role_name"] = custom_role["name"] if custom_role else "Unknown"
    
    return {"users": users, "total": len(users)}


@router.post("/users")
async def create_admin_user(
    request: AdminUserCreate,
    admin: dict = Depends(admin_route_guard)
):
    """Create a new admin user"""
    db = database.get_db()
    
    # Check permission
    if not await check_team_permission(admin, "create"):
        raise HTTPException(status_code=403, detail="Insufficient permissions to create users")
    
    # Check if email exists
    existing = await db.portal_users.find_one({"email": request.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Validate role
    if request.role_id not in BUILT_IN_ROLES:
        custom_role = await db.custom_roles.find_one({"role_id": request.role_id, "is_active": True})
        if not custom_role:
            raise HTTPException(status_code=400, detail="Invalid role")
    
    now = now_utc()
    portal_user_id = f"ADM-{uuid.uuid4().hex[:12].upper()}"
    
    user = {
        "portal_user_id": portal_user_id,
        "email": request.email.lower(),
        "name": request.name,
        "role": UserRole.ROLE_ADMIN.value,
        "role_id": request.role_id,
        "status": "INVITED" if request.send_invite else "ACTIVE",
        "password_status": "NOT_SET",
        "password_hash": None,
        "created_at": now,
        "updated_at": now,
        "created_by": admin.get("portal_user_id"),
    }
    
    await db.portal_users.insert_one(user)
    
    # TODO: Send invite email if send_invite is True
    
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=admin.get("portal_user_id"),
        resource_type="admin_user",
        resource_id=portal_user_id,
        metadata={"action": "create", "email": request.email, "role_id": request.role_id}
    )
    
    if "_id" in user:
        del user["_id"]
    del user["password_hash"]
    return user


@router.put("/users/{user_id}")
async def update_admin_user(
    user_id: str,
    request: AdminUserUpdate,
    admin: dict = Depends(admin_route_guard)
):
    """Update an admin user"""
    db = database.get_db()
    
    # Check permission
    if not await check_team_permission(admin, "edit"):
        raise HTTPException(status_code=403, detail="Insufficient permissions to edit users")
    
    # Get user
    user = await db.portal_users.find_one({"portal_user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Cannot modify own super_admin status
    if user_id == admin.get("portal_user_id") and request.role_id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    
    updates = {"updated_at": now_utc()}
    
    if request.name is not None:
        updates["name"] = request.name
    if request.role_id is not None:
        # Validate role
        if request.role_id not in BUILT_IN_ROLES:
            custom_role = await db.custom_roles.find_one({"role_id": request.role_id, "is_active": True})
            if not custom_role:
                raise HTTPException(status_code=400, detail="Invalid role")
        updates["role_id"] = request.role_id
    if request.is_active is not None:
        updates["status"] = "ACTIVE" if request.is_active else "DISABLED"
    
    await db.portal_users.update_one(
        {"portal_user_id": user_id},
        {"$set": updates}
    )
    
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=admin.get("portal_user_id"),
        resource_type="admin_user",
        resource_id=user_id,
        metadata={"action": "update", "updates": list(updates.keys())}
    )
    
    return {"success": True}


@router.delete("/users/{user_id}")
async def deactivate_admin_user(user_id: str, admin: dict = Depends(admin_route_guard)):
    """Deactivate an admin user"""
    db = database.get_db()
    
    # Check permission
    if not await check_team_permission(admin, "delete"):
        raise HTTPException(status_code=403, detail="Insufficient permissions to delete users")
    
    # Cannot delete self
    if user_id == admin.get("portal_user_id"):
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    
    result = await db.portal_users.update_one(
        {"portal_user_id": user_id},
        {"$set": {"status": "DISABLED", "updated_at": now_utc()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=admin.get("portal_user_id"),
        resource_type="admin_user",
        resource_id=user_id,
        metadata={"action": "deactivate"}
    )
    
    return {"success": True}


# ============================================
# Current User Permissions
# ============================================

@router.get("/me/permissions")
async def get_my_permissions(admin: dict = Depends(admin_route_guard)):
    """Get current admin user's permissions"""
    db = database.get_db()
    
    # Get user's role
    user = await db.portal_users.find_one(
        {"portal_user_id": admin.get("portal_user_id")},
        {"_id": 0, "role_id": 1}
    )
    
    role_id = user.get("role_id", "super_admin") if user else "super_admin"
    
    # Get permissions
    if role_id in BUILT_IN_ROLES:
        permissions = BUILT_IN_ROLES[role_id]["permissions"]
        role_name = BUILT_IN_ROLES[role_id]["name"]
    else:
        custom_role = await db.custom_roles.find_one({"role_id": role_id}, {"_id": 0})
        if custom_role:
            permissions = custom_role.get("permissions", {})
            role_name = custom_role.get("name", "Custom Role")
        else:
            permissions = BUILT_IN_ROLES["super_admin"]["permissions"]
            role_name = "Super Admin"
    
    return {
        "role_id": role_id,
        "role_name": role_name,
        "permissions": permissions
    }
