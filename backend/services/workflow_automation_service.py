"""
Order Workflow Automation Service
Implements WF1-WF10 as per workflow specification.

WORKFLOW DEFINITIONS:
- WF1: Payment Verified → Queue for Processing
- WF2: Queue → Document Generation (GPT + Render)
- WF3: Draft Ready → Internal Review
- WF4: Regeneration Request → Re-generation
- WF5: Client Input Required → Resume on Response
- WF6: Approval → Finalization
- WF7: Finalization → Delivery
- WF8: Delivery Failure → Retry or Escalate
- WF9: SLA Monitoring → Warnings and Breaches
- WF10: Priority Order → Expedited Processing
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
from database import database
from services.order_workflow import (
    OrderStatus, TransitionType, is_valid_transition,
    SLA_PAUSED_STATES, TERMINAL_STATES, ADMIN_NOTIFICATION_STATES
)
from services.order_service import transition_order_state, get_order

logger = logging.getLogger(__name__)

# ============================================================================
# SLA Configuration (User-Specified)
# ============================================================================
# SLA clock: Starts at PAID, Pauses at CLIENT_INPUT_REQUIRED, Ends at COMPLETED
#
# Category-based SLA targets:
# - Document Packs: 48 hours standard, 24 hours fast-track
# - Compliance Services: 72 hours standard
# - Automation Services: 5 business days (120 hours)
# - Market Research: 3-5 business days depending on complexity
# ============================================================================

SLA_CONFIG_BY_CATEGORY = {
    "document_pack": {
        "standard_hours": 48,       # 2 business days
        "fast_track_hours": 24,     # 1 business day
        "warning_threshold": 0.75,  # Warn at 75% of SLA
    },
    "compliance": {
        "standard_hours": 72,       # 3 business days (HMO, Full Audit)
        "fast_track_hours": 24,     # Fast-track override
        "warning_threshold": 0.75,
    },
    "ai_automation": {
        "standard_hours": 120,      # 5 business days
        "fast_track_hours": 72,     # 3 business days for fast-track
        "warning_threshold": 0.80,  # Warn at 80% for longer SLAs
    },
    "market_research": {
        "standard_hours": 72,       # Basic: 3 days
        "advanced_hours": 120,      # Advanced: 5 days
        "fast_track_hours": 24,
        "warning_threshold": 0.75,
    },
    "subscription": {
        "standard_hours": 24,       # CVP features - on-demand
        "fast_track_hours": 12,
        "warning_threshold": 0.80,
    },
    # Default fallback
    "default": {
        "standard_hours": 48,
        "fast_track_hours": 24,
        "warning_threshold": 0.75,
    },
}

# Specific service code SLA overrides (in hours)
SLA_SERVICE_OVERRIDES = {
    # Compliance services
    "COMP_HMO": {"standard": 72, "fast_track": 24},            # HMO Audit
    "COMP_FULL_AUDIT": {"standard": 72, "fast_track": 24},     # Full Compliance Audit
    "COMP_MOVEOUT": {"standard": 48, "fast_track": 24},        # Move-in/out checklist
    
    # Automation services (longer turnaround)
    "AI_WF_BLUEPRINT": {"standard": 120, "fast_track": 72},    # Workflow Blueprint - 5 days
    "AI_PROC_MAP": {"standard": 120, "fast_track": 72},        # Business Process Mapping
    "AI_TOOLS": {"standard": 72, "fast_track": 48},            # AI Tool Report - 3 days
    
    # Market research
    "MR_BASIC": {"standard": 72, "fast_track": 24},            # Basic - 3 days
    "MR_ADV": {"standard": 120, "fast_track": 48},             # Advanced - 5 days
    
    # Document packs (fastest)
    "DOC_PACK_ESSENTIAL": {"standard": 48, "fast_track": 24},  # Essential - 2 days
    "DOC_PACK_PLUS": {"standard": 48, "fast_track": 24},       # Plus - 2 days
    "DOC_PACK_PRO": {"standard": 48, "fast_track": 24},        # Pro - 2 days
}

# Fast-track MUST NOT bypass these controls
FAST_TRACK_GUARDRAILS = [
    "human_review",      # Admin must review before approval
    "audit_logs",        # All actions logged
    "versioning",        # Document versions tracked
    "sla_tracking",      # SLA still monitored
]


def get_sla_hours_for_order(order: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get SLA configuration for an order based on service code and category.
    
    Returns dict with:
    - target_hours: SLA deadline in hours
    - warning_threshold: Percentage at which to send warning (0.75 = 75%)
    - sla_pause_states: States where SLA clock pauses
    """
    service_code = order.get("service_code", "")
    is_fast_track = order.get("fast_track", False) or order.get("priority", False)
    
    # Check service-specific overrides first
    if service_code in SLA_SERVICE_OVERRIDES:
        override = SLA_SERVICE_OVERRIDES[service_code]
        target = override["fast_track"] if is_fast_track else override["standard"]
        return {
            "target_hours": target,
            "warning_threshold": 0.75,
            "sla_pause_states": [OrderStatus.CLIENT_INPUT_REQUIRED.value],
        }
    
    # Fall back to category-based config
    category = order.get("category", "default")
    if category not in SLA_CONFIG_BY_CATEGORY:
        category = "default"
    
    config = SLA_CONFIG_BY_CATEGORY[category]
    target = config.get("fast_track_hours", 24) if is_fast_track else config.get("standard_hours", 48)
    
    return {
        "target_hours": target,
        "warning_threshold": config.get("warning_threshold", 0.75),
        "sla_pause_states": [OrderStatus.CLIENT_INPUT_REQUIRED.value],
    }


