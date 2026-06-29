"""Tenant and access guards for Intelligence Service Layer."""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from services.compliance_graph_service.access import ActorContext


def enforce_tenant_access(actor: ActorContext, *, client_id: str) -> None:
    if actor.is_admin:
        return
    if not actor.client_id or actor.client_id != client_id:
        raise HTTPException(status_code=403, detail="Access denied for tenant scope")


def resolve_client_id(actor: ActorContext, client_id: Optional[str]) -> str:
    if client_id:
        enforce_tenant_access(actor, client_id=client_id)
        return client_id
    if actor.client_id:
        return actor.client_id
    if actor.is_admin:
        raise HTTPException(status_code=422, detail="client_id required for admin scope")
    raise HTTPException(status_code=403, detail="Access denied for tenant scope")
