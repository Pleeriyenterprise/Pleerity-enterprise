"""Client lifecycle runtime contract API (ILP-2)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response

from database import database
from middleware import client_route_guard
from services.account_lifecycle_runtime_contract import (
    CONTRACT_VERSION,
    compare_runtime_with_legacy,
    resolve_runtime_contract_for_client,
    runtime_contract_to_dict,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/client", tags=["client-lifecycle-runtime"], dependencies=[Depends(client_route_guard)])


async def _build_response(request: Request, response: Response) -> dict:
    user = await client_route_guard(request)
    client_id = user["client_id"]
    contract = await resolve_runtime_contract_for_client(database.get_db(), client_id)
    payload = runtime_contract_to_dict(contract)
    response.headers["X-Lifecycle-Contract-Version"] = CONTRACT_VERSION
    response.headers["X-Lifecycle-Runtime-Version"] = str(payload.get("runtime_version", ""))
    return {"lifecycle_runtime": payload}


@router.get("/lifecycle-runtime")
async def get_lifecycle_runtime(request: Request, response: Response):
    """Return governed Account Lifecycle Runtime Contract (read-only, non-enforcing)."""
    return await _build_response(request, response)


@router.get("/lifecycle-contract")
async def get_lifecycle_contract_alias(request: Request, response: Response):
    """Transitional alias for lifecycle-runtime (governance)."""
    return await _build_response(request, response)


@router.get("/lifecycle-runtime/diagnostic")
async def get_lifecycle_runtime_diagnostic(request: Request, response: Response):
    """Read-only comparison of runtime contract vs legacy entitlement fields."""
    user = await client_route_guard(request)
    client_id = user["client_id"]
    contract = await resolve_runtime_contract_for_client(database.get_db(), client_id, include_audit=True)
    payload = runtime_contract_to_dict(contract)
    comparison = compare_runtime_with_legacy(contract)
    response.headers["X-Lifecycle-Contract-Version"] = CONTRACT_VERSION
    response.headers["X-Lifecycle-Runtime-Version"] = str(payload.get("runtime_version", ""))
    return {
        "lifecycle_runtime": payload,
        "legacy_comparison": comparison,
    }
