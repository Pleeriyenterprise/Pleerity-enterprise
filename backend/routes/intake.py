from fastapi import APIRouter, HTTPException, Request, status
from database import database
from models import IntakeFormData, Client, Property, ServiceCode, AuditAction
from services.stripe_service import stripe_service
from utils.audit import create_audit_log
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intake", tags=["intake"])

@router.post("/submit")
async def submit_intake(request: Request, data: IntakeFormData):
    """Universal intake form submission."""
    db = database.get_db()
    
    try:
        # Validation
        if not data.properties or len(data.properties) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one property is required"
            )
        
        if not data.consent_data_processing or not data.consent_communications:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Required consents must be provided"
            )
        
        # Check if client already exists
        existing_client = await db.clients.find_one(
            {"email": data.email},
            {"_id": 0}
        )
        
        if existing_client:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists"
            )
        
        # Create client
        client = Client(
            full_name=data.full_name,
            email=data.email,
            phone=data.phone,
            company_name=data.company_name,
            client_type=data.client_type,
            preferred_contact=data.preferred_contact,
            billing_plan=data.billing_plan,
            service_code=ServiceCode.VAULT_PRO
        )
        
        client_doc = client.model_dump()
        for key in ["created_at", "updated_at"]:
            if client_doc.get(key):
                client_doc[key] = client_doc[key].isoformat()
        
        await db.clients.insert_one(client_doc)
        
        # Create properties
        for prop_data in data.properties:
            prop = Property(
                client_id=client.client_id,
                address_line_1=prop_data["address_line_1"],
                address_line_2=prop_data.get("address_line_2"),
                city=prop_data["city"],
                postcode=prop_data["postcode"],
                property_type=prop_data.get("property_type", "residential"),
                number_of_units=prop_data.get("number_of_units", 1)
            )
            
            prop_doc = prop.model_dump()
            for key in ["created_at", "updated_at"]:
                if prop_doc.get(key):
                    prop_doc[key] = prop_doc[key].isoformat()
            
            await db.properties.insert_one(prop_doc)
        
        # Audit log
        await create_audit_log(
            action=AuditAction.INTAKE_SUBMITTED,
            client_id=client.client_id,
            metadata={
                "email": data.email,
                "properties_count": len(data.properties),
                "billing_plan": data.billing_plan.value
            }
        )
        
        logger.info(f"Intake submitted for {data.email}")
        
        return {
            "message": "Intake submitted successfully",
            "client_id": client.client_id,
            "next_step": "checkout"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Intake submission error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process intake"
        )

@router.post("/checkout")
async def create_checkout(request: Request, client_id: str):
    """Create Stripe checkout session."""
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Get origin from request
        origin = request.headers.get("origin") or "http://localhost:3000"
        
        # Create checkout session
        session = await stripe_service.create_checkout_session(
            client_id=client_id,
            billing_plan=client["billing_plan"],
            origin_url=origin
        )
        
        return {
            "checkout_url": session.url,
            "session_id": session.session_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Checkout creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )

@router.get("/onboarding-status/{client_id}")
async def get_onboarding_status(client_id: str):
    """Get detailed client onboarding status with step-by-step progress."""
    db = database.get_db()
    
    try:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Get portal user if exists
        portal_user = await db.portal_users.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        # Get properties count
        properties_count = await db.properties.count_documents({"client_id": client_id})
        
        # Get requirements count
        requirements_count = await db.requirements.count_documents(
            {"property_id": {"$in": [p["property_id"] async for p in db.properties.find({"client_id": client_id}, {"property_id": 1})]}}
        ) if properties_count > 0 else 0
        
        # Determine step statuses
        onboarding_status = client.get("onboarding_status", "INTAKE_PENDING")
        subscription_status = client.get("subscription_status", "PENDING")
        
        # Step 1: Intake - Always complete if we have a client record
        intake_complete = True
        
        # Step 2: Payment
        payment_complete = subscription_status in ["ACTIVE", "PAID"]
        payment_pending = subscription_status == "PENDING"
        
        # Step 3: Provisioning
        provisioning_complete = onboarding_status == "PROVISIONED"
        provisioning_in_progress = onboarding_status == "PROVISIONING"
        provisioning_failed = onboarding_status == "FAILED"
        
        # Step 4: Account Setup (password set)
        account_setup_complete = portal_user and portal_user.get("password_status") == "SET"
        account_invited = portal_user and portal_user.get("status") == "INVITED"
        
        # Step 5: Ready to use
        ready_to_use = provisioning_complete and account_setup_complete
        
        # Build steps array
        steps = [
            {
                "step": 1,
                "name": "Intake Form",
                "description": "Submit your details and property information",
                "status": "complete" if intake_complete else "pending",
                "icon": "clipboard-check"
            },
            {
                "step": 2,
                "name": "Payment",
                "description": "Complete subscription payment",
                "status": "complete" if payment_complete else ("pending" if payment_pending else "waiting"),
                "icon": "credit-card"
            },
            {
                "step": 3,
                "name": "Portal Setup",
                "description": "Your compliance portal is being configured",
                "status": "complete" if provisioning_complete else ("in_progress" if provisioning_in_progress else ("failed" if provisioning_failed else "waiting")),
                "icon": "settings"
            },
            {
                "step": 4,
                "name": "Account Activation",
                "description": "Set your password to access the portal",
                "status": "complete" if account_setup_complete else ("pending" if account_invited else "waiting"),
                "icon": "key"
            },
            {
                "step": 5,
                "name": "Ready to Use",
                "description": "Your compliance dashboard is ready",
                "status": "complete" if ready_to_use else "waiting",
                "icon": "check-circle"
            }
        ]
        
        # Calculate overall progress percentage
        complete_steps = sum(1 for s in steps if s["status"] == "complete")
        progress_percent = int((complete_steps / len(steps)) * 100)
        
        # Current step (first non-complete step)
        current_step = next((s["step"] for s in steps if s["status"] != "complete"), 5)
        
        return {
            "client_id": client["client_id"],
            "client_name": client.get("full_name"),
            "email": client["email"],
            "onboarding_status": onboarding_status,
            "subscription_status": subscription_status,
            "steps": steps,
            "current_step": current_step,
            "progress_percent": progress_percent,
            "is_complete": ready_to_use,
            "properties_count": properties_count,
            "requirements_count": requirements_count,
            "can_login": ready_to_use,
            "portal_url": "/app/dashboard" if ready_to_use else None,
            "next_action": _get_next_action(steps, current_step)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Onboarding status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get onboarding status"
        )

def _get_next_action(steps, current_step):
    """Get the next action the client needs to take."""
    step = next((s for s in steps if s["step"] == current_step), None)
    if not step:
        return None
    
    actions = {
        1: {"action": "complete_intake", "message": "Complete the intake form to get started"},
        2: {"action": "complete_payment", "message": "Complete payment to activate your subscription"},
        3: {"action": "wait_provisioning", "message": "Please wait while we set up your portal"},
        4: {"action": "set_password", "message": "Check your email and set your password"},
        5: {"action": "login", "message": "Your portal is ready! Log in to get started"}
    }
    
    return actions.get(current_step)
