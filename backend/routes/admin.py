from fastapi import APIRouter, HTTPException, Request, Depends, status
from database import database
from middleware import admin_route_guard
from models import AuditAction, PasswordToken
from utils.audit import create_audit_log
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(admin_route_guard)])

@router.get("/dashboard")
async def get_admin_dashboard(request: Request):
    """Get admin dashboard data with enhanced statistics."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Basic stats
        total_clients = await db.clients.count_documents({})
        active_clients = await db.clients.count_documents({"subscription_status": "ACTIVE"})
        pending_clients = await db.clients.count_documents({"subscription_status": "PENDING"})
        
        # Enhanced stats
        provisioned_clients = await db.clients.count_documents({"onboarding_status": "PROVISIONED"})
        failed_provisioning = await db.clients.count_documents({"onboarding_status": "FAILED"})
        
        # Property stats
        total_properties = await db.properties.count_documents({})
        
        # Compliance overview
        properties = await db.properties.find({}, {"_id": 0, "compliance_status": 1}).to_list(10000)
        compliance_breakdown = {
            "GREEN": sum(1 for p in properties if p.get("compliance_status") == "GREEN"),
            "AMBER": sum(1 for p in properties if p.get("compliance_status") == "AMBER"),
            "RED": sum(1 for p in properties if p.get("compliance_status") == "RED")
        }
        
        # Recent activity (last 7 days)
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        recent_signups = await db.clients.count_documents({
            "created_at": {"$gte": seven_days_ago}
        })
        
        return {
            "stats": {
                "total_clients": total_clients,
                "active_clients": active_clients,
                "pending_clients": pending_clients,
                "provisioned_clients": provisioned_clients,
                "failed_provisioning": failed_provisioning,
                "total_properties": total_properties,
                "recent_signups_7d": recent_signups
            },
            "compliance_overview": compliance_breakdown
        }
    
    except Exception as e:
        logger.error(f"Admin dashboard error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load admin dashboard"
        )

@router.get("/clients")
async def get_clients(request: Request, skip: int = 0, limit: int = 50):
    """Get all clients (admin only)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        clients = await db.clients.find({}, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
        total = await db.clients.count_documents({})
        
        return {
            "clients": clients,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    
    except Exception as e:
        logger.error(f"Get clients error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load clients"
        )

@router.get("/clients/{client_id}")
async def get_client_detail(request: Request, client_id: str):
    """Get client details (admin only)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        properties = await db.properties.find({"client_id": client_id}, {"_id": 0}).to_list(100)
        portal_users = await db.portal_users.find({"client_id": client_id}, {"_id": 0}).to_list(10)
        requirements = await db.requirements.find({"client_id": client_id}, {"_id": 0}).to_list(1000)
        documents = await db.documents.find({"client_id": client_id}, {"_id": 0}).to_list(1000)
        
        # Calculate compliance summary
        compliant = sum(1 for r in requirements if r["status"] == "COMPLIANT")
        overdue = sum(1 for r in requirements if r["status"] == "OVERDUE")
        expiring = sum(1 for r in requirements if r["status"] == "EXPIRING_SOON")
        
        return {
            "client": client,
            "properties": properties,
            "portal_users": portal_users,
            "requirements": requirements,
            "documents": documents,
            "compliance_summary": {
                "total": len(requirements),
                "compliant": compliant,
                "overdue": overdue,
                "expiring_soon": expiring
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get client detail error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load client details"
        )

@router.get("/audit-logs")
async def get_audit_logs(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    client_id: str = None,
    action: str = None,
    start_date: str = None,
    end_date: str = None
):
    """Get audit logs with enhanced filtering (admin only)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Build query with filters
        query = {}
        if client_id:
            query["client_id"] = client_id
        if action:
            query["action"] = action
        
        # Date range filter
        if start_date or end_date:
            query["timestamp"] = {}
            if start_date:
                query["timestamp"]["$gte"] = start_date
            if end_date:
                query["timestamp"]["$lte"] = end_date
        
        logs = await db.audit_logs.find(
            query,
            {"_id": 0}
        ).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
        
        total = await db.audit_logs.count_documents(query)
        
        # Get unique actions for filter dropdown
        unique_actions = await db.audit_logs.distinct("action")
        
        return {
            "logs": logs,
            "total": total,
            "skip": skip,
            "limit": limit,
            "filters": {
                "available_actions": unique_actions
            }
        }
    
    except Exception as e:
        logger.error(f"Get audit logs error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load audit logs"
        )

@router.post("/clients/{client_id}/resend-password-setup")
async def resend_password_setup(request: Request, client_id: str):
    """Resend password setup link (admin only)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Rate limiting
        from utils.rate_limiter import rate_limiter
        
        allowed, error_msg = await rate_limiter.check_rate_limit(
            key=f"password_resend_{client_id}",
            max_attempts=3,
            window_minutes=60
        )
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )
        
        from services.provisioning import provisioning_service
        from auth import generate_secure_token, hash_token
        from models import PasswordToken
        import os
        
        # Get client and portal user
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        portal_user = await db.portal_users.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        if not portal_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portal user not found"
            )
        
        # Revoke old tokens
        await db.password_tokens.update_many(
            {"portal_user_id": portal_user["portal_user_id"], "used_at": None, "revoked_at": None},
            {"$set": {"revoked_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        # Generate new token
        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        
        password_token = PasswordToken(
            token_hash=token_hash,
            portal_user_id=portal_user["portal_user_id"],
            client_id=client_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            created_by="ADMIN",
            send_count=1
        )
        
        doc = password_token.model_dump()
        for key in ["expires_at", "used_at", "revoked_at", "created_at"]:
            if doc.get(key) and isinstance(doc[key], datetime):
                doc[key] = doc[key].isoformat()
        
        await db.password_tokens.insert_one(doc)
        
        # Send email
        from services.email_service import email_service
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        setup_link = f"{frontend_url}/set-password?token={raw_token}"
        
        await email_service.send_password_setup_email(
            recipient=client["email"],
            client_name=client["full_name"],
            setup_link=setup_link,
            client_id=client_id
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.PASSWORD_SETUP_LINK_RESENT,
            actor_id=user["portal_user_id"],
            client_id=client_id,
            metadata={"admin_email": user["email"]}
        )
        
        return {"message": "Password setup link resent"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend password setup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resend password setup link"
        )

@router.get("/messages")
async def get_message_logs(request: Request, skip: int = 0, limit: int = 100, client_id: str = None):
    """Get email message logs (admin only)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        query = {}
        if client_id:
            query["client_id"] = client_id
        
        messages = await db.message_logs.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        total = await db.message_logs.count_documents(query)
        
        return {
            "messages": messages,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    
    except Exception as e:
        logger.error(f"Get message logs error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load message logs"
        )

@router.post("/send-manual-email")
async def send_manual_email(
    request: Request,
    client_id: str,
    subject: str,
    message: str
):
    """Send manual email to client (admin only)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Send email using email service
        from services.email_service import email_service
        from models import EmailTemplateAlias
        
        await email_service.send_email(
            recipient=client["email"],
            template_alias=EmailTemplateAlias.ADMIN_MANUAL,
            template_model={
                "client_name": client["full_name"],
                "message": message,
                "company_name": "Pleerity Enterprise Ltd",
                "tagline": "AI-Driven Solutions & Compliance"
            },
            client_id=client_id,
            subject=subject
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=client_id,
            metadata={
                "action": "manual_email_sent",
                "subject": subject,
                "admin_email": user["email"]
            }
        )
        
        return {"message": "Email sent successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send manual email error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send email"
        )

@router.get("/clients/{client_id}/compliance-pack")
async def generate_compliance_pack(request: Request, client_id: str):
    """Generate compliance pack for client (PLAN_6_15 only)."""
    user = await admin_route_guard(request)
    
    try:
        from services.compliance_pack import compliance_pack_generator
        
        pack_data = await compliance_pack_generator.generate_pack(client_id)
        
        return pack_data
    
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Compliance pack generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate compliance pack"
        )

@router.get("/jobs/status")
async def get_jobs_status(request: Request):
    """Get background jobs status (read-only monitoring)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get last reminder job run from audit logs
        last_reminder = await db.audit_logs.find_one(
            {"action": "REMINDER_SENT"},
            {"_id": 0},
            sort=[("timestamp", -1)]
        )
        
        # Get last digest job run
        last_digest = await db.digest_logs.find_one(
            {},
            {"_id": 0},
            sort=[("sent_at", -1)]
        )
        
        # Count pending reminders (requirements expiring in 30 days)
        thirty_days = datetime.now(timezone.utc) + timedelta(days=30)
        
        requirements = await db.requirements.find(
            {"status": {"$in": ["PENDING", "EXPIRING_SOON"]}},
            {"_id": 0}
        ).to_list(10000)
        
        pending_reminders = 0
        for r in requirements:
            try:
                due_date_str = r.get("due_date")
                if due_date_str:
                    due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00')) if isinstance(due_date_str, str) else due_date_str
                    if due_date <= thirty_days:
                        pending_reminders += 1
            except Exception:
                pass
        
        # Get scheduler status
        from server import scheduler
        scheduler_jobs = []
        for job in scheduler.get_jobs():
            scheduler_jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            })
        
        return {
            "daily_reminders": {
                "last_run": last_reminder["timestamp"] if last_reminder else None,
                "pending_count": pending_reminders
            },
            "monthly_digest": {
                "last_run": last_digest["sent_at"] if last_digest else None,
                "total_sent": await db.digest_logs.count_documents({})
            },
            "scheduled_jobs": scheduler_jobs,
            "system_status": "operational"
        }
    
    except Exception as e:
        logger.error(f"Jobs status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load jobs status"
        )

@router.post("/jobs/trigger/{job_type}")
async def trigger_job(request: Request, job_type: str):
    """Manually trigger a background job (admin only).
    
    job_type: 'daily' or 'monthly'
    """
    user = await admin_route_guard(request)
    
    if job_type not in ["daily", "monthly"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job type. Use 'daily' or 'monthly'"
        )
    
    try:
        from services.jobs import JobScheduler
        job_scheduler = JobScheduler()
        await job_scheduler.connect()
        
        if job_type == "daily":
            count = await job_scheduler.send_daily_reminders()
            result_msg = f"Daily reminders sent: {count}"
        else:
            count = await job_scheduler.send_monthly_digests()
            result_msg = f"Monthly digests sent: {count}"
        
        await job_scheduler.close()
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=None,
            metadata={
                "action": f"manual_job_trigger_{job_type}",
                "result_count": count,
                "admin_email": user["email"]
            }
        )
        
        return {"message": result_msg, "count": count}
    
    except Exception as e:
        logger.error(f"Manual job trigger error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger {job_type} job"
        )