async def initialize_order_sla(order_id: str, order: Dict[str, Any]) -> Dict[str, Any]:
    """
    Initialize SLA fields for a newly paid order.
    Call this when order transitions to PAID status (WF1).
    
    Sets:
    - sla_target_at: When SLA deadline occurs
    - sla_warning_at: When SLA warning should trigger
    - sla_started_at: When SLA clock started (now)
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    
    sla_config = get_sla_hours_for_order(order)
    target_hours = sla_config["target_hours"]
    warning_threshold = sla_config["warning_threshold"]
    
    sla_target = now + timedelta(hours=target_hours)
    sla_warning = now + timedelta(hours=target_hours * warning_threshold)
    
    sla_fields = {
        "sla_started_at": now,
        "sla_target_at": sla_target,
        "sla_warning_at": sla_warning,
        "sla_target_hours": target_hours,
        "sla_paused_at": None,
        "sla_total_paused_duration": 0,
        "sla_warning_sent": False,
        "sla_breach_sent": False,
    }
    
    await db.orders.update_one(
        {"order_id": order_id},
        {"$set": sla_fields}
    )
    
    # Log SLA start event
    await db.workflow_executions.insert_one({
        "order_id": order_id,
        "event_type": "SLA_STARTED",
        "previous_state": None,
        "new_state": "SLA_ACTIVE",
        "triggered_by_type": "system",
        "timestamp": now,
        "metadata": {
            "target_hours": target_hours,
            "target_at": sla_target.isoformat(),
            "warning_at": sla_warning.isoformat(),
            "service_code": order.get("service_code"),
            "fast_track": order.get("fast_track", False),
        },
    })
    
    logger.info(f"SLA initialized for order {order_id}: {target_hours}h target, deadline {sla_target.isoformat()}")
    return sla_fields


async def log_sla_event(order_id: str, event_type: str, metadata: Dict[str, Any] = None):
    """
    Log an SLA timeline event for audit purposes.
    
    Event types:
    - SLA_STARTED: SLA clock began
    - SLA_PAUSED: Waiting for client input
    - SLA_RESUMED: Client provided input
    - SLA_WARNING_ISSUED: Warning notification sent
    - SLA_BREACHED: SLA deadline missed
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    
    await db.workflow_executions.insert_one({
        "order_id": order_id,
        "event_type": event_type,
        "triggered_by_type": "system",
        "timestamp": now,
        "metadata": metadata or {},
    })
    
    logger.info(f"SLA event logged for {order_id}: {event_type}")


# Max retry attempts for delivery
MAX_DELIVERY_RETRIES = 3


