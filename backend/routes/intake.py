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
    """Get client onboarding status."""
    db = database.get_db()
    
    try:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        return {
            "client_id": client["client_id"],
            "onboarding_status": client["onboarding_status"],
            "subscription_status": client["subscription_status"],
            "email": client["email"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Onboarding status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get onboarding status"
        )
