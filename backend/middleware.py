from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, Callable
from datetime import datetime, timezone
import logging
import uuid
from auth import decode_access_token
from models import UserRole, OnboardingStatus, PasswordStatus
from database import database

logger = logging.getLogger(__name__)

CORRELATION_ID_HEADER = "X-Correlation-Id"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Set or forward X-Correlation-Id on every request; add to response for tracing."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = (request.headers.get(CORRELATION_ID_HEADER) or "").strip() or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        if CORRELATION_ID_HEADER not in response.headers:
            response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response

async def get_current_user(request: Request) -> Optional[dict]:
    """Extract and validate current user from JWT token. Validates session_version when present (force-logout)."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ")[1]
    payload = decode_access_token(token)
    
    if not payload:
        return None
    
    # If token carries session_version, verify it matches DB (force-logout invalidation)
    if "session_version" in payload:
        db = database.get_db()
        user_doc = await db.portal_users.find_one(
            {"portal_user_id": payload.get("portal_user_id")},
            {"_id": 0, "session_version": 1}
        )
        if user_doc is None:
            return None
        if user_doc.get("session_version", 0) != payload.get("session_version", 0):
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

# Staff roles that can access admin console (OWNER, ADMIN see all; SUPPORT/CONTENT see role-gated sections)
STAFF_ROLES = (UserRole.ROLE_OWNER.value, UserRole.ROLE_ADMIN.value, UserRole.ROLE_SUPPORT.value, UserRole.ROLE_CONTENT.value)

def _role_hierarchy() -> dict:
    return {
        UserRole.ROLE_OWNER.value: 4,
        UserRole.ROLE_ADMIN.value: 3,
        UserRole.ROLE_SUPPORT.value: 2,
        UserRole.ROLE_CONTENT.value: 2,
        UserRole.ROLE_AUDITOR.value: 1,  # Read-only admin; cannot pass require_owner_or_admin
        UserRole.ROLE_CLIENT_ADMIN.value: 1,
        UserRole.ROLE_CLIENT.value: 1,
        UserRole.ROLE_TENANT.value: 0,
    }


async def require_role(request: Request, required_role: UserRole) -> dict:
    """Require specific role."""
    user = await require_auth(request)
    user_role = user.get("role")
    role_hierarchy = _role_hierarchy()
    if role_hierarchy.get(user_role, 0) < role_hierarchy.get(required_role.value, 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    return user


async def require_role_in(request: Request, allowed_roles: tuple) -> dict:
    """Require user role to be one of allowed_roles (e.g. OWNER, ADMIN, SUPPORT)."""
    user = await require_auth(request)
    if user.get("role") not in [r.value if hasattr(r, "value") else r for r in allowed_roles]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return user

async def require_admin(request: Request) -> dict:
    """Require admin-capable role: Owner, Admin, Support, Content, or Auditor (read-only)."""
    return await require_role_in(
        request,
        (UserRole.ROLE_OWNER, UserRole.ROLE_ADMIN, UserRole.ROLE_SUPPORT, UserRole.ROLE_CONTENT, UserRole.ROLE_AUDITOR),
    )


async def require_support_or_above(request: Request) -> dict:
    """Allow OWNER, ADMIN, or SUPPORT (e.g. Support Dashboard, Notification Health)."""
    return await require_role_in(request, (UserRole.ROLE_OWNER, UserRole.ROLE_ADMIN, UserRole.ROLE_SUPPORT))


async def require_content_or_above(request: Request) -> dict:
    """Allow OWNER, ADMIN, or CONTENT (e.g. Site Builder, Blog, FAQ, Legal)."""
    return await require_role_in(request, (UserRole.ROLE_OWNER, UserRole.ROLE_ADMIN, UserRole.ROLE_CONTENT))

async def require_owner_or_admin(request: Request) -> dict:
    """Explicit RBAC: require OWNER or ADMIN (writes). Auditor cannot pass."""
    return await require_role_in(request, (UserRole.ROLE_OWNER, UserRole.ROLE_ADMIN))

async def require_owner(request: Request) -> dict:
    """Require owner role (OWNER-only actions)."""
    return await require_role(request, UserRole.ROLE_OWNER)

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

async def require_step_up_token(request: Request) -> dict:
    """
    For sensitive endpoints: require auth and valid X-Step-Up-Token header.
    Token is one-time use (consumed on success). Validates user match and expiry.
    """
    user = await require_auth(request)
    user_id = user.get("portal_user_id") or user.get("client_id")
    token = (request.headers.get("X-Step-Up-Token") or "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Step-up verification required",
        )
    from services.otp_service import consume_step_up_token
    valid = await consume_step_up_token(token, user_id)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired step-up token",
        )
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
