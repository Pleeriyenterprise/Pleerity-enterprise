"""Admin Billing & Subscription Management Routes.

Enterprise-grade billing management for Compliance Vault Pro.

Endpoints:
- GET /api/admin/billing/clients/search - Search clients by email, CRN, client_id, postcode
- GET /api/admin/billing/clients/{client_id} - Get full billing snapshot
- POST /api/admin/billing/clients/{client_id}/sync - Force sync from Stripe
- POST /api/admin/billing/clients/{client_id}/portal-link - Create Stripe billing portal link
- POST /api/admin/billing/clients/{client_id}/resend-setup - Resend password setup email
- POST /api/admin/billing/clients/{client_id}/force-provision - Re-run provisioning
- POST /api/admin/billing/clients/{client_id}/message - Send message to client

NON-NEGOTIABLE RULES:
1. Stripe is the billing authority. App is the entitlement authority.
2. No admin action may "pretend" a subscription is active.
3. Every admin billing action must be audit-logged.
4. Feature gating is server-side first.
"""
import stripe
import os
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Request, status, Depends
from pydantic import BaseModel
from database import database
from middleware import admin_route_guard
from models import AuditAction, EmailTemplateAlias, UserRole
from utils.audit import create_audit_log
from services.plan_registry import plan_registry, PlanCode, EntitlementStatus, SUBSCRIPTION_PRICE_TO_PLAN
from services.provisioning import provisioning_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/billing", tags=["admin-billing"], dependencies=[Depends(admin_route_guard)])

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_API_KEY", "")


# =============================================================================
# Request/Response Models
# =============================================================================

class MessageRequest(BaseModel):
    """Request to send message to client."""
    channels: List[str]  # ["in_app", "email", "sms"]
    template_id: Optional[str] = None
    custom_text: Optional[str] = None
    subject: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# =============================================================================
# Search Clients
# =============================================================================

