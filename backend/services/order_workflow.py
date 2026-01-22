"""
Order Workflow State Machine
Defines all valid states, transitions, and business rules for the Orders system.
This is the single source of truth for order workflow logic.

NOTE: CVP ISOLATION - This file handles NON-CVP services only.
Orders do NOT write to any CVP collections.
"""
from enum import Enum
from typing import List, Dict, Optional, Set
from datetime import datetime, timezone


class OrderStatus(str, Enum):
    """
    Order workflow states - 14 states total (including DELIVERY_FAILED)
    """
    # Payment & Intake
    CREATED = "CREATED"                       # Order record created, pending payment
    PAID = "PAID"                             # Payment confirmed, ref generated
    
    # Execution
    QUEUED = "QUEUED"                         # Ready to execute, waiting worker
    IN_PROGRESS = "IN_PROGRESS"               # Generation/execution running
    DRAFT_READY = "DRAFT_READY"               # Draft produced and stored
    INTERNAL_REVIEW = "INTERNAL_REVIEW"       # Human gate starts here
    
    # Review outcomes
    REGEN_REQUESTED = "REGEN_REQUESTED"       # Review notes captured
    REGENERATING = "REGENERATING"             # System regenerating
    CLIENT_INPUT_REQUIRED = "CLIENT_INPUT_REQUIRED"  # Paused; SLA paused
    FINALISING = "FINALISING"                 # Approved, final assembly running
    DELIVERING = "DELIVERING"                 # Email send in progress
    
    # Terminal
    COMPLETED = "COMPLETED"                   # Delivered successfully
    DELIVERY_FAILED = "DELIVERY_FAILED"       # Delivery failed (email rejected/bounced)
    FAILED = "FAILED"                         # Blocked error state
    CANCELLED = "CANCELLED"                   # Admin only


class TransitionType(str, Enum):
    """Types of state transitions"""
    SYSTEM = "system"                         # Automatic system transition
    ADMIN_MANUAL = "admin_manual"             # Admin manual action
    CUSTOMER_ACTION = "customer_action"       # Customer response


# Valid state transitions - whitelist approach
ALLOWED_TRANSITIONS: Dict[OrderStatus, List[OrderStatus]] = {
    OrderStatus.CREATED: [OrderStatus.PAID, OrderStatus.CANCELLED],
    OrderStatus.PAID: [OrderStatus.QUEUED, OrderStatus.CANCELLED],
    OrderStatus.QUEUED: [OrderStatus.IN_PROGRESS, OrderStatus.CANCELLED],
    OrderStatus.IN_PROGRESS: [OrderStatus.DRAFT_READY, OrderStatus.FAILED],
    OrderStatus.DRAFT_READY: [OrderStatus.INTERNAL_REVIEW],
    OrderStatus.INTERNAL_REVIEW: [
        OrderStatus.FINALISING,           # Approve
        OrderStatus.REGEN_REQUESTED,      # Request regen
        OrderStatus.CLIENT_INPUT_REQUIRED,  # Request info
        OrderStatus.CANCELLED,
    ],
    OrderStatus.REGEN_REQUESTED: [OrderStatus.REGENERATING],
    OrderStatus.REGENERATING: [OrderStatus.INTERNAL_REVIEW, OrderStatus.FAILED],
    OrderStatus.CLIENT_INPUT_REQUIRED: [OrderStatus.INTERNAL_REVIEW],
    OrderStatus.FINALISING: [OrderStatus.DELIVERING, OrderStatus.FAILED],
    OrderStatus.DELIVERING: [OrderStatus.COMPLETED, OrderStatus.DELIVERY_FAILED],
    # Terminal states
    OrderStatus.COMPLETED: [],
    OrderStatus.DELIVERY_FAILED: [OrderStatus.DELIVERING, OrderStatus.FAILED],  # Retry or escalate
    OrderStatus.FAILED: [OrderStatus.QUEUED],  # Admin can re-queue
    OrderStatus.CANCELLED: [],
}


# Transitions that require admin action (human gate)
ADMIN_ONLY_TRANSITIONS: Set[tuple] = {
    (OrderStatus.INTERNAL_REVIEW, OrderStatus.FINALISING),       # Approve
    (OrderStatus.INTERNAL_REVIEW, OrderStatus.REGEN_REQUESTED),  # Request regen
    (OrderStatus.INTERNAL_REVIEW, OrderStatus.CLIENT_INPUT_REQUIRED),  # Request info
    (OrderStatus.FAILED, OrderStatus.QUEUED),                    # Re-queue failed
    (OrderStatus.DELIVERY_FAILED, OrderStatus.DELIVERING),       # Retry delivery
}


# Transitions that can cancel from any non-terminal state
CANCELLABLE_STATES: Set[OrderStatus] = {
    OrderStatus.CREATED,
    OrderStatus.PAID,
    OrderStatus.QUEUED,
    OrderStatus.INTERNAL_REVIEW,
}


