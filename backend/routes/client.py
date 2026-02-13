from fastapi import APIRouter, HTTPException, Request, Depends, status
from fastapi.responses import StreamingResponse
from database import database
from middleware import client_route_guard
from services.compliance_score import calculate_compliance_score
import logging
import io

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


@router.get("/compliance-score/trend")
async def get_compliance_score_trend(
    request: Request,
    days: int = 30,
    include_breakdown: bool = False
):
    """Get compliance score trend data for trend visualization.
    
    Returns sparkline data and change analysis for the dashboard.
    
    Args:
        days: Number of days of history (default 30, max 90)
        include_breakdown: Include detailed breakdown per day
    """
    user = await client_route_guard(request)
    
    try:
        from services.compliance_trending import get_score_trend
        
        # Cap at 90 days
        days = min(days, 90)
        
        trend_data = await get_score_trend(
            client_id=user["client_id"],
            days=days,
            include_breakdown=include_breakdown
        )
        return trend_data
    except Exception as e:
        logger.error(f"Compliance score trend error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get compliance score trend"
        )


@router.get("/compliance-score/explanation")
async def get_compliance_score_explanation(
    request: Request,
    compare_days: int = 7
):
    """Get a plain-English explanation of what changed in the compliance score.
    
    Compares current state to N days ago and explains the difference.
    
    Args:
        compare_days: Days back to compare (default 7, max 30)
    """
    user = await client_route_guard(request)
    
    try:
        from services.compliance_trending import get_score_change_explanation
        
        # Cap at 30 days
        compare_days = min(compare_days, 30)
        
        explanation = await get_score_change_explanation(
            client_id=user["client_id"],
            compare_days=compare_days
        )
        return explanation
    except Exception as e:
        logger.error(f"Compliance score explanation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get compliance score explanation"
        )


