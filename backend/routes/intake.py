"""Universal Intake Wizard Routes - Premium 5-step intake with conditional logic.

Endpoints:
- POST /api/intake/submit - Submit completed intake wizard
- POST /api/intake/checkout - Create Stripe checkout session
- GET /api/intake/onboarding-status/{client_id} - Get onboarding progress
- GET /api/intake/councils - Search UK councils
- POST /api/intake/upload-document - Upload document during intake (non-blocking)
- GET /api/intake/plans - Get available billing plans with limits
- POST /api/intake/validate-property-count - Validate property count against plan limit

INTAKE-LEVEL GATING (NON-NEGOTIABLE):
- Plan gating MUST be enforced inside the intake form
- Property limits are enforced at:
  1. Frontend UI (prevent adding beyond limit)
  2. Intake API validation (block submission)
  3. Provisioning safeguards (defense in depth)
"""
from fastapi import APIRouter, HTTPException, Request, status, UploadFile, File, Form
from database import database
from models import (
    IntakeFormData, IntakePropertyData, Client, Property, ServiceCode, 
    AuditAction, BillingPlan, OnboardingStatus, SubscriptionStatus,
    Document, DocumentStatus, ClientType, PreferredContact
)
from services.stripe_service import stripe_service
from services.plan_registry import plan_registry, PlanCode
from utils.audit import create_audit_log
import logging
import json
import os
import uuid
import random
import string
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intake", tags=["intake"])

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


def _generate_customer_reference() -> str:
    """Generate unique customer reference: PLE-CVP-YYYY-XXXXX
    
    Rules:
    - Uppercase only
    - 5-character alphanumeric suffix
    - Avoid confusing characters (O/0, I/1, L)
    """
    year = datetime.now(timezone.utc).year
    
    # Safe characters (excluding O, 0, I, 1, L)
    safe_chars = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    suffix = ''.join(random.choices(safe_chars, k=5))
    
    return f"PLE-CVP-{year}-{suffix}"


async def _ensure_unique_reference(db) -> str:
    """Generate a unique customer reference, checking database."""
    for _ in range(10):  # Max 10 attempts
        reference = _generate_customer_reference()
        existing = await db.clients.find_one({"customer_reference": reference})
        if not existing:
            return reference
    
    # Fallback with timestamp
    timestamp = int(datetime.now(timezone.utc).timestamp()) % 100000
    return f"PLE-CVP-{datetime.now(timezone.utc).year}-{timestamp:05d}"


@router.get("/plans")
async def get_plans():
    """Get available billing plans with property limits and features.
    
    Returns the new plan structure:
    - PLAN_1_SOLO: 2 properties, £19/mo, £49 setup
    - PLAN_2_PORTFOLIO: 10 properties, £39/mo, £79 setup
    - PLAN_3_PRO: 25 properties, £79/mo, £149 setup
    """
    # Use plan_registry as single source of truth
    all_plans = plan_registry.get_all_plans()
    
    plans = []
    for plan in all_plans:
        plans.append({
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
        })
    
    return {"plans": plans}


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
                postcodes.append({
                    "postcode": item.get("postcode"),
                    "admin_district": item.get("admin_district"),
                    "post_town": item.get("post_town") or item.get("admin_district"),
                    "region": item.get("region"),
                    "country": item.get("country")
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
        
        # Check if client already exists
        existing_client = await db.clients.find_one(
            {"email": data.email},
            {"_id": 0}
        )
        
        if existing_client:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists"
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
            # Log the blocked attempt
            logger.warning(
                f"Intake property limit exceeded: email={data.email}, "
                f"plan={plan_str}, requested={len(data.properties)}, "
                f"limit={error_details.get('current_limit')}"
            )
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "PROPERTY_LIMIT_EXCEEDED",
                    "message": error_msg,
                    "current_limit": error_details.get("current_limit"),
                    "requested_count": len(data.properties),
                    "upgrade_required": True,
                    "upgrade_to": error_details.get("upgrade_to"),
                    "upgrade_to_name": error_details.get("upgrade_to_name"),
                }
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
        
        # Generate unique customer reference
        customer_reference = await _ensure_unique_reference(db)
        
        client = Client(
            customer_reference=customer_reference,
            full_name=data.full_name,
            email=data.email,
            phone=data.phone if data.phone else None,
            company_name=data.company_name if data.company_name else None,
            client_type=data.client_type,
            preferred_contact=data.preferred_contact,
            billing_plan=data.billing_plan,
            service_code=ServiceCode.VAULT_PRO,
            document_submission_method=data.document_submission_method,
            email_upload_consent=data.email_upload_consent,
            consent_data_processing=data.consent_data_processing,
            consent_service_boundary=data.consent_service_boundary
        )
        
        client_doc = client.model_dump()
        for key in ["created_at", "updated_at"]:
            if client_doc.get(key):
                client_doc[key] = client_doc[key].isoformat()
        
        await db.clients.insert_one(client_doc)
        
        # =========== CREATE PROPERTIES ===========
        
        property_temp_key_map = {}  # Map temp_key to property_id for document reconciliation
        
        for i, prop_data in enumerate(data.properties):
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
                is_hmo=prop_data.is_hmo,
                hmo_license_required=hmo_license_required,
                has_gas_supply=True,  # Default, can be updated later
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
                "customer_reference": customer_reference,
                "properties_count": len(data.properties),
                "billing_plan": data.billing_plan.value,
                "document_submission_method": data.document_submission_method
            }
        )
        
        logger.info(f"Intake submitted for {data.email}, ref: {customer_reference}")
        
        return {
            "message": "Intake submitted successfully",
            "client_id": client.client_id,
            "customer_reference": customer_reference,
            "next_step": "checkout"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Intake submission error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process intake"
        )


async def _reconcile_intake_documents(db, client_id: str, session_id: str, property_map: dict):
    """Link documents uploaded during intake to their actual property IDs."""
    try:
        # Find documents with this session ID
        documents = await db.documents.find({
            "intake_session_id": session_id,
            "source": "INTAKE_UPLOAD"
        }).to_list(100)
        
        for doc in documents:
            property_temp_key = doc.get("property_temp_key")
            if property_temp_key and property_temp_key in property_map:
                actual_property_id = property_map[property_temp_key]
                
                await db.documents.update_one(
                    {"document_id": doc["document_id"]},
                    {
                        "$set": {
                            "client_id": client_id,
                            "property_id": actual_property_id,
                            "property_temp_key": None  # Clear temp key
                        }
                    }
                )
                
                logger.info(f"Reconciled document {doc['document_id']} to property {actual_property_id}")
    
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
        storage_dir = os.path.join("/app", "uploads", "intake", intake_session_id)
        os.makedirs(storage_dir, exist_ok=True)
        
        file_ext = os.path.splitext(file.filename)[1] if file.filename else ".pdf"
        file_path = os.path.join(storage_dir, f"{document_id}{file_ext}")
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Create document record (UNVERIFIED, source=INTAKE_UPLOAD)
        doc_record = {
            "document_id": document_id,
            "client_id": None,  # Will be set after intake submission
            "property_id": None,  # Will be set after intake submission
            "property_temp_key": f"{intake_session_id}_property_{property_index}",
            "intake_session_id": intake_session_id,
            "source": "INTAKE_UPLOAD",
            "file_name": file.filename,
            "file_path": file_path,
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
            "manual_review_flag": True  # Always require review for intake uploads
        }
        
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


@router.post("/checkout")
async def create_checkout(request: Request, client_id: str):
    """Create Stripe checkout session for intake payment."""
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Get origin from request
        origin = request.headers.get("origin") or "http://localhost:3000"
        
        # Create checkout session
        session = await stripe_service.create_checkout_session(
            client_id=client_id,
            billing_plan=BillingPlan(client["billing_plan"]),
            origin_url=origin
        )
        
        return {
            "checkout_url": session.url,
            "session_id": session.session_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Checkout creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )


@router.get("/onboarding-status/{client_id}")
async def get_onboarding_status(client_id: str):
    """Get detailed client onboarding status with step-by-step progress."""
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
        
        return {
            "client_id": client["client_id"],
            "customer_reference": client.get("customer_reference"),
            "client_name": client.get("full_name"),
            "email": client["email"],
            "onboarding_status": onboarding_status,
            "subscription_status": subscription_status,
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
