"""
Capability gating helpers (ILP-4 Phase 0–1).

require_capability() is available for route migration but is NOT wired to production routes in this phase.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request

from database import database
from services.account_capability_enforcement import (
    CapabilityAction,
    CapabilityDeniedError,
    CapabilityEnforcementService,
)

logger = logging.getLogger(__name__)


def _owner_bypass(user: dict) -> bool:
    return user.get("role") == "ROLE_OWNER"


async def evaluate_capability_dependency(
    request: Request,
    capability_id: str,
    action: CapabilityAction = "write",
) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    if _owner_bypass(user):
        return {"bypass": "ROLE_OWNER", "capability_id": capability_id, "action": action}

    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=404, detail="Client not found")

    service = CapabilityEnforcementService(database.get_db())
    decision = await service.evaluate(client_id, capability_id, action)
    if not decision.allowed:
        raise CapabilityDeniedError(decision)
    request.state.capability_decision = decision
    return decision.to_dict()


def require_capability(
    capability_id: str,
    action: CapabilityAction = "write",
) -> Callable:
    """
    FastAPI dependency factory for capability enforcement.

    Not attached to live routes in ILP-4 Phase 0–1.
  """

    async def _dependency(request: Request):
        try:
            return await evaluate_capability_dependency(request, capability_id, action)
        except CapabilityDeniedError as exc:
            logger.info(
                "capability_denied client capability=%s action=%s code=%s",
                capability_id,
                action,
                exc.decision.reason_code,
            )
            raise HTTPException(status_code=403, detail=exc.to_detail()) from exc

    return Depends(_dependency)


def capability_denied_handler(exc: CapabilityDeniedError) -> dict:
    """Serialize for tests and future ILP-6 safe responses."""
    return exc.to_detail()
