"""
Fix Stuck Orders Script
Identifies and fixes orders that are stuck in FINALISING without proper documents.

Issue: Orders in FINALISING status without document_versions or proper approval fields
Root Cause: Document generation failed silently, but workflow state advanced anyway

Solution: Move stuck orders back to QUEUED to retry generation
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import database
from services.order_service import transition_order_state
from services.order_workflow import OrderStatus
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def identify_stuck_orders():
    """
    Identify orders stuck in FINALISING without proper documents.
    
    Criteria for "stuck":
    - Status is FINALISING
    - Either:
      - document_versions is empty, OR
      - version_locked is False, OR  
      - approved_document_version is None/missing
    """
    db = database.get_db()
    
    # Find all FINALISING orders
    finalising_orders = await db.orders.find({
        "status": OrderStatus.FINALISING.value
    }, {"_id": 0}).to_list(length=100)
    
    stuck_orders = []
    
    for order in finalising_orders:
        order_id = order.get("order_id")
        doc_versions = order.get("document_versions", [])
        version_locked = order.get("version_locked", False)
        approved_version = order.get("approved_document_version")
        
        # Check if order is stuck
        is_stuck = (
            len(doc_versions) == 0 or 
            not version_locked or 
            not approved_version
        )
        
        if is_stuck:
            stuck_orders.append({
                "order_id": order_id,
                "service_code": order.get("service_code"),
                "paid_at": order.get("paid_at"),
                "customer_email": order.get("customer_email"),
                "doc_versions_count": len(doc_versions),
                "version_locked": version_locked,
                "approved_version": approved_version,
                "created_at": order.get("created_at"),
            })
    
    return stuck_orders


async def fix_stuck_order(order_id: str, reason: str = "auto_recovery") -> dict:
    """
    Fix a stuck order by moving it back to QUEUED for retry.
    
    Args:
        order_id: The order to fix
        reason: Reason for the fix
    
    Returns:
        dict with success status and details
    """
    db = database.get_db()
    
    # Get the order
    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        return {"success": False, "error": "Order not found"}
    
    # Clear any invalid approval fields
    await db.orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "version_locked": False,
                "approved_document_version": None,
                "approved_at": None,
                "approved_by": None,
            }
        }
    )
    
    # Transition back to QUEUED
    try:
        await transition_order_state(
            order_id=order_id,
            new_status=OrderStatus.QUEUED,
            triggered_by_type="system",
            reason=f"Auto-recovery: Order stuck in FINALISING without documents. Moved to QUEUED for retry. Reason: {reason}",
            metadata={
                "recovery_action": "stuck_order_fix",
                "recovery_reason": reason,
                "recovered_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        
        logger.info(f"Successfully recovered order {order_id} - moved to QUEUED")
        return {"success": True, "new_status": "QUEUED"}
        
    except Exception as e:
        logger.error(f"Failed to recover order {order_id}: {e}")
        return {"success": False, "error": str(e)}


async def main():
    """Main execution function."""
    await database.connect()
    
    logger.info("=" * 80)
    logger.info("STUCK ORDER RECOVERY SCRIPT")
    logger.info("=" * 80)
    
    # Step 1: Identify stuck orders
    logger.info("\nStep 1: Identifying stuck orders...")
    stuck_orders = await identify_stuck_orders()
    
    if not stuck_orders:
        logger.info("✅ No stuck orders found! All orders in FINALISING have proper documents.")
        await database.close()
        return
    
    logger.info(f"\n🚨 Found {len(stuck_orders)} stuck orders:")
    logger.info("=" * 80)
    
    for order in stuck_orders:
        logger.info(f"\nOrder ID: {order['order_id']}")
        logger.info(f"  Service: {order['service_code']}")
        logger.info(f"  Customer: {order.get('customer_email', 'N/A')}")
        logger.info(f"  Paid: {bool(order.get('paid_at'))}")
        logger.info(f"  Document Versions: {order['doc_versions_count']}")
        logger.info(f"  Version Locked: {order['version_locked']}")
        logger.info(f"  Approved Version: {order['approved_version']}")
    
    # Step 2: Ask for confirmation
    logger.info("\n" + "=" * 80)
    logger.info("Step 2: Recovery Action")
    logger.info("=" * 80)
    logger.info(f"This script will move {len(stuck_orders)} orders back to QUEUED status")
    logger.info("for automatic retry of document generation.")
    
    # Auto-proceed in script mode
    logger.info("\nProceeding with recovery...")
    
    # Step 3: Fix each order
    results = {"success": 0, "failed": 0, "errors": []}
    
    for order in stuck_orders:
        order_id = order["order_id"]
        result = await fix_stuck_order(order_id, reason="document_generation_failed")
        
        if result.get("success"):
            results["success"] += 1
        else:
            results["failed"] += 1
            results["errors"].append({
                "order_id": order_id,
                "error": result.get("error")
            })
    
    # Step 4: Report results
    logger.info("\n" + "=" * 80)
    logger.info("RECOVERY COMPLETE")
    logger.info("=" * 80)
    logger.info(f"✅ Successfully recovered: {results['success']}")
    logger.info(f"❌ Failed: {results['failed']}")
    
    if results["errors"]:
        logger.info("\nErrors:")
        for error in results["errors"]:
            logger.info(f"  - {error['order_id']}: {error['error']}")
    
    logger.info("\nNext Steps:")
    logger.info("1. The automated queue processor will pick up these orders")
    logger.info("2. They will go through document generation again")
    logger.info("3. Monitor the workflow_executions collection for progress")
    
    await database.close()


if __name__ == "__main__":
    asyncio.run(main())
