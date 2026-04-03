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
    OrderStatus,
    TransitionType,
    is_valid_transition,
    requires_admin_action,
    is_terminal_state,
    requires_admin_notification,
    is_sla_paused,
    get_allowed_transitions,
    PIPELINE_COLUMNS,
    AUTOMATIC_GENERATION_RETRY_METADATA_KEY,
    AUTOMATIC_GENERATION_RETRY_METADATA_VALUE,
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
        allow_system_auto_retry = (
            triggered_by_type == "system"
            and current_status == OrderStatus.FAILED
            and new_status == OrderStatus.QUEUED
            and (metadata or {}).get(AUTOMATIC_GENERATION_RETRY_METADATA_KEY)
            == AUTOMATIC_GENERATION_RETRY_METADATA_VALUE
        )
        if triggered_by_type != "admin" and not allow_system_auto_retry:
            raise ValueError(
                f"Transition {current_status.value} → {new_status.value} requires admin action"
            )
        if not reason:
            raise ValueError("Transitions that require an audit reason must include `reason`")
    
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
    
    # Save failure reason when transitioning to FAILED status
    if new_status == OrderStatus.FAILED and reason:
        update_fields["failure_reason"] = reason
        update_fields["failed_at"] = datetime.now(timezone.utc)
    
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

    # Task: each transition also writes workflow_events record (same event, dual-write for consumers)
    now = execution_doc["created_at"]
    event_id = execution_id  # reuse so one logical event has same id in both collections
    actor_id = triggered_by_user_id or triggered_by_email
    workflow_event_doc = {
        "event_id": event_id,
        "order_id": order_id,
        "from_status": previous_state,
        "to_status": new_state,
        "transition_type": transition_type,
        "actor_id": actor_id,
        "metadata": {
            "reason": reason,
            "notes": notes,
            "triggered_by_type": triggered_by_type,
            **(metadata or {}),
        },
        "created_at": now,
    }
    try:
        await db.workflow_events.insert_one(workflow_event_doc)
    except Exception as e:
        logger.warning("workflow_events insert failed (non-fatal): %s", e)

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
        
        from services.notification_orchestrator import notification_orchestrator
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
        if admin.get("email"):
            try:
                await notification_orchestrator.send(
                    template_key="ORDER_NOTIFICATION",
                    client_id=None,
                    context={"recipient": admin["email"], "subject": subject, "message": message},
                    idempotency_key=f"{order_id}_ORDER_NOTIFICATION_admin_{status.value}",
                    event_type="order_admin_notify",
                )
                logger.info(f"Admin email notification sent for {order_id}")
            except Exception as e:
                logger.error(f"Failed to send admin email: {e}")
        if admin.get("phone"):
            try:
                sms_body = f"Order {order_id} needs attention: {status.value}. Check admin dashboard."
                await notification_orchestrator.send(
                    template_key="ADMIN_MANUAL_SMS",
                    client_id=None,
                    context={"recipient": admin["phone"], "body": sms_body},
                    idempotency_key=f"{order_id}_ADMIN_MANUAL_SMS_{status.value}",
                    event_type="order_admin_sms",
                )
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


# ============================================================================
# CLIENT INPUT REQUEST & RESPONSE HANDLING
# ============================================================================

async def create_client_input_request(
    order_id: str,
    admin_id: str,
    admin_email: str,
    request_notes: str,
    requested_fields: Optional[List[str]] = None,
    deadline_days: Optional[int] = None,
    request_attachments: bool = False,
) -> Dict:
    """
    Create a client input request when admin clicks 'Request More Info'.
    Stores the request details on the order for client to respond to.
    """
    db = database.get_db()
    
    order = await db.orders.find_one({"order_id": order_id})
    if not order:
        raise ValueError(f"Order not found: {order_id}")
    
    # Calculate deadline if specified
    deadline = None
    if deadline_days:
        from datetime import timedelta
        deadline = (datetime.now(timezone.utc) + timedelta(days=deadline_days)).isoformat()
    
    # Create the request record
    input_request = {
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "requested_by_admin_id": admin_id,
        "requested_by_admin_email": admin_email,
        "request_notes": request_notes,
        "requested_fields": requested_fields or [],
        "deadline": deadline,
        "request_attachments": request_attachments,
        "status": "PENDING",
    }
    
    # Update order with the request
    await db.orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "client_input_request": input_request,
                "regen_notes_current": None,  # Clear any pending regen notes
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )
    
    logger.info(f"Client input request created for order {order_id} by {admin_email}")
    return await db.orders.find_one({"order_id": order_id}, {"_id": 0})


