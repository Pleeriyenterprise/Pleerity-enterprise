import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, status

from services.admin_confirmation_token_service import (
    consume_admin_confirmation_token,
    issue_admin_confirmation_token,
)

CONFIRMATION_HEADER = "X-Admin-Confirmation-Token"


_REGISTRY_PATH = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "src"
    / "config"
    / "adminActionPolicyRegistry.json"
)


def _load_registry() -> Dict[str, Dict[str, Any]]:
    with _REGISTRY_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


_REGISTRY: Dict[str, Dict[str, Any]] = _load_registry()


def get_admin_action_policy(action_id: str) -> Dict[str, Any]:
    policy = _REGISTRY.get(action_id)
    if not isinstance(policy, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Missing admin action policy for {action_id}",
        )
    return policy


def ensure_action_reason(action_id: str, reason: Optional[str]) -> str:
    policy = get_admin_action_policy(action_id)
    trimmed = str(reason or "").strip()
    if policy.get("requires_reason") and len(trimmed) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A support reason of at least 10 characters is required for this action.",
        )
    return trimmed


async def enforce_step_up_if_required(action_id: str, request: Any, user: Dict[str, Any], require_recent_step_up: Any) -> None:
    policy = get_admin_action_policy(action_id)
    if policy.get("requires_step_up"):
        await require_recent_step_up(request, user)


async def enforce_governed_admin_action(
    request: Request,
    user: Dict[str, Any],
    action_id: str,
    *,
    reason: Optional[str] = None,
    resource_key: Optional[str] = None,
    require_recent_step_up: Any = None,
) -> str:
    """Enforce registry policy: reason, confirmation token, optional step-up."""
    support_reason = ensure_action_reason(action_id, reason)
    policy = get_admin_action_policy(action_id)
    if policy.get("requires_confirmation"):
        token = (request.headers.get(CONFIRMATION_HEADER) or "").strip()
        await consume_admin_confirmation_token(
            token,
            user["portal_user_id"],
            action_id,
            resource_key=resource_key,
        )
    if policy.get("requires_step_up") and require_recent_step_up is not None:
        await require_recent_step_up(request, user)
    return support_reason


async def create_confirmation_token_for_action(
    user: Dict[str, Any],
    action_id: str,
    *,
    reason: Optional[str] = None,
    resource_key: Optional[str] = None,
) -> Dict[str, str]:
    support_reason = ensure_action_reason(action_id, reason)
    token = await issue_admin_confirmation_token(
        user["portal_user_id"],
        action_id,
        resource_key=resource_key,
        reason=support_reason,
    )
    return {"token": token, "expires_in_seconds": "300"}


def normalized_admin_action_metadata(
    action_id: str,
    support_reason: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    policy = get_admin_action_policy(action_id)
    payload: Dict[str, Any] = {
        "action_id": policy.get("action_id"),
        "risk_class": policy.get("risk_class"),
        "operator_level": policy.get("operator_level"),
        "support_reason": support_reason or None,
        "affects_multiple_customers": bool(policy.get("affects_multiple_customers")),
    }
    if extra:
        payload.update(extra)
    return payload

