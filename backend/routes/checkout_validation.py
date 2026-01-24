"""
Checkout Validation API

Provides validation endpoints to ensure service_code alignment before
Stripe checkout is initiated. Prevents mismatches between frontend
selections and backend capabilities.

Key Features:
- Validates service_code exists in service catalogue
- Validates document selections for pack orders
- Returns pricing and pack info for checkout display
- Ensures Stripe product/price IDs are configured
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from database import database
from services.document_pack_orchestrator import (
    document_pack_orchestrator,
    SERVICE_CODE_TO_PACK_TIER,
    DOCUMENT_REGISTRY,
    CANONICAL_ORDER,
)
from services.document_pack_webhook_handler import document_pack_webhook_handler

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/checkout", tags=["checkout-validation"])


# ============================================
# Request/Response Models
# ============================================

class ValidateCheckoutRequest(BaseModel):
    """Request to validate checkout before Stripe session creation."""
    service_code: str = Field(..., description="Service code to validate")
    selected_documents: Optional[List[str]] = Field(None, description="For document packs, list of doc_keys selected")
    variant_code: Optional[str] = Field("standard", description="Pricing variant (standard, fast_track, printed)")


class ValidationResult(BaseModel):
    """Validation result for checkout."""
    valid: bool
    service_code: str
    service_name: Optional[str] = None
    variant_code: str
    errors: List[str] = []
    warnings: List[str] = []
    
    # Pricing info
    stripe_price_id: Optional[str] = None
    price_amount: Optional[int] = None
    currency: str = "gbp"
    
    # Pack-specific info
    is_document_pack: bool = False
    pack_tier: Optional[str] = None
    total_documents_available: int = 0
    documents_selected: int = 0
    selected_documents: List[str] = []
    
    # Metadata for checkout session
    checkout_metadata: Dict[str, Any] = {}


# ============================================
# Validation Endpoints
# ============================================

@router.post("/validate", response_model=ValidationResult)
async def validate_checkout(request: ValidateCheckoutRequest):
    """
    Validate service code and selections before creating Stripe checkout.
    
    Returns:
    - Valid flag and any errors/warnings
    - Stripe price_id to use
    - Pack info if document pack
    - Metadata to include in checkout session
    """
    errors = []
    warnings = []
    service_name = None
    stripe_price_id = None
    price_amount = None
    pack_tier = None
    total_docs = 0
    docs_selected = 0
    valid_selections = []
    
    db = database.get_db()
    
    # Step 1: Check if service exists in catalogue
    service = await db.service_catalogue_v2.find_one(
        {"service_code": request.service_code, "active": True},
        {"_id": 0}
    )
    
    if not service:
        errors.append(f"Service not found or inactive: {request.service_code}")
        return ValidationResult(
            valid=False,
            service_code=request.service_code,
            variant_code=request.variant_code,
            errors=errors,
        )
    
    service_name = service.get("service_name")
    
    # Step 2: Find matching pricing variant
    pricing_variants = service.get("pricing_variants", [])
    selected_variant = None
    
    for variant in pricing_variants:
        if variant.get("variant_code") == request.variant_code:
            selected_variant = variant
            break
    
    if not selected_variant:
        # Default to standard if not found
        for variant in pricing_variants:
            if variant.get("variant_code") == "standard":
                selected_variant = variant
                warnings.append(f"Variant '{request.variant_code}' not found, using 'standard'")
                break
    
    if selected_variant:
        stripe_price_id = selected_variant.get("stripe_price_id")
        price_amount = selected_variant.get("price_amount")
        
        if not stripe_price_id:
            warnings.append(f"No Stripe price_id configured for {request.service_code}/{request.variant_code}")
    else:
        errors.append(f"No pricing variants found for {request.service_code}")
    
    # Step 3: Document Pack specific validation
    is_document_pack = request.service_code in document_pack_webhook_handler.VALID_PACK_CODES
    
    if is_document_pack:
        # Validate pack tier
        is_valid, pack_error = await document_pack_webhook_handler.validate_service_code(request.service_code)
        
        if not is_valid:
            errors.append(pack_error)
        else:
            pack_tier = SERVICE_CODE_TO_PACK_TIER.get(request.service_code)
            if pack_tier:
                pack_tier = pack_tier.value
                allowed_docs = document_pack_orchestrator.get_allowed_docs(
                    document_pack_orchestrator.get_pack_tier(request.service_code)
                )
                total_docs = len(allowed_docs)
                
                # Validate selected documents
                if request.selected_documents:
                    for doc_key in request.selected_documents:
                        if doc_key in allowed_docs:
                            valid_selections.append(doc_key)
                        else:
                            warnings.append(f"Document '{doc_key}' not available in {request.service_code} pack")
                    
                    docs_selected = len(valid_selections)
                    
                    if docs_selected == 0:
                        warnings.append("No valid documents selected, all pack documents will be generated")
                else:
                    warnings.append("No documents explicitly selected, all pack documents will be generated")
                    docs_selected = total_docs
    
    # Build checkout metadata
    checkout_metadata = {
        "service_code": request.service_code,
        "variant_code": request.variant_code or "standard",
        "pleerity_checkout": "true",
    }
    
    if is_document_pack:
        checkout_metadata["pack_tier"] = pack_tier or ""
        checkout_metadata["documents_selected"] = str(docs_selected)
        if valid_selections:
            checkout_metadata["selected_doc_keys"] = ",".join(valid_selections[:20])  # Stripe metadata limit
    
    return ValidationResult(
        valid=len(errors) == 0,
        service_code=request.service_code,
        service_name=service_name,
        variant_code=request.variant_code or "standard",
        errors=errors,
        warnings=warnings,
        stripe_price_id=stripe_price_id,
        price_amount=price_amount,
        is_document_pack=is_document_pack,
        pack_tier=pack_tier,
        total_documents_available=total_docs,
        documents_selected=docs_selected,
        selected_documents=valid_selections,
        checkout_metadata=checkout_metadata,
    )


@router.get("/service-info/{service_code}")
async def get_service_checkout_info(service_code: str):
    """
    Get service information for checkout display.
    
    Returns service details, pricing, and pack info if applicable.
    """
    db = database.get_db()
    
    service = await db.service_catalogue_v2.find_one(
        {"service_code": service_code, "active": True},
        {"_id": 0}
    )
    
    if not service:
        raise HTTPException(status_code=404, detail=f"Service not found: {service_code}")
    
    result = {
        "service_code": service_code,
        "service_name": service.get("service_name"),
        "description": service.get("description"),
        "category": service.get("category"),
        "pricing_variants": service.get("pricing_variants", []),
        "base_price": service.get("base_price"),
        "fast_track_available": service.get("fast_track_available", False),
        "fast_track_price": service.get("fast_track_price"),
        "printed_copy_available": service.get("printed_copy_available", False),
        "printed_copy_price": service.get("printed_copy_price"),
    }
    
    # Add document pack info
    if service_code in document_pack_webhook_handler.VALID_PACK_CODES:
        pack_info = document_pack_orchestrator.get_pack_info(service_code)
        result["is_document_pack"] = True
        result["pack_tier"] = pack_info.get("pack_tier")
        result["total_documents"] = pack_info.get("total_documents")
        result["documents"] = pack_info.get("documents", [])
        result["inherits_from"] = service.get("parent_pack_code")
    else:
        result["is_document_pack"] = False
    
    return result


@router.get("/document-packs")
async def list_document_packs():
    """
    List all document packs with their info for checkout selection.
    """
    packs = []
    
    for pack_code in ["DOC_PACK_ESSENTIAL", "DOC_PACK_PLUS", "DOC_PACK_PRO"]:
        try:
            pack_info = document_pack_orchestrator.get_pack_info(pack_code)
            
            db = database.get_db()
            service = await db.service_catalogue_v2.find_one(
                {"service_code": pack_code, "active": True},
                {"_id": 0, "pricing_variants": 1, "service_name": 1, "description": 1}
            )
            
            packs.append({
                "service_code": pack_code,
                "pack_tier": pack_info.get("pack_tier"),
                "service_name": service.get("service_name") if service else pack_code,
                "description": service.get("description") if service else "",
                "total_documents": pack_info.get("total_documents"),
                "pricing_variants": service.get("pricing_variants", []) if service else [],
                "documents": pack_info.get("documents", []),
            })
        except Exception as e:
            logger.error(f"Error getting pack info for {pack_code}: {e}")
    
    return {
        "document_packs": packs,
        "pack_hierarchy": "ESSENTIAL → PLUS → PRO (inherits all lower tier documents)",
    }


@router.get("/validate-stripe-alignment")
async def validate_stripe_alignment():
    """
    Validate that all services have Stripe price IDs configured.
    
    Use this to identify services that need Stripe product setup.
    """
    db = database.get_db()
    
    services = await db.service_catalogue_v2.find(
        {"active": True},
        {"_id": 0, "service_code": 1, "service_name": 1, "pricing_variants": 1}
    ).to_list(length=100)
    
    aligned = []
    misaligned = []
    
    for service in services:
        service_code = service.get("service_code")
        variants = service.get("pricing_variants", [])
        
        missing_prices = []
        for variant in variants:
            if not variant.get("stripe_price_id"):
                missing_prices.append(variant.get("variant_code"))
        
        if missing_prices:
            misaligned.append({
                "service_code": service_code,
                "service_name": service.get("service_name"),
                "missing_stripe_prices": missing_prices,
            })
        else:
            aligned.append({
                "service_code": service_code,
                "variants_configured": len(variants),
            })
    
    return {
        "aligned_services": len(aligned),
        "misaligned_services": len(misaligned),
        "aligned": aligned,
        "misaligned": misaligned,
        "action_needed": len(misaligned) > 0,
        "recommendation": "Run 'python scripts/setup_stripe_products.py' to create missing Stripe products" if misaligned else "All services aligned with Stripe",
    }
