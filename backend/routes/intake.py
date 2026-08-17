"""Universal Intake Wizard Routes - Premium 5-step intake with conditional logic.

Endpoints:
- POST /api/intake/submit - Submit completed intake wizard
- POST /api/intake/agreement-preview - Checkout-grade agreement HTML (same pipeline as acceptance; Step 5)
- POST /api/intake/pilot-invite/validate - Validate founding pilot invite code (optional pre-checkout)
- POST /api/intake/checkout - Create Stripe checkout session (JSON: acceptance_id required; invite_code optional)
- GET /api/intake/onboarding-status/{client_id} - Get onboarding progress
- GET /api/intake/councils - Search UK councils
- POST /api/intake/upload-document - Upload document during intake (non-blocking)
- GET /api/intake/plans - Get available billing plans with limits
- POST /api/intake/validate-property-count - Validate property count against plan limit
- POST /api/intake/check-email - Whether email is available for new intake (rate-limited; matches submit duplicate rule)

INTAKE-LEVEL GATING (NON-NEGOTIABLE):
- Plan gating MUST be enforced inside the intake form
- Property limits are enforced at:
  1. Frontend UI (prevent adding beyond limit)
  2. Intake API validation (block submission)
  3. Provisioning safeguards (defense in depth)
"""
from fastapi import APIRouter, HTTPException, Request, status, UploadFile, File, Form, Body
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from utils.rate_limiter import rate_limiter, log_rate_limit_event
from database import database
from models import (
    IntakeFormData, IntakePropertyData, Client, Property, ServiceCode, 
    AuditAction, BillingPlan, OnboardingStatus, SubscriptionStatus,
    Document, DocumentStatus, ClientType, PreferredContact
)
from services.stripe_service import stripe_service
from services.plan_registry import plan_registry, PlanCode, PriceConfigMissingError, StripeModeMismatchError
from services.compliance_rules_registry import canonicalize_uk_portfolio_label
from models.agreements import IntakeCheckoutBody
from models.pilot_invite import PilotInvitePublicError, PilotInviteValidateBody, PilotInviteValidateResponse
from services.pilot_invite_service import validate_invite_for_checkout
from services.agreement_acceptance_service import mark_acceptance_checkout_started, validate_acceptance_for_checkout
from services.crn_service import get_next_crn
from utils.audit import create_audit_log
import logging
import json
import os
import shutil
import uuid
import string
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from utils.storage_paths import resolve_document_storage_path, resolve_intake_upload_dir

from pymongo.errors import DuplicateKeyError
from utils.request_ip import get_client_ip
from utils.client_email import (
    INTAKE_EMAIL_ALREADY_EXISTS_MESSAGE,
    ONBOARDING_IDENTITY_ACTIVE,
    canonical_client_email,
    client_email_taken,
    classify_clients_duplicate_key_error,
    find_latest_released_attempt_for_email,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intake", tags=["intake"])

INTAKE_AGREEMENT_PREVIEW_RATE_ATTEMPTS = 60
INTAKE_AGREEMENT_PREVIEW_RATE_WINDOW_MINUTES = 10

# Document vault path for copying intake-uploaded files (same as documents route / intake_upload_migration)
DOCUMENT_STORAGE_PATH = resolve_document_storage_path()

# Plan property limits - now uses plan_registry as single source of truth
# These are kept for backward compatibility but plan_registry is authoritative
PLAN_PROPERTY_LIMITS = {
    BillingPlan.PLAN_1_SOLO: 2,
    BillingPlan.PLAN_2_PORTFOLIO: 10,
    BillingPlan.PLAN_3_PRO: 25,
    # Legacy mappings
    BillingPlan.PLAN_1: 2,
    BillingPlan.PLAN_2_5: 10,
    BillingPlan.PLAN_6_15: 25,
}

# Plan details for UI - now uses plan_registry as single source of truth
PLAN_DETAILS = {
    BillingPlan.PLAN_1_SOLO: {
        "name": "Solo Landlord",
        "max_properties": 2,
        "monthly_price": 19.00,
        "setup_fee": 49.00,
        "features": [
            "Up to 2 properties",
            "Full compliance tracking",
            "Document storage",
            "Email reminders",
            "AI document scanner (basic)"
        ]
    },
    BillingPlan.PLAN_2_PORTFOLIO: {
        "name": "Portfolio Landlord",
        "max_properties": 10,
        "monthly_price": 39.00,
        "setup_fee": 79.00,
        "features": [
            "Up to 10 properties",
            "Full compliance tracking",
            "Document storage",
            "Email & SMS reminders",
            "AI document scanner (advanced)",
            "PDF/CSV reports",
            "Tenant portal (view-only)",
            "Priority support"
        ]
    },
    BillingPlan.PLAN_3_PRO: {
        "name": "Professional",
        "max_properties": 25,
        "monthly_price": 79.00,
        "setup_fee": 149.00,
        "features": [
            "Up to 25 properties",
            "Full compliance tracking",
            "Unlimited document storage",
            "Email & SMS reminders",
            "AI document scanner (advanced)",
            "PDF/CSV reports",
            "Tenant portal (view-only)",
            "Webhook integrations",
            "API access",
            "White-label reports",
            "Audit log export",
            "Priority support"
        ]
    },
    # Legacy plan details (for backward compatibility)
    BillingPlan.PLAN_1: {
        "name": "Solo Landlord",
        "max_properties": 2,
        "monthly_price": 19.00,
        "setup_fee": 49.00,
        "features": ["Up to 2 properties", "Full compliance tracking"]
    },
    BillingPlan.PLAN_2_5: {
        "name": "Portfolio Landlord",
        "max_properties": 10,
        "monthly_price": 39.00,
        "setup_fee": 79.00,
        "features": ["Up to 10 properties", "Advanced features"]
    },
    BillingPlan.PLAN_6_15: {
        "name": "Professional",
        "max_properties": 25,
        "monthly_price": 79.00,
        "setup_fee": 149.00,
        "features": ["Up to 25 properties", "All features"]
    },
}

# Cache for councils data
_councils_cache = None

# Council type suffixes based on council code prefix
# E06 = Unitary Authorities (usually "City Council" or "Borough Council")
# E07 = District Councils
# E08 = Metropolitan Districts
# E09 = London Boroughs
# S12 = Scottish Councils
# W06 = Welsh Councils
# N09 = Northern Ireland

# Councils that should use specific suffixes (exceptions to the standard rules)
COUNCIL_NAME_OVERRIDES = {
    "City of London": "City of London Corporation",
    "Westminster": "City of Westminster",
    "Bristol": "Bristol City Council",
    "Plymouth": "Plymouth City Council",
    "Southampton": "Southampton City Council",
    "Portsmouth": "Portsmouth City Council",
    "Kingston upon Hull": "Kingston upon Hull City Council",
    "Leicester": "Leicester City Council",
    "Nottingham": "Nottingham City Council",
    "Derby": "Derby City Council",
    "York": "City of York Council",
    "Stoke-on-Trent": "Stoke-on-Trent City Council",
    "Peterborough": "Peterborough City Council",
    "Brighton and Hove": "Brighton and Hove City Council",
    "Milton Keynes": "Milton Keynes City Council",
    "Sunderland": "Sunderland City Council",
    "Newcastle upon Tyne": "Newcastle City Council",
    "Manchester": "Manchester City Council",
    "Liverpool": "Liverpool City Council",
    "Leeds": "Leeds City Council",
    "Sheffield": "Sheffield City Council",
    "Birmingham": "Birmingham City Council",
    "Coventry": "Coventry City Council",
    "Wolverhampton": "City of Wolverhampton Council",
    "Bradford": "City of Bradford Metropolitan District Council",
    "Salford": "Salford City Council",
    "Wakefield": "City of Wakefield Metropolitan District Council",
}

def normalize_council_name(name: str, code: str = None) -> str:
    """
    Normalize a council name to its full official format.
    
    This ensures audit-readiness and professional display across all surfaces.
    
    Rules:
    1. Check for explicit overrides first
    2. If already has "Council" suffix, return as-is
    3. Apply suffix based on council code prefix:
       - E09 (London): "London Borough of X" or "X Council"
       - E08 (Metropolitan): "X Metropolitan Borough Council"
       - E07 (District): "X District Council"
       - E06 (Unitary): "X Council" or "X City Council" for cities
       - S12 (Scotland): "X Council"
       - W06 (Wales): "X Council" or "X County Borough Council"
    4. Default: append "Council" if no suffix present
    
    Args:
        name: The raw council name (e.g., "Bristol")
        code: Optional council code for more precise formatting
        
    Returns:
        Full normalized council name (e.g., "Bristol City Council")
    """
    if not name:
        return name
    
    # Check explicit overrides first
    if name in COUNCIL_NAME_OVERRIDES:
        return COUNCIL_NAME_OVERRIDES[name]
    
    # If already has a proper suffix, return as-is
    proper_suffixes = [
        "Council", "Corporation", "Authority", 
        "County Council", "City Council", "Borough Council",
        "District Council", "Metropolitan Borough Council"
    ]
    for suffix in proper_suffixes:
        if name.endswith(suffix):
            return name
    
    # Apply rules based on code prefix if available
    if code:
        if code.startswith("E09"):  # London Boroughs
            # Most London boroughs use "London Borough of X" or "X Council"
            if name not in ["City of London", "Westminster"]:
                return f"London Borough of {name}"
        elif code.startswith("E08"):  # Metropolitan Districts
            return f"{name} Metropolitan Borough Council"
        elif code.startswith("E07"):  # District Councils
            return f"{name} District Council"
        elif code.startswith("S12"):  # Scottish Councils
            return f"{name} Council"
        elif code.startswith("W06"):  # Welsh Councils
            # Some Welsh councils are "County Borough Council", others are just "Council"
            return f"{name} Council"
    
    # Default: append "Council" 
    return f"{name} Council"


# District to Council mapping (common mappings)
DISTRICT_TO_COUNCIL = {
    # London Boroughs
    "Westminster": "Westminster",
    "Camden": "Camden",
    "Islington": "Islington",
    "Hackney": "Hackney",
    "Tower Hamlets": "Tower Hamlets",
    "Greenwich": "Greenwich",
    "Lewisham": "Lewisham",
    "Southwark": "Southwark",
    "Lambeth": "Lambeth",
    "Wandsworth": "Wandsworth",
    "Hammersmith and Fulham": "Hammersmith and Fulham",
    "Kensington and Chelsea": "Kensington and Chelsea",
    "City of London": "City of London",
    "Barking and Dagenham": "Barking and Dagenham",
    "Barnet": "Barnet",
    "Bexley": "Bexley",
    "Brent": "Brent",
    "Bromley": "Bromley",
    "Croydon": "Croydon",
    "Ealing": "Ealing",
    "Enfield": "Enfield",
    "Haringey": "Haringey",
    "Harrow": "Harrow",
    "Havering": "Havering",
    "Hillingdon": "Hillingdon",
    "Hounslow": "Hounslow",
    "Kingston upon Thames": "Kingston upon Thames",
    "Merton": "Merton",
    "Newham": "Newham",
    "Redbridge": "Redbridge",
    "Richmond upon Thames": "Richmond upon Thames",
    "Sutton": "Sutton",
    "Waltham Forest": "Waltham Forest",
}


def _load_councils():
    """Load and cache UK councils data."""
    global _councils_cache
    if _councils_cache is None:
        try:
            councils_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                "data", 
                "uk_councils.json"
            )
            with open(councils_path, "r") as f:
                data = json.load(f)
                _councils_cache = data.get("councils", [])
                logger.info(f"Loaded {len(_councils_cache)} UK councils")
        except Exception as e:
            logger.error(f"Failed to load councils data: {e}")
            _councils_cache = []
    return _councils_cache


