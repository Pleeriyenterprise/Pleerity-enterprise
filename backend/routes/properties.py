"""Property Management Routes - Additive Enhancement
Allows clients to create and manage properties.
"""
from fastapi import APIRouter, HTTPException, Request, status
from database import database
from middleware import client_route_guard
from models import Property, ComplianceStatus, AuditAction, UserRole
from utils.expiry_utils import get_effective_expiry_date, get_computed_status, is_included_for_calendar
from utils.audit import create_audit_log
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/properties", tags=["properties"])

class CreatePropertyRequest(BaseModel):
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    postcode: str
    property_type: str = "residential"
    number_of_units: int = 1

@router.post("/create")
async def create_property(request: Request, data: CreatePropertyRequest):
    """Create a new property for the authenticated client.
    
    Enforces plan-based property limits.
    """
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client with plan info
        client = await db.clients.find_one(
            {"client_id": user["client_id"]},
            {"_id": 0}
        )
        
        if not client or client["onboarding_status"] != "PROVISIONED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account must be fully provisioned to add properties"
            )
        
        # Property cap enforcement (plan_registry canonical) – count only active properties
        active_count = await db.properties.count_documents({
            "client_id": user["client_id"],
            "$or": [{"is_active": True}, {"is_active": {"$exists": False}}],
        })
        from services.plan_registry import plan_registry
        allowed, error_msg, error_details = await plan_registry.enforce_property_limit(
            user["client_id"], active_count + 1
        )
        if not allowed:
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role=UserRole(user["role"]),
                actor_id=user["portal_user_id"],
                client_id=user["client_id"],
                metadata={
                    "action_type": "PLAN_LIMIT_EXCEEDED",
                    "feature": "property_create",
                    "current_count": active_count,
                    "requested_count": 1,
                    "attempted_address": data.address_line_1,
                },
            )
            detail = dict(error_details or {})
            detail["error_code"] = "PLAN_LIMIT"  # API contract for plan-limit 403
            detail["message"] = detail.get("message") or error_msg
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail,
            )
        
        # Create property
        property_obj = Property(
            client_id=user["client_id"],
            address_line_1=data.address_line_1,
            address_line_2=data.address_line_2,
            city=data.city,
            postcode=data.postcode,
            property_type=data.property_type,
            number_of_units=data.number_of_units,
            compliance_status=ComplianceStatus.RED
        )
        
        prop_doc = property_obj.model_dump()
        for key in ["created_at", "updated_at"]:
            if prop_doc.get(key):
                prop_doc[key] = prop_doc[key].isoformat()
        
        await db.properties.insert_one(prop_doc)
        
        # Remove MongoDB _id from response
        prop_doc.pop("_id", None)
        
        # Generate requirements using existing logic
        from services.provisioning import provisioning_service
        await provisioning_service._generate_requirements(
            user["client_id"],
            property_obj.property_id
        )
        
        # Update compliance status
        await provisioning_service._update_property_compliance(
            property_obj.property_id
        )
        from services.compliance_recalc_queue import enqueue_compliance_recalc, TRIGGER_PROPERTY_CREATED, ACTOR_ADMIN
        await enqueue_compliance_recalc(
            property_id=property_obj.property_id,
            client_id=user["client_id"],
            trigger_reason=TRIGGER_PROPERTY_CREATED,
            actor_type=ACTOR_ADMIN,
            actor_id=user.get("portal_user_id"),
            correlation_id=f"PROPERTY_CREATED:{property_obj.property_id}",
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole(user["role"]),
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="property",
            resource_id=property_obj.property_id,
            metadata={
                "action": "property_created",
                "address": f"{data.address_line_1}, {data.city}",
                "postcode": data.postcode
            }
        )
        
        logger.info(f"Property created by client {user['client_id']}: {property_obj.property_id}")
        
        return {
            "message": "Property created successfully",
            "property_id": property_obj.property_id,
            "property": prop_doc
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Property creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create property"
        )

# Fields that affect compliance score applicability (v1); changing any triggers recalc.
APPLICABILITY_FIELDS = frozenset({"is_hmo", "bedrooms", "occupancy", "licence_required", "has_gas_supply", "has_gas", "tenancy_active", "furnished", "property_type"})


class PatchPropertyRequest(BaseModel):
    """Optional fields for PATCH; only provided keys are updated."""
    nickname: Optional[str] = None
    property_type: Optional[str] = None  # residential, commercial, flat, house, bungalow, etc.; commercial excludes residential-only requirements
    is_hmo: Optional[bool] = None
    bedrooms: Optional[int] = None
    occupancy: Optional[str] = None
    licence_required: Optional[str] = None
    has_gas_supply: Optional[bool] = None
    has_gas: Optional[bool] = None
    tenancy_active: Optional[bool] = None
    furnished: Optional[bool] = None
    is_active: Optional[bool] = None  # False = archived (read-only) when over property limit


@router.patch("/{property_id}")
async def patch_property(request: Request, property_id: str, data: PatchPropertyRequest):
    """Update a property. Only provided fields are updated.
    Changing is_hmo, bedrooms, occupancy, licence_required, has_gas_supply, or has_gas triggers compliance score recalc.
    Setting is_active=False archives the property (read-only); is_active=True counts toward plan limit.
    """
    user = await client_route_guard(request)
    db = database.get_db()

    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0, "property_id": 1, "client_id": 1, "property_type": 1, "is_hmo": 1, "bedrooms": 1, "occupancy": 1,
         "licence_required": 1, "has_gas_supply": 1, "has_gas": 1, "tenancy_active": 1, "furnished": 1, "is_active": 1},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    update = {}
    payload = data.model_dump(exclude_none=True)
    for key, value in payload.items():
        update[key] = value

    # When activating a property, enforce plan limit (active count cannot exceed allowed)
    if "is_active" in update and update["is_active"] is True:
        from services.plan_registry import plan_registry
        active_count = await db.properties.count_documents({
            "client_id": user["client_id"],
            "property_id": {"$ne": property_id},
            "$or": [{"is_active": True}, {"is_active": {"$exists": False}}],
        })
        allowed, error_msg, error_details = await plan_registry.enforce_property_limit(
            user["client_id"], active_count + 1
        )
        if not allowed:
            detail = error_details or {}
            if "error_code" not in detail:
                detail["error_code"] = "PLAN_LIMIT"
            detail["message"] = detail.get("message") or error_msg
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    if not update:
        return {"message": "No updates", "property_id": property_id}

    applicability_changed = any(
        f in update and prop.get(f) != update[f]
        for f in APPLICABILITY_FIELDS
    )

    now = datetime.now(timezone.utc)
    update["updated_at"] = now.isoformat()
    await db.properties.update_one(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"$set": update},
    )

    if applicability_changed:
        from services.compliance_recalc_queue import (
            enqueue_compliance_recalc,
            TRIGGER_PROPERTY_UPDATED,
            ACTOR_CLIENT,
        )
        await enqueue_compliance_recalc(
            property_id=property_id,
            client_id=user["client_id"],
            trigger_reason=TRIGGER_PROPERTY_UPDATED,
            actor_type=ACTOR_CLIENT,
            actor_id=user.get("portal_user_id"),
            correlation_id=f"PROPERTY_UPDATED:{property_id}",
        )

    return {"message": "Property updated", "property_id": property_id}


# Controlled reason list for NOT_REQUIRED (no legal advice; user selects from list)
NOT_REQUIRED_REASONS = ["no_gas_supply", "exempt", "not_applicable", "other"]


class PatchRequirementRequest(BaseModel):
    """Update expiry, applicability, or certificate fields for a property requirement."""
    confirmed_expiry_date: Optional[str] = None  # ISO date
    issue_date: Optional[str] = None  # ISO date
    certificate_number: Optional[str] = None
    applicability: Optional[str] = None  # REQUIRED | NOT_REQUIRED | UNKNOWN
    not_required_reason: Optional[str] = None  # Required when applicability=NOT_REQUIRED; one of NOT_REQUIRED_REASONS


