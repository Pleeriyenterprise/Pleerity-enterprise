"""Tenant Routes - Read-only access to property compliance status.

ROLE_TENANT has STRICTLY LIMITED permissions:
✅ View property compliance status (GREEN/AMBER/RED)
✅ View certificate status and expiry dates
✅ View basic summaries

❌ No document uploads
❌ No messaging or chat
❌ No audit logs access
❌ No reports access
❌ No billing/settings visibility
❌ No admin actions
"""
from fastapi import APIRouter, HTTPException, Request, status
from database import database
from middleware import client_route_guard
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tenant", tags=["tenant"])


async def tenant_route_guard(request: Request):
    """Guard that allows ROLE_TENANT access (read-only)."""
    user = await client_route_guard(request)
    
    # Tenants have their own role but share client_id with landlord
    if user.get("role") not in ["ROLE_TENANT", "ROLE_CLIENT", "ROLE_CLIENT_ADMIN", "ROLE_ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return user


@router.get("/dashboard")
async def get_tenant_dashboard(request: Request):
    """
    Get simplified tenant dashboard data.
    
    Shows ONLY:
    - Properties the tenant is assigned to
    - Compliance status (GREEN/AMBER/RED)
    - Certificate expiry summaries
    - Basic statistics
    
    Does NOT show:
    - Documents or upload functionality
    - Audit logs
    - Admin features
    - Billing information
    """
    user = await tenant_route_guard(request)
    db = database.get_db()
    
    # For tenants, we need to check their tenant_properties assignment
    # For now, we show all properties linked to their client_id
    client_id = user.get("client_id")
    tenant_id = user.get("portal_user_id")
    
    # Get tenant-specific property assignments if they exist
    tenant_properties = await db.tenant_assignments.find(
        {"tenant_id": tenant_id},
        {"_id": 0, "property_id": 1}
    ).to_list(100)
    
    # If tenant has specific assignments, filter by those
    property_filter = {"client_id": client_id}
    if tenant_properties:
        assigned_property_ids = [tp["property_id"] for tp in tenant_properties]
        property_filter["property_id"] = {"$in": assigned_property_ids}
    
    # Get properties with limited fields
    properties = await db.properties.find(
        property_filter,
        {
            "_id": 0,
            "property_id": 1,
            "address_line_1": 1,
            "city": 1,
            "postcode": 1,
            "property_type": 1,
            "compliance_status": 1
        }
    ).to_list(100)
    
    # Get requirements for these properties
    property_ids = [p["property_id"] for p in properties]
    requirements = await db.requirements.find(
        {"property_id": {"$in": property_ids}},
        {
            "_id": 0,
            "requirement_id": 1,
            "property_id": 1,
            "requirement_type": 1,
            "description": 1,
            "status": 1,
            "due_date": 1
        }
    ).to_list(1000)
    
    # Build simplified response
    property_summaries = []
    for prop in properties:
        prop_reqs = [r for r in requirements if r.get("property_id") == prop["property_id"]]
        
        # Simplify requirement info for tenants
        cert_summary = []
        for req in prop_reqs:
            cert_summary.append({
                "type": req.get("requirement_type", "Unknown"),
                "description": req.get("description", ""),
                "status": req.get("status", "UNKNOWN"),
                "expiry": req.get("due_date", "N/A")[:10] if req.get("due_date") else "N/A"
            })
        
        property_summaries.append({
            "property_id": prop["property_id"],
            "address": f"{prop.get('address_line_1', '')}, {prop.get('city', '')} {prop.get('postcode', '')}",
            "property_type": prop.get("property_type", "N/A"),
            "compliance_status": prop.get("compliance_status", "UNKNOWN"),
            "certificates": cert_summary
        })
    
    # Calculate overall stats
    total_properties = len(properties)
    green_count = sum(1 for p in properties if p.get("compliance_status") == "GREEN")
    amber_count = sum(1 for p in properties if p.get("compliance_status") == "AMBER")
    red_count = sum(1 for p in properties if p.get("compliance_status") == "RED")
    
    return {
        "tenant_name": user.get("full_name", user.get("email")),
        "summary": {
            "total_properties": total_properties,
            "fully_compliant": green_count,
            "needs_attention": amber_count,
            "action_required": red_count
        },
        "properties": property_summaries,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "role": "ROLE_TENANT"
    }


@router.get("/property/{property_id}")
async def get_tenant_property_details(request: Request, property_id: str):
    """
    Get detailed compliance status for a specific property.
    
    Tenant can only view properties they are assigned to.
    """
    user = await tenant_route_guard(request)
    db = database.get_db()
    
    client_id = user.get("client_id")
    tenant_id = user.get("portal_user_id")
    
    # Verify property access
    property_doc = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {
            "_id": 0,
            "property_id": 1,
            "address_line_1": 1,
            "address_line_2": 1,
            "city": 1,
            "postcode": 1,
            "property_type": 1,
            "compliance_status": 1
        }
    )
    
    if not property_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found or access denied"
        )
    
    # Check tenant assignment if tenant role
    if user.get("role") == "ROLE_TENANT":
        assignment = await db.tenant_assignments.find_one({
            "tenant_id": tenant_id,
            "property_id": property_id
        })
        # If tenant assignments exist and this property isn't assigned, deny access
        all_assignments = await db.tenant_assignments.count_documents({"tenant_id": tenant_id})
        if all_assignments > 0 and not assignment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not assigned to this property"
            )
    
    # Get requirements
    requirements = await db.requirements.find(
        {"property_id": property_id},
        {
            "_id": 0,
            "requirement_id": 1,
            "requirement_type": 1,
            "description": 1,
            "status": 1,
            "due_date": 1,
            "frequency_days": 1
        }
    ).to_list(100)
    
    # Format certificates for tenant view
    certificates = []
    for req in requirements:
        status_color = "gray"
        if req.get("status") == "COMPLIANT":
            status_color = "green"
        elif req.get("status") == "EXPIRING_SOON":
            status_color = "yellow"
        elif req.get("status") == "OVERDUE":
            status_color = "red"
        elif req.get("status") == "PENDING":
            status_color = "blue"
        
        certificates.append({
            "type": req.get("requirement_type", "Unknown"),
            "description": req.get("description", ""),
            "status": req.get("status", "UNKNOWN"),
            "status_color": status_color,
            "expiry_date": req.get("due_date", "N/A")[:10] if req.get("due_date") else "Not Set",
            "renewal_frequency": f"Every {req.get('frequency_days', 0)} days" if req.get("frequency_days") else "N/A"
        })
    
    return {
        "property": {
            "property_id": property_id,
            "address": f"{property_doc.get('address_line_1', '')}, {property_doc.get('city', '')} {property_doc.get('postcode', '')}",
            "type": property_doc.get("property_type", "N/A"),
            "compliance_status": property_doc.get("compliance_status", "UNKNOWN")
        },
        "certificates": certificates,
        "note": "This view shows the compliance status of certificates for your rental property. Contact your landlord for more details."
    }