@router.get("/plans")
async def get_plans(request: Request):
    """Get available billing plans with property limits and features.
    
    Returns the new plan structure:
    - PLAN_1_SOLO: 2 properties, £19/mo, £49 setup
    - PLAN_2_PORTFOLIO: 10 properties, £39/mo, £79 setup
    - PLAN_3_PRO: 25 properties, £79/mo, £149 setup
    
    When Stripe price env vars are missing, still returns plans (with null stripe IDs).
    Checkout will fail with 400 STRIPE_MODE_MISMATCH until env is configured.
    """
    request_id = str(uuid.uuid4())
    all_plans = plan_registry.get_all_plans(_request_id=request_id)

    invite_code = (request.query_params.get("invite_code") or request.query_params.get("invite") or "").strip()
    plan_code = (request.query_params.get("plan_code") or request.query_params.get("plan") or "").strip()
    email = (request.query_params.get("email") or "").strip() or None
    invite_entry_channel = (request.query_params.get("invite_entry_channel") or "manual").strip().lower()
    if invite_entry_channel not in ("manual", "link"):
        invite_entry_channel = "manual"

    pilot_ctx = None
    if invite_code and plan_code:
        try:
            from services.pilot_invite_service import validate_invite_for_checkout

            invite_doc, _ = await validate_invite_for_checkout(
                code=invite_code,
                plan_code=plan_code,
                email=email,
                for_checkout=False,
                entry_channel=invite_entry_channel,
                log_audit=False,
                record_attempts=False,
            )
            from services.pilot_commercial_truth import commercial_context_from_invite

            pilot_ctx = commercial_context_from_invite(invite_doc, plan_code=plan_code)
        except Exception:
            pilot_ctx = None

    from services.pilot_commercial_truth import intake_plan_pricing_overlay

    plans = []
    for plan in all_plans:
        row = {
            "plan_id": plan["code"],
            "name": plan["name"],
            "display_name": plan.get("display_name", plan["name"]),
            "max_properties": plan["max_properties"],
            "monthly_price": plan["monthly_price"],
            "setup_fee": plan["onboarding_fee"],
            "total_first_payment": plan["monthly_price"] + plan["onboarding_fee"],
            "features": PLAN_DETAILS.get(
                BillingPlan(plan["code"]) if plan["code"] in [e.value for e in BillingPlan] else BillingPlan.PLAN_1_SOLO,
                {}
            ).get("features", []),
            "color": plan.get("color"),
            "badge": plan.get("badge"),
            "is_popular": plan.get("is_popular", False),
        }
        if pilot_ctx and plan["code"] == pilot_ctx.get("plan_code"):
            row = intake_plan_pricing_overlay(row, pilot_ctx)
        plans.append(row)

    return {"plans": plans}


INTAKE_EMAIL_CHECK_RATE_ATTEMPTS = 40
INTAKE_EMAIL_CHECK_RATE_WINDOW_MINUTES = 10


class IntakeEmailCheckBody(BaseModel):
    """Public intake: same email identity rule as POST /submit (clients.email unique)."""

    email: EmailStr


IntakeEmailReasonCode = Literal["OK", "EMAIL_TAKEN"]


class IntakeEmailAvailabilityResponse(BaseModel):
    """Structured result for live intake email availability (UX); submit remains authoritative."""

    available: bool
    normalized_email: str
    reason_code: IntakeEmailReasonCode


@router.post("/check-email", response_model=IntakeEmailAvailabilityResponse)
async def check_intake_email_available(request: Request, body: IntakeEmailCheckBody):
    """Return whether this email can start a new CVP intake (no existing clients row).

    Rate-limited per IP. Intended for step-1 gating before multi-step wizard investment.
    """
    ip = _client_ip_intake(request)
    allowed, rl_msg = await rate_limiter.check_rate_limit(
        f"intake_check_email:{ip}",
        INTAKE_EMAIL_CHECK_RATE_ATTEMPTS,
        INTAKE_EMAIL_CHECK_RATE_WINDOW_MINUTES,
    )
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=rl_msg or "Too many requests.")
    db = database.get_db()
    normalized = canonical_client_email(str(body.email))
    taken = await client_email_taken(db, normalized)
    return IntakeEmailAvailabilityResponse(
        available=not taken,
        normalized_email=normalized,
        reason_code="EMAIL_TAKEN" if taken else "OK",
    )


