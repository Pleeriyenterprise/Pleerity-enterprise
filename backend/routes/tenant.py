"""Tenant Routes - View compliance + optional messaging to landlord.

ROLE_TENANT can:
✅ View property compliance status (GREEN/AMBER/RED)
✅ View certificate status and expiry dates
✅ Download compliance pack for assigned properties
✅ Contact landlord (message stored, email sent to landlord)
✅ Request certificate (request stored, email sent to landlord)

Landlord is notified by email; messages/requests are stored for audit and landlord view.
"""
from fastapi import APIRouter, HTTPException, Request, status
from database import database
from middleware import client_route_guard
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional
from models import AuditAction
from utils.audit import create_audit_log
import logging
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tenant", tags=["tenant"])


class ContactLandlordBody(BaseModel):
    property_id: str
    subject: str
    message: str


class RequestCertificateBody(BaseModel):
    property_id: str
    certificate_type: str
    message: Optional[str] = None


class ReportMaintenanceBody(BaseModel):
    property_id: str
    description: str
    category: Optional[str] = None


async def _ensure_tenant_property_access(request: Request, property_id: str):
    """Verify the authenticated tenant has access to the property. Returns (db, user, client_id)."""
    user = await tenant_route_guard(request)
    db = database.get_db()
    client_id = user.get("client_id")
    tenant_id = user.get("portal_user_id")
    property_doc = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0, "property_id": 1, "address_line_1": 1, "city": 1, "postcode": 1},
    )
    if not property_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found or access denied",
        )
    if user.get("role") == "ROLE_TENANT":
        assignment = await db.tenant_assignments.find_one({
            "tenant_id": tenant_id,
            "property_id": property_id,
        })
        all_assignments = await db.tenant_assignments.count_documents({"tenant_id": tenant_id})
        if all_assignments > 0 and not assignment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not assigned to this property",
            )
    return db, user, client_id, property_doc


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
    """Submit a certificate request for a property. Stored and landlord notified by email."""
    body = await request.json()
    try:
        data = RequestCertificateBody(
            property_id=body.get("property_id", ""),
            certificate_type=body.get("certificate_type", ""),
            message=body.get("message"),
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid body: property_id and certificate_type required")
    if not data.property_id or not data.certificate_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="property_id and certificate_type are required")

    db, user, client_id, property_doc = await _ensure_tenant_property_access(request, data.property_id)
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "email": 1, "full_name": 1, "contact_email": 1})
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    landlord_email = (client.get("email") or client.get("contact_email") or "").strip()
    if not landlord_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Landlord has no email on file")

    request_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    tenant_name = user.get("full_name", user.get("email", "Tenant"))
    address = f"{property_doc.get('address_line_1', '')}, {property_doc.get('city', '')} {property_doc.get('postcode', '')}".strip(", ")
    doc = {
        "request_id": request_id,
        "client_id": client_id,
        "tenant_id": user.get("portal_user_id"),
        "tenant_email": user.get("email", ""),
        "tenant_name": tenant_name,
        "property_id": data.property_id,
        "property_address": address,
        "certificate_type": data.certificate_type,
        "message": (data.message or "").strip(),
        "status": "PENDING",
        "created_at": now,
    }
    await db.tenant_requests.insert_one(doc)

    email_body = (
        f"A tenant has requested a certificate update via the tenant portal.<br><br>"
        f"<strong>Tenant:</strong> {tenant_name}<br>"
        f"<strong>Property:</strong> {address}<br>"
        f"<strong>Certificate type:</strong> {data.certificate_type}<br>"
    )
    if data.message:
        email_body += f"<br><strong>Message:</strong><br>{data.message.replace(chr(10), '<br>')}"
    from services.notification_orchestrator import notification_orchestrator
    idempotency_key = f"{client_id}_TENANT_REQUEST_{request_id}"
    result = await notification_orchestrator.send(
        template_key="ADMIN_MANUAL",
        client_id=client_id,
        context={
            "client_name": client.get("full_name", "Client"),
            "subject": "Certificate request from tenant",
            "message": email_body,
            "customer_reference": client.get("customer_reference", "N/A"),
            "company_name": "Pleerity Enterprise Ltd",
            "tagline": "AI-Driven Solutions & Compliance",
        },
        idempotency_key=idempotency_key,
        event_type="tenant_request_certificate",
    )
    if result.outcome not in ("sent", "duplicate_ignored"):
        logger.warning("Tenant request certificate email failed: %s", result.error_message)

    await create_audit_log(
        action=AuditAction.TENANT_REQUEST_CERTIFICATE,
        client_id=client_id,
        actor_id=user.get("portal_user_id"),
        resource_type="tenant_request",
        resource_id=request_id,
        metadata={
            "property_id": data.property_id,
            "certificate_type": data.certificate_type,
            "tenant_email": user.get("email"),
            "landlord_email": landlord_email,
        },
    )
    return {"request_id": request_id, "status": "PENDING"}