@router.get("/clients/search")
async def search_billing_clients(request: Request, q: str = "", limit: int = 20):
    """
    Search clients for billing management.
    
    Search by: email, CRN, client_id, property address/postcode
    """
    admin = await admin_route_guard(request)
    db = database.get_db()
    
    if not q or len(q) < 2:
        return {"clients": [], "total": 0, "query": q}
    
    try:
        # Build search query
        search_query = {
            "$or": [
                {"contact_email": {"$regex": q, "$options": "i"}},
                {"crn": {"$regex": q, "$options": "i"}},
                {"client_id": {"$regex": q, "$options": "i"}},
                {"company_name": {"$regex": q, "$options": "i"}},
                {"contact_name": {"$regex": q, "$options": "i"}},
            ]
        }
        
        # Search clients
        clients = await db.clients.find(
            search_query,
            {
                "_id": 0,
                "client_id": 1,
                "contact_email": 1,
                "contact_name": 1,
                "company_name": 1,
                "crn": 1,
                "billing_plan": 1,
                "subscription_status": 1,
                "entitlement_status": 1,
                "stripe_customer_id": 1,
                "created_at": 1,
            }
        ).limit(limit).to_list(limit)
        
        # Also search by property address/postcode
        if len(clients) < limit:
            properties = await db.properties.find(
                {
                    "$or": [
                        {"address": {"$regex": q, "$options": "i"}},
                        {"postcode": {"$regex": q, "$options": "i"}},
                    ]
                },
                {"_id": 0, "client_id": 1}
            ).limit(limit).to_list(limit)
            
            property_client_ids = list(set(p["client_id"] for p in properties))
            existing_client_ids = [c["client_id"] for c in clients]
            new_client_ids = [cid for cid in property_client_ids if cid not in existing_client_ids]
            
            if new_client_ids:
                additional_clients = await db.clients.find(
                    {"client_id": {"$in": new_client_ids}},
                    {
                        "_id": 0,
                        "client_id": 1,
                        "contact_email": 1,
                        "contact_name": 1,
                        "company_name": 1,
                        "crn": 1,
                        "billing_plan": 1,
                        "subscription_status": 1,
                        "entitlement_status": 1,
                        "stripe_customer_id": 1,
                        "created_at": 1,
                    }
                ).limit(limit - len(clients)).to_list(limit - len(clients))
                
                clients.extend(additional_clients)
        
        # Add plan names
        for client in clients:
            plan_code = client.get("billing_plan", "PLAN_1_SOLO")
            plan_def = plan_registry.get_plan_by_code_string(plan_code)
            client["plan_name"] = plan_def.get("name") if plan_def else plan_code
            client["max_properties"] = plan_def.get("max_properties", 2) if plan_def else 2
        
        return {
            "clients": clients,
            "total": len(clients),
            "query": q,
        }
        
    except Exception as e:
        logger.error(f"Search billing clients error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )


# =============================================================================
# Get Client Billing Snapshot
# =============================================================================

@router.get("/clients/{client_id}")
async def get_client_billing_snapshot(request: Request, client_id: str):
    """
    Get full billing snapshot for a client.
    
    Includes:
    - Client identifiers
    - Plan and entitlement status
    - Stripe billing details
    - Last sync and webhook info
    - Recent billing events
    """
    admin = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Get billing record
        billing = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        # Get portal user (use auth_email field)
        portal_user = await db.portal_users.find_one(
            {"client_id": client_id, "role": "ROLE_CLIENT_ADMIN"},
            {"_id": 0, "portal_user_id": 1, "auth_email": 1, "email": 1, "password_set": 1, "password_status": 1, "created_at": 1}
        )
        
        # Get last Stripe events
        last_events = await db.stripe_events.find(
            {"related_client_id": client_id}
        ).sort("created", -1).limit(5).to_list(5)
        
        for event in last_events:
            if "_id" in event:
                del event["_id"]
        
        # Get property count
        property_count = await db.properties.count_documents({"client_id": client_id})
        
        # Build plan info
        plan_code = client.get("billing_plan", "PLAN_1_SOLO")
        plan_def = plan_registry.get_plan_by_code_string(plan_code)
        
        # Build snapshot
        snapshot = {
            # Client identifiers
            "client_id": client_id,
            "contact_name": client.get("contact_name"),
            "contact_email": client.get("contact_email"),
            "company_name": client.get("company_name"),
            "crn": client.get("crn"),
            
            # Plan info
            "plan_code": plan_code,
            "plan_name": plan_def.get("name") if plan_def else plan_code,
            "max_properties": plan_def.get("max_properties", 2) if plan_def else 2,
            "current_property_count": property_count,
            "over_property_limit": property_count > (plan_def.get("max_properties", 2) if plan_def else 2),
            
            # Entitlement
            "subscription_status": client.get("subscription_status", "PENDING"),
            "entitlement_status": client.get("entitlement_status", "DISABLED"),
            "onboarding_status": client.get("onboarding_status", "PENDING"),
            
            # Stripe fields
            "stripe_customer_id": client.get("stripe_customer_id") or (billing.get("stripe_customer_id") if billing else None),
            "stripe_subscription_id": billing.get("stripe_subscription_id") if billing else None,
            "cancel_at_period_end": billing.get("cancel_at_period_end", False) if billing else False,
            "current_period_start": billing.get("current_period_start") if billing else None,
            "current_period_end": billing.get("current_period_end") if billing else None,
            "onboarding_fee_paid": billing.get("onboarding_fee_paid", False) if billing else False,
            "latest_invoice_id": billing.get("latest_invoice_id") if billing else None,
            "payment_failed_at": billing.get("payment_failed_at") if billing else None,
            
            # Sync info
            "last_synced_at": billing.get("updated_at") if billing else None,
            "billing_record_exists": billing is not None,
            
            # Portal user - include email from auth_email field
            "portal_user": {
                **portal_user,
                "email": portal_user.get("auth_email") or portal_user.get("email")
            } if portal_user else None,
            "password_setup_complete": (portal_user.get("password_set", False) or portal_user.get("password_status") == "SET") if portal_user else False,
            
            # Recent events
            "recent_stripe_events": last_events,
            
            # Created
            "created_at": client.get("created_at"),
        }
        
        return snapshot
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get billing snapshot error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get billing snapshot"
        )