@router.post("/validate-property-count")
async def validate_property_count(request: Request):
    """Validate property count against plan limit.
    
    INTAKE-LEVEL GATING: This endpoint MUST be called before adding properties
    in the frontend to enforce plan limits immediately.
    
    Request body:
    - plan_id: The selected plan code
    - property_count: Number of properties being added
    
    Returns:
    - allowed: true if within limit
    - error: message if limit exceeded
    - upgrade_info: details about required upgrade
    """
    body = await request.json()
    plan_id = body.get("plan_id", "PLAN_1_SOLO")
    property_count = body.get("property_count", 1)
    
    try:
        # Resolve plan code
        try:
            plan_code = PlanCode(plan_id)
        except ValueError:
            # Handle legacy codes
            legacy_mapping = {
                "PLAN_1": PlanCode.PLAN_1_SOLO,
                "PLAN_2_5": PlanCode.PLAN_2_PORTFOLIO,
                "PLAN_6_15": PlanCode.PLAN_3_PRO,
            }
            plan_code = legacy_mapping.get(plan_id, PlanCode.PLAN_1_SOLO)
        
        # Check property limit using plan_registry
        is_allowed, error_msg, error_details = plan_registry.check_property_limit(
            plan_code,
            property_count
        )
        
        if not is_allowed:
            return {
                "allowed": False,
                "error": error_msg,
                "error_code": error_details.get("error_code"),
                "current_limit": error_details.get("current_limit"),
                "requested_count": property_count,
                "upgrade_required": True,
                "upgrade_to": error_details.get("upgrade_to"),
                "upgrade_to_name": error_details.get("upgrade_to_name"),
                "upgrade_to_limit": error_details.get("upgrade_to_limit"),
            }
        
        return {
            "allowed": True,
            "plan": plan_code.value,
            "max_properties": plan_registry.get_property_limit(plan_code),
            "current_count": property_count,
        }
    
    except Exception as e:
        logger.error(f"Property count validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate property count"
        )


@router.get("/councils")
async def search_councils(
    q: Optional[str] = None,
    nation: Optional[str] = None,
    page: int = 1,
    limit: int = 50
):
    """Search UK councils with pagination.
    
    Query params:
    - q: Search term (partial match on name)
    - nation: Filter by nation (England, Wales, Scotland, Northern Ireland)
    - page: Page number (default 1)
    - limit: Results per page (default 50, max 100)
    """
    councils = _load_councils()
    
    # Filter by search term
    if q:
        q_lower = q.lower()
        councils = [c for c in councils if q_lower in c["name"].lower()]
    
    # Filter by nation
    if nation:
        nation_lower = nation.lower()
        councils = [c for c in councils if c.get("nation", "").lower() == nation_lower]
    
    # Pagination
    limit = min(limit, 100)
    total = len(councils)
    start = (page - 1) * limit
    end = start + limit
    paginated = councils[start:end]
    
    # Normalize council names in the response
    normalized_councils = [
        {
            **c,
            "name": normalize_council_name(c["name"], c.get("code")),
            "raw_name": c["name"]  # Keep original for reference
        }
        for c in paginated
    ]
    
    return {
        "councils": normalized_councils,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit
    }


@router.get("/postcode-autocomplete")
async def autocomplete_postcode(q: str):
    """Autocomplete UK postcodes as user types.
    
    Uses postcodes.io free API - no API key required.
    Returns up to 10 matching postcodes with their locations.
    """
    import httpx
    
    if not q or len(q) < 2:
        return {"postcodes": []}
    
    # Clean query
    clean_query = q.strip().upper()
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://api.postcodes.io/postcodes",
                params={"q": clean_query, "limit": 10}
            )
            
            if response.status_code != 200:
                return {"postcodes": []}
            
            data = response.json()
            
            if data.get("status") != 200 or not data.get("result"):
                return {"postcodes": []}
            
            # Format results
            postcodes = []
            for item in data["result"][:10]:
                outcode = item.get("outcode")
                incode = item.get("incode")
                pc = item.get("postcode")
                if not pc and outcode and incode:
                    pc = f"{outcode} {incode}".strip()
                elif not pc and outcode:
                    pc = str(outcode).strip()
                postcodes.append({
                    "postcode": pc,
                    "outcode": outcode,
                    "incode": incode,
                    "admin_district": item.get("admin_district"),
                    "post_town": item.get("post_town") or item.get("admin_district"),
                    "region": item.get("region"),
                    "country": item.get("country"),
                })
            
            return {"postcodes": postcodes}
    
    except Exception as e:
        logger.error(f"Postcode autocomplete error: {e}")
        return {"postcodes": []}


@router.get("/postcode-lookup/{postcode}")
async def lookup_postcode(postcode: str):
    """Lookup UK postcode using postcodes.io API.
    
    Returns address data including:
    - Formatted addresses (if available)
    - Admin district (council)
    - Post town (city)
    - Region
    - Country
    
    This endpoint proxies to postcodes.io to avoid CORS issues.
    """
    import httpx
    
    # Clean and validate postcode format
    clean_postcode = postcode.strip().upper().replace(" ", "")
    
    if len(clean_postcode) < 5 or len(clean_postcode) > 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid postcode format"
        )
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Lookup postcode via postcodes.io
            response = await client.get(
                f"https://api.postcodes.io/postcodes/{clean_postcode}"
            )
            
            if response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Postcode not found"
                )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Postcode lookup service unavailable"
                )
            
            data = response.json()
            
            if data.get("status") != 200 or not data.get("result"):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Postcode not found"
                )
            
            result = data["result"]
            
            # Extract relevant fields
            admin_district = result.get("admin_district", "")
            post_town = result.get("post_town", "") or result.get("admin_district", "")
            region = result.get("region", "")
            country = result.get("country", "")
            parish = result.get("parish", "")
            
            # Try to match council from our database
            councils = _load_councils()
            matched_council = None
            matched_council_code = None
            
            # First try exact match on admin_district
            for council in councils:
                if council["name"].lower() == admin_district.lower():
                    matched_council = council["name"]
                    matched_council_code = council["code"]
                    break
            
            # If no exact match, try partial match
            if not matched_council and admin_district:
                for council in councils:
                    if admin_district.lower() in council["name"].lower() or council["name"].lower() in admin_district.lower():
                        matched_council = council["name"]
                        matched_council_code = council["code"]
                        break
            
            # Check DISTRICT_TO_COUNCIL mapping
            if not matched_council and admin_district in DISTRICT_TO_COUNCIL:
                mapped_name = DISTRICT_TO_COUNCIL[admin_district]
                for council in councils:
                    if council["name"] == mapped_name:
                        matched_council = council["name"]
                        matched_council_code = council["code"]
                        break
            
            return {
                "postcode": result.get("postcode", postcode),
                "admin_district": admin_district,
                "post_town": post_town,
                "region": region,
                "country": country,
                "parish": parish,
                "latitude": result.get("latitude"),
                "longitude": result.get("longitude"),
                # Matched council from our database - normalized to full official name
                "council_name": normalize_council_name(matched_council, matched_council_code) if matched_council else None,
                "council_code": matched_council_code,
                # Suggested address (user can edit)
                "suggested_city": post_town or admin_district,
                "suggested_address": None,  # postcodes.io doesn't provide street address
                "note": "Please enter your street address manually"
            }
    
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Postcode lookup timed out"
        )
    except Exception as e:
        logger.error(f"Postcode lookup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to lookup postcode"
        )


class IntakeRequirementsPreviewRequest(BaseModel):
    properties: List[IntakePropertyData]


class IntakeAgreementPreviewBody(BaseModel):
    """Checkout-grade agreement preview: either post-submit (client_id) or wizard payload (intake)."""

    intake_session_id: str = Field(..., min_length=8)
    client_id: Optional[str] = None
    intake: Optional[IntakeFormData] = None
    invite_code: Optional[str] = Field(default=None, max_length=64)
    invite_entry_channel: str = Field(
        default="manual",
        max_length=16,
        description="manual | link — aligns pilot validation with invite URL vs typed code.",
    )

    @field_validator("invite_entry_channel")
    @classmethod
    def _invite_entry_preview(cls, v: Any) -> str:
        e = str(v or "manual").strip().lower()
        return e if e in ("manual", "link") else "manual"

    @model_validator(mode="after")
    def require_intake_or_client(self) -> "IntakeAgreementPreviewBody":
        cid = (self.client_id or "").strip()
        if not cid and self.intake is None:
            raise ValueError("intake is required when client_id is omitted")
        return self