# States where SLA timer is paused
SLA_PAUSED_STATES: Set[OrderStatus] = {
    OrderStatus.CLIENT_INPUT_REQUIRED,
}


# Terminal states - no further transitions possible
TERMINAL_STATES: Set[OrderStatus] = {
    OrderStatus.COMPLETED,
    OrderStatus.CANCELLED,
}


# States that require admin notification
ADMIN_NOTIFICATION_STATES: Set[OrderStatus] = {
    OrderStatus.INTERNAL_REVIEW,  # Human review needed
    OrderStatus.FAILED,           # Error needs attention
    OrderStatus.DELIVERY_FAILED,  # Delivery failed
}


# System-driven transitions (no human intervention)
SYSTEM_DRIVEN_STATES: Set[OrderStatus] = {
    OrderStatus.CREATED,
    OrderStatus.PAID,
    OrderStatus.QUEUED,
    OrderStatus.IN_PROGRESS,
    OrderStatus.DRAFT_READY,
    OrderStatus.REGENERATING,
    OrderStatus.FINALISING,
    OrderStatus.DELIVERING,
}


def is_valid_transition(from_status: OrderStatus, to_status: OrderStatus) -> bool:
    """Check if a state transition is valid"""
    if from_status not in ALLOWED_TRANSITIONS:
        return False
    return to_status in ALLOWED_TRANSITIONS[from_status]


def requires_admin_action(from_status: OrderStatus, to_status: OrderStatus) -> bool:
    """Check if a transition requires admin manual action"""
    return (from_status, to_status) in ADMIN_ONLY_TRANSITIONS


def is_terminal_state(status: OrderStatus) -> bool:
    """Check if a status is terminal (no further transitions)"""
    return status in TERMINAL_STATES


def requires_admin_notification(status: OrderStatus) -> bool:
    """Check if entering this status should notify admin"""
    return status in ADMIN_NOTIFICATION_STATES


def is_sla_paused(status: OrderStatus) -> bool:
    """Check if SLA timer should be paused in this status"""
    return status in SLA_PAUSED_STATES


def get_allowed_transitions(status: OrderStatus) -> List[OrderStatus]:
    """Get list of valid next states from current status"""
    return ALLOWED_TRANSITIONS.get(status, [])


def get_admin_actions_for_review() -> Dict[str, OrderStatus]:
    """Get the three admin actions available at INTERNAL_REVIEW"""
    return {
        "approve": OrderStatus.FINALISING,
        "regen": OrderStatus.REGEN_REQUESTED,
        "request_info": OrderStatus.CLIENT_INPUT_REQUIRED,
    }


# Pipeline columns for admin dashboard (in display order)
PIPELINE_COLUMNS: List[Dict] = [
    {"status": OrderStatus.PAID, "label": "Paid", "color": "blue"},
    {"status": OrderStatus.QUEUED, "label": "Queued", "color": "gray"},
    {"status": OrderStatus.IN_PROGRESS, "label": "In Progress", "color": "yellow"},
    {"status": OrderStatus.DRAFT_READY, "label": "Draft Ready", "color": "purple"},
    {"status": OrderStatus.INTERNAL_REVIEW, "label": "Review", "color": "orange"},
    {"status": OrderStatus.CLIENT_INPUT_REQUIRED, "label": "Awaiting Client", "color": "pink"},
    {"status": OrderStatus.FINALISING, "label": "Finalising", "color": "teal"},
    {"status": OrderStatus.DELIVERING, "label": "Delivering", "color": "cyan"},
    {"status": OrderStatus.COMPLETED, "label": "Completed", "color": "green"},
    {"status": OrderStatus.DELIVERY_FAILED, "label": "Delivery Failed", "color": "red"},
    {"status": OrderStatus.FAILED, "label": "Failed", "color": "red"},
]


# Service categories
class ServiceCategory(str, Enum):
    RESEARCH = "research"
    DOCUMENTS = "documents"
    AUDIT = "audit"
    CLEANING = "cleaning"
    WORKFLOW = "workflow"


# Service codes
class ServiceCode(str, Enum):
    AI_WORKFLOW = "AI_WORKFLOW"
    MARKET_RESEARCH = "MARKET_RESEARCH"
    DOC_PACK_TENANCY = "DOC_PACK_TENANCY"
    DOC_PACK_INVENTORY = "DOC_PACK_INVENTORY"
    AUDIT_HMO = "AUDIT_HMO"
    AUDIT_FULL = "AUDIT_FULL"
    CLEANING_EOT = "CLEANING_EOT"
    CLEANING_DEEP = "CLEANING_DEEP"
    CLEANING_REGULAR = "CLEANING_REGULAR"