# =============================================================================
# Force Sync from Stripe
# =============================================================================

@router.post("/clients/{client_id}/sync")
async def sync_client_billing(request: Request, client_id: str):
    """
    Force sync billing data from Stripe.
    
    Fetches:
    - Customer details
    - Active subscriptions
    - Subscription status
    - Latest invoice and payment status
    
    Updates:
    - client_billing record
    - Entitlements
    - Triggers provisioning if entitlement becomes ENABLED
    
    Returns before/after diff.
    """
    admin = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Get current billing state (before)
        billing_before = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        before_state = {
            "subscription_status": billing_before.get("subscription_status") if billing_before else None,
            "entitlement_status": billing_before.get("entitlement_status") if billing_before else None,
            "current_plan_code": billing_before.get("current_plan_code") if billing_before else None,
        }
        
        # Get Stripe customer ID
        stripe_customer_id = client.get("stripe_customer_id") or (billing_before.get("stripe_customer_id") if billing_before else None)
        
        if not stripe_customer_id:
            # No Stripe customer - nothing to sync
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role=UserRole.ROLE_ADMIN,
                actor_id=admin.get("portal_user_id"),
                client_id=client_id,
                metadata={
                    "action_type": "BILLING_SYNC_ATTEMPTED",
                    "result": "NO_STRIPE_CUSTOMER",
                    "message": "Client has no Stripe customer ID"
                }
            )
            
            return {
                "success": False,
                "message": "Client has no Stripe customer ID. Cannot sync.",
                "has_stripe_customer": False,
            }
        
        # Fetch from Stripe
        try:
            customer = stripe.Customer.retrieve(stripe_customer_id)
        except stripe.error.InvalidRequestError:
            return {
                "success": False,
                "message": f"Stripe customer {stripe_customer_id} not found",
                "has_stripe_customer": False,
            }
        
        # Get subscriptions
        subscriptions = stripe.Subscription.list(
            customer=stripe_customer_id,
            status="all",
            limit=5,
            expand=["data.items.data.price", "data.latest_invoice"]
        )
        
        # Find active/relevant subscription
        active_subscription = None
        for sub in subscriptions.data:
            if sub.status in ("active", "trialing", "past_due"):
                active_subscription = sub
                break
        
        if not active_subscription and subscriptions.data:
            # Use most recent
            active_subscription = subscriptions.data[0]
        
        # Build billing update
        billing_update = {
            "client_id": client_id,
            "stripe_customer_id": stripe_customer_id,
            "updated_at": datetime.now(timezone.utc),
        }
        
        new_plan_code = None
        new_subscription_status = None
        new_entitlement_status = EntitlementStatus.DISABLED
        
        if active_subscription:
            # Determine plan from price_id
            for item in active_subscription.get("items", {}).get("data", []):
                price_id = item.get("price", {}).get("id")
                new_plan_code = plan_registry.get_plan_from_subscription_price_id(price_id)
                if new_plan_code:
                    break
            
            if not new_plan_code:
                new_plan_code = PlanCode.PLAN_1_SOLO
            
            new_subscription_status = active_subscription.status.upper()
            new_entitlement_status = plan_registry.get_entitlement_status_from_subscription(active_subscription.status)
            
            billing_update.update({
                "stripe_subscription_id": active_subscription.id,
                "current_plan_code": new_plan_code.value if isinstance(new_plan_code, PlanCode) else new_plan_code,
                "subscription_status": new_subscription_status,
                "entitlement_status": new_entitlement_status.value,
                "cancel_at_period_end": active_subscription.cancel_at_period_end,
                "current_period_start": datetime.fromtimestamp(active_subscription.current_period_start, tz=timezone.utc),
                "current_period_end": datetime.fromtimestamp(active_subscription.current_period_end, tz=timezone.utc),
            })
            
            # Get invoice info
            latest_invoice = active_subscription.get("latest_invoice")
            if latest_invoice:
                if isinstance(latest_invoice, str):
                    latest_invoice = stripe.Invoice.retrieve(latest_invoice)
                
                billing_update["latest_invoice_id"] = latest_invoice.id
                billing_update["latest_invoice_status"] = latest_invoice.status
                
                if latest_invoice.status == "open" and latest_invoice.next_payment_attempt:
                    billing_update["next_payment_attempt"] = datetime.fromtimestamp(
                        latest_invoice.next_payment_attempt, tz=timezone.utc
                    )
        else:
            # No subscription
            billing_update.update({
                "subscription_status": "NONE",
                "entitlement_status": EntitlementStatus.DISABLED.value,
            })
        
        # Upsert billing record
        await db.client_billing.update_one(
            {"client_id": client_id},
            {"$set": billing_update, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
            upsert=True
        )
        
        # Update client record
        client_update = {
            "stripe_customer_id": stripe_customer_id,
        }
        
        if new_plan_code:
            client_update["billing_plan"] = new_plan_code.value if isinstance(new_plan_code, PlanCode) else new_plan_code
        if new_subscription_status:
            client_update["subscription_status"] = "ACTIVE" if new_subscription_status in ("ACTIVE", "TRIALING") else new_subscription_status
        if new_entitlement_status:
            client_update["entitlement_status"] = new_entitlement_status.value
        
        await db.clients.update_one(
            {"client_id": client_id},
            {"$set": client_update}
        )
        
        # Check if entitlement flipped to ENABLED - trigger provisioning
        provisioning_triggered = False
        if (
            before_state.get("entitlement_status") != EntitlementStatus.ENABLED.value and
            new_entitlement_status == EntitlementStatus.ENABLED
        ):
            onboarding_status = client.get("onboarding_status")
            if onboarding_status != "PROVISIONED":
                success, message = await provisioning_service.provision_client_portal(client_id)
                provisioning_triggered = success
                logger.info(f"Provisioning triggered by sync for {client_id}: {success}")
        
        after_state = {
            "subscription_status": new_subscription_status,
            "entitlement_status": new_entitlement_status.value if new_entitlement_status else None,
            "current_plan_code": new_plan_code.value if isinstance(new_plan_code, PlanCode) else new_plan_code,
        }
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=admin.get("portal_user_id"),
            client_id=client_id,
            metadata={
                "action_type": "BILLING_SYNC_COMPLETED",
                "before": before_state,
                "after": after_state,
                "provisioning_triggered": provisioning_triggered,
                "stripe_customer_id": stripe_customer_id,
                "stripe_subscription_id": active_subscription.id if active_subscription else None,
            }
        )
        
        return {
            "success": True,
            "message": "Billing synced from Stripe",
            "before": before_state,
            "after": after_state,
            "changes_detected": before_state != after_state,
            "provisioning_triggered": provisioning_triggered,
            "stripe_customer_id": stripe_customer_id,
            "stripe_subscription_id": active_subscription.id if active_subscription else None,
        }
        
    except HTTPException:
        raise
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error during sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Sync billing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sync failed"
        )


