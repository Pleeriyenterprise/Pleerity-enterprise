"""ClearForm Authentication Routes

Endpoints:
- POST /api/clearform/auth/register - Register new user
- POST /api/clearform/auth/login - User login
- GET /api/clearform/auth/me - Get current user
- PUT /api/clearform/auth/profile - Update profile
- POST /api/clearform/auth/change-password - Change password
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
import logging
import asyncio

from clearform.models.user import (
    ClearFormUserCreate,
    ClearFormUserResponse,
    ClearFormUserLogin,
    ClearFormTokenResponse,
)
from clearform.services.clearform_auth import clearform_auth_service
from services.email_service import email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clearform/auth", tags=["ClearForm Auth"])


async def get_current_clearform_user(authorization: Optional[str] = Header(None)):
    """Dependency to get current ClearForm user from token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization[7:]
    user = await clearform_auth_service.get_current_user(token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return user


@router.post("/register", response_model=ClearFormTokenResponse)
async def register(data: ClearFormUserCreate):
    """Register a new ClearForm user.
    
    Returns auth token and user info. New users get 5 welcome credits.
    Sends branded welcome email.
    """
    try:
        user = await clearform_auth_service.register(data)
        
        # Auto-login after registration
        login_response = await clearform_auth_service.login(
            ClearFormUserLogin(email=data.email, password=data.password)
        )
        
        # Send welcome email (fire-and-forget, don't block response)
        asyncio.create_task(
            email_service.send_clearform_welcome_email(
                recipient=user.email,
                full_name=user.full_name,
                user_id=user.user_id,
                credit_balance=user.credit_balance,
            )
        )
        
        return login_response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/login", response_model=ClearFormTokenResponse)
async def login(data: ClearFormUserLogin):
    """Login to ClearForm.
    
    Returns auth token and user info.
    """
    try:
        return await clearform_auth_service.login(data)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.get("/me", response_model=ClearFormUserResponse)
async def get_me(user = Depends(get_current_clearform_user)):
    """Get current user info."""
    return ClearFormUserResponse(
        user_id=user.user_id,
        email=user.email,
        full_name=user.full_name,
        status=user.status,
        email_verified=user.email_verified,
        credit_balance=user.credit_balance,
        lifetime_credits_purchased=user.lifetime_credits_purchased,
        lifetime_credits_used=user.lifetime_credits_used,
        subscription_id=user.subscription_id,
        subscription_plan=user.subscription_plan,
        next_credit_grant_at=user.next_credit_grant_at,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.put("/profile", response_model=ClearFormUserResponse)
async def update_profile(
    full_name: Optional[str] = None,
    user = Depends(get_current_clearform_user),
):
    """Update user profile."""
    try:
        updated = await clearform_auth_service.update_profile(
            user_id=user.user_id,
            full_name=full_name,
        )
        return ClearFormUserResponse(
            user_id=updated.user_id,
            email=updated.email,
            full_name=updated.full_name,
            status=updated.status,
            email_verified=updated.email_verified,
            credit_balance=updated.credit_balance,
            lifetime_credits_purchased=updated.lifetime_credits_purchased,
            lifetime_credits_used=updated.lifetime_credits_used,
            subscription_id=updated.subscription_id,
            subscription_plan=updated.subscription_plan,
            next_credit_grant_at=updated.next_credit_grant_at,
            created_at=updated.created_at,
            last_login_at=updated.last_login_at,
        )
    except Exception as e:
        logger.error(f"Profile update failed: {e}")
        raise HTTPException(status_code=500, detail="Profile update failed")


@router.post("/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    user = Depends(get_current_clearform_user),
):
    """Change user password."""
    try:
        await clearform_auth_service.change_password(
            user_id=user.user_id,
            current_password=current_password,
            new_password=new_password,
        )
        return {"message": "Password changed successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Password change failed: {e}")
        raise HTTPException(status_code=500, detail="Password change failed")
