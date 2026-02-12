"""
Feature Gating Middleware
Server-side enforcement of plan-based feature access
"""
from fastapi import HTTPException, Request
from database import database
from models import AuditAction
from utils.audit import create_audit_log
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def require_feature(feature_key: str):
    """
    Decorator to enforce plan-based feature access.
    
    Usage:
        @router.post("/endpoint")
        @require_feature("zip_upload")
        async def my_endpoint(request: Request):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Get user from request state (set by auth middleware)
            user = getattr(request.state, 'user', None)
            
            if not user:
                raise HTTPException(401, "Authentication required")
            
            # Skip gating for admin users
            if user.get("role") == "ROLE_ADMIN":
                return await func(request, *args, **kwargs)
            
            db = database.get_db()
            
            # Get client plan and subscription status
            client = await db.clients.find_one(
                {"client_id": user["client_id"]},
                {"_id": 0, "plan_code": 1, "subscription_status": 1}
            )
            
            if not client:
                raise HTTPException(404, "Client not found")
            
            # Check subscription is active
            if client.get("subscription_status") != "ACTIVE":
                raise HTTPException(
                    403,
                    "Subscription not active. Please update your billing to access features."
                )
            
            # Check feature access
            from services.plan_registry import plan_registry, PlanCode
            
            plan_code = PlanCode(client.get("plan_code", "PLAN_1_SOLO"))
            features = plan_registry.get_features(plan_code)
            
            if not features.get(feature_key, False):
                plan_def = plan_registry.get_plan(plan_code)
                
                # Log denial
                await create_audit_log(
                    action=AuditAction.ADMIN_ACTION,
                    actor_role=user.get("role"),
                    actor_id=user["portal_user_id"],
                    client_id=user["client_id"],
                    metadata={
                        "action_type": "PLAN_GATE_DENIED",
                        "feature_key": feature_key,
                        "plan_code": plan_code.value,
                        "plan_name": plan_def["name"],
                        "endpoint": str(request.url.path),
                        "method": request.method
                    }
                )
                
                logger.warning(f"Feature '{feature_key}' denied for {user['client_id']} (plan: {plan_code.value})")
                
                raise HTTPException(
                    status_code=403,
                    detail=f"This feature requires a higher plan. Your {plan_def['name']} plan does not include this feature. Please upgrade to access."
                )
            
            # Feature allowed - proceed
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator
