from fastapi import APIRouter, HTTPException, Request, Depends, status
from database import database
from middleware import client_route_guard
from services.compliance_score import calculate_compliance_score
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/client", tags=["client"], dependencies=[Depends(client_route_guard)])

@router.get("/compliance-score")
async def get_compliance_score(request: Request):
    """Get the client's overall compliance score (0-100)."""
    user = await client_route_guard(request)
    
    try:
        score_data = await calculate_compliance_score(user["client_id"])
        return score_data
    except Exception as e:
        logger.error(f"Compliance score error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate compliance score"
        )

@router.get("/dashboard")
async def get_dashboard(request: Request):
    """Get client dashboard data."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one({"client_id": user["client_id"]}, {"_id": 0})
        
        # Get properties
        properties = await db.properties.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(100)
        
        # Get requirements summary
        requirements = await db.requirements.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(1000)
        
        # Calculate compliance summary
        total_requirements = len(requirements)
        compliant = sum(1 for r in requirements if r["status"] == "COMPLIANT")
        overdue = sum(1 for r in requirements if r["status"] == "OVERDUE")
        expiring = sum(1 for r in requirements if r["status"] == "EXPIRING_SOON")
        
        return {
            "client": client,
            "properties": properties,
            "compliance_summary": {
                "total_requirements": total_requirements,
                "compliant": compliant,
                "overdue": overdue,
                "expiring_soon": expiring
            }
        }
    
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load dashboard"
        )

@router.get("/properties")
async def get_properties(request: Request):
    """Get client properties."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        properties = await db.properties.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(100)
        
        return {"properties": properties}
    
    except Exception as e:
        logger.error(f"Properties error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load properties"
        )

@router.get("/properties/{property_id}/requirements")
async def get_property_requirements(request: Request, property_id: str):
    """Get requirements for a property."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        # Verify property belongs to client
        prop = await db.properties.find_one(
            {"property_id": property_id, "client_id": user["client_id"]},
            {"_id": 0}
        )
        
        if not prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found"
            )
        
        requirements = await db.requirements.find(
            {"property_id": property_id, "client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(100)
        
        return {"requirements": requirements}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Requirements error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load requirements"
        )


@router.get("/requirements")
async def get_all_requirements(request: Request):
    """Get all requirements for the client."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        requirements = await db.requirements.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(1000)
        
        return {"requirements": requirements}
    
    except Exception as e:
        logger.error(f"Requirements error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load requirements"
        )


@router.get("/plan-features")
async def get_plan_features(request: Request):
    """Get the current client's plan features and limits.
    
    Returns feature availability for UI gating.
    """
    user = await client_route_guard(request)
    
    try:
        from services.plan_gating import plan_gating_service
        
        plan_info = await plan_gating_service.get_client_plan_info(user["client_id"])
        return plan_info
    
    except Exception as e:
        logger.error(f"Plan features error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load plan features"
        )


