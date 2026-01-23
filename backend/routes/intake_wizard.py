"""
Intake Routes - Unified Intake Wizard API

This module provides the API endpoints for the unified intake wizard.
All non-CVP services use this intake flow:
1. Create draft
2. Update draft (step by step)
3. Validate draft
4. Create checkout session
5. Stripe webhook converts draft → order

CVP subscriptions use a separate flow and are EXCLUDED.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging
import os

from database import database
from services.intake_draft_service import (
    create_draft,
    get_draft,
    get_draft_by_ref,
    update_draft,
    update_draft_intake,
    update_draft_client_identity,
    update_draft_delivery_consent,
    update_draft_addons,
    validate_draft,
    mark_ready_for_payment,
    create_checkout_session,
    mark_draft_abandoned,
    DraftStatus,
    SERVICE_BASE_PRICES,
)
from services.intake_schema_registry import (
    get_service_schema,
    get_postal_address_schema,
    SERVICE_INTAKE_SCHEMAS,
    SERVICES_WITH_UPLOADS,
)
from services.pack_registry import (
    get_pack_contents,
    get_all_packs,
    get_all_addons,
    calculate_pack_price,
    PACK_ADDONS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intake", tags=["intake"])


# ============================================================================
# SCHEMA ENDPOINTS
# ============================================================================

@router.get("/services")
async def list_available_services():
    """
    List all services available for intake.
    Excludes CVP subscription services.
    """
    services = []
    
    # AI Automation
    services.extend([
        {
            "service_code": "AI_WF_BLUEPRINT",
            "name": "Workflow Automation Blueprint",
            "category": "ai_automation",
            "price_pence": 7900,
            "price_display": "£79.00",
            "description": "Comprehensive workflow analysis and automation roadmap",
        },
        {
            "service_code": "AI_PROC_MAP",
            "name": "Business Process Mapping",
            "category": "ai_automation",
            "price_pence": 12900,
            "price_display": "£129.00",
            "description": "Detailed As-Is and To-Be process documentation",
        },
        {
            "service_code": "AI_TOOL_REPORT",
            "name": "AI Tool Recommendation Report",
            "category": "ai_automation",
            "price_pence": 5900,
            "price_display": "£59.00",
            "description": "Vendor-neutral AI tool assessment and recommendations",
        },
    ])
    
    # Market Research
    services.extend([
        {
            "service_code": "MR_BASIC",
            "name": "Market Research - Basic",
            "category": "market_research",
            "price_pence": 6900,
            "price_display": "£69.00",
            "description": "Market overview, competitor analysis, key insights",
        },
        {
            "service_code": "MR_ADV",
            "name": "Market Research - Advanced",
            "category": "market_research",
            "price_pence": 14900,
            "price_display": "£149.00",
            "description": "Comprehensive research with SWOT, pricing analysis, strategy",
        },
    ])
    
    # Compliance Services
    services.extend([
        {
            "service_code": "HMO_AUDIT",
            "name": "HMO Compliance Audit",
            "category": "compliance",
            "price_pence": 7900,
            "price_display": "£79.00",
            "description": "Full HMO compliance assessment and recommendations",
        },
        {
            "service_code": "FULL_AUDIT",
            "name": "Full Compliance Audit",
            "category": "compliance",
            "price_pence": 9900,
            "price_display": "£99.00",
            "description": "Complete landlord compliance audit including tenancy docs",
        },
        {
            "service_code": "MOVE_CHECKLIST",
            "name": "Move-In/Out Checklist",
            "category": "compliance",
            "price_pence": 3500,
            "price_display": "£35.00",
            "description": "Professional property condition checklist",
        },
    ])
    
    # Document Packs
    services.extend([
        {
            "service_code": "DOC_PACK_ESSENTIAL",
            "name": "Essential Document Pack",
            "category": "document_pack",
            "price_pence": 2900,
            "price_display": "£29.00",
            "description": "Core landlord forms and letters (5 documents)",
            "supports_addons": True,
        },
        {
            "service_code": "DOC_PACK_TENANCY",
            "name": "Tenancy Document Pack",
            "category": "document_pack",
            "price_pence": 4900,
            "price_display": "£49.00",
            "description": "Essential + Legal agreements (11 documents)",
            "supports_addons": True,
        },
        {
            "service_code": "DOC_PACK_ULTIMATE",
            "name": "Ultimate Document Pack",
            "category": "document_pack",
            "price_pence": 7900,
            "price_display": "£79.00",
            "description": "Complete coverage - all documents (15 documents)",
            "supports_addons": True,
        },
    ])
    
    return {
        "services": services,
        "categories": [
            {"code": "ai_automation", "name": "AI & Automation"},
            {"code": "market_research", "name": "Market Research"},
            {"code": "compliance", "name": "Compliance Services"},
            {"code": "document_pack", "name": "Document Packs"},
        ],
    }


@router.get("/schema/{service_code}")
async def get_intake_schema(service_code: str):
    """
    Get the intake schema for a specific service.
    Returns field definitions, visibility rules, and validation requirements.
    """
    if service_code not in SERVICE_INTAKE_SCHEMAS:
        raise HTTPException(status_code=404, detail=f"Unknown service: {service_code}")
    
    schema = get_service_schema(service_code)
    
    # Add pricing info
    schema["pricing"] = {
        "base_price_pence": SERVICE_BASE_PRICES.get(service_code, 0),
        "base_price_display": f"£{SERVICE_BASE_PRICES.get(service_code, 0) / 100:.2f}",
    }
    
    return schema


@router.get("/packs")
async def list_document_packs():
    """Get all document pack options with contents."""
    packs = get_all_packs()
    addons = get_all_addons()
    
    # Enrich with document lists
    
    for pack in packs:
        contents = get_pack_contents(pack["pack_type"])
        pack["documents"] = contents["documents"]
    
    return {
        "packs": packs,
        "addons": addons,
    }


@router.get("/addons")
async def list_addons():
    """Get all available add-ons."""
    return {"addons": get_all_addons()}


@router.get("/postal-address-schema")
async def get_postal_schema():
    """Get postal address field schema (for printed copy addon)."""
    return {"fields": get_postal_address_schema()}


# ============================================================================
# DRAFT CRUD ENDPOINTS
# ============================================================================

class CreateDraftRequest(BaseModel):
    service_code: str
    category: str


@router.post("/draft")
async def create_intake_draft(request: CreateDraftRequest):
    """
    Create a new intake draft.
    
    This is the starting point for the intake wizard.
    """
    if request.service_code not in SERVICE_INTAKE_SCHEMAS:
        raise HTTPException(status_code=400, detail=f"Unknown service: {request.service_code}")
    
    if request.service_code.startswith("CVP_"):
        raise HTTPException(status_code=400, detail="CVP services use a different intake flow")
    
    try:
        draft = await create_draft(
            service_code=request.service_code,
            category=request.category,
        )
        return draft
    except Exception as e:
        logger.error(f"Failed to create draft: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/draft/{draft_id}")
async def get_intake_draft(draft_id: str):
    """
    Get a draft by ID.
    Includes validation status.
    """
    draft = await get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    # Include validation status
    validation = await validate_draft(draft_id)
    draft["validation"] = validation
    
    # Include schema for convenience
    draft["schema"] = get_service_schema(draft["service_code"])
    
    return draft


@router.get("/draft/by-ref/{draft_ref}")
async def get_draft_by_reference(draft_ref: str):
    """Get a draft by reference (INT-YYYYMMDD-####)."""
    draft = await get_draft_by_ref(draft_ref)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    validation = await validate_draft(draft["draft_id"])
    draft["validation"] = validation
    
    return draft


class UpdateClientIdentityRequest(BaseModel):
    full_name: str
    email: str
    phone: str
    role: str
    role_other_text: Optional[str] = None
    company_name: Optional[str] = None
    company_website: Optional[str] = None


@router.put("/draft/{draft_id}/client-identity")
async def update_client_identity(draft_id: str, request: UpdateClientIdentityRequest):
    """Update client identity fields (Step 2 of wizard)."""
    draft = await get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if draft["status"] == DraftStatus.CONVERTED:
        raise HTTPException(status_code=400, detail="Cannot update converted draft")
    
    try:
        updated = await update_draft_client_identity(
            draft_id,
            request.model_dump(exclude_none=True)
        )
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class UpdateIntakeRequest(BaseModel):
    intake_data: Dict[str, Any]
    merge: bool = True


@router.put("/draft/{draft_id}/intake")
async def update_intake_data(draft_id: str, request: UpdateIntakeRequest):
    """
    Update service-specific intake fields (Step 3 of wizard).
    
    Args:
        intake_data: Service-specific field values
        merge: If true, merge with existing data; if false, replace
    """
    draft = await get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if draft["status"] == DraftStatus.CONVERTED:
        raise HTTPException(status_code=400, detail="Cannot update converted draft")
    
    try:
        updated = await update_draft_intake(
            draft_id,
            request.intake_data,
            merge=request.merge
        )
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class UpdateDeliveryConsentRequest(BaseModel):
    preferred_delivery_email: Optional[str] = None
    consent_terms_privacy: bool
    accuracy_confirmation: bool


@router.put("/draft/{draft_id}/delivery-consent")
async def update_delivery_consent(draft_id: str, request: UpdateDeliveryConsentRequest):
    """Update delivery preferences and consent (part of review step)."""
    draft = await get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if draft["status"] == DraftStatus.CONVERTED:
        raise HTTPException(status_code=400, detail="Cannot update converted draft")
    
    try:
        updated = await update_draft_delivery_consent(
            draft_id,
            request.model_dump(exclude_none=True)
        )
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class UpdateAddonsRequest(BaseModel):
    addons: List[str] = []
    postal_address: Optional[Dict[str, Any]] = None


@router.put("/draft/{draft_id}/addons")
async def update_addons(draft_id: str, request: UpdateAddonsRequest):
    """
    Update selected add-ons (for document packs).
    
    If PRINTED_COPY is selected, postal_address is required.
    """
    draft = await get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if draft["status"] == DraftStatus.CONVERTED:
        raise HTTPException(status_code=400, detail="Cannot update converted draft")
    
    # Only document packs support addons
    if not draft["service_code"].startswith("DOC_PACK"):
        raise HTTPException(status_code=400, detail="Add-ons only available for document packs")
    
    try:
        updated = await update_draft_addons(
            draft_id,
            request.addons,
            request.postal_address
        )
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# VALIDATION ENDPOINT
# ============================================================================

@router.post("/draft/{draft_id}/validate")
async def validate_intake_draft(draft_id: str):
    """
    Validate a draft against its service schema.
    
    Returns validation status, errors, and missing sections.
    """
    draft = await get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    validation = await validate_draft(draft_id)
    
    return {
        "draft_id": draft_id,
        "draft_ref": draft["draft_ref"],
        "status": draft["status"],
        **validation,
    }


# ============================================================================
# CHECKOUT ENDPOINT
# ============================================================================

class CreateCheckoutRequest(BaseModel):
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


@router.post("/draft/{draft_id}/checkout")
async def create_draft_checkout(draft_id: str, request: CreateCheckoutRequest):
    """
    Create a Stripe checkout session for a validated draft.
    
    The draft must be validated and ready for payment.
    Returns a checkout URL to redirect the user to.
    """
    draft = await get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if draft["status"] == DraftStatus.CONVERTED:
        raise HTTPException(status_code=400, detail="Draft already converted to order")
    
    # Validate before creating checkout
    validation = await validate_draft(draft_id)
    if not validation["ready_for_payment"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Draft not ready for payment",
                "errors": validation["errors"],
                "missing_sections": validation["missing_sections"],
            }
        )
    
    # Build URLs
    frontend_url = os.getenv("FRONTEND_URL", "https://pleerity.com")
    success_url = request.success_url or f"{frontend_url}/order/confirmation?draft_id={draft_id}"
    cancel_url = request.cancel_url or f"{frontend_url}/order/intake/{draft_id}?cancelled=true"
    
    try:
        result = await create_checkout_session(
            draft_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create checkout session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


# ============================================================================
# CONFIRMATION ENDPOINT
# ============================================================================

@router.get("/draft/{draft_id}/confirmation")
async def get_draft_confirmation(draft_id: str):
    """
    Get confirmation details for a draft.
    
    If the draft has been converted to an order, returns order details.
    Otherwise returns draft status (useful for polling).
    """
    draft = await get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if draft["status"] == DraftStatus.CONVERTED:
        # Get the order
        db = database.get_db()
        order = await db.orders.find_one(
            {"source_draft_id": draft_id},
            {"_id": 0, "order_ref": 1, "order_id": 1, "status": 1, "created_at": 1, "service_code": 1}
        )
        
        return {
            "converted": True,
            "draft_ref": draft["draft_ref"],
            "order": order,
        }
    else:
        return {
            "converted": False,
            "draft_ref": draft["draft_ref"],
            "status": draft["status"],
        }


# ============================================================================
# PRICE CALCULATION
# ============================================================================

class CalculatePriceRequest(BaseModel):
    service_code: str
    addons: List[str] = []


@router.post("/calculate-price")
async def calculate_service_price(request: CalculatePriceRequest):
    """
    Calculate total price for a service with add-ons.
    """
    service_code = request.service_code
    
    if service_code not in SERVICE_BASE_PRICES:
        raise HTTPException(status_code=400, detail=f"Unknown service: {service_code}")
    
    base_price = SERVICE_BASE_PRICES[service_code]
    
    if service_code.startswith("DOC_PACK"):
        # Use pack registry for document packs
        pack_type = service_code.replace("DOC_PACK_", "")
        try:
            pricing = calculate_pack_price(pack_type, request.addons)
            return pricing
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        # Non-pack services don't have addons
        return {
            "service_code": service_code,
            "base_price_pence": base_price,
            "addon_total_pence": 0,
            "total_price_pence": base_price,
            "currency": "gbp",
            "addons": [],
            "base_price_display": f"£{base_price / 100:.2f}",
            "addon_total_display": "£0.00",
            "total_price_display": f"£{base_price / 100:.2f}",
        }


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@router.get("/admin/drafts")
async def list_drafts(
    status: Optional[str] = None,
    service_code: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
):
    """
    List intake drafts (admin view).
    """
    db = database.get_db()
    
    query = {}
    if status:
        query["status"] = status
    if service_code:
        query["service_code"] = service_code
    
    drafts = await db.intake_drafts.find(
        query,
        {"_id": 0, "intake_payload": 0}  # Exclude large fields
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
    
    total = await db.intake_drafts.count_documents(query)
    
    return {
        "drafts": drafts,
        "total": total,
        "limit": limit,
        "skip": skip,
    }


@router.delete("/draft/{draft_id}")
async def abandon_draft(draft_id: str):
    """Mark a draft as abandoned."""
    draft = await get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if draft["status"] == DraftStatus.CONVERTED:
        raise HTTPException(status_code=400, detail="Cannot abandon converted draft")
    
    updated = await mark_draft_abandoned(draft_id)
    return {"success": True, "draft": updated}