@router.patch("/{property_id}/requirements/{requirement_id}")
async def patch_requirement(
    request: Request,
    property_id: str,
    requirement_id: str,
    data: PatchRequirementRequest,
):
    """Update a requirement's confirmed expiry date or applicability (e.g. mark NOT_REQUIRED with reason)."""
    user = await client_route_guard(request)
    db = database.get_db()

    req = await db.requirements.find_one(
        {"requirement_id": requirement_id, "property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0},
    )
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")

    update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if data.confirmed_expiry_date is not None:
        try:
            parsed = datetime.fromisoformat(data.confirmed_expiry_date.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            update["confirmed_expiry_date"] = parsed.isoformat()
            update["expiry_source"] = "CONFIRMED"
            update["due_date"] = parsed.isoformat()
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid confirmed_expiry_date format; use YYYY-MM-DD or ISO datetime",
            )
    if data.applicability is not None:
        app = data.applicability.strip().upper()
        if app not in ("REQUIRED", "NOT_REQUIRED", "UNKNOWN"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="applicability must be REQUIRED, NOT_REQUIRED, or UNKNOWN",
            )
        update["applicability"] = app
        if app == "NOT_REQUIRED":
            reason = (data.not_required_reason or "").strip()
            if reason and reason not in NOT_REQUIRED_REASONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"not_required_reason must be one of: {NOT_REQUIRED_REASONS}",
                )
            update["not_required_reason"] = reason or None

    if data.issue_date is not None:
        try:
            parsed = datetime.fromisoformat(data.issue_date.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            update["issue_date"] = parsed.isoformat()
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid issue_date format; use YYYY-MM-DD or ISO datetime",
            )
    if data.certificate_number is not None:
        update["certificate_number"] = (data.certificate_number or "").strip() or None

    if len(update) <= 1:
        return {"message": "No updates", "requirement_id": requirement_id}

    # Set status from deterministic rule when expiry or applicability changed
    merged = {**req, **update}
    update["status"] = get_computed_status(merged)

    await db.requirements.update_one(
        {"requirement_id": requirement_id, "property_id": property_id, "client_id": user["client_id"]},
        {"$set": update},
    )
    return {"message": "Requirement updated", "requirement_id": requirement_id}


@router.get("/list")
async def list_properties(request: Request):
    """List all properties for the authenticated client.
    
    This is a convenience endpoint that returns the same data
    as the dashboard endpoint.
    """
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        properties = await db.properties.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(100)
        
        # Get requirements count for each property
        for prop in properties:
            requirements = await db.requirements.find(
                {"property_id": prop["property_id"]},
                {"_id": 0}
            ).to_list(100)
            
            prop["requirements_count"] = len(requirements)
            prop["compliant_count"] = sum(1 for r in requirements if r["status"] == "COMPLIANT")
            prop["overdue_count"] = sum(1 for r in requirements if r["status"] == "OVERDUE")
        
        return {"properties": properties}
    
    except Exception as e:
        logger.error(f"List properties error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load properties"
        )


class BulkPropertyItem(BaseModel):
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    postcode: str
    property_type: str = "residential"
    number_of_units: int = 1


class BulkImportRequest(BaseModel):
    properties: List[BulkPropertyItem]