@router.post("/requirements-preview")
async def preview_generated_requirements(body: IntakeRequirementsPreviewRequest):
    """
    Read-only planner preview for intake UX.
    Returns generated requirement summary per property (no persistence, no manual selection).
    """
    from database import database
    from services.compliance_registry_publish_service import fetch_active_published_registry_entries
    from services.compliance_requirement_registry import build_requirement_plan_for_property
    from services.requirement_action_resolver import infer_action_type
    from presentation.property_display_name import get_property_display_name

    db = database.get_db()
    published = await fetch_active_published_registry_entries(db)

    summaries = []
    for idx, prop in enumerate(body.properties or []):
        p = prop.model_dump()
        jur = canonicalize_uk_portfolio_label(p.get("jurisdiction"))
        if not jur:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Property {idx + 1}: jurisdiction must be Scotland, England, Wales, or Northern Ireland",
            )
        p["jurisdiction"] = jur
        plan = build_requirement_plan_for_property(p, {}, published_registry_entries=published)
        action_type_counts: Dict[str, int] = {}
        for item in plan:
            action = infer_action_type({"compliance_requirement_class": item.compliance_requirement_class}) or "UNKNOWN"
            action_type_counts[action] = int(action_type_counts.get(action, 0)) + 1
        summaries.append(
            {
                "property_index": idx,
                "property_display_name": get_property_display_name(p),
                "property_nickname": p.get("nickname") or f"Property {idx + 1}",
                "jurisdiction": jur,
                "friendly_property_type": str(p.get("property_type") or "").replace("_", " ").title() or "Property",
                "likely_obligations": [str(i.description) for i in plan[:6]],
                "key_driver_facts": {
                    "property_type": p.get("property_type"),
                    "is_hmo": p.get("is_hmo"),
                    "has_gas_supply": p.get("has_gas_supply"),
                    "tenancy_active": p.get("tenancy_active"),
                    "deposit_taken": p.get("deposit_taken"),
                    "furnished": p.get("furnished"),
                    "has_communal_areas": p.get("has_communal_areas"),
                    "local_authority": p.get("council_name"),
                },
                "action_type_breakdown": action_type_counts,
                "top_generated_requirements": [str(i.description) for i in plan[:6]],
                "total_generated_requirements": len(plan),
                "assumptions": {
                    "has_gas_supply_unknown_assumed_true_for_planning": p.get("has_gas_supply") is None,
                },
            }
        )
    return {"properties": summaries}


@router.post("/agreement-preview")
async def intake_agreement_preview(request: Request, body: IntakeAgreementPreviewBody):
    """
    Authoritative agreement preview for intake Step 5 (same render pipeline as acceptance).

    - Without ``client_id``: requires ``intake`` wizard payload bound to ``intake_session_id``.
    - With ``client_id``: loads commercial snapshot from Mongo; ``intake_session_id`` must match the client row.
    """
    from services.agreement_preview_service import build_intake_agreement_preview

    request_id = str(uuid.uuid4())
    ip = get_client_ip(request)
    allowed, rl_msg = await rate_limiter.check_rate_limit(
        f"intake_agreement_preview:{ip or 'unknown'}",
        INTAKE_AGREEMENT_PREVIEW_RATE_ATTEMPTS,
        INTAKE_AGREEMENT_PREVIEW_RATE_WINDOW_MINUTES,
    )
    if not allowed:
        log_rate_limit_event("intake_agreement_preview", ip or "", ip or "")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error_code": "RATE_LIMIT_EXCEEDED", "message": rl_msg or "Too many requests. Try again shortly."},
        )

    cid = (body.client_id or "").strip() or None
    pilot_invite_doc = None
    invite_raw = (body.invite_code or "").strip()
    plan_for_invite = None
    email_for_invite = None
    if body.intake and getattr(body.intake, "billing_plan", None):
        plan_for_invite = body.intake.billing_plan.value if hasattr(body.intake.billing_plan, "value") else str(body.intake.billing_plan)
        email_for_invite = str(getattr(body.intake, "email", "") or "") if body.intake else None
    elif cid and invite_raw:
        client = await database.get_db().clients.find_one(
            {"client_id": cid},
            {"_id": 0, "billing_plan": 1, "contact_email": 1, "email": 1},
        )
        if client:
            plan_for_invite = str(client.get("billing_plan") or "PLAN_1_SOLO")
            email_for_invite = client.get("contact_email") or client.get("email")
    if invite_raw and plan_for_invite:
        try:
            pilot_invite_doc, _ = await validate_invite_for_checkout(
                code=invite_raw,
                plan_code=plan_for_invite,
                email=email_for_invite,
                for_checkout=False,
                entry_channel=body.invite_entry_channel,
                log_audit=False,
                record_attempts=False,
            )
        except PilotInvitePublicError:
            pilot_invite_doc = None
    try:
        payload, err, v_errs = await build_intake_agreement_preview(
            intake_session_id=body.intake_session_id,
            client_id=cid,
            intake=body.intake,
            pilot_invite_doc=pilot_invite_doc,
        )
    except Exception as exc:
        logger.exception(
            "Agreement preview failed request_id=%s client_id=%s invite_present=%s: %s",
            request_id,
            cid,
            bool(invite_raw),
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "AGREEMENT_PREVIEW_FAILED",
                "message": "Could not load the service agreement preview. Please retry or contact support.",
                "request_id": request_id,
            },
        )
    if err == "AGREEMENT_NOT_CONFIGURED":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": err, "message": "No published agreement is available yet.", "request_id": request_id},
        )
    if err == "CLIENT_NOT_FOUND":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error_code": err, "request_id": request_id})
    if err == "INTAKE_SESSION_INVALID":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": err,
                "message": "Agreement preview does not match this registration session.",
                "request_id": request_id,
            },
        )
    if err == "INTAKE_BODY_REQUIRED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": err, "message": "intake payload is required when client_id is omitted.", "request_id": request_id},
        )
    if err == "AGREEMENT_RENDER_INVALID":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": err,
                "message": "Agreement could not be rendered with the information provided.",
                "validation_issues": v_errs or [],
                "request_id": request_id,
            },
        )
    if err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": err, "request_id": request_id})
    return payload


