"""Tenant and access guards for Graph Service."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException


class ActorContext:
    def __init__(
        self,
        *,
        is_admin: bool,
        client_id: Optional[str] = None,
        portal_user_id: Optional[str] = None,
    ):
        self.is_admin = is_admin
        self.client_id = client_id
        self.portal_user_id = portal_user_id


def actor_from_request_user(user: Dict[str, Any], *, is_admin: bool) -> ActorContext:
    return ActorContext(
        is_admin=is_admin,
        client_id=user.get("client_id"),
        portal_user_id=user.get("portal_user_id") or user.get("sub"),
    )


def enforce_tenant_access(actor: ActorContext, *, client_id: str) -> None:
    if actor.is_admin:
        return
    if not actor.client_id or actor.client_id != client_id:
        raise HTTPException(status_code=403, detail="Access denied for tenant scope")


def enforce_decision_tenant(actor: ActorContext, decision: Dict[str, Any]) -> None:
    cid = decision.get("client_id")
    if not cid:
        raise HTTPException(status_code=404, detail="Decision not found")
    enforce_tenant_access(actor, client_id=cid)
