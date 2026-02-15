"""Property Management Routes - Additive Enhancement
Allows clients to create and manage properties.
"""
from fastapi import APIRouter, HTTPException, Request, status
from database import database
from middleware import client_route_guard
from models import Property, ComplianceStatus, AuditAction, UserRole
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
        
        # PROPERTY CAP ENFORCEMENT (plan_registry: 2/10/25)
        current_count = await db.properties.count_documents({"client_id": user["client_id"]})

        from services.plan_registry import plan_registry, PlanCode
        plan_str = client.get("billing_plan", "PLAN_1_SOLO")
        plan_code = plan_registry.resolve_plan_code(plan_str)
        plan_def = plan_registry.get_plan(plan_code)
        limit = plan_def["max_properties"]
        
        if current_count >= limit:
            # Audit log - property limit exceeded
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role=UserRole(user["role"]),
                actor_id=user["portal_user_id"],
                client_id=user["client_id"],
                metadata={
                    "action_type": "PLAN_LIMIT_EXCEEDED",
                    "feature": "property_create",
                    "plan_code": plan_code.value,
                    "plan_name": plan_def["name"],
                    "current_count": current_count,
                    "limit": limit,
                    "attempted_address": data.address_line_1
                }
            )
            upgrade_plan = None
            for check_code in [PlanCode.PLAN_2_PORTFOLIO, PlanCode.PLAN_3_PRO]:
                if plan_registry.get_property_limit(check_code) > current_count:
                    upgrade_plan = check_code
                    break
            upgrade_def = plan_registry.get_plan(upgrade_plan) if upgrade_plan else None
            detail = {
                "error_code": "PROPERTY_LIMIT_EXCEEDED",
                "message": f"Property limit reached. Your {plan_def['name']} plan allows up to {limit} properties. Upgrade to add more.",
                "feature": "property_creation",
                "upgrade_required": True,
                "current_limit": limit,
                "current_count": current_count,
                "requested_count": 1,
                "upgrade_to": upgrade_plan.value if upgrade_plan else None,
                "upgrade_to_name": upgrade_def["name"] if upgrade_def else None,
                "upgrade_to_limit": upgrade_def["max_properties"] if upgrade_def else None,
            }
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
        
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
        from services.compliance_scoring_service import recalculate_and_persist, REASON_PROPERTY_CREATED
        await recalculate_and_persist(
            property_obj.property_id,
            REASON_PROPERTY_CREATED,
            {"id": user["portal_user_id"], "role": user.get("role")},
            {},
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

        # Property cap enforcement (plan_registry: 2/10/25)
        from services.plan_registry import plan_registry, PlanCode
        plan_str = client.get("billing_plan", "PLAN_1_SOLO")
        plan_code = plan_registry.resolve_plan_code(plan_str)
        plan_def = plan_registry.get_plan(plan_code)
        limit = plan_def["max_properties"]
        current_count = await db.properties.count_documents({"client_id": user["client_id"]})
        import_count = len(data.properties)
        if current_count + import_count > limit:
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role=UserRole(user["role"]),
                actor_id=user["portal_user_id"],
                client_id=user["client_id"],
                metadata={
                    "action_type": "PLAN_LIMIT_EXCEEDED",
                    "feature": "property_bulk_import",
                    "plan_code": plan_code.value,
                    "plan_name": plan_def["name"],
                    "current_count": current_count,
                    "import_count": import_count,
                    "limit": limit,
                }
            )
            upgrade_plan = None
            for check_code in [PlanCode.PLAN_2_PORTFOLIO, PlanCode.PLAN_3_PRO]:
                if plan_registry.get_property_limit(check_code) >= current_count + import_count:
                    upgrade_plan = check_code
                    break
            upgrade_def = plan_registry.get_plan(upgrade_plan) if upgrade_plan else None
            detail = {
                "error_code": "PROPERTY_LIMIT_EXCEEDED",
                "message": f"Property limit would be exceeded. Your {plan_def['name']} plan allows up to {limit} properties (you have {current_count}; requested {import_count} more). Upgrade to add more.",
                "feature": "property_creation",
                "upgrade_required": True,
                "current_limit": limit,
                "current_count": current_count,
                "requested_count": import_count,
                "upgrade_to": upgrade_plan.value if upgrade_plan else None,
                "upgrade_to_name": upgrade_def["name"] if upgrade_def else None,
                "upgrade_to_limit": upgrade_def["max_properties"] if upgrade_def else None,
            }
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

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
            due_date = datetime.fromisoformat(req["due_date"]) if isinstance(req["due_date"], str) else req["due_date"]
            
            if now <= due_date <= deadline_threshold:
                # Get property details
                prop = await db.properties.find_one(
                    {"property_id": req["property_id"]},
                    {"_id": 0}
                )
                
                days_until_due = (due_date - now).days
                
                upcoming.append({
                    "requirement_id": req["requirement_id"],
                    "description": req["description"],
                    "due_date": req["due_date"],
                    "days_until_due": days_until_due,
                    "status": req["status"],
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