class WorkflowAutomationService:
    """
    Service for automating order workflows.
    Implements WF1-WF10 as per specification.
    """
    
    def __init__(self):
        self.notification_service = None
        self.orchestrator = None
    
    def _get_notification_service(self):
        """Lazy load notification service"""
        if not self.notification_service:
            from services.order_notification_service import order_notification_service
            self.notification_service = order_notification_service
        return self.notification_service
    
    def _get_orchestrator(self):
        """Lazy load document orchestrator"""
        if not self.orchestrator:
            from services.document_orchestrator import document_orchestrator
            self.orchestrator = document_orchestrator
        return self.orchestrator
    
    # =========================================================================
    # WF1: Payment Verified → Queue for Processing
    # =========================================================================
    
    async def wf1_payment_to_queue(self, order_id: str) -> Dict[str, Any]:
        """
        WF1: After payment is verified, queue order for processing.
        
        Trigger: Stripe webhook confirms payment
        Action: PAID → QUEUED
        Side effects:
        - Initialize SLA tracking (clock starts now)
        - Notify admins of new order
        - Special notification for fast-track/priority orders
        """
        order = await get_order(order_id)
        
        if not order:
            return {"success": False, "error": "Order not found"}
        
        if order["status"] != OrderStatus.PAID.value:
            return {"success": False, "error": f"Order not in PAID status (current: {order['status']})"}
        
        # Check for fast-track or priority
        is_fast_track = order.get("fast_track", False)
        is_priority = order.get("priority", False)
        has_printed_copy = order.get("printed_copy", False)
        
        # Initialize SLA tracking - clock starts at payment
        try:
            sla_fields = await initialize_order_sla(order_id, order)
            logger.info(f"WF1: SLA initialized for {order_id} - {sla_fields['sla_target_hours']}h deadline")
        except Exception as e:
            logger.warning(f"WF1: Failed to initialize SLA for {order_id}: {e}")
        
        # Mark order with special flags for queue processing
        db = database.get_db()
        update_fields = {}
        if is_fast_track or is_priority:
            update_fields["queue_priority"] = 10 if is_priority else 5  # Higher = processed first
            update_fields["expedited"] = True
        if has_printed_copy:
            update_fields["requires_postal_delivery"] = True
            update_fields["postal_status"] = "PENDING_PRINT"
        
        if update_fields:
            await db.orders.update_one(
                {"order_id": order_id},
                {"$set": update_fields}
            )
        
        # Transition to QUEUED
        await transition_order_state(
            order_id=order_id,
            new_status=OrderStatus.QUEUED,
            triggered_by_type="system",
            reason="WF1: Payment verified, order queued for processing",
        )
        
        # Notify admins of new order
        try:
            notif_service = self._get_notification_service()
            from services.order_notification_service import OrderNotificationEvent
            
            # Standard notification
            await notif_service.notify_order_event(
                event_type=OrderNotificationEvent.NEW_ORDER,
                order_id=order_id,
                order=order,
            )
            
            # Special notification for fast-track/priority
            if is_fast_track or is_priority:
                await notif_service.notify_order_event(
                    event_type=OrderNotificationEvent.PRIORITY_FLAGGED,
                    order_id=order_id,
                    order=order,
                    metadata={
                        "fast_track": is_fast_track,
                        "priority": is_priority,
                        "message": "⚡ FAST-TRACK order requires expedited processing"
                    }
                )
        except Exception as e:
            logger.warning(f"WF1: Failed to send new order notification: {e}")
        
        logger.info(f"WF1: Order {order_id} queued for processing (fast_track={is_fast_track}, priority={is_priority})")
        return {"success": True, "status": "QUEUED", "workflow": "WF1", "expedited": is_fast_track or is_priority}
    
    # =========================================================================
    # WF2: Queue → Document Generation (GPT + Render)
    # =========================================================================
    
    async def wf2_queue_to_generation(self, order_id: str) -> Dict[str, Any]:
        """
        WF2: Process queued order through document generation pipeline.
        
        Trigger: Worker picks up from queue
        Action: QUEUED → IN_PROGRESS → DRAFT_READY
        """
        db = database.get_db()
        order = await get_order(order_id)
        
        if not order:
            return {"success": False, "error": "Order not found"}
        
        if order["status"] != OrderStatus.QUEUED.value:
            return {"success": False, "error": f"Order not in QUEUED status (current: {order['status']})"}
        
        # Transition to IN_PROGRESS
        await transition_order_state(
            order_id=order_id,
            new_status=OrderStatus.IN_PROGRESS,
            triggered_by_type="system",
            reason="WF2: Starting document generation",
        )
        
        try:
            # Run document orchestration
            orchestrator = self._get_orchestrator()
            result = await orchestrator.execute_generation(
                order_id=order_id,
                intake_data=order.get("parameters", {}),
            )
            
            # Handle OrchestrationResult dataclass (has .success attribute, not .get())
            is_success = result.success if hasattr(result, 'success') else result.get("success") if isinstance(result, dict) else False
            result_version = result.version if hasattr(result, 'version') else result.get("version", 1) if isinstance(result, dict) else 1
            result_error = result.error_message if hasattr(result, 'error_message') else result.get("error") if isinstance(result, dict) else "Unknown error"
            
            if is_success:
                # Transition to DRAFT_READY
                await transition_order_state(
                    order_id=order_id,
                    new_status=OrderStatus.DRAFT_READY,
                    triggered_by_type="system",
                    reason=f"WF2: Document v{result_version} generated successfully",
                    metadata={
                        "version": result_version,
                    }
                )
                
                logger.info(f"WF2: Order {order_id} draft generated successfully")
                return {"success": True, "status": "DRAFT_READY", "workflow": "WF2", "version": result_version}
            else:
                # Generation failed
                await transition_order_state(
                    order_id=order_id,
                    new_status=OrderStatus.FAILED,
                    triggered_by_type="system",
                    reason=f"WF2: Document generation failed: {result_error}",
                )
                
                # Notify of failure
                try:
                    notif_service = self._get_notification_service()
                    await notif_service.notify_order_failed(
                        order_id=order_id,
                        error=result_error,
                        order=order,
                    )
                except Exception as e:
                    logger.warning(f"WF2: Failed to send failure notification: {e}")
                
                return {"success": False, "status": "FAILED", "workflow": "WF2", "error": result_error}
                
        except Exception as e:
            logger.error(f"WF2: Generation error for {order_id}: {e}")
            
            await transition_order_state(
                order_id=order_id,
                new_status=OrderStatus.FAILED,
                triggered_by_type="system",
                reason=f"WF2: Generation exception: {str(e)}",
            )
            
            return {"success": False, "status": "FAILED", "workflow": "WF2", "error": str(e)}
    
    # =========================================================================
    # WF3: Draft Ready → Internal Review
    # =========================================================================
    
    async def wf3_draft_to_review(self, order_id: str) -> Dict[str, Any]:
        """
        WF3: Move draft to internal review queue.
        
        Trigger: Draft generation complete
        Action: DRAFT_READY → INTERNAL_REVIEW
        """
        db = database.get_db()
        order = await get_order(order_id)
        
        if not order:
            return {"success": False, "error": "Order not found"}
        
        if order["status"] != OrderStatus.DRAFT_READY.value:
            return {"success": False, "error": f"Order not in DRAFT_READY status (current: {order['status']})"}
        
        # Transition to INTERNAL_REVIEW
        await transition_order_state(
            order_id=order_id,
            new_status=OrderStatus.INTERNAL_REVIEW,
            triggered_by_type="system",
            reason="WF3: Document ready for admin review",
        )
        
        # Notify admins document is ready for review
        try:
            notif_service = self._get_notification_service()
            from services.order_notification_service import OrderNotificationEvent
            
            # Get latest version number
            doc_versions = order.get("document_versions", [])
            latest_version = doc_versions[-1]["version"] if doc_versions else 1
            
            await notif_service.notify_document_ready(
                order_id=order_id,
                version=latest_version,
                order=order,
            )
        except Exception as e:
            logger.warning(f"WF3: Failed to send review notification: {e}")
        
        logger.info(f"WF3: Order {order_id} moved to internal review")
        return {"success": True, "status": "INTERNAL_REVIEW", "workflow": "WF3"}
    
    # =========================================================================
    # WF4: Regeneration Request → Re-generation
    # =========================================================================
    
    async def wf4_regeneration(self, order_id: str, regen_notes: str) -> Dict[str, Any]:
        """
        WF4: Process regeneration request.
        
        Trigger: Admin requests regeneration from INTERNAL_REVIEW
        Action: REGEN_REQUESTED → REGENERATING → INTERNAL_REVIEW
        """
        db = database.get_db()
        order = await get_order(order_id)
        
        if not order:
            return {"success": False, "error": "Order not found"}
        
        current_status = order["status"]
        if current_status not in [OrderStatus.REGEN_REQUESTED.value, OrderStatus.INTERNAL_REVIEW.value]:
            return {"success": False, "error": f"Order not in regeneration-eligible status (current: {current_status})"}
        
        # Transition to REGENERATING
        await transition_order_state(
            order_id=order_id,
            new_status=OrderStatus.REGENERATING,
            triggered_by_type="system",
            reason=f"WF4: Regenerating document with notes: {regen_notes[:100]}...",
        )
        
        try:
            # Run regeneration through orchestrator
            orchestrator = self._get_orchestrator()
            result = await orchestrator.execute_regeneration(
                order_id=order_id,
                intake_data=order.get("parameters", {}),
                regeneration_notes=regen_notes,
            )
            
            # Handle OrchestrationResult dataclass (has .success attribute, not .get())
            is_success = result.success if hasattr(result, 'success') else result.get("success") if isinstance(result, dict) else False
            result_version = result.version if hasattr(result, 'version') else result.get("version", 1) if isinstance(result, dict) else 1
            result_error = result.error_message if hasattr(result, 'error_message') else result.get("error") if isinstance(result, dict) else "Unknown error"
            
            if is_success:
                # Transition back to INTERNAL_REVIEW
                await transition_order_state(
                    order_id=order_id,
                    new_status=OrderStatus.INTERNAL_REVIEW,
                    triggered_by_type="system",
                    reason=f"WF4: Document v{result_version} regenerated successfully",
                    metadata={
                        "version": result_version,
                        "regeneration_notes": regen_notes,
                    }
                )
                
                # Notify of regeneration complete
                try:
                    notif_service = self._get_notification_service()
                    from services.order_notification_service import OrderNotificationEvent
                    await notif_service.notify_order_event(
                        event_type=OrderNotificationEvent.REGENERATION_COMPLETE,
                        order_id=order_id,
                        order=order,
                        message=f"Document v{result_version} ready for review",
                    )
                except Exception as e:
                    logger.warning(f"WF4: Failed to send regen complete notification: {e}")
                
                logger.info(f"WF4: Order {order_id} regenerated successfully")
                return {"success": True, "status": "INTERNAL_REVIEW", "workflow": "WF4", "version": result_version}
            else:
                # Regeneration failed - return to review
                await transition_order_state(
                    order_id=order_id,
                    new_status=OrderStatus.INTERNAL_REVIEW,
                    triggered_by_type="system",
                    reason=f"WF4: Regeneration failed: {result_error}",
                )
                
                return {"success": False, "status": "INTERNAL_REVIEW", "workflow": "WF4", "error": result_error}
                
        except Exception as e:
            logger.error(f"WF4: Regeneration error for {order_id}: {e}")
            
            # Return to review on error
            await transition_order_state(
                order_id=order_id,
                new_status=OrderStatus.INTERNAL_REVIEW,
                triggered_by_type="system",
                reason=f"WF4: Regeneration exception: {str(e)}",
            )
            
            return {"success": False, "status": "INTERNAL_REVIEW", "workflow": "WF4", "error": str(e)}
    
    # =========================================================================
    # WF5: Client Input Required → Resume on Response
    # =========================================================================
    
    async def wf5_client_response(self, order_id: str, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        WF5: Process client response and resume workflow.
        
        Trigger: Client submits requested information
        Action: CLIENT_INPUT_REQUIRED → INTERNAL_REVIEW (SLA resumes)
        Side effects:
        - Store client response with version
        - Resume SLA clock
        - Log SLA_RESUMED event
        - Notify admins
        """
        db = database.get_db()
        order = await get_order(order_id)
        
        if not order:
            return {"success": False, "error": "Order not found"}
        
        if order["status"] != OrderStatus.CLIENT_INPUT_REQUIRED.value:
            return {"success": False, "error": f"Order not awaiting client input (current: {order['status']})"}
        
        # Store client response
        client_responses = order.get("client_input_responses", [])
        client_responses.append({
            "version": len(client_responses) + 1,
            "payload": response_data,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        })
        
        # Calculate SLA pause duration
        pause_start = order.get("sla_paused_at")
        pause_duration_hours = 0
        if pause_start:
            pause_start_dt = datetime.fromisoformat(pause_start.replace("Z", "+00:00")) if isinstance(pause_start, str) else pause_start
            pause_duration_hours = (datetime.now(timezone.utc) - pause_start_dt).total_seconds() / 3600
        
        total_paused = order.get("sla_total_paused_duration", 0) + pause_duration_hours
        
        await db.orders.update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "client_input_responses": client_responses,
                    "sla_paused_at": None,
                    "sla_total_paused_duration": total_paused,
                    # Keep old field for backwards compat
                    "sla_pause_duration_hours": total_paused,
                }
            }
        )
        
        # Log SLA resume event
        await log_sla_event(order_id, "SLA_RESUMED", {
            "paused_duration_hours": pause_duration_hours,
            "total_paused_hours": total_paused,
            "response_version": len(client_responses),
        })
        
        # Transition back to INTERNAL_REVIEW
        await transition_order_state(
            order_id=order_id,
            new_status=OrderStatus.INTERNAL_REVIEW,
            triggered_by_type="customer_action",
            reason=f"WF5: Client responded with {len(response_data)} fields",
            metadata={"response_version": len(client_responses)},
        )
        
        # Notify admins of client response
        try:
            notif_service = self._get_notification_service()
            await notif_service.notify_client_responded(order_id=order_id, order=order)
        except Exception as e:
            logger.warning(f"WF5: Failed to send client response notification: {e}")
        
        logger.info(f"WF5: Client response received for {order_id}, SLA resumed (paused {pause_duration_hours:.1f}h)")
        return {"success": True, "status": "INTERNAL_REVIEW", "workflow": "WF5"}
    
    # =========================================================================
    # WF6: Approval → Finalization
    # =========================================================================
    
    async def wf6_approval_to_finalization(
        self,
        order_id: str,
        approved_version: int,
        admin_email: str,
        notes: str = None,
    ) -> Dict[str, Any]:
        """
        WF6: Process approval and start finalization.
        
        Trigger: Admin approves document
        Action: INTERNAL_REVIEW → FINALISING (version locked)
        """
        db = database.get_db()
        order = await get_order(order_id)
        
        if not order:
            return {"success": False, "error": "Order not found"}
        
        if order["status"] != OrderStatus.INTERNAL_REVIEW.value:
            return {"success": False, "error": f"Order not in review (current: {order['status']})"}
        
        # Lock the approved version
        approval_timestamp = datetime.now(timezone.utc)
        
        await db.orders.update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "approved_document_version": approved_version,
                    "approved_at": approval_timestamp,
                    "approved_by": admin_email,
                    "approval_notes": notes,
                    "version_locked": True,
                }
            }
        )
        
        # Transition to FINALISING
        await transition_order_state(
            order_id=order_id,
            new_status=OrderStatus.FINALISING,
            triggered_by_type="admin_manual",
            triggered_by_email=admin_email,
            reason=f"WF6: Document v{approved_version} approved and locked",
            metadata={"approved_version": approved_version},
        )
        
        logger.info(f"WF6: Order {order_id} approved by {admin_email}, version {approved_version} locked")
        return {
            "success": True,
            "status": "FINALISING",
            "workflow": "WF6",
            "approved_version": approved_version,
        }
    
    # =========================================================================
    # WF7: Finalization → Delivery
    # =========================================================================
    
    async def wf7_finalization_to_delivery(self, order_id: str) -> Dict[str, Any]:
        """
        WF7: Complete finalization and deliver to client.
        
        Trigger: Order in FINALISING with locked version
        Action: FINALISING → DELIVERING → COMPLETED
        """
        from services.order_delivery_service import order_delivery_service
        
        result = await order_delivery_service.deliver_order(order_id)
        
        if result.get("success"):
            logger.info(f"WF7: Order {order_id} delivered successfully")
            return {"success": True, "status": "COMPLETED", "workflow": "WF7"}
        else:
            logger.warning(f"WF7: Delivery failed for {order_id}: {result.get('error')}")
            return {"success": False, "status": result.get("status", "DELIVERY_FAILED"), "workflow": "WF7", "error": result.get("error")}
    
    # =========================================================================
    # WF8: Delivery Failure → Retry or Escalate
    # =========================================================================
    
    async def wf8_delivery_retry(self, order_id: str) -> Dict[str, Any]:
        """
        WF8: Handle delivery failure with retry logic.
        
        Trigger: Order in DELIVERY_FAILED
        Action: Retry up to MAX_DELIVERY_RETRIES, then escalate
        """
        db = database.get_db()
        order = await get_order(order_id)
        
        if not order:
            return {"success": False, "error": "Order not found"}
        
        if order["status"] != OrderStatus.DELIVERY_FAILED.value:
            return {"success": False, "error": f"Order not in DELIVERY_FAILED status (current: {order['status']})"}
        
        retry_count = order.get("delivery_retry_count", 0)
        
        if retry_count >= MAX_DELIVERY_RETRIES:
            # Max retries exceeded - escalate
            logger.warning(f"WF8: Max delivery retries ({MAX_DELIVERY_RETRIES}) exceeded for {order_id}")
            
            # Notify of escalation
            try:
                notif_service = self._get_notification_service()
                from services.order_notification_service import OrderNotificationEvent
                await notif_service.notify_order_event(
                    event_type=OrderNotificationEvent.ORDER_FAILED,
                    order_id=order_id,
                    order=order,
                    message=f"Delivery failed after {retry_count} attempts - manual intervention required",
                )
            except Exception as e:
                logger.warning(f"WF8: Failed to send escalation notification: {e}")
            
            return {
                "success": False,
                "status": "DELIVERY_FAILED",
                "workflow": "WF8",
                "error": f"Max retries ({MAX_DELIVERY_RETRIES}) exceeded",
                "escalated": True,
            }
        
        # Increment retry counter
        await db.orders.update_one(
            {"order_id": order_id},
            {"$set": {"delivery_retry_count": retry_count + 1}}
        )
        
        # Attempt redelivery
        from services.order_delivery_service import order_delivery_service
        result = await order_delivery_service.retry_delivery(order_id)
        
        if result.get("success"):
            logger.info(f"WF8: Order {order_id} redelivered successfully on attempt {retry_count + 1}")
            return {"success": True, "status": "COMPLETED", "workflow": "WF8", "retry_count": retry_count + 1}
        else:
            logger.warning(f"WF8: Retry {retry_count + 1} failed for {order_id}: {result.get('error')}")
            return {
                "success": False,
                "status": "DELIVERY_FAILED",
                "workflow": "WF8",
                "error": result.get("error"),
                "retry_count": retry_count + 1,
            }
    
    # =========================================================================
    # WF9: SLA Monitoring → Warnings and Breaches
    # =========================================================================
    
    async def wf9_sla_check(self) -> Dict[str, Any]:
        """
        WF9: Check all active orders for SLA warnings and breaches.
        
        Trigger: Scheduled job (every 15 minutes)
        Action: Send warnings at 75% SLA, breach notifications at 100%
        """
        db = database.get_db()
        
        # Get all non-terminal orders
        active_orders = await db.orders.find({
            "status": {"$nin": [s.value for s in TERMINAL_STATES] + [OrderStatus.CANCELLED.value]},
        }).to_list(length=500)
        
        results = {
            "checked": 0,
            "warnings_sent": 0,
            "breaches_sent": 0,
            "paused_skipped": 0,
        }
        
        now = datetime.now(timezone.utc)
        
        for order in active_orders:
            results["checked"] += 1
            order_id = order["order_id"]
            status = order.get("status")
            
            # Skip SLA-paused orders
            if status in [s.value for s in SLA_PAUSED_STATES]:
                results["paused_skipped"] += 1
                continue
            
            # Get service-specific SLA configuration
            sla_config = get_sla_hours_for_order(order)
            target_hours = sla_config["target_hours"]
            warning_threshold = sla_config["warning_threshold"]
            
            # Calculate effective time (excluding pause duration)
            # SLA clock starts at PAID, not created_at
            sla_start = order.get("paid_at") or order.get("created_at")
            if isinstance(sla_start, str):
                sla_start = datetime.fromisoformat(sla_start.replace("Z", "+00:00"))
            
            pause_duration = order.get("sla_pause_duration_hours", 0)
            effective_hours = ((now - sla_start).total_seconds() / 3600) - pause_duration
            
            # Check for existing SLA flags
            sla_warning_sent = order.get("sla_warning_sent", False)
            sla_breach_sent = order.get("sla_breach_sent", False)
            
            # Check for warning (75% of SLA)
            warning_hours = target_hours * warning_threshold
            if effective_hours >= warning_hours and not sla_warning_sent and effective_hours < target_hours:
                # Send warning
                try:
                    notif_service = self._get_notification_service()
                    hours_remaining = target_hours - effective_hours
                    await notif_service.notify_sla_warning(
                        order_id=order_id,
                        hours_remaining=hours_remaining,
                        order=order,
                    )
                    
                    await db.orders.update_one(
                        {"order_id": order_id},
                        {"$set": {"sla_warning_sent": True, "sla_warning_at": now}}
                    )
                    
                    # Log SLA warning event
                    await log_sla_event(order_id, "SLA_WARNING_ISSUED", {
                        "hours_remaining": hours_remaining,
                        "target_hours": target_hours,
                        "effective_hours": effective_hours,
                        "service_code": order.get("service_code"),
                    })
                    
                    results["warnings_sent"] += 1
                    logger.info(f"WF9: SLA warning sent for {order_id} ({hours_remaining:.1f}h remaining)")
                except Exception as e:
                    logger.error(f"WF9: Failed to send SLA warning for {order_id}: {e}")
            
            # Check for breach (100% of SLA)
            if effective_hours >= target_hours and not sla_breach_sent:
                # Send breach
                try:
                    notif_service = self._get_notification_service()
                    hours_overdue = effective_hours - target_hours
                    await notif_service.notify_sla_breach(
                        order_id=order_id,
                        hours_overdue=hours_overdue,
                        order=order,
                    )
                    
                    await db.orders.update_one(
                        {"order_id": order_id},
                        {"$set": {"sla_breach_sent": True, "sla_breach_at": now}}
                    )
                    
                    # Log SLA breach event
                    await log_sla_event(order_id, "SLA_BREACHED", {
                        "hours_overdue": hours_overdue,
                        "target_hours": target_hours,
                        "effective_hours": effective_hours,
                        "service_code": order.get("service_code"),
                    })
                    
                    results["breaches_sent"] += 1
                    logger.warning(f"WF9: SLA BREACH for {order_id} ({hours_overdue:.1f}h overdue)")
                except Exception as e:
                    logger.error(f"WF9: Failed to send SLA breach for {order_id}: {e}")
        
        logger.info(
            f"WF9: SLA check complete - {results['checked']} orders checked, "
            f"{results['warnings_sent']} warnings, {results['breaches_sent']} breaches"
        )
        
        return {"success": True, "workflow": "WF9", "results": results}
    
    # =========================================================================
    # WF10: Priority Order → Expedited Processing
    # =========================================================================
    
    async def wf10_expedite_priority(self) -> Dict[str, Any]:
        """
        WF10: Process priority orders ahead of standard queue.
        
        Trigger: Scheduled job or manual trigger
        Action: Process priority QUEUED orders first
        """
        db = database.get_db()
        
        # Get all priority orders in QUEUED status
        priority_orders = await db.orders.find({
            "status": OrderStatus.QUEUED.value,
            "$or": [
                {"priority": True},
                {"fast_track": True},
            ]
        }).sort("created_at", 1).to_list(length=50)
        
        results = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
        }
        
        for order in priority_orders:
            order_id = order["order_id"]
            results["processed"] += 1
            
            try:
                result = await self.wf2_queue_to_generation(order_id)
                
                if result.get("success"):
                    # Also run WF3 to move to review
                    await self.wf3_draft_to_review(order_id)
                    results["succeeded"] += 1
                else:
                    results["failed"] += 1
                    
            except Exception as e:
                logger.error(f"WF10: Failed to process priority order {order_id}: {e}")
                results["failed"] += 1
        
        logger.info(
            f"WF10: Priority processing complete - {results['processed']} orders, "
            f"{results['succeeded']} succeeded, {results['failed']} failed"
        )
        
        return {"success": True, "workflow": "WF10", "results": results}
    
    # =========================================================================
    # BATCH PROCESSING
    # =========================================================================
    
    async def process_queued_orders(self, limit: int = 10) -> Dict[str, Any]:
        """
        Process queued orders in priority order.
        Called by background job.
        
        Priority ordering:
        1. queue_priority (higher = first) - Fast-track=5, Priority=10
        2. fast_track flag
        3. priority flag  
        4. created_at (oldest first)
        """
        db = database.get_db()
        
        # Get QUEUED orders, sorted by priority
        queued_orders = await db.orders.find({
            "status": OrderStatus.QUEUED.value,
        }).sort([
            ("queue_priority", -1),  # Higher priority first
            ("priority", -1),        # Then priority flag
            ("fast_track", -1),      # Then fast-track flag
            ("created_at", 1),       # Then oldest first
        ]).limit(limit).to_list(length=limit)
        
        results = {
            "processed": 0,
            "to_review": 0,
            "failed": 0,
            "fast_track_processed": 0,
        }
        
        for order in queued_orders:
            order_id = order["order_id"]
            is_expedited = order.get("expedited", False) or order.get("fast_track", False)
            results["processed"] += 1
            
            try:
                # WF2: Generate documents
                gen_result = await self.wf2_queue_to_generation(order_id)
                
                if gen_result.get("success"):
                    # WF3: Move to review
                    review_result = await self.wf3_draft_to_review(order_id)
                    if review_result.get("success"):
                        results["to_review"] += 1
                        if is_expedited:
                            results["fast_track_processed"] += 1
                    else:
                        results["failed"] += 1
                else:
                    results["failed"] += 1
                    
            except Exception as e:
                logger.error(f"Batch processing error for {order_id}: {e}")
                results["failed"] += 1
        
        return {"success": True, "results": results}


# Singleton instance
workflow_automation_service = WorkflowAutomationService()
