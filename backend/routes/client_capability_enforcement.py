"""Capability enforcement diagnostics API (ILP-4 Phase 0–1). Read-only; does not change route behaviour."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response

from database import database
from middleware import client_route_guard
from middleware.capability_gating import assert_client_capability
from services.account_capability_enforcement import (
    CapabilityAction,
    CapabilityEnforcementService,
    runtime_resolved_capability_ids,
)
from services.account_lifecycle_runtime_contract import CONTRACT_VERSION, runtime_contract_to_dict
from services.capability_compatibility import (
    CAPABILITY_TO_FEATURE_KEYS,
    FEATURE_KEY_TO_CAPABILITIES,
    evaluate_feature_via_capability,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/client",
    tags=["capability-enforcement"],
    dependencies=[Depends(client_route_guard)],
)


@router.get("/capability-enforcement/diagnostic")
async def capability_enforcement_diagnostic(
    request: Request,
    response: Response,
    capability: Optional[str] = Query(None, description="Evaluate a single CAP_* id"),
    action: CapabilityAction = Query("write"),
    feature_key: Optional[str] = Query(None, description="Evaluate via legacy feature_key mapping"),
):
    """
    Developer diagnostics for capability enforcement (read-only).

    Does not enforce access on other endpoints. Safe for staging inspection.
    """
    user = await client_route_guard(request)
    await assert_client_capability(user, "CAP_PROFILE_VIEW", "read")
    client_id = user["client_id"]
    service = CapabilityEnforcementService(database.get_db())
    contract = await service.load_contract(client_id, include_audit=True)
    payload = runtime_contract_to_dict(contract)

    response.headers["X-Lifecycle-Contract-Version"] = CONTRACT_VERSION
    response.headers["X-Lifecycle-Runtime-Version"] = str(payload.get("runtime_version", ""))

    result = {
        "client_id": client_id,
        "lifecycle_state": payload.get("lifecycle_state"),
        "portal_mode": payload.get("portal_mode"),
        "runtime_version": payload.get("runtime_version"),
        "contract_version": payload.get("contract_version"),
        "warnings": payload.get("warnings") or [],
        "runtime_capability_count": len(payload.get("capabilities") or {}),
        "runtime_resolved_catalog_count": len(runtime_resolved_capability_ids()),
        "compatibility_mappings": len(FEATURE_KEY_TO_CAPABILITIES),
    }

    if feature_key:
        decision = await evaluate_feature_via_capability(service, client_id, feature_key, action, contract=contract)
        result["feature_key"] = feature_key
        result["mapped_capabilities"] = list(FEATURE_KEY_TO_CAPABILITIES.get(feature_key, ()))
        result["decision"] = decision.to_dict()
    elif capability:
        decision = service.evaluate_from_contract(contract, capability, action)
        result["capability"] = capability
        result["action"] = action
        result["decision"] = decision.to_dict()
        result["legacy_feature_keys"] = list(CAPABILITY_TO_FEATURE_KEYS.get(capability, ()))
    else:
        decisions = service.evaluate_all_from_contract(contract)
        result["evaluations"] = [d.to_dict() for d in decisions]

    result["capabilities"] = payload.get("capabilities")
    result["customer_experience"] = {
        "heading": (payload.get("customer_experience") or {}).get("heading"),
        "primary_cta": (payload.get("customer_experience") or {}).get("primary_cta"),
    }
    return result