@router.post("/report-maintenance")
async def report_maintenance(request: Request):
    """Report a maintenance issue for an assigned property. Creates a work order. Requires MAINTENANCE_WORKFLOWS for the landlord."""
    body = await request.json()
    property_id = (body.get("property_id") or "").strip()
    description = (body.get("description") or "").strip()
    if not property_id or not description:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="property_id and description are required")
    db, user, client_id, property_doc = await _ensure_tenant_property_access(request, property_id)
    from services.ops_compliance_feature_flags import get_effective_flags, MAINTENANCE_WORKFLOWS
    flags = await get_effective_flags(client_id)
    if not flags.get(MAINTENANCE_WORKFLOWS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Maintenance reporting is not enabled for this property's account",
        )
    from services import maintenance_service
    severity = maintenance_service._categorise_severity(description)
    doc = await maintenance_service.create_work_order(
        client_id=client_id,
        property_id=property_id,
        description=description,
        source=maintenance_service.SOURCE_TENANT_REQUEST,
        reporter_id=user.get("portal_user_id"),
        category=body.get("category"),
        severity=body.get("severity") or severity,
    )
    await create_audit_log(
        action=AuditAction.TENANT_REPORT_MAINTENANCE,
        client_id=client_id,
        actor_id=user.get("portal_user_id"),
        resource_type="work_order",
        resource_id=doc.get("work_order_id"),
        metadata={"property_id": property_id, "source": "tenant_request"},
    )
    return doc


@router.get("/requests")
async def get_tenant_requests(request: Request):
    """List the authenticated tenant's certificate requests (for their assigned properties)."""
    user = await tenant_route_guard(request)
    db = database.get_db()
    tenant_id = user.get("portal_user_id")
    cursor = db.tenant_requests.find(
        {"tenant_id": tenant_id},
        {"_id": 0, "request_id": 1, "property_id": 1, "property_address": 1, "certificate_type": 1, "message": 1, "status": 1, "created_at": 1},
    ).sort("created_at", -1)
    requests = await cursor.to_list(100)
    for r in requests:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
    return {"requests": requests}