@router.post("/compliance-score/snapshot")
async def trigger_compliance_snapshot(request: Request):
    """Manually trigger a compliance score snapshot (for testing/admin).
    
    Creates an immediate snapshot of the current compliance score.
    Useful for manual updates or debugging.
    """
    user = await client_route_guard(request)
    
    try:
        from services.compliance_trending import capture_daily_snapshot
        
        result = await capture_daily_snapshot(user["client_id"])
        return result
    except Exception as e:
        logger.error(f"Compliance snapshot trigger error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to capture compliance snapshot"
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
    Uses plan_registry (2/10/25 caps); response shape preserved for compatibility.
    """
    user = await client_route_guard(request)
    try:
        from services.plan_registry import plan_registry, subscription_allows_feature_access

        client_id = user["client_id"]
        db = database.get_db()
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "billing_plan": 1, "subscription_status": 1}
        )
        if not client:
            plan_code = plan_registry.resolve_plan_code("PLAN_1_SOLO")
            plan_def = plan_registry.get_plan(plan_code)
            features = plan_registry.get_features(plan_code)
            features["max_properties"] = plan_registry.get_property_limit(plan_code)
            return {
                "plan": plan_code.value,
                "plan_name": plan_def["name"],
                "subscription_status": "UNKNOWN",
                "features": features,
                "is_active": False,
            }
        plan_str = client.get("billing_plan", "PLAN_1_SOLO")
        plan_code = plan_registry.resolve_plan_code(plan_str)
        plan_def = plan_registry.get_plan(plan_code)
        subscription_status = client.get("subscription_status", "PENDING")
        is_active = subscription_allows_feature_access(subscription_status)
        features = plan_registry.get_features(plan_code)
        features["max_properties"] = plan_registry.get_property_limit(plan_code)
        return {
            "plan": plan_code.value,
            "plan_name": plan_def["name"],
            "subscription_status": subscription_status,
            "features": features,
            "is_active": is_active,
        }
    except Exception as e:
        logger.error(f"Plan features error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load plan features"
        )


@router.get("/entitlements")
async def get_client_entitlements(request: Request):
    """Get comprehensive feature entitlements for the client.
    
    Returns detailed feature availability with metadata for UI rendering.
    This is the primary endpoint for feature gating in the frontend.
    Uses plan_registry as single source of truth.
    """
    user = await client_route_guard(request)
    
    try:
        from services.plan_registry import plan_registry
        
        entitlements = await plan_registry.get_client_entitlements(user["client_id"])
        return entitlements
    
    except Exception as e:
        logger.error(f"Entitlements error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load entitlements"
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


@router.get("/compliance-pack/{property_id}/preview")
async def get_compliance_pack_preview(request: Request, property_id: str):
    """Get a preview of what the compliance pack will contain."""
    user = await client_route_guard(request)
    
    try:
        from services.compliance_pack import compliance_pack_service
        
        preview = await compliance_pack_service.get_pack_preview(
            property_id=property_id,
            client_id=user["client_id"]
        )
        return preview
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Compliance pack preview error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate preview"
        )


@router.get("/compliance-pack/{property_id}/download")
async def download_compliance_pack(
    request: Request, 
    property_id: str,
    include_expired: bool = False
):
    """Download a compliance pack PDF for a property.
    
    Requires Portfolio plan or higher. TEMP: gated by reports_pdf until Step 5 canonical key.
    """
    user = await client_route_guard(request)
    try:
        # TEMP Step 2: compliance_packs has no plan_registry key; gate by reports_pdf (Portfolio+)
        from services.plan_registry import plan_registry

        allowed, error_msg, error_details = await plan_registry.enforce_feature(
            user["client_id"],
            "reports_pdf"
        )
        if not allowed:
            detail = {
                "error_code": (error_details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
                "message": error_msg,
                "upgrade_required": True,
                **(error_details or {}),
            }
            detail["feature"] = "compliance_packs"  # preserve response shape
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

        from services.compliance_pack import compliance_pack_service
        
        pdf_bytes = await compliance_pack_service.generate_compliance_pack(
            property_id=property_id,
            client_id=user["client_id"],
            include_expired=include_expired,
            requested_by=user["portal_user_id"],
            requested_by_role=user.get("role")
        )
        
        # Get property for filename
        db = database.get_db()
        property_doc = await db.properties.find_one(
            {"property_id": property_id},
            {"_id": 0, "nickname": 1, "postcode": 1}
        )
        
        filename = f"compliance_pack_{property_doc.get('postcode', property_id)}.pdf"
        if property_doc and property_doc.get('nickname'):
            filename = f"compliance_pack_{property_doc['nickname'].replace(' ', '_')}.pdf"
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Compliance pack download error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate compliance pack"
        )


@router.post("/tenants/invite")
async def invite_tenant(request: Request):
    """
    Invite a tenant to view property compliance status.
    
    Creates a ROLE_TENANT user with read-only access.
    Gated: Portfolio and Professional only (tenant_portal).
    """
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "tenant_portal")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "tenant_portal", "upgrade_required": True}
        )
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
    """List all tenants invited by this client. Gated: Portfolio+ (tenant_portal)."""
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "tenant_portal")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "tenant_portal", "upgrade_required": True}
        )
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
    """Assign a tenant to a property. Gated: Portfolio+ (tenant_portal)."""
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "tenant_portal")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "tenant_portal", "upgrade_required": True}
        )
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
    """Remove a tenant's assignment to a property. Gated: Portfolio+ (tenant_portal)."""
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "tenant_portal")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "tenant_portal", "upgrade_required": True}
        )
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
    """Revoke a tenant's access entirely (disable account). Gated: Portfolio+ (tenant_portal)."""
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "tenant_portal")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "tenant_portal", "upgrade_required": True}
        )
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
    """Resend invitation email to a tenant. Gated: Portfolio+ (tenant_portal)."""
    user = await client_route_guard(request)
    from services.plan_registry import plan_registry
    allowed, error_msg, error_details = await plan_registry.enforce_feature(user["client_id"], "tenant_portal")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_details or {"message": error_msg, "feature": "tenant_portal", "upgrade_required": True}
        )
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


# ============================================================================
# BRANDING SETTINGS (White-Label)
# ============================================================================