async def submit_client_input_response(
    order_id: str,
    client_id: str,
    client_email: str,
    payload: Dict[str, Any],
    file_references: Optional[List[Dict]] = None,
) -> Dict:
    """
    Submit client's response to an input request.
    Stores versioned response and triggers workflow to return to INTERNAL_REVIEW.
    """
    db = database.get_db()
    
    order = await db.orders.find_one({"order_id": order_id})
    if not order:
        raise ValueError(f"Order not found: {order_id}")
    
    if order.get("status") != OrderStatus.CLIENT_INPUT_REQUIRED.value:
        raise ValueError(f"Order is not awaiting client input: {order['status']}")
    
    # Get existing responses for versioning
    existing_responses = order.get("client_input_responses", [])
    new_version = len(existing_responses) + 1
    
    # Create response record
    response_record = {
        "version": new_version,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "submitted_by_client_id": client_id,
        "submitted_by_client_email": client_email,
        "payload": payload,
        "files": file_references or [],
    }
    
    # Update order with response
    await db.orders.update_one(
        {"order_id": order_id},
        {
            "$push": {"client_input_responses": response_record},
            "$set": {
                "client_input_request.status": "RECEIVED",
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )
    
    logger.info(f"Client input response v{new_version} submitted for order {order_id}")
    return await db.orders.find_one({"order_id": order_id}, {"_id": 0})


# ============================================================================
# REGENERATION REQUEST HANDLING
# ============================================================================

async def create_regeneration_request(
    order_id: str,
    admin_id: str,
    admin_email: str,
    reason: str,
    correction_notes: str,
    affected_sections: Optional[List[str]] = None,
    guardrails: Optional[Dict[str, bool]] = None,
) -> Dict:
    """
    Create a structured regeneration request from INTERNAL_REVIEW.
    Stores the request details for the regeneration process.
    """
    db = database.get_db()
    
    order = await db.orders.find_one({"order_id": order_id})
    if not order:
        raise ValueError(f"Order not found: {order_id}")
    
    # Create the regeneration request record
    regen_request = {
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "requested_by_admin_id": admin_id,
        "requested_by_admin_email": admin_email,
        "reason": reason,
        "correction_notes": correction_notes,
        "affected_sections": affected_sections or [],
        "guardrails": guardrails or {},
    }
    
    # Update order with the request
    await db.orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "regen_notes_current": regen_request,
                "updated_at": datetime.now(timezone.utc),
            },
            "$push": {
                "regeneration_history": regen_request,
            }
        }
    )
    
    logger.info(f"Regeneration request created for order {order_id} by {admin_email}")
    return await db.orders.find_one({"order_id": order_id}, {"_id": 0})


async def get_current_regeneration_notes(order_id: str) -> Optional[Dict]:
    """Get the current (pending) regeneration request."""
    db = database.get_db()
    order = await db.orders.find_one({"order_id": order_id}, {"regen_notes_current": 1})
    return order.get("regen_notes_current") if order else None


async def get_regeneration_history(order_id: str) -> List[Dict]:
    """Get all past regeneration requests for an order."""
    db = database.get_db()
    order = await db.orders.find_one({"order_id": order_id}, {"regeneration_history": 1})
    return order.get("regeneration_history", []) if order else []


# ============================================================================
# DOCUMENT APPROVAL & LOCKING
# ============================================================================

