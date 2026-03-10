"""
Client API for invoice approvals (Operations → Approvals). Gated by INVOICING.
List, filter, get one, approve/reject/needs_info, export CSV.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional

from middleware import client_route_guard
from services.ops_compliance_feature_flags import get_effective_flags, INVOICING
from services import approval_service

router = APIRouter(prefix="/api/client", tags=["client-approvals"], dependencies=[Depends(client_route_guard)])


async def _require_invoicing_enabled(request: Request):
    """Ensure client has INVOICING enabled."""
    user = await client_route_guard(request)
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=403, detail="Client context required")
    flags = await get_effective_flags(client_id)
    if not flags.get(INVOICING):
        raise HTTPException(
            status_code=403,
            detail="Invoicing is not enabled for your account. Contact your administrator.",
        )
    return user


@router.get("/approvals")
async def list_approvals(
    request: Request,
    status: Optional[str] = Query(None, description="pending | approved | rejected | needs_info"),
    contractorId: Optional[str] = Query(None, alias="contractorId"),
    propertyId: Optional[str] = Query(None, alias="propertyId"),
    workOrderId: Optional[str] = Query(None, alias="workOrderId"),
    benchmarkFit: Optional[str] = Query(None, alias="benchmarkFit", description="below | within | above | none"),
    q: Optional[str] = Query(None, description="Search: invoice ref, contractor, property, work order"),
    from_date: Optional[str] = Query(None, alias="from", description="From date YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, alias="to", description="To date YYYY-MM-DD"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    """List approval items with summary and exceptions. Requires INVOICING."""
    user = await _require_invoicing_enabled(request)
    result = await approval_service.list_approvals(
        client_id=user["client_id"],
        status=status,
        contractor_id=contractorId,
        property_id=propertyId,
        work_order_id=workOrderId,
        benchmark_fit=benchmarkFit,
        q=q,
        from_date=from_date,
        to_date=to_date,
        skip=skip,
        limit=limit,
    )
    return result


@router.get("/approvals/export")
async def export_approvals(
    request: Request,
    status: Optional[str] = Query(None),
    contractorId: Optional[str] = Query(None, alias="contractorId"),
    propertyId: Optional[str] = Query(None, alias="propertyId"),
    workOrderId: Optional[str] = Query(None, alias="workOrderId"),
    benchmarkFit: Optional[str] = Query(None, alias="benchmarkFit"),
    q: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    """Export filtered approvals as CSV. Requires INVOICING."""
    user = await _require_invoicing_enabled(request)
    csv_str = await approval_service.export_approvals_csv(
        client_id=user["client_id"],
        status=status,
        contractor_id=contractorId,
        property_id=propertyId,
        work_order_id=workOrderId,
        benchmark_fit=benchmarkFit,
        q=q,
        from_date=from_date,
        to_date=to_date,
    )
    return PlainTextResponse(
        csv_str,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=approvals_export.csv"},
    )


@router.get("/approvals/{invoice_id}")
async def get_approval(request: Request, invoice_id: str):
    """Get a single approval/invoice for the detail drawer. Requires INVOICING."""
    user = await _require_invoicing_enabled(request)
    doc = await approval_service.get_approval(client_id=user["client_id"], invoice_id=invoice_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Approval not found")
    return doc


class ApprovalActionBody(BaseModel):
    action: str  # approved | rejected | needs_info
    notes: Optional[str] = None


@router.patch("/approvals/{invoice_id}")
async def update_approval(request: Request, invoice_id: str, body: ApprovalActionBody):
    """Approve, reject, or request more info. Requires INVOICING."""
    user = await _require_invoicing_enabled(request)
    if body.action not in ("approved", "rejected", "needs_info"):
        raise HTTPException(status_code=400, detail="action must be approved, rejected, or needs_info")
    doc = await approval_service.update_approval(
        client_id=user["client_id"],
        invoice_id=invoice_id,
        action=body.action,
        notes=body.notes,
        reviewer_id=user.get("portal_user_id"),
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Approval not found or already decided")
    return doc
