"""ClearForm Credit Routes

Endpoints:
- GET /api/clearform/credits/wallet - Get wallet summary
- GET /api/clearform/credits/balance - Get simple balance
- GET /api/clearform/credits/history - Get transaction history
- GET /api/clearform/credits/packages - Get available credit packages
- POST /api/clearform/credits/purchase - Create checkout for credit purchase
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from pydantic import BaseModel
import logging

from clearform.models.credits import (
    CreditWallet,
    CreditTransaction,
    CreditPackage,
    CREDIT_PACKAGES,
)
from clearform.services.credit_service import credit_service
from clearform.routes.auth import get_current_clearform_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clearform/credits", tags=["ClearForm Credits"])


class BalanceResponse(BaseModel):
    credit_balance: int
    expiring_soon: int


class PurchaseRequest(BaseModel):
    package_id: str


class PurchaseResponse(BaseModel):
    checkout_url: str
    session_id: str


@router.get("/wallet", response_model=CreditWallet)
async def get_wallet(user = Depends(get_current_clearform_user)):
    """Get detailed wallet information.
    
    Includes:
    - Current balance
    - Expiring credits
    - Usage stats
    - Next events
    """
    try:
        return await credit_service.get_wallet(user.user_id)
    except Exception as e:
        logger.error(f"Failed to get wallet: {e}")
        raise HTTPException(status_code=500, detail="Failed to get wallet")


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(user = Depends(get_current_clearform_user)):
    """Get simple credit balance."""
    try:
        wallet = await credit_service.get_wallet(user.user_id)
        return BalanceResponse(
            credit_balance=wallet.total_balance,
            expiring_soon=wallet.expiring_soon,
        )
    except Exception as e:
        logger.error(f"Failed to get balance: {e}")
        raise HTTPException(status_code=500, detail="Failed to get balance")


@router.get("/history")
async def get_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    transaction_type: Optional[str] = None,
    user = Depends(get_current_clearform_user),
):
    """Get credit transaction history."""
    try:
        from clearform.models.credits import CreditTransactionType
        
        tx_type = None
        if transaction_type:
            try:
                tx_type = CreditTransactionType(transaction_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid transaction type: {transaction_type}")
        
        transactions = await credit_service.get_transaction_history(
            user_id=user.user_id,
            limit=limit,
            offset=offset,
            transaction_type=tx_type,
        )
        
        return {
            "transactions": transactions,
            "limit": limit,
            "offset": offset,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get history")


@router.get("/packages", response_model=List[CreditPackage])
async def get_packages():
    """Get available credit packages for purchase.
    
    No auth required - for display on pricing page.
    """
    return CREDIT_PACKAGES


@router.post("/purchase", response_model=PurchaseResponse)
async def create_purchase_checkout(
    request: PurchaseRequest,
    user = Depends(get_current_clearform_user),
):
    """Create Stripe checkout session for credit purchase.
    
    Returns checkout URL to redirect user.
    """
    try:
        import os
        import stripe
        
        # Find package
        package = next((p for p in CREDIT_PACKAGES if p.package_id == request.package_id), None)
        if not package:
            raise HTTPException(status_code=400, detail=f"Invalid package: {request.package_id}")
        
        stripe.api_key = os.getenv("STRIPE_API_KEY")
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        
        # Create or get Stripe customer
        from database import database
        db = database.get_db()
        
        user_data = await db.clearform_users.find_one({"user_id": user.user_id}, {"_id": 0})
        
        if user_data.get("stripe_customer_id"):
            customer_id = user_data["stripe_customer_id"]
        else:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.full_name,
                metadata={
                    "clearform_user_id": user.user_id,
                    "product": "clearform",
                }
            )
            customer_id = customer.id
            
            await db.clearform_users.update_one(
                {"user_id": user.user_id},
                {"$set": {"stripe_customer_id": customer_id}}
            )
        
        # Create checkout session
        # Note: In production, you'd create actual Stripe products/prices
        # For now, use one-time price
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "gbp",
                    "product_data": {
                        "name": f"ClearForm - {package.name}",
                        "description": f"{package.credits} document generation credits",
                    },
                    "unit_amount": package.price_gbp,
                },
                "quantity": 1,
            }],
            success_url=f"{frontend_url}/clearform/credits/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url}/clearform/credits",
            metadata={
                "clearform_user_id": user.user_id,
                "product": "clearform",
                "type": "credit_purchase",
                "package_id": package.package_id,
                "credits": str(package.credits),
            }
        )
        
        # Save pending top-up
        from clearform.models.credits import CreditTopUp
        from datetime import datetime, timezone, timedelta
        from clearform.models.credits import CREDIT_EXPIRY_DAYS
        
        topup = CreditTopUp(
            user_id=user.user_id,
            credits=package.credits,
            price_gbp=package.price_gbp,
            stripe_checkout_session_id=session.id,
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(days=CREDIT_EXPIRY_DAYS),
        )
        
        await db.clearform_credit_topups.insert_one(topup.model_dump())
        
        return PurchaseResponse(
            checkout_url=session.url,
            session_id=session.id,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create checkout: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout")


@router.get("/purchase/{session_id}/status")
async def get_purchase_status(
    session_id: str,
    user = Depends(get_current_clearform_user),
):
    """Check status of a credit purchase."""
    try:
        from database import database
        db = database.get_db()
        
        topup = await db.clearform_credit_topups.find_one({
            "stripe_checkout_session_id": session_id,
            "user_id": user.user_id,
        }, {"_id": 0})
        
        if not topup:
            raise HTTPException(status_code=404, detail="Purchase not found")
        
        return {
            "topup_id": topup["topup_id"],
            "status": topup["status"],
            "credits": topup["credits"],
            "completed_at": topup.get("completed_at"),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get purchase status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get purchase status")