@router.get("/branding")
async def get_branding_settings(request: Request):
    """Get the client's branding settings.
    
    Returns current branding configuration for white-label customization.
    Plan gating: Requires Portfolio plan (PLAN_6_15) for full customization.
    """
    from services.plan_registry import plan_registry
    from datetime import datetime, timezone

    user = await client_route_guard(request)
    try:
        db = database.get_db()
        client_id = user["client_id"]

        # Canonical: white_label -> white_label_reports (plan_registry)
        allowed, error_msg, error_details = await plan_registry.enforce_feature(
            client_id,
            "white_label_reports"
        )
        
        # Get existing branding settings
        branding = await db.branding_settings.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        # Get client info for defaults
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "company_name": 1, "email": 1, "phone": 1}
        )
        
        # Return defaults if no branding set
        if not branding:
            branding = {
                "client_id": client_id,
                "company_name": client.get("company_name"),
                "logo_url": None,
                "favicon_url": None,
                "primary_color": "#0B1D3A",
                "secondary_color": "#00B8A9",
                "accent_color": "#FFB800",
                "text_color": "#1F2937",
                "report_header_text": None,
                "report_footer_text": None,
                "include_pleerity_branding": True,
                "email_from_name": None,
                "email_reply_to": client.get("email"),
                "contact_email": client.get("email"),
                "contact_phone": client.get("phone"),
                "website_url": None,
                "is_default": True
            }
        
        # Add feature availability info
        branding["feature_enabled"] = allowed
        if not allowed:
            branding["upgrade_message"] = error_msg
            branding["upgrade_required"] = True
        
        return branding
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get branding settings error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load branding settings"
        )


@router.put("/branding")
async def update_branding_settings(request: Request):
    """Update the client's branding settings.
    
    Plan gating: Requires Professional plan (white_label_reports).
    """
    from services.plan_registry import plan_registry
    from models import AuditAction
    from utils.audit import create_audit_log
    from datetime import datetime, timezone

    user = await client_route_guard(request)
    body = await request.json()
    try:
        db = database.get_db()
        client_id = user["client_id"]

        # Canonical: white_label -> white_label_reports (plan_registry)
        allowed, error_msg, error_details = await plan_registry.enforce_feature(
            client_id,
            "white_label_reports"
        )
        if not allowed:
            detail = {
                "error_code": (error_details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
                "message": error_msg,
                "upgrade_required": True,
                **(error_details or {}),
            }
            detail["feature"] = "white_label"  # preserve response shape
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

        # Allowed fields to update
        allowed_fields = [
            "company_name", "logo_url", "favicon_url",
            "primary_color", "secondary_color", "accent_color", "text_color",
            "report_header_text", "report_footer_text", "include_pleerity_branding",
            "email_from_name", "email_reply_to",
            "contact_email", "contact_phone", "website_url"
        ]
        
        # Build update document
        update_doc = {
            "client_id": client_id,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        for field in allowed_fields:
            if field in body:
                # Validate colors
                if field.endswith("_color") and body[field]:
                    color = body[field]
                    if not (color.startswith("#") and len(color) in [4, 7]):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid color format for {field}. Use hex format (e.g., #0B1D3A)"
                        )
                update_doc[field] = body[field]
        
        # Upsert branding settings
        await db.branding_settings.update_one(
            {"client_id": client_id},
            {"$set": update_doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.SETTINGS_UPDATED,
            client_id=client_id,
            actor_id=user.get("portal_user_id"),
            metadata={"updated_fields": [k for k in update_doc.keys() if k not in ["client_id", "updated_at"]]}
        )
        
        logger.info(f"Branding settings updated for client {client_id}")
        
        # Return updated settings
        updated = await db.branding_settings.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        updated["feature_enabled"] = True
        
        return updated
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update branding settings error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update branding settings"
        )


@router.post("/branding/reset")
async def reset_branding_settings(request: Request):
    """Reset branding settings to defaults.
    
    Plan gating: Requires Professional plan (white_label_reports).
    """
    from services.plan_registry import plan_registry
    from models import AuditAction
    from utils.audit import create_audit_log

    user = await client_route_guard(request)
    try:
        db = database.get_db()
        client_id = user["client_id"]

        # Canonical: white_label -> white_label_reports (plan_registry)
        allowed, error_msg, error_details = await plan_registry.enforce_feature(
            client_id,
            "white_label_reports"
        )
        if not allowed:
            detail = {
                "error_code": (error_details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
                "message": error_msg,
                "upgrade_required": True,
                **(error_details or {}),
            }
            detail["feature"] = "white_label"  # preserve response shape
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

        # Delete branding settings
        result = await db.branding_settings.delete_one({"client_id": client_id})
        
        # Audit log
        await create_audit_log(
            action=AuditAction.SETTINGS_UPDATED,
            client_id=client_id,
            actor_id=user.get("portal_user_id"),
            metadata={"action": "branding_reset"}
        )
        
        logger.info(f"Branding settings reset for client {client_id}")
        
        return {"message": "Branding settings reset to defaults", "deleted": result.deleted_count > 0}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset branding settings error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset branding settings"
        )

