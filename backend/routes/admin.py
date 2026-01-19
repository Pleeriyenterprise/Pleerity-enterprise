from fastapi import APIRouter, HTTPException, Request, Depends, status
from database import database
from middleware import admin_route_guard
from models import AuditAction
from utils.audit import create_audit_log
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(admin_route_guard)])

@router.get("/dashboard")
async def get_admin_dashboard(request: Request):
    """Get admin dashboard data."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get stats
        total_clients = await db.clients.count_documents({})
        active_clients = await db.clients.count_documents({"subscription_status": "ACTIVE"})
        pending_clients = await db.clients.count_documents({"subscription_status": "PENDING"})
        
        return {
            "stats": {
                "total_clients": total_clients,
                "active_clients": active_clients,
                "pending_clients": pending_clients
            }
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
        
        return {
            "client": client,
            "properties": properties,
            "portal_users": portal_users
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
async def get_audit_logs(request: Request, skip: int = 0, limit: int = 100, client_id: str = None):
    """Get audit logs (admin only)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        query = {}
        if client_id:
            query["client_id"] = client_id
        
        logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
        total = await db.audit_logs.count_documents(query)
        
        return {
            "logs": logs,
            "total": total,
            "skip": skip,
            "limit": limit
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
        from services.provisioning import provisioning_service
        from auth import generate_secure_token, hash_token
        from datetime import datetime, timedelta, timezone
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
