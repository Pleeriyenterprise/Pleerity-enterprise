"""
Account Customer Communication Authority (ILP-8).

Single decision point for account-level customer communication eligibility,
channel selection, lifecycle messaging, CTAs, and suppression.

Consumes Runtime Contract communication_policy only — never infers from
subscription_status, plan, billing state, or feature flags directly.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional

from services.account_lifecycle_runtime_contract import (
    CONTRACT_VERSION,
    resolve_runtime_contract_for_client,
)

logger = logging.getLogger(__name__)

POLICY_VERSION = "account_customer_communication_v1"

# Template / event → communication_policy key
_COMM_CATEGORY_BY_TEMPLATE: Dict[str, str] = {
    "SUBSCRIPTION_GRACE_REMINDER": "email_billing",
    "SUBSCRIPTION_RENEWAL_7D": "email_billing",
    "SUBSCRIPTION_RENEWAL_3D": "email_billing",
}

_COMM_CATEGORY_BY_EMAIL_CATEGORY: Dict[str, str] = {
    "billing": "email_billing",
    "subscription": "email_billing",
    "compliance": "email_operational",
    "compliance_notification": "email_operational",
    "operational": "email_operational",
    "digest": "email_operational",
    "report": "email_operational",
    "maintenance": "email_operational",
    "tenant": "email_operational",
    "support": "email_operational",
}


class CommunicationSeverity(str, Enum):
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    CRITICAL = "critical"


class CommunicationSurface(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"
    PUSH = "push"
    PORTAL_BANNER = "portal_banner"
    DASHBOARD_NOTICE = "dashboard_notice"
    DIGEST = "digest"
    REPORT = "report"


@dataclass(frozen=True)
class CommunicationDecision:
    allowed: bool
    suppressed: bool
    client_id: str
    lifecycle_state: str
    portal_mode: str
    surface: str
    channel_policy_key: str
    communication_category: str
    message: str
    severity: str
    tone: str
    cta_label: Optional[str] = None
    cta_route: Optional[str] = None
    recovery_journey_id: Optional[str] = None
    template_family: Optional[str] = None
    template_context: Dict[str, Any] = field(default_factory=dict)
    suppression_reason: Optional[str] = None
    fallback_channel: Optional[str] = None
    priority: str = "normal"
    runtime_version: Optional[Any] = None
    contract_version: str = CONTRACT_VERSION
    policy_version: str = POLICY_VERSION
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "suppressed": self.suppressed,
            "client_id": self.client_id,
            "lifecycle_state": self.lifecycle_state,
            "portal_mode": self.portal_mode,
            "surface": self.surface,
            "channel_policy_key": self.channel_policy_key,
            "communication_category": self.communication_category,
            "message": self.message,
            "severity": self.severity,
            "tone": self.tone,
            "cta_label": self.cta_label,
            "cta_route": self.cta_route,
            "recovery_journey_id": self.recovery_journey_id,
            "template_family": self.template_family,
            "template_context": dict(self.template_context),
            "suppression_reason": self.suppression_reason,
            "fallback_channel": self.fallback_channel,
            "priority": self.priority,
            "runtime_version": self.runtime_version,
            "contract_version": self.contract_version,
            "policy_version": self.policy_version,
            "reason": self.reason,
        }


def _severity_for_lifecycle(lifecycle_state: str, portal_mode: str) -> str:
    ls = str(lifecycle_state or "UNKNOWN").upper()
    pm = str(portal_mode or "")
    if ls in ("ACCOUNT_DELETED", "ARCHIVED"):
        return CommunicationSeverity.CRITICAL.value
    if ls in ("SUSPENDED", "CANCELLED_IMMEDIATE", "SUBSCRIPTION_EXPIRED"):
        return CommunicationSeverity.WARNING.value
    if ls in ("GRACE_PERIOD", "PAYMENT_FAILED") or pm == "GRACE":
        return CommunicationSeverity.WARNING.value
    if ls == "READ_ONLY" or pm == "READ_ONLY":
        return CommunicationSeverity.NOTICE.value
    if ls == "UNKNOWN":
        return CommunicationSeverity.WARNING.value
    return CommunicationSeverity.INFO.value


def _tone_for_lifecycle(lifecycle_state: str, portal_mode: str) -> str:
    pm = str(portal_mode or "")
    if pm in ("BILLING_RECOVERY", "PAYMENT_REQUIRED", "SUSPENDED"):
        return "recovery"
    if pm == "READ_ONLY":
        return "retention"
    if pm == "GRACE":
        return "urgency"
    return "operational"


def _recovery_journey_id(lifecycle_state: str, portal_mode: str) -> Optional[str]:
    ls = str(lifecycle_state or "").upper()
    pm = str(portal_mode or "")
    if pm in ("BILLING_RECOVERY", "PAYMENT_REQUIRED") or ls in (
        "CANCELLED_IMMEDIATE",
        "SUBSCRIPTION_EXPIRED",
        "GRACE_PERIOD",
    ):
        return "complete_payment"
    if ls == "READ_ONLY" or pm == "READ_ONLY":
        return "reactivate_account"
    if ls == "SUSPENDED" or pm == "SUSPENDED":
        return "contact_support"
    if ls in ("ARCHIVED", "ACCOUNT_DELETED"):
        return "contact_support"
    if ls == "CANCELLATION_SCHEDULED":
        return "undo_scheduled_cancellation"
    return None


def _resolve_comm_category(
    *,
    surface: str,
    channel: str,
    template_key: Optional[str],
    template: Optional[Mapping[str, Any]],
    event_type: Optional[str],
) -> str:
    key = str(template_key or "").upper()
    if key in _COMM_CATEGORY_BY_TEMPLATE:
        return _COMM_CATEGORY_BY_TEMPLATE[key]

    template = template or {}
    email_cat = str(template.get("email_category") or "").lower()
    if email_cat in _COMM_CATEGORY_BY_EMAIL_CATEGORY:
        return _COMM_CATEGORY_BY_EMAIL_CATEGORY[email_cat]

    evt = str(event_type or "").lower()
    if any(x in evt for x in ("renewal", "grace", "subscription", "billing", "invoice")):
        return "email_billing"
    if any(x in evt for x in ("digest", "report", "compliance", "reminder", "maintenance", "tenant")):
        return "email_operational"

    ch = str(channel or surface or "").lower()
    if ch == "sms":
        return "sms"
    if ch in ("in_app", "push", "portal_banner", "dashboard_notice"):
        return "portal_notifications"
    return "email_operational"


def _channel_policy_key(communication_category: str, channel: str) -> str:
    cat = str(communication_category or "")
    if cat == "sms":
        return "sms"
    if cat == "email_billing":
        return "email_billing"
    if cat in ("portal_notifications", "in_app", "push"):
        return "portal_notifications"
    return "email_operational"


def _surface_from_channel(channel: str) -> str:
    ch = str(channel or "email").lower()
    if ch == "sms":
        return CommunicationSurface.SMS.value
    if ch == "in_app":
        return CommunicationSurface.IN_APP.value
    if ch == "push":
        return CommunicationSurface.PUSH.value
    return CommunicationSurface.EMAIL.value


def _suppression_reason(
    *,
    lifecycle_state: str,
    portal_mode: str,
    communication_category: str,
    comm_policy: Mapping[str, Any],
    channel_allowed: bool,
) -> Optional[str]:
    ls = str(lifecycle_state or "").upper()
    pm = str(portal_mode or "")

    if ls == "ACCOUNT_DELETED":
        if communication_category != "email_billing":
            return "account_deleted_no_operational_comms"
    if ls == "ARCHIVED" and communication_category == "email_operational":
        return "archived_no_operational_comms"

    if pm in ("BILLING_RECOVERY", "PAYMENT_REQUIRED") and communication_category == "email_operational":
        return "billing_recovery_suppress_operational_spam"

    if pm == "SUSPENDED" and communication_category == "email_operational":
        return "suspended_suppress_operational_comms"

    if not channel_allowed:
        return f"communication_policy_{communication_category}_denied"

    return None


def _build_template_context(
    contract: Mapping[str, Any],
    decision_message: str,
    cta_label: Optional[str],
    cta_route: Optional[str],
) -> Dict[str, Any]:
    cx = dict(contract.get("customer_experience") or {})
    primary = cx.get("primary_cta") or {}
    return {
        "lifecycle_message": decision_message or cx.get("explanation") or cx.get("heading") or "",
        "lifecycle_cta": cta_label or primary.get("label") or "",
        "lifecycle_status": cx.get("current_state_label") or contract.get("lifecycle_state"),
        "recovery_url": cta_route or primary.get("route") or "",
        "portal_mode": contract.get("portal_mode"),
        "lifecycle_state": contract.get("lifecycle_state"),
        "template_family": (contract.get("communication_policy") or {}).get("template_family"),
    }


class CustomerCommunicationAuthority:
    """Evaluate governed customer communication from Runtime Contract."""

    @staticmethod
    def from_contract(
        contract: Mapping[str, Any],
        *,
        client_id: str,
        surface: str = "notification",
        channel: str = "email",
        template_key: Optional[str] = None,
        template: Optional[Mapping[str, Any]] = None,
        event_type: Optional[str] = None,
    ) -> CommunicationDecision:
        lifecycle_state = str(contract.get("lifecycle_state") or "UNKNOWN")
        portal_mode = str(contract.get("portal_mode") or "FULL_ACCESS")
        comm_policy = dict(contract.get("communication_policy") or {})
        cx = dict(contract.get("customer_experience") or {})
        primary = cx.get("primary_cta") or {}

        communication_category = _resolve_comm_category(
            surface=surface,
            channel=channel,
            template_key=template_key,
            template=template,
            event_type=event_type,
        )
        policy_key = _channel_policy_key(communication_category, channel)
        channel_allowed = bool(comm_policy.get(policy_key, False))

        message = str(
            cx.get("explanation") or cx.get("heading") or cx.get("current_state_label") or ""
        ).strip()
        cta_label = primary.get("label")
        cta_route = primary.get("route")
        journey_id = _recovery_journey_id(lifecycle_state, portal_mode)
        template_family = comm_policy.get("template_family")
        severity = _severity_for_lifecycle(lifecycle_state, portal_mode)
        tone = _tone_for_lifecycle(lifecycle_state, portal_mode)

        suppression = _suppression_reason(
            lifecycle_state=lifecycle_state,
            portal_mode=portal_mode,
            communication_category=communication_category,
            comm_policy=comm_policy,
            channel_allowed=channel_allowed,
        )

        allowed = suppression is None
        template_context = _build_template_context(contract, message, cta_label, cta_route)

        fallback = None
        if not allowed and communication_category == "email_operational" and comm_policy.get("email_billing"):
            fallback = "email_billing"

        priority = "high" if severity in (CommunicationSeverity.WARNING.value, CommunicationSeverity.CRITICAL.value) else "normal"

        return CommunicationDecision(
            allowed=allowed,
            suppressed=not allowed,
            client_id=client_id,
            lifecycle_state=lifecycle_state,
            portal_mode=portal_mode,
            surface=_surface_from_channel(channel) if surface == "notification" else surface,
            channel_policy_key=policy_key,
            communication_category=communication_category,
            message=message,
            severity=severity,
            tone=tone,
            cta_label=cta_label,
            cta_route=cta_route,
            recovery_journey_id=journey_id,
            template_family=template_family,
            template_context=template_context,
            suppression_reason=suppression,
            fallback_channel=fallback,
            priority=priority,
            runtime_version=contract.get("runtime_version"),
            reason=suppression or "communication_allowed",
        )


async def evaluate_customer_communication(
    db,
    client_id: str,
    *,
    surface: str = "notification",
    channel: str = "email",
    template_key: Optional[str] = None,
    template: Optional[Mapping[str, Any]] = None,
    event_type: Optional[str] = None,
    contract: Optional[Mapping[str, Any]] = None,
) -> CommunicationDecision:
    if contract is None:
        contract = await resolve_runtime_contract_for_client(db, client_id)
    decision = CustomerCommunicationAuthority.from_contract(
        contract,
        client_id=client_id,
        surface=surface,
        channel=channel,
        template_key=template_key,
        template=template,
        event_type=event_type,
    )
    log_communication_decision(decision, template_key=template_key, event_type=event_type)
    return decision


def enrich_context_with_lifecycle_placeholders(
    context: Optional[Mapping[str, Any]],
    decision: CommunicationDecision,
) -> Dict[str, Any]:
    """Merge governed lifecycle placeholders into template context without overwriting caller keys."""
    out = dict(context or {})
    for key, value in (decision.template_context or {}).items():
        if key not in out or out[key] in (None, ""):
            out[key] = value
    return out


def log_communication_decision(
    decision: CommunicationDecision,
    *,
    template_key: Optional[str] = None,
    event_type: Optional[str] = None,
) -> None:
    if decision.allowed:
        logger.info(
            "customer_communication_allowed client_id=%s surface=%s category=%s lifecycle=%s "
            "channel_key=%s runtime_version=%s template_key=%s event_type=%s policy=%s",
            decision.client_id,
            decision.surface,
            decision.communication_category,
            decision.lifecycle_state,
            decision.channel_policy_key,
            decision.runtime_version,
            template_key or "-",
            event_type or "-",
            POLICY_VERSION,
        )
    else:
        logger.info(
            "customer_communication_suppressed client_id=%s surface=%s category=%s lifecycle=%s "
            "suppression=%s runtime_version=%s template_key=%s policy=%s",
            decision.client_id,
            decision.surface,
            decision.communication_category,
            decision.lifecycle_state,
            decision.suppression_reason,
            decision.runtime_version,
            template_key or "-",
            POLICY_VERSION,
        )
