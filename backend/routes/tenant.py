"""Tenant Routes - Read-only access to property compliance status.

ROLE_TENANT has STRICTLY LIMITED permissions:
✅ View property compliance status (GREEN/AMBER/RED)
✅ View certificate status and expiry dates
✅ View basic summaries
✅ Download compliance pack for assigned properties
✅ Request certificate updates from landlord
✅ Contact landlord via messaging

❌ No document uploads
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
import uuid

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


@router.get("/compliance-pack/{property_id}")
async def get_tenant_compliance_pack(request: Request, property_id: str):
    """Download compliance pack for a property the tenant is assigned to.
    
    Tenants get free access to compliance packs for their assigned properties.
    """
    from fastapi.responses import StreamingResponse
    import io
    
    user = await tenant_route_guard(request)
    db = database.get_db()
    
    client_id = user.get("client_id")
    tenant_id = user.get("portal_user_id")
    
    # Verify property access
    property_doc = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0}
    )
    
    if not property_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    # Check tenant assignment
    if user.get("role") == "ROLE_TENANT":
        assignment = await db.tenant_assignments.find_one({
            "tenant_id": tenant_id,
            "property_id": property_id
        })
        all_assignments = await db.tenant_assignments.count_documents({"tenant_id": tenant_id})
        if all_assignments > 0 and not assignment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not assigned to this property"
            )
    
    try:
        from services.compliance_pack import compliance_pack_service
        
        pdf_bytes = await compliance_pack_service.generate_compliance_pack(
            property_id=property_id,
            client_id=client_id,
            include_expired=False,  # Tenants only see valid certificates
            requested_by=tenant_id,
            requested_by_role="ROLE_TENANT"
        )
        
        filename = f"compliance_pack_{property_doc.get('postcode', property_id)}.pdf"
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    
    except Exception as e:
        logger.error(f"Tenant compliance pack error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate compliance pack"
        )


@router.post("/request-certificate")
async def request_certificate_update(request: Request):
    """Request landlord to provide an updated certificate.
    
    Creates a request that the landlord will see in their dashboard.
    """
    user = await tenant_route_guard(request)
    db = database.get_db()
    
    try:
        body = await request.json()
        property_id = body.get("property_id")
        certificate_type = body.get("certificate_type")
        message = body.get("message", "")
        
        if not property_id or not certificate_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="property_id and certificate_type are required"
            )
        
        # Verify property access
        client_id = user.get("client_id")
        tenant_id = user.get("portal_user_id")
        
        property_doc = await db.properties.find_one(
            {"property_id": property_id, "client_id": client_id},
            {"_id": 0}
        )
        
        if not property_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found"
            )
        
        # Check tenant assignment
        if user.get("role") == "ROLE_TENANT":
            assignment = await db.tenant_assignments.find_one({
                "tenant_id": tenant_id,
                "property_id": property_id
            })
            all_assignments = await db.tenant_assignments.count_documents({"tenant_id": tenant_id})
            if all_assignments > 0 and not assignment:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not assigned to this property"
                )
        
        # Create certificate request
        import uuid
        request_id = f"req-{uuid.uuid4().hex[:12]}"
        
        certificate_request = {
            "request_id": request_id,
            "client_id": client_id,
            "property_id": property_id,
            "tenant_id": tenant_id,
            "tenant_name": user.get("full_name", user.get("email")),
            "tenant_email": user.get("email") or user.get("auth_email"),
            "certificate_type": certificate_type,
            "message": message[:500] if message else "",
            "status": "PENDING",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.certificate_requests.insert_one(certificate_request)
        
        # Notify landlord (try to send email)
        try:
            from services.email_service import email_service
            from models import EmailTemplateAlias
            
            client = await db.clients.find_one(
                {"client_id": client_id},
                {"_id": 0, "email": 1, "full_name": 1}
            )
            
            if client and client.get("email"):
                await email_service.send_email(
                    recipient=client["email"],
                    template_alias=EmailTemplateAlias.REMINDER,
                    template_model={
                        "subject": "Certificate Request from Tenant",
                        "message": f"Your tenant {user.get('full_name', 'A tenant')} has requested an updated {certificate_type.replace('_', ' ')} certificate for property {property_doc.get('address_line_1', '')}.\n\nMessage: {message or 'No message provided.'}\n\nPlease log into Compliance Vault Pro to respond.",
                        "company_name": "Pleerity Enterprise Ltd"
                    },
                    client_id=client_id,
                    subject=f"Certificate Request from Tenant: {certificate_type.replace('_', ' ')}"
                )
        except Exception as email_err:
            logger.warning(f"Failed to send certificate request email: {email_err}")
        
        logger.info(f"Certificate request created: {request_id} by tenant {tenant_id}")
        
        return {
            "message": "Certificate request submitted successfully",
            "request_id": request_id,
            "note": "Your landlord has been notified and will respond soon."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Certificate request error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit request"
        )


@router.get("/requests")
async def get_tenant_requests(request: Request):
    """Get list of certificate requests submitted by this tenant."""
    user = await tenant_route_guard(request)
    db = database.get_db()
    
    try:
        tenant_id = user.get("portal_user_id")
        
        requests = await db.certificate_requests.find(
            {"tenant_id": tenant_id},
            {"_id": 0}
        ).sort("created_at", -1).to_list(50)
        
        return {"requests": requests}
    
    except Exception as e:
        logger.error(f"Get tenant requests error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load requests"
        )


@router.post("/contact-landlord")
async def contact_landlord(request: Request):
    """Send a message to the landlord.
    
    Simple messaging for tenants to communicate with their landlord.
    """
    user = await tenant_route_guard(request)
    db = database.get_db()
    
    try:
        body = await request.json()
        property_id = body.get("property_id")
        subject = body.get("subject", "Message from Tenant")
        message = body.get("message", "")
        
        if not property_id or not message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="property_id and message are required"
            )
        
        if len(message) > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message too long (max 1000 characters)"
            )
        
        # Verify property access
        client_id = user.get("client_id")
        tenant_id = user.get("portal_user_id")
        
        property_doc = await db.properties.find_one(
            {"property_id": property_id, "client_id": client_id},
            {"_id": 0, "address_line_1": 1, "postcode": 1}
        )
        
        if not property_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found"
            )
        
        # Get landlord info
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "email": 1, "full_name": 1}
        )
        
        if not client or not client.get("email"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to contact landlord"
            )
        
        # Send email to landlord
        from services.email_service import email_service
        from models import EmailTemplateAlias
        
        property_address = f"{property_doc.get('address_line_1', '')}, {property_doc.get('postcode', '')}"
        
        await email_service.send_email(
            recipient=client["email"],
            template_alias=EmailTemplateAlias.REMINDER,
            template_model={
                "subject": subject,
                "message": f"Message from: {user.get('full_name', 'Your tenant')}\nProperty: {property_address}\n\n{message}\n\n---\nReply to this email or log into Compliance Vault Pro to respond.",
                "company_name": "Pleerity Enterprise Ltd"
            },
            client_id=client_id,
            subject=f"[Tenant Message] {subject}"
        )
        
        logger.info(f"Tenant message sent from {tenant_id} to landlord {client_id}")
        
        return {
            "message": "Message sent successfully",
            "note": "Your landlord will receive your message via email."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Contact landlord error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message"
        )