# =============================================================================
# Create Billing Portal Link
# =============================================================================

@router.post("/clients/{client_id}/portal-link")
async def create_billing_portal_link(request: Request, client_id: str):
    """
    Generate a Stripe Billing Portal session for the customer.
    
    Returns a one-time URL that can be shared with the client.
    """
    admin = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Get Stripe customer ID
        billing = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0, "stripe_customer_id": 1}
        )
        
        stripe_customer_id = client.get("stripe_customer_id") or (billing.get("stripe_customer_id") if billing else None)
        
        if not stripe_customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client has no Stripe customer ID"
            )
        
        # Get return URL
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        
        # Create portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=f"{frontend_url}/app/billing",
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=admin.get("portal_user_id"),
            client_id=client_id,
            metadata={
                "action_type": "BILLING_PORTAL_LINK_CREATED",
                "stripe_customer_id": stripe_customer_id,
                "portal_url_created": True,
            }
        )
        
        return {
            "success": True,
            "portal_url": portal_session.url,
            "expires_at": None,  # Stripe portal sessions don't have explicit expiry
            "client_email": client.get("contact_email"),
            "message": "Billing portal link created. Share with client to manage subscription.",
        }
        
    except HTTPException:
        raise
    except stripe.error.StripeError as e:
        logger.error(f"Stripe portal error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Create portal link error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create portal link"
        )