@router.post("/clients/invite")
async def admin_invite_client(
    request: Request,
    full_name: str,
    email: str,
    billing_plan: str = "PLAN_1"
):
    """Admin-initiated client invitation.
    
    Creates client record in INVITED state. Admin must manually trigger
    provisioning after payment is arranged separately.
    
    IMPORTANT: This does NOT bypass the normal flow. It simply pre-creates
    the client record. Provisioning must still be triggered manually.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        from models import Client, BillingPlan, ClientType, PreferredContact, ServiceCode
        
        # Check if email already exists
        existing = await db.clients.find_one({"email": email}, {"_id": 0})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A client with this email already exists"
            )
        
        # Create client in INVITED state (not yet provisioned)
        client = Client(
            full_name=full_name,
            email=email,
            client_type=ClientType.INDIVIDUAL,
            preferred_contact=PreferredContact.EMAIL,
            billing_plan=BillingPlan(billing_plan),
            service_code=ServiceCode.VAULT_PRO,
            subscription_status="PENDING",  # Admin must activate
            onboarding_status="INTAKE_PENDING"  # Not provisioned yet
        )
        
        client_doc = client.model_dump()
        for key in ["created_at", "updated_at"]:
            if client_doc.get(key):
                client_doc[key] = client_doc[key].isoformat()
        
        await db.clients.insert_one(client_doc)
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=client.client_id,
            metadata={
                "action": "admin_client_invited",
                "email": email,
                "billing_plan": billing_plan,
                "admin_email": user["email"]
            }
        )
        
        logger.info(f"Admin invited client: {email}")
        
        return {
            "message": "Client invited successfully",
            "client_id": client.client_id,
            "next_steps": [
                "Add property details for the client",
                "Arrange payment separately",
                "Manually trigger provisioning via /admin/clients/{client_id}/provision"
            ]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin invite client error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invite client"
        )

@router.post("/clients/{client_id}/properties")
async def admin_add_property(
    request: Request,
    client_id: str,
    address_line_1: str,
    city: str,
    postcode: str,
    property_type: str = "residential",
    number_of_units: int = 1
):
    """Add a property for a client (admin only).
    
    Used when setting up a client before provisioning.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        from models import Property, ComplianceStatus
        
        # Verify client exists
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Create property
        property_obj = Property(
            client_id=client_id,
            address_line_1=address_line_1,
            city=city,
            postcode=postcode,
            property_type=property_type,
            number_of_units=number_of_units,
            compliance_status=ComplianceStatus.RED
        )
        
        prop_doc = property_obj.model_dump()
        for key in ["created_at", "updated_at"]:
            if prop_doc.get(key):
                prop_doc[key] = prop_doc[key].isoformat()
        
        await db.properties.insert_one(prop_doc)
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=client_id,
            metadata={
                "action": "admin_property_added",
                "property_id": property_obj.property_id,
                "address": address_line_1,
                "admin_email": user["email"]
            }
        )
        
        logger.info(f"Admin added property for client {client_id}: {address_line_1}")
        
        return {
            "message": "Property added successfully",
            "property_id": property_obj.property_id,
            "client_id": client_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin add property error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add property"
        )