@router.get("/documents")
async def get_documents(request: Request):
    """Get client documents."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        documents = await db.documents.find(
            {"client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(1000)
        
        return {"documents": documents}
    
    except Exception as e:
        logger.error(f"Documents error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load documents"
        )



@router.post("/tenants/invite")
async def invite_tenant(request: Request):
    """
    Invite a tenant to view property compliance status.
    
    Creates a ROLE_TENANT user with read-only access.
    """
    user = await client_route_guard(request)
    db = database.get_db()
    
    # Only CLIENT_ADMIN can invite tenants
    if user.get("role") not in ["ROLE_CLIENT_ADMIN", "ROLE_ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only client admins can invite tenants"
        )
    
    try:
        body = await request.json()
        email = body.get("email")
        full_name = body.get("full_name", "")
        property_ids = body.get("property_ids", [])  # Optional: specific properties
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required"
            )
        
        # Check if tenant already exists
        existing = await db.portal_users.find_one({"email": email.lower()})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        # Create tenant user
        import uuid
        from datetime import datetime, timezone, timedelta
        
        tenant_id = str(uuid.uuid4())
        
        tenant_user = {
            "portal_user_id": tenant_id,
            "client_id": user["client_id"],
            "email": email.lower(),
            "full_name": full_name,
            "role": "ROLE_TENANT",
            "status": "INVITED",
            "password_status": "NOT_SET",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "invited_by": user["portal_user_id"]
        }
        
        await db.portal_users.insert_one(tenant_user)
        
        # Create password token
        token = str(uuid.uuid4())
        token_doc = {
            "token": token,
            "portal_user_id": tenant_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "used": False
        }
        await db.password_tokens.insert_one(token_doc)
        
        # Create property assignments if specified
        if property_ids:
            for prop_id in property_ids:
                # Verify property belongs to client
                prop = await db.properties.find_one({
                    "property_id": prop_id,
                    "client_id": user["client_id"]
                })
                if prop:
                    await db.tenant_assignments.insert_one({
                        "tenant_id": tenant_id,
                        "property_id": prop_id,
                        "assigned_at": datetime.now(timezone.utc).isoformat(),
                        "assigned_by": user["portal_user_id"]
                    })
        
        # Send invite email using proper template
        from services.email_service import email_service
        from models import EmailTemplateAlias
        invite_url = f"{body.get('base_url', '')}/set-password?token={token}"
        
        await email_service.send_email(
            recipient=email,
            template_alias=EmailTemplateAlias.TENANT_INVITE,
            template_model={
                "tenant_name": full_name or "there",
                "setup_link": invite_url
            },
            client_id=user["client_id"],
            subject="You've been invited to view property compliance"
        )
        
        logger.info(f"Tenant invited: {email} by {user['email']}")
        
        return {
            "message": "Tenant invited successfully",
            "tenant_id": tenant_id,
            "email": email,
            "invite_sent": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tenant invite error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invite tenant"
        )


@router.get("/tenants")
async def list_tenants(request: Request):
    """List all tenants invited by this client."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        tenants = await db.portal_users.find(
            {
                "client_id": user["client_id"],
                "role": "ROLE_TENANT"
            },
            {"_id": 0, "password_hash": 0}
        ).to_list(100)
        
        # Get property assignments
        tenant_ids = [t["portal_user_id"] for t in tenants]
        assignments = await db.tenant_assignments.find(
            {"tenant_id": {"$in": tenant_ids}},
            {"_id": 0}
        ).to_list(1000)
        
        # Build assignment map
        assignment_map = {}
        for a in assignments:
            if a["tenant_id"] not in assignment_map:
                assignment_map[a["tenant_id"]] = []
            assignment_map[a["tenant_id"]].append(a["property_id"])
        
        # Add assignments to tenant data
        for tenant in tenants:
            tenant["assigned_properties"] = assignment_map.get(tenant["portal_user_id"], [])
        
        return {"tenants": tenants}
    
    except Exception as e:
        logger.error(f"List tenants error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tenants"
        )



