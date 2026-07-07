"""
Capability gating helpers (ILP-4).

require_capability() / client_require_capability() evaluate CAP_* grants from the Runtime Contract.
ILP-7: HTTP denial payloads delegate to Lifecycle Response Authority.
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
from services.account_lifecycle_response_authority import (
    capability_denied_http_detail,
    log_lifecycle_response_generated,
)

logger = logging.getLogger(__name__)


def _owner_bypass(user: dict) -> bool:
    return user.get("role") == "ROLE_OWNER"


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

    contract = getattr(request.state, "runtime_contract", None) or user.get("runtime_contract")
    service = CapabilityEnforcementService(database.get_db())
    decision = await service.evaluate(
        client_id,
        capability_id,
        action,
        contract=contract,
    )
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
            contract = getattr(request.state, "runtime_contract", None) or user.get("runtime_contract")
            service = CapabilityEnforcementService(database.get_db())
            decision = await service.evaluate(
                client_id,
                capability_id,
                action,
                contract=contract,
            )
            if not decision.allowed:
                raise CapabilityDeniedError(decision)
            request.state.capability_decision = decision
            return decision.to_dict()
        except CapabilityDeniedError as exc:
            log_lifecycle_response_generated(
                client_id=user.get("client_id"),
                route=str(request.url.path),
                capability=capability_id,
                grant=exc.decision.grant,
                lifecycle_state=exc.decision.lifecycle_state,
                response_type="capability_denied",
                runtime_version=exc.decision.runtime_version,
            )
            raise HTTPException(
                status_code=403,
                detail=capability_denied_http_detail(
                    exc.decision,
                    contract=getattr(request.state, "runtime_contract", None) or user.get("runtime_contract"),
                ),
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

        contract = getattr(request.state, "runtime_contract", None) or user.get("runtime_contract")
        service = CapabilityEnforcementService(database.get_db())
        decision = await service.evaluate(
            client_id,
            capability_id,
            action,
            contract=contract,
        )
        if not decision.allowed:
            log_lifecycle_response_generated(
                client_id=client_id,
                route=str(request.url.path),
                capability=capability_id,
                grant=decision.grant,
                lifecycle_state=decision.lifecycle_state,
                response_type="capability_denied",
                runtime_version=decision.runtime_version,
            )
            raise HTTPException(
                status_code=403,
                detail=capability_denied_http_detail(decision, contract=contract),
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
    contract = user.get("runtime_contract")
    service = CapabilityEnforcementService(database.get_db())
    decision = await service.evaluate(
        client_id,
        capability_id,
        action,
        contract=contract,
    )
    if not decision.allowed:
        log_lifecycle_response_generated(
            client_id=client_id,
            capability=capability_id,
            grant=decision.grant,
            lifecycle_state=decision.lifecycle_state,
            response_type="capability_denied",
            runtime_version=decision.runtime_version,
        )
        raise HTTPException(
            status_code=403,
            detail=capability_denied_http_detail(decision, contract=contract),
        )
    return decision