@router.post("/clients/{client_id}/provision")
async def admin_trigger_provision(request: Request, client_id: str):
    """Manually trigger provisioning for a client (admin only).
    
    Uses the existing provisioning engine. This is for admin-invited clients
    where payment was arranged separately.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Verify client has at least one property
        property_count = await db.properties.count_documents({"client_id": client_id})
        if property_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client must have at least one property before provisioning"
            )
        
        # Set subscription active (manual approval by admin)
        await db.clients.update_one(
            {"client_id": client_id},
            {"$set": {"subscription_status": "ACTIVE"}}
        )
        
        # Trigger existing provisioning engine
        from services.provisioning import provisioning_service
        success, message = await provisioning_service.provision_client_portal(client_id)
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=client_id,
            metadata={
                "action": "admin_manual_provision",
                "success": success,
                "message": message,
                "admin_email": user["email"]
            }
        )
        
        if success:
            return {
                "message": "Provisioning triggered successfully",
                "status": "provisioned"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Provisioning failed: {message}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin provision error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger provisioning"
        )

@router.get("/clients/{client_id}/password-setup-link")
async def get_password_setup_link(request: Request, client_id: str, generate_new: bool = False):
    """Get or generate password setup link for a client (admin only, for internal testing).
    
    This endpoint allows admins to:
    1. View the latest valid password setup link for a client
    2. Generate a new link if none exists or if generate_new=True
    
    SECURITY: This is for internal testing only. In production, consider restricting access.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Get portal user
        portal_user = await db.portal_users.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        if not portal_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portal user not found - client may not be provisioned"
            )
        
        import os
        from auth import generate_secure_token, hash_token
        from models import PasswordToken
        
        frontend_url = os.getenv("FRONTEND_URL", "https://compliancevault.preview.emergentagent.com")
        
        # Check for existing valid token (not used, not revoked, not expired)
        existing_token = None
        if not generate_new:
            # Find valid token - we need to check expiry
            tokens = await db.password_tokens.find(
                {
                    "portal_user_id": portal_user["portal_user_id"],
                    "used_at": None,
                    "revoked_at": None
                },
                {"_id": 0}
            ).sort("created_at", -1).to_list(10)
            
            for token in tokens:
                expires_at = datetime.fromisoformat(token["expires_at"].replace('Z', '+00:00')) if isinstance(token["expires_at"], str) else token["expires_at"]
                if expires_at > datetime.now(timezone.utc):
                    existing_token = token
                    break
        
        if existing_token and not generate_new:
            # NOTE: We cannot retrieve the raw token from hash - must generate new
            return {
                "message": "Existing valid token found but raw token not retrievable",
                "token_exists": True,
                "expires_at": existing_token["expires_at"],
                "created_at": existing_token["created_at"],
                "portal_user_id": portal_user["portal_user_id"],
                "client_email": client["email"],
                "note": "Use generate_new=true to create a new link",
                "client_status": {
                    "subscription_status": client.get("subscription_status"),
                    "onboarding_status": client.get("onboarding_status")
                },
                "portal_user_status": {
                    "status": portal_user.get("status"),
                    "password_status": portal_user.get("password_status")
                }
            }
        
        # Generate new token
        # First, revoke any existing tokens
        await db.password_tokens.update_many(
            {"portal_user_id": portal_user["portal_user_id"], "used_at": None, "revoked_at": None},
            {"$set": {"revoked_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        
        password_token = PasswordToken(
            token_hash=token_hash,
            portal_user_id=portal_user["portal_user_id"],
            client_id=client_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),  # 24 hours for admin-generated
            created_by="ADMIN",
            send_count=0  # Not sent via email
        )
        
        doc = password_token.model_dump()
        for key in ["expires_at", "used_at", "revoked_at", "created_at"]:
            if doc.get(key) and isinstance(doc[key], datetime):
                doc[key] = doc[key].isoformat()
        
        await db.password_tokens.insert_one(doc)
        
        setup_link = f"{frontend_url}/set-password?token={raw_token}"
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=client_id,
            metadata={
                "action": "admin_generated_password_link",
                "admin_email": user["email"],
                "for_user": portal_user["portal_user_id"]
            }
        )
        
        return {
            "message": "Password setup link generated",
            "setup_link": setup_link,
            "raw_token": raw_token,
            "expires_at": password_token.expires_at.isoformat(),
            "client_email": client["email"],
            "client_name": client["full_name"],
            "client_status": {
                "subscription_status": client.get("subscription_status"),
                "onboarding_status": client.get("onboarding_status")
            },
            "portal_user_status": {
                "status": portal_user.get("status"),
                "password_status": portal_user.get("password_status")
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get password setup link error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get/generate password setup link"
        )

@router.get("/clients/{client_id}/full-status")
async def get_client_full_status(request: Request, client_id: str):
    """Get complete client status including all related records (admin only).
    
    Returns a comprehensive view of client state for debugging and verification.
    """
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Get portal user(s)
        portal_users = await db.portal_users.find(
            {"client_id": client_id},
            {"_id": 0, "password_hash": 0}
        ).to_list(10)
        
        # Get properties
        properties = await db.properties.find(
            {"client_id": client_id},
            {"_id": 0}
        ).to_list(100)
        
        # Get requirements count by status
        requirements = await db.requirements.find(
            {"client_id": client_id},
            {"_id": 0, "status": 1}
        ).to_list(1000)
        
        req_summary = {}
        for r in requirements:
            status = r.get("status", "UNKNOWN")
            req_summary[status] = req_summary.get(status, 0) + 1
        
        # Get password tokens
        tokens = await db.password_tokens.find(
            {"client_id": client_id},
            {"_id": 0, "token_hash": 0}  # Don't expose hash
        ).sort("created_at", -1).to_list(5)
        
        # Get recent audit logs
        audit_logs = await db.audit_logs.find(
            {"client_id": client_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(10).to_list(10)
        
        # Get message logs
        message_logs = await db.message_logs.find(
            {"client_id": client_id},
            {"_id": 0}
        ).sort("created_at", -1).limit(10).to_list(10)
        
        return {
            "client": client,
            "portal_users": portal_users,
            "properties_count": len(properties),
            "properties": properties[:5],  # First 5 only
            "requirements_summary": req_summary,
            "requirements_total": len(requirements),
            "recent_password_tokens": tokens,
            "recent_audit_logs": audit_logs,
            "recent_message_logs": message_logs,
            "readiness_check": {
                "has_properties": len(properties) > 0,
                "is_provisioned": client.get("onboarding_status") == "PROVISIONED",
                "subscription_active": client.get("subscription_status") == "ACTIVE",
                "has_portal_user": len(portal_users) > 0,
                "portal_user_active": any(u.get("status") == "ACTIVE" for u in portal_users),
                "password_set": any(u.get("password_status") == "SET" for u in portal_users)
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get client full status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get client status"
        )
