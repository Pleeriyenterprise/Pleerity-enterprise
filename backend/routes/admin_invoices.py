"""
Admin API: create invoice (manual/admin entry).
Invoices then flow to client Approvals workspace.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from typing import Optional

from middleware import admin_route_guard, require_owner_or_admin
from services import invoice_service

router = APIRouter(prefix="/api/admin/ops", tags=["ops-invoices"], dependencies=[Depends(admin_route_guard)])


class CreateInvoiceBody(BaseModel):
    client_id: str
    property_id: str
    contractor_id: str
    work_order_id: str
    reference: Optional[str] = None
    description: Optional[str] = None
    submitted_amount: Optional[float] = None
    currency: Optional[str] = "GBP"
    benchmark_min: Optional[float] = None
    benchmark_max: Optional[float] = None
    attachment_storage_key: Optional[str] = None


@router.post("/invoices", dependencies=[Depends(require_owner_or_admin)])
async def create_invoice_admin(request: Request, body: CreateInvoiceBody):
    """Create an invoice (admin/manual). Links to work order, contractor, property, client. Invoice appears in client Approvals."""
    user = await admin_route_guard(request)
    try:
        doc = await invoice_service.create_invoice(
            client_id=body.client_id,
            property_id=body.property_id,
            contractor_id=body.contractor_id,
            work_order_id=body.work_order_id,
            reference=body.reference or "",
            description=body.description,
            submitted_amount=body.submitted_amount,
            currency=body.currency or "GBP",
            benchmark_min=body.benchmark_min,
            benchmark_max=body.benchmark_max,
            attachment_storage_key=body.attachment_storage_key,
            source=invoice_service.SOURCE_ADMIN,
            created_by_id=user.get("portal_user_id") or user.get("email"),
        )
        return doc
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
