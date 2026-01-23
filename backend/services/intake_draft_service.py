"""
Intake Draft Service - Manages intake drafts before payment.

Key Principles:
1. Drafts are created BEFORE payment
2. Orders are created ONLY after successful payment
3. Draft → Order conversion happens via Stripe webhook
4. Drafts store intake data; Orders are immutable records

Draft Lifecycle:
DRAFT → READY_FOR_PAYMENT → (payment success) → CONVERTED
                         → (payment failed) → stays READY_FOR_PAYMENT
                         → (abandoned) → ABANDONED
"""
import uuid
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from database import database
from services.intake_schema_registry import (
    get_service_schema,
    validate_intake_payload,
    get_postal_address_schema,
    SERVICES_WITH_UPLOADS,
)
from services.pack_registry import (
    get_pack_contents,
    calculate_pack_price,
    get_addon_requirements,
    validate_pack_addons,
    PACK_ADDONS,
)

logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS
# ============================================================================

class DraftStatus:
    DRAFT = "DRAFT"
    READY_FOR_PAYMENT = "READY_FOR_PAYMENT"
    ABANDONED = "ABANDONED"
    CONVERTED = "CONVERTED"


# Service pricing (in pence) - loaded from catalogue
SERVICE_BASE_PRICES = {
    "AI_WF_BLUEPRINT": 7900,     # £79
    "AI_PROC_MAP": 12900,        # £129
    "AI_TOOL_REPORT": 5900,      # £59
    "MR_BASIC": 6900,            # £69
    "MR_ADV": 14900,             # £149
    "HMO_AUDIT": 7900,           # £79
    "FULL_AUDIT": 9900,          # £99
    "MOVE_CHECKLIST": 3500,      # £35
    "DOC_PACK_ESSENTIAL": 2900,  # £29
    "DOC_PACK_TENANCY": 4900,    # £49
    "DOC_PACK_ULTIMATE": 7900,   # £79
}


# ============================================================================
# DRAFT REFERENCE GENERATOR
# ============================================================================

async def generate_draft_ref() -> str:
    """Generate unique draft reference: INT-YYYYMMDD-####"""
    db = database.get_db()
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"INT-{today}-"
    
    # Find the highest number for today
    latest = await db.intake_drafts.find_one(
        {"draft_ref": {"$regex": f"^{prefix}"}},
        sort=[("draft_ref", -1)]
    )
    
    if latest:
        try:
            last_num = int(latest["draft_ref"].split("-")[-1])
            next_num = last_num + 1
        except (ValueError, IndexError):
            next_num = 1
    else:
        next_num = 1
    
    return f"{prefix}{next_num:04d}"


async def generate_order_ref() -> str:
    """Generate unique order reference: PLE-YYYYMMDD-####"""
    db = database.get_db()
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"PLE-{today}-"
    
    # Find the highest number for today
    latest = await db.orders.find_one(
        {"order_ref": {"$regex": f"^{prefix}"}},
        sort=[("order_ref", -1)]
    )
    
    if latest:
        try:
            last_num = int(latest["order_ref"].split("-")[-1])
            next_num = last_num + 1
        except (ValueError, IndexError):
            next_num = 1
    else:
        next_num = 1
    
    return f"{prefix}{next_num:04d}"


# ============================================================================
# DRAFT CRUD OPERATIONS
# ============================================================================