async def lock_approved_version(order_id: str, version: int, admin_email: str) -> Dict:
    """
    Lock an approved document version as final.
    Prevents further edits unless explicitly reopened.
    """
    db = database.get_db()
    
    order = await db.orders.find_one({"order_id": order_id})
    if not order:
        raise ValueError(f"Order not found: {order_id}")
    
    # Mark the version as approved and locked
    await db.orders.update_one(
        {
            "order_id": order_id,
            "document_versions.version": version,
        },
        {
            "$set": {
                "document_versions.$.is_approved": True,
                "document_versions.$.approved_at": datetime.now(timezone.utc).isoformat(),
                "document_versions.$.approved_by": admin_email,
                "approved_document_version": version,
                "version_locked": True,
                "version_locked_at": datetime.now(timezone.utc).isoformat(),
                "version_locked_by": admin_email,
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )
    
    logger.info(f"Document version {version} locked for order {order_id}")
    return await db.orders.find_one({"order_id": order_id}, {"_id": 0})


async def is_version_locked(order_id: str) -> bool:
    """Check if the order has a locked approved version."""
    db = database.get_db()
    order = await db.orders.find_one({"order_id": order_id}, {"version_locked": 1})
    return order.get("version_locked", False) if order else False


async def reopen_for_edit(order_id: str, admin_email: str, reason: str) -> Dict:
    """
    Reopen a locked order for editing.
    Requires explicit action and reason - logged in audit.
    """
    db = database.get_db()
    
    order = await db.orders.find_one({"order_id": order_id})
    if not order:
        raise ValueError(f"Order not found: {order_id}")
    
    # Create audit record for reopening
    await create_workflow_execution(
        order_id=order_id,
        previous_state=order["status"],
        new_state=order["status"],  # Same state
        transition_type=TransitionType.ADMIN_MANUAL.value,
        triggered_by_type="admin",
        triggered_by_email=admin_email,
        reason=f"[REOPEN] {reason}",
        metadata={"action": "reopen_for_edit", "previous_locked_version": order.get("approved_document_version")},
    )
    
    # Unlock the order
    await db.orders.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "version_locked": False,
                "reopened_at": datetime.now(timezone.utc).isoformat(),
                "reopened_by": admin_email,
                "reopened_reason": reason,
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )
    
    logger.info(f"Order {order_id} reopened for editing by {admin_email}")
    return await db.orders.find_one({"order_id": order_id}, {"_id": 0})


# ============================================================================
# ADMIN NOTIFICATION PREFERENCES
# ============================================================================

def _portal_user_prefs_query(admin_id: str) -> Dict:
    """Match the logged-in staff user by id only. admin_route_guard already enforced staff role."""
    return {"$or": [{"portal_user_id": admin_id}, {"user_id": admin_id}]}


async def get_admin_notification_preferences(admin_id: str) -> Dict:
    """Get staff notification preferences. Lookup by portal_user_id or user_id (any admin-capable role)."""
    default_prefs = {
        "email_enabled": True,
        "sms_enabled": False,
        "in_app_enabled": True,
        "notification_email": None,
        "notification_phone": None,
    }
    if not admin_id:
        return default_prefs
    db = database.get_db()
    admin = await db.portal_users.find_one(
        _portal_user_prefs_query(admin_id),
        {"notification_preferences": 1, "email": 1, "phone": 1, "name": 1}
    )
    
    if not admin:
        return default_prefs
    
    prefs = admin.get("notification_preferences", {})
    return {
        "email_enabled": prefs.get("email_enabled", True),
        "sms_enabled": prefs.get("sms_enabled", False),
        "in_app_enabled": prefs.get("in_app_enabled", True),
        "notification_email": prefs.get("notification_email", admin.get("email")),
        "notification_phone": prefs.get("notification_phone", admin.get("phone")),
    }


async def update_admin_notification_preferences(
    admin_id: str,
    email_enabled: Optional[bool] = None,
    sms_enabled: Optional[bool] = None,
    in_app_enabled: Optional[bool] = None,
    notification_email: Optional[str] = None,
    notification_phone: Optional[str] = None,
) -> Dict:
    """Update admin's notification preferences."""
    db = database.get_db()
    
    update_fields = {"updated_at": datetime.now(timezone.utc)}
    
    if email_enabled is not None:
        update_fields["notification_preferences.email_enabled"] = email_enabled
    if sms_enabled is not None:
        update_fields["notification_preferences.sms_enabled"] = sms_enabled
    if in_app_enabled is not None:
        update_fields["notification_preferences.in_app_enabled"] = in_app_enabled
    if notification_email is not None:
        update_fields["notification_preferences.notification_email"] = notification_email
    if notification_phone is not None:
        update_fields["notification_preferences.notification_phone"] = notification_phone
    
    result = await db.portal_users.update_one(
        _portal_user_prefs_query(admin_id),
        {"$set": update_fields}
    )
    if result.matched_count == 0:
        logger.warning(
            "update_admin_notification_preferences: no portal_users row matched admin_id=%s",
            admin_id,
        )
        raise ValueError("Could not save notification preferences: portal user not found.")
    
    return await get_admin_notification_preferences(admin_id)


# ============================================================================
# IN-APP NOTIFICATIONS (enterprise inbox)
# ============================================================================

_INBOX_SEVERITY_ORDER = ("critical", "high", "medium", "low", "info")
_VALID_INBOX_FILTERS = frozenset(
    {"all", "unread", "critical", "compliance", "billing", "operations", "system"}
)


def _not_dismissed_query() -> Dict[str, Any]:
    return {"$or": [{"dismissed_at": None}, {"dismissed_at": {"$exists": False}}]}


def priority_string_to_severity(priority: Optional[str]) -> str:
    if not priority:
        return "medium"
    p = str(priority).lower()
    if p in ("urgent",):
        return "critical"
    if p in ("high",):
        return "high"
    if p in ("low",):
        return "low"
    if p in ("medium",):
        return "medium"
    return "medium"


def infer_in_app_severity(doc: Dict[str, Any]) -> str:
    raw = (doc.get("severity") or "").strip().lower()
    if raw in _INBOX_SEVERITY_ORDER:
        return raw
    return priority_string_to_severity(doc.get("priority"))


def infer_in_app_category(doc: Dict[str, Any]) -> str:
    cat = (doc.get("notification_category") or "").strip().lower()
    if cat in ("compliance", "billing", "operations", "system"):
        return cat
    nt = str(doc.get("notification_type") or doc.get("type") or "").lower()
    meta = doc.get("metadata") or {}
    if "admin_communication" in nt or str(meta.get("message_type") or "").lower() in (
        "broadcast",
        "announcement",
    ):
        return "system"
    if "billing" in nt or "invoice" in nt or "payment" in nt:
        return "billing"
    if "compliance" in nt or "requirement" in nt or "sla" in nt:
        return "compliance"
    if doc.get("order_id") or "order" in nt or "work_order" in nt or "maintenance" in nt:
        return "operations"
    return "system"


def serialize_in_app_notification(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize stored document for API/clients (legacy + new fields)."""
    out = dict(doc)
    for key in ("created_at", "read_at", "dismissed_at"):
        if key in out and out[key] is not None and hasattr(out[key], "isoformat"):
            out[key] = out[key].isoformat()
    nt = out.get("notification_type") or out.get("type") or "general"
    out["notification_type"] = nt
    out["severity"] = infer_in_app_severity(out)
    out["notification_category"] = infer_in_app_category(out)
    oid = out.get("related_entity_id") or out.get("order_id")
    if not out.get("related_entity_type") and oid and (out.get("order_id") or "order" in str(nt).lower()):
        out["related_entity_type"] = "order"
        out["related_entity_id"] = out.get("order_id") or oid
    if out.get("primary_cta_path") is None and out.get("link"):
        out["primary_cta_path"] = out["link"]
    return out


def _inbox_sort_key(doc: Dict[str, Any]) -> tuple:
    sev = infer_in_app_severity(doc)
    try:
        sev_i = _INBOX_SEVERITY_ORDER.index(sev)
    except ValueError:
        sev_i = len(_INBOX_SEVERITY_ORDER)
    unread = not bool(doc.get("is_read"))
    created = doc.get("created_at")
    if created is None:
        ts = 0.0
    elif hasattr(created, "timestamp"):
        ts = created.timestamp()
    else:
        ts = 0.0
    # Unread first, then severity (critical first), then newest
    return (0 if unread else 1, sev_i, -ts)


async def create_in_app_notification(
    recipient_id: str,
    title: str,
    message: str,
    notification_type: str,
    link: Optional[str] = None,
    metadata: Optional[Dict] = None,
    *,
    severity: Optional[str] = None,
    notification_category: Optional[str] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str] = None,
    primary_cta_label: Optional[str] = None,
    primary_cta_path: Optional[str] = None,
) -> str:
    """Create an in-app notification for a portal user (client or admin)."""
    db = database.get_db()

    notification_id = f"NOTIF-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)
    meta = dict(metadata or {})
    sev = (severity or meta.get("severity") or "medium")
    if isinstance(sev, str):
        sev = sev.strip().lower()
    if sev not in _INBOX_SEVERITY_ORDER:
        sev = "medium"

    cta_path = primary_cta_path if primary_cta_path is not None else link

    notification: Dict[str, Any] = {
        "notification_id": notification_id,
        "recipient_id": recipient_id,
        "title": title,
        "message": message,
        "notification_type": notification_type,
        "link": link,
        "metadata": meta,
        "is_read": False,
        "created_at": now,
        "severity": sev,
        "notification_category": notification_category,
        "related_entity_type": related_entity_type,
        "related_entity_id": related_entity_id,
        "primary_cta_label": primary_cta_label,
        "primary_cta_path": cta_path,
    }
    # Strip keys with None to avoid clutter (Mongo accepts null; we prefer absent for sparse indexes)
    notification = {k: v for k, v in notification.items() if v is not None}

    await db.in_app_notifications.insert_one(notification)
    logger.info("In-app notification created: %s for %s type=%s", notification_id, recipient_id, notification_type)

    return notification_id


async def notify_all_portal_admins_in_app(
    *,
    title: str,
    message: str,
    notification_type: str,
    severity: str = "high",
    notification_category: str = "operations",
    link: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str] = None,
    primary_cta_label: Optional[str] = None,
    primary_cta_path: Optional[str] = None,
) -> int:
    """Fan-out the same in-app notification to all admin/owner portal users."""
    db = database.get_db()
    admins = await db.portal_users.find(
        {"role": {"$in": ["ROLE_ADMIN", "admin", "ROLE_OWNER"]}},
        {"_id": 0, "portal_user_id": 1, "user_id": 1},
    ).to_list(length=500)
    count = 0
    for admin in admins:
        aid = admin.get("portal_user_id") or admin.get("user_id")
        if not aid:
            continue
        await create_in_app_notification(
            recipient_id=aid,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link,
            metadata=metadata,
            severity=severity,
            notification_category=notification_category,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            primary_cta_label=primary_cta_label,
            primary_cta_path=primary_cta_path,
        )
        count += 1
    return count


async def list_inbox_notifications(
    user_id: str,
    *,
    limit: int = 100,
    inbox_filter: str = "all",
) -> List[Dict]:
    """List non-dismissed notifications with filter; sorted for bell (unread + severity + recency)."""
    if inbox_filter not in _VALID_INBOX_FILTERS:
        inbox_filter = "all"
    db = database.get_db()
    and_parts: List[Dict[str, Any]] = [
        {"recipient_id": user_id},
        _not_dismissed_query(),
    ]
    if inbox_filter == "unread":
        and_parts.append({"is_read": False})
    elif inbox_filter == "critical":
        and_parts.append(
            {
                "$or": [
                    {"severity": "critical"},
                    {"priority": {"$in": ["urgent", "URGENT"]}},
                ]
            }
        )
    query: Dict[str, Any] = {"$and": and_parts}
    cursor = db.in_app_notifications.find(query, {"_id": 0})
    items = await cursor.to_list(length=max(limit * 4, 400))

    if inbox_filter in ("compliance", "billing", "operations", "system"):
        items = [d for d in items if infer_in_app_category(d) == inbox_filter]

    items.sort(key=_inbox_sort_key)
    return [serialize_in_app_notification(d) for d in items[:limit]]


async def get_unread_notifications(user_id: str, limit: int = 50) -> List[Dict]:
    """Unread-only slice (non-dismissed), sorted for inbox."""
    return await list_inbox_notifications(user_id, limit=limit, inbox_filter="unread")


async def get_all_notifications(user_id: str, limit: int = 100) -> List[Dict]:
    """All non-dismissed notifications for a user."""
    return await list_inbox_notifications(user_id, limit=limit, inbox_filter="all")


async def mark_notification_read(notification_id: str, recipient_id: str) -> bool:
    """Mark a notification as read; must belong to recipient_id."""
    db = database.get_db()
    result = await db.in_app_notifications.update_one(
        {"notification_id": notification_id, "recipient_id": recipient_id, **_not_dismissed_query()},
        {"$set": {"is_read": True, "read_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0


async def dismiss_notification(notification_id: str, recipient_id: str) -> bool:
    """Soft-dismiss (archive) a notification for one recipient."""
    db = database.get_db()
    result = await db.in_app_notifications.update_one(
        {"notification_id": notification_id, "recipient_id": recipient_id},
        {"$set": {"dismissed_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0


async def mark_all_notifications_read(user_id: str) -> int:
    """Mark all non-dismissed notifications as read for a user."""
    db = database.get_db()
    result = await db.in_app_notifications.update_many(
        {"recipient_id": user_id, "is_read": False, **_not_dismissed_query()},
        {"$set": {"is_read": True, "read_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count


async def get_unread_count(user_id: str) -> int:
    """Count unread, non-dismissed notifications."""
    db = database.get_db()
    return await db.in_app_notifications.count_documents(
        {"recipient_id": user_id, "is_read": False, **_not_dismissed_query()}
    )


async def record_in_app_cta_action(
    notification_id: str,
    recipient_id: str,
    action_key: str,
) -> bool:
    """Append CTA action metadata (audit is logged by the route)."""
    db = database.get_db()
    doc = await db.in_app_notifications.find_one(
        {"notification_id": notification_id, "recipient_id": recipient_id},
        {"_id": 0, "actions_taken": 1},
    )
    if not doc:
        return False
    actions = list(doc.get("actions_taken") or [])
    actions.append(
        {
            "action_key": action_key,
            "at": datetime.now(timezone.utc).isoformat(),
        }
    )
    await db.in_app_notifications.update_one(
        {"notification_id": notification_id, "recipient_id": recipient_id},
        {"$set": {"actions_taken": actions}},
    )
    return True
