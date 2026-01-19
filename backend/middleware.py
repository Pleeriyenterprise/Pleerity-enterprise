from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional, Callable
from datetime import datetime, timezone
import logging
from auth import decode_access_token
from models import UserRole, OnboardingStatus, PasswordStatus
from database import database

logger = logging.getLogger(__name__)

async def get_current_user(request: Request) -> Optional[dict]:
    """Extract and validate current user from JWT token."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ")[1]
    payload = decode_access_token(token)
    
    if not payload:
        return None
    
    return payload

async def require_auth(request: Request) -> dict:
    """Require valid authentication."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user

async def require_role(request: Request, required_role: UserRole) -> dict:
    """Require specific role."""
    user = await require_auth(request)
    user_role = user.get("role")
    
    role_hierarchy = {
        UserRole.ROLE_ADMIN.value: 3,
        UserRole.ROLE_CLIENT_ADMIN.value: 2,
        UserRole.ROLE_CLIENT.value: 1
    }
    
    if role_hierarchy.get(user_role, 0) < role_hierarchy.get(required_role.value, 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    return user

async def require_admin(request: Request) -> dict:
    """Require admin role."""
    return await require_role(request, UserRole.ROLE_ADMIN)

async def client_route_guard(request: Request) -> dict:
    """Guard for client routes - checks auth, provisioning, password status."""
    user = await require_auth(request)
    
    db = database.get_db()
    
    # Get portal user
    portal_user = await db.portal_users.find_one(
        {"portal_user_id": user["portal_user_id"]},
        {"_id": 0}
    )
    
    if not portal_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Check user status
    if portal_user["status"] != "ACTIVE":
        await log_route_guard_redirect(
            user["portal_user_id"],
            str(request.url.path),
            "USER_NOT_ACTIVE"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active"
        )
    
    # Check password status
    if portal_user["password_status"] != PasswordStatus.SET.value:
        await log_route_guard_redirect(
            user["portal_user_id"],
            str(request.url.path),
            "PASSWORD_NOT_SET"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password not set",
            headers={"X-Redirect": "/set-password"}
        )
    
    # Get client
    client = await db.clients.find_one(
        {"client_id": user["client_id"]},
        {"_id": 0}
    )
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Check provisioning status
    if client["onboarding_status"] != OnboardingStatus.PROVISIONED.value:
        await log_route_guard_redirect(
            user["portal_user_id"],
            str(request.url.path),
            "PROVISIONING_INCOMPLETE"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Provisioning incomplete",
            headers={"X-Redirect": "/onboarding-status"}
        )
    
    return user

async def admin_route_guard(request: Request) -> dict:
    """Guard for admin routes."""
    user = await require_admin(request)
    return user

async def log_route_guard_redirect(user_id: str, path: str, reason: str):
    """Log route guard redirect for audit."""
    from utils.audit import create_audit_log
    from models import AuditAction
    
    await create_audit_log(
        action=AuditAction.ROUTE_GUARD_REDIRECT,
        metadata={
            "path": path,
            "reason": reason,
            "user_id": user_id
        }
    )
