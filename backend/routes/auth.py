from fastapi import APIRouter, HTTPException, Request, status
from database import database
from models import (
    LoginRequest, SetPasswordRequest, TokenResponse,
    UserRole, UserStatus, PasswordStatus, OnboardingStatus, AuditAction
)
from auth import verify_password, hash_password, create_access_token, hash_token, validate_password_strength
from utils.audit import create_audit_log
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login", response_model=TokenResponse)
async def login(request: Request, credentials: LoginRequest):
    """Client login endpoint."""
    db = database.get_db()
    
    try:
        # Find portal user
        portal_user = await db.portal_users.find_one(
            {"auth_email": credentials.email},
            {"_id": 0}
        )
        
        if not portal_user:
            await create_audit_log(
                action=AuditAction.USER_LOGIN_FAILED,
                metadata={"email": credentials.email, "reason": "user_not_found"}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Verify password
        if not portal_user.get("password_hash") or not verify_password(
            credentials.password,
            portal_user["password_hash"]
        ):
            await create_audit_log(
                action=AuditAction.USER_LOGIN_FAILED,
                actor_id=portal_user["portal_user_id"],
                metadata={"email": credentials.email, "reason": "invalid_password"}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Check user status
        if portal_user["status"] != UserStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active"
            )
        
        # Check password status
        if portal_user["password_status"] != PasswordStatus.SET.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Password not set"
            )
        
        # Admin users don't need client association
        client = None
        if portal_user["role"] == UserRole.ROLE_ADMIN.value:
            # Admin login - no client check needed
            pass
        else:
            # Get client info for non-admin users
            client = await db.clients.find_one(
                {"client_id": portal_user["client_id"]},
                {"_id": 0}
            )
            
            if not client:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Client not found"
                )
            
            # Check provisioning for client users
            if client["onboarding_status"] != OnboardingStatus.PROVISIONED.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account provisioning incomplete"
                )
        
        # Update last login
        await db.portal_users.update_one(
            {"portal_user_id": portal_user["portal_user_id"]},
            {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}}
        )
        
        # Create access token
        token_data = {
            "portal_user_id": portal_user["portal_user_id"],
            "client_id": portal_user["client_id"],
            "email": portal_user["auth_email"],
            "role": portal_user["role"]
        }
        access_token = create_access_token(token_data)
        
        await create_audit_log(
            action=AuditAction.USER_LOGIN_SUCCESS,
            actor_role=UserRole(portal_user["role"]),
            actor_id=portal_user["portal_user_id"],
            client_id=portal_user["client_id"]
        )
        
        # Check if this is first login and emit enablement event
        try:
            login_count = portal_user.get("login_count", 0)
            if login_count == 0:
                from services.enablement_service import emit_enablement_event
                from models.enablement import EnablementEventType
                
                # Get client info
                client = await db.clients.find_one(
                    {"client_id": portal_user["client_id"]},
                    {"_id": 0, "plan_code": 1}
                )
                
                await emit_enablement_event(
                    event_type=EnablementEventType.FIRST_LOGIN,
                    client_id=portal_user["client_id"],
                    plan_code=client.get("plan_code") if client else None,
                    context_payload={"email": portal_user["auth_email"]}
                )
                
            # Increment login count
            await db.portal_users.update_one(
                {"portal_user_id": portal_user["portal_user_id"]},
                {"$inc": {"login_count": 1}}
            )
        except Exception as enable_err:
            logger.warning(f"Failed to emit first login event: {enable_err}")
        
        return TokenResponse(
            access_token=access_token,
            user={
                "portal_user_id": portal_user["portal_user_id"],
                "email": portal_user["auth_email"],
                "role": portal_user["role"],
                "client_id": portal_user["client_id"]
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.post("/set-password")
async def set_password(request: Request, data: SetPasswordRequest):
    """Set password using token (production-safe)."""
    db = database.get_db()
    
    try:
        # Hash the provided token
        token_hash_value = hash_token(data.token)
        
        # Find token
        password_token = await db.password_tokens.find_one(
            {"token_hash": token_hash_value},
            {"_id": 0}
        )
        
        if not password_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password setup link"
            )
        
        # Validate token
        now = datetime.now(timezone.utc)
        
        # Handle both string and datetime objects, ensure timezone-aware
        expires_at_raw = password_token["expires_at"]
        if isinstance(expires_at_raw, str):
            expires_at = datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
        elif isinstance(expires_at_raw, datetime):
            # Ensure timezone-aware
            if expires_at_raw.tzinfo is None:
                expires_at = expires_at_raw.replace(tzinfo=timezone.utc)
            else:
                expires_at = expires_at_raw
        else:
            expires_at = expires_at_raw
        
        if password_token.get("used_at"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This password setup link has already been used"
            )
        
        if password_token.get("revoked_at"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This password setup link has been revoked"
            )
        
        if now > expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This password setup link has expired"
            )
        
        # Validate password strength
        is_valid, message = validate_password_strength(data.password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        # Get portal user
        portal_user = await db.portal_users.find_one(
            {"portal_user_id": password_token["portal_user_id"]},
            {"_id": 0}
        )
        
        if not portal_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if this is an admin user - admin users don't need client provisioning check
        is_admin = portal_user.get("role") == UserRole.ROLE_ADMIN.value
        
        if not is_admin:
            # Check client provisioning only for non-admin users
            client = await db.clients.find_one(
                {"client_id": password_token["client_id"]},
                {"_id": 0}
            )
            
            if not client or client["onboarding_status"] != OnboardingStatus.PROVISIONED.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Account provisioning incomplete"
                )
        
        # Hash password
        password_hash = hash_password(data.password)
        
        # Update portal user
        await db.portal_users.update_one(
            {"portal_user_id": portal_user["portal_user_id"]},
            {
                "$set": {
                    "password_hash": password_hash,
                    "password_status": PasswordStatus.SET.value,
                    "must_set_password": False,
                    "status": UserStatus.ACTIVE.value
                }
            }
        )
        
        # Mark token as used
        await db.password_tokens.update_one(
            {"token_hash": token_hash_value},
            {"$set": {"used": True, "used_at": now.isoformat()}}
        )
        
        # Audit logs - differentiate between admin invite acceptance and regular password setup
        is_admin_invite = password_token.get("client_id") == "ADMIN_INVITE"
        
        await create_audit_log(
            action=AuditAction.PASSWORD_TOKEN_VALIDATED,
            actor_id=portal_user["portal_user_id"],
            client_id=None if is_admin_invite else password_token.get("client_id")
        )
        
        if is_admin_invite:
            await create_audit_log(
                action=AuditAction.ADMIN_INVITE_ACCEPTED,
                actor_role=UserRole.ROLE_ADMIN,
                actor_id=portal_user["portal_user_id"],
                metadata={
                    "email": portal_user["auth_email"],
                    "accepted_at": now.isoformat()
                }
            )
        else:
            await create_audit_log(
                action=AuditAction.PASSWORD_SET_SUCCESS,
                actor_id=portal_user["portal_user_id"],
                client_id=password_token.get("client_id")
            )
        
        # Create access token for auto-login
        token_data = {
            "portal_user_id": portal_user["portal_user_id"],
            "client_id": portal_user.get("client_id"),
            "email": portal_user["auth_email"],
            "role": portal_user["role"]
        }
        access_token = create_access_token(token_data)
        
        await create_audit_log(
            action=AuditAction.USER_AUTHENTICATED_POST_SETUP,
            actor_role=UserRole(portal_user["role"]),
            actor_id=portal_user["portal_user_id"],
            client_id=portal_user.get("client_id")
        )
        
        return {
            "message": "Password set successfully",
            "access_token": access_token,
            "user": {
                "portal_user_id": portal_user["portal_user_id"],
                "email": portal_user["auth_email"],
                "role": portal_user["role"],
                "client_id": portal_user.get("client_id")
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Set password error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set password"
        )

@router.post("/admin/login", response_model=TokenResponse)
async def admin_login(request: Request, credentials: LoginRequest):
    """
    Admin login endpoint - FULLY INDEPENDENT of client provisioning.
    
    Admins:
    - Do NOT require a Client record
    - Are NOT blocked by onboarding_status, provisioning, or client guards
    - Can log in as long as they have a valid password and ACTIVE status
    """
    db = database.get_db()
    
    try:
        # Find admin user - ONLY check role, no client association needed
        portal_user = await db.portal_users.find_one(
            {
                "auth_email": credentials.email,
                "role": UserRole.ROLE_ADMIN.value
            },
            {"_id": 0}
        )
        
        if not portal_user:
            await create_audit_log(
                action=AuditAction.ADMIN_LOGIN_FAILED,
                metadata={"email": credentials.email, "reason": "admin_not_found"}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Verify password exists and is correct
        if not portal_user.get("password_hash") or not verify_password(
            credentials.password,
            portal_user["password_hash"]
        ):
            await create_audit_log(
                action=AuditAction.ADMIN_LOGIN_FAILED,
                actor_id=portal_user["portal_user_id"],
                metadata={"email": credentials.email, "reason": "invalid_password"}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Check user status - admin must be ACTIVE
        if portal_user.get("status") != UserStatus.ACTIVE.value:
            await create_audit_log(
                action=AuditAction.ADMIN_LOGIN_FAILED,
                actor_id=portal_user["portal_user_id"],
                metadata={"email": credentials.email, "reason": "account_not_active", "status": portal_user.get("status")}
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active"
            )
        
        # Check password status - must have set password
        if portal_user.get("password_status") != PasswordStatus.SET.value:
            await create_audit_log(
                action=AuditAction.ADMIN_LOGIN_FAILED,
                actor_id=portal_user["portal_user_id"],
                metadata={"email": credentials.email, "reason": "password_not_set"}
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Password not set"
            )
        
        # Update last login timestamp
        await db.portal_users.update_one(
            {"portal_user_id": portal_user["portal_user_id"]},
            {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}}
        )
        
        # Create access token - NO client_id required for admins
        token_data = {
            "portal_user_id": portal_user["portal_user_id"],
            "client_id": None,  # Admins don't need client association
            "email": portal_user["auth_email"],
            "role": portal_user["role"]
        }
        access_token = create_access_token(token_data)
        
        await create_audit_log(
            action=AuditAction.ADMIN_LOGIN_SUCCESS,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=portal_user["portal_user_id"],
            metadata={"email": credentials.email}
        )
        
        return TokenResponse(
            access_token=access_token,
            user={
                "portal_user_id": portal_user["portal_user_id"],
                "email": portal_user["auth_email"],
                "role": portal_user["role"]
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )



@router.post("/log-route-guard-block")
async def log_route_guard_block(request: Request):
    """Log when a non-admin user attempts to access admin routes.
    
    This endpoint is called by the frontend when the route guard blocks access.
    """
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header else None
        
        user_info = {}
        if token:
            from auth import decode_access_token
            payload = decode_access_token(token)
            if payload:
                user_info = {
                    "portal_user_id": payload.get("portal_user_id"),
                    "email": payload.get("email"),
                    "role": payload.get("role")
                }
        
        # Get attempted path from request body
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        attempted_path = body.get("attempted_path", "unknown")
        
        await create_audit_log(
            action=AuditAction.ADMIN_ROUTE_GUARD_BLOCK,
            actor_id=user_info.get("portal_user_id"),
            metadata={
                "attempted_path": attempted_path,
                "user_role": user_info.get("role"),
                "email": user_info.get("email"),
                "reason": "non_admin_accessing_admin_route"
            }
        )
        
        return {"status": "logged"}
    except Exception as e:
        logger.error(f"Failed to log route guard block: {e}")
        return {"status": "error"}