@router.post("/submit")
async def submit_intake(request: Request, data: IntakeFormData):
    """Universal intake wizard submission.
    
    INTAKE-LEVEL GATING ENFORCED:
    - Property count MUST NOT exceed plan limit
    - This is the PRIMARY line of defense
    - No soft gates or bypasses
    
    Validates:
    - Required conditional fields (company_name, phone)
    - Plan-based property limits (NON-NEGOTIABLE)
    - Required consents
    
    Creates:
    - Client record with customer_reference
    - Property records with full metadata
    - Audit log entries
    
    Returns client_id for checkout.
    """
    db = database.get_db()
    
    try:
        # =========== VALIDATION ===========
        
        # Check if client already exists (same rule as POST /check-email)
        if await client_email_taken(db, str(data.email)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=INTAKE_EMAIL_ALREADY_EXISTS_MESSAGE,
            )
        
        # Validate conditional fields
        if data.client_type in [ClientType.COMPANY, ClientType.AGENT]:
            if not data.company_name or not data.company_name.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Company name is required for Property Companies and Letting Agents"
                )
        
        if data.preferred_contact in [PreferredContact.SMS, PreferredContact.BOTH]:
            if not data.phone or not data.phone.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phone number is required when SMS notifications are enabled"
                )
        
        # =========== PROPERTY LIMIT ENFORCEMENT (NON-NEGOTIABLE) ===========
        # Resolve plan code
        plan_str = data.billing_plan.value
        try:
            plan_code = PlanCode(plan_str)
        except ValueError:
            # Handle legacy codes
            legacy_mapping = {
                "PLAN_1": PlanCode.PLAN_1_SOLO,
                "PLAN_2_5": PlanCode.PLAN_2_PORTFOLIO,
                "PLAN_6_15": PlanCode.PLAN_3_PRO,
            }
            plan_code = legacy_mapping.get(plan_str, PlanCode.PLAN_1_SOLO)
        
        # Check property limit using plan_registry
        is_allowed, error_msg, error_details = plan_registry.check_property_limit(
            plan_code,
            len(data.properties)
        )
        
        if not is_allowed:
            # Log the blocked attempt (API bypass / server-side enforcement)
            logger.warning(
                f"Intake property limit exceeded: email={data.email}, "
                f"plan={plan_str}, requested={len(data.properties)}, "
                f"limit={error_details.get('current_limit')}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "PROPERTY_LIMIT_EXCEEDED",
                    "message": error_msg,
                    "current_limit": error_details.get("current_limit"),
                    "requested_count": len(data.properties),
                    "upgrade_required": True,
                    "upgrade_to": error_details.get("upgrade_to"),
                    "upgrade_to_name": error_details.get("upgrade_to_name"),
                },
            )
        
        if not data.properties or len(data.properties) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one property is required"
            )
        
        # Validate required consents
        if not data.consent_data_processing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GDPR data processing consent is required"
            )
        
        if not data.consent_service_boundary:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Service boundary acknowledgment is required"
            )
        
        # Validate email upload consent if method is EMAIL
        if data.document_submission_method == "EMAIL" and not data.email_upload_consent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Consent to email document upload is required when choosing to email documents"
            )
        
        # Validate property agent details when reminders include agent
        for i, prop in enumerate(data.properties):
            if prop.send_reminders_to in ["AGENT", "BOTH"]:
                if not prop.agent_name or not prop.agent_email:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Property {i + 1}: Agent name and email are required when sending reminders to agent"
                    )
        
        # =========== CREATE CLIENT ===========
        # Assign CRN before insert so customer_reference is never null (concurrency-safe via atomic counter).
        crn = await get_next_crn()
        intake_email = canonical_client_email(str(data.email))
        client = Client(
            customer_reference=crn,
            full_name=data.full_name,
            email=intake_email,
            phone=data.phone if data.phone else None,
            company_name=data.company_name if data.company_name else None,
            client_type=data.client_type,
            preferred_contact=data.preferred_contact,
            billing_plan=data.billing_plan,
            service_code=ServiceCode.VAULT_PRO,
            document_submission_method=data.document_submission_method,
            email_upload_consent=data.email_upload_consent,
            intake_session_id=data.intake_session_id,
            consent_data_processing=data.consent_data_processing,
            consent_service_boundary=data.consent_service_boundary
        )
        
        client_doc = client.model_dump()
        client_doc["onboarding_identity_status"] = ONBOARDING_IDENTITY_ACTIVE
        released_prior = await find_latest_released_attempt_for_email(db, intake_email)
        if released_prior and released_prior.get("client_id"):
            client_doc["restarted_from_client_id"] = released_prior["client_id"]
        for key in ["created_at", "updated_at"]:
            if client_doc.get(key):
                client_doc[key] = client_doc[key].isoformat()
        if getattr(data, "schema_version", None):
            client_doc["intake_schema_version"] = (data.schema_version or "")[:32]
        lead_id_val = getattr(data, "lead_id", None)
        if lead_id_val and (lead_id_val or "").strip():
            src = (getattr(data, "source", None) or "risk-check")
            client_doc["marketing"] = {
                "source": (str(src)).strip()[:64] if src else "risk-check",
                "lead_id": (lead_id_val or "").strip()[:128],
            }
        
        # Account-level jurisdiction: mirror intake property selections (union + default = first property).
        from services.compliance_rules_registry import derive_account_jurisdiction_fields_from_property_labels

        _dj, _ej = derive_account_jurisdiction_fields_from_property_labels([p.jurisdiction for p in data.properties])
        if _dj and _ej:
            client_doc["default_jurisdiction"] = _dj
            client_doc["enabled_jurisdictions"] = _ej

        try:
            await db.clients.insert_one(client_doc)
        except DuplicateKeyError as dup_err:
            kind = classify_clients_duplicate_key_error(dup_err)
            if kind == "email":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=INTAKE_EMAIL_ALREADY_EXISTS_MESSAGE,
                ) from dup_err
            if kind in ("customer_reference", "client_id", "other"):
                logger.warning(
                    "Intake clients.insert_one duplicate key (non-email kind=%s): %s",
                    kind,
                    dup_err,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Could not complete signup due to a conflict; please try again.",
                ) from dup_err
            raise
        try:
            from services.client_lifecycle_service import persist_operational_client_lifecycle_if_needed

            await persist_operational_client_lifecycle_if_needed(db, client.client_id)
        except Exception as lc_err:
            logger.warning(
                "persist client lifecycle after intake insert failed client_id=%s: %s",
                client.client_id,
                lc_err,
            )

        # Link risk-check lead to client (best-effort; do not block intake)
        if lead_id_val and (lead_id_val or "").strip():
            try:
                await db.risk_leads.update_one(
                    {"lead_id": (lead_id_val or "").strip()},
                    {"$set": {"status": "checkout_created", "client_id": client.client_id, "updated_at": datetime.now(timezone.utc).isoformat()}},
                )
            except Exception as link_err:
                logger.warning("Risk lead link after intake failed lead_id=%s: %s", lead_id_val, link_err)
        
        # =========== CREATE PROPERTIES ===========
        
        property_temp_key_map = {}  # Map temp_key to property_id for document reconciliation
        
        for i, prop_data in enumerate(data.properties):
            prop_jurisdiction = canonicalize_uk_portfolio_label(prop_data.jurisdiction)
            if not prop_jurisdiction:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Property {i + 1}: jurisdiction must be Scotland, England, Wales, or Northern Ireland",
                )
            # Determine HMO license requirement based on is_hmo and licence_required
            hmo_license_required = (
                prop_data.is_hmo and 
                prop_data.licence_required == "YES"
            )
            
            prop = Property(
                client_id=client.client_id,
                nickname=prop_data.nickname or f"Property {i + 1}",
                address_line_1=prop_data.address_line_1,
                address_line_2=prop_data.address_line_2,
                city=prop_data.city,
                postcode=prop_data.postcode,
                property_type=prop_data.property_type,
                bedrooms=prop_data.bedrooms,
                occupancy=prop_data.occupancy,
                jurisdiction=prop_jurisdiction,
                is_hmo=prop_data.is_hmo,
                hmo_license_required=hmo_license_required,
                has_gas_supply=prop_data.has_gas_supply,
                tenancy_active=prop_data.tenancy_active,
                deposit_taken=prop_data.deposit_taken,
                furnished=prop_data.furnished,
                has_communal_areas=prop_data.has_communal_areas,
                # Normalize council name to full official format for audit-readiness
                local_authority=normalize_council_name(prop_data.council_name, prop_data.council_code) if prop_data.council_name else None,
                local_authority_code=prop_data.council_code,
                licence_required=prop_data.licence_required,
                licence_type=prop_data.licence_type,
                licence_status=prop_data.licence_status,
                managed_by=prop_data.managed_by,
                send_reminders_to=prop_data.send_reminders_to,
                agent_name=prop_data.agent_name,
                agent_email=prop_data.agent_email,
                agent_phone=prop_data.agent_phone,
                cert_gas_safety=prop_data.cert_gas_safety,
                cert_eicr=prop_data.cert_eicr,
                cert_epc=prop_data.cert_epc,
                cert_licence=prop_data.cert_licence
            )
            
            prop_doc = prop.model_dump()
            for key in ["created_at", "updated_at"]:
                if prop_doc.get(key):
                    prop_doc[key] = prop_doc[key].isoformat()
            
            await db.properties.insert_one(prop_doc)
            
            # Store mapping for document reconciliation
            if data.intake_session_id:
                temp_key = f"{data.intake_session_id}_property_{i}"
                property_temp_key_map[temp_key] = prop.property_id
            
            # Audit log for each property
            await create_audit_log(
                action=AuditAction.INTAKE_PROPERTY_ADDED,
                client_id=client.client_id,
                resource_type="property",
                resource_id=prop.property_id,
                metadata={
                    "address": f"{prop_data.address_line_1}, {prop_data.city}",
                    "is_hmo": prop_data.is_hmo,
                    "council": normalize_council_name(prop_data.council_name, prop_data.council_code) if prop_data.council_name else None,
                    "certificates": {
                        "gas": prop_data.cert_gas_safety,
                        "eicr": prop_data.cert_eicr,
                        "epc": prop_data.cert_epc,
                        "licence": prop_data.cert_licence
                    }
                }
            )
        
        # =========== RECONCILE UPLOADED DOCUMENTS ===========
        
        if data.intake_session_id:
            # Link any documents uploaded during intake to the created properties
            await _reconcile_intake_documents(
                db, 
                client.client_id, 
                data.intake_session_id,
                property_temp_key_map
            )
        
        # =========== AUDIT LOG ===========
        
        await create_audit_log(
            action=AuditAction.INTAKE_SUBMITTED,
            client_id=client.client_id,
            metadata={
                "email": data.email,
                "properties_count": len(data.properties),
                "billing_plan": data.billing_plan.value,
                "document_submission_method": data.document_submission_method,
                "schema_version": getattr(data, "schema_version", None),
            }
        )
        
        try:
            from services.analytics_service import log_event
            await log_event("intake_submitted", {
                "client_id": client.client_id,
                "customer_reference": crn,
                "email": data.email,
                "plan_code": data.billing_plan.value,
                "properties_count": len(data.properties),
            })
        except Exception:
            pass
        
        # =========== ENABLEMENT EVENT ===========
        try:
            from services.enablement_service import emit_enablement_event
            from models.enablement import EnablementEventType
            await emit_enablement_event(
                event_type=EnablementEventType.CLIENT_INTAKE_COMPLETED,
                client_id=client.client_id,
                plan_code=data.billing_plan.value,
                context_payload={
                    "email": data.email,
                    "properties_count": len(data.properties)
                }
            )
        except Exception as enable_err:
            logger.warning(f"Failed to emit enablement event: {enable_err}")
        
        logger.info(f"Intake submitted for {data.email}, client_id: {client.client_id}")
        
        return {
            "message": "Intake submitted successfully",
            "client_id": client.client_id,
            "customer_reference": crn,
            "intake_session_id": data.intake_session_id,
            "next_step": "checkout",
        }
    
    except HTTPException:
        raise
    except Exception as e:
        request_id = str(uuid.uuid4())
        exc_type = type(e).__name__
        exc_msg = str(e) or "(no message)"
        logger.error(
            "Intake submission error request_id=%s exc_type=%s exc_msg=%s",
            request_id,
            exc_type,
            exc_msg,
        )
        logger.exception("Intake submission full traceback request_id=%s", request_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Failed to process intake. Please try again or contact support.",
                "error_code": "SUBMIT_FAILED",
                "request_id": request_id,
            },
        )


