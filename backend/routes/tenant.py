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
from middleware import tenant_route_guard
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional
from models import AuditAction
from utils.audit import create_audit_log
from services.requirement_code_registry import normalize_requirement_code_strict
from services.compliance_rules_registry import jurisdiction_attribution_for_property
from utils.expiry_utils import get_computed_status, get_effective_expiry_date
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


class ReportIssueBody(BaseModel):
    property_id: str
    description: str
    category: Optional[str] = None
    photos: Optional[list] = None


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
    
    client_doc = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "default_jurisdiction": 1},
    ) or {}

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
            "compliance_status": 1,
            "jurisdiction": 1,
        }
    ).to_list(100)
    
    # Get requirements for these properties
    property_ids = [p["property_id"] for p in properties]
    requirements = await db.requirements.find(
        {"property_id": {"$in": property_ids}, "client_id": client_id},
        {"_id": 0},
    ).to_list(1000)
    props_full = await db.properties.find(
        {"client_id": client_id, "property_id": {"$in": property_ids}},
        {"_id": 0},
    ).to_list(200)
    from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

    requirements = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=requirements,
        client_doc=client_doc,
        properties=props_full,
    )

    prop_by_id = {p["property_id"]: p for p in properties if p.get("property_id")}

    # Build simplified response
    property_summaries = []
    for prop in properties:
        att = jurisdiction_attribution_for_property(prop, client_doc)
        prop_reqs = [r for r in requirements if r.get("property_id") == prop["property_id"]]
        pd = prop_by_id.get(prop["property_id"])

        # Simplify requirement info for tenants
        cert_summary = []
        for req in prop_reqs:
            cs = get_computed_status(req, property_doc=pd, client_doc=client_doc) or (req.get("status") or "UNKNOWN")
            eff = get_effective_expiry_date(req)
            exp_s = eff.date().isoformat() if eff and hasattr(eff, "date") else (
                str(req.get("due_date") or "")[:10] if req.get("due_date") else "N/A"
            )
            cert_summary.append({
                "type": req.get("requirement_type", "Unknown"),
                "description": req.get("description", ""),
                "status": cs,
                "expiry": exp_s if exp_s else "N/A",
            })
        
        property_summaries.append({
            "property_id": prop["property_id"],
            "address": f"{prop.get('address_line_1', '')}, {prop.get('city', '')} {prop.get('postcode', '')}",
            "property_type": prop.get("property_type", "N/A"),
            "compliance_status": prop.get("compliance_status", "UNKNOWN"),
            "effective_jurisdiction_label": att["effective_jurisdiction_label"],
            "jurisdiction_source": att["jurisdiction_source"],
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
    
    client_doc = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "default_jurisdiction": 1},
    ) or {}

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
            "compliance_status": 1,
            "jurisdiction": 1,
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
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0},
    ).to_list(100)
    prop_full = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0},
    ) or property_doc
    from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

    requirements = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=requirements,
        client_doc=client_doc,
        properties=[prop_full],
    )

    # Format certificates for tenant view
    certificates = []
    for req in requirements:
        cs = get_computed_status(req, property_doc=prop_full, client_doc=client_doc) or (
            req.get("status") or "UNKNOWN"
        )
        status_color = "gray"
        if cs == "COMPLIANT" or cs == "NOT_REQUIRED":
            status_color = "green"
        elif cs == "EXPIRING_SOON":
            status_color = "yellow"
        elif cs in ("OVERDUE", "EXPIRED"):
            status_color = "red"
        elif cs in ("PENDING", "UNKNOWN_DATE"):
            status_color = "blue"

        eff = get_effective_expiry_date(req)
        exp_line = (
            eff.date().isoformat()
            if eff and hasattr(eff, "date")
            else (req.get("due_date", "N/A")[:10] if req.get("due_date") else "Not Set")
        )

        certificates.append({
            "type": req.get("requirement_type", "Unknown"),
            "description": req.get("description", ""),
            "status": cs,
            "status_color": status_color,
            "expiry_date": exp_line,
            "renewal_frequency": f"Every {req.get('frequency_days', 0)} days" if req.get("frequency_days") else "N/A"
        })
    
    att = jurisdiction_attribution_for_property(prop_full, client_doc)
    return {
        "property": {
            "property_id": property_id,
            "address": f"{prop_full.get('address_line_1', '')}, {prop_full.get('city', '')} {prop_full.get('postcode', '')}",
            "type": prop_full.get("property_type", "N/A"),
            "compliance_status": prop_full.get("compliance_status", "UNKNOWN"),
            "effective_jurisdiction_label": att["effective_jurisdiction_label"],
            "jurisdiction_source": att["jurisdiction_source"],
        },
        "certificates": certificates,
        "note": "This view shows safety checks for your rental property. Renewals are your landlord's responsibility—contact them if you need an update."
    }