@router.post("/tenants/{tenant_id}/assign-property")
async def assign_tenant_to_property(request: Request, tenant_id: str):
    """Assign a tenant to a property."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    if user.get("role") not in ["ROLE_CLIENT_ADMIN", "ROLE_ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only client admins can manage tenant assignments"
        )
    
    try:
        body = await request.json()
        property_id = body.get("property_id")
        
        if not property_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="property_id is required"
            )
        
        # Verify tenant belongs to this client
        tenant = await db.portal_users.find_one({
            "portal_user_id": tenant_id,
            "client_id": user["client_id"],
            "role": "ROLE_TENANT"
        })
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Verify property belongs to this client
        prop = await db.properties.find_one({
            "property_id": property_id,
            "client_id": user["client_id"]
        })
        
        if not prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found"
            )
        
        # Check if already assigned
        existing = await db.tenant_assignments.find_one({
            "tenant_id": tenant_id,
            "property_id": property_id
        })
        
        if existing:
            return {"message": "Tenant already assigned to this property"}
        
        # Create assignment
        from datetime import datetime, timezone
        await db.tenant_assignments.insert_one({
            "tenant_id": tenant_id,
            "property_id": property_id,
            "assigned_at": datetime.now(timezone.utc).isoformat(),
            "assigned_by": user["portal_user_id"]
        })
        
        logger.info(f"Tenant {tenant_id} assigned to property {property_id}")
        
        return {
            "message": "Tenant assigned to property",
            "tenant_id": tenant_id,
            "property_id": property_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Assign tenant error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign tenant"
        )


@router.delete("/tenants/{tenant_id}/unassign-property/{property_id}")
async def unassign_tenant_from_property(request: Request, tenant_id: str, property_id: str):
    """Remove a tenant's assignment to a property."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    if user.get("role") not in ["ROLE_CLIENT_ADMIN", "ROLE_ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only client admins can manage tenant assignments"
        )
    
    try:
        # Verify tenant belongs to this client
        tenant = await db.portal_users.find_one({
            "portal_user_id": tenant_id,
            "client_id": user["client_id"],
            "role": "ROLE_TENANT"
        })
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Remove assignment
        result = await db.tenant_assignments.delete_one({
            "tenant_id": tenant_id,
            "property_id": property_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found"
            )
        
        logger.info(f"Tenant {tenant_id} unassigned from property {property_id}")
        
        return {"message": "Tenant unassigned from property"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unassign tenant error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unassign tenant"
        )


@router.delete("/tenants/{tenant_id}")
async def revoke_tenant_access(request: Request, tenant_id: str):
    """Revoke a tenant's access entirely (disable account)."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    if user.get("role") not in ["ROLE_CLIENT_ADMIN", "ROLE_ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only client admins can revoke tenant access"
        )
    
    try:
        # Verify tenant belongs to this client
        tenant = await db.portal_users.find_one({
            "portal_user_id": tenant_id,
            "client_id": user["client_id"],
            "role": "ROLE_TENANT"
        })
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        # Disable the tenant account
        await db.portal_users.update_one(
            {"portal_user_id": tenant_id},
            {"$set": {"status": "DISABLED"}}
        )
        
        # Remove all property assignments
        await db.tenant_assignments.delete_many({"tenant_id": tenant_id})
        
        logger.info(f"Tenant {tenant_id} access revoked by {user['email']}")
        
        return {"message": "Tenant access revoked"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Revoke tenant error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke tenant access"
        )


@router.post("/tenants/{tenant_id}/resend-invite")
async def resend_tenant_invite(request: Request, tenant_id: str):
    """Resend invitation email to a tenant."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    if user.get("role") not in ["ROLE_CLIENT_ADMIN", "ROLE_ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only client admins can resend invites"
        )
    
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        
        # Verify tenant belongs to this client
        tenant = await db.portal_users.find_one({
            "portal_user_id": tenant_id,
            "client_id": user["client_id"],
            "role": "ROLE_TENANT"
        })
        
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        
        if tenant.get("status") == "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant has already set up their account"
            )
        
        # Create new password token
        import uuid
        from datetime import datetime, timezone, timedelta
        
        token = str(uuid.uuid4())
        token_doc = {
            "token": token,
            "portal_user_id": tenant_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "used": False
        }
        await db.password_tokens.insert_one(token_doc)
        
        # Send invite email
        from services.email_service import email_service
        from models import EmailTemplateAlias
        
        invite_url = f"{body.get('base_url', '')}/set-password?token={token}"
        
        await email_service.send_email(
            recipient=tenant["email"],
            template_alias=EmailTemplateAlias.TENANT_INVITE,
            template_model={
                "tenant_name": tenant.get("full_name", "there"),
                "setup_link": invite_url
            },
            client_id=user["client_id"],
            subject="Reminder: Set up your tenant portal access"
        )
        
        logger.info(f"Tenant invite resent to {tenant['email']}")
        
        return {"message": "Invitation resent successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend invite error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resend invitation"
        )

