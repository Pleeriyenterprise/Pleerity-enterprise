"""
Client API for Rent Operations — operational rent tracking and property expenses.
Permission authority: Runtime Contract CAP_OPS_RENT.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from typing import Optional

from database import database
from middleware import client_route_guard
from middleware.capability_gating import capability_denied_http_detail, enforce_route_capability
from services.account_capability_enforcement import CapabilityEnforcementService
from models.rent_operations import (
    CreateRentScheduleBody,
    RentSchedulePreviewBody,
    CreatePropertyTenancyBody,
    ClosePropertyTenancyBody,
    UpdateRentLedgerBody,
    RecordPaymentBody,
    MarkReminderSentBody,
    CreateExpenseBody,
    UpdateExpenseBody,
)
from services import rent_ledger_service
from services import rent_payment_service
from services import rent_tenancy_authority_service as tenancy_authority
from services import rent_reminder_service
from services import property_expense_service
from utils.api_errors import structured_error
from models import UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/client", tags=["client-rent-operations"], dependencies=[Depends(client_route_guard)])


async def _enforce_capability(user: dict, capability_id: str, action: str) -> None:
    await enforce_route_capability(user, capability_id, action)


async def _require_rent_operations_enabled(request: Request, action: str = "read") -> dict:
    """Capability gate for rent operations (CAP_OPS_RENT)."""
    user = await client_route_guard(request)
    await _enforce_capability(user, "CAP_OPS_RENT", action)
    return user


def _actor_role(user) -> UserRole:
    role = (user.get("role") or "ROLE_CLIENT").upper()
    try:
        return UserRole(role)
    except ValueError:
        return UserRole.ROLE_CLIENT


def _raise_rent_value_error(code: str) -> None:
    """Map rent service ValueError codes to HTTP errors."""
    if code == "PROPERTY_NOT_FOUND":
        raise HTTPException(status_code=404, detail="Property not found")
    if code == "LEDGER_NOT_FOUND":
        raise HTTPException(status_code=404, detail="Rent ledger not found")
    if code == "TENANCY_NOT_FOUND":
        raise HTTPException(
            status_code=404,
            detail=structured_error("TENANCY_NOT_FOUND", "Tenancy not found for this property."),
        )
    if code == "NO_OCCUPANCY_FOR_TENANCY":
        raise HTTPException(
            status_code=400,
            detail=structured_error(
                code,
                "No tenant is linked to this property. Link a tenant under Occupancy or Tenants before creating tenancy authority.",
            ),
        )
    if code == "TENANCY_PROPERTY_MISMATCH":
        raise HTTPException(
            status_code=403,
            detail=structured_error(
                code,
                "Selected tenancy does not belong to this property.",
            ),
        )
    if code in ("TENANCY_ID_REQUIRED", "EXTERNAL_PAYER_NAME_REQUIRED", "TENANCY_NOT_ACTIVE", "TENANCY_LINEAGE_INVALID"):
        raise HTTPException(status_code=400, detail=structured_error(code, code.replace("_", " ").title()))
    if code in (
        "PAYMENT_AUTHORITY_INCOMPLETE",
        "LEDGER_ID_REQUIRED",
        "NO_OUTSTANDING_LEDGER",
        "NO_ALLOCATION_MADE",
    ):
        raise HTTPException(status_code=400, detail=structured_error(code, code.replace("_", " ").title()))
    raise HTTPException(status_code=400, detail=code)


@router.get("/operations/rent/capabilities")
async def get_rent_operations_capabilities(request: Request):
    """Handshake for frontend deploy continuity — tenancy-authority APIs."""
    await _require_rent_operations_enabled(request)
    return {
        "tenancy_authority": True,
        "tenancies_api": True,
        "schedule_preview_api": True,
        "ledger_payment_api": True,
        "version": "tenancy_authority_v1",
    }


@router.get("/operations/rent/tenancies")
async def list_rent_tenancies(
    request: Request,
    property_id: str = Query(..., description="Property scope"),
    active_only: bool = Query(True),
):
    user = await _require_rent_operations_enabled(request)
    try:
        tenancies = await tenancy_authority.list_property_tenancies(
            user["client_id"],
            property_id,
            active_only=active_only,
        )
        return {"tenancies": tenancies}
    except ValueError as e:
        _raise_rent_value_error(str(e))


@router.post("/operations/rent/tenancies")
async def create_rent_tenancy(request: Request, body: CreatePropertyTenancyBody):
    user = await _require_rent_operations_enabled(request, "write")
    try:
        if body.lineage_parent_tenancy_id:
            doc = await tenancy_authority.create_replacement_tenancy(
                user["client_id"],
                body.property_id,
                body.lineage_parent_tenancy_id,
                tenant_ids=body.tenant_ids,
                tenant_display_name=body.tenant_display_name,
                actor_id=user.get("portal_user_id"),
            )
        else:
            doc = await tenancy_authority.resolve_or_create_active_tenancy(
                user["client_id"],
                body.property_id,
                tenant_ids=body.tenant_ids,
                tenant_display_name=body.tenant_display_name,
                rent_tracking_enabled=body.rent_tracking_enabled,
                actor_id=user.get("portal_user_id"),
            )
        return doc
    except ValueError as e:
        _raise_rent_value_error(str(e))


@router.post(
    "/operations/rent/tenancies/{tenancy_id}/close",
)
async def close_rent_tenancy(
    request: Request,
    tenancy_id: str,
    body: ClosePropertyTenancyBody,
):
    user = await _require_rent_operations_enabled(request, "write")
    try:
        return await tenancy_authority.close_tenancy_rent_lineage(
            tenancy_id,
            user["client_id"],
            status=body.status,
            actor_id=user.get("portal_user_id"),
        )
    except ValueError as e:
        _raise_rent_value_error(str(e))


@router.post("/operations/rent/schedules/preview")
async def preview_rent_schedule(request: Request, body: RentSchedulePreviewBody):
    user = await _require_rent_operations_enabled(request)
    try:
        await rent_ledger_service.ensure_property_scope(user["client_id"], body.property_id)
        return rent_ledger_service.preview_schedule_periods(body.model_dump(mode="json"))
    except ValueError as e:
        _raise_rent_value_error(str(e))


@router.get("/operations/rent/summary")
async def get_rent_summary(
    request: Request,
    property_id: Optional[str] = Query(None),
):
    user = await _require_rent_operations_enabled(request)
    try:
        return await rent_ledger_service.get_rent_summary(user["client_id"], property_id=property_id)
    except ValueError as e:
        if str(e) == "PROPERTY_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Property not found")
        raise


@router.get("/operations/rent/schedules")
async def list_rent_schedules(
    request: Request,
    property_id: Optional[str] = Query(None),
):
    user = await _require_rent_operations_enabled(request)
    schedules = await rent_ledger_service.list_schedules(user["client_id"], property_id=property_id)
    return {"schedules": schedules}


@router.post("/operations/rent/schedules")
async def create_rent_schedule(request: Request, body: CreateRentScheduleBody):
    user = await _require_rent_operations_enabled(request, "write")
    try:
        schedule = await rent_ledger_service.create_rent_schedule(
            user["client_id"],
            body.model_dump(mode="json"),
            actor_id=user.get("portal_user_id"),
        )
        return schedule
    except ValueError as e:
        code = str(e)
        if code == "PROPERTY_NOT_FOUND":
            raise HTTPException(
                status_code=404,
                detail=structured_error("PROPERTY_NOT_FOUND", "Property not found or not in your account."),
            )
        _raise_rent_value_error(code)


@router.get("/operations/rent/ledgers")
async def list_rent_ledgers(
    request: Request,
    property_id: Optional[str] = Query(None),
    tenancy_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    due_from: Optional[str] = Query(None),
    due_to: Optional[str] = Query(None),
    tenant_name: Optional[str] = Query(None),
    attention_only: bool = Query(False),
    overdue_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    user = await _require_rent_operations_enabled(request)
    try:
        result = await rent_ledger_service.list_ledgers(
            user["client_id"],
            property_id=property_id,
            tenancy_id=tenancy_id,
            status=status,
            due_from=due_from,
            due_to=due_to,
            tenant_name=tenant_name,
            attention_only=attention_only,
            overdue_only=overdue_only,
            skip=skip,
            limit=limit,
        )
        from services.operational_cognition_service import attach_cognition_to_rent_ledger

        if isinstance(result.get("ledgers"), list):
            enriched = []
            for row in result["ledgers"]:
                enriched.append(await attach_cognition_to_rent_ledger(row))
            result["ledgers"] = enriched
        return result
    except ValueError as e:
        if str(e) == "PROPERTY_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Property not found")
        raise


@router.get("/operations/rent/ledgers/{ledger_id}")
async def get_rent_ledger(request: Request, ledger_id: str):
    user = await _require_rent_operations_enabled(request)
    doc = await rent_ledger_service.get_ledger(ledger_id, user["client_id"])
    if not doc:
        raise HTTPException(status_code=404, detail="Rent ledger not found")
    from services.operational_cognition_service import attach_cognition_to_rent_ledger

    return await attach_cognition_to_rent_ledger(doc)


@router.patch("/operations/rent/ledgers/{ledger_id}")
async def update_rent_ledger(request: Request, ledger_id: str, body: UpdateRentLedgerBody):
    user = await _require_rent_operations_enabled(request, "write")
    doc = await rent_ledger_service.update_ledger(
        ledger_id,
        user["client_id"],
        body.model_dump(mode="json", exclude_unset=True),
        actor_id=user.get("portal_user_id"),
        actor_role=_actor_role(user),
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Rent ledger not found")
    return doc


@router.post("/operations/rent/payments")
async def record_rent_payment(request: Request, body: RecordPaymentBody):
    user = await _require_rent_operations_enabled(request, "write")
    try:
        return await rent_payment_service.record_payment(
            user["client_id"],
            body.model_dump(mode="json"),
            actor_id=user.get("portal_user_id"),
            actor_role=_actor_role(user),
        )
    except ValueError as e:
        _raise_rent_value_error(str(e))


@router.post("/operations/rent/ledgers/{ledger_id}/payments")
async def record_ledger_payment(request: Request, ledger_id: str, body: RecordPaymentBody):
    user = await _require_rent_operations_enabled(request, "write")
    try:
        return await rent_payment_service.record_payment_for_ledger(
            ledger_id,
            user["client_id"],
            body.model_dump(mode="json", exclude_unset=True),
            actor_id=user.get("portal_user_id"),
            actor_role=_actor_role(user),
        )
    except ValueError as e:
        _raise_rent_value_error(str(e))


@router.post(
    "/operations/rent/ledgers/{ledger_id}/reminders/mark-sent",
)
async def mark_reminder_sent(request: Request, ledger_id: str, body: MarkReminderSentBody):
    user = await _require_rent_operations_enabled(request, "write")
    try:
        return await rent_reminder_service.mark_reminder_sent(
            ledger_id,
            user["client_id"],
            body.model_dump(),
            actor_id=user.get("portal_user_id"),
            actor_role=_actor_role(user),
        )
    except ValueError as e:
        if str(e) == "LEDGER_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Rent ledger not found")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/operations/expenses/summary")
async def get_expenses_summary(
    request: Request,
    property_id: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
):
    user = await _require_rent_operations_enabled(request)
    try:
        return await property_expense_service.get_expense_summary(
            user["client_id"],
            property_id=property_id,
            from_date=from_date,
            to_date=to_date,
        )
    except ValueError as e:
        if str(e) == "PROPERTY_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Property not found")
        raise


@router.get("/operations/expenses")
async def list_expenses(
    request: Request,
    property_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    compliance_related: Optional[bool] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    user = await _require_rent_operations_enabled(request)
    return await property_expense_service.list_expenses(
        user["client_id"],
        property_id=property_id,
        category=category,
        compliance_related=compliance_related,
        from_date=from_date,
        to_date=to_date,
        skip=skip,
        limit=limit,
    )


@router.post("/operations/expenses")
async def create_expense(request: Request, body: CreateExpenseBody):
    user = await _require_rent_operations_enabled(request, "write")
    try:
        return await property_expense_service.create_expense(
            user["client_id"],
            body.model_dump(mode="json"),
            actor_id=user.get("portal_user_id"),
            actor_role=_actor_role(user),
        )
    except ValueError as e:
        code = str(e)
        if code == "PROPERTY_NOT_FOUND":
            raise HTTPException(
                status_code=404,
                detail=structured_error("PROPERTY_NOT_FOUND", "Property not found or not in your account."),
            )
        if code == "DOCUMENT_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Document not found")
        raise HTTPException(status_code=400, detail=code)


@router.patch("/operations/expenses/{expense_id}")
async def update_expense(request: Request, expense_id: str, body: UpdateExpenseBody):
    user = await _require_rent_operations_enabled(request, "write")
    doc = await property_expense_service.update_expense(
        expense_id,
        user["client_id"],
        body.model_dump(mode="json", exclude_unset=True),
        actor_id=user.get("portal_user_id"),
        actor_role=_actor_role(user),
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Expense not found")
    return doc


@router.delete("/operations/expenses/{expense_id}")
async def delete_expense(request: Request, expense_id: str):
    user = await _require_rent_operations_enabled(request, "write")
    ok = await property_expense_service.delete_expense(
        expense_id,
        user["client_id"],
        actor_id=user.get("portal_user_id"),
        actor_role=_actor_role(user),
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"deleted": True}


@router.get("/properties/{property_id}/financial-snapshot")
async def get_property_financial_snapshot(request: Request, property_id: str):
    user = await _require_rent_operations_enabled(request)
    try:
        return await property_expense_service.get_property_financial_snapshot(user["client_id"], property_id)
    except ValueError as e:
        if str(e) == "PROPERTY_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Property not found")
        raise HTTPException(status_code=400, detail=str(e))