@router.get("/compliance-pack/{property_id}")
async def get_tenant_compliance_pack(request: Request, property_id: str):
    """Download compliance pack for a property the tenant is assigned to.
    
    Tenants have included access to compliance packs for their assigned properties.
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
            include_expired=False,  # For tenants the pack service still lists overdue rows for transparency
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


@router.post("/compliance/deliveries/{delivery_id}/acknowledge")
async def acknowledge_tenant_compliance_delivery(request: Request, delivery_id: str):
    """Tenant confirms receipt of a governed compliance delivery (distinct from provider open pixels)."""
    user = await tenant_route_guard(request)
    client_id = user.get("client_id")
    tenant_id = user.get("portal_user_id")
    if not client_id or not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required")
    try:
        from services.tenant_delivery_reconciliation import acknowledge_tenant_delivery_for_tenant

        out = await acknowledge_tenant_delivery_for_tenant(
            delivery_id=delivery_id.strip(),
            tenant_portal_user_id=tenant_id,
            client_id=client_id,
        )
    except ValueError as ve:
        code = str(ve)
        if code == "delivery_not_found":
            raise HTTPException(status_code=404, detail="Delivery not found")
        if code == "tenant_not_assigned":
            raise HTTPException(status_code=403, detail="Not assigned to this property")
        raise HTTPException(status_code=400, detail=code)
    return out


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

    canon_code, err = normalize_requirement_code_strict(data.certificate_type)
    if err or not canon_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported certificate_type {data.certificate_type!r}; use a supported requirement code",
        )

    now = datetime.now(timezone.utc)
    existing_req = await db.requirements.find_one(
        {
            "client_id": client_id,
            "property_id": data.property_id,
            "$or": [
                {"requirement_code": canon_code},
                {"requirement_type": canon_code},
            ],
        },
        {"_id": 0, "requirement_id": 1},
    )
    requirement_id = (existing_req or {}).get("requirement_id")
    if not requirement_id:
        requirement_id = str(uuid.uuid4())
        due_far = now.replace(microsecond=0).isoformat()
        await db.requirements.insert_one(
            {
                "requirement_id": requirement_id,
                "client_id": client_id,
                "property_id": data.property_id,
                "requirement_type": canon_code,
                "requirement_code": canon_code,
                "description": canon_code.replace("_", " ").title(),
                "frequency_days": 0,
                "due_date": due_far,
                "status": "PENDING",
                "created_at": due_far,
                "updated_at": due_far,
            }
        )

    request_id = str(uuid.uuid4())
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
        "requirement_code": canon_code,
        "requirement_id": requirement_id,
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
            "requirement_code": canon_code,
            "requirement_id": requirement_id,
            "tenant_email": user.get("email"),
            "landlord_email": landlord_email,
        },
    )
    return {"request_id": request_id, "status": "PENDING", "requirement_id": requirement_id, "requirement_code": canon_code}


@router.post("/report-issue")
async def report_issue(request: Request):
    """Report a maintenance issue for an assigned property. Creates a maintenance issue (with triage); landlord sees it in Operations → Issues. Requires MAINTENANCE_WORKFLOWS."""
    body = await request.json()
    try:
        data = ReportIssueBody(
            property_id=(body.get("property_id") or "").strip(),
            description=(body.get("description") or "").strip(),
            category=body.get("category"),
            photos=body.get("photos"),
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="property_id and description are required")
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
    from services import maintenance_issues_service
    tenant_name = user.get("full_name") or user.get("email") or "Tenant"
    doc = await maintenance_issues_service.create_issue(
        client_id=client_id,
        property_id=data.property_id,
        description=data.description,
        source=maintenance_issues_service.SOURCE_TENANT_REQUEST,
        category=data.category,
        asset_id=None,
        reporter_name=tenant_name,
        reporter_contact=(user.get("email") or "").strip().lower() or None,
        reported_urgency=None,
        photos=data.photos or [],
    )
    await create_audit_log(
        action=AuditAction.TENANT_ISSUE_REPORTED,
        client_id=client_id,
        actor_id=user.get("portal_user_id"),
        resource_type="maintenance_issue",
        resource_id=doc.get("issue_id"),
        metadata={"property_id": data.property_id, "source": "tenant_request", "tenant_email": user.get("email")},
    )
    return {"issue_id": doc["issue_id"], "status": doc["status"], "message": "Issue reported. Your landlord will be notified."}


@router.get("/requests")
async def get_tenant_requests(request: Request):
    """List the authenticated tenant's certificate requests (for their assigned properties)."""
    user = await tenant_route_guard(request)
    db = database.get_db()
    tenant_id = user.get("portal_user_id")
    cursor = db.tenant_requests.find(
        {"tenant_id": tenant_id},
        {
            "_id": 0,
            "request_id": 1,
            "property_id": 1,
            "property_address": 1,
            "certificate_type": 1,
            "requirement_code": 1,
            "requirement_id": 1,
            "message": 1,
            "status": 1,
            "created_at": 1,
        },
    ).sort("created_at", -1)
    requests = await cursor.to_list(100)
    for r in requests:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
    return {"requests": requests}


