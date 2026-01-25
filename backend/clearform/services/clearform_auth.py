"""ClearForm Authentication Service

Reuses existing auth utilities but maintains separate user collection.
ClearForm users are distinct from Pleerity clients/portal users.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import logging
import os

from database import database
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    validate_password_strength,
)
from clearform.models.user import (
    ClearFormUser,
    ClearFormUserCreate,
    ClearFormUserResponse,
    ClearFormUserStatus,
    ClearFormUserLogin,
    ClearFormTokenResponse,
)

logger = logging.getLogger(__name__)


class ClearFormAuthService:
    """Authentication service for ClearForm users."""
    
    def __init__(self):
        self.db = None
    
    def _get_db(self):
        if self.db is None:
            self.db = database.get_db()
        return self.db
    
    async def register(self, data: ClearFormUserCreate) -> ClearFormUser:
        """Register a new ClearForm user."""
        db = self._get_db()
        
        # Check if email already exists
        existing = await db.clearform_users.find_one({"email": data.email.lower()})
        if existing:
            raise ValueError("Email already registered")
        
        # Validate password strength
        is_valid, message = validate_password_strength(data.password)
        if not is_valid:
            raise ValueError(message)
        
        # Create user
        user = ClearFormUser(
            email=data.email.lower(),
            full_name=data.full_name,
            password_hash=hash_password(data.password),
            status=ClearFormUserStatus.ACTIVE,  # Skip email verification for MVP
            email_verified=True,  # Auto-verify for MVP
            email_verified_at=datetime.now(timezone.utc),
            credit_balance=5,  # Welcome bonus credits
        )
        
        await db.clearform_users.insert_one(user.model_dump())
        
        # Record welcome credits transaction
        from clearform.services.credit_service import credit_service
        from clearform.models.credits import CreditTransactionType
        
        await credit_service.add_credits(
            user_id=user.user_id,
            amount=5,
            transaction_type=CreditTransactionType.BONUS,
            description="Welcome bonus: 5 free credits to get started",
            reference_id=user.user_id,
            reference_type="welcome_bonus",
        )
        
        logger.info(f"New ClearForm user registered: {user.user_id}")
        return user
    
    async def login(self, data: ClearFormUserLogin) -> ClearFormTokenResponse:
        """Authenticate user and return token."""
        db = self._get_db()
        
        user = await db.clearform_users.find_one({"email": data.email.lower()}, {"_id": 0})
        if not user:
            raise ValueError("Invalid email or password")
        
        if not verify_password(data.password, user["password_hash"]):
            raise ValueError("Invalid email or password")
        
        if user["status"] == ClearFormUserStatus.SUSPENDED.value:
            raise ValueError("Account suspended")
        
        if user["status"] == ClearFormUserStatus.DELETED.value:
            raise ValueError("Account not found")
        
        # Update last login
        now = datetime.now(timezone.utc)
        await db.clearform_users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"last_login_at": now}}
        )
        user["last_login_at"] = now
        
        # Create token with clearform-specific claims
        token = create_access_token({
            "sub": user["user_id"],
            "email": user["email"],
            "product": "clearform",  # Important: identifies this as a ClearForm token
        })
        
        user_response = ClearFormUserResponse(
            user_id=user["user_id"],
            email=user["email"],
            full_name=user["full_name"],
            status=user["status"],
            email_verified=user["email_verified"],
            credit_balance=user["credit_balance"],
            lifetime_credits_purchased=user.get("lifetime_credits_purchased", 0),
            lifetime_credits_used=user.get("lifetime_credits_used", 0),
            subscription_id=user.get("subscription_id"),
            subscription_plan=user.get("subscription_plan"),
            next_credit_grant_at=user.get("next_credit_grant_at"),
            created_at=user["created_at"],
            last_login_at=user.get("last_login_at"),
        )
        
        return ClearFormTokenResponse(
            access_token=token,
            user=user_response,
        )
    
    async def get_current_user(self, token: str) -> Optional[ClearFormUser]:
        """Get current user from token."""
        payload = decode_access_token(token)
        if not payload:
            return None
        
        # Verify this is a ClearForm token
        if payload.get("product") != "clearform":
            return None
        
        db = self._get_db()
        user = await db.clearform_users.find_one(
            {"user_id": payload["sub"]},
            {"_id": 0}
        )
        
        if not user:
            return None
        
        return ClearFormUser(**user)
    
    async def get_user_by_id(self, user_id: str) -> Optional[ClearFormUser]:
        """Get user by ID."""
        db = self._get_db()
        user = await db.clearform_users.find_one(
            {"user_id": user_id},
            {"_id": 0}
        )
        if user:
            return ClearFormUser(**user)
        return None
    
    async def update_profile(
        self,
        user_id: str,
        full_name: Optional[str] = None,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> ClearFormUser:
        """Update user profile."""
        db = self._get_db()
        
        updates = {"updated_at": datetime.now(timezone.utc)}
        if full_name:
            updates["full_name"] = full_name
        if preferences:
            updates["preferences"] = preferences
        
        await db.clearform_users.update_one(
            {"user_id": user_id},
            {"$set": updates}
        )
        
        return await self.get_user_by_id(user_id)
    
    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change user password."""
        db = self._get_db()
        
        user = await db.clearform_users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise ValueError("User not found")
        
        if not verify_password(current_password, user["password_hash"]):
            raise ValueError("Current password is incorrect")
        
        is_valid, message = validate_password_strength(new_password)
        if not is_valid:
            raise ValueError(message)
        
        await db.clearform_users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "password_hash": hash_password(new_password),
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        )
        
        return True


# Global service instance
clearform_auth_service = ClearFormAuthService()
