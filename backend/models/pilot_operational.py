"""Pilot operational maturity — separated lifecycle domains, health, anomalies."""
from __future__ import annotations

from enum import Enum


class PilotGovernanceStatus(str, Enum):
    """Platform governance authority (pilot_lifecycle_service)."""

    ACTIVE = "active"
    EXTENDED = "extended"
    EXPIRED = "expired"
    CONVERTED = "converted"
    CANCELLED = "cancelled"
    COMPED = "comped"
    PAUSED = "paused"


class PilotBillingStatus(str, Enum):
    """Stripe billing authority (subscription_status + lifecycle)."""

    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    CANCELLED = "cancelled"
    INCOMPLETE = "incomplete"
    NONE = "none"


class PilotEntitlementStatus(str, Enum):
    """Portal entitlement engine (mapped from canonical_entitlement_state)."""

    ENABLED = "enabled"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    GRACE_PERIOD = "grace_period"


class PilotHealthBand(str, Enum):
    HEALTHY = "healthy"
    AT_RISK = "at_risk"
    INACTIVE = "inactive"
    CONVERSION_READY = "conversion_ready"


class PilotAnomalySeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class PilotAnomalyCode(str, Enum):
    EXPIRED_PILOT_ACTIVE_PAID_SUB = "expired_pilot_active_paid_sub"
    CONVERTED_WITHOUT_PAYMENT_METHOD = "converted_without_payment_method"
    COMPED_CANCELLED_SUBSCRIPTION = "comped_cancelled_subscription"
    ENTITLEMENT_WITHOUT_BILLING_BASIS = "entitlement_without_billing_basis"
    GOVERNANCE_BILLING_MISMATCH = "governance_billing_mismatch"
    MISSING_PAYMENT_METHOD_NEAR_CONVERSION = "missing_payment_method_near_conversion"
    MULTIPLE_EXTENSIONS = "multiple_extensions"
    EXCESSIVE_COMP_DURATION = "excessive_comp_duration"
    PILOT_BEYOND_MAX_GOVERNANCE_DURATION = "pilot_beyond_max_governance_duration"
    INVALID_STATE_COMBINATION = "invalid_state_combination"
    PILOT_EXPIRED_WITHOUT_CONVERSION = "pilot_expired_without_conversion"
    COMP_REVIEW_OVERDUE = "comp_review_overdue"


# Max pilot governance window (months from start) before anomaly
DEFAULT_MAX_PILOT_GOVERNANCE_MONTHS = 24
# Comp without review expiry longer than this triggers warning
DEFAULT_MAX_COMP_DAYS_WITHOUT_REVIEW = 365