# =============================================================================
# Resend Password Setup Link
# =============================================================================

@router.post("/clients/{client_id}/resend-setup")
async def resend_password_setup(request: Request, client_id: str):
    """
    Resend password setup email to client.
    
    Works even if user never completed setup previously.
    """
    admin = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get portal user
        portal_user = await db.portal_users.find_one(
            {"client_id": client_id, "role": "ROLE_CLIENT_ADMIN"},
            {"_id": 0}
        )
        
        if not portal_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No portal user found for this client"
            )
        
        # Generate new setup token
        import secrets
        setup_token = secrets.token_urlsafe(32)
        
        await db.portal_users.update_one(
            {"portal_user_id": portal_user["portal_user_id"]},
            {
                "$set": {
                    "setup_token": setup_token,
                    "setup_token_created_at": datetime.now(timezone.utc),
                }
            }
        )
        
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        setup_url = f"{frontend_url}/setup-password?token={setup_token}"
        user_email = (portal_user.get("auth_email") or portal_user.get("email") or "").strip()
        if not user_email or not setup_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "EMAIL_INPUT_INVALID", "message": "Missing recipient email or setup link"},
            )
        
        from services.email_service import email_service
        try:
            result = await email_service.send_password_setup_email(
                recipient=user_email,
                client_name=portal_user.get("full_name") or portal_user.get("name", ""),
                setup_link=setup_url,
                client_id=client_id
            )
        except Exception as e:
            logger.error(f"Resend setup send error: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error_code": "EMAIL_SEND_FAILED", "template": EmailTemplateAlias.PASSWORD_SETUP.value},
            )
        if result.status != "sent":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "error_code": "EMAIL_SEND_FAILED",
                    "template": EmailTemplateAlias.PASSWORD_SETUP.value,
                    "message_id": getattr(result, "message_id", None),
                },
            )
        
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=admin.get("portal_user_id"),
            client_id=client_id,
            metadata={
                "action_type": "PASSWORD_SETUP_RESENT",
                "reason": "Admin requested resend",
            }
        )
        
        return {
            "success": True,
            "message": "Password setup email sent",
            "email": user_email,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend setup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error_code": "EMAIL_SEND_FAILED", "template": EmailTemplateAlias.PASSWORD_SETUP.value},
        )


# =============================================================================
# Force Provisioning
# =============================================================================

class TestProvisionBody(BaseModel):
    """Set onboarding_status and billing_plan for test clients (admin only)."""
    onboarding_status: str = "PROVISIONED"
    billing_plan: Optional[str] = "PLAN_1_SOLO"


@router.patch("/clients/{client_id}/test-provision")
async def set_test_client_provisioned(request: Request, client_id: str, body: TestProvisionBody):
    """
    Set onboarding_status and billing_plan for a client (test/seed accounts).
    Use so test clients can access /app/dashboard without full Stripe provisioning.
    Admin only.
    """
    admin = await admin_route_guard(request)
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 1})
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    update = {}
    if body.onboarding_status in ("PROVISIONED", "PENDING_PAYMENT", "PROVISIONING", "FAILED", "INTAKE_PENDING"):
        update["onboarding_status"] = body.onboarding_status
    if body.billing_plan and body.billing_plan in ("PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO"):
        update["billing_plan"] = body.billing_plan
    if not update:
        return {"updated": False, "client_id": client_id}
    await db.clients.update_one({"client_id": client_id}, {"$set": update})
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=admin.get("portal_user_id"),
        client_id=client_id,
        metadata={"action_type": "TEST_PROVISION_UPDATE", "update": update}
    )
    return {"updated": True, "client_id": client_id, "update": update}