@router.post("/contact-landlord")
async def contact_landlord(request: Request):
    """Send a message to the landlord for a property. Stored and landlord notified by email."""
    body = await request.json()
    try:
        data = ContactLandlordBody(
            property_id=body.get("property_id", ""),
            subject=(body.get("subject") or "").strip(),
            message=(body.get("message") or "").strip(),
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid body: property_id, subject and message required")
    if not data.property_id or not data.subject or not data.message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="property_id, subject and message are required")

    db, user, client_id, property_doc = await _ensure_tenant_property_access(request, data.property_id)
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "email": 1, "full_name": 1, "contact_email": 1})
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    landlord_email = (client.get("email") or client.get("contact_email") or "").strip()
    if not landlord_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Landlord has no email on file")

    message_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    tenant_name = user.get("full_name", user.get("email", "Tenant"))
    address = f"{property_doc.get('address_line_1', '')}, {property_doc.get('city', '')} {property_doc.get('postcode', '')}".strip(", ")
    doc = {
        "message_id": message_id,
        "client_id": client_id,
        "tenant_id": user.get("portal_user_id"),
        "tenant_email": user.get("email", ""),
        "tenant_name": tenant_name,
        "property_id": data.property_id,
        "property_address": address,
        "subject": data.subject,
        "message": data.message,
        "created_at": now,
    }
    await db.tenant_messages.insert_one(doc)

    email_body = (
        f"Message from your tenant via the tenant portal.<br><br>"
        f"<strong>From:</strong> {tenant_name}<br>"
        f"<strong>Property:</strong> {address}<br>"
        f"<strong>Subject:</strong> {data.subject}<br><br>"
        f"{data.message.replace(chr(10), '<br>')}"
    )
    from services.notification_orchestrator import notification_orchestrator
    idempotency_key = f"{client_id}_TENANT_CONTACT_{message_id}"
    result = await notification_orchestrator.send(
        template_key="ADMIN_MANUAL",
        client_id=client_id,
        context={
            "client_name": client.get("full_name", "Client"),
            "subject": data.subject,
            "message": email_body,
            "customer_reference": client.get("customer_reference", "N/A"),
            "company_name": "Pleerity Enterprise Ltd",
            "tagline": "AI-Driven Solutions & Compliance",
        },
        idempotency_key=idempotency_key,
        event_type="tenant_contact_landlord",
    )
    if result.outcome not in ("sent", "duplicate_ignored"):
        logger.warning("Tenant contact landlord email failed: %s", result.error_message)

    await create_audit_log(
        action=AuditAction.TENANT_CONTACT_LANDLORD,
        client_id=client_id,
        actor_id=user.get("portal_user_id"),
        resource_type="tenant_message",
        resource_id=message_id,
        metadata={
            "property_id": data.property_id,
            "subject": data.subject,
            "tenant_email": user.get("email"),
            "landlord_email": landlord_email,
        },
    )
    return {"message_id": message_id}


@router.post("/report-maintenance")
async def report_maintenance(request: Request):
    """Report a maintenance issue for an assigned property. Creates a work order. Requires MAINTENANCE_WORKFLOWS for the landlord."""
    body = await request.json()
    try:
        data = ReportMaintenanceBody(
            property_id=body.get("property_id", ""),
            description=(body.get("description") or "").strip(),
            category=body.get("category"),
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid body: property_id and description required")
    if not data.property_id or not data.description:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="property_id and description are required")

    db, user, client_id, property_doc = await _ensure_tenant_property_access(request, data.property_id)
    from services.ops_compliance_feature_flags import get_effective_flags, MAINTENANCE_WORKFLOWS
    flags = await get_effective_flags(client_id)
    if not flags.get(MAINTENANCE_WORKFLOWS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Maintenance reporting is not enabled for this property's account",
        )

    from services import maintenance_service
    severity = maintenance_service._categorise_severity(data.description)
    doc = await maintenance_service.create_work_order(
        client_id=client_id,
        property_id=data.property_id,
        description=data.description,
        source=maintenance_service.SOURCE_TENANT_REQUEST,
        reporter_id=user.get("portal_user_id"),
        category=data.category or maintenance_service.CATEGORY_GENERAL,
        severity=severity,
    )
    await create_audit_log(
        action=AuditAction.TENANT_REPORT_MAINTENANCE,
        client_id=client_id,
        actor_id=user.get("portal_user_id"),
        resource_type="work_order",
        resource_id=doc["work_order_id"],
        metadata={"property_id": data.property_id, "source": "tenant_request"},
    )
    return {"work_order_id": doc["work_order_id"], "status": doc["status"]}
