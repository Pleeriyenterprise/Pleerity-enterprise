"""
Capability gating helpers (ILP-4).

require_capability() / client_require_capability() evaluate CAP_* grants from the Runtime Contract.
"""
from __future__ import annotations

import logging
from typing import Callable

from fastapi import Depends, HTTPException, Request

from database import database
from middleware import client_route_guard
from services.account_capability_enforcement import (
    CapabilityAction,
    CapabilityDecision,
    CapabilityDeniedError,
    CapabilityEnforcementService,
)

logger = logging.getLogger(__name__)


def _owner_bypass(user: dict) -> bool:
    return user.get("role") == "ROLE_OWNER"


def capability_denied_http_detail(decision: CapabilityDecision) -> dict:
    """Governed safe 403 payload for capability denials (ILP-6 precursor)."""
    recovery = None
    if decision.recovery_route or decision.recovery_label:
        recovery = {
            "route": decision.recovery_route,
            "label": decision.recovery_label,
        }
    return {
        "error": "capability_denied",
        "error_code": decision.reason_code,
        "message": decision.reason,
        "capability_id": decision.capability_id,
        "action": decision.action,
        "grant": decision.grant,
        "effective_semantic": decision.effective_semantic,
        "lifecycle_state": decision.lifecycle_state,
        "portal_mode": decision.portal_mode,
        "recovery": recovery,
        "contract_version": decision.contract_version,
        "runtime_version": decision.runtime_version,
    }


def capability_denied_handler(exc: CapabilityDeniedError) -> dict:
    return capability_denied_http_detail(exc.decision)


async def evaluate_capability_dependency(
    request: Request,
    capability_id: str,
    action: CapabilityAction = "write",
    user: dict = Depends(client_route_guard),
) -> dict:
    if _owner_bypass(user):
        return {
            "bypass": "ROLE_OWNER",
            "capability_id": capability_id,
            "action": action,
        }

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
    """FastAPI dependency factory — evaluates capability after client_route_guard."""

    async def _dependency(
        request: Request,
        user: dict = Depends(client_route_guard),
    ):
        try:
            if _owner_bypass(user):
                return {
                    "bypass": "ROLE_OWNER",
                    "capability_id": capability_id,
                    "action": action,
                }
            client_id = user.get("client_id")
            if not client_id:
                raise HTTPException(status_code=404, detail="Client not found")
            service = CapabilityEnforcementService(database.get_db())
            decision = await service.evaluate(client_id, capability_id, action)
            if not decision.allowed:
                raise CapabilityDeniedError(decision)
            request.state.capability_decision = decision
            return decision.to_dict()
        except CapabilityDeniedError as exc:
            logger.info(
                "capability_denied client capability=%s action=%s code=%s",
                capability_id,
                action,
                exc.decision.reason_code,
            )
            raise HTTPException(
                status_code=403,
                detail=capability_denied_http_detail(exc.decision),
            ) from exc

    return Depends(_dependency)


def client_require_capability(
    capability_id: str,
    action: CapabilityAction = "write",
) -> Callable:
    """
    Client-route dependency: runs client_route_guard then CAP_* evaluation.
    Returns authenticated user dict when allowed.
    """

    async def _dependency(
        request: Request,
        user: dict = Depends(client_route_guard),
    ) -> dict:
        if _owner_bypass(user):
            return user

        client_id = user.get("client_id")
        if not client_id:
            raise HTTPException(status_code=404, detail="Client not found")

        service = CapabilityEnforcementService(database.get_db())
        decision = await service.evaluate(client_id, capability_id, action)
        if not decision.allowed:
            logger.info(
                "capability_denied client_id=%s capability=%s action=%s code=%s",
                client_id,
                capability_id,
                action,
                decision.reason_code,
            )
            raise HTTPException(
                status_code=403,
                detail=capability_denied_http_detail(decision),
            )
        request.state.capability_decision = decision
        return user

    return Depends(_dependency)


async def assert_client_capability(
    user: dict,
    capability_id: str,
    action: CapabilityAction = "write",
) -> CapabilityDecision:
    """
    In-handler CAP_* check for routes with conditional capability (e.g. format=csv|pdf).
    Raises governed 403; use only in fully capability-governed modules.
    """
    if _owner_bypass(user):
        return CapabilityDecision(
            capability_id=capability_id,
            action=action,
            grant="ALLOW",
            effective_semantic="ALLOW",
            allowed=True,
            source="owner_bypass",
            reason_code="allowed",
            reason="ROLE_OWNER bypass",
        )
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=404, detail="Client not found")
    service = CapabilityEnforcementService(database.get_db())
    decision = await service.evaluate(client_id, capability_id, action)
    if not decision.allowed:
        logger.info(
            "capability_denied client_id=%s capability=%s action=%s code=%s",
            client_id,
            capability_id,
            action,
            decision.reason_code,
        )
        raise HTTPException(
            status_code=403,
            detail=capability_denied_http_detail(decision),
        )
    return decision