async def create_draft(
    service_code: str,
    category: str,
    initial_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a new intake draft.
    
    Args:
        service_code: The service being ordered
        category: Service category (ai_automation, market_research, compliance, document_pack)
        initial_data: Optional initial intake data
    
    Returns:
        Created draft document
    """
    db = database.get_db()
    
    draft_id = str(uuid.uuid4())
    draft_ref = await generate_draft_ref()
    now = datetime.now(timezone.utc)
    
    # Get base price
    base_price = SERVICE_BASE_PRICES.get(service_code, 0)
    
    draft_doc = {
        "draft_id": draft_id,
        "draft_ref": draft_ref,
        "service_code": service_code,
        "category": category,
        
        # Add-ons
        "selected_addons": [],
        
        # Pricing snapshot
        "pricing_snapshot": {
            "base_price_pence": base_price,
            "addon_total_pence": 0,
            "total_price_pence": base_price,
            "currency": "gbp",
            "addons": [],
        },
        
        # Client identity (populated during wizard)
        "client_identity": {},
        
        # Delivery consent (populated during wizard)
        "delivery_consent": {},
        
        # Service-specific intake data
        "intake_payload": initial_data or {},
        
        # Schema version for future migrations
        "intake_schema_version": "1.0",
        
        # Status
        "status": DraftStatus.DRAFT,
        
        # Timestamps
        "created_at": now,
        "updated_at": now,
        
        # Audit log
        "audit_log": [
            {
                "action": "DRAFT_CREATED",
                "timestamp": now,
                "details": {"service_code": service_code},
            }
        ],
        
        # Stripe session (set when checkout is created)
        "stripe_checkout_session_id": None,
        
        # Postal address (for printed copy addon)
        "postal_address": None,
    }
    
    await db.intake_drafts.insert_one(draft_doc)
    
    logger.info(f"Created draft {draft_ref} for service {service_code}")
    
    # Return without _id
    draft_doc.pop("_id", None)
    return draft_doc


async def get_draft(draft_id: str) -> Optional[Dict[str, Any]]:
    """Get a draft by ID."""
    db = database.get_db()
    draft = await db.intake_drafts.find_one(
        {"draft_id": draft_id},
        {"_id": 0}
    )
    return draft


async def get_draft_by_ref(draft_ref: str) -> Optional[Dict[str, Any]]:
    """Get a draft by reference."""
    db = database.get_db()
    draft = await db.intake_drafts.find_one(
        {"draft_ref": draft_ref},
        {"_id": 0}
    )
    return draft


async def update_draft(
    draft_id: str,
    updates: Dict[str, Any],
    step: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update a draft with new data.
    
    Args:
        draft_id: Draft ID
        updates: Fields to update
        step: Wizard step name (for audit log)
    
    Returns:
        Updated draft document
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    
    # Get current draft
    draft = await get_draft(draft_id)
    if not draft:
        raise ValueError(f"Draft not found: {draft_id}")
    
    if draft["status"] == DraftStatus.CONVERTED:
        raise ValueError("Cannot update a converted draft")
    
    # Build update document
    update_doc = {
        "$set": {
            "updated_at": now,
            **updates,
        },
        "$push": {
            "audit_log": {
                "action": "DRAFT_UPDATED",
                "timestamp": now,
                "details": {"step": step, "fields_updated": list(updates.keys())},
            }
        }
    }
    
    await db.intake_drafts.update_one(
        {"draft_id": draft_id},
        update_doc
    )
    
    return await get_draft(draft_id)


async def update_draft_intake(
    draft_id: str,
    intake_data: Dict[str, Any],
    merge: bool = True,
) -> Dict[str, Any]:
    """
    Update the intake payload of a draft.
    
    Args:
        draft_id: Draft ID
        intake_data: New intake data
        merge: If True, merge with existing data; if False, replace
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    
    draft = await get_draft(draft_id)
    if not draft:
        raise ValueError(f"Draft not found: {draft_id}")
    
    if draft["status"] == DraftStatus.CONVERTED:
        raise ValueError("Cannot update a converted draft")
    
    if merge:
        existing = draft.get("intake_payload", {})
        new_payload = {**existing, **intake_data}
    else:
        new_payload = intake_data
    
    update_doc = {
        "$set": {
            "intake_payload": new_payload,
            "updated_at": now,
        },
        "$push": {
            "audit_log": {
                "action": "INTAKE_UPDATED",
                "timestamp": now,
                "details": {"fields": list(intake_data.keys())},
            }
        }
    }
    
    await db.intake_drafts.update_one(
        {"draft_id": draft_id},
        update_doc
    )
    
    return await get_draft(draft_id)


async def update_draft_client_identity(
    draft_id: str,
    client_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Update client identity fields."""
    return await update_draft(
        draft_id,
        {"client_identity": client_data},
        step="client_identity"
    )


async def update_draft_delivery_consent(
    draft_id: str,
    consent_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Update delivery and consent fields."""
    return await update_draft(
        draft_id,
        {"delivery_consent": consent_data},
        step="delivery_consent"
    )


async def update_draft_addons(
    draft_id: str,
    addons: List[str],
    postal_address: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Update selected add-ons and recalculate pricing.
    
    Args:
        draft_id: Draft ID
        addons: List of addon codes (e.g., ["FAST_TRACK", "PRINTED_COPY"])
        postal_address: Required if PRINTED_COPY is selected
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    
    draft = await get_draft(draft_id)
    if not draft:
        raise ValueError(f"Draft not found: {draft_id}")
    
    service_code = draft["service_code"]
    
    # For document packs, validate addons
    if service_code.startswith("DOC_PACK"):
        pack_type = service_code.replace("DOC_PACK_", "")
        validation = validate_pack_addons(pack_type, addons)
        if not validation["valid"]:
            raise ValueError(f"Invalid addons: {validation['errors']}")
        
        # Calculate pricing with addons
        pricing = calculate_pack_price(pack_type, addons)
        pricing_snapshot = {
            "base_price_pence": pricing["base_price_pence"],
            "addon_total_pence": pricing["addon_total_pence"],
            "total_price_pence": pricing["total_price_pence"],
            "currency": "gbp",
            "addons": pricing["addons"],
        }
    else:
        # Non-document pack services don't have addons
        base_price = SERVICE_BASE_PRICES.get(service_code, 0)
        pricing_snapshot = {
            "base_price_pence": base_price,
            "addon_total_pence": 0,
            "total_price_pence": base_price,
            "currency": "gbp",
            "addons": [],
        }
    
    # Validate postal address if PRINTED_COPY selected
    if "PRINTED_COPY" in [a.upper() for a in addons]:
        if not postal_address:
            raise ValueError("Postal address required for Printed Copy addon")
        
        # Validate required postal fields
        required_fields = ["postal_recipient_name", "postal_address_line1", "postal_city", "postal_postcode", "postal_phone"]
        missing = [f for f in required_fields if not postal_address.get(f)]
        if missing:
            raise ValueError(f"Missing postal address fields: {missing}")
    
    update_doc = {
        "$set": {
            "selected_addons": addons,
            "pricing_snapshot": pricing_snapshot,
            "postal_address": postal_address,
            "updated_at": now,
        },
        "$push": {
            "audit_log": {
                "action": "ADDONS_UPDATED",
                "timestamp": now,
                "details": {"addons": addons, "total_pence": pricing_snapshot["total_price_pence"]},
            }
        }
    }
    
    await db.intake_drafts.update_one(
        {"draft_id": draft_id},
        update_doc
    )
    
    return await get_draft(draft_id)


# ============================================================================
# VALIDATION
# ============================================================================

async def validate_draft(draft_id: str) -> Dict[str, Any]:
    """
    Validate a draft against its service schema.
    
    Returns:
        {
            "valid": bool,
            "ready_for_payment": bool,
            "errors": [...],
            "warnings": [...],
            "missing_sections": [...],
        }
    """
    draft = await get_draft(draft_id)
    if not draft:
        return {"valid": False, "errors": [{"field_key": "_draft", "message": "Draft not found"}]}
    
    service_code = draft["service_code"]
    errors = []
    warnings = []
    missing_sections = []
    
    # Validate client identity
    client = draft.get("client_identity", {})
    if not client.get("full_name"):
        errors.append({"field_key": "full_name", "message": "Full name is required"})
    if not client.get("email"):
        errors.append({"field_key": "email", "message": "Email is required"})
    if not client.get("phone"):
        errors.append({"field_key": "phone", "message": "Phone is required"})
    if not client.get("role"):
        errors.append({"field_key": "role", "message": "Role is required"})
    if client.get("role") == "Other" and not client.get("role_other_text"):
        errors.append({"field_key": "role_other_text", "message": "Please specify your role"})
    
    if not client:
        missing_sections.append("client_identity")
    
    # Validate delivery consent
    consent = draft.get("delivery_consent", {})
    if not consent.get("consent_terms_privacy"):
        errors.append({"field_key": "consent_terms_privacy", "message": "You must agree to Terms and Privacy Policy"})
    if not consent.get("accuracy_confirmation"):
        errors.append({"field_key": "accuracy_confirmation", "message": "You must confirm accuracy of information"})
    
    if not consent:
        missing_sections.append("delivery_consent")
    
    # Validate service-specific intake
    intake = draft.get("intake_payload", {})
    if not intake:
        missing_sections.append("service_intake")
    else:
        intake_validation = validate_intake_payload(service_code, intake)
        errors.extend(intake_validation.get("errors", []))
        warnings.extend(intake_validation.get("warnings", []))
    
    # Validate postal address if printed copy selected
    addons = draft.get("selected_addons", [])
    if "PRINTED_COPY" in [a.upper() for a in addons]:
        postal = draft.get("postal_address", {})
        if not postal:
            errors.append({"field_key": "postal_address", "message": "Postal address required for printed copy"})
        else:
            required_postal = ["postal_recipient_name", "postal_address_line1", "postal_city", "postal_postcode", "postal_phone"]
            for field in required_postal:
                if not postal.get(field):
                    errors.append({"field_key": field, "message": f"Postal address field {field} is required"})
    
    is_valid = len(errors) == 0
    ready_for_payment = is_valid and len(missing_sections) == 0
    
    return {
        "valid": is_valid,
        "ready_for_payment": ready_for_payment,
        "errors": errors,
        "warnings": warnings,
        "missing_sections": missing_sections,
    }


async def mark_ready_for_payment(draft_id: str) -> Dict[str, Any]:
    """
    Validate and mark draft as ready for payment.
    
    Raises ValueError if validation fails.
    """
    validation = await validate_draft(draft_id)
    
    if not validation["ready_for_payment"]:
        raise ValueError(f"Draft not ready for payment: {validation['errors']}")
    
    db = database.get_db()
    now = datetime.now(timezone.utc)
    
    await db.intake_drafts.update_one(
        {"draft_id": draft_id},
        {
            "$set": {
                "status": DraftStatus.READY_FOR_PAYMENT,
                "updated_at": now,
            },
            "$push": {
                "audit_log": {
                    "action": "MARKED_READY_FOR_PAYMENT",
                    "timestamp": now,
                }
            }
        }
    )
    
    return await get_draft(draft_id)


# ============================================================================
# DRAFT → ORDER CONVERSION (Called by Stripe Webhook)
# ============================================================================

async def convert_draft_to_order(
    draft_id: str,
    stripe_payment_intent_id: str,
    stripe_checkout_session_id: str,
) -> Dict[str, Any]:
    """
    Convert a draft to an order after successful payment.
    
    THIS IS CALLED BY THE STRIPE WEBHOOK HANDLER ONLY.
    
    Args:
        draft_id: The draft to convert
        stripe_payment_intent_id: Stripe payment intent ID
        stripe_checkout_session_id: Stripe checkout session ID
    
    Returns:
        Created order document
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    
    # Get and validate draft
    draft = await get_draft(draft_id)
    if not draft:
        raise ValueError(f"Draft not found: {draft_id}")
    
    if draft["status"] == DraftStatus.CONVERTED:
        # Idempotency - already converted
        existing_order = await db.orders.find_one(
            {"source_draft_id": draft_id},
            {"_id": 0}
        )
        if existing_order:
            logger.info(f"Draft {draft_id} already converted to order {existing_order['order_ref']}")
            return existing_order
    
    # Generate order reference
    order_ref = await generate_order_ref()
    order_id = str(uuid.uuid4())
    
    # Create intake hash for integrity
    intake_snapshot = {
        "client_identity": draft["client_identity"],
        "intake_payload": draft["intake_payload"],
        "delivery_consent": draft["delivery_consent"],
    }
    intake_hash = hashlib.sha256(
        json.dumps(intake_snapshot, sort_keys=True, default=str).encode()
    ).hexdigest()
    
    # Determine SLA hours based on fast track
    sla_hours = 48  # Default
    addons = draft.get("selected_addons", [])
    if "FAST_TRACK" in [a.upper() for a in addons]:
        sla_hours = 24
    
    # Build customer object
    client = draft["client_identity"]
    customer = {
        "full_name": client.get("full_name"),
        "email": client.get("email"),
        "phone": client.get("phone"),
        "role": client.get("role"),
        "company_name": client.get("company_name"),
    }
    
    # Build order document
    from services.order_workflow import OrderStatus
    
    order_doc = {
        "order_id": order_id,
        "order_ref": order_ref,
        "source_draft_id": draft_id,
        "source_draft_ref": draft["draft_ref"],
        
        # Service
        "service_code": draft["service_code"],
        "category": draft["category"],
        "service_name": _get_service_name(draft["service_code"]),
        
        # Add-ons
        "selected_addons": draft["selected_addons"],
        "fast_track": "FAST_TRACK" in [a.upper() for a in addons],
        "priority": "FAST_TRACK" in [a.upper() for a in addons],
        "requires_postal_delivery": "PRINTED_COPY" in [a.upper() for a in addons],
        "postal_address": draft.get("postal_address"),
        "postal_status": "PENDING_PRINT" if "PRINTED_COPY" in [a.upper() for a in addons] else None,
        
        # Pricing snapshot (immutable)
        "pricing_snapshot": draft["pricing_snapshot"],
        "pricing": {
            "base_price": draft["pricing_snapshot"]["base_price_pence"],
            "vat_amount": 0,  # VAT handling can be added
            "total_amount": draft["pricing_snapshot"]["total_price_pence"],
            "currency": "gbp",
            "stripe_payment_intent_id": stripe_payment_intent_id,
            "stripe_checkout_session_id": stripe_checkout_session_id,
        },
        
        # Customer snapshot (immutable)
        "customer": customer,
        
        # Intake snapshot (immutable)
        "intake_snapshot": intake_snapshot,
        "intake_hash": intake_hash,
        "intake_schema_version": draft["intake_schema_version"],
        
        # Workflow state - starts at PAID (payment confirmed)
        "status": OrderStatus.PAID.value,
        "workflow_state": OrderStatus.PAID.value,
        
        # SLA tracking
        "sla_hours": sla_hours,
        "sla_paused_at": None,
        "sla_pause_duration_hours": 0,
        
        # Deliverables (populated during generation)
        "deliverables": [],
        "document_versions": [],
        
        # Timestamps
        "created_at": now,
        "paid_at": now,
        "updated_at": now,
        
        # Payment tracking
        "stripe_payment_status": "paid",
        
        # Audit log (immutable event log)
        "audit_log": [
            {
                "action": "ORDER_CREATED",
                "timestamp": now,
                "details": {
                    "from_draft": draft["draft_ref"],
                    "payment_intent": stripe_payment_intent_id,
                }
            }
        ],
    }
    
    # Insert order
    await db.orders.insert_one(order_doc)
    
    # Mark draft as converted
    await db.intake_drafts.update_one(
        {"draft_id": draft_id},
        {
            "$set": {
                "status": DraftStatus.CONVERTED,
                "converted_at": now,
                "converted_order_id": order_id,
                "converted_order_ref": order_ref,
            },
            "$push": {
                "audit_log": {
                    "action": "CONVERTED_TO_ORDER",
                    "timestamp": now,
                    "details": {"order_ref": order_ref},
                }
            }
        }
    )
    
    logger.info(f"Converted draft {draft['draft_ref']} to order {order_ref}")
    
    # Trigger workflow (WF1)
    try:
        from services.workflow_automation_service import workflow_automation_service
        await workflow_automation_service.wf1_payment_to_queue(order_id)
    except Exception as e:
        logger.error(f"Failed to trigger WF1 for order {order_id}: {e}")
        # Don't fail the conversion - order is created
    
    order_doc.pop("_id", None)
    return order_doc


def _get_service_name(service_code: str) -> str:
    """Get display name for service code."""
    names = {
        "AI_WF_BLUEPRINT": "Workflow Automation Blueprint",
        "AI_PROC_MAP": "Business Process Mapping",
        "AI_TOOL_REPORT": "AI Tool Recommendation Report",
        "MR_BASIC": "Market Research - Basic",
        "MR_ADV": "Market Research - Advanced",
        "HMO_AUDIT": "HMO Compliance Audit",
        "FULL_AUDIT": "Full Compliance Audit",
        "MOVE_CHECKLIST": "Move-In/Out Checklist",
        "DOC_PACK_ESSENTIAL": "Essential Document Pack",
        "DOC_PACK_TENANCY": "Tenancy Document Pack",
        "DOC_PACK_ULTIMATE": "Ultimate Document Pack",
    }
    return names.get(service_code, service_code)


# ============================================================================
# STRIPE CHECKOUT SESSION
# ============================================================================

async def create_checkout_session(
    draft_id: str,
    success_url: str,
    cancel_url: str,
) -> Dict[str, Any]:
    """
    Create a Stripe checkout session for a draft.
    
    Returns:
        {
            "checkout_url": str,
            "session_id": str,
        }
    """
    import stripe
    import os
    
    stripe.api_key = os.getenv("STRIPE_API_KEY", "sk_test_emergent")
    
    # Validate draft is ready
    draft = await get_draft(draft_id)
    if not draft:
        raise ValueError(f"Draft not found: {draft_id}")
    
    validation = await validate_draft(draft_id)
    if not validation["ready_for_payment"]:
        raise ValueError(f"Draft not ready for payment: {validation['errors']}")
    
    # Mark as ready for payment
    await mark_ready_for_payment(draft_id)
    
    pricing = draft["pricing_snapshot"]
    client = draft["client_identity"]
    
    # Create line items
    line_items = [
        {
            "price_data": {
                "currency": "gbp",
                "product_data": {
                    "name": _get_service_name(draft["service_code"]),
                    "description": f"Order: {draft['draft_ref']}",
                },
                "unit_amount": pricing["base_price_pence"],
            },
            "quantity": 1,
        }
    ]
    
    # Add addon line items
    for addon in pricing.get("addons", []):
        line_items.append({
            "price_data": {
                "currency": "gbp",
                "product_data": {
                    "name": addon["name"],
                },
                "unit_amount": addon["price_pence"],
            },
            "quantity": 1,
        })
    
    # Create Stripe checkout session
    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=line_items,
        customer_email=client.get("email"),
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "draft_id": draft_id,
            "draft_ref": draft["draft_ref"],
            "service_code": draft["service_code"],
            "type": "order_intake",
        },
        expires_at=int((datetime.now(timezone.utc).timestamp()) + 3600),  # 1 hour
    )
    
    # Store session ID in draft
    db = database.get_db()
    await db.intake_drafts.update_one(
        {"draft_id": draft_id},
        {
            "$set": {
                "stripe_checkout_session_id": session.id,
                "updated_at": datetime.now(timezone.utc),
            },
            "$push": {
                "audit_log": {
                    "action": "CHECKOUT_SESSION_CREATED",
                    "timestamp": datetime.now(timezone.utc),
                    "details": {"session_id": session.id},
                }
            }
        }
    )
    
    logger.info(f"Created checkout session {session.id} for draft {draft_id}")
    
    return {
        "checkout_url": session.url,
        "session_id": session.id,
    }


# ============================================================================
# DRAFT CLEANUP
# ============================================================================

async def mark_draft_abandoned(draft_id: str) -> Dict[str, Any]:
    """Mark a draft as abandoned."""
    db = database.get_db()
    now = datetime.now(timezone.utc)
    
    await db.intake_drafts.update_one(
        {"draft_id": draft_id},
        {
            "$set": {
                "status": DraftStatus.ABANDONED,
                "updated_at": now,
            },
            "$push": {
                "audit_log": {
                    "action": "MARKED_ABANDONED",
                    "timestamp": now,
                }
            }
        }
    )
    
    return await get_draft(draft_id)


async def cleanup_abandoned_drafts(hours_old: int = 24) -> int:
    """
    Mark old drafts as abandoned.
    Called by background job.
    """
    db = database.get_db()
    from datetime import timedelta
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_old)
    
    result = await db.intake_drafts.update_many(
        {
            "status": {"$in": [DraftStatus.DRAFT, DraftStatus.READY_FOR_PAYMENT]},
            "updated_at": {"$lt": cutoff},
        },
        {
            "$set": {"status": DraftStatus.ABANDONED},
            "$push": {
                "audit_log": {
                    "action": "AUTO_ABANDONED",
                    "timestamp": datetime.now(timezone.utc),
                    "details": {"reason": f"Inactive for {hours_old}+ hours"},
                }
            }
        }
    )
    
    if result.modified_count > 0:
        logger.info(f"Marked {result.modified_count} drafts as abandoned")
    
    return result.modified_count
