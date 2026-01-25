"""ClearForm Credit Service

Handles all credit operations:
- Credit balance management
- Transaction recording
- Expiry tracking (FIFO)
- Subscription grants
- Purchase processing
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
import logging

from database import database
from clearform.models.credits import (
    CreditTransaction,
    CreditTransactionType,
    CreditWallet,
    CreditExpiry,
    CREDIT_EXPIRY_DAYS,
    DOCUMENT_CREDIT_COSTS,
)
from clearform.models.user import ClearFormUser

logger = logging.getLogger(__name__)


class CreditService:
    """Credit economy management service."""
    
    def __init__(self):
        self.db = None
    
    def _get_db(self):
        if self.db is None:
            self.db = database.get_db()
        return self.db
    
    async def get_wallet(self, user_id: str) -> CreditWallet:
        """Get detailed wallet information for a user."""
        db = self._get_db()
        
        # Get user for balance
        user = await db.clearform_users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Get expiring credits (next 30 days)
        thirty_days = datetime.now(timezone.utc) + timedelta(days=30)
        expiring_cursor = db.clearform_credit_expiry.find({
            "user_id": user_id,
            "expired": False,
            "remaining_amount": {"$gt": 0},
            "expires_at": {"$lte": thirty_days}
        }, {"_id": 0})
        
        expiring_credits = 0
        next_expiry_date = None
        next_expiry_amount = 0
        
        async for exp in expiring_cursor:
            expiring_credits += exp["remaining_amount"]
            if next_expiry_date is None or exp["expires_at"] < next_expiry_date:
                next_expiry_date = exp["expires_at"]
                next_expiry_amount = exp["remaining_amount"]
        
        # Get this month's usage
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_usage = await db.clearform_credit_transactions.aggregate([
            {
                "$match": {
                    "user_id": user_id,
                    "transaction_type": CreditTransactionType.DOCUMENT_GENERATION.value,
                    "created_at": {"$gte": month_start}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_used": {"$sum": {"$abs": "$amount"}},
                    "doc_count": {"$sum": 1}
                }
            }
        ]).to_list(1)
        
        credits_used = month_usage[0]["total_used"] if month_usage else 0
        docs_generated = month_usage[0]["doc_count"] if month_usage else 0
        
        # Get next grant date from user subscription
        next_grant_date = user.get("next_credit_grant_at")
        next_grant_amount = 0
        if user.get("subscription_plan"):
            from clearform.models.subscriptions import CLEARFORM_PLANS, ClearFormPlan
            try:
                plan = ClearFormPlan(user["subscription_plan"])
                if plan in CLEARFORM_PLANS:
                    next_grant_amount = CLEARFORM_PLANS[plan].monthly_credits
            except ValueError:
                pass
        
        return CreditWallet(
            user_id=user_id,
            total_balance=user.get("credit_balance", 0),
            expiring_soon=expiring_credits,
            credits_used_this_month=credits_used,
            documents_generated_this_month=docs_generated,
            next_expiry_date=next_expiry_date,
            next_expiry_amount=next_expiry_amount,
            next_grant_date=next_grant_date,
            next_grant_amount=next_grant_amount,
        )
    
    async def add_credits(
        self,
        user_id: str,
        amount: int,
        transaction_type: CreditTransactionType,
        description: str,
        reference_id: Optional[str] = None,
        reference_type: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> CreditTransaction:
        """Add credits to user's wallet.
        
        Creates transaction record and expiry tracking.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive for adding credits")
        
        db = self._get_db()
        
        # Get current balance
        user = await db.clearform_users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        current_balance = user.get("credit_balance", 0)
        new_balance = current_balance + amount
        
        # Create transaction
        transaction = CreditTransaction(
            user_id=user_id,
            transaction_type=transaction_type,
            amount=amount,
            balance_after=new_balance,
            reference_id=reference_id,
            reference_type=reference_type,
            description=description,
            expires_at=expires_at or (datetime.now(timezone.utc) + timedelta(days=CREDIT_EXPIRY_DAYS)),
        )
        
        # Create expiry record
        expiry = CreditExpiry(
            user_id=user_id,
            original_amount=amount,
            remaining_amount=amount,
            source_type=transaction_type,
            source_id=reference_id or transaction.transaction_id,
            expires_at=transaction.expires_at,
        )
        
        # Update user balance and record transaction
        await db.clearform_users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "credit_balance": new_balance,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$inc": {"lifetime_credits_purchased": amount}
            }
        )
        
        await db.clearform_credit_transactions.insert_one(transaction.model_dump())
        await db.clearform_credit_expiry.insert_one(expiry.model_dump())
        
        logger.info(f"Added {amount} credits to user {user_id}. New balance: {new_balance}")
        return transaction
    
    async def deduct_credits(
        self,
        user_id: str,
        amount: int,
        transaction_type: CreditTransactionType,
        description: str,
        reference_id: Optional[str] = None,
        reference_type: Optional[str] = None,
    ) -> Tuple[CreditTransaction, bool]:
        """Deduct credits from user's wallet using FIFO.
        
        Returns (transaction, success).
        If insufficient credits, returns (None, False).
        """
        if amount <= 0:
            raise ValueError("Amount must be positive for deduction")
        
        db = self._get_db()
        
        # Get current balance
        user = await db.clearform_users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        current_balance = user.get("credit_balance", 0)
        
        if current_balance < amount:
            logger.warning(f"Insufficient credits for user {user_id}. Has {current_balance}, needs {amount}")
            return None, False
        
        new_balance = current_balance - amount
        
        # FIFO: Deduct from oldest expiry batches first
        remaining_to_deduct = amount
        expiry_cursor = db.clearform_credit_expiry.find({
            "user_id": user_id,
            "expired": False,
            "remaining_amount": {"$gt": 0}
        }, {"_id": 0}).sort("expires_at", 1)  # Oldest first
        
        async for expiry in expiry_cursor:
            if remaining_to_deduct <= 0:
                break
            
            deduct_from_this = min(expiry["remaining_amount"], remaining_to_deduct)
            new_remaining = expiry["remaining_amount"] - deduct_from_this
            
            await db.clearform_credit_expiry.update_one(
                {"expiry_id": expiry["expiry_id"]},
                {"$set": {"remaining_amount": new_remaining}}
            )
            
            remaining_to_deduct -= deduct_from_this
        
        # Create transaction
        transaction = CreditTransaction(
            user_id=user_id,
            transaction_type=transaction_type,
            amount=-amount,  # Negative for deductions
            balance_after=new_balance,
            reference_id=reference_id,
            reference_type=reference_type,
            description=description,
        )
        
        # Update user balance
        await db.clearform_users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "credit_balance": new_balance,
                    "updated_at": datetime.now(timezone.utc),
                },
                "$inc": {"lifetime_credits_used": amount}
            }
        )
        
        await db.clearform_credit_transactions.insert_one(transaction.model_dump())
        
        logger.info(f"Deducted {amount} credits from user {user_id}. New balance: {new_balance}")
        return transaction, True
    
    async def check_balance(self, user_id: str, required_amount: int) -> bool:
        """Check if user has sufficient credits."""
        db = self._get_db()
        user = await db.clearform_users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            return False
        return user.get("credit_balance", 0) >= required_amount
    
    async def get_document_cost(self, document_type: str) -> int:
        """Get credit cost for a document type."""
        return DOCUMENT_CREDIT_COSTS.get(document_type, 1)
    
    async def process_expired_credits(self) -> Dict[str, int]:
        """Process all expired credits (scheduled job).
        
        Returns dict with counts of users and credits affected.
        """
        db = self._get_db()
        now = datetime.now(timezone.utc)
        
        # Find all expired batches
        expired_cursor = db.clearform_credit_expiry.find({
            "expired": False,
            "remaining_amount": {"$gt": 0},
            "expires_at": {"$lt": now}
        }, {"_id": 0})
        
        users_affected = set()
        total_expired = 0
        
        async for expiry in expired_cursor:
            user_id = expiry["user_id"]
            expired_amount = expiry["remaining_amount"]
            
            # Get current balance
            user = await db.clearform_users.find_one({"user_id": user_id}, {"_id": 0})
            if not user:
                continue
            
            current_balance = user.get("credit_balance", 0)
            new_balance = max(0, current_balance - expired_amount)
            
            # Create expiry transaction
            transaction = CreditTransaction(
                user_id=user_id,
                transaction_type=CreditTransactionType.EXPIRY,
                amount=-expired_amount,
                balance_after=new_balance,
                reference_id=expiry["expiry_id"],
                reference_type="credit_expiry",
                description=f"Credits expired: {expired_amount} credits",
            )
            
            # Update expiry record
            await db.clearform_credit_expiry.update_one(
                {"expiry_id": expiry["expiry_id"]},
                {"$set": {"expired": True, "remaining_amount": 0}}
            )
            
            # Update user balance
            await db.clearform_users.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "credit_balance": new_balance,
                        "updated_at": now,
                    },
                    "$inc": {"lifetime_credits_expired": expired_amount}
                }
            )
            
            await db.clearform_credit_transactions.insert_one(transaction.model_dump())
            
            users_affected.add(user_id)
            total_expired += expired_amount
            
            logger.info(f"Expired {expired_amount} credits for user {user_id}")
        
        return {
            "users_affected": len(users_affected),
            "total_credits_expired": total_expired,
        }
    
    async def grant_subscription_credits(self, user_id: str, amount: int, subscription_id: str) -> CreditTransaction:
        """Grant monthly subscription credits."""
        return await self.add_credits(
            user_id=user_id,
            amount=amount,
            transaction_type=CreditTransactionType.SUBSCRIPTION_GRANT,
            description=f"Monthly subscription credit grant: {amount} credits",
            reference_id=subscription_id,
            reference_type="subscription",
        )
    
    async def get_transaction_history(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        transaction_type: Optional[CreditTransactionType] = None,
    ) -> List[Dict[str, Any]]:
        """Get credit transaction history for a user."""
        db = self._get_db()
        
        query = {"user_id": user_id}
        if transaction_type:
            query["transaction_type"] = transaction_type.value
        
        cursor = db.clearform_credit_transactions.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).skip(offset).limit(limit)
        
        return await cursor.to_list(limit)


# Global service instance
credit_service = CreditService()
