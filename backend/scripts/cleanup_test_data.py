"""
Aggressive Test Data Cleanup Script
Removes all test data to provide a clean slate for real testing.
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def cleanup_test_data():
    """Remove all test data from the database."""
    await database.connect()
    db = database.get_db()
    
    logger.info("="  * 80)
    logger.info("AGGRESSIVE TEST DATA CLEANUP")
    logger.info("=" * 80)
    
    # Count before
    total_orders = await db.orders.count_documents({})
    total_drafts = await db.intake_drafts.count_documents({})
    total_clients = await db.clients.count_documents({})
    total_executions = await db.workflow_executions.count_documents({})
    
    logger.info(f"\nBefore cleanup:")
    logger.info(f"  Orders: {total_orders}")
    logger.info(f"  Drafts: {total_drafts}")
    logger.info(f"  Clients: {total_clients}")
    logger.info(f"  Workflow Executions: {total_executions}")
    
    # 1. Delete ALL unpaid orders (test data)
    result1 = await db.orders.delete_many({
        "paid_at": {"$exists": False}
    })
    logger.info(f"\n✅ Deleted {result1.deleted_count} unpaid orders")
    
    # 2. Delete old FAILED orders (>48 hours)
    two_days_ago = datetime.now(timezone.utc) - timedelta(hours=48)
    result2 = await db.orders.delete_many({
        "status": "FAILED",
        "created_at": {"$lt": two_days_ago}
    })
    logger.info(f"✅ Deleted {result2.deleted_count} old failed orders")
    
    # 3. Delete old CANCELLED orders
    result3 = await db.orders.delete_many({
        "status": "CANCELLED",
        "created_at": {"$lt": two_days_ago}
    })
    logger.info(f"✅ Deleted {result3.deleted_count} old cancelled orders")
    
    # 4. Keep only last 5 drafts
    drafts = await db.intake_drafts.find({}, {"draft_id": 1}).sort("created_at", -1).skip(5).to_list(1000)
    if drafts:
        draft_ids = [d["draft_id"] for d in drafts]
        result4 = await db.intake_drafts.delete_many({"draft_id": {"$in": draft_ids}})
        logger.info(f"✅ Deleted {result4.deleted_count} old drafts (kept last 5)")
    
    # 5. Clean up orphaned workflow executions
    order_ids = await db.orders.distinct("order_id")
    result5 = await db.workflow_executions.delete_many({
        "order_id": {"$nin": order_ids}
    })
    logger.info(f"✅ Deleted {result5.deleted_count} orphaned workflow executions")
    
    # 6. Clean up test clients (clients with test email domains)
    result6 = await db.clients.delete_many({
        "email": {"$regex": "test_.*@pleerity\\.com"}
    })
    logger.info(f"✅ Deleted {result6.deleted_count} test clients")
    
    # Count after
    total_orders_after = await db.orders.count_documents({})
    total_drafts_after = await db.intake_drafts.count_documents({})
    total_clients_after = await db.clients.count_documents({})
    total_executions_after = await db.workflow_executions.count_documents({})
    
    logger.info("\n" + "=" * 80)
    logger.info("CLEANUP COMPLETE")
    logger.info("=" * 80)
    logger.info(f"\nAfter cleanup:")
    logger.info(f"  Orders: {total_orders_after} (removed {total_orders - total_orders_after})")
    logger.info(f"  Drafts: {total_drafts_after} (removed {total_drafts - total_drafts_after})")
    logger.info(f"  Clients: {total_clients_after} (removed {total_clients - total_clients_after})")
    logger.info(f"  Workflow Executions: {total_executions_after} (removed {total_executions - total_executions_after})")
    
    logger.info("\n✅ Database is now clean and ready for real data testing!")
    
    await database.close()


if __name__ == "__main__":
    asyncio.run(cleanup_test_data())