@router.post("/clients/{client_id}/force-provision")
async def force_provision_client(request: Request, client_id: str):
    """
    Re-run provisioning pipeline for a client.
    
    Only allowed if entitlement is ENABLED.
    Idempotent and safe to rerun.
    """
    admin = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Check entitlement
        entitlement_status = client.get("entitlement_status", "DISABLED")
        
        if entitlement_status != "ENABLED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot provision: entitlement is {entitlement_status}. Sync billing first."
            )
        
        # Run provisioning
        success, message = await provisioning_service.provision_client_portal(client_id)
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=admin.get("portal_user_id"),
            client_id=client_id,
            metadata={
                "action_type": "FORCE_PROVISIONING",
                "success": success,
                "message": message,
                "previous_onboarding_status": client.get("onboarding_status"),
            }
        )
        
        return {
            "success": success,
            "message": message,
            "client_id": client_id,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Force provision error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Provisioning failed"
        )


# =============================================================================
# Send Message to Client
# =============================================================================

@router.post("/clients/{client_id}/message")
async def send_client_message(request: Request, client_id: str, data: MessageRequest):
    """
    Send message to client via specified channels.
    
    Channels:
    - in_app: Always available
    - email: Always available
    - sms: Only if plan entitled + Twilio configured
    
    Templates:
    - payment_received
    - provisioning_complete
    - payment_failed
    - subscription_canceled
    """
    admin = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        results = {
            "in_app": None,
            "email": None,
            "sms": None,
        }
        
        # Check SMS entitlement
        sms_entitled = False
        if "sms" in data.channels:
            plan_code = client.get("billing_plan", "PLAN_1_SOLO")
            features = plan_registry.get_features_by_string(plan_code)
            sms_entitled = features.get("sms_reminders", False)
            
            if not sms_entitled:
                results["sms"] = {
                    "sent": False,
                    "reason": "PLAN_NOT_ENTITLED",
                    "message": "SMS requires Portfolio plan or higher",
                }
        
        # Template content
        templates = {
            "payment_received": {
                "subject": "Payment Received - Compliance Vault Pro",
                "body": "Thank you for your payment. Your subscription is now active and provisioning has started. You'll receive another email shortly with your login details.",
            },
            "provisioning_complete": {
                "subject": "Your Account is Ready - Compliance Vault Pro",
                "body": "Great news! Your Compliance Vault Pro account is ready. Please check your email for the password setup link to get started.",
            },
            "payment_failed": {
                "subject": "Payment Failed - Action Required",
                "body": "We were unable to process your payment. Please update your payment method to maintain access to your account.",
            },
            "subscription_canceled": {
                "subject": "Subscription Cancelled - Compliance Vault Pro",
                "body": "Your subscription has been cancelled. You'll continue to have access until the end of your current billing period.",
            },
        }
        
        template = templates.get(data.template_id, {})
        subject = data.subject or template.get("subject", "Message from Compliance Vault Pro")
        body = data.custom_text or template.get("body", "")
        
        # Send in-app message
        if "in_app" in data.channels:
            import uuid
            message_record = {
                "message_id": str(uuid.uuid4()),
                "client_id": client_id,
                "channel": "in_app",
                "subject": subject,
                "body": body,
                "template_id": data.template_id,
                "sent_by": admin.get("portal_user_id"),
                "sent_at": datetime.now(timezone.utc),
                "read": False,
            }
            await db.client_messages.insert_one(message_record)
            results["in_app"] = {"sent": True, "message_id": message_record["message_id"]}
        
        # Send email
        if "email" in data.channels:
            from services.email_service import email_service
            
            email_sent = await email_service.send_admin_message(
                to_email=client.get("contact_email"),
                subject=subject,
                body=body,
            )
            results["email"] = {"sent": email_sent}
        
        # Send SMS
        if "sms" in data.channels and sms_entitled:
            phone = client.get("phone")
            if phone:
                from services.sms_service import sms_service
                
                sms_sent = await sms_service.send_sms(
                    to_phone=phone,
                    message=body[:160],  # SMS limit
                )
                results["sms"] = {"sent": sms_sent}
            else:
                results["sms"] = {"sent": False, "reason": "NO_PHONE_NUMBER"}
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=admin.get("portal_user_id"),
            client_id=client_id,
            metadata={
                "action_type": "CLIENT_MESSAGE_SENT",
                "channels": data.channels,
                "template_id": data.template_id,
                "results": results,
            }
        )
        
        return {
            "success": True,
            "results": results,
            "client_email": client.get("contact_email"),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send message error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message"
        )