async def _reconcile_intake_documents(db, client_id: str, session_id: str, property_map: dict):
    """Link documents uploaded during intake to their actual property IDs.
    Copies files into the document vault (DOCUMENT_STORAGE_PATH) so viewing works after login,
    and enqueues AI extraction so Apply can be used like Path B (intake_uploads) documents.
    """
    try:
        documents = await db.documents.find({
            "intake_session_id": session_id,
            "source": "INTAKE_UPLOAD"
        }).to_list(100)

        DOCUMENT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
        dest_dir = DOCUMENT_STORAGE_PATH / client_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        for doc in documents:
            property_temp_key = doc.get("property_temp_key")
            if property_temp_key and property_temp_key in property_map:
                actual_property_id = property_map[property_temp_key]

                from services.requirement_evidence_authority import normalize_document_evidence_scope

                prop_scope = normalize_document_evidence_scope(
                    property_id=actual_property_id,
                    client_id=client_id,
                    evidence_scope_type="PROPERTY",
                )
                await db.documents.update_one(
                    {"document_id": doc["document_id"]},
                    {
                        "$set": {
                            "client_id": client_id,
                            "property_temp_key": None,
                            **prop_scope,
                        }
                    }
                )
                logger.info(f"Reconciled document {doc['document_id']} to property {actual_property_id}")

                # Copy file into vault so GET /documents/{id}/file works after login
                old_path = doc.get("file_path")
                if old_path and os.path.isfile(old_path):
                    try:
                        ext = (Path(old_path).suffix or Path(doc.get("file_name", "")).suffix or "").strip().lower()
                        if not ext or "/" in ext or "\\" in ext or len(ext) > 12:
                            ext = ".bin"
                        unique_name = f"{uuid.uuid4().hex}{ext}"
                        dest_path = dest_dir / unique_name
                        shutil.copy2(old_path, dest_path)
                        file_size = os.path.getsize(dest_path)
                        # Store relative vault key (same convention as portal uploads) so GET /documents/{id}/file
                        # survives DOCUMENT_STORAGE_PATH / volume changes and matches _resolve_document_file_path.
                        stored_rel = f"{client_id}/{unique_name}"
                        await db.documents.update_one(
                            {"document_id": doc["document_id"]},
                            {"$set": {"file_path": stored_rel, "file_size": file_size}}
                        )
                        logger.info(f"Copied intake document {doc['document_id']} to vault at {dest_path} (db file_path={stored_rel})")
                    except Exception as copy_err:
                        logger.warning("Intake doc vault copy failed document_id=%s: %s", doc["document_id"], copy_err)

                # Enqueue extraction so user can Apply after login (same as Path B)
                try:
                    from services.document_extraction_service import enqueue_extraction
                    await enqueue_extraction(
                        document_id=doc["document_id"],
                        client_id=client_id,
                        source="intake_upload",
                        property_id=actual_property_id,
                        intake_session_id=session_id,
                    )
                except Exception as ext_err:
                    logger.warning("Enqueue extraction after intake reconcile failed document_id=%s: %s", doc["document_id"], ext_err)

    except Exception as e:
        logger.error(f"Document reconciliation error: {e}")


@router.post("/upload-document")
async def upload_intake_document(
    file: UploadFile = File(...),
    intake_session_id: str = Form(...),
    property_index: int = Form(...),
    document_type: Optional[str] = Form(None)
):
    """Upload a document during intake (non-blocking).
    
    Documents are stored with UNVERIFIED status and source=INTAKE_UPLOAD.
    They will be reconciled to actual property IDs after intake submission.
    """
    db = database.get_db()
    
    try:
        # Validate file type
        allowed_types = ["application/pdf", "image/jpeg", "image/png", "image/jpg"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF, JPG, and PNG files are allowed"
            )
        
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Check file size (max 10MB)
        if file_size > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size must be under 10MB"
            )
        
        # Generate storage path
        document_id = str(uuid.uuid4())
        storage_dir = resolve_intake_upload_dir() / intake_session_id
        storage_dir.mkdir(parents=True, exist_ok=True)

        file_ext = os.path.splitext(file.filename)[1] if file.filename else ".pdf"
        file_path = storage_dir / f"{document_id}{file_ext}"
        
        # Save file
        with open(str(file_path), "wb") as f:
            f.write(content)
        
        from services.requirement_evidence_authority import normalize_document_evidence_scope

        scope_fields = normalize_document_evidence_scope(
            property_id=None,
            client_id="",
            evidence_scope_type="INTAKE_STAGING",
            intake_session_id=intake_session_id,
        )
        # Create document record (UNVERIFIED, source=INTAKE_UPLOAD)
        doc_record = {
            "document_id": document_id,
            "client_id": None,  # Will be set after intake submission
            "property_temp_key": f"{intake_session_id}_property_{property_index}",
            "intake_session_id": intake_session_id,
            "source": "INTAKE_UPLOAD",
            "file_name": file.filename,
            "file_path": str(file_path),
            "file_size": file_size,
            "mime_type": file.content_type,
            "status": DocumentStatus.PENDING.value,
            "verification_state": "UNVERIFIED",
            "document_type_hint": document_type,
            "uploaded_by": "INTAKE_WIZARD",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            # AI extraction fields (to be populated after provisioning)
            "ai_extracted_data": None,
            "suggested_issue_date": None,
            "suggested_expiry_date": None,
            "suggested_certificate_number": None,
            "extraction_confidence": None,
            "manual_review_flag": True,  # Always require review for intake uploads
            **scope_fields,
        }
        from services.evidence_document_match_engine import (
            evaluate_document_requirement_match,
            match_evaluation_to_persisted_document_fields,
        )
        from services.evidence_document_taxonomy import EVIDENCE_MATCH_LEGACY_STATE_UNCLASSIFIED_PRE_ENGINE

        _mev = evaluate_document_requirement_match(
            requirement=None,
            filename=file.filename or "",
            user_declared_document_type=document_type,
            extracted_data=None,
            upload_route_context="intake_wizard_upload",
        )
        doc_record.update(match_evaluation_to_persisted_document_fields(_mev))
        doc_record["evidence_match_legacy_state"] = EVIDENCE_MATCH_LEGACY_STATE_UNCLASSIFIED_PRE_ENGINE

        await db.documents.insert_one(doc_record)
        
        logger.info(f"Intake document uploaded: {document_id} for session {intake_session_id}")
        
        return {
            "message": "Document uploaded successfully",
            "document_id": document_id,
            "file_name": file.filename,
            "file_size": file_size
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Intake document upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )


def _checkout_error_detail(error_code: str, message: str, request_id: str) -> dict:
    """Structured error detail for checkout responses (error_code, message, request_id)."""
    return {"error_code": error_code, "message": message, "request_id": request_id}


