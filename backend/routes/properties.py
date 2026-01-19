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
    
    This creates the property and triggers requirement generation
    using the existing provisioning logic.
    """
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
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
