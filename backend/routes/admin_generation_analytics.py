"""
Admin generation health & analytics (provider reliability, failed orders, prompt patterns).

Retry endpoints live on /api/admin/orders (see admin_orders) to avoid duplicate surfaces.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from middleware import admin_route_guard
from services.generation_analytics_service import (
    get_provider_health_summary,
    get_recent_generation_runs,
    get_failed_orders_summary,
    get_prompt_failure_patterns,
)

router = APIRouter(tags=["admin-generation-analytics"])


@router.get("/provider-health")
async def provider_health(
    hours: int = Query(24, ge=1, le=336),
    current_user: dict = Depends(admin_route_guard),
):
    _ = current_user
    return await get_provider_health_summary(hours=hours)


@router.get("/generation-runs")
async def generation_runs(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    service_code: Optional[str] = Query(None),
    current_user: dict = Depends(admin_route_guard),
):
    _ = current_user
    return await get_recent_generation_runs(
        limit=limit,
        status=status,
        provider=provider,
        service_code=service_code,
    )


@router.get("/failed-orders")
async def failed_orders(
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(admin_route_guard),
):
    _ = current_user
    return await get_failed_orders_summary(limit=limit)


@router.get("/prompt-failure-patterns")
async def prompt_failure_patterns(
    limit: int = Query(40, ge=1, le=200),
    current_user: dict = Depends(admin_route_guard),
):
    _ = current_user
    return await get_prompt_failure_patterns(limit=limit)