_PILOT_INVITE_HTTP_STATUS = {
    "PILOT_INVITE_INVALID": status.HTTP_400_BAD_REQUEST,
    "PILOT_INVITE_EXPIRED": status.HTTP_400_BAD_REQUEST,
    "PILOT_INVITE_EXHAUSTED": status.HTTP_400_BAD_REQUEST,
    "PILOT_INVITE_PLAN_NOT_ELIGIBLE": status.HTTP_400_BAD_REQUEST,
    "PILOT_INVITE_EMAIL_NOT_ELIGIBLE": status.HTTP_400_BAD_REQUEST,
    "PILOT_INVITE_MISCONFIGURED": status.HTTP_503_SERVICE_UNAVAILABLE,
    "PILOT_ONBOARDING_DEFERRED_NOT_AVAILABLE": status.HTTP_400_BAD_REQUEST,
    "PILOT_INVITE_PUBLIC_ENTRY_DISABLED": status.HTTP_400_BAD_REQUEST,
    "PILOT_INVITE_CAMPAIGN_INACTIVE": status.HTTP_400_BAD_REQUEST,
    "PILOT_INVITE_CAMPAIGN_PAUSED": status.HTTP_400_BAD_REQUEST,
    "PILOT_INVITE_NOT_FIRST_TIME_CUSTOMER": status.HTTP_400_BAD_REQUEST,
    "PILOT_INVITE_EMAIL_DOMAIN_NOT_ALLOWED": status.HTTP_400_BAD_REQUEST,
    "PILOT_INVITE_ALREADY_REDEEMED_EMAIL": status.HTTP_400_BAD_REQUEST,
    "PILOT_INVITE_ALREADY_REDEEMED_CUSTOMER": status.HTTP_400_BAD_REQUEST,
    "PILOT_INVITE_ALREADY_REDEEMED_PAYMENT_METHOD": status.HTTP_400_BAD_REQUEST,
    "PILOT_INVITE_DAILY_LIMIT_EXCEEDED": status.HTTP_400_BAD_REQUEST,
}


@router.post("/pilot-invite/validate", response_model=PilotInviteValidateResponse)
async def validate_pilot_invite(body: PilotInviteValidateBody):
    """
    Validate a founding pilot invite code before checkout (no Stripe IDs exposed).
    Returns valid=false with a safe message when invalid; does not reveal internal config.
    """
    try:
        _, resp = await validate_invite_for_checkout(
            code=body.code,
            plan_code=body.plan_code,
            email=body.email,
            for_checkout=False,
            entry_channel=body.entry_channel,
        )
        return resp
    except PilotInvitePublicError as e:
        return PilotInviteValidateResponse(
            valid=False,
            message=e.message,
            program_type=None,
            plan_code=body.plan_code,
            discount_applied=False,
        )


@router.post("/checkout")
async def create_checkout(request: Request, client_id: str, checkout_body: IntakeCheckoutBody = Body(...)):
    """Create Stripe checkout session for intake payment.
    Returns checkout_url for redirect; no entitlement is granted until Stripe payment succeeds.
    Requires a valid agreement acceptance (see POST /api/public/agreements/acceptance).
    All error responses include error_code, message, and request_id for correlation.
    """
    request_id = str(uuid.uuid4())
    db = database.get_db()
    try:
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "billing_plan": 1, "email": 1, "contact_email": 1, "marketing": 1},
        )
        if not client:
            logger.warning("Checkout client not found client_id=%s request_id=%s", client_id, request_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_checkout_error_detail("CLIENT_NOT_FOUND", "Client not found", request_id),
            )
        origin = (request.headers.get("origin") or os.getenv("FRONTEND_ORIGIN") or "").strip() or "http://localhost:3000"
        base = origin.rstrip("/")
        if not base.startswith("http://") and not base.startswith("https://"):
            logger.warning("Checkout invalid origin request_id=%s origin=%r", request_id, origin or "(empty)")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_checkout_error_detail(
                    "CHECKOUT_FAILED",
                    "Invalid redirect URL: set Origin header or FRONTEND_ORIGIN env to a valid http(s) base URL.",
                    request_id,
                ),
            )
        origin = base
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role="SYSTEM",
            client_id=client_id,
            metadata={
                "action_type": "INTAKE_CHECKOUT_SESSION_REQUESTED",
                "target_plan": client.get("billing_plan"),
                "source": "intake_checkout",
                "request_id": request_id,
            },
        )
        plan_code = client.get("billing_plan") or "PLAN_1_SOLO"
        customer_email = client.get("contact_email") or client.get("email")
        lead_id = (client.get("marketing") or {}).get("lead_id") if client.get("marketing") else None

        entry_ch = (checkout_body.invite_entry_channel or "manual").strip().lower()
        if entry_ch not in ("manual", "link"):
            entry_ch = "manual"

        pilot_invite_doc = None
        invite_raw = (checkout_body.invite_code or "").strip()
        if invite_raw:
            try:
                pilot_invite_doc, _pilot_resp = await validate_invite_for_checkout(
                    code=invite_raw,
                    plan_code=plan_code,
                    email=customer_email,
                    for_checkout=True,
                    entry_channel=entry_ch,
                    client_id=client_id,
                )
            except PilotInvitePublicError as e:
                logger.warning(
                    "Pilot invite rejected client_id=%s request_id=%s error_code=%s",
                    client_id,
                    request_id,
                    e.error_code,
                )
                raise HTTPException(
                    status_code=_PILOT_INVITE_HTTP_STATUS.get(e.error_code, status.HTTP_400_BAD_REQUEST),
                    detail=_checkout_error_detail(e.error_code, e.message, request_id),
                )

        acc_doc, acc_err = await validate_acceptance_for_checkout(
            client_id=client_id,
            acceptance_id=checkout_body.acceptance_id.strip(),
            pilot_invite_doc=pilot_invite_doc,
        )
        if acc_err:
            status_map = {
                "ACCEPTANCE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
                "ACCEPTANCE_CLIENT_MISMATCH": status.HTTP_403_FORBIDDEN,
                "ACCEPTANCE_NOT_VALID_FOR_CHECKOUT": status.HTTP_409_CONFLICT,
                "AGREEMENT_VERSION_NOT_PUBLISHED": status.HTTP_503_SERVICE_UNAVAILABLE,
                "AGREEMENT_TEMPLATE_INACTIVE": status.HTTP_503_SERVICE_UNAVAILABLE,
                "ACCEPTANCE_COMMERCIAL_MISMATCH": status.HTTP_409_CONFLICT,
                "ACCEPTANCE_RENDER_INVALID": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "ACCEPTANCE_INTEGRITY_INVALID": status.HTTP_409_CONFLICT,
            }
            st = status_map.get(acc_err, status.HTTP_400_BAD_REQUEST)
            raise HTTPException(
                status_code=st,
                detail=_checkout_error_detail(
                    acc_err,
                    "Agreement acceptance is missing, invalid, or no longer matches your details. Please review and accept again.",
                    request_id,
                ),
            )

        template_id = str(acc_doc.get("template_id") or "")
        template_version_id = str(acc_doc.get("template_version_id") or "")

        session = await stripe_service.create_checkout_session(
            client_id=client_id,
            plan_code=plan_code,
            origin_url=origin,
            customer_email=customer_email,
            lead_id=lead_id,
            customer_reference=client.get("customer_reference"),
            acceptance_id=checkout_body.acceptance_id.strip(),
            agreement_template_id=template_id,
            agreement_template_version_id=template_version_id,
            pilot_invite_doc=pilot_invite_doc,
        )
        url = session.get("checkout_url")
        session_id = session.get("session_id")
        if not url or not (session_id or "").strip():
            if (session_id or "").strip():
                try:
                    await stripe_service.expire_checkout_session(session_id)
                except Exception as exp_err:
                    logger.warning("expire_checkout_session after missing checkout_url failed: %s", exp_err)
            logger.error("Stripe session missing checkout_url for client %s request_id=%s", client_id, request_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=_checkout_error_detail(
                    "CHECKOUT_URL_MISSING",
                    "Payment provider did not return a checkout URL. Please try again.",
                    request_id,
                ),
            )
        try:
            await mark_acceptance_checkout_started(checkout_body.acceptance_id.strip(), session_id)
        except ValueError as acc_link_err:
            logger.error(
                "mark_acceptance_checkout_started failed client_id=%s acceptance_id=%s: %s",
                client_id,
                checkout_body.acceptance_id.strip(),
                acc_link_err,
                exc_info=True,
            )
            try:
                await create_audit_log(
                    action=AuditAction.AGREEMENT_ACCEPTANCE_CHECKOUT_LINK_FAILED,
                    actor_role="SYSTEM",
                    client_id=client_id,
                    resource_type="agreement_acceptance",
                    resource_id=checkout_body.acceptance_id.strip(),
                    metadata={
                        "request_id": request_id,
                        "stripe_checkout_session_id": session_id,
                        "reason": str(acc_link_err),
                    },
                )
            except Exception as audit_err:
                logger.warning("audit log AGREEMENT_ACCEPTANCE_CHECKOUT_LINK_FAILED failed: %s", audit_err)
            try:
                await stripe_service.expire_checkout_session(session_id)
            except Exception as exp_err:
                logger.warning("expire_checkout_session after link failure failed: %s", exp_err)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=_checkout_error_detail(
                    "ACCEPTANCE_CHECKOUT_LINK_FAILED",
                    "Could not link your agreement acceptance to this payment session. Please accept the agreement again and try checkout.",
                    request_id,
                ),
            )
        if lead_id and session_id:
            try:
                await db.risk_leads.update_one(
                    {"lead_id": lead_id},
                    {"$set": {"stripe_session_id": session_id, "updated_at": datetime.now(timezone.utc).isoformat()}},
                )
            except Exception as e:
                logger.warning("Risk lead stripe_session_id update failed lead_id=%s: %s", lead_id, e)
        try:
            from services.analytics_service import log_event
            await log_event("checkout_started", {
                "client_id": client_id,
                "stripe_session_id": session.get("session_id"),
            })
        except Exception:
            pass
        return {
            "checkout_url": url,
            "session_id": session.get("session_id", ""),
        }
    except HTTPException:
        raise
    except StripeModeMismatchError as e:
        logger.warning("Checkout Stripe mode mismatch request_id=%s: %s", request_id, e)
        try:
            from services.analytics_service import log_event
            await log_event("checkout_failed", {"client_id": client_id, "error_code": "STRIPE_MODE_MISMATCH", "request_id": request_id})
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_checkout_error_detail(
                "STRIPE_MODE_MISMATCH",
                str(e) or "Stripe key mode does not match price configuration. Contact support.",
                request_id,
            ),
        )
    except PriceConfigMissingError as e:
        logger.error("Checkout price config missing request_id=%s: %s", request_id, e)
        try:
            from services.analytics_service import log_event
            await log_event("checkout_failed", {"client_id": client_id, "error_code": "PRICE_CONFIG_MISSING", "request_id": request_id})
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_checkout_error_detail(
                "PRICE_CONFIG_MISSING",
                str(e) or "Stripe price configuration is missing. Contact support.",
                request_id,
            ),
        )
    except ValueError as e:
        logger.warning("Checkout validation/Stripe error request_id=%s: %s", request_id, e)
        try:
            from services.analytics_service import log_event
            await log_event("checkout_failed", {"client_id": client_id, "error_code": "CHECKOUT_FAILED", "request_id": request_id})
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_checkout_error_detail(
                "CHECKOUT_FAILED",
                str(e) or "Could not create checkout session. Please try again.",
                request_id,
            ),
        )
    except Exception as e:
        logger.exception("Checkout creation error for client %s request_id=%s: %s", client_id, request_id, e)
        try:
            from services.analytics_service import log_event
            await log_event("checkout_failed", {"client_id": client_id, "error_code": "CHECKOUT_FAILED", "request_id": request_id})
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_checkout_error_detail(
                "CHECKOUT_FAILED",
                "Failed to create checkout session. Please try again or contact support.",
                request_id,
            ),
        )