@router.post("/bulk-import")
async def bulk_import_properties(request: Request, data: BulkImportRequest):
    """Import multiple properties from a list (e.g., parsed CSV data).
    
    Accepts a list of property objects and creates them with requirements.
    Useful for letting agents managing multiple properties.
    
    Returns summary of successful and failed imports.
    """
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        from services.provisioning import ProvisioningService
        
        # Verify client is provisioned
        client = await db.clients.find_one(
            {"client_id": user["client_id"]},
            {"_id": 0}
        )
        
        if not client or client["onboarding_status"] != "PROVISIONED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account must be fully provisioned to add properties"
            )

        # Property cap enforcement (plan_registry canonical) – count only active properties
        active_count = await db.properties.count_documents({
            "client_id": user["client_id"],
            "$or": [{"is_active": True}, {"is_active": {"$exists": False}}],
        })
        import_count = len(data.properties)
        from services.plan_registry import plan_registry
        allowed, error_msg, error_details = await plan_registry.enforce_property_limit(
            user["client_id"], active_count + import_count
        )
        if not allowed:
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role=UserRole(user["role"]),
                actor_id=user["portal_user_id"],
                client_id=user["client_id"],
                metadata={
                    "action_type": "PLAN_LIMIT_EXCEEDED",
                    "feature": "property_bulk_import",
                    "current_count": active_count,
                    "import_count": import_count,
                },
            )
            detail = dict(error_details or {})
            detail["error_code"] = "PLAN_LIMIT"
            detail["message"] = detail.get("message") or error_msg
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail,
            )

        results = {
            "total": len(data.properties),
            "successful": 0,
            "failed": 0,
            "errors": [],
            "created_properties": []
        }

        provisioning = ProvisioningService()
        
        for idx, prop_data in enumerate(data.properties):
            try:
                # Validate required fields
                if not prop_data.address_line_1 or not prop_data.city or not prop_data.postcode:
                    results["failed"] += 1
                    results["errors"].append({
                        "row": idx + 1,
                        "error": "Missing required field (address_line_1, city, or postcode)"
                    })
                    continue
                
                # Check for duplicate address
                existing = await db.properties.find_one({
                    "client_id": user["client_id"],
                    "address_line_1": prop_data.address_line_1,
                    "postcode": prop_data.postcode
                })
                
                if existing:
                    results["failed"] += 1
                    results["errors"].append({
                        "row": idx + 1,
                        "address": f"{prop_data.address_line_1}, {prop_data.postcode}",
                        "error": "Property already exists"
                    })
                    continue
                
                # Create property
                property_obj = Property(
                    client_id=user["client_id"],
                    address_line_1=prop_data.address_line_1,
                    address_line_2=prop_data.address_line_2,
                    city=prop_data.city,
                    postcode=prop_data.postcode,
                    property_type=prop_data.property_type,
                    number_of_units=prop_data.number_of_units,
                    compliance_status=ComplianceStatus.RED
                )
                
                prop_doc = property_obj.model_dump()
                await db.properties.insert_one(prop_doc)
                
                # Generate requirements using internal method
                req_count = 0
                try:
                    await provisioning._generate_requirements(
                        client_id=user["client_id"],
                        property_id=property_obj.property_id
                    )
                    # Count generated requirements
                    req_count = await db.requirements.count_documents({
                        "property_id": property_obj.property_id
                    })
                except Exception as req_err:
                    logger.warning(f"Failed to generate requirements for {property_obj.property_id}: {req_err}")
                
                results["successful"] += 1
                results["created_properties"].append({
                    "property_id": property_obj.property_id,
                    "address": f"{prop_data.address_line_1}, {prop_data.city}",
                    "requirements_created": req_count
                })
                
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "row": idx + 1,
                    "error": str(e)
                })
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="property",
            metadata={
                "action": "bulk_import",
                "total": results["total"],
                "successful": results["successful"],
                "failed": results["failed"]
            }
        )
        
        logger.info(f"Bulk import: {results['successful']}/{results['total']} properties created for {user['email']}")
        
        return {
            "message": f"Imported {results['successful']} of {results['total']} properties",
            "summary": results
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk import error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to import properties"
        )



@router.get("/upcoming-deadlines")
async def get_upcoming_deadlines(request: Request, days: int = 30):
    """Get upcoming compliance deadlines for dashboard widget."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        from datetime import timedelta
        
        # Get all requirements for client
        requirements = await db.requirements.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(1000)
        
        # Filter for upcoming deadlines
        now = datetime.now(timezone.utc)
        deadline_threshold = now + timedelta(days=days)
        
        upcoming = []
        for req in requirements:
            if not is_included_for_calendar(req):
                continue
            due_date = get_effective_expiry_date(req)
            if due_date is None or not (now <= due_date <= deadline_threshold):
                continue
            # Get property details
            prop = await db.properties.find_one(
                {"property_id": req["property_id"]},
                {"_id": 0}
            )
            days_until_due = (due_date - now).days
            upcoming.append({
                "requirement_id": req["requirement_id"],
                "description": req.get("description", ""),
                "due_date": due_date.isoformat(),
                "days_until_due": days_until_due,
                "status": req.get("status", "PENDING"),
                "property_address": f"{prop['address_line_1']}, {prop['city']}" if prop else "Unknown",
                "property_id": req["property_id"]
            })
        
        # Sort by due date
        upcoming.sort(key=lambda x: x["days_until_due"])
        
        return {
            "upcoming_deadlines": upcoming[:10],  # Return top 10
            "total_upcoming": len(upcoming)
        }
    
    except Exception as e:
        logger.error(f"Get upcoming deadlines error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load upcoming deadlines"
        )