# =============================================================================
# Get Billing Statistics (Dashboard)
# =============================================================================

@router.get("/statistics")
async def get_billing_statistics(request: Request):
    """Get billing statistics for admin dashboard."""
    admin = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Count by entitlement status
        enabled_count = await db.clients.count_documents({"entitlement_status": "ENABLED"})
        limited_count = await db.clients.count_documents({"entitlement_status": "LIMITED"})
        disabled_count = await db.clients.count_documents({"entitlement_status": "DISABLED"})
        
        # Count by plan
        plan_counts = {}
        for plan in ["PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO"]:
            plan_counts[plan] = await db.clients.count_documents({"billing_plan": plan})
        
        # Recent webhook events
        recent_events = await db.stripe_events.find(
            {"status": {"$in": ["PROCESSED", "FAILED"]}}
        ).sort("created", -1).limit(10).to_list(10)
        
        for event in recent_events:
            if "_id" in event:
                del event["_id"]
        
        # Clients needing attention
        attention_needed = await db.clients.find(
            {
                "$or": [
                    {"entitlement_status": "LIMITED"},
                    {"onboarding_status": {"$nin": ["PROVISIONED", "COMPLETE"]}},
                ]
            },
            {"_id": 0, "client_id": 1, "contact_email": 1, "entitlement_status": 1, "onboarding_status": 1}
        ).limit(20).to_list(20)
        
        return {
            "entitlement_counts": {
                "enabled": enabled_count,
                "limited": limited_count,
                "disabled": disabled_count,
            },
            "plan_counts": plan_counts,
            "recent_webhook_events": recent_events,
            "clients_needing_attention": attention_needed,
        }
        
    except Exception as e:
        logger.error(f"Get billing statistics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get statistics"
        )


# =============================================================================
# Background Job Triggers (Admin Only)
# =============================================================================

@router.post("/jobs/renewal-reminders")
async def trigger_renewal_reminders(request: Request):
    """
    Manually trigger the renewal reminder job.
    
    Sends renewal reminders to all eligible clients
    (ENABLED entitlement, renewal within 7 days, not already reminded).
    """
    admin = await admin_route_guard(request)
    
    try:
        from services.jobs import run_renewal_reminders
        
        count = await run_renewal_reminders()
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=admin.get("portal_user_id"),
            metadata={
                "action_type": "JOB_TRIGGERED",
                "job_name": "renewal_reminders",
                "reminders_sent": count,
            }
        )
        
        return {
            "success": True,
            "job": "renewal_reminders",
            "reminders_sent": count,
        }
        
    except Exception as e:
        logger.error(f"Renewal reminder job error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run renewal reminder job"
        )


@router.get("/jobs/status")
async def get_job_status(request: Request):
    """
    Get status of background jobs and entitlement-based blocking info.
    
    Returns:
    - Job scheduler status
    - Clients blocked from background jobs (LIMITED/DISABLED)
    """
    admin = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Count clients by entitlement for job blocking status
        blocked_limited = await db.clients.count_documents({"entitlement_status": "LIMITED"})
        blocked_disabled = await db.clients.count_documents({"entitlement_status": "DISABLED"})
        
        return {
            "job_blocking": {
                "limited_clients": blocked_limited,
                "disabled_clients": blocked_disabled,
                "message": f"{blocked_limited + blocked_disabled} clients blocked from background jobs (reminders, digests, scheduled reports)"
            },
            "job_types": [
                {"name": "daily_reminders", "schedule": "Daily at 8 AM", "description": "Compliance expiry reminders"},
                {"name": "monthly_digest", "schedule": "1st of month", "description": "Monthly compliance digest"},
                {"name": "compliance_check", "schedule": "Hourly", "description": "Status change detection"},
                {"name": "renewal_reminders", "schedule": "Daily", "description": "7-day subscription renewal reminders"},
                {"name": "scheduled_reports", "schedule": "Per schedule", "description": "Automated report delivery"},
            ],
        }
        
    except Exception as e:
        logger.error(f"Get job status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get job status"
        )

