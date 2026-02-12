"""
Feature Gating Middleware
Server-side enforcement of plan-based feature access.
Uses plan_registry as single source of truth; reads client from DB by client_id only.
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
    Fetches client fresh from DB by client_id; projects billing_plan and subscription_status only.
    Uses plan_registry.resolve_plan_code() and subscription_allows_feature_access() for consistency.

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

            # Only OWNER bypasses billing/plan gating; ADMIN does not
            if user.get("role") == "ROLE_OWNER":
                return await func(request, *args, **kwargs)

            db = database.get_db()
            client_id = user.get("client_id")
            if not client_id:
                raise HTTPException(404, "Client not found")

            # Always fetch client fresh from DB by client_id; do not read plan from request/payload
            client = await db.clients.find_one(
                {"client_id": client_id},
                {"_id": 0, "billing_plan": 1, "subscription_status": 1}
            )

            if not client:
                raise HTTPException(404, "Client not found")

            # Subscription allow-list: ACTIVE and TRIALING (shared helper)
            from services.plan_registry import (
                plan_registry,
                subscription_allows_feature_access,
            )
            subscription_status = client.get("subscription_status")
            if not subscription_allows_feature_access(subscription_status):
                raise HTTPException(
                    403,
                    "Subscription not active. Please update your billing to access features."
                )

            # Resolve plan via public API; do not use plan_code from client document
            plan_str = client.get("billing_plan", "PLAN_1_SOLO")
            plan_code = plan_registry.resolve_plan_code(plan_str)
            features = plan_registry.get_features(plan_code)

            if not features.get(feature_key, False):
                plan_def = plan_registry.get_plan(plan_code)

                # Log denial with resolved plan_code and requested feature
                await create_audit_log(
                    action=AuditAction.ADMIN_ACTION,
                    actor_role=user.get("role"),
                    actor_id=user["portal_user_id"],
                    client_id=client_id,
                    metadata={
                        "action_type": "PLAN_GATE_DENIED",
                        "feature_key": feature_key,
                        "plan_code": plan_code.value,
                        "plan_name": plan_def["name"],
                        "endpoint": str(request.url.path),
                        "method": request.method
                    }
                )
                logger.warning(
                    "Feature access denied: client_id=%s resolved_plan_code=%s requested_feature=%s endpoint=%s method=%s",
                    client_id, plan_code.value, feature_key, request.url.path, request.method
                )

                raise HTTPException(
                    status_code=403,
                    detail=f"This feature requires a higher plan. Your {plan_def['name']} plan does not include this feature. Please upgrade to access."
                )

            # Feature allowed - proceed
            return await func(request, *args, **kwargs)

        return wrapper
    return decorator