# Rate limit for unauthenticated onboarding-status (prevent enumeration)
ONBOARDING_STATUS_RATE_LIMIT_ATTEMPTS = 60
ONBOARDING_STATUS_RATE_LIMIT_WINDOW_MINUTES = 5


def _client_ip_intake(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return (request.client and request.client.host) or "unknown"


@router.get("/onboarding-status/{client_id}")
async def get_onboarding_status(request: Request, client_id: str):
    """Get detailed client onboarding status with step-by-step progress."""
    ip = _client_ip_intake(request)
    allowed, err_msg = await rate_limiter.check_rate_limit(
        f"intake_onboarding_status:{ip}", ONBOARDING_STATUS_RATE_LIMIT_ATTEMPTS, ONBOARDING_STATUS_RATE_LIMIT_WINDOW_MINUTES
    )
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err_msg or "Too many requests. Try again later.")
    db = database.get_db()
    
    try:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Get portal user if exists
        portal_user = await db.portal_users.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        # Get properties count
        properties_count = await db.properties.count_documents({"client_id": client_id})
        
        # Get requirements count
        property_ids = [p["property_id"] async for p in db.properties.find({"client_id": client_id}, {"property_id": 1})]
        requirements_count = await db.requirements.count_documents(
            {"property_id": {"$in": property_ids}}
        ) if property_ids else 0
        
        # Determine step statuses
        onboarding_status = client.get("onboarding_status", "INTAKE_PENDING")
        subscription_status = client.get("subscription_status", "PENDING")
        
        # Step 1: Intake - Always complete if we have a client record
        intake_complete = True
        
        # Step 2: Payment
        payment_complete = subscription_status in ["ACTIVE", "PAID"]
        payment_pending = subscription_status == "PENDING"
        
        # Step 3: Provisioning
        provisioning_complete = onboarding_status == "PROVISIONED"
        provisioning_in_progress = onboarding_status == "PROVISIONING"
        provisioning_failed = onboarding_status == "FAILED"
        
        # Step 4: Account Setup (password set)
        account_setup_complete = portal_user and portal_user.get("password_status") == "SET"
        account_invited = portal_user and portal_user.get("status") == "INVITED"
        
        # Step 5: Ready to use
        ready_to_use = provisioning_complete and account_setup_complete
        
        # Build steps array
        steps = [
            {
                "step": 1,
                "name": "Intake Form",
                "description": "Submit your details and property information",
                "status": "complete" if intake_complete else "pending",
                "icon": "clipboard-check"
            },
            {
                "step": 2,
                "name": "Payment",
                "description": "Complete subscription payment",
                "status": "complete" if payment_complete else ("pending" if payment_pending else "waiting"),
                "icon": "credit-card"
            },
            {
                "step": 3,
                "name": "Portal Setup",
                "description": "Your compliance portal is being configured",
                "status": "complete" if provisioning_complete else ("in_progress" if provisioning_in_progress else ("failed" if provisioning_failed else "waiting")),
                "icon": "settings"
            },
            {
                "step": 4,
                "name": "Account Activation",
                "description": "Set your password to access the portal",
                "status": "complete" if account_setup_complete else ("pending" if account_invited else "waiting"),
                "icon": "key"
            },
            {
                "step": 5,
                "name": "Ready to Use",
                "description": "Your compliance dashboard is ready",
                "status": "complete" if ready_to_use else "waiting",
                "icon": "check-circle"
            }
        ]
        
        # Calculate overall progress percentage
        complete_steps = sum(1 for s in steps if s["status"] == "complete")
        progress_percent = int((complete_steps / len(steps)) * 100)
        
        # Current step (first non-complete step)
        current_step = next((s["step"] for s in steps if s["status"] != "complete"), 5)
        
        created_at = client.get("created_at")
        if hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()

        return {
            "client_id": client["client_id"],
            "customer_reference": client.get("customer_reference"),
            "client_name": client.get("full_name"),
            "email": client["email"],
            "onboarding_status": onboarding_status,
            "subscription_status": subscription_status,
            "created_at": created_at,
            "steps": steps,
            "current_step": current_step,
            "progress_percent": progress_percent,
            "is_complete": ready_to_use,
            "properties_count": properties_count,
            "requirements_count": requirements_count,
            "can_login": ready_to_use,
            "portal_url": "/app/dashboard" if ready_to_use else None,
            "next_action": _get_next_action(steps, current_step),
            # Additional info for email method users
            "document_submission_method": client.get("document_submission_method"),
            "pleerity_email": "info@pleerityenterprise.co.uk" if client.get("document_submission_method") == "EMAIL" else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Onboarding status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get onboarding status"
        )


def _get_next_action(steps, current_step):
    """Get the next action the client needs to take."""
    step = next((s for s in steps if s["step"] == current_step), None)
    if not step:
        return None
    
    actions = {
        1: {"action": "complete_intake", "message": "Complete the intake form to get started"},
        2: {"action": "complete_payment", "message": "Complete payment to activate your subscription"},
        3: {"action": "wait_provisioning", "message": "Please wait while we set up your portal"},
        4: {"action": "set_password", "message": "Check your email and set your password"},
        5: {"action": "login", "message": "Your portal is ready! Log in to get started"}
    }
    
    return actions.get(current_step)
