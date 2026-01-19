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
        expires_at = datetime.fromisoformat(password_token["expires_at"]) if isinstance(password_token["expires_at"], str) else password_token["expires_at"]
        
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
        
        # Check client provisioning
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
            {"token_id": password_token["token_id"]},
            {"$set": {"used_at": now.isoformat()}}
        )
        
        # Audit logs
        await create_audit_log(
            action=AuditAction.PASSWORD_TOKEN_VALIDATED,
            actor_id=portal_user["portal_user_id"],
            client_id=password_token["client_id"]
        )
        
        await create_audit_log(
            action=AuditAction.PASSWORD_SET_SUCCESS,
            actor_id=portal_user["portal_user_id"],
            client_id=password_token["client_id"]
        )
        
        # Create access token for auto-login
        token_data = {
            "portal_user_id": portal_user["portal_user_id"],
            "client_id": portal_user["client_id"],
            "email": portal_user["auth_email"],
            "role": portal_user["role"]
        }
        access_token = create_access_token(token_data)
        
        await create_audit_log(
            action=AuditAction.USER_AUTHENTICATED_POST_SETUP,
            actor_role=UserRole(portal_user["role"]),
            actor_id=portal_user["portal_user_id"],
            client_id=portal_user["client_id"]
        )
        
        return {
            "message": "Password set successfully",
            "access_token": access_token,
            "user": {
                "portal_user_id": portal_user["portal_user_id"],
                "email": portal_user["auth_email"],
                "role": portal_user["role"],
                "client_id": portal_user["client_id"]
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
    """Admin login endpoint."""
    db = database.get_db()
    
    try:
        # Find admin user
        portal_user = await db.portal_users.find_one(
            {
                "auth_email": credentials.email,
                "role": UserRole.ROLE_ADMIN.value
            },
            {"_id": 0}
        )
        
        if not portal_user:
            await create_audit_log(
                action=AuditAction.USER_LOGIN_FAILED,
                metadata={"email": credentials.email, "reason": "admin_not_found"}
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
        
        # Create access token
        token_data = {
            "portal_user_id": portal_user["portal_user_id"],
            "client_id": portal_user.get("client_id"),
            "email": portal_user["auth_email"],
            "role": portal_user["role"]
        }
        access_token = create_access_token(token_data)
        
        await create_audit_log(
            action=AuditAction.USER_LOGIN_SUCCESS,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=portal_user["portal_user_id"]
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
