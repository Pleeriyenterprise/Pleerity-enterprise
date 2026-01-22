"""
Order Service - Business Logic Layer
Handles all order operations with proper state machine enforcement.

CVP ISOLATION: This service NEVER writes to CVP collections.
Read-only linkage via cvp_user_ref is allowed for display only.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from database import database
from services.order_workflow import (
    OrderStatus, TransitionType, 
    is_valid_transition, requires_admin_action, 
    is_terminal_state, requires_admin_notification,
    is_sla_paused, get_allowed_transitions,
    PIPELINE_COLUMNS
)

logger = logging.getLogger(__name__)


def generate_order_id() -> str:
    """Generate unique order ID: ORD-YYYY-XXXXXX"""
    year = datetime.now(timezone.utc).strftime("%Y")
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"ORD-{year}-{short_uuid}"


def generate_execution_id() -> str:
    """Generate unique workflow execution ID: WFE-XXXXXX"""
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"WFE-{short_uuid}"


async def create_order(
    order_type: str,
    service_code: str,
    service_name: str,
    service_category: str,
    customer_email: str,
    customer_name: str,
    customer_phone: Optional[str] = None,
    customer_company: Optional[str] = None,
    cvp_user_ref: Optional[str] = None,  # Read-only link, never required
    parameters: Optional[Dict] = None,
    base_price: int = 0,
    vat_amount: int = 0,
    sla_hours: Optional[int] = None,
) -> Dict:
    """
    Create a new order in CREATED status.
    Returns the created order document.
    """
    db = database.get_db()
    
    order_id = generate_order_id()
    total_amount = base_price + vat_amount
    
    order_doc = {
        "order_id": order_id,
        "order_type": order_type,
        
        # Customer (may or may not be CVP client)
        "customer": {
            "email": customer_email,
            "full_name": customer_name,
            "phone": customer_phone,
            "company_name": customer_company,
            "cvp_user_ref": cvp_user_ref,  # String only, never triggers CVP writes
        },
        
        # Service
        "service_code": service_code,
        "service_name": service_name,
        "service_category": service_category,
        "parameters": parameters or {},
        
        # Pricing
        "pricing": {
            "base_price": base_price,
            "vat_amount": vat_amount,
            "total_amount": total_amount,
            "currency": "gbp",
            "stripe_payment_intent_id": None,
            "stripe_checkout_session_id": None,
        },
        
        # Status & Workflow
        "status": OrderStatus.CREATED.value,
        "sla_hours": sla_hours,
        "sla_paused_at": None,
        "sla_pause_duration_hours": 0,
        
        # Deliverables
        "deliverables": [],
        
        # Tracking
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "completed_at": None,
        "delivered_at": None,
        
        # Internal
        "internal_notes": None,
    }
    
    await db.orders.insert_one(order_doc)
    
    # Create initial workflow execution entry
    await create_workflow_execution(
        order_id=order_id,
        previous_state=None,
        new_state=OrderStatus.CREATED.value,
        transition_type=TransitionType.SYSTEM.value,
        triggered_by_type="system",
    )
    
    logger.info(f"Order created: {order_id}")
    
    # Return without _id
    order_doc.pop("_id", None)
    return order_doc


async def transition_order_state(
    order_id: str,
    new_status: OrderStatus,
    triggered_by_type: str,  # "system", "admin", "customer"
    triggered_by_user_id: Optional[str] = None,
    triggered_by_email: Optional[str] = None,
    reason: Optional[str] = None,
    notes: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> Dict:
    """
    Transition an order to a new state with full validation and audit logging.
    This is the ONLY function that should modify order status.
    
    Raises ValueError for invalid transitions.
    Returns updated order document.
    """
    db = database.get_db()
    
    # Fetch current order
    order = await db.orders.find_one({"order_id": order_id})
    if not order:
        raise ValueError(f"Order not found: {order_id}")
    
    current_status = OrderStatus(order["status"])
    
    # Validate transition
    if not is_valid_transition(current_status, new_status):
        raise ValueError(
            f"Invalid transition: {current_status.value} → {new_status.value}. "
            f"Allowed: {[s.value for s in get_allowed_transitions(current_status)]}"
        )
    
    # Check if admin action required
    if requires_admin_action(current_status, new_status):
        if triggered_by_type != "admin":
            raise ValueError(
                f"Transition {current_status.value} → {new_status.value} requires admin action"
            )
        if not reason:
            raise ValueError("Admin manual transitions require a reason")
    
    # Handle SLA pause/resume
    update_fields = {
        "status": new_status.value,
        "updated_at": datetime.now(timezone.utc),
    }
    
    # Pause SLA when entering CLIENT_INPUT_REQUIRED
    if is_sla_paused(new_status) and not is_sla_paused(current_status):
        update_fields["sla_paused_at"] = datetime.now(timezone.utc)
    
    # Resume SLA when leaving CLIENT_INPUT_REQUIRED
    if is_sla_paused(current_status) and not is_sla_paused(new_status):
        if order.get("sla_paused_at"):
            pause_duration = (datetime.now(timezone.utc) - order["sla_paused_at"]).total_seconds() / 3600
            update_fields["sla_pause_duration_hours"] = order.get("sla_pause_duration_hours", 0) + pause_duration
            update_fields["sla_paused_at"] = None
    
    # Set completion timestamps
    if new_status == OrderStatus.COMPLETED:
        update_fields["completed_at"] = datetime.now(timezone.utc)
        update_fields["delivered_at"] = datetime.now(timezone.utc)
    
    # Update order
    await db.orders.update_one(
        {"order_id": order_id},
        {"$set": update_fields}
    )
    
    # Create audit trail
    await create_workflow_execution(
        order_id=order_id,
        previous_state=current_status.value,
        new_state=new_status.value,
        transition_type=(
            TransitionType.ADMIN_MANUAL.value if triggered_by_type == "admin"
            else TransitionType.CUSTOMER_ACTION.value if triggered_by_type == "customer"
            else TransitionType.SYSTEM.value
        ),
        triggered_by_type=triggered_by_type,
        triggered_by_user_id=triggered_by_user_id,
        triggered_by_email=triggered_by_email,
        reason=reason,
        notes=notes,
        metadata=metadata,
    )
    
    logger.info(f"Order {order_id} transitioned: {current_status.value} → {new_status.value}")
    
    # Check if admin notification needed
    if requires_admin_notification(new_status):
        await notify_admin_of_state(order_id, new_status)
    
    # Fetch and return updated order
    updated_order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    return updated_order


async def create_workflow_execution(
    order_id: str,
    previous_state: Optional[str],
    new_state: str,
    transition_type: str,
    triggered_by_type: str,
    triggered_by_user_id: Optional[str] = None,
    triggered_by_email: Optional[str] = None,
    reason: Optional[str] = None,
    notes: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> str:
    """
    Create an audit log entry for a workflow state transition.
    Returns the execution_id.
    """
    db = database.get_db()
    
    execution_id = generate_execution_id()
    
    execution_doc = {
        "execution_id": execution_id,
        "order_id": order_id,
        "previous_state": previous_state,
        "new_state": new_state,
        "transition_type": transition_type,
        "triggered_by": {
            "type": triggered_by_type,
            "user_id": triggered_by_user_id,
            "user_email": triggered_by_email,
        },
        "reason": reason,
        "notes": notes,
        "metadata": metadata,
        "created_at": datetime.now(timezone.utc),
    }
    
    await db.workflow_executions.insert_one(execution_doc)
    
    return execution_id


async def notify_admin_of_state(order_id: str, status: OrderStatus):
    """
    Send notification to admin when order reaches a state requiring attention.
    Sends both email and SMS.
    """
    try:
        db = database.get_db()
        order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
        
        if not order:
            return
        
        # Import here to avoid circular imports
        from services.email_service import send_email
        from services.sms_service import send_sms
        
        # Get admin contact info
        admin = await db.portal_users.find_one(
            {"role": "admin", "status": "active"},
            {"email": 1, "phone": 1, "name": 1}
        )
        
        if not admin:
            logger.warning("No active admin found for notification")
            return
        
        subject_map = {
            OrderStatus.INTERNAL_REVIEW: f"Order {order_id} Ready for Review",
            OrderStatus.FAILED: f"Order {order_id} Failed - Action Required",
            OrderStatus.DELIVERY_FAILED: f"Order {order_id} Delivery Failed",
        }
        
        subject = subject_map.get(status, f"Order {order_id} Status Update")
        
        message = (
            f"Order {order_id} has reached status: {status.value}\n"
            f"Service: {order.get('service_name', 'Unknown')}\n"
            f"Customer: {order.get('customer', {}).get('full_name', 'Unknown')}\n"
            f"Please review in the admin dashboard."
        )
        
        # Send email notification
        if admin.get("email"):
            try:
                await send_email(
                    to_email=admin["email"],
                    subject=subject,
                    body=message,
                )
                logger.info(f"Admin email notification sent for {order_id}")
            except Exception as e:
                logger.error(f"Failed to send admin email: {e}")
        
        # Send SMS notification
        if admin.get("phone"):
            try:
                sms_message = f"Order {order_id} needs attention: {status.value}. Check admin dashboard."
                await send_sms(admin["phone"], sms_message)
                logger.info(f"Admin SMS notification sent for {order_id}")
            except Exception as e:
                logger.error(f"Failed to send admin SMS: {e}")
                
    except Exception as e:
        logger.error(f"Failed to notify admin for order {order_id}: {e}")


async def get_order(order_id: str) -> Optional[Dict]:
    """Get order by ID"""
    db = database.get_db()
    return await db.orders.find_one({"order_id": order_id}, {"_id": 0})


async def get_order_timeline(order_id: str) -> List[Dict]:
    """Get all workflow executions for an order (audit timeline)"""
    db = database.get_db()
    cursor = db.workflow_executions.find(
        {"order_id": order_id},
        {"_id": 0}
    ).sort("created_at", 1)
    return await cursor.to_list(length=None)


async def get_orders_by_status(status: OrderStatus, limit: int = 100) -> List[Dict]:
    """Get orders by status"""
    db = database.get_db()
    cursor = db.orders.find(
        {"status": status.value},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=None)


async def get_pipeline_counts() -> Dict[str, int]:
    """Get count of orders in each pipeline column"""
    db = database.get_db()
    
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    
    cursor = db.orders.aggregate(pipeline)
    results = await cursor.to_list(length=None)
    
    counts = {col["status"].value: 0 for col in PIPELINE_COLUMNS}
    for result in results:
        if result["_id"] in counts:
            counts[result["_id"]] = result["count"]
    
    return counts


async def get_orders_for_pipeline(
    status_filter: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
) -> Dict:
    """
    Get orders grouped by status for pipeline view.
    Returns dict with orders grouped by status and total counts.
    """
    db = database.get_db()
    
    # Build query
    query = {}
    if status_filter:
        query["status"] = status_filter
    
    # Get orders
    cursor = db.orders.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    orders = await cursor.to_list(length=None)
    
    # Get total counts
    total = await db.orders.count_documents(query)
    counts = await get_pipeline_counts()
    
    return {
        "orders": orders,
        "total": total,
        "counts": counts,
    }


async def add_internal_note(order_id: str, note: str, admin_email: str) -> Dict:
    """Add internal note to an order (does NOT change state)"""
    db = database.get_db()
    
    order = await db.orders.find_one({"order_id": order_id})
    if not order:
        raise ValueError(f"Order not found: {order_id}")
    
    current_notes = order.get("internal_notes") or ""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    new_note = f"\n[{timestamp}] {admin_email}: {note}"
    
    await db.orders.update_one(
        {"order_id": order_id},
        {"$set": {
            "internal_notes": current_notes + new_note,
            "updated_at": datetime.now(timezone.utc),
        }}
    )
    
    return await db.orders.find_one({"order_id": order_id}, {"_id": 0})