def _tenant_issue_lifecycle_phase(issue_status: str, wo_status: Optional[str] = None) -> str:
    """Map landlord issue/WO state to tenant-safe lifecycle labels."""
    status = (issue_status or "").lower()
    wo = (wo_status or "").upper()
    if status in ("closed", "cancelled", "resolved"):
        return "completed"
    if status in ("in_progress", "investigating", "ready_for_work_order"):
        return "in_progress"
    if wo in ("IN_PROGRESS", "ACCEPTED", "ASSIGNED", "COMPLETED"):
        return "completed" if wo == "COMPLETED" else "in_progress"
    if status in ("monitoring",):
        return "acknowledged"
    return "reported"


@router.get("/reported-issues")
async def get_tenant_reported_issues(request: Request):
    """Bounded tenant-safe projection of maintenance issues this tenant reported."""
    user = await tenant_route_guard(request)
    if user.get("role") != "ROLE_TENANT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant access required",
        )
    db = database.get_db()
    client_id = user.get("client_id")
    tenant_id = user.get("portal_user_id")
    tenant_email = (user.get("email") or "").strip().lower()
    if not tenant_email:
        pu = await db.portal_users.find_one(
            {"portal_user_id": tenant_id},
            {"_id": 0, "auth_email": 1, "email": 1},
        )
        tenant_email = ((pu or {}).get("auth_email") or (pu or {}).get("email") or "").strip().lower()
    if not tenant_email:
        return {"issues": []}

    tenant_properties = await db.tenant_assignments.find(
        {"tenant_id": tenant_id},
        {"_id": 0, "property_id": 1},
    ).to_list(100)
    q: dict = {
        "client_id": client_id,
        "source": {"$in": ["tenant_request", "tenant"]},
        "reporter_contact": tenant_email,
    }
    if tenant_properties:
        q["property_id"] = {"$in": [tp["property_id"] for tp in tenant_properties]}

    rows = await db.maintenance_issues.find(
        q,
        {
            "_id": 0,
            "issue_id": 1,
            "property_id": 1,
            "description": 1,
            "status": 1,
            "category": 1,
            "created_at": 1,
            "updated_at": 1,
            "closed_at": 1,
        },
    ).sort("created_at", -1).to_list(50)

    out = []
    for row in rows:
        wo = await db.work_orders.find_one(
            {"issue_id": row.get("issue_id"), "client_id": client_id},
            {"_id": 0, "status": 1},
        )
        wo_status = (wo or {}).get("status")
        phase = _tenant_issue_lifecycle_phase(row.get("status"), wo_status)
        desc = (row.get("description") or "").strip()
        if len(desc) > 200:
            desc = desc[:197] + "..."
        created = row.get("created_at")
        updated = row.get("updated_at")
        out.append(
            {
                "issue_id": row.get("issue_id"),
                "property_id": row.get("property_id"),
                "summary": desc,
                "category": row.get("category"),
                "lifecycle_phase": phase,
                "landlord_status": row.get("status"),
                "created_at": created.isoformat() if hasattr(created, "isoformat") else created,
                "updated_at": updated.isoformat() if hasattr(updated, "isoformat") else updated,
            }
        )
    return {"issues": out}


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
        created_from="tenant_request",
        triggering_rule="tenant_report_maintenance",
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
